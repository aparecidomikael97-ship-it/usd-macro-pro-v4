from __future__ import annotations

import unittest

import atlasquant_aion_b2b_execution_finalization_contract_v1 as finalization
import atlasquant_aion_b2b_execution_finalization_persistence_contract_v1 as persistence
from test_atlasquant_aion_b2b_execution_finalization_contract_v1 import (
    approved_reconciliation_review,
)


def approved_finalization_review():
    return finalization.build_execution_finalization_contract(
        outcome_reconciliation_review=approved_reconciliation_review(),
    )


class ExecutionFinalizationPersistenceContractV1Tests(unittest.TestCase):
    def assert_no_authority(self, out):
        for key in persistence.FALSE_FIELDS:
            self.assertIs(out[key], False, key)

    def test_approved_finalization_unlocks_design_only(self):
        out = persistence.build_execution_finalization_persistence_contract(
            execution_finalization_review=approved_finalization_review(),
        )
        self.assertEqual(out["state"], persistence.READY)
        self.assertTrue(out["execution_finalization_persistence_design_only"])
        self.assertEqual(
            out["persistence_mode"],
            "APPEND_ONLY_CAS_TERMINAL_COMMIT",
        )
        self.assertTrue(out["reuses_existing_core_durable_store"])
        self.assertTrue(out["compare_and_set_required"])
        self.assertTrue(out["exactly_once_terminal_commit_required"])
        self.assertFalse(out["persistence_creates_execution_authority"])
        self.assertEqual(out["finops_cap_cents"], 20000)
        self.assert_no_authority(out)

    def test_finalization_must_be_exact_ready_state(self):
        row = approved_finalization_review()
        row["state"] = "BLOCKED"
        out = persistence.build_execution_finalization_persistence_contract(
            execution_finalization_review=row,
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn(
            "EXECUTION_FINALIZATION_DESIGN_REVIEW_REQUIRED",
            out["blockers"],
        )
        self.assert_no_authority(out)

    def test_upstream_finalization_write_flip_blocks(self):
        row = approved_finalization_review()
        row["finalization_record_persisted"] = True
        out = persistence.build_execution_finalization_persistence_contract(
            execution_finalization_review=row,
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn(
            "EXECUTION_FINALIZATION_UNSAFE_FIELD:finalization_record_persisted",
            out["blockers"],
        )
        self.assert_no_authority(out)

    def test_terminal_states_are_closed_and_explicit(self):
        out = persistence.build_execution_finalization_persistence_contract(
            execution_finalization_review=approved_finalization_review(),
        )
        self.assertEqual(
            tuple(out["terminal_states"]),
            ("FINALIZED_SUCCESS", "FINALIZED_TERMINAL_FAILURE"),
        )
        self.assert_no_authority(out)

    def test_persistence_is_cas_exactly_once_and_append_only(self):
        out = persistence.build_execution_finalization_persistence_contract(
            execution_finalization_review=approved_finalization_review(),
        )
        required = set(out["required_persistence_invariants"])
        self.assertTrue({
            "CANONICAL_EXECUTION_ID_REQUIRED",
            "EXISTING_EXECUTION_RECORD_REQUIRED",
            "EXPECTED_PRE_FINALIZATION_REVISION_REQUIRED",
            "COMPARE_AND_SET_REQUIRED",
            "SINGLE_TERMINAL_WINNER_REQUIRED",
            "FINALIZATION_DIGEST_UNIQUENESS_REQUIRED",
            "TERMINAL_STATE_APPEND_ONLY",
            "TERMINAL_STATE_IMMUTABLE",
            "TERMINAL_STATE_DELETE_FORBIDDEN",
            "TERMINAL_STATE_REOPEN_FORBIDDEN",
            "TERMINAL_STATE_DOWNGRADE_FORBIDDEN",
            "TERMINAL_STATE_CROSSGRADE_FORBIDDEN",
        }.issubset(required))
        self.assertTrue(out["compare_and_set_required"])
        self.assertTrue(out["append_only_terminal_record_required"])
        self.assertTrue(out["immutable_terminal_record_required"])
        self.assert_no_authority(out)

    def test_idempotent_replay_and_conflict_semantics_are_explicit(self):
        out = persistence.build_execution_finalization_persistence_contract(
            execution_finalization_review=approved_finalization_review(),
        )
        required = set(out["required_persistence_invariants"])
        self.assertIn(
            "SAME_FINALIZATION_SAME_DIGEST_IS_IDEMPOTENT_REPLAY",
            required,
        )
        self.assertIn(
            "SAME_EXECUTION_DIFFERENT_FINALIZATION_DIGEST_IS_CONFLICT",
            required,
        )
        self.assertTrue(out["idempotent_same_digest_replay_required"])
        self.assertTrue(out["different_digest_conflict_required"])
        self.assertTrue(out["terminal_state_crossgrade_forbidden"])
        self.assertTrue(out["terminal_state_downgrade_forbidden"])
        self.assert_no_authority(out)

    def test_crash_and_reopen_semantics_preserve_truth(self):
        out = persistence.build_execution_finalization_persistence_contract(
            execution_finalization_review=approved_finalization_review(),
        )
        required = set(out["required_persistence_invariants"])
        self.assertTrue({
            "DURABLE_REOPEN_MUST_PRESERVE_TERMINAL_RECORD",
            "CRASH_AFTER_COMMIT_MUST_REPLAY_TERMINAL_RECORD",
            "CRASH_BEFORE_COMMIT_MUST_NOT_INFER_FINALIZATION",
        }.issubset(required))
        assertions = set(out["required_reopen_assertions"])
        self.assertTrue({
            "TERMINAL_RECORD_EXISTS_AFTER_REOPEN",
            "TERMINAL_STATE_MATCHES_COMMITTED_STATE",
            "FINALIZATION_RECORD_DIGEST_MATCH",
            "AUDIT_CHAIN_DIGEST_MATCH",
            "EXECUTION_ID_MATCH",
            "NO_DUPLICATE_TERMINAL_RECORD",
            "NO_TERMINAL_REVISION_REGRESSION",
        }.issubset(assertions))
        self.assertTrue(out["durable_reopen_consistency_required"])
        self.assertTrue(out["crash_before_commit_cannot_infer_finalization"])
        self.assertTrue(out["crash_after_commit_replays_terminal_record"])
        self.assert_no_authority(out)

    def test_bindings_cover_terminal_chain_of_custody(self):
        out = persistence.build_execution_finalization_persistence_contract(
            execution_finalization_review=approved_finalization_review(),
        )
        fields = set(out["required_persistence_bindings"])
        self.assertTrue({
            "execution_id",
            "expected_pre_finalization_revision",
            "final_execution_state",
            "execution_finalization_contract_digest",
            "external_effect_outcome_receipt_digest",
            "outcome_reconciliation_record_digest",
            "durable_dispatch_record_digest",
            "external_effect_call_boundary_digest",
            "execution_envelope_digest",
            "fresh_owner_authorization_digest",
            "provider_adapter_attestation_digest",
            "provider_capability_binding_digest",
            "idempotency_key_digest",
            "effect_key_digest",
            "provider_request_correlation_digest",
            "terminal_evidence_set_digest",
            "expected_postcondition_digest",
            "rollback_plan_digest",
            "rollback_or_compensation_settlement_digest",
            "finops_estimate_digest",
            "finops_observation_digest",
            "observability_trace_id",
            "audit_chain_digest",
            "finalization_record_digest",
        }.issubset(fields))
        self.assert_no_authority(out)

    def test_conflicts_fail_closed_instead_of_rewriting_terminal_truth(self):
        out = persistence.build_execution_finalization_persistence_contract(
            execution_finalization_review=approved_finalization_review(),
        )
        conflicts = set(out["persistence_conflicts"])
        self.assertTrue({
            "EXECUTION_RECORD_MISSING",
            "PRE_FINALIZATION_REVISION_MISMATCH",
            "EXECUTION_ALREADY_FINALIZED_WITH_DIFFERENT_STATE",
            "EXECUTION_ALREADY_FINALIZED_WITH_DIFFERENT_DIGEST",
            "FINALIZATION_DIGEST_CONFLICT",
            "AUDIT_CHAIN_DIGEST_CONFLICT",
            "OUTCOME_CHAIN_DIGEST_CONFLICT",
            "TERMINAL_RECORD_DUPLICATE_CONFLICT",
            "REOPEN_TERMINAL_RECORD_MISMATCH",
        }.issubset(conflicts))
        self.assert_no_authority(out)

    def test_contract_does_not_open_store_write_or_execute(self):
        out = persistence.build_execution_finalization_persistence_contract(
            execution_finalization_review=approved_finalization_review(),
        )
        for key in (
            "store_opened",
            "database_opened",
            "transaction_started",
            "cas_attempted",
            "cas_succeeded",
            "finalization_record_written",
            "terminal_state_persisted",
            "terminal_state_reopened",
            "execution_finalized",
            "network_called",
            "provider_called",
            "retry_performed",
            "reconciliation_performed",
            "rollback_performed",
            "compensation_performed",
            "external_effect_attempted",
            "external_action_executed",
        ):
            self.assertFalse(out[key], key)
        self.assert_no_authority(out)

    def test_next_step_is_audit_seal_design_only(self):
        out = persistence.build_execution_finalization_persistence_contract(
            execution_finalization_review=approved_finalization_review(),
        )
        self.assertEqual(
            out["next_allowed_step"],
            "DESIGN_EXECUTION_AUDIT_SEAL_CONTRACT_ONLY",
        )
        self.assertFalse(out["execution_allowed"])
        self.assertFalse(out["external_action_executed"])
        self.assert_no_authority(out)


if __name__ == "__main__":
    unittest.main()
