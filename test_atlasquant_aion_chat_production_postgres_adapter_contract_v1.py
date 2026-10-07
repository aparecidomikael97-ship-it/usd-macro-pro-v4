from __future__ import annotations

import unittest

import atlasquant_aion_chat_production_postgres_adapter_contract_v1 as contract


def ready_inputs():
    return {
        "binding": {
            "bound": True,
            "owner_id": "mikael",
            "tenant_id": "atlasquant-owner",
            "workspace_id": "central",
            "credential_fingerprint_present": True,
            "permissions_verified": True,
        },
        "storage": {
            "attested_ready": True,
            "healthy": True,
            "schema_compatible": True,
            "scope_policy_healthy": True,
            "fail_closed_on_unavailable": True,
            "idempotent_append": True,
        },
        "routing": {
            "provider_neutral": True,
            "executes_provider_call": False,
            "executes_billing": False,
            "healthy_local_fallback": True,
        },
        "provider_boundary": {
            "external_provider_optional": True,
            "per_turn_explicit_approval": True,
            "budget_gate_required": True,
            "privacy_gate_required": True,
            "model_output_unverified": True,
            "external_actions_blocked": True,
            "provider_approval_implies_external_action_authority": False,
        },
        "persistence_policy": {
            "persist_user_before_provider": True,
            "user_persistence_confirmed": True,
            "assistant_persistence_must_confirm": True,
            "unknown_assistant_persistence_not_success": True,
            "session_only_fallback_forbidden": True,
            "staging_sqlite_fallback_forbidden": True,
            "provider_result_idempotency": True,
            "no_provider_recall_after_unknown_persistence": True,
            "separate_persistence_reconciliation": True,
            "claims_saved_when_unknown": False,
            "provider_before_user_persist": False,
            "automatic_second_provider_call_after_unknown": False,
        },
    }


class ProductionPostgresAdapterContractV1Tests(unittest.TestCase):
    def assert_zero_execution(self, out):
        for key in contract.FALSE_FIELDS:
            self.assertIs(out[key], False, key)

    def test_complete_design_unlocks_implementation_review_only(self):
        out = contract.evaluate_production_postgres_adapter_contract(**ready_inputs())
        self.assertEqual(out["state"], contract.READY)
        self.assertTrue(out["design_only"])
        self.assertEqual(
            out["next_allowed_step"],
            "IMPLEMENT_PRODUCTION_POSTGRES_STORE_ADAPTER_IN_SEPARATE_PR",
        )
        self.assertEqual(out["model_output_truth_state"], "MODEL_OUTPUT_UNVERIFIED")
        self.assert_zero_execution(out)

    def test_scope_binding_is_mandatory(self):
        data = ready_inputs()
        data["binding"]["bound"] = False
        data["binding"]["workspace_id"] = ""
        out = contract.evaluate_production_postgres_adapter_contract(**data)
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("AUTHENTICATED_BINDING_REQUIRED", out["blockers"])
        self.assertIn("WORKSPACE_SCOPE_REQUIRED", out["blockers"])
        self.assert_zero_execution(out)

    def test_unhealthy_database_blocks_adapter_readiness(self):
        data = ready_inputs()
        data["storage"]["healthy"] = False
        out = contract.evaluate_production_postgres_adapter_contract(**data)
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("DATABASE_HEALTH_REQUIRED", out["blockers"])
        self.assert_zero_execution(out)

    def test_router_itself_may_not_call_or_bill(self):
        data = ready_inputs()
        data["routing"]["executes_provider_call"] = True
        data["routing"]["executes_billing"] = True
        out = contract.evaluate_production_postgres_adapter_contract(**data)
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("ROUTER_MUST_NOT_CALL_PROVIDER", out["blockers"])
        self.assertIn("ROUTER_MUST_NOT_BILL", out["blockers"])
        self.assert_zero_execution(out)

    def test_user_turn_must_be_confirmed_before_provider(self):
        data = ready_inputs()
        data["persistence_policy"]["user_persistence_confirmed"] = False
        data["persistence_policy"]["provider_before_user_persist"] = True
        out = contract.evaluate_production_postgres_adapter_contract(**data)
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("USER_PERSISTENCE_CONFIRMATION_REQUIRED", out["blockers"])
        self.assertIn("PROVIDER_BEFORE_USER_PERSIST_FORBIDDEN", out["blockers"])
        self.assert_zero_execution(out)

    def test_unknown_assistant_persistence_never_becomes_saved(self):
        data = ready_inputs()
        data["persistence_policy"]["unknown_assistant_persistence_not_success"] = False
        data["persistence_policy"]["claims_saved_when_unknown"] = True
        out = contract.evaluate_production_postgres_adapter_contract(**data)
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("UNKNOWN_ASSISTANT_PERSISTENCE_NOT_SUCCESS", out["blockers"])
        self.assertIn("FALSE_SAVED_CLAIM_FORBIDDEN", out["blockers"])
        self.assert_zero_execution(out)

    def test_unknown_persistence_must_not_trigger_second_paid_call(self):
        data = ready_inputs()
        data["persistence_policy"]["no_provider_recall_after_unknown_persistence"] = False
        data["persistence_policy"]["automatic_second_provider_call_after_unknown"] = True
        out = contract.evaluate_production_postgres_adapter_contract(**data)
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn(
            "NO_AUTO_PROVIDER_RECALL_AFTER_UNKNOWN_PERSISTENCE",
            out["blockers"],
        )
        self.assertIn(
            "AUTOMATIC_DUPLICATE_PROVIDER_CALL_FORBIDDEN",
            out["blockers"],
        )
        self.assert_zero_execution(out)

    def test_model_approval_never_grants_external_action_authority(self):
        data = ready_inputs()
        data["provider_boundary"]["provider_approval_implies_external_action_authority"] = True
        out = contract.evaluate_production_postgres_adapter_contract(**data)
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn(
            "MODEL_APPROVAL_MUST_NOT_GRANT_EXTERNAL_ACTION_AUTHORITY",
            out["blockers"],
        )
        self.assert_zero_execution(out)


if __name__ == "__main__":
    unittest.main()
