"""A301 LAB negative recovery evidence contract; green is NOT GO."""
import unittest

from labs.a301_recovery_evidence_contract_lab import (
    SCHEMA, REQUIRED_MANIFEST_FIELDS, probe_recovery_manifest_matrix,
    assess_recovery_candidate,
)


class A301ManifestContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = probe_recovery_manifest_matrix()

    def test_real_sqlite_snapshots_not_mocks(self):
        self.assertTrue(self.m["real_sqlite_snapshots"])
        self.assertTrue(self.m["no_external_effects"])

    def test_contract_declares_all_evidence_fields(self):
        self.assertIn("db_sha256", REQUIRED_MANIFEST_FIELDS)
        self.assertIn("history_sha256", REQUIRED_MANIFEST_FIELDS)
        self.assertIn("intent_sha256", REQUIRED_MANIFEST_FIELDS)
        self.assertIn("pending_marker_sha256", REQUIRED_MANIFEST_FIELDS)
        self.assertIn("generation", REQUIRED_MANIFEST_FIELDS)

    def test_structurally_consistent_snapshot_cannot_resume(self):
        coherent = self.m["coherent"]
        self.assertEqual(coherent["schema"], SCHEMA)
        self.assertTrue(coherent["locally_consistent_only"])
        self.assertEqual(coherent["observed_messages"], 1)
        self.assertFalse(coherent["can_resume"])
        self.assertEqual(coherent["issues"], [
            "INDEPENDENT_CUSTODY_NOT_AUTHENTICATED"
        ])

    def test_self_signed_boolean_cannot_be_external_proof(self):
        case = self.m["fake_claim"]
        self.assertTrue(case["faked_custody_claim_ignored"])
        self.assertFalse(case["external_witness_verified"])
        self.assertFalse(case["can_resume"])
        self.assertTrue(case["locally_consistent_only"])

    def test_missing_semantic_intent_is_denied(self):
        self.assertIn(
            "INTENT_LEDGER_DOES_NOT_COVER_SQLITE_HISTORY",
            self.m["missing_intent"]["issues"],
        )
        self.assertIn(
            "INTENT_LEDGER_DIGEST_MISMATCH",
            self.m["missing_intent"]["issues"],
        )

    def test_duplicate_semantic_effect_is_denied(self):
        self.assertIn(
            "INTENT_DUPLICATE_SEMANTIC_EFFECT",
            self.m["duplicate_intent"]["issues"],
        )
        self.assertFalse(self.m["duplicate_intent"]["can_resume"])

    def test_wrong_database_digest_is_denied(self):
        self.assertIn(
            "SNAPSHOT_MISMATCH_DB_SHA256",
            self.m["wrong_hash"]["issues"],
        )

    def test_stale_generation_is_denied(self):
        self.assertIn(
            "GENERATION_STALE_OR_INVALID",
            self.m["stale"]["issues"],
        )

    def test_wrong_source_identity_is_denied(self):
        self.assertIn(
            "SOURCE_ID_MISMATCH",
            self.m["wrong_source"]["issues"],
        )

    def test_missing_manifest_fields_are_denied(self):
        self.assertIn(
            "MANIFEST_MISSING_OR_MALFORMED",
            self.m["malformed"]["issues"],
        )

    def test_database_modified_after_manifest_is_denied(self):
        case = self.m["tampered_db"]
        self.assertIn("SNAPSHOT_MISMATCH_DB_SHA256", case["issues"])
        self.assertIn("SNAPSHOT_MISMATCH_HISTORY_SHA256", case["issues"])

    def test_local_pending_marker_is_detected_but_not_trusted(self):
        case = self.m["uncertain_marker_present"]
        self.assertTrue(case["locally_consistent_only"])
        self.assertFalse(case["can_resume"])

    def test_ack_unknown_marker_lost_in_relocation_is_denied(self):
        case = self.m["uncertain_marker_lost"]
        self.assertIn("UNCERTAIN_ACK_MARKER_MISSING", case["issues"])
        self.assertIn("PENDING_MARKER_BINDING_MISMATCH", case["issues"])
        self.assertFalse(case["can_resume"])

    def test_old_snapshot_and_self_manifest_cannot_prove_freshness(self):
        case = self.m["old_self_attested_rollback"]
        self.assertTrue(case["locally_consistent_only"])
        self.assertEqual(case["observed_messages"], 0)
        self.assertFalse(case["can_resume"])
        self.assertIn(
            "INDEPENDENT_CUSTODY_NOT_AUTHENTICATED", case["issues"]
        )

    def test_full_negative_matrix_never_authorizes(self):
        for name, case in self.m.items():
            if not isinstance(case, dict):
                continue
            with self.subTest(candidate=name):
                self.assertFalse(case["can_resume"])
                self.assertFalse(case["can_authorize_real_effect"])
                self.assertFalse(case["external_witness_verified"])
                self.assertFalse(case["authenticated_native_fd"])
                self.assertEqual(case["p0_homologated"], 0)
                self.assertTrue(case["hard_no_go"])
                self.assertTrue(case["zero_auto_resend"])
                self.assertEqual(case["automatic_retries"], 0)
                self.assertTrue(case["no_new_paid_services"])
                self.assertTrue(case["no_provider_worker_deploy_orders"])


class A301MalformedInputTests(unittest.TestCase):
    def test_invalid_path_is_fail_closed_without_io(self):
        case = assess_recovery_candidate(
            "not-a-path", "cid", [], {}, expected_source_id="host",
            min_generation=1,
        )
        self.assertFalse(case["can_resume"])
        self.assertTrue(any(
            x.startswith("SQLITE_CANDIDATE_REJECTED:")
            for x in case["issues"]
        ))

    def test_boolean_generation_floor_is_invalid(self):
        case = assess_recovery_candidate(
            "not-a-path", "cid", [], {}, expected_source_id="host",
            min_generation=True,
        )
        self.assertIn("GENERATION_FLOOR_INVALID", case["issues"])
        self.assertFalse(case["can_resume"])

    def test_wrong_ledger_type_is_invalid(self):
        case = assess_recovery_candidate(
            "not-a-path", "cid", "not-list", {},
            expected_source_id="host", min_generation=1,
        )
        self.assertIn("INTENT_LEDGER_INVALID", case["issues"])
        self.assertFalse(case["can_resume"])


if __name__ == "__main__":
    unittest.main()
