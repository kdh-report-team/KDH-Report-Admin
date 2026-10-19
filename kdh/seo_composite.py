
"""Internal SEO composite builder.

Combines source Release payloads without granting
publication rights.

Cryptographic verification and database persistence
belong to the next integration step.
"""

from copy import deepcopy
from datetime import date

from .core import Problem
from .marketing_provenance import is_demo, sha


SEO_METRICS = {
    "ga4": (
        "ga4.sessions",
        "ga4.active_users",
        "ga4.page_views",
        "ga4.engagement_rate",
    ),
    "gsc": (
        "gsc.clicks",
        "gsc.impressions",
        "gsc.ctr",
        "gsc.position",
    ),
    "keywords": (
        "keywords.top5",
        "keywords.top10",
        "keywords.top20",
        "keywords.top30",
        "keywords.top50",
        "keywords.top100",
    ),
}

SEO_SOURCES = tuple(SEO_METRICS)

PERIOD_KEYS = (
    "start",
    "end",
    "previous_start",
    "previous_end",
)


def _reject(message):
    raise Problem(message, 409, "invalid_seo_composite")


def _date_value(value):
    if not isinstance(value, str):
        _reject("Ngay bao cao khong hop le.")

    try:
        parsed = date.fromisoformat(value)
        if parsed.isoformat() != value:
            raise ValueError
    except ValueError:
        _reject("Ngay bao cao phai dung YYYY-MM-DD.")

    return parsed


def build_seo_composite_draft(releases, *, client_id):
    """Create a non-publishable SEO composite object."""

    if (
        not isinstance(releases, dict)
        or set(releases) != set(SEO_SOURCES)
    ):
        _reject("Can du 3 Release: GA4, GSC, Keywords.")

    if not isinstance(client_id, str) or not client_id:
        _reject("Client ID khong hop le.")

    combined_sources = {}
    combined_widgets = []
    lineage = {}
    common_period = None

    for source in SEO_SOURCES:
        data = releases[source]

        if not isinstance(data, dict) or is_demo(data):
            _reject("Release khong hop le hoac la demo.")

        params = data.get("params")
        marketing = data.get("marketing")
        release = data.get("release")
        source_map = data.get("sources")

        if not all(
            isinstance(item, dict)
            for item in (
                params, marketing, release, source_map
            )
        ):
            _reject("Release thieu metadata bat buoc.")

        if (
            data.get("dataset_kind")
            != "marketing_release_snapshot_v1"
            or data.get("data_origin")
            != "provider_origin_confirmed"
            or data.get("client_id") != client_id
            or not isinstance(data.get("id"), str)
            or not data["id"]
        ):
            _reject("Release khong khop client hoac loai.")

        if (
            params.get("source") != source
            or params.get("report_type") != source
            or params.get("compare") is not True
            or set(source_map) != {source}
        ):
            _reject("Nguon Release khong khop.")

        source_data = source_map[source]

        if (
            not isinstance(source_data, dict)
            or source_data.get("source") != source
        ):
            _reject("Source payload khong hop le.")

        if (
            release.get("state") != "release_approved"
            or release.get("provider_origin_confirmed")
            is not True
            or release.get("quality") != "complete"
            or release.get("policy") != {
                "provisional": True,
                "final": True,
            }
            or not release.get("approval_id")
            or not release.get("seal")
        ):
            _reject("Release thieu metadata phe duyet.")

        period = {
            key: params.get(key)
            for key in PERIOD_KEYS
        }

        parsed = {
            key: _date_value(value)
            for key, value in period.items()
        }

        if (
            parsed["start"] > parsed["end"]
            or parsed["previous_start"]
            > parsed["previous_end"]
            or parsed["previous_end"] >= parsed["start"]
            or (
                parsed["end"] - parsed["start"]
            ).days != (
                parsed["previous_end"]
                - parsed["previous_start"]
            ).days
        ):
            _reject("Ky bao cao hoac so sanh khong hop le.")

        if common_period is None:
            common_period = period
        elif common_period != period:
            _reject("Ba Release khac ky bao cao.")

        if marketing.get("kind") != "approved_release":
            _reject("Thieu Marketing Release.")

        widgets = marketing.get("widgets")

        if not isinstance(widgets, list):
            _reject("Danh sach KPI khong hop le.")

        ids = []

        for widget in widgets:
            if not isinstance(widget, dict):
                _reject("KPI khong hop le.")

            metric_id = widget.get("metric_id")
            ids.append(metric_id)

            if (
                widget.get("value") is not None
                and (
                    widget.get("verified") is not True
                    or widget.get("publishable") is not True
                )
            ):
                _reject("KPI co gia tri chua duoc xac nhan.")

        if (
            len(ids) != len(set(ids))
            or set(ids) != set(SEO_METRICS[source])
        ):
            _reject("Danh sach KPI khong dung contract SEO.")

        combined_sources[source] = deepcopy(source_data)
        combined_widgets.extend(deepcopy(widgets))

        # This hash is only a structural reference.
        # It is NOT verification of the release seal.
        lineage[source] = {
            "dataset_id": data["id"],
            "content_sha256": sha(data),
            "approval_id": release["approval_id"],
        }

    return {
        "dataset_kind": "marketing_seo_composite_draft_v1",
        "data_origin": "internal_only",
        "publishable": False,
        "client_id": client_id,
        "params": {
            "report_type": "seo",
            "compare": True,
            **common_period,
        },
        "sources": combined_sources,
        "marketing": {
            "kind": "composite_draft",
            "widgets": combined_widgets,
        },
        "lineage": lineage,
    }
