import unittest

from atlasquant_publication_truth import publication_truth


SHA_A = "a" * 40
SHA_B = "b" * 40


class AtlasQuantPublicationTruthTests(unittest.TestCase):
    def test_source_bundle_without_commit_never_claims_live_main(self):
        out = publication_truth(
            environment="LOCAL",
            source_build="build-123",
        )
        self.assertEqual(out["state"], "SOURCE_BUNDLE_IDENTIFIED")
        self.assertEqual(out["main_match"], "UNKNOWN")
        self.assertFalse(out["can_claim_latest_main_live"])

    def test_runtime_commit_without_main_identity_stays_unverified(self):
        out = publication_truth(
            environment="RUNTIME",
            source_build="build-123",
            runtime_commit=SHA_A,
        )
        self.assertEqual(out["state"], "RUNTIME_IDENTIFIED_MAIN_UNKNOWN")
        self.assertEqual(out["runtime_identity"], "CONFIRMED")
        self.assertEqual(out["main_identity"], "UNKNOWN")
        self.assertFalse(out["can_claim_latest_main_live"])

    def test_runtime_mismatch_with_main_is_explicit(self):
        out = publication_truth(
            environment="PRODUCTION",
            source_build="build-123",
            runtime_commit=SHA_A,
            expected_main_commit=SHA_B,
        )
        self.assertEqual(out["state"], "RUNTIME_BEHIND_OR_DIVERGED")
        self.assertEqual(out["main_match"], "MISMATCH")
        self.assertFalse(out["can_claim_latest_main_live"])

    def test_matching_main_without_production_proof_is_not_live_claim(self):
        out = publication_truth(
            environment="PRODUCTION",
            source_build="build-123",
            runtime_commit=SHA_A,
            expected_main_commit=SHA_A,
        )
        self.assertEqual(out["state"], "MAIN_MATCH_PRODUCTION_UNVERIFIED")
        self.assertEqual(out["main_match"], "MATCH")
        self.assertEqual(out["production_verification"], "UNKNOWN")
        self.assertFalse(out["can_claim_latest_main_live"])

    def test_verified_production_and_complete_interface_can_claim_current_main_live(self):
        out = publication_truth(
            environment="PRODUCTION",
            source_build="build-123",
            runtime_commit=SHA_A,
            expected_main_commit=SHA_A,
            production_verified_commit=SHA_A,
            interface_validation={"all_confirmed_current_build": True},
        )
        self.assertEqual(out["state"], "PRODUCTION_VERIFIED")
        self.assertTrue(out["can_claim_latest_main_live"])
        self.assertTrue(out["can_claim_interface_validated"])
        self.assertFalse(out["automatic_deploy"])
        self.assertFalse(out["real_orders_enabled"])

    def test_verified_commit_does_not_replace_interface_validation(self):
        out = publication_truth(
            environment="PRODUCTION",
            runtime_commit=SHA_A,
            expected_main_commit=SHA_A,
            production_verified_commit=SHA_A,
            interface_validation={"all_confirmed_current_build": False},
        )
        self.assertEqual(out["state"], "PRODUCTION_VERIFIED_INTERFACE_PENDING")
        self.assertTrue(out["can_claim_latest_main_live"])
        self.assertFalse(out["can_claim_interface_validated"])

    def test_malformed_commit_is_ignored(self):
        out = publication_truth(
            runtime_commit="not-a-sha",
            expected_main_commit=SHA_A,
        )
        self.assertEqual(out["runtime_identity"], "UNKNOWN")
        self.assertEqual(out["main_match"], "UNKNOWN")
        self.assertFalse(out["can_claim_latest_main_live"])


if __name__ == "__main__":
    unittest.main()
