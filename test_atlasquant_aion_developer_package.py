from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from atlasquant_aion_developer_intelligence import scan_repository
from atlasquant_aion_developer_package import (
    REQUIRED_GATES,
    SCHEMA,
    build_developer_package,
)


class AionDeveloperPackageTests(unittest.TestCase):
    def _snapshot(self):
        tmp = tempfile.TemporaryDirectory()
        root = Path(tmp.name)
        (root / "atlasquant_aion_admin.py").write_text(
            "def render():\n    return True\n",
            encoding="utf-8",
        )
        (root / "atlasquant_access_control.py").write_text(
            "def allowed():\n    return False\n",
            encoding="utf-8",
        )
        (root / "test_atlasquant_aion_admin.py").write_text(
            "import atlasquant_aion_admin\n"
            "def test_render():\n"
            "    assert atlasquant_aion_admin.render()\n",
            encoding="utf-8",
        )
        (root / "test_atlasquant_access_control.py").write_text(
            "import atlasquant_access_control\n"
            "def test_access():\n"
            "    assert atlasquant_access_control.allowed() is False\n",
            encoding="utf-8",
        )
        return tmp, scan_repository(root)

    def test_package_bridges_all_existing_planning_contracts(self):
        tmp, snapshot = self._snapshot()
        try:
            out = build_developer_package(
                "Ajustar admin com segurança",
                snapshot,
                branch="cursor/dev-intelligence",
                baseline_ref="main@abc",
                candidate_ref="cursor/dev-intelligence@def",
                changed_paths=[
                    "atlasquant_aion_admin.py",
                    "atlasquant_access_control.py",
                ],
                created_at="2026-09-27T12:00:00+00:00",
            )
        finally:
            tmp.cleanup()

        self.assertEqual(out["schema"], SCHEMA)
        self.assertRegex(out["package_id"], r"^DEVPACK-[0-9A-F]{16}$")
        self.assertEqual(out["state"], "WAITING_HUMAN")

        workflow = out["developer_workflow"]
        plan_phase = next(x for x in workflow["phases"] if x["phase"] == "PLAN")
        implement_phase = next(x for x in workflow["phases"] if x["phase"] == "IMPLEMENT")
        self.assertEqual(plan_phase["state"], "WAITING_HUMAN")
        self.assertEqual(implement_phase["state"], "PENDING")
        self.assertEqual(workflow["status"], "WAITING_HUMAN")

        twin = out["digital_twin"]
        self.assertTrue(twin["simulation_only"])
        self.assertFalse(twin["production_touched"])
        self.assertEqual(twin["rollback_plan"], "")

        fusion = out["dev_fusion"]
        self.assertEqual(fusion["state"], "PLANNED")
        self.assertEqual(fusion["twin_id"], twin["twin_id"])
        self.assertTrue(all(stage["state"] == "PENDING" for stage in fusion["stages"]))

    def test_risk_surface_adds_risk_based_test_candidates(self):
        tmp, snapshot = self._snapshot()
        try:
            out = build_developer_package(
                "Alterar acesso",
                snapshot,
                branch="cursor/access",
                baseline_ref="main@a",
                candidate_ref="cursor/access@b",
                changed_paths=["atlasquant_access_control.py"],
                created_at="2026-09-27T12:00:00+00:00",
            )
        finally:
            tmp.cleanup()
        strategy = out["test_strategy"]
        self.assertIn("AUTHORITY", out["plan"]["risk_tags"])
        self.assertIn(
            "test_atlasquant_access_control.py",
            strategy["risk_based_tests"]["AUTHORITY"],
        )
        self.assertIn(
            "test_atlasquant_access_control.py",
            strategy["required_test_candidates"],
        )
        self.assertTrue(strategy["selection_is_heuristic"])
        self.assertFalse(strategy["tests_executed"])

    def test_package_never_auto_approves_or_executes(self):
        tmp, snapshot = self._snapshot()
        try:
            out = build_developer_package(
                "Mudança segura",
                snapshot,
                branch="cursor/safe",
                baseline_ref="main@a",
                candidate_ref="cursor/safe@b",
                changed_paths=["atlasquant_aion_admin.py"],
                created_at="2026-09-27T12:00:00+00:00",
            )
        finally:
            tmp.cleanup()
        self.assertEqual(
            [gate["gate"] for gate in out["gates"]],
            list(REQUIRED_GATES),
        )
        self.assertEqual(out["gates"][0]["state"], "WAITING_HUMAN")
        self.assertFalse(out["persists_checkpoint"])
        self.assertFalse(out["executes_repository_code"])
        self.assertFalse(out["runs_tests"])
        self.assertFalse(out["writes_files"])
        self.assertFalse(out["network_called"])
        self.assertFalse(out["subprocess_called"])
        self.assertFalse(out["automatic_edit"])
        self.assertFalse(out["automatic_commit"])
        self.assertFalse(out["automatic_merge"])
        self.assertFalse(out["automatic_deploy"])
        self.assertFalse(out["production_change_allowed"])
        self.assertFalse(out["real_trading_enabled"])
        self.assertFalse(out["tool_output_is_authority"])

    def test_unsafe_snapshot_is_rejected(self):
        tmp, snapshot = self._snapshot()
        try:
            unsafe = dict(snapshot)
            unsafe["network_called"] = True
            with self.assertRaises(ValueError):
                build_developer_package(
                    "unsafe",
                    unsafe,
                    branch="cursor/unsafe",
                    baseline_ref="main@a",
                    candidate_ref="cursor/unsafe@b",
                )
        finally:
            tmp.cleanup()

    def test_candidate_must_differ_from_baseline(self):
        tmp, snapshot = self._snapshot()
        try:
            with self.assertRaises(ValueError):
                build_developer_package(
                    "same ref",
                    snapshot,
                    branch="same",
                    baseline_ref="same",
                    candidate_ref="same",
                )
        finally:
            tmp.cleanup()

    def test_unmatched_python_creates_review_gap(self):
        tmp, snapshot = self._snapshot()
        try:
            out = build_developer_package(
                "Novo módulo sem teste",
                snapshot,
                branch="cursor/new",
                baseline_ref="main@a",
                candidate_ref="cursor/new@b",
                changed_paths=["new_uncovered_module.py"],
                created_at="2026-09-27T12:00:00+00:00",
            )
        finally:
            tmp.cleanup()
        self.assertIn("PYTHON_WITHOUT_LIKELY_TEST", out["gaps"])
        test_gate = next(x for x in out["gates"] if x["gate"] == "TEST_SELECTION")
        self.assertEqual(test_gate["state"], "REVIEW_REQUIRED")


if __name__ == "__main__":
    unittest.main()
