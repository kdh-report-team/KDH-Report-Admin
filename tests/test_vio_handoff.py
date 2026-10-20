"""Sandbox-only handoff; all data and approvals are disposable fixtures."""
import base64
import hashlib
import os
import secrets
import unittest
from urllib.parse import parse_qs, urlsplit

import test_facebook_bundles as fixtures


class VioHandoffTests(unittest.TestCase):
    fixture_class = fixtures.FacebookBundleTests

    def setUp(self):
        self.f = self.fixture_class()
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.f.candidate('facebook_content')
        self.report = self.f.bundle(self.f.release())
        self.assertEqual(self.f.post(f'/api/report-bundles/{self.report}/revisions/1/publish', {'status': 'provisional'}).status_code, 200)
        self.app, self.store, self.browser = self.f.app, self.f.store, self.f.client
        self.app.config.update(APP_URL='http://localhost', META_CLIENT_ID='client_meta_sandbox',
                               REPORT_VIO_HANDOFF_ENABLED=True, REPORT_NEW_BASE_URL='https://new.example.test')
        self.user = self.store.one("SELECT id FROM users WHERE role='admin'")['id']
        self.service = {'Authorization': 'Bearer fixture-service'}
        self.grant()

    def grant(self, active=True):
        self.assertEqual(self.f.post(f'/api/report-bundles/{self.report}/access',
            {'user_id': self.user, 'min_revision': 1, 'max_revision': 1, 'active': active}).status_code, 200)

    def create(self, **changes):
        self.verifier = secrets.token_urlsafe(48)
        self.data = {'state': secrets.token_urlsafe(32),
            'challenge': base64.urlsafe_b64encode(hashlib.sha256(self.verifier.encode()).digest()).decode().rstrip('='),
            'target_id': self.report, 'revision': 1, 'mode': 'published',
            'audience': 'https://new.example.test', 'callback': 'https://new.example.test/auth/handoff/callback', **changes}
        return self.app.test_client().post('/api/internal/v1/handoffs', json=self.data, headers=self.service)

    def code(self):
        r = self.create(); self.assertEqual(r.status_code, 200, r.json)
        self.tx = r.json['transaction']
        r = self.browser.get('/viewer/authorize?transaction=' + self.tx)
        self.assertEqual(r.status_code, 303)
        return {k: v[0] for k, v in parse_qs(urlsplit(r.location).fragment).items()}

    def redeem(self, code, **changes):
        return self.app.test_client().post('/api/internal/v1/handoffs/redeem', headers=self.service,
            json={**code, 'verifier': self.verifier, 'audience': self.data['audience'], 'callback': self.data['callback'], **changes})

    def test_derived_client_grant_pinned_revision_and_replay(self):
        code = self.code()
        self.assertEqual(self.store.one('SELECT client_id FROM viewer_handoffs WHERE id=?', (self.tx,))['client_id'], 'client_meta_sandbox')
        r = self.redeem(code); self.assertEqual(r.status_code, 200)
        headers = {**self.service, 'X-KDH-Viewer-Session': r.json['session']}
        path = f'/api/internal/v1/viewer/report-bundles/{self.report}?revision='
        self.assertEqual(self.app.test_client().get(path + '1', headers=headers).status_code, 200)
        self.assertEqual(self.app.test_client().get(path + '2', headers=headers).status_code, 404)
        self.assertEqual(self.redeem(code).status_code, 400)
        self.grant(False)
        self.assertEqual(self.app.test_client().get(path + '1', headers=headers).status_code, 404)

    def test_wrong_client_target_revision_and_no_preview(self):
        for change in ({'client_id': 'client_kinderhealth'}, {'target_id': 'rpt_' + 'f' * 32},
                       {'revision': 2}, {'target_id': self.f.candidate_id, 'revision': 0, 'mode': 'preview'}):
            with self.subTest(change=change): self.assertIn(self.create(**change).status_code, (400, 403, 404))

    def test_disabled_flag_and_production_origin_denied(self):
        for change in ({'REPORT_VIO_HANDOFF_ENABLED': False}, {'META_CLIENT_ID': 'client_kinderhealth'},
                       {'APP_URL': 'https://admin.example.test'}):
            old = {k: self.app.config[k] for k in change}; self.app.config.update(change)
            self.assertEqual(self.create().status_code, 400)
            self.app.config.update(old)

    def test_no_grant_is_not_bypassed_by_admin_role(self):
        self.grant(False)
        r = self.create(); self.assertEqual(r.status_code, 200)
        self.assertEqual(self.browser.get('/viewer/authorize?transaction=' + r.json['transaction']).status_code, 404)

    def test_wrong_binding_and_revoked_session(self):
        code = self.code()
        for change in ({'state': secrets.token_urlsafe(32)}, {'verifier': secrets.token_urlsafe(48)},
                       {'callback': 'https://evil.example.test/auth/handoff/callback'}):
            self.assertEqual(self.redeem(code, **change).status_code, 400)
        self.store.execute('DELETE FROM sessions WHERE user_id=?', (self.user,))
        self.assertEqual(self.redeem(code).status_code, 401)

    def test_expired_and_flag_revoked_before_redeem(self):
        code = self.code()
        self.app.config['REPORT_VIO_HANDOFF_ENABLED'] = False
        self.assertEqual(self.redeem(code).status_code, 403)
        self.app.config['REPORT_VIO_HANDOFF_ENABLED'] = True
        self.store.execute("UPDATE viewer_handoffs SET expires_at='2000-01-01' WHERE id=?", (self.tx,))
        self.assertEqual(self.redeem(code).status_code, 400)

    def test_draft_and_bad_signature_denied(self):
        row = self.store.one('SELECT snapshot_payload FROM report_bundles WHERE bundle_key=?', (self.report,))
        self.store.execute("UPDATE report_bundles SET status='draft' WHERE bundle_key=?", (self.report,))
        self.assertEqual(self.create().status_code, 404)
        self.store.execute("UPDATE report_bundles SET status='provisional',snapshot_payload=? WHERE bundle_key=?",
                           (row['snapshot_payload'].replace('marketing-release-v1', 'invalid'), self.report))
        import json
        p = json.loads(row['snapshot_payload']); p['sections']['facebook_content']['data']['release']['seal'] = 'invalid'
        self.store.execute('UPDATE report_bundles SET snapshot_payload=? WHERE bundle_key=?', (json.dumps(p), self.report))
        self.assertEqual(self.create().status_code, 409)

    def test_ui_capability_tracks_config(self):
        self.assertTrue(self.browser.get('/api/marketing/workflow').json['viewer_handoff_supported'])
        self.app.config['REPORT_VIO_HANDOFF_ENABLED'] = False
        self.assertFalse(self.browser.get('/api/marketing/workflow').json['viewer_handoff_supported'])


from test_facebook_bundles_postgres import PostgresFacebookBundleTests


@unittest.skipUnless(os.getenv('KDH_PHASE4_ISOLATED') == '1' and os.getenv('TEST_DATABASE_URL'),
                     'Requires isolated disposable PostgreSQL')
class PostgresVioHandoffTests(VioHandoffTests):
    fixture_class = PostgresFacebookBundleTests
