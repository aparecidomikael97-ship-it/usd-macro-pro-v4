from __future__ import annotations

import unittest

import atlasquant_aion_b2b_execution_terminal_certificate_persistence_contract_v1 as persistence
import atlasquant_aion_b2b_execution_terminal_certificate_read_model_v1 as read_model
from test_atlasquant_aion_b2b_execution_terminal_certificate_persistence_contract_v1 import (
    approved_terminal_certificate_review,
)


def approved_certificate_persistence_review():
    return persistence.build_execution_terminal_certificate_persistence_contract(
        terminal_certificate_review=approved_terminal_certificate_review(),
    )


class ExecutionTerminalCertificateReadModelV1Tests(unittest.TestCase):
    def assert_no_authority(self, out):
        for key in read_model.FALSE_FIELDS:
            self.assertIs(out[key], False, key)

    def test_approved_persistence_unlocks_design_only_read_model(self):
        out = read_model.build_execution_terminal_certificate_read_model_contract(
            terminal_certificate_persistence_review=approved_certificate_persistence_review(),
        )
        self.assertEqual(out["state"], read_model.READY)
        self.assertTrue(out["execution_terminal_certificate_read_model_design_only"])
        self.assertEqual(
            out["read_model_mode"],
            "READ_ONLY_TERMINAL_CERTIFICATE_PROJECTION",
        )
        self.assertTrue(out["read_only"])
        self.assertTrue(out["observational_only"])
        self.assertTrue(out["persisted_certificate_required"])
        self.assertFalse(out["read_model_creates_execution_authority"])
        self.assertFalse(out["read_model_authorizes_retry"])
        self.assertFalse(out["read_model_authorizes_reopen"])
        self.assertFalse(out["read_model_authorizes_external_effect"])
        self.assertEqual(
            out["next_allowed_step"],
            "DESIGN_EXECUTION_TERMINAL_CERTIFICATE_READ_MODEL_UI_ONLY",
        )
        self.assert_no_authority(out)

    def test_upstream_must_be_exact_ready_state(self):
        row = approved_certificate_persistence_review()
        row["state"] = "BLOCKED"
        out = read_model.build_execution_terminal_certificate_read_model_contract(
            terminal_certificate_persistence_review=row,
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn(
            "TERMINAL_CERTIFICATE_PERSISTENCE_DESIGN_REVIEW_REQUIRED",
            out["blockers"],
        )
        self.assert_no_authority(out)

    def test_upstream_side_effect_flip_blocks(self):
        row = approved_certificate_persistence_review()
        row["certificate_persisted"] = True
        out = read_model.build_execution_terminal_certificate_read_model_contract(
            terminal_certificate_persistence_review=row,
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn(
            "TERMINAL_CERTIFICATE_PERSISTENCE_UNSAFE_FIELD:certificate_persisted",
            out["blockers"],
        )
        self.assert_no_authority(out)

    def test_required_persistence_semantics_cannot_be_relaxed(self):
        for field, blocker in (
            ("compare_and_set_required", "COMPARE_AND_SET_CERTIFICATE_PERSISTENCE_REQUIRED"),
            ("exactly_once_certificate_commit_required", "EXACTLY_ONCE_CERTIFICATE_COMMIT_REQUIRED"),
            ("append_only_certificate_record_required", "APPEND_ONLY_CERTIFICATE_RECORD_REQUIRED"),
            ("immutable_certificate_record_required", "IMMUTABLE_CERTIFICATE_RECORD_REQUIRED"),
            ("durable_reopen_consistency_required", "DURABLE_REOPEN_CONSISTENCY_REQUIRED"),
            ("terminal_execution_reopen_forbidden", "TERMINAL_EXECUTION_REOPEN_MUST_BE_FORBIDDEN"),
        ):
            row = approved_certificate_persistence_review()
            row[field] = False
            out = read_model.build_execution_terminal_certificate_read_model_contract(
                terminal_certificate_persistence_review=row,
            )
            self.assertEqual(out["state"], "BLOCKED")
            self.assertIn(blocker, out["blockers"])
            self.assert_no_authority(out)

    def test_projection_states_fail_closed(self):
        out = read_model.build_execution_terminal_certificate_read_model_contract(
            terminal_certificate_persistence_review=approved_certificate_persistence_review(),
        )
        self.assertEqual(
            tuple(out["read_model_states"]),
            ("VERIFIED", "MISMATCH", "UNAVAILABLE", "STALE"),
        )
        self.assertTrue(out["verification_status_fail_closed"])
        self.assertTrue(out["verified_requires_all_bound_digests_match"])
        self.assertTrue(out["unavailable_never_implies_verified"])
        self.assertTrue(out["stale_never_implies_verified"])
        self.assertTrue(out["mismatch_never_implies_verified"])
        self.assert_no_authority(out)

    def test_projection_fields_bind_terminal_evidence_without_raw_material(self):
        out = read_model.build_execution_terminal_certificate_read_model_contract(
            terminal_certificate_persistence_review=approved_certificate_persistence_review(),
        )
        fields = set(out["required_read_model_fields"])
        self.assertTrue({
            "tenant_id",
            "workspace_id",
            "execution_id",
            "final_execution_state",
            "terminal_revision",
            "certificate_status",
            "certificate_manifest_digest",
            "certificate_digest",
            "certificate_persistence_record_digest",
            "finalization_record_digest",
            "audit_seal_manifest_digest",
            "audit_seal_persistence_record_digest",
            "terminal_evidence_set_digest",
            "finops_observation_digest",
            "observability_trace_id",
            "pre_terminal_audit_chain_digest",
            "digest_algorithm",
            "canonical_encoding",
        }.issubset(fields))
        forbidden = set(out["forbidden_read_model_material"])
        self.assertTrue({
            "private_signing_key_value",
            "credential_value",
            "secret_value",
            "api_key_value",
            "access_token_value",
            "private_key_value",
            "payload_body_value",
            "raw_provider_response_body",
            "raw_customer_message_body",
            "shell_command_value",
        }.issubset(forbidden))
        self.assert_no_authority(out)

    def test_invariants_keep_read_model_observational(self):
        out = read_model.build_execution_terminal_certificate_read_model_contract(
            terminal_certificate_persistence_review=approved_certificate_persistence_review(),
        )
        required = set(out["required_read_model_invariants"])
        self.assertTrue({
            "PERSISTED_TERMINAL_CERTIFICATE_REQUIRED",
            "TENANT_SCOPE_REQUIRED",
            "WORKSPACE_SCOPE_REQUIRED",
            "CANONICAL_EXECUTION_ID_REQUIRED",
            "TERMINAL_EXECUTION_REQUIRED",
            "CERTIFICATE_RECORD_IMMUTABLE",
            "CERTIFICATE_RECORD_APPEND_ONLY",
            "DURABLE_REOPEN_CONSISTENCY_REQUIRED",
            "ANY_MISMATCH_MUST_NOT_RENDER_VERIFIED",
            "MISSING_EVIDENCE_MUST_NOT_RENDER_VERIFIED",
            "STALE_EVIDENCE_MUST_NOT_RENDER_VERIFIED",
            "READ_MODEL_IS_OBSERVATIONAL_ONLY",
            "READ_MODEL_CANNOT_ISSUE_CERTIFICATE",
            "READ_MODEL_CANNOT_SIGN_CERTIFICATE",
            "READ_MODEL_CANNOT_REOPEN_EXECUTION",
            "READ_MODEL_CANNOT_AUTHORIZE_RETRY",
            "READ_MODEL_CANNOT_AUTHORIZE_EXTERNAL_EFFECT",
            "READ_MODEL_CANNOT_CREATE_EXECUTION_AUTHORITY",
        }.issubset(required))
        self.assert_no_authority(out)

    def test_display_rules_never_turn_status_into_authority(self):
        out = read_model.build_execution_terminal_certificate_read_model_contract(
            terminal_certificate_persistence_review=approved_certificate_persistence_review(),
        )
        rules = set(out["required_verification_display_rules"])
        self.assertTrue({
            "VERIFIED_REQUIRES_ALL_BOUND_DIGESTS_MATCH",
            "MISMATCH_SHOWS_FAIL_CLOSED_STATUS",
            "UNAVAILABLE_SHOWS_EVIDENCE_MISSING_STATUS",
            "STALE_SHOWS_REFRESH_REQUIRED_STATUS",
            "NO_STATUS_GRANTS_EXECUTION_AUTHORITY",
            "NO_STATUS_GRANTS_RETRY_AUTHORITY",
            "NO_STATUS_GRANTS_REOPEN_AUTHORITY",
            "NO_STATUS_GRANTS_EXTERNAL_EFFECT_AUTHORITY",
        }.issubset(rules))
        self.assert_no_authority(out)

    def test_design_layer_performs_no_read_or_effect(self):
        out = read_model.build_execution_terminal_certificate_read_model_contract(
            terminal_certificate_persistence_review=approved_certificate_persistence_review(),
        )
        self.assertFalse(out["read_model_verified"])
        self.assertFalse(out["certificate_record_loaded"])
        self.assertFalse(out["store_opened"])
        self.assertFalse(out["database_opened"])
        self.assertFalse(out["network_called"])
        self.assertFalse(out["provider_called"])
        self.assertFalse(out["external_action_executed"])
        self.assertFalse(out["billing_executed"])
        self.assertFalse(out["crm_write_authorized"])
        self.assertFalse(out["deploy_authorized"])
        self.assertFalse(out["production_mutation_performed"])
        self.assertFalse(out["execution_allowed"])
        self.assertFalse(out["executes_action"])
        self.assert_no_authority(out)


if __name__ == "__main__":
    unittest.main()
