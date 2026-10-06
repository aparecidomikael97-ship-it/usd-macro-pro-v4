from __future__ import annotations

import unittest

import atlasquant_aion_b2b_fresh_owner_execution_authorization_contract_v1 as fresh
import atlasquant_aion_b2b_future_executor_boundary_v2 as boundary
import atlasquant_aion_b2b_future_executor_capability_contract_v1 as capability
import atlasquant_aion_b2b_idempotency_replay_contract_v1 as replay
import atlasquant_aion_b2b_owner_renewal_action_adapter_plan_v2 as adapter
import atlasquant_aion_b2b_owner_renewal_action_adapter_receipt_v2 as receipts
import atlasquant_aion_b2b_real_receipt_authenticator_contract_v1 as auth
import atlasquant_aion_b2b_rollback_compensation_contract_v1 as rollback
import atlasquant_aion_b2b_runtime_execution_guards_contract_v1 as guards
from test_atlasquant_aion_b2b_owner_renewal_action_adapter_v2 import (
    args_v2,
    receipt_args_v2,
)


def approved_fresh_review():
    plan = adapter.build_owner_renewal_action_adapter_plan_v2(**args_v2())
    receipt = receipts.validate_synthetic_owner_renewal_action_receipt_v2(
        **receipt_args_v2()
    )
    boundary_review = boundary.evaluate_future_executor_boundary(
        adapter_plan_v2=plan,
        synthetic_receipt_validation=receipt,
    )
    capability_review = capability.build_future_executor_capability_contract(
        boundary_review=boundary_review,
    )
    auth_review = auth.build_real_receipt_authenticator_contract(
        capability_review=capability_review,
    )
    replay_review = replay.build_idempotency_replay_contract(
        authenticator_review=auth_review,
    )
    rollback_review = rollback.build_rollback_compensation_contract(
        idempotency_replay_review=replay_review,
    )
    return fresh.build_fresh_owner_execution_authorization_contract(
        rollback_compensation_review=rollback_review,
    )


class RuntimeExecutionGuardsContractV1Tests(unittest.TestCase):
    def assert_no_authority(self, out):
        for key in guards.FALSE_FIELDS:
            self.assertIs(out[key], False, key)

    def test_approved_fresh_review_unlocks_runtime_guard_design_only(self):
        out = guards.build_runtime_execution_guards_contract(
            fresh_owner_authorization_review=approved_fresh_review(),
        )
        self.assertEqual(out["state"], guards.READY)
        self.assertTrue(out["runtime_guards_design_only"])
        self.assertTrue(out["provider_neutral"])
        self.assertEqual(out["finops_cap_cents"], 20000)
        self.assertFalse(out["production_scope_expansion_allowed"])
        self.assertFalse(out["irreversible_effect_default_allowed"])
        self.assertEqual(out["next_allowed_step"], guards.NEXT_ALLOWED_STEP)
        self.assert_no_authority(out)

    def test_fresh_authorization_must_be_exact_ready_state(self):
        row = approved_fresh_review()
        row["state"] = "BLOCKED"
        out = guards.build_runtime_execution_guards_contract(
            fresh_owner_authorization_review=row,
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn(
            "FRESH_OWNER_AUTHORIZATION_DESIGN_REVIEW_REQUIRED",
            out["blockers"],
        )
        self.assert_no_authority(out)

    def test_historical_authorization_reuse_is_forbidden(self):
        row = approved_fresh_review()
        row["authorization_reuse_allowed"] = True
        out = guards.build_runtime_execution_guards_contract(
            fresh_owner_authorization_review=row,
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("AUTHORIZATION_REUSE_MUST_BE_FORBIDDEN", out["blockers"])
        self.assert_no_authority(out)

    def test_generic_chat_can_never_promote_runtime_readiness(self):
        row = approved_fresh_review()
        row["generic_chat_is_authorization"] = True
        out = guards.build_runtime_execution_guards_contract(
            fresh_owner_authorization_review=row,
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("GENERIC_CHAT_AUTHORIZATION_FORBIDDEN", out["blockers"])
        self.assert_no_authority(out)

    def test_runtime_guard_matrix_covers_core_operational_risks(self):
        out = guards.build_runtime_execution_guards_contract(
            fresh_owner_authorization_review=approved_fresh_review(),
        )
        required = set(out["required_runtime_guards"])
        self.assertTrue({
            "FRESH_OWNER_AUTHORIZATION_VERIFIED_AT_DISPATCH",
            "AUTHORIZATION_SINGLE_USE_ENFORCED",
            "TENANT_ISOLATION_ENFORCED",
            "PERSISTENT_IDEMPOTENCY_ENFORCED",
            "PERSISTENT_EFFECT_KEY_UNIQUENESS",
            "DISPATCH_RECORDED_BEFORE_EXTERNAL_EFFECT",
            "OUTCOME_UNKNOWN_FAIL_CLOSED",
            "ROLLBACK_COMPENSATION_CLASS_BOUND",
            "FINOPS_RUNTIME_CAP_ENFORCED",
            "CAPACITY_QUOTA_ENFORCED",
            "PROVIDER_ADAPTER_ATTESTATION_REQUIRED",
            "SECURITY_PRIVACY_INCIDENT_FAIL_CLOSED",
            "CIRCUIT_BREAKER_REQUIRED",
            "KILL_SWITCH_REQUIRED",
            "AUDIT_RECEIPT_REQUIRED",
        }.issubset(required))
        self.assert_no_authority(out)

    def test_observability_contract_binds_scope_effect_and_cost(self):
        out = guards.build_runtime_execution_guards_contract(
            fresh_owner_authorization_review=approved_fresh_review(),
        )
        fields = set(out["required_observability_fields"])
        self.assertTrue({
            "trace_id",
            "execution_id",
            "owner_id",
            "tenant_id",
            "workspace_id",
            "customer_id",
            "pilot_id",
            "action_family",
            "operation_kind",
            "authorization_digest",
            "authenticated_receipt_digest",
            "idempotency_key_digest",
            "effect_key_digest",
            "provider_identity_ref",
            "writer_identity_ref",
            "before_state_digest",
            "after_state_digest",
            "rollback_plan_digest",
            "finops_estimate_cents",
            "outcome",
        }.issubset(fields))
        self.assert_no_authority(out)

    def test_runtime_contract_performs_no_runtime_action(self):
        out = guards.build_runtime_execution_guards_contract(
            fresh_owner_authorization_review=approved_fresh_review(),
        )
        for key in (
            "runtime_guard_verified",
            "fresh_authorization_consumed",
            "capacity_reserved",
            "quota_consumed",
            "finops_charge_reserved",
            "provider_adapter_attested",
            "provider_identity_verified",
            "writer_identity_verified",
            "circuit_breaker_armed",
            "kill_switch_armed",
            "audit_receipt_written",
            "observability_event_written",
        ):
            self.assertFalse(out[key], key)
        self.assert_no_authority(out)

    def test_provider_remains_unselected_and_unbound(self):
        out = guards.build_runtime_execution_guards_contract(
            fresh_owner_authorization_review=approved_fresh_review(),
        )
        self.assertTrue(out["provider_adapter_attestation_required"])
        self.assertTrue(out["provider_identity_binding_required"])
        self.assertFalse(out["provider_selected"])
        self.assertFalse(out["provider_bound"])
        self.assertFalse(out["provider_called"])
        self.assert_no_authority(out)

    def test_next_step_is_provider_adapter_attestation_design_only(self):
        out = guards.build_runtime_execution_guards_contract(
            fresh_owner_authorization_review=approved_fresh_review(),
        )
        self.assertEqual(
            out["next_allowed_step"],
            "DESIGN_PROVIDER_ADAPTER_ATTESTATION_CONTRACT_ONLY",
        )
        self.assertFalse(out["executor_implementation_allowed"])
        self.assertFalse(out["production_mutation_authorized"])
        self.assert_no_authority(out)


if __name__ == "__main__":
    unittest.main()
