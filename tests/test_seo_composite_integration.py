
"""SEO composite integration with isolated SQLite QA database.

No real Google API, no production PostgreSQL,
and no mocked release signature validator.
"""

import json
import unittest

import test_marketing_verification as verification

from kdh.core import Problem, filters, pack
from kdh.report_bundles import _guard_marketing_snapshot
from kdh.seo_composite_loader import (
    build_seo_composite_from_store,
)


CLIENT_ID = "client_kinderhealth"

START = "2026-09-01"
END = "2026-09-03"
PREVIOUS_START = "2026-08-29"
PREVIOUS_END = "2026-08-31"


class SeoCompositeIntegrationTests(unittest.TestCase):

    def setUp(self):
        # Existing Admin fixture uses a temporary SQLite database.
        self.fx = verification.VerificationTests(
            "test_confirmed_source_and_comparison_then_approved_without_publication"
        )

        self.addCleanup(self.fx.doCleanups)
        self.fx.setUp()

        self.store = self.fx.store
        self.client = self.fx.client
        self.headers = self.fx.headers

        self.fx.app.config.update(
            KEYWORD_SPREADSHEET_ID="isolated-seo-sheet",
            KEYWORD_SHEET="Ranking",
        )

    @staticmethod
    def ga4_response(method, url, **kwargs):
        request_data = kwargs["json"]

        dimensions = [
            item["name"]
            for item in request_data.get("dimensions", [])
        ]

        # No channel/page breakdown needed for this QA case.
        if dimensions and dimensions != ["date"]:
            return {
                "rows": [],
                "metadata": {
                    "timeZone": "Asia/Ho_Chi_Minh"
                },
            }

        previous = (
            request_data["dateRanges"][0]["startDate"]
            == PREVIOUS_START
        )

        dates = (
            ["20260829", "20260830", "20260831"]
            if previous else
            ["20260901", "20260902", "20260903"]
        )

        metric_names = [
            item["name"]
            for item in request_data["metrics"]
        ]

        def make_row(day=None):
            values = (
                {
                    "activeUsers": 10,
                    "sessions": 20,
                    "screenPageViews": 30,
                    "engagementRate": 0.5,
                }
                if day is not None else
                {
                    "activeUsers": 22,
                    "sessions": 60,
                    "screenPageViews": 90,
                    "engagementRate": 0.5,
                }
            )

            return {
                "dimensionValues": (
                    [{"value": day}] if day else []
                ),
                "metricValues": [
                    {"value": str(values[name])}
                    for name in metric_names
                ],
            }

        return {
            "rows": (
                [make_row(day) for day in dates]
                if dimensions else
                [make_row()]
            ),
            "metadata": {
                "timeZone": "Asia/Ho_Chi_Minh"
            },
        }

    @staticmethod
    def keywords_response(method, url, **kwargs):
        return {
            "values": [
                ["keyword", "position", "date", "url"],
                [
                    "fixture-a", "5", END,
                    "https://fixture.example.test/a",
                ],
                [
                    "fixture-b", "15", END,
                    "https://fixture.example.test/b",
                ],
                [
                    "fixture-a", "12", PREVIOUS_END,
                    "https://fixture.example.test/a",
                ],
                [
                    "fixture-b", "17", PREVIOUS_END,
                    "https://fixture.example.test/b",
                ],
            ]
        }

    def google_transport(self, method, url, **kwargs):
        if "analyticsdata.googleapis.com" in url:
            return self.ga4_response(method, url, **kwargs)

        if "webmasters/v3/sites/" in url:
            return verification.VerificationTests.response(
                method, url, **kwargs
            )

        if "sheets.googleapis.com" in url:
            return self.keywords_response(
                method, url, **kwargs
            )

        raise AssertionError("Unexpected Google API URL")

    def create_release(self, source, asset_id):
        # 1. Create internal Marketing Dataset.
        response = self.client.post(
            "/api/marketing/datasets",
            json={
                "source": source,
                "start": START,
                "end": END,
                "compare_start": PREVIOUS_START,
                "compare_end": PREVIOUS_END,
                "asset_id": asset_id,
            },
            headers=self.headers,
        )

        self.assertEqual(
            response.status_code, 201, response.json
        )

        dataset_id = response.json["dataset_id"]

        # 2. Internal review.
        review = self.client.get(
            f"/api/marketing/datasets/{dataset_id}/review"
        ).json

        reviewed = self.client.post(
            f"/api/marketing/datasets/{dataset_id}/review",
            json={
                "decision": "approved_internal",
                "note": "SEO composite integration QA review.",
                "expected_sha256": review["dataset_sha256"],
            },
            headers=self.headers,
        )

        self.assertEqual(
            reviewed.status_code, 201, reviewed.json
        )

        # 3. Create release candidate.
        candidate = self.client.post(
            f"/api/marketing/datasets/{dataset_id}/release-candidates",
            json={
                "expected_sha256": review["dataset_sha256"],
                "expected_review_id": reviewed.json["review_id"],
            },
            headers=self.headers,
        )

        self.assertEqual(
            candidate.status_code, 201, candidate.json
        )

        candidate_id = candidate.json["release_dataset_id"]

        # 4. Verify source lineage.
        checks = self.fx.check(candidate_id)

        self.assertEqual(checks["issues"], [], checks)

        # 5. Approve the release.
        approved = self.fx.approve(candidate_id)

        self.assertEqual(
            approved.status_code, 201, approved.json
        )

        # 6. Create a sealed Release Snapshot.
        release = self.client.post(
            f"/api/marketing/release-candidates/{candidate_id}/release-snapshots",
            json={
                "expected_approval_id": approved.json["approval_id"],
                "expected_candidate_sha256": checks["candidate_sha256"],
            },
            headers=self.headers,
        )

        self.assertEqual(
            release.status_code, 201, release.json
        )

        return release.json["dataset_id"]

    def test_three_sealed_releases_build_internal_seo(self):
        # One SEO job syncs all three sources.
        self.fx.params = filters({
            "report_type": "seo",
            "start": START,
            "end": END,
            "compare": True,
        })

        self.fx.response = self.google_transport

        run = self.fx.sync()

        # Get real source asset IDs stored by the QA worker.
        rows = self.store.all(
            """
            SELECT
                ss.source_key,
                ss.asset_id,
                sr.id AS sync_id,
                sr.status
            FROM source_snapshots ss
            JOIN sync_runs sr
              ON sr.id = ss.sync_run_id
            WHERE sr.job_id=?
            """,
            (run["job_id"],),
        )

        assets = {
            row["source_key"]: row["asset_id"]
            for row in rows
        }

        self.assertEqual(
            set(assets),
            {"ga4", "gsc", "keywords"},
        )

        for row in rows:
            self.assertEqual(row["status"], "succeeded")

            attestation = self.store.one(
                """
                SELECT sync_run_id
                FROM source_attestations
                WHERE sync_run_id=?
                """,
                (row["sync_id"],),
            )

            self.assertIsNotNone(attestation)

        # Create three independently approved releases.
        release_ids = {
            source: self.create_release(
                source, assets[source]
            )
            for source in ("ga4", "gsc", "keywords")
        }

        before = self.store.one(
            "SELECT COUNT(*) AS n FROM datasets"
        )["n"]

        # No mock of validate_release_snapshot here.
        composite = build_seo_composite_from_store(
            self.store,
            release_ids,
            client_id=CLIENT_ID,
        )

        after = self.store.one(
            "SELECT COUNT(*) AS n FROM datasets"
        )["n"]

        self.assertEqual(before, after)

        self.assertEqual(
            set(composite["sources"]),
            {"ga4", "gsc", "keywords"},
        )

        self.assertEqual(
            len(composite["marketing"]["widgets"]),
            14,
        )

        keyword_ids = {
            widget["metric_id"]
            for widget in composite["marketing"]["widgets"]
            if widget["metric_id"].startswith("keywords.")
        }

        self.assertEqual(
            keyword_ids,
            {
                "keywords.top5",
                "keywords.top10",
                "keywords.top20",
                "keywords.top30",
                "keywords.top50",
                "keywords.top100",
            },
        )

        self.assertFalse(composite["publishable"])

        # Composite draft must remain blocked by existing guard.
        with self.assertRaises(Problem):
            _guard_marketing_snapshot({
                "sections": {
                    "seo": {"data": composite}
                }
            })

        # Tampering with a source release must invalidate its seal.
        row = self.store.one(
            "SELECT data FROM datasets WHERE id=?",
            (release_ids["keywords"],),
        )

        changed = json.loads(row["data"])
        changed["sources"]["keywords"]["totals"]["top30"] = 999

        self.store.execute(
            "UPDATE datasets SET data=? WHERE id=?",
            (pack(changed), release_ids["keywords"]),
        )

        with self.assertRaises(Problem):
            build_seo_composite_from_store(
                self.store,
                release_ids,
                client_id=CLIENT_ID,
            )


if __name__ == "__main__":
    unittest.main()
