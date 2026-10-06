from __future__ import annotations

import unittest

import atlasquant_aion_b2b_execution_terminal_certificate_contract_v1 as certificate
import atlasquant_aion_b2b_execution_terminal_certificate_persistence_contract_v1 as persistence
from test_atlasquant_aion_b2b_execution_terminal_certificate_contract_v1 import (
    approved_seal_persistence_review,
)


def approved_terminal_certificate_review():
    return certificate.build_execution_terminal_certificate_contract(
        audit_seal_persistence_review=approved_seal_persistence_review(),
    )


class ExecutionTerminalCertificatePersistenceContractV1Tests(unittest.TestCase):
    def assert_no_authority(self, out):
        for key in persistence.FALSE_FIELDS:
            self.assertIs(out[key], False, key)

    def test_approved_certificate_unlocks_design_only(self):
        out = persistence.build_execution_terminal_certificate_persistence_contract(
            terminal_certificate_review=approved_terminal_certificate_review(),
        )
        self.assertEqual(out["state"], persistence.READY)
        self.assertTrue(out["execution_terminal_certificate_persistence_design_only"])
        self.assertEqual(
            out["persistence_mode"],
            "APPEND_ONLY_CAS_TERMINAL_CERTIFICATE_COMMIT",
        )
        self.assertTrue(out["compare_and_set_required"])
        self.assertTrue(out["exactly_once_certificate_commit_required"])
        self.assertFalse(out["persistence_creates_execution_authority"])
        self.assertEqual(out["digest_algorithm"], "SHA256")
        self.assert_no_authority(out)

    def test_certificate_must_be_exact_ready_state(self):
        row = approved_terminal_certificate_review()
        row["state"] = "BLOCKED"
        out = persistence.build_execution_terminal_certificate_persistence_contract(
            terminal_certificate_review=row,
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("TERMINAL_CERTIFICATE_DESIGN_REVIEW_REQUIRED", out["blockers"])
        self.assert_no_authority(out)

    def test_upstream_write_flip_blocks(self):
        row = approved_terminal_certificate_review()
        row["certificate_persisted"] = True
        out = persistence.build_execution_terminal_certificate_persistence_contract(
            terminal_certificate_review=row,
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn(
            "TERMINAL_CERTIFICATE_UNSAFE_FIELD:certificate_persisted",
            out["blockers"],
        )
        self.assert_no_authority(out)

    def test_persistence_is_append_only_cas_and_exactly_once(self):
        out = persistence.build_execution_terminal_certificate_persistence_contract(
            terminal_certificate_review=approved_terminal_certificate_review(),
        )
        required = set(out["required_certificate_persistence_invariants"])
        self.assertTrue({
            "CANONICAL_EXECUTION_ID_REQUIRED",
            "TERMINAL_EXECUTION_REQUIRED",
            "EXPECTED_PRE_CERTIFICATE_REVISION_REQUIRED",
            "COMPARE_AND_SET_REQUIRED",
            "SINGLE_CERTIFICATE_WINNER_REQUIRED",
            "CERTIFICATE_DIGEST_UNIQUENESS_REQUIRED",
            "CERTIFICATE_RECORD_APPEND_ONLY",
            "CERTIFICATE_RECORD_IMMUTABLE",
            "CERTIFICATE_RECORD_DELETE_FORBIDDEN",
            "CERTIFICATE_RECORD_REPLACE_FORBIDDEN",
            "TERMINAL_EXECUTION_REOPEN_FORBIDDEN",
        }.issubset(required))
        self.assert_no_authority(out)

    def test_replay_and_conflict_semantics_preserve_single_truth(self):
        out = persistence.build_execution_terminal_certificate_persistence_contract(
            terminal_certificate_review=approved_terminal_certificate_review(),
        )
        required = set(out["required_certificate_persistence_invariants"])
        self.assertIn(
            "SAME_CERTIFICATE_SAME_DIGEST_IS_IDEMPOTENT_REPLAY",
            required,
        )
        self.assertIn(
            "SAME_TERMINAL_IDENTITY_DIFFERENT_CERTIFICATE_DIGEST_IS_CONFLICT",
            required,
        )
        self.assertTrue(out["idempotent_same_digest_replay_required"])
        self.assertTrue(out["different_digest_conflict_required"])
        self.assert_no_authority(out)

    def test_crash_and_reopen_preserve_certificate_truth(self):
        out = persistence.build_execution_terminal_certificate_persistence_contract(
            terminal_certificate_review=approved_terminal_certificate_review(),
        )
        assertions = set(out["required_certificate_reopen_assertions"])
        self.assertTrue({
            "CERTIFICATE_RECORD_EXISTS_AFTER_REOPEN",
            "EXECUTION_ID_MATCH",
            "TERMINAL_REVISION_MATCH",
            "FINAL_EXECUTION_STATE_MATCH",
            "FINALIZATION_RECORD_DIGEST_MATCH",
            "AUDIT_SEAL_MANIFEST_DIGEST_MATCH",
            "AUDIT_SEAL_PERSISTENCE_RECORD_DIGEST_MATCH",
            "CERTIFICATE_MANIFEST_DIGEST_MATCH",
            "CERTIFICATE_DIGEST_MATCH",
            "NO_DUPLICATE_CERTIFICATE_RECORD",
            "NO_CERTIFICATE_REVISION_REGRESSION",
        }.issubset(assertions))
        self.assertTrue(out["durable_reopen_consistency_required"])
        self.assertTrue(out["crash_before_commit_cannot_infer_persisted_certificate"])
        self.assertTrue(out["crash_after_commit_replays_certificate_record"])
        self.assert_no_authority(out)

    def test_bindings_cover_exact_terminal_certificate_identity(self):
        out = persistence.build_execution_terminal_certificate_persistence_contract(
            terminal_certificate_review=approved_terminal_certificate_review(),
        )
        fields = set(out["required_certificate_persistence_bindings"])
        self.assertTrue({
            "execution_id",
            "terminal_revision",
            "expected_pre_certificate_revision",
            "final_execution_state",
            "finalization_record_digest",
            "execution_finalization_persistence_record_digest",
            "audit_seal_manifest_digest",
            "audit_seal_persistence_record_digest",
            "execution_terminal_certificate_contract_digest",
            "certificate_manifest_digest",
            "certificate_digest",
            "idempotency_key_digest",
            "effect_key_digest",
            "provider_request_correlation_digest",
            "terminal_evidence_set_digest",
            "finops_estimate_digest",
            "finops_observation_digest",
            "pre_terminal_audit_chain_digest",
        }.issubset(fields))
        self.assert_no_authority(out)

    def test_conflicts_fail_closed(self):
        out = persistence.build_execution_terminal_certificate_persistence_contract(
            terminal_certificate_review=approved_terminal_certificate_review(),
        )
        conflicts = set(out["certificate_persistence_conflicts"])
        self.assertTrue({
            "TERMINAL_EXECUTION_RECORD_MISSING",
            "FINALIZATION_RECORD_MISSING",
            "AUDIT_SEAL_RECORD_MISSING",
            "TERMINAL_CERTIFICATE_CONTRACT_INVALID",
            "PRE_CERTIFICATE_REVISION_MISMATCH",
            "EXECUTION_ALREADY_CERTIFIED_WITH_DIFFERENT_DIGEST",
            "TERMINAL_REVISION_ALREADY_CERTIFIED_WITH_DIFFERENT_DIGEST",
            "FINALIZATION_RECORD_DIGEST_CONFLICT",
            "AUDIT_SEAL_DIGEST_CONFLICT",
            "CERTIFICATE_MANIFEST_DIGEST_CONFLICT",
            "FINOPS_OBSERVATION_CONFLICT",
            "AUDIT_CHAIN_DIGEST_CONFLICT",
            "REOPEN_CERTIFICATE_RECORD_MISMATCH",
        }.issubset(conflicts))
        self.assert_no_authority(out)

    def test_contract_does_not_open_store_sign_persist_or_execute(self):
        out = persistence.build_execution_terminal_certificate_persistence_contract(
            terminal_certificate_review=approved_terminal_certificate_review(),
        )
        for key in (
            "store_opened",
            "database_opened",
            "transaction_started",
            "cas_attempted",
            "cas_succeeded",
            "certificate_generated",
            "certificate_signed",
            "certificate_record_written",
            "certificate_persisted",
            "certificate_reopened",
            "private_key_loaded",
            "signing_key_loaded",
            "execution_reopened",
            "network_called",
            "provider_called",
            "external_action_executed",
        ):
            self.assertFalse(out[key], key)
        self.assert_no_authority(out)

    def test_next_step_is_terminal_certificate_read_model_only(self):
        out = persistence.build_execution_terminal_certificate_persistence_contract(
            terminal_certificate_review=approved_terminal_certificate_review(),
        )
        self.assertEqual(
            out["next_allowed_step"],
            "DESIGN_EXECUTION_TERMINAL_CERTIFICATE_READ_MODEL_ONLY",
        )
        self.assertFalse(out["execution_allowed"])
        self.assertFalse(out["external_action_executed"])
        self.assert_no_authority(out)


if __name__ == "__main__":
    unittest.main()
