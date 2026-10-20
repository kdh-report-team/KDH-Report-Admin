"""Admin workflow entry point and resumable snapshot index; no provider calls."""
import json
from urllib.parse import urlsplit

from flask import current_app, g, jsonify, redirect, render_template, request

from .core import Problem, now
from .metric_catalog import SOURCES
from .platform_data import DEFAULT_CLIENT_ID


def sandbox_marketing_client():
    """Approved sandbox-only scope; never derive authorization from request data."""
    return 'client_meta_sandbox' if current_app.config.get('META_CLIENT_ID') == 'client_meta_sandbox' else None


def marketing_client():
    return sandbox_marketing_client() or DEFAULT_CLIENT_ID


def register_marketing_console(app, store, require):
    def scoped_dataset(dataset_id, seen=None):
        seen = set() if seen is None else seen
        if not isinstance(dataset_id, str) or dataset_id in seen or len(seen) >= 8:
            raise Problem('Truy vết Dataset không hợp lệ.', 404, 'dataset_not_found')
        seen.add(dataset_id)
        row = store.one('SELECT data FROM datasets WHERE id=?', (dataset_id,))
        if not row:
            raise Problem('Không tìm thấy Dataset trong phạm vi hiện tại.', 404, 'dataset_not_found')
        data = json.loads(row['data'])
        if data.get('client_id') != sandbox_marketing_client():
            raise Problem('Không tìm thấy Dataset trong phạm vi hiện tại.', 404, 'dataset_not_found')
        for lineage in ('release_candidate', 'release'):
            ref = data.get(lineage) or {}
            for key in ('origin_dataset_id', 'candidate_id'):
                if ref.get(key):
                    scoped_dataset(ref[key], set(seen))
        return data

    @app.before_request
    def sandbox_marketing_scope():
        client = sandbox_marketing_client()
        if not client:
            return  # Production and other runtimes retain their existing policy.
        path = request.path
        marketing = path.startswith('/api/marketing/')
        dataset = path.startswith('/api/datasets/')
        bundle = path.startswith('/api/report-bundles')
        if not (marketing or dataset or bundle):
            return
        if not g.user:
            raise Problem('Cần đăng nhập Admin.', 401)
        if g.user['role'] != 'admin' or not g.user['active']:
            raise Problem('Marketing sandbox chỉ dành cho Admin đang hoạt động.', 403, 'admin_required')
        if not store.one('SELECT id FROM clients WHERE id=? AND active=1', (client,)):
            raise Problem('Client sandbox không còn hoạt động.', 403, 'client_not_allowed')
        data = request.get_json(silent=True)
        for owner in request.args.getlist('client_id') + ([data['client_id']] if isinstance(data, dict) and 'client_id' in data else []):
            if owner != client:
                raise Problem('Client ngoài phạm vi sandbox.', 403, 'client_not_allowed')
        if len(request.args.getlist('client_id')) > 1:
            raise Problem('Không được truyền trùng client_id.', 400)
        args = request.view_args or {}
        for key in ('dataset_id', 'candidate_id'):
            if args.get(key):
                scoped_dataset(args[key])
        if isinstance(data, dict):
            if path == '/api/marketing/datasets' and data.get('client_id') != client:
                raise Problem('Cần client sandbox rõ ràng.', 403, 'client_not_allowed')
            sections = data.get('sections')
            if isinstance(sections, list):
                for section in sections:
                    if isinstance(section, dict) and section.get('dataset_id'):
                        scoped_dataset(section['dataset_id'])
        asset_id = request.args.get('asset_id') or (data.get('asset_id') if isinstance(data, dict) else None)
        if asset_id and not store.one('SELECT id FROM source_assets WHERE id=? AND client_id=? AND enabled=1', (asset_id, client)):
            raise Problem('Tài sản ngoài phạm vi sandbox.', 404, 'asset_not_found')
        if args.get('report_id') and bundle:
            owners = store.all('SELECT client_id FROM report_bundles WHERE bundle_key=?', (args['report_id'],))
            if not owners or any(row['client_id'] != client for row in owners):
                raise Problem('Báo cáo ngoài phạm vi sandbox.', 404, 'report_not_found')
        if path in ('/api/marketing/preview', '/api/marketing/datasets'):
            source = request.args.get('source') if request.method == 'GET' else (data.get('source') if isinstance(data, dict) else None)
            if source not in ('facebook_content', 'facebook_ads'):
                raise Problem('Marketing sandbox chỉ hỗ trợ nguồn Meta trong phạm vi đã cấu hình.', 403, 'forbidden_source')

    @app.get('/marketing')
    def marketing_console():
        if not g.user:
            return redirect('/')
        if g.user['role'] != 'admin':
            return 'Chỉ quản trị viên được duyệt báo cáo.', 403
        return render_template('marketing.html')

    @app.get('/api/marketing/workflow')
    @require('admin')
    def marketing_workflow():
        client_id = marketing_client()
        client = store.one('SELECT name FROM clients WHERE id=? AND active=1', (client_id,))
        if not client:
            raise Problem('Client không còn hoạt động.', 404)
        if sandbox_marketing_client() and set(request.args) - {'client_id'}:
            raise Problem('Tham số workflow không hợp lệ.', 400)
        snapshots = []
        # Read metadata only; contents remain behind the existing Dataset API.
        for row in store.all('SELECT id,created_at,report_type,data FROM datasets ORDER BY created_at DESC LIMIT 500'):
            data = json.loads(row['data'])
            kind = data.get('dataset_kind', '')
            if data.get('client_id') != client_id or kind not in (
                    'marketing_internal_preview_v1', 'marketing_release_candidate_v1', 'marketing_release_snapshot_v1'):
                continue
            snapshots.append({'id': row['id'], 'kind': kind, 'created_at': row['created_at'],
                              'source': data['params']['source'], 'start': data['params']['start'],
                              'end': data['params']['end']})
        new_url = app.config.get('REPORT_NEW_BASE_URL', 'http://localhost:8080').rstrip('/')
        try:
            parsed = urlsplit(new_url)
            if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
                new_url = ''
        except ValueError:
            new_url = ''
        from .viewer_handoff import handoff_supported
        return jsonify(client_id=client_id, client_name=client['name'], new_url=new_url,
                       viewer_handoff_supported=handoff_supported(client_id),
                       sources=[{'id': key, 'label': item['label'], 'integration': item['integration']}
                                for key, item in SOURCES.items() if not sandbox_marketing_client() or key in ('facebook_content', 'facebook_ads')], snapshots=snapshots,
                       assets=store.all('''SELECT id,name,asset_type,provider,external_id FROM source_assets
                           WHERE client_id=? AND enabled=1 ORDER BY name''', (client_id,)))

    @app.get('/api/marketing/datasets/<dataset_id>/source-evidence')
    @require('admin')
    def marketing_source_evidence(dataset_id):
        # Display technical receipt checks only; never create attestation/review.
        from datetime import datetime, timedelta, timezone
        from .marketing_review import _dataset
        from .marketing_provenance import verify_adapter_receipt, sha
        from .meta_contract import daily_consistent
        with store.connect() as db:
            _, data = _dataset(db, dataset_id)
            preview = data['marketing']['preview']
            if data['params']['source'] not in ('facebook_content', 'facebook_ads'):
                raise Problem('Dataset không phải nguồn Meta.', 404)
            meta = preview.get('meta_snapshot') or {}
            snap = db.execute('SELECT * FROM source_snapshots WHERE id=?', (meta.get('snapshot_id'),)).fetchone()
            run = db.execute('SELECT * FROM sync_runs WHERE id=?', (snap['sync_run_id'],)).fetchone() if snap else None
            asset = db.execute('SELECT * FROM source_assets WHERE id=?', (preview.get('asset_id'),)).fetchone()
            if not snap or not run or not asset or any(r['client_id'] != data['client_id'] for r in (snap, run, asset)):
                raise Problem('Không tìm thấy bằng chứng đúng client.', 409, 'source_scope_mismatch')
            payload = json.loads(snap['payload'])
            if (snap['asset_id'] != asset['id'] or run['asset_id'] != asset['id'] or snap['source_key'] != data['params']['source']
                    or meta.get('sync_run_ids') != [run['id']] or meta.get('external_id') != asset['external_id']
                    or (snap['requested_start'], snap['requested_end']) != (data['params']['start'], data['params']['end'])):
                raise Problem('Truy vết nguồn không khớp Dataset.', 409, 'source_scope_mismatch')
            fetched = payload.get('fetched_at')
            try:
                fresh = timedelta(0) <= datetime.now(timezone.utc) - datetime.fromisoformat(fetched) <= timedelta(days=7)
            except (TypeError, ValueError):
                fresh = False
            receipt = db.execute('SELECT claims FROM source_attestations WHERE sync_run_id=?', (run['id'],)).fetchone()
            claims = json.loads(receipt['claims']) if receipt else {}
            valid_receipt = (verify_adapter_receipt(db, store.report_cipher, run, snap)
                             and claims.get('snapshot_id') == snap['id'] and claims.get('contract_version') == 'meta-reporting-v1')
            return jsonify(client_id=data['client_id'], dataset_id=dataset_id, asset_id=asset['id'], asset_name=asset['name'],
                external_id=asset['external_id'], source=snap['source_key'], snapshot_id=snap['id'], sync_run_id=run['id'],
                job_id=run['job_id'], contract_version=payload.get('contract_version'), fetched_at=fetched,
                timezone=payload.get('timezone'), snapshot_hash_matches=sha(payload) == meta.get('snapshot_sha256'),
                receipt_exists=bool(receipt), receipt_valid=bool(valid_receipt), daily_consistent=daily_consistent(db, run, payload),
                fresh=fresh, checked_at=now(), verified=False, publishable=False, official_source_check='not_performed',
                note='Bằng chứng adapter của ứng dụng; chưa thay thế human review hoặc source-check trên Candidate.')
