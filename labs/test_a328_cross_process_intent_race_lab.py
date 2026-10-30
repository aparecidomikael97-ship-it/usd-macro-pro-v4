"""A328 tests: two OS processes race on the same synthetic local intent.

Local single-effect evidence is not independent authority or P0 closure.
"""
import unittest

from labs.a328_cross_process_intent_race_lab import (
    SCHEMA, probe_two_process_same_intent,
)


class A328TwoProcessIntentRaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.observation = probe_two_process_same_intent()

    def assert_no_real_authority(self, r):
        self.assertEqual(r["schema"], SCHEMA)
        self.assertTrue(r["research_only"])
        self.assertTrue(r["synthetic_fixture_only"])
        self.assertTrue(r["strict_semantic_intent_enabled"])
        self.assertFalse(r["independent_writer_authority"])
        self.assertFalse(r["off_host_high_water_custody"])
        self.assertFalse(r["native_sqlite_vfs_fd_identity_verified"])
        self.assertFalse(r["operational_cross_host_exactly_once"])
        self.assertFalse(r["provider_effect_or_ack_verified"])
        self.assertFalse(r["power_loss_durability_proven"])
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

    def test_both_children_reached_bounded_barrier(self):
        r = self.observation
        self.assertTrue(r["both_ready_at_release"], repr(r))
        self.assertTrue(r["actual_distinct_processes_used"])
        self.assertEqual(len(r["child_reports"]), 2)
        self.assert_no_real_authority(r)

    def test_exactly_one_local_ack_for_same_semantic_intent(self):
        r = self.observation
        self.assertEqual(r["local_acked_count"], 1, repr(r))
        self.assertEqual(r["child_error_count"], 0)
        self.assertEqual(
            r["local_duplicate_count"] + r["local_denial_count"], 1
        )
        self.assert_no_real_authority(r)

    def test_final_sqlite_contains_one_message_and_one_receipt(self):
        r = self.observation
        self.assertTrue(r["sqlite_quick_check_ok"])
        self.assertEqual(r["message_count"], 1)
        self.assertEqual(r["intent_receipt_count"], 1)
        self.assert_no_real_authority(r)

    def test_every_child_has_no_authorization_even_when_acked(self):
        r = self.observation
        for child in r["child_reports"]:
            with self.subTest(pid=child.get("pid")):
                self.assertIn(child["status"], (
                    "LOCAL_ACKED_ONCE", "DUPLICATE_LOCAL_NO_EFFECT",
                    "STORAGE_DENIED",
                ))
                self.assertTrue(child["hard_no_go"])
                self.assertTrue(child["zero_auto_resend"])
                self.assertEqual(child["automatic_retries"], 0)
                self.assertEqual(child["p0_homologated"], 0)
        self.assert_no_real_authority(r)

    def test_positive_local_race_still_blocks_p0_5_and_p0_6(self):
        r = self.observation
        self.assertEqual(r["status"], "LAB_ONE_LOCAL_ACK_NO_OPERATIONAL_AUTHORITY")
        self.assertTrue(r["same_intent_single_local_effect_observed"])
        self.assert_no_real_authority(r)

    def test_invalid_timeout_never_launches_children(self):
        for bad in (None, True, 0, -1, 4, 41, "25", [], 2.0):
            with self.subTest(bad=repr(bad)):
                with self.assertRaises(ValueError):
                    probe_two_process_same_intent(timeout_seconds=bad)

    def test_local_experiment_does_not_claim_rollback_protection(self):
        r = self.observation
        self.assertFalse(r["off_host_high_water_custody"])
        self.assertFalse(r["power_loss_durability_proven"])
        self.assertFalse(r["operational_cross_host_exactly_once"])
        self.assert_no_real_authority(r)


if __name__ == "__main__":
    unittest.main()
