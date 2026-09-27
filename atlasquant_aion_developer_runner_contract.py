"""Read-only runner contract simulator for AION Developer.

Consumes a Builder Sandbox Request, passing Sandbox Preflight and a read-only
Patch Validation result. It emits an immutable *plan description* for a future
isolated runner. It never executes the plan.

READY means only READY_FOR_RUNNER_DESIGN_REVIEW. It does not mean execution is
authorized. Promotion requires a structural Content Attestation Contract.
content_binding_verified and a free-form content_binding_ref are not evidence.
Independent verification stays false because no external probe runs here. If
the attestation does not match the sealed lineage, or the patch has not been
explicitly reviewed by a human, the simulator fails closed.

No shell, subprocess, filesystem write, network, secret mount, test execution,
commit, merge, deploy, publication, production change or real trading occurs.
"""
from __future__ import annotations

import unicodedata
from typing import Any, Mapping, Sequence

from atlasquant_aion_developer_builder_sandbox import SCHEMA as BUILDER_SCHEMA
from atlasquant_aion_developer_content_attestation import (
    assert_content_attestation_matches,
)
from atlasquant_aion_developer_executable_pinning import SANDBOX_EPHEMERAL_PYCACHE
from atlasquant_aion_developer_patch_validation import SCHEMA as PATCH_SCHEMA
from atlasquant_aion_developer_manifest import (
    assert_builder_request_lineage,
    assert_required_mandatory_gates,
    require_string_sequence,
    stable_digest,
)
from atlasquant_aion_developer_sandbox_preflight import (
    ALLOWED_COMMAND_POLICY,
    SCHEMA as PREFLIGHT_SCHEMA,
    canonical_repository_relative_path,
    expected_preflight_id,
    validate_resource_budget,
)
from atlasquant_aion_observability import redact_text

SCHEMA = "ATLASQUANT_AION_DEVELOPER_RUNNER_CONTRACT_V1"
MAX_TEST_TARGETS = 80
MAX_MANDATORY_GATES = 40
MAX_REVIEW_REFS = 40


def _clean(value: Any, limit: int = 1200) -> str:
    return " ".join(redact_text(value).replace("\x00", "").split())[:limit]


def _unique(values: Sequence[Any] | None, limit: int) -> list[str]:
    out: list[str] = []
    for raw in list(values or [])[:limit * 2]:
        text = _clean(raw, 500)
        if text and text not in out:
            out.append(text)
        if len(out) >= limit:
            break
    return out


_COMMAND_STEP_FIELDS = (
    "step",
    "executable",
    "argv",
    "shell",
    "cwd",
    "network",
    "writes_repo",
)
_OPTIONAL_STEP_FIELDS = (
    "writes_repository",
    "may_write_ephemeral_cache",
    "pycache_prefix",
)
_BUDGET_FIELDS = ("runtime_seconds", "memory_mb", "output_bytes", "max_commands")
_RUNNER_FALSE_FLAGS = (
    "shell_allowed",
    "network_allowed",
    "secrets_allowed",
    "repo_write_allowed",
    "path_lookup_allowed",
    "parent_environment_inheritance",
    "caller_environment_overrides_allowed",
    "content_binding_independently_verified",
    "executable_pinning_verified",
    "os_sandbox_verified",
    "child_process_policy_verified",
    "symlink_physical_boundary_verified",
    "hardlink_physical_boundary_verified",
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
    "tool_output_is_authority",
)


def _step_manifest(step: Any) -> Any:
    if not isinstance(step, Mapping):
        return {"non_mapping": True}
    row = {field: step.get(field) for field in _COMMAND_STEP_FIELDS}
    argv = row.get("argv")
    if isinstance(argv, (list, tuple)):
        row["argv"] = list(argv)
    for field in _OPTIONAL_STEP_FIELDS:
        if field in step:
            row[field] = step.get(field)
    return row


def runner_contract_manifest(contract: Mapping[str, Any]) -> dict[str, Any]:
    """Canonical security and semantic fields. Ids are not inputs."""
    if not isinstance(contract, Mapping):
        raise ValueError("runner contract must be an object")
    lineage = contract.get("lineage") if isinstance(contract.get("lineage"), Mapping) else {}
    review = contract.get("review") if isinstance(contract.get("review"), Mapping) else {}
    tests = contract.get("tests") if isinstance(contract.get("tests"), Mapping) else {}
    budget = contract.get("resource_budget") if isinstance(contract.get("resource_budget"), Mapping) else {}
    review_refs = review.get("human_patch_review_refs")
    targets = tests.get("targets")
    gates = tests.get("mandatory_gates")
    return {
        "lineage": {
            "builder_request_id": lineage.get("builder_request_id"),
            "preflight_id": lineage.get("preflight_id"),
            "patch_validation_id": lineage.get("patch_validation_id"),
            "patch_digest": lineage.get("patch_digest"),
            "content_attestation_id": lineage.get("content_attestation_id"),
            "content_binding_structurally_bound": lineage.get("content_binding_structurally_bound"),
            "content_binding_independently_verified": lineage.get("content_binding_independently_verified"),
        },
        "review": {
            "human_patch_reviewed": review.get("human_patch_reviewed"),
            "human_patch_reviewer": review.get("human_patch_reviewer"),
            "human_patch_review_refs": list(review_refs) if isinstance(review_refs, (list, tuple)) else review_refs,
        },
        "tests": {
            "targets": list(targets) if isinstance(targets, (list, tuple)) else targets,
            "mandatory_gates": list(gates) if isinstance(gates, (list, tuple)) else gates,
            "tests_executed": tests.get("tests_executed"),
        },
        "resource_budget": {field: budget.get(field) for field in _BUDGET_FIELDS},
        "command_plan": [
            _step_manifest(step) for step in list(contract.get("command_plan") or [])
        ],
        "command_plan_is_data_only": contract.get("command_plan_is_data_only"),
        "shell_allowed": contract.get("shell_allowed"),
        "network_allowed": contract.get("network_allowed"),
        "secrets_allowed": contract.get("secrets_allowed"),
        "repo_write_allowed": contract.get("repo_write_allowed"),
        "path_lookup_allowed": contract.get("path_lookup_allowed"),
        "parent_environment_inheritance": contract.get("parent_environment_inheritance"),
        "caller_environment_overrides_allowed": contract.get("caller_environment_overrides_allowed"),
        "content_binding_structurally_bound": contract.get("content_binding_structurally_bound"),
        "content_binding_independently_verified": contract.get("content_binding_independently_verified"),
        "executable_pinning_verified": contract.get("executable_pinning_verified"),
        "os_sandbox_verified": contract.get("os_sandbox_verified"),
        "child_process_policy_verified": contract.get("child_process_policy_verified"),
        "symlink_physical_boundary_verified": contract.get("symlink_physical_boundary_verified"),
        "hardlink_physical_boundary_verified": contract.get("hardlink_physical_boundary_verified"),
        "execution_authorized": contract.get("execution_authorized"),
        "executor_attached": contract.get("executor_attached"),
        "commands_executed": contract.get("commands_executed"),
        "writes_files": contract.get("writes_files"),
        "runs_tests": contract.get("runs_tests"),
        "network_called": contract.get("network_called"),
        "subprocess_called": contract.get("subprocess_called"),
        "automatic_commit": contract.get("automatic_commit"),
        "automatic_merge": contract.get("automatic_merge"),
        "automatic_deploy": contract.get("automatic_deploy"),
        "production_change_allowed": contract.get("production_change_allowed"),
        "real_trading_enabled": contract.get("real_trading_enabled"),
        "tool_output_is_authority": contract.get("tool_output_is_authority"),
    }


def runner_contract_manifest_id(contract: Mapping[str, Any]) -> str:
    return stable_digest(runner_contract_manifest(contract), prefix="DEVRMAN-", length=18)


def expected_runner_contract_id(contract: Mapping[str, Any]) -> str:
    """Digest the manifest id. A caller-supplied runner id is not an input."""
    return stable_digest(
        {"runner_contract_manifest_id": runner_contract_manifest_id(contract)},
        prefix="DEVRUN-",
        length=18,
    )


def _canonical_command_plan() -> list[dict[str, Any]]:
    """The only command plan the constructor emits. Callers cannot supply another."""
    return [
        {
            "step": "COMPILE_CHANGED_SCOPE",
            "executable": "python",
            "argv": ["-m", "compileall", "-q", "<AUTHORIZED_CHANGED_SCOPE>"],
            "shell": False,
            "cwd": "<ISOLATED_WORKTREE>",
            "network": False,
            "writes_repo": False,
            "writes_repository": False,
            "may_write_ephemeral_cache": True,
            "pycache_prefix": SANDBOX_EPHEMERAL_PYCACHE,
        },
        {
            "step": "RUN_TARGETED_TESTS",
            "executable": "python",
            "argv": ["-m", "unittest", "-q", "<APPROVED_TEST_TARGETS>"],
            "shell": False,
            "cwd": "<ISOLATED_WORKTREE>",
            "network": False,
            "writes_repo": False,
        },
        {
            "step": "VERIFY_DIFF_CHECK",
            "executable": "git",
            "argv": ["diff", "--check"],
            "shell": False,
            "cwd": "<ISOLATED_WORKTREE>",
            "network": False,
            "writes_repo": False,
        },
    ]


def _require_exact(document: Mapping[str, Any], field: str, expected: Any) -> None:
    if document.get(field) is not expected:
        raise ValueError(f"runner flag {field} is not {expected}")


def _assert_runner_digest(contract: Mapping[str, Any]) -> str:
    """Reject a stale id and any true authority flag.

    This check does not decide that the payload is a legitimate contract.
    Consumers call assert_runner_contract_integrity for that.
    """
    if not isinstance(contract, Mapping):
        raise ValueError("runner contract must be an object")
    if contract.get("schema") != SCHEMA:
        raise ValueError("invalid runner contract")
    if contract.get("command_plan_is_data_only") is not True:
        raise ValueError("command plan must remain data only")
    if contract.get("content_binding_structurally_bound") is not True:
        raise ValueError("runner content binding is not structural")
    for field in _RUNNER_FALSE_FLAGS:
        _require_exact(contract, field, False)
    lineage = contract.get("lineage")
    if not isinstance(lineage, Mapping):
        raise ValueError("runner lineage required")
    if lineage.get("content_binding_structurally_bound") is not True:
        raise ValueError("runner lineage content binding is not structural")
    if lineage.get("content_binding_independently_verified") is not False:
        raise ValueError("independent content verification cannot be claimed")
    tests = contract.get("tests")
    if not isinstance(tests, Mapping) or tests.get("tests_executed") is not False:
        raise ValueError("tests_executed must remain false")
    manifest_id = runner_contract_manifest_id(contract)
    if contract.get("runner_contract_manifest_id") != manifest_id:
        raise ValueError("runner contract manifest mismatch")
    if contract.get("runner_contract_id") != expected_runner_contract_id(contract):
        raise ValueError("runner contract id mismatch")
    return manifest_id


def _assert_runner_semantics(contract: Mapping[str, Any]) -> None:
    """Reject a resealed document whose local security payload is not canonical.

    A freshly computed digest is not evidence that the constructor produced
    the document.
    """
    budget = contract.get("resource_budget")
    validated, blockers = validate_resource_budget(budget if isinstance(budget, Mapping) else None)
    if blockers:
        raise ValueError("resource budget is outside the allowed range")
    if dict(budget) != validated:
        raise ValueError("resource budget has non-canonical fields")
    if contract.get("command_plan") != _canonical_command_plan():
        raise ValueError("runner command plan is not the canonical template")
    if (
        contract.get("state") == "READY_FOR_RUNNER_DESIGN_REVIEW"
        and not list(contract.get("blockers") or [])
    ):
        tests = contract.get("tests") if isinstance(contract.get("tests"), Mapping) else {}
        assert_required_mandatory_gates(
            require_string_sequence(tests.get("mandatory_gates"), "mandatory_gates")
        )


def assert_runner_contract_integrity(contract: Mapping[str, Any]) -> str:
    """Revalidate the runner. A matching id is not legitimacy.

    Authority flags are rejected even after the id is recomputed. The command
    plan, budget and required gates are checked against the local canonical
    contract, not against the caller-supplied digest.
    """
    manifest_id = _assert_runner_digest(contract)
    _assert_runner_semantics(contract)
    return manifest_id


def _bind_runner_contract_ids(contract: dict[str, Any]) -> dict[str, Any]:
    """Constructor helper. Recomputing these ids does not authorize the payload."""
    contract["runner_contract_manifest_id"] = runner_contract_manifest_id(contract)
    contract["runner_contract_id"] = expected_runner_contract_id(contract)
    return contract


def _authorized_files(builder_request: Mapping[str, Any]) -> set[str]:
    scope = (
        builder_request.get("scope")
        if isinstance(builder_request.get("scope"), Mapping)
        else {}
    )
    authorized: set[str] = set()
    for raw in list(scope.get("authorized_files") or []):
        path = canonical_repository_relative_path(raw)
        if path:
            authorized.add(path)
    return authorized


def _classify_test_target(value: Any, authorized: set[str]) -> str:
    """Return '' when the target is safe and bound to an authorized file.

    Membership in authorized_files is the only existence evidence this contract
    accepts. A syntactically valid name outside that set fails closed. This
    function does not stat the filesystem.
    """
    if not isinstance(value, str) or not value or any(unicodedata.category(char) == "Cc" for char in value):
        return "UNSAFE_TEST_TARGET"
    file_part, separator, selector = value.partition("::")
    if separator and (
        not selector
        or "\\" in selector
        or "/" in selector
        or ".." in selector
        or any(unicodedata.category(char) == "Cc" for char in selector)
    ):
        return "UNSAFE_TEST_TARGET"
    path = canonical_repository_relative_path(file_part)
    if path is None:
        return "UNSAFE_TEST_TARGET"
    if path not in authorized:
        return "TEST_TARGET_NOT_IN_AUTHORIZED_FILES"
    return ""


def build_runner_contract(
    builder_request: Mapping[str, Any],
    preflight: Mapping[str, Any],
    patch_validation: Mapping[str, Any],
    *,
    content_attestation: Mapping[str, Any] | None = None,
    human_patch_reviewed: bool,
    human_patch_reviewer: Any,
    human_patch_review_refs: Sequence[Any] | None,
) -> dict[str, Any]:
    """Build a non-executing isolated runner design contract."""
    if builder_request.get("schema") != BUILDER_SCHEMA:
        raise ValueError("invalid Builder Sandbox Request")
    if str(builder_request.get("state") or "") != "READY_FOR_BUILDER_SANDBOX":
        raise ValueError("builder request is not ready")
    if list(builder_request.get("blockers") or []):
        raise ValueError("builder request has blockers")
    if builder_request.get("execution_authorized") is not False:
        raise ValueError("builder request unexpectedly authorizes execution")
    if builder_request.get("executor_attached") is not False:
        raise ValueError("builder request unexpectedly has executor")
    manifest_id = assert_builder_request_lineage(builder_request)

    if preflight.get("schema") != PREFLIGHT_SCHEMA:
        raise ValueError("invalid Sandbox Preflight")
    if str(preflight.get("state") or "") != "READY_FOR_EXECUTOR_DESIGN_REVIEW":
        raise ValueError("sandbox preflight is not ready")
    if preflight.get("preflight_passed") is not True:
        raise ValueError("sandbox preflight did not pass")
    if preflight.get("execution_authorized") is not False:
        raise ValueError("preflight unexpectedly authorizes execution")
    if preflight.get("executor_attached") is not False:
        raise ValueError("preflight unexpectedly attaches executor")
    if str(preflight.get("builder_request_id") or "") != str(builder_request.get("request_id") or ""):
        raise ValueError("preflight lineage mismatch")
    if str(preflight.get("test_contract_manifest_id") or "") != manifest_id:
        raise ValueError("preflight test contract mismatch")
    if str(preflight.get("preflight_id") or "") != expected_preflight_id(preflight):
        raise ValueError("preflight id mismatch")

    env = (
        preflight.get("environment_contract")
        if isinstance(preflight.get("environment_contract"), Mapping)
        else {}
    )
    if env.get("isolated_worktree") is not True:
        raise ValueError("isolated worktree is required")
    if env.get("repository_root_bound") is not True:
        raise ValueError("repository root boundary is required")
    if env.get("network_disabled") is not True:
        raise ValueError("network must remain disabled")
    if env.get("secrets_mounted") is not False:
        raise ValueError("secrets must not be mounted")
    if str(env.get("command_policy") or "") != ALLOWED_COMMAND_POLICY:
        raise ValueError("command policy must remain allowlist only")

    if patch_validation.get("schema") != PATCH_SCHEMA:
        raise ValueError("invalid Patch Validation")
    if str(patch_validation.get("state") or "") != "READY_FOR_PATCH_REVIEW":
        raise ValueError("patch validation is not ready")
    if list(patch_validation.get("blockers") or []):
        raise ValueError("patch validation has blockers")
    if patch_validation.get("patch_applied") is not False:
        raise ValueError("patch must not be applied by validator")
    if patch_validation.get("execution_authorized") is not False:
        raise ValueError("patch validation unexpectedly authorizes execution")
    if patch_validation.get("executor_attached") is not False:
        raise ValueError("patch validation unexpectedly attaches executor")
    if str(patch_validation.get("builder_request_id") or "") != str(builder_request.get("request_id") or ""):
        raise ValueError("patch validation request lineage mismatch")
    if str(patch_validation.get("preflight_id") or "") != str(preflight.get("preflight_id") or ""):
        raise ValueError("patch validation preflight lineage mismatch")

    revision = (
        patch_validation.get("revision_binding")
        if isinstance(patch_validation.get("revision_binding"), Mapping)
        else {}
    )
    branch_contract = (
        builder_request.get("branch_contract")
        if isinstance(builder_request.get("branch_contract"), Mapping)
        else {}
    )
    if revision.get("refs_match_approved_request") is not True:
        raise ValueError("patch refs are not bound to approved request")
    if str(revision.get("baseline_ref") or "") != str(branch_contract.get("baseline_ref") or ""):
        raise ValueError("patch baseline differs from builder request")
    if str(revision.get("candidate_ref") or "") != str(branch_contract.get("candidate_ref") or ""):
        raise ValueError("patch candidate differs from builder request")

    blockers: list[str] = []
    attestation_id = ""
    structurally_bound = False
    if content_attestation is None:
        blockers.append("CONTENT_ATTESTATION_REQUIRED")
    else:
        assert_content_attestation_matches(
            content_attestation,
            builder_request,
            preflight,
            patch_validation,
        )
        structurally_bound = True
        attestation_id = str(content_attestation.get("content_attestation_id") or "")
    if revision.get("revision_content_verified") is not True:
        blockers.append("PATCH_VALIDATOR_CONTENT_BINDING_NOT_VERIFIED")

    reviewer = _clean(human_patch_reviewer, 160)
    raw_review_refs = require_string_sequence(human_patch_review_refs, "human_patch_review_refs")
    if len(raw_review_refs) > MAX_REVIEW_REFS:
        blockers.append("REVIEW_EVIDENCE_LIMIT_EXCEEDED")
        review_refs: list[str] = []
    else:
        review_refs = _unique(raw_review_refs, MAX_REVIEW_REFS)
    if human_patch_reviewed is not True:
        blockers.append("HUMAN_PATCH_REVIEW_REQUIRED")
    if not reviewer:
        blockers.append("HUMAN_PATCH_REVIEWER_REQUIRED")
    if not review_refs:
        blockers.append("HUMAN_PATCH_REVIEW_EVIDENCE_REQUIRED")

    test_contract = (
        builder_request.get("test_contract")
        if isinstance(builder_request.get("test_contract"), Mapping)
        else {}
    )
    raw_tests = require_string_sequence(test_contract.get("candidate_tests"), "candidate_tests")
    raw_gates = require_string_sequence(test_contract.get("mandatory_gates"), "mandatory_gates")
    authorized = _authorized_files(builder_request)
    tests: list[str] = []
    if len(raw_tests) > MAX_TEST_TARGETS:
        blockers.append("TEST_TARGET_LIMIT_EXCEEDED")
    else:
        for item in raw_tests:
            reason = _classify_test_target(item, authorized)
            if reason:
                blockers.append(reason)
                continue
            if item not in tests:
                tests.append(item)
        if not tests:
            blockers.append("TEST_TARGETS_REQUIRED")
    gates: list[str] = []
    if len(raw_gates) > MAX_MANDATORY_GATES:
        blockers.append("MANDATORY_GATE_LIMIT_EXCEEDED")
    else:
        assert_required_mandatory_gates(raw_gates)
        gates = _unique(raw_gates, MAX_MANDATORY_GATES)
        if not gates:
            blockers.append("MANDATORY_GATES_REQUIRED")

    budget = (
        preflight.get("resource_budget")
        if isinstance(preflight.get("resource_budget"), Mapping)
        else None
    )
    validated_budget, budget_blockers = validate_resource_budget(budget)
    blockers.extend(budget_blockers)

    blockers = list(dict.fromkeys(blockers))
    state = "READY_FOR_RUNNER_DESIGN_REVIEW" if not blockers else "BLOCKED"

    return _bind_runner_contract_ids({
        "schema": SCHEMA,
        "state": state,
        "lineage": {
            "builder_request_id": str(builder_request.get("request_id") or ""),
            "preflight_id": str(preflight.get("preflight_id") or ""),
            "patch_validation_id": str(patch_validation.get("validation_id") or ""),
            "patch_digest": str(patch_validation.get("patch_digest") or ""),
            "content_attestation_id": attestation_id,
            "content_binding_structurally_bound": structurally_bound,
            "content_binding_independently_verified": False,
        },
        "review": {
            "human_patch_reviewed": bool(human_patch_reviewed),
            "human_patch_reviewer": reviewer,
            "human_patch_review_refs": review_refs,
        },
        "tests": {
            "targets": tests,
            "mandatory_gates": gates,
            "tests_executed": False,
        },
        "resource_budget": validated_budget,
        "command_plan": _canonical_command_plan(),
        "command_plan_is_data_only": True,
        "shell_allowed": False,
        "network_allowed": False,
        "secrets_allowed": False,
        "repo_write_allowed": False,
        "blockers": blockers,
        "runner_design_review_required": True,
        "content_binding_structurally_bound": structurally_bound,
        "content_binding_independently_verified": False,
        "path_lookup_allowed": False,
        "parent_environment_inheritance": False,
        "caller_environment_overrides_allowed": False,
        "executable_pinning_verified": False,
        "os_sandbox_verified": False,
        "child_process_policy_verified": False,
        "symlink_physical_boundary_verified": False,
        "hardlink_physical_boundary_verified": False,
        "execution_authorized": False,
        "executor_attached": False,
        "commands_executed": False,
        "writes_files": False,
        "runs_tests": False,
        "network_called": False,
        "subprocess_called": False,
        "automatic_commit": False,
        "automatic_merge": False,
        "automatic_deploy": False,
        "production_change_allowed": False,
        "real_trading_enabled": False,
        "tool_output_is_authority": False,
    })


__all__ = [
    "SCHEMA",
    "MAX_TEST_TARGETS",
    "MAX_MANDATORY_GATES",
    "MAX_REVIEW_REFS",
    "runner_contract_manifest",
    "runner_contract_manifest_id",
    "expected_runner_contract_id",
    "assert_runner_contract_integrity",
    "build_runner_contract",
]
