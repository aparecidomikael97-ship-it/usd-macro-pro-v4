from __future__ import annotations

import unittest

import atlasquant_aion_b2b_provider_adapter_attestation_contract_v1 as provider
import atlasquant_aion_b2b_runtime_execution_guards_contract_v1 as guards
from test_atlasquant_aion_b2b_runtime_execution_guards_contract_v1 import (
    approved_fresh_review,
)


def approved_runtime_review():
    return guards.build_runtime_execution_guards_contract(
        fresh_owner_authorization_review=approved_fresh_review(),
    )


class ProviderAdapterAttestationContractV1Tests(unittest.TestCase):
    def assert_no_authority(self, out):
        for key in provider.FALSE_FIELDS:
            self.assertIs(out[key], False, key)

    def test_approved_runtime_guards_unlock_design_only(self):
        out = provider.build_provider_adapter_attestation_contract(
            runtime_guards_review=approved_runtime_review(),
        )
        self.assertEqual(out["state"], provider.READY)
        self.assertTrue(out["provider_adapter_attestation_design_only"])
        self.assertTrue(out["provider_neutral"])
        self.assertTrue(out["no_implicit_authority"])
        self.assertTrue(out["concrete_adapter_not_loaded"])
        self.assertTrue(out["concrete_provider_not_selected"])
        self.assertEqual(out["finops_cap_cents"], 20000)
        self.assertEqual(out["next_allowed_step"], provider.NEXT_ALLOWED_STEP)
        self.assert_no_authority(out)

    def test_runtime_guards_must_be_exact_ready_state(self):
        row = approved_runtime_review()
        row["state"] = "BLOCKED"
        out = provider.build_provider_adapter_attestation_contract(
            runtime_guards_review=row,
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("RUNTIME_GUARDS_DESIGN_REVIEW_REQUIRED", out["blockers"])
        self.assert_no_authority(out)

    def test_provider_neutrality_cannot_be_removed(self):
        row = approved_runtime_review()
        row["provider_neutral"] = False
        out = provider.build_provider_adapter_attestation_contract(
            runtime_guards_review=row,
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("PROVIDER_NEUTRAL_BOUNDARY_REQUIRED", out["blockers"])
        self.assert_no_authority(out)

    def test_finops_cap_cannot_expand(self):
        row = approved_runtime_review()
        row["finops_cap_cents"] = 20001
        out = provider.build_provider_adapter_attestation_contract(
            runtime_guards_review=row,
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("FINOPS_CAP_MUST_REMAIN_20000_CENTS", out["blockers"])
        self.assert_no_authority(out)

    def test_upstream_provider_selection_flip_blocks(self):
        row = approved_runtime_review()
        row["provider_selected"] = True
        out = provider.build_provider_adapter_attestation_contract(
            runtime_guards_review=row,
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn(
            "RUNTIME_GUARDS_UNSAFE_FIELD:provider_selected",
            out["blockers"],
        )
        self.assert_no_authority(out)

    def test_attestations_cover_identity_capabilities_cost_and_data_policy(self):
        out = provider.build_provider_adapter_attestation_contract(
            runtime_guards_review=approved_runtime_review(),
        )
        required = set(out["required_attestations"])
        self.assertTrue({
            "ADAPTER_IDENTITY_STABLE",
            "ADAPTER_VERSION_PINNED",
            "ADAPTER_MANIFEST_DIGEST_BOUND",
            "ADAPTER_CODE_DIGEST_BOUND",
            "ADAPTER_SUPPLY_CHAIN_EVIDENCE_BOUND",
            "PROVIDER_IDENTITY_REFERENCE_BOUND",
            "CAPABILITY_ALLOWLIST_DECLARED",
            "TENANT_SCOPE_BINDING_DECLARED",
            "ACTION_FAMILY_OPERATION_BINDING_DECLARED",
            "IDEMPOTENCY_SUPPORT_DECLARED",
            "EFFECT_KEY_SUPPORT_DECLARED",
            "MAX_PER_ACTION_COST_DECLARED",
            "DATA_RETENTION_POLICY_DECLARED",
            "LOG_REDACTION_POLICY_DECLARED",
            "SECRET_HANDLING_POLICY_DECLARED",
            "AUDIT_RECEIPT_SCHEMA_DECLARED",
            "NO_IMPLICIT_AUTHORITY_DECLARED",
        }.issubset(required))
        self.assert_no_authority(out)

    def test_manifest_explicitly_forbids_live_secret_and_endpoint_values(self):
        out = provider.build_provider_adapter_attestation_contract(
            runtime_guards_review=approved_runtime_review(),
        )
        forbidden = set(out["forbidden_manifest_material"])
        self.assertTrue({
            "credential_value",
            "secret_value",
            "api_key_value",
            "access_token_value",
            "refresh_token_value",
            "password_value",
            "private_key_value",
            "authorization_header_value",
            "cookie_value",
            "provider_endpoint_value",
            "webhook_url_value",
            "callback_url_value",
            "request_payload_value",
            "shell_command_value",
        }.issubset(forbidden))
        self.assert_no_authority(out)

    def test_reuses_existing_provider_neutral_and_capability_contract_names(self):
        out = provider.build_provider_adapter_attestation_contract(
            runtime_guards_review=approved_runtime_review(),
        )
        self.assertEqual(out["model_gateway_schema"], "ATLASQUANT_AION_MODEL_GATEWAY_V2")
        self.assertEqual(
            out["provider_registry_schema"],
            "ATLASQUANT_AION_PROVIDER_NEUTRAL_MODEL_REGISTRY_V1",
        )
        self.assertEqual(
            out["capability_scope_schema"],
            "ATLASQUANT_AION_CAPABILITY_SCOPE_GRANT_V1",
        )
        self.assert_no_authority(out)

    def test_contract_loads_no_adapter_and_performs_no_external_action(self):
        out = provider.build_provider_adapter_attestation_contract(
            runtime_guards_review=approved_runtime_review(),
        )
        for key in (
            "provider_adapter_attested",
            "provider_identity_verified",
            "adapter_manifest_loaded",
            "adapter_code_loaded",
            "adapter_selected",
            "provider_selected",
            "provider_bound",
            "credentials_loaded",
            "secrets_loaded",
            "endpoint_resolved",
            "payload_constructed",
            "network_called",
            "provider_called",
            "billing_executed",
        ):
            self.assertFalse(out[key], key)
        self.assert_no_authority(out)

    def test_next_step_is_provider_capability_binding_design_only(self):
        out = provider.build_provider_adapter_attestation_contract(
            runtime_guards_review=approved_runtime_review(),
        )
        self.assertEqual(
            out["next_allowed_step"],
            "DESIGN_PROVIDER_CAPABILITY_BINDING_CONTRACT_ONLY",
        )
        self.assertFalse(out["executor_implementation_allowed"])
        self.assertFalse(out["production_mutation_authorized"])
        self.assert_no_authority(out)


if __name__ == "__main__":
    unittest.main()
