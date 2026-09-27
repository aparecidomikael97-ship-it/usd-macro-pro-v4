"""Read-only command allowlist contract for the future AION Developer runner.

Validates the Runner Contract command plan against exact argv templates. It
does not resolve executables or run any command. Passing this contract means
only that the command *description* matches the approved design.

Important: Python test execution still executes repository code. Therefore this
contract explicitly requires OS sandbox proof and executable pinning before any
future execution path can be designed.

No shell, subprocess, filesystem write, network, secret access, test execution,
commit, push, merge, deploy, publication, production change or real trading
occurs in this module.
"""
from __future__ import annotations

import re
from typing import Any, Mapping

from atlasquant_aion_developer_executable_pinning import (
    FORBIDDEN_INHERITED_ENVIRONMENT,
    FIXED_ENVIRONMENT,
    SANDBOX_EPHEMERAL_PYCACHE,
)
from atlasquant_aion_developer_manifest import stable_digest
from atlasquant_aion_developer_runner_contract import (
    SCHEMA as RUNNER_SCHEMA,
    assert_runner_contract_integrity,
)
from atlasquant_aion_developer_sandbox_preflight import validate_resource_budget

SCHEMA = "ATLASQUANT_AION_DEVELOPER_COMMAND_POLICY_V1"

_EXPECTED_STEPS = (
    (
        "COMPILE_CHANGED_SCOPE",
        "python",
        ("-m", "compileall", "-q", "<AUTHORIZED_CHANGED_SCOPE>"),
    ),
    (
        "RUN_TARGETED_TESTS",
        "python",
        ("-m", "unittest", "-q", "<APPROVED_TEST_TARGETS>"),
    ),
    (
        "VERIFY_DIFF_CHECK",
        "git",
        ("diff", "--check"),
    ),
)
_EXPECTED_STEP_NAMES = tuple(row[0] for row in _EXPECTED_STEPS)
_ALLOWED_EXECUTABLES = frozenset({"python", "git"})
_FORBIDDEN_ARG_PATTERN = re.compile(r"(?:\x00|\n|\r|;|&&|\|\||`|\$\(|<\(|>\()")
_SECRET_ENV_RE = re.compile(
    r"(?i)(?:token|secret|password|passwd|api[_-]?key|authorization|credential|senha|chave)"
)


_POLICY_FALSE_FLAGS = (
    "path_lookup_allowed",
    "parent_environment_inheritance",
    "caller_environment_overrides_allowed",
    "compile_step_executable",
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
_POLICY_TRUE_FLAGS = (
    "absolute_executable_required",
    "executable_digest_required",
    "command_policy_is_data_only",
)
_ALLOWED_POLICY_STATES = frozenset({
    "READY_FOR_EXECUTABLE_PINNING_REVIEW",
    "BLOCKED",
})


def _canonical_step(expected: tuple[str, str, tuple[str, ...]]) -> dict[str, Any]:
    name, executable, argv = expected
    row = {
        "step": name,
        "executable": executable,
        "argv": list(argv),
        "shell": False,
        "cwd": "<ISOLATED_WORKTREE>",
        "network": False,
        "writes_repo": False,
    }
    if name == "COMPILE_CHANGED_SCOPE":
        row["writes_repository"] = False
        row["may_write_ephemeral_cache"] = True
        row["pycache_prefix"] = SANDBOX_EPHEMERAL_PYCACHE
    return row


def _pycache_location_blockers(prefix: Any) -> list[str]:
    if not isinstance(prefix, str):
        return []
    if "<ISOLATED_WORKTREE>" in prefix:
        return ["PYCACHE_INSIDE_WORKTREE"]
    if (
        "<REPOSITORY_ROOT>" in prefix
        or "__pycache__" in prefix
        or "/repository/" in prefix
        or prefix == "repository"
        or prefix.casefold().startswith("repository/")
    ):
        return ["PYCACHE_INSIDE_REPOSITORY"]
    return []


def _validate_step(row: Mapping[str, Any], expected: tuple[str, str, tuple[str, ...]]) -> list[str]:
    """Compare raw command fields with the canonical template.

    Security fields are not stripped, case-folded or cleaned before comparison.
    """
    blockers: list[str] = []
    expected_name, expected_exec, expected_argv = expected
    name = row.get("step")
    executable = row.get("executable")
    argv = row.get("argv")

    if name != expected_name:
        blockers.append(f"STEP_NAME_MISMATCH:{expected_name}")
    if executable != expected_exec:
        blockers.append(f"EXECUTABLE_MISMATCH:{expected_name}")
    if not isinstance(executable, str) or executable not in _ALLOWED_EXECUTABLES:
        blockers.append(f"EXECUTABLE_NOT_ALLOWLISTED:{expected_name}")
    if not isinstance(argv, list) or tuple(argv) != expected_argv:
        blockers.append(f"ARGV_TEMPLATE_MISMATCH:{expected_name}")
    if isinstance(argv, list) and any(
        not isinstance(arg, str) or _FORBIDDEN_ARG_PATTERN.search(arg) for arg in argv
    ):
        blockers.append(f"FORBIDDEN_ARG_SYNTAX:{expected_name}")
    if row.get("shell") is not False:
        blockers.append(f"SHELL_MUST_BE_FALSE:{expected_name}")
    if row.get("network") is not False:
        blockers.append(f"NETWORK_MUST_BE_FALSE:{expected_name}")
    if row.get("writes_repo") is not False:
        blockers.append(f"REPO_WRITE_MUST_BE_FALSE:{expected_name}")
    if row.get("cwd") != "<ISOLATED_WORKTREE>":
        blockers.append(f"CWD_MUST_BE_ISOLATED_WORKTREE:{expected_name}")
    if expected_name == "COMPILE_CHANGED_SCOPE":
        if row.get("writes_repository", False) is not False:
            blockers.append("COMPILE_WRITES_REPOSITORY")
        prefix = row.get("pycache_prefix")
        location = _pycache_location_blockers(prefix)
        if location:
            blockers.extend(location)
        elif row.get("may_write_ephemeral_cache") is not True or prefix != SANDBOX_EPHEMERAL_PYCACHE:
            blockers.append("COMPILEALL_CACHE_POLICY_REQUIRED")
    else:
        blockers.extend(_pycache_location_blockers(row.get("pycache_prefix")))
    return blockers


def command_policy_manifest(policy: Mapping[str, Any]) -> dict[str, Any]:
    """Fields that define the accepted command-policy decision. Ids are not inputs."""
    if not isinstance(policy, Mapping):
        raise ValueError("command policy must be an object")
    allowlist = policy.get("allowlist_policy") if isinstance(policy.get("allowlist_policy"), Mapping) else {}
    budget = policy.get("resource_budget") if isinstance(policy.get("resource_budget"), Mapping) else {}
    return {
        "state": policy.get("state"),
        "runner_contract_id": policy.get("runner_contract_id"),
        "runner_contract_manifest_id": policy.get("runner_contract_manifest_id"),
        "validated_command_plan": policy.get("validated_command_plan"),
        "resource_budget": {
            "runtime_seconds": budget.get("runtime_seconds"),
            "memory_mb": budget.get("memory_mb"),
            "output_bytes": budget.get("output_bytes"),
            "max_commands": budget.get("max_commands"),
        },
        "allowlist_policy": {
            "mode": allowlist.get("mode"),
            "step_names": allowlist.get("step_names"),
            "executables": allowlist.get("executables"),
            "caller_environment_overrides_allowed": allowlist.get("caller_environment_overrides_allowed"),
            "fixed_environment": allowlist.get("fixed_environment"),
            "shell_allowed": allowlist.get("shell_allowed"),
            "network_allowed": allowlist.get("network_allowed"),
            "repo_write_allowed": allowlist.get("repo_write_allowed"),
            "PATH_LOOKUP_ALLOWED": allowlist.get("PATH_LOOKUP_ALLOWED"),
            "ABSOLUTE_EXECUTABLE_REQUIRED": allowlist.get("ABSOLUTE_EXECUTABLE_REQUIRED"),
            "EXECUTABLE_DIGEST_REQUIRED": allowlist.get("EXECUTABLE_DIGEST_REQUIRED"),
            "PARENT_ENV_INHERITANCE": allowlist.get("PARENT_ENV_INHERITANCE"),
        },
        "fixed_environment": policy.get("fixed_environment"),
        "caller_environment_overrides_allowed": policy.get("caller_environment_overrides_allowed"),
        "path_lookup_allowed": policy.get("path_lookup_allowed"),
        "absolute_executable_required": policy.get("absolute_executable_required"),
        "executable_digest_required": policy.get("executable_digest_required"),
        "parent_environment_inheritance": policy.get("parent_environment_inheritance"),
        "compile_step_executable": policy.get("compile_step_executable"),
        "command_policy_is_data_only": policy.get("command_policy_is_data_only"),
        "executable_pinning_verified": policy.get("executable_pinning_verified"),
        "os_sandbox_verified": policy.get("os_sandbox_verified"),
        "child_process_policy_verified": policy.get("child_process_policy_verified"),
        "symlink_physical_boundary_verified": policy.get("symlink_physical_boundary_verified"),
        "hardlink_physical_boundary_verified": policy.get("hardlink_physical_boundary_verified"),
        "execution_authorized": policy.get("execution_authorized"),
        "executor_attached": policy.get("executor_attached"),
        "commands_executed": policy.get("commands_executed"),
        "writes_files": policy.get("writes_files"),
        "runs_tests": policy.get("runs_tests"),
        "network_called": policy.get("network_called"),
        "subprocess_called": policy.get("subprocess_called"),
        "automatic_commit": policy.get("automatic_commit"),
        "automatic_merge": policy.get("automatic_merge"),
        "automatic_deploy": policy.get("automatic_deploy"),
        "production_change_allowed": policy.get("production_change_allowed"),
        "real_trading_enabled": policy.get("real_trading_enabled"),
        "tool_output_is_authority": policy.get("tool_output_is_authority"),
    }


def command_policy_manifest_id(policy: Mapping[str, Any]) -> str:
    return stable_digest(command_policy_manifest(policy), prefix="DEVCMAN-", length=18)


def expected_command_policy_id(policy: Mapping[str, Any]) -> str:
    """Digest the policy manifest id. A caller-supplied policy id is not an input."""
    return stable_digest(
        {"command_policy_manifest_id": command_policy_manifest_id(policy)},
        prefix="DEVCMD-",
        length=18,
    )


def assert_command_policy_integrity(policy: Mapping[str, Any]) -> str:
    """Revalidate closed flags and reject a stale command_policy_id."""
    if not isinstance(policy, Mapping):
        raise ValueError("command policy must be an object")
    if policy.get("schema") != SCHEMA:
        raise ValueError("invalid command policy")
    if policy.get("state") not in _ALLOWED_POLICY_STATES:
        raise ValueError("command policy state is not an accepted design state")
    for field in _POLICY_TRUE_FLAGS:
        if policy.get(field) is not True:
            raise ValueError(f"command policy flag {field} is not true")
    for field in _POLICY_FALSE_FLAGS:
        if policy.get(field) is not False:
            raise ValueError(f"command policy flag {field} is not false")
    allowlist = policy.get("allowlist_policy")
    if not isinstance(allowlist, Mapping):
        raise ValueError("allowlist policy required")
    if allowlist.get("caller_environment_overrides_allowed") is not False:
        raise ValueError("caller environment overrides must remain forbidden")
    if allowlist.get("PATH_LOOKUP_ALLOWED") is not False:
        raise ValueError("path lookup must remain forbidden")
    if allowlist.get("PARENT_ENV_INHERITANCE") is not False:
        raise ValueError("parent environment inheritance must remain forbidden")
    if allowlist.get("ABSOLUTE_EXECUTABLE_REQUIRED") is not True:
        raise ValueError("absolute executable must remain required")
    if allowlist.get("EXECUTABLE_DIGEST_REQUIRED") is not True:
        raise ValueError("executable digest must remain required")
    if allowlist.get("shell_allowed") is not False or allowlist.get("network_allowed") is not False:
        raise ValueError("shell and network must remain forbidden")
    if allowlist.get("repo_write_allowed") is not False:
        raise ValueError("repository writes must remain forbidden")
    manifest_id = command_policy_manifest_id(policy)
    if policy.get("command_policy_manifest_id") != manifest_id:
        raise ValueError("command policy manifest mismatch")
    if policy.get("command_policy_id") != expected_command_policy_id(policy):
        raise ValueError("command policy id mismatch")
    return manifest_id


def bind_command_policy_ids(policy: dict[str, Any]) -> dict[str, Any]:
    policy["command_policy_manifest_id"] = command_policy_manifest_id(policy)
    policy["command_policy_id"] = expected_command_policy_id(policy)
    return policy


def assert_runner_policy_boundary(
    runner_contract: Mapping[str, Any],
    command_policy: Mapping[str, Any],
) -> None:
    """Reject a mutated runner or a recycled policy before the next boundary."""
    assert_runner_contract_integrity(runner_contract)
    assert_command_policy_integrity(command_policy)
    if command_policy.get("runner_contract_id") != runner_contract.get("runner_contract_id"):
        raise ValueError("command policy is not bound to this runner contract")
    if command_policy.get("runner_contract_manifest_id") != runner_contract.get("runner_contract_manifest_id"):
        raise ValueError("command policy manifest is not bound to this runner contract")


def build_command_policy_contract(
    runner_contract: Mapping[str, Any],
    *,
    requested_environment: Mapping[str, Any] | None = None,
    path_lookup_allowed: bool = False,
    parent_environment_inheritance: bool = False,
    absolute_executable_required: bool = True,
    executable_digest_required: bool = True,
) -> dict[str, Any]:
    """Validate exact command templates without resolving or executing them."""
    if runner_contract.get("schema") != RUNNER_SCHEMA:
        raise ValueError("invalid Runner Contract")
    if str(runner_contract.get("state") or "") != "READY_FOR_RUNNER_DESIGN_REVIEW":
        raise ValueError("runner contract is not ready for command policy review")
    if list(runner_contract.get("blockers") or []):
        raise ValueError("runner contract still has blockers")
    runner_manifest_id = assert_runner_contract_integrity(runner_contract)

    raw_plan = list(runner_contract.get("command_plan") or [])
    blockers: list[str] = []
    if any(not isinstance(item, Mapping) for item in raw_plan):
        blockers.append("COMMAND_PLAN_ENTRY_NOT_OBJECT")
    rows = [item for item in raw_plan if isinstance(item, Mapping)]
    if len(raw_plan) != len(_EXPECTED_STEPS):
        blockers.append("COMMAND_PLAN_LENGTH_MISMATCH")

    names = tuple(row.get("step") for row in rows)
    if len(rows) == len(_EXPECTED_STEPS) and names != _EXPECTED_STEP_NAMES:
        blockers.append("COMMAND_PLAN_ORDER_OR_STEP_SET_MISMATCH")
    elif len(rows) != len(_EXPECTED_STEPS):
        blockers.append("COMMAND_PLAN_ORDER_OR_STEP_SET_MISMATCH")

    if not any(not isinstance(item, Mapping) for item in raw_plan):
        for idx, expected in enumerate(_EXPECTED_STEPS):
            if idx >= len(rows):
                blockers.append(f"MISSING_STEP:{expected[0]}")
                continue
            blockers.extend(_validate_step(rows[idx], expected))

    budget = (
        runner_contract.get("resource_budget")
        if isinstance(runner_contract.get("resource_budget"), Mapping)
        else None
    )
    validated_budget, budget_blockers = validate_resource_budget(budget)
    blockers.extend(budget_blockers)
    if (
        "COMMAND_BUDGET_OUT_OF_RANGE" not in budget_blockers
        and validated_budget["max_commands"] < len(_EXPECTED_STEPS)
    ):
        blockers.append("COMMAND_PLAN_EXCEEDS_RESOURCE_BUDGET")

    if path_lookup_allowed is not False or runner_contract.get("path_lookup_allowed") is True:
        blockers.append("PATH_LOOKUP_NOT_ALLOWED")
    if (
        parent_environment_inheritance is not False
        or runner_contract.get("parent_environment_inheritance") is True
    ):
        blockers.append("PARENT_ENVIRONMENT_INHERITANCE_NOT_ALLOWED")
    if absolute_executable_required is not True:
        blockers.append("ABSOLUTE_EXECUTABLE_REQUIRED")
    if executable_digest_required is not True:
        blockers.append("EXECUTABLE_DIGEST_REQUIRED")

    requested_env = dict(requested_environment or {})
    if requested_env or runner_contract.get("caller_environment_overrides_allowed") is True:
        blockers.append("CALLER_ENVIRONMENT_OVERRIDES_NOT_ALLOWED")
    if any(_SECRET_ENV_RE.search(str(key)) for key in requested_env):
        blockers.append("SECRET_LIKE_ENVIRONMENT_KEY_NOT_ALLOWED")
    if any(str(key).casefold() in FORBIDDEN_INHERITED_ENVIRONMENT for key in requested_env):
        blockers.append("INHERITED_ENVIRONMENT_KEY_NOT_ALLOWED")

    fixed_environment = dict(FIXED_ENVIRONMENT)

    blockers = list(dict.fromkeys(blockers))
    state = "READY_FOR_EXECUTABLE_PINNING_REVIEW" if not blockers else "BLOCKED"

    return bind_command_policy_ids({
        "schema": SCHEMA,
        "state": state,
        "runner_contract_id": str(runner_contract.get("runner_contract_id") or ""),
        "runner_contract_manifest_id": runner_manifest_id,
        "allowlist_policy": {
            "mode": "EXACT_ARGV_TEMPLATES",
            "step_names": list(_EXPECTED_STEP_NAMES),
            "executables": sorted(_ALLOWED_EXECUTABLES),
            "caller_environment_overrides_allowed": False,
            "fixed_environment": fixed_environment,
            "shell_allowed": False,
            "network_allowed": False,
            "repo_write_allowed": False,
            "PATH_LOOKUP_ALLOWED": False,
            "ABSOLUTE_EXECUTABLE_REQUIRED": True,
            "EXECUTABLE_DIGEST_REQUIRED": True,
            "PARENT_ENV_INHERITANCE": False,
        },
        "fixed_environment": fixed_environment,
        "resource_budget": validated_budget,
        "validated_command_plan": [
            _canonical_step(expected) for expected in _EXPECTED_STEPS
        ] if not blockers else [],
        "blockers": blockers,
        "hazards": [
            "RUN_TARGETED_TESTS executes repository Python code.",
            "Executable names are not yet bound to absolute paths or SHA-256 digests.",
            "A runner executable path is not a pin. Resolved commands must come from the pinning contract.",
            "An allowlist does not replace operating-system sandbox isolation.",
            "Python imports, unittest discovery and repository code may create subprocesses unless OS policy blocks them.",
        ],
        "required_before_future_execution": [
            "PIN_PYTHON_EXECUTABLE_ABSOLUTE_PATH_AND_DIGEST",
            "PIN_GIT_EXECUTABLE_ABSOLUTE_PATH_AND_DIGEST",
            "PROVE_OS_SANDBOX_PROCESS_ISOLATION",
            "PROVE_FILESYSTEM_BOUNDARY",
            "PROVE_NETWORK_DENY",
            "PROVE_SECRET_ABSENCE",
            "PROVE_CHILD_PROCESS_LIMITS",
            "PROVE_TIMEOUT_MEMORY_DISK_OUTPUT_LIMITS",
        ],
        "compile_step_executable": False,
        "caller_environment_overrides_allowed": False,
        "path_lookup_allowed": False,
        "absolute_executable_required": True,
        "executable_digest_required": True,
        "parent_environment_inheritance": False,
        "executable_pinning_verified": False,
        "os_sandbox_verified": False,
        "child_process_policy_verified": False,
        "symlink_physical_boundary_verified": False,
        "hardlink_physical_boundary_verified": False,
        "command_policy_is_data_only": True,
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
    "command_policy_manifest",
    "command_policy_manifest_id",
    "expected_command_policy_id",
    "assert_command_policy_integrity",
    "bind_command_policy_ids",
    "assert_runner_policy_boundary",
    "build_command_policy_contract",
]
