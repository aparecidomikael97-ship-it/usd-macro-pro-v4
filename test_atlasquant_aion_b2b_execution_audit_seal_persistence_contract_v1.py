from __future__ import annotations

import unittest

import atlasquant_aion_b2b_execution_audit_seal_contract_v1 as seal
import atlasquant_aion_b2b_execution_audit_seal_persistence_contract_v1 as persistence
from test_atlasquant_aion_b2b_execution_audit_seal_contract_v1 import (
    approved_persistence_review,
)


def approved_seal_review():
    return seal.build_execution_audit_seal_contract(
        finalization_persistence_review=approved_persistence_review(),
    )


class ExecutionAuditSealPersistenceContractV1Tests(unittest.TestCase):
    def assert_no_authority(self, out):
        for key in persistence.FALSE_FIELDS:
            self.assertIs(out[key], False, key)

    def test_approved_seal_unlocks_design_only(self):
        out = persistence.build_execution_audit_seal_persistence_contract(
            audit_seal_review=approved_seal_review(),
        )
        self.assertEqual(out["state"], persistence.READY)
        self.assertTrue(out["execution_audit_seal_persistence_design_only"])
        self.assertEqual(out["persistence_mode"], "APPEND_ONLY_CAS_AUDIT_SEAL_COMMIT")
        self.assertTrue(out["compare_and_set_required"])
        self.assertTrue(out["exactly_once_seal_commit_required"])
        self.assertFalse(out["persistence_creates_execution_authority"])
        self.assertEqual(out["digest_algorithm"], "SHA256")
        self.assert_no_authority(out)

    def test_seal_must_be_exact_ready_state(self):
        row = approved_seal_review()
        row["state"] = "BLOCKED"
        out = persistence.build_execution_audit_seal_persistence_contract(
            audit_seal_review=row,
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("AUDIT_SEAL_DESIGN_REVIEW_REQUIRED", out["blockers"])
        self.assert_no_authority(out)

    def test_upstream_effect_flip_blocks(self):
        row = approved_seal_review()
        row["seal_persisted"] = True
        out = persistence.build_execution_audit_seal_persistence_contract(
            audit_seal_review=row,
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("AUDIT_SEAL_UNSAFE_FIELD:seal_persisted", out["blockers"])
        self.assert_no_authority(out)

    def test_persistence_is_append_only_cas_and_exactly_once(self):
        out = persistence.build_execution_audit_seal_persistence_contract(
            audit_seal_review=approved_seal_review(),
        )
        required = set(out["required_seal_persistence_invariants"])
        self.assertTrue({
            "CANONICAL_EXECUTION_ID_REQUIRED",
            "TERMINAL_REVISION_REQUIRED",
            "EXPECTED_PRE_SEAL_REVISION_REQUIRED",
            "COMPARE_AND_SET_REQUIRED",
            "SINGLE_SEAL_WINNER_REQUIRED",
            "AUDIT_SEAL_DIGEST_UNIQUENESS_REQUIRED",
            "SEAL_RECORD_APPEND_ONLY",
            "SEAL_RECORD_IMMUTABLE",
            "SEAL_RECORD_DELETE_FORBIDDEN",
            "SEAL_RECORD_REPLACE_FORBIDDEN",
            "TERMINAL_EXECUTION_REOPEN_FORBIDDEN",
        }.issubset(required))
        self.assert_no_authority(out)

    def test_replay_and_conflict_semantics_preserve_single_truth(self):
        out = persistence.build_execution_audit_seal_persistence_contract(
            audit_seal_review=approved_seal_review(),
        )
        required = set(out["required_seal_persistence_invariants"])
        self.assertIn("SAME_SEAL_SAME_DIGEST_IS_IDEMPOTENT_REPLAY", required)
        self.assertIn(
            "SAME_TERMINAL_IDENTITY_DIFFERENT_SEAL_DIGEST_IS_CONFLICT",
            required,
        )
        self.assertTrue(out["idempotent_same_digest_replay_required"])
        self.assertTrue(out["different_digest_conflict_required"])
        self.assert_no_authority(out)

    def test_crash_and_reopen_preserve_seal_truth(self):
        out = persistence.build_execution_audit_seal_persistence_contract(
            audit_seal_review=approved_seal_review(),
        )
        assertions = set(out["required_seal_reopen_assertions"])
        self.assertTrue({
            "SEAL_RECORD_EXISTS_AFTER_REOPEN",
            "EXECUTION_ID_MATCH",
            "TERMINAL_REVISION_MATCH",
            "FINAL_EXECUTION_STATE_MATCH",
            "FINALIZATION_RECORD_DIGEST_MATCH",
            "AUDIT_SEAL_MANIFEST_DIGEST_MATCH",
            "AUDIT_SEAL_DIGEST_MATCH",
            "DIGEST_ALGORITHM_MATCH",
            "CANONICAL_ENCODING_MATCH",
            "NO_DUPLICATE_SEAL_RECORD",
            "NO_SEAL_REVISION_REGRESSION",
        }.issubset(assertions))
        self.assertTrue(out["durable_reopen_consistency_required"])
        self.assertTrue(out["crash_before_commit_cannot_infer_persisted_seal"])
        self.assertTrue(out["crash_after_commit_replays_seal_record"])
        self.assert_no_authority(out)

    def test_bindings_cover_exact_terminal_seal_identity(self):
        out = persistence.build_execution_audit_seal_persistence_contract(
            audit_seal_review=approved_seal_review(),
        )
        fields = set(out["required_seal_persistence_bindings"])
        self.assertTrue({
            "execution_id",
            "terminal_revision",
            "expected_pre_seal_revision",
            "final_execution_state",
            "finalization_record_digest",
            "execution_finalization_persistence_record_digest",
            "execution_audit_seal_contract_digest",
            "audit_seal_manifest_digest",
            "audit_seal_digest",
            "digest_algorithm",
            "canonical_encoding",
            "pre_terminal_audit_chain_digest",
            "finops_observation_digest",
            "observability_trace_id",
        }.issubset(fields))
        self.assert_no_authority(out)

    def test_conflicts_fail_closed(self):
        out = persistence.build_execution_audit_seal_persistence_contract(
            audit_seal_review=approved_seal_review(),
        )
        conflicts = set(out["seal_persistence_conflicts"])
        self.assertTrue({
            "TERMINAL_RECORD_MISSING",
            "PRE_SEAL_REVISION_MISMATCH",
            "AUDIT_SEAL_CONTRACT_INVALID",
            "EXECUTION_ALREADY_SEALED_WITH_DIFFERENT_DIGEST",
            "TERMINAL_REVISION_ALREADY_SEALED_WITH_DIFFERENT_DIGEST",
            "FINALIZATION_RECORD_DIGEST_CONFLICT",
            "SEAL_MANIFEST_DIGEST_CONFLICT",
            "AUDIT_CHAIN_DIGEST_CONFLICT",
            "FINOPS_OBSERVATION_CONFLICT",
            "REOPEN_SEAL_RECORD_MISMATCH",
        }.issubset(conflicts))
        self.assert_no_authority(out)

    def test_contract_does_not_open_store_sign_persist_or_execute(self):
        out = persistence.build_execution_audit_seal_persistence_contract(
            audit_seal_review=approved_seal_review(),
        )
        for key in (
            "store_opened",
            "database_opened",
            "transaction_started",
            "cas_attempted",
            "cas_succeeded",
            "seal_generated",
            "seal_signed",
            "seal_record_written",
            "seal_persisted",
            "seal_reopened",
            "private_key_loaded",
            "execution_reopened",
            "network_called",
            "provider_called",
            "external_action_executed",
        ):
            self.assertFalse(out[key], key)
        self.assert_no_authority(out)

    def test_next_step_is_terminal_certificate_design_only(self):
        out = persistence.build_execution_audit_seal_persistence_contract(
            audit_seal_review=approved_seal_review(),
        )
        self.assertEqual(
            out["next_allowed_step"],
            "DESIGN_EXECUTION_TERMINAL_CERTIFICATE_CONTRACT_ONLY",
        )
        self.assertFalse(out["execution_allowed"])
        self.assertFalse(out["external_action_executed"])
        self.assert_no_authority(out)


if __name__ == "__main__":
    unittest.main()
