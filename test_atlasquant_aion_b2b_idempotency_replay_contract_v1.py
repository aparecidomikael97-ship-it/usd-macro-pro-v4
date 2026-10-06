from __future__ import annotations

import unittest

import atlasquant_aion_b2b_future_executor_boundary_v2 as boundary
import atlasquant_aion_b2b_future_executor_capability_contract_v1 as capability
import atlasquant_aion_b2b_idempotency_replay_contract_v1 as replay
import atlasquant_aion_b2b_owner_renewal_action_adapter_plan_v2 as adapter
import atlasquant_aion_b2b_owner_renewal_action_adapter_receipt_v2 as receipts
import atlasquant_aion_b2b_real_receipt_authenticator_contract_v1 as auth
from test_atlasquant_aion_b2b_owner_renewal_action_adapter_v2 import (
    args_v2,
    receipt_args_v2,
)


def approved_authenticator_review():
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
    return auth.build_real_receipt_authenticator_contract(
        capability_review=capability_review,
    )


class IdempotencyReplayContractV1Tests(unittest.TestCase):
    def assert_no_authority(self, out):
        for key in replay.FALSE_FIELDS:
            self.assertIs(out[key], False, key)

    def test_approved_authenticator_unlocks_design_only(self):
        out = replay.build_idempotency_replay_contract(
            authenticator_review=approved_authenticator_review(),
        )
        self.assertEqual(out["state"], replay.READY)
        self.assertTrue(out["idempotency_replay_design_only"])
        self.assertTrue(out["reuses_existing_core_safety"])
        self.assertTrue(out["persistent_registry_required"])
        self.assertTrue(out["persistent_execution_store_required"])
        self.assertTrue(out["dispatch_record_before_external_effect_required"])
        self.assertTrue(out["automatic_retry_after_unknown_forbidden"])
        self.assertEqual(out["next_allowed_step"], replay.NEXT_ALLOWED_STEP)
        self.assert_no_authority(out)

    def test_authenticator_must_be_exact_ready_state(self):
        row = approved_authenticator_review()
        row["state"] = "BLOCKED"
        out = replay.build_idempotency_replay_contract(
            authenticator_review=row,
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("AUTHENTICATOR_DESIGN_REVIEW_REQUIRED", out["blockers"])
        self.assert_no_authority(out)

    def test_authenticator_authority_flip_blocks(self):
        row = approved_authenticator_review()
        row["nonce_claimed"] = True
        out = replay.build_idempotency_replay_contract(
            authenticator_review=row,
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("AUTHENTICATOR_UNSAFE_FIELD:nonce_claimed", out["blockers"])
        self.assert_no_authority(out)

    def test_replay_rejection_requirement_cannot_be_removed(self):
        row = approved_authenticator_review()
        row["replay_rejection_required"] = False
        out = replay.build_idempotency_replay_contract(
            authenticator_review=row,
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("REPLAY_REJECTION_REQUIREMENT_MISSING", out["blockers"])
        self.assert_no_authority(out)

    def test_core_safety_components_are_reused_not_reimplemented(self):
        out = replay.build_idempotency_replay_contract(
            authenticator_review=approved_authenticator_review(),
        )
        self.assertEqual(
            out["core_nonce_registry"],
            "atlasquant_aion_nonce_registry.PersistentNonceRegistry",
        )
        self.assertEqual(
            out["core_execution_store"],
            "atlasquant_aion_durable_execution_kernel.DurableExecutionStore",
        )
        self.assertEqual(
            out["core_execution_id"],
            "atlasquant_aion_durable_execution_kernel.canonical_execution_id",
        )
        self.assert_no_authority(out)

    def test_state_model_matches_durable_execution_safety_kernel(self):
        out = replay.build_idempotency_replay_contract(
            authenticator_review=approved_authenticator_review(),
        )
        self.assertEqual(
            out["required_state_model"],
            (
                "PREPARED",
                "LEASED",
                "DISPATCH_RECORDED",
                "RETRY_WAIT",
                "OUTCOME_UNKNOWN",
                "COMPLETED",
                "CANCELED",
                "DLQ",
            ),
        )
        self.assert_no_authority(out)

    def test_invariants_cover_conflict_concurrency_unknown_and_reconciliation(self):
        out = replay.build_idempotency_replay_contract(
            authenticator_review=approved_authenticator_review(),
        )
        invariants = set(out["required_invariants"])
        self.assertTrue({
            "SAME_IDEMPOTENCY_SAME_PAYLOAD_IS_REPLAY",
            "SAME_IDEMPOTENCY_DIFFERENT_PAYLOAD_IS_CONFLICT",
            "PERSISTENT_EFFECT_KEY_UNIQUENESS",
            "CONCURRENT_DUPLICATE_SINGLE_WINNER",
            "DURABLE_STATE_SURVIVES_REOPEN",
            "EXTERNAL_DISPATCH_RECORDED_BEFORE_EFFECT",
            "POST_DISPATCH_AMBIGUITY_BECOMES_OUTCOME_UNKNOWN",
            "OUTCOME_UNKNOWN_AUTOMATIC_RETRY_FORBIDDEN",
            "OUTCOME_UNKNOWN_REQUIRES_EXPLICIT_RECONCILIATION",
            "RECONCILIATION_REQUIRES_EVIDENCE",
            "RECONCILIATION_REQUIRES_SEPARATE_AUTHORIZATION",
        }.issubset(invariants))
        self.assert_no_authority(out)

    def test_required_bindings_cover_scope_receipt_and_effect_identity(self):
        out = replay.build_idempotency_replay_contract(
            authenticator_review=approved_authenticator_review(),
        )
        required = set(out["required_bindings"])
        self.assertTrue({
            "owner_id",
            "tenant_id",
            "workspace_id",
            "customer_id",
            "pilot_id",
            "action_family",
            "operation_kind",
            "execution_request_digest",
            "command_plan_digest",
            "adapter_plan_digest",
            "dry_run_digest",
            "rollback_plan_digest",
            "authenticated_receipt_digest",
            "idempotency_key_digest",
            "effect_key_digest",
            "payload_digest",
        }.issubset(required))
        self.assert_no_authority(out)

    def test_contract_contains_no_runtime_or_persistence_material(self):
        out = replay.build_idempotency_replay_contract(
            authenticator_review=approved_authenticator_review(),
        )
        text = repr(out)
        for marker in (
            "sqlite://",
            "http://",
            "https://",
            "Bearer ",
            "Authorization:",
            "lease-token-",
            "curl ",
            "powershell ",
        ):
            self.assertNotIn(marker, text)
        self.assertFalse(out["nonce_claimed"])
        self.assertFalse(out["idempotency_reserved"])
        self.assertFalse(out["effect_key_reserved"])
        self.assertFalse(out["execution_record_created"])
        self.assertFalse(out["execution_store_opened"])
        self.assertFalse(out["lease_acquired"])
        self.assertFalse(out["dispatch_recorded"])
        self.assertFalse(out["retry_scheduled"])
        self.assertFalse(out["reconciliation_performed"])
        self.assert_no_authority(out)

    def test_next_step_is_rollback_compensation_design_only(self):
        out = replay.build_idempotency_replay_contract(
            authenticator_review=approved_authenticator_review(),
        )
        self.assertEqual(
            out["next_allowed_step"],
            "DESIGN_ROLLBACK_COMPENSATION_CONTRACT_ONLY",
        )
        self.assertFalse(out["executor_implementation_allowed"])
        self.assertFalse(out["external_action_executed"])
        self.assert_no_authority(out)


if __name__ == "__main__":
    unittest.main()
