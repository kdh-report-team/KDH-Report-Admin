"""Meta sync diagnostics against temporary SQLite; all provider traffic is mocked."""
from contextlib import contextmanager
import json
import logging
import os
import sqlite3
import subprocess
import sys
import unittest
from uuid import uuid4
from types import SimpleNamespace
from unittest.mock import patch

import psycopg
import requests

from kdh.core import now, pack, uid
from kdh.google import SourceError
from kdh.jobs import Worker
from kdh.meta import Meta
from kdh.meta_diagnostics import MetaRequestError, MetaSyncDiagnostics
from kdh.meta_reporting_worker import MetaReportingWorker
import test_meta_worker_integration as fixtures


SECRETS = ('PRIVATE_USER_TOKEN', 'PRIVATE_PAGE_TOKEN', 'PRIVATE_APP_SECRET',
           'PRIVATE_OAUTH_CODE', 'PRIVATE_COOKIE', 'PRIVATE_PASSWORD')
PRIVATE = ' '.join(SECRETS) + ' Authorization: Bearer PRIVATE_USER_TOKEN https://graph.invalid/?access_token=PRIVATE_PAGE_TOKEN'


class MetaDiagnosticsTests(unittest.TestCase):
    def setUp(self):
        fixtures.MetaWorkerIntegrationTests.setUp(self)
        network = patch('requests.sessions.Session.request', side_effect=AssertionError('No external HTTP in tests'))
        network.start()
        self.addCleanup(network.stop)
        delay = patch('kdh.meta_reporting.time.sleep')
        delay.start()
        self.addCleanup(delay.stop)
        self.meta = fixtures.FakeMeta({
            ('me/accounts', None): {'data': [{'id': '1234', 'access_token': 'PRIVATE_PAGE_TOKEN'}]},
            ('1234/posts', None): {'data': [{
                'id': '1234_1', 'created_time': '2026-09-01T03:00:00+0000',
                'reactions': {'summary': {'total_count': 4}},
            }]},
        })

    def queue(self):
        asset_id = self.platform.upsert_asset(client_id=self.client_id, provider='meta',
            asset_type='facebook_page', external_id='1234', name='Mock Page',
            connection_id=self.connection_id)
        job_id = uid()
        params = {'source': 'facebook_content', 'asset_id': asset_id, 'report_type': 'facebook-content',
                  'start': '2026-09-01', 'end': '2026-09-02', 'demo': False}
        self.store.execute('''INSERT INTO jobs (id,kind,user_id,params,status,active_key,created_at)
            VALUES (?,?,?,?,?,?,?)''', (job_id, 'meta_sync', self.admin_id, pack(params), 'queued', job_id, now()))
        return job_id

    def run_job(self):
        job_id = self.queue()
        with self.assertLogs('kdh.meta_sync', level=logging.INFO) as captured:
            self.assertTrue(Worker(self.store, fixtures.FakeGoogle(), self.meta).run_one(job_id))
        logs = [json.loads(record.getMessage()) for record in captured.records]
        job = self.store.one('SELECT status,error,steps FROM jobs WHERE id=?', (job_id,))
        sync = self.store.one('SELECT * FROM sync_runs WHERE job_id=?', (job_id,))
        for record in captured.records:
            self.assertIsNone(record.exc_info)
            self.assertIsNone(record.stack_info)
            self.assertFalse(record.args)
        for event in logs:
            self.assertEqual(event['source'], 'facebook_content')
            self.assertEqual(event['client_id'], 'client_meta_sandbox')
            self.assertEqual(event['job_id'], job_id)
            self.assertNotIn('message', event)
            if 'sync_run_id' in event:
                self.assertIsNotNone(sync)
                self.assertEqual(event['sync_run_id'], sync['id'])
        public_and_logs = pack([logs, job, sync, self.store.all('SELECT * FROM events')])
        for secret in (*SECRETS, 'Authorization:', 'access_token=', 'Traceback (most recent call last)'):
            self.assertNotIn(secret, public_and_logs)
        return logs, job, sync

    def assert_failure(self, stage, code, exception_type):
        logs, job, sync = self.run_job()
        failures = [event for event in logs if event['status'] == 'failed']
        self.assertEqual(len(failures), 1, failures)
        failure = failures[0]
        self.assertEqual((failure['stage'], failure['error_code'], failure['exception_type']),
                         (stage, code, exception_type))
        self.assertTrue(failure['file'].startswith('kdh/'))
        self.assertGreater(failure['line'], 0)
        self.assertEqual(job['status'], 'failed')
        self.assertEqual(sync['status'], 'failed')
        self.assertEqual(sync['error_code'], code)
        self.assertEqual(sync['record_count'], 0)
        self.assertNotIn('exception_type', pack(job))
        self.assertNotIn('kdh/', pack(job))
        for table in ('daily_metrics', 'source_snapshots'):
            self.assertEqual(self.store.one('SELECT COUNT(*) AS n FROM ' + table)['n'], 0)
        self.assertFalse(any(event['stage'] == 'sync_complete' for event in logs))

    def test_success_logs_all_stages_after_commit(self):
        logs, job, sync = self.run_job()
        stages = ['job_validation', 'oauth_validation', 'sync_start', 'page_token', 'fetch_posts', 'normalize_content',
                  'snapshot_validation', 'database_write', 'sync_finalize', 'sync_complete']
        self.assertEqual([event['stage'] for event in logs if event['status'] == 'started'], stages)
        self.assertEqual([event['stage'] for event in logs if event['status'] == 'succeeded'],
                         ['oauth_validation', 'job_validation', *stages[2:]])
        self.assertEqual(logs[-1]['sync_run_id'], sync['id'])
        self.assertEqual(job['status'], 'succeeded')
        self.assertEqual(sync['status'], 'succeeded')
        self.assertEqual(sync['record_count'], 3)
        payload = self.store.one('SELECT payload FROM source_snapshots WHERE sync_run_id=?', (sync['id'],))['payload']
        self.assertEqual(json.loads(payload)['data_origin'], 'meta_api_unverified')
        for secret in SECRETS:
            self.assertNotIn(secret, payload)

    def test_missing_page_token_identifies_permission_stage(self):
        self.meta.replies[('me/accounts', None)] = {'data': [{'id': '1234'}]}
        self.assert_failure('page_token', 'meta_page_permission', 'Problem')

    def test_expired_oauth_fails_before_creating_sync_or_calling_provider(self):
        with patch.object(self.meta, 'info', return_value={'connected': False}), \
                patch.object(self.meta, 'call') as provider:
            logs, job, sync = self.run_job()
        failure = next(event for event in logs if event['status'] == 'failed')
        self.assertEqual((failure['stage'], failure['error_code']),
                         ('oauth_validation', 'meta_reconnect_required'))
        self.assertNotIn('sync_run_id', failure)
        self.assertIsNone(sync)
        self.assertEqual(job['status'], 'failed')
        provider.assert_not_called()

    def test_real_transport_metadata_survives_reader_and_worker_boundaries(self):
        transport = object.__new__(Meta)
        transport.config = {'META_GRAPH_VERSION': 'v26.0'}
        original = self.meta.call
        for path, stage in [('me/accounts', 'page_token'), ('1234/posts', 'fetch_posts')]:
            with self.subTest(stage=stage):
                def call(method, endpoint, **kwargs):
                    return (transport.call(method, endpoint, **kwargs) if endpoint == path
                            else original(method, endpoint, **kwargs))
                response = SimpleNamespace(status_code=400, json=lambda: {'error': {
                    'code': 190, 'error_subcode': 463, 'is_transient': False,
                    'message': PRIVATE, 'error_data': {'secret': PRIVATE}}})
                with patch.object(self.meta, 'call', side_effect=call), \
                        patch('kdh.meta.requests.request', return_value=response):
                    logs, job, sync = self.run_job()
                failure = next(event for event in logs if event['status'] == 'failed')
                self.assertEqual((failure['stage'], failure['error_code']),
                                 (stage, 'meta_reconnect_required'))
                self.assertEqual(failure['sync_run_id'], sync['id'])
                self.assertEqual(failure['http_status'], 400)
                self.assertEqual(failure['graph_error_code'], 190)
                self.assertEqual(failure['graph_error_subcode'], 463)
                self.assertIs(failure['is_transient'], False)
                self.assertEqual(failure['failure_layer'], 'graph_api')
                self.assertEqual(sync['error_code'], 'meta_reconnect_required')
                self.assertNotIn('graph_error_code', pack(job))

    def test_failed_resync_preserves_previous_successful_data(self):
        self.run_job()
        tables = ('daily_metrics', 'source_snapshots', 'sync_watermarks')
        before = {table: self.store.all('SELECT * FROM ' + table) for table in tables}
        self.meta.replies[('1234/posts', None)]['data'].append({
            'id': '1234_2', 'created_time': '2026-09-01T05:00:00+0000'})
        original = MetaReportingWorker._save_metric
        def write_then_fail(worker, *args, **kwargs):
            original(worker, *args, **kwargs)
            raise psycopg.OperationalError(PRIVATE)
        with patch.object(MetaReportingWorker, '_save_metric', write_then_fail):
            logs, job, sync = self.run_job()
        self.assertEqual(job['status'], 'failed')
        self.assertEqual(sync['error_code'], 'meta_database_error')
        self.assertFalse(any(event['stage'] == 'sync_complete' for event in logs))
        for table in tables:
            self.assertEqual(self.store.all('SELECT * FROM ' + table), before[table])

    def test_successful_empty_resync_replaces_only_requested_asset_and_period(self):
        _, _, first_sync = self.run_job()
        snapshot = self.store.one('SELECT * FROM source_snapshots WHERE sync_run_id=?', (first_sync['id'],))
        other_asset = self.platform.upsert_asset(client_id=self.client_id, provider='meta',
            asset_type='facebook_page', external_id='5678', name='Other Page', connection_id=self.connection_id)
        worker = MetaReportingWorker(self.store, self.meta)
        with self.store.connect(immediate=True) as db:
            for asset, day, post in [(first_sync['asset_id'], '2026-08-31', '1234_old'),
                                     (other_asset, '2026-09-01', '5678_other')]:
                worker._save_metric(db, asset_id=asset, source='facebook_content', sync_id=first_sync['id'],
                    entity_type='post', entity_id=post, row={'date': day, 'reactions_lifetime': 8})
        self.meta.replies[('1234/posts', None)] = {'data': []}
        _, job, sync = self.run_job()
        self.assertEqual((job['status'], sync['status']), ('succeeded', 'succeeded'))
        self.assertEqual(json.loads(job['steps'])[0]['status'], 'no_data')
        self.assertEqual(sync['latest_available_date'], '2026-09-02')
        payload = json.loads(self.store.one('SELECT payload FROM source_snapshots WHERE sync_run_id=?', (sync['id'],))['payload'])
        self.assertIsNone(payload['latest_post_date'])
        self.assertEqual(self.store.all("SELECT entity_id FROM daily_metrics WHERE entity_type='post' ORDER BY entity_id"),
                         [{'entity_id': '1234_old'}, {'entity_id': '5678_other'}])
        pages = self.store.all("SELECT metrics FROM daily_metrics WHERE entity_type='page'")
        self.assertEqual(len(pages), 2)
        self.assertTrue(all(json.loads(row['metrics'])['posts_published'] == 0 for row in pages))
        metric = fixtures.read_metric_series(self.store, metric_id='facebook_content.posts_published',
            client_id=self.client_id, allowed_sources={'facebook_content'},
            start='2026-09-01', end='2026-09-02', asset_id=first_sync['asset_id'])
        self.assertEqual(metric['summary']['value'], 0)
        self.assertEqual(metric['data_origin'], 'persisted_unverified')
        self.assertEqual(self.store.one('SELECT * FROM source_snapshots WHERE sync_run_id=?', (first_sync['id'],)), snapshot)

    def test_failed_content_read_preserves_prior_data(self):
        self.run_job()
        tables = ('daily_metrics', 'source_snapshots', 'sync_watermarks', 'connections')
        before = {table: sorted(self.store.all('SELECT * FROM ' + table), key=pack) for table in tables}
        for body, stage in [({}, 'fetch_posts'), ({'data': [{}]}, 'normalize_content')]:
            with self.subTest(stage=stage):
                self.meta.replies[('1234/posts', None)] = body
                logs, job, sync = self.run_job()
                self.assertEqual((job['status'], sync['status']), ('failed', 'failed'))
                failure = next(event for event in logs if event['status'] == 'failed')
                self.assertEqual((failure['stage'], failure['error_code']), (stage, 'meta_data_error'))
                for table, rows in before.items():
                    self.assertEqual(sorted(self.store.all('SELECT * FROM ' + table), key=pack), rows)

    def test_api_and_permission_errors_are_distinct_from_data_and_database(self):
        original = self.meta.call
        for status, code in [('meta_permission_error', 'meta_permission_error'), ('meta_oauth_error', 'meta_api_error')]:
            with self.subTest(status=status):
                def call(method, path, **kwargs):
                    if path == '1234/posts':
                        raise SourceError(status, PRIVATE)
                    return original(method, path, **kwargs)
                with patch.object(self.meta, 'call', side_effect=call):
                    self.assert_failure('fetch_posts', code, 'SourceError')

    def test_malformed_graph_rows_identify_data_error_at_fetch(self):
        self.meta.replies[('1234/posts', None)] = {'data': PRIVATE}
        self.assert_failure('fetch_posts', 'meta_data_error', 'Problem')

    def test_malformed_post_counter_identifies_normalization_failure(self):
        self.meta.replies[('1234/posts', None)]['data'][0]['reactions']['summary'] = PRIVATE
        self.assert_failure('normalize_content', 'meta_data_error', 'Problem')

    def test_snapshot_rejection_keeps_sensitive_payload_out_of_logs(self):
        from kdh.meta_reporting import MetaReportingReader
        original = MetaReportingReader._normalize_content
        def unsafe(reader, *args):
            result = original(reader, *args)
            result['access_token'] = PRIVATE
            return result
        with patch.object(MetaReportingReader, '_normalize_content', unsafe):
            self.assert_failure('snapshot_validation', 'meta_snapshot_invalid', 'ValueError')

    def test_postgres_write_failure_rolls_back_partial_metrics(self):
        original = MetaReportingWorker._save_metric
        def write_then_fail(worker, *args, **kwargs):
            original(worker, *args, **kwargs)
            raise psycopg.OperationalError(PRIVATE)
        with patch.object(MetaReportingWorker, '_save_metric', write_then_fail):
            self.assert_failure('database_write', 'meta_database_error', 'OperationalError')

    def test_finalize_and_commit_failures_do_not_log_sync_success(self):
        original = self.store.connect
        for fail_on_commit in (False, True):
            with self.subTest(commit=fail_on_commit):
                @contextmanager
                def connection(*args, **kwargs):
                    with original(*args, **kwargs) as db:
                        wrote_snapshot = False
                        class Proxy:
                            def execute(inner, sql, values=()):
                                nonlocal wrote_snapshot
                                if 'INSERT INTO source_snapshots' in sql:
                                    wrote_snapshot = True
                                if not fail_on_commit and "UPDATE sync_runs SET status='succeeded'" in sql:
                                    raise psycopg.OperationalError(PRIVATE)
                                return db.execute(sql, values)
                        yield Proxy()
                        if fail_on_commit and wrote_snapshot:
                            raise psycopg.OperationalError(PRIVATE)
                with patch.object(self.store, 'connect', connection):
                    self.assert_failure('sync_finalize', 'meta_database_error', 'OperationalError')

    def test_failure_status_write_does_not_hide_original_error(self):
        with patch.object(self.meta, 'call', side_effect=SourceError('meta_oauth_error', PRIVATE)), \
                patch('kdh.platform_data.PlatformData.finish_sync', side_effect=psycopg.OperationalError(PRIVATE)):
            logs, job, sync = self.run_job()
        failures = [event for event in logs if event['status'] == 'failed']
        self.assertEqual([(event['stage'], event['error_code']) for event in failures],
                         [('page_token', 'meta_api_error'), ('failure_status_write', 'meta_database_error')])
        self.assertEqual(job['status'], 'failed')
        self.assertEqual(sync['status'], 'running')  # failed-status persistence was deliberately unavailable

    def test_jobs_boundary_logs_uncaught_meta_error_without_persisting_message(self):
        with patch.object(MetaReportingWorker, 'run', side_effect=RuntimeError(PRIVATE)):
            logs, job, sync = self.run_job()
        failures = [event for event in logs if event['status'] == 'failed']
        self.assertEqual(failures[0]['stage'], 'job_dispatch')
        self.assertEqual(failures[0]['exception_type'], 'RuntimeError')
        self.assertEqual(failures[0]['error_code'], 'meta_sync_internal_error')
        self.assertEqual(job['status'], 'failed')
        self.assertIsNone(sync)

    def test_job_status_write_failure_is_logged_without_swallowing_original(self):
        original = self.store.execute
        def execute(sql, values=()):
            if "UPDATE jobs SET status='failed'" in sql:
                raise psycopg.OperationalError(PRIVATE)
            return original(sql, values)
        with patch.object(self.meta, 'call', side_effect=SourceError('meta_oauth_error', PRIVATE)), \
                patch.object(self.store, 'execute', side_effect=execute):
            logs, job, sync = self.run_job()
        failures = [event for event in logs if event['status'] == 'failed']
        self.assertEqual([(event['stage'], event['error_code']) for event in failures],
                         [('page_token', 'meta_api_error'), ('job_status_write', 'meta_database_error')])
        self.assertEqual(job['status'], 'running')
        self.assertEqual(sync['status'], 'failed')

    def test_diagnostics_never_format_exception_or_untrusted_context(self):
        class PrivateError(Exception):
            def __str__(self):
                raise AssertionError('Exception messages must never be formatted')
            __repr__ = __str__
        diagnostics = MetaSyncDiagnostics(source=PRIVATE, client_id=PRIVATE, job_id=PRIVATE)
        diagnostics.bind_sync(PRIVATE)
        with self.assertLogs('kdh.meta_sync', level=logging.INFO) as captured:
            diagnostics.start('snapshot_validation')
            try:
                raise PrivateError(PRIVATE) from ValueError(PRIVATE)
            except PrivateError as exc:
                diagnostics.failure(exc)
        events = [json.loads(record.getMessage()) for record in captured.records]
        self.assertEqual(events[-1]['exception_type'], 'PrivateError')
        self.assertEqual(events[-1]['client_id'], 'unknown')
        self.assertEqual(events[-1]['source'], 'unknown')
        self.assertNotIn('job_id', events[-1])
        self.assertNotIn('sync_run_id', events[-1])
        for secret in SECRETS:
            self.assertNotIn(secret, pack(events))

    def test_logger_emits_to_stderr_without_flask_or_debug_configuration(self):
        code = "from kdh.meta_diagnostics import MetaSyncDiagnostics; MetaSyncDiagnostics(source='facebook_content', client_id='client_meta_sandbox', postgres=True).start('fetch_posts')"
        result = subprocess.run([sys.executable, '-c', code], capture_output=True, text=True, check=True)
        self.assertEqual(result.stdout, '')
        event = json.loads(result.stderr)
        self.assertEqual(event['stage'], 'fetch_posts')
        self.assertEqual(event['database'], 'postgresql')

    def test_meta_transport_retains_only_safe_permission_or_api_category(self):
        meta = object.__new__(Meta)
        meta.config = {'META_GRAPH_VERSION': 'v26.0'}
        for http_status, expected in [(401, 'meta_permission_error'), (403, 'meta_permission_error'), (500, 'meta_oauth_error')]:
            with self.subTest(status=http_status):
                response = SimpleNamespace(status_code=http_status, json=lambda: {'error': {'message': PRIVATE}})
                with patch('kdh.meta.requests.request', return_value=response):
                    with self.assertRaises(SourceError) as caught:
                        meta.call('GET', '1234/posts', token='PRIVATE_PAGE_TOKEN')
                self.assertEqual(caught.exception.status, expected)
                for secret in SECRETS:
                    self.assertNotIn(secret, caught.exception.message)


class MetaTransportDiagnosticsTests(unittest.TestCase):
    def setUp(self):
        self.meta = object.__new__(Meta)
        self.meta.config = {'META_GRAPH_VERSION': 'v26.0'}

    def failure(self, response=None, exception=None):
        with patch('kdh.meta.requests.request', return_value=response, side_effect=exception):
            with self.assertRaises(MetaRequestError) as caught:
                self.meta.call('GET', '1234/posts', token=PRIVATE)
        error = caught.exception
        diagnostics = MetaSyncDiagnostics()
        with self.assertLogs('kdh.meta_sync') as logs:
            diagnostics.start('fetch_posts')
            diagnostics.failure(error)
        event = json.loads(logs.records[-1].getMessage())
        for secret in SECRETS:
            self.assertNotIn(secret, pack(event) + str(error) + repr(error.__dict__))
        self.assertIsNone(logs.records[-1].exc_info)
        return error, event

    def test_http_and_graph_error_categories(self):
        for http, code, expected in [(400, 190, 'meta_reconnect_required'),
                                    (400, 10, 'meta_permission_error'),
                                    (400, 200, 'meta_permission_error'),
                                    (200, 190, 'meta_reconnect_required'),
                                    (429, 4, 'meta_api_error'), (500, 2, 'meta_api_error')]:
            with self.subTest(http=http, code=code):
                _, event = self.failure(SimpleNamespace(status_code=http, json=lambda: {'error': {
                    'code': code, 'error_subcode': 42, 'is_transient': True, 'message': PRIVATE}}))
                self.assertEqual(event['error_code'], expected)
                self.assertEqual(event['http_status'], http)
                self.assertEqual(event['graph_error_code'], code)
                self.assertEqual(event['graph_error_subcode'], 42)
                self.assertIs(event['is_transient'], True)

    def test_untrusted_metadata_is_not_coerced_or_logged(self):
        for value in (PRIVATE, True, -1, 2**63, 190.0, [PRIVATE], {'secret': PRIVATE}):
            with self.subTest(value_type=type(value).__name__):
                _, event = self.failure(SimpleNamespace(status_code=400, json=lambda: {'error': {
                    'code': value, 'error_subcode': value, 'is_transient': value, 'message': PRIVATE}}))
                self.assertNotIn('graph_error_code', event)
                self.assertNotIn('graph_error_subcode', event)
                if type(value) is not bool:
                    self.assertNotIn('is_transient', event)
        for body in ({'error': PRIVATE}, {'error': [PRIVATE]}, [PRIVATE]):
            _, event = self.failure(SimpleNamespace(status_code=400, json=lambda: body))
            self.assertEqual(event['error_code'], 'meta_api_error')

    def test_network_and_decode_failures_are_distinct(self):
        for error in (requests.Timeout(PRIVATE), requests.ConnectionError(PRIVATE)):
            _, event = self.failure(exception=error)
            self.assertEqual(event['failure_layer'], 'transport')
            self.assertNotIn('http_status', event)
        for status in (200, 403, 502):
            def bad_json():
                raise ValueError(PRIVATE)
            _, event = self.failure(SimpleNamespace(status_code=status, json=bad_json))
            self.assertEqual(event['http_status'], status)
            self.assertEqual(event['failure_layer'], 'response_decode' if status == 200 else 'graph_api')
        _, event = self.failure(SimpleNamespace(status_code=200, json=lambda: [PRIVATE]))
        self.assertEqual(event['error_code'], 'meta_data_error')

    def test_sqlstate_is_preserved_through_store_constraint_wrapper(self):
        diagnostics = MetaSyncDiagnostics(postgres=True)
        with self.assertLogs('kdh.meta_sync') as logs:
            diagnostics.start('database_write')
            try:
                try:
                    raise psycopg.errors.UniqueViolation(PRIVATE)
                except psycopg.IntegrityError as cause:
                    raise sqlite3.IntegrityError(PRIVATE) from cause
            except sqlite3.IntegrityError as error:
                diagnostics.failure(error)
        event = json.loads(logs.records[-1].getMessage())
        self.assertEqual(event['sqlstate'], '23505')
        self.assertEqual(event['error_code'], 'meta_database_error')
        self.assertNotIn(PRIVATE, pack(event))


@unittest.skipUnless(os.getenv('TEST_DATABASE_URL') and os.getenv('TEST_META_POSTGRES') == '1',
                     'Requires disposable TEST_DATABASE_URL and TEST_META_POSTGRES=1; never production')
class PostgresMetaDiagnosticsTests(unittest.TestCase):
    """Real PostgreSQL transactions, mocked provider; each test owns a fresh schema."""
    queue = MetaDiagnosticsTests.queue
    run_job = MetaDiagnosticsTests.run_job
    assert_failure = MetaDiagnosticsTests.assert_failure
    test_success_logs_all_stages_after_commit = MetaDiagnosticsTests.test_success_logs_all_stages_after_commit
    test_successful_empty_resync_replaces_only_requested_asset_and_period = MetaDiagnosticsTests.test_successful_empty_resync_replaces_only_requested_asset_and_period
    test_failed_content_read_preserves_prior_data = MetaDiagnosticsTests.test_failed_content_read_preserves_prior_data
    test_missing_page_token_identifies_permission_stage = MetaDiagnosticsTests.test_missing_page_token_identifies_permission_stage
    test_snapshot_rejection_keeps_sensitive_payload_out_of_logs = MetaDiagnosticsTests.test_snapshot_rejection_keeps_sensitive_payload_out_of_logs

    def setUp(self):
        from psycopg import sql
        from psycopg.conninfo import make_conninfo
        from kdh.core import Store
        url = os.environ['TEST_DATABASE_URL']
        schema = 'kdh_meta_test_' + uuid4().hex
        with psycopg.connect(url, autocommit=True) as db:
            db.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(schema)))
        def cleanup():
            with psycopg.connect(url, autocommit=True) as db:
                db.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(schema)))
        self.addCleanup(cleanup)
        isolated = make_conninfo(url, options='-csearch_path=' + schema)
        with patch.object(fixtures, 'Store', side_effect=lambda folder, _: Store(folder, isolated)):
            MetaDiagnosticsTests.setUp(self)
        self.assertTrue(self.store.postgres)

    def test_resync_upserts_metrics_and_keeps_prior_snapshot_immutable(self):
        _, first_job, first_sync = self.run_job()
        self.assertEqual(first_job['status'], 'succeeded')
        original = self.store.all('SELECT * FROM source_snapshots ORDER BY id')
        metric_ids = self.store.all('SELECT id FROM daily_metrics ORDER BY id')
        self.meta.replies[('1234/posts', None)]['data'][0]['reactions']['summary']['total_count'] = 9
        _, job, sync = self.run_job()
        self.assertEqual(job['status'], 'succeeded')
        self.assertNotEqual(first_sync['id'], sync['id'])
        self.assertEqual(self.store.all('SELECT id FROM daily_metrics ORDER BY id'), metric_ids)
        self.assertEqual(len(metric_ids), 3)
        post = self.store.one("SELECT metrics,sync_run_id FROM daily_metrics WHERE entity_type='post'")
        self.assertEqual(json.loads(post['metrics'])['reactions_lifetime'], 9)
        self.assertEqual(post['sync_run_id'], sync['id'])
        self.assertEqual(self.store.all('SELECT * FROM source_snapshots WHERE sync_run_id=?',
                                        (first_sync['id'],)), original)
        self.assertEqual(self.store.one('SELECT COUNT(*) AS n FROM source_snapshots')['n'], 2)
        self.assertEqual(self.store.one('SELECT COUNT(*) AS n FROM sync_watermarks')['n'], 1)

    def _successful_state(self):
        _, job, _ = self.run_job()
        self.assertEqual(job['status'], 'succeeded')
        tables = ('daily_metrics', 'source_snapshots', 'sync_watermarks', 'connections')
        return {table: sorted(self.store.all('SELECT * FROM ' + table), key=pack) for table in tables}

    def _assert_preserved(self, before, stage, sqlstate):
        logs, job, sync = self.run_job()
        failure = next(event for event in logs if event['status'] == 'failed')
        self.assertEqual((failure['stage'], failure['error_code'], failure['sqlstate']),
                         (stage, 'meta_database_error', sqlstate))
        self.assertEqual((job['status'], sync['status']), ('failed', 'failed'))
        self.assertFalse(any(event['stage'] == 'sync_complete' for event in logs))
        for table, rows in before.items():
            self.assertEqual(sorted(self.store.all('SELECT * FROM ' + table), key=pack), rows, table)

    def test_real_write_failure_preserves_previous_success(self):
        before = self._successful_state()
        self.meta.replies[('1234/posts', None)]['data'].append({
            'id': '1234_2', 'created_time': '2026-09-02T05:00:00+0000'})
        original = MetaReportingWorker._save_metric
        def duplicate(worker, db, **kwargs):
            original(worker, db, **kwargs)
            db.execute('INSERT INTO clients SELECT * FROM clients WHERE id=?', ('client_meta_sandbox',))
        with patch.object(MetaReportingWorker, '_save_metric', duplicate):
            self._assert_preserved(before, 'database_write', '23505')

    def test_real_deferred_failure_preserves_previous_success(self):
        before = self._successful_state()
        self.store.execute('CREATE TABLE meta_test_snapshot_ids (id TEXT PRIMARY KEY)')
        self.store.execute('INSERT INTO meta_test_snapshot_ids SELECT id FROM source_snapshots')
        self.store.execute('''ALTER TABLE source_snapshots ADD CONSTRAINT meta_test_deferred_fk
            FOREIGN KEY (id) REFERENCES meta_test_snapshot_ids(id) DEFERRABLE INITIALLY DEFERRED''')
        self.meta.replies[('1234/posts', None)]['data'][0]['reactions']['summary']['total_count'] = 99
        self._assert_preserved(before, 'sync_finalize', '23503')

    def test_real_constraint_failure_rolls_back_and_records_sqlstate(self):
        original = MetaReportingWorker._save_metric
        def duplicate(worker, db, **kwargs):
            original(worker, db, **kwargs)
            db.execute('INSERT INTO clients SELECT * FROM clients WHERE id=?', ('client_meta_sandbox',))
        with patch.object(MetaReportingWorker, '_save_metric', duplicate):
            logs, job, sync = self.run_job()
        failure = next(event for event in logs if event['status'] == 'failed')
        self.assertEqual((failure['stage'], failure['error_code'], failure['sqlstate']),
                         ('database_write', 'meta_database_error', '23505'))
        self.assertEqual(job['status'], 'failed')
        self.assertEqual(sync['status'], 'failed')
        for table in ('daily_metrics', 'source_snapshots'):
            self.assertEqual(self.store.one('SELECT COUNT(*) AS n FROM ' + table)['n'], 0)

    def test_real_deferred_constraint_fails_at_commit(self):
        self.store.execute('''ALTER TABLE source_snapshots ADD CONSTRAINT meta_test_deferred_fk
            FOREIGN KEY (id) REFERENCES clients(id) DEFERRABLE INITIALLY DEFERRED''')
        logs, job, sync = self.run_job()
        failure = next(event for event in logs if event['status'] == 'failed')
        self.assertEqual((failure['stage'], failure['error_code'], failure['sqlstate']),
                         ('sync_finalize', 'meta_database_error', '23503'))
        self.assertEqual(job['status'], 'failed')
        self.assertEqual(sync['status'], 'failed')
        self.assertFalse(any(event['stage'] == 'sync_complete' for event in logs))
        for table in ('daily_metrics', 'source_snapshots', 'sync_watermarks'):
            self.assertEqual(self.store.one('SELECT COUNT(*) AS n FROM ' + table)['n'], 0)


if __name__ == '__main__':
    unittest.main()
