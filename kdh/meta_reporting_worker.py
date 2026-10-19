"""Execute one queued Meta sync with atomic normalized-data persistence."""

import json
import os

from .core import Problem, digest, now, pack, uid
from .meta_diagnostics import MetaSyncDiagnostics
from .meta_reporting import MetaReportingReader, SOURCES, validate_range
from .platform_data import PlatformData, DEFAULT_CLIENT_ID, _stable_metric_id, _validate_snapshot_payload


class MetaReportingWorker:
    def __init__(self, store, meta):
        self.store, self.meta = store, meta
        self.platform = PlatformData(store)

    def _step(self, job_id, source, status, count=0, message=None):
        step = {'source': source, 'status': status, 'record_count': count}
        if message:
            step['error'] = message
        self.store.execute('UPDATE jobs SET steps=? WHERE id=?', (pack([step]), job_id))

    def _save_metric(self, db, *, asset_id, source, sync_id, entity_type, row,
                     entity_id='', dimensions=None):
        day = row['date']
        metric_id = _stable_metric_id(asset_id, entity_type, entity_id, day, '')
        measures = {k: v for k, v in row.items() if k not in
                    ('date', 'campaign_id', 'campaign_name', 'post_id')}
        db.execute('''INSERT INTO daily_metrics
            (id,client_id,asset_id,provider,entity_type,entity_id,metric_date,dimension_key,
             dimensions,metrics,source_hash,sync_run_id,fetched_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(asset_id,entity_type,entity_id,metric_date,dimension_key)
            DO UPDATE SET metrics=excluded.metrics,dimensions=excluded.dimensions,
               source_hash=excluded.source_hash,sync_run_id=excluded.sync_run_id,
               fetched_at=excluded.fetched_at''',
            (metric_id, self.meta.client_id, asset_id, 'meta', entity_type, entity_id, day,
             '', pack(dimensions or {}), pack(measures), digest(pack(row)), sync_id, now()))

    def _persist(self, sync_id, job, source, asset, connection_id, result, start, end, diagnostics):
        # Source snapshot + normalized rows + sync status are committed together;
        # a failed attempt cannot overwrite previously successful metrics.
        with diagnostics.phase('snapshot_validation'):
            _validate_snapshot_payload(result)
            n = len(result['daily']) + len(result['entries'])
            payload = pack(result)
        diagnostics.start('database_write')
        with self.store.connect(immediate=True) as db:
            if source in SOURCES:
                # Replace only the fully fetched asset period. Removed posts must not
                # survive a successful resync; any later failure rolls this back too.
                db.execute('''DELETE FROM daily_metrics WHERE client_id=? AND asset_id=?
                    AND provider='meta' AND entity_type IN ('page','post','ad_account','campaign')
                    AND metric_date>=? AND metric_date<=?''',
                    (self.meta.client_id, asset['id'], start, end))
            entity_type = 'ad_account' if source == 'facebook_ads' else 'page'
            for row in result['daily']:
                self._save_metric(db, asset_id=asset['id'], source=source, sync_id=sync_id,
                                  entity_type=entity_type, row=row)
            for row in result['entries']:
                item_id = row.get('campaign_id') if source == 'facebook_ads' else row.get('post_id')
                if not item_id:
                    continue
                dimensions = ({'campaign_name': row.get('campaign_name', '')}
                              if source == 'facebook_ads' else {})
                self._save_metric(db, asset_id=asset['id'], source=source, sync_id=sync_id,
                    entity_type='campaign' if source == 'facebook_ads' else 'post',
                    entity_id=item_id, dimensions=dimensions, row=row)
            stamp = now()
            db.execute('''INSERT INTO source_snapshots
                (id,sync_run_id,client_id,asset_id,provider,source_key,
                 requested_start,requested_end,payload,created_at)
                VALUES (?,?,?,?,?,?,?,?,?,?)''',
                (uid(), sync_id, self.meta.client_id, asset['id'], 'meta', source,
                 start, end, payload, stamp))
            diagnostics.success()
            diagnostics.start('sync_finalize')
            db.execute('''UPDATE sync_runs SET status='succeeded',latest_available_date=?,
                record_count=?,finished_at=?,fetched_at=?,warnings=? WHERE id=?''',
                (result['latest_available_date'], n, stamp, stamp,
                 pack(result.get('warnings', [])), sync_id))
            db.execute('UPDATE connections SET last_sync_at=?,updated_at=? WHERE id=?',
                       (stamp, stamp, connection_id))
            if result['latest_available_date'] and (result['status'] == 'ready' or source == 'facebook_content'):
                db.execute('''INSERT INTO sync_watermarks
                    (asset_id,last_complete_date,last_attempt_at,lookback_days,updated_at)
                    VALUES (?,?,?,?,?) ON CONFLICT(asset_id) DO UPDATE SET
                    last_complete_date=excluded.last_complete_date,
                    last_attempt_at=excluded.last_attempt_at,updated_at=excluded.updated_at''',
                    (asset['id'], result['latest_available_date'], stamp, 3, stamp))
            step = [{'source': source, 'status': 'no_data' if result['status'] == 'no_data' else 'succeeded',
                     'record_count': n}]
            db.execute("UPDATE jobs SET status='succeeded',finished_at=?,error=NULL,steps=? WHERE id=?",
                       (stamp, pack(step), job['id']))
            from .meta_contract import record_receipt
            record_receipt(db, self.store, self.meta, sync_id, result)
        # Finalization is successful only after the transaction commits.
        diagnostics.success()
        return n

    def _prepare(self, job, diagnostics):
        if self.meta and self.meta.client_id == DEFAULT_CLIENT_ID and os.getenv('META_REPORTING_ALLOW_PRIMARY_CLIENT') != '1':
            raise Problem('Meta Reporting trên client chính chưa được bật để bảo vệ dữ liệu.')
        if self.meta is None:
            raise Problem('Worker chưa được cấu hình Meta.', 503)
        params = json.loads(job['params'])
        source, asset_id = params.get('source'), params.get('asset_id')
        if source not in SOURCES or not isinstance(asset_id, str) or params.get('demo') is not False:
            raise Problem('Tác vụ Meta không hợp lệ.')
        start, end = params.get('start'), params.get('end')
        validate_range(start, end)
        expected_report = 'facebook-ads' if source == 'facebook_ads' else 'facebook-content'
        if params.get('report_type') != expected_report:
            raise Problem('Loại báo cáo không khớp nguồn Meta.')
        actor = self.store.one('SELECT role,active FROM users WHERE id=?', (job['user_id'],))
        if not actor or actor['role'] != 'admin' or not actor['active']:
            raise Problem('Người yêu cầu không còn quyền đồng bộ Meta.', 403)
        with diagnostics.phase('oauth_validation'):
            if not self.meta.info()['connected']:
                raise Problem('Meta OAuth chưa kết nối hoặc đã hết hạn.', 409, 'meta_reconnect_required')
            token = self.meta.read() or {}
        conn = self.store.one('''SELECT id FROM connections WHERE client_id=? AND provider='meta'
            AND external_account_id=? AND status='connected' ORDER BY created_at DESC LIMIT 1''',
            (self.meta.client_id, token.get('account_id')))
        if not conn:
            raise Problem('Không tìm thấy kết nối Meta phù hợp.', 409)
        asset = self.store.one('''SELECT * FROM source_assets WHERE id=? AND client_id=?
            AND provider='meta' AND connection_id=? AND asset_type=? AND enabled=1''',
            (asset_id, self.meta.client_id, conn['id'], SOURCES[source][0]))
        if not asset:
            raise Problem('Tài sản Meta không còn khả dụng.', 403)
        return source, asset, conn, start, end

    def run(self, job, diagnostics=None):
        diagnostics = diagnostics or MetaSyncDiagnostics.for_job(job, self.meta, self.store)
        sync_id = None
        try:
            with diagnostics.phase('job_validation'):
                source, asset, conn, start, end = self._prepare(job, diagnostics)
            with diagnostics.phase('sync_start'):
                self._step(job['id'], source, 'running')
                sync_id = self.platform.start_sync(client_id=self.meta.client_id, provider='meta',
                    sync_type='manual', requested_start=start, requested_end=end,
                    connection_id=conn['id'], asset_id=asset['id'], job_id=job['id'])
                diagnostics.bind_sync(sync_id)
            reader = MetaReportingReader(self.meta, diagnostics=diagnostics)
            if source == 'facebook_ads':
                with diagnostics.phase('read_ads'):
                    result = reader.ads(asset['external_id'], start, end)
            else:
                result = reader.content(asset['external_id'], start, end)
            self._persist(sync_id, job, source, asset, conn['id'], result, start, end, diagnostics)
        except Exception as exc:
            failure = diagnostics.failure(exc)
            if sync_id:
                try:
                    with diagnostics.phase('failure_status_write'):
                        self.platform.finish_sync(sync_id, status='failed', record_count=0,
                            error_code=failure.code, error_message=failure.message)
                        self._step(job['id'], source, 'failed', message=failure.message)
                except Exception as status_error:
                    # A DB outage must not erase the original failure from logs.
                    diagnostics.failure(status_error)
            raise failure from None
        diagnostics.start('sync_complete')
        diagnostics.success()
