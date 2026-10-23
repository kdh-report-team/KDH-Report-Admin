"""Offline Insights contracts. All provider responses below are test fixtures."""
import copy
import unittest
from unittest.mock import patch

from kdh.core import Problem
from kdh.meta_content_insights import collect, normalize, project, CATALOG
from kdh.meta_reporting import MetaReportingReader
from kdh.meta_diagnostics import MetaRequestError
from test_meta_reporting import FakeMeta


def response(metric, object_id='1234', values=None):
    period = CATALOG[metric][1]
    values = values if values is not None else ([{'value': 0}] if period == 'lifetime' else
        [{'value': 0, 'end_time': '2026-09-02T00:00:00+00:00'},
         {'value': 3, 'end_time': '2026-09-03T00:00:00+00:00'}])
    return {'data': [{'name': metric, 'id': f'{object_id}/insights/{metric}/{period}',
                     'period': period, 'values': values}]}


def fixture():
    meta = FakeMeta({})
    meta.config = {'META_GRAPH_VERSION': 'v26.0'}
    meta.scopes += ['read_insights']
    reader = MetaReportingReader(meta)
    reader.page_tasks['1234'] = ['ANALYZE']
    return meta, reader


def collected(reader):
    return collect(reader, '1234', 'fixture-only', [{'post_id': '1234_1'}], '2026-09-01', '2026-09-02')


class ContentInsightsTests(unittest.TestCase):
    def test_content_hard_cap_includes_lookup_and_stops_before_provider(self):
        meta, reader = fixture()
        reader.requests_used = 100
        with self.assertRaises(Problem) as error:
            reader.content('1234', '2026-09-01', '2026-09-02')
        self.assertEqual(error.exception.code, 'meta_request_budget')
        self.assertEqual(reader.request_budget, 100)
        self.assertEqual(reader.requests_used, 100)

    def test_partial_daily_values_remain_in_chart_without_false_total(self):
        meta, reader = fixture()
        with patch.object(reader, '_insight_rows', side_effect=lambda path, token, params:
                          response(params['metric'], path.split('/')[0])['data']):
            raw = collected(reader)
        row = raw['measurements'][0]
        row.update(status='partial', values=[{'value': 0, 'end_time': '2026-09-02T00:00:00+00:00'},
                                           {'value': None, 'end_time': '2026-09-03T00:00:00+00:00'}])
        projected = project(raw)
        self.assertIsNone(projected['measurements'][0]['value'])
        self.assertEqual(projected['charts'][0]['values'], [0, None])
        self.assertEqual(projected['charts'][0]['status'], 'partial')

    def test_basic_posts_survive_missing_insights_permission_and_keep_real_zero(self):
        from test_facebook_content_report import source_fixture
        data = source_fixture()
        self.assertEqual(data['totals']['posts_published'], 2)
        self.assertEqual(data['entries'][0]['reactions_lifetime'], 0)
        self.assertEqual(data['insights']['status'], 'permission_denied')
        self.assertTrue(all(not m['values'] for m in data['insights']['measurements']))

    def test_permission_task_and_version_gates_never_call_provider(self):
        for gate in ('permission', 'task', 'version'):
            meta, reader = fixture()
            if gate == 'permission': meta.scopes.remove('read_insights')
            if gate == 'task': reader.page_tasks.clear()
            if gate == 'version': meta.config['META_GRAPH_VERSION'] = 'v99.0'
            with patch.object(meta, 'call') as call:
                self.assertNotEqual(collected(reader)['status'], 'available')
                call.assert_not_called()

    def test_zero_exact_daily_totals_and_non_additive_values(self):
        meta, reader = fixture()
        with patch.object(meta, 'call', side_effect=lambda method, path, **kw: response(kw['params']['metric'], path.split('/')[0])):
            raw = collected(reader)
        original = copy.deepcopy(raw)
        result = project(raw)
        by = {m['metric']: m for m in result['measurements']}
        self.assertEqual(by['page_media_view']['value'], 3)
        self.assertEqual(by['post_media_view']['value'], 0)
        for key in ('page_follows', 'page_total_media_view_unique'):
            self.assertIsNone(by[key]['value'])
        self.assertEqual(by['page_media_view']['coverage'], {'available': 2, 'expected': 2, 'unit': 'days'})
        self.assertEqual(len(result['charts']), 4)
        self.assertEqual(raw, original)
        for forbidden in ('access_token', 'fixture-only', 'paging'):
            self.assertNotIn(forbidden, str(raw))

    def test_provider_day_not_relabelled_as_utc_and_partial_not_zero(self):
        meta, reader = fixture()
        with patch.object(meta, 'call', side_effect=lambda method, path, **kw: response(kw['params']['metric'], path.split('/')[0],
                [{'value': 4, 'end_time': '2026-09-02T07:00:00+0000'}] if kw['params']['period'] == 'day' else [{'value': None}])):
            result = project(collected(reader))
        self.assertTrue(all(m['value'] is None for m in result['measurements']))
        self.assertEqual(result['measurements'][0]['report_status'], 'period_boundary_mismatch')
        self.assertEqual(result['measurements'][-1]['status'], 'partial')

    def test_failure_classes_and_no_retry_on_permanent_errors(self):
        for error, status, calls in (
            (MetaRequestError(graph_error={'code': 190}), 'invalid_token', 1),
            (MetaRequestError(graph_error={'code': 200}), 'permission_denied', 1),
            (MetaRequestError(graph_error={'code': 100}), 'invalid_metric_or_parameter', 6),
            (MetaRequestError(failure_layer='response_decode'), 'invalid_response', 6),
            (MetaRequestError(failure_layer='transport'), 'transport_error', 18)):
            meta, reader = fixture()
            with self.subTest(status=status), patch.object(meta, 'call', side_effect=error) as call, patch('kdh.meta_reporting.time.sleep'):
                raw = collected(reader)
                self.assertEqual(raw['measurements'][0]['status'], status)
                self.assertEqual(call.call_count, calls)

    def test_one_metric_failure_does_not_erase_other_metrics(self):
        meta, reader = fixture()
        def fake(method, path, **kw):
            metric = kw['params']['metric']
            if metric == 'page_media_view': raise MetaRequestError(graph_error={'code': 100})
            return response(metric, path.split('/')[0])
        with patch.object(meta, 'call', side_effect=fake): raw = collected(reader)
        self.assertEqual(raw['status'], 'partial')
        self.assertEqual(raw['measurements'][1]['status'], 'available')

    def test_empty_is_ambiguous_not_no_data_or_zero(self):
        meta, reader = fixture()
        with patch.object(meta, 'call', return_value={'data': []}): raw = collected(reader)
        self.assertTrue(all(m['status'] == 'empty_unconfirmed' and not m['values'] for m in raw['measurements']))

    def test_budget_counts_retries_and_pagination_and_does_not_follow_urls(self):
        meta, reader = fixture(); reader.request_budget = 2
        with patch.object(meta, 'call', side_effect=MetaRequestError(http_status=503)) as call, patch('kdh.meta_reporting.time.sleep'):
            raw = collected(reader)
        self.assertEqual(call.call_count, 2)
        self.assertEqual(raw['measurements'][0]['status'], 'budget_exhausted')
        meta, reader = fixture()
        one = response('page_media_view'); one['paging'] = {'next': 'https://evil/?access_token=secret'}
        with patch.object(meta, 'call', return_value=one) as call:
            self.assertEqual(len(reader._insight_rows('1234/insights', 'fixture', {'metric': 'page_media_view'})), 1)
            self.assertEqual(call.call_count, 1)
        one['paging']['cursors'] = {'after': 'repeat'}
        with patch.object(meta, 'call', return_value=one), self.assertRaises(Problem):
            reader._insight_rows('1234/insights', 'fixture', {'metric': 'page_media_view'})

    def test_strict_measurement_identity_null_and_duplicate_validation(self):
        good = response('page_media_view')['data']
        for patcher in (lambda r: r.update(name='other'), lambda r: r.update(period='lifetime'),
                        lambda r: r.update(id='9999/insights/page_media_view/day'),
                        lambda r: r.update(values=[{'value': True, 'end_time': '2026-09-02T00:00:00Z'}]),
                        lambda r: r.update(values=[{'value': 1, 'end_time': '2026-09-02'}]),
                        lambda r: r['values'].append({'value': 2, 'end_time': '2026-09-02T00:00:00Z'})):
            rows = copy.deepcopy(good); patcher(rows[0])
            with self.assertRaises(ValueError): normalize(rows, 'page_media_view', '1234')

    def test_diagnostic_rejects_scope_and_missing_permission_before_provider(self):
        meta, reader = fixture(); meta.scopes.remove('read_insights')
        with patch.object(meta, 'call') as call:
            for ids, end in ((['9999_1'], '2026-09-02'), (['1234_1'] * 4, '2026-09-02'), ([], '2026-09-05'), ([], '2026-09-02')):
                with self.assertRaises(Problem): reader.content_insights_diagnostic('1234', ids, '2026-09-01', end)
            call.assert_not_called()

    def test_diagnostic_20_request_cap_includes_page_lookup(self):
        meta, reader = fixture()
        def fake(method, path, **kw):
            if path == 'me/accounts':
                return {'data': [{'id': '1234', 'tasks': ['ANALYZE'], 'access_token': 'fixture'}]}
            raise MetaRequestError(http_status=503)
        with patch.object(meta, 'call', side_effect=fake) as call, patch('kdh.meta_reporting.time.sleep'):
            raw = reader.content_insights_diagnostic('1234', ['1234_1', '1234_2', '1234_3'], '2026-09-01', '2026-09-02')
        self.assertEqual(call.call_count, 20)
        self.assertEqual(raw['status'], 'partial')
        self.assertEqual(raw['requests_used'], 20)

    def test_post_limit_is_explicit_partial_and_projection_freezes_values(self):
        meta, reader = fixture()
        with patch.object(meta, 'call', side_effect=lambda method, path, **kw: response(kw['params']['metric'], path.split('/')[0])):
            raw = collect(reader, '1234', 'fixture', [{'post_id': f'1234_{i}'} for i in range(4)], '2026-09-01', '2026-09-02', max_posts=3)
        self.assertEqual(raw['post_coverage'], {'selected': 3, 'expected': 4})
        self.assertEqual(raw['status'], 'partial')

    def test_scope_guard_and_bad_pagination_do_not_become_empty_success(self):
        meta, reader = fixture()
        with patch.object(meta, 'call') as call, self.assertRaises(Problem):
            collect(reader, '1234', 'fixture', [{'post_id': '9999_1'}], '2026-09-01', '2026-09-02')
        call.assert_not_called()
        with patch.object(reader, '_insight_rows', side_effect=Problem('fixture', 502, 'meta_bad_paging')):
            raw = collected(reader)
        self.assertEqual(raw['measurements'][0]['status'], 'pagination_incomplete')
