"""Phase 5B read-only preflight. No original resource start or modification."""
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
PRIOR = ROOT / "docs/phase5-20261018"
sys.path.insert(0, str(PRIOR))
from cold_backup import digest, docker, dpapi, original_gate
from cryptography.fernet import Fernet


def main():
    assert not (HERE / "preflight.json").exists()
    baseline = json.loads((PRIOR / "baseline.json").read_text(encoding="utf-8-sig"))
    head = subprocess.check_output(["git", "rev-parse", "HEAD"]).decode().strip()
    branch = subprocess.check_output(["git", "branch", "--show-current"]).decode().strip()
    assert head == baseline["head"] and branch == baseline["branch"]
    assert all(digest((ROOT / path).read_bytes()) == value for path, value in baseline["hashes"].items())
    all_paths = subprocess.check_output(["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"]).decode().split("\0")
    all_paths = sorted(set(p for p in all_paths if p))
    extras = set(all_paths) - set(baseline["hashes"])
    assert all(p == "KDH_PHASE5_SANDBOX_DEPLOYMENT_PLAN.md" or p.startswith("docs/phase5-20261018/") or p == "docs/phase5b-20261018/preflight.py" for p in extras)
    (HERE / "baseline.json").write_text(json.dumps({"head": head, "branch": branch,
        "hashes": {p: digest((ROOT / p).read_bytes()) for p in all_paths},
        "status": subprocess.check_output(["git", "status", "--porcelain=v1"]).decode().splitlines()}, indent=2) + "\n")
    assert docker("context", "show").decode().strip() == "desktop-linux"
    runtime = json.loads((PRIOR / "runtime-baseline.json").read_text(encoding="utf-8-sig"))
    originals = original_gate(runtime)
    for expected, actual in zip(runtime, originals):
        assert actual["HostConfig"]["PortBindings"] == expected["bindings"]
        assert set(actual["NetworkSettings"]["Networks"]) == set(expected["networks"])
        for name, network in expected["networks"].items():
            assert {k: actual["NetworkSettings"]["Networks"][name][k] for k in network} == network
    security = json.loads((PRIOR / "security-readiness.json").read_text())
    run_root = Path("D:/KDH-Meta-Phase2B/20261016-132836-5c512a53")
    assert all(digest((run_root / p).read_bytes()) == h for p, h in security["hashes"].items())
    for expected in security["networks"]:
        current = json.loads(docker("network", "inspect", expected["Name"]))[0]
        assert {k: current[k] for k in expected} == expected
    manifest = json.loads((PRIOR / "deployment-manifest.json").read_text())
    assert len(manifest["files"]) == 61
    assert all(digest((ROOT / p).read_bytes()) == h for p, h in manifest["files"].items())
    context = Path(manifest["build_context"]).read_bytes()
    assert digest(context) == manifest["build_context_sha256"]
    with tarfile.open(fileobj=io.BytesIO(context)) as archive:
        assert set(archive.getnames()) == set(manifest["files"])
        assert all(digest(archive.extractfile(p).read()) == h for p, h in manifest["files"].items())
    backup = json.loads((PRIOR / "backup-result.json").read_text())
    assert backup["status"] == "PASS"
    directory = Path(backup["private_backup_directory"])
    cipher = Fernet(dpapi((directory / "backup-key.dpapi").read_bytes(), decrypt=True))
    for entry in backup["archives"].values():
        encrypted = (directory / entry["file"]).read_bytes()
        assert digest(encrypted) == entry["encrypted_sha256"]
        assert digest(cipher.decrypt(encrypted)) == entry["archive_sha256"]
    encrypted = (directory / "admin.config.fernet").read_bytes()
    assert digest(encrypted) == backup["config_backup"]["encrypted_sha256"]
    private_config = Path(os.environ["LOCALAPPDATA"]) / "KDH-Meta-Acceptance-Secrets/20261016-132836-5c512a53/admin.config"
    assert cipher.decrypt(encrypted) == private_config.read_bytes()
    raw = private_config.read_text(encoding="utf-8-sig")
    try:
        config = json.loads(raw)
    except ValueError:
        config = dict(line.split("=", 1) for line in raw.splitlines() if "=" in line and not line.lstrip().startswith("#"))
    admin = next(c for c in originals if "-admin-" in c["Name"])
    env = dict(v.split("=", 1) for v in admin["Config"]["Env"])
    for key in ("ENCRYPTION_KEY", "DATABASE_URL", "META_APP_SECRET", "META_APP_ID", "META_CONFIG_ID", "ADMIN_SESSION_COOKIE_NAME", "JOB_MODE", "META_CLIENT_ID"):
        assert config.get(key) and config[key] == env[key]
    restore = json.loads((PRIOR / "restore-result.json").read_text())
    period = json.loads((PRIOR / "period-verification.json").read_text())
    assert restore["status"] == period["status"] == "PASS"
    assert restore["oauth_compatibility"]["decrypt_with_existing_key"]
    assert [m["version"] for m in restore["migrations"]] == list(range(1, 9))
    assert restore["assets"][0]["external_id"] == "2188688654687066"
    result = {"status": "PASS", "head": head, "branch": branch, "originals_unchanged_stopped": True,
        "backup_encrypted_and_plaintext_checksums_match": True, "dpapi_decryption": "PASS",
        "oauth_encryption_key_unchanged": True, "independent_restore": "PASS", "off_host_backup": "NOT AVAILABLE",
        "source_file_count": 61, "source_manifest_sha256": manifest["aggregate_sha256"],
        "migration_versions": list(range(1, 9)), "new_migrations": 0}
    (HERE / "preflight.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print("PREFLIGHT BLOCKED: " + type(error).__name__ + "; sensitive details withheld")
        raise SystemExit(1)
