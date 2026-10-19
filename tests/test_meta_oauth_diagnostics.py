"""OAuth failures expose only fixed stages and allowlisted scalar metadata."""
import json
import sqlite3
import unittest
from unittest.mock import patch

import test_app
import test_meta
from kdh.meta_diagnostics import MetaExpirationError, MetaOAuthDiagnostics, MetaRequestError


class OAuthDiagnosticsTests(unittest.TestCase):
    client_id = 'client_meta_sandbox'
    permissions = ('pages_show_list', 'pages_read_engagement')
    prepare = test_meta.MetaCases.prepare
    post = test_meta.MetaCases.post
    start = test_meta.MetaCases.start
    callback = test_meta.MetaCases.callback
    provider = test_meta.MetaCases.provider
    setUp = test_meta.SQLiteMetaTest.setUp
    tearDown = test_app.AppTest.tearDown

    def events(self, logs):
        events = [json.loads(record.getMessage()) for record in logs.records]
        raw = json.dumps(events)
        for secret in ('test-code', 'test-short-token', 'test-long-token',
                       'test-meta-secret', 'private-provider-message', 'test-user'):
            self.assertNotIn(secret, raw)
        for event in events:
            self.assertEqual(event['event'], 'meta_oauth')
            self.assertRegex(event['attempt_id'], r'^[0-9a-f]{32}$')
        return events

    def test_exchange_failure_logs_stage_and_numeric_metadata_only(self):
        state = self.start()
        error = MetaRequestError(http_status=400, graph_error={
            'code': 100, 'error_subcode': 36008, 'message': 'private-provider-message',
        })
        with self.assertLogs('kdh.meta_sync') as logs, patch.object(self.meta, 'call', side_effect=error):
            response = self.callback(state)
        self.assertIn('oauth=failed', response.location)
        event = self.events(logs)[0]
        self.assertEqual(event['stage'], 'code_exchange')
        self.assertEqual(event['http_status'], 400)
        self.assertEqual(event['graph_error_code'], 100)
        self.assertEqual(event['graph_error_subcode'], 36008)
        self.assertIsNone(self.store.one('SELECT * FROM meta_oauth_states'))

    def test_token_validation_and_permissions_have_distinct_stages(self):
        for key, value, stage in (
            ('type', 'SYSTEM_USER', 'token_validation'),
            ('expires_at', 1, 'expiration_validation'),
            ('scopes', [], 'permissions_validation'),
        ):
            with self.subTest(stage=stage):
                state = self.start()
                with patch.dict(self.metadata, {key: value}), self.assertLogs('kdh.meta_sync') as logs, \
                        patch('kdh.meta.requests.request', side_effect=self.provider):
                    response = self.callback(state)
                self.assertIn('oauth=failed', response.location)
                self.assertEqual(self.events(logs)[0]['stage'], stage)

    def test_invalid_state_denial_and_success_are_distinct(self):
        with self.assertLogs('kdh.meta_sync') as logs:
            response = self.callback('wrong-state')
        self.assertIn('oauth=failed', response.location)
        self.assertEqual(self.events(logs)[0]['stage'], 'state_validation')
        state = self.start()
        with self.assertLogs('kdh.meta_sync') as logs:
            response = self.callback(state, error='access_denied')
        self.assertEqual(self.events(logs)[0]['status'], 'denied')
        state = self.start()
        with self.assertLogs('kdh.meta_sync') as logs, patch('kdh.meta.requests.request', side_effect=self.provider):
            response = self.callback(state)
        self.assertIn('oauth=success', response.location)
        self.assertEqual(self.events(logs)[0]['status'], 'success')
        self.assertEqual(self.events(logs)[0]['stage'], 'connection_write')

    def test_cleanup_failure_does_not_hide_original_exchange_failure(self):
        state = self.start()
        error = MetaRequestError(http_status=400, graph_error={'code': 100})
        with self.assertLogs('kdh.meta_sync') as logs, \
                patch.object(self.meta, 'call', side_effect=error), \
                patch.object(self.store, 'execute', side_effect=sqlite3.OperationalError('private-provider-message')):
            response = self.callback(state)
        self.assertIn('oauth=failed', response.location)
        events = self.events(logs)
        self.assertEqual([e['stage'] for e in events], ['state_cleanup', 'code_exchange'])
        self.assertEqual(events[0]['attempt_id'], events[1]['attempt_id'])

    def test_rejected_expiry_identifies_field_and_reason_without_provider_value(self):
        for field, value, reason in (
            ('expires_at', None, 'missing'),
            ('expires_at', True, 'invalid_type'),
            ('expires_at', 'private-provider-message', 'invalid_type'),
            ('expires_at', float('inf'), 'out_of_range'),
            ('expires_at', float('nan'), 'out_of_range'),
            ('expires_at', 1, 'past'),
            ('data_access_expires_at', 1, 'past'),
            ('data_access_expires_at', 'private-provider-message', 'invalid_type'),
        ):
            with self.subTest(field=field, reason=reason):
                state = self.start()
                with patch.dict(self.metadata, {field: value}), self.assertLogs('kdh.meta_sync') as logs, \
                        patch('kdh.meta.requests.request', side_effect=self.provider) as request:
                    response = self.callback(state)
                self.assertIn('oauth=failed', response.location)
                event = self.events(logs)[0]
                self.assertEqual(event['stage'], 'expiration_validation')
                self.assertEqual(event['expiration_field'], field)
                self.assertEqual(event['expiration_reason'], reason)
                self.assertEqual(request.call_count, 3)  # No profile fetch after rejected metadata.
                self.assertIsNone(self.meta.read())
                self.assertIsNone(self.store.one('SELECT * FROM meta_oauth_states'))

    def test_optional_expiry_remains_optional_and_success_has_no_failure_metadata(self):
        for value in (None, 0):
            with self.subTest(value=value):
                state = self.start()
                with patch.dict(self.metadata, {'data_access_expires_at': value}), \
                        self.assertLogs('kdh.meta_sync') as logs, \
                        patch('kdh.meta.requests.request', side_effect=self.provider):
                    response = self.callback(state)
                self.assertIn('oauth=success', response.location)
                event = self.events(logs)[0]
                self.assertNotIn('expiration_field', event)
                self.assertNotIn('expiration_reason', event)
                self.assertIsNone(self.meta.read()['data_access_expires_at'])

    def test_expiry_diagnostics_revalidate_allowlist_at_log_boundary(self):
        error = MetaExpirationError('expires_at', 'zero')
        error.field = 'private-provider-message'
        error.reason = {'access_token': 'test-long-token'}
        diagnostics = MetaOAuthDiagnostics()
        diagnostics.start('expiration_validation')
        with self.assertLogs('kdh.meta_sync') as logs:
            diagnostics.finish(exc=error)
        event = self.events(logs)[0]
        self.assertEqual(event['expiration_field'], 'unknown')
        self.assertEqual(event['expiration_reason'], 'unknown')
