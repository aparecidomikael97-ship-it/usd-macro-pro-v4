from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from atlasquant_aion_durable_execution_kernel import (
    DurableExecutionError,
    DurableExecutionStore,
    STORE_SCHEMA_VERSION,
)


NOW = "2026-10-06T13:30:00Z"
DONE = "2026-10-06T13:31:00Z"
DEADLINE = "2026-10-06T15:00:00Z"
PERSISTED = "2026-10-06T13:32:00Z"


def prepare_completed(store: DurableExecutionStore, suffix: str = "1") -> str:
    prepared = store.prepare(
        task_id=f"TASK-{suffix}",
        step_id=f"STEP-{suffix}",
        idempotency_key=f"idem-{suffix}",
        effect_key=f"effect-{suffix}",
        payload_digest=("a" * 63) + suffix[-1],
        mode="LOCAL_SAFE",
        now_ts=NOW,
        deadline_at=DEADLINE,
        max_attempts=3,
        poison_threshold=3,
    )
    execution_id = prepared.record["execution_id"]
    store.acquire_lease(
        execution_id,
        owner="offline-test",
        now_ts=NOW,
        lease_token=f"lease-{suffix}",
    )
    store.complete(
        execution_id,
        lease_token=f"lease-{suffix}",
        result_digest=f"result-{suffix}",
        now_ts=DONE,
    )
    return execution_id


def bind_scope(store: DurableExecutionStore, execution_id: str):
    return store.bind_execution_scope_once(
        execution_id,
        owner_id="owner-1",
        tenant_id="tenant-1",
        workspace_id="workspace-1",
        scope_digest="scope-digest-1",
        scope_binding_source_digest="scope-source-digest-1",
        bound_at=PERSISTED,
    )


def persist_finalization(store: DurableExecutionStore, execution_id: str):
    return store.persist_terminal_finalization_once(
        execution_id,
        terminal_revision=1,
        final_execution_state="FINALIZED_SUCCESS",
        execution_finalization_contract_digest="finalization-contract-digest",
        finalization_record_digest="finalization-record-digest",
        external_effect_outcome_receipt_digest="outcome-receipt-digest",
        outcome_reconciliation_record_digest="",
        rollback_or_compensation_settlement_digest="",
        finops_estimate_digest="finops-estimate-digest",
        finops_observation_digest="finops-observation-digest",
        observability_trace_id="trace-1",
        pre_terminal_audit_chain_digest="pre-terminal-audit-digest",
        persisted_at=PERSISTED,
    )


def persist_seal(store: DurableExecutionStore, execution_id: str):
    return store.persist_audit_seal_once(
        execution_id,
        terminal_revision=1,
        finalization_record_digest="finalization-record-digest",
        audit_seal_manifest_digest="audit-seal-manifest-digest",
        audit_seal_record_digest="audit-seal-record-digest",
        audit_chain_digest="audit-chain-digest",
        finops_observation_digest="finops-observation-digest",
        observability_trace_id="trace-1",
        persisted_at=PERSISTED,
    )


def persist_certificate(store: DurableExecutionStore, execution_id: str):
    return store.persist_terminal_certificate_once(
        execution_id,
        terminal_revision=1,
        final_execution_state="FINALIZED_SUCCESS",
        scope_digest="scope-digest-1",
        finalization_record_digest="finalization-record-digest",
        audit_seal_manifest_digest="audit-seal-manifest-digest",
        audit_seal_record_digest="audit-seal-record-digest",
        certificate_manifest_digest="certificate-manifest-digest",
        certificate_digest="certificate-digest",
        certificate_persistence_record_digest="certificate-persistence-digest",
        terminal_evidence_set_digest="terminal-evidence-set-digest",
        finops_observation_digest="finops-observation-digest",
        observability_trace_id="trace-1",
        pre_terminal_audit_chain_digest="pre-terminal-audit-digest",
        persisted_at=PERSISTED,
    )


def build_full_chain(store: DurableExecutionStore, suffix: str = "1") -> str:
    execution_id = prepare_completed(store, suffix)
    bind_scope(store, execution_id)
    persist_finalization(store, execution_id)
    persist_seal(store, execution_id)
    persist_certificate(store, execution_id)
    return execution_id


def create_legacy_v1_database(path: Path) -> str:
    execution_id = "EXE-LEGACY000000000000000001"
    conn = sqlite3.connect(str(path))
    try:
        conn.execute(
            """
            CREATE TABLE executions (
                execution_id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                step_id TEXT NOT NULL,
                idempotency_key TEXT NOT NULL UNIQUE,
                effect_key TEXT NOT NULL UNIQUE,
                payload_digest TEXT NOT NULL,
                mode TEXT NOT NULL,
                state TEXT NOT NULL,
                attempt INTEGER NOT NULL,
                max_attempts INTEGER NOT NULL,
                poison_threshold INTEGER NOT NULL,
                same_error_count INTEGER NOT NULL,
                last_error_fingerprint TEXT NOT NULL,
                next_attempt_at TEXT NOT NULL,
                deadline_at TEXT NOT NULL,
                lease_owner TEXT NOT NULL,
                lease_token TEXT NOT NULL,
                lease_expires_at TEXT NOT NULL,
                dispatch_recorded_at TEXT NOT NULL,
                completed_at TEXT NOT NULL,
                result_digest TEXT NOT NULL,
                reconciliation_evidence_digest TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            INSERT INTO executions (
                execution_id, task_id, step_id, idempotency_key, effect_key,
                payload_digest, mode, state, attempt, max_attempts,
                poison_threshold, same_error_count, last_error_fingerprint,
                next_attempt_at, deadline_at, lease_owner, lease_token,
                lease_expires_at, dispatch_recorded_at, completed_at,
                result_digest, reconciliation_evidence_digest, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                execution_id,
                "LEGACY-TASK",
                "LEGACY-STEP",
                "legacy-idem",
                "legacy-effect",
                "a" * 64,
                "LOCAL_SAFE",
                "COMPLETED",
                1,
                3,
                3,
                0,
                "",
                "",
                DEADLINE,
                "",
                "",
                "",
                "",
                DONE,
                "legacy-result",
                "",
                NOW,
                DONE,
            ),
        )
        conn.commit()
    finally:
        conn.close()
    return execution_id


class DurableStoreExtensionOfflineV1Tests(unittest.TestCase):
    def test_fresh_store_migrates_to_schema_v2_with_additive_tables(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "execution.sqlite3"
            store = DurableExecutionStore(path)
            self.assertEqual(store.store_schema_version(), STORE_SCHEMA_VERSION)
            with sqlite3.connect(str(path)) as conn:
                tables = {
                    row[0]
                    for row in conn.execute(
                        "SELECT name FROM sqlite_master WHERE type='table'"
                    ).fetchall()
                }
            self.assertTrue({
                "executions",
                "execution_store_meta",
                "execution_scope_bindings",
                "execution_terminal_finalizations",
                "execution_audit_seals",
                "execution_terminal_certificates",
            }.issubset(tables))

    def test_legacy_v1_database_is_preserved_and_unscoped_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "legacy.sqlite3"
            execution_id = create_legacy_v1_database(path)
            store = DurableExecutionStore(path)
            self.assertEqual(store.store_schema_version(), STORE_SCHEMA_VERSION)
            self.assertEqual(store.count(), 1)
            self.assertEqual(store.get(execution_id)["state"], "COMPLETED")
            snapshot = store.read_terminal_certificate_snapshot(
                execution_id,
                owner_id="owner-unknown",
                tenant_id="tenant-unknown",
                workspace_id="workspace-unknown",
            )
            self.assertEqual(snapshot["state"], "UNAVAILABLE")
            self.assertEqual(snapshot["error_code"], "EXECUTION_SCOPE_NOT_FOUND")
            self.assertFalse(snapshot["executes_action"])

    def test_scope_binding_is_one_time_idempotent_and_conflict_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = DurableExecutionStore(Path(tmp) / "execution.sqlite3")
            execution_id = prepare_completed(store)
            first = bind_scope(store, execution_id)
            replay = bind_scope(store, execution_id)
            self.assertFalse(first["replay"])
            self.assertTrue(replay["replay"])
            with self.assertRaises(DurableExecutionError) as ctx:
                store.bind_execution_scope_once(
                    execution_id,
                    owner_id="owner-1",
                    tenant_id="tenant-2",
                    workspace_id="workspace-1",
                    scope_digest="different-scope",
                    scope_binding_source_digest="scope-source-digest-1",
                    bound_at=PERSISTED,
                )
            self.assertEqual(ctx.exception.result["error_code"], "EXECUTION_SCOPE_CONFLICT")

    def test_finalization_requires_terminal_execution_and_bound_scope(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = DurableExecutionStore(Path(tmp) / "execution.sqlite3")
            prepared = store.prepare(
                task_id="TASK-open",
                step_id="STEP-open",
                idempotency_key="idem-open",
                effect_key="effect-open",
                payload_digest="b" * 64,
                mode="LOCAL_SAFE",
                now_ts=NOW,
                deadline_at=DEADLINE,
            )
            execution_id = prepared.record["execution_id"]
            bind_scope(store, execution_id)
            with self.assertRaises(DurableExecutionError) as ctx:
                persist_finalization(store, execution_id)
            self.assertEqual(ctx.exception.result["error_code"], "EXECUTION_NOT_TERMINAL")

    def test_terminal_chain_is_append_only_and_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = DurableExecutionStore(Path(tmp) / "execution.sqlite3")
            execution_id = prepare_completed(store)
            bind_scope(store, execution_id)
            first_final = persist_finalization(store, execution_id)
            replay_final = persist_finalization(store, execution_id)
            self.assertFalse(first_final["replay"])
            self.assertTrue(replay_final["replay"])
            first_seal = persist_seal(store, execution_id)
            replay_seal = persist_seal(store, execution_id)
            self.assertFalse(first_seal["replay"])
            self.assertTrue(replay_seal["replay"])
            first_cert = persist_certificate(store, execution_id)
            replay_cert = persist_certificate(store, execution_id)
            self.assertFalse(first_cert["replay"])
            self.assertTrue(replay_cert["replay"])
            self.assertFalse(first_cert["executes_action"])

    def test_divergent_certificate_replay_is_conflict(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = DurableExecutionStore(Path(tmp) / "execution.sqlite3")
            execution_id = build_full_chain(store)
            with self.assertRaises(DurableExecutionError) as ctx:
                store.persist_terminal_certificate_once(
                    execution_id,
                    terminal_revision=1,
                    final_execution_state="FINALIZED_SUCCESS",
                    scope_digest="scope-digest-1",
                    finalization_record_digest="finalization-record-digest",
                    audit_seal_manifest_digest="audit-seal-manifest-digest",
                    audit_seal_record_digest="audit-seal-record-digest",
                    certificate_manifest_digest="certificate-manifest-digest",
                    certificate_digest="DIFFERENT-CERTIFICATE-DIGEST",
                    certificate_persistence_record_digest="certificate-persistence-digest",
                    terminal_evidence_set_digest="terminal-evidence-set-digest",
                    finops_observation_digest="finops-observation-digest",
                    observability_trace_id="trace-1",
                    pre_terminal_audit_chain_digest="pre-terminal-audit-digest",
                    persisted_at=PERSISTED,
                )
            self.assertEqual(
                ctx.exception.result["error_code"],
                "TERMINAL_CERTIFICATE_CONFLICT",
            )

    def test_verified_snapshot_survives_reopen(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "execution.sqlite3"
            store = DurableExecutionStore(path)
            execution_id = build_full_chain(store)
            first = store.read_terminal_certificate_snapshot(
                execution_id,
                owner_id="owner-1",
                tenant_id="tenant-1",
                workspace_id="workspace-1",
            )
            self.assertEqual(first["state"], "VERIFIED")
            self.assertFalse(first["executes_action"])
            reopened = DurableExecutionStore(path)
            second = reopened.read_terminal_certificate_snapshot(
                execution_id,
                owner_id="owner-1",
                tenant_id="tenant-1",
                workspace_id="workspace-1",
            )
            self.assertEqual(second["state"], "VERIFIED")
            self.assertEqual(
                second["certificate"]["certificate_digest"],
                "certificate-digest",
            )
            self.assertEqual(reopened.count(), 1)

    def test_cross_tenant_or_workspace_snapshot_is_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = DurableExecutionStore(Path(tmp) / "execution.sqlite3")
            execution_id = build_full_chain(store)
            cross_tenant = store.read_terminal_certificate_snapshot(
                execution_id,
                owner_id="owner-1",
                tenant_id="tenant-OTHER",
                workspace_id="workspace-1",
            )
            cross_workspace = store.read_terminal_certificate_snapshot(
                execution_id,
                owner_id="owner-1",
                tenant_id="tenant-1",
                workspace_id="workspace-OTHER",
            )
            self.assertEqual(cross_tenant["state"], "MISMATCH")
            self.assertEqual(cross_workspace["state"], "MISMATCH")
            self.assertEqual(
                cross_tenant["error_code"],
                "EXECUTION_SCOPE_MISMATCH",
            )

    def test_certificate_cannot_skip_finalization_or_seal(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = DurableExecutionStore(Path(tmp) / "execution.sqlite3")
            execution_id = prepare_completed(store)
            bind_scope(store, execution_id)
            with self.assertRaises(DurableExecutionError) as no_final:
                persist_certificate(store, execution_id)
            self.assertEqual(
                no_final.exception.result["error_code"],
                "TERMINAL_FINALIZATION_NOT_FOUND",
            )
            persist_finalization(store, execution_id)
            with self.assertRaises(DurableExecutionError) as no_seal:
                persist_certificate(store, execution_id)
            self.assertEqual(
                no_seal.exception.result["error_code"],
                "AUDIT_SEAL_NOT_FOUND",
            )

    def test_existing_execution_kernel_contract_stays_non_executable(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = DurableExecutionStore(Path(tmp) / "execution.sqlite3")
            execution_id = build_full_chain(store)
            self.assertFalse(store.get(execution_id)["executes_action"])
            self.assertFalse(store.get_execution_scope(execution_id)["executes_action"])
            self.assertFalse(store.get_terminal_finalization(execution_id)["executes_action"])
            self.assertFalse(store.get_audit_seal(execution_id)["executes_action"])
            self.assertFalse(store.get_terminal_certificate(execution_id)["executes_action"])


if __name__ == "__main__":
    unittest.main()
