from __future__ import annotations

import unittest

import atlasquant_aion_chat_postgres_schema_scope_contract_v1 as contract


def ready_design():
    return {
        "tables": [
            "chat_conversations",
            "chat_messages",
            "chat_attachment_metadata",
            "chat_access_audit",
        ],
        "scope_columns": ["owner_id", "tenant_id", "workspace_id"],
        "scope_columns_not_null": True,
        "composite_scope_index": True,
        "conversation_scope_unique": True,
        "message_scope_bound": True,
        "attachment_scope_bound": True,
        "audit_scope_bound": True,
        "cross_scope_foreign_keys_forbidden": True,
        "cross_tenant_query_default_deny": True,
        "parameterized_queries_only": True,
        "row_level_security_planned": True,
        "force_row_level_security_planned": True,
        "least_privilege_app_role": True,
        "app_role_is_not_superuser": True,
        "audit_excludes_message_content": True,
        "attachments_metadata_only": True,
        "secrets_forbidden_in_chat_tables": True,
        "immutable_message_id": True,
        "ordered_message_sequence": True,
        "idempotency_key_required": True,
        "retention_controlled_delete": True,
        "global_unscoped_conversation_lookup": False,
        "global_unscoped_message_lookup": False,
        "stores_provider_secret": False,
        "stores_db_credentials": False,
    }


class PostgresSchemaScopeContractV1Tests(unittest.TestCase):
    def assert_zero_execution(self, out):
        for key in contract.FALSE_FIELDS:
            self.assertIs(out[key], False, key)

    def test_complete_design_unlocks_review_only(self):
        out = contract.evaluate_postgres_schema_scope_contract(ready_design())
        self.assertEqual(out["state"], contract.READY)
        self.assertTrue(out["design_only"])
        self.assertTrue(out["rls_is_defense_in_depth"])
        self.assertTrue(out["application_scope_checks_still_required"])
        self.assert_zero_execution(out)

    def test_missing_scope_column_is_blocked(self):
        design = ready_design()
        design["scope_columns"] = ["owner_id", "tenant_id"]
        out = contract.evaluate_postgres_schema_scope_contract(design)
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn(
            "REQUIRED_SCOPE_COLUMN_MISSING:workspace_id",
            out["blockers"],
        )
        self.assert_zero_execution(out)

    def test_unscoped_lookup_is_forbidden(self):
        design = ready_design()
        design["global_unscoped_message_lookup"] = True
        out = contract.evaluate_postgres_schema_scope_contract(design)
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn(
            "GLOBAL_UNSCOPED_MESSAGE_LOOKUP_FORBIDDEN",
            out["blockers"],
        )
        self.assert_zero_execution(out)

    def test_rls_does_not_replace_application_scope_checks(self):
        design = ready_design()
        design["cross_tenant_query_default_deny"] = False
        out = contract.evaluate_postgres_schema_scope_contract(design)
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn(
            "CROSS_TENANT_QUERY_DEFAULT_DENY_REQUIRED",
            out["blockers"],
        )
        self.assert_zero_execution(out)

    def test_app_role_cannot_be_superuser(self):
        design = ready_design()
        design["app_role_is_not_superuser"] = False
        out = contract.evaluate_postgres_schema_scope_contract(design)
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("NO_DB_SUPERUSER_FOR_APP_REQUIRED", out["blockers"])
        self.assert_zero_execution(out)

    def test_secrets_are_forbidden_in_chat_tables(self):
        design = ready_design()
        design["stores_provider_secret"] = True
        design["stores_db_credentials"] = True
        out = contract.evaluate_postgres_schema_scope_contract(design)
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("PROVIDER_SECRET_STORAGE_FORBIDDEN", out["blockers"])
        self.assertIn("DB_CREDENTIAL_STORAGE_FORBIDDEN", out["blockers"])
        self.assert_zero_execution(out)

    def test_audit_never_contains_message_content(self):
        design = ready_design()
        design["audit_excludes_message_content"] = False
        out = contract.evaluate_postgres_schema_scope_contract(design)
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn(
            "MESSAGE_CONTENT_EXCLUDED_FROM_AUDIT_REQUIRED",
            out["blockers"],
        )
        self.assert_zero_execution(out)

    def test_attachment_binary_storage_is_outside_chat_metadata_contract(self):
        design = ready_design()
        design["attachments_metadata_only"] = False
        out = contract.evaluate_postgres_schema_scope_contract(design)
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("ATTACHMENT_METADATA_ONLY_REQUIRED", out["blockers"])
        self.assert_zero_execution(out)


if __name__ == "__main__":
    unittest.main()
