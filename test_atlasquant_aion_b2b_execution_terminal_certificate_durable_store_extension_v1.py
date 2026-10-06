from __future__ import annotations

import unittest

import atlasquant_aion_b2b_execution_terminal_certificate_durable_store_extension_v1 as extension
import atlasquant_aion_b2b_execution_terminal_certificate_runtime_reader_store_adapter_v1 as adapter
from test_atlasquant_aion_b2b_execution_terminal_certificate_runtime_reader_store_adapter_v1 import (
    approved_runtime_reader_review,
)


def approved_store_adapter_review():
    return adapter.build_execution_terminal_certificate_runtime_reader_store_adapter_contract(
        runtime_reader_review=approved_runtime_reader_review(),
    )


class ExecutionTerminalCertificateDurableStoreExtensionV1Tests(unittest.TestCase):
    def assert_no_authority(self, out):
        for key in extension.FALSE_FIELDS:
            self.assertIs(out[key], False, key)

    def test_approved_adapter_unlocks_extension_design(self):
        out = extension.build_execution_terminal_certificate_durable_store_extension_contract(
            store_adapter_review=approved_store_adapter_review(),
        )
        self.assertEqual(out["state"], extension.READY)
        self.assertTrue(
            out["execution_terminal_certificate_durable_store_extension_design_only"]
        )
        self.assertEqual(
            out["extension_mode"],
            "ADDITIVE_SAME_DB_TERMINAL_EVIDENCE_EXTENSION",
        )
        self.assertTrue(out["same_database_required"])
        self.assertTrue(out["additive_migration_required"])
        self.assertTrue(out["core_executions_table_preserved"])
        self.assertTrue(out["no_sidecar_database"])
        self.assertTrue(out["no_second_terminal_truth"])
        self.assertTrue(out["implementation_offline_only_pending"])
        self.assertFalse(out["extension_creates_execution_authority"])
        self.assertEqual(
            out["next_allowed_step"],
            "IMPLEMENT_EXECUTION_TERMINAL_CERTIFICATE_DURABLE_STORE_EXTENSION_OFFLINE_ONLY",
        )
        self.assert_no_authority(out)

    def test_upstream_must_be_exact_ready_state(self):
        row = approved_store_adapter_review()
        row["state"] = "BLOCKED"
        out = extension.build_execution_terminal_certificate_durable_store_extension_contract(
            store_adapter_review=row,
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn(
            "RUNTIME_READER_STORE_ADAPTER_DESIGN_REVIEW_REQUIRED",
            out["blockers"],
        )
        self.assert_no_authority(out)

    def test_upstream_side_effect_flip_blocks(self):
        row = approved_store_adapter_review()
        row["store_opened"] = True
        out = extension.build_execution_terminal_certificate_durable_store_extension_contract(
            store_adapter_review=row,
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("STORE_ADAPTER_UNSAFE_FIELD:store_opened", out["blockers"])
        self.assert_no_authority(out)

    def test_extension_is_same_db_and_additive_only(self):
        out = extension.build_execution_terminal_certificate_durable_store_extension_contract(
            store_adapter_review=approved_store_adapter_review(),
        )
        invariants = set(out["required_extension_invariants"])
        self.assertTrue({
            "SAME_DATABASE_AS_CORE_EXECUTION_STORE",
            "CORE_EXECUTIONS_TABLE_REMAINS_SOURCE_OF_EXECUTION_IDENTITY",
            "ADDITIVE_MIGRATION_ONLY",
            "NO_DESTRUCTIVE_EXECUTIONS_TABLE_REBUILD",
            "NO_SIDECAR_DATABASE",
            "NO_SECOND_TERMINAL_TRUTH",
            "FOREIGN_KEY_TO_EXECUTIONS_REQUIRED",
        }.issubset(invariants))
        self.assert_no_authority(out)

    def test_scope_binding_is_explicit_immutable_and_never_guessed(self):
        out = extension.build_execution_terminal_certificate_durable_store_extension_contract(
            store_adapter_review=approved_store_adapter_review(),
        )
        fields = set(out["execution_scope_binding_fields"])
        self.assertTrue({
            "execution_id",
            "owner_id",
            "tenant_id",
            "workspace_id",
            "scope_digest",
            "scope_binding_source_digest",
            "bound_at",
        }.issubset(fields))
        invariants = set(out["required_extension_invariants"])
        self.assertTrue({
            "EXECUTION_SCOPE_BINDING_ONE_TO_ONE",
            "EXECUTION_SCOPE_BINDING_IMMUTABLE",
            "SCOPE_BACKFILL_BY_GUESS_FORBIDDEN",
            "LEGACY_UNSCOPED_EXECUTION_MUST_FAIL_CLOSED",
        }.issubset(invariants))
        self.assertTrue(out["legacy_unscoped_execution_fails_closed"])
        self.assertTrue(out["scope_backfill_by_guess_forbidden"])
        self.assert_no_authority(out)

    def test_terminal_chain_tables_and_order_are_explicit(self):
        out = extension.build_execution_terminal_certificate_durable_store_extension_contract(
            store_adapter_review=approved_store_adapter_review(),
        )
        self.assertEqual(
            tuple(out["required_additive_tables"]),
            (
                "execution_scope_bindings",
                "execution_terminal_finalizations",
                "execution_audit_seals",
                "execution_terminal_certificates",
            ),
        )
        invariants = set(out["required_extension_invariants"])
        self.assertTrue({
            "FINALIZATION_RECORD_APPEND_ONLY",
            "FINALIZATION_RECORD_IMMUTABLE",
            "AUDIT_SEAL_RECORD_APPEND_ONLY",
            "AUDIT_SEAL_RECORD_IMMUTABLE",
            "TERMINAL_CERTIFICATE_RECORD_APPEND_ONLY",
            "TERMINAL_CERTIFICATE_RECORD_IMMUTABLE",
            "FINALIZATION_MUST_PRECEDE_AUDIT_SEAL",
            "AUDIT_SEAL_MUST_PRECEDE_CERTIFICATE",
            "ONE_TERMINAL_FINALIZATION_PER_EXECUTION",
            "ONE_AUDIT_SEAL_PER_FINALIZATION",
            "ONE_TERMINAL_CERTIFICATE_PER_FINALIZATION",
        }.issubset(invariants))
        self.assert_no_authority(out)

    def test_terminal_revision_is_durable_not_timestamp_inference(self):
        out = extension.build_execution_terminal_certificate_durable_store_extension_contract(
            store_adapter_review=approved_store_adapter_review(),
        )
        self.assertTrue(out["durable_terminal_revision_required"])
        self.assertTrue(out["timestamp_as_revision_forbidden"])
        invariants = set(out["required_extension_invariants"])
        self.assertIn("DURABLE_TERMINAL_REVISION_REQUIRED", invariants)
        self.assertIn("TIMESTAMP_AS_TERMINAL_REVISION_FORBIDDEN", invariants)
        self.assert_no_authority(out)

    def test_certificate_record_binds_scope_and_evidence_chain(self):
        out = extension.build_execution_terminal_certificate_durable_store_extension_contract(
            store_adapter_review=approved_store_adapter_review(),
        )
        fields = set(out["terminal_certificate_fields"])
        self.assertTrue({
            "execution_id",
            "terminal_revision",
            "final_execution_state",
            "scope_digest",
            "finalization_record_digest",
            "audit_seal_manifest_digest",
            "audit_seal_record_digest",
            "certificate_manifest_digest",
            "certificate_digest",
            "certificate_persistence_record_digest",
            "terminal_evidence_set_digest",
            "finops_observation_digest",
            "observability_trace_id",
            "pre_terminal_audit_chain_digest",
            "digest_algorithm",
            "canonical_encoding",
            "persisted_at",
        }.issubset(fields))
        invariants = set(out["required_extension_invariants"])
        self.assertTrue({
            "CERTIFICATE_MUST_BIND_SCOPE_DIGEST",
            "CERTIFICATE_MUST_BIND_FINALIZATION_DIGEST",
            "CERTIFICATE_MUST_BIND_AUDIT_SEAL_DIGEST",
            "CERTIFICATE_MUST_BIND_FINOPS_OBSERVATION_DIGEST",
            "CERTIFICATE_MUST_BIND_OBSERVABILITY_TRACE",
        }.issubset(invariants))
        self.assert_no_authority(out)

    def test_future_store_api_is_typed_and_readable(self):
        out = extension.build_execution_terminal_certificate_durable_store_extension_contract(
            store_adapter_review=approved_store_adapter_review(),
        )
        apis = set(out["required_future_store_apis"])
        self.assertTrue({
            "bind_execution_scope_once",
            "get_execution_scope",
            "persist_terminal_finalization_once",
            "get_terminal_finalization",
            "persist_audit_seal_once",
            "get_audit_seal",
            "persist_terminal_certificate_once",
            "get_terminal_certificate",
            "read_terminal_certificate_snapshot",
        }.issubset(apis))
        self.assert_no_authority(out)

    def test_migration_gates_protect_existing_store(self):
        out = extension.build_execution_terminal_certificate_durable_store_extension_contract(
            store_adapter_review=approved_store_adapter_review(),
        )
        gates = set(out["migration_gates"])
        self.assertTrue({
            "SCHEMA_VERSION_BUMP_REQUIRED",
            "EXISTING_EXECUTION_ROWS_PRESERVED",
            "FOREIGN_KEYS_ENABLED",
            "WAL_AND_SYNCHRONOUS_FULL_PRESERVED",
            "MIGRATION_TRANSACTION_REQUIRED",
            "MIGRATION_REOPEN_TEST_REQUIRED",
            "MIGRATION_CRASH_BEFORE_COMMIT_TEST_REQUIRED",
            "MIGRATION_CRASH_AFTER_COMMIT_TEST_REQUIRED",
            "LEGACY_UNSCOPED_READ_RETURNS_FAIL_CLOSED",
            "NO_AUTOMATIC_LEGACY_SCOPE_GUESS",
            "BACKUP_ROLLBACK_PLAN_REQUIRED_BEFORE_NON_TEST_MIGRATION",
        }.issubset(gates))
        self.assert_no_authority(out)

    def test_design_layer_executes_no_migration_or_effect(self):
        out = extension.build_execution_terminal_certificate_durable_store_extension_contract(
            store_adapter_review=approved_store_adapter_review(),
        )
        self.assertFalse(out["migration_executed"])
        self.assertFalse(out["schema_changed"])
        self.assertFalse(out["store_opened"])
        self.assertFalse(out["database_opened"])
        self.assertFalse(out["transaction_started"])
        self.assertFalse(out["table_created"])
        self.assertFalse(out["row_written"])
        self.assertFalse(out["network_called"])
        self.assertFalse(out["provider_called"])
        self.assertFalse(out["external_action_executed"])
        self.assertFalse(out["billing_executed"])
        self.assertFalse(out["crm_write_authorized"])
        self.assertFalse(out["deploy_authorized"])
        self.assertFalse(out["production_mutation_performed"])
        self.assertFalse(out["execution_allowed"])
        self.assertFalse(out["executes_action"])
        self.assert_no_authority(out)


if __name__ == "__main__":
    unittest.main()
