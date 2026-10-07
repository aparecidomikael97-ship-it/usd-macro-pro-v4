from __future__ import annotations

import unittest

import atlasquant_aion_b2b_durable_dispatch_record_contract_v1 as dispatch
import atlasquant_aion_b2b_pre_dispatch_attestation_contract_v1 as predispatch
from test_atlasquant_aion_b2b_pre_dispatch_attestation_contract_v1 import (
    approved_envelope_review,
)


def approved_pre_dispatch_review():
    return predispatch.build_pre_dispatch_attestation_contract(
        execution_envelope_review=approved_envelope_review(),
    )


class DurableDispatchRecordContractV1Tests(unittest.TestCase):
    def assert_no_authority(self, out):
        for key in dispatch.FALSE_FIELDS:
            self.assertIs(out[key], False, key)

    def test_approved_pre_dispatch_unlocks_design_only(self):
        out = dispatch.build_durable_dispatch_record_contract(
            pre_dispatch_attestation_review=approved_pre_dispatch_review(),
        )
        self.assertEqual(out["state"], dispatch.READY)
        self.assertTrue(out["durable_dispatch_record_design_only"])
        self.assertTrue(out["reuses_core_durable_execution_kernel"])
        self.assertTrue(out["no_provider_call_before_record"])
        self.assertTrue(out["write_ahead_record_required"])
        self.assertEqual(out["required_core_mode"], "EXTERNAL_EFFECT")
        self.assertEqual(out["required_dispatch_state"], "DISPATCH_RECORDED")
        self.assertEqual(out["post_dispatch_unknown_state"], "OUTCOME_UNKNOWN")
        self.assertEqual(out["next_allowed_step"], dispatch.NEXT_ALLOWED_STEP)
        self.assert_no_authority(out)

    def test_pre_dispatch_must_be_exact_ready_state(self):
        row = approved_pre_dispatch_review()
        row["state"] = "BLOCKED"
        out = dispatch.build_durable_dispatch_record_contract(
            pre_dispatch_attestation_review=row,
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn(
            "PRE_DISPATCH_ATTESTATION_DESIGN_REVIEW_REQUIRED",
            out["blockers"],
        )
        self.assert_no_authority(out)

    def test_upstream_dispatch_flip_blocks(self):
        row = approved_pre_dispatch_review()
        row["dispatch_recorded"] = True
        out = dispatch.build_durable_dispatch_record_contract(
            pre_dispatch_attestation_review=row,
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn(
            "PRE_DISPATCH_UNSAFE_FIELD:dispatch_recorded",
            out["blockers"],
        )
        self.assert_no_authority(out)

    def test_core_state_transition_matches_durable_kernel(self):
        out = dispatch.build_durable_dispatch_record_contract(
            pre_dispatch_attestation_review=approved_pre_dispatch_review(),
        )
        self.assertEqual(
            out["required_state_transition"],
            ("PREPARED", "LEASED", "DISPATCH_RECORDED"),
        )
        self.assertEqual(
            out["core_execution_store"],
            "atlasquant_aion_durable_execution_kernel.DurableExecutionStore",
        )
        self.assertEqual(
            out["core_dispatch_method"],
            "DurableExecutionStore.record_dispatch_started",
        )
        self.assert_no_authority(out)

    def test_record_bindings_cover_exact_effect_context(self):
        out = dispatch.build_durable_dispatch_record_contract(
            pre_dispatch_attestation_review=approved_pre_dispatch_review(),
        )
        fields = set(out["required_record_bindings"])
        self.assertTrue({
            "execution_id",
            "task_id",
            "step_id",
            "owner_id",
            "tenant_id",
            "workspace_id",
            "customer_id",
            "pilot_id",
            "action_family",
            "operation_kind",
            "execution_envelope_digest",
            "pre_dispatch_attestation_digest",
            "fresh_owner_authorization_digest",
            "authenticated_receipt_digest",
            "provider_adapter_attestation_digest",
            "provider_capability_binding_digest",
            "effective_capabilities_digest",
            "provider_identity_ref",
            "idempotency_key_digest",
            "effect_key_digest",
            "payload_digest",
            "lease_identity_digest",
            "before_state_digest",
            "expected_postcondition_digest",
            "rollback_plan_digest",
            "rollback_compensation_contract_digest",
            "finops_estimate_digest",
            "capacity_reservation_digest",
            "quota_snapshot_digest",
            "observability_trace_id",
            "dispatch_recorded_at",
        }.issubset(fields))
        self.assert_no_authority(out)

    def test_invariants_make_dispatch_write_ahead_and_unknown_fail_closed(self):
        out = dispatch.build_durable_dispatch_record_contract(
            pre_dispatch_attestation_review=approved_pre_dispatch_review(),
        )
        required = set(out["required_dispatch_invariants"])
        self.assertTrue({
            "STATE_MUST_BE_LEASED_BEFORE_RECORD",
            "LEASE_TOKEN_MATCH_REQUIRED",
            "LEASE_NOT_EXPIRED",
            "PRE_DISPATCH_ATTESTATION_FRESH",
            "IDEMPOTENCY_KEY_ALREADY_RESERVED",
            "EFFECT_KEY_ALREADY_RESERVED",
            "EFFECT_KEY_UNIQUE",
            "DISPATCH_RECORD_DURABLE_BEFORE_EXTERNAL_EFFECT",
            "DISPATCH_RECORD_ATOMIC",
            "NO_PROVIDER_CALL_BEFORE_DURABLE_RECORD",
            "POST_RECORD_CRASH_BECOMES_OUTCOME_UNKNOWN",
            "POST_RECORD_AMBIGUITY_BECOMES_OUTCOME_UNKNOWN",
            "OUTCOME_UNKNOWN_AUTOMATIC_RETRY_FORBIDDEN",
            "OUTCOME_UNKNOWN_REQUIRES_EXPLICIT_RECONCILIATION",
            "RECONCILIATION_REQUIRES_EVIDENCE",
            "RECONCILIATION_REQUIRES_SEPARATE_AUTHORIZATION",
        }.issubset(required))
        self.assert_no_authority(out)

    def test_live_dispatch_material_is_forbidden(self):
        out = dispatch.build_durable_dispatch_record_contract(
            pre_dispatch_attestation_review=approved_pre_dispatch_review(),
        )
        forbidden = set(out["forbidden_record_material"])
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
            "payload_body",
            "command",
            "shell",
            "subprocess",
            "powershell",
            "curl",
            "script",
        }.issubset(forbidden))
        self.assert_no_authority(out)

    def test_contract_writes_no_store_or_dispatch_record(self):
        out = dispatch.build_durable_dispatch_record_contract(
            pre_dispatch_attestation_review=approved_pre_dispatch_review(),
        )
        for key in (
            "execution_store_opened",
            "execution_record_created",
            "execution_record_loaded",
            "idempotency_reserved",
            "effect_key_reserved",
            "lease_acquired",
            "lease_token_verified",
            "dispatch_record_created",
            "dispatch_record_persisted",
            "dispatch_recorded",
            "outcome_unknown_marked",
            "reconciliation_performed",
        ):
            self.assertFalse(out[key], key)
        self.assert_no_authority(out)

    def test_next_step_is_external_effect_call_boundary_design_only(self):
        out = dispatch.build_durable_dispatch_record_contract(
            pre_dispatch_attestation_review=approved_pre_dispatch_review(),
        )
        self.assertEqual(
            out["next_allowed_step"],
            "DESIGN_EXTERNAL_EFFECT_CALL_BOUNDARY_CONTRACT_ONLY",
        )
        self.assertFalse(out["provider_called"])
        self.assertFalse(out["external_action_executed"])
        self.assertFalse(out["execution_allowed"])
        self.assert_no_authority(out)


if __name__ == "__main__":
    unittest.main()
