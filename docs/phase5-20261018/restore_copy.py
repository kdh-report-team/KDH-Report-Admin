"""Restore encrypted Phase 5 archives into NEW isolated volumes; never original DB.

No application/Store/create_app is imported. SQL uses read-only transactions.
No credentials, tokens, cookie values or raw query results are logged.
Retains stopped clone and helpers. Requires the same Windows DPAPI user.
"""
import io
import json
import os
import sys
import tarfile
import time
from pathlib import Path

from cryptography.fernet import Fernet
from cold_backup import HERE, LABEL, RUN, digest, docker, dpapi, inspect, original_gate

EXTRACT = r'''
import io, pathlib, sys, tarfile
with tarfile.open(fileobj=io.BytesIO(sys.stdin.buffer.read()), mode='r:') as archive:
    for item in archive.getmembers():
        path = pathlib.PurePosixPath(item.name)
        assert path.parts[0] == 'data' and '..' not in path.parts
        assert item.isfile() or item.isdir()
    archive.extractall('/restore', filter='fully_trusted')
'''
VERIFY = r'''
import hashlib, json, pathlib, stat
root = pathlib.Path('/restore')
result = {}
for path in sorted(root.rglob('*')):
    assert not path.is_symlink()
    info = path.stat()
    result[str(path.relative_to(root))] = [stat.S_IMODE(info.st_mode), info.st_uid, info.st_gid,
        hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None]
print(json.dumps(result, sort_keys=True))
'''


def archive_manifest(data):
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:") as archive:
        return {m.name: [m.mode, m.uid, m.gid, digest(archive.extractfile(m).read()) if m.isfile() else None]
                for m in archive.getmembers()}


def helper(name, volume, image, prefix, script, data=None, readonly=False):
    mount = "type=volume,src=" + volume + ",dst=/restore,volume-nocopy" + (",readonly" if readonly else "")
    container_id = docker("create", "-i", "--name", name, "--label", LABEL + "=" + prefix,
        "--network", "none", "--read-only", "--log-driver", "none", "--user", "0:0",
        "--cap-drop", "ALL", "--cap-add", "DAC_OVERRIDE", "--cap-add", "CHOWN", "--cap-add", "FOWNER",
        "--security-opt", "no-new-privileges", "--memory", "256m", "--cpus", "0.5",
        "--mount", mount, "--entrypoint", "python", image, "-B", "-c", script).decode().strip()
    info = inspect(container_id)
    assert len(info["Mounts"]) == 1 and info["Mounts"][0]["Name"] == volume
    assert info["HostConfig"]["NetworkMode"] == "none"
    result = docker("start", "-ai", container_id, data=data)
    assert inspect(container_id)["State"]["ExitCode"] == 0
    return result


def main():
    assert sys.argv[1:] == ["--execute"]
    assert not (HERE / "restore-result.json").exists()
    backup = json.loads((HERE / "backup-result.json").read_text())
    assert backup["status"] == "PASS"
    baseline = json.loads((HERE / "runtime-baseline.json").read_text(encoding="utf-8-sig"))
    originals = original_gate(baseline)
    pg = next(x for x in originals if "-pg-" in x["Name"])
    admin = next(x for x in originals if "-admin-" in x["Name"])
    prefix = backup["test_prefix"]
    private = Path(backup["private_backup_directory"])
    cipher = Fernet(dpapi((private / "backup-key.dpapi").read_bytes(), decrypt=True))
    evidence = {"test_prefix": prefix, "network": "none", "host_ports": [], "volumes": {}, "read_only_sql": True}
    clone_id = None
    try:
        for kind, entry in backup["archives"].items():
            data = cipher.decrypt((private / entry["file"]).read_bytes())
            assert digest(data) == entry["archive_sha256"]
            volume = prefix + "-" + kind + "-restore"
            assert volume not in docker("volume", "ls", "-q").decode().splitlines()
            docker("volume", "create", "--label", LABEL + "=" + prefix, volume)
            assert json.loads(docker("volume", "inspect", volume))[0]["Labels"][LABEL] == prefix
            helper(prefix + "-" + kind + "-extract", volume, admin["Image"], prefix, EXTRACT, data)
            restored = json.loads(helper(prefix + "-" + kind + "-verify", volume, admin["Image"], prefix, VERIFY, readonly=True))
            assert restored == archive_manifest(data)
            evidence["volumes"][kind] = {"name": volume, "file_bytes_ownership_modes_match": True,
                "entries": len(restored), "manifest_sha256": digest(json.dumps(restored, sort_keys=True).encode())}
            print(kind + ": RESTORE FILE INTEGRITY PASS", flush=True)
        pg_volume = evidence["volumes"]["postgres"]["name"]
        helper(prefix + "-clone-pid", pg_volume, admin["Image"], prefix,
               "from pathlib import Path; Path('/restore/data/postmaster.pid').unlink(missing_ok=True)")
        clone_id = docker("create", "--name", prefix + "-pg-restore", "--label", LABEL + "=" + prefix,
            "--network", "none", "--read-only", "--log-driver", "none", "--user", "999:999",
            "--cap-drop", "ALL", "--security-opt", "no-new-privileges", "--memory", "512m", "--cpus", "1",
            "--tmpfs", "/tmp:rw,nosuid,nodev,noexec,size=64m,mode=1777",
            "--mount", "type=volume,src=" + pg_volume + ",dst=/var/lib/postgresql/data,volume-nocopy",
            "--entrypoint", "postgres", pg["Image"], "-D", "/var/lib/postgresql/data/data",
            "-c", "listen_addresses=", "-c", "unix_socket_directories=/tmp",
            "-c", "default_transaction_read_only=on").decode().strip()
        evidence["container_id"] = clone_id
        evidence["container_name"] = prefix + "-pg-restore"
        info = inspect(clone_id)
        assert info["HostConfig"]["NetworkMode"] == "none" and not info["HostConfig"]["PortBindings"]
        assert len(info["Mounts"]) == 1 and info["Mounts"][0]["Name"] == pg_volume
        docker("start", clone_id)
        for _ in range(30):
            try:
                docker("exec", clone_id, "pg_isready", "-h", "/tmp")
                break
            except RuntimeError:
                if not inspect(clone_id)["State"]["Running"]:
                    raise RuntimeError("restore copy stopped")
                time.sleep(1)
        else:
            raise RuntimeError("restore copy readiness timed out")
        pg_env = dict(x.split("=", 1) for x in pg["Config"]["Env"])
        admin_env = dict(x.split("=", 1) for x in admin["Config"]["Env"])
        database = "meta_acceptance_20261016_132836"

        def sql(query):
            statement = "BEGIN READ ONLY; " + query + "; COMMIT;"
            return docker("exec", "-i", clone_id, "psql", "-X", "-qAt", "-v", "ON_ERROR_STOP=1",
                "-h", "/tmp", "-U", pg_env["POSTGRES_USER"], "-d", database, data=statement.encode()).decode().strip()

        def rows(query):
            return json.loads(sql("SELECT coalesce(json_agg(t),'[]'::json) FROM (" + query + ") t"))

        assert sql("SHOW transaction_read_only") == "on"
        evidence["version"] = sql("SHOW server_version")
        evidence["database"] = sql("SELECT current_database()")
        evidence["data_checksums"] = sql("SHOW data_checksums")
        evidence["migrations"] = rows("SELECT version,name,applied_at FROM schema_migrations ORDER BY version")
        evidence["connections"] = rows("SELECT id,client_id,provider,status FROM connections ORDER BY id")
        evidence["assets"] = rows("SELECT id,client_id,provider,asset_type,external_id,name,enabled FROM source_assets ORDER BY id")
        evidence["sync_runs"] = rows("SELECT id,client_id,asset_id,provider,status,requested_start,requested_end,record_count,job_id,started_at,finished_at FROM sync_runs ORDER BY created_at")
        evidence["snapshots"] = rows("SELECT id,sync_run_id,client_id,asset_id,source_key,requested_start,requested_end,created_at FROM source_snapshots ORDER BY id")
        evidence["metric_groups"] = rows("SELECT client_id,asset_id,provider,entity_type,count(*) AS rows,count(DISTINCT entity_id) AS entities,min(metric_date) AS first_date,max(metric_date) AS last_date FROM daily_metrics GROUP BY 1,2,3,4 ORDER BY 1,2,3,4")
        evidence["jobs"] = rows("SELECT id,kind,status,created_at,started_at,finished_at FROM jobs ORDER BY created_at")
        evidence["duplicate_metric_keys"] = sql("SELECT count(*) FROM (SELECT 1 FROM daily_metrics GROUP BY asset_id,entity_type,entity_id,metric_date,dimension_key HAVING count(*)>1) t")
        evidence["table_integrity"] = {}
        for table in ("connections", "source_assets", "jobs", "sync_runs", "source_snapshots", "daily_metrics", "secrets", "datasets", "reports", "source_attestations", "marketing_release_approvals", "marketing_release_snapshots"):
            # Raw row data is hashed only in memory; never persisted or printed.
            raw = sql("SELECT coalesce(jsonb_agg(t ORDER BY to_jsonb(t)::text),'[]'::jsonb) FROM " + table + " t")
            evidence["table_integrity"][table] = {"rows": len(json.loads(raw)), "sha256": digest(raw.encode())}
        token_hex = sql("SELECT encode(value,'hex') FROM secrets WHERE name='meta:client_meta_sandbox'")
        grant = json.loads(Fernet(admin_env["ENCRYPTION_KEY"].encode()).decrypt(bytes.fromhex(token_hex)))
        evidence["oauth_compatibility"] = {"decrypt_with_existing_key": True,
            "access_token_present": bool(grant.get("access_token")), "scopes": grant.get("scopes", []),
            "live_validity_checked": False}
        # Verify all stored encrypted secret records are decryptable with the existing key.
        encrypted_values = rows("SELECT encode(value,'hex') AS value FROM secrets")
        for value in encrypted_values:
            Fernet(admin_env["ENCRYPTION_KEY"].encode()).decrypt(bytes.fromhex(value["value"]))
        evidence["oauth_compatibility"]["all_secret_records_decryptable"] = len(encrypted_values)
        original_gate(baseline)
        evidence["status"] = "PASS"
        print("POSTGRES RESTORE / READ-ONLY INVENTORY / ENCRYPTION: PASS", flush=True)
    except Exception as error:
        evidence["status"] = "BLOCKED"
        evidence["error_type"] = type(error).__name__
        raise
    finally:
        if clone_id:
            info = inspect(clone_id)
            assert info["Config"]["Labels"][LABEL] == prefix
            if info["State"]["Running"]:
                docker("stop", "-t", "30", clone_id)
            evidence["clone_final_state"] = inspect(clone_id)["State"]["Status"]
        (HERE / "restore-result.json").write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print("RESTORE BLOCKED: " + type(error).__name__ + " (details withheld)")
        sys.exit(1)
