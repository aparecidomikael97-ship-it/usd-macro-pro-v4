import json
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parent

class AtlasQuantPWAAssetsTests(unittest.TestCase):
    def test_manifest_has_installable_identity_and_icons(self):
        manifest=json.loads((ROOT/"docs"/"manifest.webmanifest").read_text(encoding="utf-8"))
        self.assertEqual(manifest["name"],"AtlasQuant")
        self.assertEqual(manifest["id"],"./")
        self.assertEqual(manifest["start_url"],"./")
        self.assertEqual(manifest["display"],"standalone")
        self.assertEqual(manifest["lang"],"pt-BR")
        sizes={x.get("sizes") for x in manifest.get("icons",[])}
        self.assertTrue({"192x192","512x512","180x180"}.issubset(sizes))
        for icon in manifest["icons"]:
            self.assertTrue((ROOT/"docs"/icon["src"]).is_file())

    def test_service_worker_only_runtime_caches_successful_gets(self):
        src=(ROOT/"docs"/"sw.js").read_text(encoding="utf-8")
        self.assertIn('event.request.method === "GET"',src)
        self.assertIn("response.ok",src)
        self.assertIn('event.request.mode === "navigate"',src)
        self.assertNotIn('url.origin !== self.location.origin',src)


    def test_shell_exposes_network_status_without_caching_private_app(self):
        src=(ROOT/"docs"/"index.html").read_text(encoding="utf-8")
        self.assertIn('id="status"',src)
        self.assertIn('window.addEventListener("offline"',src)
        self.assertIn('window.addEventListener("online"',src)
        self.assertIn('referrerpolicy="no-referrer"',src)
        sw=(ROOT/"docs"/"sw.js").read_text(encoding="utf-8")
        self.assertIn("url.origin === self.location.origin",sw)

    def test_shell_references_manifest_service_worker_and_private_app(self):
        src=(ROOT/"docs"/"index.html").read_text(encoding="utf-8")
        self.assertIn('rel="manifest"',src)
        self.assertIn('navigator.serviceWorker.register("./sw.js")',src)
        self.assertIn("atlasquant-private.onrender.com",src)
        self.assertIn('rel="noopener"',src)

if __name__=="__main__":
    unittest.main()
