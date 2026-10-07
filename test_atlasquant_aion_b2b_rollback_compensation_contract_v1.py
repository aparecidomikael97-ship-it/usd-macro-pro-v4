from __future__ import annotations

import unittest

import atlasquant_aion_b2b_future_executor_boundary_v2 as boundary
import atlasquant_aion_b2b_future_executor_capability_contract_v1 as capability
import atlasquant_aion_b2b_idempotency_replay_contract_v1 as replay
import atlasquant_aion_b2b_owner_renewal_action_adapter_plan_v2 as adapter
import atlasquant_aion_b2b_owner_renewal_action_adapter_receipt_v2 as receipts
import atlasquant_aion_b2b_real_receipt_authenticator_contract_v1 as auth
import atlasquant_aion_b2b_rollback_compensation_contract_v1 as rollback
from test_atlasquant_aion_b2b_owner_renewal_action_adapter_v2 import (
    args_v2,
    receipt_args_v2,
)


def approved_replay_review():
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
    return replay.build_idempotency_replay_contract(
        authenticator_review=auth_review,
    )


class RollbackCompensationContractV1Tests(unittest.TestCase):
    def assert_no_authority(self, out):
        for key in rollback.FALSE_FIELDS:
            self.assertIs(out[key], False, key)

    def test_approved_replay_review_unlocks_design_only(self):
        out = rollback.build_rollback_compensation_contract(
            idempotency_replay_review=approved_replay_review(),
        )
        self.assertEqual(out["state"], rollback.READY)
        self.assertTrue(out["rollback_compensation_design_only"])
        self.assertTrue(out["synthetic_rollback_is_not_production_rollback"])
        self.assertFalse(out["production_rollback_proven"])
        self.assertFalse(out["production_compensation_proven"])
        self.assertEqual(
            out["proven_synthetic_rollback_mode"],
            "PRE_EXECUTION_STAGING_REVERSAL_ONLY",
        )
        self.assertEqual(out["next_allowed_step"], rollback.NEXT_ALLOWED_STEP)
        self.assert_no_authority(out)

    def test_replay_contract_must_be_exact_ready_state(self):
        row = approved_replay_review()
        row["state"] = "BLOCKED"
        out = rollback.build_rollback_compensation_contract(
            idempotency_replay_review=row,
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn(
            "IDEMPOTENCY_REPLAY_DESIGN_REVIEW_REQUIRED",
            out["blockers"],
        )
        self.assert_no_authority(out)

    def test_outcome_unknown_safety_cannot_be_removed(self):
        row = approved_replay_review()
        row["automatic_retry_after_unknown_forbidden"] = False
        out = rollback.build_rollback_compensation_contract(
            idempotency_replay_review=row,
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn(
            "UNKNOWN_AUTOMATIC_RETRY_MUST_BE_FORBIDDEN",
            out["blockers"],
        )
        self.assert_no_authority(out)

    def test_reconciliation_authority_cannot_be_reused(self):
        row = approved_replay_review()
        row["authorization_reuse_allowed"] = True
        out = rollback.build_rollback_compensation_contract(
            idempotency_replay_review=row,
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("AUTHORIZATION_REUSE_MUST_BE_FORBIDDEN", out["blockers"])
        self.assert_no_authority(out)

    def test_reversibility_classes_are_explicit(self):
        out = rollback.build_rollback_compensation_contract(
            idempotency_replay_review=approved_replay_review(),
        )
        self.assertEqual(
            out["reversibility_classes"],
            (
                "REVERSIBLE_PRE_EXECUTION_ONLY",
                "COMPENSATABLE_EXTERNAL_EFFECT",
                "MANUAL_REMEDIATION_REQUIRED",
                "IRREVERSIBLE_EXTERNAL_EFFECT",
            ),
        )
        self.assert_no_authority(out)

    def test_required_proofs_separate_real_compensation_from_synthetic_rollback(self):
        out = rollback.build_rollback_compensation_contract(
            idempotency_replay_review=approved_replay_review(),
        )
        proofs = set(out["required_proofs"])
        self.assertTrue({
            "BEFORE_STATE_DIGEST_BOUND",
            "AFTER_STATE_DIGEST_BOUND",
            "ROLLBACK_PLAN_DIGEST_BOUND",
            "REVERSIBILITY_CLASS_EXPLICIT",
            "IRREVERSIBLE_BOUNDARY_EXPLICIT",
            "COMPENSATION_EVIDENCE_REQUIRED",
            "COMPENSATION_RECEIPT_REQUIRED",
            "SEPARATE_COMPENSATION_AUTHORIZATION_REQUIRED",
            "OUTCOME_UNKNOWN_BLOCKS_AUTOMATIC_COMPENSATION",
        }.issubset(proofs))
        self.assert_no_authority(out)

    def test_unknown_outcome_blocks_automatic_compensation(self):
        out = rollback.build_rollback_compensation_contract(
            idempotency_replay_review=approved_replay_review(),
        )
        self.assertTrue(out["outcome_unknown_blocks_automatic_compensation"])
        self.assertTrue(
            out["manual_reconciliation_precedes_compensation_when_unknown"]
        )
        self.assertFalse(out["automatic_compensation_allowed"])
        self.assertFalse(out["compensation_authorized"])
        self.assertFalse(out["compensation_performed"])
        self.assert_no_authority(out)

    def test_contract_contains_no_real_runtime_material(self):
        out = rollback.build_rollback_compensation_contract(
            idempotency_replay_review=approved_replay_review(),
        )
        text = repr(out)
        for marker in (
            "http://",
            "https://",
            "Bearer ",
            "Authorization:",
            "curl ",
            "powershell ",
            "provider_endpoint=",
        ):
            self.assertNotIn(marker, text)
        self.assertFalse(out["state_restored"])
        self.assertFalse(out["production_state_changed"])
        self.assertFalse(out["external_effect_reversed"])
        self.assert_no_authority(out)

    def test_next_step_is_fresh_owner_authorization_design_only(self):
        out = rollback.build_rollback_compensation_contract(
            idempotency_replay_review=approved_replay_review(),
        )
        self.assertEqual(
            out["next_allowed_step"],
            "DESIGN_FRESH_OWNER_EXECUTION_AUTHORIZATION_CONTRACT_ONLY",
        )
        self.assertFalse(out["business_action_authorized"])
        self.assertFalse(out["executor_implementation_allowed"])
        self.assert_no_authority(out)


if __name__ == "__main__":
    unittest.main()
