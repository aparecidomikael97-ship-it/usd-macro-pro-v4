"""Declarative preflight for a future AION Builder sandbox executor.

This module validates the already-authorized Builder Sandbox Request against an
isolated execution-environment contract. It does not attach or invoke an
executor. Passing preflight means only READY_FOR_EXECUTOR_DESIGN_REVIEW.

No function edits files, runs commands/tests, spawns processes, accesses the
network, mounts secrets, persists checkpoints, commits, merges, deploys,
publishes or enables real trading.
"""
from __future__ import annotations

from hashlib import sha256
import json
import re
import unicodedata
from typing import Any, Mapping

from atlasquant_aion_developer_builder_sandbox import SCHEMA as BUILDER_REQUEST_SCHEMA
from atlasquant_aion_developer_manifest import (
    assert_builder_request_lineage,
    assert_required_mandatory_gates,
    require_string_sequence,
)
from atlasquant_aion_observability import redact_text

SCHEMA = "ATLASQUANT_AION_DEVELOPER_SANDBOX_PREFLIGHT_V1"

MIN_RUNTIME_SECONDS = 1
MAX_RUNTIME_SECONDS = 900
MIN_MEMORY_MB = 128
MAX_MEMORY_MB = 2048
MIN_OUTPUT_BYTES = 1024
MAX_OUTPUT_BYTES = 2_000_000
MIN_COMMANDS = 1
MAX_COMMANDS = 24
ALLOWED_COMMAND_POLICY = "ALLOWLIST_ONLY"
ALLOWED_ENVIRONMENT_KINDS = frozenset({"LOCAL_EPHEMERAL", "ISOLATED_WORKTREE"})
_DRIVE_PREFIX_RE = re.compile(r"^[A-Za-z]:")


def _clean(value: Any, limit: int = 800) -> str:
    return " ".join(redact_text(value).replace("\x00", "").split())[:limit]


def _digest(value: Any, length: int = 18) -> str:
    raw = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        default=str,
        separators=(",", ":"),
    )
    return sha256(raw.encode("utf-8")).hexdigest()[:length].upper()


def canonical_repository_relative_path(value: Any) -> str | None:
    """Return a safe relative repository path, or None.

    Absolute, drive-letter, UNC, tilde and traversal forms are rejected on the
    raw text before separators are normalized. This does not stat the
    filesystem and does not depend on the host operating system.
    """
    if not isinstance(value, str) or not value or value != value.strip():
        return None
    if any(unicodedata.category(char) == "Cc" for char in value):
        return None
    if (
        value.startswith("/")
        or value.startswith("\\")
        or value.startswith("~")
        or _DRIVE_PREFIX_RE.match(value) is not None
    ):
        return None
    normalized = value.replace("\\", "/")
    if (
        not normalized
        or normalized.startswith("/")
        or normalized.startswith("~")
        or _DRIVE_PREFIX_RE.match(normalized) is not None
    ):
        return None
    parts = normalized.split("/")
    if any(part in {"", ".", ".."} or ":" in part for part in parts):
        return None
    return normalized


def _safe_relative_path(value: Any) -> bool:
    return canonical_repository_relative_path(value) is not None


def expected_preflight_id(preflight: Mapping[str, Any]) -> str:
    """Recompute the preflight id, including the bound test-contract manifest."""
    env = (
        preflight.get("environment_contract")
        if isinstance(preflight.get("environment_contract"), Mapping)
        else {}
    )
    budget = (
        preflight.get("resource_budget")
        if isinstance(preflight.get("resource_budget"), Mapping)
        else {}
    )
    scope = preflight.get("scope") if isinstance(preflight.get("scope"), Mapping) else {}
    seed = {
        "request_id": str(preflight.get("builder_request_id") or ""),
        "environment": str(env.get("environment_kind") or ""),
        "environment_id": str(env.get("environment_id") or ""),
        "files": require_string_sequence(scope.get("requested_files"), "requested_files"),
        "policy": str(env.get("command_policy") or ""),
        "budgets": {
            "runtime_seconds": int(budget.get("runtime_seconds")),
            "memory_mb": int(budget.get("memory_mb")),
            "output_bytes": int(budget.get("output_bytes")),
            "max_commands": int(budget.get("max_commands")),
        },
        "test_contract_manifest_id": str(preflight.get("test_contract_manifest_id") or ""),
    }
    return "DEVPREF-" + _digest(seed)


def _canonical_scope_paths(values: Any, *, label: str) -> list[str]:
    out: list[str] = []
    for raw in list(values or []):
        path = canonical_repository_relative_path(raw)
        if path is None:
            raise ValueError(f"unsafe {label} repository path")
        if path not in out:
            out.append(path)
    return out


def build_sandbox_preflight(
    builder_request: Mapping[str, Any],
    *,
    environment_kind: Any,
    environment_id: Any,
    isolated_worktree: bool,
    repository_root_bound: bool,
    network_disabled: bool,
    secrets_mounted: bool,
    command_policy: Any,
    runtime_seconds: int = MAX_RUNTIME_SECONDS,
    memory_mb: int = MAX_MEMORY_MB,
    output_bytes: int = MAX_OUTPUT_BYTES,
    max_commands: int = MAX_COMMANDS,
) -> dict[str, Any]:
    """Validate a future sandbox boundary without authorizing execution."""
    if builder_request.get("schema") != BUILDER_REQUEST_SCHEMA:
        raise ValueError("invalid Builder Sandbox Request")
    if str(builder_request.get("state") or "") != "READY_FOR_BUILDER_SANDBOX":
        raise ValueError("builder request is not ready")
    if list(builder_request.get("blockers") or []):
        raise ValueError("builder request still has blockers")
    if builder_request.get("execution_authorized") is not False:
        raise ValueError("builder request unexpectedly authorizes execution")
    if builder_request.get("executor_attached") is not False:
        raise ValueError("builder request already has an executor attached")
    if builder_request.get("writes_files") is not False:
        raise ValueError("builder request unexpectedly writes files")

    branch = (
        builder_request.get("branch_contract")
        if isinstance(builder_request.get("branch_contract"), Mapping)
        else {}
    )
    if branch.get("candidate_bound_to_branch") is not True:
        raise ValueError("candidate ref is not bound to isolated branch")
    if branch.get("main_branch_allowed") is not False:
        raise ValueError("main branch authority must remain blocked")
    if branch.get("force_push_allowed") is not False:
        raise ValueError("force push must remain blocked")
    if branch.get("history_rewrite_allowed") is not False:
        raise ValueError("history rewrite must remain blocked")

    scope = (
        builder_request.get("scope")
        if isinstance(builder_request.get("scope"), Mapping)
        else {}
    )
    requested = _canonical_scope_paths(
        require_string_sequence(scope.get("requested_files"), "requested_files"),
        label="requested",
    )
    authorized = set(_canonical_scope_paths(
        require_string_sequence(scope.get("authorized_files"), "authorized_files"),
        label="authorized",
    ))
    if not requested:
        raise ValueError("requested file scope is empty")
    if any(path not in authorized for path in requested):
        raise ValueError("requested files exceed authorized scope")
    if scope.get("scope_expansion_allowed") is not False:
        raise ValueError("scope expansion must remain blocked")
    for flag in ("new_file_allowed", "delete_file_allowed", "rename_file_allowed"):
        if scope.get(flag) is not False:
            raise ValueError(f"{flag} must remain false")

    manifest_id = assert_builder_request_lineage(builder_request)
    tests = (
        builder_request.get("test_contract")
        if isinstance(builder_request.get("test_contract"), Mapping)
        else {}
    )
    candidate_tests = require_string_sequence(tests.get("candidate_tests"), "candidate_tests")
    mandatory_gates = require_string_sequence(tests.get("mandatory_gates"), "mandatory_gates")
    if not candidate_tests:
        raise ValueError("candidate tests are required")
    assert_required_mandatory_gates(mandatory_gates)
    if tests.get("test_deletion_allowed") is not False:
        raise ValueError("test deletion must remain blocked")
    if tests.get("test_weakening_allowed") is not False:
        raise ValueError("test weakening must remain blocked")

    environment = _clean(environment_kind, 80).upper()
    env_id = _clean(environment_id, 160)
    policy = _clean(command_policy, 80).upper()
    if environment not in ALLOWED_ENVIRONMENT_KINDS:
        raise ValueError("unsupported sandbox environment kind")
    if not env_id:
        raise ValueError("sandbox environment id required")

    blockers: list[str] = []
    if isolated_worktree is not True:
        blockers.append("ISOLATED_WORKTREE_REQUIRED")
    if repository_root_bound is not True:
        blockers.append("REPOSITORY_ROOT_BOUNDARY_REQUIRED")
    if network_disabled is not True:
        blockers.append("NETWORK_MUST_BE_DISABLED")
    if secrets_mounted is not False:
        blockers.append("SECRETS_MUST_NOT_BE_MOUNTED")
    if policy != ALLOWED_COMMAND_POLICY:
        blockers.append("COMMAND_POLICY_MUST_BE_ALLOWLIST_ONLY")

    budgets = {
        "runtime_seconds": int(runtime_seconds),
        "memory_mb": int(memory_mb),
        "output_bytes": int(output_bytes),
        "max_commands": int(max_commands),
    }
    if budgets["runtime_seconds"] < MIN_RUNTIME_SECONDS or budgets["runtime_seconds"] > MAX_RUNTIME_SECONDS:
        blockers.append("RUNTIME_BUDGET_OUT_OF_RANGE")
    if budgets["memory_mb"] < MIN_MEMORY_MB or budgets["memory_mb"] > MAX_MEMORY_MB:
        blockers.append("MEMORY_BUDGET_OUT_OF_RANGE")
    if budgets["output_bytes"] < MIN_OUTPUT_BYTES or budgets["output_bytes"] > MAX_OUTPUT_BYTES:
        blockers.append("OUTPUT_BUDGET_OUT_OF_RANGE")
    if budgets["max_commands"] < MIN_COMMANDS or budgets["max_commands"] > MAX_COMMANDS:
        blockers.append("COMMAND_BUDGET_OUT_OF_RANGE")

    blockers = list(dict.fromkeys(blockers))
    state = "READY_FOR_EXECUTOR_DESIGN_REVIEW" if not blockers else "BLOCKED"

    out = {
        "schema": SCHEMA,
        "preflight_id": "",
        "state": state,
        "builder_request_id": str(builder_request.get("request_id") or ""),
        "test_contract_manifest_id": manifest_id,
        "environment_contract": {
            "environment_kind": environment,
            "environment_id": env_id,
            "isolated_worktree": bool(isolated_worktree),
            "repository_root_bound": bool(repository_root_bound),
            "network_disabled": bool(network_disabled),
            "secrets_mounted": bool(secrets_mounted),
            "command_policy": policy,
        },
        "resource_budget": budgets,
        "scope": {
            "requested_files": requested,
            "scope_expansion_allowed": False,
            "new_file_allowed": False,
            "delete_file_allowed": False,
            "rename_file_allowed": False,
        },
        "blockers": blockers,
        "future_executor_requirements": [
            "Command allowlist must be explicit and immutable per run.",
            "Working directory must remain inside the isolated worktree.",
            "No network or mounted secrets.",
            "All writes, if ever enabled later, must remain inside requested_files.",
            "Every command/result must emit bounded audit evidence.",
            "Budget exhaustion must fail closed.",
            "Executor design review is separate from execution authorization.",
            "Physical symlink and hardlink boundaries are not verified by this contract.",
        ],
        "symlink_physical_boundary_verified": False,
        "hardlink_physical_boundary_verified": False,
        "preflight_passed": not blockers,
        "executor_design_review_required": True,
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
    out["preflight_id"] = expected_preflight_id(out)
    return out


__all__ = [
    "SCHEMA",
    "MIN_RUNTIME_SECONDS",
    "MAX_RUNTIME_SECONDS",
    "MIN_MEMORY_MB",
    "MAX_MEMORY_MB",
    "MIN_OUTPUT_BYTES",
    "MAX_OUTPUT_BYTES",
    "MIN_COMMANDS",
    "MAX_COMMANDS",
    "ALLOWED_COMMAND_POLICY",
    "ALLOWED_ENVIRONMENT_KINDS",
    "canonical_repository_relative_path",
    "expected_preflight_id",
    "build_sandbox_preflight",
]
