from __future__ import annotations

import unittest

import atlasquant_aion_b2b_execution_terminal_certificate_read_model_ui_v1 as ui
import atlasquant_aion_b2b_execution_terminal_certificate_runtime_reader_v1 as reader
from test_atlasquant_aion_b2b_execution_terminal_certificate_read_model_ui_v1 import (
    approved_read_model_review,
)


def approved_ui_review():
    return ui.build_execution_terminal_certificate_read_model_ui_contract(
        terminal_certificate_read_model_review=approved_read_model_review(),
    )


class ExecutionTerminalCertificateRuntimeReaderV1Tests(unittest.TestCase):
    def assert_no_authority(self, out):
        for key in reader.FALSE_FIELDS:
            self.assertIs(out[key], False, key)

    def test_approved_ui_unlocks_design_only_runtime_reader(self):
        out = reader.build_execution_terminal_certificate_runtime_reader_contract(
            terminal_certificate_read_model_ui_review=approved_ui_review(),
        )
        self.assertEqual(out["state"], reader.READY)
        self.assertTrue(out["execution_terminal_certificate_runtime_reader_design_only"])
        self.assertEqual(
            out["runtime_reader_mode"],
            "READ_ONLY_FAIL_CLOSED_TERMINAL_CERTIFICATE_RUNTIME_READER",
        )
        self.assertTrue(out["read_only"])
        self.assertTrue(out["observational_only"])
        self.assertTrue(out["read_model_is_only_logical_source"])
        self.assertTrue(out["persisted_certificate_required"])
        self.assertTrue(out["mutation_forbidden"])
        self.assertFalse(out["runtime_reader_creates_execution_authority"])
        self.assertFalse(out["runtime_reader_authorizes_retry"])
        self.assertFalse(out["runtime_reader_authorizes_reopen"])
        self.assertFalse(out["runtime_reader_authorizes_external_effect"])
        self.assertEqual(
            out["next_allowed_step"],
            "DESIGN_EXECUTION_TERMINAL_CERTIFICATE_RUNTIME_READER_STORE_ADAPTER_ONLY",
        )
        self.assert_no_authority(out)

    def test_upstream_must_be_exact_ready_state(self):
        row = approved_ui_review()
        row["state"] = "BLOCKED"
        out = reader.build_execution_terminal_certificate_runtime_reader_contract(
            terminal_certificate_read_model_ui_review=row,
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn(
            "TERMINAL_CERTIFICATE_READ_MODEL_UI_DESIGN_REVIEW_REQUIRED",
            out["blockers"],
        )
        self.assert_no_authority(out)

    def test_upstream_side_effect_flip_blocks(self):
        row = approved_ui_review()
        row["network_called"] = True
        out = reader.build_execution_terminal_certificate_runtime_reader_contract(
            terminal_certificate_read_model_ui_review=row,
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn(
            "TERMINAL_CERTIFICATE_UI_UNSAFE_FIELD:network_called",
            out["blockers"],
        )
        self.assert_no_authority(out)

    def test_ui_fail_closed_guards_cannot_be_relaxed(self):
        for field, blocker in (
            ("ui_consumes_read_model_only", "UI_MUST_CONSUME_READ_MODEL_ONLY"),
            ("tenant_scope_must_match", "TENANT_SCOPE_MATCH_REQUIRED"),
            ("workspace_scope_must_match", "WORKSPACE_SCOPE_MATCH_REQUIRED"),
            (
                "verified_badge_requires_verified_state",
                "VERIFIED_BADGE_MUST_REQUIRE_VERIFIED_STATE",
            ),
            ("mismatch_badge_fail_closed", "MISMATCH_BADGE_MUST_FAIL_CLOSED"),
            (
                "unavailable_badge_fail_closed",
                "UNAVAILABLE_BADGE_MUST_FAIL_CLOSED",
            ),
            ("stale_badge_fail_closed", "STALE_BADGE_MUST_FAIL_CLOSED"),
            ("action_controls_forbidden", "ACTION_CONTROLS_MUST_REMAIN_FORBIDDEN"),
        ):
            row = approved_ui_review()
            row[field] = False
            out = reader.build_execution_terminal_certificate_runtime_reader_contract(
                terminal_certificate_read_model_ui_review=row,
            )
            self.assertEqual(out["state"], "BLOCKED")
            self.assertIn(blocker, out["blockers"])
            self.assert_no_authority(out)

    def test_runtime_reader_states_match_fail_closed_projection(self):
        out = reader.build_execution_terminal_certificate_runtime_reader_contract(
            terminal_certificate_read_model_ui_review=approved_ui_review(),
        )
        self.assertEqual(
            tuple(out["runtime_reader_states"]),
            ("VERIFIED", "MISMATCH", "UNAVAILABLE", "STALE"),
        )
        self.assertTrue(out["verified_requires_bound_digest_match"])
        self.assertTrue(out["mismatch_returns_fail_closed"])
        self.assertTrue(out["unavailable_returns_fail_closed"])
        self.assertTrue(out["stale_returns_fail_closed"])
        self.assert_no_authority(out)

    def test_runtime_reader_rules_forbid_fallback_and_mutation(self):
        out = reader.build_execution_terminal_certificate_runtime_reader_contract(
            terminal_certificate_read_model_ui_review=approved_ui_review(),
        )
        rules = set(out["required_runtime_reader_rules"])
        self.assertTrue({
            "READ_MODEL_IS_ONLY_LOGICAL_SOURCE",
            "PERSISTED_CERTIFICATE_REQUIRED",
            "CANONICAL_EXECUTION_ID_REQUIRED",
            "TENANT_SCOPE_MUST_MATCH",
            "WORKSPACE_SCOPE_MUST_MATCH",
            "TERMINAL_REVISION_MUST_MATCH",
            "SNAPSHOT_CONSISTENCY_REQUIRED",
            "CERTIFICATE_DIGEST_MUST_MATCH_FOR_VERIFIED",
            "FINALIZATION_DIGEST_MUST_MATCH_FOR_VERIFIED",
            "AUDIT_SEAL_DIGEST_MUST_MATCH_FOR_VERIFIED",
            "ANY_MISMATCH_MUST_FAIL_CLOSED",
            "MISSING_EVIDENCE_MUST_RETURN_UNAVAILABLE",
            "STALE_EVIDENCE_MUST_RETURN_STALE",
            "UNKNOWN_STATE_MUST_FAIL_CLOSED",
            "NO_PROVIDER_FALLBACK",
            "NO_NETWORK_FALLBACK",
            "NO_RUNTIME_READER_MUTATION",
            "NO_READ_STATUS_GRANTS_EXECUTION_AUTHORITY",
            "NO_READ_STATUS_GRANTS_RETRY_AUTHORITY",
            "NO_READ_STATUS_GRANTS_REOPEN_AUTHORITY",
            "NO_READ_STATUS_GRANTS_EXTERNAL_EFFECT_AUTHORITY",
        }.issubset(rules))
        self.assertTrue(out["provider_fallback_forbidden"])
        self.assertTrue(out["network_fallback_forbidden"])
        self.assertTrue(out["mutation_forbidden"])
        self.assert_no_authority(out)

    def test_sensitive_material_is_never_readable(self):
        out = reader.build_execution_terminal_certificate_runtime_reader_contract(
            terminal_certificate_read_model_ui_review=approved_ui_review(),
        )
        forbidden = set(out["forbidden_runtime_reader_material"])
        self.assertTrue({
            "private_signing_key_value",
            "signing_key_value",
            "credential_value",
            "secret_value",
            "api_key_value",
            "access_token_value",
            "private_key_value",
            "authorization_header_value",
            "payload_body_value",
            "raw_provider_response_body",
            "raw_customer_message_body",
            "shell_command_value",
        }.issubset(forbidden))
        self.assert_no_authority(out)

    def test_design_layer_performs_no_live_read_or_effect(self):
        out = reader.build_execution_terminal_certificate_runtime_reader_contract(
            terminal_certificate_read_model_ui_review=approved_ui_review(),
        )
        self.assertFalse(out["runtime_read_performed"])
        self.assertFalse(out["runtime_reader_connected"])
        self.assertFalse(out["store_opened"])
        self.assertFalse(out["database_opened"])
        self.assertFalse(out["certificate_record_loaded"])
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
