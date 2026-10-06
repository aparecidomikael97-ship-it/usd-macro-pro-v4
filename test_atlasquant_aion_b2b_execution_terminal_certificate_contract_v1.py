from __future__ import annotations

import unittest

import atlasquant_aion_b2b_execution_audit_seal_persistence_contract_v1 as seal_persistence
import atlasquant_aion_b2b_execution_terminal_certificate_contract_v1 as certificate
from test_atlasquant_aion_b2b_execution_audit_seal_persistence_contract_v1 import (
    approved_seal_review,
)


def approved_seal_persistence_review():
    return seal_persistence.build_execution_audit_seal_persistence_contract(
        audit_seal_review=approved_seal_review(),
    )


class ExecutionTerminalCertificateContractV1Tests(unittest.TestCase):
    def assert_no_authority(self, out):
        for key in certificate.FALSE_FIELDS:
            self.assertIs(out[key], False, key)

    def test_approved_seal_persistence_unlocks_design_only(self):
        out = certificate.build_execution_terminal_certificate_contract(
            audit_seal_persistence_review=approved_seal_persistence_review(),
        )
        self.assertEqual(out["state"], certificate.READY)
        self.assertTrue(out["execution_terminal_certificate_design_only"])
        self.assertEqual(
            out["certificate_mode"],
            "VERIFICATION_ONLY_TERMINAL_CHAIN_CERTIFICATE",
        )
        self.assertTrue(out["verification_only"])
        self.assertTrue(out["certificate_read_only"])
        self.assertFalse(out["certificate_is_real_signature"])
        self.assertFalse(out["certificate_creates_execution_authority"])
        self.assert_no_authority(out)

    def test_seal_persistence_must_be_exact_ready_state(self):
        row = approved_seal_persistence_review()
        row["state"] = "BLOCKED"
        out = certificate.build_execution_terminal_certificate_contract(
            audit_seal_persistence_review=row,
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn(
            "AUDIT_SEAL_PERSISTENCE_DESIGN_REVIEW_REQUIRED",
            out["blockers"],
        )
        self.assert_no_authority(out)

    def test_upstream_write_flip_blocks(self):
        row = approved_seal_persistence_review()
        row["seal_persisted"] = True
        out = certificate.build_execution_terminal_certificate_contract(
            audit_seal_persistence_review=row,
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn(
            "AUDIT_SEAL_PERSISTENCE_UNSAFE_FIELD:seal_persisted",
            out["blockers"],
        )
        self.assert_no_authority(out)

    def test_certificate_binds_terminal_chain(self):
        out = certificate.build_execution_terminal_certificate_contract(
            audit_seal_persistence_review=approved_seal_persistence_review(),
        )
        fields=set(out["required_certificate_bindings"])
        self.assertTrue({
            "execution_id",
            "final_execution_state",
            "terminal_revision",
            "finalization_record_digest",
            "execution_finalization_persistence_record_digest",
            "audit_seal_manifest_digest",
            "audit_seal_persistence_record_digest",
            "idempotency_key_digest",
            "effect_key_digest",
            "provider_request_correlation_digest",
            "terminal_evidence_set_digest",
            "rollback_or_compensation_settlement_digest",
            "finops_estimate_digest",
            "finops_observation_digest",
            "observability_trace_id",
            "pre_terminal_audit_chain_digest",
            "certificate_manifest_digest",
        }.issubset(fields))
        self.assert_no_authority(out)

    def test_certificate_requires_reverified_persisted_seal(self):
        out = certificate.build_execution_terminal_certificate_contract(
            audit_seal_persistence_review=approved_seal_persistence_review(),
        )
        invariants=set(out["required_certificate_invariants"])
        self.assertTrue({
            "TERMINAL_EXECUTION_REQUIRED",
            "PERSISTED_FINALIZATION_RECORD_REQUIRED",
            "PERSISTED_AUDIT_SEAL_REQUIRED",
            "DURABLE_AUDIT_SEAL_REOPEN_CONSISTENCY_REQUIRED",
            "PERSISTED_AUDIT_SEAL_DIGEST_MATCH_REQUIRED",
            "NO_OUTCOME_UNKNOWN",
            "NO_STILL_OUTCOME_UNKNOWN",
        }.issubset(invariants))
        self.assertTrue(out["persisted_audit_seal_required"])
        self.assertTrue(out["audit_seal_reopen_consistency_required"])
        self.assert_no_authority(out)

    def test_certificate_is_deterministic_and_fail_closed(self):
        out = certificate.build_execution_terminal_certificate_contract(
            audit_seal_persistence_review=approved_seal_persistence_review(),
        )
        self.assertEqual(out["digest_algorithm"], "SHA256")
        self.assertEqual(out["canonical_encoding"], "UTF8_CANONICAL_JSON")
        self.assertTrue(out["same_manifest_same_digest_required"])
        self.assertTrue(out["any_bound_field_change_changes_digest_required"])
        self.assertTrue(out["any_verification_mismatch_fails_closed"])
        self.assert_no_authority(out)

    def test_invalidators_cover_terminal_integrity_breaks(self):
        out = certificate.build_execution_terminal_certificate_contract(
            audit_seal_persistence_review=approved_seal_persistence_review(),
        )
        invalidators=set(out["certificate_invalidators"])
        self.assertTrue({
            "TERMINAL_EXECUTION_RECORD_MISSING",
            "FINALIZATION_RECORD_MISSING",
            "AUDIT_SEAL_RECORD_MISSING",
            "AUDIT_SEAL_REOPEN_RECORD_MISMATCH",
            "NON_TERMINAL_EXECUTION_STATE",
            "OUTCOME_UNKNOWN_PRESENT",
            "STILL_OUTCOME_UNKNOWN_PRESENT",
            "EXECUTION_ID_MISMATCH",
            "TERMINAL_STATE_MISMATCH",
            "TERMINAL_REVISION_MISMATCH",
            "FINALIZATION_RECORD_DIGEST_MISMATCH",
            "AUDIT_SEAL_MANIFEST_DIGEST_MISMATCH",
            "AUDIT_SEAL_PERSISTENCE_RECORD_DIGEST_MISMATCH",
            "CERTIFICATE_DIGEST_MISMATCH",
        }.issubset(invalidators))
        self.assert_no_authority(out)

    def test_certificate_never_grants_operational_authority(self):
        out = certificate.build_execution_terminal_certificate_contract(
            audit_seal_persistence_review=approved_seal_persistence_review(),
        )
        self.assertFalse(out["certificate_creates_execution_authority"])
        self.assertFalse(out["certificate_authorizes_retry"])
        self.assertFalse(out["certificate_authorizes_reopen"])
        self.assertFalse(out["certificate_authorizes_external_effect"])
        self.assertFalse(out["certificate_is_real_signature"])
        self.assert_no_authority(out)

    def test_contract_does_not_generate_sign_persist_or_execute(self):
        out = certificate.build_execution_terminal_certificate_contract(
            audit_seal_persistence_review=approved_seal_persistence_review(),
        )
        for key in (
            "certificate_generated",
            "certificate_signed",
            "certificate_persisted",
            "certificate_issued",
            "private_key_loaded",
            "signing_key_loaded",
            "store_opened",
            "database_opened",
            "network_called",
            "provider_called",
            "retry_performed",
            "reconciliation_performed",
            "rollback_performed",
            "compensation_performed",
            "external_action_executed",
        ):
            self.assertFalse(out[key], key)
        self.assert_no_authority(out)

    def test_next_step_is_certificate_persistence_design_only(self):
        out = certificate.build_execution_terminal_certificate_contract(
            audit_seal_persistence_review=approved_seal_persistence_review(),
        )
        self.assertEqual(
            out["next_allowed_step"],
            "DESIGN_EXECUTION_TERMINAL_CERTIFICATE_PERSISTENCE_CONTRACT_ONLY",
        )
        self.assertFalse(out["execution_allowed"])
        self.assertFalse(out["external_action_executed"])
        self.assert_no_authority(out)


if __name__ == "__main__":
    unittest.main()
