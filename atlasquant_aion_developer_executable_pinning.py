"""Data-only executable pinning and minimum environment contracts.

Pins record a caller claim. This module does not stat, read, or hash a
binary, so executable_pinning_verified stays false even when the spec is
complete. /tmp/python, a symlink, an arbitrary absolute path and a
caller-supplied digest are claims, not proof.

The maximum bundle state is READY_FOR_OS_SANDBOX_DESIGN_REVIEW.
READY_FOR_EXECUTION is not produced.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Any, Mapping, Sequence

from atlasquant_aion_developer_manifest import require_string_sequence, stable_digest

SCHEMA = "ATLASQUANT_AION_DEVELOPER_EXECUTABLE_PINNING_V1"
ENVIRONMENT_SCHEMA = "ATLASQUANT_AION_DEVELOPER_ENVIRONMENT_CONTRACT_V1"
OS_SANDBOX_SCHEMA = "ATLASQUANT_AION_DEVELOPER_OS_SANDBOX_DESIGN_REVIEW_V1"

SANDBOX_EPHEMERAL_PYCACHE = "<SANDBOX_EPHEMERAL_PYCACHE>"
ALLOWED_LOGICAL_EXECUTABLES = ("python", "git")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

FORBIDDEN_INHERITED_ENVIRONMENT = frozenset({
    "path",
    "pythonpath",
    "pythonhome",
    "pythonstartup",
    "home",
    "userprofile",
    "git_config",
    "git_config_global",
    "git_config_system",
    "git_dir",
    "git_work_tree",
    "ssh_auth_sock",
    "virtual_env",
})
FIXED_ENVIRONMENT = {
    "PYTHONDONTWRITEBYTECODE": "1",
    "PYTHONNOUSERSITE": "1",
    "PYTHONHASHSEED": "0",
    "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
    "PIP_DISABLE_PIP_VERSION_CHECK": "1",
}
_CLAIM_FLAGS = (
    "executable_pinning_verified",
    "os_sandbox_verified",
    "child_process_policy_verified",
    "symlink_physical_boundary_verified",
    "hardlink_physical_boundary_verified",
    "content_binding_independently_verified",
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
)
_CLOSED_FLAGS = {flag: False for flag in _CLAIM_FLAGS}


def _strict_token(value: Any, field: str, limit: int = 240) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be a string")
    if not value or value != value.strip() or len(value) > limit:
        raise ValueError(f"{field} is empty or malformed")
    if any(unicodedata.category(char) in {"Cc", "Cf"} for char in value):
        raise ValueError(f"{field} contains control or invisible characters")
    return value


def require_absolute_path(value: Any, field: str = "absolute_path") -> str:
    """Require an explicit absolute path. Relative and PATH lookups fail."""
    text = _strict_token(value, field, 500)
    if "\\" in text or text.startswith("~") or not text.startswith("/") or text.startswith("//"):
        raise ValueError(f"{field} must be an explicit absolute path")
    parts = text.split("/")
    if any(part in {"", ".", ".."} for part in parts[1:]):
        raise ValueError(f"{field} must be an explicit absolute path")
    return text


def _reject_true_claims(payload: Mapping[str, Any], label: str) -> None:
    for key in _CLAIM_FLAGS:
        if payload.get(key) is True:
            raise ValueError(f"{label} cannot claim {key}")


def _validated_pin(pin: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(pin, Mapping):
        raise ValueError("executable pin must be an object")
    logical_name = pin.get("logical_name")
    if logical_name not in ALLOWED_LOGICAL_EXECUTABLES:
        raise ValueError("logical executable is not allowlisted")
    digest = pin.get("sha256")
    if not isinstance(digest, str) or not _SHA256_RE.fullmatch(digest):
        raise ValueError("sha256 must be exactly 64 lowercase hex characters")
    size = pin.get("file_size_bytes")
    if type(size) is not int or size <= 0:
        raise ValueError("file_size_bytes must be an exact int greater than zero")
    evidence = require_string_sequence(
        pin.get("verification_evidence_refs"),
        "verification_evidence_refs",
    )
    if not evidence:
        raise ValueError("pin verification evidence refs are required")
    return {
        "logical_name": logical_name,
        "absolute_path": require_absolute_path(pin.get("absolute_path")),
        "sha256": digest,
        "file_size_bytes": size,
        "version_claim": _strict_token(pin.get("version_claim"), "version_claim", 120),
        "verification_evidence_refs": evidence,
    }


def build_executable_pinning_spec(
    pins: Sequence[Any],
    *,
    executable_pinning_verified: bool = False,
    pinning_spec_id: Any = None,
) -> dict[str, Any]:
    """Record a complete python+git pin claim without reading the binaries."""
    if executable_pinning_verified is not False:
        raise ValueError("executable pinning cannot be marked verified without a probe")
    if isinstance(pins, (str, bytes, bytearray)) or not isinstance(pins, (list, tuple)):
        raise ValueError("pins must be an explicit list or tuple")
    validated = [_validated_pin(pin) for pin in pins]
    names = [pin["logical_name"] for pin in validated]
    if len(names) != len(set(names)):
        raise ValueError("duplicate logical executable")
    if set(names) != set(ALLOWED_LOGICAL_EXECUTABLES):
        raise ValueError("python and git pins are both required and no extra executable is allowed")
    ordered = tuple(sorted(validated, key=lambda pin: pin["logical_name"]))
    spec_id = stable_digest(list(ordered), prefix="DEVPIN-", length=18)
    if pinning_spec_id is not None and pinning_spec_id != spec_id:
        raise ValueError("pinning spec id mismatch")
    return {
        "schema": SCHEMA,
        "pinning_spec_id": spec_id,
        "state": "READY_FOR_EXECUTABLE_PINNING_PROBE",
        "pins": [dict(pin) for pin in ordered],
        "logical_executables": list(ALLOWED_LOGICAL_EXECUTABLES),
        "pinning_spec_complete": True,
        "path_lookup_allowed": False,
        "absolute_executable_required": True,
        "executable_digest_required": True,
        "caller_supplied_digest_is_proof": False,
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
    }


def build_environment_contract(
    *,
    inherit_parent_environment: bool = False,
    path_lookup_allowed: bool = False,
    caller_environment_overrides_allowed: bool = False,
    caller_environment: Mapping[str, Any] | None = None,
    fixed_environment: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Declare the minimum environment. Caller environments are not copied."""
    blockers: list[str] = []
    if inherit_parent_environment is not False:
        blockers.append("PARENT_ENVIRONMENT_INHERITANCE_NOT_ALLOWED")
    if path_lookup_allowed is not False:
        blockers.append("PATH_LOOKUP_NOT_ALLOWED")
    if caller_environment_overrides_allowed is not False:
        blockers.append("CALLER_ENVIRONMENT_OVERRIDES_NOT_ALLOWED")
    if caller_environment is not None and not isinstance(caller_environment, Mapping):
        raise ValueError("caller environment must be an object")
    supplied = dict(caller_environment or {})
    if supplied:
        blockers.append("CALLER_ENVIRONMENT_NOT_ALLOWED")
    if any(str(key).casefold() in FORBIDDEN_INHERITED_ENVIRONMENT for key in supplied):
        blockers.append("INHERITED_ENVIRONMENT_KEY_NOT_ALLOWED")
    if fixed_environment is not None and dict(fixed_environment) != FIXED_ENVIRONMENT:
        blockers.append("FIXED_ENVIRONMENT_MISMATCH")
    blockers = list(dict.fromkeys(blockers))
    return {
        "schema": ENVIRONMENT_SCHEMA,
        "state": "ENVIRONMENT_DECLARED" if not blockers else "BLOCKED",
        "inherit_parent_environment": False,
        "path_lookup_allowed": False,
        "caller_environment_overrides_allowed": False,
        "fixed_environment": dict(FIXED_ENVIRONMENT),
        "caller_environment_accepted": False,
        "blockers": blockers,
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
    }


def build_os_sandbox_design_review(
    command_policy: Mapping[str, Any],
    pinning_spec: Mapping[str, Any],
    attestation: Mapping[str, Any],
    environment_contract: Mapping[str, Any],
    *,
    runner_contract: Mapping[str, Any],
    builder_request: Mapping[str, Any],
    preflight: Mapping[str, Any],
    patch_validation: Mapping[str, Any],
) -> dict[str, Any]:
    """Bundle the contracts for design review. This does not authorize execution.

    The runner is checked against the upstream documents, then the command
    policy is checked against that runner. A ready label with blockers, or a
    digest that was recomputed after a mutation, fails closed. This does not
    create an operating-system sandbox.
    """
    from atlasquant_aion_developer_command_policy import assert_runner_policy_boundary
    from atlasquant_aion_developer_runner_contract import assert_runner_provenance

    assert_runner_provenance(
        runner_contract,
        builder_request,
        preflight,
        patch_validation,
        attestation,
    )
    assert_runner_policy_boundary(runner_contract, command_policy)
    if runner_contract.get("state") != "READY_FOR_RUNNER_DESIGN_REVIEW":
        raise ValueError("runner is not ready for design review")
    if list(runner_contract.get("blockers") or []) != []:
        raise ValueError("runner blockers must be empty")
    if command_policy.get("state") != "READY_FOR_EXECUTABLE_PINNING_REVIEW":
        raise ValueError("command policy is not ready for design review")
    if list(command_policy.get("blockers") or []) != []:
        raise ValueError("command policy blockers must be empty")
    for label, document in (
        ("command policy", command_policy),
        ("pinning spec", pinning_spec),
        ("content attestation", attestation),
        ("environment contract", environment_contract),
    ):
        if not isinstance(document, Mapping):
            raise ValueError(f"{label} must be an object")
        _reject_true_claims(document, label)
    ready = (
        command_policy.get("state") == "READY_FOR_EXECUTABLE_PINNING_REVIEW"
        and command_policy.get("executable_pinning_verified") is False
        and pinning_spec.get("state") == "READY_FOR_EXECUTABLE_PINNING_PROBE"
        and pinning_spec.get("pinning_spec_complete") is True
        and pinning_spec.get("executable_pinning_verified") is False
        and attestation.get("content_binding_structurally_bound") is True
        and attestation.get("content_binding_independently_verified") is False
        and environment_contract.get("state") == "ENVIRONMENT_DECLARED"
        and environment_contract.get("inherit_parent_environment") is False
        and environment_contract.get("path_lookup_allowed") is False
        and environment_contract.get("caller_environment_overrides_allowed") is False
        and list(environment_contract.get("blockers") or []) == []
    )
    return {
        "schema": OS_SANDBOX_SCHEMA,
        "state": "READY_FOR_OS_SANDBOX_DESIGN_REVIEW" if ready else "BLOCKED",
        "pinning_spec_complete": pinning_spec.get("pinning_spec_complete") is True,
        "content_binding_structurally_bound": attestation.get("content_binding_structurally_bound") is True,
        "content_binding_independently_verified": False,
        "executable_pinning_verified": False,
        "os_sandbox_verified": False,
        "child_process_policy_verified": False,
        "symlink_physical_boundary_verified": False,
        "hardlink_physical_boundary_verified": False,
        "compile_step_executable": False,
        **_CLOSED_FLAGS,
    }


__all__ = [
    "SCHEMA",
    "ENVIRONMENT_SCHEMA",
    "OS_SANDBOX_SCHEMA",
    "SANDBOX_EPHEMERAL_PYCACHE",
    "ALLOWED_LOGICAL_EXECUTABLES",
    "FORBIDDEN_INHERITED_ENVIRONMENT",
    "FIXED_ENVIRONMENT",
    "require_absolute_path",
    "build_executable_pinning_spec",
    "build_environment_contract",
    "build_os_sandbox_design_review",
]
