"""Read-only command allowlist contract for the future AION Developer runner.

Validates the Runner Contract command plan against exact argv templates. It
does not resolve executables or run any command. Passing this contract means
only that the command *description* matches the approved design.

Four distinct checks are used, and they are not interchangeable:

INTERNAL INTEGRITY: the digest matches the bytes of this document.
LOCAL SEMANTICS: fields follow the canonical plan, budget, environment and flags.
STRUCTURAL PROVENANCE: the builder request, preflight, patch validation,
content attestation and runner agree with each other and with this policy.
This is a deterministic cross-document comparison. It does not establish an
independent root of trust.
INDEPENDENT ROOT OF TRUST: not implemented. Documents can be constructed
together. ``upstream_provenance_independently_verified`` stays false.

A caller boolean cannot make a policy ready. ``READY_FOR_EXECUTABLE_PINNING_REVIEW``
is emitted only after ``assert_runner_provenance`` accepts the supplied documents.

Important: Python test execution still executes repository code. Therefore this
contract explicitly requires OS sandbox proof and executable pinning before any
future execution path can be designed.

No shell, subprocess, filesystem write, network, secret access, test execution,
commit, push, merge, deploy, publication, production change or real trading
occurs in this module. No signature, PKI, KMS, HSM or remote attestation is
created here.
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
    _assert_runner_digest,
    assert_runner_contract_integrity,
    assert_runner_provenance,
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
    "upstream_provenance_independently_verified",
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


def _canonical_command_plan() -> list[dict[str, Any]]:
    return [_canonical_step(expected) for expected in _EXPECTED_STEPS]


def _canonical_allowlist() -> dict[str, Any]:
    return {
        "mode": "EXACT_ARGV_TEMPLATES",
        "step_names": list(_EXPECTED_STEP_NAMES),
        "executables": sorted(_ALLOWED_EXECUTABLES),
        "caller_environment_overrides_allowed": False,
        "fixed_environment": dict(FIXED_ENVIRONMENT),
        "shell_allowed": False,
        "network_allowed": False,
        "repo_write_allowed": False,
        "PATH_LOOKUP_ALLOWED": False,
        "ABSOLUTE_EXECUTABLE_REQUIRED": True,
        "EXECUTABLE_DIGEST_REQUIRED": True,
        "PARENT_ENV_INHERITANCE": False,
    }


def _assert_environment_exact(value: Any, label: str) -> None:
    """Both environment copies must be the canonical fixed environment.

    Dict equality rejects an injected key, a changed value and a missing key.
    Forbidden inherited names are rejected even when the rest of the mapping
    matches.
    """
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be an object")
    for key in value:
        folded = str(key).casefold()
        if folded in FORBIDDEN_INHERITED_ENVIRONMENT or folded.startswith("git_config"):
            raise ValueError(f"{label} contains a forbidden environment key")
    if dict(value) != dict(FIXED_ENVIRONMENT):
        raise ValueError(f"{label} is not the canonical fixed environment")


def _assert_policy_budget(policy: Mapping[str, Any]) -> dict[str, int]:
    budget = policy.get("resource_budget")
    validated, blockers = validate_resource_budget(
        budget if isinstance(budget, Mapping) else None
    )
    if blockers:
        raise ValueError("resource budget is outside the allowed range")
    if not isinstance(budget, Mapping) or dict(budget) != validated:
        raise ValueError("resource budget has non-canonical fields")
    if validated["max_commands"] < len(_EXPECTED_STEPS):
        raise ValueError("resource budget does not cover the canonical command plan")
    return validated


def _assert_policy_semantics(policy: Mapping[str, Any]) -> None:
    """Reject a resealed policy whose security payload is not canonical.

    A freshly computed command_policy_id proves only that the id matches the
    current bytes. It does not prove the constructor produced them.
    """
    _assert_environment_exact(policy.get("fixed_environment"), "fixed_environment")
    allowlist = policy.get("allowlist_policy")
    if not isinstance(allowlist, Mapping):
        raise ValueError("allowlist policy required")
    _assert_environment_exact(
        allowlist.get("fixed_environment"),
        "allowlist fixed_environment",
    )
    if dict(policy["fixed_environment"]) != dict(allowlist["fixed_environment"]):
        raise ValueError("fixed environment copies diverge")
    if dict(allowlist) != _canonical_allowlist():
        raise ValueError("allowlist policy is not the canonical allowlist")
    _assert_policy_budget(policy)
    if policy.get("validated_command_plan") != _canonical_command_plan():
        raise ValueError("validated command plan is not the canonical template")
    _assert_policy_state(policy)
    _assert_policy_provenance_claims(policy)


def _assert_policy_state(policy: Mapping[str, Any]) -> None:
    blockers = policy.get("blockers")
    if not isinstance(blockers, list):
        raise ValueError("command policy blockers must be a list")
    if policy.get("state") == "READY_FOR_EXECUTABLE_PINNING_REVIEW":
        if blockers:
            raise ValueError("ready command policy cannot carry blockers")
    elif not blockers:
        raise ValueError("blocked command policy must name blockers")


def _assert_policy_provenance_claims(policy: Mapping[str, Any]) -> None:
    """Local shape of the provenance claims. This does not recompute them.

    A true structural claim still has to be derived again from the upstream
    documents. An independent root of trust is not a field a document can set.
    """
    structural = policy.get("upstream_provenance_structurally_verified")
    independent = policy.get("upstream_provenance_independently_verified")
    binding = policy.get("upstream_provenance_binding_id")
    if independent is not False:
        raise ValueError("independent root of trust is not established")
    if not isinstance(structural, bool):
        raise ValueError("structural provenance claim must be a boolean")
    if not isinstance(binding, str):
        raise ValueError("structural provenance binding must be a string")
    if structural is True:
        if not binding.startswith("DEVPROV-") or len(binding) != len("DEVPROV-") + 18:
            raise ValueError("structural provenance binding was not derived")
        if "UPSTREAM_PROVENANCE_REQUIRED" in list(policy.get("blockers") or []):
            raise ValueError("structural provenance claim contradicts its blocker")
    elif binding != "":
        raise ValueError("unverified policy cannot carry a provenance binding")
    if policy.get("state") == "READY_FOR_EXECUTABLE_PINNING_REVIEW" and structural is not True:
        raise ValueError("ready command policy requires structural provenance")


def command_policy_manifest(policy: Mapping[str, Any]) -> dict[str, Any]:
    """Fields that define the accepted command-policy decision. Ids are not inputs.

    ``hazards`` and ``required_before_future_execution`` are informational.
    They are not authority fields and are intentionally outside this digest.
    ``state`` and ``blockers`` are authority fields: a blocked policy cannot
    be relabeled ready while keeping the same id.
    ``upstream_provenance_structurally_verified`` records a cross-document
    comparison. ``upstream_provenance_independently_verified`` is not an
    authority that this module can grant, and it stays false.
    ``upstream_provenance_binding_id`` names the documents that were compared.
    It is not an external attestation.
    """
    if not isinstance(policy, Mapping):
        raise ValueError("command policy must be an object")
    allowlist = policy.get("allowlist_policy") if isinstance(policy.get("allowlist_policy"), Mapping) else {}
    budget = policy.get("resource_budget") if isinstance(policy.get("resource_budget"), Mapping) else {}
    blockers = policy.get("blockers")
    return {
        "state": policy.get("state"),
        "blockers": list(blockers) if isinstance(blockers, (list, tuple)) else blockers,
        "upstream_provenance_structurally_verified": policy.get(
            "upstream_provenance_structurally_verified"
        ),
        "upstream_provenance_independently_verified": policy.get(
            "upstream_provenance_independently_verified"
        ),
        "upstream_provenance_binding_id": policy.get("upstream_provenance_binding_id"),
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
    """Revalidate the policy. A matching id is not legitimacy.

    Schema, authority flags, the resource budget, both fixed-environment
    copies and the command plan are checked against the local canonical
    contract. The digest is checked after that, so a resealed document still
    fails when the payload is not the one the constructor would emit.
    """
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
    _assert_policy_semantics(policy)
    manifest_id = command_policy_manifest_id(policy)
    if policy.get("command_policy_manifest_id") != manifest_id:
        raise ValueError("command policy manifest mismatch")
    if policy.get("command_policy_id") != expected_command_policy_id(policy):
        raise ValueError("command policy id mismatch")
    return manifest_id


def _bind_command_policy_ids(policy: dict[str, Any]) -> dict[str, Any]:
    """Constructor helper. Recomputing these ids does not authorize the payload."""
    policy["command_policy_manifest_id"] = command_policy_manifest_id(policy)
    policy["command_policy_id"] = expected_command_policy_id(policy)
    return policy


def _classify_command_policy(
    runner_contract: Mapping[str, Any],
    *,
    requested_environment: Mapping[str, Any] | None = None,
    path_lookup_allowed: bool = False,
    parent_environment_inheritance: bool = False,
    absolute_executable_required: bool = True,
    executable_digest_required: bool = True,
) -> tuple[list[str], dict[str, int]]:
    """Blockers the constructor would record for this runner. Ids are not inputs."""
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
    return list(dict.fromkeys(blockers)), validated_budget


def _provenance_binding_id(
    runner_contract: Mapping[str, Any],
    builder_request: Mapping[str, Any],
    preflight: Mapping[str, Any],
    patch_validation: Mapping[str, Any],
    content_attestation: Mapping[str, Any],
) -> str:
    """Name the documents that were compared. This is not an external attestation."""
    return stable_digest(
        {
            "builder_request_id": builder_request.get("request_id"),
            "preflight_id": preflight.get("preflight_id"),
            "patch_validation_id": patch_validation.get("validation_id"),
            "content_attestation_id": content_attestation.get("content_attestation_id"),
            "runner_contract_id": runner_contract.get("runner_contract_id"),
        },
        prefix="DEVPROV-",
        length=18,
    )


def _structural_provenance(
    runner_contract: Mapping[str, Any],
    builder_request: Mapping[str, Any] | None,
    preflight: Mapping[str, Any] | None,
    patch_validation: Mapping[str, Any] | None,
    content_attestation: Mapping[str, Any] | None,
) -> tuple[bool, str, list[str]]:
    """Cross-check the runner against upstream documents.

    Missing documents are not a passed comparison. Supplied documents that
    disagree raise. Neither result is an independent root of trust.
    """
    documents = (builder_request, preflight, patch_validation, content_attestation)
    if any(not isinstance(document, Mapping) for document in documents):
        return False, "", ["UPSTREAM_PROVENANCE_REQUIRED"]
    assert_runner_provenance(
        runner_contract,
        builder_request,
        preflight,
        patch_validation,
        content_attestation,
    )
    return True, _provenance_binding_id(
        runner_contract,
        builder_request,
        preflight,
        patch_validation,
        content_attestation,
    ), []


def _command_policy_decision(
    runner_contract: Mapping[str, Any],
    *,
    builder_request: Mapping[str, Any] | None = None,
    preflight: Mapping[str, Any] | None = None,
    patch_validation: Mapping[str, Any] | None = None,
    content_attestation: Mapping[str, Any] | None = None,
    requested_environment: Mapping[str, Any] | None = None,
    path_lookup_allowed: bool = False,
    parent_environment_inheritance: bool = False,
    absolute_executable_required: bool = True,
    executable_digest_required: bool = True,
    require_ready_runner: bool = False,
) -> dict[str, Any]:
    """State, blockers and structural claim the constructor would seal."""
    blockers, validated_budget = _classify_command_policy(
        runner_contract,
        requested_environment=requested_environment,
        path_lookup_allowed=path_lookup_allowed,
        parent_environment_inheritance=parent_environment_inheritance,
        absolute_executable_required=absolute_executable_required,
        executable_digest_required=executable_digest_required,
    )
    if not require_ready_runner and (
        runner_contract.get("state") != "READY_FOR_RUNNER_DESIGN_REVIEW"
        or list(runner_contract.get("blockers") or [])
    ):
        blockers = ["RUNNER_CONTRACT_NOT_READY", *blockers]
    structural, binding, provenance_blockers = _structural_provenance(
        runner_contract,
        builder_request,
        preflight,
        patch_validation,
        content_attestation,
    )
    blockers = list(dict.fromkeys([*blockers, *provenance_blockers]))
    if not structural:
        binding = ""
    state = "READY_FOR_EXECUTABLE_PINNING_REVIEW" if not blockers else "BLOCKED"
    if state == "READY_FOR_EXECUTABLE_PINNING_REVIEW" and structural is not True:
        blockers = ["UPSTREAM_PROVENANCE_REQUIRED"]
        state = "BLOCKED"
        structural = False
        binding = ""
    return {
        "state": state,
        "blockers": blockers,
        "validated_budget": validated_budget,
        "structural": structural is True and state == "READY_FOR_EXECUTABLE_PINNING_REVIEW",
        "binding": binding if state == "READY_FOR_EXECUTABLE_PINNING_REVIEW" else "",
        "independent": False,
    }


def expected_command_policy_state_and_blockers(
    runner_contract: Mapping[str, Any],
    *,
    builder_request: Mapping[str, Any] | None = None,
    preflight: Mapping[str, Any] | None = None,
    patch_validation: Mapping[str, Any] | None = None,
    content_attestation: Mapping[str, Any] | None = None,
) -> tuple[str, list[str]]:
    """State the constructor would seal. The supplied policy id is not an input.

    READY requires a passed structural comparison. A missing comparison adds
    ``UPSTREAM_PROVENANCE_REQUIRED`` and stays BLOCKED.
    """
    decision = _command_policy_decision(
        runner_contract,
        builder_request=builder_request,
        preflight=preflight,
        patch_validation=patch_validation,
        content_attestation=content_attestation,
    )
    return decision["state"], list(decision["blockers"])


def expected_command_policy_payload(
    runner_contract: Mapping[str, Any],
    *,
    builder_request: Mapping[str, Any] | None = None,
    preflight: Mapping[str, Any] | None = None,
    patch_validation: Mapping[str, Any] | None = None,
    content_attestation: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Security fields a constructor would seal for this runner.

    The supplied command_policy_id is not an input. The command plan is the
    local canonical template, not the plan carried by the runner document.
    """
    assert_runner_contract_integrity(runner_contract)
    budget = runner_contract.get("resource_budget")
    validated, blockers = validate_resource_budget(
        budget if isinstance(budget, Mapping) else None
    )
    if blockers or not isinstance(budget, Mapping) or dict(budget) != validated:
        raise ValueError("runner resource budget is not canonical")
    decision = _command_policy_decision(
        runner_contract,
        builder_request=builder_request,
        preflight=preflight,
        patch_validation=patch_validation,
        content_attestation=content_attestation,
    )
    policy_blockers = list(decision["blockers"])
    return {
        "state": decision["state"],
        "blockers": policy_blockers,
        "upstream_provenance_structurally_verified": decision["structural"],
        "upstream_provenance_independently_verified": False,
        "upstream_provenance_binding_id": decision["binding"],
        "resource_budget": validated,
        "validated_command_plan": (
            _canonical_command_plan() if not policy_blockers else []
        ),
        "runner_contract_id": runner_contract.get("runner_contract_id"),
        "runner_contract_manifest_id": runner_contract.get("runner_contract_manifest_id"),
        "allowlist_policy": _canonical_allowlist(),
        "fixed_environment": dict(FIXED_ENVIRONMENT),
        "path_lookup_allowed": False,
        "absolute_executable_required": True,
        "executable_digest_required": True,
        "parent_environment_inheritance": False,
        "caller_environment_overrides_allowed": False,
        "compile_step_executable": False,
        "command_policy_is_data_only": True,
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
    }


_BOUNDARY_FIELDS = (
    "state",
    "blockers",
    "upstream_provenance_structurally_verified",
    "upstream_provenance_independently_verified",
    "upstream_provenance_binding_id",
    "resource_budget",
    "validated_command_plan",
    "runner_contract_id",
    "runner_contract_manifest_id",
    "allowlist_policy",
    "fixed_environment",
    "path_lookup_allowed",
    "absolute_executable_required",
    "executable_digest_required",
    "parent_environment_inheritance",
    "caller_environment_overrides_allowed",
    "compile_step_executable",
    "command_policy_is_data_only",
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


def assert_runner_policy_boundary(
    runner_contract: Mapping[str, Any],
    command_policy: Mapping[str, Any],
    *,
    builder_request: Mapping[str, Any] | None = None,
    preflight: Mapping[str, Any] | None = None,
    patch_validation: Mapping[str, Any] | None = None,
    content_attestation: Mapping[str, Any] | None = None,
) -> None:
    """Reject a pair that is only internally consistent.

    The runner is revalidated, the policy is revalidated, and the policy's
    security fields are compared with the payload derived from the runner.
    A recomputed digest on either document is not authority. Structural
    provenance is derived only when the upstream documents are supplied here.
    """
    assert_runner_contract_integrity(runner_contract)
    assert_command_policy_integrity(command_policy)
    expected = expected_command_policy_payload(
        runner_contract,
        builder_request=builder_request,
        preflight=preflight,
        patch_validation=patch_validation,
        content_attestation=content_attestation,
    )
    for field in _BOUNDARY_FIELDS:
        if command_policy.get(field) != expected[field]:
            raise ValueError(
                f"command policy {field} was not derived from the runner contract"
            )


def assert_command_policy_provenance(
    command_policy: Mapping[str, Any],
    runner_contract: Mapping[str, Any],
    builder_request: Mapping[str, Any],
    preflight: Mapping[str, Any],
    patch_validation: Mapping[str, Any],
    content_attestation: Mapping[str, Any],
) -> None:
    """Reject a policy whose id matches but whose provenance was not derived.

    The runner is compared with the upstream documents, then the policy is
    compared with the runner. The structural claim and the binding id must
    match that comparison. ``upstream_provenance_independently_verified``
    stays false: agreement among these documents is not an external root of trust.
    """
    assert_runner_provenance(
        runner_contract,
        builder_request,
        preflight,
        patch_validation,
        content_attestation,
    )
    assert_runner_policy_boundary(
        runner_contract,
        command_policy,
        builder_request=builder_request,
        preflight=preflight,
        patch_validation=patch_validation,
        content_attestation=content_attestation,
    )
    if command_policy.get("upstream_provenance_structurally_verified") is not True:
        raise ValueError("structural provenance claim was not derived")
    if command_policy.get("upstream_provenance_independently_verified") is not False:
        raise ValueError("independent root of trust is not established")
    state, blockers = expected_command_policy_state_and_blockers(
        runner_contract,
        builder_request=builder_request,
        preflight=preflight,
        patch_validation=patch_validation,
        content_attestation=content_attestation,
    )
    if command_policy.get("state") != state:
        raise ValueError("command policy state was not derived from provenance")
    if list(command_policy.get("blockers") or []) != blockers:
        raise ValueError("command policy blockers were not derived from provenance")
    if state == "READY_FOR_EXECUTABLE_PINNING_REVIEW" and blockers:
        raise ValueError("ready command policy cannot carry blockers")


def _reject_caller_provenance_claim(
    upstream_provenance_structurally_verified: Any,
    upstream_provenance_independently_verified: Any,
) -> None:
    if (
        upstream_provenance_structurally_verified is not None
        or upstream_provenance_independently_verified is not None
    ):
        raise ValueError("caller cannot assert upstream provenance")


def build_command_policy_contract(
    runner_contract: Mapping[str, Any],
    *,
    builder_request: Mapping[str, Any] | None = None,
    preflight: Mapping[str, Any] | None = None,
    patch_validation: Mapping[str, Any] | None = None,
    content_attestation: Mapping[str, Any] | None = None,
    requested_environment: Mapping[str, Any] | None = None,
    path_lookup_allowed: bool = False,
    parent_environment_inheritance: bool = False,
    absolute_executable_required: bool = True,
    executable_digest_required: bool = True,
    upstream_provenance_structurally_verified: Any = None,
    upstream_provenance_independently_verified: Any = None,
) -> dict[str, Any]:
    """Validate exact command templates without resolving or executing them.

    READY is sealed only after the runner's structural provenance passes.
    The two provenance fields on the result are derived here. Arguments of
    the same name are rejected instead of being copied.
    """
    _reject_caller_provenance_claim(
        upstream_provenance_structurally_verified,
        upstream_provenance_independently_verified,
    )
    if runner_contract.get("schema") != RUNNER_SCHEMA:
        raise ValueError("invalid Runner Contract")
    if str(runner_contract.get("state") or "") != "READY_FOR_RUNNER_DESIGN_REVIEW":
        raise ValueError("runner contract is not ready for command policy review")
    if list(runner_contract.get("blockers") or []):
        raise ValueError("runner contract still has blockers")
    runner_manifest_id = _assert_runner_digest(runner_contract)
    decision = _command_policy_decision(
        runner_contract,
        builder_request=builder_request,
        preflight=preflight,
        patch_validation=patch_validation,
        content_attestation=content_attestation,
        requested_environment=requested_environment,
        path_lookup_allowed=path_lookup_allowed,
        parent_environment_inheritance=parent_environment_inheritance,
        absolute_executable_required=absolute_executable_required,
        executable_digest_required=executable_digest_required,
        require_ready_runner=True,
    )
    blockers = list(decision["blockers"])
    validated_budget = decision["validated_budget"]
    fixed_environment = dict(FIXED_ENVIRONMENT)
    state = decision["state"]

    return _bind_command_policy_ids({
        "schema": SCHEMA,
        "state": state,
        "upstream_provenance_structurally_verified": decision["structural"],
        "upstream_provenance_independently_verified": False,
        "upstream_provenance_binding_id": decision["binding"],
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
    "expected_command_policy_state_and_blockers",
    "expected_command_policy_payload",
    "assert_runner_policy_boundary",
    "assert_command_policy_provenance",
    "build_command_policy_contract",
]
