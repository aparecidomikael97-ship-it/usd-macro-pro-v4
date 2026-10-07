from __future__ import annotations

import unittest

import atlasquant_aion_b2b_provider_adapter_attestation_contract_v1 as adapter
import atlasquant_aion_b2b_provider_capability_binding_contract_v1 as binding
from test_atlasquant_aion_b2b_provider_adapter_attestation_contract_v1 import (
    approved_runtime_review,
)


def approved_adapter_review():
    return adapter.build_provider_adapter_attestation_contract(
        runtime_guards_review=approved_runtime_review(),
    )


class ProviderCapabilityBindingContractV1Tests(unittest.TestCase):
    def assert_no_authority(self, out):
        for key in binding.FALSE_FIELDS:
            self.assertIs(out[key], False, key)

    def test_approved_adapter_review_unlocks_design_only(self):
        out = binding.build_provider_capability_binding_contract(
            provider_adapter_attestation_review=approved_adapter_review(),
        )
        self.assertEqual(out["state"], binding.READY)
        self.assertTrue(out["provider_capability_binding_design_only"])
        self.assertTrue(out["provider_neutral"])
        self.assertEqual(out["binding_mode"], "EXACT_INTERSECTION_FAIL_CLOSED")
        self.assertTrue(out["exact_intersection_required"])
        self.assertTrue(out["empty_intersection_blocks"])
        self.assertTrue(out["requested_extra_capability_blocks"])
        self.assertFalse(out["adapter_allowlist_is_authority"])
        self.assertTrue(out["adapter_allowlist_is_ceiling"])
        self.assertEqual(out["finops_cap_cents"], 20000)
        self.assert_no_authority(out)

    def test_adapter_attestation_must_be_exact_ready_state(self):
        row = approved_adapter_review()
        row["state"] = "BLOCKED"
        out = binding.build_provider_capability_binding_contract(
            provider_adapter_attestation_review=row,
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn(
            "PROVIDER_ADAPTER_ATTESTATION_DESIGN_REVIEW_REQUIRED",
            out["blockers"],
        )
        self.assert_no_authority(out)

    def test_implicit_authority_cannot_be_introduced(self):
        row = approved_adapter_review()
        row["no_implicit_authority"] = False
        out = binding.build_provider_capability_binding_contract(
            provider_adapter_attestation_review=row,
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn(
            "NO_IMPLICIT_AUTHORITY_REQUIREMENT_MISSING",
            out["blockers"],
        )
        self.assert_no_authority(out)

    def test_upstream_provider_binding_flip_blocks(self):
        row = approved_adapter_review()
        row["provider_bound"] = True
        out = binding.build_provider_capability_binding_contract(
            provider_adapter_attestation_review=row,
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn(
            "PROVIDER_ADAPTER_ATTESTATION_UNSAFE_FIELD:provider_bound",
            out["blockers"],
        )
        self.assert_no_authority(out)

    def test_finops_cap_cannot_expand(self):
        row = approved_adapter_review()
        row["finops_cap_cents"] = 50000
        out = binding.build_provider_capability_binding_contract(
            provider_adapter_attestation_review=row,
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("FINOPS_CAP_MUST_REMAIN_20000_CENTS", out["blockers"])
        self.assert_no_authority(out)

    def test_binding_rules_are_fail_closed_and_least_privilege(self):
        out = binding.build_provider_capability_binding_contract(
            provider_adapter_attestation_review=approved_adapter_review(),
        )
        rules = set(out["required_binding_rules"])
        self.assertTrue({
            "EXACT_INTERSECTION_ONLY",
            "EMPTY_INTERSECTION_BLOCKS",
            "REQUESTED_EXTRA_CAPABILITY_BLOCKS",
            "NO_WILDCARDS",
            "NO_PERMISSION_EXPANSION",
            "NO_CROSS_TENANT",
            "NO_CROSS_WORKSPACE",
            "NO_CROSS_DOMAIN",
            "NO_CROSS_ACTION_FAMILY",
            "NO_CROSS_OPERATION_KIND",
            "OWNER_SCOPE_CANNOT_BE_OVERRIDDEN",
            "RUNTIME_GUARD_CANNOT_BE_OVERRIDDEN",
            "ADAPTER_FORBIDDEN_CAPABILITY_WINS",
            "ADAPTER_ALLOWLIST_IS_CEILING_NOT_AUTHORITY",
            "COST_CEILING_MUST_REMAIN_WITHIN_FINOPS_CAP",
            "BINDING_SINGLE_USE_WITH_AUTHORIZATION",
        }.issubset(rules))
        self.assert_no_authority(out)

    def test_binding_fields_cover_scope_authorization_and_capability_digests(self):
        out = binding.build_provider_capability_binding_contract(
            provider_adapter_attestation_review=approved_adapter_review(),
        )
        fields = set(out["required_binding_fields"])
        self.assertTrue({
            "owner_id",
            "tenant_id",
            "workspace_id",
            "domain",
            "customer_id",
            "pilot_id",
            "action_family",
            "operation_kind",
            "authorization_digest",
            "runtime_guards_digest",
            "adapter_attestation_digest",
            "adapter_manifest_digest",
            "provider_identity_ref",
            "capability_scope_digest",
            "requested_capabilities_digest",
            "effective_capabilities_digest",
            "forbidden_capabilities_digest",
            "finops_ceiling_digest",
            "binding_issued_at",
            "binding_expires_at",
        }.issubset(fields))
        self.assert_no_authority(out)

    def test_capability_sources_are_all_upstream_authority_ceiling_sources(self):
        out = binding.build_provider_capability_binding_contract(
            provider_adapter_attestation_review=approved_adapter_review(),
        )
        self.assertEqual(
            set(out["capability_sources"]),
            {
                "FRESH_OWNER_AUTHORIZATION_SCOPE",
                "RUNTIME_GUARD_ALLOWLIST",
                "ADAPTER_ATTESTED_ALLOWLIST",
                "TENANT_WORKSPACE_DOMAIN_SCOPE",
                "ACTION_FAMILY_OPERATION_SCOPE",
            },
        )
        self.assert_no_authority(out)

    def test_contract_materializes_no_capabilities_or_provider(self):
        out = binding.build_provider_capability_binding_contract(
            provider_adapter_attestation_review=approved_adapter_review(),
        )
        self.assertFalse(out["capability_scope_loaded"])
        self.assertFalse(out["requested_capabilities_loaded"])
        self.assertFalse(out["effective_capabilities_materialized"])
        self.assertFalse(out["permissions_expanded"])
        self.assertFalse(out["provider_selected"])
        self.assertFalse(out["provider_bound"])
        self.assertFalse(out["endpoint_resolved"])
        self.assertFalse(out["credentials_loaded"])
        self.assertFalse(out["provider_called"])
        self.assert_no_authority(out)

    def test_next_step_is_execution_envelope_design_only(self):
        out = binding.build_provider_capability_binding_contract(
            provider_adapter_attestation_review=approved_adapter_review(),
        )
        self.assertEqual(
            out["next_allowed_step"],
            "DESIGN_EXECUTION_ENVELOPE_CONTRACT_ONLY",
        )
        self.assertFalse(out["execution_allowed"])
        self.assertFalse(out["executor_implementation_allowed"])
        self.assert_no_authority(out)


if __name__ == "__main__":
    unittest.main()
