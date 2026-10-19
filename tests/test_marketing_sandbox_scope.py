"""Sandbox Marketing ACL regression; providers mocked, disposable SQLite only."""
import copy
import hashlib
import json
import unittest

from kdh.core import now, pack, uid
import test_facebook_bundles as bundle_fixtures


class MarketingSandboxScopeTests(unittest.TestCase):
    def setUp(self):
        self.fx = bundle_fixtures.FacebookBundleTests()
        self.fx.setUp()
        self.addCleanup(self.fx.doCleanups)
        self.client, self.store = self.fx.client, self.fx.store
        self.asset = self.fx.fixture.select_asset('facebook_content', '1234')
        self.fx.fixture.sync_asset(self.asset)
        self.payload = {'client_id': 'client_meta_sandbox', 'source': 'facebook_content',
                        'asset_id': self.asset, 'start': self.fx.fixture.START, 'end': self.fx.fixture.END}
        created = self.fx.post('/api/marketing/datasets', self.payload)
        self.assertEqual(created.status_code, 201)
        self.id = created.json['dataset_id']
        self.raw = self.store.one('SELECT data FROM datasets WHERE id=?', (self.id,))['data']
        self.data = json.loads(self.raw)
        # Deliberately foreign immutable fixture, not business/runtime records.
        self.foreign = uid()
        foreign = copy.deepcopy(self.data)
        foreign.update(id=self.foreign, client_id='client_kinderhealth')
        self.store.execute('INSERT INTO datasets (id,user_id,report_type,created_at,valid,data) VALUES (?,?,?,?,?,?)',
                           (self.foreign, self.fx.fixture.admin_id, 'facebook-content', now(), 0, pack(foreign)))

    def test_index_and_detail_only_runtime_client(self):
        response = self.client.get('/api/marketing/workflow')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['client_id'], 'client_meta_sandbox')
        self.assertFalse(response.json['viewer_handoff_supported'])
        self.assertIn(self.id, [r['id'] for r in response.json['snapshots']])
        self.assertNotIn(self.foreign, [r['id'] for r in response.json['snapshots']])
        self.assertEqual(self.client.get('/api/datasets/' + self.id).status_code, 200)
        self.assertEqual(self.client.get('/api/datasets/' + self.foreign).status_code, 404)
        self.assertEqual(self.client.get('/api/marketing/datasets/' + self.foreign + '/review').status_code, 404)

    def test_query_body_and_foreign_ids_cannot_override_scope(self):
        for path in ('/api/marketing/workflow', '/api/datasets/' + self.id,
                     '/api/marketing/datasets/' + self.id + '/review'):
            self.assertEqual(self.client.get(path + '?client_id=client_kinderhealth').status_code, 403)
        self.assertEqual(self.client.get('/api/marketing/workflow?client_id=client_meta_sandbox&client_id=client_meta_sandbox').status_code, 400)
        for client in ('client_kinderhealth', 'arbitrary', None):
            self.assertEqual(self.fx.post('/api/marketing/datasets', dict(self.payload, client_id=client)).status_code, 403)
        self.assertEqual(self.fx.post('/api/marketing/datasets/' + self.id + '/review', {'client_id': 'client_kinderhealth'}).status_code, 403)
        for tail in ('source-check', 'approval', 'release-snapshots'):
            path = '/api/marketing/release-candidates/' + self.foreign + '/' + tail
            response = self.fx.post(path, {}) if tail == 'release-snapshots' else self.client.get(path)
            self.assertEqual(response.status_code, 404)

    def test_roles_and_inactive_user_cannot_review(self):
        for role in ('viewer', 'operator'):
            self.store.execute('UPDATE users SET role=? WHERE id=?', (role, self.fx.fixture.admin_id))
            for path in ('/marketing', '/api/marketing/workflow', '/api/datasets/' + self.id,
                         '/api/marketing/datasets/' + self.id + '/review', '/api/marketing/datasets/' + self.id + '/source-evidence'):
                self.assertEqual(self.client.get(path).status_code, 403)
            self.assertEqual(self.fx.post('/api/marketing/datasets/' + self.id + '/review', {}).status_code, 403)
        self.store.execute("UPDATE users SET role='admin',active=0 WHERE id=?", (self.fx.fixture.admin_id,))
        self.assertEqual(self.client.get('/api/marketing/workflow').status_code, 401)

    def test_receipt_evidence_is_readonly_and_not_official_verification(self):
        response = self.client.get('/api/marketing/datasets/' + self.id + '/source-evidence')
        self.assertEqual(response.status_code, 200)
        evidence = response.json
        for key in ('receipt_exists', 'receipt_valid', 'snapshot_hash_matches', 'daily_consistent', 'fresh'):
            self.assertIs(evidence[key], True, key)
        self.assertIs(evidence['verified'], False)
        self.assertIs(evidence['publishable'], False)
        self.assertEqual(evidence['official_source_check'], 'not_performed')
        self.assertEqual(evidence['external_id'], '1234')
        self.assertNotIn('FIXTURE_ONLY', response.get_data(as_text=True))
        self.assertNotIn('seal', evidence)
        self.assertEqual(self.store.one('SELECT data FROM datasets WHERE id=?', (self.id,))['data'], self.raw)
        review = self.client.get('/api/marketing/datasets/' + self.id + '/review').json
        self.assertEqual(review['dataset_sha256'], hashlib.sha256(self.raw.encode()).hexdigest())
        self.assertIsNone(review['latest_review'])
        self.assertIs(review['checks']['provider_verified'], False)
        readiness = self.client.get('/api/marketing/datasets/' + self.id + '/release-readiness').json
        self.assertIn('review_missing', readiness['issues'])
        self.assertFalse(readiness['ready_to_stage'])

    def test_missing_receipt_is_not_rendered_valid(self):
        self.store.execute('DELETE FROM source_attestations')
        response = self.client.get('/api/marketing/datasets/' + self.id + '/source-evidence')
        self.assertEqual(response.status_code, 200)
        self.assertIs(response.json['receipt_exists'], False)
        self.assertIs(response.json['receipt_valid'], False)
        self.assertIs(response.json['verified'], False)

    def test_nested_candidate_cannot_reference_foreign_origin(self):
        candidate = copy.deepcopy(self.data)
        candidate.update(id=uid(), dataset_kind='marketing_release_candidate_v1',
                         release_candidate={'origin_dataset_id': self.foreign})
        self.store.execute('INSERT INTO datasets (id,user_id,report_type,created_at,valid,data) VALUES (?,?,?,?,?,?)',
                           (candidate['id'], self.fx.fixture.admin_id, 'facebook-content', now(), 0, pack(candidate)))
        for path in ('/api/datasets/' + candidate['id'], '/api/marketing/release-candidates/' + candidate['id'] + '/source-check'):
            self.assertEqual(self.client.get(path).status_code, 404)

    def test_meta_preview_no_comparison_and_semantics_preserved(self):
        path = '/api/marketing/preview?source=facebook_content&asset_id=' + self.asset + '&start=' + self.payload['start'] + '&end=' + self.payload['end']
        response = self.client.get(path)
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json['comparison'])
        self.assertEqual(response.json['widgets'], self.data['marketing']['preview']['widgets'])
        comparison = self.client.get(path + '&compare_start=2026-08-01&compare_end=2026-08-02')
        self.assertEqual(comparison.status_code, 409)
        self.assertEqual(comparison.json['code'], 'meta_comparison_unsupported')

    def test_primary_runtime_keeps_existing_policy_and_workflow(self):
        self.fx.app.config['META_CLIENT_ID'] = 'client_kinderhealth'
        workflow = self.client.get('/api/marketing/workflow').json
        self.assertEqual(workflow['client_id'], 'client_kinderhealth')
        self.assertIn(self.foreign, [r['id'] for r in workflow['snapshots']])
        self.assertNotIn(self.id, [r['id'] for r in workflow['snapshots']])
        # Existing production Admin policy is intentionally unchanged.
        self.assertEqual(self.client.get('/api/datasets/' + self.foreign).status_code, 200)
        self.assertEqual(self.client.get('/api/datasets/' + self.id).status_code, 200)
