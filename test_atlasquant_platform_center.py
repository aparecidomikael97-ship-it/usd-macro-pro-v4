import tempfile
import unittest
from pathlib import Path

from atlasquant_platform_center import pwa_asset_audit, platform_matrix, platform_status, PWA_URL

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


    def test_pwa_entry_point_is_https_github_pages(self):
        self.assertTrue(PWA_URL.startswith("https://"))
        self.assertIn("github.io",PWA_URL)

    def test_render_contract_can_report_native_prep_without_store_publication(self):
        from atlasquant_native_packaging import native_packaging_audit
        native=native_packaging_audit()
        self.assertTrue(native["preparation_ready"])
        self.assertFalse(native["native_store_publication_verified"])
        self.assertFalse(native["android_signed"])
        self.assertFalse(native["ios_signed"])

    def test_native_stores_are_not_falsely_marked_ready(self):
        rows=platform_matrix({"pwa_ready":True})
        by={r["Plataforma"]:r for r in rows}
        self.assertIn("PRONTO",by["Android"]["Distribuição atual"])
        self.assertEqual(by["Google Play"]["Distribuição atual"],"PENDENTE")
        self.assertEqual(by["Apple App Store"]["Distribuição atual"],"PENDENTE")


    def test_platform_status_distinguishes_pwa_from_native_store_readiness(self):
        self.assertEqual(platform_status({"pwa_ready":True})["label"],"PWA PRONTA")
        self.assertEqual(platform_status({"pwa_ready":False,"missing":["docs/sw.js"]})["label"],"PWA BLOQUEADA")
        self.assertIn("navegador",platform_status({"pwa_ready":True})["detail"])


if __name__=="__main__":
    unittest.main()
