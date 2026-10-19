"""Approved image smoke: fresh tmpfs PostgreSQL, no network/host ports/original data."""
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import time
import uuid

HERE = Path(__file__).resolve().parent
PRIOR = HERE.parent / "phase5-20261018"
ROOT = HERE.parents[1]
sys.path.insert(0, str(PRIOR))
from cold_backup import docker, inspect
from cryptography.fernet import Fernet


def create(args, values):
    environment = dict(os.environ)
    environment.update(values)
    for key in values:
        args.extend(["--env", key])
    process = subprocess.run(["docker", "create", *args], env=environment, capture_output=True)
    if process.returncode:
        raise RuntimeError("smoke container create failed; details withheld")
    return process.stdout.decode().strip()


def main():
    assert not (HERE / "smoke.json").exists()
    assert json.loads((HERE / "preflight.json").read_text())["status"] == "PASS"
    built = json.loads((PRIOR / "approved-image-result.json").read_text())
    manifest = json.loads((PRIOR / "deployment-manifest.json").read_text())
    originals = json.loads((PRIOR / "runtime-baseline.json").read_text(encoding="utf-8-sig"))
    pg_image = next(c["Image"] for c in originals if "-pg-" in c["Name"])
    prefix = "kdh-meta-phase5b-smoke-" + uuid.uuid4().hex[:8]
    report = {"prefix": prefix, "image_id": built["image_id"], "network": "none (shared namespace)",
        "host_ports": [], "database_storage": "new tmpfs", "original_resources_mounted": False}
    pg_id = app_id = None
    try:
        pg_env = {"POSTGRES_USER": "phase5b_fixture", "POSTGRES_DB": "phase5b_smoke", "POSTGRES_PASSWORD": secrets.token_urlsafe(32)}
        # env switches must precede image; create() handles the ordered arguments below.
        args = ["--name", prefix + "-pg", "--label", "kdh.phase5b.smoke=" + prefix, "--network", "none",
            "--log-driver", "none", "--memory", "512m", "--cpus", "1",
            "--tmpfs", "/var/lib/postgresql/data:rw,nosuid,nodev,size=256m"]
        env = dict(os.environ, **pg_env)
        for key in pg_env:
            args.extend(["--env", key])
        completed = subprocess.run(["docker", "create", *args, pg_image], env=env, capture_output=True)
        assert completed.returncode == 0
        pg_id = completed.stdout.decode().strip()
        assert not inspect(pg_id)["HostConfig"]["PortBindings"] and not inspect(pg_id)["Mounts"]
        docker("start", pg_id)
        for _ in range(40):
            try:
                docker("exec", pg_id, "pg_isready", "-U", pg_env["POSTGRES_USER"], "-d", pg_env["POSTGRES_DB"])
                break
            except RuntimeError:
                time.sleep(1)
        else:
            raise RuntimeError("smoke PostgreSQL readiness")
        app_env = {"DATABASE_URL": "postgresql://phase5b_fixture:" + pg_env["POSTGRES_PASSWORD"] + "@127.0.0.1:5432/phase5b_smoke",
            "ENCRYPTION_KEY": Fernet.generate_key().decode(), "JOB_MODE": "request", "DATA_DIR": "/tmp/appdata",
            "META_CLIENT_ID": "client_meta_sandbox", "APP_URL": "http://localhost:8090", "COOKIE_SECURE": "0",
            "ADMIN_SESSION_COOKIE_NAME": "phase5b_fixture_session", "INITIAL_ADMIN_EMAIL": "phase5b@example.invalid",
            "INITIAL_ADMIN_PASSWORD": secrets.token_urlsafe(32), "PYTHONDONTWRITEBYTECODE": "1"}
        args = ["docker", "create", "--name", prefix + "-app", "--label", "kdh.phase5b.smoke=" + prefix,
            "--network", "container:" + pg_id, "--log-driver", "none", "--read-only", "--cap-drop", "ALL",
            "--security-opt", "no-new-privileges", "--memory", "512m", "--cpus", "1",
            "--tmpfs", "/tmp:rw,nosuid,nodev,noexec,size=128m,mode=1777",
            "--mount", "type=bind,src=" + str(ROOT / "tests") + ",dst=/app/tests,readonly"]
        for key in app_env:
            args.extend(["--env", key])
        args.append(built["image_id"])
        completed = subprocess.run(args, env=dict(os.environ, **app_env), capture_output=True)
        assert completed.returncode == 0
        app_id = completed.stdout.decode().strip()
        app = inspect(app_id)
        assert len(app["Mounts"]) == 1 and app["Mounts"][0]["Destination"] == "/app/tests" and not app["Mounts"][0]["RW"]
        assert not app["HostConfig"]["PortBindings"]
        docker("start", app_id)
        for _ in range(40):
            try:
                docker("exec", app_id, "python", "-B", "-c", "import urllib.request; assert urllib.request.urlopen('http://localhost:8090/health', timeout=2).status==200")
                break
            except RuntimeError:
                if not inspect(app_id)["State"]["Running"]:
                    raise RuntimeError("new image startup failed")
                time.sleep(1)
        else:
            raise RuntimeError("smoke app readiness")
        report["http_startup"] = "PASS"
        expected_files = {p: h for p, h in manifest["files"].items() if p not in ("Dockerfile", ".dockerignore")}
        verify = "import hashlib,json,sys,pathlib; expected=json.load(sys.stdin); assert not pathlib.Path('/app/.env').exists(); assert all(hashlib.sha256(pathlib.Path('/app',p).read_bytes()).hexdigest()==h for p,h in expected.items()); print('PASS')"
        assert docker("exec", "-i", app_id, "python", "-B", "-c", verify, data=json.dumps(expected_files).encode()).strip() == b"PASS"
        report["image_source_hashes"] = {"status": "PASS", "files": len(expected_files)}
        probe = '''
import importlib,json,os,requests
for module in ('meta_reporting','meta_contract','meta_marketing','marketing_dataset','marketing_review','marketing_source_check','marketing_approval','marketing_publication','report_bundles'):
    importlib.import_module('kdh.'+module)
s=requests.Session(); s.trust_env=False
base='http://localhost:8090'
h={'X-KDH-Request':'1','Origin':base}
r=s.post(base+'/api/auth/login',headers=h,json={'email':os.environ['INITIAL_ADMIN_EMAIL'],'password':os.environ['INITIAL_ADMIN_PASSWORD']},timeout=5)
assert r.status_code==200
csrf=r.json()['csrf']; cookie=r.headers['Set-Cookie']
assert 'phase5b_fixture_session=' in cookie and 'HttpOnly' in cookie and 'SameSite=Lax' in cookie
assert s.get(base+'/api/auth/me',timeout=5).json()['user']['role']=='admin'
assert s.post(base+'/api/auth/logout',headers=h,json={},timeout=5).status_code==403
assert s.get(base+'/api/auth/me',timeout=5).json()['user']
h['X-CSRF-Token']=csrf
assert s.post(base+'/api/auth/logout',headers=h,json={},timeout=5).status_code==200
assert s.get(base+'/api/auth/me',timeout=5).json()['user'] is None
from kdh.app import create_app
app=create_app(); routes={r.rule for r in app.url_map.iter_rules()}
required={'/api/meta/reporting/assets','/api/meta/reporting/sync','/api/meta/reporting/kpis/<asset_id>','/api/meta/reporting/preview','/api/marketing/datasets'}
assert required <= routes
assert any('/api/internal/v1/viewer/report-bundles/' in r for r in routes)
store=app.extensions['store']; app.extensions['worker'].start()
assert app.config['JOB_MODE']=='request'
assert store.one('SELECT count(*) AS n FROM jobs')['n']==0
assert store.one('SELECT count(*) AS n FROM source_snapshots')['n']==0
assert [r['version'] for r in store.all('SELECT version FROM schema_migrations ORDER BY version')]==list(range(1,9))
print(json.dumps({'modules':'PASS','login_session_csrf_logout':'PASS','routes':'PASS','migrations_1_8':'PASS','no_background_jobs':'PASS'}))
'''
        report["application"] = json.loads(docker("exec", "-i", app_id, "python", "-B", "-", data=probe.encode()))
        tests = subprocess.run(["docker", "exec", app_id, "python", "-B", "/app/tests/run_offline.py", "test_facebook_bundles.py"], capture_output=True)
        assert tests.returncode == 0
        import re
        total = re.search(rb"Ran (\d+) tests", tests.stderr + tests.stdout)
        assert total and int(total.group(1)) == 16
        report["bundle_guard_fixtures"] = {"pass": 16, "fail": 0, "skip": 0, "providers": "blocked by fixture runner and network namespace"}
        report["status"] = "PASS"
    except Exception as error:
        report["status"] = "FAIL"
        report["error_type"] = type(error).__name__
        raise
    finally:
        for kind, cid in (("app", app_id), ("postgres", pg_id)):
            if cid:
                assert inspect(cid)["Config"]["Labels"]["kdh.phase5b.smoke"] == prefix
                if inspect(cid)["State"]["Running"]:
                    docker("stop", "-t", "20", cid)
                report[kind + "_container"] = {"id": cid, "name": inspect(cid)["Name"], "final_state": inspect(cid)["State"]["Status"]}
        (HERE / "smoke.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print("SMOKE FAIL: " + type(error).__name__ + "; sensitive details withheld")
        raise SystemExit(1)
