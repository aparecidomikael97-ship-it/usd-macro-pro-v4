from __future__ import annotations

import unittest

import atlasquant_aion_chat_postgres_migration_health_contract_v1 as contract


def ready_migration():
    return {
        "versioned": True,
        "checksum_required": True,
        "single_writer_lock": True,
        "auto_migrate_on_startup": False,
        "isolated_copy_test_required": True,
        "recovery_point_required": True,
        "additive_first": True,
        "destructive_changes_v1_forbidden": True,
        "schema_version_compatibility": True,
        "roll_forward_plan": True,
        "real_migration_requires_owner_authorization": True,
        "production_migration_implicit_authority": False,
    }


def ready_health():
    return {
        "database_health_required": True,
        "schema_compatibility_required": True,
        "scope_policy_health_required": True,
        "fail_closed_on_db_unavailable": True,
        "session_only_fallback_forbidden": True,
        "staging_sqlite_fallback_forbidden": True,
        "persist_user_turn_before_provider": True,
        "assistant_persistence_must_be_confirmed": True,
        "unknown_persistence_never_success": True,
        "idempotent_retry_required": True,
        "degraded_state_visible": True,
        "claims_saved_when_unconfirmed": False,
        "provider_call_before_user_persist": False,
    }


class MigrationHealthContractV1Tests(unittest.TestCase):
    def assert_zero_execution(self, out):
        for key in contract.FALSE_FIELDS:
            self.assertIs(out[key], False, key)

    def test_complete_design_unlocks_review_only(self):
        out = contract.evaluate_migration_health_contract(
            ready_migration(), ready_health()
        )
        self.assertEqual(out["state"], contract.READY)
        self.assertTrue(out["design_only"])
        self.assertTrue(out["production_migration_is_protected_action"])
        self.assertTrue(out["durability_truthful"])
        self.assert_zero_execution(out)

    def test_auto_migration_on_prod_startup_is_forbidden(self):
        m = ready_migration()
        m["auto_migrate_on_startup"] = True
        out = contract.evaluate_migration_health_contract(m, ready_health())
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("NO_AUTO_PROD_MIGRATION_ON_STARTUP", out["blockers"])
        self.assert_zero_execution(out)

    def test_destructive_v1_change_is_forbidden(self):
        m = ready_migration()
        m["destructive_changes_v1_forbidden"] = False
        out = contract.evaluate_migration_health_contract(m, ready_health())
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("DESTRUCTIVE_V1_FORBIDDEN", out["blockers"])
        self.assert_zero_execution(out)

    def test_db_unavailable_must_fail_closed(self):
        h = ready_health()
        h["fail_closed_on_db_unavailable"] = False
        out = contract.evaluate_migration_health_contract(ready_migration(), h)
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("FAIL_CLOSED_ON_DB_UNAVAILABLE_REQUIRED", out["blockers"])
        self.assert_zero_execution(out)

    def test_session_only_fallback_cannot_impersonate_durability(self):
        h = ready_health()
        h["session_only_fallback_forbidden"] = False
        h["claims_saved_when_unconfirmed"] = True
        out = contract.evaluate_migration_health_contract(ready_migration(), h)
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("NO_SESSION_ONLY_DURABLE_FALLBACK", out["blockers"])
        self.assertIn("FALSE_DURABILITY_CLAIM_FORBIDDEN", out["blockers"])
        self.assert_zero_execution(out)

    def test_staging_sqlite_is_not_prod_fallback(self):
        h = ready_health()
        h["staging_sqlite_fallback_forbidden"] = False
        out = contract.evaluate_migration_health_contract(ready_migration(), h)
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("NO_STAGING_SQLITE_PROD_FALLBACK", out["blockers"])
        self.assert_zero_execution(out)

    def test_user_turn_must_persist_before_paid_provider_call(self):
        h = ready_health()
        h["persist_user_turn_before_provider"] = False
        h["provider_call_before_user_persist"] = True
        out = contract.evaluate_migration_health_contract(ready_migration(), h)
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("USER_TURN_DURABLE_BEFORE_PROVIDER_REQUIRED", out["blockers"])
        self.assertIn("PROVIDER_CALL_BEFORE_USER_PERSIST_FORBIDDEN", out["blockers"])
        self.assert_zero_execution(out)

    def test_unknown_assistant_persistence_never_becomes_success(self):
        h = ready_health()
        h["unknown_persistence_never_success"] = False
        h["assistant_persistence_must_be_confirmed"] = False
        out = contract.evaluate_migration_health_contract(ready_migration(), h)
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("UNKNOWN_PERSISTENCE_NEVER_SUCCESS", out["blockers"])
        self.assertIn("ASSISTANT_DURABILITY_EXPLICIT_REQUIRED", out["blockers"])
        self.assert_zero_execution(out)


if __name__ == "__main__":
    unittest.main()
