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

from atlasquant_aion_developer_builder_sandbox import assert_builder_sandbox_request_integrity
from atlasquant_aion_developer_manifest import require_string_sequence
from atlasquant_aion_observability import redact_text

SCHEMA = "ATLASQUANT_AION_DEVELOPER_SANDBOX_PREFLIGHT_V1"
READY_STATE = "READY_FOR_EXECUTOR_DESIGN_REVIEW"
BLOCKED_STATE = "BLOCKED"

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


_BUDGET_FIELDS = (
    ("runtime_seconds", MIN_RUNTIME_SECONDS, MAX_RUNTIME_SECONDS, "RUNTIME_BUDGET_OUT_OF_RANGE"),
    ("memory_mb", MIN_MEMORY_MB, MAX_MEMORY_MB, "MEMORY_BUDGET_OUT_OF_RANGE"),
    ("output_bytes", MIN_OUTPUT_BYTES, MAX_OUTPUT_BYTES, "OUTPUT_BUDGET_OUT_OF_RANGE"),
    ("max_commands", MIN_COMMANDS, MAX_COMMANDS, "COMMAND_BUDGET_OUT_OF_RANGE"),
)


def validate_resource_budget(budget: Mapping[str, Any] | None) -> tuple[dict[str, int], list[str]]:
    """Return exact ints and official range blockers.

    ``type(value) is int`` is required. ``bool`` is a subclass of ``int`` and
    is rejected, as are strings, floats and every other representation. This
    function does not coerce values, so ``True`` and ``1`` cannot share a digest.
    """
    if not isinstance(budget, Mapping):
        raise ValueError("resource budget must be an object")
    validated: dict[str, int] = {}
    blockers: list[str] = []
    for field, low, high, blocker in _BUDGET_FIELDS:
        value = budget.get(field)
        if type(value) is not int:
            raise ValueError(f"{field} must be an exact int")
        validated[field] = value
        if value < low or value > high:
            blockers.append(blocker)
    return validated, blockers


_ENV_KEYS = frozenset({
    "environment_kind",
    "environment_id",
    "isolated_worktree",
    "repository_root_bound",
    "network_disabled",
    "secrets_mounted",
    "command_policy",
})
_SCOPE_KEYS = frozenset({
    "requested_files",
    "scope_expansion_allowed",
    "new_file_allowed",
    "delete_file_allowed",
    "rename_file_allowed",
})
_BUDGET_KEYS = frozenset(field for field, _low, _high, _blocker in _BUDGET_FIELDS)
_FALSE_FLAGS = (
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
_FUTURE_REQUIREMENTS = (
    "Command allowlist must be explicit and immutable per run.",
    "Working directory must remain inside the isolated worktree.",
    "No network or mounted secrets.",
    "All writes, if ever enabled later, must remain inside requested_files.",
    "Every command/result must emit bounded audit evidence.",
    "Budget exhaustion must fail closed.",
    "Executor design review is separate from execution authorization.",
    "Physical symlink and hardlink boundaries are not verified by this contract.",
)
_CONTRACT_KEYS = frozenset({
    "schema",
    "preflight_id",
    "state",
    "builder_request_id",
    "test_contract_manifest_id",
    "environment_contract",
    "resource_budget",
    "scope",
    "blockers",
    "future_executor_requirements",
    "preflight_passed",
    "executor_design_review_required",
}) | frozenset(_FALSE_FLAGS)


def _reject_closed(document: Mapping[str, Any], allowed: frozenset[str], label: str) -> None:
    unknown = sorted(set(document) - allowed)
    if unknown:
        raise ValueError(f"unknown {label} field {unknown[0]}")
    missing = sorted(allowed - set(document))
    if missing:
        raise ValueError(f"{label} is missing {missing[0]}")


def _environment_blockers(env: Mapping[str, Any]) -> list[str]:
    blockers: list[str] = []
    if env.get("isolated_worktree") is not True:
        blockers.append("ISOLATED_WORKTREE_REQUIRED")
    if env.get("repository_root_bound") is not True:
        blockers.append("REPOSITORY_ROOT_BOUNDARY_REQUIRED")
    if env.get("network_disabled") is not True:
        blockers.append("NETWORK_MUST_BE_DISABLED")
    if env.get("secrets_mounted") is not False:
        blockers.append("SECRETS_MUST_NOT_BE_MOUNTED")
    if env.get("command_policy") != ALLOWED_COMMAND_POLICY:
        blockers.append("COMMAND_POLICY_MUST_BE_ALLOWLIST_ONLY")
    return blockers


def expected_preflight_id(preflight: Mapping[str, Any]) -> str:
    """Recompute the preflight id from the sealed semantic fields.

    State, blockers, environment booleans and authority flags enter the
    digest. Recomputing the id does not make a contradictory document ready.
    """
    env = (
        preflight.get("environment_contract")
        if isinstance(preflight.get("environment_contract"), Mapping)
        else {}
    )
    budget = (
        preflight.get("resource_budget")
        if isinstance(preflight.get("resource_budget"), Mapping)
        else None
    )
    scope = preflight.get("scope") if isinstance(preflight.get("scope"), Mapping) else {}
    validated_budget, _range_blockers = validate_resource_budget(budget)
    blockers = preflight.get("blockers")
    seed = {
        "request_id": str(preflight.get("builder_request_id") or ""),
        "environment": str(env.get("environment_kind") or ""),
        "environment_id": str(env.get("environment_id") or ""),
        "isolated_worktree": env.get("isolated_worktree"),
        "repository_root_bound": env.get("repository_root_bound"),
        "network_disabled": env.get("network_disabled"),
        "secrets_mounted": env.get("secrets_mounted"),
        "files": require_string_sequence(scope.get("requested_files"), "requested_files"),
        "scope_expansion_allowed": scope.get("scope_expansion_allowed"),
        "new_file_allowed": scope.get("new_file_allowed"),
        "delete_file_allowed": scope.get("delete_file_allowed"),
        "rename_file_allowed": scope.get("rename_file_allowed"),
        "policy": str(env.get("command_policy") or ""),
        "budgets": validated_budget,
        "test_contract_manifest_id": str(preflight.get("test_contract_manifest_id") or ""),
        "state": preflight.get("state"),
        "blockers": list(blockers) if isinstance(blockers, list) else blockers,
        "preflight_passed": preflight.get("preflight_passed"),
        **{field: preflight.get(field) for field in _FALSE_FLAGS},
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
    manifest_id = assert_builder_sandbox_request_integrity(builder_request)
    if builder_request.get("state") != "READY_FOR_BUILDER_SANDBOX":
        raise ValueError("builder request is not ready")
    scope = builder_request.get("scope") if isinstance(builder_request.get("scope"), Mapping) else {}
    requested = _canonical_scope_paths(
        require_string_sequence(scope.get("requested_files"), "requested_files"),
        label="requested",
    )
    if requested != list(scope.get("requested_files") or []):
        raise ValueError("builder requested files are not canonical")
    tests = builder_request.get("test_contract") if isinstance(builder_request.get("test_contract"), Mapping) else {}
    candidate_tests = require_string_sequence(tests.get("candidate_tests"), "candidate_tests")
    if not candidate_tests:
        raise ValueError("candidate tests are required")

    environment = _clean(environment_kind, 80).upper()
    env_id = _clean(environment_id, 160)
    policy = _clean(command_policy, 80).upper()
    if environment not in ALLOWED_ENVIRONMENT_KINDS:
        raise ValueError("unsupported sandbox environment kind")
    if not env_id:
        raise ValueError("sandbox environment id required")

    environment_contract = {
        "environment_kind": environment,
        "environment_id": env_id,
        "isolated_worktree": isolated_worktree is True,
        "repository_root_bound": repository_root_bound is True,
        "network_disabled": network_disabled is True,
        "secrets_mounted": secrets_mounted is True,
        "command_policy": policy,
    }
    budgets, budget_blockers = validate_resource_budget({
        "runtime_seconds": runtime_seconds,
        "memory_mb": memory_mb,
        "output_bytes": output_bytes,
        "max_commands": max_commands,
    })
    blockers = _environment_blockers(environment_contract) + budget_blockers
    blockers = list(dict.fromkeys(blockers))
    state = READY_STATE if not blockers else BLOCKED_STATE

    out = {
        "schema": SCHEMA,
        "preflight_id": "",
        "state": state,
        "builder_request_id": str(builder_request.get("request_id") or ""),
        "test_contract_manifest_id": manifest_id,
        "environment_contract": environment_contract,
        "resource_budget": budgets,
        "scope": {
            "requested_files": requested,
            "scope_expansion_allowed": False,
            "new_file_allowed": False,
            "delete_file_allowed": False,
            "rename_file_allowed": False,
        },
        "blockers": blockers,
        "future_executor_requirements": list(_FUTURE_REQUIREMENTS),
        "preflight_passed": not blockers,
        "executor_design_review_required": True,
        **{field: False for field in _FALSE_FLAGS},
    }
    out["preflight_id"] = expected_preflight_id(out)
    assert_sandbox_preflight_integrity(out, builder_request)
    return out


def assert_sandbox_preflight_integrity(
    preflight: Mapping[str, Any],
    builder_request: Mapping[str, Any],
) -> str:
    """Rebuild the preflight decision against the builder document.

    ``requested_files`` must equal the builder scope. A recomputed preflight
    id does not authorize a swapped scope or a contradictory environment.
    """
    manifest_id = assert_builder_sandbox_request_integrity(builder_request)
    if not isinstance(preflight, Mapping):
        raise ValueError("sandbox preflight must be an object")
    if preflight.get("schema") != SCHEMA:
        raise ValueError("invalid Sandbox Preflight")
    _reject_closed(preflight, _CONTRACT_KEYS, "sandbox preflight")
    for field in _FALSE_FLAGS:
        if preflight.get(field) is not False:
            raise ValueError(f"sandbox preflight cannot claim {field}")
    if preflight.get("executor_design_review_required") is not True:
        raise ValueError("executor design review remains required")
    if list(preflight.get("future_executor_requirements") or []) != list(_FUTURE_REQUIREMENTS):
        raise ValueError("future executor requirements are not canonical")
    if preflight.get("builder_request_id") != builder_request.get("request_id"):
        raise ValueError("preflight lineage mismatch")
    if preflight.get("test_contract_manifest_id") != manifest_id:
        raise ValueError("preflight test contract mismatch")
    env = preflight.get("environment_contract")
    if not isinstance(env, Mapping):
        raise ValueError("preflight environment contract must be an object")
    _reject_closed(env, _ENV_KEYS, "preflight environment")
    if env.get("environment_kind") not in ALLOWED_ENVIRONMENT_KINDS:
        raise ValueError("unsupported sandbox environment kind")
    if not isinstance(env.get("environment_id"), str) or not env.get("environment_id"):
        raise ValueError("sandbox environment id required")
    budget = preflight.get("resource_budget")
    if not isinstance(budget, Mapping):
        raise ValueError("resource budget must be an object")
    _reject_closed(budget, _BUDGET_KEYS, "preflight resource budget")
    validated_budget, budget_blockers = validate_resource_budget(budget)
    if dict(budget) != validated_budget:
        raise ValueError("preflight resource budget was not canonical")
    scope = preflight.get("scope")
    if not isinstance(scope, Mapping):
        raise ValueError("preflight scope must be an object")
    _reject_closed(scope, _SCOPE_KEYS, "preflight scope")
    builder_scope = builder_request.get("scope") if isinstance(builder_request.get("scope"), Mapping) else {}
    requested = _canonical_scope_paths(
        require_string_sequence(builder_scope.get("requested_files"), "requested_files"),
        label="requested",
    )
    if require_string_sequence(scope.get("requested_files"), "requested_files") != requested:
        raise ValueError("preflight scope was not derived from the builder request")
    for flag in ("scope_expansion_allowed", "new_file_allowed", "delete_file_allowed", "rename_file_allowed"):
        if scope.get(flag) is not False:
            raise ValueError(f"preflight {flag} must remain false")
    derived = list(dict.fromkeys(_environment_blockers(env) + budget_blockers))
    blockers = preflight.get("blockers")
    if not isinstance(blockers, list) or blockers != derived:
        raise ValueError("preflight blockers were not derived")
    ready = not derived
    if preflight.get("preflight_passed") is not ready:
        raise ValueError("preflight_passed was not derived")
    state = preflight.get("state")
    if ready:
        if state != READY_STATE:
            raise ValueError("ready preflight state was not derived")
    else:
        if state != BLOCKED_STATE:
            raise ValueError("blocked preflight state was not derived")
    if preflight.get("preflight_id") != expected_preflight_id(preflight):
        raise ValueError("preflight id mismatch")
    return str(preflight.get("preflight_id"))


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
    "validate_resource_budget",
    "READY_STATE",
    "expected_preflight_id",
    "assert_sandbox_preflight_integrity",
    "build_sandbox_preflight",
]
