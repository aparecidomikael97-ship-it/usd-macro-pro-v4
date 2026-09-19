import tempfile
import unittest
from pathlib import Path

from atlasquant_platform_center import pwa_asset_audit, platform_matrix

class AtlasQuantPlatformCenterTests(unittest.TestCase):
    def test_current_repository_has_ready_pwa_assets(self):
        audit=pwa_asset_audit()
        self.assertTrue(audit["pwa_ready"])
        self.assertEqual(audit["missing"],[])

    def test_missing_assets_fail_closed(self):
        with tempfile.TemporaryDirectory() as td:
            audit=pwa_asset_audit(Path(td))
        self.assertFalse(audit["pwa_ready"])
        self.assertTrue(audit["missing"])

    def test_native_stores_are_not_falsely_marked_ready(self):
        rows=platform_matrix({"pwa_ready":True})
        by={r["Plataforma"]:r for r in rows}
        self.assertIn("PRONTO",by["Android"]["Distribuição atual"])
        self.assertEqual(by["Google Play"]["Distribuição atual"],"PENDENTE")
        self.assertEqual(by["Apple App Store"]["Distribuição atual"],"PENDENTE")

if __name__=="__main__":
    unittest.main()
