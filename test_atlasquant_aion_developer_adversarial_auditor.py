from __future__ import annotations

import ast
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
import unittest

from atlasquant_aion_developer_adversarial_auditor import (
    SCHEMA,
    audit_developer_chain,
    format_audit_report,
    main,
)

_ROOT = Path(__file__).resolve().parent
_AUDITOR = _ROOT / "atlasquant_aion_developer_adversarial_auditor.py"

_EXPECTED_GAPS = {
    "replay.gate_not_bound_to_targets": "HIGH",
    "lineage.stale_snapshot_after_authorization": "HIGH",
    "scope.plan_records_outside_snapshot": "MEDIUM",
    "scope.post_authorization_expansion": "HIGH",
    "branch.equivalent_refs": "HIGH",
    "branch.prefix_bypass": "HIGH",
    "branch.early_layers_accept_main": "MEDIUM",
    "candidate.unbound_ref": "HIGH",
    "candidate.baseline_casefold_equal": "HIGH",
    "identity.case_variants": "CRITICAL",
    "identity.unicode_nfkc": "CRITICAL",
    "identity.fullwidth": "CRITICAL",
    "identity.combining": "CRITICAL",
    "auth.replay_other_envelope": "HIGH",
    "auth.stolen_authorization_id": "HIGH",
    "auth.approver_is_builder": "MEDIUM",
    "rollback.reused_text": "MEDIUM",
    "tests.approval_accepts_weakening": "HIGH",
    "workflow.envelope_includes_workflow": "MEDIUM",
    "release.notes_ready": "HIGH",
    "payload.excess_files_not_rejected": "MEDIUM",
}

_EXPECTED_BLOCKED = {
    "lineage.crossed_snapshot",
    "lineage.evidence_snapshot_mismatch",
    "lineage.evidence_diagnostic_mismatch",
    "lineage.implementation_package_mismatch",
    "lineage.builder_digest_mismatch",
    "replay.gate_other_correction",
    "scope.outside_editable",
    "scope.unknown_path",
    "scope.traversal_path",
    "scope.absolute_path",
    "files.new_path",
    "scope.correction_excludes_unknown",
    "scope.evidence_outside_files",
    "branch.exact_forbidden",
    "branch.refs_heads_main_master",
    "branch.fullwidth_rejected",
    "candidate.baseline_equal",
    "candidate.baseline_whitespace_equal",
    "identity.exact_duplicate",
    "identity.whitespace_duplicate",
    "auth.approved_false",
    "auth.approved_string",
    "auth.missing",
    "auth.human_flag_false",
    "rollback.empty",
    "tests.builder_blocks_deleted_tests",
    "workflow.builder_blocks_workflow",
    "authority.forged_merge",
    "authority.forged_deploy",
    "authority.forged_trading",
    "secrets.scan_skips_dotenv",
    "path.symlink_skipped",
    "payload.huge_branch_bounded",
}


class AionDeveloperAdversarialAuditorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = audit_developer_chain()

    def test_report_shape_has_no_score(self):
        report = self.report
        self.assertEqual(report["schema"], SCHEMA)
        self.assertEqual(report["state"], "GAPS_PRESENT")
        self.assertEqual(report["cases_total"], 57)
        self.assertEqual(report["gap_count"], 21)
        self.assertEqual(report["blocked_by_design_count"], 33)
        self.assertEqual(report["pass_count"], 3)
        self.assertNotIn("score", report)
        self.assertNotIn("security_score", report)
        for key in (
            "executes_repository_code",
            "writes_existing_files",
            "network_called",
            "subprocess_called",
            "automatic_commit",
            "automatic_merge",
            "automatic_deploy",
            "real_trading_enabled",
            "tool_output_is_authority",
        ):
            self.assertFalse(report[key])
        self.assertEqual(len(report["findings"]), 57)
        for item in report["findings"]:
            self.assertIn(item["classification"], {"PASS", "GAP", "BLOCKED_BY_DESIGN"})
            if item["classification"] == "GAP":
                self.assertIn(item["severity"], {"CRITICAL", "HIGH", "MEDIUM", "LOW"})
            else:
                self.assertEqual(item["severity"], "")

    def test_known_gaps_stay_visible(self):
        found = {item["invariant_id"]: item["severity"] for item in self.report["gaps"]}
        self.assertEqual(found, _EXPECTED_GAPS)

    def test_known_blocks_stay_blocked(self):
        blocked = {
            item["invariant_id"]
            for item in self.report["findings"]
            if item["classification"] == "BLOCKED_BY_DESIGN"
        }
        self.assertTrue(_EXPECTED_BLOCKED <= blocked)

    def test_report_is_deterministic_and_has_no_secret(self):
        again = audit_developer_chain()
        self.assertEqual(again["report_digest"], self.report["report_digest"])
        text = format_audit_report(self.report)
        self.assertNotIn("supersecretvalue", text)
        self.assertNotIn("ghp_ADVERSARIALAUDITOR1234567890", text)
        self.assertIn("GAPS_PRESENT", text)
        self.assertIn("21 gaps", text)

    def test_cli_exits_when_gaps_exist_without_dumping_secrets(self):
        buffer = StringIO()
        with redirect_stdout(buffer):
            code = main()
        text = buffer.getvalue()
        self.assertEqual(code, 1)
        self.assertIn("AION Developer Adversarial Audit", text)
        self.assertIn("identity.case_variants", text)
        self.assertIn("CRITICAL", text)
        self.assertNotIn("supersecretvalue", text)
        self.assertNotIn("ghp_", text)

    def test_auditor_source_is_read_only(self):
        tree = ast.parse(_AUDITOR.read_text(encoding="utf-8"))
        banned_calls = {"eval", "exec", "__import__", "getattr"}
        banned_modules = {
            "importlib", "subprocess", "socket", "requests", "urllib",
            "http", "ftplib", "smtplib",
        }
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                name = ""
                if isinstance(func, ast.Name):
                    name = func.id
                elif isinstance(func, ast.Attribute):
                    name = func.attr
                self.assertNotIn(name, banned_calls)
                if name in {"system", "Popen"}:
                    self.fail(name)
            if isinstance(node, ast.Import):
                for alias in node.names:
                    self.assertNotIn(alias.name.split(".")[0], banned_modules)
            if isinstance(node, ast.ImportFrom) and node.module:
                self.assertNotIn(node.module.split(".")[0], banned_modules)
        source = _AUDITOR.read_text(encoding="utf-8")
        self.assertNotIn("expectedFailure", source)
        self.assertNotIn("unittest.skip", source)


if __name__ == "__main__":
    unittest.main()
