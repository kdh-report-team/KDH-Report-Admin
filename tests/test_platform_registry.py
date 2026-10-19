"""Contract checks for the metadata-only multi-platform source registry."""

import unittest

from kdh.metric_catalog import SOURCES
from kdh.platform_registry import PLATFORM_REGISTRY, SOURCE_TO_PLATFORM


class PlatformRegistryTests(unittest.TestCase):
    def test_required_source_ids_and_report_types_are_canonical(self):
        by_id = {item["id"]: item for item in PLATFORM_REGISTRY}
        self.assertEqual(set(by_id), {"seo_website", "facebook_content", "facebook_ads", "tiktok_ads"})
        self.assertEqual(by_id["facebook_content"]["sources"], ("facebook_content",))
        self.assertEqual(by_id["facebook_content"]["report_type"], "facebook-content")
        self.assertEqual(by_id["facebook_ads"]["sources"], ("facebook_ads",))
        self.assertEqual(by_id["facebook_ads"]["report_type"], "facebook-ads")
        self.assertEqual(by_id["seo_website"]["sources"], ("ga4", "gsc", "keywords"))
        for source in ("facebook_content", "facebook_ads", "tiktok_ads"):
            self.assertIn(source, SOURCES)
            self.assertIn(source, SOURCE_TO_PLATFORM)

    def test_tiktok_is_explicitly_scaffold_only(self):
        tiktok = next(item for item in PLATFORM_REGISTRY if item["id"] == "tiktok_ads")
        self.assertEqual(tiktok["integration"], "planned")
        self.assertEqual(tiktok["operations"], ())
        self.assertEqual(tiktok["reporting_periods"], ())
        self.assertIn("not implemented", tiktok["verification"])
        self.assertIn("not available", tiktok["dataset_readiness"])

    def test_meta_sources_do_not_share_report_or_asset_contracts(self):
        by_id = {item["id"]: item for item in PLATFORM_REGISTRY}
        content = by_id["facebook_content"]
        ads = by_id["facebook_ads"]
        self.assertNotEqual(content["asset_types"], ads["asset_types"])
        self.assertNotEqual(content["report_type"], ads["report_type"])
        self.assertIn("source_check", content["operations"])
        self.assertIn("source_check", ads["operations"])


if __name__ == "__main__":
    unittest.main()
