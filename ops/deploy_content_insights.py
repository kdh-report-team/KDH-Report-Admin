"""VIO-only Insights deployment with encrypted backup and app-only rollback."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from urllib.parse import urlsplit

from cryptography.fernet import Fernet
import shared_viewer as s

u = s.u
OUT = u.ROOT / 'docs/content-insights-deploy-20261021'
PRIVATE = Path(os.environ['LOCALAPPDATA']) / 'KDH-Content-Insights-Deploy-20261021'
ADMIN = s.VIO
PG = s.f.PG
BACKUP = ADMIN + '-before-insights-20261021'
PATHS = ['kdh/app.py', 'kdh/facebook_content_report.py', 'kdh/meta_content_insights.py',
         'kdh/meta_reporting.py', 'kdh/meta_marketing.py', 'kdh/marketing_dataset.py',
         'kdh/marketing_preview.py', 'kdh/meta.py', 'static/facebook-content-report.js',
         'static/marketing.js', 'static/views.js', 'templates/marketing.html']


def save(name, value):
    (OUT / (name + '.json')).write_text(json.dumps(value, indent=2), encoding='utf-8')


def read(name):
    return json.loads((OUT / (name + '.json')).read_text(encoding='utf-8'))


def signature(name):
    value = u.signature(u.inspect(name))
    value['mounts'] = sorted(value['mounts'], key=lambda m: m['Destination'])
    value['networks'] = sorted(value['networks'])
    return value


def network_signature(name):
    item = u.inspect(name)
    return {k: item[k] for k in ('Id', 'Internal', 'Options', 'IPAM', 'EnableIPv6')}


def prepare(expected_id='9290296d0bfea39e1ee1cf97ee1402af0f0d2090be9eb2fb71a8a8a0cbc28aa9'):
    OUT.mkdir(exist_ok=True)
    assert not (OUT / 'prepared.json').exists()
    original = u.inspect(ADMIN)
    assert original['Id'] == expected_id
    assert original['State']['Health']['Status'] == 'healthy'
    values = u.env(original)
    assert values['META_CLIENT_ID'] == 'client_meta_sandbox' and values['JOB_MODE'] == 'request'
    assert values['APP_URL'] == 'http://localhost:8191'
    assert values['REPORT_NEW_BASE_URL'] == 'http://127.0.0.1:8080'
    assert not original['HostConfig']['PortBindings'] and not original['Config']['Entrypoint']
    assert original['HostConfig']['ReadonlyRootfs'] and original['HostConfig']['CapDrop'] == ['ALL']
    assert original['HostConfig']['RestartPolicy']['Name'] == 'unless-stopped'
    assert len(original['NetworkSettings']['Networks']) == 1
    network, endpoint = next(iter(original['NetworkSettings']['Networks'].items()))
    assert network == 'kdh-meta-2b-net-20261016-132836-5c512a53'
    assert endpoint['IPAddress'] and u.inspect(network)['Internal']
    db = urlsplit(values['DATABASE_URL'])
    assert db.hostname == PG and db.path == '/meta_acceptance_20261016_132836'
    pg = u.inspect(PG)
    assert {m.get('Name') for m in pg['Mounts']} == {'kdh-meta-2b-pgdata-20261016-132836-5c512a53'}
    assert {m.get('Name') for m in original['Mounts']} == {'kdh-meta-2b-appdata-20261016-132836-5c512a53'}
    checks = json.loads(u.code(ADMIN, """import os,json,psycopg
with psycopg.connect(os.environ['DATABASE_URL'],options='-c default_transaction_read_only=on') as db:
 print(json.dumps({'pending_jobs':db.execute("SELECT count(*) FROM jobs WHERE status IN ('queued','running')").fetchone()[0], 'schedules':db.execute('SELECT count(*) FROM schedules WHERE enabled=1').fetchone()[0]}))
"""))
    assert checks == {'pending_jobs': 0, 'schedules': 0}
    for path in ('requirements.lock', 'kdh/migrations.py'):
        raw = u.code(ADMIN, 'from pathlib import Path;import sys;sys.stdout.buffer.write(Path(' + repr('/app/' + path) + ').read_bytes())')
        assert raw == (u.ROOT / path).read_bytes(), path
    names = u.docker('ps', '-a', '--format', '{{.Names}}').decode().splitlines()
    protected = {n: signature(n) for n in names if n != ADMIN}
    networks = {n: network_signature(n) for n in u.docker('network', 'ls', '--format', '{{.Name}}').decode().splitlines()}
    ingress = u.inspect('kdh-meta-2b-ingress-20261016-132836-5c512a53')
    assert ingress['Options']['com.docker.network.bridge.enable_icc'] == 'false'
    PRIVATE.mkdir(exist_ok=False)
    key = Fernet.generate_key()
    (PRIVATE / 'key.dpapi').write_bytes(u.dpapi(key))
    box = Fernet(key)
    (PRIVATE / 'original.fernet').write_bytes(box.encrypt(json.dumps(original).encode()))
    backups = {'database.dump': u.docker('exec', PG, 'pg_dump', '-U', u.env(pg)['POSTGRES_USER'], '-d', db.path[1:], '-Fc'),
               'appdata.tar': u.docker('exec', ADMIN, 'tar', '-C', '/app/instance', '-cf', '-', '.')}
    assert backups['database.dump'].startswith(b'PGDMP')
    u.docker('exec', '-i', PG, 'pg_restore', '--list', data=backups['database.dump'])
    for name, raw in backups.items():
        encrypted = box.encrypt(raw)
        (PRIVATE / (name + '.fernet')).write_bytes(encrypted)
        assert box.decrypt((PRIVATE / (name + '.fernet')).read_bytes()) == raw
    (OUT / 'previous-startup-manifest.json').write_bytes((s.OUT / 'deployment.json').read_bytes())
    save('prepared', {'container': signature(ADMIN), 'network': network, 'ip': endpoint['IPAddress'],
                     'protected': protected, 'networks': networks, 'data': s.data(ADMIN), 'idle': checks,
                     'files': {p: u.sha((u.ROOT / p).read_bytes()) for p in PATHS},
                     'backups': {k: u.sha(v) for k, v in backups.items()}, 'private': str(PRIVATE)})
    print('Identity, network policy, idle jobs, unchanged migrations and encrypted backups PASS', flush=True)


def build():
    baseline = read('prepared')
    assert signature(ADMIN) == baseline['container']
    assert {p: u.sha((u.ROOT / p).read_bytes()) for p in PATHS} == baseline['files']
    previous = s.OUT
    try:
        s.OUT = OUT
        built = s.build_image(baseline['container']['image'], u.ROOT, PATHS, 'kdh-admin-meta:insights-20261021-')
    finally:
        s.OUT = previous
    save('build', built)
    args = ['docker', 'run', '--rm', '--network', 'none', '--entrypoint', 'python',
            '--mount', 'type=bind,source=' + str(u.ROOT / 'tests') + ',target=/app/tests,readonly',
            '--env', 'PYTHONPATH=/app:/app/tests', built['image'], '-B', '-m', 'unittest',
            'test_meta_content_insights', 'test_meta_reporting', 'test_facebook_content_report',
            'test_loopback_entry', 'test_viewer_handoff.SQLiteHandoffTests',
            'test_viewer_access.SQLiteViewerTests', 'test_vio_handoff.VioHandoffTests', '-v']
    with (OUT / 'image-tests.log').open('wb') as log:
        result = subprocess.run(args, stdout=log, stderr=subprocess.STDOUT)
    save('tests', {'exit_code': result.returncode, 'image': built['image']})
    assert result.returncode == 0
    print('Exact immutable image offline tests PASS; no live database/provider access', flush=True)


def verify_protected():
    p = read('prepared')
    assert {n: signature(n) for n in p['protected']} == p['protected']
    assert {n: network_signature(n) for n in p['networks']} == p['networks']


def rollback():
    if not u.docker('ps', '-aq', '--filter', 'name=^/' + BACKUP + '$').strip():
        return
    if u.docker('ps', '-aq', '--filter', 'name=^/' + ADMIN + '$').strip():
        u.docker('stop', '--time', '20', ADMIN)
        u.docker('rename', ADMIN, ADMIN + '-insights-failed-' + str(int(time.time())))
    u.docker('rename', BACKUP, ADMIN)
    u.docker('update', '--restart=unless-stopped', ADMIN)
    u.docker('start', ADMIN)
    u.wait_health(ADMIN)
    (s.OUT / 'deployment.json').write_bytes((OUT / 'previous-startup-manifest.json').read_bytes())
    save('deployment', {'status': 'ROLLED_BACK', 'service': signature(ADMIN)})


def deploy():
    p, built = read('prepared'), read('build')
    assert read('tests') == {'exit_code': 0, 'image': built['image']}
    assert signature(ADMIN) == p['container']
    assert {f: u.sha((u.ROOT / f).read_bytes()) for f in PATHS} == built['files']
    verify_protected()
    assert s.data(ADMIN) == p['data']
    box = Fernet(u.dpapi((PRIVATE / 'key.dpapi').read_bytes(), True))
    original = json.loads(box.decrypt((PRIVATE / 'original.fernet').read_bytes()))
    assert u.env(u.inspect(ADMIN)) == u.env(original)
    assert not u.docker('ps', '-aq', '--filter', 'name=^/' + BACKUP + '$').strip()
    try:
        u.docker('stop', '--time', '20', ADMIN)
        u.docker('rename', ADMIN, BACKUP)
        u.docker('update', '--restart=no', BACKUP)
        s.clone(ADMIN, original, built['image'], fixed_ip=p['ip'])
        current = u.inspect(ADMIN)
        for key in ('LogConfig', 'ReadonlyRootfs', 'CapAdd', 'CapDrop', 'SecurityOpt', 'Sysctls', 'Tmpfs', 'Dns',
                    'Memory', 'MemorySwap', 'NanoCpus', 'PortBindings', 'NetworkMode', 'RestartPolicy'):
            actual, expected = current['HostConfig'].get(key), original['HostConfig'].get(key)
            if key == 'Dns':
                actual, expected = actual or [], expected or []
            assert actual == expected, key
        assert current['Mounts'] == original['Mounts'] and u.env(current) == u.env(original)
        assert current['Config']['Cmd'] == original['Config']['Cmd']
        u.docker('start', ADMIN)
        u.wait_health(ADMIN)
        assert s.data(ADMIN) == p['data']
        verify_protected()
        manifest = s.read('deployment')
        manifest['services'][ADMIN] = u.signature(u.inspect(ADMIN))
        s.save('deployment', manifest)
        save('deployment', {'status': 'PASS', 'service': signature(ADMIN), 'tag': built['tag'],
                            'rollback': BACKUP, 'business_data': 'UNCHANGED', 'other_services': 'UNCHANGED'})
        print('VIO Admin healthy; business hashes, New and all other containers unchanged', flush=True)
    except Exception:
        rollback()
        raise


if __name__ == '__main__':
    try:
        {'prepare': prepare, 'build': build, 'deploy': deploy, 'rollback': rollback}[sys.argv[1]]()
    except Exception as exc:
        import traceback
        last = traceback.extract_tb(exc.__traceback__)[-1]
        print(json.dumps({'status': 'FAIL', 'type': type(exc).__name__, 'line': last.lineno}))
        sys.exit(1)
