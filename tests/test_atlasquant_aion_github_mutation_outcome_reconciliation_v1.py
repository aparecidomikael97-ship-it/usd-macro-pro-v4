import copy
import hashlib
import json
import unittest

from atlasquant_aion_signed_github_mutation_adapter_outcome_v1 import (
    OUTCOME_SCHEMA,
)
from atlasquant_aion_github_mutation_outcome_reconciliation_v1 import (
    AUTHORITATIVE_EVIDENCE_CLASSES,
    MAX_EVIDENCE_AGE_SECONDS,
    MAX_RECONCILIATION_AUTH_WINDOW_SECONDS,
    RECONCILIATION_MECHANISM,
    RECONCILIATION_PURPOSE,
    build_authoritative_reconciliation_evidence,
    build_outcome_reconciliation_record,
    build_reconciliation_authorization,
    github_mutation_reconciliation_policy,
    verify_outcome_reconciliation_record,
)


D = lambda c: "sha256:" + (c * 64)


def digest(value):
    return "sha256:" + hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
            default=str,
        ).encode("utf-8")
    ).hexdigest()


class AionGithubMutationOutcomeReconciliationV1Tests(unittest.TestCase):
    def unknown_receipt(self):
        material = {
            "receipt_id": "outcome-unknown-1",
            "attempt_observation_digest": D("1"),
            "execution_attempt_id": "repo-attempt-1",
            "executor_boundary_digest": D("2"),
            "adapter_attestation_digest": D("3"),
            "provider_identity": "GITHUB",
            "pr_number": 1015,
            "requested_mutation": "PR_DRAFT_TO_READY",
            "logical_operation": "SET_PR_READY_FOR_REVIEW",
            "idempotency_key_digest": D("4"),
            "effect_key_digest": D("5"),
            "request_correlation_digest": D("6"),
            "declared_outcome": "OUTCOME_UNKNOWN",
            "outcome": "OUTCOME_UNKNOWN",
            "expected_postcondition": "PR_IS_READY_FOR_REVIEW",
            "provider_response_evidence_digest": D("7"),
            "postcondition_evidence_digest": "",
            "terminal_failure_evidence_digest": "",
            "ambiguity_evidence_digest": D("8"),
            "ambiguity_triggers": ["TIMEOUT_AFTER_DISPATCH"],
            "provider_response_received": False,
            "response_correlation_verified": False,
            "response_authenticity_verified": False,
            "response_schema_verified": False,
            "provider_success_semantics_verified": False,
            "provider_terminal_failure_semantics_verified": False,
            "repository_postcondition_readback_verified": False,
            "expected_postcondition_match": False,
            "authoritative_no_effect_or_terminal_rejection_verified": False,
            "evidence_complete": True,
            "observed_at": "2026-10-08T10:01:07+00:00",
        }
        return {
            "schema": OUTCOME_SCHEMA,
            "state": "IMMUTABLE_MUTATION_OUTCOME_RECORDED",
            "blockers": [],
            **material,
            "outcome_receipt_digest": digest(material),
            "receipt_immutable": True,
            "receipt_append_only": True,
            "success_confirmed": False,
            "terminal_failure_confirmed": False,
            "outcome_unknown_recorded": True,
            "absence_of_error_is_success": False,
            "absence_of_response_is_terminal_failure": False,
            "automatic_retry_allowed": False,
            "retry_scheduled": False,
            "retry_performed": False,
            "reconciliation_required": True,
            "separate_reconciliation_record_required": True,
            "separate_reconciliation_authorization_required": True,
            "new_attempt_authorized": False,
            "fresh_authorization_required_for_new_attempt": True,
            "new_effect_key_required_for_new_attempt": True,
            "new_execution_attempt_id_required": True,
            "original_receipt_mutable": False,
            "receipt_persisted_by_this_module": False,
            "github_api_called_by_this_module": False,
            "network_called_by_this_module": False,
            "repository_mutation_performed_by_this_module": False,
            "executes_action": False,
        }

    def authorization(self, receipt=None, decision=None, **changes):
        receipt = receipt or self.unknown_receipt()
        decision = decision or "AUTHORIZE_GITHUB_MUTATION_RECONCILIATION"
        signed_material = {
            "authorization_id": "reconciliation-auth-1",
            "purpose": RECONCILIATION_PURPOSE,
            "mechanism": RECONCILIATION_MECHANISM,
            "decision": decision,
            "owner_subject": "owner://mikael",
            "owner_binding_digest": D("9"),
            "owner_key_fingerprint": D("a"),
            "nonce_digest": D("b"),
            "original_outcome_receipt_digest": receipt["outcome_receipt_digest"],
            "execution_attempt_id": receipt["execution_attempt_id"],
            "pr_number": receipt["pr_number"],
            "requested_mutation": receipt["requested_mutation"],
            "request_correlation_digest": receipt["request_correlation_digest"],
            "idempotency_key_digest": receipt["idempotency_key_digest"],
            "effect_key_digest": receipt["effect_key_digest"],
            "issued_at": "2026-10-08T10:02:00+00:00",
            "expires_at": "2026-10-08T10:03:30+00:00",
        }
        kwargs = {
            "outcome_receipt": receipt,
            "authorization_id": "reconciliation-auth-1",
            "decision": decision,
            "owner_subject": "owner://mikael",
            "owner_binding_digest": D("9"),
            "owner_key_fingerprint": D("a"),
            "nonce_digest": D("b"),
            "signed_authorization_digest": digest(signed_material),
            "verified_owner_signature": True,
            "verified_active_trust_root": True,
            "persistent_nonce_replay_guard_verified": True,
            "nonce_single_use_claimed": True,
            "issued_at": "2026-10-08T10:02:00+00:00",
            "expires_at": "2026-10-08T10:03:30+00:00",
            "now": "2026-10-08T10:02:15+00:00",
        }
        kwargs.update(changes)
        return build_reconciliation_authorization(**kwargs)

    def evidence(
        self,
        receipt=None,
        auth=None,
        success=True,
        no_effect=False,
        terminal_rejection=False,
        conflict=False,
        classes=None,
        **changes,
    ):
        receipt = receipt or self.unknown_receipt()
        auth = auth or self.authorization(receipt)
        classes = classes or ["GITHUB_PR_STATE_READBACK"]
        kwargs = {
            "outcome_receipt": receipt,
            "reconciliation_authorization": auth,
            "evidence_id": "reconciliation-evidence-1",
            "evidence_classes": classes,
            "evidence_source_digest": D("c"),
            "evidence_set_digest": D("d"),
            "repository_observation_digest": D("e"),
            "pr_state_evidence_digest": D("f"),
            "main_state_evidence_digest": D("1"),
            "audit_evidence_digest": "",
            "repository_identity_match": True,
            "pr_number_match": True,
            "requested_mutation_match": True,
            "execution_attempt_id_match": True,
            "request_correlation_match": True,
            "idempotency_key_match": True,
            "effect_key_match": True,
            "evidence_source_attested": True,
            "evidence_schema_valid": True,
            "evidence_authenticity_verified": True,
            "evidence_freshness_verified": True,
            "evidence_sequence_monotonic": True,
            "independent_repository_readback_verified": True,
            "success_postcondition_verified": success,
            "authoritative_no_effect_verified": no_effect,
            "authoritative_terminal_rejection_verified": terminal_rejection,
            "conflicting_evidence_present": conflict,
            "observed_at": "2026-10-08T10:02:20+00:00",
            "now": "2026-10-08T10:02:25+00:00",
        }
        kwargs.update(changes)
        return build_authoritative_reconciliation_evidence(**kwargs)

    def record(self, receipt=None, auth=None, evidence=None, **changes):
        receipt = receipt or self.unknown_receipt()
        auth = auth or self.authorization(receipt)
        evidence = evidence or self.evidence(receipt, auth)
        kwargs = {
            "outcome_receipt": receipt,
            "reconciliation_authorization": auth,
            "reconciliation_evidence": evidence,
            "reconciliation_id": "reconciliation-record-1",
            "evidence_complete": True,
            "observed_at": "2026-10-08T10:02:30+00:00",
        }
        kwargs.update(changes)
        return build_outcome_reconciliation_record(**kwargs)

    def test_authorization_only_accepts_unknown_receipt(self):
        receipt = self.unknown_receipt()
        auth = self.authorization(receipt)
        self.assertEqual(
            auth["state"],
            "RECONCILIATION_AUTHORIZED",
            auth["blockers"],
        )
        self.assertTrue(auth["reconciliation_authorized"])
        self.assertFalse(auth["reconciliation_denied"])
        self.assertFalse(auth["authorization_consumed"])
        self.assertFalse(auth["authorization_reuse_allowed"])
        self.assertFalse(auth["provider_query_authorized_by_this_module"])
        self.assertFalse(auth["github_query_performed_by_this_module"])
        self.assertFalse(auth["network_called_by_this_module"])
        self.assertFalse(auth["retry_authorized"])
        self.assertFalse(auth["new_attempt_authorized"])
        self.assertFalse(auth["repository_mutation_performed"])

        non_unknown = copy.deepcopy(receipt)
        non_unknown["outcome"] = "CONFIRMED_SUCCESS"
        non_unknown["outcome_unknown_recorded"] = False
        blocked = self.authorization(non_unknown)
        self.assertEqual(blocked["state"], "BLOCKED")
        self.assertIn(
            "VALID_MUTATION_OUTCOME_RECEIPT_REQUIRED",
            blocked["blockers"],
        )
        self.assertIn(
            "RECONCILIATION_ONLY_ALLOWED_FOR_OUTCOME_UNKNOWN",
            blocked["blockers"],
        )

    def test_deny_authorization_blocks_reconciliation_evidence(self):
        receipt = self.unknown_receipt()
        denied = self.authorization(
            receipt,
            decision="DENY_GITHUB_MUTATION_RECONCILIATION",
        )
        self.assertEqual(denied["state"], "RECONCILIATION_DENIED")
        self.assertTrue(denied["reconciliation_denied"])
        evidence = self.evidence(receipt, denied)
        self.assertEqual(evidence["state"], "BLOCKED")
        self.assertIn(
            "RECONCILIATION_AUTHORIZATION_REQUIRED",
            evidence["blockers"],
        )

    def test_authorization_digest_tamper_or_replay_guard_failure_blocks(self):
        receipt = self.unknown_receipt()
        tampered = self.authorization(
            receipt,
            signed_authorization_digest=D("0"),
        )
        self.assertEqual(tampered["state"], "BLOCKED")
        self.assertIn(
            "SIGNED_AUTHORIZATION_DIGEST_MISMATCH",
            tampered["blockers"],
        )

        replay_weak = self.authorization(
            receipt,
            persistent_nonce_replay_guard_verified=False,
        )
        self.assertEqual(replay_weak["state"], "BLOCKED")
        self.assertIn(
            "PERSISTENT_NONCE_REPLAY_GUARD_REQUIRED",
            replay_weak["blockers"],
        )

    def test_success_reconciliation_requires_authoritative_pr_readback(self):
        receipt = self.unknown_receipt()
        auth = self.authorization(receipt)
        evidence = self.evidence(receipt, auth, success=True)
        self.assertEqual(
            evidence["state"],
            "AUTHORITATIVE_RECONCILIATION_EVIDENCE_ATTESTED",
            evidence["blockers"],
        )
        record = self.record(receipt, auth, evidence)
        self.assertEqual(record["state"], "RECONCILIATION_RECORD_READY")
        self.assertEqual(
            record["reconciled_outcome"],
            "RECONCILED_CONFIRMED_SUCCESS",
        )
        self.assertFalse(record["original_receipt_mutated"])
        self.assertTrue(record["reconciliation_record_append_only"])
        self.assertFalse(record["reconciliation_is_retry"])
        self.assertFalse(record["repository_mutation_replayed"])
        self.assertFalse(record["automatic_retry_allowed"])
        self.assertFalse(record["new_attempt_authorized"])
        self.assertTrue(
            verify_outcome_reconciliation_record(record)["valid"]
        )

    def test_success_without_required_mutation_specific_class_blocks(self):
        receipt = self.unknown_receipt()
        auth = self.authorization(receipt)
        evidence = self.evidence(
            receipt,
            auth,
            success=True,
            classes=["IMMUTABLE_REPOSITORY_OBSERVATION"],
        )
        self.assertEqual(evidence["state"], "BLOCKED")
        self.assertIn(
            "SUCCESS_EVIDENCE_CLASS_REQUIREMENTS_NOT_MET",
            evidence["blockers"],
        )

    def test_confirmed_no_effect_reconciles_failure_but_never_authorizes_retry(self):
        receipt = self.unknown_receipt()
        auth = self.authorization(receipt)
        evidence = self.evidence(
            receipt,
            auth,
            success=False,
            no_effect=True,
        )
        self.assertEqual(
            evidence["state"],
            "AUTHORITATIVE_RECONCILIATION_EVIDENCE_ATTESTED",
            evidence["blockers"],
        )
        record = self.record(receipt, auth, evidence)
        self.assertEqual(
            record["reconciled_outcome"],
            "RECONCILED_CONFIRMED_TERMINAL_FAILURE",
        )
        self.assertTrue(record["confirmed_no_effect"])
        self.assertTrue(
            record["new_attempt_may_be_considered_with_fresh_authorization"]
        )
        self.assertFalse(record["new_attempt_authorized"])
        self.assertTrue(
            record["fresh_owner_authorization_required_for_new_attempt"]
        )
        self.assertTrue(record["new_effect_key_required_for_new_attempt"])
        self.assertTrue(record["new_execution_attempt_id_required"])
        self.assertFalse(record["automatic_retry_allowed"])
        self.assertFalse(record["retry_scheduled"])
        self.assertFalse(record["retry_performed"])

    def test_conflicting_evidence_preserves_unknown(self):
        receipt = self.unknown_receipt()
        auth = self.authorization(receipt)
        evidence = self.evidence(
            receipt,
            auth,
            success=True,
            no_effect=True,
            conflict=False,
        )
        self.assertEqual(
            evidence["state"],
            "AUTHORITATIVE_RECONCILIATION_EVIDENCE_ATTESTED",
        )
        self.assertTrue(evidence["conflicting_evidence_present"])
        record = self.record(receipt, auth, evidence)
        self.assertEqual(
            record["reconciled_outcome"],
            "STILL_OUTCOME_UNKNOWN",
        )
        self.assertIn(
            "SUCCESS_AND_FAILURE_SIGNAL_CONFLICT",
            record["unknown_preserving_conditions"],
        )
        self.assertFalse(record["automatic_retry_allowed"])
        self.assertFalse(record["new_attempt_authorized"])

    def test_incomplete_evidence_preserves_unknown(self):
        record = self.record(evidence_complete=False)
        self.assertEqual(
            record["reconciled_outcome"],
            "STILL_OUTCOME_UNKNOWN",
        )
        self.assertIn(
            "EVIDENCE_INCOMPLETE",
            record["unknown_preserving_conditions"],
        )
        self.assertFalse(record["automatic_retry_allowed"])

    def test_stale_or_unauthenticated_evidence_blocks_attestation(self):
        receipt = self.unknown_receipt()
        auth = self.authorization(receipt)
        stale = self.evidence(
            receipt,
            auth,
            success=True,
            observed_at="2026-10-08T09:59:00+00:00",
            now="2026-10-08T10:02:25+00:00",
        )
        self.assertEqual(stale["state"], "BLOCKED")
        self.assertIn(
            "RECONCILIATION_EVIDENCE_STALE",
            stale["blockers"],
        )

        unauth = self.evidence(
            receipt,
            auth,
            success=True,
            evidence_authenticity_verified=False,
        )
        self.assertEqual(unauth["state"], "BLOCKED")
        self.assertIn(
            "EVIDENCE_AUTHENTICITY_REQUIRED",
            unauth["blockers"],
        )
        self.assertEqual(MAX_EVIDENCE_AGE_SECONDS, 120)

    def test_terminal_rejection_requires_authoritative_evidence_class(self):
        receipt = self.unknown_receipt()
        auth = self.authorization(receipt)
        blocked = self.evidence(
            receipt,
            auth,
            success=False,
            terminal_rejection=True,
            classes=["GITHUB_PR_STATE_READBACK"],
        )
        self.assertEqual(blocked["state"], "BLOCKED")
        self.assertIn(
            "TERMINAL_REJECTION_EVIDENCE_CLASS_REQUIRED",
            blocked["blockers"],
        )

        ready = self.evidence(
            receipt,
            auth,
            success=False,
            terminal_rejection=True,
            classes=[
                "GITHUB_PR_STATE_READBACK",
                "GITHUB_REPOSITORY_AUDIT_EVENT",
            ],
        )
        self.assertEqual(
            ready["state"],
            "AUTHORITATIVE_RECONCILIATION_EVIDENCE_ATTESTED",
            ready["blockers"],
        )

    def test_reconciliation_record_is_tamper_evident(self):
        record = self.record()
        tampered = copy.deepcopy(record)
        tampered["reconciled_outcome"] = (
            "RECONCILED_CONFIRMED_TERMINAL_FAILURE"
        )
        checked = verify_outcome_reconciliation_record(tampered)
        self.assertFalse(checked["valid"])
        self.assertIn(
            "RECONCILIATION_DIGEST_MISMATCH",
            checked["blockers"],
        )

    def test_policy_is_fail_closed_and_nonexecuting(self):
        policy = github_mutation_reconciliation_policy()
        self.assertEqual(
            policy["reconciliation_purpose"],
            RECONCILIATION_PURPOSE,
        )
        self.assertEqual(
            policy["reconciliation_mechanism"],
            RECONCILIATION_MECHANISM,
        )
        self.assertTrue(policy["reconciliation_only_for_outcome_unknown"])
        self.assertTrue(policy["original_receipt_immutable"])
        self.assertTrue(policy["reconciliation_record_append_only"])
        self.assertTrue(policy["separate_owner_authorization_required"])
        self.assertTrue(policy["owner_signature_required"])
        self.assertTrue(policy["active_trust_root_required"])
        self.assertTrue(policy["persistent_nonce_replay_guard_required"])
        self.assertTrue(policy["single_use_reconciliation_nonce_required"])
        self.assertFalse(policy["authorization_reuse_allowed"])
        self.assertTrue(policy["authoritative_repository_evidence_required"])
        self.assertTrue(policy["independent_repository_readback_required"])
        self.assertTrue(policy["conflicting_evidence_preserves_unknown"])
        self.assertTrue(policy["incomplete_evidence_preserves_unknown"])
        self.assertTrue(policy["stale_evidence_preserves_unknown"])
        self.assertTrue(policy["unauthenticated_evidence_preserves_unknown"])
        self.assertFalse(policy["reconciliation_is_retry"])
        self.assertFalse(policy["repository_mutation_replayed"])
        self.assertFalse(policy["automatic_retry_allowed"])
        self.assertFalse(policy["new_attempt_authorized"])
        self.assertTrue(
            policy["fresh_owner_authorization_required_for_new_attempt"]
        )
        self.assertFalse(policy["github_query_performed_by_this_module"])
        self.assertFalse(policy["network_called_by_this_module"])
        self.assertFalse(policy["repository_mutation_performed"])
        self.assertFalse(policy["merge_executed"])
        self.assertFalse(policy["retarget_executed"])
        self.assertFalse(policy["draft_transition_executed"])
        self.assertFalse(policy["branch_deleted"])
        self.assertFalse(policy["deploy_executed"])
        self.assertFalse(policy["worker_activation_allowed"])
        self.assertFalse(policy["provider_activation_allowed"])
        self.assertFalse(policy["production_persistence_activation_allowed"])
        self.assertFalse(policy["external_action_executed"])
        self.assertFalse(policy["executes_action"])
        self.assertIn(
            "GITHUB_PR_STATE_READBACK",
            AUTHORITATIVE_EVIDENCE_CLASSES,
        )
        self.assertEqual(MAX_RECONCILIATION_AUTH_WINDOW_SECONDS, 120)


if __name__ == "__main__":
    unittest.main()
