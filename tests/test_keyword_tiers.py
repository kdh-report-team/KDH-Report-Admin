
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from kdh.google import Google


class KeywordTierTests(unittest.TestCase):

    def test_six_keyword_tiers(self):
        positions = [
            1, 5, 6, 10, 11, 20,
            21, 30, 31, 50, 51, 100, 101
        ]

        values = [
            ["keyword", "position", "date", "url"]
        ]

        for index, position in enumerate(positions):
            values.append([
                f"keyword-{index}",
                str(position),
                "2026-09-30",
                f"https://example.test/page-{index}",
            ])

        fake_google = SimpleNamespace(
            config={
                "KEYWORD_SHEET": "Ranking",
                "KEYWORD_SPREADSHEET_ID": "test-sheet",
            }
        )

        params = {
            "start": "2026-09-01",
            "end": "2026-09-30",
            "compare": False,
        }

        with patch(
            "kdh.google.call",
            return_value={"values": values},
        ):
            result = Google.keywords(
                fake_google,
                params,
                {},
            )

        self.assertEqual(
            result["totals"],
            {
                "top5": 2,
                "top10": 4,
                "top20": 6,
                "top30": 8,
                "top50": 10,
                "top100": 12,
            },
        )


if __name__ == "__main__":
    unittest.main()
