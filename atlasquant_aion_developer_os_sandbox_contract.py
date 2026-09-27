"""Data-only security contract for a future operating-system sandbox.

This module describes the properties a later physical probe would have to
prove. It does not create a sandbox, start a process, resolve an executable,
open a file for enforcement, or use the network.

Four checks stay distinct:

INTERNAL INTEGRITY: the digest matches the bytes of this document.
LOCAL SEMANTICS: the sealed requirements and closed flags are the canonical
design, and state agrees with the contractual blockers.
STRUCTURAL PROVENANCE: the builder request, preflight, patch validation,
content attestation, runner and command policy already agree. This contract
reuses that comparison. It does not establish an independent root of trust.
PHYSICAL PROOF: not implemented. Every physical verification flag stays false.
Those flags are required before any future execution. They are not design
blockers, and they do not prevent ``READY_FOR_OS_SANDBOX_PROBE_DESIGN``.

Design blockers mean a contractual requirement is missing. The
``required_before_future_execution`` list means a physical proof is still
absent. A false verification flag belongs to the second list.

``READY_FOR_OS_SANDBOX_PROBE_DESIGN`` means the probe requirements are fully
described. It does not mean a sandbox is running. ``READY_FOR_EXECUTION`` is
not a state of this contract. The older design-review document is only a
projection of this decision.

Executable paths in this phase are the existing POSIX pinning contract.
Windows physical path support is future work. ``platform_adapter`` stays
``UNRESOLVED`` and ``platform_adapter_verified`` stays false.

Captured stdout and stderr share the existing ``output_bytes`` budget. There
is no separate stdout, stderr, or disk-write enforcement value.

No shell, subprocess, container, namespace, seccomp, cgroup, chroot, or
binary hash is created here.
"""
from __future__ import annotations

from typing import Any, Mapping

from atlasquant_aion_developer_command_policy import assert_command_policy_provenance
from atlasquant_aion_developer_executable_pinning import (
    ALLOWED_LOGICAL_EXECUTABLES,
    FIXED_ENVIRONMENT,
    SANDBOX_EPHEMERAL_PYCACHE,
    assert_executable_pinning_spec_integrity,
    sealed_environment_blockers,
)
from atlasquant_aion_developer_manifest import stable_digest
from atlasquant_aion_developer_sandbox_preflight import validate_resource_budget

SCHEMA = "ATLASQUANT_AION_DEVELOPER_OS_SANDBOX_CONTRACT_V1"
READY_STATE = "READY_FOR_OS_SANDBOX_PROBE_DESIGN"
BLOCKED_STATE = "BLOCKED"
_ALLOWED_STATES = frozenset({READY_STATE, BLOCKED_STATE})
PLATFORM_ADAPTER = "UNRESOLVED"
SUPPORTED_FUTURE_ADAPTERS = ("LINUX", "WINDOWS")

EPHEMERAL_WRITE_CANDIDATES = (
    "<SANDBOX_TEMP>",
    SANDBOX_EPHEMERAL_PYCACHE,
    "<SANDBOX_OUTPUT_CAPTURE>",
)
FILESYSTEM_REQUIREMENTS = (
    "REPOSITORY_ROOT_BOUND",
    "SOURCE_TREE_READ_ONLY",
    "EPHEMERAL_WRITE_CANDIDATES_ONLY",
    "NO_REPO_WRITE",
    "NO_RENAME",
    "NO_DELETE",
    "NO_CHMOD",
    "NO_CHOWN",
    "NO_HARDLINK_CREATION",
    "NO_SYMLINK_ESCAPE",
    "NO_PATH_TRAVERSAL",
    "NO_MOUNT",
    "NO_DEVICE_ACCESS",
)
TOCTOU_REQUIREMENTS = (
    "RESOLVE_FINAL_PATH_INSIDE_SANDBOX",
    "REJECT_SYMLINK_ESCAPE",
    "REJECT_WINDOWS_REPARSE_POINT_ESCAPE",
    "REJECT_HARDLINK_OUTSIDE_PERMITTED_AREA",
    "VALIDATE_AFTER_SECURE_HANDLE",
    "DO_NOT_TRUST_PATH_STRING_ALONE",
    "MITIGATE_TOCTOU_BETWEEN_CHECK_AND_USE",
)
PHYSICAL_PROOF_BLOCKERS = (
    "EXECUTABLE_PINNING_PROOF_REQUIRED",
    "CHILD_PROCESS_POLICY_PROOF_REQUIRED",
    "NETWORK_ISOLATION_PROOF_REQUIRED",
    "FILESYSTEM_ISOLATION_PROOF_REQUIRED",
    "SYMLINK_PHYSICAL_PROOF_REQUIRED",
    "HARDLINK_PHYSICAL_PROOF_REQUIRED",
    "TOCTOU_PHYSICAL_PROOF_REQUIRED",
    "ENVIRONMENT_ISOLATION_PROOF_REQUIRED",
    "RESOURCE_LIMITS_PROOF_REQUIRED",
    "OUTPUT_LIMITS_PROOF_REQUIRED",
    "PLATFORM_ADAPTER_PROOF_REQUIRED",
    "OS_SANDBOX_PROOF_REQUIRED",
)
REQUIRED_BEFORE_FUTURE_EXECUTION = PHYSICAL_PROOF_BLOCKERS + (
    "FUTURE_PROBE_DISK_WRITE_MB_NOT_DEFINED",
    "FUTURE_PROBE_STDOUT_BYTES_NOT_DEFINED",
    "FUTURE_PROBE_STDERR_BYTES_NOT_DEFINED",
)
FUTURE_RESOURCE_PROBE_FIELDS = (
    "disk_write_mb",
    "stdout_bytes",
    "stderr_bytes",
)
EXECUTABLE_PATH_MODEL = "POSIX_PINNING_CONTRACT"
WINDOWS_PHYSICAL_PATH_SUPPORT = "FUTURE_WORK"
_FALSE_FLAGS = (
    "shell_allowed",
    "arbitrary_process_spawn_allowed",
    "process_tree_escape_allowed",
    "detached_process_allowed",
    "background_process_allowed",
    "network_allowed",
    "dns_allowed",
    "loopback_allowed",
    "outbound_allowed",
    "inbound_allowed",
    "repo_write_allowed",
    "rename_allowed",
    "delete_allowed",
    "chmod_allowed",
    "chown_allowed",
    "hardlink_creation_allowed",
    "symlink_escape_allowed",
    "path_traversal_allowed",
    "mount_allowed",
    "device_access_allowed",
    "parent_environment_inheritance",
    "caller_environment_overrides_allowed",
    "path_lookup_allowed",
    "secrets_mounted",
    "binary_output_allowed",
    "truncation_hides_security_status",
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
    "content_binding_independently_verified",
    "upstream_provenance_independently_verified",
    "executable_pinning_verified",
    "os_sandbox_verified",
    "child_process_policy_verified",
    "filesystem_isolation_verified",
    "network_isolation_verified",
    "resource_limits_verified",
    "environment_isolation_verified",
    "output_limits_verified",
    "symlink_physical_boundary_verified",
    "hardlink_physical_boundary_verified",
    "platform_adapter_verified",
)
_TRUE_REQUIREMENTS = (
    "repository_root_bound",
    "stdout_captured",
    "stderr_captured",
    "pinned_executables_only",
    "upstream_provenance_structurally_verified",
    "sandbox_contract_is_data_only",
)
_ESCALATION_FIELDS = (
    "sandbox_escape_allowed",
    "physical_probe_passed",
    "root_of_trust_verified",
    "ready_for_execution",
    "execution_authorized",
)
_CLAIM_FLAGS = (
    "executable_pinning_verified",
    "os_sandbox_verified",
    "child_process_policy_verified",
    "filesystem_isolation_verified",
    "network_isolation_verified",
    "resource_limits_verified",
    "environment_isolation_verified",
    "output_limits_verified",
    "symlink_physical_boundary_verified",
    "hardlink_physical_boundary_verified",
    "platform_adapter_verified",
    "content_binding_independently_verified",
    "upstream_provenance_independently_verified",
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
_CONTRACT_KEYS = frozenset({
    "schema",
    "state",
    "blockers",
    "physical_proof_blockers",
    "required_before_future_execution",
    "runner_contract_id",
    "command_policy_id",
    "upstream_provenance_binding_id",
    "upstream_provenance_structurally_verified",
    "pinning_spec_id",
    "pinned_logical_executables",
    "environment_binding_id",
    "child_process_policy",
    "pinned_executables_only",
    "network_default",
    "source_tree_mode",
    "repository_root_bound",
    "ephemeral_write_candidates",
    "filesystem_requirements",
    "toctou_requirements",
    "fixed_environment",
    "resource_budget",
    "resource_limit_fields",
    "stdout_captured",
    "stderr_captured",
    "output_bound_field",
    "separate_stdout_stderr_budgets_defined",
    "disk_write_budget_defined",
    "future_resource_probe_fields",
    "platform_adapter",
    "supported_future_adapters",
    "executable_path_model",
    "windows_physical_path_support",
    "sandbox_contract_is_data_only",
    "os_sandbox_manifest_id",
    "os_sandbox_contract_id",
    "hazards",
}) | frozenset(_FALSE_FLAGS)


def _reject_true_claims(document: Mapping[str, Any], label: str) -> None:
    for field in _CLAIM_FLAGS:
        if document.get(field) is True:
            raise ValueError(f"{label} cannot claim {field}")
    for field in _ESCALATION_FIELDS:
        if document.get(field) is True:
            raise ValueError(f"{label} cannot escalate through {field}")


def _reject_caller_claims(claims: Mapping[str, Any]) -> None:
    for field, value in claims.items():
        if value is not None:
            raise ValueError(f"caller cannot assert {field}")


def environment_binding_id(environment: Mapping[str, Any]) -> str:
    """Digest the environment declaration. This is not a physical measurement."""
    blockers = environment.get("blockers")
    return stable_digest(
        {
            "state": environment.get("state"),
            "blockers": list(blockers) if isinstance(blockers, (list, tuple)) else blockers,
            "inherit_parent_environment": environment.get("inherit_parent_environment"),
            "path_lookup_allowed": environment.get("path_lookup_allowed"),
            "caller_environment_overrides_allowed": environment.get(
                "caller_environment_overrides_allowed"
            ),
            "fixed_environment": environment.get("fixed_environment"),
            "caller_environment_accepted": environment.get("caller_environment_accepted"),
            "rejected_environment_keys": list(environment.get("rejected_environment_keys") or []),
        },
        prefix="DEVENV-",
        length=18,
    )


def _contractual_blockers(
    command_policy: Mapping[str, Any],
    preflight: Mapping[str, Any],
    pinning_spec: Mapping[str, Any],
    environment_contract: Mapping[str, Any],
) -> list[str]:
    """Design gaps still visible on the supplied documents.

    A false physical-verification flag is not a gap. Claiming that flag is
    true is rejected before this list is built.
    """
    blockers: list[str] = []
    allowlist = (
        command_policy.get("allowlist_policy")
        if isinstance(command_policy.get("allowlist_policy"), Mapping)
        else {}
    )
    if command_policy.get("shell_allowed") is True or allowlist.get("shell_allowed") is True:
        blockers.append("SHELL_NOT_ALLOWED")
    if command_policy.get("network_allowed") is True or allowlist.get("network_allowed") is True:
        blockers.append("NETWORK_NOT_ALLOWED")
    if (
        command_policy.get("repo_write_allowed") is True
        or allowlist.get("repo_write_allowed") is True
    ):
        blockers.append("REPO_WRITE_NOT_ALLOWED")
    blockers.extend(sealed_environment_blockers(environment_contract))
    preflight_env = (
        preflight.get("environment_contract")
        if isinstance(preflight.get("environment_contract"), Mapping)
        else {}
    )
    if preflight_env.get("secrets_mounted") is not False:
        blockers.append("SECRETS_MUST_NOT_BE_MOUNTED")
    assert_executable_pinning_spec_integrity(pinning_spec)
    policy_budget = (
        command_policy.get("resource_budget")
        if isinstance(command_policy.get("resource_budget"), Mapping)
        else None
    )
    preflight_budget = (
        preflight.get("resource_budget")
        if isinstance(preflight.get("resource_budget"), Mapping)
        else None
    )
    if policy_budget != preflight_budget:
        blockers.append("RESOURCE_BUDGET_MISMATCH")
    return list(dict.fromkeys(blockers))


def _design_view(
    command_policy: Mapping[str, Any],
    runner_contract: Mapping[str, Any],
    preflight: Mapping[str, Any],
    pinning_spec: Mapping[str, Any],
    environment_contract: Mapping[str, Any],
    *,
    state: str,
    blockers: list[str],
) -> dict[str, Any]:
    budget = dict(command_policy.get("resource_budget") or {})
    return {
        "state": state,
        "blockers": list(blockers),
        "physical_proof_blockers": list(PHYSICAL_PROOF_BLOCKERS),
        "required_before_future_execution": list(REQUIRED_BEFORE_FUTURE_EXECUTION),
        "runner_contract_id": runner_contract.get("runner_contract_id"),
        "command_policy_id": command_policy.get("command_policy_id"),
        "upstream_provenance_binding_id": command_policy.get("upstream_provenance_binding_id"),
        "upstream_provenance_structurally_verified": True,
        "upstream_provenance_independently_verified": False,
        "pinning_spec_id": pinning_spec.get("pinning_spec_id"),
        "pinned_logical_executables": list(ALLOWED_LOGICAL_EXECUTABLES),
        "environment_binding_id": environment_binding_id(environment_contract),
        "child_process_policy": "DENY_BY_DEFAULT",
        "pinned_executables_only": True,
        "network_default": "DENY",
        "source_tree_mode": "READ_ONLY",
        "repository_root_bound": True,
        "ephemeral_write_candidates": list(EPHEMERAL_WRITE_CANDIDATES),
        "filesystem_requirements": list(FILESYSTEM_REQUIREMENTS),
        "toctou_requirements": list(TOCTOU_REQUIREMENTS),
        "fixed_environment": dict(FIXED_ENVIRONMENT),
        "resource_budget": {
            "runtime_seconds": budget.get("runtime_seconds"),
            "memory_mb": budget.get("memory_mb"),
            "output_bytes": budget.get("output_bytes"),
            "max_commands": budget.get("max_commands"),
        },
        "resource_limit_fields": [
            "max_commands",
            "runtime_seconds",
            "memory_mb",
            "output_bytes",
        ],
        "stdout_captured": True,
        "stderr_captured": True,
        "output_bound_field": "output_bytes",
        "separate_stdout_stderr_budgets_defined": False,
        "disk_write_budget_defined": False,
        "future_resource_probe_fields": list(FUTURE_RESOURCE_PROBE_FIELDS),
        "platform_adapter": PLATFORM_ADAPTER,
        "supported_future_adapters": list(SUPPORTED_FUTURE_ADAPTERS),
        "executable_path_model": EXECUTABLE_PATH_MODEL,
        "windows_physical_path_support": WINDOWS_PHYSICAL_PATH_SUPPORT,
        "sandbox_contract_is_data_only": True,
        **{field: False for field in _FALSE_FLAGS},
    }


def os_sandbox_manifest(contract: Mapping[str, Any]) -> dict[str, Any]:
    """Authority fields. Informational hazards are outside this digest.

    ``state`` and ``blockers`` are the design decision. ``physical_proof_blockers``
    and ``required_before_future_execution`` record absent physical proof.
    They stay present on a ready probe-design contract. Clearing either list
    is not a passed probe, and neither list authorizes execution.
    """
    if not isinstance(contract, Mapping):
        raise ValueError("os sandbox contract must be an object")
    blockers = contract.get("blockers")
    physical = contract.get("physical_proof_blockers")
    budget = contract.get("resource_budget") if isinstance(contract.get("resource_budget"), Mapping) else {}
    return {
        "state": contract.get("state"),
        "blockers": list(blockers) if isinstance(blockers, (list, tuple)) else blockers,
        "physical_proof_blockers": list(physical) if isinstance(physical, (list, tuple)) else physical,
        "required_before_future_execution": list(
            contract.get("required_before_future_execution") or []
        ),
        "runner_contract_id": contract.get("runner_contract_id"),
        "command_policy_id": contract.get("command_policy_id"),
        "upstream_provenance_binding_id": contract.get("upstream_provenance_binding_id"),
        "upstream_provenance_structurally_verified": contract.get(
            "upstream_provenance_structurally_verified"
        ),
        "upstream_provenance_independently_verified": contract.get(
            "upstream_provenance_independently_verified"
        ),
        "pinning_spec_id": contract.get("pinning_spec_id"),
        "pinned_logical_executables": list(contract.get("pinned_logical_executables") or []),
        "environment_binding_id": contract.get("environment_binding_id"),
        "child_process_policy": contract.get("child_process_policy"),
        "pinned_executables_only": contract.get("pinned_executables_only"),
        "network_default": contract.get("network_default"),
        "source_tree_mode": contract.get("source_tree_mode"),
        "repository_root_bound": contract.get("repository_root_bound"),
        "ephemeral_write_candidates": list(contract.get("ephemeral_write_candidates") or []),
        "filesystem_requirements": list(contract.get("filesystem_requirements") or []),
        "toctou_requirements": list(contract.get("toctou_requirements") or []),
        "fixed_environment": contract.get("fixed_environment"),
        "resource_budget": {
            "runtime_seconds": budget.get("runtime_seconds"),
            "memory_mb": budget.get("memory_mb"),
            "output_bytes": budget.get("output_bytes"),
            "max_commands": budget.get("max_commands"),
        },
        "resource_limit_fields": list(contract.get("resource_limit_fields") or []),
        "stdout_captured": contract.get("stdout_captured"),
        "stderr_captured": contract.get("stderr_captured"),
        "output_bound_field": contract.get("output_bound_field"),
        "separate_stdout_stderr_budgets_defined": contract.get(
            "separate_stdout_stderr_budgets_defined"
        ),
        "disk_write_budget_defined": contract.get("disk_write_budget_defined"),
        "future_resource_probe_fields": list(contract.get("future_resource_probe_fields") or []),
        "platform_adapter": contract.get("platform_adapter"),
        "supported_future_adapters": list(contract.get("supported_future_adapters") or []),
        "executable_path_model": contract.get("executable_path_model"),
        "windows_physical_path_support": contract.get("windows_physical_path_support"),
        "sandbox_contract_is_data_only": contract.get("sandbox_contract_is_data_only"),
        **{field: contract.get(field) for field in _FALSE_FLAGS},
    }


def os_sandbox_manifest_id(contract: Mapping[str, Any]) -> str:
    return stable_digest(os_sandbox_manifest(contract), prefix="DEVOSMAN-", length=18)


def expected_os_sandbox_contract_id(contract: Mapping[str, Any]) -> str:
    """Digest the manifest id. A caller-supplied contract id is not an input."""
    return stable_digest(
        {"os_sandbox_manifest_id": os_sandbox_manifest_id(contract)},
        prefix="DEVOS-",
        length=18,
    )


def _bind_os_sandbox_ids(contract: dict[str, Any]) -> dict[str, Any]:
    contract["os_sandbox_manifest_id"] = os_sandbox_manifest_id(contract)
    contract["os_sandbox_contract_id"] = expected_os_sandbox_contract_id(contract)
    return contract


def _assert_budget_exact(budget: Mapping[str, Any]) -> None:
    validated, blockers = validate_resource_budget(budget)
    if blockers or dict(budget) != validated:
        raise ValueError("resource budget is not the canonical exact-int budget")


def expected_os_sandbox_state_and_blockers(
    command_policy: Mapping[str, Any],
    runner_contract: Mapping[str, Any],
    builder_request: Mapping[str, Any],
    preflight: Mapping[str, Any],
    patch_validation: Mapping[str, Any],
    content_attestation: Mapping[str, Any],
    pinning_spec: Mapping[str, Any],
    environment_contract: Mapping[str, Any],
) -> tuple[str, list[str]]:
    """State this chain would seal. Physical proof stays a separate list.

    ``READY_FOR_OS_SANDBOX_PROBE_DESIGN`` requires an empty contractual
    blocker list. The physical-proof list is still required and still false
    as verification.
    """
    for label, document in (
        ("command policy", command_policy),
        ("runner contract", runner_contract),
        ("pinning spec", pinning_spec),
        ("environment contract", environment_contract),
        ("content attestation", content_attestation),
    ):
        if not isinstance(document, Mapping):
            raise ValueError(f"{label} must be an object")
        _reject_true_claims(document, label)
    assert_command_policy_provenance(
        command_policy,
        runner_contract,
        builder_request,
        preflight,
        patch_validation,
        content_attestation,
    )
    if command_policy.get("upstream_provenance_structurally_verified") is not True:
        raise ValueError("command policy structural provenance was not derived")
    if command_policy.get("upstream_provenance_independently_verified") is not False:
        raise ValueError("independent root of trust is not established")
    budget = command_policy.get("resource_budget")
    if isinstance(budget, Mapping):
        _assert_budget_exact(budget)
    blockers = _contractual_blockers(
        command_policy,
        preflight,
        pinning_spec,
        environment_contract,
    )
    state = READY_STATE if not blockers else BLOCKED_STATE
    return state, blockers


def assert_os_sandbox_contract_integrity(contract: Mapping[str, Any]) -> str:
    """Revalidate the sealed design. A matching id is not a physical probe."""
    if not isinstance(contract, Mapping):
        raise ValueError("os sandbox contract must be an object")
    if contract.get("schema") != SCHEMA:
        raise ValueError("invalid os sandbox contract")
    unknown = sorted(set(contract) - _CONTRACT_KEYS)
    if unknown:
        raise ValueError(f"unknown os sandbox authority field {unknown[0]}")
    _reject_true_claims(contract, "os sandbox contract")
    if contract.get("state") not in _ALLOWED_STATES:
        raise ValueError("os sandbox state is not an accepted design state")
    if contract.get("state") == "READY_FOR_EXECUTION":
        raise ValueError("os sandbox contract cannot be ready for execution")
    blockers = contract.get("blockers")
    physical = contract.get("physical_proof_blockers")
    if not isinstance(blockers, list) or not isinstance(physical, list):
        raise ValueError("os sandbox blockers must be lists")
    if list(physical) != list(PHYSICAL_PROOF_BLOCKERS):
        raise ValueError("physical proof blockers are not the canonical absent-proof list")
    future = contract.get("required_before_future_execution")
    if (
        not isinstance(future, list)
        or list(future) != list(REQUIRED_BEFORE_FUTURE_EXECUTION)
    ):
        raise ValueError("required before future execution is not the canonical absent-proof list")
    if contract.get("state") == READY_STATE:
        if blockers:
            raise ValueError("ready os sandbox design cannot carry contractual blockers")
    elif not blockers:
        raise ValueError("blocked os sandbox design must name contractual blockers")
    for field in _FALSE_FLAGS:
        if contract.get(field) is not False:
            raise ValueError(f"os sandbox flag {field} is not false")
    for field in _TRUE_REQUIREMENTS:
        if contract.get(field) is not True:
            raise ValueError(f"os sandbox requirement {field} is not true")
    if contract.get("child_process_policy") != "DENY_BY_DEFAULT":
        raise ValueError("child process policy must deny by default")
    if contract.get("network_default") != "DENY":
        raise ValueError("network default must deny")
    if contract.get("source_tree_mode") != "READ_ONLY":
        raise ValueError("source tree must be read only")
    if contract.get("platform_adapter") != PLATFORM_ADAPTER:
        raise ValueError("platform adapter is unresolved")
    if list(contract.get("supported_future_adapters") or []) != list(SUPPORTED_FUTURE_ADAPTERS):
        raise ValueError("future platform adapters are not the logical pair")
    if list(contract.get("toctou_requirements") or []) != list(TOCTOU_REQUIREMENTS):
        raise ValueError("toctou requirements were not preserved")
    if list(contract.get("filesystem_requirements") or []) != list(FILESYSTEM_REQUIREMENTS):
        raise ValueError("filesystem requirements were not preserved")
    if list(contract.get("ephemeral_write_candidates") or []) != list(EPHEMERAL_WRITE_CANDIDATES):
        raise ValueError("ephemeral write candidates were not preserved")
    if dict(contract.get("fixed_environment") or {}) != dict(FIXED_ENVIRONMENT):
        raise ValueError("fixed environment is not the canonical map")
    budget = contract.get("resource_budget")
    if not isinstance(budget, Mapping):
        raise ValueError("resource budget must be an object")
    _assert_budget_exact(budget)
    if contract.get("output_bound_field") != "output_bytes":
        raise ValueError("output bound must stay the existing output_bytes field")
    if contract.get("separate_stdout_stderr_budgets_defined") is not False:
        raise ValueError("separate stdout and stderr budgets are not defined")
    if contract.get("disk_write_budget_defined") is not False:
        raise ValueError("disk write budget is not defined")
    if list(contract.get("future_resource_probe_fields") or []) != list(FUTURE_RESOURCE_PROBE_FIELDS):
        raise ValueError("future resource probe fields are not the undeclared names")
    if contract.get("executable_path_model") != EXECUTABLE_PATH_MODEL:
        raise ValueError("executable path model is the POSIX pinning contract")
    if contract.get("windows_physical_path_support") != WINDOWS_PHYSICAL_PATH_SUPPORT:
        raise ValueError("windows physical path support is future work")
    if set(budget) != {"runtime_seconds", "memory_mb", "output_bytes", "max_commands"}:
        raise ValueError("resource budget contains a field that is not enforced")
    manifest_id = os_sandbox_manifest_id(contract)
    if contract.get("os_sandbox_manifest_id") != manifest_id:
        raise ValueError("os sandbox manifest mismatch")
    if contract.get("os_sandbox_contract_id") != expected_os_sandbox_contract_id(contract):
        raise ValueError("os sandbox contract id mismatch")
    return manifest_id


def assert_os_sandbox_contract(
    contract: Mapping[str, Any],
    command_policy: Mapping[str, Any],
    runner_contract: Mapping[str, Any],
    builder_request: Mapping[str, Any],
    preflight: Mapping[str, Any],
    patch_validation: Mapping[str, Any],
    content_attestation: Mapping[str, Any],
    pinning_spec: Mapping[str, Any],
    environment_contract: Mapping[str, Any],
) -> None:
    """Reject a contract whose id matches but whose inputs were not these documents."""
    assert_os_sandbox_contract_integrity(contract)
    state, blockers = expected_os_sandbox_state_and_blockers(
        command_policy,
        runner_contract,
        builder_request,
        preflight,
        patch_validation,
        content_attestation,
        pinning_spec,
        environment_contract,
    )
    expected = _design_view(
        command_policy,
        runner_contract,
        preflight,
        pinning_spec,
        environment_contract,
        state=state,
        blockers=blockers,
    )
    sealed = os_sandbox_manifest(contract)
    for field, value in expected.items():
        if sealed.get(field) != value:
            raise ValueError(f"os sandbox {field} was not derived from the supplied chain")


def build_os_sandbox_contract(
    command_policy: Mapping[str, Any],
    runner_contract: Mapping[str, Any],
    builder_request: Mapping[str, Any],
    preflight: Mapping[str, Any],
    patch_validation: Mapping[str, Any],
    content_attestation: Mapping[str, Any],
    pinning_spec: Mapping[str, Any],
    environment_contract: Mapping[str, Any],
    **caller_claims: Any,
) -> dict[str, Any]:
    """Seal the sandbox security design. Caller verification flags are rejected.

    The result is data. ``READY_FOR_OS_SANDBOX_PROBE_DESIGN`` describes a
    complete probe checklist. Physical verification flags remain false.
    """
    _reject_caller_claims(caller_claims)
    state, blockers = expected_os_sandbox_state_and_blockers(
        command_policy,
        runner_contract,
        builder_request,
        preflight,
        patch_validation,
        content_attestation,
        pinning_spec,
        environment_contract,
    )
    view = _design_view(
        command_policy,
        runner_contract,
        preflight,
        pinning_spec,
        environment_contract,
        state=state,
        blockers=blockers,
    )
    return _bind_os_sandbox_ids({
        "schema": SCHEMA,
        **view,
        "hazards": [
            "This contract does not create an operating-system sandbox.",
            "Pinned paths and digests are caller claims until a physical probe reads the binaries.",
            "Symlink, hardlink and TOCTOU resistance are requirements, not measurements.",
            "A matching digest does not prove process, network, or filesystem isolation.",
        ],
    })


__all__ = [
    "SCHEMA",
    "READY_STATE",
    "PHYSICAL_PROOF_BLOCKERS",
    "REQUIRED_BEFORE_FUTURE_EXECUTION",
    "FUTURE_RESOURCE_PROBE_FIELDS",
    "EXECUTABLE_PATH_MODEL",
    "WINDOWS_PHYSICAL_PATH_SUPPORT",
    "TOCTOU_REQUIREMENTS",
    "FILESYSTEM_REQUIREMENTS",
    "os_sandbox_manifest",
    "os_sandbox_manifest_id",
    "expected_os_sandbox_contract_id",
    "expected_os_sandbox_state_and_blockers",
    "assert_os_sandbox_contract_integrity",
    "assert_os_sandbox_contract",
    "build_os_sandbox_contract",
]
