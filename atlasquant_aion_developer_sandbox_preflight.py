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
from pathlib import PurePosixPath
from typing import Any, Mapping

from atlasquant_aion_developer_builder_sandbox import SCHEMA as BUILDER_REQUEST_SCHEMA
from atlasquant_aion_observability import redact_text

SCHEMA = "ATLASQUANT_AION_DEVELOPER_SANDBOX_PREFLIGHT_V1"

MAX_RUNTIME_SECONDS = 900
MAX_MEMORY_MB = 2048
MAX_OUTPUT_BYTES = 2_000_000
MAX_COMMANDS = 24
ALLOWED_COMMAND_POLICY = "ALLOWLIST_ONLY"
ALLOWED_ENVIRONMENT_KINDS = frozenset({"LOCAL_EPHEMERAL", "ISOLATED_WORKTREE"})


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


def _safe_relative_path(value: Any) -> bool:
    raw = _clean(value, 500).replace("\\", "/")
    if not raw or raw.startswith("/") or raw.startswith("~"):
        return False
    path = PurePosixPath(raw)
    if path.is_absolute():
        return False
    return all(part not in {"", ".", ".."} for part in path.parts)


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
    requested = [str(x) for x in list(scope.get("requested_files") or [])]
    authorized = {str(x) for x in list(scope.get("authorized_files") or [])}
    if not requested:
        raise ValueError("requested file scope is empty")
    if any(path not in authorized for path in requested):
        raise ValueError("requested files exceed authorized scope")
    if any(not _safe_relative_path(path) for path in requested):
        raise ValueError("unsafe requested repository path")
    if scope.get("scope_expansion_allowed") is not False:
        raise ValueError("scope expansion must remain blocked")
    for flag in ("new_file_allowed", "delete_file_allowed", "rename_file_allowed"):
        if scope.get(flag) is not False:
            raise ValueError(f"{flag} must remain false")

    tests = (
        builder_request.get("test_contract")
        if isinstance(builder_request.get("test_contract"), Mapping)
        else {}
    )
    if not list(tests.get("candidate_tests") or []):
        raise ValueError("candidate tests are required")
    if not list(tests.get("mandatory_gates") or []):
        raise ValueError("mandatory gates are required")
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
    if budgets["runtime_seconds"] < 1 or budgets["runtime_seconds"] > MAX_RUNTIME_SECONDS:
        blockers.append("RUNTIME_BUDGET_OUT_OF_RANGE")
    if budgets["memory_mb"] < 128 or budgets["memory_mb"] > MAX_MEMORY_MB:
        blockers.append("MEMORY_BUDGET_OUT_OF_RANGE")
    if budgets["output_bytes"] < 1024 or budgets["output_bytes"] > MAX_OUTPUT_BYTES:
        blockers.append("OUTPUT_BUDGET_OUT_OF_RANGE")
    if budgets["max_commands"] < 1 or budgets["max_commands"] > MAX_COMMANDS:
        blockers.append("COMMAND_BUDGET_OUT_OF_RANGE")

    blockers = list(dict.fromkeys(blockers))
    state = "READY_FOR_EXECUTOR_DESIGN_REVIEW" if not blockers else "BLOCKED"

    seed = {
        "request_id": builder_request.get("request_id"),
        "environment": environment,
        "environment_id": env_id,
        "files": requested,
        "policy": policy,
        "budgets": budgets,
    }
    return {
        "schema": SCHEMA,
        "preflight_id": "DEVPREF-" + _digest(seed),
        "state": state,
        "builder_request_id": str(builder_request.get("request_id") or ""),
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
        ],
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


__all__ = [
    "SCHEMA",
    "MAX_RUNTIME_SECONDS",
    "MAX_MEMORY_MB",
    "MAX_OUTPUT_BYTES",
    "MAX_COMMANDS",
    "ALLOWED_COMMAND_POLICY",
    "ALLOWED_ENVIRONMENT_KINDS",
    "build_sandbox_preflight",
]
