"""A327 only: A315 strict semantic idempotency under a full local DB restore.

The result intentionally exposes why a matching local pin and SQLite
integrity_check do not independently authorize recovery or resend.
"""
import unittest

from labs.a327_semantic_intent_rollback_lab import (
    SCHEMA, probe_full_host_rollback_strict_semantic_intent,
)


class A327StrictSemanticRollbackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.observation = probe_full_host_rollback_strict_semantic_intent()

    def assert_hard_no_go(self, result):
        self.assertEqual(result["schema"], SCHEMA)
        self.assertTrue(result["research_only"])
        self.assertTrue(result["synthetic_fixture_only"])
        self.assertTrue(result["native_sqlite_used"])
        self.assertTrue(result["strict_semantic_intent_enabled"])
        self.assertFalse(result["external_write_or_provider_effect"])
        self.assertFalse(result["independent_off_host_witness"])
        self.assertFalse(result["local_pin_is_authenticated"])
        self.assertFalse(result["native_vfs_fd_identity_attested"])
        self.assertFalse(result["real_power_loss_durability_proven"])
        self.assertFalse(result["p0_5_homologated"])
        self.assertFalse(result["p0_6_homologated"])
        self.assertEqual(result["p0_homologated"], 0)
        for name in (
            "can_restore_real_state", "can_resume", "can_replay",
            "can_resend", "can_auto_retry", "can_authorize_real_effect",
        ):
            self.assertFalse(result[name], name)
        self.assertEqual(result["automatic_retries"], 0)
        self.assertTrue(result["zero_auto_resend"])
        self.assertTrue(result["hard_no_go"])
        self.assertTrue(result["no_worker_deploy_provider_orders"])
        self.assertFalse(result["new_paid_services"])

    def test_initial_local_strict_intents_acked_once(self):
        r = self.observation
        self.assertEqual(r["first_local_status"], "LOCAL_ACKED_ONCE")
        self.assertEqual(r["second_local_status_before_rollback"], "LOCAL_ACKED_ONCE")
        self.assertEqual(r["current_intent_count_before_rollback"], 2)
        self.assertEqual(r["current_message_count_before_rollback"], 2)
        self.assert_hard_no_go(r)

    def test_normal_restart_deduplicates_intent(self):
        r = self.observation
        self.assertEqual(r["ordinary_restart_status"], "DUPLICATE_LOCAL_NO_EFFECT")
        self.assert_hard_no_go(r)

    def test_valid_native_sqlite_backup_has_older_history(self):
        r = self.observation
        self.assertTrue(r["old_snapshot_sqlite_integrity_ok"])
        self.assertTrue(r["fresh_sqlite_integrity_ok"])
        self.assertTrue(r["older_backup_accepted_by_sqlite_integrity_check"])
        self.assertEqual(r["old_snapshot_messages"], 1)
        self.assertEqual(r["old_snapshot_intents"], 1)
        self.assertEqual(r["restored_older_intent_count"], 1)
        self.assert_hard_no_go(r)

    def test_strict_mode_reopens_the_host_rolled_back_state(self):
        r = self.observation
        self.assertTrue(r["restored_strict_store_healthy_before_reack"])
        self.assert_hard_no_go(r)

    def test_same_semantic_intent_can_be_locally_reacked_after_rollback(self):
        r = self.observation
        self.assertEqual(r["second_local_status_before_rollback"], "LOCAL_ACKED_ONCE")
        self.assertEqual(r["ordinary_restart_status"], "DUPLICATE_LOCAL_NO_EFFECT")
        self.assertEqual(r["post_rollback_same_intent_status"], "LOCAL_ACKED_ONCE")
        self.assertTrue(r["local_semantic_reack_after_co_rollback"])
        self.assertEqual(r["message_count_after_reack"], 2)
        self.assertEqual(r["receipt_count_after_reack"], 2)
        self.assert_hard_no_go(r)

    def test_unmodified_local_pin_can_detect_but_not_guarantee_rollback(self):
        r = self.observation
        self.assertTrue(r["unchanged_local_pin_would_notice_rollback"])
        self.assertFalse(r["local_pin_is_authenticated"])
        self.assert_hard_no_go(r)

    def test_host_can_corollback_local_pin_to_hide_same_host_loss(self):
        r = self.observation
        self.assertTrue(r["co_rolled_local_pin_matches_old_state"])
        self.assertFalse(r["independent_off_host_witness"])
        self.assertFalse(r["can_restore_real_state"])
        self.assert_hard_no_go(r)


if __name__ == "__main__":
    unittest.main()
