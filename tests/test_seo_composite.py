
import unittest
from copy import deepcopy

from kdh.core import Problem
from kdh.report_bundles import _guard_marketing_snapshot
from kdh.seo_composite import (
    SEO_METRICS,
    build_seo_composite_draft,
)


CLIENT = "client_kinderhealth"

PERIOD = {
    "start": "2026-09-01",
    "end": "2026-09-30",
    "previous_start": "2026-08-02",
    "previous_end": "2026-08-31",
}


def make_release(source):
    return {
        "id": "qa-release-" + source,
        "client_id": CLIENT,
        "dataset_kind": "marketing_release_snapshot_v1",
        "data_origin": "provider_origin_confirmed",
        "params": {
            "report_type": source,
            "source": source,
            "compare": True,
            **PERIOD,
        },
        "sources": {
            source: {
                "source": source,
                "status": "ready",
                "totals": {},
            },
        },
        "marketing": {
            "kind": "approved_release",
            "widgets": [
                {
                    "metric_id": metric_id,
                    "value": 10,
                    "verified": True,
                    "publishable": True,
                }
                for metric_id in SEO_METRICS[source]
            ],
        },
        "release": {
            "state": "release_approved",
            "provider_origin_confirmed": True,
            "quality": "complete",
            "policy": {
                "provisional": True,
                "final": True,
            },
            "approval_id": "qa-approval-" + source,
            "seal": "placeholder-not-a-real-signature",
        },
    }


def make_releases():
    return {
        source: make_release(source)
        for source in SEO_METRICS
    }


class SeoCompositeTests(unittest.TestCase):

    def build(self, releases=None):
        return build_seo_composite_draft(
            releases if releases is not None
            else make_releases(),
            client_id=CLIENT,
        )

    def test_three_sources_fourteen_metrics(self):
        result = self.build()

        self.assertEqual(
            set(result["sources"]),
            {"ga4", "gsc", "keywords"},
        )

        self.assertEqual(
            len(result["marketing"]["widgets"]),
            14,
        )

        self.assertEqual(
            result["params"]["report_type"],
            "seo",
        )

        self.assertEqual(
            set(result["lineage"]),
            {"ga4", "gsc", "keywords"},
        )

        self.assertFalse(result["publishable"])

    def test_input_is_not_modified(self):
        releases = make_releases()
        before = deepcopy(releases)

        result = self.build(releases)
        result["sources"]["ga4"]["totals"]["x"] = 999

        self.assertEqual(releases, before)

    def test_missing_source_rejected(self):
        releases = make_releases()
        del releases["keywords"]

        with self.assertRaises(Problem):
            self.build(releases)

    def test_wrong_client_rejected(self):
        releases = make_releases()
        releases["gsc"]["client_id"] = "other-client"

        with self.assertRaises(Problem):
            self.build(releases)

    def test_wrong_period_rejected(self):
        releases = make_releases()
        releases["keywords"]["params"]["end"] = "2026-09-29"

        with self.assertRaises(Problem):
            self.build(releases)

    def test_unapproved_release_rejected(self):
        releases = make_releases()
        releases["ga4"]["release"]["state"] = "pending"

        with self.assertRaises(Problem):
            self.build(releases)

    def test_unverified_kpi_rejected(self):
        releases = make_releases()
        releases["gsc"]["marketing"]["widgets"][0]["verified"] = False

        with self.assertRaises(Problem):
            self.build(releases)

    def test_missing_metric_rejected(self):
        releases = make_releases()
        releases["keywords"]["marketing"]["widgets"].pop()

        with self.assertRaises(Problem):
            self.build(releases)

    def test_composite_cannot_be_published(self):
        composite = self.build()

        bundle = {
            "sections": {
                "seo": {"data": composite}
            }
        }

        with self.assertRaises(Problem) as error:
            _guard_marketing_snapshot(bundle)

        self.assertEqual(
            error.exception.code,
            "marketing_review_required",
        )


if __name__ == "__main__":
    unittest.main()
