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

from hashlib import sha256
import json
import re
from typing import Any, Mapping

from atlasquant_aion_developer_runner_contract import SCHEMA as RUNNER_SCHEMA
from atlasquant_aion_developer_sandbox_preflight import (
    MAX_COMMANDS,
    MAX_MEMORY_MB,
    MAX_OUTPUT_BYTES,
    MAX_RUNTIME_SECONDS,
    MIN_COMMANDS,
    MIN_MEMORY_MB,
    MIN_OUTPUT_BYTES,
    MIN_RUNTIME_SECONDS,
)

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


def _digest(value: Any, length: int = 18) -> str:
    raw = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        default=str,
        separators=(",", ":"),
    )
    return sha256(raw.encode("utf-8")).hexdigest()[:length].upper()


def _canonical_step(expected: tuple[str, str, tuple[str, ...]]) -> dict[str, Any]:
    name, executable, argv = expected
    return {
        "step": name,
        "executable": executable,
        "argv": list(argv),
        "shell": False,
        "cwd": "<ISOLATED_WORKTREE>",
        "network": False,
        "writes_repo": False,
    }


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
    return blockers


def _budget_in_range(value: Any, low: int, high: int) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and low <= value <= high


def build_command_policy_contract(
    runner_contract: Mapping[str, Any],
    *,
    requested_environment: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate exact command templates without resolving or executing them."""
    if runner_contract.get("schema") != RUNNER_SCHEMA:
        raise ValueError("invalid Runner Contract")
    if str(runner_contract.get("state") or "") != "READY_FOR_RUNNER_DESIGN_REVIEW":
        raise ValueError("runner contract is not ready for command policy review")
    if list(runner_contract.get("blockers") or []):
        raise ValueError("runner contract still has blockers")

    for key in (
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
    ):
        if runner_contract.get(key) is not False:
            raise ValueError(f"runner authority invariant violated: {key}")

    if runner_contract.get("command_plan_is_data_only") is not True:
        raise ValueError("command plan must remain data only")
    if runner_contract.get("shell_allowed") is not False:
        raise ValueError("shell must remain forbidden")
    if runner_contract.get("network_allowed") is not False:
        raise ValueError("network must remain forbidden")
    if runner_contract.get("secrets_allowed") is not False:
        raise ValueError("secrets must remain forbidden")
    if runner_contract.get("repo_write_allowed") is not False:
        raise ValueError("repository writes must remain forbidden")

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
        else {}
    )
    if not _budget_in_range(budget.get("runtime_seconds"), MIN_RUNTIME_SECONDS, MAX_RUNTIME_SECONDS):
        blockers.append("RUNTIME_BUDGET_OUT_OF_RANGE")
    if not _budget_in_range(budget.get("memory_mb"), MIN_MEMORY_MB, MAX_MEMORY_MB):
        blockers.append("MEMORY_BUDGET_OUT_OF_RANGE")
    if not _budget_in_range(budget.get("output_bytes"), MIN_OUTPUT_BYTES, MAX_OUTPUT_BYTES):
        blockers.append("OUTPUT_BUDGET_OUT_OF_RANGE")
    command_budget = budget.get("max_commands")
    if not _budget_in_range(command_budget, MIN_COMMANDS, MAX_COMMANDS):
        blockers.append("COMMAND_BUDGET_OUT_OF_RANGE")
    elif command_budget < len(_EXPECTED_STEPS):
        blockers.append("COMMAND_PLAN_EXCEEDS_RESOURCE_BUDGET")

    requested_env = dict(requested_environment or {})
    if requested_env:
        blockers.append("CALLER_ENVIRONMENT_OVERRIDES_NOT_ALLOWED")
    if any(_SECRET_ENV_RE.search(str(key)) for key in requested_env):
        blockers.append("SECRET_LIKE_ENVIRONMENT_KEY_NOT_ALLOWED")

    fixed_environment = {
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONNOUSERSITE": "1",
        "PYTHONHASHSEED": "0",
        "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
        "PIP_DISABLE_PIP_VERSION_CHECK": "1",
    }

    blockers = list(dict.fromkeys(blockers))
    state = "READY_FOR_EXECUTABLE_PINNING_REVIEW" if not blockers else "BLOCKED"

    policy_seed = {
        "runner_contract_id": runner_contract.get("runner_contract_id"),
        "steps": rows,
        "fixed_environment": fixed_environment,
    }
    return {
        "schema": SCHEMA,
        "command_policy_id": "DEVCMD-" + _digest(policy_seed),
        "state": state,
        "runner_contract_id": str(runner_contract.get("runner_contract_id") or ""),
        "allowlist_policy": {
            "mode": "EXACT_ARGV_TEMPLATES",
            "step_names": list(_EXPECTED_STEP_NAMES),
            "executables": sorted(_ALLOWED_EXECUTABLES),
            "caller_environment_overrides_allowed": False,
            "fixed_environment": fixed_environment,
            "shell_allowed": False,
            "network_allowed": False,
            "repo_write_allowed": False,
        },
        "validated_command_plan": [
            _canonical_step(expected) for expected in _EXPECTED_STEPS
        ] if not blockers else [],
        "blockers": blockers,
        "hazards": [
            "RUN_TARGETED_TESTS executes repository Python code.",
            "Executable names are not yet bound to absolute paths or SHA-256 digests.",
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
    }


__all__ = [
    "SCHEMA",
    "build_command_policy_contract",
]
