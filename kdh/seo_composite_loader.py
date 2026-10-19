
"""Load and validate SEO source releases.

Read-only integration. No publishing or database writes.
"""

import json

from .core import Problem
from .marketing_publication import validate_release_snapshot
from .report_bundles import _check_no_credentials
from .seo_composite import (
    SEO_SOURCES,
    build_seo_composite_draft,
)


def _reject(message, code="invalid_seo_release"):
    raise Problem(message, 409, code)


def build_seo_composite_from_store(
    store,
    release_ids,
    *,
    client_id,
):
    """Build an internal SEO draft from stored, validated releases."""

    if (
        not isinstance(release_ids, dict)
        or set(release_ids) != set(SEO_SOURCES)
    ):
        _reject("Can du Release ID cua GA4, GSC, Keywords.")

    if not isinstance(client_id, str) or not client_id.strip():
        _reject("Client ID khong hop le.")

    ids = []

    for source in SEO_SOURCES:
        dataset_id = release_ids[source]

        if (
            not isinstance(dataset_id, str)
            or not 1 <= len(dataset_id) <= 128
        ):
            _reject("Release Dataset ID khong hop le.")

        ids.append(dataset_id)

    if len(set(ids)) != len(SEO_SOURCES):
        _reject("Khong duoc dung trung Release Dataset ID.")

    releases = {}

    # Keep all reads and verification in one transaction.
    with store.connect(immediate=True) as db:

        for source in SEO_SOURCES:
            dataset_id = release_ids[source]

            row = db.execute(
                """
                SELECT id, report_type, valid, data
                FROM datasets
                WHERE id=?
                """,
                (dataset_id,),
            ).fetchone()

            if not row:
                _reject(
                    "Khong tim thay Release Dataset.",
                    "release_not_found",
                )

            if (
                row["valid"] != 1
                or row["report_type"] != source
            ):
                _reject("Release chua hop le hoac sai nguon.")

            try:
                data = json.loads(row["data"])
            except (ValueError, TypeError):
                _reject("Release JSON khong hop le.")

            if (
                not isinstance(data, dict)
                or data.get("id") != row["id"]
                or data.get("client_id") != client_id
            ):
                _reject(
                    "Release khong khop Dataset hoac khach hang."
                )

            # Do not accept sensitive data in reporting payloads.
            _check_no_credentials(data)

            # IMPORTANT:
            # Verifies seal, content hash, release registry,
            # current approval and provider-origin evidence.
            validate_release_snapshot(
                data,
                store,
                db=db,
                publication=True,
            )

            releases[source] = data

        # The existing builder still produces an internal-only draft.
        composite = build_seo_composite_draft(
            releases,
            client_id=client_id,
        )

    return composite
