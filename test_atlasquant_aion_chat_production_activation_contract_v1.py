from __future__ import annotations

import unittest

import atlasquant_aion_chat_production_activation_contract_v1 as contract


def ready_inputs():
    return {
        "owner_context": {
            "is_human_owner": True,
            "owner_id": "HUMAN_OWNER",
            "session_bound": True,
        },
        "production_store_attestation": {
            "state": "ATTESTED_READY",
            "production": True,
            "durable": True,
            "scope_bound": True,
            "encryption_at_rest_attested": True,
            "backup_restore_attested": True,
            "schema_migration_attested": True,
            "health_check_attested": True,
        },
        "model_gateway_review": {
            "provider_neutral": True,
            "healthy_local_fallback": True,
            "routing_executes_provider_call": False,
        },
        "provider_review": {
            "ready": True,
            "state": "EXTERNAL_READY",
            "api_key_present": True,
            "pricing_configured": True,
        },
        "budget_review": {
            "budget_amounts_valid": True,
            "allow_paid": True,
            "monthly_limit_usd": 10.0,
            "remaining_usd": 10.0,
            "request_approval_mode": "PER_TURN_EXPLICIT",
        },
        "external_feature_enabled": True,
        "external_actions_blocked": True,
    }


class ProductionChatActivationContractV1Tests(unittest.TestCase):
    def assert_zero_execution(self, out):
        for key in contract.FALSE_FIELDS:
            self.assertIs(out[key], False, key)

    def test_complete_evidence_unlocks_design_review_only(self):
        out = contract.evaluate_production_chat_activation_contract(**ready_inputs())
        self.assertEqual(out["state"], contract.READY)
        self.assertTrue(out["activation_design_only"])
        self.assertEqual(
            out["next_allowed_step"],
            "IMPLEMENT_PRODUCTION_CHAT_HOST_ADAPTER_IN_SEPARATE_PR",
        )
        self.assertEqual(out["model_output_truth_state"], "MODEL_OUTPUT_UNVERIFIED")
        self.assert_zero_execution(out)

    def test_owner_identity_is_fail_closed(self):
        data = ready_inputs()
        data["owner_context"] = {
            "is_human_owner": False,
            "owner_id": "",
            "session_bound": False,
        }
        out = contract.evaluate_production_chat_activation_contract(**data)
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("HUMAN_OWNER_SESSION_REQUIRED", out["blockers"])
        self.assertIn("HUMAN_OWNER_ID_REQUIRED", out["blockers"])
        self.assertIn("HUMAN_OWNER_SESSION_BINDING_REQUIRED", out["blockers"])
        self.assert_zero_execution(out)

    def test_staging_or_unattested_store_cannot_unlock_production(self):
        data = ready_inputs()
        data["production_store_attestation"]["state"] = "STAGING_READY"
        data["production_store_attestation"]["production"] = False
        data["production_store_attestation"]["encryption_at_rest_attested"] = False
        out = contract.evaluate_production_chat_activation_contract(**data)
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("PRODUCTION_STORE_ATTESTATION_REQUIRED", out["blockers"])
        self.assertIn("PRODUCTION_STORE_FLAG_REQUIRED", out["blockers"])
        self.assertIn("ENCRYPTION_AT_REST_ATTESTATION_REQUIRED", out["blockers"])
        self.assert_zero_execution(out)

    def test_local_fallback_is_mandatory(self):
        data = ready_inputs()
        data["model_gateway_review"]["healthy_local_fallback"] = False
        out = contract.evaluate_production_chat_activation_contract(**data)
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("HEALTHY_LOCAL_FALLBACK_REQUIRED", out["blockers"])
        self.assert_zero_execution(out)

    def test_routing_layer_may_not_call_provider(self):
        data = ready_inputs()
        data["model_gateway_review"]["routing_executes_provider_call"] = True
        out = contract.evaluate_production_chat_activation_contract(**data)
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("ROUTING_MUST_NOT_CALL_PROVIDER", out["blockers"])
        self.assert_zero_execution(out)

    def test_provider_config_and_pricing_are_required(self):
        data = ready_inputs()
        data["provider_review"] = {
            "ready": False,
            "state": "MISSING_PRICING_CONFIG",
            "api_key_present": True,
            "pricing_configured": False,
        }
        out = contract.evaluate_production_chat_activation_contract(**data)
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("EXTERNAL_PROVIDER_READY_REQUIRED", out["blockers"])
        self.assertIn("PROVIDER_PRICING_REQUIRED", out["blockers"])
        self.assert_zero_execution(out)

    def test_budget_and_per_turn_approval_are_mandatory(self):
        data = ready_inputs()
        data["budget_review"]["allow_paid"] = False
        data["budget_review"]["request_approval_mode"] = "SESSION_WIDE"
        out = contract.evaluate_production_chat_activation_contract(**data)
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("PAID_MODEL_USE_NOT_EXPLICITLY_ENABLED", out["blockers"])
        self.assertIn("PER_TURN_EXPLICIT_APPROVAL_REQUIRED", out["blockers"])
        self.assert_zero_execution(out)

    def test_no_external_action_authority_can_be_smuggled_in(self):
        data = ready_inputs()
        data["external_actions_blocked"] = False
        out = contract.evaluate_production_chat_activation_contract(**data)
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("EXTERNAL_ACTIONS_MUST_REMAIN_BLOCKED", out["blockers"])
        self.assert_zero_execution(out)


if __name__ == "__main__":
    unittest.main()
