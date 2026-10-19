"""Allowlisted Meta sync diagnostics. Never format exceptions or provider data."""
import json
import logging
from contextlib import contextmanager
from pathlib import Path
import re
import sqlite3
import traceback
from uuid import uuid4

import psycopg

from .core import Problem
from .google import SourceError


LOGGER = logging.getLogger('kdh.meta_sync')
LOGGER.setLevel(logging.INFO)
LOGGER.propagate = False
if not LOGGER.handlers:
    handler = logging.StreamHandler()  # stderr is collected by Docker, also outside Flask requests.
    handler.setFormatter(logging.Formatter('%(message)s'))
    LOGGER.addHandler(handler)

STAGES = frozenset({
    'job_dispatch', 'job_validation', 'oauth_validation', 'sync_start', 'page_token', 'fetch_posts',
    'normalize_content', 'read_ads', 'snapshot_validation', 'database_write',
    'sync_finalize', 'sync_complete', 'failure_status_write', 'job_status_write',
})
ERRORS = {
    'meta_permission_error': (403, 'Meta chưa cấp đủ quyền đọc dữ liệu cho tài sản đã chọn. Hãy kiểm tra quyền và kết nối lại.'),
    'meta_page_permission': (403, 'Meta chưa cấp quyền đọc Trang được chọn. Hãy kiểm tra quyền và kết nối lại.'),
    'meta_ads_permission': (403, 'Meta chưa được cấp quyền ads_read. Không thể đồng bộ Facebook Ads.'),
    'meta_reconnect_required': (409, 'Kết nối Meta không còn hợp lệ. Hãy kết nối lại.'),
    'meta_api_error': (502, 'Không thể lấy dữ liệu từ Meta. Hãy thử lại hoặc kiểm tra kết nối.'),
    'meta_data_error': (502, 'Dữ liệu Meta chưa hợp lệ để đồng bộ. Kết quả cũ được giữ nguyên.'),
    'meta_snapshot_invalid': (502, 'Dữ liệu chưa đạt kiểm tra an toàn để lưu. Kết quả cũ được giữ nguyên.'),
    'meta_database_error': (503, 'Không thể lưu kết quả đồng bộ. Hãy thử lại sau.'),
    'meta_validation_error': (409, 'Tác vụ Meta hoặc quyền truy cập không còn hợp lệ. Hãy kiểm tra và thử lại.'),
    'meta_sync_internal_error': (500, 'Đồng bộ Meta chưa hoàn tất. Hãy liên hệ quản trị hệ thống.'),
}


def safe_integer(value, minimum=0, maximum=2147483647):
    # Never coerce provider strings, booleans or arbitrary objects into log fields.
    return value if type(value) is int and minimum <= value <= maximum else None


class MetaRequestError(SourceError):
    """Transport failure with fixed text and scalar metadata, never a raw response."""
    def __init__(self, *, http_status=None, graph_error=None, failure_layer='graph_api'):
        self.http_status = safe_integer(http_status, 100, 599)
        error = graph_error if isinstance(graph_error, dict) else {}
        self.graph_code = safe_integer(error.get('code'))
        self.graph_subcode = safe_integer(error.get('error_subcode'))
        self.is_transient = error.get('is_transient') if type(error.get('is_transient')) is bool else None
        self.failure_layer = failure_layer if failure_layer in (
            'graph_api', 'transport', 'response_decode') else 'graph_api'
        if self.graph_code == 190:
            status, code = 'meta_reconnect_required', 'meta_reconnect_required'
        elif self.http_status in (401, 403) or self.graph_code in (10, 200):
            status, code = 'meta_permission_error', 'meta_permission_error'
        elif self.failure_layer == 'response_decode':
            status, code = 'meta_bad_response', 'meta_data_error'
        else:
            status, code = 'meta_oauth_error', 'meta_api_error'
        super().__init__(status, ERRORS[code][1])

    def safe_metadata(self):
        # Revalidate even these attributes at the logging boundary.
        fields = {
            'http_status': safe_integer(self.http_status, 100, 599),
            'graph_error_code': safe_integer(self.graph_code),
            'graph_error_subcode': safe_integer(self.graph_subcode),
        }
        if type(self.is_transient) is bool:
            fields['is_transient'] = self.is_transient
        if self.failure_layer in ('graph_api', 'transport', 'response_decode'):
            fields['failure_layer'] = self.failure_layer
        return {key: value for key, value in fields.items() if value is not None}


class MetaSyncFailure(Problem):
    """Only a fixed public message/code crosses the worker boundary."""
    def __init__(self, code):
        status, message = ERRORS[code]
        super().__init__(message, status, code)


class MetaExpirationError(Problem):
    """Classify rejected expiry metadata without retaining its provider value."""
    FIELDS = frozenset({'expires_at', 'data_access_expires_at'})
    REASONS = frozenset({'missing', 'zero', 'invalid_type', 'out_of_range', 'past'})

    def __init__(self, field, reason):
        super().__init__('Thời hạn token Meta không hợp lệ. Hãy kết nối lại.', 502)
        self.field = field
        self.reason = reason

    def safe_metadata(self):
        return {
            'expiration_field': self.field if isinstance(self.field, str) and self.field in self.FIELDS else 'unknown',
            'expiration_reason': self.reason if isinstance(self.reason, str) and self.reason in self.REASONS else 'unknown',
        }


class MetaOAuthDiagnostics:
    """OAuth attempt metadata only; never log callback arguments or messages."""
    STAGES = frozenset({
        'state_validation', 'callback_validation', 'code_exchange', 'long_token_exchange',
        'token_inspection', 'token_validation', 'expiration_validation',
        'permissions_validation', 'profile_fetch', 'profile_validation',
        'connection_write', 'state_cleanup',
    })

    def __init__(self):
        self.attempt_id = uuid4().hex
        self.stage = 'state_validation'

    def start(self, stage):
        if stage not in self.STAGES:
            raise ValueError('Unknown OAuth diagnostic stage')
        self.stage = stage

    def finish(self, result=None, exc=None):
        fields = {'event': 'meta_oauth', 'attempt_id': self.attempt_id,
                  'stage': self.stage, 'status': 'failed' if exc else result}
        if exc is not None:
            fields['exception_type'] = type(exc).__name__
            if isinstance(exc, MetaRequestError):
                fields.update(exc.safe_metadata())
            if isinstance(exc, MetaExpirationError):
                fields.update(exc.safe_metadata())
            if isinstance(exc, psycopg.Error) and isinstance(exc.sqlstate, str) and re.fullmatch(r'[0-9A-Z]{5}', exc.sqlstate):
                fields['sqlstate'] = exc.sqlstate
        LOGGER.log(logging.ERROR if exc else logging.INFO,
                   json.dumps(fields, ensure_ascii=True, separators=(',', ':')))


class MetaSyncDiagnostics:
    def __init__(self, *, source=None, client_id=None, job_id=None, postgres=False):
        self.source = source if source in ('facebook_content', 'facebook_ads') else 'unknown'
        self.client_id = client_id if client_id in ('client_meta_sandbox', 'client_kinderhealth') else 'unknown'
        self.job_id = job_id if isinstance(job_id, str) and re.fullmatch(r'[0-9a-f]{32}', job_id) else None
        self.database = 'postgresql' if postgres else 'sqlite'
        self.stage = 'job_dispatch'
        self.sync_run_id = None

    def bind_sync(self, sync_run_id):
        self.sync_run_id = (sync_run_id if isinstance(sync_run_id, str)
                            and re.fullmatch(r'[0-9a-f]{32}', sync_run_id) else None)

    @classmethod
    def for_job(cls, job, meta, store):
        try:
            params = json.loads(job.get('params', '{}'))
            source = params.get('source') if isinstance(params, dict) else None
        except (ValueError, TypeError):
            source = None
        return cls(source=source, client_id=getattr(meta, 'client_id', None),
                   job_id=job.get('id'), postgres=store.postgres)

    def _emit(self, status, *, exc=None, code=None):
        fields = {'event': 'meta_sync', 'source': self.source, 'client_id': self.client_id,
                  'stage': self.stage, 'status': status, 'database': self.database}
        if self.job_id:
            fields['job_id'] = self.job_id
        if self.sync_run_id:
            fields['sync_run_id'] = self.sync_run_id
        if exc is not None:
            fields['exception_type'] = type(exc).__name__
            fields['error_code'] = code
            if isinstance(exc, MetaRequestError):
                fields.update(exc.safe_metadata())
            database_error = exc
            if isinstance(exc, sqlite3.DatabaseError) and isinstance(exc.__cause__, psycopg.Error):
                database_error = exc.__cause__  # Store's PostgreSQL constraint wrapper.
            if isinstance(database_error, psycopg.Error):
                sqlstate = database_error.sqlstate
                if isinstance(sqlstate, str) and re.fullmatch(r'[0-9A-Z]{5}', sqlstate):
                    fields['sqlstate'] = sqlstate
            # Walk code objects only: no traceback formatting, source lines, locals,
            # SQL, exception message/cause/context, request URL or response payload.
            root = Path(__file__).resolve().parent
            for frame, line in traceback.walk_tb(exc.__traceback__):
                path = Path(frame.f_code.co_filename).resolve()
                if path.parent == root:
                    fields['file'] = 'kdh/' + path.name
                    fields['line'] = line
        LOGGER.log(logging.ERROR if exc is not None else logging.INFO,
                   json.dumps(fields, ensure_ascii=True, separators=(',', ':')))

    def start(self, stage):
        if stage not in STAGES:
            raise ValueError('Unknown Meta diagnostic stage')
        self.stage = stage
        self._emit('started')

    def success(self):
        self._emit('succeeded')

    @contextmanager
    def phase(self, stage):
        previous = self.stage
        self.start(stage)
        yield
        self.success()
        # Restore only on success: failures retain the innermost operation.
        self.stage = previous

    def failure(self, exc):
        if isinstance(exc, (psycopg.Error, sqlite3.DatabaseError)):
            code = 'meta_database_error'
        elif isinstance(exc, SourceError):
            code = {'meta_permission_error': 'meta_permission_error',
                    'meta_reconnect_required': 'meta_reconnect_required',
                    'meta_bad_response': 'meta_data_error'}.get(exc.status, 'meta_api_error')
        elif isinstance(exc, Problem):
            code = exc.code if isinstance(exc.code, str) and exc.code in ERRORS else (
                'meta_data_error' if exc.code in ('meta_bad_response', 'meta_bad_paging',
                                                'meta_too_many_rows', 'meta_pagination_limit')
                else 'meta_validation_error')
        elif self.stage == 'snapshot_validation':
            code = 'meta_snapshot_invalid'
        elif self.stage == 'normalize_content' or isinstance(exc, (ValueError, TypeError, KeyError, AttributeError)):
            code = 'meta_data_error'
        else:
            code = 'meta_sync_internal_error'
        self._emit('failed', exc=exc, code=code)
        return MetaSyncFailure(code)
