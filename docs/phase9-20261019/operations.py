"""Approved Phase 9 sandbox operations. Never print credentials or raw inspect.

Each stage checks its prior evidence; no production service is modified.
"""
import io
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import tarfile
import time
import uuid

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
NEW = ROOT.parent / 'KDH-Report-New-VIO-Phase9'
sys.path[:0] = [str(ROOT / 'docs/phase5-20261018'), str(ROOT / 'docs/phase5b-20261018'),
               str(ROOT / 'docs/ui-deployment-20261019')]
from cold_backup import docker, inspect, digest, dpapi, RUN
from runtime_common import rows, sql, NET
from deploy_ui import integrity, app_hashes, service_signature
from cryptography.fernet import Fernet

ADMIN = 'kdh-meta-2b-admin-' + RUN
PG = 'kdh-meta-2b-pg-' + RUN
GATEWAY = 'kdh-meta-3-egress-' + RUN
RELAY = 'kdh-meta-2b-relay-' + RUN
INGRESS = 'kdh-meta-2b-ingress-' + RUN
HANDOFF_NET = 'kdh-vio-handoff-phase9-recovery-20261019'
HOST_NET = 'kdh-vio-host-phase9-20261019'
SIDECAR = 'kdh-vio-relay-phase9-20261019'
EXPECTED_ADMIN = '41a7100e18cbde6d0aa1d58c281a0ad96086b3023b67f73c3a53ee38328cd104'
EXPECTED_IMAGE = 'sha256:61fc38a6e3d5e64271db0d88ed994b7d355f659d0a3dbbe2dee68632d9baa030'
NEW_NAME = 'kdh-vio-new-phase9-20261019'
ADMIN_FILES = ['kdh/core.py', 'kdh/viewer_handoff.py', 'kdh/marketing_console.py',
               'kdh/report_bundle_routes.py', 'static/marketing.js']


def save(name, value):
    (HERE / (name + '.json')).write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


def read(name):
    return json.loads((HERE / (name + '.json')).read_text(encoding='utf-8'))


def env(item):
    return dict(v.split('=', 1) for v in item['Config']['Env'])


def create(args, values):
    # Pass names in argv, values only through the child's private environment.
    image, command = args.pop('image'), args.pop('command', [])
    cli = args['cli']
    for key in values: cli += ['--env', key]
    r = subprocess.run(['docker', 'create', *cli, image, *command],
                       env=dict(os.environ, **values), capture_output=True)
    assert r.returncode == 0, 'container create failed (details withheld)'
    return r.stdout.decode().strip()


def private_dir():
    path = Path(os.environ['LOCALAPPDATA']) / 'KDH-Meta-Acceptance-Secrets' / RUN / 'phase9'
    path.mkdir(exist_ok=True)
    return path


def free_port(port):
    with socket.socket() as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        s.bind(('127.0.0.1', port))


def host_network(empty=True):
    existing = json.loads(docker('network', 'inspect', HOST_NET))[0]
    assert existing['Labels'].get('kdh.phase9.run') == RUN
    assert not existing['Internal']
    assert existing['Options'].get('com.docker.network.bridge.enable_icc') == 'false'
    assert existing['Options'].get('com.docker.network.bridge.enable_ip_masquerade') == 'false'
    if (HERE / 'host-network.json').exists():
        assert existing['Id'] == read('host-network')['id']
    if empty:
        assert not existing['Containers']
    return existing


def stable_networks(networks):
    keys=('NetworkID','IPAddress','IPPrefixLen','Gateway','GlobalIPv6Address','GlobalIPv6PrefixLen')
    return {name:{key:details.get(key) for key in keys if key in details}
            for name,details in networks.items()}


def verify_recovery_preflight():
    baseline=read('preflight')
    private=private_dir()
    admin=inspect(ADMIN);pg=inspect(PG)
    assert admin['Id']==EXPECTED_ADMIN and admin['Image']==baseline['admin_image']
    assert pg['Id']==baseline['services'][PG]['Id'] and pg['Image']==baseline['services'][PG]['Image']
    assert admin['State']['Status']=='exited' and pg['State']['Status']=='exited'
    assert not admin['State']['OOMKilled'] and not pg['State']['OOMKilled']
    pg_expected=baseline['services'][PG];pg_actual=service_signature(pg)
    assert pg_actual['HostConfig']==pg_expected['HostConfig'] and pg_actual['Mounts']==pg_expected['Mounts']
    for name in (GATEWAY,RELAY):
        info=inspect(name)
        assert info['Id']==baseline['services'][name]['Id'] and info['Image']==baseline['services'][name]['Image']
        assert info['State']['Status']=='exited' and not info['State']['OOMKilled']
        expected=baseline['services'][name]
        actual=service_signature(info)
        assert actual['HostConfig']==expected['HostConfig'] and actual['Mounts']==expected['Mounts']
    rollback_env=json.loads(dpapi((private/'rollback-env.dpapi').read_bytes(),decrypt=True))
    assert env(admin)==rollback_env
    assert not admin['HostConfig']['PortBindings']
    assert {m['Name'] for m in admin['Mounts']}=={'kdh-meta-2b-appdata-'+RUN}
    assert {m['Name'] for m in pg['Mounts']}=={'kdh-meta-2b-pgdata-'+RUN}
    assert not pg['HostConfig']['PortBindings']
    backup=baseline['backup'];folder=Path(backup['directory']);key_file=folder.parent/'backup-key.dpapi'
    assert backup['prior_restore']=='PASS' and folder.is_dir() and key_file.is_file()
    box=Fernet(dpapi(key_file.read_bytes(),decrypt=True))
    assert set(backup['checksums'])=={'database.dump','appdata.tar','admin-env.json'}
    for name,expected_hash in backup['checksums'].items():
        encrypted=(folder/(name+'.fernet')).read_bytes()
        raw=box.decrypt(encrypted)
        assert digest(raw)==expected_hash
        if name=='database.dump':
            assert raw.startswith(b'PGDMP')
        elif name=='appdata.tar':
            with tarfile.open(fileobj=io.BytesIO(raw),mode='r:*') as archive:
                assert archive.getmembers()
        else:
            assert json.loads(raw)==rollback_env
    token=dpapi((private/'service-token.dpapi').read_bytes(),decrypt=True)
    assert len(token)>=48
    # All original network objects must still be the exact preflight networks.
    for signature in baseline['services'].values():
        for name,details in signature['networks'].items():
            current=json.loads(docker('network','inspect',name))[0]
            assert current['Id']==details['NetworkID']
    new8080=inspect('kdh-report-new-app-1')
    assert new8080['State']['Running']
    new_signature=service_signature(new8080);expected_new=baseline['services']['kdh-report-new-app-1']
    for key in ('Id','Image','HostConfig','Mounts'):
        assert new_signature[key]==expected_new[key]
    assert stable_networks(new_signature['networks'])==stable_networks(expected_new['networks'])
    ingress=json.loads(docker('network','inspect',INGRESS))[0]
    net=json.loads(docker('network','inspect',NET))[0]
    outbound=json.loads(docker('network','inspect','kdh-meta-3-outbound-'+RUN))[0]
    assert ingress['Options'].get('com.docker.network.bridge.enable_icc')=='false'
    assert ingress['Options'].get('com.docker.network.bridge.enable_ip_masquerade')=='false'
    assert net['Internal'] and outbound['Options'].get('com.docker.network.bridge.enable_icc')=='false'
    evidence={'admin_id':admin['Id'],'admin_finished_at':admin['State']['FinishedAt'],
            'pg_id':pg['Id'],'pg_finished_at':pg['State']['FinishedAt'],
            'gateway_id':inspect(GATEWAY)['Id'],'gateway_finished_at':inspect(GATEWAY)['State']['FinishedAt'],
            'relay_id':inspect(RELAY)['Id'],'relay_finished_at':inspect(RELAY)['State']['FinishedAt'],
            'backup':'checksum and decryption PASS','backup_prior_restore':'PASS','backup_off_host':False,
            'new_8080':'same ID/image/config/mounts/networks; runtime restarted since baseline',
            'new_8080_started_at':new_signature['started_at'],
            'networks':'identity and isolation PASS','oauth_config':'DPAPI compatibility PASS'}
    save('recovery-preflight',evidence)
    return evidence


def wait_healthy(cid,seconds=60):
    for _ in range(seconds):
        info=inspect(cid)
        assert info['State']['Running'],'container exited during recovery'
        if info['State'].get('Health',{}).get('Status')=='healthy':return
        time.sleep(1)
    raise RuntimeError('container health timeout')


def recover_originals():
    evidence=verify_recovery_preflight()
    free_port(8191)
    docker('start',PG);wait_healthy(PG)
    assert rows('SELECT version FROM schema_migrations ORDER BY version')==[{'version':n} for n in range(1,9)]
    assert sql("SELECT count(*) FROM jobs WHERE status IN ('queued','running')")=='0'
    assert integrity()==read('preflight')['data']
    docker('start',GATEWAY)
    from deploy_admin import policy
    policy(GATEWAY)
    docker('start',ADMIN);wait_healthy(ADMIN)
    assert inspect(ADMIN)['NetworkSettings']['Networks'][NET]['IPAddress']=='192.168.0.3'
    docker('start',RELAY);policy(RELAY)
    import requests
    http=requests.Session();http.trust_env=False
    assert http.get('http://127.0.0.1:8191/health',timeout=8).status_code==200
    assert http.get('http://127.0.0.1:8080/api/v1/health',timeout=8).status_code==200
    assert rows('SELECT version FROM schema_migrations ORDER BY version')==[{'version':n} for n in range(1,9)]
    assert sql("SELECT count(*) FROM jobs WHERE status IN ('queued','running')")=='0'
    assert integrity()==read('preflight')['data']
    protected_services(read('preflight'))
    evidence.update(status='PASS',schemas=list(range(1,9)),queued_jobs=0,
                    admin_health=200,new_8080_health=200,data_unchanged=True)
    save('runtime-recovery',evidence)
    print(json.dumps(evidence))


def create_host_network():
    try:
        existing = json.loads(docker('network', 'inspect', HOST_NET))[0]
    except RuntimeError:
        docker('network', 'create', '--driver', 'bridge', '--label', 'kdh.phase9.run='+RUN,
               '--opt', 'com.docker.network.bridge.enable_icc=false',
               '--opt', 'com.docker.network.bridge.enable_ip_masquerade=false', HOST_NET)
    existing = host_network()
    save('host-network', {'id': existing['Id'], 'name': HOST_NET, 'internal': existing['Internal'],
                          'subnet': existing['IPAM']['Config'][0]['Subnet'],
                          'icc': existing['Options']['com.docker.network.bridge.enable_icc'],
                          'masquerade': existing['Options']['com.docker.network.bridge.enable_ip_masquerade']})
    print(json.dumps(read('host-network')))


def create_handoff_network():
    try:
        existing = json.loads(docker('network', 'inspect', HANDOFF_NET))[0]
    except RuntimeError:
        docker('network', 'create', '--driver', 'bridge', '--internal', '--label', 'kdh.phase9.run='+RUN,
               HANDOFF_NET)
        existing = json.loads(docker('network', 'inspect', HANDOFF_NET))[0]
    assert existing['Labels'].get('kdh.phase9.run') == RUN and existing['Internal']
    assert not existing['Containers']
    save('handoff-network-recovery', {'id': existing['Id'], 'name': HANDOFF_NET,
                                      'internal': existing['Internal'],
                                      'subnet': existing['IPAM']['Config'][0]['Subnet']})
    print(json.dumps(read('handoff-network-recovery')))


def preflight():
    assert not (HERE / 'preflight.json').exists()
    assert docker('context', 'show').decode().strip() == 'desktop-linux'
    a = inspect(ADMIN); values = env(a)
    assert a['Id'] == EXPECTED_ADMIN and a['Image'] == EXPECTED_IMAGE
    assert a['State']['Health']['Status'] == 'healthy'
    assert values['JOB_MODE'] == 'request' and values['META_CLIENT_ID'] == 'client_meta_sandbox'
    assert values['APP_URL'] == 'http://localhost:8191'
    assert not a['HostConfig']['PortBindings'] and set(a['NetworkSettings']['Networks']) == {NET}
    ip = a['NetworkSettings']['Networks'][NET]['IPAddress']
    r = inspect(RELAY); pg = inspect(PG)
    assert r['HostConfig']['PortBindings'] == {'8090/tcp': [{'HostIp': '127.0.0.1', 'HostPort': '8191'}]}
    policy = json.loads(Path('D:/KDH-Meta-Phase2B', RUN, 'relay/config.json').read_text())
    assert policy['upstream_ip'] == ip
    relay_ip = r['NetworkSettings']['Networks'][INGRESS]['IPAddress']
    assert policy['listen_ip'] == relay_ip
    assert json.loads(docker('network', 'inspect', NET))[0]['Internal']
    assert not pg['HostConfig']['PortBindings'] and set(pg['NetworkSettings']['Networks']) == {NET}
    assert pg['State']['Health']['Status'] == 'healthy'
    assert {m['Name'] for m in pg['Mounts']} == {'kdh-meta-2b-pgdata-' + RUN}
    assert {m['Name'] for m in a['Mounts']} == {'kdh-meta-2b-appdata-' + RUN}
    hashes = app_hashes(a['Id'])
    old = json.loads((ROOT / 'docs/ui-deployment-20261019/brand-polish-manifest.json').read_text())['files']
    assert hashes == old
    assert all(digest((ROOT / n).read_bytes()) == h for n,h in hashes.items() if n not in ADMIN_FILES)
    assert rows('SELECT version FROM schema_migrations ORDER BY version') == [{'version': n} for n in range(1,9)]
    assert sql("SELECT count(*) FROM jobs WHERE status IN ('queued','running')") == '0'
    backup = json.loads((ROOT / 'docs/ui-deployment-20261019/brand-polish-backup.json').read_text())
    folder = Path(backup['backup_directory'])
    box = Fernet(dpapi((folder.parent / 'backup-key.dpapi').read_bytes(), decrypt=True))
    for n,h in backup['files'].items():
        encrypted = (folder / (n + '.fernet')).read_bytes()
        assert digest(encrypted) == h['encrypted_sha256'] and digest(box.decrypt(encrypted)) == h['sha256']
    assert backup['restore_integrity'] == 'PASS'
    backup_path = folder.parent / ('phase9-' + time.strftime('%Y%m%d-%H%M%S'))
    backup_path.mkdir()
    pg_env = env(pg)
    raw = {'database.dump': docker('exec', pg['Id'], 'pg_dump', '-U', pg_env['POSTGRES_USER'], '-d', 'meta_acceptance_20261016_132836', '-Fc'),
           'appdata.tar': docker('exec', a['Id'], 'tar', '-C', '/app/instance', '-cf', '-', '.'),
           'admin-env.json': json.dumps(values).encode()}
    assert raw['database.dump'].startswith(b'PGDMP')
    checksums = {}
    for n,data in raw.items():
        encrypted = box.encrypt(data); (backup_path / (n + '.fernet')).write_bytes(encrypted)
        assert box.decrypt(encrypted) == data
        checksums[n] = digest(data)
    private = private_dir()
    (private / 'rollback-env.dpapi').write_bytes(dpapi(json.dumps(values).encode()))
    token = secrets.token_urlsafe(48)
    (private / 'service-token.dpapi').write_bytes(dpapi(token.encode()))
    assert dpapi((private / 'service-token.dpapi').read_bytes(), decrypt=True).decode() == token
    port = next(p for p in range(8192,8200) if port_available(p))
    baseline = {'admin_id':a['Id'],'admin_image':a['Image'],'admin_ip':ip,'relay_ip':relay_ip,'new_port':port,
        'new_url':'http://localhost:' + str(port),'services':{n:service_signature(inspect(n)) for n in (PG,GATEWAY,RELAY,'kdh-report-new-app-1')},
        'data':integrity(),'app_hashes':hashes,'backup':{'directory':str(backup_path),'checksums':checksums,'prior_restore':'PASS','off_host':False},
        't_sha256':digest((ROOT/'t').read_bytes()),'status':'PASS'}
    save('preflight', baseline)
    print(json.dumps({'preflight':'PASS','tables':len(baseline['data']),'new_url':baseline['new_url'],'backup':'PASS','secrets':'DPAPI protected'}))


def port_available(port):
    try: free_port(port); return True
    except OSError: return False


def build_image(root, files, base, tag_prefix, extra=''):
    base_info = json.loads(docker('image', 'inspect', base))[0]
    base_tag = base_info['RepoTags'][0]
    assert json.loads(docker('image', 'inspect', base_tag))[0]['Id'] == base
    hashes = {n:digest((root/n).read_bytes()) for n in files}
    aggregate = digest(json.dumps(hashes, sort_keys=True).encode())
    tag = tag_prefix + aggregate[:12]
    if docker('image','ls','-q',tag).strip():
        existing=json.loads(docker('image','inspect',tag))[0]
        assert existing['Config']['Labels']['kdh.phase9.source']==aggregate
        return {'tag':tag,'image_id':existing['Id'],'files':hashes,'aggregate':aggregate}
    df = 'FROM ' + base_tag + '\n' + '\n'.join('COPY --chown=10001:10001 ' + n + ' /app/' + n for n in files) + '\n' + extra
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode='w') as t:
        for n,data in [('Dockerfile',df.encode())] + [(n,(root/n).read_bytes()) for n in files]:
            info=tarfile.TarInfo(n);info.size=len(data);info.mode=0o644;t.addfile(info,io.BytesIO(data))
    r=subprocess.run(['docker','build','--pull=false','--network=none','--label','kdh.phase9.source='+aggregate,'-t',tag,'-'],input=buf.getvalue(),capture_output=True)
    (HERE/(tag_prefix.split(':')[0]+'-build.log')).write_bytes(r.stdout+r.stderr)
    assert r.returncode==0,'build failed'
    assert json.loads(docker('image', 'inspect', base_tag))[0]['Id'] == base
    return {'tag':tag,'image_id':json.loads(docker('image','inspect',tag))[0]['Id'],'files':hashes,'aggregate':aggregate}


def build():
    b=read('preflight');assert inspect(ADMIN)['Image']==b['admin_image']
    admin=build_image(ROOT,ADMIN_FILES,b['admin_image'],'kdh-admin-meta:phase9-')
    files=sorted(str(p.relative_to(NEW)).replace('\\','/') for folder in ('app','templates','static','ops') for p in (NEW/folder).rglob('*')
                 if p.is_file() and '__pycache__' not in p.parts and p.suffix not in ('.pyc','.map')) + ['main.py']
    assert not any('.env' in n or 'instance/' in n for n in files)
    new=build_image(NEW,files,inspect('kdh-report-new-app-1')['Image'],'kdh-vio-new:phase9-',
                    'CMD ["python","-B","-m","uvicorn","main:app","--host","0.0.0.0","--port","8000","--no-access-log","--no-proxy-headers"]\n')
    save('build',{'admin':admin,'new':new,'status':'PASS'})
    print(json.dumps({'build':'PASS','admin':admin['tag'],'new':new['tag']}))


def wait_http(cid, url):
    for _ in range(45):
        assert inspect(cid)['State']['Running'], 'application stopped'
        try:
            docker('exec',cid,'python','-B','-c',"import urllib.request;assert urllib.request.urlopen("+repr(url)+",timeout=2).status==200")
            return
        except RuntimeError: time.sleep(1)
    raise RuntimeError('health timeout')


def wait_host_http(url):
    import requests
    session=requests.Session();session.trust_env=False
    for _ in range(20):
        try:
            if session.get(url,timeout=2).status_code==200:return
        except requests.RequestException:
            time.sleep(0.5)
    raise RuntimeError('loopback New health timeout')


def smoke():
    built=read('build');prefix='kdh-phase9-smoke-'+uuid.uuid4().hex[:8]
    pg=app=new=None
    try:
        pg_values={'POSTGRES_USER':'phase9','POSTGRES_DB':'phase9','POSTGRES_PASSWORD':secrets.token_urlsafe(32)}
        pg=create({'cli':['--name',prefix+'-pg','--label','kdh.phase9.smoke='+prefix,'--network','none','--log-driver','none',
                         '--tmpfs','/var/lib/postgresql/data:rw,nosuid,nodev,size=512m'], 'image':inspect(PG)['Image']},pg_values)
        docker('start',pg)
        for _ in range(40):
            try:docker('exec',pg,'pg_isready','-U','phase9','-d','phase9');break
            except RuntimeError:time.sleep(1)
        else:raise RuntimeError('fixture PostgreSQL timeout')
        values={'DATABASE_URL':'postgresql://phase9:'+pg_values['POSTGRES_PASSWORD']+'@127.0.0.1:5432/phase9',
                'ENCRYPTION_KEY':Fernet.generate_key().decode(),'JOB_MODE':'request','DATA_DIR':'/tmp/appdata',
                'META_CLIENT_ID':'client_meta_sandbox','APP_URL':'http://localhost:8090','COOKIE_SECURE':'0',
                'REPORT_VIO_HANDOFF_ENABLED':'1','REPORT_NEW_BASE_URL':'http://localhost:8192',
                'REPORT_SERVICE_TOKEN':secrets.token_urlsafe(32),'INITIAL_ADMIN_EMAIL':'smoke@example.invalid','INITIAL_ADMIN_PASSWORD':secrets.token_urlsafe(32)}
        app=create({'cli':['--name',prefix+'-admin','--label','kdh.phase9.smoke='+prefix,'--network','container:'+pg,
                          '--log-driver','none','--read-only','--cap-drop','ALL','--security-opt','no-new-privileges',
                          '--tmpfs','/tmp:rw,nosuid,nodev,size=256m,mode=1777','--mount','type=bind,src='+str(ROOT/'tests')+',dst=/app/tests,readonly'],
                    'image':built['admin']['image_id']},values)
        docker('start',app);wait_http(app,'http://127.0.0.1:8090/health')
        # Tests use ONLY the tmpfs fixture DB in this network-none namespace.
        runner='''import os,sys,unittest,json
sys.path[:0]=['/app','/app/tests']
os.environ['TEST_DATABASE_URL']=os.environ['DATABASE_URL']
os.environ['KDH_PHASE4_ISOLATED']='1'
for k in ('DATABASE_URL','DATA_DIR','INITIAL_ADMIN_EMAIL','INITIAL_ADMIN_PASSWORD','META_CLIENT_ID','APP_URL','REPORT_VIO_HANDOFF_ENABLED','REPORT_NEW_BASE_URL','REPORT_SERVICE_TOKEN'):
 os.environ.pop(k,None)
suite=unittest.TestSuite()
for pattern in ('test_viewer_handoff.py','test_viewer_access.py','test_vio_handoff.py','test_facebook_bundles_postgres.py'):
 suite.addTests(unittest.defaultTestLoader.discover('/app/tests',pattern=pattern))
r=unittest.TextTestRunner(verbosity=1).run(suite)
print('PHASE9_TEST_RESULT='+json.dumps({'run':r.testsRun,'pass':r.testsRun-len(r.skipped)-len(r.failures)-len(r.errors),'skip':len(r.skipped),'fail':len(r.failures)+len(r.errors)}))
sys.exit(0 if r.wasSuccessful() else 1)
'''
        r=subprocess.run(['docker','exec','-i',app,'python','-B','-'],input=runner.encode(),capture_output=True)
        (HERE/'postgres-security-tests.log').write_bytes(r.stdout+r.stderr)
        result=json.loads(next(line.split('=',1)[1] for line in r.stdout.decode().splitlines() if line.startswith('PHASE9_TEST_RESULT=')))
        assert r.returncode==0,'PostgreSQL/security tests failed'
        new=create({'cli':['--name',prefix+'-new','--label','kdh.phase9.smoke='+prefix,'--network','none','--log-driver','none',
                          '--read-only','--cap-drop','ALL','--security-opt','no-new-privileges','--tmpfs','/tmp:rw,nosuid,nodev,size=64m,mode=1777'],
                    'image':built['new']['image_id']},{'APP_ENV':'production','ENABLE_DEMO_PREVIEW':'0','KDH_VIEWER_COOKIE_PREFIX':'kdh_vio'})
        docker('start',new);wait_http(new,'http://127.0.0.1:8000/api/v1/health')
        assert integrity()==read('preflight')['data']
        save('smoke',{'status':'PASS','tests':result,'admin_health':200,'new_health':200,'prefix':prefix,'network':'none','original_db_used':False,
                      'admin_image':built['admin']['image_id'],'new_image':built['new']['image_id']})
        print(json.dumps(read('smoke')))
    finally:
        for cid in (new,app,pg):
            if cid:
                assert inspect(cid)['Config']['Labels']['kdh.phase9.smoke']==prefix
                if inspect(cid)['State']['Running']:docker('stop','-t','15',cid)


def smoke_new():
    """Recheck only a revised New image; retain tests for the identical Admin image."""
    built=read('build');prior=read('smoke')
    assert prior['status']=='PASS' and prior['admin_image']==built['admin']['image_id']
    name='kdh-phase9-smoke-new-'+uuid.uuid4().hex[:8]
    cid=create({'cli':['--name',name,'--label','kdh.phase9.smoke='+name,'--network','none','--log-driver','none',
                        '--read-only','--cap-drop','ALL','--security-opt','no-new-privileges',
                        '--tmpfs','/tmp:rw,nosuid,nodev,size=64m,mode=1777'],
                'image':built['new']['image_id']},{'APP_ENV':'production','ENABLE_DEMO_PREVIEW':'0','KDH_VIEWER_COOKIE_PREFIX':'kdh_vio'})
    try:
        docker('start',cid);wait_http(cid,'http://127.0.0.1:8000/api/v1/health')
        assert integrity()==read('preflight')['data']
        prior.update(new_image=built['new']['image_id'],new_health=200,new_recheck=name)
        save('smoke',prior);print(json.dumps(prior))
    finally:
        assert inspect(cid)['Config']['Labels']['kdh.phase9.smoke']==name
        if inspect(cid)['State']['Running']:docker('stop','-t','15',cid)


def protected_services(baseline):
    for name, expected in baseline['services'].items():
        actual=service_signature(inspect(name))
        for key in ('Id','Image','HostConfig','Mounts'):
            assert actual[key]==expected[key],'protected service identity/config changed'
        assert stable_networks(actual['networks'])==stable_networks(expected['networks']), 'protected service network changed'
        if name=='kdh-report-new-app-1' and (HERE/'recovery-preflight.json').exists():
            assert actual['started_at']==read('recovery-preflight')['new_8080_started_at'],'New 8080 runtime changed during Phase 9'


def handoff_network():
    network=json.loads(docker('network','inspect',HANDOFF_NET))[0]
    assert network['Id']==read('handoff-network-recovery')['id']
    assert network['Labels']['kdh.phase9.run']==RUN and network['Internal'] and not network['Containers']
    assert not docker('ps','-aq','--filter','name=^/'+SIDECAR+'$').strip()
    original=inspect(RELAY)
    source=Path(original['Mounts'][0]['Source']); target=source.parent/('phase9-private-relay-'+uuid.uuid4().hex[:8])
    target.mkdir(exist_ok=False)
    hashes={}
    for name in ('launch.py','serve.py'):
        raw=(source/name).read_bytes();(target/name).write_bytes(raw);hashes[name]=digest(raw)
    import ipaddress
    net=ipaddress.ip_network(network['IPAM']['Config'][0]['Subnet'])
    gateway=ipaddress.ip_address(network['IPAM']['Config'][0]['Gateway'])
    peer=next(ip for ip in net.hosts() if ip!=gateway)
    entrypoint=original['Config'].get('Entrypoint') or []
    assert entrypoint==['python']
    cid=create({'cli':['--name',SIDECAR,'--label','kdh.phase9.run='+RUN,'--network',HANDOFF_NET,'--ip',str(peer),
               '--entrypoint',entrypoint[0],
               '--dns','127.0.0.1','--user','0:0','--read-only','--cap-drop','ALL',
               '--cap-add','NET_ADMIN','--cap-add','SETUID','--cap-add','SETGID','--cap-add','SETPCAP',
               '--security-opt','no-new-privileges','--sysctl','net.ipv6.conf.all.disable_ipv6=1',
               '--sysctl','net.ipv4.ip_forward=0','--memory','128m','--cpus','0.5','--restart','no',
               '--log-driver','none','--mount','type=bind,src='+str(target)+',dst=/relay,readonly'],
                'image':original['Image'],'command':original['Config']['Cmd']},{})
    docker('network','connect',NET,cid)
    config={'listen_ip':str(peer),'upstream_ip':inspect(ADMIN)['NetworkSettings']['Networks'][NET]['IPAddress'],
            'pg_ip':inspect(PG)['NetworkSettings']['Networks'][NET]['IPAddress']}
    (target/'config.json').write_text(json.dumps(config),encoding='utf-8')
    hashes['config.json']=digest((target/'config.json').read_bytes())
    save('private-relay',{'id':cid,'name':SIDECAR,'image':original['Image'],'listener':str(peer),
                          'config_directory':str(target),'files':hashes,'upstream':config['upstream_ip']})
    docker('start',cid)
    relay=inspect(cid)
    assert relay['NetworkSettings']['Networks'][HANDOFF_NET]['IPAddress']==str(peer)
    from deploy_admin import policy
    policy(cid);wait_http(cid,'http://'+str(peer)+':8090/health')
    assert not inspect(cid)['HostConfig']['PortBindings']
    return str(peer)


def network_checks(new, sidecar):
    pg=inspect(PG)['NetworkSettings']['Networks'][NET]['IPAddress']
    gateway=inspect(GATEWAY)['NetworkSettings']['Networks'][NET]['IPAddress']
    admin=inspect(ADMIN)['NetworkSettings']['Networks'][NET]['IPAddress']
    outcome={}
    network_subnet=json.loads(docker('network','inspect',HANDOFF_NET))[0]['IPAM']['Config'][0]['Subnet']
    host_network_info=host_network(empty=False)
    host_subnet=host_network_info['IPAM']['Config'][0]['Subnet']
    expected_admin_route=admin+'/32'
    for cid,label in ((new,'new'),(sidecar,'private_relay')):
        targets=[('postgres',pg,5432),('meta_gateway',gateway,8090),('internet','198.51.100.1',443)]
        if label=='new':targets.append(('direct_admin',admin,8090))
        code='''import socket,errno,json,pathlib
targets=TARGETS
result={}
for name,ip,port in targets:
 with socket.socket() as s:
  s.settimeout(2)
  err=s.connect_ex((ip,port))
  assert err==errno.ENETUNREACH, 'unexpected route to '+name
  result[name]='DENIED_ENETUNREACH'
routes=[]
for row in pathlib.Path('/proc/net/route').read_text().splitlines()[1:]:
 fields=row.split(); address=socket.inet_ntoa(bytes.fromhex(fields[1])[::-1]); mask=socket.inet_ntoa(bytes.fromhex(fields[7])[::-1])
 prefix=sum(bin(int(part)).count('1') for part in mask.split('.'))
 routes.append(str(__import__('ipaddress').ip_network(address+'/'+str(prefix),strict=False)))
assert set(routes)==set(ALLOWED), 'route table contains a route outside its allowlist'
print(json.dumps(result))
        '''.replace('TARGETS',repr(targets)).replace('ALLOWED',repr([network_subnet, host_subnet] if label=='new' else [network_subnet, expected_admin_route]))
        outcome[label]=json.loads(docker('exec','--user','10001','-i',cid,'python','-B','-',data=code.encode()))
    ingress=json.loads(docker('network','inspect',INGRESS))[0]
    assert ingress['Options']['com.docker.network.bridge.enable_icc']=='false'
    outcome.update(ingress_icc=False,host_network_icc=False,host_network_masquerade=False,
                   new_to_relay_http=200,relay_to_admin_http=200,forwarding=False)
    save('network-tests',outcome)


def deploy():
    b=read('preflight');built=read('build');target=read('deployment-target')
    assert read('smoke')['status']=='PASS'
    assert all(read('smoke')[name+'_image']==built[name]['image_id'] for name in ('admin','new'))
    assert integrity()==b['data'],'business data changed since baseline'
    protected_services(b)
    assert digest((ROOT/'t').read_bytes())==b['t_sha256']
    for spec,root in ((built['admin'],ROOT),(built['new'],NEW)):
        assert all(digest((root/n).read_bytes())==h for n,h in spec['files'].items())
    old=inspect(ADMIN);assert old['Id']==EXPECTED_ADMIN and old['Image']==b['admin_image']
    values=env(old)
    rollback=json.loads(dpapi((private_dir()/'rollback-env.dpapi').read_bytes(),decrypt=True))
    assert values==rollback
    service=dpapi((private_dir()/'service-token.dpapi').read_bytes(),decrypt=True).decode()
    assert not docker('ps','-aq','--filter','name=^/'+NEW_NAME+'$').strip()
    retained=ADMIN+'-before-phase9'
    assert not docker('ps','-aq','--filter','name=^/'+retained+'$').strip()
    new_port=target['new_port'];public_url=target['new_url']
    assert public_url=='http://127.0.0.1:'+str(new_port)
    free_port(new_port)
    new_values={'APP_ENV':'production','DEBUG':'false','ENABLE_DEMO_PREVIEW':'0','REPORT_PREVIEW_ENABLED':'false',
        'REPORT_ADMIN_BASE_URL':'http://'+b['relay_ip']+':8090','REPORT_ADMIN_PUBLIC_URL':'http://localhost:8191',
        'REPORT_NEW_PUBLIC_URL':public_url,'REPORT_SERVICE_TOKEN':service,'KDH_VIEWER_COOKIE_PREFIX':'kdh_vio',
        'PYTHONDONTWRITEBYTECODE':'1'}
    new=admin=None;stopped=renamed=detached=False
    try:
        host_network()
        peer=handoff_network()
        new_values['REPORT_ADMIN_BASE_URL']='http://'+peer+':8090'
        new=create({'cli':['--name',NEW_NAME,'--label','kdh.phase9.run='+RUN,'--network',HOST_NET,
                 '--publish','127.0.0.1:'+str(new_port)+':8000','--dns','127.0.0.1','--user','0:0',
                 '--read-only','--cap-drop','ALL','--cap-add','NET_ADMIN','--cap-add','SETUID','--cap-add','SETGID','--cap-add','SETPCAP',
                 '--security-opt','no-new-privileges','--sysctl','net.ipv6.conf.all.disable_ipv6=1','--sysctl','net.ipv4.ip_forward=0',
                 '--memory','512m','--cpus','1','--restart','no','--log-driver','none','--tmpfs','/tmp:rw,nosuid,nodev,noexec,size=64m,mode=1777',
                 '--health-interval','3s','--health-timeout','4s','--health-retries','10'],
                 'image':built['new']['image_id'],'command':['python','-B','/app/ops/vio_sandbox_entrypoint.py']},new_values)
        docker('network','connect',HANDOFF_NET,new)
        docker('start',new);wait_http(new,'http://127.0.0.1:8000/api/v1/health')
        # Namespace restrictions must already be effective before touching Admin.
        from deploy_admin import policy
        policy(new)
        wait_host_http(public_url+'/api/v1/health')
        ni=inspect(new);assert set(ni['NetworkSettings']['Networks'])=={HANDOFF_NET,HOST_NET} and not ni['Mounts']
        network=json.loads(docker('network','inspect',HANDOFF_NET))[0]
        assert network['Internal'] and set(network['Containers'])=={new,inspect(SIDECAR)['Id']}
        host_network_info=host_network(empty=False)
        assert set(host_network_info['Containers'])=={new}
        assert ni['HostConfig']['PortBindings']=={'8000/tcp':[{'HostIp':'127.0.0.1','HostPort':str(new_port)}]}
        wait_http(new,'http://'+peer+':8090/health')
        network_checks(new,inspect(SIDECAR)['Id'])
        docker('stop','-t','20',old['Id']);stopped=True
        docker('rename',old['Id'],retained);renamed=True
        docker('network','disconnect',NET,old['Id']);detached=True
        values.update(REPORT_NEW_BASE_URL=public_url,REPORT_SERVICE_TOKEN=service,REPORT_VIO_HANDOFF_ENABLED='1')
        admin=create({'cli':['--name',ADMIN,'--label','kdh.phase9.run='+RUN,'--network',NET,'--ip',b['admin_ip'],
                 '--dns','127.0.0.1','--user',old['Config']['User'],'--workdir','/app','--read-only','--cap-drop','ALL',
                 '--security-opt','no-new-privileges','--memory','512m','--cpus','1','--restart','no','--shm-size','64m',
                 '--log-driver','json-file','--tmpfs','/tmp:rw,noexec,nosuid,size=64m',
                 '--mount','type=volume,src=kdh-meta-2b-appdata-'+RUN+',dst=/app/instance,volume-nocopy',
                 '--health-cmd',old['Config']['Healthcheck']['Test'][1],'--health-interval','3s','--health-timeout','4s','--health-retries','10'],
                 'image':built['admin']['image_id'],'command':old['Config']['Cmd']},values)
        ai=inspect(admin);assert ai['Mounts']==old['Mounts'] and not ai['HostConfig']['PortBindings']
        for k in ('ReadonlyRootfs','CapDrop','SecurityOpt','Dns','Tmpfs','Memory','NanoCpus','RestartPolicy','ShmSize','LogConfig'):
            assert ai['HostConfig'][k]==old['HostConfig'][k]
        assert env(ai)==values and set(ai['NetworkSettings']['Networks'])=={NET}
        docker('start',admin);wait_http(admin,'http://127.0.0.1:8090/health')
        assert inspect(admin)['NetworkSettings']['Networks'][NET]['IPAddress']==b['admin_ip']
        assert app_hashes(admin)==b['app_hashes']|built['admin']['files']
        import requests
        http=requests.Session();http.trust_env=False
        assert http.get('http://localhost:8191/health',timeout=5).status_code==200
        assert http.get(public_url+'/api/v1/health',timeout=5).status_code==200
        assert integrity()==b['data'],'business data changed after startup'
        protected_services(b)
        save('deployment',{'status':'PASS','admin_id':admin,'admin_image':built['admin']['image_id'],
            'new_id':new,'new_image':built['new']['image_id'],'new_name':NEW_NAME,'new_url':public_url,
            'rollback_container':retained,'business_tables_unchanged':len(b['data']),'network_policy':'PASS',
            'provider_calls':0,'production_services':'UNCHANGED'})
        print(json.dumps(read('deployment')))
    except Exception:
        if new and inspect(new)['State']['Running']:docker('stop','-t','15',new)
        if docker('ps','-aq','--filter','name=^/'+SIDECAR+'$').strip():
            sidecar=inspect(SIDECAR)
            assert sidecar['Config']['Labels']['kdh.phase9.run']==RUN
            if sidecar['State']['Running']:docker('stop','-t','15',sidecar['Id'])
            for network_name in (HANDOFF_NET,NET):
                if network_name in inspect(sidecar['Id'])['NetworkSettings']['Networks']:
                    docker('network','disconnect',network_name,sidecar['Id'])
            docker('rename',sidecar['Id'],SIDECAR+'-failed-'+sidecar['Id'][:8])
        if admin:
            if inspect(admin)['State']['Running']:docker('stop','-t','15',admin)
            if NET in inspect(admin)['NetworkSettings']['Networks']:docker('network','disconnect',NET,admin)
            docker('rename',admin,ADMIN+'-phase9-failed-'+admin[:8])
        if stopped:
            if renamed:docker('rename',old['Id'],ADMIN)
            if detached:docker('network','connect','--ip',b['admin_ip'],NET,old['Id'])
            docker('start',old['Id']);wait_http(old['Id'],'http://127.0.0.1:8090/health')
        save('deployment',{'status':'BLOCKED','application_rollback':'prior Admin restored' if stopped else 'Admin untouched',
                           'new_stopped':bool(new),'database_restore':False})
        raise


def rollback():
    """Application-only rollback; no database/config writes and no resource deletion."""
    b=read('preflight');d=read('deployment')
    assert d['status']=='PASS'
    protected_services(b)
    current=inspect(ADMIN);previous=inspect(d['rollback_container']);viewer=inspect(NEW_NAME)
    assert current['Id']==d['admin_id'] and previous['Id']==b['admin_id']
    assert previous['Image']==b['admin_image'] and not previous['State']['Running']
    assert viewer['Id']==d['new_id']
    if viewer['State']['Running']:docker('stop','-t','15',viewer['Id'])
    sidecar=inspect(SIDECAR)
    assert sidecar['Config']['Labels']['kdh.phase9.run']==RUN
    if sidecar['State']['Running']:docker('stop','-t','15',sidecar['Id'])
    for network_name in (HANDOFF_NET,NET):
        if network_name in inspect(sidecar['Id'])['NetworkSettings']['Networks']:
            docker('network','disconnect',network_name,sidecar['Id'])
    if current['State']['Running']:docker('stop','-t','20',current['Id'])
    docker('network','disconnect',NET,current['Id'])
    docker('rename',current['Id'],ADMIN+'-phase9-rolled-back-'+current['Id'][:8])
    docker('rename',previous['Id'],ADMIN)
    docker('network','connect','--ip',b['admin_ip'],NET,previous['Id'])
    docker('start',previous['Id']);wait_http(previous['Id'],'http://127.0.0.1:8090/health')
    save('rollback',{'status':'PASS','restored_admin_id':previous['Id'],'new_stopped':True,'database_restore':False})
    print(json.dumps(read('rollback')))


if __name__=='__main__':
    try:
        globals()[sys.argv[1]]()
    except Exception as e:
        import traceback
        last=traceback.extract_tb(e.__traceback__)[-1]
        print(json.dumps({'status':'BLOCKED','type':type(e).__name__,'file':Path(last.filename).name,'line':last.lineno}))
        sys.exit(1)
