"""Controlled local two-Admin/one-Viewer deployment, no business writes."""
import io
import ipaddress
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tarfile
import time
from urllib.parse import urlsplit

from cryptography.fernet import Fernet
import unify_primary as u
import fix_sandbox_origin as f

OUT = u.ROOT / 'docs/shared-viewer-20261021'
PRIVATE = Path(os.environ['LOCALAPPDATA']) / 'KDH-Shared-Viewer-20261021'
VIO = f.ADMIN
VR = 'kdh-vio-relay-phase9-20261019'
VG = 'kdh-meta-3-egress-' + f.RUN
HOST_RELAY = 'kdh-meta-2b-relay-' + f.RUN
VNET = 'kdh-vio-handoff-phase9-recovery-20261019'
HNET = 'kdh-vio-host-phase9-20261019'
PNET = 'kdh-shared-viewer-primary-20261021'
PR = 'kdh-shared-viewer-primary-relay'


def save(name, data):
    OUT.mkdir(exist_ok=True)
    (OUT / (name + '.json')).write_text(json.dumps(data, indent=2), encoding='utf-8')


def read(name):
    return json.loads((OUT / (name + '.json')).read_text(encoding='utf-8'))


def box():
    return Fernet(u.dpapi((PRIVATE / 'key.dpapi').read_bytes(), True))


def originals():
    return json.loads(box().decrypt((PRIVATE / 'originals.fernet').read_bytes()))


def data(name):
    result = json.loads(u.code(name, u.INTEGRITY))
    return {k: v for k, v in result.items() if k not in (
        'sessions', 'events', 'attempts', 'viewer_handoffs', 'delegated_viewer_sessions')}


def prepare():
    assert not PRIVATE.exists()
    PRIVATE.mkdir()
    # Generate the stored key separately, so no key is printed or put in Git.
    key = Fernet.generate_key()
    cipher = Fernet(key)
    (PRIVATE / 'key.dpapi').write_bytes(u.dpapi(key))
    names = (u.A, u.N, u.PG, VIO, f.PG, VG, HOST_RELAY, VR, 'kdh-vio-new-phase9-20261019')
    original = {n: u.inspect(n) for n in names}
    (PRIVATE / 'originals.fernet').write_bytes(cipher.encrypt(json.dumps(original).encode()))
    assert u.env(original[VIO])['META_CLIENT_ID'] == 'client_meta_sandbox'
    assert original[VIO]['Image'] == f.read('deployment')['image']
    assert original[u.A]['Image'] == u.read('build')['admin']['image']
    assert original[u.N]['Image'] == u.read('build')['new']['image']
    assert u.env(original[VIO])['ADMIN_SESSION_COOKIE_NAME'] != u.env(original[u.A]).get('ADMIN_SESSION_COOKIE_NAME', 'kdh_session')
    assert {m['Name'] for m in original[f.PG]['Mounts']} == {'kdh-meta-2b-pgdata-' + f.RUN}
    assert {m['Name'] for m in original[u.PG]['Mounts']} == {'kdh-report-admin_postgres-data'}
    assert not original['kdh-vio-new-phase9-20261019']['State']['Running']
    net = u.inspect(VNET)
    assert net['Internal'] and not net['Containers']
    assert u.inspect('kdh-meta-2b-ingress-' + f.RUN)['Options']['com.docker.network.bridge.enable_icc'] == 'false'
    # Stop only obsolete deployments/tests belonging to this project's earlier work.
    retired = [u.A + '-rollback-unified-20261020', u.N + '-rollback-unified-20261020',
        'kdh-unified-20261020-admin-smoke', 'kdh-unified-20261020-postgres-tests',
        'kdh-unified-admin-offline-20261020', 'kdh-unified-extra-postgres-20261020',
        'kdh-unified-facebook-postgres-20261020']
    saved_retired = {}
    for name in retired:
        item = u.inspect(name)
        saved_retired[name] = {'id': item['Id'], 'restart': item['HostConfig']['RestartPolicy']}
        u.docker('update', '--restart=no', name)
        if item['State']['Running']:
            u.docker('stop', '--time', '15', name)
    save('retired', saved_retired)
    for name in (f.PG, VG, VIO, HOST_RELAY, VR):
        if not u.inspect(name)['State']['Running']:
            u.docker('start', name)
        if name in (f.PG, VIO):
            u.wait_health(name)
    assert u.inspect(VIO)['NetworkSettings']['Networks'][f.NET]['IPAddress'] == '192.168.0.3'
    assert u.inspect(VR)['NetworkSettings']['Networks'][VNET]['IPAddress'] == '192.168.96.2'
    backups = {}
    for name, pg in ((u.A, u.PG), (VIO, f.PG)):
        values = u.env(original[name]); db = urlsplit(values['DATABASE_URL'])
        assert db.path == ('/kdh_report' if name == u.A else '/meta_acceptance_20261016_132836')
        raw = u.docker('exec', pg, 'pg_dump', '-U', u.env(original[pg])['POSTGRES_USER'], '-d', db.path[1:], '-Fc')
        assert raw.startswith(b'PGDMP')
        u.docker('exec', '-i', pg, 'pg_restore', '--list', data=raw)
        (PRIVATE / (name + '.dump.fernet')).write_bytes(cipher.encrypt(raw))
        assert cipher.decrypt((PRIVATE / (name + '.dump.fernet')).read_bytes()) == raw
        backups[name] = u.sha(raw)
        raw = u.docker('exec', name, 'tar', '-C', '/app/instance', '-cf', '-', '.')
        (PRIVATE / (name + '.appdata.fernet')).write_bytes(cipher.encrypt(raw))
    save('baseline', {'data': {n: data(n) for n in (u.A, VIO)}, 'backups': backups,
        'services': {n: u.signature(u.inspect(n)) for n in names},
        'heads': {str(root): u.call('git', '-C', str(root), 'rev-parse', 'HEAD').decode().strip() for root in (u.ROOT, u.NEW)},
        'status': {str(root): u.call('git', '-C', str(root), 'status', '--short').decode() for root in (u.ROOT, u.NEW)}})
    print('Identity, sandbox recovery and encrypted backup PASS')


def build_image(base, root, paths, tag_prefix):
    files = {p: (root / p).read_bytes() for p in paths}
    digest = u.sha(b''.join(k.encode() + files[k] for k in sorted(files)))
    tag = tag_prefix + digest[:12]
    base_tag = tag_prefix + 'base'
    u.docker('tag', base, base_tag)
    dockerfile = 'FROM ' + base_tag + '\n' + ''.join('COPY --chown=10001:10001 ' + p + ' /app/' + p + '\n' for p in files)
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode='w') as tf:
        for path, raw in {'Dockerfile': dockerfile.encode(), **files}.items():
            info = tarfile.TarInfo(path); info.size = len(raw); info.mode = 0o644
            tf.addfile(info, io.BytesIO(raw))
    r = subprocess.run(['docker', 'build', '--network=none', '--pull=false', '-t', tag, '-'], input=stream.getvalue(), capture_output=True)
    (OUT / (tag_prefix.split(':')[0] + '-build.log')).write_bytes(r.stdout + r.stderr)
    assert r.returncode == 0
    return {'tag': tag, 'image': u.inspect(tag)['Id'], 'files': {p: u.sha(v) for p, v in files.items()}}


def build():
    old = originals()
    result = {'admin': build_image(old[u.A]['Image'], u.ROOT, ['kdh/app.py'], 'kdh-admin:shared-20261021-'),
        'new': build_image(old[u.N]['Image'], u.NEW, ['app/config.py', 'app/viewer_environment.py',
            'app/routes/viewer.py', 'app/routes/handoff.py', 'ops/shared_viewer_entrypoint.py'], 'kdh-new:shared-20261021-')}
    save('build', result)
    print('Both minimal immutable images built; no credentials in build context')


def clone(name, item, image, updates=None, fixed_ip=None):
    c, h = item['Config'], item['HostConfig']
    values = {**u.env(item), **(updates or {})}
    args = ['create', '--name', name, '--network', h['NetworkMode'], '--restart', 'unless-stopped',
        '--user', c['User'], '--workdir', c['WorkingDir']]
    if fixed_ip: args += ['--ip', fixed_ip]
    if h.get('LogConfig', {}).get('Type'):
        args += ['--log-driver', h['LogConfig']['Type']]
        for key, value in h['LogConfig'].get('Config', {}).items():
            args += ['--log-opt', key + '=' + value]
    if h.get('Init'): args += ['--init']
    if h['ReadonlyRootfs']: args += ['--read-only']
    for key, flag in [('CapDrop', '--cap-drop'), ('CapAdd', '--cap-add'), ('SecurityOpt', '--security-opt'), ('Dns', '--dns')]:
        for value in h.get(key) or []: args += [flag, value]
    for key, flag in [('Memory', '--memory'), ('MemorySwap', '--memory-swap')]:
        if h.get(key): args += [flag, str(h[key])]
    if h.get('NanoCpus'): args += ['--cpus', str(h['NanoCpus'] / 1e9)]
    for path, value in (h.get('Tmpfs') or {}).items(): args += ['--tmpfs', path + ':' + value]
    for key, value in (h.get('Sysctls') or {}).items(): args += ['--sysctl', key + '=' + value]
    for alias in item['NetworkSettings']['Networks'][h['NetworkMode']].get('Aliases') or []:
        args += ['--network-alias', alias]
    for port, bindings in (h.get('PortBindings') or {}).items():
        for b in bindings:
            assert b['HostIp'] == '127.0.0.1'
            args += ['--publish', b['HostIp'] + ':' + b['HostPort'] + ':' + port]
    for m in item['Mounts']:
        source = m.get('Name', m['Source']) if m['Type'] == 'volume' else m['Source']
        args += ['--mount', 'type=' + m['Type'] + ',source=' + source + ',target=' + m['Destination']
            + (',readonly' if not m['RW'] else '') + (',volume-nocopy' if m['Type'] == 'volume' else '')]
    health = c.get('Healthcheck')
    if health:
        args += ['--health-cmd', health['Test'][1] if health['Test'][0] == 'CMD-SHELL' else shlex.join(health['Test'][1:]),
            '--health-interval', str(health['Interval']) + 'ns', '--health-timeout', str(health['Timeout']) + 'ns',
            '--health-start-period', str(health.get('StartPeriod', 0)) + 'ns', '--health-retries', str(health['Retries'])]
    for key, value in (c.get('Labels') or {}).items():
        if key not in ('com.docker.compose.config-hash', 'com.docker.compose.image'):
            args += ['--label', key + '=' + value]
    for key in values: args += ['--env', key]
    args += [image, *c['Cmd']]
    u.docker(*args, env={**os.environ, **values})
    for network, spec in item['NetworkSettings']['Networks'].items():
        if network == h['NetworkMode']: continue
        cli = []
        ip = (spec.get('IPAMConfig') or {}).get('IPv4Address')
        if ip: cli += ['--ip', ip]
        u.docker('network', 'connect', *cli, network, name)
    assert u.env(u.inspect(name)) == values


def relay():
    assert not u.docker('network', 'ls', '-q', '--filter', 'name=^' + PNET + '$').strip()
    u.docker('network', 'create', '--internal', '--label', 'kdh.shared=20261021', PNET)
    net = u.inspect(PNET)
    config = net['IPAM']['Config'][0]
    peer = str(next(ip for ip in ipaddress.ip_network(config['Subnet']).hosts() if str(ip) != config['Gateway']))
    original = u.inspect(VR)
    target = PRIVATE / 'primary-relay'; target.mkdir()
    source = Path(original['Mounts'][0]['Source'])
    for name in ('launch.py', 'serve.py'):
        (target / name).write_bytes((source / name).read_bytes())
    upstream = u.inspect(u.A)['NetworkSettings']['Networks']['kdh-report-admin_default']['IPAddress']
    pg = u.inspect(u.PG)['NetworkSettings']['Networks']['kdh-report-admin_default']['IPAddress']
    (target / 'config.json').write_text(json.dumps({'listen_ip': peer, 'upstream_ip': upstream, 'pg_ip': pg}))
    args = ['create', '--name', PR, '--network', PNET, '--ip', peer, '--restart', 'unless-stopped',
        '--entrypoint', 'python', '--dns', '127.0.0.1', '--user', '0:0', '--read-only', '--cap-drop', 'ALL',
        '--cap-add', 'NET_ADMIN', '--cap-add', 'SETUID', '--cap-add', 'SETGID', '--cap-add', 'SETPCAP',
        '--security-opt', 'no-new-privileges', '--sysctl', 'net.ipv6.conf.all.disable_ipv6=1',
        '--sysctl', 'net.ipv4.ip_forward=0', '--memory', '128m', '--cpus', '0.5', '--log-driver', 'none',
        '--mount', 'type=bind,source=' + str(target) + ',target=/relay,readonly', original['Image'], *original['Config']['Cmd']]
    u.docker(*args)
    u.docker('network', 'connect', 'kdh-report-admin_default', PR)
    u.docker('start', PR)
    save('relay', {'name': PR, 'listener': peer, 'upstream': upstream, 'subnet': config['Subnet']})
    print('Dedicated primary relay created; no shared Viewer membership in either database network')


def smoke():
    built = read('build')
    name = 'kdh-shared-viewer-smoke-20261021'
    values = {'APP_ENV': 'production', 'REPORT_VIO_VIEWER_ENABLED': 'true',
        'REPORT_ADMIN_BASE_URL': 'http://primary.invalid:8090', 'REPORT_ADMIN_PUBLIC_URL': 'http://localhost:8090',
        'REPORT_NEW_PUBLIC_URL': 'http://localhost:8000', 'REPORT_SERVICE_TOKEN': 'disposable-main-' + 'm' * 32,
        'REPORT_VIO_ADMIN_BASE_URL': 'http://vio.invalid:8090', 'REPORT_VIO_ADMIN_PUBLIC_URL': 'http://localhost:8191',
        'REPORT_VIO_NEW_PUBLIC_URL': 'http://127.0.0.1:8000', 'REPORT_VIO_SERVICE_TOKEN': 'disposable-vio-' + 'v' * 32}
    args = ['run', '-d', '--name', name, '--network', 'none']
    for k in values: args += ['--env', k]
    args += [built['new']['tag']]
    u.docker(*args, env={**os.environ, **values})
    try:
        u.wait_health(name)
        checks = json.loads(u.code(name, """import urllib.request,urllib.error,json
class NoRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,*args): return None
opener=urllib.request.build_opener(NoRedirect())
out={}
for host in ('localhost','127.0.0.1'):
 try: r=opener.open('http://'+host+':8000/reports')
 except urllib.error.HTTPError as e: r=e
 out[host]={'status':r.code,'location':r.headers.get('Location')}
print(json.dumps(out))
"""))
        assert checks['localhost'] == {'status': 303, 'location': 'http://localhost:8090/viewer/reports'}
        assert checks['127.0.0.1'] == {'status': 303, 'location': 'http://localhost:8191/viewer/reports'}
    finally:
        u.docker('stop', '--time', '10', name)
    args = ['docker', 'run', '--name', 'kdh-shared-admin-tests-20261021', '--network', 'none',
        '--mount', 'type=bind,source=' + str(u.ROOT / 'tests') + ',target=/app/tests,readonly',
        '--env', 'PYTHONPATH=/app:/app/tests', built['admin']['tag'], 'python', '-B', '-m', 'unittest',
        'test_loopback_entry', 'test_app', 'test_viewer_handoff.SQLiteHandoffTests',
        'test_viewer_access.SQLiteViewerTests', 'test_marketing_sandbox_scope', 'test_vio_handoff.VioHandoffTests', '-v']
    with (OUT / 'admin-tests.log').open('wb') as log:
        tested = subprocess.run(args, stdout=log, stderr=subprocess.STDOUT)
    save('smoke', {'new': checks, 'admin_tests_exit': tested.returncode})
    assert tested.returncode == 0
    print('Isolated image smoke and Admin regression PASS')


def deploy():
    baseline = read('baseline'); old = originals(); built = read('build')
    assert read('smoke')['admin_tests_exit'] == 0
    assert all(data(n) == baseline['data'][n] for n in (u.A, VIO))
    done = []
    backups = {n: n + '-before-shared-20261021' for n in (u.A, VIO, u.N)}
    try:
        for name, image, updates, fixed in (
                (u.A, built['admin']['tag'], {}, read('relay')['upstream']),
                (VIO, old[VIO]['Image'], {'REPORT_NEW_BASE_URL': 'http://127.0.0.1:8080'}, '192.168.0.3')):
            u.docker('stop', '--time', '20', name)
            u.docker('rename', name, backups[name]); done.append(name)
            u.docker('update', '--restart=no', backups[name])
            clone(name, old[name], image, updates, fixed)
            u.docker('start', name); u.wait_health(name)
        u.docker('stop', '--time', '20', u.N)
        u.docker('rename', u.N, backups[u.N]); done.append(u.N)
        u.docker('update', '--restart=no', backups[u.N])
        values = {'APP_ENV': 'production', 'DEBUG': 'false', 'REPORT_PREVIEW_ENABLED': 'false',
            'REPORT_ADMIN_BASE_URL': 'http://' + read('relay')['listener'] + ':8090',
            'REPORT_ADMIN_PUBLIC_URL': 'http://localhost:8090', 'REPORT_NEW_PUBLIC_URL': 'http://localhost:8080',
            'REPORT_SERVICE_TOKEN': u.env(old[u.A])['REPORT_SERVICE_TOKEN'],
            'REPORT_VIO_VIEWER_ENABLED': 'true', 'REPORT_VIO_ADMIN_BASE_URL': 'http://192.168.96.2:8090',
            'REPORT_VIO_ADMIN_PUBLIC_URL': 'http://localhost:8191', 'REPORT_VIO_NEW_PUBLIC_URL': 'http://127.0.0.1:8080',
            'REPORT_VIO_SERVICE_TOKEN': u.env(old[VIO])['REPORT_SERVICE_TOKEN']}
        assert values['REPORT_SERVICE_TOKEN'] != values['REPORT_VIO_SERVICE_TOKEN']
        args = ['create', '--name', u.N, '--network', HNET, '--publish', '127.0.0.1:8080:8000',
            '--restart', 'unless-stopped', '--dns', '127.0.0.1', '--user', '0:0', '--read-only', '--cap-drop', 'ALL',
            '--cap-add', 'NET_ADMIN', '--cap-add', 'SETUID', '--cap-add', 'SETGID', '--cap-add', 'SETPCAP',
            '--security-opt', 'no-new-privileges', '--sysctl', 'net.ipv6.conf.all.disable_ipv6=1',
            '--sysctl', 'net.ipv4.ip_forward=0', '--memory', '512m', '--cpus', '1', '--log-driver', 'none',
            '--tmpfs', '/tmp:rw,nosuid,nodev,noexec,size=64m,mode=1777',
            '--health-interval', '3s', '--health-timeout', '4s', '--health-retries', '10',
            '--label', 'kdh.shared=20261021', '--label', 'com.docker.compose.project=kdh-report-admin',
            '--label', 'com.docker.compose.service=new']
        for key in values: args += ['--env', key]
        args += [built['new']['tag'], 'python', '-B', '/app/ops/shared_viewer_entrypoint.py']
        u.docker(*args, env={**os.environ, **values})
        for network in (PNET, VNET): u.docker('network', 'connect', network, u.N)
        u.docker('start', u.N); u.wait_health(u.N)
        assert all(data(n) == baseline['data'][n] for n in (u.A, VIO))
        save('deployment', {'status': 'PASS', 'rollback': backups,
            'services': {n: u.signature(u.inspect(n)) for n in done}})
        print('Shared Viewer and both Admin applications healthy; business data unchanged')
    except Exception:
        for name in reversed(done):
            if u.docker('ps', '-aq', '--filter', 'name=^/' + name + '$').strip():
                u.docker('stop', '--time', '15', name)
                u.docker('rename', name, name + '-shared-failed-' + str(int(time.time())))
            u.docker('rename', backups[name], name)
            u.docker('start', name); u.wait_health(name)
        save('deployment', {'status': 'ROLLED_BACK'})
        raise


def start():
    """Start only verified current services, never rebuild/recreate or run archives."""
    deployed = read('deployment')
    assert deployed['status'] == 'PASS'
    for name, expected in deployed['services'].items():
        actual = u.inspect(name)
        assert actual['Id'] == expected['id'] and actual['Image'] == expected['image'], name
    for name in (u.PG, f.PG, VG, HOST_RELAY, VR):
        actual = u.inspect(name); expected = read('baseline')['services'][name]
        assert actual['Id'] == expected['id'] and actual['Image'] == expected['image'], name
    for name in (u.PG, f.PG, VG, u.A, VIO, HOST_RELAY, VR, PR, u.N):
        if not u.inspect(name)['State']['Running']:
            u.docker('start', name)
        if u.inspect(name)['Config'].get('Healthcheck'):
            u.wait_health(name)
    print('Admin chinh: http://localhost:8090')
    print('Admin VIO: http://localhost:8191')
    print('New dung chung cong 8080; mo bao cao tu dung Admin.')


def rollback():
    """Application-only rollback; keep both databases, grants and reports intact."""
    deployed = read('deployment')
    assert deployed['status'] == 'PASS'
    for name in (u.N, VIO, u.A):
        assert u.inspect(name)['Id'] == deployed['services'][name]['id']
        u.docker('stop', '--time', '20', name)
        u.docker('rename', name, name + '-shared-retained-' + str(int(time.time())))
        u.docker('rename', deployed['rollback'][name], name)
        u.docker('update', '--restart=unless-stopped', name)
        u.docker('start', name); u.wait_health(name)
    prior = 'kdh-vio-new-phase9-20261019'
    assert u.inspect(prior)['Id'] == originals()[prior]['Id']
    u.docker('start', prior); u.wait_health(prior)
    save('rollback', {'status': 'PASS', 'data': {n: data(n) for n in (u.A, VIO)}})
    print('Previous applications restored; databases untouched')


if __name__ == '__main__':
    globals()[sys.argv[1]]()
