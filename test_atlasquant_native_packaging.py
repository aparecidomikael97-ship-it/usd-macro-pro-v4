import tempfile
import unittest
from pathlib import Path

from atlasquant_native_packaging import native_packaging_audit

class AtlasQuantNativePackagingTests(unittest.TestCase):
    def test_repository_native_packaging_preparation_is_ready(self):
        status=native_packaging_audit()
        self.assertTrue(status["preparation_ready"])
        self.assertTrue(status["metadata_ok"])
        self.assertEqual(status["missing"],[])

    def test_native_store_state_remains_fail_closed(self):
        status=native_packaging_audit()
        self.assertFalse(status["android_signed"])
        self.assertFalse(status["ios_signed"])
        self.assertFalse(status["native_store_publication_verified"])
        self.assertTrue(status["pwa_remains_current_distribution"])
        self.assertFalse(status["signing_secrets_in_repo"])
        self.assertFalse(status["real_orders_changed"])

    def test_missing_native_metadata_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            status=native_packaging_audit(Path(td))
        self.assertFalse(status["preparation_ready"])
        self.assertTrue(status["missing"])
        self.assertFalse(status["native_store_publication_verified"])

if __name__=="__main__":
    unittest.main()
