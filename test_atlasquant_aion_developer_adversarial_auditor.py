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

_ROOT=Path(__file__).resolve().parent
_AUDITOR=_ROOT/"atlasquant_aion_developer_adversarial_auditor.py"

_HARDENED_INVARIANTS={
    "replay.gate_not_bound_to_targets",
    "lineage.stale_snapshot_after_authorization",
    "scope.plan_records_outside_snapshot",
    "scope.post_authorization_expansion",
    "branch.equivalent_refs",
    "branch.prefix_bypass",
    "candidate.unbound_ref",
    "candidate.baseline_casefold_equal",
    "identity.case_variants",
    "identity.unicode_nfkc",
    "identity.fullwidth",
    "identity.combining",
    "auth.replay_other_envelope",
    "auth.stolen_authorization_id",
    "auth.approver_is_builder",
    "rollback.reused_text",
    "tests.approval_accepts_weakening",
    "workflow.envelope_includes_workflow",
    "release.notes_ready",
    "payload.excess_files_not_rejected",
    "identity.format_characters",
    "branch.nested_refs_and_aliases",
    "release.deployment_and_deploy_scripts",
    "tests.added_skip_or_expected_failure",
    "tests.recomputed_manifest_still_blocks_weakening",
    "runner.external_test_path",
    "runner.windows_absolute_test_path",
    "runner.unauthorized_or_nonexistent_test",
    "preflight.windows_drive_path",
    "patch.diff_header_mismatch",
    "patch.secret_beyond_prefix",
    "patch.additive_test_neutralization",
    "command.executable_nul",
    "command.executable_newline",
    "command.executable_whitespace",
    "command.non_mapping_entry",
    "command.runtime_budget_invalid",
    "command.memory_budget_invalid",
    "command.output_budget_invalid",
    "command.command_budget_invalid",
    "patch.missing_hunk",
    "runner.excessive_test_targets",
    "path.symlink_hardlink_physical_boundary_unverified",
    "test_contract.candidate_tests_mutated_after_request_id",
    "test_contract.mandatory_gates_mutated_after_request_id",
    "test_contract.required_gate_removed",
    "test_contract.arbitrary_gate",
    "test_contract.candidate_tests_string",
    "test_contract.mandatory_gates_string",
    "test_contract.review_refs_string",
    "test_contract.non_string_elements",
    "budget.runtime_true_initial",
    "budget.runtime_false_initial",
    "budget.runtime_numeric_string",
    "budget.runtime_integral_float",
    "budget.runtime_fractional_float",
    "budget.runtime_none",
    "budget.max_commands_true_initial",
    "budget.runtime_list_and_dict",
    "budget.runtime_mutated_to_true_keeps_id",
    "budget.max_commands_mutated_to_true_keeps_id",
    "budget.recompute_rejects_true",
    "budget.runner_revalidates_exact_int",
    "budget.command_policy_revalidates_exact_int",
}


class AionDeveloperAdversarialAuditorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report=audit_developer_chain()

    def test_report_shape_is_deterministic_and_unscored(self):
        report=self.report
        self.assertEqual(report["schema"],SCHEMA)
        self.assertEqual(report["cases_total"],101)
        self.assertEqual(
            report["gap_count"]+report["blocked_by_design_count"]+report["pass_count"],
            101,
        )
        self.assertFalse(report["symlink_physical_boundary_verified"])
        self.assertFalse(report["hardlink_physical_boundary_verified"])
        self.assertNotIn("score",report)
        self.assertNotIn("security_score",report)
        for key in (
            "executes_repository_code","writes_existing_files","network_called",
            "subprocess_called","automatic_commit","automatic_merge",
            "automatic_deploy","real_trading_enabled","tool_output_is_authority",
        ):
            self.assertFalse(report[key])

    def test_manifest_hardening_closes_previous_critical_and_high_findings(self):
        gaps={item["invariant_id"]:item for item in self.report["gaps"]}
        still_open=sorted(_HARDENED_INVARIANTS & set(gaps))
        self.assertEqual(still_open,[])
        self.assertEqual(self.report["gaps_by_severity"]["CRITICAL"],[])
        self.assertEqual(self.report["gaps_by_severity"]["HIGH"],[])

    def test_every_remaining_gap_is_explicit_and_noncritical(self):
        for item in self.report["gaps"]:
            self.assertIn(item["severity"],{"MEDIUM","LOW"})
            self.assertTrue(item["invariant_id"])
            self.assertTrue(item["description"])

    def test_report_is_deterministic_and_has_no_secret(self):
        again=audit_developer_chain()
        self.assertEqual(again["report_digest"],self.report["report_digest"])
        text=format_audit_report(self.report)
        self.assertNotIn("supersecretvalue",text)
        self.assertNotIn("ghp_ADVERSARIALAUDITOR1234567890",text)

    def test_cli_exit_matches_gap_state_without_dumping_secrets(self):
        buffer=StringIO()
        with redirect_stdout(buffer):
            code=main()
        text=buffer.getvalue()
        self.assertEqual(code,1 if self.report["gap_count"] else 0)
        self.assertIn("AION Developer Adversarial Audit",text)
        self.assertNotIn("supersecretvalue",text)
        self.assertNotIn("ghp_",text)

    def test_auditor_source_is_read_only(self):
        tree=ast.parse(_AUDITOR.read_text(encoding="utf-8"))
        banned_calls={"eval","exec","__import__","getattr"}
        banned_modules={"importlib","subprocess","socket","requests","urllib","http","ftplib","smtplib"}
        for node in ast.walk(tree):
            if isinstance(node,ast.Call):
                func=node.func
                name=func.id if isinstance(func,ast.Name) else func.attr if isinstance(func,ast.Attribute) else ""
                self.assertNotIn(name,banned_calls)
                if name in {"system","Popen"}:
                    self.fail(name)
            if isinstance(node,ast.Import):
                for alias in node.names:
                    self.assertNotIn(alias.name.split(".")[0],banned_modules)
            if isinstance(node,ast.ImportFrom) and node.module:
                self.assertNotIn(node.module.split(".")[0],banned_modules)
        source=_AUDITOR.read_text(encoding="utf-8")
        self.assertNotIn("expectedFailure",source)
        self.assertNotIn("unittest.skip",source)


if __name__=="__main__":
    unittest.main()
