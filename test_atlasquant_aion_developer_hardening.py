"""Regression tests for adversarial gaps still open at d1352158."""
from __future__ import annotations

from copy import deepcopy
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
    approve_implementation_session,
    build_implementation_envelope,
    prepare_implementation_readiness,
)
from atlasquant_aion_developer_intelligence import scan_repository
from atlasquant_aion_developer_manifest import (
    canonical_identity,
    implementation_base_manifest_id,
    implementation_readiness_manifest_id,
    release_sensitive_path,
    validate_candidate_ref,
    validate_isolated_branch,
)
from atlasquant_aion_developer_package import build_developer_package
from atlasquant_aion_developer_patch_validation import validate_patch


class AionDeveloperHardeningRegressionTests(unittest.TestCase):
    def test_format_characters_do_not_split_one_identity(self):
        pairs = (
            ("Alice", "alice"),
            ("Alice", "ALICE"),
            ("file", "ﬁle"),
            ("é", "e\u0301"),
            ("Alice", "Ａlice"),
            ("Alice", "Alice\u200b"),
            ("Alice", "Alice\ufeff"),
            ("Alice", "Al\u00adice"),
            ("builder", "bui\u200clder"),
        )
        for left, right in pairs:
            with self.subTest(left=left, right=right):
                self.assertEqual(canonical_identity(left), canonical_identity(right))

    def test_nested_protected_branch_aliases_are_rejected(self):
        blocked = (
            "main",
            "MAIN",
            "master",
            "prod",
            "production",
            "live",
            "refs/heads/main",
            "refs/heads/master",
            "refs/heads/prod",
            "refs/heads/production",
            "refs/heads/live",
            "origin/main",
            "main/hotfix",
            "production/hotfix",
            "refs/heads/refs/heads/main",
            "refs/heads/refs/heads/production",
            "heads/main",
            "main.git",
            "main.git.git",
            "production.git",
        )
        for branch in blocked:
            with self.subTest(branch=branch):
                with self.assertRaises(ValueError):
                    validate_isolated_branch(branch)
        tmp = tempfile.TemporaryDirectory()
        try:
            root = Path(tmp.name)
            (root / "module.py").write_text("VALUE = 1\n", encoding="utf-8")
            snapshot = scan_repository(root)
            with self.assertRaises(ValueError):
                build_developer_package(
                    "pedido",
                    snapshot,
                    branch="refs/heads/refs/heads/main",
                    baseline_ref="base@a",
                    candidate_ref="refs/heads/refs/heads/main@c",
                    created_at="2026-09-27T12:00:00+00:00",
                )
        finally:
            tmp.cleanup()

    def test_candidate_must_stay_on_the_isolated_branch(self):
        for candidate in ("main", "main@c", "cursor/other@c", "CURSOR/admin-fix@c"):
            with self.subTest(candidate=candidate):
                with self.assertRaises(ValueError):
                    validate_candidate_ref(candidate, "cursor/admin-fix")
        self.assertEqual(
            validate_candidate_ref("cursor/admin-fix@c", "cursor/admin-fix"),
            "cursor/admin-fix@c",
        )
        with self.assertRaises(ValueError):
            validate_candidate_ref("cursor/admin-fix@c", "cursor/admin-fix@c")

    def test_deploy_surfaces_require_release_review(self):
        for path in (
            "docs/release/NOTES.md",
            "release/app.yaml",
            "deploy/app.yaml",
            "deployment/app.yaml",
            "scripts/release/go.sh",
            "scripts/deploy/go.sh",
            "docs/deployment/notes.md",
            ".github/workflows/quality-tests.yml",
        ):
            with self.subTest(path=path):
                self.assertTrue(release_sensitive_path(path))
        self.assertFalse(release_sensitive_path("atlasquant_aion_admin.py"))

    def test_added_skip_or_expected_failure_blocks_patch_review(self):
        request = {
            "schema": "ATLASQUANT_AION_DEVELOPER_BUILDER_SANDBOX_REQUEST_V1",
            "request_id": "DEVBUILD-1",
            "state": "READY_FOR_BUILDER_SANDBOX",
            "branch_contract": {
                "branch": "cursor/safe",
                "baseline_ref": "base@a",
                "candidate_ref": "cursor/safe@c",
            },
            "scope": {
                "requested_files": ["test_module.py"],
                "authorized_files": ["test_module.py"],
            },
            "blockers": [],
            "execution_authorized": False,
            "executor_attached": False,
        }
        preflight = {
            "schema": "ATLASQUANT_AION_DEVELOPER_SANDBOX_PREFLIGHT_V1",
            "preflight_id": "DEVPREF-1",
            "builder_request_id": "DEVBUILD-1",
            "state": "READY_FOR_EXECUTOR_DESIGN_REVIEW",
            "preflight_passed": True,
            "execution_authorized": False,
            "executor_attached": False,
        }
        patches = (
            "+@unittest.skip('bypass')\n",
            "+@unittest.expectedFailure\n",
            "+pytest.skip('bypass')\n",
            "+@pytest.mark.xfail\n",
        )
        for added in patches:
            patch = (
                "diff --git a/test_module.py b/test_module.py\n"
                "--- a/test_module.py\n+++ b/test_module.py\n"
                "@@ -1 +1,2 @@\n def test_guard():\n"
                + added
            )
            with self.subTest(added=added.strip()):
                out = validate_patch(
                    request, preflight, patch,
                    baseline_ref="base@a", candidate_ref="cursor/safe@c",
                )
                self.assertEqual(out["state"], "BLOCKED")
                self.assertIn("TEST_DELETION_OR_WEAKENING_NOT_ALLOWED", out["blockers"])
                self.assertFalse(out["execution_authorized"])
                self.assertFalse(out["writes_files"])
                self.assertFalse(out["runs_tests"])

    def test_recomputed_manifest_cannot_authorize_test_removal(self):
        tmp = tempfile.TemporaryDirectory()
        try:
            root = Path(tmp.name)
            (root / "atlasquant_aion_admin.py").write_text("def render():\n    return True\n", encoding="utf-8")
            (root / "test_atlasquant_aion_admin.py").write_text(
                "import atlasquant_aion_admin\ndef test_render():\n    assert atlasquant_aion_admin.render()\n",
                encoding="utf-8",
            )
            snapshot = scan_repository(root)
            package = build_developer_package(
                "Corrigir admin", snapshot, branch="cursor/admin-fix",
                baseline_ref="base@a", candidate_ref="cursor/admin-fix@b",
                changed_paths=["atlasquant_aion_admin.py"], created_at="2026-09-27T12:00:00+00:00",
            )
            diagnostic = diagnose_failure(
                snapshot,
                "AssertionError: mismatch\nFAILED test_atlasquant_aion_admin.py::test_render\n"
                f'File "{root / "atlasquant_aion_admin.py"}", line 1\n',
            )
            correction = build_correction_plan(snapshot, diagnostic, package)
            gate = evaluate_evidence_promotion(
                correction,
                hypothesis_label=correction["hypotheses"][0]["label"],
                test_id=correction["test_candidates"][0],
                before_state="FAIL", after_state="PASS",
                changed_files=["atlasquant_aion_admin.py"],
                evidence_refs=["run:before", "run:after"],
                intervention_summary="Mudanca minima.",
                scope_preserved=True,
                snapshot_digest=snapshot["snapshot_digest"],
                diagnostic_id=diagnostic["diagnostic_id"],
            )
            confirmed = confirm_root_cause_human_review(
                correction, gate, approved=True, reviewer_actor="cause-reviewer",
                review_evidence_refs=["review:cause"],
            )
            envelope = build_implementation_envelope(snapshot, package, confirmed)
            ready = prepare_implementation_readiness(
                envelope, rollback_plan="Reverter a mudanca.",
                builder_actor="builder-a", reviewer_actor="reviewer-b", breaker_actor="breaker-c",
                readiness_refs=["ready:1"],
            )
            weakened = deepcopy(ready)
            weakened["test_contract"] = deepcopy(weakened["test_contract"])
            weakened["test_contract"]["candidate_tests"] = []
            weakened["test_contract"]["test_deletion_allowed"] = True
            weakened["test_contract"]["test_weakening_allowed"] = True
            weakened["envelope_manifest_id"] = implementation_base_manifest_id(weakened)
            weakened["readiness_manifest_id"] = implementation_readiness_manifest_id(weakened)
            with self.assertRaises(ValueError):
                approve_implementation_session(
                    weakened, approved=True, approver_actor="human-approver",
                    approval_refs=["approval:1"],
                )
        finally:
            tmp.cleanup()


if __name__ == "__main__":
    unittest.main()
