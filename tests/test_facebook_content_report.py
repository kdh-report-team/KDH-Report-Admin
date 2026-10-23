"""Offline metadata, reporting and editorial scope; no provider or runtime DB."""
import copy
import unittest

from kdh.core import Problem
from kdh.facebook_content_report import build_content_report, post_metadata, approved_content_report
from test_meta_reporting import FakeMeta
from kdh.meta_reporting import MetaReportingReader


def source_fixture():
    fake = FakeMeta({('me/accounts', None, None): {'data': [{'id': '1234', 'access_token': 'fixture'}]},
        ('1234/posts', None, None): {'data': [
            {'id': '1234_1', 'created_time': '2026-09-01T00:00:00+0000', 'message': 'Nội dung bài thật từ fixture',
             'permalink_url': 'https://www.facebook.com/1234/posts/1?tracking=remove',
             'attachments': {'data': [{'type': 'photo'}]}, 'reactions': {'summary': {'total_count': 0}},
             'comments': {'summary': {'total_count': 2}}},
            {'id': '1234_2', 'created_time': '2026-09-02T00:00:00+0000',
             'shares': {'count': 1}, 'reactions': {'summary': {'total_count': 3}}}]}})
    result = MetaReportingReader(fake).content('1234', '2026-09-01', '2026-09-02')
    result.update(identity={'client_id': 'client_meta_sandbox', 'external_id': '1234', 'asset_type': 'facebook_page'},
                  fetched_at='2026-09-03T00:00:00+00:00', provenance={'permissions': fake.scopes})
    return result


class ContentReportTests(unittest.TestCase):
    def test_metadata_retained_without_reels_guess_or_unsafe_links(self):
        p = source_fixture()
        self.assertEqual(p['entries'][0]['format'], 'photo')
        self.assertEqual(p['entries'][0]['permalink_url'], 'https://www.facebook.com/1234/posts/1')
        self.assertIsNone(p['entries'][1]['title'])
        video = post_metadata({'attachments': {'data': [{'type': 'video_inline'}]}}, '1234_1')
        self.assertEqual(video['format'], 'video')
        for url in ('javascript:alert(1)', 'https://facebook.com.evil/1234/posts/1',
                    'https://www.facebook.com/9999/posts/1', 'https://user:pass@facebook.com/1234/posts/1'):
            self.assertIsNone(post_metadata({'permalink_url': url}, '1234_1')['permalink_url'])

    def test_complete_requirement_inventory_without_false_totals(self):
        p = source_fixture(); before = copy.deepcopy(p)
        r = build_content_report(p)
        m = {v['key']: v for v in r['metrics']}
        self.assertEqual(m['posts_published']['value'], 2)
        self.assertEqual(m['reactions_lifetime']['value'], 3)
        self.assertIsNone(m['comments_lifetime']['value'])
        self.assertEqual(m['shares_lifetime']['status'], 'partial')
        self.assertIsNone(m['engagements']['value'])
        for key in ('reach', 'engagement_rate', 'followers_gained', 'link_clicks', 'ctr', 'response_rate'):
            self.assertIsNone(m[key]['value']); self.assertTrue(m[key]['reason'])
        self.assertEqual(len(r['sections']), 7)
        self.assertEqual(r['sections']['formats']['coverage']['available'], 1)
        self.assertEqual(sum(x['count'] for x in r['sections']['formats']['rows']), 2)
        self.assertEqual(p, before)

    def test_editorial_is_separate_pending_and_never_updates_source(self):
        p = source_fixture(); before = copy.deepcopy(p)
        r = build_content_report(p, {'topics': {'1234_1': 'Sản phẩm'}, 'notes': {'posts': 'Cần thử định dạng khác.'}})
        self.assertEqual(r['sections']['topics']['coverage']['available'], 1)
        self.assertEqual(r['sections']['posts']['commentary']['status'], 'pending_review')
        released = approved_content_report(r)
        self.assertEqual(released['sections']['posts']['commentary']['status'], 'approved')
        self.assertEqual(r['review_status'], 'pending_review')
        self.assertEqual(p, before)

    def test_editorial_rejects_foreign_post_scope_and_invalid_input(self):
        for editorial in ({'topics': {'9999_1': 'Foreign'}}, {'notes': {'other': 'Unknown'}},
                          {'notes': {'posts': 1}}, {'approved': True}, {'topics': {'1234_1': ''}}):
            with self.subTest(editorial=editorial), self.assertRaises(Problem):
                build_content_report(source_fixture(), editorial)

    def test_empty_period_is_zero_posts_not_zero_insights(self):
        p = source_fixture(); p['entries'] = []
        p['totals']['posts_published'] = 0
        for row in p['daily']: row['posts_published'] = 0
        r = build_content_report(p)
        self.assertEqual(r['metrics'][0]['value'], 0)
        self.assertEqual(r['sections']['posts']['status'], 'no_data')
        self.assertEqual(r['sections']['formats']['rows'], [])


class ContentWorkflowTests(unittest.TestCase):
    def setUp(self):
        from test_facebook_bundles import FacebookBundleTests
        self.fx = FacebookBundleTests()
        self.fx.setUp()
        self.addCleanup(self.fx.doCleanups)

    def test_preview_is_read_only_and_editorial_is_frozen_through_release(self):
        fx = self.fx
        asset = fx.fixture.select_asset('facebook_content', '1234')
        fx.fixture.sync_asset(asset)
        request = dict(source='facebook_content', asset_id=asset, start=fx.fixture.START, end=fx.fixture.END,
                       content_editorial={'notes': {'overview': 'Nhận xét người phụ trách, cần duyệt.'}})
        before = fx.store.all('SELECT id,data FROM datasets')
        result = fx.post('/api/marketing/preview', request)
        self.assertEqual(result.status_code, 200, result.json)
        self.assertEqual(fx.store.all('SELECT id,data FROM datasets'), before)
        self.assertEqual(result.json['content_report']['review_status'], 'pending_review')
        wrong = fx.post('/api/marketing/preview', dict(request, content_editorial={'topics': {'wrong': 'x'}}))
        self.assertEqual(wrong.status_code, 400)
        # Full editorial Dataset -> human review -> source-check -> release.
        fx.source = 'facebook_content'
        created = fx.post('/api/marketing/datasets', dict(request, client_id='client_meta_sandbox'))
        self.assertEqual(created.status_code, 201, created.json)
        fx.origin = created.json['dataset_id']
        review = fx.client.get(f'/api/marketing/datasets/{fx.origin}/review').json
        decision = fx.post(f'/api/marketing/datasets/{fx.origin}/review', dict(decision='approved_internal',
            note='Fixture human review of editorial content.', expected_sha256=review['dataset_sha256']))
        self.assertEqual(decision.status_code, 201, decision.json)
        candidate = fx.post(f'/api/marketing/datasets/{fx.origin}/release-candidates',
            dict(expected_sha256=review['dataset_sha256'], expected_review_id=decision.json['review_id']))
        self.assertEqual(candidate.status_code, 201, candidate.json)
        fx.candidate_id = candidate.json['release_dataset_id']
        raw = fx.store.one('SELECT data FROM datasets WHERE id=?', (fx.origin,))['data']
        fx.release()
        self.assertEqual(fx.store.one('SELECT data FROM datasets WHERE id=?', (fx.origin,))['data'], raw)
        import json
        released = [json.loads(r['data']) for r in fx.store.all('SELECT data FROM datasets')
                    if json.loads(r['data']).get('dataset_kind') == 'marketing_release_snapshot_v1']
        self.assertEqual(released[0]['sources']['facebook_content']['content_report']['review_status'], 'approved')
        self.assertEqual(released[0]['sources']['facebook_content']['content_report']['sections']['overview']['commentary'],
            {'text': request['content_editorial']['notes']['overview'], 'origin': 'editorial', 'status': 'approved'})

    def test_editorial_preview_requires_admin_csrf_and_exact_asset(self):
        fx = self.fx
        asset = fx.fixture.select_asset('facebook_content', '1234')
        fx.fixture.sync_asset(asset)
        request = dict(source='facebook_content', asset_id=asset, start=fx.fixture.START, end=fx.fixture.END)
        self.assertEqual(fx.client.post('/api/marketing/preview', json=request).status_code, 403)
        self.assertEqual(fx.post('/api/marketing/preview', dict(request, asset_id='foreign')).status_code, 404)
        for role in ('operator', 'viewer'):
            fx.store.execute('UPDATE users SET role=? WHERE id=?', (role, fx.fixture.admin_id))
            self.assertEqual(fx.post('/api/marketing/preview', request).status_code, 403)
