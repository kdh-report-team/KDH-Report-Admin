"""Isolated Meta reader tests; no real Meta credentials or network calls."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from kdh.meta_reporting import MetaReportingReader, validate_range
from kdh.core import Problem
from kdh.meta import Meta
from kdh.meta_contract import metrics as contract_metrics
from kdh.meta_diagnostics import MetaRequestError


class FakeMeta:
    def __init__(self, responses):
        self.responses = responses
        self.calls = []
        self.scopes = ['pages_show_list', 'pages_read_engagement', 'ads_read']

    def info(self):
        return {'connected': True}

    def read(self):
        return {'access_token': 'test-user-token', 'scopes': self.scopes}

    def call(self, method, path, *, token, params):
        self.calls.append((method, path, token, dict(params)))
        assert method == 'GET'
        assert 'access_token' not in params
        key = (path, params.get('level'), params.get('after'))
        if path == 'act_123' and key not in self.responses:
            return {'id': 'act_123', 'currency': 'VND', 'timezone_name': 'Asia/Ho_Chi_Minh'}
        return self.responses[key]


class MetaReportingTests(unittest.TestCase):
    def test_pagination_does_not_retry_permanent_or_unclassified_errors(self):
        from kdh.google import SourceError
        errors = [
            MetaRequestError(http_status=403, graph_error={'code': 10, 'is_transient': True}),
            MetaRequestError(http_status=400, graph_error={'code': 190}),
            MetaRequestError(http_status=401),
            MetaRequestError(http_status=400, graph_error={'code': 102, 'is_transient': True}),
            MetaRequestError(http_status=200, failure_layer='response_decode'),
            MetaRequestError(http_status=400, graph_error={'code': 100, 'is_transient': True}),
            SourceError('invalid_data', 'fixture'),
            SourceError('meta_oauth_error', 'fixture'),
            SourceError('permission_denied', 'fixture'),
            ValueError('fixture'),
        ]
        for error in errors:
            with self.subTest(error=type(error).__name__, status=getattr(error, 'status', None)):
                fake = FakeMeta({})
                with patch.object(fake, 'call', side_effect=error) as call, \
                        patch('kdh.meta_reporting.time.sleep') as sleep, \
                        self.assertRaises(type(error)) as caught:
                    MetaReportingReader(fake)._page_rows('fixture', 'fixture', {})
                self.assertIs(caught.exception, error)
                self.assertEqual(call.call_count, 1)
                sleep.assert_not_called()

    def test_pagination_transient_retry_is_bounded_and_preserves_empty_success(self):
        errors = [MetaRequestError(failure_layer='transport'),
                  MetaRequestError(http_status=503), MetaRequestError(http_status=429),
                  MetaRequestError(http_status=400, graph_error={'is_transient': True})]
        for error in errors:
            for recovered in (True, False):
                with self.subTest(error=error.safe_metadata(), recovered=recovered):
                    fake = FakeMeta({})
                    effects = [error, {'data': []}] if recovered else [error] * 3
                    with patch.object(fake, 'call', side_effect=effects) as call, \
                            patch('kdh.meta_reporting.time.sleep') as sleep:
                        if recovered:
                            self.assertEqual(MetaReportingReader(fake)._page_rows('fixture', 'fixture', {}), [])
                        else:
                            with self.assertRaises(type(error)) as caught:
                                MetaReportingReader(fake)._page_rows('fixture', 'fixture', {})
                            self.assertIs(caught.exception, error)
                    self.assertEqual(call.call_count, 2 if recovered else 3)
                    self.assertEqual(sleep.call_count, 1 if recovered else 2)

    def test_invalid_list_response_is_not_retried(self):
        for response in ({}, {'data': None}, {'data': {}}, []):
            fake = FakeMeta({})
            with patch.object(fake, 'call', return_value=response) as call, \
                    patch('kdh.meta_reporting.time.sleep') as sleep, self.assertRaises(Problem):
                MetaReportingReader(fake)._page_rows('fixture', 'fixture', {})
            self.assertEqual(call.call_count, 1)
            sleep.assert_not_called()

    def test_discovery_never_returns_page_token(self):
        fake = FakeMeta({
            ('me/adaccounts', None, None): {'data': [{'id': 'act_1234', 'name': 'Ads 1', 'currency': 'VND'}]},
            ('me/accounts', None, None): {'data': [
                {'id': '9876', 'name': 'Test Page', 'access_token': 'PAGE-SECRET', 'tasks': ['ANALYZE']}]},
        })
        result = MetaReportingReader(fake).discover()
        self.assertEqual(result['facebook_ads'][0]['id'], 'act_1234')
        self.assertEqual(result['facebook_content'][0]['id'], '9876')
        self.assertNotIn('PAGE-SECRET', str(result))

    def test_page_only_grant_discovers_pages_without_calling_adaccounts(self):
        fake = FakeMeta({
            ('me/accounts', None, None): {'data': [
                {'id': '9876', 'name': 'VIO Agency', 'access_token': 'PAGE-SECRET', 'tasks': ['ANALYZE']}],
                'paging': {'next': 'https://graph.invalid/?access_token=PAGE-SECRET',
                           'cursors': {'after': 'page2'}}},
            ('me/accounts', None, 'page2'): {'data': [{'id': '1234', 'name': 'Second Page'}]},
        })
        fake.scopes = ['pages_show_list', 'pages_read_engagement']
        result = MetaReportingReader(fake).discover()
        self.assertEqual(result['facebook_ads'], [])
        self.assertEqual([page['id'] for page in result['facebook_content']], ['9876', '1234'])
        self.assertEqual([call[1] for call in fake.calls], ['me/accounts', 'me/accounts'])
        for secret in ('test-user-token', 'PAGE-SECRET', 'access_token', 'paging'):
            self.assertNotIn(secret, str(result))

    def test_missing_or_malformed_ads_permission_blocks_insights_without_network(self):
        fake = FakeMeta({})
        for scopes in (['pages_show_list', 'pages_read_engagement'], [], None, 'ads_read',
                       {'ads_read': True}, ['ads_read', None]):
            with self.subTest(scopes=scopes):
                fake.scopes = scopes
                with self.assertRaises(Problem) as caught:
                    MetaReportingReader(fake).ads('act_123', '2026-09-01', '2026-09-02')
                self.assertEqual(caught.exception.status, 403)
                self.assertEqual(caught.exception.code, 'meta_ads_permission')
                self.assertIn('ads_read', str(caught.exception))
                self.assertNotIn('test-user-token', str(caught.exception))
                self.assertEqual(fake.calls, [])

    def test_cursor_paging_without_following_next_url(self):
        fake = FakeMeta({
            ('me/adaccounts', None, None): {'data': [{'id': 'act_10'}],
                'paging': {'next': 'https://evil.invalid/?access_token=leak', 'cursors': {'after': 'cursor1'}}},
            ('me/adaccounts', None, 'cursor1'): {'data': [{'id': 'act_20'}]},
            ('me/accounts', None, None): {'data': []},
        })
        data = MetaReportingReader(fake).discover()
        self.assertEqual(len(data['facebook_ads']), 2)
        self.assertEqual(fake.calls[1][3]['after'], 'cursor1')

    def test_ads_totals_do_not_sum_unique_reach(self):
        fake = FakeMeta({
            ('act_123/insights', 'account', None): {'data': [
                {'date_start': '2026-09-01', 'spend': '100.75', 'impressions': '123',
                    'clicks': '11', 'reach': '90', 'actions': [{'action_type': 'lead', 'value': '2'}]},
                {'date_start': '2026-09-02', 'spend': '20.25', 'impressions': '50',
                    'clicks': '4', 'reach': '30', 'actions': [{'action_type': 'lead', 'value': '1'}]}]},
            ('act_123/insights', 'campaign', None): {'data': [
                {'campaign_id': '321', 'campaign_name': 'Campaign A', 'date_start': '2026-09-01',
                 'spend': '100.75', 'impressions': '123', 'clicks': '11'}]},
        })
        result = MetaReportingReader(fake).ads('act_123', '2026-09-01', '2026-09-02')
        self.assertEqual(result['totals']['spend'], 121.0)
        self.assertEqual(result['totals']['leads'], 3.0)
        self.assertIsNone(result['totals']['reach'])
        self.assertEqual(len(result['daily']), 2)
        self.assertEqual(len(result['entries']), 1)
        self.assertNotIn('test-user-token', str(result))

    def test_content_lifetime_engagement_is_not_a_daily_metric(self):
        fake = FakeMeta({
            ('me/accounts', None, None): {'data': [
                {'id': '1234', 'access_token': 'page-secret'}]},
            ('1234/posts', None, None): {'data': [
                {'id': '1234_1', 'created_time': '2026-09-01T03:00:00+0000',
                 'reactions': {'summary': {'total_count': 4}},
                 'comments': {'summary': {'total_count': 2}}, 'shares': {'count': 3}}]},
        })
        fake.scopes = ['pages_show_list', 'pages_read_engagement']
        result = MetaReportingReader(fake).content('1234', '2026-09-01', '2026-09-02')
        self.assertEqual(result['totals']['posts_published'], 1.0)
        self.assertIsNone(result['daily'][0]['engagements'])
        self.assertEqual(result['entries'][0]['reactions_lifetime'], 4)
        self.assertEqual(result['entries'][0]['comments_lifetime'], 2)
        self.assertEqual(result['entries'][0]['shares_lifetime'], 3)
        self.assertIsNone(result['totals']['engagements'])
        self.assertEqual(result['daily'][1]['posts_published'], 0)
        self.assertNotIn('page-secret', str(result))

    def test_empty_ads_are_no_data_not_fake_performance(self):
        fake = FakeMeta({
            ('act_123/insights', 'account', None): {'data': []},
            ('act_123/insights', 'campaign', None): {'data': []},
        })
        result = MetaReportingReader(fake).ads('act_123', '2026-09-01', '2026-09-02')
        self.assertEqual(result['status'], 'no_data')
        self.assertIsNone(result['latest_available_date'])
        self.assertTrue(all(result['totals'][key] is None for key in (
            'spend', 'spend_decimal', 'impressions', 'clicks', 'link_clicks', 'ctr',
            'cpc', 'cpm', 'leads', 'results', 'cost_per_result', 'reach', 'frequency',
            'purchases', 'roas')))
        self.assertEqual(result['daily'], [])
        self.assertEqual(result['entries'], [])
        self.assertTrue(all(metric['status'] == 'no_data' and metric['value'] is None
                            and metric['verified'] is False and metric['publishable'] is False
                            for metric in contract_metrics(result)))

    def test_http_200_with_empty_insights_data_is_successful_no_data(self):
        meta = Meta.__new__(Meta)
        meta.config = {'META_GRAPH_VERSION': 'v26.0', 'META_APP_ID': 'fixture-app'}
        meta.info = lambda: {'connected': True}
        meta.read = lambda: {'access_token': 'fixture-user-token', 'scopes': ['ads_read']}
        calls = []

        def response(method, url, **kwargs):
            calls.append((method, url, kwargs))
            if url.endswith('/act_123'):
                body = {'id': 'act_123', 'currency': 'VND', 'timezone_name': 'Asia/Ho_Chi_Minh'}
            elif url.endswith('/act_123/insights'):
                body = {'data': []}
            else:
                raise AssertionError('Unexpected offline Meta endpoint')
            return SimpleNamespace(status_code=200, json=lambda: body)

        with patch('kdh.meta.requests.request', side_effect=response):
            result = MetaReportingReader(meta).ads('act_123', '2026-09-01', '2026-09-02')

        self.assertEqual(result['status'], 'no_data')
        self.assertTrue(all(metric['status'] == 'no_data' and metric['value'] is None
                            for metric in contract_metrics(result)))
        insight_calls = [call for call in calls if call[1].endswith('/act_123/insights')]
        self.assertEqual(len(insight_calls), 2)
        self.assertTrue(all(call[2]['params']['level'] in ('account', 'campaign') for call in insight_calls))

    def test_empty_ads_requires_a_valid_data_list(self):
        for body in ({}, {'data': None}, {'data': {}}, {'data': 'private'}):
            fake = FakeMeta({('act_123/insights', 'account', None): body})
            with self.subTest(body=body), self.assertRaises(Problem) as caught:
                MetaReportingReader(fake).ads('act_123', '2026-09-01', '2026-09-02')
            self.assertEqual(caught.exception.code, 'meta_bad_response')
            self.assertNotEqual(caught.exception.code, 'no_data')

    def test_ads_permission_and_transport_errors_do_not_become_empty_results(self):
        failures = (
            MetaRequestError(http_status=403, graph_error={'code': 10, 'error_subcode': 33}),
            MetaRequestError(failure_layer='transport'),
        )
        for failure in failures:
            fake = FakeMeta({})
            original = fake.call

            def fail_insights(method, path, *, token, params):
                if path == 'act_123/insights':
                    fake.calls.append((method, path, token, dict(params)))
                    raise failure
                return original(method, path, token=token, params=params)

            with self.subTest(failure=failure.failure_layer), \
                    patch.object(fake, 'call', side_effect=fail_insights), \
                    patch('kdh.meta_reporting.time.sleep'), \
                    self.assertRaises(MetaRequestError) as caught:
                MetaReportingReader(fake).ads('act_123', '2026-09-01', '2026-09-02')

            self.assertEqual(caught.exception.failure_layer, failure.failure_layer)
            self.assertTrue(any(call[1] == 'act_123/insights' for call in fake.calls))
            self.assertNotIn('test-user-token', str(caught.exception))

    def test_missing_page_token_blocks_content(self):
        fake = FakeMeta({('me/accounts', None, None): {'data': [{'id': '1234'}]}})
        with self.assertRaises(Problem):
            MetaReportingReader(fake).content('1234', '2026-09-01', '2026-09-02')

    def test_broken_meta_pagination_fails_closed(self):
        fake = FakeMeta({
            ('me/adaccounts', None, None): {'data': [], 'paging': {'next': 'https://host/next'}},
        })
        with self.assertRaises(Problem):
            MetaReportingReader(fake).discover()

    def test_range_validation(self):
        with self.assertRaises(Problem):
            validate_range('2026-09-02', '2026-09-01')
        with self.assertRaises(Problem):
            validate_range('2025-01-01', '2026-09-01')


class ContentContractTests(unittest.TestCase):
    def read(self, posts):
        fake = FakeMeta({
            ('me/accounts', None, None): {'data': [{'id': '1234', 'access_token': 'page-secret'}]},
            ('1234/posts', None, None): posts,
        })
        fake.scopes = ['pages_show_list', 'pages_read_engagement']
        result = MetaReportingReader(fake).content('1234', '2026-09-01', '2026-09-02')
        self.assertEqual([call[1] for call in fake.calls], ['me/accounts', '1234/posts'])
        self.assertEqual(fake.calls[-1][2], 'page-secret')
        return result

    def test_empty_response_is_distinct_from_missing_data(self):
        result = self.read({'data': []})
        self.assertEqual(result['status'], 'no_data')
        self.assertEqual(result['totals']['posts_published'], 0)
        self.assertEqual(result['latest_available_date'], '2026-09-02')
        self.assertIsNone(result['latest_post_date'])
        self.assertEqual(result['entries'], [])
        self.assertTrue(all(row['posts_published'] == 0 for row in result['daily']))
        for body in ({}, {'data': None}, {'data': {}}, {'data': 'private'}):
            with self.subTest(body=body):
                with self.assertRaises(Problem) as caught:
                    self.read(body)
                self.assertEqual(caught.exception.code, 'meta_bad_response')

    def test_missing_optional_counters_remain_unknown(self):
        result = self.read({'data': [{'id': '1234_1', 'created_time': '2026-09-01T03:00:00+0000'}]})
        self.assertEqual(result['totals']['posts_published'], 1)
        for key in ('reactions_lifetime', 'comments_lifetime', 'shares_lifetime'):
            self.assertIsNone(result['entries'][0][key])
        self.assertIsNone(result['totals']['engagements'])

    def test_malformed_counters_fail_with_safe_data_error(self):
        invalid = [('reactions', {'summary': 'private'}), ('comments', {'summary': []}),
                   ('reactions', []), ('shares', 'private'), ('shares', {'count': -1}),
                   ('shares', {'count': True}), ('reactions', {'summary': {'total_count': 1.5}})]
        for field, value in invalid:
            with self.subTest(field=field, value=value):
                with self.assertRaises(Problem) as caught:
                    self.read({'data': [{'id': '1234_1', 'created_time': '2026-09-01T03:00:00+0000', field: value}]})
                self.assertEqual(caught.exception.code, 'meta_bad_response')
                self.assertNotIn('private', str(caught.exception))

    def test_malformed_required_post_fields_cannot_become_successful_zero(self):
        for row in ('private', {}, {'id': ''}, {'id': '1234_1'},
                    {'id': '1234_1', 'created_time': '2026-09-01INVALID'},
                    {'id': '1234_1', 'created_time': '2026-09-01T12:00:00'}):
            with self.subTest(row=row), self.assertRaises(Problem):
                self.read({'data': [row]})

    def test_publication_day_is_normalized_to_request_timezone_utc(self):
        result = self.read({'data': [{'id': '1234_1', 'created_time': '2026-09-02T01:00:00+0700'}]})
        self.assertEqual(result['entries'][0]['date'], '2026-09-01')
        self.assertEqual(result['latest_available_date'], '2026-09-02')
        self.assertEqual(result['latest_post_date'], '2026-09-01')
        self.assertEqual(result['timezone'], 'UTC')

    def test_duplicate_posts_are_counted_once_but_conflicts_fail_closed(self):
        row = {'id': '1234_1', 'created_time': '2026-09-01T03:00:00+0000'}
        result = self.read({'data': [row, dict(row)]})
        self.assertEqual(result['totals']['posts_published'], 1)
        with self.assertRaises(Problem):
            self.read({'data': [row, dict(row, created_time='2026-09-02T03:00:00+0000')]})

    def test_page_selection_discovery_never_calls_adaccounts_even_with_ads_grant(self):
        fake = FakeMeta({('me/accounts', None, None): {'data': [{'id': '1234'}]}})
        result = MetaReportingReader(fake).discover(source='facebook_content')
        self.assertEqual(result['facebook_content'][0]['id'], '1234')
        self.assertEqual([call[1] for call in fake.calls], ['me/accounts'])

    def test_malformed_paging_cannot_be_treated_as_complete_empty_response(self):
        for paging in ('private', [], {'cursors': []}, {'next': 'private'}):
            with self.subTest(paging=paging), self.assertRaises(Problem):
                self.read({'data': [], 'paging': paging})

    def test_page_token_and_posts_pagination_use_expected_tokens_and_cursors(self):
        row = {'id': '1234_1', 'created_time': '2026-09-01T03:00:00+0000'}
        fake = FakeMeta({
            ('me/accounts', None, None): {'data': [], 'paging': {'next': 'https://untrusted.invalid', 'cursors': {'after': 'pages2'}}},
            ('me/accounts', None, 'pages2'): {'data': [{'id': '1234', 'access_token': 'page-secret'}]},
            ('1234/posts', None, None): {'data': [row], 'paging': {'next': 'https://untrusted.invalid', 'cursors': {'after': 'posts2'}}},
            ('1234/posts', None, 'posts2'): {'data': [row, dict(row, id='1234_2')]},
        })
        fake.scopes = ['pages_show_list', 'pages_read_engagement']
        result = MetaReportingReader(fake).content('1234', '2026-09-01', '2026-09-02')
        self.assertEqual(result['totals']['posts_published'], 2)
        self.assertEqual([c[2] for c in fake.calls], ['test-user-token'] * 2 + ['page-secret'] * 2)
        self.assertEqual([c[1] for c in fake.calls], ['me/accounts'] * 2 + ['1234/posts'] * 2)

    def test_api_failure_on_later_page_never_returns_partial_success(self):
        from kdh.google import SourceError
        fake = FakeMeta({
            ('me/accounts', None, None): {'data': [{'id': '1234', 'access_token': 'page-secret'}]},
            ('1234/posts', None, None): {'data': [{'id': '1234_1', 'created_time': '2026-09-01T03:00:00+0000'}],
                'paging': {'next': 'https://untrusted.invalid', 'cursors': {'after': 'posts2'}}},
        })
        original = fake.call
        def call(method, path, **kwargs):
            if kwargs['params'].get('after') == 'posts2':
                raise SourceError('meta_oauth_error', 'Mock API unavailable')
            return original(method, path, **kwargs)
        with patch.object(fake, 'call', side_effect=call), patch('kdh.meta_reporting.time.sleep'), self.assertRaises(SourceError):
            MetaReportingReader(fake).content('1234', '2026-09-01', '2026-09-02')


if __name__ == '__main__':
    unittest.main()
