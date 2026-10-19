"""Create a NEW PostgreSQL 16 container, run isolated fixtures, then remove it.

Usage: python -B tests/run_postgres_acceptance.py --evidence-dir <new-directory>
Never accepts a caller-supplied database URL or reuses an existing container.
No secrets/DSNs/provider responses are written to evidence or stdout.
"""
import argparse
import contextlib
import io
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'tests')]


def docker(*args, env=None):
    result = subprocess.run(['docker', *args], capture_output=True, text=True, env=env)
    if result.returncode:
        raise RuntimeError('Docker command failed: ' + args[0])
    return result.stdout.strip()


def flatten(suite):
    for test in suite:
        if isinstance(test, unittest.TestSuite):
            yield from flatten(test)
        else:
            yield test


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--evidence-dir', required=True)
    args = parser.parse_args()
    folder = Path(args.evidence_dir).resolve()
    folder.mkdir(parents=True, exist_ok=False)
    run = 'kdh-phase4-pg-' + time.strftime('%Y%m%d-%H%M%S') + '-' + uuid4().hex[:8]
    database, user = 'phase4_acceptance', 'phase4_fixture'
    password = secrets.token_hex(32)
    report = {'run': run, 'tests': [], 'cleanup': 'not_created'}
    container_id = None
    original_read = Path.read_text
    try:
        report['context'] = docker('context', 'show')
        if report['context'] != 'desktop-linux':
            raise RuntimeError('Unexpected Docker context')
        report['daemon'] = docker('version', '--format', '{{.Server.Version}}')
        image = json.loads(docker('image', 'inspect', 'postgres:16'))[0]
        report['image_id'] = image['Id']
        if run in docker('ps', '-a', '--format', '{{.Names}}').splitlines():
            raise RuntimeError('Disposable name already exists')
        child_env = dict(os.environ, POSTGRES_PASSWORD=password)
        container_id = docker('run', '-d', '--name', run, '--label', 'kdh.phase4.run=' + run,
                              '--restart=no', '--memory=512m', '--cpus=2',
                              '--publish', '127.0.0.1::5432', '--network', 'bridge',
                              '--tmpfs', '/var/lib/postgresql/data:rw,size=512m',
                              '-e', 'POSTGRES_PASSWORD', '-e', 'POSTGRES_DB=' + database,
                              '-e', 'POSTGRES_USER=' + user, image['Id'], env=child_env)
        info = json.loads(docker('inspect', container_id))[0]
        bindings = info['NetworkSettings']['Ports']['5432/tcp']
        if (info['Name'] != '/' + run or info['Image'] != image['Id']
                or info['Config']['Labels'].get('kdh.phase4.run') != run
                or len(bindings) != 1 or bindings[0]['HostIp'] != '127.0.0.1'
                or any(m['Type'] != 'tmpfs' for m in info['Mounts'])
                or set(info['NetworkSettings']['Networks']) != {'bridge'}):
            raise RuntimeError('Disposable identity/isolation gate failed')
        port = bindings[0]['HostPort']
        report['database'] = {'container_id': container_id, 'name': database, 'user': user,
                              'host': '127.0.0.1', 'port': int(port), 'storage': 'tmpfs',
                              'network': 'default bridge, loopback published port only'}
        # Local workstation variables and .env must never select live resources.
        for key in list(os.environ):
            if key.startswith(('TEST_', 'META_', 'GOOGLE_', 'GA4_', 'GSC_', 'KEYWORD_', 'INITIAL_ADMIN_', 'ADMIN_SESSION_', 'PG')) or key in {
                    'DATABASE_URL', 'DATA_DIR', 'ENCRYPTION_KEY', 'JOB_MODE', 'APP_URL', 'COOKIE_SECURE', 'REPORT_SIGNING_KEY'}:
                os.environ.pop(key, None)
        import psycopg
        from psycopg.conninfo import conninfo_to_dict
        original_connect = psycopg.connect
        url = f'postgresql://{user}:{password}@127.0.0.1:{port}/{database}'

        def safe_connect(conninfo='', **kwargs):
            parsed = conninfo_to_dict(conninfo)
            parsed.update({key: str(value) for key, value in kwargs.items()
                           if key in ('host', 'hostaddr', 'port', 'dbname', 'user', 'password', 'service')})
            if (parsed.get('host') != '127.0.0.1' or parsed.get('port') != port
                    or parsed.get('dbname') != database or parsed.get('user') != user
                    or parsed.get('password') != password or parsed.get('hostaddr') or parsed.get('service')):
                raise AssertionError('PostgreSQL connection outside disposable identity blocked')
            return original_connect(conninfo, **kwargs)

        def no_network(*args, **kwargs):
            raise AssertionError('Provider/network access disabled during acceptance')

        def safe_read(path, *args, **kwargs):
            return '' if path.resolve() == ROOT / '.env' else original_read(path, *args, **kwargs)

        for attempt in range(30):
            try:
                with safe_connect(url, connect_timeout=2) as db:
                    version = db.execute('SHOW server_version').fetchone()[0]
                    if not version.startswith('16.'):
                        raise RuntimeError('PostgreSQL major version mismatch')
                break
            except psycopg.OperationalError:
                time.sleep(1)
        else:
            raise RuntimeError('Disposable PostgreSQL readiness timed out')
        report['postgres_version'] = version
        os.environ.update(TEST_DATABASE_URL=url, TEST_META_POSTGRES='1', KDH_PHASE4_ISOLATED='1')
        with patch.object(Path, 'read_text', safe_read), patch.object(psycopg, 'connect', safe_connect), \
                patch.object(socket.socket, 'connect', no_network), patch.object(socket.socket, 'connect_ex', no_network), \
                patch('requests.sessions.Session.request', no_network):
            from kdh.core import Store
            with tempfile.TemporaryDirectory(prefix='kdh_phase4_migration_') as data_dir:
                store = Store(data_dir, url)
                report['migrations'] = store.all('SELECT version,name FROM schema_migrations ORDER BY version')
            suite = unittest.defaultTestLoader.discover(str(ROOT / 'tests'))
            selected = [test for test in flatten(suite) if type(test).__name__.startswith('Postgres')]
            report['selected'] = len(selected)
            report['previously_skipped_selected'] = sum(type(t).__name__ != 'PostgresFacebookBundleTests' for t in selected)
            report['classes'] = {name: sum(type(t).__name__ == name for t in selected)
                                 for name in sorted({type(t).__name__ for t in selected})}

            class Result(unittest.TestResult):
                def startTest(self, test):
                    super().startTest(test)
                    self.started = time.monotonic()

                def record(self, test, status, err=None):
                    row = {'test': test.id(), 'status': status, 'seconds': round(time.monotonic() - self.started, 3)}
                    if err:
                        row['exception_type'] = err[0].__name__
                        frames, tb = [], err[2]
                        while tb:
                            frames.append({'file': Path(tb.tb_frame.f_code.co_filename).name,
                                           'line': tb.tb_lineno, 'function': tb.tb_frame.f_code.co_name})
                            tb = tb.tb_next
                        row['frames'] = frames  # No exception text, locals or credentials.
                    report['tests'].append(row)

                def addSuccess(self, test):
                    super().addSuccess(test); self.record(test, 'PASS')

                def addFailure(self, test, err):
                    super().addFailure(test, err); self.record(test, 'FAIL', err)

                def addError(self, test, err):
                    super().addError(test, err); self.record(test, 'ERROR', err)

                def addSkip(self, test, reason):
                    super().addSkip(test, reason); self.record(test, 'SKIP')

                def addSubTest(self, test, subtest, err):
                    super().addSubTest(test, subtest, err)
                    if err:
                        self.record(test, 'SUBTEST_FAIL', err)

            result = Result()
            print(json.dumps({'run': run, 'selected': len(selected), 'previously_skipped': report['previously_skipped_selected']}), flush=True)
            for index, test in enumerate(selected, 1):
                # Even failing fixture output may contain fixture credentials: discard it.
                with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                    test.run(result)
                if index % 10 == 0 or index == len(selected):
                    print(json.dumps({'completed': index, 'total': len(selected), 'failures': len(result.failures), 'errors': len(result.errors)}), flush=True)
            report['summary'] = {'run': result.testsRun, 'pass': result.testsRun - len(result.failures) - len(result.errors) - len(result.skipped),
                                 'fail': len(result.failures), 'error': len(result.errors), 'skip': len(result.skipped)}
            report['success'] = result.wasSuccessful() and not result.skipped and report['previously_skipped_selected'] == 104
    except Exception as exc:
        report['blocked_exception_type'] = type(exc).__name__
        report['success'] = False
    finally:
        if container_id:
            try:
                info = json.loads(docker('inspect', container_id))[0]
                if (info['Id'] != container_id or info['Name'] != '/' + run
                        or info['Config']['Labels'].get('kdh.phase4.run') != run):
                    raise RuntimeError('Cleanup identity mismatch')
                docker('rm', '-f', container_id)
                report['cleanup'] = 'removed_verified_disposable_container_only'
            except Exception as exc:
                report['cleanup'] = 'blocked_' + type(exc).__name__
                report['success'] = False
        (folder / 'results.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
        print(json.dumps({key: report[key] for key in ('run', 'summary', 'success', 'cleanup', 'blocked_exception_type') if key in report}), flush=True)
    return 0 if report.get('success') else 1


if __name__ == '__main__':
    raise SystemExit(main())
