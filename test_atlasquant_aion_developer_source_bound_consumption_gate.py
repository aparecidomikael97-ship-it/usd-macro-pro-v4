"""Source-bound consumption gate. A stored proof record is not replay proof.

The gate requires the transient patch and does not execute, apply, merge,
deploy or trade. Design-only readiness does not call it.
"""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
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
    expected_patch_validation_id,
    patch_validation_manifest_id,
    validate_patch,
)
from atlasquant_aion_developer_runner_contract import build_runner_contract
from atlasquant_aion_developer_sandbox_preflight import build_sandbox_preflight
from atlasquant_aion_developer_source_bound_consumption_gate import (
    CONSUMPTION_BASIS,
    READY_STATE,
    STORED_PROOF_RELATION,
    assert_source_bound_consumption_gate,
    expected_source_bound_consumption_id,
)
from atlasquant_aion_developer_source_bound_patch_proof import (
    READY_STATE as SOURCE_BOUND_PATCH_MATCH,
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
        "@@ -1 +1 @@\n-x=1\n+x=2 # CONSUMPTION_GATE_MARKER\n"
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


_OMITTED = object()


class SourceBoundConsumptionGateTests(unittest.TestCase):
    def setUp(self):
        self.builder = _builder()
        self.preflight = _preflight(self.builder)
        self.raw = _safe_patch()
        self.sealed = validate_patch(self.builder, self.preflight, self.raw, **_refs())
        self.proof = verify_source_bound_patch(
            self.builder, self.preflight, self.sealed, self.raw, **_refs(),
        )

    def _gate(self, sealed=None, raw=_OMITTED, stored_proof=None, **refs):
        values = _refs()
        values.update(refs)
        return assert_source_bound_consumption_gate(
            self.builder,
            self.preflight,
            self.sealed if sealed is None else sealed,
            self.raw if raw is _OMITTED else raw,
            stored_proof=stored_proof,
            **values,
        )

    def test_stored_record_without_patch_is_blocked(self):
        with self.assertRaisesRegex(ValueError, "not replay proof"):
            self._gate(raw=None, stored_proof=self.proof)
        with self.assertRaisesRegex(ValueError, "not replay proof"):
            assert_source_bound_consumption_gate(
                self.builder,
                self.preflight,
                self.sealed,
                self.proof,
                stored_proof=self.proof,
                **_refs(),
            )

    def test_resealed_record_and_adulterated_document_are_blocked(self):
        raw = _mode_patch()
        sealed = validate_patch(self.builder, self.preflight, raw, **_refs())
        summary = dict(sealed["files"][0])
        summary["mode_changed"] = False
        summary["blockers"] = []
        forged = _reseal_ready(sealed, summary)
        copied = deepcopy(self.proof)
        copied["validation_id"] = forged["validation_id"]
        copied["patch_digest"] = forged["patch_digest"]
        copied["patch_manifest_id"] = patch_validation_manifest_id(forged)
        copied["proof_id"] = expected_source_bound_patch_proof_id(copied)
        assert_source_bound_patch_proof_record(copied, forged, self.builder, self.preflight)
        with self.assertRaisesRegex(ValueError, "not derived from the transient patch"):
            self._gate(forged, raw, stored_proof=copied)
        with self.assertRaisesRegex(ValueError, "not replay proof"):
            self._gate(forged, None, stored_proof=copied)

    def test_legitimate_record_with_different_patch_is_blocked(self):
        with self.assertRaisesRegex(ValueError, "not derived from the transient patch"):
            self._gate(raw=_mode_patch(), stored_proof=self.proof)

    def test_truncated_patch_is_blocked(self):
        with self.assertRaises(ValueError):
            self._gate(raw=self.raw[:-8], stored_proof=self.proof)
        with self.assertRaises(ValueError):
            self._gate(raw="", stored_proof=self.proof)

    def test_swapped_lineage_is_blocked(self):
        forged = deepcopy(self.sealed)
        forged["builder_request_id"] = "DEVBUILD-OTHERLINEAGE"
        forged["validation_id"] = expected_patch_validation_id(forged)
        with self.assertRaisesRegex(ValueError, "lineage mismatch"):
            self._gate(forged, self.raw, stored_proof=self.proof)

    def test_swapped_refs_are_blocked(self):
        with self.assertRaisesRegex(ValueError, "revision refs differ"):
            self._gate(stored_proof=self.proof, candidate_ref="cursor/other@b")

    def test_recomputed_proof_id_does_not_replace_replay(self):
        raw = _mode_patch()
        sealed = validate_patch(self.builder, self.preflight, raw, **_refs())
        summary = dict(sealed["files"][0])
        summary["mode_changed"] = False
        summary["blockers"] = []
        forged = _reseal_ready(sealed, summary)
        copied = deepcopy(self.proof)
        copied["validation_id"] = forged["validation_id"]
        copied["patch_digest"] = forged["patch_digest"]
        copied["patch_manifest_id"] = patch_validation_manifest_id(forged)
        copied["proof_id"] = expected_source_bound_patch_proof_id(copied)
        assert_source_bound_patch_proof_record(copied, forged, self.builder, self.preflight)
        with self.assertRaisesRegex(ValueError, "not replay proof"):
            self._gate(forged, None, stored_proof=copied)

        stale = deepcopy(self.proof)
        stale["proof_id"] = "DEVSRCBIND-RECOMPUTED"
        receipt = self._gate(stored_proof=stale)
        rendered = json.dumps(receipt)
        self.assertEqual(receipt["replay_proof_id"], self.proof["proof_id"])
        self.assertNotIn("DEVSRCBIND-RECOMPUTED", rendered)
        self.assertNotIn(self.raw, rendered)

    def test_caller_independent_verification_is_blocked(self):
        with self.assertRaisesRegex(ValueError, "not authority"):
            assert_source_bound_consumption_gate(
                self.builder,
                self.preflight,
                self.sealed,
                self.raw,
                independent_external_verification=True,
                **_refs(),
            )
        claimed = deepcopy(self.proof)
        claimed["independent_external_verification"] = True
        claimed["proof_id"] = expected_source_bound_patch_proof_id(claimed)
        with self.assertRaisesRegex(ValueError, "independent external verification"):
            self._gate(stored_proof=claimed)

    def test_unknown_authority_field_is_blocked(self):
        with self.assertRaisesRegex(ValueError, "not authority"):
            assert_source_bound_consumption_gate(
                self.builder,
                self.preflight,
                self.sealed,
                self.raw,
                git_object_verified=True,
                **_refs(),
            )
        unknown = deepcopy(self.proof)
        unknown["git_object_verified"] = True
        with self.assertRaisesRegex(ValueError, "unknown source-bound consumption authority field"):
            self._gate(stored_proof=unknown)

    def test_match_state_alone_does_not_release_physical_gate(self):
        with self.assertRaisesRegex(ValueError, "does not release the future physical consumption gate"):
            self._gate(raw=None, stored_proof=SOURCE_BOUND_PATCH_MATCH)
        with self.assertRaisesRegex(ValueError, "does not release the future physical consumption gate"):
            self._gate(raw=None, stored_proof={"state": SOURCE_BOUND_PATCH_MATCH})
        with self.assertRaisesRegex(ValueError, "does not release the future physical consumption gate"):
            assert_source_bound_consumption_gate(
                self.builder,
                self.preflight,
                self.sealed,
                SOURCE_BOUND_PATCH_MATCH,
                **_refs(),
            )
        self.assertEqual(self.proof["state"], SOURCE_BOUND_PATCH_MATCH)
        with self.assertRaisesRegex(ValueError, "not replay proof"):
            self._gate(raw=None, stored_proof=self.proof)

    def test_matching_replay_is_consumption_correspondence_not_execution(self):
        receipt = self._gate()
        with_record = self._gate(stored_proof=self.proof)
        self.assertEqual(receipt, with_record)
        self.assertEqual(receipt["state"], READY_STATE)
        self.assertEqual(receipt["consumption_basis"], CONSUMPTION_BASIS)
        self.assertEqual(receipt["stored_proof_relation"], STORED_PROOF_RELATION)
        self.assertEqual(receipt["consumption_id"], expected_source_bound_consumption_id(receipt))
        self.assertEqual(receipt["replay_proof_id"], self.proof["proof_id"])
        self.assertEqual(receipt["validation_id"], self.sealed["validation_id"])
        self.assertEqual(receipt["builder_request_id"], self.builder["request_id"])
        self.assertEqual(receipt["preflight_id"], self.preflight["preflight_id"])
        self.assertEqual(receipt["baseline_ref"], "main@a")
        self.assertEqual(receipt["candidate_ref"], "cursor/safe@b")
        self.assertIs(receipt["independent_external_verification"], False)
        self.assertIs(receipt["caller_input_is_independent_authority"], False)
        self.assertIs(receipt["stored_proof_is_replay_proof"], False)
        self.assertIs(receipt["stored_proof_is_not_replay_proof"], True)
        self.assertIs(receipt["stored_proof_record_is_consumption_authorization"], False)
        self.assertIs(receipt["source_bound_patch_match_authorizes_physical_consumption"], False)
        self.assertIs(receipt["saved_receipt_authorizes_physical_execution"], False)
        self.assertIs(receipt["consumption_requires_transient_replay"], True)
        self.assertIs(receipt["replay_performed"], True)
        self.assertIs(receipt["patch_text_included"], False)
        self.assertIs(receipt["future_physical_patch_execution_requires_consumption_gate"], True)
        self.assertIs(receipt["design_only_readiness_requires_consumption_gate"], False)
        self.assertIs(receipt["execution_authorized"], False)
        self.assertIs(receipt["physical_execution_authorized"], False)
        self.assertIs(receipt["physical_probe_authorized"], False)
        self.assertIs(receipt["patch_applied"], False)
        self.assertIs(receipt["subprocess_called"], False)
        self.assertIs(receipt["shell_authorized"], False)
        self.assertIs(receipt["filesystem_write_authorized"], False)
        self.assertIs(receipt["network_called"], False)
        self.assertIs(receipt["git_mutation_authorized"], False)
        self.assertIs(receipt["automatic_merge"], False)
        self.assertIs(receipt["automatic_deploy"], False)
        self.assertIs(receipt["real_trading_enabled"], False)
        rendered = json.dumps(receipt)
        self.assertNotIn(self.raw, rendered)
        self.assertNotIn("CONSUMPTION_GATE_MARKER", rendered)
        self.assertNotIn("diff --git", rendered)
        self.assertNotIn(self.proof["proof_id"], json.dumps({
            key: value for key, value in receipt.items() if key != "replay_proof_id"
        }))

    def test_saved_receipt_is_not_later_authorization(self):
        receipt = self._gate()
        with self.assertRaisesRegex(ValueError, "not replay proof"):
            self._gate(raw=None, stored_proof=receipt)
        with self.assertRaisesRegex(ValueError, "unknown source-bound consumption authority field"):
            self._gate(stored_proof=receipt)

    def test_design_only_chain_does_not_require_the_gate(self):
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
        for document in (self.sealed, runner, policy, sandbox, result):
            for field in (
                "execution_authorized",
                "subprocess_called",
                "automatic_merge",
                "automatic_deploy",
                "real_trading_enabled",
            ):
                if field in document:
                    self.assertIs(document[field], False, field)

    def test_gate_module_imports_no_execution_primitives(self):
        text = Path("atlasquant_aion_developer_source_bound_consumption_gate.py").read_text(
            encoding="utf-8",
        )
        self.assertNotIn("import subprocess", text)
        self.assertNotIn("import os", text)
        self.assertNotIn("Popen", text)
        self.assertNotIn("os.system", text)
        self.assertNotIn("shell=True", text)


if __name__ == "__main__":
    unittest.main()
