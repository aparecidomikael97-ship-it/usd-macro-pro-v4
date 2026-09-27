from __future__ import annotations

import os
from pathlib import Path
import tempfile
import unittest

from atlasquant_aion_developer_intelligence import (
    PLAN_SCHEMA,
    SCHEMA,
    build_development_plan,
    build_test_coverage_map,
    scan_repository,
)


class AionDeveloperIntelligenceTests(unittest.TestCase):
    def _repo(self):
        tmp = tempfile.TemporaryDirectory()
        root = Path(tmp.name)
        (root / "app.py").write_text(
            "import json\nfrom atlasquant_aion_guardian import guard\n\ndef run():\n    return 1\n",
            encoding="utf-8",
        )
        (root / "test_app.py").write_text(
            "import unittest\nimport app\n\nclass T(unittest.TestCase):\n    def test_run(self):\n        self.assertEqual(app.run(), 1)\n",
            encoding="utf-8",
        )
        (root / "atlasquant_billing_guard.py").write_text(
            "def check():\n    return False\n",
            encoding="utf-8",
        )
        (root / "broken.py").write_text("def broken(:\n", encoding="utf-8")
        (root / ".env").write_text("API_KEY=NEVER-LEAK-THIS", encoding="utf-8")
        (root / ".streamlit").mkdir()
        (root / ".streamlit" / "secrets.toml").write_text(
            'token="NEVER-LEAK-THAT"', encoding="utf-8"
        )
        (root / ".github" / "workflows").mkdir(parents=True)
        (root / ".github" / "workflows" / "quality.yml").write_text(
            "name: Quality\n", encoding="utf-8"
        )
        return tmp, root

    def test_scan_is_structural_and_skips_sensitive_files(self):
        tmp, root = self._repo()
        try:
            out = scan_repository(root)
        finally:
            tmp.cleanup()
        self.assertEqual(out["schema"], SCHEMA)
        paths = {row["path"] for row in out["files"]}
        self.assertIn("app.py", paths)
        self.assertIn("test_app.py", paths)
        self.assertIn(".github/workflows/quality.yml", paths)
        self.assertNotIn(".env", paths)
        self.assertNotIn(".streamlit/secrets.toml", paths)
        rendered = str(out)
        self.assertNotIn("NEVER-LEAK-THIS", rendered)
        self.assertNotIn("NEVER-LEAK-THAT", rendered)
        self.assertFalse(out["content_included"])
        self.assertFalse(out["executes_repository_code"])
        self.assertFalse(out["writes_files"])
        self.assertFalse(out["network_called"])
        self.assertFalse(out["subprocess_called"])

    def test_python_scan_extracts_imports_without_importing_modules(self):
        tmp, root = self._repo()
        try:
            out = scan_repository(root)
        finally:
            tmp.cleanup()
        app = next(row for row in out["files"] if row["path"] == "app.py")
        self.assertEqual(app["syntax_state"], "OK")
        self.assertIn("json", app["imports"])
        self.assertIn("atlasquant_aion_guardian", app["imports"])
        self.assertEqual(app["functions"], 1)
        test = next(row for row in out["files"] if row["path"] == "test_app.py")
        self.assertEqual(test["test_functions"], 1)
        self.assertIn("app", test["imports"])

    def test_syntax_error_is_metadata_not_execution_failure(self):
        tmp, root = self._repo()
        try:
            out = scan_repository(root)
        finally:
            tmp.cleanup()
        broken = next(row for row in out["files"] if row["path"] == "broken.py")
        self.assertEqual(broken["syntax_state"], "ERROR")
        self.assertEqual(out["syntax_errors"], 1)

    def test_symlink_is_never_followed(self):
        tmp, root = self._repo()
        outside = tempfile.TemporaryDirectory()
        try:
            target = Path(outside.name) / "outside.py"
            target.write_text("SECRET_OUTSIDE='do-not-read'\n", encoding="utf-8")
            link = root / "linked.py"
            try:
                os.symlink(target, link)
            except (OSError, NotImplementedError):
                self.skipTest("symlink unsupported on this platform")
            out = scan_repository(root)
            paths = {row["path"] for row in out["files"]}
            self.assertNotIn("linked.py", paths)
            self.assertNotIn("SECRET_OUTSIDE", str(out))
            self.assertGreaterEqual(out["skipped_symlink"], 1)
        finally:
            tmp.cleanup()
            outside.cleanup()

    def test_test_coverage_map_uses_direct_name_and_static_import(self):
        tmp, root = self._repo()
        try:
            snapshot = scan_repository(root)
            coverage = build_test_coverage_map(snapshot, ["app.py", "atlasquant_billing_guard.py"])
        finally:
            tmp.cleanup()
        app = next(item for item in coverage["changes"] if item["path"] == "app.py")
        billing = next(item for item in coverage["changes"] if item["path"] == "atlasquant_billing_guard.py")
        self.assertEqual(app["state"], "COVERED")
        self.assertEqual(app["matched_tests"], ["test_app.py"])
        self.assertEqual(billing["state"], "NO_MATCH")
        self.assertIn("atlasquant_billing_guard.py", coverage["unmatched_code"])
        self.assertFalse(coverage["coverage_is_proof"])
        self.assertFalse(coverage["executes_tests"])

    def test_development_plan_feeds_existing_engine_without_actions(self):
        tmp, root = self._repo()
        try:
            snapshot = scan_repository(root)
            plan = build_development_plan(
                "Corrigir billing sem liberar produção",
                snapshot,
                branch="cursor/dev-safe",
                baseline_ref="abc123",
                changed_paths=["atlasquant_billing_guard.py"],
            )
        finally:
            tmp.cleanup()
        self.assertEqual(plan["schema"], PLAN_SCHEMA)
        self.assertRegex(plan["plan_id"], r"^DEVPLAN-[0-9A-F]{16}$")
        self.assertIn("FINANCIAL", plan["risk_tags"])
        self.assertIn("CHANGED_PYTHON_WITHOUT_LIKELY_TEST", plan["warnings"])
        self.assertTrue(plan["analysis_only"])
        self.assertTrue(plan["human_release_review_required"])
        self.assertFalse(plan["automatic_edit"])
        self.assertFalse(plan["automatic_commit"])
        self.assertFalse(plan["automatic_merge"])
        self.assertFalse(plan["automatic_deploy"])
        self.assertFalse(plan["production_change_allowed"])
        self.assertFalse(plan["real_trading_enabled"])
        self.assertFalse(plan["tool_output_is_authority"])

    def test_scan_is_bounded(self):
        tmp, root = self._repo()
        try:
            for index in range(10):
                (root / f"extra_{index}.py").write_text("x=1\n", encoding="utf-8")
            out = scan_repository(root, max_files=3)
        finally:
            tmp.cleanup()
        self.assertEqual(out["file_count"], 3)
        self.assertTrue(out["truncated"])

    def test_oversized_file_is_not_read(self):
        tmp, root = self._repo()
        try:
            (root / "huge.py").write_text("x" * 5000, encoding="utf-8")
            out = scan_repository(root, max_file_bytes=100)
        finally:
            tmp.cleanup()
        self.assertNotIn("huge.py", {row["path"] for row in out["files"]})
        self.assertGreaterEqual(out["skipped_oversized"], 1)


if __name__ == "__main__":
    unittest.main()
