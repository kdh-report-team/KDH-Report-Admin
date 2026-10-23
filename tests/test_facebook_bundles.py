"""Offline dual Meta -> existing review/release/Bundle/Viewer acceptance.

All provider transports are fixtures; every database is disposable SQLite.
No live OAuth, discovery, sync, publication or cross-application test.
"""
import copy
import json
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import test_meta_reporting_routes as fixtures
from kdh.core import now, pack
from kdh.meta_contract import ATTRIBUTION, normalize_ads, metrics


class AdsSemanticsTests(unittest.TestCase):
    def account(self):
        return {'id': 'act_123', 'currency': 'USD', 'timezone_name': 'America/Los_Angeles'}

    def rows(self):
        return [{'date_start': '2026-09-01', 'spend': '0.10', 'impressions': '100', 'clicks': '10',
                 'inline_link_clicks': '4', 'reach': '70', 'actions': [{'action_type': 'lead', 'value': '1'}]},
                {'date_start': '2026-09-02', 'spend': '0.20', 'impressions': '300', 'clicks': '30',
                 'inline_link_clicks': '8', 'reach': '80', 'actions': [{'action_type': 'offsite_conversion.fb_pixel_lead', 'value': '8'}]}]

    def test_precision_ratios_nonadditive_and_exact_action(self):
        result = normalize_ads(self.rows(), [], self.account(), '2026-09-01', '2026-09-02')
        totals = result['totals']
        self.assertEqual(totals['spend_decimal'], '0.30')
        self.assertEqual(totals['ctr'], .1)
        self.assertEqual(totals['cpc'], .0075)
        self.assertEqual(totals['cpm'], .75)
        self.assertEqual(totals['link_clicks'], 12)
        self.assertIsNone(totals['reach']); self.assertIsNone(totals['frequency'])
        self.assertIsNone(totals['leads']); self.assertIsNone(totals['cost_per_result'])
        self.assertEqual(result['daily'][0]['leads'], 1)
        self.assertEqual(result['attribution'], ATTRIBUTION)
        self.assertEqual(result['report_timezone'], 'America/Los_Angeles')
        self.assertEqual(next(m for m in metrics(result) if m['key'] == 'spend')['value'], '0.30')

    def test_partial_duplicate_account_currency_and_invalid_counters(self):
        rows = self.rows()
        partial = normalize_ads(rows[:1], [], self.account(), '2026-09-01', '2026-09-02')
        self.assertEqual(partial['status'], 'partial'); self.assertIsNone(partial['totals']['spend'])
        spend = next(m for m in metrics(partial) if m['key'] == 'spend')
        self.assertEqual(spend['status'], 'partial')
        self.assertEqual(spend['coverage'], {'available': 1, 'expected': 2, 'unit': 'days'})
        dedup = normalize_ads(rows + [copy.deepcopy(rows[0])], [], self.account(), '2026-09-01', '2026-09-02')
        self.assertEqual(len(dedup['daily']), 2)
        for changes in ({'account_id': '456'}, {'account_currency': 'VND'}, {'date_stop': '2026-09-02'},
                        {'impressions': '1.5'}, {'spend': 'NaN'}):
            broken = copy.deepcopy(rows); broken[0].update(changes)
            with self.subTest(changes=changes), self.assertRaises(Exception):
                normalize_ads(broken, [], self.account(), '2026-09-01', '2026-09-02')
        bad = copy.deepcopy(rows[0]); bad['spend'] = '9'
        with self.assertRaises(Exception):
            normalize_ads(rows + [bad], [], self.account(), '2026-09-01', '2026-09-02')

    def test_real_zero_is_not_missing_conversion_and_zero_denominator(self):
        rows = self.rows()
        for row in rows:
            row.update(spend='0', clicks='0', impressions='0', actions=[{'action_type': 'lead', 'value': '0'}])
        totals = normalize_ads(rows, [], self.account(), '2026-09-01', '2026-09-02')['totals']
        self.assertEqual(totals['leads'], 0)
        self.assertEqual(totals['spend_decimal'], '0')
        for key in ('ctr', 'cpc', 'cpm', 'cost_per_result', 'purchases', 'roas'):
            self.assertIsNone(totals[key])


class FacebookBundleTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.MetaReportingHttpTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.store, self.app, self.client, self.meta = self.fixture.store, self.fixture.app, self.fixture.client, self.fixture.meta
        self.grant = {'access_token': 'FIXTURE_ONLY', 'client_id': 'client_meta_sandbox', 'app_id': 'test-app',
                      'account_id': '999123', 'connected_at': now(), 'expires_at': 0,
                      'data_access_expires_at': (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
                      'scopes': ['pages_show_list', 'pages_read_engagement', 'pages_read_user_content', 'ads_read']}
        self.meta.read = lambda: copy.deepcopy(self.grant)
        self.meta.config['META_GRAPH_VERSION'] = 'v26.0'
        self.meta.cipher = self.store.report_cipher
        self.store.execute('INSERT INTO secrets (name,value) VALUES (?,?)',
                           ('meta:client_meta_sandbox', self.meta.cipher.encrypt(pack(self.grant).encode())))
        self.store.execute('UPDATE connections SET secret_name=? WHERE id=?', ('meta:client_meta_sandbox', self.fixture.connection_id))
        self.app.config['REPORT_SERVICE_TOKEN'] = 'fixture-service'

    def post(self, path, body):
        return self.fixture.post(path, body)

    def candidate(self, source):
        self.source = source
        self.asset = self.fixture.select_asset(source, '1234' if source == 'facebook_content' else 'act_123')
        self.fixture.sync_asset(self.asset)
        run = self.store.one('SELECT * FROM sync_runs WHERE asset_id=? ORDER BY created_at DESC', (self.asset,))
        self.run_id = run['id']
        self.assertIsNotNone(self.store.one('SELECT * FROM source_attestations WHERE sync_run_id=?', (self.run_id,)))
        result = self.post('/api/marketing/datasets', {'client_id': 'client_meta_sandbox', 'source': source,
                           'asset_id': self.asset, 'start': self.fixture.START, 'end': self.fixture.END})
        self.assertEqual(result.status_code, 201, result.json)
        self.origin = result.json['dataset_id']
        review = self.client.get(f'/api/marketing/datasets/{self.origin}/review').json
        result = self.post(f'/api/marketing/datasets/{self.origin}/review', {'decision': 'approved_internal',
                           'note': 'Offline fixture reviewer confirms exact period and semantics.', 'expected_sha256': review['dataset_sha256']})
        self.assertEqual(result.status_code, 201, result.json)
        result = self.post(f'/api/marketing/datasets/{self.origin}/release-candidates',
                          {'expected_sha256': review['dataset_sha256'], 'expected_review_id': result.json['review_id']})
        self.assertEqual(result.status_code, 201, result.json)
        self.candidate_id = result.json['release_dataset_id']
        return self.candidate_id

    def check(self):
        r = self.client.get(f'/api/marketing/release-candidates/{self.candidate_id}/source-check')
        self.assertEqual(r.status_code, 200, r.json)
        return r.json

    def approve(self, checks=None):
        checks = checks or self.check()
        return self.post(f'/api/marketing/release-candidates/{self.candidate_id}/approval', {
            'decision': 'release_approved', 'note': 'Offline reviewer approves only supported qualified metrics.',
            'expected_candidate_sha256': checks['candidate_sha256'], 'expected_dataset_sha256': checks['dataset_sha256'],
            'expected_review_id': checks['internal_review_id']})

    def release(self):
        checks = self.check(); self.assertEqual(checks['issues'], [])
        approval = self.approve(checks); self.assertEqual(approval.status_code, 201, approval.json)
        result = self.post(f'/api/marketing/release-candidates/{self.candidate_id}/release-snapshots',
                          {'expected_approval_id': approval.json['approval_id'], 'expected_candidate_sha256': checks['candidate_sha256']})
        self.assertEqual(result.status_code, 201, result.json)
        return result.json['dataset_id']

    def bundle(self, release):
        r = self.post('/api/report-bundles', {'client_id': 'client_meta_sandbox', 'name': 'Offline ' + self.source,
                      'start_date': self.fixture.START, 'end_date': self.fixture.END, 'default_section': self.source,
                      'sections': [{'key': self.source, 'dataset_id': release}]})
        self.assertEqual(r.status_code, 201, r.json)
        return r.json['report_id']

    def insights_candidate(self):
        from test_meta_content_insights import response
        self.grant['scopes'].append('read_insights')
        self.store.execute('UPDATE secrets SET value=? WHERE name=?',
            (self.meta.cipher.encrypt(pack(self.grant).encode()), 'meta:client_meta_sandbox'))
        original = self.meta.call
        def provider(method, path, **kwargs):
            if path.endswith('/insights') and not path.startswith('act_'):
                return response(kwargs['params']['metric'], path.split('/')[0])
            return original(method, path, **kwargs)
        with patch.object(self.meta, 'call', side_effect=provider):
            self.candidate('facebook_content')

    def test_insights_saved_attested_reviewed_and_immutable_bundle(self):
        self.insights_candidate()
        before = self.store.one('SELECT data FROM datasets WHERE id=?', (self.origin,))['data']
        frozen = json.loads(before)['marketing']['preview']['content_report']['insights']
        self.assertEqual(frozen['measurements'][0]['value'], 3)
        release = self.release(); report = self.bundle(release)
        self.assertEqual(self.post(f'/api/report-bundles/{report}/revisions/1/publish', {'status': 'provisional'}).status_code, 200)
        path = f'/api/internal/v1/report-bundles/{report}?revision=1'
        result = self.client.get(path, headers={'Authorization': 'Bearer fixture-service'})
        self.assertEqual(result.status_code, 200)
        source = result.json['sections']['facebook_content']['data']['sources']['facebook_content']
        self.assertEqual(source['content_report']['insights'], frozen)
        self.assertEqual(source['content_report']['review_status'], 'approved')
        self.assertIsNone(source['totals']['engagements'])
        self.assertEqual(self.store.one('SELECT data FROM datasets WHERE id=?', (self.origin,))['data'], before)
        self.assertNotIn('FIXTURE_ONLY', result.get_data(as_text=True))

    def test_insights_removed_permission_blocks_source_verification(self):
        self.insights_candidate()
        self.assertEqual(self.check()['issues'], [])
        self.grant['scopes'].remove('read_insights')
        self.store.execute('UPDATE secrets SET value=? WHERE name=?',
            (self.meta.cipher.encrypt(pack(self.grant).encode()), 'meta:client_meta_sandbox'))
        self.assertIn('insights_permission_unconfirmed', self.check()['issues'])

    def test_dual_bundles_immutable_and_viewer_revision_authorization(self):
        reports = []
        for source in ('facebook_content', 'facebook_ads'):
            self.candidate(source)
            before = self.store.one('SELECT data FROM datasets WHERE id=?', (self.origin,))['data']
            release = self.release(); report = self.bundle(release); reports.append(report)
            published = self.post(f'/api/report-bundles/{report}/revisions/1/publish', {'status': 'final'})
            self.assertEqual(published.status_code, 200, published.json)
            listed = self.client.get('/api/report-bundles')
            self.assertEqual(listed.status_code, 200, listed.get_data(as_text=True))
            item = next(row for row in listed.json if row['report_id'] == report and row['revision'] == 1)
            self.assertEqual(item['client_id'], 'client_meta_sandbox')
            self.assertEqual(item['default_section'], source)
            self.assertFalse(item['viewer_handoff_supported'])
            path = f'/api/internal/v1/report-bundles/{report}?revision=1'
            self.assertEqual(self.client.get(path).status_code, 401)
            response = self.client.get(path, headers={'Authorization': 'Bearer fixture-service'})
            self.assertEqual(response.status_code, 200, response.json)
            bundle = response.json
            self.assertEqual(bundle['schema_version'], '1.0')
            self.assertEqual(bundle['client']['id'], 'client_meta_sandbox')
            self.assertEqual(list(bundle['sections']), [source])
            data = bundle['sections'][source]['data']['sources'][source]
            self.assertEqual(data['identity']['external_id'], '1234' if source == 'facebook_content' else 'act_123')
            kpis = {k['key']: k for k in data['kpis']}
            self.assertTrue(all(k['evidence_status'] == 'provider_origin_confirmed'
                                for k in kpis.values() if k['verified']))
            if source == 'facebook_content':
                self.assertEqual(kpis['posts_published']['value'], 1)
                self.assertEqual(kpis['reactions_lifetime']['value'], 4)
                self.assertIsNone(kpis['engagements']['value']); self.assertFalse(kpis['engagements']['verified'])
            else:
                self.assertEqual(kpis['spend']['value'], '121.00')
                self.assertEqual(kpis['spend']['currency'], 'VND')
                self.assertIsNone(kpis['reach']['value']); self.assertEqual(data['attribution'], ATTRIBUTION)
            self.assertNotIn('FIXTURE_ONLY', response.get_data(as_text=True))
            self.assertEqual(before, self.store.one('SELECT data FROM datasets WHERE id=?', (self.origin,))['data'])
            revision = self.post(f'/api/report-bundles/{report}/revisions', {})
            self.assertEqual(revision.status_code, 201, revision.json)
            self.assertEqual(self.post(f'/api/report-bundles/{report}/revisions/2/publish', {'status': 'final'}).status_code, 200)
            self.store.execute("UPDATE source_snapshots SET payload='{}' WHERE sync_run_id=?", (self.run_id,))
            self.assertEqual(self.client.get(path, headers={'Authorization': 'Bearer fixture-service'}).json, bundle)
            # Published revisions cannot be rewritten, even by Admin.
            self.assertNotEqual(self.client.patch(f'/api/report-bundles/{report}/revisions/1', json={},
                headers={'X-KDH-Request': '1', 'X-CSRF-Token': self.fixture.csrf}).status_code, 200)
        self.assertNotEqual(*reports)
        user = self.post('/api/users', {'email': 'meta-viewer@example.test', 'name': 'Meta Viewer',
            'password': 'Fixture-viewer-password-123', 'role': 'viewer', 'allowed': ['facebook-content', 'facebook-ads']})
        self.assertEqual(user.status_code, 201, user.json)
        viewer = self.store.one('SELECT id FROM users WHERE email=?', ('meta-viewer@example.test',))['id']
        browser = self.app.test_client()
        self.assertEqual(browser.post('/api/auth/login', json={'email': 'meta-viewer@example.test',
            'password': 'Fixture-viewer-password-123'}, headers={'X-KDH-Request': '1'}).status_code, 200)
        headers = {'Authorization': 'Bearer fixture-service', 'X-KDH-Viewer-Session': browser.get_cookie('kdh_session').value}
        for report in reports:
            path = f'/api/internal/v1/viewer/report-bundles/{report}?revision=1'
            self.assertEqual(browser.get(path, headers=headers).status_code, 404)
            self.assertEqual(self.post(f'/api/report-bundles/{report}/access', {'user_id': viewer,
                'min_revision': 1, 'max_revision': 1, 'active': True}).status_code, 200)
            self.assertEqual(browser.get(path, headers=headers).status_code, 200)
            self.assertEqual(browser.get(path.replace('revision=1', 'revision=2'), headers=headers).status_code, 404)
            self.assertEqual(browser.get(f'/api/marketing/datasets/{self.origin}/review').status_code, 403)

    def test_missing_forged_attestation_and_changed_grant_block_publication(self):
        self.candidate('facebook_content')
        self.assertEqual(self.check()['issues'], [])
        row = self.store.one('SELECT * FROM source_attestations WHERE sync_run_id=?', (self.run_id,))
        for bad in ('missing', 'forged'):
            if bad == 'missing':
                self.store.execute('DELETE FROM source_attestations WHERE sync_run_id=?', (self.run_id,))
            else:
                self.store.execute('INSERT INTO source_attestations (sync_run_id,claims,seal,created_at) VALUES (?,?,?,?)',
                                   (self.run_id, row['claims'], 'forged', now()))
            self.assertIn('provider_origin_unconfirmed', self.check()['issues'])
            self.assertEqual(self.approve().status_code, 409)
        self.store.execute('UPDATE source_attestations SET seal=? WHERE sync_run_id=?', (row['seal'], self.run_id))
        self.grant['scopes'].remove('pages_read_user_content')
        self.store.execute('UPDATE secrets SET value=? WHERE name=?',
                           (self.meta.cipher.encrypt(pack(self.grant).encode()), 'meta:client_meta_sandbox'))
        self.assertIn('grant_changed_or_missing_permission', self.check()['issues'])

    def test_wrong_client_missing_client_comparison_and_stale_review(self):
        self.candidate('facebook_ads')
        for extra in ({}, {'client_id': 'client_kinderhealth'}, {'client_id': 'client_meta_sandbox',
                       'compare_start': '2026-08-30', 'compare_end': '2026-08-31'}):
            result = self.post('/api/marketing/datasets', {'source': self.source, 'asset_id': self.asset,
                'start': self.fixture.START, 'end': self.fixture.END, **extra})
            self.assertIn(result.status_code, (400, 403, 409), result.json)
        check = self.check(); self.assertEqual(self.approve(check).status_code, 201)
        self.store.execute("UPDATE users SET role='operator' WHERE id=?", (self.fixture.admin_id,))
        from kdh.marketing_source_check import read_source_check
        self.assertIn('reviewer_not_authorized', read_source_check(self.store, self.candidate_id)['issues'])
        self.store.execute("UPDATE users SET role='admin' WHERE id=?", (self.fixture.admin_id,))
        review = self.client.get(f'/api/marketing/datasets/{self.origin}/review').json
        self.post(f'/api/marketing/datasets/{self.origin}/review', {'decision': 'needs_changes',
                  'note': 'New fixture decision invalidates prior approval.', 'expected_sha256': review['dataset_sha256']})
        self.assertFalse(self.check()['provider_origin_confirmed'])
        self.assertEqual(self.approve(check).status_code, 409)

    def test_ads_attribution_and_snapshot_mutations_are_rejected(self):
        self.candidate('facebook_ads')
        snap = self.store.one('SELECT * FROM source_snapshots WHERE sync_run_id=?', (self.run_id,))
        payload = json.loads(snap['payload'])
        payload['attribution']['action_report_time'] = 'conversion'
        self.store.execute('UPDATE source_snapshots SET payload=? WHERE id=?', (pack(payload), snap['id']))
        self.assertIn('ads_currency_timezone_attribution_mismatch', self.check()['issues'])
        self.assertIn('provider_origin_unconfirmed', self.check()['issues'])
        self.assertEqual(self.approve().status_code, 409)

    def test_content_partial_lifetime_retains_missing_and_period_no_data(self):
        original_call = self.meta.call
        def call(method, path, **kwargs):
            if path == '1234/posts':
                return {'data': [
                    {'id': '1234_101', 'created_time': '2026-09-01T23:30:00-0100', 'reactions': {'summary': {'total_count': 0}}},
                    {'id': '1234_102', 'created_time': '2026-09-02T02:00:00Z', 'shares': {'count': 5}}]}
            return original_call(method, path, **kwargs)
        with patch.object(self.meta, 'call', side_effect=call):
            self.candidate('facebook_content')
        release = self.release()
        data = json.loads(self.store.one('SELECT data FROM datasets WHERE id=?', (release,))['data'])
        source = data['sources']['facebook_content']; kpis = {m['key']: m for m in source['kpis']}
        self.assertEqual(source['daily'][0]['posts_published'], 0)
        self.assertEqual(source['daily'][1]['posts_published'], 2)
        self.assertEqual(kpis['shares_lifetime']['observed_sum'], 5)
        self.assertEqual(kpis['shares_lifetime']['coverage'], {'available': 1, 'expected': 2, 'unit': 'posts'})
        self.assertIsNone(kpis['shares_lifetime']['value']); self.assertFalse(kpis['shares_lifetime']['verified'])
        self.assertIsNone(kpis['engagements']['value'])

    def test_explicit_ads_lookup_and_missing_permission_never_enumerates_other_accounts(self):
        response = self.client.get('/api/meta/reporting/assets?source=facebook_ads&external_id=act_123')
        self.assertEqual(response.status_code, 200, response.json)
        self.assertEqual(self.meta.calls, [('act_123', None)])
        self.meta.calls.clear(); self.grant['scopes'].remove('ads_read')
        response = self.client.get('/api/meta/reporting/assets?source=facebook_ads&external_id=act_123')
        self.assertEqual(response.status_code, 403); self.assertEqual(self.meta.calls, [])

    def test_empty_ads_observation_cannot_be_reviewed_or_released(self):
        original_call = self.meta.call

        def call(method, path, **kwargs):
            if path == 'act_123/insights':
                return {'data': []}
            return original_call(method, path, **kwargs)

        with patch.object(self.meta, 'call', side_effect=call):
            asset = self.fixture.select_asset('facebook_ads', 'act_123')
            self.fixture.sync_asset(asset)

        run = self.store.one('SELECT * FROM sync_runs WHERE asset_id=? ORDER BY created_at DESC', (asset,))
        snapshot = self.store.one('SELECT * FROM source_snapshots WHERE sync_run_id=?', (run['id'],))
        payload = json.loads(snapshot['payload'])
        self.assertEqual(payload['status'], 'no_data')
        self.assertEqual(payload['data_origin'], 'meta_api_unverified')
        self.assertEqual(payload['daily'], [])
        self.assertEqual(payload['entries'], [])
        ads_kpis = {metric['key']: metric for metric in metrics(payload)}
        for key in ('spend', 'impressions', 'clicks'):
            self.assertIsNone(ads_kpis[key]['value'])
            self.assertEqual(ads_kpis[key]['status'], 'no_data')
            self.assertFalse(ads_kpis[key]['verified'])
            self.assertFalse(ads_kpis[key]['publishable'])
        self.assertEqual(self.store.one(
            'SELECT COUNT(*) AS n FROM daily_metrics WHERE sync_run_id=?', (run['id'],))['n'], 0)

        result = self.post('/api/marketing/datasets', {'client_id': 'client_meta_sandbox',
            'source': 'facebook_ads', 'asset_id': asset,
            'start': self.fixture.START, 'end': self.fixture.END})
        self.assertEqual(result.status_code, 201, result.json)
        dataset_id = result.json['dataset_id']
        review = self.client.get(f'/api/marketing/datasets/{dataset_id}/review')
        self.assertEqual(review.status_code, 200, review.json)
        self.assertEqual(review.json['review_status'], 'needs_data')
        self.assertFalse(review.json['checks']['can_approve_internal'])
        rejected = self.post(f'/api/marketing/datasets/{dataset_id}/review', {
            'decision': 'approved_internal', 'note': 'No-data fixture must remain blocked.',
            'expected_sha256': review.json['dataset_sha256']})
        self.assertEqual(rejected.status_code, 409, rejected.json)
        self.assertEqual(rejected.json['code'], 'insufficient_evidence')
        self.assertEqual(self.store.one(
            "SELECT COUNT(*) AS n FROM datasets WHERE report_type='facebook-ads' AND valid=1")['n'], 0)
        self.assertEqual(self.store.one('SELECT COUNT(*) AS n FROM report_bundles')['n'], 0)

    def test_complete_empty_content_period_preserves_zero_and_missing_lifetime(self):
        original_call = self.meta.call
        def call(method, path, **kwargs):
            return {'data': []} if path == '1234/posts' else original_call(method, path, **kwargs)
        with patch.object(self.meta, 'call', side_effect=call):
            self.candidate('facebook_content')
        release = self.release()
        report = self.bundle(release)
        self.assertEqual(self.post(f'/api/report-bundles/{report}/revisions/1/publish', {'status': 'final'}).status_code, 200)
        data = json.loads(self.store.one('SELECT data FROM datasets WHERE id=?', (release,))['data'])
        source = data['sources']['facebook_content']
        kpis = {m['key']: m for m in source['kpis']}
        self.assertEqual(source['ingestion_status'], 'no_data')
        self.assertEqual(kpis['posts_published']['value'], 0)
        self.assertTrue(kpis['posts_published']['verified'])
        for key in ('engagements', 'reactions_lifetime', 'comments_lifetime', 'shares_lifetime'):
            self.assertIsNone(kpis[key]['value'])
            self.assertFalse(kpis[key]['verified'])

    def test_receipt_cannot_be_reused_for_a_different_snapshot_identity(self):
        self.candidate('facebook_content')
        self.store.execute("UPDATE source_snapshots SET id='replacement-snapshot' WHERE sync_run_id=?", (self.run_id,))
        self.assertIn('snapshot_identity_mismatch', self.check()['issues'])
        self.assertEqual(self.approve().status_code, 409)

    def test_partial_ads_persists_observations_without_advancing_complete_watermark(self):
        asset = self.fixture.select_asset('facebook_ads', 'act_123')
        original_call = self.meta.call
        def call(method, path, **kwargs):
            result = original_call(method, path, **kwargs)
            if path == 'act_123/insights' and kwargs.get('params', {}).get('level') == 'account':
                result['data'] = result['data'][:1]
            return result
        with patch.object(self.meta, 'call', side_effect=call):
            self.fixture.sync_asset(asset)
        snapshot = self.store.one('SELECT payload FROM source_snapshots WHERE asset_id=?', (asset,))
        payload = json.loads(snapshot['payload'])
        self.assertEqual(payload['status'], 'partial')
        self.assertIsNone(payload['totals']['spend_decimal'])
        self.assertIsNone(self.store.one('SELECT * FROM sync_watermarks WHERE asset_id=?', (asset,)))
        self.assertGreater(self.store.one('SELECT COUNT(*) AS n FROM daily_metrics WHERE asset_id=?', (asset,))['n'], 0)

    def test_historical_snapshot_cannot_acquire_receipt_or_dataset_implicitly(self):
        self.candidate('facebook_content')
        snap = self.store.one('SELECT * FROM source_snapshots WHERE sync_run_id=?', (self.run_id,))
        payload = json.loads(snap['payload']); payload.pop('contract_version')
        self.store.execute('UPDATE source_snapshots SET payload=? WHERE id=?', (pack(payload), snap['id']))
        self.store.execute('DELETE FROM source_attestations WHERE sync_run_id=?', (self.run_id,))
        response = self.post('/api/marketing/datasets', {'client_id': 'client_meta_sandbox', 'source': self.source,
            'asset_id': self.asset, 'start': self.fixture.START, 'end': self.fixture.END})
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json['code'], 'meta_contract_missing')
        self.assertEqual(self.store.one('SELECT COUNT(*) AS n FROM source_attestations')['n'], 0)

    def test_evidence_expiry_and_wrong_asset_currency_fail_closed(self):
        self.candidate('facebook_ads')
        # Age is evaluated without provider requests or writes to the snapshot.
        class Future(datetime):
            @classmethod
            def now(cls, tz=None):
                return datetime.now(tz) + timedelta(days=8)
        with patch('kdh.meta_marketing.datetime', Future):
            self.assertIn('evidence_stale', self.check()['issues'])
        self.store.execute("UPDATE source_assets SET currency='USD' WHERE id=?", (self.asset,))
        self.assertIn('ads_currency_timezone_attribution_mismatch', self.check()['issues'])
        self.store.execute("UPDATE source_assets SET client_id='client_kinderhealth' WHERE id=?", (self.asset,))
        self.assertFalse(self.check()['provider_origin_confirmed'])

    def test_failed_or_partial_period_cannot_release_and_unverified_bundle_cannot_publish(self):
        self.candidate('facebook_ads')
        report = self.bundle(self.candidate_id)
        for status in ('provisional', 'final'):
            response = self.post(f'/api/report-bundles/{report}/revisions/1/publish', {'status': status})
            self.assertEqual(response.status_code, 409)
            self.assertEqual(response.json['code'], 'marketing_review_required')
        self.store.execute("UPDATE sync_runs SET status='failed' WHERE id=?", (self.run_id,))
        self.assertFalse(self.check()['provider_origin_confirmed'])
        self.assertEqual(self.approve().status_code, 409)

    def test_stale_candidate_hash_and_mismatched_section_are_rejected(self):
        self.candidate('facebook_content')
        checks = self.check(); checks['candidate_sha256'] = '0' * 64
        self.assertEqual(self.approve(checks).status_code, 409)
        release = self.release()
        result = self.post('/api/report-bundles', {'client_id': 'client_meta_sandbox', 'name': 'Wrong section',
            'start_date': self.fixture.START, 'end_date': self.fixture.END, 'default_section': 'facebook_ads',
            'sections': [{'key': 'facebook_ads', 'dataset_id': release}]})
        self.assertEqual(result.status_code, 400)
        self.assertEqual(result.json['code'], 'meta_bundle_scope_mismatch')

