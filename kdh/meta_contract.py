"""Meta snapshot semantics and adapter attestations; no provider calls or migrations.

Receipts are produced only by the authenticated reader after a complete fetch.
They attest the application's adapter path, not an independent audit by Meta.
"""
import copy
import json
import re
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, localcontext
from zoneinfo import ZoneInfo

from .core import Problem, digest, now, pack
from .marketing_provenance import AdapterResult, _claims, is_demo, seal, sha, unseal

SOURCES = {'facebook_content': 'facebook_page', 'facebook_ads': 'facebook_ad_account'}
READ_SCOPES = {
    'facebook_content': {'pages_show_list', 'pages_read_engagement', 'pages_read_user_content'},
    'facebook_ads': {'ads_read'},
}
ATTRIBUTION = {'action_report_time': 'impression', 'action_attribution_windows': ['7d_click', '1d_view'],
               'use_account_attribution_setting': False, 'use_unified_attribution_setting': False,
               'result_action_type': 'lead'}


def decimal_value(value):
    if value is None:
        return None
    try:
        if isinstance(value, bool):
            raise ValueError()
        result = Decimal(str(value))
        if not result.is_finite() or result < 0 or len(str(value)) > 60:
            raise ValueError()
        return result
    except (InvalidOperation, ValueError):
        raise Problem('Invalid Meta numeric value.', 502, 'meta_bad_response') from None


def integer(value):
    number = decimal_value(value)
    if number is not None and number != number.to_integral_value():
        raise Problem('Invalid Meta integer counter.', 502, 'meta_bad_response')
    return int(number) if number is not None else None


def ratio(numerator, denominator, scale=1):
    if numerator is None or denominator is None or denominator == 0:
        return None
    return float(Decimal(str(numerator)) * scale / Decimal(str(denominator)))


def normalize_ads(rows, campaigns, account, start, end):
    currency, tz = account.get('currency'), account.get('timezone_name')
    if not isinstance(currency, str) or not re.fullmatch('[A-Z]{3}', currency) or not isinstance(tz, str):
        raise Problem('Ad Account currency/timezone missing.', 502, 'meta_account_metadata')
    try:
        zone = ZoneInfo(tz)
    except (KeyError, ValueError):
        raise Problem('Ad Account timezone invalid.', 502, 'meta_account_metadata') from None
    if date.fromisoformat(end) >= datetime.now(zone).date():
        raise Problem('Ad Account reporting day has not ended.', 409, 'meta_open_day')
    expected = (date.fromisoformat(end) - date.fromisoformat(start)).days + 1
    def normalize(items, campaign=False):
        output, seen = [], {}
        for item in items:
            if not isinstance(item, dict):
                raise Problem('Invalid Insights row.', 502, 'meta_bad_response')
            day = item.get('date_start')
            if (not isinstance(day, str) or not start <= day <= end or item.get('date_stop', day) != day
                    or item.get('account_id', account['id'][4:]) != account['id'][4:]
                    or item.get('account_currency', currency) != currency):
                raise Problem('Insights account/currency/date mismatch.', 502, 'meta_bad_response')
            date.fromisoformat(day)
            amount = decimal_value(item.get('spend'))
            row = {'date': day, 'spend': float(amount) if amount is not None else None,
                   'spend_decimal': str(amount) if amount is not None else None,
                   'impressions': integer(item.get('impressions')), 'clicks': integer(item.get('clicks')),
                   'link_clicks': integer(item.get('inline_link_clicks')), 'reach': integer(item.get('reach'))}
            actions = item.get('actions')
            lead = None
            if actions is not None:
                if not isinstance(actions, list) or any(not isinstance(a, dict) for a in actions):
                    raise Problem('Invalid action rows.', 502, 'meta_bad_response')
                selected = [a for a in actions if a.get('action_type') == 'lead']
                if len(selected) > 1:
                    raise Problem('Duplicate action type.', 502, 'meta_bad_response')
                lead = float(decimal_value(selected[0].get('value'))) if selected and selected[0].get('value') is not None else None
            row.update(leads=lead, ctr=ratio(row['clicks'], row['impressions']),
                       cpc=ratio(amount, row['clicks']), cpm=ratio(amount, row['impressions'], 1000))
            key = day
            if campaign:
                cid = item.get('campaign_id')
                if not isinstance(cid, str) or not cid:
                    raise Problem('Missing campaign identity.', 502, 'meta_bad_response')
                row.update(campaign_id=cid, campaign_name=str(item.get('campaign_name') or '')[:180])
                key = (day, cid)
            if key in seen:
                # Never count duplicated API rows twice or accept conflicting values.
                if seen[key] != row:
                    raise Problem('Conflicting duplicate Insights.', 502, 'meta_bad_response')
                continue
            seen[key] = row
            output.append(row)
        return sorted(output, key=lambda r: (r['date'], r.get('campaign_id', '')))
    daily, entries = normalize(rows), normalize(campaigns, True)
    complete = len(daily) == expected
    totals = {}
    for key in ('impressions', 'clicks', 'link_clicks', 'leads'):
        totals[key] = sum(r[key] for r in daily) if complete and all(r[key] is not None for r in daily) else None
    amounts = [decimal_value(r['spend_decimal']) for r in daily]
    with localcontext() as context:
        context.prec = 80  # Preserve provider decimal precision through the period sum.
        amount = sum(amounts, Decimal(0)) if complete and all(v is not None for v in amounts) else None
    totals.update(spend=float(amount) if amount is not None else None,
                  spend_decimal=str(amount) if amount is not None else None, reach=None, frequency=None,
                  ctr=ratio(totals['clicks'], totals['impressions']), cpc=ratio(amount, totals['clicks']),
                  cpm=ratio(amount, totals['impressions'], 1000), results=totals['leads'],
                  cost_per_result=ratio(amount, totals['leads']), purchases=None, roas=None)
    ready = complete and all(totals[key] is not None for key in ('spend_decimal', 'impressions', 'clicks'))
    return {'source': 'facebook_ads', 'requested_start': start, 'requested_end': end,
            'status': 'ready' if ready else ('partial' if daily else 'no_data'),
            'data_origin': 'meta_api_unverified', 'timezone': tz, 'account_timezone': tz,
            'report_timezone': tz, 'currency': currency, 'attribution': copy.deepcopy(ATTRIBUTION),
            'latest_available_date': daily[-1]['date'] if daily else None,
            'daily': daily, 'entries': entries, 'totals': totals,
            'warnings': ['Reach/frequency period totals are unavailable; never sum daily unique counts.',
                         'Missing conversions remain null. Results means action_type=lead only.']}


def seal_result(meta, result, external_id, account=None):
    """Called at the reader boundary, never on an arbitrary persisted snapshot."""
    grant = meta.read() or {}
    config = getattr(meta, 'config', {})
    result = AdapterResult(copy.deepcopy(result))
    result.update(contract_version='meta-reporting-v1', fetched_at=now(),
                  identity={'client_id': getattr(meta, 'client_id', None), 'external_id': external_id,
                            'asset_type': SOURCES[result['source']], 'account': account},
                  provenance={'provider': 'meta', 'graph_version': config.get('META_GRAPH_VERSION'),
                              'app_id': grant.get('app_id'), 'account_id': grant.get('account_id'),
                              'grant_observed_at': now(), 'grant_connected_at': grant.get('connected_at'),
                              'permissions': sorted(set(grant.get('scopes') or [])),
                              'asset_access_confirmed': True, 'pagination_complete': True})
    # Test/legacy readers without a cipher can still ingest, but cannot attest.
    if getattr(meta, 'cipher', None):
        result.receipt = seal(meta.cipher, 'meta-adapter-v1', {'payload_sha256': sha(result)})
    return result


def daily_consistent(db, run, payload):
    expected = []
    content = payload['source'] == 'facebook_content'
    for detail, rows in ((False, payload['daily']), (True, payload['entries'])):
        for point in rows:
            entity = ('post' if content else 'campaign') if detail else ('page' if content else 'ad_account')
            identity = point.get('post_id' if content else 'campaign_id', '') if detail else ''
            measures = {k: v for k, v in point.items() if k not in ('date', 'campaign_id', 'campaign_name', 'post_id')}
            dimensions = {'campaign_name': point.get('campaign_name', '')} if detail and not content else {}
            expected.append(sha([run['client_id'], run['asset_id'], 'meta', entity, identity,
                                 point['date'], '', measures, dimensions, digest(pack(point))]))
    actual = [sha([r['client_id'], r['asset_id'], r['provider'], r['entity_type'], r['entity_id'],
                   r['metric_date'], r['dimension_key'], json.loads(r['metrics']), json.loads(r['dimensions']), r['source_hash']])
              for r in db.execute('SELECT * FROM daily_metrics WHERE sync_run_id=?', (run['id'],)).fetchall()]
    return sorted(expected) == sorted(actual)


def record_receipt(db, store, meta, sync_id, result):
    proof = unseal(getattr(meta, 'cipher', None), 'meta-adapter-v1', getattr(result, 'receipt', None))
    if not proof or proof.get('payload_sha256') != sha(result) or is_demo(result):
        return False
    run = db.execute('SELECT * FROM sync_runs WHERE id=?', (sync_id,)).fetchone()
    snap = db.execute('SELECT * FROM source_snapshots WHERE sync_run_id=?', (sync_id,)).fetchone()
    job = db.execute('SELECT kind,params FROM jobs WHERE id=?', (run['job_id'],)).fetchone()
    asset = db.execute('SELECT * FROM source_assets WHERE id=?', (run['asset_id'],)).fetchone()
    if (job['kind'] != 'meta_sync' or sha(json.loads(snap['payload'])) != sha(result)
            or result['identity']['external_id'] != asset['external_id']
            or result['identity']['client_id'] != run['client_id'] or not daily_consistent(db, run, result)):
        raise Problem('Meta receipt scope mismatch.', 409, 'meta_receipt_mismatch')
    claims = dict(_claims(run, snap), params=json.loads(job['params']), external_id=asset['external_id'],
                  snapshot_id=snap['id'], contract_version='meta-reporting-v1')
    db.execute('INSERT INTO source_attestations (sync_run_id,claims,seal,created_at) VALUES (?,?,?,?)',
               (sync_id, pack(claims), seal(store.report_cipher, 'source-attestation-v1', claims), now()))
    return True


def metrics(payload):
    """Qualified period/lifetime values; absent optional metrics remain explicit."""
    content = payload['source'] == 'facebook_content'
    total_days = (date.fromisoformat(payload['requested_end']) - date.fromisoformat(payload['requested_start'])).days + 1
    daily, entries, totals = payload['daily'], payload['entries'], payload['totals']
    specs = ([('posts_published', 'Bài đăng mới trong kỳ', 'count', 'sum', 'day'),
              ('engagements', 'Tương tác phát sinh trong kỳ', 'count', 'sum', 'day')]
             + [(k + '_lifetime', label + ' lifetime', 'count', 'sum_posts_at_fetch', 'snapshot')
                for k, label in [('reactions', 'Reactions'), ('comments', 'Comments'), ('shares', 'Shares')]]) if content else [
        ('spend', 'Chi phí', 'currency', 'decimal_sum', 'day'),
        ('impressions', 'Lượt hiển thị', 'count', 'sum', 'day'), ('clicks', 'Tất cả lượt nhấp', 'count', 'sum', 'day'),
        ('link_clicks', 'Lượt nhấp liên kết', 'count', 'sum', 'day'),
        ('ctr', 'CTR tất cả lượt nhấp', 'ratio', 'clicks/impressions', 'period'),
        ('cpc', 'CPC', 'currency', 'spend/clicks', 'period'), ('cpm', 'CPM', 'currency', '1000*spend/impressions', 'period'),
        ('reach', 'Tiếp cận duy nhất', 'count', 'non_additive', 'period'),
        ('frequency', 'Tần suất', 'number', 'non_additive', 'period'),
        ('leads', 'Lead (action_type=lead)', 'count', 'sum', 'day'),
        ('results', 'Kết quả (action_type=lead)', 'count', 'sum', 'day'),
        ('cost_per_result', 'Chi phí/Lead', 'currency', 'spend/lead', 'period'),
        ('purchases', 'Lượt mua', 'count', 'unsupported', 'period'), ('roas', 'ROAS', 'number', 'unsupported', 'period')]
    output = []
    for key, label, unit, aggregation, grain in specs:
        value = totals.get(key)
        available = sum(r.get(key) is not None for r in daily)
        coverage = {'available': available, 'expected': total_days, 'unit': 'days'}
        observed = None
        if grain == 'snapshot':
            values = [p[key] for p in entries if p.get(key) is not None]
            coverage = {'available': len(values), 'expected': len(entries), 'unit': 'posts'}
            observed = sum(values) if values else None
            value = observed if len(values) == len(entries) and entries else None
        if key == 'spend':
            value = totals.get('spend_decimal')  # JSON decimal string is authoritative.
        if grain == 'period' or key in ('results',):
            coverage['available'] = total_days if value is not None else 0
        partial = (grain == 'snapshot' and observed is not None) or (grain == 'day' and 0 < available < total_days)
        status = 'available' if value is not None else ('partial' if partial else 'no_data')
        output.append({'key': key, 'metric_id': payload['source'] + '.' + key, 'label': label, 'unit': unit,
                       'currency': payload.get('currency') if unit == 'currency' else None,
                       'value': value, 'status': status, 'coverage': coverage, 'observed_sum': observed,
                       'aggregation': aggregation, 'grain': grain, 'fetched_at': payload.get('fetched_at'),
                       'attribution': payload.get('attribution') if key in ('leads', 'results', 'cost_per_result') else None,
                       'provider': 'meta', 'verified': False, 'publishable': False})
    return output
