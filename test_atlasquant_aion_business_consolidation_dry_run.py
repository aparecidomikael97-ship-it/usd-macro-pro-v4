import ast
import unittest
from pathlib import Path

from atlasquant_aion_business_consolidation_dry_run import (
    LIVE_REVALIDATION_GATES,
    SCHEMA,
    administrative_decision_packet,
    build_consolidation_runbook,
    live_revalidation_snapshot,
)


def _stack_ready():
    return {
        "state": "READY_FOR_ADMIN_REVIEW",
        "complete": True,
        "merge_authorized": False,
        "deploy_authorized": False,
        "runtime_activation_authorized": False,
    }


def _live_green():
    evidence = {gate: True for gate in LIVE_REVALIDATION_GATES}
    evidence["evidence_source"] = "trusted external GitHub verifier"
    evidence["observed_at"] = "2026-09-30T12:00:00Z"
    return live_revalidation_snapshot(evidence)


class BusinessConsolidationDryRunTests(unittest.TestCase):
    def test_frozen_stack_alone_never_becomes_merge_ready(self):
        live = live_revalidation_snapshot({})
        runbook = build_consolidation_runbook(_stack_ready(), live)
        self.assertEqual(runbook["state"], "AWAITING_LIVE_REVALIDATION")
        self.assertEqual(runbook["step_count"], 14)
        self.assertFalse(runbook["merge_authorized"])
        self.assertFalse(runbook["deploy_authorized"])
        self.assertFalse(runbook["runtime_activation_authorized"])
        self.assertFalse(runbook["executes_action"])

    def test_exact_boolean_live_revalidation_fails_closed(self):
        evidence = {gate: True for gate in LIVE_REVALIDATION_GATES}
        evidence["all_required_checks_success"] = "true"
        live = live_revalidation_snapshot(evidence)
        self.assertEqual(live["state"], "LIVE_REVALIDATION_REQUIRED")
        self.assertIn("all_required_checks_success", live["missing"])

    def test_fully_revalidated_stack_only_reaches_admin_decision(self):
        live = _live_green()
        runbook = build_consolidation_runbook(_stack_ready(), live)
        self.assertEqual(runbook["schema"], SCHEMA)
        self.assertEqual(runbook["state"], "READY_FOR_EXPLICIT_ADMIN_DECISION")
        self.assertTrue(runbook["requires_explicit_admin_decision"])
        self.assertTrue(runbook["requires_per_step_live_revalidation"])
        self.assertTrue(runbook["requires_post_step_ci"])
        self.assertTrue(runbook["requires_final_main_ci"])
        self.assertFalse(runbook["merge_authorized"])
        self.assertFalse(runbook["auto_merge_enabled"])

    def test_each_step_has_stop_condition_and_executes_nothing(self):
        runbook = build_consolidation_runbook(_stack_ready(), _live_green())
        self.assertEqual([row["pr"] for row in runbook["steps"]], list(range(398, 412)))
        for step in runbook["steps"]:
            self.assertTrue(step["stop_on_failure"])
            self.assertFalse(step["executes_action"])
            self.assertIn("confirm explicit administrative authorization exists", step["before_hypothetical_merge"])
            self.assertIn("re-run required CI before considering next PR", step["after_hypothetical_merge"])

    def test_bad_stack_blocks_runbook_even_with_live_evidence(self):
        stack = _stack_ready()
        stack["complete"] = False
        runbook = build_consolidation_runbook(stack, _live_green())
        self.assertEqual(runbook["state"], "STACK_REVIEW_BLOCKED")
        self.assertEqual(runbook["step_count"], 0)

    def test_decision_packet_never_grants_authority(self):
        runbook = build_consolidation_runbook(_stack_ready(), _live_green())
        packet = administrative_decision_packet(
            runbook,
            reviewer="Mikael",
            note="Revisar tecnicamente antes de qualquer autorização futura.",
        )
        self.assertEqual(packet["state"], "ADMIN_DECISION_REQUIRED")
        self.assertTrue(packet["eligible_for_human_decision"])
        self.assertFalse(packet["merge_authorized"])
        self.assertFalse(packet["deploy_authorized"])
        self.assertFalse(packet["runtime_activation_authorized"])
        self.assertFalse(packet["executes_action"])

    def test_module_has_no_network_git_or_process_executor(self):
        source = Path("atlasquant_aion_business_consolidation_dry_run.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported = []
        for node in tree.body:
            if isinstance(node, ast.Import):
                imported.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.append(node.module or "")
        for banned in ("requests", "urllib", "httpx", "socket", "subprocess", "github"):
            self.assertNotIn(banned, imported)


if __name__ == "__main__":
    unittest.main()
