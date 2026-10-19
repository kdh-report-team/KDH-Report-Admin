"""Read-only Meta Graph adapters for Facebook Ads and Page Content.

Requires an existing Meta user OAuth grant. Does not expose access tokens,
Page tokens, provider errors, or Meta's paging.next URLs to the browser.
New fetches carry server-only adapter receipts; verification and human approval
remain separate and are mandatory before Marketing publication.
"""

from __future__ import annotations

from contextlib import nullcontext
from datetime import date, datetime, time as dt_time, timezone, timedelta
from zoneinfo import ZoneInfo
import json
import math
import re
import time

from .core import Problem, pack

SOURCES = {
    'facebook_ads': ('facebook_ad_account', 'act_'),
    'facebook_content': ('facebook_page', ''),
}
MAX_PAGES = 30
MAX_ROWS = 15000


def _retryable_source_error(exc):
    from .google import SourceError
    if not isinstance(exc, SourceError):
        return False
    # Only structured, transient failures are retryable. A generic OAuth/API
    # error is not evidence of a temporary outage; preserve the original error.
    if exc.status not in ('meta_oauth_error', 'timeout'):
        return False
    if getattr(exc, 'failure_layer', None) == 'response_decode':
        return False
    if getattr(exc, 'http_status', None) in (401, 403) or getattr(exc, 'graph_code', None) in (10, 100, 102, 190, 200):
        return False
    return (exc.status == 'timeout'
            or getattr(exc, 'failure_layer', None) == 'transport'
            or getattr(exc, 'is_transient', None) is True
            or getattr(exc, 'http_status', None) in (429, 500, 502, 503, 504))


def safe_number(value, default=None):
    if isinstance(value, bool) or value is None:
        return default
    try:
        n = float(value)
    except (TypeError, ValueError, OverflowError):
        return default
    return n if math.isfinite(n) and n >= 0 else default


def count(value, default=None):
    n = safe_number(value, default)
    return int(n) if n is not None else None


def validate_range(start, end):
    if not isinstance(start, str) or not isinstance(end, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', start) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', end):
        raise Problem('Ngày phải có định dạng YYYY-MM-DD.')
    try:
        first, last = date.fromisoformat(start), date.fromisoformat(end)
    except ValueError:
        raise Problem('Ngày báo cáo không hợp lệ.') from None
    if first > last or (last - first).days > 89 or last >= datetime.now(ZoneInfo('Asia/Ho_Chi_Minh')).date():
        raise Problem('Đồng bộ tối đa 90 ngày, kết thúc không vượt quá hôm nay.')
    return first, last


def dates(first, last):
    for delta in range((last - first).days + 1):
        yield (first + timedelta(days=delta)).isoformat()


def _action_count(actions, names):
    if not isinstance(actions, list):
        return None
    values = {str(row.get('action_type')): safe_number(row.get('value')) for row in actions if isinstance(row, dict)}
    for name in names:
        if values.get(name) is not None:
            return count(values[name])
    return None


def _total(daily, key):
    values = [row[key] for row in daily if row.get(key) is not None]
    return round(sum(values), 5) if values and len(values) == len(daily) else None


class MetaReportingReader:
    def __init__(self, meta, diagnostics=None):
        self.meta = meta
        self.diagnostics = diagnostics

    def _phase(self, stage):
        return self.diagnostics.phase(stage) if self.diagnostics else nullcontext()

    def _credentials(self):
        if not self.meta.info()['connected']:
            raise Problem('Meta OAuth hết hạn hoặc chưa kết nối.', 409, 'meta_reconnect_required')
        token = self.meta.read() or {}
        if not isinstance(token.get('access_token'), str) or not token['access_token']:
            raise Problem('Meta không có Access Token hợp lệ.', 409, 'meta_reconnect_required')
        return token

    def _token(self):
        return self._credentials()['access_token']

    @staticmethod
    def _can_read_ads(credentials):
        scopes = credentials.get('scopes')
        return (isinstance(scopes, list) and all(isinstance(scope, str) for scope in scopes)
                and 'ads_read' in scopes)

    def require_ads_permission(self):
        credentials = self._credentials()
        if not self._can_read_ads(credentials):
            raise Problem('Meta chưa được cấp quyền ads_read. Không thể đồng bộ Facebook Ads; '
                          'Facebook Content vẫn có thể sử dụng quyền Page.', 403, 'meta_ads_permission')
        return credentials['access_token']

    def _page_rows(self, path, token, params):
        """Use cursor-based pagination only; never dereference untrusted next URL."""
        cursor = None
        seen = set()
        result = []
        for _ in range(MAX_PAGES):
            query = dict(params, limit=100)
            if cursor:
                query['after'] = cursor
            # Existing Meta.call supplies a bearer header and sanitizes API errors.
            # Do not include token in params, logs, or resulting data.
            for attempt in range(3):
                try:
                    payload = self.meta.call('GET', path, token=token, params=query)
                    break
                except Exception as exc:
                    if not _retryable_source_error(exc) or attempt == 2:
                        raise
                    time.sleep(attempt + 1)
            rows = payload.get('data') if isinstance(payload, dict) else None
            if not isinstance(rows, list):
                raise Problem('Meta trả về danh sách dữ liệu không hợp lệ.', 502, 'meta_bad_response')
            result.extend(rows)
            if len(result) > MAX_ROWS:
                raise Problem('Dữ liệu Meta quá lớn; hãy thu hẹp phạm vi đồng bộ.', 409, 'meta_too_many_rows')
            paging = payload.get('paging')
            paging = {} if paging is None else paging
            if not isinstance(paging, dict):
                raise Problem('Phân trang Meta không hợp lệ.', 502, 'meta_bad_paging')
            cursors = paging.get('cursors')
            cursors = {} if cursors is None else cursors
            if not isinstance(cursors, dict):
                raise Problem('Phân trang Meta không hợp lệ.', 502, 'meta_bad_paging')
            after = cursors.get('after') if paging.get('next') else None
            if paging.get('next') and not after:
                raise Problem('Meta thiếu con trỏ phân trang.', 502, 'meta_bad_paging')
            if not after:
                return result
            if not isinstance(after, str) or len(after) > 2048 or after == cursor or after in seen:
                raise Problem('Phân trang Meta không hợp lệ.', 502, 'meta_bad_paging')
            seen.add(after)
            cursor = after
        raise Problem('Đã đạt giới hạn số trang API Meta.', 409, 'meta_pagination_limit')

    def discover(self, source=None):
        if source is not None and source not in SOURCES:
            raise Problem('Nguồn Meta không hợp lệ.')
        credentials = self._credentials()
        token = credentials['access_token']
        accounts = []
        if source != 'facebook_content' and self._can_read_ads(credentials):
            accounts = self._page_rows('me/adaccounts', token, {
                'fields': 'id,name,account_status,currency,timezone_name',
            })
        pages = self._page_rows('me/accounts', token, {
            'fields': 'id,name,tasks,access_token',
        }) if source != 'facebook_ads' else []
        clean_ads = []
        for item in accounts:
            if isinstance(item, dict) and re.fullmatch(r'act_\d+', str(item.get('id', ''))):
                clean_ads.append({key: item.get(key) for key in ('id', 'name', 'account_status', 'currency', 'timezone_name')})
        clean_pages = []
        for item in pages:
            if isinstance(item, dict) and re.fullmatch(r'\d+', str(item.get('id', ''))):
                clean_pages.append({'id': item['id'], 'name': item.get('name', ''),
                                    'tasks': item.get('tasks') if isinstance(item.get('tasks'), list) else []})
        return {'facebook_ads': clean_ads, 'facebook_content': clean_pages}

    def _page_token(self, page_id):
        # Tokens for Pages remain in memory; only assets and metrics are persisted.
        pages = self._page_rows('me/accounts', self._token(), {'fields': 'id,name,tasks,access_token'})
        for item in pages:
            if isinstance(item, dict) and item.get('id') == page_id:
                token = item.get('access_token')
                if isinstance(token, str) and token:
                    return token
                break
        raise Problem('Meta chưa cấp Page Access Token cho Trang được chọn.', 403, 'meta_page_permission')

    def ads(self, external_id, start, end):
        first, last = validate_range(start, end)
        if not re.fullmatch(r'act_\d+', external_id):
            raise Problem('Ad Account ID không hợp lệ.')
        token = self.require_ads_permission()
        account = self.ad_account(external_id)
        from .meta_contract import ATTRIBUTION, normalize_ads, seal_result
        common = {'fields': 'account_id,account_currency,date_start,date_stop,spend,impressions,clicks,inline_link_clicks,reach,actions',
                  'time_range': json.dumps({'since': start, 'until': end}, separators=(',', ':')),
                  'time_increment': 1, 'action_report_time': ATTRIBUTION['action_report_time'],
                  'action_attribution_windows': json.dumps(ATTRIBUTION['action_attribution_windows']),
                  'use_account_attribution_setting': 'false', 'use_unified_attribution_setting': 'false'}
        rows = self._page_rows(external_id + '/insights', token, dict(common, level='account'))
        campaigns = self._page_rows(external_id + '/insights', token,
            dict(common, level='campaign', fields=common['fields'] + ',campaign_id,campaign_name'))
        return seal_result(self.meta, normalize_ads(rows, campaigns, account, start, end), external_id, account)

    def ad_account(self, external_id):
        if not isinstance(external_id, str) or not re.fullmatch(r'act_\d+', external_id):
            raise Problem('Ad Account ID không hợp lệ.')
        account = self.meta.call('GET', external_id, token=self.require_ads_permission(),
                                 params={'fields': 'id,name,currency,timezone_name,business,account_status'})
        if not isinstance(account, dict) or account.get('id') != external_id:
            raise Problem('Ad Account identity mismatch.', 403, 'meta_asset_not_permitted')
        return {key: account.get(key) for key in ('id', 'name', 'currency', 'timezone_name', 'business', 'account_status')}
    def content(self, page_id, start, end):
        with self._phase('page_token'):
            first, last = validate_range(start, end)
            if last >= datetime.now(timezone.utc).date():
                raise Problem('UTC reporting day has not ended.', 409, 'meta_open_day')
            if not re.fullmatch(r'\d+', page_id):
                raise Problem('Page ID không hợp lệ.')
            token = self._page_token(page_id)
        with self._phase('fetch_posts'):
            rows = self._page_rows(page_id + '/posts', token, {'fields':
                'id,created_time,permalink_url,shares,reactions.limit(0).summary(true),comments.limit(0).summary(true)',
                'since': str(int(datetime.combine(first, dt_time.min, tzinfo=timezone.utc).timestamp())),
                'until': str(int(datetime.combine(last + timedelta(days=1), dt_time.min, tzinfo=timezone.utc).timestamp()))})
        with self._phase('normalize_content'):
            if any(not isinstance(row, dict) or not str(row.get('id', '')).startswith(page_id + '_') for row in rows):
                raise Problem('Post does not belong to the selected Page.', 502, 'meta_bad_response')
            from .meta_contract import seal_result
            return seal_result(self.meta, self._normalize_content(rows, first, last, start, end), page_id)

    def _normalize_content(self, rows, first, last, start, end):
        # Post counters are lifetime values as of fetch time, NOT daily engagement.
        # Only post publication counts can safely be attributed to creation day.
        grouped = {day: {'date': day, 'posts_published': 0,
                           'reactions': None, 'comments': None, 'shares': None,
                           'engagements': None} for day in dates(first, last)}
        entries, seen = [], {}
        for item in rows:
            if not isinstance(item, dict) or not isinstance(item.get('id'), str) or not item['id'].strip():
                raise Problem('Meta trả về bài viết không hợp lệ.', 502, 'meta_bad_response')
            post_id = item['id']
            try:
                created = datetime.fromisoformat(item['created_time'])
                if created.tzinfo is None:
                    raise ValueError()
                day = created.astimezone(timezone.utc).date().isoformat()
            except (KeyError, TypeError, ValueError, OverflowError):
                raise Problem('Meta trả về thời gian bài viết không hợp lệ.', 502, 'meta_bad_response') from None
            if not start <= day <= end:
                continue
            def post_count(name, summary=False):
                info = item.get(name)
                if info is None:
                    return None
                if not isinstance(info, dict):
                    raise Problem('Meta trả về bộ đếm bài viết không hợp lệ.', 502, 'meta_bad_response')
                if summary:
                    info = info.get('summary')
                    if info is None:
                        return None
                    if not isinstance(info, dict):
                        raise Problem('Meta trả về bộ đếm bài viết không hợp lệ.', 502, 'meta_bad_response')
                value = info.get('total_count' if summary else 'count')
                if value is not None and (type(value) is not int or value < 0):
                    raise Problem('Meta trả về bộ đếm bài viết không hợp lệ.', 502, 'meta_bad_response')
                return value
            entry = {'date': day, 'post_id': post_id,
                     'reactions_lifetime': post_count('reactions', summary=True),
                     'comments_lifetime': post_count('comments', summary=True),
                     'shares_lifetime': post_count('shares')}
            if post_id in seen:
                if entry != seen[post_id]:
                    raise Problem('Meta trả về bài viết trùng nhưng không nhất quán.', 502, 'meta_bad_response')
                continue
            seen[post_id] = entry
            entries.append(entry)
            grouped[day]['posts_published'] += 1
        daily = list(grouped.values())
        totals = {'posts_published': sum(row['posts_published'] for row in daily),
                  'reactions': None, 'comments': None, 'shares': None, 'engagements': None}

        return {'source': 'facebook_content', 'requested_start': start, 'requested_end': end,
            'status': 'ready' if entries else 'no_data', 'data_origin': 'meta_api_unverified',
            'timezone': 'UTC',
            # A fully fetched period has daily publication observations, including
            # zero-post days. Keep metric coverage separate from the last post day.
            'latest_available_date': end,
            'latest_post_date': max((row['date'] for row in entries), default=None),
            'daily': daily, 'entries': entries, 'totals': totals,
            'warnings': ['Tương tác trên từng post là lifetime tại thời điểm lấy; không cộng vào KPI tương tác theo ngày.',
                         'Page/Post views, reach và follower Insights chưa được truy vấn; không suy đoán các giá trị này.',
                         'Đồng bộ Meta thành công không tự thay thế xác minh nguồn và phê duyệt phát hành.']}
