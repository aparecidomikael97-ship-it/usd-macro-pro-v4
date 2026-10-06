from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from atlasquant_aion_b2b_terminal_certificate_runtime_reader_offline_v1 import (
    FALSE_FIELDS,
    read_terminal_certificate_offline,
)
from atlasquant_aion_durable_execution_kernel import DurableExecutionStore
from test_atlasquant_aion_b2b_execution_terminal_certificate_durable_store_extension_offline_v1 import (
    NOW,
    DEADLINE,
    build_full_chain,
    prepare_completed,
)


class TerminalCertificateRuntimeReaderOfflineV1Tests(unittest.TestCase):
    def assert_no_authority(self, out):
        for key in FALSE_FIELDS:
            self.assertIs(out[key], False, key)

    def test_verified_projection_is_evidence_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = DurableExecutionStore(Path(tmp) / "execution.sqlite3")
            execution_id = build_full_chain(store)
            out = read_terminal_certificate_offline(
                store=store,
                execution_id=execution_id,
                owner_id="owner-1",
                tenant_id="tenant-1",
                workspace_id="workspace-1",
                observed_at="2026-10-06T13:33:00Z",
                max_age_seconds=120,
            )
            self.assertEqual(out["state"], "VERIFIED")
            self.assertEqual(out["age_seconds"], 60)
            self.assertEqual(out["certificate_digest"], "certificate-digest")
            self.assertTrue(out["verified_is_evidence_not_authority"])
            self.assert_no_authority(out)

    def test_stale_is_explicit_and_never_verified(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = DurableExecutionStore(Path(tmp) / "execution.sqlite3")
            execution_id = build_full_chain(store)
            out = read_terminal_certificate_offline(
                store=store,
                execution_id=execution_id,
                owner_id="owner-1",
                tenant_id="tenant-1",
                workspace_id="workspace-1",
                observed_at="2026-10-06T13:40:00Z",
                max_age_seconds=120,
            )
            self.assertEqual(out["state"], "STALE")
            self.assertEqual(out["error_code"], "CERTIFICATE_EVIDENCE_STALE")
            self.assertGreater(out["age_seconds"], out["max_age_seconds"])
            self.assert_no_authority(out)

    def test_cross_tenant_and_workspace_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = DurableExecutionStore(Path(tmp) / "execution.sqlite3")
            execution_id = build_full_chain(store)
            for tenant_id, workspace_id in (
                ("tenant-other", "workspace-1"),
                ("tenant-1", "workspace-other"),
            ):
                out = read_terminal_certificate_offline(
                    store=store,
                    execution_id=execution_id,
                    owner_id="owner-1",
                    tenant_id=tenant_id,
                    workspace_id=workspace_id,
                    observed_at="2026-10-06T13:33:00Z",
                )
                self.assertEqual(out["state"], "MISMATCH")
                self.assertEqual(out["error_code"], "EXECUTION_SCOPE_MISMATCH")
                self.assert_no_authority(out)

    def test_unscoped_execution_is_unavailable_not_guessed(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = DurableExecutionStore(Path(tmp) / "execution.sqlite3")
            execution_id = prepare_completed(store, "2")
            out = read_terminal_certificate_offline(
                store=store,
                execution_id=execution_id,
                owner_id="owner-1",
                tenant_id="tenant-1",
                workspace_id="workspace-1",
                observed_at="2026-10-06T13:33:00Z",
            )
            self.assertEqual(out["state"], "UNAVAILABLE")
            self.assertEqual(out["error_code"], "EXECUTION_SCOPE_NOT_FOUND")
            self.assert_no_authority(out)

    def test_observed_before_persisted_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = DurableExecutionStore(Path(tmp) / "execution.sqlite3")
            execution_id = build_full_chain(store)
            out = read_terminal_certificate_offline(
                store=store,
                execution_id=execution_id,
                owner_id="owner-1",
                tenant_id="tenant-1",
                workspace_id="workspace-1",
                observed_at="2026-10-06T13:31:00Z",
            )
            self.assertEqual(out["state"], "MISMATCH")
            self.assertEqual(
                out["error_code"],
                "OBSERVED_AT_BEFORE_CERTIFICATE_PERSISTED_AT",
            )
            self.assert_no_authority(out)

    def test_invalid_freshness_policy_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = DurableExecutionStore(Path(tmp) / "execution.sqlite3")
            execution_id = build_full_chain(store)
            for value in (0, -1, True, 86401, "300"):
                out = read_terminal_certificate_offline(
                    store=store,
                    execution_id=execution_id,
                    owner_id="owner-1",
                    tenant_id="tenant-1",
                    workspace_id="workspace-1",
                    observed_at="2026-10-06T13:33:00Z",
                    max_age_seconds=value,
                )
                self.assertEqual(out["state"], "MISMATCH")
                self.assertEqual(out["error_code"], "FRESHNESS_POLICY_INVALID")
                self.assert_no_authority(out)

    def test_non_store_object_is_unavailable(self):
        out = read_terminal_certificate_offline(
            store=object(),
            execution_id="EXE-test",
            owner_id="owner-1",
            tenant_id="tenant-1",
            workspace_id="workspace-1",
            observed_at="2026-10-06T13:33:00Z",
        )
        self.assertEqual(out["state"], "UNAVAILABLE")
        self.assertEqual(out["error_code"], "DURABLE_EXECUTION_STORE_REQUIRED")
        self.assert_no_authority(out)

    def test_read_does_not_mutate_durable_chain(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = DurableExecutionStore(Path(tmp) / "execution.sqlite3")
            execution_id = build_full_chain(store)
            before = (
                store.count(),
                store.get_execution_scope(execution_id),
                store.get_terminal_finalization(execution_id),
                store.get_audit_seal(execution_id),
                store.get_terminal_certificate(execution_id),
            )
            out = read_terminal_certificate_offline(
                store=store,
                execution_id=execution_id,
                owner_id="owner-1",
                tenant_id="tenant-1",
                workspace_id="workspace-1",
                observed_at="2026-10-06T13:33:00Z",
            )
            after = (
                store.count(),
                store.get_execution_scope(execution_id),
                store.get_terminal_finalization(execution_id),
                store.get_audit_seal(execution_id),
                store.get_terminal_certificate(execution_id),
            )
            self.assertEqual(out["state"], "VERIFIED")
            self.assertEqual(before, after)
            self.assert_no_authority(out)


if __name__ == "__main__":
    unittest.main()
