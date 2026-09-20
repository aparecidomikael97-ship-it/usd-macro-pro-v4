import tempfile
import unittest
from pathlib import Path

from atlasquant_finalization_audit import finalization_audit

class AtlasQuantFinalizationAuditTests(unittest.TestCase):
    def test_internal_release_preparation_is_complete(self):
        status=finalization_audit()
        self.assertTrue(status["internal_release_preparation_complete"])
        self.assertTrue(status["handoff_docs_complete"])
        self.assertEqual(status["missing_handoff_docs"],[])

    def test_external_completion_remains_fail_closed(self):
        status=finalization_audit()
        self.assertFalse(status["external_dependencies_complete"])
        self.assertFalse(status["public_launch_ready"])
        self.assertFalse(status["real_orders_enabled"])
        self.assertFalse(status["broker_execution_enabled"])
        self.assertFalse(status["automatic_public_launch"])
        self.assertTrue(status["manual_external_completion_required"])

    def test_strategy_safety_invariants_remain_fail_closed(self):
        status=finalization_audit()
        self.assertFalse(status["automatic_strategy_changes_enabled"])
        self.assertFalse(status["automatic_weight_changes_enabled"])
        self.assertFalse(status["small_sample_auto_promotion_enabled"])
        self.assertTrue(status["human_strategy_review_required"])

    def test_fast_home_contract_is_safe_and_fail_closed(self):
        status=finalization_audit()
        fast=status["fast_home_contract"]
        self.assertEqual(fast["snapshot_max_age_min"],90.0)
        self.assertTrue(fast["snapshot_required_for_fast_path"])
        self.assertTrue(fast["fallback_to_full_app"])
        self.assertFalse(fast["real_orders_enabled"])
        self.assertFalse(fast["automatic_execution"])

    def test_external_release_evidence_is_explicit_and_fail_closed(self):
        status=finalization_audit()
        evidence=status["external_evidence"]
        self.assertFalse(status["external_evidence_complete"])
        self.assertFalse(evidence["production_admin_secret_configured"])
        self.assertFalse(evidence["neural_tts_provider_ready"])
        self.assertFalse(evidence["academy_videos_published"])
        self.assertFalse(evidence["commercial_data_licenses_verified"])
        self.assertFalse(evidence["native_store_publication_verified"])

    def test_missing_handoff_docs_blocks_internal_completion(self):
        with tempfile.TemporaryDirectory() as td:
            status=finalization_audit(Path(td))
        self.assertFalse(status["handoff_docs_complete"])
        self.assertFalse(status["internal_release_preparation_complete"])
        self.assertFalse(status["public_launch_ready"])

if __name__=="__main__":
    unittest.main()
