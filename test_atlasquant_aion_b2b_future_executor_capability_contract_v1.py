from __future__ import annotations

import unittest

import atlasquant_aion_b2b_future_executor_boundary_v2 as boundary
import atlasquant_aion_b2b_future_executor_capability_contract_v1 as contract
import atlasquant_aion_b2b_owner_renewal_action_adapter_plan_v2 as adapter
import atlasquant_aion_b2b_owner_renewal_action_adapter_receipt_v2 as receipts
from test_atlasquant_aion_b2b_owner_renewal_action_adapter_v2 import (
    args_v2,
    receipt_args_v2,
)


def approved_boundary():
    plan = adapter.build_owner_renewal_action_adapter_plan_v2(**args_v2())
    receipt = receipts.validate_synthetic_owner_renewal_action_receipt_v2(
        **receipt_args_v2()
    )
    return boundary.evaluate_future_executor_boundary(
        adapter_plan_v2=plan,
        synthetic_receipt_validation=receipt,
    )


class FutureExecutorCapabilityContractV1Tests(unittest.TestCase):
    def assert_no_authority(self, out):
        for key in contract.FALSE_FIELDS:
            self.assertIs(out[key], False, key)

    def test_approved_boundary_unlocks_capability_design_only(self):
        out = contract.build_future_executor_capability_contract(
            boundary_review=approved_boundary(),
        )
        self.assertEqual(out["state"], contract.READY)
        self.assertTrue(out["capability_design_only"])
        self.assertTrue(out["provider_neutral"])
        self.assertTrue(out["fresh_owner_authorization_required"])
        self.assertFalse(out["authorization_reuse_allowed"])
        self.assertEqual(out["next_allowed_step"], contract.NEXT_ALLOWED_STEP)
        self.assert_no_authority(out)

    def test_boundary_must_be_exact_v2_ready_state(self):
        row = approved_boundary()
        row["state"] = "BLOCKED"
        out = contract.build_future_executor_capability_contract(
            boundary_review=row,
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("BOUNDARY_V2_DESIGN_REVIEW_REQUIRED", out["blockers"])
        self.assert_no_authority(out)

    def test_boundary_authority_flip_blocks(self):
        row = approved_boundary()
        row["provider_selected"] = True
        out = contract.build_future_executor_capability_contract(
            boundary_review=row,
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("BOUNDARY_V2_UNSAFE_FIELD:provider_selected", out["blockers"])
        self.assert_no_authority(out)

    def test_action_matrix_is_abstract_and_complete(self):
        out = contract.build_future_executor_capability_contract(
            boundary_review=approved_boundary(),
        )
        self.assertEqual(
            out["operation_contracts"],
            {
                "RENEWAL": "CONTRACT_CONTINUITY",
                "RENEWAL_WITH_CHANGES": "CONTRACT_CHANGE",
                "NON_RENEWAL": "SERVICE_OFFBOARDING",
                "REMEDIATION": "SERVICE_REMEDIATION",
                "CAPACITY_RESCOPE": "CAPACITY_CHANGE",
                "REPRICING": "COMMERCIAL_PRICING_CHANGE",
                "INCIDENT_REMEDIATION": "INCIDENT_REMEDIATION",
                "SERVICE_PAUSE": "SERVICE_PAUSE",
                "SERVICE_TERMINATION": "SERVICE_TERMINATION",
            },
        )
        self.assertEqual(len(out["supported_action_families"]), 9)
        self.assert_no_authority(out)

    def test_required_future_proofs_are_all_explicit(self):
        out = contract.build_future_executor_capability_contract(
            boundary_review=approved_boundary(),
        )
        self.assertEqual(
            out["required_future_proofs"],
            (
                "AUTHENTICATED_REAL_RECEIPT_CONTRACT",
                "PERSISTENT_IDEMPOTENCY_AND_REPLAY_GUARD",
                "PRODUCTION_ROLLBACK_OR_COMPENSATION_PROOF",
                "FRESH_OWNER_EXECUTION_AUTHORIZATION",
                "FINOPS_RUNTIME_BUDGET_GUARD",
                "TENANT_SCOPE_BINDING",
                "PROVIDER_ADAPTER_ATTESTATION",
                "OBSERVABILITY_AND_AUDIT_RECEIPT",
            ),
        )
        self.assert_no_authority(out)

    def test_design_contract_contains_no_runtime_material(self):
        out = contract.build_future_executor_capability_contract(
            boundary_review=approved_boundary(),
        )
        text = repr(out)
        for marker in (
            "http://",
            "https://",
            "Bearer ",
            "sk-",
            "api_key=",
            "Authorization:",
            "curl ",
            "powershell ",
        ):
            self.assertNotIn(marker, text)
        self.assert_no_authority(out)

    def test_next_step_is_receipt_authenticator_design_only(self):
        out = contract.build_future_executor_capability_contract(
            boundary_review=approved_boundary(),
        )
        self.assertEqual(
            out["next_allowed_step"],
            "DESIGN_REAL_RECEIPT_AUTHENTICATOR_CONTRACT_ONLY",
        )
        self.assertFalse(out["executor_implementation_allowed"])
        self.assertFalse(out["provider_selection_allowed"])
        self.assert_no_authority(out)


if __name__ == "__main__":
    unittest.main()
