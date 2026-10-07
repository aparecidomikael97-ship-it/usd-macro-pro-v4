from __future__ import annotations

import unittest

import atlasquant_aion_b2b_durable_dispatch_record_contract_v1 as dispatch
import atlasquant_aion_b2b_external_effect_call_boundary_contract_v1 as boundary
from test_atlasquant_aion_b2b_durable_dispatch_record_contract_v1 import (
    approved_pre_dispatch_review,
)


def approved_dispatch_review():
    return dispatch.build_durable_dispatch_record_contract(
        pre_dispatch_attestation_review=approved_pre_dispatch_review(),
    )


class ExternalEffectCallBoundaryContractV1Tests(unittest.TestCase):
    def assert_no_authority(self, out):
        for key in boundary.FALSE_FIELDS:
            self.assertIs(out[key], False, key)

    def test_approved_dispatch_review_unlocks_design_only(self):
        out = boundary.build_external_effect_call_boundary_contract(
            durable_dispatch_record_review=approved_dispatch_review(),
        )
        self.assertEqual(out["state"], boundary.READY)
        self.assertTrue(out["external_effect_call_boundary_design_only"])
        self.assertEqual(
            out["boundary_mode"],
            "SEALED_SINGLE_CALL_AFTER_DURABLE_DISPATCH",
        )
        self.assertTrue(out["single_sealed_call_required"])
        self.assertTrue(out["no_material_mutation_after_dispatch_record"])
        self.assertEqual(out["finops_cap_cents"], 20000)
        self.assertEqual(out["next_allowed_step"], boundary.NEXT_ALLOWED_STEP)
        self.assert_no_authority(out)

    def test_dispatch_review_must_be_exact_ready_state(self):
        row = approved_dispatch_review()
        row["state"] = "BLOCKED"
        out = boundary.build_external_effect_call_boundary_contract(
            durable_dispatch_record_review=row,
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn(
            "DURABLE_DISPATCH_RECORD_DESIGN_REVIEW_REQUIRED",
            out["blockers"],
        )
        self.assert_no_authority(out)

    def test_missing_unknown_fail_closed_semantics_blocks(self):
        row = approved_dispatch_review()
        row["automatic_retry_after_dispatch_forbidden"] = False
        out = boundary.build_external_effect_call_boundary_contract(
            durable_dispatch_record_review=row,
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn(
            "POST_DISPATCH_AUTOMATIC_RETRY_MUST_BE_FORBIDDEN",
            out["blockers"],
        )
        self.assert_no_authority(out)

    def test_upstream_provider_call_flip_blocks(self):
        row = approved_dispatch_review()
        row["provider_called"] = True
        out = boundary.build_external_effect_call_boundary_contract(
            durable_dispatch_record_review=row,
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn(
            "DURABLE_DISPATCH_RECORD_UNSAFE_FIELD:provider_called",
            out["blockers"],
        )
        self.assert_no_authority(out)

    def test_pre_record_preparation_freezes_all_mutable_material(self):
        out = boundary.build_external_effect_call_boundary_contract(
            durable_dispatch_record_review=approved_dispatch_review(),
        )
        required = set(out["required_pre_record_preparation"])
        self.assertTrue({
            "PROVIDER_IDENTITY_RESOLVED_FROM_ATTESTED_REFERENCE",
            "PROVIDER_ADAPTER_VERSION_PINNED",
            "PROVIDER_ADAPTER_DIGEST_MATCH",
            "CAPABILITY_BINDING_MATCH",
            "ENDPOINT_RESOLVED_FROM_TRUSTED_PROVIDER_CONFIGURATION",
            "ENDPOINT_ALLOWLIST_MATCH",
            "CREDENTIAL_REFERENCE_RESOLVED_FROM_APPROVED_SECRET_SOURCE",
            "CREDENTIAL_SCOPE_MINIMUM_REQUIRED",
            "CREDENTIAL_NOT_EXPIRED",
            "PAYLOAD_SCHEMA_VALIDATED",
            "PAYLOAD_DIGEST_MATCH",
            "REQUEST_HEADERS_POLICY_VALIDATED",
            "TRANSPORT_POLICY_VALIDATED",
            "TIMEOUT_POLICY_VALIDATED",
            "FINOPS_ESTIMATE_WITHIN_20000_CENTS",
            "OBSERVABILITY_CORRELATION_READY",
            "ALL_MATERIAL_IMMUTABLE_AFTER_DISPATCH_RECORD",
        }.issubset(required))
        self.assert_no_authority(out)

    def test_post_record_rules_are_single_call_and_unknown_fail_closed(self):
        out = boundary.build_external_effect_call_boundary_contract(
            durable_dispatch_record_review=approved_dispatch_review(),
        )
        rules = set(out["required_post_record_rules"])
        self.assertTrue({
            "EXACTLY_ONE_SEALED_CALL_ATTEMPT",
            "NO_PROVIDER_OR_ENDPOINT_SWITCH_AFTER_RECORD",
            "NO_CREDENTIAL_SWITCH_AFTER_RECORD",
            "NO_PAYLOAD_MUTATION_AFTER_RECORD",
            "NO_CAPABILITY_EXPANSION_AFTER_RECORD",
            "NO_SCOPE_EXPANSION_AFTER_RECORD",
            "NO_FINOPS_CEILING_EXPANSION_AFTER_RECORD",
            "PROVIDER_REQUEST_CORRELATION_REQUIRED",
            "RESPONSE_OR_AMBIGUITY_RECEIPT_REQUIRED",
            "TIMEOUT_AFTER_RECORD_BECOMES_OUTCOME_UNKNOWN",
            "CONNECTION_RESET_AFTER_RECORD_BECOMES_OUTCOME_UNKNOWN",
            "PROCESS_CRASH_AFTER_RECORD_BECOMES_OUTCOME_UNKNOWN",
            "AMBIGUOUS_PROVIDER_ACK_BECOMES_OUTCOME_UNKNOWN",
            "OUTCOME_UNKNOWN_AUTOMATIC_RETRY_FORBIDDEN",
            "OUTCOME_UNKNOWN_REQUIRES_EXPLICIT_RECONCILIATION",
            "RECONCILIATION_REQUIRES_EVIDENCE",
            "RECONCILIATION_REQUIRES_SEPARATE_AUTHORIZATION",
        }.issubset(rules))
        self.assert_no_authority(out)

    def test_call_bindings_cover_exact_sealed_effect_context(self):
        out = boundary.build_external_effect_call_boundary_contract(
            durable_dispatch_record_review=approved_dispatch_review(),
        )
        fields = set(out["required_call_bindings"])
        self.assertTrue({
            "execution_id",
            "durable_dispatch_record_digest",
            "execution_envelope_digest",
            "pre_dispatch_attestation_digest",
            "fresh_owner_authorization_digest",
            "provider_adapter_attestation_digest",
            "provider_capability_binding_digest",
            "effective_capabilities_digest",
            "provider_identity_ref",
            "provider_adapter_digest",
            "endpoint_reference_digest",
            "credential_reference_digest",
            "payload_digest",
            "request_headers_policy_digest",
            "transport_policy_digest",
            "timeout_policy_digest",
            "idempotency_key_digest",
            "effect_key_digest",
            "before_state_digest",
            "expected_postcondition_digest",
            "rollback_plan_digest",
            "finops_estimate_digest",
            "observability_trace_id",
        }.issubset(fields))
        self.assert_no_authority(out)

    def test_design_contains_references_not_live_values(self):
        out = boundary.build_external_effect_call_boundary_contract(
            durable_dispatch_record_review=approved_dispatch_review(),
        )
        forbidden = set(out["forbidden_design_material"])
        self.assertTrue({
            "credential_value",
            "secret_value",
            "password_value",
            "api_key_value",
            "access_token_value",
            "refresh_token_value",
            "private_key_value",
            "authorization_header_value",
            "cookie_value",
            "endpoint_value",
            "url_value",
            "webhook_value",
            "callback_value",
            "request_headers_value",
            "payload_body_value",
            "shell_command_value",
        }.issubset(forbidden))
        self.assert_no_authority(out)

    def test_contract_does_not_cross_network_boundary(self):
        out = boundary.build_external_effect_call_boundary_contract(
            durable_dispatch_record_review=approved_dispatch_review(),
        )
        for key in (
            "provider_selected",
            "provider_bound",
            "provider_identity_verified",
            "adapter_loaded",
            "adapter_instantiated",
            "endpoint_resolved",
            "credential_reference_resolved",
            "credentials_loaded",
            "payload_constructed",
            "headers_constructed",
            "transport_opened",
            "socket_opened",
            "network_called",
            "provider_called",
            "provider_request_sent",
            "provider_response_received",
            "external_effect_attempted",
        ):
            self.assertFalse(out[key], key)
        self.assert_no_authority(out)

    def test_next_step_is_outcome_receipt_design_only(self):
        out = boundary.build_external_effect_call_boundary_contract(
            durable_dispatch_record_review=approved_dispatch_review(),
        )
        self.assertEqual(
            out["next_allowed_step"],
            "DESIGN_EXTERNAL_EFFECT_OUTCOME_RECEIPT_CONTRACT_ONLY",
        )
        self.assertFalse(out["execution_allowed"])
        self.assertFalse(out["external_action_executed"])
        self.assert_no_authority(out)


if __name__ == "__main__":
    unittest.main()
