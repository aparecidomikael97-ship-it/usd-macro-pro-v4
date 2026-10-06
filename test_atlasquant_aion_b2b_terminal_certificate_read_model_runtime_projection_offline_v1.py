from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from atlasquant_aion_b2b_terminal_certificate_read_model_runtime_projection_offline_v1 import (
    FALSE_FIELDS,
    project_terminal_certificate_read_model_offline,
)
from atlasquant_aion_b2b_terminal_certificate_read_model_store_projection_offline_v1 import (
    DurableTerminalCertificateReadModelSource,
)
from atlasquant_aion_b2b_terminal_certificate_runtime_reader_offline_v1 import (
    read_terminal_certificate_offline,
)
from atlasquant_aion_durable_execution_kernel import DurableExecutionStore
from test_atlasquant_aion_b2b_execution_terminal_certificate_durable_store_extension_offline_v1 import (
    build_full_chain,
)


class TerminalCertificateReadModelRuntimeProjectionOfflineV1Tests(unittest.TestCase):
    def make_reader_result(self, *, observed_at="2026-10-06T13:33:00Z", max_age=120):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        store = DurableExecutionStore(Path(tmp.name) / "execution.sqlite3")
        execution_id = build_full_chain(store)
        source = DurableTerminalCertificateReadModelSource(store)
        result = read_terminal_certificate_offline(
            read_model_source=source,
            execution_id=execution_id,
            owner_id="owner-1",
            tenant_id="tenant-1",
            workspace_id="workspace-1",
            observed_at=observed_at,
            max_age_seconds=max_age,
        )
        return result

    def assert_no_authority(self, out):
        for key in FALSE_FIELDS:
            self.assertIs(out[key], False, key)

    def project(self, result):
        return project_terminal_certificate_read_model_offline(
            runtime_reader_result=result,
            owner_id="owner-1",
            tenant_id="tenant-1",
            workspace_id="workspace-1",
        )

    def test_verified_runtime_reader_becomes_formal_read_model_projection(self):
        out = self.project(self.make_reader_result())
        self.assertEqual(out["state"], "VERIFIED")
        self.assertEqual(out["certificate_status"], "VERIFIED")
        self.assertEqual(out["schema_version"], "1")
        self.assertEqual(out["tenant_id"], "tenant-1")
        self.assertEqual(out["workspace_id"], "workspace-1")
        self.assertEqual(out["certificate_digest"], "certificate-digest")
        self.assertEqual(
            out["audit_seal_persistence_record_digest"],
            "audit-seal-record-digest",
        )
        self.assertEqual(out["digest_algorithm"], "SHA256")
        self.assertEqual(out["canonical_encoding"], "UTF8_CANONICAL_JSON")
        self.assertTrue(out["read_model_projection_is_evidence_not_authority"])
        self.assert_no_authority(out)

    def test_stale_remains_stale_and_never_becomes_verified(self):
        out = self.project(
            self.make_reader_result(
                observed_at="2026-10-06T13:40:00Z",
                max_age=120,
            )
        )
        self.assertEqual(out["state"], "STALE")
        self.assertEqual(out["certificate_status"], "STALE")
        self.assertGreater(out["age_seconds"], out["max_age_seconds"])
        self.assert_no_authority(out)

    def test_runtime_reader_mismatch_is_preserved_fail_closed(self):
        result = self.make_reader_result()
        result["state"] = "MISMATCH"
        result["error_code"] = "TEST_MISMATCH"
        out = self.project(result)
        self.assertEqual(out["state"], "MISMATCH")
        self.assertEqual(out["error_code"], "TEST_MISMATCH")
        self.assert_no_authority(out)

    def test_wrong_schema_fails_closed(self):
        result = self.make_reader_result()
        result["schema"] = "WRONG"
        out = self.project(result)
        self.assertEqual(out["state"], "MISMATCH")
        self.assertEqual(out["error_code"], "RUNTIME_READER_SCHEMA_MISMATCH")
        self.assert_no_authority(out)

    def test_cross_tenant_scope_is_rejected(self):
        result = self.make_reader_result()
        out = project_terminal_certificate_read_model_offline(
            runtime_reader_result=result,
            owner_id="owner-1",
            tenant_id="tenant-other",
            workspace_id="workspace-1",
        )
        self.assertEqual(out["state"], "MISMATCH")
        self.assertEqual(out["error_code"], "READ_MODEL_SCOPE_MISMATCH:tenant_id")
        self.assert_no_authority(out)

    def test_missing_verified_digest_fails_closed(self):
        result = self.make_reader_result()
        result["certificate_digest"] = ""
        out = self.project(result)
        self.assertEqual(out["state"], "MISMATCH")
        self.assertEqual(
            out["error_code"],
            "READ_MODEL_EVIDENCE_REQUIRED:certificate_digest",
        )
        self.assert_no_authority(out)

    def test_authority_flag_in_reader_result_is_rejected(self):
        result = self.make_reader_result()
        result["execution_authority_created"] = True
        out = self.project(result)
        self.assertEqual(out["state"], "MISMATCH")
        self.assertTrue(
            out["error_code"].startswith("RUNTIME_READER_UNSAFE_AUTHORITY_FIELD:")
        )
        self.assert_no_authority(out)

    def test_forbidden_sensitive_material_is_rejected(self):
        result = self.make_reader_result()
        result["api_key_value"] = "secret"
        out = self.project(result)
        self.assertEqual(out["state"], "MISMATCH")
        self.assertEqual(
            out["error_code"],
            "FORBIDDEN_READ_MODEL_MATERIAL_PRESENT",
        )
        self.assert_no_authority(out)

    def test_verified_cannot_claim_age_beyond_freshness_window(self):
        result = self.make_reader_result()
        result["age_seconds"] = result["max_age_seconds"] + 1
        out = self.project(result)
        self.assertEqual(out["state"], "MISMATCH")
        self.assertEqual(
            out["error_code"],
            "VERIFIED_CANNOT_EXCEED_FRESHNESS_WINDOW",
        )
        self.assert_no_authority(out)


if __name__ == "__main__":
    unittest.main()
