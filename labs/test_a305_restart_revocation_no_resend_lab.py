"""A305 LAB: real SQLite uncertain ACK and synthetic revoked recovery proof.

All passing tests are negative security characterization, not P0 closure.
"""
import copy
import unittest

from labs.a302_witness_receipt_contract_lab import _encoded, _hash
from labs.test_a304_custodian_status_lab import (
    fixture as a304_fixture, sign,
)
from labs.a305_restart_revocation_no_resend_lab import (
    SCHEMA, INTENT_ID, MESSAGE_ID,
    probe_sqlite_restart_ack_loss, assess_restart_attempt,
)


def later_status(inputs, key, decision="REVOKED"):
    """Build post-restart signed successor, with previous signed hash."""
    earlier = inputs["statuses"][0]
    successor = sign(
        earlier, key, decision=decision,
        status_sequence=earlier["status_sequence"] + 1,
        previous_status_hash=_hash(_encoded(earlier)),
    )
    return dict(
        inputs,
        statuses=[successor],
        trusted_status_head={
            "sequence": earlier["status_sequence"],
            "status_hash": _hash(_encoded(earlier)),
        },
    )


class A305RealSQLiteRestartTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.observation = probe_sqlite_restart_ack_loss()

    def test_actual_sqlite_commit_was_applied_despite_lost_ack(self):
        o = self.observation
        self.assertTrue(o["real_sqlite_db"])
        self.assertTrue(o["uncertain_error_raised"])
        self.assertEqual(o["sqlite_effect_count"], 1)
        self.assertEqual(o["ack_state"], "ACK_UNKNOWN")

    def test_original_restart_denies_pending_commit_marker(self):
        o = self.observation
        self.assertTrue(o["source_pending_marker"])
        self.assertTrue(o["source_reopen_refused"])
        self.assertEqual(o["source_failure_reason"],
                         "COMMIT_OUTCOME_UNKNOWN_ZERO_AUTO_RETRY")

    def test_relocated_database_loses_marker_but_looks_healthy(self):
        o = self.observation
        self.assertTrue(o["relocated_marker_absent"])
        self.assertTrue(o["relocated_appears_healthy"])
        self.assertTrue(o["relocated_contains_effect"])

    def test_no_restore_or_auto_retry_executed(self):
        o = self.observation
        self.assertTrue(o["disposable_fixture"])
        self.assertTrue(o["no_restore_api_invoked"])
        self.assertTrue(o["no_retries_performed"])
        self.assertFalse(o["host_native_fd_attested"])
        self.assertFalse(o["off_host_custody_attested"])
        self.assertEqual(o["message_id"], MESSAGE_ID)


class A305PostRestartStatusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.observation = probe_sqlite_restart_ack_loss()

    def setUp(self):
        self.before, self.status_key, _ = a304_fixture()
        self.after = later_status(self.before, self.status_key)

    def assess(self, **overrides):
        params = {
            "observation": self.observation,
            "before_status_inputs": self.before,
            "after_status_inputs": self.after,
            "previous_incident_epoch": 4,
            "recovery_incident_epoch": 5,
            "requested_effect": "RESUME",
        }
        params.update(overrides)
        return assess_restart_attempt(**params)

    def test_signed_revocation_after_restart_blocks_recovery(self):
        r = self.assess()
        self.assertTrue(r["before_status_cryptographic"])
        self.assertTrue(r["after_status_cryptographic"])
        self.assertTrue(r["signed_status_advanced"])
        self.assertTrue(r["post_restart_revocation_seen"])
        self.assertIn("SIGNED_REVOCATION_BLOCKS_RECOVERY", r["issues"])
        self.assertFalse(r["can_resume"])

    def test_active_before_crash_does_not_override_signed_revocation(self):
        r = self.assess()
        self.assertIn("AFTER_CUSTODIAN_REVOKED", r["issues"])
        self.assertTrue(r["commit_ack_unknown"])

    def test_real_ack_uncertainty_forbids_auto_retry(self):
        r = self.assess(requested_effect="RESEND")
        self.assertIn("COMMIT_OUTCOME_UNKNOWN_ZERO_AUTO_RETRY", r["issues"])
        self.assertIn("OPERATIONAL_RECOVERY_FORBIDDEN", r["issues"])
        self.assertFalse(r["can_auto_retry"])
        self.assertEqual(r["automatic_retries"], 0)

    def test_fresh_signed_active_status_still_does_not_resolve_uncertain_ack(self):
        later_active = later_status(self.before, self.status_key, "ACTIVE")
        r = self.assess(after_status_inputs=later_active)
        self.assertTrue(r["after_status_cryptographic"])
        self.assertTrue(r["signed_status_advanced"])
        self.assertFalse(r["post_restart_revocation_seen"])
        self.assertIn("COMMIT_OUTCOME_UNKNOWN_ZERO_AUTO_RETRY", r["issues"])
        self.assertFalse(r["can_resume"])

    def test_cached_pre_restart_active_status_cannot_be_reused(self):
        r = self.assess(after_status_inputs=self.before)
        self.assertIn("CACHED_OR_NONSEQUENTIAL_STATUS_AFTER_RESTART",
                      r["issues"])
        self.assertFalse(r["signed_status_advanced"])

    def test_signed_suspension_also_blocks_restart(self):
        later_suspended = later_status(self.before, self.status_key,
                                       "SUSPENDED")
        r = self.assess(after_status_inputs=later_suspended)
        self.assertIn("SIGNED_SUSPENSION_BLOCKS_RECOVERY", r["issues"])
        self.assertTrue(r["post_restart_suspension_seen"])

    def test_post_restart_custodian_offline_is_denied(self):
        r = self.assess(after_status_inputs=dict(
            self.after, custodian_online=False))
        self.assertIn("AFTER_CUSTODIAN_UNAVAILABLE", r["issues"])

    def test_missing_fresh_status_is_denied(self):
        r = self.assess(after_status_inputs=dict(self.after, statuses=[]))
        self.assertIn("AFTER_STATUS_NOT_SINGULAR_AND_SIGNED", r["issues"])
        self.assertIn("POST_RESTART_STATUS_NOT_AUTHENTICATED", r["issues"])

    def test_forked_signed_active_and_revoked_status_denied(self):
        active = later_status(self.before, self.status_key, "ACTIVE")
        both = dict(self.after, statuses=[
            self.after["statuses"][0], active["statuses"][0]
        ])
        r = self.assess(after_status_inputs=both)
        self.assertIn("AFTER_SIGNED_STATUS_FORK", r["issues"])

    def test_expired_after_status_denied(self):
        r = self.assess(after_status_inputs=dict(self.after,
                                                now_epoch=10_100))
        self.assertIn("AFTER_STATUS_EXPIRED_OR_FUTURE", r["issues"])

    def test_forged_post_restart_status_signature_is_denied(self):
        fake = dict(self.after["statuses"][0], signature_hex="0" * 128)
        r = self.assess(after_status_inputs=dict(self.after,
                                                statuses=[fake]))
        self.assertFalse(r["after_status_cryptographic"])
        self.assertIn("AFTER_STATUS_NOT_SINGULAR_AND_SIGNED", r["issues"])

    def test_revocation_with_old_incident_epoch_is_explicitly_stale(self):
        r = self.assess()
        self.assertIn("STATUS_PRECEDES_REOPENED_INCIDENT", r["issues"])

    def test_unchanged_incident_epoch_is_denied(self):
        r = self.assess(recovery_incident_epoch=4)
        self.assertIn("INCIDENT_NOT_MONOTONICALLY_REOPENED", r["issues"])

    def test_boolean_incident_epoch_is_denied(self):
        r = self.assess(recovery_incident_epoch=True)
        self.assertIn("INCIDENT_NOT_MONOTONICALLY_REOPENED", r["issues"])

    def test_invalid_observation_is_fail_closed(self):
        r = self.assess(observation={})
        self.assertIn("SQLITE_OBSERVATION_INVALID", r["issues"])

    def test_tampered_marker_history_is_detected(self):
        tampered = dict(self.observation, source_pending_marker=False)
        r = self.assess(observation=tampered)
        self.assertIn("PRIMARY_RESTART_VETO_MISSING", r["issues"])

    def test_relocated_database_marker_gap_is_reported(self):
        r = self.assess()
        self.assertIn("RELOCATED_DB_MISSES_ACK_CUSTODY", r["issues"])

    def test_unknown_intent_id_is_rejected(self):
        tampered = dict(self.observation, intent_id="other-intent")
        r = self.assess(observation=tampered)
        self.assertIn("ACK_HISTORY_OR_IDENTITY_INCONSISTENT", r["issues"])

    def test_read_only_review_is_not_resume_or_resend(self):
        r = self.assess(requested_effect="READ_ONLY_REVIEW")
        self.assertNotIn("OPERATIONAL_RECOVERY_FORBIDDEN", r["issues"])
        self.assertFalse(r["can_resume"])
        self.assertFalse(r["can_authorize_real_effect"])

    def test_p0_remain_open_even_if_local_status_crypto_is_valid(self):
        r = self.assess(after_status_inputs=later_status(
            self.before, self.status_key, "ACTIVE"))
        self.assertEqual(r["schema"], SCHEMA)
        self.assertEqual(r["p0_homologated"], 0)
        self.assertFalse(r["independent_custody_authenticated"])
        self.assertFalse(r["trusted_clock_authenticated"])
        self.assertTrue(r["hard_no_go"])

    def test_no_provider_worker_deploy_or_costs(self):
        for r in (self.assess(), self.assess(requested_effect="RESEND")):
            self.assertFalse(r["can_authorize_real_effect"])
            self.assertTrue(r["zero_auto_resend"])
            self.assertTrue(r["no_provider_worker_deploy_orders"])
            self.assertFalse(r["new_paid_services"])
            self.assertEqual(r["automatic_retries"], 0)

    def test_unrecognized_effect_is_not_accepted(self):
        r = self.assess(requested_effect="SEND_REAL_ORDER")
        self.assertIn("REQUESTED_EFFECT_UNRECOGNIZED", r["issues"])
        self.assertFalse(r["can_resume"])


if __name__ == "__main__":
    unittest.main()
