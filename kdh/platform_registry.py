"""Read-only registry for the Admin's supported reporting sources.

The registry describes capabilities; it never implies provider access or data
availability. Runtime status is derived only from saved connections, assets,
and sync_runs for the active client.
"""

from __future__ import annotations

from datetime import date

from .meta_contract import READ_SCOPES
from .platform_data import DEFAULT_CLIENT_ID


PLATFORM_REGISTRY = (
    {
        "id": "seo_website",
        "label": "SEO & Website",
        "group": "Google",
        "sources": ("ga4", "gsc", "keywords"),
        "report_type": "seo",
        "connection": "Google OAuth và cấu hình tài sản",
        "asset_types": ("ga4_property", "search_console_property", "keyword_sheet"),
        "integration": "adapter_present",
        "reporting_periods": ("last7", "last28", "previous_month", "custom"),
        "metric_catalog": ("ga4", "gsc", "keywords"),
        "verification": "existing source-specific quality and review workflow",
        "dataset_readiness": "existing Dataset and Report Bundle pipeline",
        "operations": ("connect", "sync", "kpi_preview", "dataset", "review", "bundle"),
        "navigation": {"connections": "#connections/google", "assets": "#assets", "sync": "#sync", "analysis": "#analysis", "datasets": "#datasets", "review": "/marketing", "reports": "#reports"},
    },
    {
        "id": "facebook_content",
        "label": "Facebook Content",
        "group": "Meta",
        "sources": ("facebook_content",),
        "report_type": "facebook-content",
        "connection": "Meta OAuth, Page permission, and explicit Page selection",
        "asset_types": ("facebook_page",),
        "integration": "adapter_present",
        "reporting_periods": ("custom_1_to_90_days",),
        "metric_catalog": ("facebook_content",),
        "verification": "meta-reporting-v1 receipt plus official source-check and human review",
        "dataset_readiness": "existing facebook-content Dataset and Bundle contract",
        "operations": ("connect", "select_asset", "sync", "kpi_preview", "dataset", "review", "source_check", "bundle"),
        "navigation": {"connections": "#connections/facebook", "assets": "#connections/facebook", "sync": "#sync", "analysis": "#analysis", "datasets": "#datasets", "review": "/marketing", "reports": "#reports"},
    },
    {
        "id": "facebook_ads",
        "label": "Facebook Ads",
        "group": "Meta",
        "sources": ("facebook_ads",),
        "report_type": "facebook-ads",
        "connection": "Meta OAuth, ads_read, and explicit Ad Account selection",
        "asset_types": ("facebook_ad_account",),
        "integration": "adapter_present",
        "reporting_periods": ("custom_1_to_90_days",),
        "metric_catalog": ("facebook_ads",),
        "verification": "meta-reporting-v1 receipt plus official source-check and human review",
        "dataset_readiness": "existing facebook-ads Dataset and Bundle contract",
        "operations": ("connect", "select_asset", "sync", "kpi_preview", "dataset", "review", "source_check", "bundle"),
        "navigation": {"connections": "#connections/facebook", "assets": "#connections/facebook", "sync": "#sync", "analysis": "#analysis", "datasets": "#datasets", "review": "/marketing", "reports": "#reports"},
    },
    {
        "id": "tiktok_ads",
        "label": "TikTok Ads",
        "group": "TikTok",
        "sources": ("tiktok_ads",),
        "report_type": "tiktok",
        "connection": "TikTok Business OAuth and authorized advertiser account (not configured)",
        "asset_types": ("tiktok_ad_account",),
        "integration": "planned",
        "reporting_periods": (),
        "metric_catalog": ("tiktok_ads",),
        "verification": "not implemented",
        "dataset_readiness": "not available until a real adapter and provenance contract exist",
        "operations": (),
        "navigation": {"connections": "#connections/tiktok", "assets": "#assets", "sync": "#sync", "analysis": "#analysis", "datasets": "#datasets", "review": "/marketing", "reports": "#reports"},
    },
)

SOURCE_TO_PLATFORM = {
    source: platform["id"]
    for platform in PLATFORM_REGISTRY
    for source in platform["sources"]
}

ASSET_TO_SOURCE = {
    "ga4_property": "ga4",
    "search_console_property": "gsc",
    "keyword_sheet": "keywords",
    "facebook_page": "facebook_content",
    "facebook_ad_account": "facebook_ads",
    "tiktok_ad_account": "tiktok_ads",
}

STATUS_LABELS = {
    "not_configured": "Chưa cấu hình",
    "disconnected": "Chưa kết nối",
    "connected_no_asset": "Đã kết nối · chưa chọn tài sản",
    "asset_selected": "Đã chọn tài sản · chưa đồng bộ",
    "syncing": "Đang đồng bộ",
    "sync_succeeded": "Đồng bộ thành công · có dữ liệu",
    "sync_empty": "Đồng bộ thành công · không có bản ghi",
    "sync_partial": "Đồng bộ thành công một phần",
    "sync_failed": "Đồng bộ thất bại",
    "unavailable": "Chưa cấu hình tích hợp",
}


def _last_run(store, client_id: str, provider: str, asset_id: str):
    return store.one(
        """SELECT id,sync_type,requested_start,requested_end,status,record_count,
                  latest_available_date,fetched_at,error_code,created_at,finished_at
           FROM sync_runs WHERE client_id=? AND provider=? AND asset_id=?
           ORDER BY created_at DESC,id DESC LIMIT 1""",
        (client_id, provider, asset_id),
    )


def _state(asset, run, configured, connected):
    if not configured:
        return "not_configured"
    if not connected:
        return "disconnected"
    if not asset:
        return "connected_no_asset"
    if not run:
        return "asset_selected"
    if run["status"] in ("queued", "running"):
        return "syncing"
    if run["status"] == "partial":
        return "sync_partial"
    if run["status"] == "failed":
        return "sync_failed"
    return "sync_succeeded" if int(run["record_count"] or 0) > 0 else "sync_empty"


def platform_status(store, google, meta):
    """Build safe, fixed-client status without contacting a provider."""
    client_id = meta.client_id
    sandbox = client_id == "client_meta_sandbox"
    google_info = {} if sandbox else google.info()
    meta_info = meta.info()
    assets = store.all(
        """SELECT id,client_id,provider,asset_type,external_id,name,enabled,currency,timezone
           FROM source_assets WHERE client_id=? AND enabled=1 ORDER BY name,id""",
        (client_id,),
    )
    assets_by_source = {}
    for asset in assets:
        source = ASSET_TO_SOURCE.get(asset["asset_type"])
        if source:
            assets_by_source.setdefault(source, []).append(dict(asset))

    source_status = {}
    for source in ("ga4", "gsc", "keywords", "facebook_content", "facebook_ads", "tiktok_ads"):
        platform_id = SOURCE_TO_PLATFORM[source]
        spec = next(item for item in PLATFORM_REGISTRY if item["id"] == platform_id)
        source_assets = assets_by_source.get(source, [])
        if spec["integration"] == "planned":
            source_status[source] = {"state": "unavailable", "label": STATUS_LABELS["unavailable"], "asset": None, "latest_run": None, "verification": "not_available"}
            continue

        if source in ("ga4", "gsc", "keywords"):
            # Google OAuth/assets are currently owned by the primary client.
            # Never imply they are connected to the isolated Meta sandbox.
            if client_id != DEFAULT_CLIENT_ID:
                source_status[source] = {"state": "not_configured", "label": STATUS_LABELS["not_configured"], "asset": None, "latest_run": None, "verification": "not_checked"}
                continue
            configured = bool(google_info.get("configured"))
            connected = bool(google_info.get("connected"))
            latest = (google_info.get("sources") or {}).get(source, {})
        else:
            configured = bool(meta_info.get("configured"))
            connected = bool(meta_info.get("connected"))
            latest = {}

        asset = source_assets[0] if source_assets else None
        run = _last_run(store, client_id, spec["group"].lower() if spec["group"] != "Google" else "google", asset["id"]) if asset else None
        state = _state(asset, run, configured, connected)
        source_status[source] = {
            "state": state,
            "label": STATUS_LABELS[state],
            "configured": configured,
            "connected": connected,
            "asset": {key: asset[key] for key in ("id", "asset_type", "external_id", "name", "currency", "timezone")} if asset else None,
            "latest_run": dict(run) if run else None,
            "latest_data_date": (run["latest_available_date"] if run else latest.get("latest_available_date")),
            "fetched_at": (run["fetched_at"] if run else latest.get("fetched_at")),
            "verification": "unverified" if source.startswith("facebook_") and run and run["status"] == "succeeded" else "not_checked",
        }
        if source in READ_SCOPES:
            scopes = meta_info.get("scopes")
            required = READ_SCOPES[source]
            missing = sorted(required - set(scopes)) if (
                meta_info.get("has_connection") and isinstance(scopes, list)
                and all(isinstance(scope, str) for scope in scopes)
            ) else None
            source_status[source]["permission"] = {
                "required": sorted(required),
                "missing": missing,
            }

    registry = []
    for platform in PLATFORM_REGISTRY:
        states = [source_status[source] for source in platform["sources"]]
        registry.append({
            "id": platform["id"], "label": platform["label"], "group": platform["group"],
            "sources": list(platform["sources"]), "report_type": platform["report_type"],
            "integration": platform["integration"], "operations": list(platform["operations"]),
            "connection": platform["connection"], "asset_types": list(platform["asset_types"]),
            "reporting_periods": list(platform["reporting_periods"]),
            "metric_catalog": list(platform["metric_catalog"]),
            "verification": platform["verification"], "dataset_readiness": platform["dataset_readiness"],
            "navigation": dict(platform["navigation"]), "source_status": {
                source: source_status[source] for source in platform["sources"]
            },
            "state": "unavailable" if platform["integration"] == "planned" else states[0]["state"] if len(states) == 1 else _group_state(states),
        })
    return {
        "client_context": {"client_id": client_id, "environment": "sandbox" if sandbox else "primary"},
        "platforms": registry,
        "sources": source_status,
        "assets": [item for values in assets_by_source.values() for item in values],
    }


def _group_state(states):
    priority = ("syncing", "sync_failed", "sync_partial", "sync_succeeded", "sync_empty", "asset_selected", "connected_no_asset", "disconnected", "not_configured")
    return next((key for key in priority if any(item["state"] == key for item in states)), "not_configured")


def sync_history(store, client_id: str, filters: dict):
    """Read persisted sync_runs for the configured client; never reads providers."""
    allowed = {"start", "end", "provider", "status", "source", "asset_id"}
    if set(filters) - allowed:
        from .core import Problem
        raise Problem("Bộ lọc lịch sử đồng bộ không hợp lệ.", 400, "invalid_sync_filter")
    if ("start" in filters) != ("end" in filters):
        from .core import Problem
        raise Problem("Cần chọn đủ ngày bắt đầu và kết thúc.", 400, "invalid_sync_filter")
    if "start" in filters:
        try:
            start, end = date.fromisoformat(filters["start"]), date.fromisoformat(filters["end"])
        except (TypeError, ValueError):
            from .core import Problem
            raise Problem("Khoảng ngày không hợp lệ.", 400, "invalid_sync_filter") from None
        if end < start:
            from .core import Problem
            raise Problem("Ngày kết thúc phải từ ngày bắt đầu trở đi.", 400, "invalid_sync_filter")
    if filters.get("status") and filters["status"] not in {"queued", "running", "succeeded", "partial", "failed"}:
        from .core import Problem
        raise Problem("Trạng thái đồng bộ không hợp lệ.", 400, "invalid_sync_filter")
    if filters.get("provider") and filters["provider"] not in {"google", "meta", "tiktok", "youtube", "gmb", "other"}:
        from .core import Problem
        raise Problem("Nền tảng không hợp lệ.", 400, "invalid_sync_filter")
    where = ["sr.client_id=?"]
    args = [client_id]
    for key, expression in (("provider", "sr.provider=?"), ("status", "sr.status=?")):
        if filters.get(key):
            where.append(expression)
            args.append(filters[key])
    if "start" in filters:
        where.append("COALESCE(sr.requested_end,sr.created_at)>=?")
        where.append("COALESCE(sr.requested_start,sr.created_at)<=?")
        args.extend((filters["start"], filters["end"]))
    if filters.get("source"):
        where.append("EXISTS (SELECT 1 FROM source_snapshots ss WHERE ss.sync_run_id=sr.id AND ss.source_key=?)")
        args.append(filters["source"])
    if filters.get("asset_id"):
        asset = store.one("SELECT id FROM source_assets WHERE id=? AND client_id=?", (filters["asset_id"], client_id))
        if not asset:
            from .core import Problem
            raise Problem("Tài sản ngoài phạm vi client hiện tại.", 404, "asset_not_found")
        where.append("sr.asset_id=?")
        args.append(filters["asset_id"])
    rows = store.all(
        """SELECT sr.id,sr.client_id,sr.provider,sr.sync_type,sr.asset_id,sr.requested_start,
                  sr.requested_end,sr.status,sr.latest_available_date,sr.record_count,sr.started_at,
                  sr.finished_at,sr.fetched_at,sr.error_code,sr.job_id,sr.created_at,
                  sa.name AS asset_name,sa.external_id AS asset_external_id,sa.asset_type,
                  j.kind AS job_kind
           FROM sync_runs sr LEFT JOIN source_assets sa ON sa.id=sr.asset_id
           LEFT JOIN jobs j ON j.id=sr.job_id WHERE """ + " AND ".join(where) +
        " ORDER BY sr.created_at DESC,sr.id DESC LIMIT 500",
        tuple(args),
    )
    assets = store.all("""SELECT id,provider,asset_type,external_id,name FROM source_assets
        WHERE client_id=? AND enabled=1 ORDER BY provider,name""", (client_id,))
    return {"client_id": client_id, "runs": rows, "assets": assets, "limit": 500, "truncated": len(rows) == 500}
