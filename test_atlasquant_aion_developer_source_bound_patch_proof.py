"""Source-bound patch proof. Structural reseal is not this boundary.

The raw patch is a transient argument. These tests do not execute, merge or
deploy, and they do not treat caller input as independent authority.
"""
from __future__ import annotations

from copy import deepcopy
import json
import unittest

from atlasquant_aion_developer_builder_sandbox import structural_builder_sandbox_request
from atlasquant_aion_developer_command_policy import build_command_policy_contract
from atlasquant_aion_developer_content_attestation import attestation_for_documents
from atlasquant_aion_developer_executable_pinning import (
    build_environment_contract,
    build_executable_pinning_spec,
)
from atlasquant_aion_developer_os_sandbox_contract import (
    READY_STATE as OS_READY,
    build_os_sandbox_contract,
)
from atlasquant_aion_developer_os_sandbox_probe_result import (
    READY_STATE as PROBE_READY,
    build_probe_result_contract,
)
from atlasquant_aion_developer_patch_validation import (
    EXPECTED_STRUCTURAL_LIMITATION,
    assert_patch_validation_integrity,
    canonical_patch_document,
    expected_patch_validation_id,
    patch_validation_manifest_id,
    validate_patch,
)
from atlasquant_aion_developer_runner_contract import build_runner_contract
from atlasquant_aion_developer_sandbox_preflight import build_sandbox_preflight
from atlasquant_aion_developer_source_bound_patch_proof import (
    INDEPENDENT_EXTERNAL_VERIFICATION,
    READY_STATE,
    SOURCE_BOUND_VERIFICATION,
    SOURCE_PROVENANCE,
    STRUCTURAL_INTEGRITY,
    VERIFICATION_LAYERS,
    assert_source_bound_patch_proof_record,
    expected_source_bound_patch_proof_id,
    verify_source_bound_patch,
)
from test_atlasquant_aion_developer_attestation_pinning import _pin


def _builder():
    return structural_builder_sandbox_request(
        branch="cursor/safe",
        baseline_ref="main@a",
        candidate_ref="cursor/safe@b",
        requested_files=("module.py", "test_module.py"),
        candidate_tests=("test_module.py",),
    )


def _preflight(builder):
    return build_sandbox_preflight(
        builder,
        environment_kind="ISOLATED_WORKTREE",
        environment_id="sandbox-001",
        isolated_worktree=True,
        repository_root_bound=True,
        network_disabled=True,
        secrets_mounted=False,
        command_policy="ALLOWLIST_ONLY",
    )


def _refs():
    return {"baseline_ref": "main@a", "candidate_ref": "cursor/safe@b"}


def _safe_patch():
    return (
        "diff --git a/module.py b/module.py\n"
        "--- a/module.py\n+++ b/module.py\n"
        "@@ -1 +1 @@\n-x=1\n+x=2 # SOURCE_BOUND_MARKER\n"
    )


def _mode_patch():
    return (
        "diff --git a/module.py b/module.py\n"
        "old mode 100644\n"
        "new mode 100755\n"
        "--- a/module.py\n"
        "+++ b/module.py\n"
        "@@ -1 +1 @@\n"
        "-x=1\n"
        "+x=2\n"
    )


def _secret_patch(secret):
    return (
        "diff --git a/module.py b/module.py\n"
        "--- a/module.py\n+++ b/module.py\n"
        "@@ -1 +1 @@\n-x=1\n+api_key=" + secret + "\n"
    )


def _reseal_ready(document, summary_edits):
    forged = deepcopy(document)
    summary = dict(forged["files"][0])
    summary.update(summary_edits)
    forged["files"] = [summary]
    forged["blockers"] = list(summary["blockers"])
    forged["secret_like_additions"] = summary["secret_additions"]
    forged["changed_lines"] = summary["added_lines"] + summary["deleted_lines"]
    forged["state"] = "READY_FOR_PATCH_REVIEW" if not forged["blockers"] else "BLOCKED"
    forged["validation_id"] = expected_patch_validation_id(forged)
    return forged


class SourceBoundPatchProofTests(unittest.TestCase):
    def setUp(self):
        self.builder = _builder()
        self.preflight = _preflight(self.builder)
        self.raw = _safe_patch()
        self.sealed = validate_patch(self.builder, self.preflight, self.raw, **_refs())

    def _verify(self, sealed=None, raw=None, **refs):
        values = _refs()
        values.update(refs)
        return verify_source_bound_patch(
            self.builder,
            self.preflight,
            self.sealed if sealed is None else sealed,
            self.raw if raw is None else raw,
            **values,
        )

    def test_matching_patch_is_source_bound_and_not_independent(self):
        proof = self._verify()
        self.assertEqual(proof["state"], READY_STATE)
        self.assertEqual(proof["structural_integrity"], STRUCTURAL_INTEGRITY)
        self.assertEqual(proof["source_bound_verification"], SOURCE_BOUND_VERIFICATION)
        self.assertEqual(proof["source_provenance"], SOURCE_PROVENANCE)
        self.assertIs(proof["independent_external_verification"], False)
        self.assertIs(proof["caller_input_is_independent_authority"], False)
        self.assertIs(proof["source_provenance_is_independent_authority"], False)
        self.assertIs(proof["replay_requires_transient_patch"], True)
        self.assertIs(proof["patch_text_included"], False)
        self.assertIs(proof["patch_applied"], False)
        self.assertIs(proof["execution_authorized"], False)
        self.assertEqual(list(proof["verification_layers"]), list(VERIFICATION_LAYERS))
        self.assertNotEqual(STRUCTURAL_INTEGRITY, SOURCE_BOUND_VERIFICATION)
        self.assertNotEqual(SOURCE_PROVENANCE, INDEPENDENT_EXTERNAL_VERIFICATION)
        self.assertEqual(proof["proof_id"], expected_source_bound_patch_proof_id(proof))
        self.assertEqual(proof["validation_id"], self.sealed["validation_id"])
        rendered = json.dumps(proof)
        self.assertNotIn(self.raw, rendered)
        self.assertNotIn("SOURCE_BOUND_MARKER", rendered)
        self.assertNotIn("diff --git", rendered)
        self.assertIn("STRUCTURAL_CONSISTENCY", EXPECTED_STRUCTURAL_LIMITATION)

    def test_caller_claim_is_not_authority(self):
        with self.assertRaisesRegex(ValueError, "not authority"):
            verify_source_bound_patch(
                self.builder,
                self.preflight,
                self.sealed,
                self.raw,
                independent_external_verification=True,
                **_refs(),
            )

    def test_coherent_reseal_passes_structural_integrity_and_fails_source_binding(self):
        raw = _mode_patch()
        sealed = validate_patch(self.builder, self.preflight, raw, **_refs())
        self.assertIn("FILE_MODE_CHANGE_NOT_ALLOWED", sealed["blockers"])
        summary = dict(sealed["files"][0])
        summary["mode_changed"] = False
        summary["blockers"] = [
            item for item in summary["blockers"] if item != "FILE_MODE_CHANGE_NOT_ALLOWED"
        ]
        forged = _reseal_ready(sealed, summary)
        self.assertIs(forged["revision_binding"]["revision_content_verified"], False)
        assert_patch_validation_integrity(forged, self.builder, self.preflight)
        with self.assertRaisesRegex(ValueError, "not derived from the transient patch"):
            self._verify(forged, raw)

    def test_swapped_and_truncated_patches_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "not derived from the transient patch"):
            self._verify(raw=_mode_patch())
        truncated = self.raw[:-8]
        with self.assertRaises(ValueError):
            self._verify(raw=truncated)
        with self.assertRaises(ValueError):
            self._verify(raw="")

    def test_mode_facts_and_secret_counters_fail_against_the_original_patch(self):
        raw = _mode_patch()
        sealed = validate_patch(self.builder, self.preflight, raw, **_refs())
        summary = dict(sealed["files"][0])
        summary["mode_changed"] = False
        summary["blockers"] = []
        forged = _reseal_ready(sealed, summary)
        with self.assertRaisesRegex(ValueError, "not derived from the transient patch"):
            self._verify(forged, raw)

        secret = "source-bound-secret"
        secret_raw = _secret_patch(secret)
        secret_sealed = validate_patch(self.builder, self.preflight, secret_raw, **_refs())
        cleared = dict(secret_sealed["files"][0])
        cleared["secret_additions"] = 0
        cleared["blockers"] = []
        forged_secret = _reseal_ready(secret_sealed, cleared)
        self.assertIs(forged_secret["revision_binding"]["revision_content_verified"], False)
        assert_patch_validation_integrity(forged_secret, self.builder, self.preflight)
        with self.assertRaisesRegex(ValueError, "not derived from the transient patch"):
            self._verify(forged_secret, secret_raw)
        self.assertNotIn(secret, json.dumps(secret_sealed))

    def test_negative_counter_is_rejected(self):
        summary = dict(self.sealed["files"][0])
        summary["added_lines"] = 1001
        summary["deleted_lines"] = -1001
        summary["blockers"] = []
        forged = _reseal_ready(self.sealed, summary)
        with self.assertRaisesRegex(ValueError, "nonnegative"):
            self._verify(forged, self.raw)

    def test_lineage_refs_and_stale_ids_are_rejected(self):
        forged = deepcopy(self.sealed)
        forged["builder_request_id"] = "DEVBUILD-OTHERLINEAGE"
        forged["validation_id"] = expected_patch_validation_id(forged)
        with self.assertRaisesRegex(ValueError, "lineage mismatch"):
            self._verify(forged)

        with self.assertRaisesRegex(ValueError, "revision refs differ"):
            self._verify(candidate_ref="cursor/other@b")

        proof = self._verify()
        stale = deepcopy(proof)
        stale["proof_id"] = "DEVSRCBIND-STALE"
        with self.assertRaisesRegex(ValueError, "proof id mismatch"):
            assert_source_bound_patch_proof_record(
                stale, self.sealed, self.builder, self.preflight,
            )
        rebound = deepcopy(proof)
        rebound["validation_id"] = "DEVPATCHVAL-STALE"
        rebound["proof_id"] = expected_source_bound_patch_proof_id(rebound)
        with self.assertRaisesRegex(ValueError, "validation lineage mismatch"):
            assert_source_bound_patch_proof_record(
                rebound, self.sealed, self.builder, self.preflight,
            )

    def test_unknown_authority_and_false_independent_verification_are_rejected(self):
        proof = self._verify()
        unknown = deepcopy(proof)
        unknown["git_object_verified"] = True
        unknown["proof_id"] = expected_source_bound_patch_proof_id(unknown)
        with self.assertRaisesRegex(ValueError, "unknown source-bound patch proof field"):
            assert_source_bound_patch_proof_record(
                unknown, self.sealed, self.builder, self.preflight,
            )
        claimed = deepcopy(proof)
        claimed["independent_external_verification"] = True
        claimed["proof_id"] = expected_source_bound_patch_proof_id(claimed)
        with self.assertRaisesRegex(ValueError, "independent external verification"):
            assert_source_bound_patch_proof_record(
                claimed, self.sealed, self.builder, self.preflight,
            )

    def test_record_without_bytes_is_not_a_replay_of_the_original_diff(self):
        raw = _mode_patch()
        sealed = validate_patch(self.builder, self.preflight, raw, **_refs())
        summary = dict(sealed["files"][0])
        summary["mode_changed"] = False
        summary["blockers"] = []
        forged = _reseal_ready(sealed, summary)
        proof = self._verify()
        copied = deepcopy(proof)
        copied["validation_id"] = forged["validation_id"]
        copied["patch_digest"] = forged["patch_digest"]
        copied["patch_manifest_id"] = patch_validation_manifest_id(forged)
        copied["proof_id"] = expected_source_bound_patch_proof_id(copied)
        assert_source_bound_patch_proof_record(copied, forged, self.builder, self.preflight)
        with self.assertRaisesRegex(ValueError, "not derived from the transient patch"):
            self._verify(forged, raw)
        self.assertIs(copied["independent_external_verification"], False)
        self.assertIs(copied["replay_requires_transient_patch"], True)
        self.assertEqual(copied["source_provenance"], SOURCE_PROVENANCE)

    def test_synthetic_canonical_document_does_not_match_a_real_patch(self):
        synthetic = canonical_patch_document(self.builder, self.preflight)
        with self.assertRaisesRegex(ValueError, "not derived from the transient patch"):
            self._verify(synthetic, self.raw)

    def test_existing_chain_stays_design_only(self):
        proof = self._verify()
        attestation = attestation_for_documents(self.builder, self.preflight, self.sealed)
        review = dict(
            human_patch_reviewed=True,
            human_patch_reviewer="reviewer-1",
            human_patch_review_refs=["review:patch:1"],
        )
        runner = build_runner_contract(
            self.builder, self.preflight, self.sealed,
            content_attestation=attestation, **review,
        )
        policy = build_command_policy_contract(
            runner,
            builder_request=self.builder,
            preflight=self.preflight,
            patch_validation=self.sealed,
            content_attestation=attestation,
        )
        pinning = build_executable_pinning_spec([
            _pin("python", "/usr/bin/python3", "ab" * 32),
            _pin("git", "/usr/bin/git", "cd" * 32),
        ])
        environment = build_environment_contract()
        sandbox = build_os_sandbox_contract(
            policy, runner, self.builder, self.preflight, self.sealed,
            attestation, pinning, environment,
        )
        result = build_probe_result_contract(
            sandbox, policy, runner, self.builder, self.preflight, self.sealed,
            attestation, pinning, environment,
        )
        self.assertEqual(self.sealed["state"], "READY_FOR_PATCH_REVIEW")
        self.assertEqual(runner["state"], "READY_FOR_RUNNER_DESIGN_REVIEW")
        self.assertEqual(policy["state"], "READY_FOR_EXECUTABLE_PINNING_REVIEW")
        self.assertEqual(sandbox["state"], OS_READY)
        self.assertEqual(result["state"], PROBE_READY)
        for document in (proof, self.sealed, runner, policy, sandbox, result):
            for field in (
                "execution_authorized",
                "subprocess_called",
                "automatic_merge",
                "automatic_deploy",
                "real_trading_enabled",
            ):
                if field in document:
                    self.assertIs(document[field], False, field)


if __name__ == "__main__":
    unittest.main()
