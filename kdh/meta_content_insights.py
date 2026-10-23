"""Optional, bounded Page/Post Insights. No Ads, OAuth mutation or publication.

Catalog checked against Meta's v26 reference on 2026-10-21. Daily values retain
provider end_time; they are NOT assigned to UTC reporting days by date slicing.
"""
from datetime import datetime, time, timedelta, timezone, date
import copy
import re

from .core import Problem, now
from .meta_diagnostics import MetaRequestError

VERSION = 'meta-content-insights-v1'
CATALOG = {
    'page_media_view': ('page', 'day', 'Lượt xem nội dung Page', 'sum_exact_intervals'),
    'page_total_media_view_unique': ('page', 'day', 'Người xem duy nhất mỗi ngày', 'non_additive'),
    'page_post_engagements': ('page', 'day', 'Tương tác bài viết trên Page', 'sum_exact_intervals'),
    'page_follows': ('page', 'day', 'Tổng người theo dõi tại cuối ngày', 'stock_non_additive'),
    'post_media_view': ('post', 'lifetime', 'Lượt xem bài tích lũy', 'per_post_snapshot'),
    'post_total_media_view_unique': ('post', 'lifetime', 'Người xem bài duy nhất tích lũy', 'non_additive'),
}
REASONS = {
    'permission_denied': 'Chưa có quyền read_insights và pages_read_engagement.',
    'task_missing': 'Chưa xác nhận Page task ANALYZE.',
    'version_unconfirmed': 'Danh mục Insights chưa được xác minh cho phiên bản Graph này.',
    'invalid_token': 'Meta từ chối token; cần kiểm tra kết nối.',
    'invalid_metric_or_parameter': 'Meta từ chối metric hoặc tham số (code 100); chưa đủ bằng chứng kết luận metric đã bị loại.',
    'transport_error': 'Lỗi kết nối hoặc lỗi tạm thời từ Meta.',
    'invalid_response': 'Dữ liệu Insights không đúng metric, phạm vi hoặc cấu trúc yêu cầu.',
    'empty_unconfirmed': 'Meta trả danh sách rỗng; chưa xác định do ngưỡng Page, độ trễ, quyền hay không có số liệu.',
    'budget_exhausted': 'Đã hết ngân sách request; chưa đọc đủ Insights.',
    'pagination_incomplete': 'Chưa đọc đủ phân trang trong phạm vi yêu cầu.',
    'period_boundary_mismatch': 'Ranh giới ngày Insights không khớp kỳ UTC; giữ số đo gốc, chưa công bố tổng kỳ.',
    'partial': 'Thiếu một phần số đo; không thay bằng 0.',
    'available': '',
}


def failure(exc):
    if isinstance(exc, MetaRequestError):
        if exc.graph_code in (102, 190):
            return 'invalid_token'
        if exc.http_status in (401, 403) or exc.graph_code in (10, 200):
            return 'permission_denied'
        if exc.graph_code == 100:
            return 'invalid_metric_or_parameter'
        if exc.failure_layer == 'response_decode':
            return 'invalid_response'
        return 'transport_error'
    if isinstance(exc, Problem):
        if exc.code == 'meta_request_budget':
            return 'budget_exhausted'
        if exc.code in ('meta_bad_paging', 'meta_pagination_limit'):
            return 'pagination_incomplete'
        return 'invalid_response'
    raise exc


def stamp(value):
    if not isinstance(value, str):
        raise ValueError()
    result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if result.tzinfo is None:
        raise ValueError()
    return result


def normalize(rows, metric, object_id):
    """Allowlist fields; provider URLs, titles and error text never leave reader."""
    period = CATALOG[metric][1]
    points = {}
    for row in rows:
        if (not isinstance(row, dict) or row.get('name') != metric or row.get('period') != period
                or row.get('id') != f'{object_id}/insights/{metric}/{period}'
                or not isinstance(row.get('values'), list)):
            raise ValueError()
        if len(row['values']) > (90 if period == 'day' else 1):
            raise ValueError()
        for point in row['values']:
            if not isinstance(point, dict):
                raise ValueError()
            value = point.get('value')
            if value is not None and (type(value) is not int or value < 0):
                raise ValueError()
            end = point.get('end_time')
            if period == 'day' or end is not None:
                end = stamp(end).isoformat()
            identity = stamp(end).astimezone(timezone.utc).isoformat() if end is not None else None
            if identity in points and points[identity]['value'] != value:
                raise ValueError()
            points[identity] = {'value': value, 'end_time': end}
    if period == 'lifetime' and len(points) > 1:
        raise ValueError()
    return sorted(points.values(), key=lambda p: p['end_time'] or '')


def collect(reader, page_id, token, entries, start, end, *, max_posts=30):
    """Called only by an explicit sync/diagnostic reader, never by preview."""
    if (not isinstance(page_id, str) or not re.fullmatch(r'\d+', page_id)
            or type(max_posts) is not int or not 0 <= max_posts <= 30
            or any(not isinstance(r, dict) or not isinstance(r.get('post_id'), str)
                   or not re.fullmatch(re.escape(page_id) + r'_\d+', r['post_id']) for r in entries)):
        raise Problem('Insights asset scope mismatch.', 403, 'meta_asset_not_permitted')
    scopes = (reader.meta.read() or {}).get('scopes') or []
    version = getattr(reader.meta, 'config', {}).get('META_GRAPH_VERSION')
    gate = ('permission_denied' if not {'read_insights', 'pages_read_engagement'}.issubset(scopes)
            else 'version_unconfirmed' if version != 'v26.0'
            else 'task_missing' if 'ANALYZE' not in reader.page_tasks.get(page_id, []) else None)
    result = {'schema_version': VERSION, 'page_id': page_id, 'graph_version': version,
              'requested_period': {'start': start, 'end': end}, 'report_timezone': 'UTC',
              'measurement_timezone': 'provider_end_time', 'fetched_at': now(),
              'permissions': sorted(set(scopes)), 'page_tasks': reader.page_tasks.get(page_id, []),
              'post_coverage': {'selected': min(len(entries), max_posts), 'expected': len(entries)},
              'measurements': [], 'status': gate or 'available'}
    targets = [(page_id, key) for key, spec in CATALOG.items() if spec[0] == 'page']
    targets += [(r['post_id'], key) for r in entries[:max_posts]
                for key, spec in CATALOG.items() if spec[0] == 'post']
    stop = gate
    for object_id, key in targets:
        scope, period, label, aggregation = CATALOG[key]
        record = {'metric': key, 'object_id': object_id, 'scope': scope, 'period': period,
                  'unit': 'count', 'label': label, 'aggregation': aggregation,
                  'status': stop or 'available', 'values': [], 'fetched_at': now()}
        if not stop:
            params = {'metric': key, 'period': period}
            if period == 'day':
                params.update(since=start, until=(date.fromisoformat(end) + timedelta(days=1)).isoformat())
            try:
                # Each metric has an independent request/failure boundary.
                rows = reader._insight_rows(object_id + '/insights', token, params)
                record['values'] = normalize(rows, key, object_id)
                if not record['values']:
                    record['status'] = 'empty_unconfirmed'
                elif any(p['value'] is None for p in record['values']):
                    record['status'] = 'partial'
            except (MetaRequestError, Problem) as exc:
                record['status'] = failure(exc)
            except (ValueError, TypeError, OverflowError):
                record['status'] = 'invalid_response'
            if record['status'] in ('invalid_token', 'permission_denied', 'budget_exhausted'):
                stop = record['status']
        record['reason'] = REASONS[record['status']]
        result['measurements'].append(record)
    if not gate and (len(entries) > max_posts or any(r['status'] != 'available' for r in result['measurements'])):
        result['status'] = 'partial'
    result['requests_used'] = reader.requests_used
    return result


def project(raw):
    """Admin-only aggregation; exact UTC intervals required for period totals."""
    if not isinstance(raw, dict) or raw.get('schema_version') != VERSION:
        return {}
    result = copy.deepcopy(raw)
    result['charts'] = []
    first = datetime.combine(date.fromisoformat(raw['requested_period']['start']), time.min, timezone.utc)
    last = datetime.combine(date.fromisoformat(raw['requested_period']['end']) + timedelta(days=1), time.min, timezone.utc)
    days = (last - first).days
    expected = {first + timedelta(days=i + 1) for i in range(days)}
    for row in result['measurements']:
        row['value'] = None
        row['coverage'] = {'available': sum(p['value'] is not None for p in row['values']),
                           'expected': days if row['period'] == 'day' else 1,
                           'unit': 'days' if row['period'] == 'day' else 'observations'}
        row['report_status'] = row['status']
        if row['status'] not in ('available', 'partial'):
            continue
        if row['period'] == 'lifetime' and row['status'] == 'available':
            row['value'] = row['values'][0]['value']
        elif row['aggregation'] == 'sum_exact_intervals' and row['status'] == 'available':
            ends = {stamp(p['end_time']).astimezone(timezone.utc) for p in row['values']}
            if ends == expected:
                row['value'] = sum(p['value'] for p in row['values'])
            else:
                row['report_status'] = 'period_boundary_mismatch'
                row['reason'] = REASONS['period_boundary_mismatch']
        # Unique counts and follower stocks remain a series, never summed.
        if row['period'] == 'day' and row['values']:
            result['charts'].append({'title': row['label'] + ' · mốc kết thúc ngày Meta',
                'source': 'Facebook Page Insights', 'status': row['status'], 'kind': 'bar',
                'unit': 'count', 'integer_axis': True, 'timezone': 'provider_end_time',
                'labels': [p['end_time'] for p in row['values']],
                'values': [p['value'] for p in row['values']]})
    return result
