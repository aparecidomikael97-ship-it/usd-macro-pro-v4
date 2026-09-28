"""Principal authority and synthetic git-object provenance.

Display labels are not identity. Fixture SHAs are claims, not observations.
These tests do not read git objects, start a process, or authorize execution.
"""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import tempfile
import unittest

from atlasquant_aion_developer_builder_sandbox import build_builder_sandbox_request
from atlasquant_aion_developer_content_attestation import (
    GIT_OBJECT_SOURCE_PROBE,
    GIT_OBJECT_SOURCE_SYNTHETIC,
    STRUCTURAL_BASELINE_COMMIT_SHA,
    STRUCTURAL_BASELINE_TREE_SHA,
    STRUCTURAL_CANDIDATE_COMMIT_SHA,
    STRUCTURAL_CANDIDATE_TREE_SHA,
    VERIFICATION_METHOD,
    attestation_for_documents,
    build_content_attestation,
)
from atlasquant_aion_developer_correction import build_correction_plan
from atlasquant_aion_developer_diagnostics import diagnose_failure
from atlasquant_aion_developer_evidence_gate import (
    confirm_root_cause_human_review,
    evaluate_evidence_promotion,
)
from atlasquant_aion_developer_implementation import (
    AUTH_SCHEMA,
    approve_implementation_session,
    build_implementation_envelope,
    prepare_implementation_readiness,
)
from atlasquant_aion_developer_intelligence import scan_repository
from atlasquant_aion_developer_manifest import (
    authorization_manifest_id,
    expected_builder_request_id,
    implementation_readiness_manifest_id,
    structural_request_roles,
)
from atlasquant_aion_developer_package import build_developer_package
from atlasquant_aion_developer_runner_contract import build_runner_contract
from atlasquant_aion_developer_sandbox_preflight import build_sandbox_preflight
from test_atlasquant_aion_developer_attestation_pinning import (
    _builder,
    _patch,
    _preflight,
)


_ROLE_IDS = {
    "builder_principal_id": "prn_builder01",
    "reviewer_principal_id": "prn_reviewer1",
    "breaker_principal_id": "prn_breaker01",
}
_APPROVER = "prn_approver1"
_FALSE_FLAGS = (
    "execution_authorized",
    "executor_attached",
    "commands_executed",
    "writes_files",
    "runs_tests",
    "network_called",
    "subprocess_called",
    "automatic_commit",
    "automatic_merge",
    "automatic_deploy",
    "production_change_allowed",
    "real_trading_enabled",
    "content_binding_independently_verified",
    "executable_pinning_verified",
    "os_sandbox_verified",
    "child_process_policy_verified",
    "symlink_physical_boundary_verified",
    "hardlink_physical_boundary_verified",
)


def _envelope():
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
        reviewer_actor="human-reviewer",
        review_evidence_refs=["review:1"],
    )
    envelope = build_implementation_envelope(snapshot, package, confirmed)
    return tmp, snapshot, envelope


def _ready(envelope, **overrides):
    params = {
        "rollback_plan": "Reverter a mudanca logica.",
        "builder_actor": "Alice",
        "reviewer_actor": "Bob",
        "breaker_actor": "Cara",
        "readiness_refs": ["ready:1"],
        **_ROLE_IDS,
    }
    params.update(overrides)
    return prepare_implementation_readiness(envelope, **params)


def _approve(ready, **overrides):
    params = {
        "approved": True,
        "approver_actor": "human-approver",
        "approval_refs": ["approval:1"],
        "approver_principal_id": _APPROVER,
    }
    params.update(overrides)
    return approve_implementation_session(ready, **params)


def _attestation_payload(**overrides):
    payload = {
        "builder_request_id": "DEVBUILD-FIXTURE000001",
        "test_contract_manifest_id": "DEVTEST-FIXTURE000001",
        "preflight_id": "DEVPREF-FIXTURE000001",
        "patch_validation_id": "DEVPATCHVAL-1",
        "patch_digest": "DEVPATCH-ABC",
        "baseline_ref": "main@aaa",
        "candidate_ref": "cursor/fix@bbb",
        "baseline_commit_sha": STRUCTURAL_BASELINE_COMMIT_SHA,
        "candidate_commit_sha": STRUCTURAL_CANDIDATE_COMMIT_SHA,
        "baseline_tree_sha": STRUCTURAL_BASELINE_TREE_SHA,
        "candidate_tree_sha": STRUCTURAL_CANDIDATE_TREE_SHA,
        "verification_method": VERIFICATION_METHOD,
        "verification_evidence_refs": ["evidence:structural:1"],
        "git_object_source": GIT_OBJECT_SOURCE_SYNTHETIC,
        "attestor_principal_id": "prn_attestor1",
    }
    payload.update(overrides)
    return payload


class PrincipalIntegrationTests(unittest.TestCase):
    def test_readiness_rejects_missing_builder_principal(self):
        tmp, _snapshot, envelope = _envelope()
        try:
            with self.assertRaises(ValueError):
                _ready(envelope, builder_principal_id=None)
        finally:
            tmp.cleanup()

    def test_readiness_rejects_missing_reviewer_principal(self):
        tmp, _snapshot, envelope = _envelope()
        try:
            with self.assertRaises(ValueError):
                _ready(envelope, reviewer_principal_id=None)
        finally:
            tmp.cleanup()

    def test_readiness_rejects_missing_breaker_principal(self):
        tmp, _snapshot, envelope = _envelope()
        try:
            with self.assertRaises(ValueError):
                _ready(envelope, breaker_principal_id=None)
        finally:
            tmp.cleanup()

    def test_readiness_rejects_malformed_principal(self):
        tmp, _snapshot, envelope = _envelope()
        try:
            with self.assertRaises(ValueError):
                _ready(envelope, builder_principal_id="not-a-principal")
            with self.assertRaises(ValueError):
                _ready(envelope, reviewer_principal_id="PRN_REVIEWER1")
        finally:
            tmp.cleanup()

    def test_same_principal_with_different_displays_is_rejected(self):
        tmp, _snapshot, envelope = _envelope()
        try:
            with self.assertRaises(ValueError):
                _ready(
                    envelope,
                    builder_actor="Alice",
                    reviewer_actor="Bob",
                    builder_principal_id="prn_shared001",
                    reviewer_principal_id="prn_shared001",
                )
        finally:
            tmp.cleanup()

    def test_cyrillic_display_with_same_principal_is_rejected(self):
        tmp, _snapshot, envelope = _envelope()
        try:
            with self.assertRaises(ValueError):
                _ready(
                    envelope,
                    builder_actor="Alice",
                    reviewer_actor="\u0410lice",
                    builder_principal_id="prn_shared001",
                    reviewer_principal_id="prn_shared001",
                )
        finally:
            tmp.cleanup()

    def test_identical_displays_stay_distinct_when_principals_differ(self):
        tmp, _snapshot, envelope = _envelope()
        try:
            ready = _ready(
                envelope,
                builder_actor="Alice",
                reviewer_actor="Alice",
                breaker_actor="Alice",
            )
        finally:
            tmp.cleanup()
        self.assertTrue(ready["readiness"]["roles_independent"])
        self.assertEqual(ready["readiness"]["builder_actor"], "Alice")
        self.assertNotEqual(
            ready["readiness"]["builder_principal_id"],
            ready["readiness"]["reviewer_principal_id"],
        )

    def test_approver_principal_cannot_match_builder(self):
        tmp, _snapshot, envelope = _envelope()
        try:
            ready = _ready(envelope)
            with self.assertRaises(ValueError):
                _approve(ready, approver_actor="other-label", approver_principal_id="prn_builder01")
        finally:
            tmp.cleanup()

    def test_approver_principal_cannot_match_reviewer(self):
        tmp, _snapshot, envelope = _envelope()
        try:
            ready = _ready(envelope)
            with self.assertRaises(ValueError):
                _approve(ready, approver_actor="Alice", approver_principal_id="prn_reviewer1")
        finally:
            tmp.cleanup()

    def test_approver_principal_cannot_match_breaker(self):
        tmp, _snapshot, envelope = _envelope()
        try:
            ready = _ready(envelope)
            with self.assertRaises(ValueError):
                _approve(ready, approver_principal_id="prn_breaker01")
        finally:
            tmp.cleanup()

    def test_principal_mutation_after_readiness_manifest_is_rejected(self):
        tmp, _snapshot, envelope = _envelope()
        try:
            ready = _ready(envelope)
            changed = deepcopy(ready)
            changed["readiness"] = dict(changed["readiness"])
            changed["readiness"]["builder_principal_id"] = "prn_otherbld"
            with self.assertRaises(ValueError):
                _approve(changed)
        finally:
            tmp.cleanup()

    def test_principal_mutation_after_authorization_is_rejected(self):
        tmp, snapshot, envelope = _envelope()
        try:
            approved = _approve(_ready(envelope))
            changed = deepcopy(approved)
            changed["authorization"] = dict(changed["authorization"])
            changed["authorization"]["builder_principal_id"] = "prn_otherbld"
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

    def test_builder_request_principal_must_match_authorization(self):
        tmp, snapshot, envelope = _envelope()
        try:
            approved = _approve(_ready(envelope))
            changed = deepcopy(approved)
            auth = dict(changed["authorization"])
            auth["builder_principal_id"] = "prn_otherbld"
            auth["authorization_id"] = authorization_manifest_id(changed, auth)
            changed["authorization"] = auth
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

    def test_legacy_authorization_without_principals_fails_closed(self):
        tmp, snapshot, envelope = _envelope()
        try:
            approved = _approve(_ready(envelope))
            legacy = deepcopy(approved)
            auth = dict(legacy["authorization"])
            auth["schema"] = "ATLASQUANT_AION_DEVELOPER_IMPLEMENTATION_AUTH_V1"
            for field in (
                "builder_principal_id",
                "reviewer_principal_id",
                "breaker_principal_id",
                "approver_principal_id",
            ):
                auth.pop(field, None)
            legacy["authorization"] = auth
            with self.assertRaises(ValueError):
                build_builder_sandbox_request(
                    snapshot,
                    legacy,
                    branch="cursor/admin-fix",
                    baseline_ref="main@a",
                    candidate_ref="cursor/admin-fix@b",
                )
        finally:
            tmp.cleanup()

    def test_display_only_change_does_not_change_authorization_identity(self):
        tmp, snapshot, envelope = _envelope()
        try:
            ready = _ready(envelope, builder_actor="Alice")
            sealed = ready["readiness_manifest_id"]
            relabeled = deepcopy(ready)
            relabeled["readiness"] = dict(relabeled["readiness"])
            relabeled["readiness"]["builder_actor"] = "Completely Different"
            self.assertEqual(implementation_readiness_manifest_id(relabeled), sealed)
            approved = _approve(relabeled, approver_actor="Ann")
            other_label = deepcopy(approved)
            other_label["authorization"] = dict(other_label["authorization"])
            other_label["authorization"]["approver_actor"] = "Anne"
            self.assertEqual(
                authorization_manifest_id(other_label, other_label["authorization"]),
                approved["authorization"]["authorization_id"],
            )
            request = build_builder_sandbox_request(
                snapshot,
                other_label,
                branch="cursor/admin-fix",
                baseline_ref="main@a",
                candidate_ref="cursor/admin-fix@b",
            )
            display_only = deepcopy(request)
            display_only["roles"] = dict(display_only["roles"])
            display_only["roles"]["builder_actor"] = "Not Alice"
            self.assertEqual(expected_builder_request_id(display_only), request["request_id"])
        finally:
            tmp.cleanup()
        self.assertEqual(approved["authorization"]["schema"], AUTH_SCHEMA)
        self.assertEqual(approved["authorization"]["approver_principal_id"], _APPROVER)
        for flag in _FALSE_FLAGS:
            if flag in approved:
                self.assertIs(approved[flag], False)

    def test_principal_change_changes_manifest_id(self):
        tmp, _snapshot, envelope = _envelope()
        try:
            ready = _ready(envelope)
            sealed = ready["readiness_manifest_id"]
            changed = deepcopy(ready)
            changed["readiness"] = dict(changed["readiness"])
            changed["readiness"]["builder_actor"] = ready["readiness"]["builder_actor"]
            changed["readiness"]["builder_principal_id"] = "prn_otherbld"
            self.assertNotEqual(implementation_readiness_manifest_id(changed), sealed)
            approved = _approve(ready)
            auth_changed = deepcopy(approved)
            auth_changed["authorization"] = dict(auth_changed["authorization"])
            auth_changed["authorization"]["approver_actor"] = approved["authorization"]["approver_actor"]
            auth_changed["authorization"]["approver_principal_id"] = "prn_otherapp"
            self.assertNotEqual(
                authorization_manifest_id(auth_changed, auth_changed["authorization"]),
                approved["authorization"]["authorization_id"],
            )
        finally:
            tmp.cleanup()


class ShaProvenanceTests(unittest.TestCase):
    def test_placeholder_with_synthetic_source_is_structurally_bound(self):
        sealed = build_content_attestation(_attestation_payload())
        self.assertEqual(sealed["git_object_source"], GIT_OBJECT_SOURCE_SYNTHETIC)
        self.assertTrue(sealed["content_binding_structurally_bound"])
        self.assertFalse(sealed["content_binding_independently_verified"])
        self.assertEqual(sealed["baseline_commit_sha"], "a" * 40)
        self.assertNotEqual(sealed["state"], "READY_FOR_EXECUTION")

    def test_placeholder_with_external_probe_is_rejected(self):
        with self.assertRaises(ValueError):
            build_content_attestation(_attestation_payload(
                git_object_source=GIT_OBJECT_SOURCE_PROBE,
            ))

    def test_real_looking_sha_stays_a_synthetic_claim(self):
        sealed = build_content_attestation(_attestation_payload(
            baseline_commit_sha="0123456789abcdef" * 2 + "01234567",
            candidate_commit_sha="fedcba9876543210" * 2 + "fedcba98",
            baseline_tree_sha="1111111111111111" * 2 + "11111111",
            candidate_tree_sha="2222222222222222" * 2 + "22222222",
        ))
        self.assertEqual(len("0123456789abcdef" * 2 + "01234567"), 40)
        self.assertEqual(sealed["git_object_source"], GIT_OBJECT_SOURCE_SYNTHETIC)
        self.assertFalse(sealed["content_binding_independently_verified"])
        self.assertTrue(sealed["content_binding_structurally_bound"])

    def test_external_probe_without_a_real_probe_is_rejected(self):
        with self.assertRaises(ValueError):
            build_content_attestation(_attestation_payload(
                git_object_source=GIT_OBJECT_SOURCE_PROBE,
                baseline_commit_sha="0123456789abcdef" * 2 + "01234567",
                candidate_commit_sha="fedcba9876543210" * 2 + "fedcba98",
                baseline_tree_sha="1111111111111111" * 2 + "11111111",
                candidate_tree_sha="2222222222222222" * 2 + "22222222",
                verification_evidence_refs=["evidence:probe:claimed"],
                content_binding_independently_verified=False,
            ))

    def test_source_mutation_after_attestation_id_is_rejected(self):
        sealed = build_content_attestation(_attestation_payload())
        mutated = dict(sealed)
        mutated["git_object_source"] = GIT_OBJECT_SOURCE_PROBE
        with self.assertRaises(ValueError):
            build_content_attestation(mutated)

    def test_stolen_attestation_with_altered_source_is_rejected(self):
        builder = _builder()
        preflight = _preflight(builder)
        patch = _patch(builder, preflight)
        original = attestation_for_documents(builder, preflight, patch)
        other = attestation_for_documents(
            builder,
            preflight,
            patch,
            git_object_source=GIT_OBJECT_SOURCE_SYNTHETIC,
            verification_evidence_refs=["evidence:other:1"],
        )
        stolen = dict(other)
        stolen["git_object_source"] = GIT_OBJECT_SOURCE_PROBE
        stolen["content_attestation_id"] = original["content_attestation_id"]
        with self.assertRaises(ValueError):
            build_runner_contract(
                builder,
                preflight,
                patch,
                content_attestation=stolen,
                human_patch_reviewed=True,
                human_patch_reviewer="reviewer-1",
                human_patch_review_refs=["review:patch:1"],
            )

    def test_caller_cannot_promote_independent_verification(self):
        with self.assertRaises(ValueError):
            build_content_attestation(_attestation_payload(
                content_binding_independently_verified=True,
            ))

    def test_invalid_git_object_source_is_rejected(self):
        with self.assertRaises(ValueError):
            build_content_attestation(_attestation_payload(git_object_source="OBSERVED"))

    def test_missing_git_object_source_is_rejected(self):
        payload = _attestation_payload()
        payload.pop("git_object_source")
        with self.assertRaises(ValueError):
            build_content_attestation(payload)

    def test_legacy_attestation_without_provenance_is_rejected(self):
        payload = _attestation_payload()
        payload.pop("git_object_source")
        payload["schema"] = "ATLASQUANT_AION_DEVELOPER_CONTENT_ATTESTATION_V1"
        with self.assertRaises(ValueError):
            build_content_attestation(payload)
        builder = _builder()
        self.assertEqual(
            builder["roles"]["builder_principal_id"],
            structural_request_roles()["builder_principal_id"],
        )
        preflight = _preflight(builder)
        patch = _patch(builder, preflight)
        legacy = attestation_for_documents(builder, preflight, patch)
        legacy = dict(legacy)
        legacy.pop("git_object_source")
        legacy["schema"] = "ATLASQUANT_AION_DEVELOPER_CONTENT_ATTESTATION_V1"
        with self.assertRaises(ValueError):
            build_runner_contract(
                builder,
                preflight,
                patch,
                content_attestation=legacy,
                human_patch_reviewed=True,
                human_patch_reviewer="reviewer-1",
                human_patch_review_refs=["review:patch:1"],
            )


if __name__ == "__main__":
    unittest.main()
