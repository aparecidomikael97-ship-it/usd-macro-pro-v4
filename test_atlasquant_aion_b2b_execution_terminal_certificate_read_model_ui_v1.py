from __future__ import annotations

import unittest

import atlasquant_aion_b2b_execution_terminal_certificate_read_model_ui_v1 as ui
import atlasquant_aion_b2b_execution_terminal_certificate_read_model_v1 as read_model
from test_atlasquant_aion_b2b_execution_terminal_certificate_read_model_v1 import (
    approved_certificate_persistence_review,
)


def approved_read_model_review():
    return read_model.build_execution_terminal_certificate_read_model_contract(
        terminal_certificate_persistence_review=approved_certificate_persistence_review(),
    )


class ExecutionTerminalCertificateReadModelUiV1Tests(unittest.TestCase):
    def assert_no_authority(self, out):
        for key in ui.FALSE_FIELDS:
            self.assertIs(out[key], False, key)

    def test_approved_read_model_unlocks_design_only_ui(self):
        out = ui.build_execution_terminal_certificate_read_model_ui_contract(
            terminal_certificate_read_model_review=approved_read_model_review(),
        )
        self.assertEqual(out["state"], ui.READY)
        self.assertTrue(out["execution_terminal_certificate_read_model_ui_design_only"])
        self.assertEqual(
            out["ui_mode"],
            "READ_ONLY_FAIL_CLOSED_TERMINAL_CERTIFICATE_PANEL",
        )
        self.assertTrue(out["read_only"])
        self.assertTrue(out["observational_only"])
        self.assertTrue(out["ui_consumes_read_model_only"])
        self.assertTrue(out["action_controls_forbidden"])
        self.assertFalse(out["ui_creates_execution_authority"])
        self.assertFalse(out["ui_authorizes_retry"])
        self.assertFalse(out["ui_authorizes_reopen"])
        self.assertFalse(out["ui_authorizes_external_effect"])
        self.assertEqual(
            out["next_allowed_step"],
            "DESIGN_EXECUTION_TERMINAL_CERTIFICATE_RUNTIME_READER_ONLY",
        )
        self.assert_no_authority(out)

    def test_upstream_must_be_exact_ready_state(self):
        row = approved_read_model_review()
        row["state"] = "BLOCKED"
        out = ui.build_execution_terminal_certificate_read_model_ui_contract(
            terminal_certificate_read_model_review=row,
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn(
            "TERMINAL_CERTIFICATE_READ_MODEL_DESIGN_REVIEW_REQUIRED",
            out["blockers"],
        )
        self.assert_no_authority(out)

    def test_upstream_side_effect_flip_blocks(self):
        row = approved_read_model_review()
        row["network_called"] = True
        out = ui.build_execution_terminal_certificate_read_model_ui_contract(
            terminal_certificate_read_model_review=row,
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn(
            "TERMINAL_CERTIFICATE_READ_MODEL_UNSAFE_FIELD:network_called",
            out["blockers"],
        )
        self.assert_no_authority(out)

    def test_fail_closed_state_guards_cannot_be_relaxed(self):
        for field, blocker in (
            ("verification_status_fail_closed", "FAIL_CLOSED_VERIFICATION_STATUS_REQUIRED"),
            ("verified_requires_all_bound_digests_match", "ALL_BOUND_DIGESTS_MATCH_REQUIRED"),
            ("unavailable_never_implies_verified", "UNAVAILABLE_MUST_NOT_IMPLY_VERIFIED"),
            ("stale_never_implies_verified", "STALE_MUST_NOT_IMPLY_VERIFIED"),
            ("mismatch_never_implies_verified", "MISMATCH_MUST_NOT_IMPLY_VERIFIED"),
        ):
            row = approved_read_model_review()
            row[field] = False
            out = ui.build_execution_terminal_certificate_read_model_ui_contract(
                terminal_certificate_read_model_review=row,
            )
            self.assertEqual(out["state"], "BLOCKED")
            self.assertIn(blocker, out["blockers"])
            self.assert_no_authority(out)

    def test_ui_states_match_read_model_states_exactly(self):
        out = ui.build_execution_terminal_certificate_read_model_ui_contract(
            terminal_certificate_read_model_review=approved_read_model_review(),
        )
        self.assertEqual(
            tuple(out["display_states"]),
            ("VERIFIED", "MISMATCH", "UNAVAILABLE", "STALE"),
        )
        self.assertTrue(out["verified_badge_requires_verified_state"])
        self.assertTrue(out["mismatch_badge_fail_closed"])
        self.assertTrue(out["unavailable_badge_fail_closed"])
        self.assertTrue(out["stale_badge_fail_closed"])
        self.assert_no_authority(out)

    def test_ui_sections_expose_evidence_not_actions(self):
        out = ui.build_execution_terminal_certificate_read_model_ui_contract(
            terminal_certificate_read_model_review=approved_read_model_review(),
        )
        sections = set(out["required_ui_sections"])
        self.assertTrue({
            "certificate_status",
            "execution_identity",
            "terminal_state",
            "terminal_revision",
            "certificate_digest",
            "finalization_evidence",
            "audit_seal_evidence",
            "finops_evidence",
            "observability_trace",
            "scope_boundary",
        }.issubset(sections))
        controls = set(out["forbidden_ui_controls"])
        self.assertTrue({
            "execute_action_button",
            "retry_button",
            "reopen_execution_button",
            "issue_certificate_button",
            "sign_certificate_button",
            "billing_button",
            "crm_write_button",
            "deploy_button",
            "production_mutation_button",
        }.issubset(controls))
        self.assert_no_authority(out)

    def test_ui_rules_separate_status_from_authority(self):
        out = ui.build_execution_terminal_certificate_read_model_ui_contract(
            terminal_certificate_read_model_review=approved_read_model_review(),
        )
        rules = set(out["required_ui_rules"])
        self.assertTrue({
            "UI_CONSUMES_READ_MODEL_ONLY",
            "TENANT_SCOPE_MUST_MATCH",
            "WORKSPACE_SCOPE_MUST_MATCH",
            "VERIFIED_REQUIRES_VERIFIED_READ_MODEL_STATE",
            "MISMATCH_MUST_RENDER_FAIL_CLOSED",
            "UNAVAILABLE_MUST_RENDER_EVIDENCE_MISSING",
            "STALE_MUST_RENDER_REFRESH_REQUIRED",
            "NO_UNKNOWN_STATE_MAY_RENDER_VERIFIED",
            "NO_STATUS_GRANTS_EXECUTION_AUTHORITY",
            "NO_STATUS_GRANTS_RETRY_AUTHORITY",
            "NO_STATUS_GRANTS_REOPEN_AUTHORITY",
            "NO_STATUS_GRANTS_EXTERNAL_EFFECT_AUTHORITY",
            "NO_UI_CONTROL_MAY_TRIGGER_PROVIDER",
            "NO_UI_CONTROL_MAY_TRIGGER_BILLING",
            "NO_UI_CONTROL_MAY_WRITE_CRM",
            "NO_UI_CONTROL_MAY_DEPLOY",
        }.issubset(rules))
        self.assert_no_authority(out)

    def test_sensitive_material_is_never_renderable(self):
        out = ui.build_execution_terminal_certificate_read_model_ui_contract(
            terminal_certificate_read_model_review=approved_read_model_review(),
        )
        forbidden = set(out["forbidden_ui_material"])
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
        self.assertTrue(out["raw_secret_render_forbidden"])
        self.assertTrue(out["raw_provider_payload_render_forbidden"])
        self.assertTrue(out["raw_customer_message_render_forbidden"])
        self.assert_no_authority(out)

    def test_design_layer_renders_nothing_and_executes_nothing(self):
        out = ui.build_execution_terminal_certificate_read_model_ui_contract(
            terminal_certificate_read_model_review=approved_read_model_review(),
        )
        self.assertFalse(out["ui_rendered"])
        self.assertFalse(out["live_read_performed"])
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
