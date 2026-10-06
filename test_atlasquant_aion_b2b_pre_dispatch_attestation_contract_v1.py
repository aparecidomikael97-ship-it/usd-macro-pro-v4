from __future__ import annotations

import unittest

import atlasquant_aion_b2b_execution_envelope_contract_v1 as envelope
import atlasquant_aion_b2b_pre_dispatch_attestation_contract_v1 as predispatch
from test_atlasquant_aion_b2b_execution_envelope_contract_v1 import (
    approved_binding_review,
)


def approved_envelope_review():
    return envelope.build_execution_envelope_contract(
        provider_capability_binding_review=approved_binding_review(),
    )


class PreDispatchAttestationContractV1Tests(unittest.TestCase):
    def assert_no_authority(self, out):
        for key in predispatch.FALSE_FIELDS:
            self.assertIs(out[key], False, key)

    def test_approved_envelope_unlocks_design_only(self):
        out = predispatch.build_pre_dispatch_attestation_contract(
            execution_envelope_review=approved_envelope_review(),
        )
        self.assertEqual(out["state"], predispatch.READY)
        self.assertTrue(out["pre_dispatch_attestation_design_only"])
        self.assertEqual(
            out["attestation_mode"],
            "IMMEDIATE_PRE_EFFECT_REVALIDATION",
        )
        self.assertTrue(out["fail_closed"])
        self.assertEqual(out["max_attestation_age_seconds"], 30)
        self.assertEqual(out["finops_cap_cents"], 20000)
        self.assertEqual(out["next_allowed_step"], predispatch.NEXT_ALLOWED_STEP)
        self.assert_no_authority(out)

    def test_envelope_must_be_exact_ready_state(self):
        row = approved_envelope_review()
        row["state"] = "BLOCKED"
        out = predispatch.build_pre_dispatch_attestation_contract(
            execution_envelope_review=row,
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn(
            "EXECUTION_ENVELOPE_DESIGN_REVIEW_REQUIRED",
            out["blockers"],
        )
        self.assert_no_authority(out)

    def test_upstream_dispatch_flip_blocks(self):
        row = approved_envelope_review()
        row["dispatch_recorded"] = True
        out = predispatch.build_pre_dispatch_attestation_contract(
            execution_envelope_review=row,
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn(
            "EXECUTION_ENVELOPE_UNSAFE_FIELD:dispatch_recorded",
            out["blockers"],
        )
        self.assert_no_authority(out)

    def test_revalidations_cover_immediate_pre_effect_safety(self):
        out = predispatch.build_pre_dispatch_attestation_contract(
            execution_envelope_review=approved_envelope_review(),
        )
        required = set(out["required_revalidations"])
        self.assertTrue({
            "EXECUTION_ENVELOPE_DIGEST_REBUILD_MATCH",
            "FRESH_OWNER_AUTHORIZATION_STILL_VALID",
            "FRESH_OWNER_AUTHORIZATION_NOT_CONSUMED",
            "AUTHORIZATION_SINGLE_USE_PRESERVED",
            "BEFORE_STATE_DIGEST_STILL_MATCHES",
            "IDEMPOTENCY_KEY_RESERVATION_REQUIRED_BEFORE_DISPATCH",
            "EFFECT_KEY_RESERVATION_REQUIRED_BEFORE_DISPATCH",
            "LEASE_OWNERSHIP_REQUIRED_BEFORE_DISPATCH",
            "PROVIDER_ADAPTER_ATTESTATION_STILL_VALID",
            "PROVIDER_CAPABILITY_BINDING_STILL_VALID",
            "PROVIDER_HEALTH_EVIDENCE_FRESH",
            "FINOPS_ESTIMATE_WITHIN_20000_CENTS",
            "CAPACITY_RESERVATION_REQUIRED",
            "QUOTA_AVAILABLE",
            "SECURITY_INCIDENT_CLEAR",
            "PRIVACY_INCIDENT_CLEAR",
            "CIRCUIT_BREAKER_CLOSED",
            "KILL_SWITCH_AVAILABLE",
            "ROLLBACK_COMPENSATION_CLASS_STILL_VALID",
            "DISPATCH_RECORD_REQUIRED_BEFORE_EXTERNAL_EFFECT",
        }.issubset(required))
        self.assert_no_authority(out)

    def test_bindings_cover_envelope_effect_provider_state_and_guardrails(self):
        out = predispatch.build_pre_dispatch_attestation_contract(
            execution_envelope_review=approved_envelope_review(),
        )
        fields = set(out["required_attestation_bindings"])
        self.assertTrue({
            "execution_envelope_digest",
            "fresh_owner_authorization_digest",
            "authenticated_receipt_digest",
            "provider_adapter_attestation_digest",
            "provider_capability_binding_digest",
            "effective_capabilities_digest",
            "idempotency_key_digest",
            "effect_key_digest",
            "lease_identity_digest",
            "provider_identity_ref",
            "before_state_digest",
            "expected_postcondition_digest",
            "rollback_plan_digest",
            "rollback_compensation_contract_digest",
            "runtime_execution_guards_digest",
            "finops_estimate_digest",
            "capacity_reservation_digest",
            "quota_snapshot_digest",
            "provider_health_digest",
            "security_state_digest",
            "observability_trace_id",
            "checked_at",
        }.issubset(fields))
        self.assert_no_authority(out)

    def test_live_material_is_forbidden(self):
        out = predispatch.build_pre_dispatch_attestation_contract(
            execution_envelope_review=approved_envelope_review(),
        )
        forbidden = set(out["forbidden_pre_dispatch_material"])
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

    def test_attestation_contract_performs_no_runtime_preconditions(self):
        out = predispatch.build_pre_dispatch_attestation_contract(
            execution_envelope_review=approved_envelope_review(),
        )
        for key in (
            "pre_dispatch_attestation_performed",
            "pre_dispatch_attested",
            "execution_envelope_rebuilt",
            "execution_envelope_consumed",
            "fresh_authorization_revalidated",
            "fresh_authorization_consumed",
            "envelope_nonce_claimed",
            "idempotency_reserved",
            "effect_key_reserved",
            "lease_acquired",
            "capacity_reserved",
            "quota_consumed",
            "provider_adapter_revalidated",
            "provider_capability_revalidated",
            "provider_health_checked",
            "dispatch_record_created",
            "dispatch_record_persisted",
        ):
            self.assertFalse(out[key], key)
        self.assert_no_authority(out)

    def test_provider_stays_unselected_and_no_dispatch_is_recorded(self):
        out = predispatch.build_pre_dispatch_attestation_contract(
            execution_envelope_review=approved_envelope_review(),
        )
        self.assertTrue(out["provider_identity_reference_only"])
        self.assertFalse(out["provider_selected"])
        self.assertFalse(out["provider_bound"])
        self.assertFalse(out["endpoint_resolved"])
        self.assertFalse(out["payload_constructed"])
        self.assertFalse(out["dispatch_recorded"])
        self.assertFalse(out["provider_called"])
        self.assert_no_authority(out)

    def test_next_step_is_durable_dispatch_record_design_only(self):
        out = predispatch.build_pre_dispatch_attestation_contract(
            execution_envelope_review=approved_envelope_review(),
        )
        self.assertEqual(
            out["next_allowed_step"],
            "DESIGN_DURABLE_DISPATCH_RECORD_CONTRACT_ONLY",
        )
        self.assertFalse(out["execution_allowed"])
        self.assertFalse(out["external_action_executed"])
        self.assert_no_authority(out)


if __name__ == "__main__":
    unittest.main()
