from __future__ import annotations

import unittest

import atlasquant_aion_b2b_execution_terminal_certificate_runtime_reader_store_adapter_v1 as adapter
import atlasquant_aion_b2b_execution_terminal_certificate_runtime_reader_v1 as reader
from test_atlasquant_aion_b2b_execution_terminal_certificate_runtime_reader_v1 import (
    approved_ui_review,
)


def approved_runtime_reader_review():
    return reader.build_execution_terminal_certificate_runtime_reader_contract(
        terminal_certificate_read_model_ui_review=approved_ui_review(),
    )


class ExecutionTerminalCertificateRuntimeReaderStoreAdapterV1Tests(unittest.TestCase):
    def assert_no_authority(self, out):
        for key in adapter.FALSE_FIELDS:
            self.assertIs(out[key], False, key)

    def test_approved_runtime_reader_unlocks_store_adapter_design(self):
        out = adapter.build_execution_terminal_certificate_runtime_reader_store_adapter_contract(
            runtime_reader_review=approved_runtime_reader_review(),
        )
        self.assertEqual(out["state"], adapter.READY)
        self.assertTrue(
            out["execution_terminal_certificate_runtime_reader_store_adapter_design_only"]
        )
        self.assertEqual(
            out["store_adapter_mode"],
            "READ_ONLY_FAIL_CLOSED_CORE_DURABLE_STORE_ADAPTER",
        )
        self.assertTrue(out["read_only"])
        self.assertTrue(out["observational_only"])
        self.assertTrue(out["reuses_existing_core_durable_store"])
        self.assertTrue(out["second_database_forbidden"])
        self.assertTrue(out["sidecar_terminal_truth_forbidden"])
        self.assertFalse(out["current_core_store_live_binding_ready"])
        self.assertTrue(out["durable_store_extension_required"])
        self.assertFalse(out["store_adapter_creates_execution_authority"])
        self.assertEqual(
            out["next_allowed_step"],
            "DESIGN_EXECUTION_TERMINAL_CERTIFICATE_DURABLE_STORE_EXTENSION_ONLY",
        )
        self.assert_no_authority(out)

    def test_upstream_must_be_exact_ready_state(self):
        row = approved_runtime_reader_review()
        row["state"] = "BLOCKED"
        out = adapter.build_execution_terminal_certificate_runtime_reader_store_adapter_contract(
            runtime_reader_review=row,
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn(
            "TERMINAL_CERTIFICATE_RUNTIME_READER_DESIGN_REVIEW_REQUIRED",
            out["blockers"],
        )
        self.assert_no_authority(out)

    def test_upstream_side_effect_flip_blocks(self):
        row = approved_runtime_reader_review()
        row["network_called"] = True
        out = adapter.build_execution_terminal_certificate_runtime_reader_store_adapter_contract(
            runtime_reader_review=row,
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn(
            "TERMINAL_CERTIFICATE_RUNTIME_READER_UNSAFE_FIELD:network_called",
            out["blockers"],
        )
        self.assert_no_authority(out)

    def test_reader_safety_guards_cannot_be_relaxed(self):
        for field, blocker in (
            ("read_only", "READ_ONLY_RUNTIME_READER_REQUIRED"),
            ("observational_only", "OBSERVATIONAL_ONLY_RUNTIME_READER_REQUIRED"),
            ("persisted_certificate_required", "PERSISTED_CERTIFICATE_REQUIRED"),
            ("tenant_scope_must_match", "TENANT_SCOPE_MATCH_REQUIRED"),
            ("workspace_scope_must_match", "WORKSPACE_SCOPE_MATCH_REQUIRED"),
            ("snapshot_consistency_required", "SNAPSHOT_CONSISTENCY_REQUIRED"),
            ("provider_fallback_forbidden", "PROVIDER_FALLBACK_MUST_BE_FORBIDDEN"),
            ("network_fallback_forbidden", "NETWORK_FALLBACK_MUST_BE_FORBIDDEN"),
            ("mutation_forbidden", "RUNTIME_READER_MUTATION_MUST_BE_FORBIDDEN"),
        ):
            row = approved_runtime_reader_review()
            row[field] = False
            out = adapter.build_execution_terminal_certificate_runtime_reader_store_adapter_contract(
                runtime_reader_review=row,
            )
            self.assertEqual(out["state"], "BLOCKED")
            self.assertIn(blocker, out["blockers"])
            self.assert_no_authority(out)

    def test_current_store_gap_is_explicit_and_fail_closed(self):
        out = adapter.build_execution_terminal_certificate_runtime_reader_store_adapter_contract(
            runtime_reader_review=approved_runtime_reader_review(),
        )
        missing = set(out["missing_required_live_capabilities"])
        self.assertTrue({
            "TERMINAL_CERTIFICATE_RECORD_READ_API",
            "TERMINAL_CERTIFICATE_DIGEST_READ_API",
            "TERMINAL_CERTIFICATE_REVISION_READ_API",
            "TENANT_SCOPE_BINDING",
            "WORKSPACE_SCOPE_BINDING",
            "CERTIFICATE_TO_EXECUTION_FOREIGN_KEY_BINDING",
            "APPEND_ONLY_CERTIFICATE_RECORD_STORAGE",
            "CERTIFICATE_REOPEN_CONSISTENCY_READ",
        }.issubset(missing))
        self.assertFalse(out["current_core_store_live_binding_ready"])
        self.assertTrue(out["missing_store_capabilities_fail_closed"])
        self.assert_no_authority(out)

    def test_adapter_reuses_core_store_without_second_truth(self):
        out = adapter.build_execution_terminal_certificate_runtime_reader_store_adapter_contract(
            runtime_reader_review=approved_runtime_reader_review(),
        )
        self.assertEqual(
            out["core_execution_store"],
            "atlasquant_aion_durable_execution_kernel.DurableExecutionStore",
        )
        self.assertEqual(
            out["core_execution_id"],
            "atlasquant_aion_durable_execution_kernel.canonical_execution_id",
        )
        rules = set(out["required_store_adapter_rules"])
        self.assertTrue({
            "REUSE_EXISTING_CORE_DURABLE_STORE",
            "SECOND_DATABASE_FORBIDDEN",
            "SIDECAR_TERMINAL_TRUTH_FORBIDDEN",
            "CANONICAL_EXECUTION_ID_REQUIRED",
            "EXACT_TENANT_SCOPE_REQUIRED",
            "EXACT_WORKSPACE_SCOPE_REQUIRED",
            "CERTIFICATE_RECORD_MUST_BIND_TO_EXECUTION_RECORD",
            "MISSING_STORE_CAPABILITY_MUST_FAIL_CLOSED",
            "STORE_SCHEMA_MISMATCH_MUST_FAIL_CLOSED",
            "NO_STORE_MUTATION_FROM_READER_ADAPTER",
            "NO_PROVIDER_FALLBACK",
            "NO_NETWORK_FALLBACK",
        }.issubset(rules))
        self.assert_no_authority(out)

    def test_future_store_extension_fields_cover_scope_and_evidence(self):
        out = adapter.build_execution_terminal_certificate_runtime_reader_store_adapter_contract(
            runtime_reader_review=approved_runtime_reader_review(),
        )
        fields = set(out["required_future_store_extension_fields"])
        self.assertTrue({
            "execution_id",
            "tenant_id",
            "workspace_id",
            "terminal_revision",
            "final_execution_state",
            "certificate_manifest_digest",
            "certificate_digest",
            "certificate_persistence_record_digest",
            "finalization_record_digest",
            "audit_seal_manifest_digest",
            "audit_seal_persistence_record_digest",
            "terminal_evidence_set_digest",
            "finops_observation_digest",
            "observability_trace_id",
            "pre_terminal_audit_chain_digest",
            "digest_algorithm",
            "canonical_encoding",
            "persisted_at",
        }.issubset(fields))
        self.assert_no_authority(out)

    def test_forbidden_behaviors_block_mutation_and_external_effects(self):
        out = adapter.build_execution_terminal_certificate_runtime_reader_store_adapter_contract(
            runtime_reader_review=approved_runtime_reader_review(),
        )
        forbidden = set(out["forbidden_store_adapter_behaviors"])
        self.assertTrue({
            "create_sidecar_database",
            "create_second_terminal_truth",
            "write_execution_record",
            "write_certificate_record",
            "delete_certificate_record",
            "replace_certificate_record",
            "reopen_execution",
            "retry_execution",
            "call_provider",
            "open_network_fallback",
            "bill_customer",
            "write_crm",
            "deploy_service",
            "mutate_production",
        }.issubset(forbidden))
        self.assert_no_authority(out)

    def test_design_layer_connects_to_nothing(self):
        out = adapter.build_execution_terminal_certificate_runtime_reader_store_adapter_contract(
            runtime_reader_review=approved_runtime_reader_review(),
        )
        self.assertFalse(out["live_binding_available"])
        self.assertFalse(out["store_adapter_connected"])
        self.assertFalse(out["store_opened"])
        self.assertFalse(out["database_opened"])
        self.assertFalse(out["read_transaction_started"])
        self.assertFalse(out["runtime_read_performed"])
        self.assertFalse(out["certificate_record_loaded"])
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
