from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from atlasquant_aion_developer_correction import build_correction_plan
from atlasquant_aion_developer_diagnostics import diagnose_failure
from atlasquant_aion_developer_evidence_gate import (
    confirm_root_cause_human_review,
    evaluate_evidence_promotion,
)
from atlasquant_aion_developer_implementation import (
    AUTH_SCHEMA,
    SCHEMA,
    approve_implementation_session,
    build_implementation_envelope,
    prepare_implementation_readiness,
)
from atlasquant_aion_developer_intelligence import scan_repository
from atlasquant_aion_developer_package import build_developer_package


class AionDeveloperImplementationEnvelopeTests(unittest.TestCase):
    def _fixture(self):
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
        snapshot = scan_repository(root)
        package = build_developer_package(
            "Corrigir admin",
            snapshot,
            branch="cursor/admin-fix",
            baseline_ref="main@a",
            candidate_ref="cursor/admin-fix@b",
            changed_paths=["atlasquant_aion_admin.py"],
            created_at="2026-09-27T12:00:00+00:00",
        )
        diagnostic = diagnose_failure(
            snapshot,
            "AssertionError: mismatch\n"
            "FAILED test_atlasquant_aion_admin.py::test_render\n"
            f'File "{root / "atlasquant_aion_admin.py"}", line 2\n',
        )
        correction = build_correction_plan(snapshot, diagnostic, package)
        hypothesis = correction["hypotheses"][0]["label"]
        test_id = correction["test_candidates"][0]
        gate = evaluate_evidence_promotion(
            correction,
            hypothesis_label=hypothesis,
            test_id=test_id,
            before_state="FAIL",
            after_state="PASS",
            changed_files=["atlasquant_aion_admin.py"],
            evidence_refs=["run:before", "run:after"],
            intervention_summary="Mudança mínima reproduziu FAIL antes e PASS depois.",
            scope_preserved=True,
            snapshot_digest=snapshot["snapshot_digest"],
            diagnostic_id=diagnostic["diagnostic_id"],
        )
        confirmed = confirm_root_cause_human_review(
            correction,
            gate,
            approved=True,
            reviewer_actor="human-reviewer",
            review_evidence_refs=["review:1"],
        )
        return tmp, snapshot, package, correction, confirmed

    def test_requires_human_confirmed_root_cause(self):
        tmp, snapshot, package, correction, confirmed = self._fixture()
        try:
            with self.assertRaises(ValueError):
                build_implementation_envelope(snapshot, package, correction)
        finally:
            tmp.cleanup()

    def test_builds_level_two_waiting_human_envelope(self):
        tmp, snapshot, package, correction, confirmed = self._fixture()
        try:
            out = build_implementation_envelope(snapshot, package, confirmed)
        finally:
            tmp.cleanup()
        self.assertEqual(out["schema"], SCHEMA)
        self.assertRegex(out["envelope_id"], r"^DEVIMPL-[0-9A-F]{18}$")
        self.assertEqual(out["state"], "WAITING_HUMAN_IMPLEMENTATION_APPROVAL")
        self.assertEqual(out["requested_trust_level"], 2)
        self.assertEqual(out["trust_policy"]["max_autonomous_level"], 1)
        self.assertFalse(out["trust_policy"]["autonomous_allowed"])
        self.assertTrue(out["trust_policy"]["human_gate_required"])
        self.assertFalse(out["implementation_authorized"])
        self.assertFalse(out["execution_authorized"])

    def test_scope_is_bounded_to_known_source_and_test_files(self):
        tmp, snapshot, package, correction, confirmed = self._fixture()
        try:
            out = build_implementation_envelope(snapshot, package, confirmed)
        finally:
            tmp.cleanup()
        self.assertIn("atlasquant_aion_admin.py", out["scope"]["source_files"])
        self.assertIn("test_atlasquant_aion_admin.py", out["scope"]["test_files"])
        self.assertFalse(out["scope"]["scope_expansion_allowed"])
        self.assertEqual(
            out["change_budget"]["max_editable_files"],
            len(out["scope"]["editable_files"]),
        )
        self.assertFalse(out["change_budget"]["authority_delta_allowed"])
        self.assertFalse(out["test_contract"]["test_deletion_allowed"])
        self.assertFalse(out["test_contract"]["test_weakening_allowed"])

    def test_ui_scope_requires_ui_and_mobile_gates(self):
        tmp, snapshot, package, correction, confirmed = self._fixture()
        try:
            out = build_implementation_envelope(snapshot, package, confirmed)
        finally:
            tmp.cleanup()
        gates = out["test_contract"]["mandatory_gates"]
        self.assertIn("QUALITY_TESTS", gates)
        self.assertIn("RELEASE_READINESS", gates)
        self.assertIn("UI_SMOKE", gates)
        self.assertIn("MOBILE_DOM", gates)
        self.assertIn("INDEPENDENT_REVIEW", gates)
        self.assertIn("INDEPENDENT_BREAKER", gates)

    def test_readiness_requires_rollback_and_independent_roles(self):
        tmp, snapshot, package, correction, confirmed = self._fixture()
        try:
            envelope = build_implementation_envelope(snapshot, package, confirmed)
            with self.assertRaises(ValueError):
                prepare_implementation_readiness(
                    envelope,
                    rollback_plan="",
                    builder_actor="builder",
                    reviewer_actor="reviewer",
                    breaker_actor="breaker",
                    readiness_refs=["ready:1"],
                )
            with self.assertRaises(ValueError):
                prepare_implementation_readiness(
                    envelope,
                    rollback_plan="Reverter a mudança lógica.",
                    builder_actor="same",
                    reviewer_actor="same",
                    breaker_actor="breaker",
                    readiness_refs=["ready:1"],
                )
        finally:
            tmp.cleanup()

    def test_role_independence_uses_canonical_identity(self):
        tmp, snapshot, package, correction, confirmed = self._fixture()
        try:
            envelope = build_implementation_envelope(snapshot, package, confirmed)
            with self.assertRaises(ValueError):
                prepare_implementation_readiness(
                    envelope,
                    rollback_plan="Reverter a mudança lógica.",
                    builder_actor="Builder Alpha",
                    reviewer_actor=" builder alpha ",
                    breaker_actor="Breaker",
                    readiness_refs=["ready:1"],
                )
            with self.assertRaises(ValueError):
                prepare_implementation_readiness(
                    envelope,
                    rollback_plan="Reverter a mudança lógica.",
                    builder_actor="Builder",
                    reviewer_actor="Ｂｕｉｌｄｅｒ",
                    breaker_actor="Breaker",
                    readiness_refs=["ready:1"],
                )
        finally:
            tmp.cleanup()

    def test_readiness_still_does_not_execute(self):
        tmp, snapshot, package, correction, confirmed = self._fixture()
        try:
            envelope = build_implementation_envelope(snapshot, package, confirmed)
            ready = prepare_implementation_readiness(
                envelope,
                rollback_plan="Reverter a mudança lógica e restaurar o baseline.",
                builder_actor="builder",
                reviewer_actor="reviewer",
                breaker_actor="breaker",
                readiness_refs=["ready:scope", "ready:rollback"],
            )
        finally:
            tmp.cleanup()
        self.assertEqual(ready["state"], "READY_FOR_HUMAN_IMPLEMENTATION_APPROVAL")
        self.assertTrue(ready["readiness"]["roles_independent"])
        self.assertTrue(ready["rollback_contract"]["recorded_for_this_change"])
        self.assertFalse(ready["implementation_authorized"])
        self.assertFalse(ready["execution_authorized"])
        self.assertFalse(ready["writes_files"])

    def test_implementation_approval_requires_explicit_human_evidence(self):
        tmp, snapshot, package, correction, confirmed = self._fixture()
        try:
            envelope = build_implementation_envelope(snapshot, package, confirmed)
            ready = prepare_implementation_readiness(
                envelope,
                rollback_plan="Reverter a mudança lógica.",
                builder_actor="builder",
                reviewer_actor="reviewer",
                breaker_actor="breaker",
                readiness_refs=["ready:1"],
            )
            with self.assertRaises(ValueError):
                approve_implementation_session(
                    ready,
                    approved=False,
                    approver_actor="admin",
                    approval_refs=["approval:1"],
                )
        finally:
            tmp.cleanup()

    def test_approved_envelope_still_does_not_execute(self):
        tmp, snapshot, package, correction, confirmed = self._fixture()
        try:
            envelope = build_implementation_envelope(snapshot, package, confirmed)
            ready = prepare_implementation_readiness(
                envelope,
                rollback_plan="Reverter a mudança lógica.",
                builder_actor="builder",
                reviewer_actor="reviewer",
                breaker_actor="breaker",
                readiness_refs=["ready:1"],
            )
            approved = approve_implementation_session(
                ready,
                approved=True,
                approver_actor="human-approver",
                approval_refs=["approval:1"],
            )
        finally:
            tmp.cleanup()
        self.assertEqual(approved["state"], "IMPLEMENTATION_AUTHORIZED_SESSION_ONLY")
        self.assertTrue(approved["implementation_authorized"])
        self.assertFalse(approved["execution_authorized"])
        self.assertEqual(approved["authorization"]["schema"], AUTH_SCHEMA)
        self.assertEqual(approved["authorization"]["builder_actor"], "builder")
        self.assertEqual(approved["authorization"]["reviewer_actor"], "reviewer")
        self.assertEqual(approved["authorization"]["breaker_actor"], "breaker")
        self.assertEqual(approved["authorization"]["builder_identity_key"], "builder")
        self.assertEqual(approved["authorization"]["reviewer_identity_key"], "reviewer")
        self.assertEqual(approved["authorization"]["breaker_identity_key"], "breaker")
        self.assertTrue(approved["authorization"]["rollback_recorded"])
        self.assertFalse(approved["authorization"]["merge_main_allowed"])
        self.assertFalse(approved["authorization"]["deploy_allowed"])
        self.assertFalse(approved["automatic_edit"])
        self.assertFalse(approved["automatic_commit"])
        self.assertFalse(approved["automatic_merge"])
        self.assertFalse(approved["automatic_deploy"])
        self.assertFalse(approved["writes_files"])

    def test_readiness_manifest_blocks_scope_or_test_mutation(self):
        tmp, snapshot, package, correction, confirmed = self._fixture()
        try:
            envelope = build_implementation_envelope(snapshot, package, confirmed)
            ready = prepare_implementation_readiness(
                envelope,rollback_plan="Reverter mudança.",
                builder_actor="builder",reviewer_actor="reviewer",breaker_actor="breaker",
                readiness_refs=["ready:1"],
            )
            changed = dict(ready)
            changed["scope"] = dict(ready["scope"])
            changed["scope"]["editable_files"] = list(ready["scope"]["editable_files"]) + ["other.py"]
            with self.assertRaises(ValueError):
                approve_implementation_session(
                    changed,approved=True,approver_actor="human-approver",
                    approval_refs=["approval:1"],
                )
            changed2 = dict(ready)
            changed2["test_contract"] = dict(ready["test_contract"])
            changed2["test_contract"]["test_deletion_allowed"] = True
            with self.assertRaises(ValueError):
                approve_implementation_session(
                    changed2,approved=True,approver_actor="human-approver",
                    approval_refs=["approval:1"],
                )
        finally:
            tmp.cleanup()

    def test_approver_must_be_independent_from_developer_roles(self):
        tmp, snapshot, package, correction, confirmed = self._fixture()
        try:
            envelope = build_implementation_envelope(snapshot, package, confirmed)
            ready = prepare_implementation_readiness(
                envelope,rollback_plan="Reverter mudança.",
                builder_actor="builder",reviewer_actor="reviewer",breaker_actor="breaker",
                readiness_refs=["ready:1"],
            )
            with self.assertRaises(ValueError):
                approve_implementation_session(
                    ready,approved=True,approver_actor=" BUILDER ",
                    approval_refs=["approval:1"],
                )
        finally:
            tmp.cleanup()

    def test_lineage_mismatch_fails_closed(self):
        tmp, snapshot, package, correction, confirmed = self._fixture()
        try:
            broken = dict(package)
            broken["package_id"] = "DEVPACK-DIFFERENT"
            with self.assertRaises(ValueError):
                build_implementation_envelope(snapshot, broken, confirmed)
        finally:
            tmp.cleanup()


if __name__ == "__main__":
    unittest.main()
