from __future__ import annotations

import unittest

import atlasquant_aion_b2b_execution_audit_seal_contract_v1 as seal
import atlasquant_aion_b2b_execution_finalization_persistence_contract_v1 as persistence
from test_atlasquant_aion_b2b_execution_finalization_persistence_contract_v1 import (
    approved_finalization_review,
)


def approved_persistence_review():
    return persistence.build_execution_finalization_persistence_contract(
        execution_finalization_review=approved_finalization_review(),
    )


class ExecutionAuditSealContractV1Tests(unittest.TestCase):
    def assert_no_authority(self, out):
        for key in seal.FALSE_FIELDS:
            self.assertIs(out[key], False, key)

    def test_approved_persistence_unlocks_design_only(self):
        out = seal.build_execution_audit_seal_contract(
            finalization_persistence_review=approved_persistence_review(),
        )
        self.assertEqual(out["state"], seal.READY)
        self.assertTrue(out["execution_audit_seal_design_only"])
        self.assertEqual(
            out["seal_mode"],
            "DETERMINISTIC_TERMINAL_CHAIN_OF_CUSTODY_MANIFEST",
        )
        self.assertEqual(out["digest_algorithm"], "SHA256")
        self.assertEqual(out["canonical_encoding"], "UTF8_CANONICAL_JSON")
        self.assertTrue(out["seal_immutable"])
        self.assertTrue(out["seal_append_only"])
        self.assertFalse(out["seal_creates_execution_authority"])
        self.assert_no_authority(out)

    def test_persistence_must_be_exact_ready_state(self):
        row = approved_persistence_review()
        row["state"] = "BLOCKED"
        out = seal.build_execution_audit_seal_contract(
            finalization_persistence_review=row,
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn(
            "FINALIZATION_PERSISTENCE_DESIGN_REVIEW_REQUIRED",
            out["blockers"],
        )
        self.assert_no_authority(out)

    def test_upstream_persistence_flip_blocks(self):
        row = approved_persistence_review()
        row["terminal_state_persisted"] = True
        out = seal.build_execution_audit_seal_contract(
            finalization_persistence_review=row,
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn(
            "FINALIZATION_PERSISTENCE_UNSAFE_FIELD:terminal_state_persisted",
            out["blockers"],
        )
        self.assert_no_authority(out)

    def test_seal_binds_full_terminal_chain_of_custody(self):
        out = seal.build_execution_audit_seal_contract(
            finalization_persistence_review=approved_persistence_review(),
        )
        fields = set(out["required_seal_bindings"])
        self.assertTrue({
            "execution_id",
            "final_execution_state",
            "terminal_revision",
            "finalization_record_digest",
            "execution_finalization_contract_digest",
            "execution_finalization_persistence_contract_digest",
            "durable_dispatch_record_digest",
            "external_effect_call_boundary_digest",
            "external_effect_outcome_receipt_digest",
            "outcome_reconciliation_record_digest",
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
            "pre_terminal_audit_chain_digest",
        }.issubset(fields))
        self.assert_no_authority(out)

    def test_seal_is_deterministic_and_sensitive_to_bound_changes(self):
        out = seal.build_execution_audit_seal_contract(
            finalization_persistence_review=approved_persistence_review(),
        )
        required = set(out["required_seal_invariants"])
        self.assertTrue({
            "CANONICAL_FIELD_ORDER_REQUIRED",
            "CANONICAL_ENCODING_REQUIRED",
            "DETERMINISTIC_DIGEST_REQUIRED",
            "SHA256_DIGEST_REQUIRED",
            "SAME_MANIFEST_SAME_DIGEST",
            "ANY_BOUND_FIELD_CHANGE_CHANGES_DIGEST",
        }.issubset(required))
        self.assertTrue(out["same_manifest_same_digest_required"])
        self.assertTrue(out["any_bound_field_change_changes_digest_required"])
        self.assert_no_authority(out)

    def test_unknown_or_unsettled_work_invalidates_seal(self):
        out = seal.build_execution_audit_seal_contract(
            finalization_persistence_review=approved_persistence_review(),
        )
        invalidators = set(out["seal_invalidators"])
        self.assertTrue({
            "MISSING_TERMINAL_PERSISTENCE_RECORD",
            "NON_TERMINAL_EXECUTION_STATE",
            "OUTCOME_UNKNOWN_PRESENT",
            "STILL_OUTCOME_UNKNOWN_PRESENT",
            "MISSING_REQUIRED_BINDING",
            "FINALIZATION_RECORD_DIGEST_MISMATCH",
            "OUTCOME_CHAIN_DIGEST_MISMATCH",
            "RECONCILIATION_CHAIN_DIGEST_MISMATCH",
            "ROLLBACK_COMPENSATION_SETTLEMENT_DIGEST_MISMATCH",
            "FINOPS_DIGEST_MISMATCH",
            "AUDIT_CHAIN_DIGEST_MISMATCH",
            "SEAL_DIGEST_MISMATCH",
        }.issubset(invalidators))
        self.assert_no_authority(out)

    def test_verification_is_recomputation_and_fail_closed(self):
        out = seal.build_execution_audit_seal_contract(
            finalization_persistence_review=approved_persistence_review(),
        )
        rules = set(out["required_verification_rules"])
        self.assertTrue({
            "RECOMPUTE_CANONICAL_MANIFEST_DIGEST",
            "COMPARE_EXPECTED_AND_RECOMPUTED_SEAL_DIGEST",
            "VERIFY_TERMINAL_RECORD_DIGEST_MATCH",
            "VERIFY_EXECUTION_ID_MATCH",
            "VERIFY_TERMINAL_STATE_MATCH",
            "VERIFY_TERMINAL_REVISION_MATCH",
            "VERIFY_IDEMPOTENCY_KEY_DIGEST_MATCH",
            "VERIFY_EFFECT_KEY_DIGEST_MATCH",
            "VERIFY_PROVIDER_CORRELATION_MATCH",
            "VERIFY_OUTCOME_CHAIN_DIGESTS_MATCH",
            "VERIFY_FINOPS_DIGESTS_MATCH",
            "VERIFY_PRE_TERMINAL_AUDIT_CHAIN_DIGEST_MATCH",
            "ANY_MISMATCH_FAILS_CLOSED",
        }.issubset(rules))
        self.assertTrue(out["any_verification_mismatch_fails_closed"])
        self.assert_no_authority(out)

    def test_seal_never_grants_retry_reopen_or_external_effect(self):
        out = seal.build_execution_audit_seal_contract(
            finalization_persistence_review=approved_persistence_review(),
        )
        self.assertFalse(out["seal_creates_execution_authority"])
        self.assertFalse(out["seal_authorizes_retry"])
        self.assertFalse(out["seal_authorizes_reopen"])
        self.assertFalse(out["seal_authorizes_external_effect"])
        for key in (
            "execution_reopened",
            "execution_authority_created",
            "retry_authorized",
            "retry_performed",
            "network_called",
            "provider_called",
            "external_effect_attempted",
            "external_action_executed",
        ):
            self.assertFalse(out[key], key)
        self.assert_no_authority(out)

    def test_design_does_not_load_real_signing_material(self):
        out = seal.build_execution_audit_seal_contract(
            finalization_persistence_review=approved_persistence_review(),
        )
        forbidden = set(out["forbidden_seal_material"])
        self.assertTrue({
            "private_signing_key_value",
            "secret_value",
            "credential_value",
            "api_key_value",
            "access_token_value",
            "private_key_value",
            "authorization_header_value",
            "payload_body_value",
            "raw_provider_response_body",
            "shell_command_value",
        }.issubset(forbidden))
        self.assertFalse(out["private_key_loaded"])
        self.assertFalse(out["signing_key_loaded"])
        self.assertFalse(out["seal_signed"])
        self.assert_no_authority(out)

    def test_contract_does_not_generate_persist_or_execute(self):
        out = seal.build_execution_audit_seal_contract(
            finalization_persistence_review=approved_persistence_review(),
        )
        for key in (
            "seal_generated",
            "seal_signed",
            "seal_persisted",
            "store_opened",
            "database_opened",
            "terminal_record_loaded",
            "terminal_record_mutated",
            "reconciliation_performed",
            "rollback_performed",
            "compensation_performed",
            "network_called",
            "provider_called",
            "external_action_executed",
        ):
            self.assertFalse(out[key], key)
        self.assert_no_authority(out)

    def test_next_step_is_audit_seal_persistence_design_only(self):
        out = seal.build_execution_audit_seal_contract(
            finalization_persistence_review=approved_persistence_review(),
        )
        self.assertEqual(
            out["next_allowed_step"],
            "DESIGN_EXECUTION_AUDIT_SEAL_PERSISTENCE_CONTRACT_ONLY",
        )
        self.assertFalse(out["execution_allowed"])
        self.assertFalse(out["external_action_executed"])
        self.assert_no_authority(out)


if __name__ == "__main__":
    unittest.main()
