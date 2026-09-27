"""Read-only runner contract simulator for AION Developer.

Consumes a Builder Sandbox Request, passing Sandbox Preflight and a read-only
Patch Validation result. It emits an immutable *plan description* for a future
isolated runner. It never executes the plan.

READY means only READY_FOR_RUNNER_DESIGN_REVIEW. It does not mean execution is
authorized. If patch content is not bound to the approved revision or the patch
has not been explicitly reviewed by a human, the simulator fails closed.

No shell, subprocess, filesystem write, network, secret mount, test execution,
commit, merge, deploy, publication, production change or real trading occurs.
"""
from __future__ import annotations

from hashlib import sha256
import json
import re
from typing import Any, Mapping, Sequence

from atlasquant_aion_developer_builder_sandbox import SCHEMA as BUILDER_SCHEMA
from atlasquant_aion_developer_patch_validation import SCHEMA as PATCH_SCHEMA
from atlasquant_aion_developer_sandbox_preflight import (
    ALLOWED_COMMAND_POLICY,
    SCHEMA as PREFLIGHT_SCHEMA,
)
from atlasquant_aion_observability import redact_text

SCHEMA = "ATLASQUANT_AION_DEVELOPER_RUNNER_CONTRACT_V1"
MAX_TEST_TARGETS = 80

_SAFE_TEST_RE = re.compile(r"^[A-Za-z0-9_./:-]+$")


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


def _digest(value: Any, length: int = 18) -> str:
    raw = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        default=str,
        separators=(",", ":"),
    )
    return sha256(raw.encode("utf-8")).hexdigest()[:length].upper()


def _safe_test_target(value: str) -> bool:
    return bool(value) and bool(_SAFE_TEST_RE.fullmatch(value)) and ".." not in value


def build_runner_contract(
    builder_request: Mapping[str, Any],
    preflight: Mapping[str, Any],
    patch_validation: Mapping[str, Any],
    *,
    content_binding_verified: bool,
    content_binding_ref: Any,
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
    binding_ref = _clean(content_binding_ref, 240)
    if content_binding_verified is not True:
        blockers.append("REVISION_CONTENT_BINDING_REQUIRED")
    if revision.get("revision_content_verified") is not True:
        blockers.append("PATCH_VALIDATOR_CONTENT_BINDING_NOT_VERIFIED")
    if not binding_ref:
        blockers.append("CONTENT_BINDING_REF_REQUIRED")

    reviewer = _clean(human_patch_reviewer, 160)
    review_refs = _unique(human_patch_review_refs, 40)
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
    tests = _unique(test_contract.get("candidate_tests"), MAX_TEST_TARGETS)
    gates = _unique(test_contract.get("mandatory_gates"), 40)
    if not tests:
        blockers.append("TEST_TARGETS_REQUIRED")
    if any(not _safe_test_target(item) for item in tests):
        blockers.append("UNSAFE_TEST_TARGET")
    if not gates:
        blockers.append("MANDATORY_GATES_REQUIRED")

    budget = (
        preflight.get("resource_budget")
        if isinstance(preflight.get("resource_budget"), Mapping)
        else {}
    )
    if not all(int(budget.get(key) or 0) > 0 for key in (
        "runtime_seconds", "memory_mb", "output_bytes", "max_commands"
    )):
        blockers.append("INVALID_RESOURCE_BUDGET")

    blockers = list(dict.fromkeys(blockers))
    state = "READY_FOR_RUNNER_DESIGN_REVIEW" if not blockers else "BLOCKED"

    command_plan = [
        {
            "step": "COMPILE_CHANGED_SCOPE",
            "executable": "python",
            "argv": ["-m", "compileall", "-q", "<AUTHORIZED_CHANGED_SCOPE>"],
            "shell": False,
            "cwd": "<ISOLATED_WORKTREE>",
            "network": False,
            "writes_repo": False,
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

    seed = {
        "request_id": builder_request.get("request_id"),
        "preflight_id": preflight.get("preflight_id"),
        "patch_validation_id": patch_validation.get("validation_id"),
        "patch_digest": patch_validation.get("patch_digest"),
        "binding_ref": binding_ref,
        "reviewer": reviewer,
        "review_refs": review_refs,
        "tests": tests,
        "gates": gates,
    }
    return {
        "schema": SCHEMA,
        "runner_contract_id": "DEVRUN-" + _digest(seed),
        "state": state,
        "lineage": {
            "builder_request_id": str(builder_request.get("request_id") or ""),
            "preflight_id": str(preflight.get("preflight_id") or ""),
            "patch_validation_id": str(patch_validation.get("validation_id") or ""),
            "patch_digest": str(patch_validation.get("patch_digest") or ""),
            "content_binding_ref": binding_ref,
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
        "resource_budget": dict(budget),
        "command_plan": command_plan,
        "command_plan_is_data_only": True,
        "shell_allowed": False,
        "network_allowed": False,
        "secrets_allowed": False,
        "repo_write_allowed": False,
        "blockers": blockers,
        "runner_design_review_required": True,
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
    }


__all__ = [
    "SCHEMA",
    "MAX_TEST_TARGETS",
    "build_runner_contract",
]
