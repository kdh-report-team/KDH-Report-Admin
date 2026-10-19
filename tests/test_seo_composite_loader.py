
import unittest
from contextlib import contextmanager
from unittest.mock import patch

from kdh.core import Problem, pack
from kdh.seo_composite_loader import (
    build_seo_composite_from_store,
)
from test_seo_composite import CLIENT, make_releases


class FakeCursor:
    def __init__(self, row):
        self.row = row

    def fetchone(self):
        return self.row


class FakeDB:
    def __init__(self, rows):
        self.rows = rows
        self.queries = []

    def execute(self, sql, args):
        if "FROM datasets" not in sql:
            raise AssertionError("Unexpected database query")

        self.queries.append(args[0])

        return FakeCursor(self.rows.get(args[0]))


class FakeStore:
    def __init__(self, rows):
        self.db = FakeDB(rows)

    @contextmanager
    def connect(self, immediate=False):
        yield self.db


class SeoCompositeLoaderTests(unittest.TestCase):

    def setUp(self):
        self.releases = make_releases()

        self.ids = {
            source: data["id"]
            for source, data in self.releases.items()
        }

        rows = {}

        for source, data in self.releases.items():
            rows[data["id"]] = {
                "id": data["id"],
                "report_type": source,
                "valid": 1,
                "data": pack(data),
            }

        self.store = FakeStore(rows)

    def build(self, release_ids=None):
        return build_seo_composite_from_store(
            self.store,
            release_ids if release_ids is not None
            else self.ids,
            client_id=CLIENT,
        )

    def test_loads_all_three_releases(self):
        # Isolate database logic from cryptographic validation.
        # Production code never mocks this verifier.
        with patch(
            "kdh.seo_composite_loader.validate_release_snapshot"
        ) as verifier:

            result = self.build()

            self.assertEqual(verifier.call_count, 3)

            for call in verifier.call_args_list:
                self.assertIs(call.args[1], self.store)
                self.assertIs(call.kwargs["db"], self.store.db)
                self.assertIs(
                    call.kwargs["publication"],
                    True,
                )

        self.assertEqual(
            len(result["marketing"]["widgets"]),
            14,
        )

        self.assertEqual(
            set(result["sources"]),
            {"ga4", "gsc", "keywords"},
        )

        self.assertFalse(result["publishable"])

    def test_missing_release_rejected(self):
        ids = dict(self.ids)
        ids["gsc"] = "missing-release"

        with self.assertRaises(Problem):
            self.build(ids)

    def test_duplicate_release_id_rejected(self):
        ids = dict(self.ids)
        ids["gsc"] = ids["ga4"]

        with self.assertRaises(Problem):
            self.build(ids)

    def test_invalid_dataset_rejected(self):
        row = self.store.db.rows[self.ids["gsc"]]
        row["valid"] = 0

        with self.assertRaises(Problem):
            self.build()

    def test_wrong_report_type_rejected(self):
        row = self.store.db.rows[self.ids["keywords"]]
        row["report_type"] = "ga4"

        with self.assertRaises(Problem):
            self.build()

    def test_wrong_client_rejected(self):
        data = dict(self.releases["ga4"])
        data["client_id"] = "another-client"

        self.store.db.rows[self.ids["ga4"]]["data"] = pack(data)

        with self.assertRaises(Problem):
            self.build()

    def test_fake_seal_cannot_pass_real_verifier(self):
        # No mock here: placeholder signatures must be rejected.
        with self.assertRaises(Problem) as error:
            self.build()

        self.assertEqual(
            error.exception.code,
            "marketing_review_required",
        )

    def test_stale_approval_blocks_composite(self):
        with patch(
            "kdh.seo_composite_loader.validate_release_snapshot",
            side_effect=Problem(
                "Approval is stale",
                409,
                "stale_release_approval",
            ),
        ):
            with self.assertRaises(Problem) as error:
                self.build()

        self.assertEqual(
            error.exception.code,
            "stale_release_approval",
        )


if __name__ == "__main__":
    unittest.main()
