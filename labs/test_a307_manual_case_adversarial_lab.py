"""A307 adversarial regression of A306: false local validity and untrusted inputs.

Tests assert fail-closed behavior, never operational correctness/homologation.
"""
import copy
import unittest

from labs.test_a304_custodian_status_lab import fixture as status_fixture
from labs.test_a305_restart_revocation_no_resend_lab import later_status
from labs.test_a306_manual_intent_reconciliation_lab import (
    case_fixture, claim,
)
from labs.a305_restart_revocation_no_resend_lab import probe_sqlite_restart_ack_loss
from labs.a306_manual_intent_reconciliation_lab import (
    SCHEMA, assess_manual_reconciliation,
)


class A307AdversarialCaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.observation = probe_sqlite_restart_ack_loss()

    def setUp(self):
        self.before, key, _ = status_fixture()
        self.after = later_status(self.before, key, "REVOKED")
        self.case = case_fixture()

    def assess(self, **changes):
        params = {
            "observation": self.observation,
            "before_status_inputs": self.before,
            "after_status_inputs": self.after,
            "previous_incident_epoch": 4,
            "recovery_incident_epoch": 5,
            "review_case": self.case,
            "last_closed_case_generation": 6,
        }
        params.update(changes)
        return assess_manual_reconciliation(**params)

    def assert_veto(self, case):
        self.assertFalse(case["can_resume"])
        self.assertFalse(case["can_resend"])
        self.assertFalse(case["can_auto_retry"])
        self.assertFalse(case["can_authorize_real_effect"])
        self.assertFalse(case["human_reviewer_identity_authenticated"])
        self.assertFalse(case["external_evidence_provenance_verified"])
        self.assertFalse(case["independent_outcome_verified"])
        self.assertFalse(case["independent_custody_authenticated"])
        self.assertTrue(case["hard_no_go"])
        self.assertTrue(case["zero_auto_resend"])
        self.assertEqual(case["automatic_retries"], 0)
        self.assertEqual(case["p0_homologated"], 0)
        self.assertFalse(case["new_paid_services"])
        self.assertTrue(case["no_provider_worker_deploy_orders"])

    def test_empty_case_is_review_stub_not_external_evidence(self):
        r = self.assess()
        self.assertTrue(r["case_file_locally_valid"])
        self.assertFalse(r["claimed_evidence_consistent_locally"])
        self.assertTrue(r["locally_observed_effect"])
        self.assert_veto(r)

    def test_distinct_well_formed_claims_are_still_not_independent_proof(self):
        c = dict(self.case, claimed_evidence=[
            claim(source="source-a"),
            claim(source="source-b", reference="event-2"),
        ])
        r = self.assess(review_case=c)
        self.assertTrue(r["case_file_locally_valid"])
        self.assertTrue(r["claimed_evidence_consistent_locally"])
        self.assertFalse(r["external_evidence_provenance_verified"])
        self.assert_veto(r)

    def test_false_validity_missing_claim_fields_is_closed(self):
        bad = dict(claim())
        del bad["reference_id"]
        r = self.assess(review_case=dict(self.case, claimed_evidence=[bad]))
        self.assertIn("CLAIM_FIELDS_INVALID", r["issues"])
        self.assertFalse(r["case_file_locally_valid"])
        self.assertFalse(r["claimed_evidence_consistent_locally"])

    def test_false_validity_duplicate_reference_is_closed(self):
        item = claim()
        r = self.assess(review_case=dict(self.case, claimed_evidence=[
            item, copy.deepcopy(item),
        ]))
        self.assertIn("DUPLICATE_EVIDENCE_REFERENCE", r["issues"])
        self.assertFalse(r["case_file_locally_valid"])

    def test_false_validity_same_source_two_names_is_closed(self):
        r = self.assess(review_case=dict(self.case, claimed_evidence=[
            claim(), claim(reference="another-event"),
        ]))
        self.assertIn("CLAIMS_FROM_SINGLE_SOURCE", r["issues"])
        self.assertFalse(r["case_file_locally_valid"])

    def test_false_validity_conflicting_claims_is_closed(self):
        r = self.assess(review_case=dict(self.case, claimed_evidence=[
            claim("PRESENT"), claim("ABSENT", "source-b", "event-2"),
        ]))
        self.assertIn("CONFLICTING_EFFECT_CLAIMS", r["issues"])
        self.assertEqual(r["effect_category"], "CONFLICTING_CLAIMS")
        self.assertFalse(r["case_file_locally_valid"])

    def test_false_validity_claimed_absence_vs_sqlite_is_closed(self):
        r = self.assess(review_case=dict(self.case,
                                         claimed_evidence=[claim("ABSENT")]))
        self.assertIn("CLAIMED_ABSENCE_CONFLICTS_WITH_SQLITE", r["issues"])
        self.assertFalse(r["case_file_locally_valid"])

    def test_false_validity_wrong_semantic_intent_is_closed(self):
        item = dict(claim(), intent_id="not-the-intent")
        r = self.assess(review_case=dict(self.case, claimed_evidence=[item]))
        self.assertIn("CLAIM_SEMANTIC_INTENT_MISMATCH", r["issues"])
        self.assertFalse(r["case_file_locally_valid"])

    def test_false_validity_malformed_digest_is_closed(self):
        item = dict(claim(), evidence_sha256="not-a-sha")
        r = self.assess(review_case=dict(self.case, claimed_evidence=[item]))
        self.assertIn("CLAIM_DIGEST_INVALID", r["issues"])
        self.assertFalse(r["case_file_locally_valid"])

    def test_false_validity_unsupported_outcome_is_closed(self):
        item = dict(claim(), observed_outcome="PROVIDER_RETRY_OK")
        r = self.assess(review_case=dict(self.case, claimed_evidence=[item]))
        self.assertIn("CLAIM_OUTCOME_INVALID", r["issues"])
        self.assertFalse(r["case_file_locally_valid"])

    def test_false_validity_invalid_claim_identity_is_closed(self):
        item = dict(claim(), source_id="")
        r = self.assess(review_case=dict(self.case, claimed_evidence=[item]))
        self.assertIn("CLAIM_IDENTITY_INVALID", r["issues"])
        self.assertFalse(r["case_file_locally_valid"])

    def test_claim_collection_wrong_type_does_not_claim_valid(self):
        r = self.assess(review_case=dict(self.case, claimed_evidence="fake"))
        self.assertIn("EVIDENCE_COLLECTION_INVALID", r["issues"])
        self.assertFalse(r["case_file_locally_valid"])

    def test_claim_count_over_limit_does_not_claim_valid(self):
        items = [claim(source=f"s-{i}", reference=f"r-{i}")
                 for i in range(21)]
        r = self.assess(review_case=dict(self.case, claimed_evidence=items))
        self.assertIn("EVIDENCE_COLLECTION_INVALID", r["issues"])
        self.assertFalse(r["case_file_locally_valid"])

    def test_unhashable_outcome_never_crashes_or_claims_valid(self):
        item = dict(claim(), observed_outcome=["PRESENT"])
        r = self.assess(review_case=dict(self.case, claimed_evidence=[item]))
        self.assertIn("CLAIM_OUTCOME_INVALID", r["issues"])
        self.assertFalse(r["case_file_locally_valid"])
        self.assert_veto(r)

    def test_unhashable_decision_never_crashes_or_claims_valid(self):
        r = self.assess(review_case=dict(self.case, review_decision=["RESEND"]))
        self.assertIn("UNSAFE_REVIEW_DECISION", r["issues"])
        self.assertFalse(r["case_file_locally_valid"])
        self.assert_veto(r)

    def test_malformed_case_hash_stays_non_authoritative(self):
        r = self.assess(review_case=dict(
            self.case, case_generation=True,
            claimed_evidence=[dict(claim(), evidence_sha256=None)],
        ))
        self.assertIn("REPLAYED_OR_INVALID_CASE_GENERATION", r["issues"])
        self.assertFalse(r["case_file_locally_valid"])

    def test_untrusted_case_generation_floor_is_not_real_monotonicity(self):
        r = self.assess(last_closed_case_generation=True)
        self.assertIn("CASE_GENERATION_FLOOR_INVALID", r["issues"])
        self.assertFalse(r["case_file_locally_valid"])

    def test_partial_sqlite_observation_cannot_be_called_locally_observed(self):
        r = self.assess(observation={"sqlite_effect_count": 1})
        self.assertFalse(r["locally_observed_effect"])
        self.assertEqual(r["effect_category"], "UNDETERMINED")
        self.assertIn("OBSERVATION_INTEGRITY_INSUFFICIENT", r["issues"])
        self.assertFalse(r["case_file_locally_valid"])
        self.assert_veto(r)

    def test_wrong_observation_schema_is_not_locally_observed(self):
        obs = dict(self.observation, schema="forged")
        r = self.assess(observation=obs)
        self.assertIn("OBSERVATION_INTEGRITY_INSUFFICIENT", r["issues"])
        self.assertFalse(r["locally_observed_effect"])
        self.assertFalse(r["case_file_locally_valid"])

    def test_lost_pending_marker_invalidates_observation(self):
        obs = dict(self.observation, source_pending_marker=False)
        r = self.assess(observation=obs)
        self.assertIn("OBSERVATION_INTEGRITY_INSUFFICIENT", r["issues"])
        self.assertFalse(r["locally_observed_effect"])
        self.assertFalse(r["case_file_locally_valid"])

    def test_missing_source_restart_veto_invalidates_observation(self):
        obs = dict(self.observation, source_reopen_refused=False)
        r = self.assess(observation=obs)
        self.assertFalse(r["locally_observed_effect"])
        self.assertFalse(r["case_file_locally_valid"])

    def test_false_no_retry_claim_does_not_promote_local_evidence(self):
        obs = dict(self.observation, no_retries_performed=False)
        r = self.assess(observation=obs)
        self.assertFalse(r["locally_observed_effect"])
        self.assertFalse(r["case_file_locally_valid"])

    def test_self_asserted_external_custody_flag_is_not_trusted(self):
        obs = dict(self.observation, off_host_custody_attested=True)
        r = self.assess(observation=obs)
        self.assertFalse(r["locally_observed_effect"])
        self.assertFalse(r["case_file_locally_valid"])
        self.assertFalse(r["independent_custody_authenticated"])

    def test_case_status_revoked_never_becomes_authorization(self):
        r = self.assess()
        self.assertIn("POST_RESTART_KEY_REVOKED", r["issues"])
        self.assert_veto(r)

    def test_case_content_changes_digest_but_not_trust(self):
        c = dict(self.case, review_decision="ESCALATE")
        a = self.assess()
        b = self.assess(review_case=c)
        self.assertNotEqual(a["case_digest_sha256"], b["case_digest_sha256"])
        self.assertTrue(b["case_file_locally_valid"])
        self.assert_veto(b)

    def test_json_canonicalization_error_is_fail_closed(self):
        # bytes cannot be serialized by the JSON forensic digest
        c = dict(self.case, case_id=b"invalid")
        r = self.assess(review_case=c)
        self.assertIn("CASE_ID_INVALID", r["issues"])
        self.assertIn("REVIEW_CASE_NOT_CANONICAL", r["issues"])
        self.assertFalse(r["case_file_locally_valid"])
        self.assert_veto(r)

    def test_mutation_matrix_never_produces_operational_go(self):
        # Deterministic bounded mutation of all client-editable fields.
        poisons = [None, True, False, [], {}, ["RESEND"], {"go": True},
                   -1, 0, "", "RESEND", "a" * 70]
        for field in sorted(self.case):
            for poison in poisons:
                with self.subTest(field=field, poison=repr(poison)):
                    c = dict(self.case, **{field: poison})
                    r = self.assess(review_case=c)
                    self.assert_veto(r)

    def test_malformed_claim_matrix_never_produces_operational_go(self):
        poisons = [None, True, [], {}, ["PRESENT"], -1, "", "RESEND"]
        for field in sorted(claim()):
            for poison in poisons:
                with self.subTest(field=field, poison=repr(poison)):
                    item = dict(claim(), **{field: poison})
                    r = self.assess(review_case=dict(
                        self.case, claimed_evidence=[item]))
                    self.assert_veto(r)
                    self.assertFalse(r["case_file_locally_valid"])


if __name__ == "__main__":
    unittest.main()
