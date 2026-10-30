"""A306: manual case-file review cannot authorize unknown-ACK effects."""
import copy
import unittest

from labs.a305_restart_revocation_no_resend_lab import (
    probe_sqlite_restart_ack_loss, INTENT_ID, MESSAGE_ID,
)
from labs.test_a304_custodian_status_lab import fixture as a304_fixture
from labs.test_a305_restart_revocation_no_resend_lab import later_status
from labs.a306_manual_intent_reconciliation_lab import (
    SCHEMA, assess_manual_reconciliation,
)


def case_fixture():
    return {
        "schema": SCHEMA,
        "case_id": "a306-disposable-case-1",
        "case_generation": 7,
        "previous_case_sha256": "e" * 64,
        "incident_epoch": 5,
        "intent_id": INTENT_ID,
        "message_id": MESSAGE_ID,
        "reviewer_id": "synthetic-reviewer-b",
        "reporter_id": "synthetic-reporter-a",
        "reviewer_acknowledged": True,
        "review_decision": "HOLD",
        "claimed_evidence": [],
    }


def claim(outcome="PRESENT", source="synthetic-source-a",
          reference="synthetic-event-1"):
    return {
        "source_id": source,
        "reference_id": reference,
        "intent_id": INTENT_ID,
        "message_id": MESSAGE_ID,
        "observed_outcome": outcome,
        "evidence_sha256": "a" * 64,
    }


class A306ManualReconciliationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.observation = probe_sqlite_restart_ack_loss()

    def setUp(self):
        before, key, _ = a304_fixture()
        self.before = before
        self.after = later_status(before, key, "REVOKED")
        self.case = case_fixture()

    def assess(self, **overrides):
        kwargs = {
            "observation": self.observation,
            "before_status_inputs": self.before,
            "after_status_inputs": self.after,
            "previous_incident_epoch": 4,
            "recovery_incident_epoch": 5,
            "review_case": self.case,
            "last_closed_case_generation": 6,
        }
        kwargs.update(overrides)
        return assess_manual_reconciliation(**kwargs)

    def test_real_sqlite_message_was_committed_but_ack_unknown(self):
        o = self.observation
        self.assertEqual(o["sqlite_effect_count"], 1)
        self.assertEqual(o["ack_state"], "ACK_UNKNOWN")
        self.assertTrue(o["source_reopen_refused"])

    def test_empty_claims_are_not_external_proof(self):
        r = self.assess()
        self.assertTrue(r["locally_observed_effect"])
        self.assertEqual(r["effect_category"],
                         "LOCAL_EFFECT_OBSERVED_ACK_UNKNOWN")
        self.assertIn("EXTERNAL_OUTCOME_EVIDENCE_MISSING", r["issues"])

    def test_reviewer_case_has_stable_local_digest_only(self):
        r1, r2 = self.assess(), self.assess()
        self.assertTrue(r1["case_file_locally_valid"])
        self.assertEqual(r1["case_digest_sha256"], r2["case_digest_sha256"])
        self.assertFalse(r1["human_reviewer_identity_authenticated"])
        self.assertFalse(r1["independent_outcome_verified"])

    def test_two_independent_sounding_claims_remain_untrusted(self):
        c = dict(self.case, claimed_evidence=[
            claim(source="supplier-a"),
            claim(source="custodian-b", reference="synthetic-event-2"),
        ])
        r = self.assess(review_case=c)
        self.assertTrue(r["case_file_locally_valid"])
        self.assertFalse(r["external_evidence_provenance_verified"])
        self.assertIn(
            "INDEPENDENT_EVIDENCE_AND_REVIEWER_AUTHORITY_MISSING", r["issues"]
        )
        self.assertFalse(r["can_resume"])

    def test_claim_of_absence_cannot_override_observed_sqlite_effect(self):
        c = dict(self.case, claimed_evidence=[claim("ABSENT")])
        r = self.assess(review_case=c)
        self.assertIn("CLAIMED_ABSENCE_CONFLICTS_WITH_SQLITE", r["issues"])
        self.assertEqual(r["effect_category"], "CONFLICTING_CLAIMS")

    def test_disagreeing_claims_are_not_resolved_by_majority(self):
        c = dict(self.case, claimed_evidence=[
            claim("PRESENT"),
            claim("ABSENT", source="supplier-b", reference="event-2"),
        ])
        r = self.assess(review_case=c)
        self.assertIn("CONFLICTING_EFFECT_CLAIMS", r["issues"])
        self.assertFalse(r["can_resend"])

    def test_duplicate_evidence_reference_is_detected(self):
        c = dict(self.case, claimed_evidence=[claim(), claim()])
        r = self.assess(review_case=c)
        self.assertIn("DUPLICATE_EVIDENCE_REFERENCE", r["issues"])

    def test_two_claims_from_same_source_are_not_independence(self):
        c = dict(self.case, claimed_evidence=[
            claim(),
            claim(reference="event-2"),
        ])
        r = self.assess(review_case=c)
        self.assertIn("CLAIMS_FROM_SINGLE_SOURCE", r["issues"])

    def test_wrong_intent_in_claim_is_denied(self):
        bad = dict(claim(), intent_id="different-intent")
        c = dict(self.case, claimed_evidence=[bad])
        r = self.assess(review_case=c)
        self.assertIn("CLAIM_SEMANTIC_INTENT_MISMATCH", r["issues"])

    def test_invalid_evidence_digest_is_denied(self):
        bad = dict(claim(), evidence_sha256="none")
        c = dict(self.case, claimed_evidence=[bad])
        r = self.assess(review_case=c)
        self.assertIn("CLAIM_DIGEST_INVALID", r["issues"])

    def test_claim_without_required_fields_is_denied(self):
        bad = dict(claim())
        bad.pop("reference_id")
        c = dict(self.case, claimed_evidence=[bad])
        r = self.assess(review_case=c)
        self.assertIn("CLAIM_FIELDS_INVALID", r["issues"])

    def test_case_replay_generation_is_denied(self):
        c = dict(self.case, case_generation=6)
        r = self.assess(review_case=c)
        self.assertIn("REPLAYED_OR_INVALID_CASE_GENERATION", r["issues"])
        self.assertFalse(r["case_file_locally_valid"])

    def test_case_generation_boolean_is_denied(self):
        c = dict(self.case, case_generation=True)
        r = self.assess(review_case=c)
        self.assertIn("REPLAYED_OR_INVALID_CASE_GENERATION", r["issues"])

    def test_reopened_incident_must_match_case_epoch(self):
        c = dict(self.case, incident_epoch=4)
        r = self.assess(review_case=c)
        self.assertIn("INCIDENT_EPOCH_CHANGED", r["issues"])

    def test_reporter_and_reviewer_must_be_distinct_even_as_claims(self):
        c = dict(self.case, reviewer_id="synthetic-reporter-a")
        r = self.assess(review_case=c)
        self.assertIn("DISTINCT_HUMAN_ROLES_NOT_CLAIMED", r["issues"])

    def test_reviewer_acknowledgement_missing_is_denied(self):
        c = dict(self.case, reviewer_acknowledged=False)
        r = self.assess(review_case=c)
        self.assertIn("REVIEWER_ACKNOWLEDGEMENT_MISSING", r["issues"])

    def test_review_decision_cannot_be_resend(self):
        c = dict(self.case, review_decision="RESEND")
        r = self.assess(review_case=c)
        self.assertIn("UNSAFE_REVIEW_DECISION", r["issues"])
        self.assertFalse(r["can_resend"])

    def test_untrusted_previous_case_hash_is_just_local_chaining(self):
        c = dict(self.case, previous_case_sha256="not-a-digest")
        r = self.assess(review_case=c)
        self.assertIn("CASE_PREVIOUS_HASH_INVALID", r["issues"])

    def test_case_identity_cannot_be_changed(self):
        c = dict(self.case, intent_id="other")
        r = self.assess(review_case=c)
        self.assertIn("SEMANTIC_INTENT_BINDING_MISMATCH", r["issues"])

    def test_signed_revocation_remains_a_separate_block(self):
        r = self.assess()
        self.assertIn("POST_RESTART_KEY_REVOKED", r["issues"])
        self.assertIn("ACK_UNKNOWN_ZERO_AUTO_RESEND", r["issues"])
        self.assertTrue(r["a305_negative_barrier_present"])

    def test_signed_active_status_cannot_resolve_ack_unknown(self):
        before, key, _ = a304_fixture()
        active = later_status(before, key, "ACTIVE")
        r = self.assess(before_status_inputs=before,
                        after_status_inputs=active)
        self.assertNotIn("POST_RESTART_KEY_REVOKED", r["issues"])
        self.assertIn("ACK_UNKNOWN_ZERO_AUTO_RESEND", r["issues"])
        self.assertFalse(r["can_resume"])

    def test_missing_new_status_stays_blocked(self):
        r = self.assess(after_status_inputs=dict(self.after, statuses=[]))
        self.assertIn("FRESH_POST_RESTART_STATUS_NOT_SHOWN", r["issues"])
        self.assertFalse(r["can_resend"])

    def test_bad_sqlite_observation_is_not_proof_of_nonexecution(self):
        o = dict(self.observation, sqlite_effect_count=0)
        r = self.assess(observation=o)
        self.assertEqual(r["effect_category"], "UNDETERMINED")
        self.assertFalse(r["can_auto_retry"])

    def test_offline_custodian_does_not_unblock_case(self):
        after = dict(self.after, custodian_online=False)
        r = self.assess(after_status_inputs=after)
        self.assertFalse(r["can_resume"])
        self.assertFalse(r["independent_custody_authenticated"])

    def test_malformed_case_cannot_get_structural_approval(self):
        r = self.assess(review_case={"schema": SCHEMA})
        self.assertIn("REVIEW_CASE_FIELDS_INVALID", r["issues"])
        self.assertFalse(r["case_file_locally_valid"])

    def test_claimed_real_world_approval_field_is_rejected(self):
        c = dict(self.case, provider_approved=True)
        r = self.assess(review_case=c)
        self.assertIn("REVIEW_CASE_FIELDS_INVALID", r["issues"])
        self.assertFalse(r["can_authorize_real_effect"])

    def test_no_real_actions_and_p0_zero_in_all_evaluations(self):
        for r in (
            self.assess(),
            self.assess(review_case=dict(self.case,
                         claimed_evidence=[claim()])),
            self.assess(review_case={}),
        ):
            self.assertFalse(r["can_resume"])
            self.assertFalse(r["can_resend"])
            self.assertFalse(r["can_auto_retry"])
            self.assertFalse(r["can_authorize_real_effect"])
            self.assertFalse(r["independent_outcome_verified"])
            self.assertTrue(r["hard_no_go"])
            self.assertTrue(r["zero_auto_resend"])
            self.assertEqual(r["p0_homologated"], 0)
            self.assertEqual(r["automatic_retries"], 0)
            self.assertFalse(r["new_paid_services"])

    def test_unhashable_evidence_outcome_must_fail_closed_not_crash(self):
        c = dict(self.case, claimed_evidence=[
            dict(claim(), observed_outcome=["PRESENT"])
        ])
        r = self.assess(review_case=c)
        self.assertIn("CLAIM_OUTCOME_INVALID", r["issues"])
        self.assertFalse(r["can_resume"])

    def test_unhashable_review_decision_must_fail_closed_not_crash(self):
        c = dict(self.case, review_decision=["RESEND"])
        r = self.assess(review_case=c)
        self.assertIn("UNSAFE_REVIEW_DECISION", r["issues"])
        self.assertFalse(r["can_resend"])


if __name__ == "__main__":
    unittest.main()
