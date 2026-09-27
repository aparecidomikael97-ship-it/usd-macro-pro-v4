from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from atlasquant_aion_developer_builder_sandbox import (
    SCHEMA,
    build_builder_sandbox_request,
)
from atlasquant_aion_developer_correction import build_correction_plan
from atlasquant_aion_developer_diagnostics import diagnose_failure
from atlasquant_aion_developer_evidence_gate import (
    confirm_root_cause_human_review,
    evaluate_evidence_promotion,
)
from atlasquant_aion_developer_implementation import (
    approve_implementation_session,
    build_implementation_envelope,
    prepare_implementation_readiness,
)
from atlasquant_aion_developer_intelligence import scan_repository
from atlasquant_aion_developer_package import build_developer_package


class AionDeveloperBuilderSandboxTests(unittest.TestCase):
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
            reviewer_actor="root-cause-reviewer",
            review_evidence_refs=["review:cause"],
        )
        envelope = build_implementation_envelope(snapshot, package, confirmed)
        ready = prepare_implementation_readiness(
            envelope,
            rollback_plan="Reverter o commit lógico da mudança.",
            builder_actor="builder-a",
            reviewer_actor="reviewer-b",
            breaker_actor="breaker-c",
            readiness_refs=["ready:scope", "ready:rollback"],
        )
        approved = approve_implementation_session(
            ready,
            approved=True,
            approver_actor="human-approver",
            approval_refs=["approval:implementation"],
        )
        return tmp, snapshot, approved

    def test_builds_bounded_non_executing_request(self):
        tmp, snapshot, implementation = self._fixture()
        try:
            out = build_builder_sandbox_request(
                snapshot,
                implementation,
                branch="cursor/admin-fix",
                baseline_ref="main@a",
                candidate_ref="cursor/admin-fix@b",
            )
        finally:
            tmp.cleanup()
        self.assertEqual(out["schema"], SCHEMA)
        self.assertRegex(out["request_id"], r"^DEVBUILD-[0-9A-F]{18}$")
        self.assertEqual(out["state"], "READY_FOR_BUILDER_SANDBOX")
        self.assertEqual(out["roles"]["builder_actor"], "builder-a")
        self.assertTrue(out["roles"]["roles_independent"])
        self.assertTrue(out["branch_contract"]["candidate_bound_to_branch"])
        self.assertFalse(out["branch_contract"]["main_branch_allowed"])
        self.assertFalse(out["scope"]["scope_expansion_allowed"])
        self.assertFalse(out["execution_authorized"])
        self.assertFalse(out["executor_attached"])
        self.assertFalse(out["patch_generated"])

    def test_main_branch_is_rejected(self):
        tmp, snapshot, implementation = self._fixture()
        try:
            with self.assertRaises(ValueError):
                build_builder_sandbox_request(
                    snapshot,
                    implementation,
                    branch="main",
                    baseline_ref="main@a",
                    candidate_ref="main@c",
                )
        finally:
            tmp.cleanup()

    def test_unicode_main_branch_is_rejected(self):
        tmp, snapshot, implementation = self._fixture()
        try:
            with self.assertRaises(ValueError):
                build_builder_sandbox_request(
                    snapshot,
                    implementation,
                    branch="ｍａｉｎ",
                    baseline_ref="main@a",
                    candidate_ref="ｍａｉｎ@c",
                )
        finally:
            tmp.cleanup()

    def test_candidate_ref_must_be_bound_to_isolated_branch(self):
        tmp, snapshot, implementation = self._fixture()
        try:
            with self.assertRaises(ValueError):
                build_builder_sandbox_request(
                    snapshot,
                    implementation,
                    branch="cursor/admin-fix",
                    baseline_ref="main@a",
                    candidate_ref="cursor/other-branch@c",
                )
            out = build_builder_sandbox_request(
                snapshot,
                implementation,
                branch="cursor/admin-fix",
                baseline_ref="main@a",
                candidate_ref="refs/heads/cursor/admin-fix@b",
            )
        finally:
            tmp.cleanup()
        self.assertTrue(out["branch_contract"]["candidate_bound_to_branch"])

    def test_authorized_role_identity_tampering_is_rejected(self):
        tmp, snapshot, implementation = self._fixture()
        try:
            changed = dict(implementation)
            changed["readiness"] = dict(implementation["readiness"])
            changed["readiness"]["reviewer_actor"] = "reviewer-z"
            with self.assertRaises(ValueError):
                build_builder_sandbox_request(
                    snapshot,
                    changed,
                    branch="cursor/admin-fix",
                    baseline_ref="main@a",
                    candidate_ref="cursor/admin-fix@b",
                )
        finally:
            tmp.cleanup()

    def test_approved_revision_contract_blocks_ref_replay(self):
        tmp, snapshot, implementation = self._fixture()
        try:
            with self.assertRaises(ValueError):
                build_builder_sandbox_request(
                    snapshot,implementation,branch="cursor/admin-fix",
                    baseline_ref="other@a",candidate_ref="cursor/admin-fix@b",
                )
            with self.assertRaises(ValueError):
                build_builder_sandbox_request(
                    snapshot,implementation,branch="cursor/admin-fix",
                    baseline_ref="main@a",candidate_ref="cursor/admin-fix@other",
                )
        finally:
            tmp.cleanup()

    def test_authorization_manifest_blocks_post_approval_scope_expansion(self):
        tmp, snapshot, implementation = self._fixture()
        try:
            changed = dict(implementation)
            changed["scope"] = dict(implementation["scope"])
            changed["scope"]["editable_files"] = list(implementation["scope"]["editable_files"]) + ["other.py"]
            with self.assertRaises(ValueError):
                build_builder_sandbox_request(
                    snapshot,changed,branch="cursor/admin-fix",
                    baseline_ref="main@a",candidate_ref="cursor/admin-fix@b",
                )
        finally:
            tmp.cleanup()

    def test_authorization_id_tampering_is_rejected(self):
        tmp, snapshot, implementation = self._fixture()
        try:
            changed = dict(implementation)
            changed["authorization"] = dict(implementation["authorization"])
            changed["authorization"]["authorization_id"] = "DEVAUTH-STOLEN"
            with self.assertRaises(ValueError):
                build_builder_sandbox_request(
                    snapshot,changed,branch="cursor/admin-fix",
                    baseline_ref="main@a",candidate_ref="cursor/admin-fix@b",
                )
        finally:
            tmp.cleanup()

    def test_equivalent_production_branch_families_are_rejected(self):
        tmp, snapshot, implementation = self._fixture()
        try:
            for bad in (
                "refs/heads/production","refs/heads/prod","refs/heads/live",
                "origin/main","main/hotfix","production/hotfix",
            ):
                with self.assertRaises(ValueError):
                    build_builder_sandbox_request(
                        snapshot,implementation,branch=bad,
                        baseline_ref="main@a",candidate_ref=f"{bad}@x",
                    )
        finally:
            tmp.cleanup()

    def test_excess_files_are_rejected_not_truncated(self):
        tmp, snapshot, implementation = self._fixture()
        try:
            changed = dict(implementation)
            changed["scope"] = dict(implementation["scope"])
            changed["scope"]["editable_files"] = [f"f{i}.py" for i in range(120)]
            changed["scope"]["source_files"] = [f"f{i}.py" for i in range(120)]
            with self.assertRaises(ValueError):
                build_builder_sandbox_request(
                    snapshot,changed,branch="cursor/admin-fix",
                    baseline_ref="main@a",candidate_ref="cursor/admin-fix@b",
                    requested_files=[f"f{i}.py" for i in range(120)],
                )
        finally:
            tmp.cleanup()

    def test_scope_expansion_is_rejected(self):
        tmp, snapshot, implementation = self._fixture()
        try:
            with self.assertRaises(ValueError):
                build_builder_sandbox_request(
                    snapshot,
                    implementation,
                    branch="cursor/admin-fix",
                    baseline_ref="main@a",
                    candidate_ref="cursor/admin-fix@b",
                    requested_files=[
                        "atlasquant_aion_admin.py",
                        "not-authorized.py",
                    ],
                )
        finally:
            tmp.cleanup()

    def test_requires_authorized_implementation(self):
        tmp, snapshot, implementation = self._fixture()
        try:
            changed = dict(implementation)
            changed["state"] = "READY_FOR_HUMAN_IMPLEMENTATION_APPROVAL"
            changed["implementation_authorized"] = False
            with self.assertRaises(ValueError):
                build_builder_sandbox_request(
                    snapshot,
                    changed,
                    branch="cursor/admin-fix",
                    baseline_ref="main@a",
                    candidate_ref="cursor/admin-fix@b",
                )
        finally:
            tmp.cleanup()

    def test_request_never_executes_or_writes(self):
        tmp, snapshot, implementation = self._fixture()
        try:
            out = build_builder_sandbox_request(
                snapshot,
                implementation,
                branch="cursor/admin-fix",
                baseline_ref="main@a",
                candidate_ref="cursor/admin-fix@b",
            )
        finally:
            tmp.cleanup()
        for key in (
            "execution_authorized",
            "executor_attached",
            "patch_generated",
            "writes_files",
            "runs_tests",
            "network_called",
            "subprocess_called",
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
