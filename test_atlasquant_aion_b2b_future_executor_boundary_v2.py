from __future__ import annotations

import unittest
from unittest.mock import patch

import atlasquant_aion_b2b_owner_renewal_action_adapter_plan as adapter_v1
import atlasquant_aion_b2b_owner_renewal_action_adapter_plan_v2 as adapter_v2
import atlasquant_aion_b2b_owner_renewal_action_adapter_receipt_v2 as receipts
from atlasquant_aion_b2b_future_executor_boundary_v2 import (
    FALSE_FIELDS,
    READY,
    NEXT_ALLOWED_STEP,
    evaluate_future_executor_boundary,
)
from test_atlasquant_aion_b2b_owner_renewal_action_adapter_v2 import (
    args_v2,
    receipt_args_v2,
)


def build_inputs():
    plan = adapter_v2.build_owner_renewal_action_adapter_plan_v2(**args_v2())
    receipt = receipts.validate_synthetic_owner_renewal_action_receipt_v2(
        **receipt_args_v2()
    )
    return plan, receipt


class FutureExecutorBoundaryV2Tests(unittest.TestCase):
    def assert_no_authority(self, row):
        for key in FALSE_FIELDS:
            self.assertIs(row[key], False, key)

    def test_final_hardened_chain_unlocks_design_review_only(self):
        plan, receipt = build_inputs()
        out = evaluate_future_executor_boundary(
            adapter_plan_v2=plan,
            synthetic_receipt_validation=receipt,
        )
        self.assertEqual(out["state"], READY)
        self.assertTrue(out["design_review_eligible"])
        self.assertEqual(out["next_allowed_step"], NEXT_ALLOWED_STEP)
        self.assertTrue(out["executor_contract_design_only"])
        self.assertTrue(out["independent_dynamic_audit_pending"])
        self.assert_no_authority(out)

    def test_legacy_policy_mutation_does_not_reblock_v2_design_boundary(self):
        plan, receipt = build_inputs()
        with (
            patch.object(adapter_v1, "RISKS", ("legacy_canary",)),
            patch.object(adapter_v1, "ENVIRONMENT_SCHEMA", "LEGACY_MUTATED"),
            patch.object(adapter_v1, "FINOPS_CAP_CENTS", 1),
        ):
            out = evaluate_future_executor_boundary(
                adapter_plan_v2=plan,
                synthetic_receipt_validation=receipt,
            )
        self.assertEqual(out["state"], READY)
        self.assert_no_authority(out)

    def test_v2_policy_drift_blocks(self):
        plan, receipt = build_inputs()
        with patch.object(adapter_v2, "FINOPS_CAP_CENTS", 20001):
            out = evaluate_future_executor_boundary(
                adapter_plan_v2=plan,
                synthetic_receipt_validation=receipt,
            )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("V2_FINOPS_CAP_INVALID", out["blockers"])
        self.assert_no_authority(out)

    def test_v1_artifact_cannot_enter_boundary(self):
        plan, receipt = build_inputs()
        plan["schema"] = adapter_v1.SCHEMA
        out = evaluate_future_executor_boundary(
            adapter_plan_v2=plan,
            synthetic_receipt_validation=receipt,
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("ADAPTER_V2_SCHEMA_REQUIRED", out["blockers"])
        self.assert_no_authority(out)

    def test_real_receipt_authority_blocks(self):
        plan, receipt = build_inputs()
        receipt["actual_receipt_generated"] = True
        receipt["execution_verified"] = True
        out = evaluate_future_executor_boundary(
            adapter_plan_v2=plan,
            synthetic_receipt_validation=receipt,
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn(
            "RECEIPT_REAL_AUTHORITY_FORBIDDEN:actual_receipt_generated",
            out["blockers"],
        )
        self.assertIn(
            "RECEIPT_REAL_AUTHORITY_FORBIDDEN:execution_verified",
            out["blockers"],
        )
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

    def test_separate_executor_contract_is_mandatory(self):
        plan, receipt = build_inputs()
        plan["adapter_plan"]["future_executor_requires_separate_contract"] = False
        out = evaluate_future_executor_boundary(
            adapter_plan_v2=plan,
            synthetic_receipt_validation=receipt,
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("SEPARATE_EXECUTOR_CONTRACT_REQUIRED", out["blockers"])
        self.assert_no_authority(out)

    def test_boundary_output_contains_no_execution_material(self):
        plan, receipt = build_inputs()
        out = evaluate_future_executor_boundary(
            adapter_plan_v2=plan,
            synthetic_receipt_validation=receipt,
        )
        for forbidden in ("endpoint", "payload", "credential", "token", "provider_config"):
            self.assertNotIn(forbidden, out)
        self.assert_no_authority(out)


if __name__ == "__main__":
    unittest.main()
