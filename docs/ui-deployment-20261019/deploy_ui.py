"""Approved UI-only sandbox deployment. No provider calls or business mutations."""
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PRIOR = ROOT / 'docs/phase5-20261018'
sys.path.insert(0, str(PRIOR))
sys.path.insert(0, str(ROOT / 'docs/phase5b-20261018'))
from cold_backup import docker, inspect, digest, dpapi, RUN
from runtime_common import sql, rows, NET
from cryptography.fernet import Fernet

ADMIN = 'kdh-meta-2b-admin-' + RUN
EXPECTED = '854d933dd89f8cd9415c64e19ec62ff9a75aa0be75b110b1fb7cac2ed38ef4c4'
FILES = ['static/app.js', 'static/views.js', 'static/marketing.js',
         'static/admin-refinement.css', 'templates/index.html', 'templates/marketing.html']
SERVICE_NAMES = ['kdh-meta-2b-pg-' + RUN, 'kdh-meta-3-egress-' + RUN, 'kdh-meta-2b-relay-' + RUN]


def save(name, value):
    (HERE / name).write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


def read(name):
    return json.loads((HERE / name).read_text(encoding='utf-8'))


def env(info):
    return dict(value.split('=', 1) for value in info['Config']['Env'])


def git_baseline():
    names = subprocess.check_output(['git', 'ls-files', '-co', '--exclude-standard', '-z'], cwd=ROOT).decode().split('\0')
    return {name: digest((ROOT / name).read_bytes()) for name in sorted(set(names))
            if name and (ROOT / name).is_file() and not name.startswith('docs/ui-deployment-20261019/')}


def integrity():
    names = [r['table_name'] for r in rows("SELECT table_name FROM information_schema.tables WHERE table_schema='public' ORDER BY table_name")]
    result = {}
    # Only own authentication events/session timestamps may change during HTTP QA.
    for name in names:
        if name in ('events', 'sessions', 'attempts', 'users'):
            continue
        assert name.replace('_', '').isalnum()
        raw = sql('SELECT coalesce(jsonb_agg(t ORDER BY to_jsonb(t)::text),\'[]\'::jsonb) FROM "' + name + '" t')
        result[name] = {'rows': len(json.loads(raw)), 'sha256': digest(raw.encode())}
    return result


def service_signature(info):
    return {key: info[key] for key in ('Id', 'Image', 'HostConfig', 'Mounts')} | {
        'started_at': info['State']['StartedAt'], 'networks': info['NetworkSettings']['Networks']}


def app_hashes(cid):
    code = "import pathlib,json,hashlib; r=pathlib.Path('/app'); files=[*r.glob('kdh/**/*.py'),*r.glob('static/**/*'),*r.glob('templates/**/*'),r/'run.py',r/'requirements.lock']; print(json.dumps({str(p.relative_to(r)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files if p.is_file() and '__pycache__' not in p.parts}))"
    return json.loads(docker('exec', cid, 'python', '-B', '-c', code))


def preflight():
    assert not (HERE / 'preflight.json').exists()
    assert docker('context', 'show').decode().strip() == 'desktop-linux'
    admin = inspect(ADMIN)
    assert admin['Id'] == EXPECTED and admin['State']['Health']['Status'] == 'healthy'
    assert not admin['HostConfig']['PortBindings']
    assert set(admin['NetworkSettings']['Networks']) == {NET}
    assert admin['NetworkSettings']['Networks'][NET]['IPAddress'] == '192.168.0.3'
    values = env(admin)
    assert values['JOB_MODE'] == 'request' and values['META_CLIENT_ID'] == 'client_meta_sandbox'
    assert values['APP_URL'] == 'http://localhost:8191'
    assert json.loads(docker('network', 'inspect', NET))[0]['Internal']
    services = [inspect(name) for name in SERVICE_NAMES]
    assert all(item['State']['Running'] for item in services)
    assert services[0]['State']['Health']['Status'] == 'healthy'
    assert not services[0]['HostConfig']['PortBindings']
    assert services[2]['HostConfig']['PortBindings'] == {'8090/tcp': [{'HostIp': '127.0.0.1', 'HostPort': '8191'}]}
    assert rows('SELECT version FROM schema_migrations ORDER BY version') == [{'version': n} for n in range(1, 9)]
    assert sql("SELECT count(*) FROM jobs WHERE status IN ('queued','running')") == '0'
    hashes = app_hashes(EXPECTED)
    mismatches = [name for name, sha in hashes.items() if name not in FILES and
                  (not (ROOT / name).is_file() or digest((ROOT / name).read_bytes()) != sha)]
    assert not mismatches, 'non-UI source differs'
    assert sql("SELECT count(*) FROM source_assets WHERE client_id='client_meta_sandbox' AND external_id='2188688654687066'") == '1'
    cipher = sql("SELECT encode(value,'hex') FROM secrets WHERE name='meta:client_meta_sandbox'")
    assert json.loads(Fernet(values['ENCRYPTION_KEY'].encode()).decrypt(bytes.fromhex(cipher))).get('access_token')
    old = json.loads((PRIOR / 'backup-result.json').read_text())
    folder = Path(old['private_backup_directory'])
    key = dpapi((folder / 'backup-key.dpapi').read_bytes(), decrypt=True)
    box = Fernet(key)
    for archive in old['archives'].values():
        encrypted = (folder / archive['file']).read_bytes()
        assert digest(encrypted) == archive['encrypted_sha256']
        assert digest(box.decrypt(encrypted)) == archive['archive_sha256']
    assert json.loads((PRIOR / 'restore-result.json').read_text())['status'] == 'PASS'
    # Fresh logical backup supplements the old independently restored cold copy.
    backup = folder / ('ui-' + time.strftime('%Y%m%d-%H%M%S'))
    backup.mkdir()
    pg = services[0]
    pg_values = env(pg)
    dump = docker('exec', pg['Id'], 'pg_dump', '-U', pg_values['POSTGRES_USER'], '-d',
                  'meta_acceptance_20261016_132836', '-Fc')
    assert dump.startswith(b'PGDMP')
    current = {'database.dump': dump, 'admin-config.json': json.dumps(values).encode(),
               'appdata.tar': docker('exec', EXPECTED, 'tar', '-C', '/app/instance', '-cf', '-', '.')}
    backup_hashes = {}
    for name, raw in current.items():
        encrypted = box.encrypt(raw)
        (backup / (name + '.fernet')).write_bytes(encrypted)
        assert box.decrypt((backup / (name + '.fernet')).read_bytes()) == raw
        backup_hashes[name] = {'sha256': digest(raw), 'encrypted_sha256': digest(encrypted)}
    baseline = {'status': 'PASS', 'admin_id': EXPECTED, 'base_image': admin['Image'],
        'services': {item['Name']: service_signature(item) for item in services},
        'app_hashes': hashes, 'data': integrity(), 'git': git_baseline(),
        'branch': subprocess.check_output(['git', 'branch', '--show-current']).decode().strip(),
        'head': subprocess.check_output(['git', 'rev-parse', 'HEAD']).decode().strip(),
        'backup': {'directory': str(backup), 'files': backup_hashes, 'old_restore': 'PASS',
                   'fresh_logical_restore': 'NOT TESTED', 'off_host': False},
        'oauth_encryption': 'PASS', 'provider_calls': 0}
    save('preflight.json', baseline)
    print(json.dumps({'preflight': 'PASS', 'base_image': admin['Image'], 'tables': len(baseline['data']), 'backup': str(backup)}))


def build():
    baseline = read('preflight.json')
    assert inspect(EXPECTED)['Image'] == baseline['base_image']
    assert git_baseline() == baseline['git']
    hashes = {name: digest((ROOT / name).read_bytes()) for name in FILES}
    aggregate = digest(json.dumps(hashes, sort_keys=True).encode())
    tag = 'kdh-admin-meta:ui-20261019-' + aggregate[:12]
    assert not docker('image', 'ls', '-q', tag).strip()
    base_tag = 'kdh-admin-meta:phase7b-20261019-7141f68a486b'
    assert json.loads(docker('image', 'inspect', base_tag))[0]['Id'] == baseline['base_image']
    dockerfile = 'FROM ' + base_tag + '\n' + '\n'.join('COPY --chown=kdh:kdh ' + name + ' /app/' + name for name in FILES) + '\n'
    context = io.BytesIO()
    with tarfile.open(fileobj=context, mode='w') as archive:
        for name, raw in [('Dockerfile', dockerfile.encode())] + [(name, (ROOT / name).read_bytes()) for name in FILES]:
            entry = tarfile.TarInfo(name); entry.size = len(raw); entry.mode = 0o644
            archive.addfile(entry, io.BytesIO(raw))
    built = subprocess.run(['docker', 'build', '--pull=false', '--network=none', '--label',
                            'kdh.ui.source-sha256=' + aggregate, '-t', tag, '-'],
                           input=context.getvalue(), capture_output=True)
    # This allowlisted context contains only public source and its generated Dockerfile.
    (HERE / 'build.log').write_bytes(built.stdout + built.stderr)
    assert built.returncode == 0, 'image build failed'
    assert json.loads(docker('image', 'inspect', base_tag))[0]['Id'] == baseline['base_image']
    image = json.loads(docker('image', 'inspect', tag))[0]['Id']
    save('deployment-manifest.json', {'files': hashes, 'aggregate_sha256': aggregate, 'base_image': baseline['base_image'], 'tag': tag})
    save('approved-image-result.json', {'image_id': image, 'tag': tag, 'status': 'PASS'})
    print(json.dumps({'build': 'PASS', 'image': image, 'tag': tag, 'files': len(FILES)}))


def smoke():
    import smoke_ui as smoke_image
    smoke_image.HERE = HERE
    smoke_image.PRIOR = HERE
    save('runtime-baseline.json', [{'Name': '/' + SERVICE_NAMES[0], 'Image': inspect(SERVICE_NAMES[0])['Image']}])
    smoke_image.main()


def healthy(cid):
    for _ in range(45):
        current = inspect(cid)
        assert current['State']['Running']
        if current['State'].get('Health', {}).get('Status') == 'healthy':
            return current
        time.sleep(1)
    raise RuntimeError('health timeout')


def http_checks():
    import requests
    from werkzeug.security import check_password_hash
    s = requests.Session(); s.trust_env = False
    base = 'http://localhost:8191'
    assert s.get(base + '/health', timeout=10).status_code == 200
    for name in [item for item in FILES if item.startswith('static/')]:
        response = s.get(base + '/' + name, timeout=10)
        assert response.status_code == 200 and digest(response.content) == digest((ROOT / name).read_bytes())
    from jinja2 import Environment
    def template_matches(url, name):
        response = s.get(base + url, timeout=10)
        rendered = Environment().from_string((ROOT / name).read_text(encoding='utf-8')).render()
        assert response.status_code == 200 and response.content.decode('utf-8') == rendered
    template_matches('/', 'templates/index.html')
    values = env(inspect(ADMIN))
    users = rows("SELECT email,password FROM users WHERE role='admin' AND active=1")
    account = next((u for u in users if u['email'] == values.get('INITIAL_ADMIN_EMAIL', '').lower()), None)
    assert account and check_password_hash(account['password'], values['INITIAL_ADMIN_PASSWORD'])
    h = {'X-KDH-Request': '1', 'Origin': base}
    response = s.post(base + '/api/auth/login', headers=h, json={'email': account['email'], 'password': values['INITIAL_ADMIN_PASSWORD']}, timeout=10)
    assert response.status_code == 200
    csrf = response.json()['csrf']
    try:
        template_matches('/marketing', 'templates/marketing.html')
        cookie = response.headers['Set-Cookie']
        assert values['ADMIN_SESSION_COOKIE_NAME'] + '=' in cookie and 'HttpOnly' in cookie and 'SameSite=Lax' in cookie
        assert s.get(base + '/api/auth/me', timeout=10).json()['user']['role'] == 'admin'
        assert s.post(base + '/api/auth/logout', headers=h, json={}, timeout=10).status_code == 403
        assert s.post(base + '/api/auth/logout', headers={**h, 'Origin': 'http://example.invalid', 'X-CSRF-Token': csrf}, json={}, timeout=10).status_code == 403
        workflow = s.get(base + '/api/marketing/workflow', timeout=10)
        assert workflow.status_code == 200 and workflow.json()['client_id'] == 'client_meta_sandbox'
        assert s.get(base + '/api/internal/v1/viewer/report-bundles/ui-probe?revision=1', timeout=10).status_code in (401, 403)
    finally:
        assert s.post(base + '/api/auth/logout', headers={**h, 'X-CSRF-Token': csrf}, json={}, timeout=10).status_code == 200
    return {'health': 200, 'ui_hashes': 'PASS', 'login_cookie_csrf_origin': 'PASS', 'marketing_scope': 'PASS', 'viewer_guard': 'PASS'}


def deploy():
    baseline = read('preflight.json')
    assert read('smoke.json')['status'] == 'PASS'
    assert git_baseline() == baseline['git']
    assert integrity() == baseline['data'], 'data changed since preflight'
    old = inspect(ADMIN)
    assert old['Id'] == EXPECTED and old['Image'] == baseline['base_image']
    for name, expected in baseline['services'].items():
        assert service_signature(inspect(name)) == expected
    image = read('approved-image-result.json')['image_id']
    retained = ADMIN + '-before-ui-20261019'
    assert not docker('ps', '-aq', '--filter', 'name=^/' + retained + '$').strip()
    report = {'image_id': image, 'tag': read('approved-image-result.json')['tag'], 'rollback_container': retained, 'provider_calls': 0}
    new_id = None
    stopped = detached = renamed = False
    data_mismatch = False
    try:
        docker('stop', '-t', '20', EXPECTED); stopped = True
        docker('rename', EXPECTED, retained); renamed = True
        docker('network', 'disconnect', NET, EXPECTED); detached = True
        values = env(old)
        args = ['docker', 'create', '--pull', 'never', '--name', ADMIN,
                '--label', 'kdh.ui.run=' + RUN, '--network', NET, '--ip', '192.168.0.3',
                '--dns', '127.0.0.1', '--user', old['Config']['User'], '--workdir', '/app',
                '--read-only', '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges',
                '--memory', '512m', '--cpus', '1', '--restart', 'no', '--shm-size', '64m',
                '--log-driver', 'json-file', '--tmpfs', '/tmp:rw,noexec,nosuid,size=64m',
                '--mount', 'type=volume,src=kdh-meta-2b-appdata-' + RUN + ',dst=/app/instance,volume-nocopy',
                '--health-cmd', old['Config']['Healthcheck']['Test'][1], '--health-interval', '3s',
                '--health-timeout', '4s', '--health-retries', '10']
        for key in values:
            args += ['--env', key]
        result = subprocess.run(args + [image, *old['Config']['Cmd']], env=dict(os.environ, **values), capture_output=True)
        assert result.returncode == 0
        new_id = result.stdout.decode().strip()
        new = inspect(new_id)
        assert env(new) == values and new['Mounts'] == old['Mounts']
        assert not new['HostConfig']['PortBindings'] and set(new['NetworkSettings']['Networks']) == {NET}
        for key in ('ReadonlyRootfs', 'CapDrop', 'SecurityOpt', 'Dns', 'Tmpfs', 'Memory', 'NanoCpus', 'RestartPolicy', 'ShmSize', 'LogConfig'):
            assert new['HostConfig'][key] == old['HostConfig'][key]
        docker('start', new_id)
        new = healthy(new_id)
        assert new['NetworkSettings']['Networks'][NET]['IPAddress'] == '192.168.0.3'
        expected_hashes = baseline['app_hashes'] | read('deployment-manifest.json')['files']
        assert app_hashes(new_id) == expected_hashes
        after = integrity(); save('data-after-start.json', after)
        data_mismatch = after != baseline['data']
        assert not data_mismatch
        report['http'] = http_checks()
        after = integrity(); save('data-final.json', after)
        data_mismatch = after != baseline['data']
        assert not data_mismatch
        for name, expected in baseline['services'].items():
            assert service_signature(inspect(name)) == expected
        assert git_baseline() == baseline['git']
        report.update(status='PASS', admin_id=new_id, data_integrity='PASS', unchanged_tables=len(after),
                      backend_hashes='UNCHANGED', services='UNCHANGED', git='PASS', rollback='AVAILABLE; NOT NEEDED')
    except Exception as error:
        import traceback
        last = traceback.extract_tb(error.__traceback__)[-1]
        report.update(status='BLOCKED', error_type=type(error).__name__, failed_file=Path(last.filename).name, failed_line=last.lineno)
        if new_id:
            assert inspect(new_id)['Image'] == image
            if inspect(new_id)['State']['Running']:
                docker('stop', '-t', '20', new_id)
            if NET in inspect(new_id)['NetworkSettings']['Networks']:
                docker('network', 'disconnect', NET, new_id)
            docker('rename', new_id, ADMIN + '-failed-ui-20261019-' + new_id[:8])
        if data_mismatch:
            report['rollback'] = 'STOPPED: data mismatch requires investigation; original DB untouched'
        elif stopped:
            if renamed:
                docker('rename', EXPECTED, ADMIN)
            if detached:
                docker('network', 'connect', '--ip', '192.168.0.3', NET, EXPECTED)
            docker('start', EXPECTED); healthy(EXPECTED)
            report['rollback'] = 'PASS; prior application restored'
    save('deployment.json', report)
    print(json.dumps(report))
    assert report['status'] == 'PASS'


if __name__ == '__main__':
    try:
        {'preflight': preflight, 'build': build, 'smoke': smoke, 'deploy': deploy}[sys.argv[1]]()
    except Exception as error:
        import traceback
        last = traceback.extract_tb(error.__traceback__)[-1]
        print(json.dumps({'status': 'BLOCKED', 'error_type': type(error).__name__, 'file': Path(last.filename).name, 'line': last.lineno}))
        raise SystemExit(1)
