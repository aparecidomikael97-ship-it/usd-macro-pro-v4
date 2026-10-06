from __future__ import annotations

import unittest

import atlasquant_aion_b2b_execution_envelope_contract_v1 as envelope
import atlasquant_aion_b2b_provider_capability_binding_contract_v1 as binding
from test_atlasquant_aion_b2b_provider_capability_binding_contract_v1 import (
    approved_adapter_review,
)


def approved_binding_review():
    return binding.build_provider_capability_binding_contract(
        provider_adapter_attestation_review=approved_adapter_review(),
    )


class ExecutionEnvelopeContractV1Tests(unittest.TestCase):
    def assert_no_authority(self, out):
        for key in envelope.FALSE_FIELDS:
            self.assertIs(out[key], False, key)

    def test_approved_binding_unlocks_design_only(self):
        out = envelope.build_execution_envelope_contract(
            provider_capability_binding_review=approved_binding_review(),
        )
        self.assertEqual(out["state"], envelope.READY)
        self.assertTrue(out["execution_envelope_design_only"])
        self.assertEqual(out["envelope_mode"], "SEALED_DIGEST_REFERENCES_ONLY")
        self.assertTrue(out["digest_references_only"])
        self.assertTrue(out["immutable_after_seal_required"])
        self.assertEqual(out["max_envelope_window_seconds"], 120)
        self.assertEqual(out["finops_cap_cents"], 20000)
        self.assertEqual(out["next_allowed_step"], envelope.NEXT_ALLOWED_STEP)
        self.assert_no_authority(out)

    def test_capability_binding_must_be_exact_ready_state(self):
        row = approved_binding_review()
        row["state"] = "BLOCKED"
        out = envelope.build_execution_envelope_contract(
            provider_capability_binding_review=row,
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn(
            "PROVIDER_CAPABILITY_BINDING_DESIGN_REVIEW_REQUIRED",
            out["blockers"],
        )
        self.assert_no_authority(out)

    def test_permission_expansion_boundary_cannot_be_removed(self):
        row = approved_binding_review()
        row["permission_expansion_forbidden"] = False
        out = envelope.build_execution_envelope_contract(
            provider_capability_binding_review=row,
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("PERMISSION_EXPANSION_MUST_BE_FORBIDDEN", out["blockers"])
        self.assert_no_authority(out)

    def test_upstream_provider_selection_flip_blocks(self):
        row = approved_binding_review()
        row["provider_selected"] = True
        out = envelope.build_execution_envelope_contract(
            provider_capability_binding_review=row,
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn(
            "PROVIDER_CAPABILITY_BINDING_UNSAFE_FIELD:provider_selected",
            out["blockers"],
        )
        self.assert_no_authority(out)

    def test_envelope_bindings_cover_full_execution_evidence_chain(self):
        out = envelope.build_execution_envelope_contract(
            provider_capability_binding_review=approved_binding_review(),
        )
        fields = set(out["required_envelope_bindings"])
        self.assertTrue({
            "owner_id",
            "tenant_id",
            "workspace_id",
            "domain",
            "customer_id",
            "pilot_id",
            "package",
            "action_family",
            "operation_kind",
            "execution_request_digest",
            "fresh_owner_authorization_digest",
            "authenticated_receipt_digest",
            "command_plan_digest",
            "adapter_plan_digest",
            "dry_run_digest",
            "rollback_plan_digest",
            "idempotency_key_digest",
            "effect_key_digest",
            "rollback_compensation_contract_digest",
            "runtime_execution_guards_digest",
            "provider_adapter_attestation_digest",
            "provider_capability_binding_digest",
            "effective_capabilities_digest",
            "provider_identity_ref",
            "finops_ceiling_digest",
            "before_state_digest",
            "expected_postcondition_digest",
            "issued_at",
            "expires_at",
            "envelope_nonce_digest",
        }.issubset(fields))
        self.assert_no_authority(out)

    def test_rules_preserve_auth_idempotency_capability_and_finops(self):
        out = envelope.build_execution_envelope_contract(
            provider_capability_binding_review=approved_binding_review(),
        )
        rules = set(out["required_envelope_rules"])
        self.assertTrue({
            "ALL_UPSTREAM_DIGESTS_REQUIRED",
            "FRESH_OWNER_AUTHORIZATION_MUST_STILL_BE_VALID",
            "MAX_ENVELOPE_WINDOW_120_SECONDS",
            "AUTHORIZATION_SINGLE_USE_PRESERVED",
            "IDEMPOTENCY_BINDING_PRESERVED",
            "EFFECT_KEY_BINDING_PRESERVED",
            "CAPABILITY_BINDING_PRESERVED",
            "ROLLBACK_COMPENSATION_BINDING_PRESERVED",
            "FINOPS_CEILING_PRESERVED",
            "NO_IMPLICIT_EXECUTION_AUTHORITY",
            "ENVELOPE_SINGLE_USE_REQUIRED",
            "TAMPER_REBUILD_MISMATCH_BLOCKS",
        }.issubset(rules))
        self.assert_no_authority(out)

    def test_live_execution_material_is_explicitly_forbidden(self):
        out = envelope.build_execution_envelope_contract(
            provider_capability_binding_review=approved_binding_review(),
        )
        forbidden = set(out["forbidden_envelope_material"])
        self.assertTrue({
            "credential",
            "secret",
            "password",
            "api_key",
            "access_token",
            "refresh_token",
            "private_key",
            "authorization_header",
            "cookie",
            "endpoint",
            "url",
            "webhook",
            "callback",
            "http_method",
            "headers",
            "payload",
            "body",
            "command",
            "shell",
            "subprocess",
            "powershell",
            "curl",
            "script",
        }.issubset(forbidden))
        self.assert_no_authority(out)

    def test_contract_builds_no_real_envelope_or_dispatch_material(self):
        out = envelope.build_execution_envelope_contract(
            provider_capability_binding_review=approved_binding_review(),
        )
        for key in (
            "execution_envelope_built",
            "execution_envelope_signed",
            "execution_envelope_persisted",
            "envelope_nonce_claimed",
            "envelope_consumed",
            "pre_dispatch_attested",
            "credentials_loaded",
            "endpoint_resolved",
            "payload_constructed",
            "idempotency_reserved",
            "effect_key_reserved",
            "lease_acquired",
            "dispatch_recorded",
            "network_called",
            "provider_called",
        ):
            self.assertFalse(out[key], key)
        self.assert_no_authority(out)

    def test_next_step_is_pre_dispatch_attestation_design_only(self):
        out = envelope.build_execution_envelope_contract(
            provider_capability_binding_review=approved_binding_review(),
        )
        self.assertEqual(
            out["next_allowed_step"],
            "DESIGN_PRE_DISPATCH_ATTESTATION_CONTRACT_ONLY",
        )
        self.assertFalse(out["execution_allowed"])
        self.assertFalse(out["execution_command_generated"])
        self.assert_no_authority(out)


if __name__ == "__main__":
    unittest.main()
