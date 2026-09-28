from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from atlasquant_aion_developer_correction import build_correction_plan
from atlasquant_aion_developer_diagnostics import diagnose_failure
from atlasquant_aion_developer_evidence_gate import (
    CONFIRMATION_SCHEMA,
    SCHEMA,
    confirm_root_cause_human_review,
    evaluate_evidence_promotion,
)
from atlasquant_aion_developer_intelligence import scan_repository
from atlasquant_aion_developer_package import build_developer_package


class AionDeveloperEvidenceGateTests(unittest.TestCase):
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
            "Corrigir acesso",
            snapshot,
            branch="cursor/access",
            baseline_ref="main@a",
            candidate_ref="cursor/access@b",
            changed_paths=["atlasquant_access_control.py"],
            created_at="2026-09-27T12:00:00+00:00",
        )
        diagnostic = diagnose_failure(
            snapshot,
            "AssertionError: mismatch\n"
            "FAILED test_atlasquant_access_control.py::test_allowed\n"
            f'File "{root / "atlasquant_access_control.py"}", line 2\n',
        )
        correction = build_correction_plan(snapshot, diagnostic, package)
        hypothesis = correction["hypotheses"][0]["label"]
        test_id = correction["test_candidates"][0]
        return tmp, snapshot, diagnostic, correction, hypothesis, test_id

    def _ready_gate(self, correction, hypothesis, test_id, snapshot, diagnostic):
        return evaluate_evidence_promotion(
            correction,
            hypothesis_label=hypothesis,
            test_id=test_id,
            before_state="FAIL",
            after_state="PASS",
            changed_files=["atlasquant_access_control.py"],
            evidence_refs=["run:before", "run:after"],
            intervention_summary="Mudança mínima dentro do escopo reproduziu FAIL antes e PASS depois.",
            scope_preserved=True,
            snapshot_digest=snapshot["snapshot_digest"],
            diagnostic_id=diagnostic["diagnostic_id"],
        )

    def test_complete_evidence_is_only_ready_for_human_review(self):
        tmp, snapshot, diagnostic, correction, hypothesis, test_id = self._fixture()
        try:
            gate = self._ready_gate(correction, hypothesis, test_id, snapshot, diagnostic)
        finally:
            tmp.cleanup()
        self.assertEqual(gate["schema"], SCHEMA)
        self.assertEqual(gate["state"], "READY_FOR_HUMAN_CAUSE_REVIEW")
        self.assertFalse(gate["hypothesis"]["promotion_applied"])
        self.assertEqual(gate["hypothesis"]["current_truth_status"], "UNKNOWN")
        self.assertEqual(gate["hypothesis"]["proposed_truth_status"], "CONFIRMED")
        self.assertFalse(gate["root_cause_confirmed"])
        self.assertTrue(gate["human_review_required"])
        self.assertFalse(gate["automatic_truth_promotion"])

    def test_incomplete_evidence_stays_insufficient(self):
        tmp, snapshot, diagnostic, correction, hypothesis, test_id = self._fixture()
        try:
            gate = evaluate_evidence_promotion(
                correction,
                hypothesis_label=hypothesis,
                test_id=test_id,
                before_state="PASS",
                after_state="PASS",
                changed_files=[],
                evidence_refs=["one"],
                intervention_summary="",
                scope_preserved=False,
                snapshot_digest=snapshot["snapshot_digest"],
                diagnostic_id=diagnostic["diagnostic_id"],
            )
        finally:
            tmp.cleanup()
        self.assertEqual(gate["state"], "INSUFFICIENT_EVIDENCE")
        self.assertIn("BEFORE_STATE_MUST_BE_FAIL", gate["blockers"])
        self.assertIn("CHANGED_FILES_REQUIRED", gate["blockers"])
        self.assertIn("SCOPE_NOT_PRESERVED", gate["blockers"])
        self.assertFalse(gate["root_cause_confirmed"])

    def test_lineage_mismatch_fails_closed(self):
        tmp, snapshot, diagnostic, correction, hypothesis, test_id = self._fixture()
        try:
            with self.assertRaises(ValueError):
                evaluate_evidence_promotion(
                    correction,
                    hypothesis_label=hypothesis,
                    test_id=test_id,
                    before_state="FAIL",
                    after_state="PASS",
                    changed_files=["atlasquant_access_control.py"],
                    evidence_refs=["before", "after"],
                    intervention_summary="Mudança mínima.",
                    scope_preserved=True,
                    snapshot_digest="REPO-DIFFERENT",
                    diagnostic_id=diagnostic["diagnostic_id"],
                )
        finally:
            tmp.cleanup()

    def test_out_of_scope_change_is_blocked(self):
        tmp, snapshot, diagnostic, correction, hypothesis, test_id = self._fixture()
        try:
            gate = evaluate_evidence_promotion(
                correction,
                hypothesis_label=hypothesis,
                test_id=test_id,
                before_state="FAIL",
                after_state="PASS",
                changed_files=["outside.py"],
                evidence_refs=["before", "after"],
                intervention_summary="Mudança fora do escopo.",
                scope_preserved=True,
                snapshot_digest=snapshot["snapshot_digest"],
                diagnostic_id=diagnostic["diagnostic_id"],
            )
        finally:
            tmp.cleanup()
        self.assertEqual(gate["state"], "INSUFFICIENT_EVIDENCE")
        self.assertIn("CHANGED_FILE_OUTSIDE_ALLOWED_SCOPE", gate["blockers"])

    def test_gate_is_bound_to_exact_correction_manifest(self):
        tmp, snapshot, diagnostic, correction, hypothesis, test_id = self._fixture()
        try:
            gate = self._ready_gate(correction, hypothesis, test_id, snapshot, diagnostic)
            changed = dict(correction)
            changed["target_files"] = list(correction["target_files"]) + ["other.py"]
            with self.assertRaises(ValueError):
                confirm_root_cause_human_review(
                    changed,gate,approved=True,reviewer_actor="human-reviewer",
                    review_evidence_refs=["review:1"],
                )
        finally:
            tmp.cleanup()

    def test_human_confirmation_requires_explicit_approval(self):
        tmp, snapshot, diagnostic, correction, hypothesis, test_id = self._fixture()
        try:
            gate = self._ready_gate(correction, hypothesis, test_id, snapshot, diagnostic)
            with self.assertRaises(ValueError):
                confirm_root_cause_human_review(
                    correction,
                    gate,
                    approved=False,
                    reviewer_actor="reviewer",
                    review_evidence_refs=["review:1"],
                )
        finally:
            tmp.cleanup()

    def test_human_confirmation_promotes_only_session_record(self):
        tmp, snapshot, diagnostic, correction, hypothesis, test_id = self._fixture()
        try:
            gate = self._ready_gate(correction, hypothesis, test_id, snapshot, diagnostic)
            confirmed = confirm_root_cause_human_review(
                correction,
                gate,
                approved=True,
                reviewer_actor="human-reviewer",
                review_evidence_refs=["review:1"],
            )
        finally:
            tmp.cleanup()
        self.assertTrue(confirmed["root_cause_confirmed"])
        self.assertEqual(confirmed["root_cause_truth_status"], "CONFIRMED")
        self.assertEqual(confirmed["state"], "CAUSE_CONFIRMED_WAITING_IMPLEMENTATION")
        self.assertEqual(
            confirmed["confirmed_root_cause"]["schema"],
            CONFIRMATION_SCHEMA,
        )
        self.assertTrue(confirmed["confirmed_root_cause"]["human_approved"])
        self.assertEqual(
            confirmed["confirmed_root_cause"]["source"],
            "HUMAN_REVIEW",
        )
        self.assertFalse(confirmed["patch_generated"])
        self.assertFalse(confirmed["persists_checkpoint"])
        self.assertFalse(confirmed["automatic_fix"])
        self.assertFalse(confirmed["automatic_commit"])
        self.assertFalse(confirmed["automatic_merge"])
        self.assertFalse(confirmed["automatic_deploy"])

    def test_gate_never_executes_tests_or_repository_actions(self):
        tmp, snapshot, diagnostic, correction, hypothesis, test_id = self._fixture()
        try:
            gate = self._ready_gate(correction, hypothesis, test_id, snapshot, diagnostic)
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
            self.assertFalse(gate[key])


if __name__ == "__main__":
    unittest.main()
