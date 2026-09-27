from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import tempfile
import unittest

from atlasquant_aion_developer_correction import SCHEMA, build_correction_plan
from atlasquant_aion_developer_diagnostics import diagnose_failure
from atlasquant_aion_developer_intelligence import scan_repository
from atlasquant_aion_developer_package import build_developer_package


class AionDeveloperCorrectionTests(unittest.TestCase):
    def _fixture(self):
        tmp = tempfile.TemporaryDirectory()
        root = Path(tmp.name)
        (root / "atlasquant_access_control.py").write_text(
            "def allowed():\n    return False\n",
            encoding="utf-8",
        )
        (root / "test_atlasquant_access_control.py").write_text(
            "import atlasquant_access_control\n"
            "def test_allowed():\n"
            "    assert atlasquant_access_control.allowed() is False\n",
            encoding="utf-8",
        )
        snapshot = scan_repository(root)
        package = build_developer_package(
            "Corrigir acesso sem ampliar autoridade",
            snapshot,
            branch="cursor/access-fix",
            baseline_ref="main@abc",
            candidate_ref="cursor/access-fix@def",
            changed_paths=["atlasquant_access_control.py"],
            created_at="2026-09-27T12:00:00+00:00",
        )
        diagnostic = diagnose_failure(
            snapshot,
            "AssertionError: mismatch\n"
            "FAILED test_atlasquant_access_control.py::test_allowed\n"
            f'File "{root / "atlasquant_access_control.py"}", line 2\n',
        )
        return tmp, snapshot, package, diagnostic

    def test_builds_same_snapshot_human_gated_plan(self):
        tmp, snapshot, package, diagnostic = self._fixture()
        try:
            out = build_correction_plan(snapshot, diagnostic, package)
        finally:
            tmp.cleanup()
        self.assertEqual(out["schema"], SCHEMA)
        self.assertRegex(out["correction_id"], r"^DEVCORR-[0-9A-F]{18}$")
        self.assertEqual(out["state"], "WAITING_HUMAN")
        self.assertEqual(out["lineage"]["snapshot_digest"], snapshot["snapshot_digest"])
        self.assertEqual(out["lineage"]["diagnostic_id"], diagnostic["diagnostic_id"])
        self.assertEqual(out["lineage"]["package_id"], package["package_id"])
        self.assertIn("atlasquant_access_control.py", out["target_files"])
        self.assertIn("AUTHORITY", out["risk_tags"])
        self.assertIn(
            "test_atlasquant_access_control.py::test_allowed",
            out["test_candidates"],
        )
        self.assertFalse(out["root_cause_confirmed"])
        self.assertEqual(out["root_cause_truth_status"], "UNKNOWN")
        self.assertFalse(out["patch_generated"])

    def test_builder_reviewer_breaker_packets_preserve_separation(self):
        tmp, snapshot, package, diagnostic = self._fixture()
        try:
            out = build_correction_plan(snapshot, diagnostic, package)
        finally:
            tmp.cleanup()
        self.assertEqual(out["builder_packet"]["state"], "WAITING_HUMAN_ASSIGNMENT")
        self.assertTrue(out["reviewer_packet"]["must_be_independent_from_builder"])
        self.assertTrue(
            out["breaker_packet"]["must_be_independent_from_builder_and_reviewer"]
        )
        self.assertTrue(out["breaker_packet"]["checks"])
        self.assertFalse(out["builder_packet"]["executes_action"])
        self.assertFalse(out["reviewer_packet"]["executes_action"])
        self.assertFalse(out["breaker_packet"]["executes_action"])

    def test_snapshot_lineage_mismatch_fails_closed(self):
        tmp, snapshot, package, diagnostic = self._fixture()
        try:
            changed = deepcopy(diagnostic)
            changed["snapshot_digest"] = "REPO-DIFFERENT"
            with self.assertRaises(ValueError):
                build_correction_plan(snapshot, changed, package)
        finally:
            tmp.cleanup()

    def test_package_lineage_mismatch_fails_closed(self):
        tmp, snapshot, package, diagnostic = self._fixture()
        try:
            changed = deepcopy(package)
            changed["plan"] = deepcopy(package["plan"])
            changed["plan"]["snapshot_digest"] = "REPO-DIFFERENT"
            with self.assertRaises(ValueError):
                build_correction_plan(snapshot, diagnostic, changed)
        finally:
            tmp.cleanup()

    def test_confirmed_root_cause_input_is_rejected(self):
        tmp, snapshot, package, diagnostic = self._fixture()
        try:
            changed = deepcopy(diagnostic)
            changed["cause_confirmed"] = True
            changed["cause_truth_status"] = "CONFIRMED"
            with self.assertRaises(ValueError):
                build_correction_plan(snapshot, changed, package)
        finally:
            tmp.cleanup()

    def test_unknown_hypothesis_is_not_promoted(self):
        tmp, snapshot, package, diagnostic = self._fixture()
        try:
            out = build_correction_plan(snapshot, diagnostic, package)
        finally:
            tmp.cleanup()
        self.assertTrue(out["hypotheses"])
        self.assertTrue(all(
            item["truth_status"] == "UNKNOWN"
            for item in out["hypotheses"]
        ))
        self.assertIn("REPRODUCIBLE_FAILING_TEST_OR_EQUIVALENT", out["evidence_required"])
        self.assertEqual(out["rollback"]["state"], "REQUIRED")
        self.assertEqual(out["rollback"]["plan"], "")

    def test_plan_never_executes_or_changes_repository(self):
        tmp, snapshot, package, diagnostic = self._fixture()
        try:
            out = build_correction_plan(snapshot, diagnostic, package)
        finally:
            tmp.cleanup()
        for key in (
            "persists_checkpoint",
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
