"""Deploy the tested local Admin source to the isolated Phase 3 sandbox.

The script uses a frozen source-only build context, backs up the current
sandbox state to a DPAPI-protected encrypted archive, verifies a PostgreSQL
restore in a network-isolated disposable container, smoke-tests the image, and
replaces only the Admin container. It never calls a provider or alters egress.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tarfile
import time
import uuid

from cryptography.fernet import Fernet

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
RUN = "20261016-132836-5c512a53"
ADMIN = "kdh-meta-2b-admin-" + RUN
PG = "kdh-meta-2b-pg-" + RUN
RELAY = "kdh-meta-2b-relay-" + RUN
GATEWAY = "kdh-meta-3-egress-" + RUN
NET = "kdh-meta-2b-net-" + RUN
DBNAME = "meta_acceptance_20261016_132836"
EXPECTED_ADMIN_ID = "22f75e8e5e140dd87aca972a22bd5e8893cb57d08eb6857881605ca930d8927c"
EXPECTED_ADMIN_IMAGE = "sha256:6820506ebb30b1e8efa57300e47dbd50dc32eeb9c602091e3bd88862a3b35f4d"
PREVIOUS_EVIDENCE = "deployment.json"
ROLLBACK_SUFFIX = "-before-multiplatform-20261019"
ARTIFACTS = {
    "preflight": "multiplatform-preflight.json",
    "manifest": "multiplatform-manifest-r3.json",
    "build": "multiplatform-build-result-r3.json",
    "smoke": "multiplatform-smoke.json",
    "backup": "multiplatform-backup-evidence.json",
    "deployment": "multiplatform-deployment-result.json",
}

sys.path.insert(0, str(ROOT / "docs/phase5-20261018"))
sys.path.insert(0, str(ROOT / "docs/phase5b-20261018"))
sys.path.insert(0, str(HERE))
import deploy_ui as prior  # noqa: E402
from cold_backup import dpapi, digest, docker, inspect  # noqa: E402
import runtime_common as runtime  # noqa: E402


def artifact(key: str) -> Path:
    return HERE / ARTIFACTS[key]


def save(key: str, value: dict) -> None:
    path = artifact(key)
    if path.exists():
        raise RuntimeError("deployment evidence already exists")
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def read(key: str) -> dict:
    return json.loads(artifact(key).read_text(encoding="utf-8"))


def env_map(info: dict) -> dict[str, str]:
    return dict(value.split("=", 1) for value in info["Config"]["Env"] if "=" in value)


def docker_json(*args: str) -> dict | list:
    return json.loads(docker(*args))


def http_get(url: str, session=None):
    import requests

    client = session or requests.Session()
    client.trust_env = False
    return client.get(url, timeout=10)


def table_summary() -> dict:
    names = (
        "clients", "source_assets", "daily_metrics", "sync_runs", "source_snapshots",
        "source_attestations", "datasets", "marketing_dataset_reviews",
        "marketing_release_approvals", "marketing_release_snapshots", "report_bundles", "jobs",
    )
    counts = {name: int(runtime.sql("SELECT count(*) FROM " + name)) for name in names}
    page = runtime.rows(
        "SELECT client_id,asset_type,external_id,name,enabled FROM source_assets "
        "WHERE client_id='client_meta_sandbox' AND external_id='2188688654687066' ORDER BY id"
    )
    versions = runtime.rows("SELECT version FROM schema_migrations ORDER BY version")
    return {"counts": counts, "vio_page_asset": page, "migration_versions": [row["version"] for row in versions]}


def service_signature(info: dict) -> dict:
    return {
        "id": info["Id"], "image": info["Image"], "mounts": info["Mounts"],
        "host_config": info["HostConfig"], "started_at": info["State"]["StartedAt"],
        "networks": info["NetworkSettings"]["Networks"],
    }


def source_files() -> dict[str, bytes]:
    files: dict[str, bytes] = {}
    allowed_suffixes = {".py", ".js", ".css", ".svg", ".html", ".woff", ".woff2", ".ttf", ".png", ".webp", ".ico", ".csv"}
    for folder in ("kdh", "static", "templates"):
        for path in sorted((ROOT / folder).rglob("*")):
            if not path.is_file() or "__pycache__" in path.parts or path.suffix.lower() not in allowed_suffixes:
                continue
            if path.name.lower().endswith((".bak", ".pyc", ".map")) or path.is_symlink():
                continue
            relative = path.relative_to(ROOT).as_posix()
            if any(part.lower() in {"instance", "node_modules", "test-results"} for part in path.parts):
                raise RuntimeError("unsafe build source path")
            files[relative] = path.read_bytes()
    for name in ("run.py", "requirements.lock"):
        path = ROOT / name
        if not path.is_file():
            raise RuntimeError("required build source missing")
        files[name] = path.read_bytes()
    if any(Path(name).name.lower().startswith(".env") for name in files):
        raise RuntimeError("environment file in build source")
    return files


def context_tar(files: dict[str, bytes], base_image: str) -> tuple[bytes, dict]:
    file_hashes = {name: digest(raw) for name, raw in sorted(files.items())}
    source_hash = digest(json.dumps({"base_image": base_image, "files": file_hashes}, sort_keys=True).encode())
    dockerfile = (
        f"FROM {base_image}\nUSER root\nRUN rm -f /app/kdh/meta.py.bak\nUSER kdh\nWORKDIR /app\n"
        "COPY --chown=kdh:kdh kdh/ /app/kdh/\n"
        "COPY --chown=kdh:kdh static/ /app/static/\n"
        "COPY --chown=kdh:kdh templates/ /app/templates/\n"
        "COPY --chown=kdh:kdh run.py requirements.lock /app/\n"
    ).encode()
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode="w", format=tarfile.PAX_FORMAT) as archive:
        entries = [("Dockerfile", dockerfile), *sorted(files.items())]
        for name, raw in entries:
            item = tarfile.TarInfo(name)
            item.size = len(raw)
            item.mode = 0o644
            archive.addfile(item, io.BytesIO(raw))
    return stream.getvalue(), {"files": file_hashes, "aggregate_sha256": source_hash, "base_image": base_image}


def psql_in(container_id: str, role: str, database: str, query: str) -> str:
    return docker(
        "exec", "-i", container_id, "psql", "-X", "-qAt", "-v", "ON_ERROR_STOP=1",
        "-U", role, "-d", database, "-c", query,
    ).decode().strip()


def integrity_in(container_id: str, role: str, database: str) -> dict:
    names = json.loads(psql_in(
        container_id, role, database,
        "SELECT coalesce(json_agg(table_name ORDER BY table_name),'[]'::json) FROM information_schema.tables "
        "WHERE table_schema='public' AND table_type='BASE TABLE'",
    ))
    result = {}
    excluded = {"events", "sessions", "attempts", "users"}
    for name in names:
        if name in excluded:
            continue
        if not re.fullmatch(r"[a-z_]+", name):
            raise RuntimeError("unexpected table identifier")
        raw = psql_in(
            container_id, role, database,
            "SELECT coalesce(jsonb_agg(t ORDER BY to_jsonb(t)::text),'[]'::jsonb) FROM public.\"" + name + "\" t",
        ).encode()
        result[name] = {"rows": len(json.loads(raw)), "sha256": digest(raw)}
    return result


def wait_pg(container_id: str, role: str, database: str) -> None:
    for _ in range(45):
        try:
            docker("exec", container_id, "pg_isready", "-U", role, "-d", database)
            return
        except RuntimeError:
            time.sleep(1)
    raise RuntimeError("isolated PostgreSQL readiness failed")


def original_preflight() -> dict:
    if docker("context", "show").decode().strip() != "desktop-linux":
        raise RuntimeError("Docker context changed")
    admin, pg, relay, gateway = (inspect(name) for name in (ADMIN, PG, RELAY, GATEWAY))
    if admin["Id"] != EXPECTED_ADMIN_ID or admin["Image"] != EXPECTED_ADMIN_IMAGE:
        raise RuntimeError("Admin identity changed")
    if not admin["State"]["Running"] or admin["State"].get("Health", {}).get("Status") != "healthy":
        raise RuntimeError("Admin is not healthy")
    for item in (pg, relay, gateway):
        if not item["State"]["Running"]:
            raise RuntimeError("sandbox dependency is not running")
    if pg["State"].get("Health", {}).get("Status") != "healthy":
        raise RuntimeError("PostgreSQL is not healthy")
    if admin["HostConfig"].get("PortBindings") or pg["HostConfig"].get("PortBindings") or gateway["HostConfig"].get("PortBindings"):
        raise RuntimeError("non-relay container publishes a host port")
    if relay["HostConfig"].get("PortBindings") != {"8090/tcp": [{"HostIp": "127.0.0.1", "HostPort": "8191"}]}:
        raise RuntimeError("ingress binding differs from approved sandbox")
    network = docker_json("network", "inspect", NET)[0]
    if not network.get("Internal") or set(admin["NetworkSettings"]["Networks"]) != {NET}:
        raise RuntimeError("Admin network isolation differs")
    if admin["NetworkSettings"]["Networks"][NET].get("IPAddress") != "192.168.0.3":
        raise RuntimeError("Admin internal IP differs")
    if pg["NetworkSettings"]["Networks"].get(NET, {}).get("IPAddress") != "192.168.0.2":
        raise RuntimeError("PostgreSQL internal IP differs")
    if gateway["NetworkSettings"]["Networks"].get(NET, {}).get("IPAddress") != "192.168.0.10":
        raise RuntimeError("gateway internal IP differs")
    if relay["NetworkSettings"]["Networks"].get("kdh-meta-2b-ingress-" + RUN, {}).get("IPAddress") != "192.168.16.2":
        raise RuntimeError("relay ingress IP differs")
    env = env_map(admin)
    if env.get("JOB_MODE") != "request" or env.get("META_CLIENT_ID") != "client_meta_sandbox":
        raise RuntimeError("sandbox runtime scope differs")
    if env.get("APP_URL") != "http://localhost:8191":
        raise RuntimeError("sandbox URL differs")
    if {row["version"] for row in runtime.rows("SELECT version FROM schema_migrations ORDER BY version")} != set(range(1, 9)):
        raise RuntimeError("database migrations differ from 1-8")
    if runtime.sql("SELECT count(*) FROM jobs WHERE status IN ('queued','running')") != "0":
        raise RuntimeError("pending job exists")
    response = http_get("http://localhost:8191/health")
    if response.status_code != 200:
        raise RuntimeError("existing relay health is not 200")
    previous = json.loads((HERE / PREVIOUS_EVIDENCE).read_text(encoding="utf-8"))
    if previous.get("image_id", previous.get("new_image_id")) != EXPECTED_ADMIN_IMAGE or previous.get("admin_container", previous.get("admin_id")) != EXPECTED_ADMIN_ID:
        raise RuntimeError("prior deployment evidence does not match current Admin")
    services = {name: service_signature(inspect(name)) for name in (PG, RELAY, GATEWAY)}
    all_data = prior.integrity()
    summary = table_summary()
    if summary["migration_versions"] != list(range(1, 9)) or len(summary["vio_page_asset"]) != 1:
        raise RuntimeError("sandbox source identity check failed")
    return {
        "status": "PASS", "run_id": RUN, "admin_id": admin["Id"], "base_image": admin["Image"],
        "job_mode": env["JOB_MODE"], "client_id": env["META_CLIENT_ID"], "admin_ip": "192.168.0.3",
        "relay_host_binding": "127.0.0.1:8191", "network_internal": True,
        "services": services, "table_integrity": all_data, "table_summary": summary,
        "provider_calls": 0, "source_identity": "client_meta_sandbox / VIO Agency / 2188688654687066",
        "migrations": list(range(1, 9)), "health_before": 200,
    }


def backup_and_restore(baseline: dict) -> dict:
    prior_backup = json.loads((ROOT / "docs/phase5-20261018/backup-result.json").read_text(encoding="utf-8"))
    private = Path(prior_backup["private_backup_directory"])
    if not private.is_dir():
        raise RuntimeError("private backup directory missing")
    protected_key = (private / "backup-key.dpapi").read_bytes()
    cipher = Fernet(dpapi(protected_key, decrypt=True))
    stamp = time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:8]
    backup_dir = private / ("multiplatform-" + stamp)
    backup_dir.mkdir()
    acl = subprocess.run(["icacls", str(backup_dir)], capture_output=True, text=True)
    if acl.returncode or any(token in acl.stdout.lower() for token in ("everyone", "authenticated users", "builtin\\users")):
        raise RuntimeError("encrypted backup directory ACL is not private")
    pg_info = inspect(PG)
    admin_info = inspect(ADMIN)
    pg_env = env_map(pg_info)
    dump = docker("exec", pg_info["Id"], "pg_dump", "-U", pg_env["POSTGRES_USER"], "-d", DBNAME, "-Fc")
    if not dump.startswith(b"PGDMP"):
        raise RuntimeError("logical database backup format invalid")
    appdata = docker("exec", admin_info["Id"], "tar", "-C", "/app/instance", "-cf", "-", ".")
    env_bytes = json.dumps(env_map(admin_info), sort_keys=True).encode()
    raw_files = {"database.dump": dump, "appdata.tar": appdata, "admin-env.json": env_bytes}
    files = {}
    for name, raw in raw_files.items():
        encrypted = cipher.encrypt(raw)
        target = backup_dir / (name + ".fernet")
        target.write_bytes(encrypted)
        if cipher.decrypt(target.read_bytes()) != raw:
            raise RuntimeError("encrypted backup roundtrip failed")
        files[name] = {"bytes": len(raw), "sha256": digest(raw), "encrypted_sha256": digest(encrypted)}
    with tarfile.open(fileobj=io.BytesIO(appdata), mode="r:*") as archive:
        members = archive.getmembers()
        if any(not (member.isfile() or member.isdir()) for member in members):
            raise RuntimeError("appdata backup contains unsupported entry")
        appdata_entries = len(members)

    prefix = "kdh-foundation-restore-" + uuid.uuid4().hex[:10]
    pg_name = prefix + "-pg"
    label = "kdh.foundation.restore=" + prefix
    restore_env = {
        "POSTGRES_USER": pg_env["POSTGRES_USER"],
        "POSTGRES_DB": DBNAME,
        "POSTGRES_PASSWORD": uuid.uuid4().hex + uuid.uuid4().hex,
    }
    args = ["docker", "create", "--name", pg_name, "--label", label, "--network", "none",
            "--log-driver", "none", "--memory", "512m", "--cpus", "1",
            "--tmpfs", "/var/lib/postgresql/data:rw,nosuid,nodev,size=384m"]
    process_env = dict(os.environ, **restore_env)
    for key in restore_env:
        args.extend(["--env", key])
    args.append(pg_info["Image"])
    result = subprocess.run(args, env=process_env, capture_output=True)
    if result.returncode:
        raise RuntimeError("isolated restore container creation failed")
    clone_id = result.stdout.decode().strip()
    clone = inspect(clone_id)
    if clone["Config"]["Labels"].get("kdh.foundation.restore") != prefix or clone["HostConfig"].get("PortBindings") or clone["Mounts"]:
        raise RuntimeError("restore target identity or isolation invalid")
    try:
        docker("start", clone_id)
        wait_pg(clone_id, restore_env["POSTGRES_USER"], DBNAME)
        listing = subprocess.run(["docker", "exec", "-i", clone_id, "pg_restore", "--list"], input=dump, capture_output=True)
        if listing.returncode or b"TABLE DATA" not in listing.stdout:
            raise RuntimeError("backup archive validation failed")
        restored = subprocess.run([
            "docker", "exec", "-i", clone_id, "pg_restore", "--exit-on-error", "--no-owner", "--no-acl",
            "-U", restore_env["POSTGRES_USER"], "-d", DBNAME,
        ], input=dump, capture_output=True)
        if restored.returncode:
            raise RuntimeError("isolated database restore failed")
        clone_integrity = integrity_in(clone_id, restore_env["POSTGRES_USER"], DBNAME)
        if clone_integrity != baseline["table_integrity"]:
            raise RuntimeError("isolated restore integrity mismatch")
        clone_versions = json.loads(psql_in(
            clone_id, restore_env["POSTGRES_USER"], DBNAME,
            "SELECT coalesce(json_agg(version ORDER BY version),'[]'::json) FROM schema_migrations",
        ))
        if clone_versions != list(range(1, 9)):
            raise RuntimeError("restored database migration state mismatch")
    finally:
        if inspect(clone_id)["State"]["Running"]:
            docker("stop", "-t", "20", clone_id)
    evidence = {
        "status": "PASS", "backup_directory": str(backup_dir), "files": files,
        "private_acl_inherited": True, "appdata_entries": appdata_entries,
        "restore_container": pg_name, "restore_container_id": clone_id,
        "restore_network": "none", "restore_host_ports": [], "restore_storage": "tmpfs",
        "restore_integrity": "PASS", "restore_migrations": clone_versions,
        "off_host_copy": False,
    }
    (backup_dir / "manifest.json").write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    return evidence


def create_smoke(image_id: str, manifest: dict) -> dict:
    prefix = "kdh-foundation-smoke-" + uuid.uuid4().hex[:10]
    label = "kdh.foundation.smoke=" + prefix
    pg_name, app_name = prefix + "-pg", prefix + "-app"
    role, database = "foundation_fixture", "foundation_smoke"
    password = uuid.uuid4().hex + uuid.uuid4().hex
    initial_password = uuid.uuid4().hex + uuid.uuid4().hex
    pg_env = {"POSTGRES_USER": role, "POSTGRES_DB": database, "POSTGRES_PASSWORD": password}
    p_args = ["docker", "create", "--name", pg_name, "--label", label, "--network", "none",
              "--log-driver", "none", "--memory", "512m", "--cpus", "1",
              "--tmpfs", "/var/lib/postgresql/data:rw,nosuid,nodev,size=384m"]
    p_env = dict(os.environ, **pg_env)
    for key in pg_env:
        p_args.extend(["--env", key])
    p_args.append(inspect(PG)["Image"])
    p_result = subprocess.run(p_args, env=p_env, capture_output=True)
    if p_result.returncode:
        raise RuntimeError("smoke PostgreSQL create failed")
    pg_id = p_result.stdout.decode().strip()
    app_env = {
        "DATABASE_URL": f"postgresql://{role}:{password}@127.0.0.1:5432/{database}",
        "ENCRYPTION_KEY": Fernet.generate_key().decode(), "JOB_MODE": "request", "DATA_DIR": "/tmp/appdata",
        "META_CLIENT_ID": "client_meta_sandbox", "APP_URL": "http://localhost:8090", "COOKIE_SECURE": "0",
        "ADMIN_SESSION_COOKIE_NAME": "foundation_smoke_session", "INITIAL_ADMIN_EMAIL": "foundation@example.invalid",
        "INITIAL_ADMIN_PASSWORD": initial_password, "PYTHONDONTWRITEBYTECODE": "1",
    }
    a_args = ["docker", "create", "--name", app_name, "--label", label, "--network", "container:" + pg_id,
              "--log-driver", "none", "--read-only", "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
              "--memory", "512m", "--cpus", "1", "--tmpfs", "/tmp:rw,nosuid,nodev,noexec,size=128m,mode=1777"]
    a_env = dict(os.environ, **app_env)
    for key in app_env:
        a_args.extend(["--env", key])
    a_args.append(image_id)
    app_id = None
    try:
        a_result = subprocess.run(a_args, env=a_env, capture_output=True)
        if a_result.returncode:
            raise RuntimeError("smoke Admin create failed")
        app_id = a_result.stdout.decode().strip()
        for name, current in ((pg_name, pg_id), (app_name, app_id)):
            info = inspect(current)
            if info["Config"]["Labels"].get("kdh.foundation.smoke") != prefix or info["HostConfig"].get("PortBindings"):
                raise RuntimeError("smoke resource isolation invalid")
            if name == pg_name and info["Mounts"]:
                raise RuntimeError("smoke PostgreSQL is not tmpfs only")
        docker("start", pg_id)
        wait_pg(pg_id, role, database)
        docker("start", app_id)
        for _ in range(45):
            try:
                docker("exec", app_id, "python", "-B", "-c",
                       "import urllib.request; assert urllib.request.urlopen('http://127.0.0.1:8090/health',timeout=3).status==200")
                break
            except RuntimeError:
                if not inspect(app_id)["State"]["Running"]:
                    raise RuntimeError("smoke Admin exited")
                time.sleep(1)
        else:
            raise RuntimeError("smoke Admin health timeout")
        expected = manifest["files"]
        verify_code = (
            "import hashlib,json,pathlib,sys; expected=json.load(sys.stdin); root=pathlib.Path('/app'); "
            "actual={str(p.relative_to(root)).replace('\\\\','/'):hashlib.sha256(p.read_bytes()).hexdigest() "
            "for base in ('kdh','static','templates') for p in (root/base).rglob('*') if p.is_file() "
            "and '__pycache__' not in p.parts}; actual['run.py']=hashlib.sha256((root/'run.py').read_bytes()).hexdigest(); "
            "actual['requirements.lock']=hashlib.sha256((root/'requirements.lock').read_bytes()).hexdigest(); "
            "assert not (root/'.env').exists(); print('PASS' if actual==expected else "
            "json.dumps({'missing':sorted(set(expected)-set(actual)),'extra':sorted(set(actual)-set(expected)),"
            "'changed':[k for k in expected if k in actual and expected[k]!=actual[k]]}))"
        )
        verify = docker("exec", "-i", app_id, "python", "-B", "-c", verify_code, data=json.dumps(expected).encode())
        if verify.strip() != b"PASS":
            print(verify.decode())
            raise RuntimeError("smoke source hash verification failed")
        probe = r'''
import importlib,json,os,requests
for name in ('platform_registry','meta_reporting','meta_contract','meta_marketing','marketing_dataset','marketing_review','marketing_source_check','marketing_approval','marketing_publication','report_bundles'):
    importlib.import_module('kdh.'+name)
s=requests.Session(); s.trust_env=False; base='http://localhost:8090'; h={'X-KDH-Request':'1','Origin':base}
r=s.post(base+'/api/auth/login',headers=h,json={'email':os.environ['INITIAL_ADMIN_EMAIL'],'password':os.environ['INITIAL_ADMIN_PASSWORD']},timeout=5)
assert r.status_code==200
csrf=r.json()['csrf']; h['X-CSRF-Token']=csrf
status=s.get(base+'/api/platform-status',timeout=5); assert status.status_code==200
j=status.json(); assert j['job_mode']=='request' and j['client_context']['client_id']=='client_meta_sandbox'
assert j['sources']['tiktok_ads']['state']=='unavailable'
history=s.get(base+'/api/sync-history',timeout=5); assert history.status_code==200 and history.json()['client_id']=='client_meta_sandbox'
assert s.get(base+'/api/sync-history?client_id=client_kinderhealth',timeout=5).status_code==400
workflow=s.get(base+'/api/marketing/workflow',timeout=5); assert workflow.status_code==200 and workflow.json()['client_id']=='client_meta_sandbox'
assert s.post(base+'/api/auth/logout',headers={'X-KDH-Request':'1','Origin':base},json={},timeout=5).status_code==403
assert s.post(base+'/api/auth/logout',headers=h,json={},timeout=5).status_code==200
from kdh.app import create_app
app=create_app(); routes={r.rule for r in app.url_map.iter_rules()}
assert {'/api/platform-status','/api/sync-history','/api/report-bundles','/api/marketing/workflow'} <= routes
store=app.extensions['store']; assert app.config['JOB_MODE']=='request'
assert [r['version'] for r in store.all('SELECT version FROM schema_migrations ORDER BY version')]==list(range(1,9))
assert store.one("SELECT count(*) AS n FROM jobs WHERE status IN ('queued','running')")['n']==0
print(json.dumps({'modules':'PASS','health':'PASS','login_csrf':'PASS','platform_status':'PASS','sync_history_scope':'PASS','marketing_scope':'PASS','routes':'PASS','migrations_1_8':'PASS','background_jobs':'NONE'}))
'''
        result = docker("exec", "-i", app_id, "python", "-B", "-", data=probe.encode())
        smoke_result = json.loads(result)
        for name, current in ((pg_name, pg_id), (app_name, app_id)):
            if inspect(current)["State"]["Running"]:
                docker("stop", "-t", "20", current)
        return {"status": "PASS", "prefix": prefix, "image_id": image_id,
                "isolated_network": "none (shared PG namespace)", "host_ports": [],
                "original_volumes_mounted": False, "source_hashes": "PASS",
                "application": smoke_result, "containers_stopped": True}
    except Exception:
        for current in (app_id, pg_id):
            try:
                if not current:
                    continue
                info = inspect(current)
                if info["State"]["Running"]:
                    docker("stop", "-t", "20", current)
            except Exception:
                pass
        raise


def prepare() -> None:
    for key in ARTIFACTS:
        if artifact(key).exists():
            raise RuntimeError("deployment evidence already exists")
    baseline = original_preflight()
    save("preflight", baseline)
    backup = backup_and_restore(baseline)
    save("backup", backup)
    files = source_files()
    base_hashes = prior.app_hashes(EXPECTED_ADMIN_ID)
    local_requirements = digest(files["requirements.lock"])
    if base_hashes.get("requirements.lock") != local_requirements:
        raise RuntimeError("dependency lock differs from running base image")
    context, manifest = context_tar(files, EXPECTED_ADMIN_IMAGE)
    manifest["file_count"] = len(files)
    tag = "kdh-admin-meta:multiplatform-20261019-" + manifest["aggregate_sha256"][:12]
    if docker("image", "ls", "-q", tag).strip():
        raise RuntimeError("immutable image tag already exists")
    dockerfile_hash = digest(
        (f"FROM {EXPECTED_ADMIN_IMAGE}\nWORKDIR /app\nCOPY --chown=kdh:kdh kdh/ /app/kdh/\n"
         "COPY --chown=kdh:kdh static/ /app/static/\nCOPY --chown=kdh:kdh templates/ /app/templates/\n"
         "COPY --chown=kdh:kdh run.py requirements.lock /app/\n").encode()
    )
    manifest.update({"tag": tag, "dockerfile_sha256": dockerfile_hash, "included_secrets": False,
                     "included_tests_docs_instance_env": False})
    save("manifest", manifest)
    built = subprocess.run(
        ["docker", "build", "--network=none", "--pull=false", "--label",
         "kdh.foundation.source-sha256=" + manifest["aggregate_sha256"], "-t", tag, "-"],
        input=context, capture_output=True,
    )
    (HERE / "multiplatform-build.log").write_bytes(built.stdout + built.stderr)
    if built.returncode:
        raise RuntimeError("immutable image build failed")
    image_info = docker_json("image", "inspect", tag)[0]
    image_id = image_info["Id"]
    if image_info["Config"]["Labels"].get("kdh.foundation.source-sha256") != manifest["aggregate_sha256"]:
        raise RuntimeError("built image source label mismatch")
    save("build", {"status": "PASS", "tag": tag, "image_id": image_id,
                    "source_sha256": manifest["aggregate_sha256"], "base_image": EXPECTED_ADMIN_IMAGE})
    smoke = create_smoke(image_id, manifest)
    save("smoke", smoke)
    print(json.dumps({"stage": "PREPARED", "backup_restore": "PASS", "image_build": "PASS",
                      "smoke": "PASS", "tag": tag, "image_id": image_id,
                      "source_files": len(files), "provider_calls": 0}))


def resume_build_smoke() -> None:
    baseline = original_preflight()
    if baseline['table_integrity'] != read('preflight')['table_integrity']:
        raise RuntimeError('business data changed before build')
    backup = read('backup')
    if backup['status'] != 'PASS' or backup['restore_integrity'] != 'PASS':
        raise RuntimeError('backup restore not verified')
    for name, metadata in backup['files'].items():
        raw = (Path(backup['backup_directory']) / (name + '.fernet')).read_bytes()
        if digest(raw) != metadata['encrypted_sha256']:
            raise RuntimeError('encrypted backup checksum mismatch')
    files = source_files()
    if not artifact('manifest').exists():
        manifest = json.loads((HERE / 'multiplatform-manifest.json').read_text(encoding='utf-8'))
        manifest['tag'] += '-r3'
        manifest['build_revision'] = 'Remove inherited meta.py.bak; no application source changes.'
        save('manifest', manifest)
    manifest = read('manifest')
    if {name: digest(raw) for name, raw in files.items()} != manifest['files']:
        raise RuntimeError('source changed since frozen manifest')
    base_ref = 'kdh-admin-meta:ui-20261019-43c187981323'
    if docker_json('image', 'inspect', base_ref)[0]['Id'] != EXPECTED_ADMIN_IMAGE:
        raise RuntimeError('local base image tag changed')
    context, _ = context_tar(files, base_ref)
    if not artifact('build').exists():
        if docker('image', 'ls', '-q', manifest['tag']).strip():
            raise RuntimeError('immutable build tag already exists without evidence')
        built = subprocess.run(['docker', 'build', '--network=none', '--pull=false', '--label',
                                'kdh.foundation.source-sha256=' + manifest['aggregate_sha256'],
                                '-t', manifest['tag'], '-'], input=context, capture_output=True)
        (HERE / 'multiplatform-build-r3.log').write_bytes(built.stdout + built.stderr)
        if built.returncode:
            raise RuntimeError('local base image build failed')
        image_info = docker_json('image', 'inspect', manifest['tag'])[0]
        if docker_json('image', 'inspect', base_ref)[0]['Id'] != EXPECTED_ADMIN_IMAGE:
            raise RuntimeError('base image changed during build')
        save('build', {'status': 'PASS', 'tag': manifest['tag'], 'image_id': image_info['Id'],
                       'source_sha256': manifest['aggregate_sha256'], 'base_image': EXPECTED_ADMIN_IMAGE,
                       'base_reference': base_ref, 'build_context_sha256': digest(context),
                       'note': 'R2 uses a verified local tag for the same immutable base image.'})
    built = read('build')
    if not artifact('smoke').exists():
        save('smoke', create_smoke(built['image_id'], manifest))
    print(json.dumps({'build': built['status'], 'smoke': read('smoke')['status'], 'tag': built['tag']}))


def runtime_http_checks(env: dict[str, str], source_hashes: dict[str, str]) -> dict:
    import requests
    from werkzeug.security import check_password_hash

    session = requests.Session()
    session.trust_env = False
    base = "http://localhost:8191"
    health = session.get(base + "/health", timeout=10)
    if health.status_code != 200:
        raise RuntimeError("sandbox HTTP health is not 200")
    for name, expected in source_hashes.items():
        if not name.startswith("static/"):
            continue
        response = session.get(base + "/" + name, timeout=10)
        if response.status_code != 200 or hashlib.sha256(response.content).hexdigest() != expected:
            raise RuntimeError("served source does not match immutable image")
    for url in ("/", "/marketing"):
        response = session.get(base + url, timeout=10)
        if response.status_code != 200:
            raise RuntimeError("Admin page did not render")
    users = runtime.rows("SELECT email,password FROM users WHERE role='admin' AND active=1")
    account = next((item for item in users if item["email"] == env.get("INITIAL_ADMIN_EMAIL", "").lower()), None)
    password = env.get("INITIAL_ADMIN_PASSWORD", "")
    login_verified = bool(account and password and check_password_hash(account["password"], password))
    if not login_verified:
        return {"health": 200, "source_assets": "PASS", "login_csrf": "NOT TESTED (configured bootstrap password no longer matches)",
                "provider_calls": 0}
    headers = {"X-KDH-Request": "1", "Origin": base}
    response = session.post(base + "/api/auth/login", headers=headers,
                            json={"email": account["email"], "password": password}, timeout=10)
    if response.status_code != 200:
        raise RuntimeError("sandbox admin login failed")
    csrf = response.json().get("csrf")
    if not csrf:
        raise RuntimeError("CSRF token missing after login")
    me = session.get(base + "/api/auth/me", timeout=10)
    if me.status_code != 200 or me.json().get("user", {}).get("role") != "admin":
        raise RuntimeError("sandbox admin session check failed")
    status = session.get(base + "/api/platform-status", timeout=10)
    if status.status_code != 200:
        raise RuntimeError("platform status endpoint failed")
    state = status.json()
    if state.get("job_mode") != "request" or state.get("client_context", {}).get("client_id") != "client_meta_sandbox":
        raise RuntimeError("platform status client or job mode mismatch")
    if state.get("sources", {}).get("tiktok_ads", {}).get("state") != "unavailable":
        raise RuntimeError("TikTok scaffold state mismatch")
    history = session.get(base + "/api/sync-history", timeout=10)
    if history.status_code != 200 or history.json().get("client_id") != "client_meta_sandbox":
        raise RuntimeError("sync history client scope mismatch")
    foreign = session.get(base + "/api/sync-history?client_id=client_kinderhealth", timeout=10)
    if foreign.status_code != 400:
        raise RuntimeError("sync history accepted a client override")
    workflow = session.get(base + "/api/marketing/workflow", timeout=10)
    if workflow.status_code != 200 or workflow.json().get("client_id") != "client_meta_sandbox":
        raise RuntimeError("marketing client scope mismatch")
    bad_csrf = session.post(base + "/api/auth/logout", headers=headers, json={}, timeout=10)
    if bad_csrf.status_code != 403:
        raise RuntimeError("CSRF rejection test failed")
    good = session.post(base + "/api/auth/logout", headers={**headers, "X-CSRF-Token": csrf}, json={}, timeout=10)
    if good.status_code != 200:
        raise RuntimeError("CSRF logout test failed")
    return {"health": 200, "source_assets": "PASS", "login_csrf": "PASS",
            "platform_status": "PASS", "sync_history_scope": "PASS", "marketing_scope": "PASS",
            "provider_calls": 0}


def create_admin(image_id: str, old: dict, source_hash: str) -> str:
    values = env_map(old)
    args = ["docker", "create", "--name", ADMIN, "--label", "kdh.ui.run=" + RUN,
            "--label", "kdh.foundation.source-sha256=" + source_hash,
            "--network", NET, "--ip", "192.168.0.3", "--dns", "127.0.0.1",
            "--user", old["Config"]["User"], "--workdir", old["Config"]["WorkingDir"],
            "--read-only", "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
            "--memory", "512m", "--cpus", "1", "--restart", "no", "--shm-size", "64m",
            "--log-driver", "json-file", "--tmpfs", "/tmp:rw,noexec,nosuid,size=64m",
            "--mount", "type=volume,src=kdh-meta-2b-appdata-" + RUN + ",dst=/app/instance,volume-nocopy",
            "--health-cmd", old["Config"]["Healthcheck"]["Test"][1], "--health-interval", "3s",
            "--health-timeout", "4s", "--health-retries", "10"]
    for key in values:
        args.extend(["--env", key])
    result = subprocess.run(args + [image_id, *old["Config"]["Cmd"]],
                            env=dict(os.environ, **values), capture_output=True)
    if result.returncode:
        raise RuntimeError("new Admin container creation failed")
    return result.stdout.decode().strip()


def deploy() -> None:
    baseline = read("preflight")
    backup = read("backup")
    built = read("build")
    smoke = read("smoke")
    manifest = read("manifest")
    if {name: digest(raw) for name, raw in source_files().items()} != manifest['files']:
        raise RuntimeError('source changed before deployment')
    if any(item.get("status") != "PASS" for item in (baseline, backup, built, smoke)):
        raise RuntimeError("deployment prerequisite failed")
    if prior.integrity() != baseline["table_integrity"]:
        raise RuntimeError("sandbox data changed since backup")
    for name, expected in baseline["services"].items():
        if service_signature(inspect(name)) != expected:
            raise RuntimeError("sandbox dependency changed since preflight")
    old = inspect(ADMIN)
    if old["Id"] != EXPECTED_ADMIN_ID or old["Image"] != EXPECTED_ADMIN_IMAGE:
        raise RuntimeError("Admin changed since preflight")
    retained = ADMIN + ROLLBACK_SUFFIX
    if docker("ps", "-aq", "--filter", "name=^/" + retained + "$").strip():
        raise RuntimeError("rollback container name already exists")
    report = {"status": "RUNNING", "new_image_id": built["image_id"], "new_tag": built["tag"],
              "rollback_container": retained, "provider_calls": 0, "database_mutations_requested": 0}
    new_id = None
    renamed = detached = stopped = False
    data_mismatch = False
    try:
        docker("stop", "-t", "20", EXPECTED_ADMIN_ID)
        stopped = True
        docker("rename", EXPECTED_ADMIN_ID, retained)
        renamed = True
        docker("network", "disconnect", NET, EXPECTED_ADMIN_ID)
        detached = True
        new_id = create_admin(built["image_id"], old, manifest["aggregate_sha256"])
        new = inspect(new_id)
        if new["Image"] != built["image_id"] or new["HostConfig"].get("PortBindings"):
            raise RuntimeError("new Admin image or host binding mismatch")
        old_mounts = [(item["Type"], item.get("Name"), item["Destination"], item["RW"]) for item in old["Mounts"]]
        new_mounts = [(item["Type"], item.get("Name"), item["Destination"], item["RW"]) for item in new["Mounts"]]
        if new_mounts != old_mounts or set(new["NetworkSettings"]["Networks"]) != {NET}:
            raise RuntimeError("new Admin volume/network mismatch")
        new_env = env_map(new)
        if new_env != env_map(old):
            raise RuntimeError("runtime configuration changed during replacement")
        for key in ("ReadonlyRootfs", "CapDrop", "SecurityOpt", "Dns", "Tmpfs", "Memory", "NanoCpus", "RestartPolicy", "ShmSize", "LogConfig"):
            if new["HostConfig"].get(key) != old["HostConfig"].get(key):
                raise RuntimeError("Admin security/runtime option changed")
        docker("start", new_id)
        for _ in range(45):
            new = inspect(new_id)
            if new["State"].get("Health", {}).get("Status") == "healthy":
                break
            if not new["State"]["Running"]:
                raise RuntimeError("new Admin exited during startup")
            time.sleep(1)
        else:
            raise RuntimeError("new Admin health timeout")
        if new["NetworkSettings"]["Networks"][NET].get("IPAddress") != "192.168.0.3":
            raise RuntimeError("new Admin IP differs from relay upstream")
        if prior.app_hashes(new_id) != manifest["files"]:
            raise RuntimeError("deployed Admin source hashes mismatch")
        versions = [row["version"] for row in runtime.rows("SELECT version FROM schema_migrations ORDER BY version")]
        if versions != list(range(1, 9)):
            raise RuntimeError("sandbox migrations changed")
        data_mismatch = prior.integrity() != baseline["table_integrity"]
        if data_mismatch:
            raise RuntimeError("sandbox business data changed during startup")
        source_hashes = manifest["files"]
        report["http_checks"] = runtime_http_checks(new_env, source_hashes)
        data_mismatch = prior.integrity() != baseline["table_integrity"]
        if data_mismatch:
            raise RuntimeError("sandbox business data changed during HTTP verification")
        for name, expected in baseline["services"].items():
            if service_signature(inspect(name)) != expected:
                raise RuntimeError("PostgreSQL/gateway/relay changed during deployment")
        report.update({"status": "PASS", "admin_id": new_id, "admin_health": "healthy",
                       "admin_ip": "192.168.0.3", "network_isolation": "PASS",
                       "database_integrity": "PASS", "migrations": versions,
                       "relay_binding": "127.0.0.1:8191", "rollback": "AVAILABLE; NOT NEEDED"})
    except Exception as exc:
        report["failure_type"] = type(exc).__name__
        if new_id:
            current = inspect(new_id)
            if current["State"]["Running"]:
                docker("stop", "-t", "20", new_id)
            if NET in current["NetworkSettings"]["Networks"]:
                docker("network", "disconnect", NET, new_id)
            failed_name = ADMIN + "-failed-multiplatform-" + new_id[:8]
            docker("rename", new_id, failed_name)
        if data_mismatch:
            report["rollback"] = "STOPPED; data mismatch requires investigation"
        elif stopped:
            if renamed:
                docker("rename", EXPECTED_ADMIN_ID, ADMIN)
            if detached:
                docker("network", "connect", "--ip", "192.168.0.3", NET, EXPECTED_ADMIN_ID)
            docker("start", EXPECTED_ADMIN_ID)
            restored = inspect(EXPECTED_ADMIN_ID)
            for _ in range(45):
                if restored["State"].get("Health", {}).get("Status") == "healthy":
                    break
                time.sleep(1)
                restored = inspect(EXPECTED_ADMIN_ID)
            if restored["State"].get("Health", {}).get("Status") == "healthy":
                report["rollback"] = "PASS; prior application restored"
            else:
                report["rollback"] = "BLOCKED; prior application did not become healthy"
        else:
            report["rollback"] = "NOT NEEDED; original Admin state retained"
        save("deployment", report)
        raise RuntimeError("deployment failed; sanitized report saved") from None
    save("deployment", report)
    print(json.dumps({"stage": "DEPLOYED", "status": report["status"], "admin_id": new_id,
                      "image_id": built["image_id"], "health": "PASS", "database_integrity": "PASS",
                      "provider_calls": 0, "rollback": report["rollback"]}))


if __name__ == "__main__":
    try:
        if len(sys.argv) != 2 or sys.argv[1] not in {"prepare", "build-smoke", "deploy"}:
            raise RuntimeError("expected prepare or deploy stage")
        {"prepare": prepare, "build-smoke": resume_build_smoke, "deploy": deploy}[sys.argv[1]]()
    except Exception as error:
        import traceback
        frames = [{'file': Path(frame.filename).name, 'line': frame.lineno} for frame in traceback.extract_tb(error.__traceback__)]
        print(json.dumps({"status": "BLOCKED", "error_type": type(error).__name__, "frames": frames, "details": "withheld"}))
        raise SystemExit(1)
