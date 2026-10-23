"""Presentation-only New update; preserves existing runtime, authentication and data."""
import json
import os
import sys
import time
from pathlib import Path

import shared_viewer as s

u = s.u
OUT = u.ROOT / 'docs/content-shell-20261021'
PRIVATE = Path(os.environ['LOCALAPPDATA']) / 'KDH-Content-Shell-20261021'
BACKUP = u.N + '-before-content-shell-20261021'


def read(name):
    return json.loads((OUT / (name + '.json')).read_text(encoding='utf-8'))


def save(name, value):
    (OUT / (name + '.json')).write_text(json.dumps(value, indent=2), encoding='utf-8')


def stable_signature(name):
    value = u.signature(u.inspect(name))
    value['mounts'] = sorted(value['mounts'], key=lambda m: m['Destination'])
    value['networks'] = sorted(value['networks'])
    return value


def build():
    baseline = read('baseline')
    current = u.inspect(u.N)
    assert u.signature(current) == baseline['container']
    paths = [p for p, digest in baseline['files'].items() if u.sha((u.NEW / p).read_bytes()) != digest]
    assert paths
    previous = s.OUT
    try:
        s.OUT = OUT
        built = s.build_image(current['Image'], u.NEW, paths, 'kdh-new:content-shell-20261021-')
    finally:
        s.OUT = previous
    save('build', built)
    fixture = json.loads((u.NEW / 'tests/fixtures/facebook_content_vio.json').read_text(encoding='utf-8'))
    script = '''import json
from app.mappers.bundle import BundleViewMapper
from app.mappers.dashboard import dashboard_context
from jinja2 import Environment,FileSystemLoader,select_autoescape
p=json.loads(FIXTURE)
b=BundleViewMapper().map(p,p['report']['id'],1)
c=dashboard_context(b,'facebook_content','/reports/test')
assert [m['value'] for m in c['dashboard']['visible_content_kpis']]==[15,80,10]
h=Environment(loader=FileSystemLoader('templates'),autoescape=select_autoescape()).get_template('pages/facebook_content/index.html').render(**c)
assert 'fc-live-shell' in h and 'fc-agency' not in h
assert 'id="fc-topics"' not in h and 'id="fc-reach"' not in h
print('Immutable image render smoke PASS')
'''.replace('FIXTURE', repr(json.dumps(fixture)))
    result = u.docker('run', '--rm', '-i', '--network', 'none', '--entrypoint', 'python', built['image'], '-', data=script.encode())
    assert b'smoke PASS' in result
    save('smoke', {'status': 'PASS', 'image': built['image']})
    print('Presentation-only image built; offline render smoke PASS')


def deploy():
    baseline = read('baseline'); built = read('build')
    assert read('smoke') == {'status': 'PASS', 'image': built['image']}
    original = u.inspect(u.N)
    assert u.signature(original) == baseline['container']
    assert all(s.data(n) == baseline['data'][n] for n in (u.A, s.VIO))
    protected_names = (u.A, s.VIO, u.PG, s.f.PG, s.VG, s.HOST_RELAY, s.VR, s.PR)
    protected = {n: stable_signature(n) for n in protected_names}
    assert all(value['running'] for value in protected.values()), 'Protected service must be running before update'
    save('protected-before', protected)
    assert original['HostConfig']['LogConfig']['Type'] == 'none'
    assert not original['Config']['Entrypoint']
    assert set(original['NetworkSettings']['Networks']) == {s.PNET, s.VNET, s.HNET}
    assert all(m['Type'] == 'bind' and not m['RW'] and m['Destination'] == '/app/static/layout-preview' for m in original['Mounts'])
    assert not PRIVATE.exists()
    PRIVATE.mkdir()
    (PRIVATE / 'original.dpapi').write_bytes(u.dpapi(json.dumps(original).encode()))
    (OUT / 'previous-startup-manifest.json').write_bytes((s.OUT / 'deployment.json').read_bytes())
    renamed = False
    try:
        u.docker('stop', '--time', '20', u.N)
        u.docker('rename', u.N, BACKUP); renamed = True
        u.docker('update', '--restart=no', BACKUP)
        s.clone(u.N, original, built['image'])
        current = u.inspect(u.N)
        for key in ('LogConfig', 'ReadonlyRootfs', 'CapAdd', 'CapDrop', 'SecurityOpt', 'Sysctls', 'Tmpfs', 'Dns',
                    'Memory', 'MemorySwap', 'NanoCpus', 'PortBindings', 'NetworkMode', 'RestartPolicy'):
            assert current['HostConfig'][key] == original['HostConfig'][key], key
        assert current['Mounts'] == original['Mounts']
        assert u.env(current) == u.env(original)
        assert current['Config']['Cmd'] == original['Config']['Cmd']
        u.docker('start', u.N); u.wait_health(u.N)
        assert all(s.data(n) == baseline['data'][n] for n in (u.A, s.VIO))
        protected_after = {n: stable_signature(n) for n in protected}
        save('protected-after', protected_after)
        assert protected_after == protected
        manifest = s.read('deployment')
        manifest['services'][u.N] = u.signature(u.inspect(u.N))
        s.save('deployment', manifest)
        compose = u.NEW / 'compose.shared.yaml'
        source = compose.read_text(encoding='utf-8')
        current_tag = next(line.strip().split(': ', 1)[1] for line in source.splitlines() if line.strip().startswith('image: '))
        assert u.inspect(current_tag)['Id'] == original['Image']
        compose.write_text(source.replace(current_tag, built['tag']), encoding='utf-8')
        save('deployment', {'status': 'PASS', 'service': u.signature(u.inspect(u.N)), 'rollback': BACKUP,
                            'image': built['tag'], 'protected_services': protected, 'business_data': 'UNCHANGED'})
        print('New 8080 healthy; runtime configuration, other containers and business data unchanged')
    except Exception:
        if renamed:
            if u.docker('ps', '-aq', '--filter', 'name=^/' + u.N + '$').strip():
                u.docker('stop', '--time', '15', u.N)
                u.docker('rename', u.N, u.N + '-content-failed-' + str(int(time.time())))
            u.docker('rename', BACKUP, u.N)
            u.docker('update', '--restart=unless-stopped', u.N)
            u.docker('start', u.N); u.wait_health(u.N)
        save('deployment', {'status': 'ROLLED_BACK'})
        raise


if __name__ == '__main__':
    try:
        {'build': build, 'deploy': deploy}[sys.argv[1]]()
    except Exception as exc:
        import traceback
        last = traceback.extract_tb(exc.__traceback__)[-1]
        print(json.dumps({'status': 'FAIL', 'type': type(exc).__name__, 'line': last.lineno}))
        sys.exit(1)
