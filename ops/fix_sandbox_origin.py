"""Deploy only the loopback browser-entry fix to the existing VIO Admin."""
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import time
from urllib.parse import urlsplit

from cryptography.fernet import Fernet
import unify_primary as u

OUT = u.ROOT / 'docs/origin-fix-20261021'
PRIVATE = Path(os.environ['LOCALAPPDATA']) / 'KDH-Meta-Origin-Fix-20261021'
RUN = '20261016-132836-5c512a53'
ADMIN = 'kdh-meta-2b-admin-' + RUN
PG = 'kdh-meta-2b-pg-' + RUN
NET = 'kdh-meta-2b-net-' + RUN
PROTECTED = (PG, 'kdh-meta-3-egress-' + RUN, 'kdh-meta-2b-relay-' + RUN,
             'kdh-vio-relay-phase9-20261019', 'kdh-vio-new-phase9-20261019', u.A, u.N, u.PG)


def save(name, value):
    (OUT / (name + '.json')).write_text(json.dumps(value, indent=2), encoding='utf-8')


def read(name):
    return json.loads((OUT / (name + '.json')).read_text(encoding='utf-8'))


def box():
    return Fernet(u.dpapi((PRIVATE / 'key.dpapi').read_bytes(), True))


def original():
    return json.loads(box().decrypt((PRIVATE / 'container.fernet').read_bytes()))


def data():
    hashes = json.loads(u.code(ADMIN, u.INTEGRITY))
    return {k: v for k, v in hashes.items() if k not in
            ('sessions', 'events', 'attempts', 'viewer_handoffs', 'delegated_viewer_sessions')}


def verify_protected():
    # Docker may reorder mount arrays; order does not change mount identity.
    differences = {}
    for name, expected in read('prepared')['protected'].items():
        actual = u.signature(u.inspect(name))
        for value in (expected, actual):
            value['networks'] = sorted(value['networks'])
            value['mounts'] = sorted(value['mounts'], key=lambda m: m['Destination'])
        if actual != expected:
            differences[name] = {'expected': expected, 'actual': actual}
    if differences:
        save('protected-differences', differences)
        raise RuntimeError('Protected service changed; safe metadata recorded')


def prepare():
    assert not (OUT / 'prepared.json').exists()
    item = u.inspect(ADMIN)
    previous = u.read('preflight')['protected'][ADMIN]
    assert item['Id'] == previous['id'] and item['Image'] == previous['image']
    assert item['State']['Health']['Status'] == 'healthy'
    values = u.env(item)
    assert values['JOB_MODE'] == 'request' and values['META_CLIENT_ID'] == 'client_meta_sandbox'
    assert values['APP_URL'] == 'http://localhost:8191'
    assert not item['HostConfig']['PortBindings']
    assert item['NetworkSettings']['Networks'][NET]['IPAddress'] == '192.168.0.3'
    assert item['HostConfig']['ReadonlyRootfs'] and item['HostConfig']['CapDrop'] == ['ALL']
    pg = u.inspect(PG)
    assert {m['Name'] for m in pg['Mounts']} == {'kdh-meta-2b-pgdata-' + RUN}
    db = urlsplit(values['DATABASE_URL'])
    assert db.hostname == PG and db.path == '/meta_acceptance_20261016_132836'
    old = u.code(ADMIN, "from pathlib import Path;import sys;sys.stdout.buffer.write(Path('/app/kdh/app.py').read_bytes())")
    assert u.sha(old) == read('baseline')['app_sha256']
    PRIVATE.mkdir(exist_ok=False)
    key = Fernet.generate_key()
    (PRIVATE / 'key.dpapi').write_bytes(u.dpapi(key))
    cipher = Fernet(key)
    (PRIVATE / 'container.fernet').write_bytes(cipher.encrypt(json.dumps(item).encode()))
    backups = {
        'database.dump': u.docker('exec', PG, 'pg_dump', '-U', u.env(pg)['POSTGRES_USER'],
                                  '-d', db.path.lstrip('/'), '-Fc'),
        'appdata.tar': u.docker('exec', ADMIN, 'tar', '-C', '/app/instance', '-cf', '-', '.'),
    }
    assert backups['database.dump'].startswith(b'PGDMP')
    u.docker('exec', '-i', PG, 'pg_restore', '--list', data=backups['database.dump'])
    for name, raw in backups.items():
        encrypted = cipher.encrypt(raw)
        (PRIVATE / (name + '.fernet')).write_bytes(encrypted)
        assert cipher.decrypt(encrypted) == raw
    protected = {n: u.signature(u.inspect(n)) for n in PROTECTED}
    source = (u.ROOT / 'kdh/app.py').read_bytes()
    tag = 'kdh-admin-meta:origin-fix-20261021-' + u.sha(source)[:12]
    base = 'kdh-admin-meta:origin-baseline-' + item['Image'].split(':')[1][:12]
    u.docker('tag', item['Image'], base)
    dockerfile = ('FROM ' + base + '\nCOPY --chown=10001:10001 app.py /app/kdh/app.py\n').encode()
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode='w') as tf:
        for name, raw in {'Dockerfile': dockerfile, 'app.py': source}.items():
            info = tarfile.TarInfo(name)
            info.size = len(raw)
            info.mode = 0o644
            tf.addfile(info, io.BytesIO(raw))
    result = subprocess.run(['docker', 'build', '--pull=false', '--network=none', '-t', tag, '-'],
                            input=stream.getvalue(), capture_output=True)
    (OUT / 'build.log').write_bytes(result.stdout + result.stderr)
    assert result.returncode == 0
    save('prepared', {'old_id': item['Id'], 'old_image': item['Image'], 'tag': tag,
                      'new_image': u.inspect(tag)['Id'], 'app_sha256': u.sha(source),
                      'protected': protected, 'data': data(),
                      'backup': {k: u.sha(v) for k, v in backups.items()}, 'private': str(PRIVATE)})
    print('Sandbox identity, encrypted backup and minimal image build PASS', flush=True)
    args = ['docker', 'run', '--name', 'kdh-origin-fix-tests-20261021', '--network', 'none',
            '--mount', 'type=bind,source=' + str(u.ROOT / 'tests') + ',target=/app/tests,readonly',
            '--env', 'PYTHONPATH=/app:/app/tests', tag, 'python', '-B', '-m', 'unittest',
            'test_loopback_entry', 'test_app', 'test_viewer_handoff.SQLiteHandoffTests',
            'test_viewer_access.SQLiteViewerTests', 'test_marketing_sandbox_scope',
            'test_vio_handoff.VioHandoffTests', '-v']
    with (OUT / 'python-tests.log').open('wb') as log:
        result = subprocess.run(args, stdout=log, stderr=subprocess.STDOUT)
    save('tests', {'exit_code': result.returncode})
    assert result.returncode == 0
    print('Offline regression tests PASS')


def deploy():
    assert read('tests')['exit_code'] == 0
    p = read('prepared')
    item = u.inspect(ADMIN)
    assert item['Id'] == p['old_id'] and item['Image'] == p['old_image']
    assert u.sha((u.ROOT / 'kdh/app.py').read_bytes()) == p['app_sha256']
    verify_protected()
    assert data() == p['data']
    previous = original()
    assert u.env(item) == u.env(previous)
    rollback = ADMIN + '-before-origin-fix-20261021'
    assert not u.docker('ps', '-aq', '--filter', 'name=^/' + rollback + '$').strip()
    h = item['HostConfig']
    values = u.env(item)
    args = ['create', '--name', ADMIN, '--network', NET, '--ip', '192.168.0.3',
            '--read-only', '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges',
            '--memory', str(h['Memory']), '--memory-swap', str(h['MemorySwap']),
            '--cpus', str(h['NanoCpus'] / 1000000000), '--restart', h['RestartPolicy']['Name'],
            '--user', item['Config']['User'], '--workdir', item['Config']['WorkingDir']]
    for path, options in h['Tmpfs'].items():
        args += ['--tmpfs', path + ':' + options]
    assert len(h['Mounts']) == 1
    mount = h['Mounts'][0]
    assert mount['Type'] == 'volume' and mount['Source'] == 'kdh-meta-2b-appdata-' + RUN
    args += ['--mount', 'type=volume,source=' + mount['Source'] + ',target=' + mount['Target'] + ',volume-nocopy']
    health = item['Config']['Healthcheck']
    assert health['Test'][0] == 'CMD-SHELL'
    args += ['--health-cmd', health['Test'][1], '--health-interval', str(health['Interval']) + 'ns',
             '--health-timeout', str(health['Timeout']) + 'ns', '--health-retries', str(health['Retries'])]
    for key, value in item['Config'].get('Labels', {}).items():
        args += ['--label', key + '=' + value]
    for key in values:
        args += ['--env', key]
    args += [p['tag'], *item['Config']['Cmd']]
    u.docker('stop', '--time', '20', ADMIN)
    u.docker('rename', ADMIN, rollback)
    try:
        u.docker(*args, env={**os.environ, **values})
        created = u.inspect(ADMIN)
        assert u.env(created) == values and created['Mounts'] == item['Mounts']
        for key in ('PortBindings', 'ReadonlyRootfs', 'CapDrop', 'SecurityOpt', 'Memory', 'MemorySwap',
                    'NanoCpus', 'Tmpfs', 'RestartPolicy', 'NetworkMode'):
            assert created['HostConfig'][key] == h[key], key
        u.docker('start', ADMIN)
        u.wait_health(ADMIN)
        assert data() == p['data']
        verify_protected()
        save('deployment', {'status': 'PASS', 'container': ADMIN, 'id': u.inspect(ADMIN)['Id'],
                            'image': p['new_image'], 'rollback': rollback,
                            'business_data': 'unchanged', 'protected_services': 'unchanged'})
        print('Sandbox Admin-only deployment PASS; original config/security/data preserved')
    except Exception:
        if u.docker('ps', '-aq', '--filter', 'name=^/' + ADMIN + '$').strip():
            u.docker('stop', '--time', '20', ADMIN)
            u.docker('rename', ADMIN, ADMIN + '-origin-fix-failed-' + str(int(time.time())))
        u.docker('rename', rollback, ADMIN)
        u.docker('start', ADMIN)
        u.wait_health(ADMIN)
        save('deployment', {'status': 'ROLLED_BACK'})
        raise


if __name__ == '__main__':
    globals()[sys.argv[1]]()
