"""Integrity of the builder/preflight test contract.

The request id and the preflight id are bound to candidate_tests,
mandatory_gates and the deletion/weakening flags. A stale id, a missing
required gate, an arbitrary gate, or a non-list collection fails closed.
"""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import tempfile
import unittest

from atlasquant_aion_developer_builder_sandbox import build_builder_sandbox_request
from atlasquant_aion_developer_content_attestation import attestation_for_documents
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
    REQUIRED_MANDATORY_GATES,
    bind_builder_request_lineage,
    expected_builder_request_id,
)
from atlasquant_aion_developer_package import build_developer_package
from atlasquant_aion_developer_runner_contract import build_runner_contract
from atlasquant_aion_developer_sandbox_preflight import (
    build_sandbox_preflight,
    expected_preflight_id,
)


_CLOSED = (
    "execution_authorized",
    "executor_attached",
    "commands_executed",
    "writes_files",
    "runs_tests",
    "network_called",
    "subprocess_called",
)


def _chain():
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
    gate = evaluate_evidence_promotion(
        correction,
        hypothesis_label=correction["hypotheses"][0]["label"],
        test_id=correction["test_candidates"][0],
        before_state="FAIL",
        after_state="PASS",
        changed_files=["atlasquant_aion_admin.py"],
        evidence_refs=["run:before", "run:after"],
        intervention_summary="Mudanca minima.",
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
        rollback_plan="Reverter a mudanca.",
        builder_actor="builder-a",
        reviewer_actor="reviewer-b",
        breaker_actor="breaker-c",
        readiness_refs=["ready:1"],
    )
    approved = approve_implementation_session(
        ready,
        approved=True,
        approver_actor="human-approver",
        approval_refs=["approval:1"],
    )
    request = build_builder_sandbox_request(
        snapshot,
        approved,
        branch="cursor/admin-fix",
        baseline_ref="main@a",
        candidate_ref="cursor/admin-fix@b",
    )
    return tmp, request


def _preflight(request):
    return build_sandbox_preflight(
        request,
        environment_kind="ISOLATED_WORKTREE",
        environment_id="sandbox-001",
        isolated_worktree=True,
        repository_root_bound=True,
        network_disabled=True,
        secrets_mounted=False,
        command_policy="ALLOWLIST_ONLY",
    )


def _runner(request, preflight, **overrides):
    branch = request["branch_contract"]
    patch = {
        "schema": "ATLASQUANT_AION_DEVELOPER_PATCH_VALIDATION_V1",
        "validation_id": "DEVPATCHVAL-1",
        "state": "READY_FOR_PATCH_REVIEW",
        "builder_request_id": request["request_id"],
        "preflight_id": preflight["preflight_id"],
        "patch_digest": "DEVPATCH-ABC",
        "revision_binding": {
            "baseline_ref": branch["baseline_ref"],
            "candidate_ref": branch["candidate_ref"],
            "refs_match_approved_request": True,
            "revision_content_verified": True,
        },
        "blockers": [],
        "patch_applied": False,
        "execution_authorized": False,
        "executor_attached": False,
    }
    args = {
        "content_attestation": attestation_for_documents(request, preflight, patch),
        "human_patch_reviewed": True,
        "human_patch_reviewer": "reviewer-independent",
        "human_patch_review_refs": ["review:patch:1"],
    }
    args.update(overrides)
    return build_runner_contract(request, preflight, patch, **args)


def _assert_closed(test, document):
    for key in _CLOSED:
        if key in document:
            test.assertFalse(document[key])


class TestContractIntegrityTests(unittest.TestCase):
    def test_valid_builder_request_binds_manifest_and_stays_closed(self):
        tmp, request = _chain()
        try:
            self.assertEqual(request["state"], "READY_FOR_BUILDER_SANDBOX")
            self.assertEqual(request["request_id"], expected_builder_request_id(request))
            self.assertTrue(request["test_contract_manifest_id"].startswith("DEVTEST-"))
            self.assertTrue(set(REQUIRED_MANDATORY_GATES).issubset(request["test_contract"]["mandatory_gates"]))
            preflight = _preflight(request)
            self.assertEqual(preflight["state"], "READY_FOR_EXECUTOR_DESIGN_REVIEW")
            self.assertEqual(preflight["preflight_id"], expected_preflight_id(preflight))
            self.assertEqual(preflight["test_contract_manifest_id"], request["test_contract_manifest_id"])
            runner = _runner(request, preflight)
            self.assertEqual(runner["state"], "READY_FOR_RUNNER_DESIGN_REVIEW")
            _assert_closed(self, request)
            _assert_closed(self, preflight)
            _assert_closed(self, runner)
        finally:
            tmp.cleanup()

    def _reject_stale(self, mutate):
        tmp, request = _chain()
        try:
            preflight = _preflight(request)
            original_id = request["request_id"]
            tampered = deepcopy(request)
            mutate(tampered)
            self.assertEqual(tampered["request_id"], original_id)
            with self.assertRaises(ValueError):
                _preflight(tampered)
            with self.assertRaises(ValueError):
                _runner(tampered, preflight)
        finally:
            tmp.cleanup()

    def test_mutated_candidate_tests_keep_request_id_and_are_rejected(self):
        def mutate(request):
            contract = deepcopy(request["test_contract"])
            contract["candidate_tests"] = list(contract["candidate_tests"]) + [
                str(contract["candidate_tests"][0]) + "::lineage_probe"
            ]
            request["test_contract"] = contract

        self._reject_stale(mutate)

    def test_mutated_mandatory_gates_keep_request_id_and_are_rejected(self):
        def mutate(request):
            contract = deepcopy(request["test_contract"])
            contract["mandatory_gates"] = list(contract["mandatory_gates"]) + ["UI_SMOKE_EXTRA"]
            request["test_contract"] = contract

        self._reject_stale(mutate)

    def test_removed_required_gate_fails_closed_even_after_rebind(self):
        tmp, request = _chain()
        try:
            tampered = deepcopy(request)
            contract = deepcopy(tampered["test_contract"])
            contract["mandatory_gates"] = [
                gate for gate in contract["mandatory_gates"] if gate != "ROLLBACK_REVIEW"
            ]
            tampered["test_contract"] = contract
            rebound = bind_builder_request_lineage(tampered)
            self.assertEqual(rebound["request_id"], expected_builder_request_id(rebound))
            with self.assertRaises(ValueError):
                _preflight(rebound)
            matching = {
                "schema": "ATLASQUANT_AION_DEVELOPER_SANDBOX_PREFLIGHT_V1",
                "state": "READY_FOR_EXECUTOR_DESIGN_REVIEW",
                "builder_request_id": rebound["request_id"],
                "test_contract_manifest_id": rebound["test_contract_manifest_id"],
                "preflight_passed": True,
                "environment_contract": {
                    "environment_kind": "ISOLATED_WORKTREE",
                    "environment_id": "sandbox-001",
                    "isolated_worktree": True,
                    "repository_root_bound": True,
                    "network_disabled": True,
                    "secrets_mounted": False,
                    "command_policy": "ALLOWLIST_ONLY",
                },
                "resource_budget": {
                    "runtime_seconds": 900,
                    "memory_mb": 2048,
                    "output_bytes": 2_000_000,
                    "max_commands": 24,
                },
                "scope": {"requested_files": list(rebound["scope"]["requested_files"])},
                "execution_authorized": False,
                "executor_attached": False,
            }
            matching["preflight_id"] = expected_preflight_id(matching)
            with self.assertRaises(ValueError):
                _runner(rebound, matching)
        finally:
            tmp.cleanup()

    def test_arbitrary_gate_does_not_satisfy_contract(self):
        tmp, request = _chain()
        try:
            tampered = deepcopy(request)
            contract = deepcopy(tampered["test_contract"])
            contract["mandatory_gates"] = ["ANYTHING"]
            tampered["test_contract"] = contract
            rebound = bind_builder_request_lineage(tampered)
            with self.assertRaises(ValueError):
                _preflight(rebound)
            matching = {
                "schema": "ATLASQUANT_AION_DEVELOPER_SANDBOX_PREFLIGHT_V1",
                "state": "READY_FOR_EXECUTOR_DESIGN_REVIEW",
                "builder_request_id": rebound["request_id"],
                "test_contract_manifest_id": rebound["test_contract_manifest_id"],
                "preflight_passed": True,
                "environment_contract": {
                    "environment_kind": "ISOLATED_WORKTREE",
                    "environment_id": "sandbox-001",
                    "isolated_worktree": True,
                    "repository_root_bound": True,
                    "network_disabled": True,
                    "secrets_mounted": False,
                    "command_policy": "ALLOWLIST_ONLY",
                },
                "resource_budget": {
                    "runtime_seconds": 900,
                    "memory_mb": 2048,
                    "output_bytes": 2_000_000,
                    "max_commands": 24,
                },
                "scope": {"requested_files": list(rebound["scope"]["requested_files"])},
                "execution_authorized": False,
                "executor_attached": False,
            }
            matching["preflight_id"] = expected_preflight_id(matching)
            with self.assertRaises(ValueError):
                _runner(rebound, matching)
        finally:
            tmp.cleanup()

    def test_security_collections_reject_scalars_and_non_strings(self):
        tmp, request = _chain()
        try:
            preflight = _preflight(request)
            scalars = ("test_module.py", {"gate": "QUALITY_TESTS"}, 1, True, 1.5, None)
            for value in scalars:
                with self.subTest(field="candidate_tests", value=type(value).__name__):
                    tampered = deepcopy(request)
                    tampered["test_contract"] = deepcopy(tampered["test_contract"])
                    tampered["test_contract"]["candidate_tests"] = value
                    with self.assertRaises(ValueError):
                        _preflight(tampered)
                    with self.assertRaises(ValueError):
                        _runner(tampered, preflight)
                with self.subTest(field="mandatory_gates", value=type(value).__name__):
                    tampered = deepcopy(request)
                    tampered["test_contract"] = deepcopy(tampered["test_contract"])
                    tampered["test_contract"]["mandatory_gates"] = value
                    with self.assertRaises(ValueError):
                        _preflight(tampered)
                    with self.assertRaises(ValueError):
                        _runner(tampered, preflight)
                with self.subTest(field="requested_files", value=type(value).__name__):
                    tampered = deepcopy(request)
                    tampered["scope"] = deepcopy(tampered["scope"])
                    tampered["scope"]["requested_files"] = value
                    with self.assertRaises(ValueError):
                        _preflight(tampered)
                with self.subTest(field="authorized_files", value=type(value).__name__):
                    tampered = deepcopy(request)
                    tampered["scope"] = deepcopy(tampered["scope"])
                    tampered["scope"]["authorized_files"] = value
                    with self.assertRaises(ValueError):
                        _preflight(tampered)
            for field, bad in (
                ("candidate_tests", ["test_module.py", 1]),
                ("mandatory_gates", ["QUALITY_TESTS", None]),
                ("requested_files", ["atlasquant_aion_admin.py", True]),
                ("authorized_files", ["atlasquant_aion_admin.py", 1.5]),
            ):
                with self.subTest(field=field, value="element"):
                    tampered = deepcopy(request)
                    if field in {"candidate_tests", "mandatory_gates"}:
                        tampered["test_contract"] = deepcopy(tampered["test_contract"])
                        tampered["test_contract"][field] = bad
                    else:
                        tampered["scope"] = deepcopy(tampered["scope"])
                        tampered["scope"][field] = bad
                    with self.assertRaises(ValueError):
                        _preflight(tampered)
                    with self.assertRaises(ValueError):
                        _runner(tampered, preflight)
        finally:
            tmp.cleanup()

    def test_review_refs_must_be_an_explicit_string_sequence(self):
        tmp, request = _chain()
        try:
            preflight = _preflight(request)
            with self.assertRaises(ValueError) as caught:
                _runner(request, preflight, human_patch_review_refs="review:1")
            self.assertIn("human_patch_review_refs", str(caught.exception))
            for bad in ({"ref": "review:1"}, 1, True, 1.5, None, ["review:1", 2], ("review:1", None)):
                with self.subTest(value=type(bad).__name__):
                    with self.assertRaises(ValueError):
                        _runner(request, preflight, human_patch_review_refs=bad)
            accepted = _runner(request, preflight, human_patch_review_refs=("review:patch:1",))
            self.assertEqual(accepted["review"]["human_patch_review_refs"], ["review:patch:1"])
            self.assertNotIn("r", accepted["review"]["human_patch_review_refs"])
            _assert_closed(self, accepted)
        finally:
            tmp.cleanup()


if __name__ == "__main__":
    unittest.main()
