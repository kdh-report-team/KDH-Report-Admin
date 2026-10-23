"""Update existing VIO Admin and shared New only; no business mutations."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from cryptography.fernet import Fernet
import deploy_content_insights as d

s, u = d.s, d.u
OUT = u.ROOT / 'docs/tonight-delivery-20261021'
PRIVATE = Path(os.environ['LOCALAPPDATA']) / 'KDH-Tonight-Delivery-20261021'
NEW_PATHS = ['app/mappers/bundle.py', 'app/mappers/dashboard.py', 'app/mappers/facebook_content.py',
             'app/schemas/bundle_view.py', 'templates/pages/snapshot/components.html',
             'static/css/pages/facebook-content.css', 'static/js/shared/charts.js'] + [str(p.relative_to(u.NEW)).replace('\\', '/')
                for p in (u.NEW / 'templates/pages/facebook_content').rglob('*.html')]


def configure_admin():
    d.OUT = OUT / 'admin'
    d.PRIVATE = PRIVATE / 'admin'
    d.BACKUP = d.ADMIN + '-before-tonight-20261021'


def save(name, value):
    (OUT / (name + '.json')).write_text(json.dumps(value, indent=2), encoding='utf-8')


def read(name):
    return json.loads((OUT / (name + '.json')).read_text(encoding='utf-8'))


def prepare():
    OUT.mkdir(exist_ok=True)
    PRIVATE.mkdir(exist_ok=False)
    configure_admin()
    d.prepare(expected_id='57c571479a8063163a1de424142bf213b51361392ddd67c9063a3e6d9074397b')
    original = u.inspect(u.N)
    assert original['Image'] == 'sha256:fb1089d786b5b3f5a9d383b77e2c13024fb32435a0eff505395a1416943228db'
    assert original['State']['Health']['Status'] == 'healthy'
    assert original['HostConfig']['PortBindings'] == {'8000/tcp': [{'HostIp': '127.0.0.1', 'HostPort': '8080'}]}
    assert set(original['NetworkSettings']['Networks']) == {s.PNET, s.VNET, s.HNET}
    assert original['HostConfig']['LogConfig']['Type'] == 'none'
    assert all(m['Type'] == 'bind' and not m['RW'] and m['Destination'] == '/app/static/layout-preview' for m in original['Mounts'])
    key = Fernet.generate_key()
    (PRIVATE / 'new-key.dpapi').write_bytes(u.dpapi(key))
    (PRIVATE / 'new-original.fernet').write_bytes(Fernet(key).encrypt(json.dumps(original).encode()))
    save('new-baseline', {'service': d.signature(u.N), 'files': {p: u.sha((u.NEW / p).read_bytes()) for p in NEW_PATHS}})
    print('Existing Admin/New identities and encrypted rollback configuration verified', flush=True)


def build():
    configure_admin()
    d.build()
    build_new()


def build_new():
    assert d.signature(u.N) == read('new-baseline')['service']
    previous = s.OUT
    try:
        s.OUT = OUT
        built = s.build_image(u.inspect(u.N)['Image'], u.NEW, NEW_PATHS, 'kdh-new:tonight-content-20261021-')
    finally:
        s.OUT = previous
    save('new-build', built)
    args = ['docker', 'run', '--rm', '--network', 'none', '--entrypoint', 'python',
            '--mount', 'type=bind,source=' + str(u.NEW / 'tests') + ',target=/app/tests,readonly',
            '--mount', 'type=bind,source=' + str(u.NEW / 'scripts') + ',target=/app/scripts,readonly',
            '--env', 'PYTHONPATH=/app:/app/tests', built['image'], '-B', '-m', 'pytest', '-q', '-p', 'no:cacheprovider']
    with (OUT / 'new-image-tests.log').open('wb') as log:
        result = subprocess.run(args, stdout=log, stderr=subprocess.STDOUT)
    save('new-image-tests', {'exit_code': result.returncode, 'image': built['image']})
    assert result.returncode == 0
    print('Both exact images tested offline successfully', flush=True)


def deploy_admin():
    configure_admin()
    assert read('new-image-tests')['exit_code'] == 0
    temp = Path(os.environ['TEMP'])
    pg = json.loads((temp / 'KDH-FB-Tonight-20261021-postgres-final/results.json').read_text())
    offline = json.loads((temp / 'KDH-FB-Tonight-20261021-offline-result.json').read_text())
    assert pg['success'] and pg['summary']['fail'] == 0 and pg['summary']['error'] == 0 and pg['summary']['skip'] == 0
    assert offline['fail'] == 0 and offline['error'] == 0
    assert pg['cleanup'] == 'removed_verified_disposable_container_only'
    # Preflight also observed the disposable acceptance container. Its verified
    # cleanup is expected; business service identities must still match exactly.
    baseline = d.read('prepared')
    name = pg['run']
    if name in baseline['protected']:
        assert baseline['protected'][name]['id'] == pg['database']['container_id']
        assert not u.docker('ps', '-aq', '--filter', 'name=^/' + name + '$').strip()
        save('disposable-test-cleanup', {'name': name, 'id': baseline['protected'][name]['id'], 'cleanup': pg['cleanup']})
        del baseline['protected'][name]
        d.save('prepared', baseline)
    save('acceptance-gates', {'postgres': pg['summary'], 'offline': {'run': offline['run'],
        'fail': offline['fail'], 'error': offline['error'], 'skip': len(offline['skipped'])}, 'new_image': '317 PASS'})
    d.deploy()


def deploy_new():
    configure_admin()
    assert d.read('deployment')['status'] == 'PASS'
    built = read('new-build')
    assert read('new-image-tests') == {'exit_code': 0, 'image': built['image']}
    assert {p: u.sha((u.NEW / p).read_bytes()) for p in NEW_PATHS} == built['files']
    assert d.signature(u.N) == read('new-baseline')['service']
    key = u.dpapi((PRIVATE / 'new-key.dpapi').read_bytes(), True)
    original = json.loads(Fernet(key).decrypt((PRIVATE / 'new-original.fernet').read_bytes()))
    assert u.env(original) == u.env(u.inspect(u.N))
    protected = {n: d.signature(n) for n in d.read('prepared')['protected'] if n != u.N}
    protected[d.ADMIN] = d.signature(d.ADMIN)
    business = s.data(d.ADMIN)
    backup = u.N + '-before-tonight-content-20261021'
    assert not u.docker('ps', '-aq', '--filter', 'name=^/' + backup + '$').strip()
    (OUT / 'before-new-startup-manifest.json').write_bytes((s.OUT / 'deployment.json').read_bytes())
    renamed = False
    try:
        u.docker('stop', '--time', '20', u.N)
        u.docker('rename', u.N, backup)
        renamed = True
        u.docker('update', '--restart=no', backup)
        s.clone(u.N, original, built['image'])
        current = u.inspect(u.N)
        for key in ('LogConfig', 'ReadonlyRootfs', 'CapAdd', 'CapDrop', 'SecurityOpt', 'Sysctls', 'Tmpfs', 'Dns',
                    'Memory', 'MemorySwap', 'NanoCpus', 'PortBindings', 'NetworkMode', 'RestartPolicy'):
            a, b = current['HostConfig'].get(key), original['HostConfig'].get(key)
            if key == 'Dns': a, b = a or [], b or []
            assert a == b, key
        assert current['Mounts'] == original['Mounts'] and u.env(current) == u.env(original)
        assert current['Config']['Cmd'] == original['Config']['Cmd']
        u.docker('start', u.N)
        u.wait_health(u.N)
        assert s.data(d.ADMIN) == business
        assert {n: d.signature(n) for n in protected} == protected
        assert {n: d.network_signature(n) for n in d.read('prepared')['networks']} == d.read('prepared')['networks']
        manifest = s.read('deployment')
        manifest['services'][u.N] = u.signature(u.inspect(u.N))
        s.save('deployment', manifest)
        compose = u.NEW / 'compose.shared.yaml'
        content = compose.read_text(encoding='utf-8')
        old_tag = next(line.strip().split(': ', 1)[1] for line in content.splitlines() if line.strip().startswith('image: '))
        assert u.inspect(old_tag)['Id'] == original['Image']
        (OUT / 'previous-new-compose.yaml').write_text(content, encoding='utf-8')
        compose.write_text(content.replace(old_tag, built['tag']), encoding='utf-8')
        save('deployment', {'status': 'PASS', 'admin': d.read('deployment'), 'new': d.signature(u.N),
                            'new_tag': built['tag'], 'new_rollback': backup,
                            'business_data': 'UNCHANGED', 'other_services': 'UNCHANGED', 'networks': 'UNCHANGED'})
        print('Admin 8191 and New 8080 updated, healthy; data/isolation preserved', flush=True)
    except Exception:
        if renamed:
            if u.docker('ps', '-aq', '--filter', 'name=^/' + u.N + '$').strip():
                u.docker('stop', '--time', '15', u.N)
                u.docker('rename', u.N, u.N + '-tonight-failed-' + str(int(time.time())))
            u.docker('rename', backup, u.N)
            u.docker('update', '--restart=unless-stopped', u.N)
            u.docker('start', u.N)
            u.wait_health(u.N)
            (s.OUT / 'deployment.json').write_bytes((OUT / 'before-new-startup-manifest.json').read_bytes())
        save('deployment', {'status': 'NEW_ROLLED_BACK'})
        raise


if __name__ == '__main__':
    try:
        {'prepare': prepare, 'build': build, 'build-new': build_new, 'deploy-admin': deploy_admin, 'deploy-new': deploy_new}[sys.argv[1]]()
    except Exception as exc:
        import traceback
        last = traceback.extract_tb(exc.__traceback__)[-1]
        print(json.dumps({'status': 'FAIL', 'type': type(exc).__name__, 'line': last.lineno}))
        sys.exit(1)
