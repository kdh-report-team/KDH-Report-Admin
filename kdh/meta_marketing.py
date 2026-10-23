"""Source-specific Meta support inside the existing Marketing review lifecycle.

Reads persisted snapshots only. No OAuth, provider fetch, sync, approval or
publication is initiated here. v1 supports one explicit asset and one period.
"""
import copy
import hashlib
import json
from datetime import date, datetime, timedelta, timezone

from .core import Problem, now, pack
from .marketing_provenance import is_demo, sha, verify_adapter_receipt
from .meta_contract import SOURCES, READ_SCOPES, ATTRIBUTION, daily_consistent, metrics


def scoped_snapshot(store, client_id, source, asset_id, start, end):
    if not client_id or not asset_id or source not in SOURCES:
        raise Problem('Meta requires explicit client/source/asset.', 400, 'meta_scope_required')
    asset = store.one('''SELECT * FROM source_assets WHERE id=? AND client_id=?
        AND provider='meta' AND asset_type=? AND enabled=1''', (asset_id, client_id, SOURCES[source]))
    if not asset:
        raise Problem('Meta asset is outside the selected client/source.', 403, 'asset_scope_mismatch')
    run = store.one('''SELECT * FROM sync_runs WHERE client_id=? AND asset_id=? AND provider='meta'
        AND requested_start=? AND requested_end=? ORDER BY created_at DESC,id DESC LIMIT 1''',
        (client_id, asset_id, start, end))
    if not run or run['status'] != 'succeeded':
        raise Problem('An exact successful Meta period snapshot is required.', 409, 'meta_snapshot_missing')
    snap = store.one('SELECT * FROM source_snapshots WHERE sync_run_id=?', (run['id'],))
    if not snap:
        raise Problem('Meta source snapshot missing.', 409, 'meta_snapshot_missing')
    payload = json.loads(snap['payload'])
    if (snap['client_id'] != client_id or snap['asset_id'] != asset_id or snap['provider'] != 'meta'
            or snap['source_key'] != source or (snap['requested_start'], snap['requested_end']) != (start, end)
            or payload.get('source') != source
            or (payload.get('requested_start'), payload.get('requested_end')) != (start, end)):
        raise Problem('Meta snapshot scope mismatch.', 409, 'meta_snapshot_scope')
    return asset, run, snap, payload


def build_preview(store, *, client_id, source, asset_id, start, end, compare_start=None, compare_end=None,
                  content_report=True, content_editorial=None):
    if compare_start is not None or compare_end is not None:
        raise Problem('Meta v1 requires a single period; comparisons are not supported.', 409, 'meta_comparison_unsupported')
    days = (date.fromisoformat(end) - date.fromisoformat(start)).days + 1
    if not 1 <= days <= 90:
        raise Problem('Meta period must contain 1-90 days.')
    asset, run, snap, payload = scoped_snapshot(store, client_id, source, asset_id, start, end)
    if payload.get('contract_version') != 'meta-reporting-v1':
        raise Problem('Historical snapshot lacks the Meta reporting contract; no retroactive verification.', 409, 'meta_contract_missing')
    period = {'start': start, 'end': end}
    lineage = {'sync_run_ids': [run['id']], 'snapshot_id': snap['id'], 'snapshot_sha256': sha(payload)}
    widgets, evidence = [], []
    for metric in metrics(payload):
        item = dict(metric, type='kpi', source=source, asset_id=asset_id,
                    evidence_id=sha([snap['id'], metric['metric_id']]), comparison=None,
                    period=period, daily_observations=[], lineage=copy.deepcopy(lineage),
                    evidence_status='recorded_unverified' if metric['status'] == 'available' else 'not_ready')
        widgets.append(item)
        if metric['status'] == 'available':
            evidence.append(dict(item, status='recorded_unverified'))
    result = {'preview_schema_version': '0.1', 'kind': 'marketing_internal_preview', 'generated_at': now(),
            'client_id': client_id, 'source_filter': source, 'sources': [source], 'asset_id': asset_id,
            'period': period, 'comparison': None, 'widgets': widgets, 'evidence_cards': evidence,
            'opportunity_candidates': [], 'publishable': False, 'not_a_report_bundle': True,
            'meta_snapshot': dict(lineage, external_id=asset['external_id'], timezone=payload.get('timezone'),
                                  fetched_at=payload.get('fetched_at'), currency=payload.get('currency'),
                                  attribution=payload.get('attribution')),
            'quality': {'status': 'unverified_with_data' if evidence else 'no_eligible_data',
                        'independently_verified': False, 'ready_for_customer_claims': False},
            'summary': {'widget_count': len(widgets), 'widgets_with_values': len(evidence),
                        'evidence_count': len(evidence), 'opportunity_count': 0}}
    if source == 'facebook_content' and content_report:
        from .facebook_content_report import build_content_report
        result['content_report'] = build_content_report(payload, content_editorial)
    return result


def check_source(store, db, candidate, original, latest, assessment, issues):
    """Verify the immutable reviewed projection against an attested ingestion."""
    from .marketing_source_check import ReadView
    reader = ReadView(db)
    p = original['params']; source = p['source']; preview = original['marketing']['preview']
    issues = list(issues)
    try:
        asset, run, snap, payload = scoped_snapshot(reader, original['client_id'], source, preview['asset_id'], p['start'], p['end'])
    except Problem as exc:
        issues.append(exc.code or 'meta_snapshot_missing')
        asset = run = snap = payload = None
    witnesses = []
    if payload is not None:
        # Preserve the projection used by historical immutable previews.
        expected = build_preview(reader, client_id=original['client_id'], source=source, asset_id=asset['id'], start=p['start'], end=p['end'],
                                 content_report='content_report' in preview,
                                 content_editorial=preview.get('content_report', {}).get('editorial'))
        expected['generated_at'] = preview.get('generated_at')
        if sha(expected) != sha(preview):
            issues.append('meta_projection_changed_or_stale')
        identity = payload.get('identity', {}); proof = payload.get('provenance', {})
        if (identity.get('client_id') != original['client_id'] or identity.get('external_id') != asset['external_id']
                or identity.get('asset_type') != asset['asset_type']):
            issues.append('asset_scope_mismatch')
        if not reader.one('SELECT id FROM clients WHERE id=? AND active=1', (original['client_id'],)):
            issues.append('client_disabled')
        conn = reader.one('SELECT * FROM connections WHERE id=?', (run['connection_id'],))
        if (not conn or conn['client_id'] != original['client_id'] or conn['provider'] != 'meta'
                or conn['status'] != 'connected' or conn['id'] != asset['connection_id']
                or conn['external_account_id'] != proof.get('account_id')):
            issues.append('connection_scope_mismatch')
        # Grant is decrypted only in server memory, never included in evidence.
        try:
            secret = reader.one('SELECT value FROM secrets WHERE name=?', (conn['secret_name'],))
            grant = json.loads(store.report_cipher.decrypt(bytes(secret['value'])))
            if (grant.get('client_id') != original['client_id'] or grant.get('app_id') != proof.get('app_id')
                    or grant.get('account_id') != proof.get('account_id')
                    or grant.get('connected_at') != proof.get('grant_connected_at')
                    or not READ_SCOPES[source] <= set(grant.get('scopes') or [])):
                issues.append('grant_changed_or_missing_permission')
            if any(m.get('status') in ('available', 'partial') and m.get('values')
                   for m in payload.get('insights', {}).get('measurements', [])):
                if ('read_insights' not in (grant.get('scopes') or [])
                        or 'read_insights' not in proof.get('permissions', [])
                        or 'ANALYZE' not in payload['insights'].get('page_tasks', [])):
                    issues.append('insights_permission_unconfirmed')
            for key in ('expires_at', 'data_access_expires_at'):
                value = grant.get(key)
                if key == 'expires_at' and value is None:
                    issues.append('grant_expiry_unknown')
                if value not in (None, 0) and datetime.fromisoformat(value) <= datetime.now(timezone.utc):
                    issues.append('grant_expired')
        except Exception:
            issues.append('grant_unreadable')
        if (not READ_SCOPES[source] <= set(proof.get('permissions') or [])
                or proof.get('asset_access_confirmed') is not True or proof.get('pagination_complete') is not True
                or not proof.get('app_id') or not proof.get('graph_version')):
            issues.append('provider_scope_unconfirmed')
        job = reader.one('SELECT * FROM jobs WHERE id=?', (run['job_id'],))
        params = json.loads(job['params']) if job else {}
        if (not job or job['kind'] != 'meta_sync' or job['status'] != 'succeeded'
                or params.get('source') != source or params.get('asset_id') != asset['id']
                or params.get('report_type') != source.replace('_', '-')
                or (params.get('start'), params.get('end')) != (p['start'], p['end']) or params.get('demo') is not False):
            issues.append('provider_job_not_confirmed')
        if is_demo(payload) or not daily_consistent(db, run, payload):
            issues.append('daily_metrics_mismatch')
        if not verify_adapter_receipt(db, getattr(store, 'report_cipher', None), run, snap):
            issues.append('provider_origin_unconfirmed')
        else:
            receipt = reader.one('SELECT claims FROM source_attestations WHERE sync_run_id=?', (run['id'],))
            claims = json.loads(receipt['claims'])
            if claims.get('snapshot_id') != snap['id'] or claims.get('contract_version') != 'meta-reporting-v1':
                issues.append('snapshot_identity_mismatch')
        try:
            fetched = datetime.fromisoformat(payload['fetched_at'])
            age = datetime.now(timezone.utc) - fetched
            if age < timedelta(0) or age > timedelta(days=7):
                issues.append('evidence_stale')
        except (KeyError, TypeError, ValueError):
            issues.append('freshness_unknown')
        dates = [r['date'] for r in payload['daily']]
        expected_days = (date.fromisoformat(p['end']) - date.fromisoformat(p['start'])).days + 1
        if (len(dates) != len(set(dates)) or len(dates) != expected_days
                or min(dates, default=None) != p['start'] or max(dates, default=None) != p['end']
                or (payload['status'] != 'ready' and not empty_content_period(payload))):
            issues.append('partial')
        required = ['posts_published'] if source == 'facebook_content' else ['spend', 'impressions', 'clicks']
        by_key = {m['key']: m for m in metrics(payload)}
        if any(by_key[k]['status'] != 'available' for k in required):
            issues.append('required_metric_missing')
        if source == 'facebook_content':
            ids = [r['post_id'] for r in payload['entries']]
            if (payload.get('timezone') != 'UTC' or len(ids) != len(set(ids))
                    or any(not i.startswith(asset['external_id'] + '_') for i in ids)
                    or payload['totals'].get('engagements') is not None):
                issues.append('content_semantics_mismatch')
        elif (payload.get('currency') != asset['currency'] or payload.get('timezone') != asset['timezone']
              or payload.get('report_timezone') != asset['timezone'] or payload.get('attribution') != ATTRIBUTION):
            issues.append('ads_currency_timezone_attribution_mismatch')
        witnesses = [dict(preview['meta_snapshot'], sync_run_id=run['id'], asset_id=asset['id'],
                          period=preview['period'], latest_available_date=payload['latest_available_date'])]
    if latest:
        reviewer = reader.one('SELECT role,active FROM users WHERE id=?', (latest['reviewer_id'],))
        if not reviewer or reviewer['role'] != 'admin' or not reviewer['active']:
            issues.append('reviewer_not_authorized')
    issues = list(dict.fromkeys(issues))
    row = reader.one('SELECT data FROM datasets WHERE id=?', (candidate['id'],))
    return {'schema_version': '1.0', 'candidate_id': candidate['id'], 'dataset_id': original['id'],
            'client_id': original['client_id'], 'source': source, 'dataset_sha256': assessment['dataset_sha256'],
            'candidate_sha256': hashlib.sha256(row['data'].encode()).hexdigest(),
            'internal_review_id': latest['id'] if latest else None,
            'state': 'release_blocked' if issues else 'provider_origin_confirmed',
            'provider_origin_confirmed': not issues, 'publishable': False, 'issues': issues,
            'checks': [dict(evidence_id=e['evidence_id'], metric_id=e['metric_id'], asset_id=e['asset_id'],
                            issues=issues, status='release_blocked' if issues else 'provider_origin_confirmed', witnesses=witnesses)
                       for e in preview['evidence_cards']]}


def empty_content_period(payload):
    """A completed Page query can prove zero posts, but no interaction counters."""
    return (payload['source'] == 'facebook_content' and payload['status'] == 'no_data'
            and payload['entries'] == [] and payload['totals'].get('posts_published') == 0
            and bool(payload['daily']) and all(row.get('posts_published') == 0 for row in payload['daily']))


def release_source(reader, candidate, checks):
    p = candidate['params']; preview = candidate['marketing']['preview']
    _, _, snap, payload = scoped_snapshot(reader, candidate['client_id'], p['source'], preview['asset_id'], p['start'], p['end'])
    normalized = copy.deepcopy(payload)
    normalized.update(snapshot_id=snap['id'], snapshot_sha256=sha(payload), sync_run_id=snap['sync_run_id'],
                      asset_id=preview['asset_id'], data_origin='provider_origin_confirmed')
    if empty_content_period(payload):
        normalized.update(status='ready', ingestion_status=payload['status'])
    normalized['kpis'] = copy.deepcopy(preview['widgets'])
    for metric in normalized['kpis']:
        metric['verified'] = metric['status'] == 'available'
        metric['publishable'] = metric['status'] == 'available'
        if metric['verified']:
            metric['evidence_status'] = 'provider_origin_confirmed'
    normalized['warnings'] = list(normalized.get('warnings', [])) + [
        'Application adapter verification and authorized review; not an independent Meta audit.',
        'Unavailable/partial optional metrics are not verified claims. Lifetime is not period engagement.']
    if p['source'] == 'facebook_content' and 'content_report' in preview:
        from .facebook_content_report import approved_content_report
        normalized['content_report'] = approved_content_report(preview['content_report'])
    return normalized, checks['checks'][0]['witnesses'][0]
