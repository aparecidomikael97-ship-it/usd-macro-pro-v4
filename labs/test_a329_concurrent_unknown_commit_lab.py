"""A329: preconnected rival must not create a second effect after ACK loss."""
import unittest

from labs.a329_concurrent_unknown_commit_lab import (
    SCHEMA, probe_unknown_commit_with_preconnected_rival,
)


class A329UnknownCommitCrossPIDTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = probe_unknown_commit_with_preconnected_rival()

    def assert_no_real_authority(self, r):
        self.assertEqual(r["schema"], SCHEMA)
        self.assertTrue(r["research_only"])
        self.assertTrue(r["synthetic_only"])
        self.assertTrue(r["real_native_sqlite_commit"])
        self.assertTrue(r["synthetic_ack_loss_only"])
        self.assertFalse(r["off_host_ledger_authenticated"])
        self.assertFalse(r["external_provider_ack_authenticated"])
        self.assertFalse(r["independent_writer_or_file_custody"])
        self.assertFalse(r["native_fd_vfs_wal_identity_attested"])
        self.assertFalse(r["power_loss_survival_proven"])
        self.assertFalse(r["cross_host_semantic_exactly_once_proven"])
        self.assertFalse(r["can_resume"])
        self.assertFalse(r["can_resend"])
        self.assertFalse(r["can_auto_retry"])
        self.assertFalse(r["can_authorize_real_effect"])
        self.assertEqual(r["automatic_retries"], 0)
        self.assertTrue(r["zero_auto_resend"])
        self.assertTrue(r["hard_no_go"])
        self.assertEqual(r["p0_homologated"], 0)
        self.assertTrue(r["no_worker_deploy_provider_orders"])
        self.assertFalse(r["new_paid_services"])

    def test_rival_opened_before_real_commit_fault(self):
        r = self.r
        self.assertTrue(r["other_process_open_before_fault"], repr(r))
        self.assertTrue(r["two_distinct_processes"])
        self.assert_no_real_authority(r)

    def test_real_commit_ack_loss_is_unknown_not_success_claim(self):
        r = self.r
        self.assertEqual(r["parent_fault_status"], "COMMIT_OUTCOME_UNKNOWN")
        self.assertEqual(
            r["parent_health_reason"],
            "COMMIT_OUTCOME_UNKNOWN_ZERO_AUTO_RETRY",
        )
        self.assert_no_real_authority(r)

    def test_parent_sticky_veto_and_pending_marker(self):
        r = self.r
        self.assertTrue(r["parent_pending_marker_before_release"])
        self.assertTrue(r["parent_retry_denied"])
        self.assertTrue(r["pending_marker_persisted"])
        self.assert_no_real_authority(r)

    def test_preconnected_other_pid_does_not_reack(self):
        r = self.r
        self.assertTrue(r["rival_did_not_reack"], repr(r))
        child = r["rival_report"]
        self.assertIn(
            child["status"], ("STORAGE_DENIED", "DUPLICATE_LOCAL_NO_EFFECT")
        )
        self.assertTrue(child["hard_no_go"])
        self.assertTrue(child["zero_auto_resend"])
        self.assertEqual(child["automatic_retries"], 0)
        self.assertEqual(child["p0_homologated"], 0)
        self.assert_no_real_authority(r)

    def test_sqlite_has_only_one_message_and_intent_receipt(self):
        r = self.r
        self.assertTrue(r["sqlite_integrity_ok"])
        self.assertEqual(r["final_message_count"], 1)
        self.assertEqual(r["final_intent_receipt_count"], 1)
        self.assert_no_real_authority(r)

    def test_fresh_strict_store_cannot_reopen_uncertain_commit(self):
        r = self.r
        self.assertTrue(r["fresh_strict_open_denied"])
        self.assertTrue(r["unknown_commit_quarantined_locally"])
        self.assertEqual(
            r["status"], "LAB_UNKNOWN_COMMIT_HOLD_WITH_PRECONNECTED_RIVAL"
        )
        self.assert_no_real_authority(r)

    def test_invalid_timeout_is_rejected_before_fixture(self):
        for bad in (None, True, 0, -1, 4, 41, "25", [], 4.5):
            with self.subTest(bad=repr(bad)):
                with self.assertRaises(ValueError):
                    probe_unknown_commit_with_preconnected_rival(
                        timeout_seconds=bad
                    )


if __name__ == "__main__":
    unittest.main()
