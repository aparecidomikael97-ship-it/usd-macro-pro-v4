"""Data-only executable pinning and minimum environment contracts.

Pins record a caller claim. This module does not stat, read, or hash a
binary, so executable_pinning_verified stays false even when the spec is
complete. /tmp/python, a symlink, an arbitrary absolute path and a
caller-supplied digest are claims, not proof.

Physical executable paths follow this POSIX pinning contract. Windows drive
and UNC paths are rejected here. A Windows adapter is future work, not a
verified platform.

``build_os_sandbox_design_review`` is a compatibility projection. Readiness is
decided only by the OS sandbox security contract. This module does not keep a
second state machine. READY_FOR_EXECUTION is not produced.
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


def forbidden_inherited_environment_key(key: Any) -> bool:
    """True for an exact forbidden name or any git_config* key.

    ``GIT_CONFIG_COUNT``, ``GIT_CONFIG_KEY_0`` and ``GIT_CONFIG_VALUE_0`` are
    covered by the prefix. Matching is case-insensitive and does not read the
    process environment.
    """
    folded = str(key).casefold()
    return folded in FORBIDDEN_INHERITED_ENVIRONMENT or folded.startswith("git_config")


def require_absolute_path(value: Any, field: str = "absolute_path") -> str:
    """Require an explicit POSIX absolute path. Relative and PATH lookups fail.

    Backslash, drive-letter and UNC forms are rejected. That is the current
    pinning contract, not verified Windows path support.
    """
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


_PIN_FIELDS = frozenset({
    "logical_name",
    "absolute_path",
    "sha256",
    "file_size_bytes",
    "version_claim",
    "verification_evidence_refs",
})
PINNING_READY_STATE = "READY_FOR_EXECUTABLE_PINNING_PROBE"


def _validated_pin(pin: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(pin, Mapping):
        raise ValueError("executable pin must be an object")
    if set(pin) != _PIN_FIELDS:
        raise ValueError("executable pin fields are not the closed pin schema")
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


def executable_pinning_manifest(spec: Mapping[str, Any]) -> dict[str, Any]:
    """Authority fields for a pinning spec, including state and completeness.

    The id is not part of the manifest. A caller-supplied digest is not proof
    that a binary was read.
    """
    pins = spec.get("pins")
    rows: list[dict[str, Any]] = []
    if isinstance(pins, (list, tuple)) and not isinstance(pins, (str, bytes, bytearray)):
        for pin in pins:
            if not isinstance(pin, Mapping):
                rows.append({"invalid": True})
                continue
            evidence = pin.get("verification_evidence_refs")
            rows.append({
                "logical_name": pin.get("logical_name"),
                "absolute_path": pin.get("absolute_path"),
                "sha256": pin.get("sha256"),
                "file_size_bytes": pin.get("file_size_bytes"),
                "version_claim": pin.get("version_claim"),
                "verification_evidence_refs": (
                    list(evidence) if isinstance(evidence, (list, tuple)) else evidence
                ),
            })
    return {
        "schema": spec.get("schema"),
        "state": spec.get("state"),
        "pinning_spec_complete": spec.get("pinning_spec_complete"),
        "pins": rows,
        "logical_executables": list(spec.get("logical_executables") or []),
        "path_lookup_allowed": spec.get("path_lookup_allowed"),
        "absolute_executable_required": spec.get("absolute_executable_required"),
        "executable_digest_required": spec.get("executable_digest_required"),
        "caller_supplied_digest_is_proof": spec.get("caller_supplied_digest_is_proof"),
        "executable_pinning_verified": spec.get("executable_pinning_verified"),
        "os_sandbox_verified": spec.get("os_sandbox_verified"),
        "child_process_policy_verified": spec.get("child_process_policy_verified"),
        "symlink_physical_boundary_verified": spec.get("symlink_physical_boundary_verified"),
        "hardlink_physical_boundary_verified": spec.get("hardlink_physical_boundary_verified"),
        "execution_authorized": spec.get("execution_authorized"),
    }


def expected_pinning_spec_id(spec: Mapping[str, Any]) -> str:
    """Recompute the pinning id. State and completeness are inside this digest."""
    return stable_digest(executable_pinning_manifest(spec), prefix="DEVPIN-", length=18)


def assert_executable_pinning_spec_integrity(spec: Mapping[str, Any]) -> str:
    """Revalidate a pinning spec. State and completeness are not trusted alone."""
    if not isinstance(spec, Mapping):
        raise ValueError("pinning spec must be an object")
    if spec.get("schema") != SCHEMA:
        raise ValueError("invalid pinning spec")
    _reject_true_claims(spec, "pinning spec")
    pins = spec.get("pins")
    if isinstance(pins, (str, bytes, bytearray)) or not isinstance(pins, (list, tuple)):
        raise ValueError("pins must be an explicit list or tuple")
    validated = [_validated_pin(pin) for pin in pins]
    names = [pin["logical_name"] for pin in validated]
    if len(names) != len(set(names)) or set(names) != set(ALLOWED_LOGICAL_EXECUTABLES):
        raise ValueError("python and git pins are both required and no extra executable is allowed")
    ordered = [dict(pin) for pin in sorted(validated, key=lambda pin: pin["logical_name"])]
    if [dict(pin) for pin in pins] != ordered:
        raise ValueError("pins are not the canonical ordered pin set")
    if spec.get("state") != PINNING_READY_STATE:
        raise ValueError("pinning spec state was not reconstructed")
    if spec.get("pinning_spec_complete") is not True:
        raise ValueError("pinning spec completeness was not reconstructed")
    if list(spec.get("logical_executables") or []) != list(ALLOWED_LOGICAL_EXECUTABLES):
        raise ValueError("logical executables are not the allowlist")
    if spec.get("path_lookup_allowed") is not False:
        raise ValueError("pinning spec cannot allow path lookup")
    if spec.get("absolute_executable_required") is not True:
        raise ValueError("absolute executable must stay required")
    if spec.get("executable_digest_required") is not True:
        raise ValueError("executable digest must stay required")
    if spec.get("caller_supplied_digest_is_proof") is not False:
        raise ValueError("caller digest is not proof")
    for field in (
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
    ):
        if spec.get(field) is not False:
            raise ValueError(f"pinning spec flag {field} is not false")
    spec_id = expected_pinning_spec_id(spec)
    if spec.get("pinning_spec_id") != spec_id:
        raise ValueError("pinning spec id mismatch")
    return spec_id


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
    document = {
        "schema": SCHEMA,
        "state": PINNING_READY_STATE,
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
    spec_id = expected_pinning_spec_id(document)
    if pinning_spec_id is not None and pinning_spec_id != spec_id:
        raise ValueError("pinning spec id mismatch")
    document["pinning_spec_id"] = spec_id
    return document


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
    rejected = sorted({
        str(key).casefold()
        for key in supplied
        if forbidden_inherited_environment_key(key)
    })
    if rejected:
        blockers.append("INHERITED_ENVIRONMENT_KEY_NOT_ALLOWED")
    if fixed_environment is not None and dict(fixed_environment) != FIXED_ENVIRONMENT:
        blockers.append("FIXED_ENVIRONMENT_MISMATCH")
    elif isinstance(fixed_environment, Mapping) and any(
        forbidden_inherited_environment_key(key) for key in fixed_environment
    ):
        blockers.append("INHERITED_ENVIRONMENT_KEY_NOT_ALLOWED")
    blockers = list(dict.fromkeys(blockers))
    return {
        "schema": ENVIRONMENT_SCHEMA,
        "state": "ENVIRONMENT_DECLARED" if not blockers else "BLOCKED",
        "inherit_parent_environment": False,
        "path_lookup_allowed": False,
        "caller_environment_overrides_allowed": False,
        "fixed_environment": dict(FIXED_ENVIRONMENT),
        "caller_environment_accepted": False,
        "rejected_environment_keys": rejected,
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


def sealed_environment_blockers(environment: Mapping[str, Any]) -> list[str]:
    """Recompute environment design blockers without trusting the state label.

    ``ENVIRONMENT_DECLARED`` is not authority. A cleared blocker list still
    fails when rejected keys or a non-canonical fixed environment remain.
    """
    if not isinstance(environment, Mapping):
        return ["ENVIRONMENT_CONTRACT_INVALID"]
    blockers: list[str] = []
    if environment.get("schema") != ENVIRONMENT_SCHEMA:
        blockers.append("ENVIRONMENT_CONTRACT_INVALID")
    if environment.get("inherit_parent_environment") is not False:
        blockers.append("PARENT_ENVIRONMENT_INHERITANCE_NOT_ALLOWED")
    if environment.get("path_lookup_allowed") is not False:
        blockers.append("PATH_LOOKUP_NOT_ALLOWED")
    if (
        environment.get("caller_environment_overrides_allowed") is not False
        or environment.get("caller_environment_accepted") is not False
    ):
        blockers.append("CALLER_ENVIRONMENT_OVERRIDES_NOT_ALLOWED")
    fixed = environment.get("fixed_environment")
    if not isinstance(fixed, Mapping) or dict(fixed) != dict(FIXED_ENVIRONMENT):
        blockers.append("FIXED_ENVIRONMENT_MISMATCH")
    elif any(forbidden_inherited_environment_key(key) for key in fixed):
        blockers.append("INHERITED_ENVIRONMENT_KEY_NOT_ALLOWED")
    rejected = environment.get("rejected_environment_keys")
    if not isinstance(rejected, list) or any(type(item) is not str for item in rejected):
        blockers.append("ENVIRONMENT_CONTRACT_INVALID")
    elif rejected:
        blockers.append("INHERITED_ENVIRONMENT_KEY_NOT_ALLOWED")
    declared = environment.get("blockers")
    if not isinstance(declared, list):
        blockers.append("ENVIRONMENT_CONTRACT_INVALID")
    else:
        for item in declared:
            if item == "CALLER_ENVIRONMENT_NOT_ALLOWED":
                item = "CALLER_ENVIRONMENT_OVERRIDES_NOT_ALLOWED"
            if item not in blockers:
                blockers.append(item)
    if environment.get("state") != "ENVIRONMENT_DECLARED" and not blockers:
        blockers.append("ENVIRONMENT_CONTRACT_NOT_DECLARED")
    return list(dict.fromkeys(blockers))


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
    """Project the canonical OS sandbox contract into the design-review schema.

    Readiness is the contract state. This function does not classify pinning,
    environment, or provenance a second time. ``READY_FOR_OS_SANDBOX_DESIGN_REVIEW``
    is emitted only when that contract is ``READY_FOR_OS_SANDBOX_PROBE_DESIGN``.
    Physical verification stays false. No sandbox is created.
    """
    from atlasquant_aion_developer_os_sandbox_contract import (
        READY_STATE,
        build_os_sandbox_contract,
    )

    contract = build_os_sandbox_contract(
        command_policy,
        runner_contract,
        builder_request,
        preflight,
        patch_validation,
        attestation,
        pinning_spec,
        environment_contract,
    )
    ready = (
        contract.get("state") == READY_STATE
        and list(contract.get("blockers") or []) == []
    )
    return {
        "schema": OS_SANDBOX_SCHEMA,
        "state": "READY_FOR_OS_SANDBOX_DESIGN_REVIEW" if ready else "BLOCKED",
        "canonical_schema": contract.get("schema"),
        "canonical_os_sandbox_state": contract.get("state"),
        "canonical_os_sandbox_contract_id": contract.get("os_sandbox_contract_id"),
        "pinning_spec_complete": pinning_spec.get("pinning_spec_complete") is True,
        "content_binding_structurally_bound": attestation.get("content_binding_structurally_bound") is True,
        "content_binding_independently_verified": False,
        "executable_pinning_verified": False,
        "os_sandbox_verified": False,
        "child_process_policy_verified": False,
        "symlink_physical_boundary_verified": False,
        "hardlink_physical_boundary_verified": False,
        "compile_step_executable": False,
        "platform_adapter_verified": False,
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
    "PINNING_READY_STATE",
    "require_absolute_path",
    "forbidden_inherited_environment_key",
    "executable_pinning_manifest",
    "expected_pinning_spec_id",
    "assert_executable_pinning_spec_integrity",
    "build_executable_pinning_spec",
    "build_environment_contract",
    "sealed_environment_blockers",
    "build_os_sandbox_design_review",
]
