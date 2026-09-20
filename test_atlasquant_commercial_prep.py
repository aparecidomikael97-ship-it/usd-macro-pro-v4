import tempfile
import unittest
from pathlib import Path

from atlasquant_commercial_prep import (
    commercial_external_blockers,
    commercial_prep_audit,
)

class AtlasQuantCommercialPrepTests(unittest.TestCase):
    def test_repository_has_complete_internal_prep_pack(self):
        status=commercial_prep_audit()
        self.assertTrue(status["internal_prep_ready"])
        self.assertTrue(status["legal_drafts_ready"])
        self.assertTrue(status["data_licensing_checklist_ready"])
        self.assertTrue(status["billing_checklist_ready"])
        self.assertTrue(status["store_checklist_ready"])

    def test_internal_prep_never_fakes_external_completion(self):
        status=commercial_prep_audit()
        self.assertFalse(status["legal_review_verified"])
        self.assertFalse(status["data_licensing_verified"])
        self.assertFalse(status["billing_integrated"])
        self.assertFalse(status["native_store_published"])
        self.assertFalse(status["public_launch_ready"])
        self.assertFalse(status["automatic_launch"])
        self.assertFalse(status["trading_permission_changed"])

    def test_missing_pack_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            status=commercial_prep_audit(Path(td))
        self.assertFalse(status["internal_prep_ready"])
        self.assertTrue(status["missing"])
        self.assertFalse(status["public_launch_ready"])

    def test_external_blockers_remain_explicit(self):
        blockers=" ".join(commercial_external_blockers()).casefold()
        self.assertIn("primeiro admin",blockers)
        self.assertIn("produção",blockers)
        self.assertIn("revisão jurídica",blockers)
        self.assertIn("licenciamento comercial",blockers)
        self.assertIn("pagamento",blockers)
        self.assertIn("lojas nativas",blockers)
        self.assertIn("vídeos da academy",blockers)
        self.assertIn("tts",blockers)

if __name__=="__main__":
    unittest.main()
