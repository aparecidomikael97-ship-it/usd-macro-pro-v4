from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from atlasquant_aion_developer_diagnostics import (
    SCHEMA,
    diagnose_failure,
    record_failure_attempt,
)
from atlasquant_aion_developer_engine import new_development_workflow
from atlasquant_aion_developer_intelligence import scan_repository


class AionDeveloperDiagnosticsTests(unittest.TestCase):
    def _snapshot(self):
        tmp = tempfile.TemporaryDirectory()
        root = Path(tmp.name)
        (root / "atlasquant_aion_admin.py").write_text(
            "def render():\n    return True\n",
            encoding="utf-8",
        )
        (root / "test_atlasquant_aion_admin.py").write_text(
            "import atlasquant_aion_admin\n"
            "def test_render():\n"
            "    assert atlasquant_aion_admin.render()\n",
            encoding="utf-8",
        )
        return tmp, root, scan_repository(root)

    def test_traceback_maps_only_repo_relative_paths(self):
        tmp, root, snapshot = self._snapshot()
        try:
            log = (
                "Traceback (most recent call last):\n"
                f'  File "{root / "atlasquant_aion_admin.py"}", line 42, in render\n'
                "    raise AssertionError\n"
                "AssertionError: expected-state-mismatch\n"
                "FAILED test_atlasquant_aion_admin.py::test_render\n"
            )
            out = diagnose_failure(snapshot, log)
        finally:
            tmp.cleanup()

        self.assertEqual(out["schema"], SCHEMA)
        self.assertEqual(out["state"], "FAILURE_EVIDENCE")
        self.assertEqual(out["exception_type"], "AssertionError")
        self.assertIn("atlasquant_aion_admin.py", out["affected_files"])
        self.assertIn(
            "test_atlasquant_aion_admin.py::test_render",
            out["explicit_tests"],
        )
        self.assertNotIn(str(root), str(out))
        self.assertFalse(out["raw_log_included"])
        self.assertFalse(out["cause_confirmed"])
        self.assertEqual(out["cause_truth_status"], "UNKNOWN")

    def test_external_traceback_path_is_not_exposed(self):
        tmp, root, snapshot = self._snapshot()
        try:
            log = (
                "Traceback (most recent call last):\n"
                '  File "/outside/location/module.py", line 9, in run\n'
                "TypeError: mismatch\n"
            )
            out = diagnose_failure(snapshot, log)
        finally:
            tmp.cleanup()
        self.assertNotIn("/outside/location", str(out))
        self.assertNotIn("module.py", out["affected_files"])
        self.assertEqual(out["exception_type"], "TypeError")

    def test_hypothesis_is_explicitly_unknown(self):
        tmp, root, snapshot = self._snapshot()
        try:
            out = diagnose_failure(
                snapshot,
                "AssertionError: expected 1 got 2\n"
                "FAILED test_atlasquant_aion_admin.py::test_render\n",
            )
        finally:
            tmp.cleanup()
        self.assertTrue(out["hypotheses"])
        self.assertTrue(all(
            item["truth_status"] == "UNKNOWN"
            for item in out["hypotheses"]
        ))
        self.assertFalse(out["cause_confirmed"])

    def test_failure_can_be_recorded_without_claiming_root_cause(self):
        tmp, root, snapshot = self._snapshot()
        try:
            diagnostic = diagnose_failure(
                snapshot,
                "AssertionError: mismatch\n"
                "FAILED test_atlasquant_aion_admin.py::test_render\n",
            )
        finally:
            tmp.cleanup()

        workflow = new_development_workflow(
            "Diagnosticar falha",
            branch="cursor/diag",
            baseline_ref="main@a",
            requested_by="admin",
            created_at="2026-09-27T12:00:00+00:00",
        )
        changed = record_failure_attempt(
            workflow,
            diagnostic,
            command_label="quality suite",
        )
        self.assertEqual(changed["status"], "CORRECTION_REQUIRED")
        self.assertEqual(len(changed["test_attempts"]), 1)
        attempt = changed["test_attempts"][0]
        self.assertEqual(attempt["state"], "FAIL")
        self.assertEqual(attempt["cause"], "")
        self.assertEqual(attempt["cause_truth"], "UNKNOWN")
        self.assertIn(diagnostic["diagnostic_id"], attempt["evidence_refs"])

    def test_insufficient_evidence_is_not_recorded_as_failure_attempt(self):
        tmp, root, snapshot = self._snapshot()
        try:
            diagnostic = diagnose_failure(snapshot, "Execução sem detalhe de falha.")
        finally:
            tmp.cleanup()
        self.assertEqual(diagnostic["state"], "INSUFFICIENT_EVIDENCE")
        workflow = new_development_workflow(
            "Sem evidência",
            branch="cursor/none",
            baseline_ref="main@a",
            requested_by="admin",
        )
        with self.assertRaises(ValueError):
            record_failure_attempt(workflow, diagnostic)

    def test_diagnostic_never_executes_or_fixes(self):
        tmp, root, snapshot = self._snapshot()
        try:
            out = diagnose_failure(
                snapshot,
                "TypeError: wrong type\n"
                "FAILED test_atlasquant_aion_admin.py::test_render\n",
            )
        finally:
            tmp.cleanup()
        for key in (
            "executes_repository_code",
            "runs_tests",
            "writes_files",
            "network_called",
            "subprocess_called",
            "automatic_fix",
            "automatic_commit",
            "automatic_merge",
            "automatic_deploy",
            "production_change_allowed",
            "real_trading_enabled",
            "tool_output_is_authority",
        ):
            self.assertFalse(out[key])


if __name__ == "__main__":
    unittest.main()
