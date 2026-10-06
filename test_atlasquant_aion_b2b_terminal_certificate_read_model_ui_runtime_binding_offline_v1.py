from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from atlasquant_aion_b2b_terminal_certificate_read_model_runtime_projection_offline_v1 import (
    project_terminal_certificate_read_model_offline,
)
from atlasquant_aion_b2b_terminal_certificate_read_model_store_projection_offline_v1 import (
    DurableTerminalCertificateReadModelSource,
)
from atlasquant_aion_b2b_terminal_certificate_read_model_ui_runtime_binding_offline_v1 import (
    FALSE_FIELDS,
    REQUIRED_UI_SECTIONS,
    build_terminal_certificate_panel_view_model_offline,
)
from atlasquant_aion_b2b_terminal_certificate_runtime_reader_offline_v1 import (
    read_terminal_certificate_offline,
)
from atlasquant_aion_durable_execution_kernel import DurableExecutionStore
from test_atlasquant_aion_b2b_execution_terminal_certificate_durable_store_extension_offline_v1 import (
    build_full_chain,
)


class TerminalCertificateReadModelUiRuntimeBindingOfflineV1Tests(unittest.TestCase):
    def make_projection(self, *, observed_at="2026-10-06T13:33:00Z", max_age=120):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        store = DurableExecutionStore(Path(tmp.name) / "execution.sqlite3")
        execution_id = build_full_chain(store)
        source = DurableTerminalCertificateReadModelSource(store)
        runtime = read_terminal_certificate_offline(
            read_model_source=source,
            execution_id=execution_id,
            owner_id="owner-1",
            tenant_id="tenant-1",
            workspace_id="workspace-1",
            observed_at=observed_at,
            max_age_seconds=max_age,
        )
        return project_terminal_certificate_read_model_offline(
            runtime_reader_result=runtime,
            owner_id="owner-1",
            tenant_id="tenant-1",
            workspace_id="workspace-1",
        )

    def assert_no_authority(self, out):
        for key in FALSE_FIELDS:
            self.assertIs(out[key], False, key)
        self.assertEqual(out["controls"], ())
        self.assertFalse(out["action_controls_present"])

    def test_verified_projection_builds_all_required_sections(self):
        out = build_terminal_certificate_panel_view_model_offline(
            read_model_projection=self.make_projection(),
        )
        self.assertEqual(out["state"], "VERIFIED")
        self.assertEqual(out["badge"]["tone"], "POSITIVE_EVIDENCE_ONLY")
        self.assertTrue(out["badge"]["evidence_only"])
        self.assertEqual(tuple(out["sections"]), REQUIRED_UI_SECTIONS)
        self.assertEqual(
            out["sections"]["certificate_digest"]["certificate_digest"],
            "certificate-digest",
        )
        self.assertEqual(
            out["sections"]["scope_boundary"]["tenant_id"],
            "tenant-1",
        )
        self.assert_no_authority(out)

    def test_stale_projection_renders_refresh_required_not_verified(self):
        projection = self.make_projection(
            observed_at="2026-10-06T13:40:00Z",
            max_age=120,
        )
        out = build_terminal_certificate_panel_view_model_offline(
            read_model_projection=projection,
        )
        self.assertEqual(out["state"], "STALE")
        self.assertEqual(out["badge"]["tone"], "REFRESH_REQUIRED")
        self.assertNotEqual(out["badge"]["state"], "VERIFIED")
        self.assert_no_authority(out)

    def test_mismatch_projection_stays_fail_closed(self):
        projection = self.make_projection()
        projection["state"] = "MISMATCH"
        projection["certificate_status"] = "MISMATCH"
        projection["error_code"] = "TEST_MISMATCH"
        out = build_terminal_certificate_panel_view_model_offline(
            read_model_projection=projection,
        )
        self.assertEqual(out["state"], "MISMATCH")
        self.assertEqual(out["badge"]["tone"], "FAIL_CLOSED")
        self.assertEqual(out["error_code"], "TEST_MISMATCH")
        self.assert_no_authority(out)

    def test_unknown_state_cannot_render_verified(self):
        projection = self.make_projection()
        projection["state"] = "MAYBE"
        projection["certificate_status"] = "MAYBE"
        out = build_terminal_certificate_panel_view_model_offline(
            read_model_projection=projection,
        )
        self.assertEqual(out["state"], "MISMATCH")
        self.assertEqual(
            out["error_code"],
            "READ_MODEL_RUNTIME_PROJECTION_STATE_UNKNOWN",
        )
        self.assert_no_authority(out)

    def test_certificate_status_must_match_state(self):
        projection = self.make_projection()
        projection["certificate_status"] = "STALE"
        out = build_terminal_certificate_panel_view_model_offline(
            read_model_projection=projection,
        )
        self.assertEqual(out["state"], "MISMATCH")
        self.assertEqual(out["error_code"], "CERTIFICATE_STATUS_STATE_MISMATCH")
        self.assert_no_authority(out)

    def test_missing_verified_evidence_fails_closed(self):
        projection = self.make_projection()
        projection["observability_trace_id"] = ""
        out = build_terminal_certificate_panel_view_model_offline(
            read_model_projection=projection,
        )
        self.assertEqual(out["state"], "MISMATCH")
        self.assertEqual(
            out["error_code"],
            "UI_EVIDENCE_REQUIRED:observability_trace_id",
        )
        self.assert_no_authority(out)

    def test_sensitive_material_is_never_rendered(self):
        projection = self.make_projection()
        projection["authorization_header_value"] = "Bearer secret"
        out = build_terminal_certificate_panel_view_model_offline(
            read_model_projection=projection,
        )
        self.assertEqual(out["state"], "MISMATCH")
        self.assertEqual(out["error_code"], "FORBIDDEN_UI_MATERIAL_PRESENT")
        self.assert_no_authority(out)

    def test_upstream_authority_flip_is_rejected(self):
        projection = self.make_projection()
        projection["retry_authorized"] = True
        out = build_terminal_certificate_panel_view_model_offline(
            read_model_projection=projection,
        )
        self.assertEqual(out["state"], "MISMATCH")
        self.assertTrue(
            out["error_code"].startswith("READ_MODEL_UNSAFE_AUTHORITY_FIELD:")
        )
        self.assert_no_authority(out)

    def test_panel_has_no_action_control_names(self):
        out = build_terminal_certificate_panel_view_model_offline(
            read_model_projection=self.make_projection(),
        )
        flat = repr(out)
        for control in (
            "execute_action_button",
            "retry_button",
            "reopen_execution_button",
            "issue_certificate_button",
            "sign_certificate_button",
            "billing_button",
            "crm_write_button",
            "deploy_button",
            "production_mutation_button",
        ):
            self.assertNotIn(control, flat)
        self.assert_no_authority(out)


if __name__ == "__main__":
    unittest.main()
