from __future__ import annotations

import unittest
from unittest.mock import patch

import atlasquant_aion_b2b_owner_renewal_action_adapter_plan as adapter_v1
import atlasquant_aion_b2b_owner_renewal_action_adapter_plan_v2 as adapter_v2
from atlasquant_aion_b2b_future_executor_boundary import (
    FALSE_FIELDS,
    READY,
    evaluate_future_executor_boundary,
)
from test_atlasquant_aion_b2b_owner_renewal_action_adapter_v2 import (
    args_v2,
    receipt_args_v2,
)
import atlasquant_aion_b2b_owner_renewal_action_adapter_receipt_v2 as receipts


def build_inputs():
    adapter_plan = adapter_v2.build_owner_renewal_action_adapter_plan_v2(**args_v2())
    data = receipt_args_v2()
    receipt_validation = receipts.validate_synthetic_owner_renewal_action_receipt_v2(
        **data
    )
    return adapter_plan, receipt_validation


class FutureExecutorBoundaryTests(unittest.TestCase):
    def assert_no_authority(self, out):
        for key in FALSE_FIELDS:
            self.assertIs(out[key], False, key)

    def test_current_head_is_intentionally_blocked_until_h1_h2_close(self):
        plan, receipt = build_inputs()
        out = evaluate_future_executor_boundary(
            adapter_plan_v2=plan,
            synthetic_receipt_validation=receipt,
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("V2_FINOPS_NOT_LOCALLY_OWNED", out["blockers"])
        self.assertIn("V2_FINOPS_TYPE_CONTRACT_MISSING", out["blockers"])
        self.assertIn("V1_NOT_MARKED_LEGACY_NON_EXECUTABLE", out["blockers"])
        self.assertIn("V1_EXECUTOR_BOUNDARY_NOT_CLOSED", out["blockers"])
        self.assertFalse(out["design_review_eligible"])
        self.assert_no_authority(out)

    def test_future_hardened_markers_only_unlock_design_review(self):
        plan, receipt = build_inputs()
        with (
            patch.object(adapter_v2, "FINOPS_CAP_CENTS", 20000),
            patch.object(adapter_v2, "FINOPS_CONTRACT_SOURCE", "LOCAL_V2_LITERAL", create=True),
            patch.object(adapter_v2, "FINOPS_INPUT_TYPE", "EXACT_INT", create=True),
            patch.object(adapter_v1, "LEGACY_NON_EXECUTABLE", True, create=True),
            patch.object(adapter_v1, "EXECUTOR_ELIGIBLE", False, create=True),
        ):
            out = evaluate_future_executor_boundary(
                adapter_plan_v2=plan,
                synthetic_receipt_validation=receipt,
            )
        self.assertEqual(out["state"], READY)
        self.assertTrue(out["design_review_eligible"])
        self.assertEqual(out["next_allowed_step"], "DESIGN_EXECUTOR_CONTRACT_ONLY")
        self.assert_no_authority(out)

    def test_v1_adapter_artifact_cannot_enter_v2_boundary(self):
        plan, receipt = build_inputs()
        plan["schema"] = adapter_v1.SCHEMA
        out = evaluate_future_executor_boundary(
            adapter_plan_v2=plan,
            synthetic_receipt_validation=receipt,
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("ADAPTER_V2_SCHEMA_REQUIRED", out["blockers"])
        self.assert_no_authority(out)

    def test_non_synthetic_or_execution_verified_receipt_blocks(self):
        plan, receipt = build_inputs()
        receipt["synthetic"] = False
        receipt["execution_verified"] = True
        out = evaluate_future_executor_boundary(
            adapter_plan_v2=plan,
            synthetic_receipt_validation=receipt,
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("SYNTHETIC_RECEIPT_REQUIRED", out["blockers"])
        self.assertIn("EXECUTION_VERIFICATION_FORBIDDEN", out["blockers"])
        self.assert_no_authority(out)

    def test_adapter_authority_flip_blocks(self):
        plan, receipt = build_inputs()
        plan["provider_called"] = True
        out = evaluate_future_executor_boundary(
            adapter_plan_v2=plan,
            synthetic_receipt_validation=receipt,
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("ADAPTER_V2_UNSAFE_FIELD:provider_called", out["blockers"])
        self.assert_no_authority(out)

    def test_body_requires_separate_executor_contract(self):
        plan, receipt = build_inputs()
        plan["adapter_plan"]["future_executor_requires_separate_contract"] = False
        out = evaluate_future_executor_boundary(
            adapter_plan_v2=plan,
            synthetic_receipt_validation=receipt,
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("SEPARATE_EXECUTOR_CONTRACT_NOT_REQUIRED", out["blockers"])
        self.assert_no_authority(out)

    def test_boundary_never_creates_execution_material(self):
        plan, receipt = build_inputs()
        out = evaluate_future_executor_boundary(
            adapter_plan_v2=plan,
            synthetic_receipt_validation=receipt,
        )
        self.assertNotIn("endpoint", out)
        self.assertNotIn("payload", out)
        self.assertNotIn("command", out)
        self.assertNotIn("credential", out)
        self.assert_no_authority(out)


if __name__ == "__main__":
    unittest.main()
