from __future__ import annotations

import unittest

import atlasquant_aion_chat_postgres_store_adapter_contract_v1 as contract


def ready_inputs():
    return {
        "interface": {
            "methods": list(contract.REQUIRED_METHODS),
            "aion_chat_store_compatible": True,
            "reuse_existing_models": True,
            "storage_unavailable_error_contract": True,
            "provider_dependency_absent": True,
            "store_calls_provider": False,
        },
        "scope_policy": {
            "trusted_scope_required": True,
            "scope_on_every_query": True,
            "cross_scope_default_deny": True,
            "rls_defense_in_depth": True,
            "application_scope_checks": True,
            "no_unscoped_admin_bypass": True,
            "global_lookup_without_scope": False,
        },
        "transaction_policy": {
            "append_message_atomic": True,
            "sequence_lock_required": True,
            "idempotency_required": True,
            "duplicate_append_safe": True,
            "conversation_count_atomic": True,
            "checkpoint_monotonic": True,
            "no_auto_retry_unknown_commit": True,
            "blind_retry_after_unknown_commit": False,
        },
        "health_policy": {
            "pre_operation_health_required": True,
            "schema_version_health": True,
            "scope_policy_health": True,
            "fail_closed": True,
            "unknown_commit_explicit": True,
        },
    }


class PostgresStoreAdapterContractV1Tests(unittest.TestCase):
    def assert_zero_execution(self, out):
        for key in contract.FALSE_FIELDS:
            self.assertIs(out[key], False, key)

    def test_complete_contract_unlocks_implementation_only(self):
        out = contract.evaluate_postgres_store_adapter_contract(**ready_inputs())
        self.assertEqual(out["state"], contract.READY)
        self.assertTrue(out["preserves_existing_store_protocol"])
        self.assertEqual(out["unknown_commit_state"], "COMMIT_OUTCOME_UNKNOWN")
        self.assert_zero_execution(out)

    def test_every_existing_store_method_is_required(self):
        data = ready_inputs()
        data["interface"]["methods"].remove("append_message")
        out = contract.evaluate_postgres_store_adapter_contract(**data)
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("STORE_METHOD_MISSING:append_message", out["blockers"])
        self.assert_zero_execution(out)

    def test_scope_is_required_on_every_operation(self):
        data = ready_inputs()
        data["scope_policy"]["scope_on_every_query"] = False
        data["scope_policy"]["global_lookup_without_scope"] = True
        out = contract.evaluate_postgres_store_adapter_contract(**data)
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("SCOPE_ON_EVERY_QUERY_REQUIRED", out["blockers"])
        self.assertIn("GLOBAL_LOOKUP_WITHOUT_SCOPE_FORBIDDEN", out["blockers"])
        self.assert_zero_execution(out)

    def test_rls_never_replaces_app_scope_checks(self):
        data = ready_inputs()
        data["scope_policy"]["application_scope_checks"] = False
        out = contract.evaluate_postgres_store_adapter_contract(**data)
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("APP_SCOPE_CHECKS_REQUIRED", out["blockers"])
        self.assert_zero_execution(out)

    def test_unknown_commit_may_not_be_blindly_retried(self):
        data = ready_inputs()
        data["transaction_policy"]["no_auto_retry_unknown_commit"] = False
        data["transaction_policy"]["blind_retry_after_unknown_commit"] = True
        out = contract.evaluate_postgres_store_adapter_contract(**data)
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("NO_AUTO_RETRY_UNKNOWN_COMMIT_REQUIRED", out["blockers"])
        self.assertIn("BLIND_RETRY_AFTER_UNKNOWN_COMMIT_FORBIDDEN", out["blockers"])
        self.assert_zero_execution(out)

    def test_store_has_no_provider_dependency(self):
        data = ready_inputs()
        data["interface"]["provider_dependency_absent"] = False
        data["interface"]["store_calls_provider"] = True
        out = contract.evaluate_postgres_store_adapter_contract(**data)
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("NO_PROVIDER_DEPENDENCY_REQUIRED", out["blockers"])
        self.assertIn("STORE_PROVIDER_CALL_FORBIDDEN", out["blockers"])
        self.assert_zero_execution(out)

    def test_append_sequence_and_count_are_atomic(self):
        data = ready_inputs()
        data["transaction_policy"]["sequence_lock_required"] = False
        data["transaction_policy"]["conversation_count_atomic"] = False
        out = contract.evaluate_postgres_store_adapter_contract(**data)
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("MESSAGE_SEQUENCE_LOCK_REQUIRED", out["blockers"])
        self.assertIn("CONVERSATION_COUNT_UPDATE_ATOMIC_REQUIRED", out["blockers"])
        self.assert_zero_execution(out)


if __name__ == "__main__":
    unittest.main()
