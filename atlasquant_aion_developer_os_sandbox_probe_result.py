"""Data-only contract for a future physical-probe result.

Four layers stay separate:

A. The OS sandbox contract describes what a probe would have to prove.
B. A physical probe would measure a real environment. It is not implemented.
C. This module is the result contract: the shape of that future measurement.
D. An executor does not exist.

``READY_FOR_PHYSICAL_PROBE_IMPLEMENTATION_REVIEW`` means the result format is
fully described. It does not mean a probe ran. ``READY_FOR_EXECUTION``,
``EXECUTION_AUTHORIZED`` and ``PHYSICAL_PROOF_VERIFIED`` are not states.

No file is opened, no binary is hashed, no process is created, no network is
used, and no sandbox is built. ``stable_digest`` covers this document only.

There is no independent root of trust, signed probe, KMS, HSM, PKI, remote
attestation, hardware trust, or external evidence.

The next implementation step is Executable Pin Physical Probe V1, because the
pinning claim already names a path, a size and a sha256. A version probe is
not that step: reading ``--version`` would spawn a process. Neither probe is
implemented here.

A timestamp is not a field. A future timestamp would be metadata outside the
authority digest. It would not prove order or authenticity.

``required_verified``, ``missing_requirements`` and ``physical_proof_satisfied``
are reconstructed from the measurements and from
``PHYSICAL_PROOF_BLOCKERS`` plus ``REQUIRED_BEFORE_FUTURE_EXECUTION``. Counts
and lists supplied on the document are not authority. Nothing is verified, so
the satisfied list stays empty and every applicable proof stays missing.

``measurement_identity`` is a digest of the uncollected declaration. It is not
physical evidence and not an independent root of trust. ``evidence_digest``
stays empty. ``evidence_is_physical`` and ``independently_verified`` stay
false.

``window_validity`` and ``recheck_required_before_use`` are data only. This
module has no clock. A future executor must not treat the document as
eternally valid.
"""
from __future__ import annotations

from typing import Any, Mapping

from atlasquant_aion_developer_manifest import stable_digest
from atlasquant_aion_developer_os_sandbox_contract import (
    PHYSICAL_PROOF_BLOCKERS,
    READY_STATE as OS_SANDBOX_READY_STATE,
    REQUIRED_BEFORE_FUTURE_EXECUTION,
    assert_os_sandbox_contract,
)

SCHEMA = "ATLASQUANT_AION_DEVELOPER_OS_SANDBOX_PROBE_RESULT_V1"
MEASUREMENT_SCHEMA = "ATLASQUANT_AION_DEVELOPER_OS_SANDBOX_PROBE_MEASUREMENT_V1"
EVIDENCE_SCHEMA = "ATLASQUANT_AION_DEVELOPER_OS_SANDBOX_PROBE_EVIDENCE_V1"
READY_STATE = "READY_FOR_PHYSICAL_PROBE_IMPLEMENTATION_REVIEW"
BLOCKED_STATE = "BLOCKED"
PARTIAL_STATE = "PARTIAL"
_ALLOWED_STATES = frozenset({READY_STATE, BLOCKED_STATE, PARTIAL_STATE})
_FORBIDDEN_STATES = frozenset({
    "READY_FOR_EXECUTION",
    "EXECUTION_AUTHORIZED",
    "PHYSICAL_PROOF_VERIFIED",
})
ALLOWED_PLATFORMS = ("LINUX", "WINDOWS", "UNRESOLVED")
_REJECTED_PLATFORMS = frozenset({"UNKNOWN", "OTHER", "UNSUPPORTED"})
NEXT_IMPLEMENTATION_STEP = "EXECUTABLE_PIN_PHYSICAL_PROBE_V1"
_UPSTREAM_BLOCKER = "OS_SANDBOX_PROBE_DESIGN_REQUIRED"
_PARTIAL_BLOCKER = "MEASUREMENT_COVERAGE_INCOMPLETE"
_OBSERVED_VALUE = "NOT_MEASURED"
_MEASUREMENT_METHOD = "NOT_IMPLEMENTED"
_FAILURE_REASON = "PROBE_NOT_IMPLEMENTED"
_WINDOW = "NO_MEASUREMENT_WINDOW"

_FALSE_FLAGS = (
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
    "platform_verified",
    "physical_probe_executed",
    "physical_probe_passed",
    "physical_proof_verified",
    "independently_verified",
    "probe_signed",
    "remote_attestation_verified",
    "hardware_trust_verified",
    "external_evidence_accepted",
    "kms_used",
    "pki_used",
    "hsm_used",
    "version_probe_implemented",
    "upstream_contract_independently_verified",
)
_MEASUREMENT_KEYS = frozenset({
    "schema",
    "requirement",
    "requested_requirement",
    "observed_value",
    "verified",
    "evidence",
    "measurement_method",
    "failure_reason",
    "platform",
    "sequence",
    "window_validity",
    "recheck_required_before_use",
})
_EVIDENCE_KEYS = frozenset({
    "schema",
    "method",
    "tool_identity",
    "raw_evidence_ref",
    "evidence_digest",
    "measurement_identity",
    "evidence_is_physical",
    "independently_verified",
})
_COVERAGE_KEYS = frozenset({"required_total", "required_verified", "missing"})
_CONTRACT_KEYS = frozenset({
    "schema",
    "probe_result_id",
    "probe_result_manifest_id",
    "os_sandbox_contract_id",
    "platform",
    "probe_principal",
    "probe_identity",
    "execution_context",
    "sequence",
    "measurements",
    "coverage",
    "missing_requirements",
    "physical_proof_satisfied",
    "state",
    "blockers",
    "required_before_future_execution",
    "upstream_contract_structurally_verified",
    "probe_result_is_data_only",
    "next_implementation_step",
    "recheck_required_before_use",
    "hazards",
}) | frozenset(_FALSE_FLAGS)


def derived_probe_requirements() -> tuple[str, ...]:
    """Requirements taken from the sandbox contract, in that contract's order.

    ``REQUIRED_BEFORE_FUTURE_EXECUTION`` already starts with
    ``PHYSICAL_PROOF_BLOCKERS``. The union keeps that order and adds nothing
    that the sandbox contract does not already name.
    """
    ordered: list[str] = []
    for item in tuple(PHYSICAL_PROOF_BLOCKERS) + tuple(REQUIRED_BEFORE_FUTURE_EXECUTION):
        if item not in ordered:
            ordered.append(item)
    return tuple(ordered)


def _reject_unknown(document: Mapping[str, Any], allowed: frozenset[str], label: str) -> None:
    unknown = sorted(set(document) - allowed)
    if unknown:
        raise ValueError(f"unknown {label} field {unknown[0]}")
    missing = sorted(allowed - set(document))
    if missing:
        raise ValueError(f"{label} is missing {missing[0]}")


def _reject_caller_claims(claims: Mapping[str, Any]) -> None:
    for field, value in claims.items():
        if value is not None:
            raise ValueError(f"caller cannot assert {field}")


def _require_platform(platform: str) -> str:
    if platform in _REJECTED_PLATFORMS or platform not in ALLOWED_PLATFORMS:
        raise ValueError("unsupported platform cannot be verified")
    return platform


def _evidence(requirement: str) -> dict[str, Any]:
    """Declarative evidence slot. Nothing was collected.

    ``measurement_identity`` binds this uncollected declaration. The digest is
    not a measurement, not physical proof, and not an independent root of
    trust. ``evidence_digest`` stays empty. Caller evidence cannot fill it.
    """
    return {
        "schema": EVIDENCE_SCHEMA,
        "method": "NOT_COLLECTED",
        "tool_identity": "NONE",
        "raw_evidence_ref": "",
        "evidence_digest": "",
        "measurement_identity": stable_digest(
            {"requirement": requirement, "collected": False},
            prefix="DEVPROBEV-",
            length=18,
        ),
        "evidence_is_physical": False,
        "independently_verified": False,
    }


def _measurement(requirement: str, sequence: int, platform: str) -> dict[str, Any]:
    return {
        "schema": MEASUREMENT_SCHEMA,
        "requirement": requirement,
        "requested_requirement": requirement,
        "observed_value": _OBSERVED_VALUE,
        "verified": False,
        "evidence": _evidence(requirement),
        "measurement_method": _MEASUREMENT_METHOD,
        "failure_reason": _FAILURE_REASON,
        "platform": platform,
        "sequence": sequence,
        "window_validity": _WINDOW,
        "recheck_required_before_use": True,
    }


def canonical_measurements(platform: str) -> list[dict[str, Any]]:
    """One unverified slot per derived requirement. This is not a measurement."""
    _require_platform(platform)
    return [
        _measurement(requirement, index, platform)
        for index, requirement in enumerate(derived_probe_requirements(), start=1)
    ]


def _evidence_is_valid_physical_proof(evidence: Any, requirement: str) -> bool:
    """No caller payload and no document digest is physical proof.

    A future satisfied item must match one derived requirement, with
    ``verified`` true and evidence a real probe collected. Forged
    ``evidence_is_physical`` or ``independently_verified`` flags do not create
    that evidence. ``measurement_identity`` does not create it either.
    """
    if not isinstance(evidence, Mapping):
        return False
    if evidence.get("schema") != EVIDENCE_SCHEMA:
        return False
    if requirement not in derived_probe_requirements():
        return False
    if evidence.get("evidence_is_physical") is not True:
        return False
    if evidence.get("independently_verified") is not True:
        return False
    return False


def reconstruct_physical_coverage(measurements: Any) -> dict[str, Any]:
    """Derive coverage from measurements and the canonical requirement lists.

    Supplied ``required_verified``, ``missing`` and ``physical_proof_satisfied``
    values are ignored. A requirement is satisfied only when its measurement
    is verified and its evidence is valid physical proof. This contract has
    no such evidence, so the verified count is 0, the satisfied list is empty,
    and every derived requirement is missing.
    """
    requirements = list(derived_probe_requirements())
    satisfied: list[str] = []
    if isinstance(measurements, list) and not isinstance(measurements, (str, bytes, bytearray)):
        for measurement in measurements:
            if not isinstance(measurement, Mapping):
                continue
            requirement = measurement.get("requirement")
            if not isinstance(requirement, str) or requirement not in requirements:
                continue
            if requirement in satisfied:
                continue
            evidence = measurement.get("evidence")
            if (
                measurement.get("verified") is True
                and _evidence_is_valid_physical_proof(evidence, requirement)
            ):
                satisfied.append(requirement)
    satisfied_in_order = [item for item in requirements if item in set(satisfied)]
    return {
        "required_total": len(requirements),
        "required_verified": len(satisfied_in_order),
        "missing": [item for item in requirements if item not in set(satisfied_in_order)],
        "physical_proof_satisfied": satisfied_in_order,
    }


def canonical_coverage() -> dict[str, Any]:
    """Coverage of the unmeasured declaration. Nothing is satisfied."""
    derived = reconstruct_physical_coverage(canonical_measurements("UNRESOLVED"))
    return {
        "required_total": derived["required_total"],
        "required_verified": derived["required_verified"],
        "missing": list(derived["missing"]),
    }


def _assert_evidence(evidence: Mapping[str, Any], requirement: str) -> None:
    if not isinstance(evidence, Mapping):
        raise ValueError("probe evidence must be an object")
    _reject_unknown(evidence, _EVIDENCE_KEYS, "probe evidence")
    expected = _evidence(requirement)
    if dict(evidence) != expected:
        if evidence.get("independently_verified") is not False:
            raise ValueError("probe evidence cannot be independently verified")
        if evidence.get("evidence_is_physical") is not False:
            raise ValueError("probe evidence is not physical")
        raise ValueError("probe evidence is not the uncollected declaration")


def _assert_measurement(measurement: Mapping[str, Any], expected: Mapping[str, Any]) -> None:
    if not isinstance(measurement, Mapping):
        raise ValueError("probe measurement must be an object")
    _reject_unknown(measurement, _MEASUREMENT_KEYS, "probe measurement")
    if measurement.get("verified") is not False:
        raise ValueError("probe measurement cannot be verified")
    if measurement.get("failure_reason") != _FAILURE_REASON:
        raise ValueError("probe measurement failure reason is not the unimplemented probe")
    if measurement.get("recheck_required_before_use") is not True:
        raise ValueError("probe measurement must be rechecked before use")
    if measurement.get("observed_value") != _OBSERVED_VALUE:
        raise ValueError("ambiguous measurement cannot pass")
    evidence = measurement.get("evidence")
    if not isinstance(evidence, Mapping):
        raise ValueError("probe evidence must be an object")
    _assert_evidence(evidence, str(expected.get("requirement")))
    if dict(measurement) != dict(expected):
        raise ValueError("probe measurement is not the unmeasured declaration")


def _assert_measurement_list(measurements: Any, platform: str, *, partial: bool) -> None:
    if not isinstance(measurements, list) or isinstance(measurements, (str, bytes, bytearray)):
        raise ValueError("probe measurements must be a list")
    requirements = derived_probe_requirements()
    canonical = {item["requirement"]: item for item in canonical_measurements(platform)}
    seen: list[str] = []
    for measurement in measurements:
        if not isinstance(measurement, Mapping):
            raise ValueError("probe measurement must be an object")
        requirement = measurement.get("requirement")
        if requirement not in canonical:
            raise ValueError("probe measurement requirement is not derived")
        _assert_measurement(measurement, canonical[str(requirement)])
        seen.append(str(requirement))
    if len(seen) != len(set(seen)):
        raise ValueError("probe measurement requirement is duplicated")
    if partial:
        if not seen or len(seen) >= len(requirements):
            raise ValueError("partial probe result must omit at least one requirement")
        expected_order = [item for item in requirements if item in set(seen)]
        if seen != expected_order:
            raise ValueError("partial probe measurements are not in canonical order")
        return
    if seen != list(requirements):
        raise ValueError("probe measurements do not cover the derived requirements")


def _assert_coverage(result: Mapping[str, Any], measurements: Any) -> None:
    """Stored coverage is accepted only when it matches reconstruction."""
    coverage = result.get("coverage")
    if not isinstance(coverage, Mapping):
        raise ValueError("probe coverage must be an object")
    _reject_unknown(coverage, _COVERAGE_KEYS, "probe coverage")
    derived = reconstruct_physical_coverage(measurements)
    if coverage.get("required_total") != derived["required_total"]:
        raise ValueError("probe coverage total was not derived")
    verified = coverage.get("required_verified")
    if type(verified) is not int or verified != derived["required_verified"]:
        raise ValueError("probe coverage verified count was not derived from the measurements")
    if list(coverage.get("missing") or []) != list(derived["missing"]):
        raise ValueError("probe coverage missing list was not derived")
    if list(result.get("missing_requirements") or []) != list(derived["missing"]):
        raise ValueError("probe missing requirements were not derived")
    satisfied = result.get("physical_proof_satisfied")
    if not isinstance(satisfied, list) or satisfied != list(derived["physical_proof_satisfied"]):
        raise ValueError("physical proof satisfied was not derived from the measurements")


def probe_result_manifest(result: Mapping[str, Any]) -> dict[str, Any]:
    """Authority fields. Informational hazards are outside this digest.

    ``hazards`` may sit on the document. It is commentary. It does not enter
    this manifest, and changing it does not change the result id.
    """
    if not isinstance(result, Mapping):
        raise ValueError("probe result must be an object")
    blockers = result.get("blockers")
    coverage = result.get("coverage") if isinstance(result.get("coverage"), Mapping) else {}
    return {
        "state": result.get("state"),
        "blockers": list(blockers) if isinstance(blockers, (list, tuple)) else blockers,
        "os_sandbox_contract_id": result.get("os_sandbox_contract_id"),
        "platform": result.get("platform"),
        "probe_principal": result.get("probe_principal"),
        "probe_identity": result.get("probe_identity"),
        "execution_context": result.get("execution_context"),
        "sequence": list(result.get("sequence") or []),
        "measurements": result.get("measurements"),
        "coverage": {
            "required_total": coverage.get("required_total"),
            "required_verified": coverage.get("required_verified"),
            "missing": list(coverage.get("missing") or []),
        },
        "missing_requirements": list(result.get("missing_requirements") or []),
        "physical_proof_satisfied": list(result.get("physical_proof_satisfied") or []),
        "required_before_future_execution": list(result.get("required_before_future_execution") or []),
        "upstream_contract_structurally_verified": result.get(
            "upstream_contract_structurally_verified"
        ),
        "probe_result_is_data_only": result.get("probe_result_is_data_only"),
        "next_implementation_step": result.get("next_implementation_step"),
        "recheck_required_before_use": result.get("recheck_required_before_use"),
        **{field: result.get(field) for field in _FALSE_FLAGS},
    }


def probe_result_manifest_id(result: Mapping[str, Any]) -> str:
    return stable_digest(probe_result_manifest(result), prefix="DEVPROBEMAN-", length=18)


def expected_probe_result_id(result: Mapping[str, Any]) -> str:
    """Digest the manifest id. This id is not a seed of itself."""
    return stable_digest(
        {"probe_result_manifest_id": probe_result_manifest_id(result)},
        prefix="DEVPROBE-",
        length=18,
    )


def _bind_probe_result_ids(result: dict[str, Any]) -> dict[str, Any]:
    result["probe_result_manifest_id"] = probe_result_manifest_id(result)
    result["probe_result_id"] = expected_probe_result_id(result)
    return result


def expected_probe_result_state_and_blockers(
    os_sandbox_contract: Mapping[str, Any],
    command_policy: Mapping[str, Any],
    runner_contract: Mapping[str, Any],
    builder_request: Mapping[str, Any],
    preflight: Mapping[str, Any],
    patch_validation: Mapping[str, Any],
    content_attestation: Mapping[str, Any],
    pinning_spec: Mapping[str, Any],
    environment_contract: Mapping[str, Any],
) -> tuple[str, list[str]]:
    """State this chain would seal. Absence of measurements is not a blocker.

    The sandbox contract is revalidated. Its id string is not trusted alone.
    Agreement among these documents is not an independent root of trust.
    """
    assert_os_sandbox_contract(
        os_sandbox_contract,
        command_policy,
        runner_contract,
        builder_request,
        preflight,
        patch_validation,
        content_attestation,
        pinning_spec,
        environment_contract,
    )
    ready = (
        os_sandbox_contract.get("state") == OS_SANDBOX_READY_STATE
        and list(os_sandbox_contract.get("blockers") or []) == []
    )
    if ready:
        return READY_STATE, []
    return BLOCKED_STATE, [_UPSTREAM_BLOCKER]


def _design_view(
    os_sandbox_contract: Mapping[str, Any],
    *,
    platform: str,
    state: str,
    blockers: list[str],
) -> dict[str, Any]:
    requirements = list(derived_probe_requirements())
    measurements = canonical_measurements(platform)
    derived = reconstruct_physical_coverage(measurements)
    return {
        "state": state,
        "blockers": list(blockers),
        "os_sandbox_contract_id": os_sandbox_contract.get("os_sandbox_contract_id"),
        "platform": platform,
        "probe_principal": "UNDECLARED",
        "probe_identity": "UNDECLARED",
        "execution_context": "NOT_EXECUTED",
        "sequence": requirements,
        "measurements": measurements,
        "coverage": {
            "required_total": derived["required_total"],
            "required_verified": derived["required_verified"],
            "missing": list(derived["missing"]),
        },
        "missing_requirements": list(derived["missing"]),
        "physical_proof_satisfied": list(derived["physical_proof_satisfied"]),
        "required_before_future_execution": requirements,
        "upstream_contract_structurally_verified": True,
        "probe_result_is_data_only": True,
        "next_implementation_step": NEXT_IMPLEMENTATION_STEP,
        "recheck_required_before_use": True,
        **{field: False for field in _FALSE_FLAGS},
    }


def assert_probe_result_integrity(result: Mapping[str, Any]) -> str:
    """Revalidate the sealed result shape. A matching id is not a probe."""
    if not isinstance(result, Mapping):
        raise ValueError("probe result must be an object")
    if result.get("schema") != SCHEMA:
        raise ValueError("invalid probe result")
    _reject_unknown(result, _CONTRACT_KEYS, "probe result")
    for field in _FALSE_FLAGS:
        if result.get(field) is True:
            raise ValueError(f"probe result cannot claim {field}")
    state = result.get("state")
    if state in _FORBIDDEN_STATES:
        raise ValueError("probe result cannot be ready for execution")
    if state not in _ALLOWED_STATES:
        raise ValueError("probe result state is not an accepted design state")
    platform = _require_platform(str(result.get("platform")))
    blockers = result.get("blockers")
    if not isinstance(blockers, list):
        raise ValueError("probe result blockers must be a list")
    partial = state == PARTIAL_STATE
    _assert_measurement_list(result.get("measurements"), platform, partial=partial)
    _assert_coverage(result, result.get("measurements"))
    derived = reconstruct_physical_coverage(result.get("measurements"))
    if list(result.get("sequence") or []) != [item["requirement"] for item in result["measurements"]]:
        raise ValueError("probe sequence was not derived from the measurements")
    if list(result.get("required_before_future_execution") or []) != list(derived_probe_requirements()):
        raise ValueError("required before future execution was not derived")
    if result.get("upstream_contract_structurally_verified") is not True:
        raise ValueError("probe result structural binding was not derived")
    if result.get("upstream_contract_independently_verified") is not False:
        raise ValueError("independent root of trust is not established")
    if result.get("probe_result_is_data_only") is not True:
        raise ValueError("probe result must stay data only")
    if result.get("next_implementation_step") != NEXT_IMPLEMENTATION_STEP:
        raise ValueError("next implementation step is the executable pin probe")
    if result.get("probe_principal") != "UNDECLARED" or result.get("probe_identity") != "UNDECLARED":
        raise ValueError("probe identity is an undeclared claim")
    if result.get("execution_context") != "NOT_EXECUTED":
        raise ValueError("probe execution context is not executed")
    if result.get("recheck_required_before_use") is not True:
        raise ValueError("probe result must be rechecked before use")
    for field in _FALSE_FLAGS:
        if result.get(field) is not False:
            raise ValueError(f"probe result flag {field} is not false")
    if state == READY_STATE:
        if blockers:
            raise ValueError("ready probe result format cannot carry blockers")
        if derived["missing"] != list(derived_probe_requirements()):
            raise ValueError("ready probe result format must list every unmeasured requirement")
        if derived["physical_proof_satisfied"] or derived["required_verified"] != 0:
            raise ValueError("ready probe result format cannot claim physical proof")
    elif state == BLOCKED_STATE:
        if blockers != [_UPSTREAM_BLOCKER]:
            raise ValueError("blocked probe result must name the upstream design gap")
        if derived["missing"] != list(derived_probe_requirements()):
            raise ValueError("blocked probe result must still list every unmeasured requirement")
    else:
        if blockers != [_PARTIAL_BLOCKER]:
            raise ValueError("partial probe result must name the incomplete inventory")
    if result.get("probe_result_manifest_id") != probe_result_manifest_id(result):
        raise ValueError("probe result manifest mismatch")
    if result.get("probe_result_id") != expected_probe_result_id(result):
        raise ValueError("probe result id mismatch")
    return str(result.get("probe_result_manifest_id"))


def assert_probe_result(
    result: Mapping[str, Any],
    os_sandbox_contract: Mapping[str, Any],
    command_policy: Mapping[str, Any],
    runner_contract: Mapping[str, Any],
    builder_request: Mapping[str, Any],
    preflight: Mapping[str, Any],
    patch_validation: Mapping[str, Any],
    content_attestation: Mapping[str, Any],
    pinning_spec: Mapping[str, Any],
    environment_contract: Mapping[str, Any],
) -> None:
    """Reject a result whose id matches but whose sandbox chain is not this one."""
    assert_probe_result_integrity(result)
    state, blockers = expected_probe_result_state_and_blockers(
        os_sandbox_contract,
        command_policy,
        runner_contract,
        builder_request,
        preflight,
        patch_validation,
        content_attestation,
        pinning_spec,
        environment_contract,
    )
    if result.get("state") != state or list(result.get("blockers") or []) != blockers:
        raise ValueError("probe result state was not reconstructed from the sandbox chain")
    platform = _require_platform(str(result.get("platform")))
    expected = _design_view(
        os_sandbox_contract,
        platform=platform,
        state=state,
        blockers=blockers,
    )
    sealed = probe_result_manifest(result)
    for field, value in expected.items():
        if sealed.get(field) != value:
            raise ValueError(f"probe result {field} was not derived from the supplied chain")


def build_probe_result_contract(
    os_sandbox_contract: Mapping[str, Any],
    command_policy: Mapping[str, Any],
    runner_contract: Mapping[str, Any],
    builder_request: Mapping[str, Any],
    preflight: Mapping[str, Any],
    patch_validation: Mapping[str, Any],
    content_attestation: Mapping[str, Any],
    pinning_spec: Mapping[str, Any],
    environment_contract: Mapping[str, Any],
    *,
    platform: str = "UNRESOLVED",
    **caller_claims: Any,
) -> dict[str, Any]:
    """Seal the result format. Caller verification flags are rejected.

    Coverage is reconstructed. ``required_verified`` stays 0 and
    ``physical_proof_satisfied`` stays empty. That absence is coverage, not a
    design blocker. ``READY_FOR_PHYSICAL_PROBE_IMPLEMENTATION_REVIEW`` describes
    the format. It does not record a physical probe.
    """
    _reject_caller_claims(caller_claims)
    platform = _require_platform(platform)
    state, blockers = expected_probe_result_state_and_blockers(
        os_sandbox_contract,
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
        os_sandbox_contract,
        platform=platform,
        state=state,
        blockers=blockers,
    )
    return _bind_probe_result_ids({
        "schema": SCHEMA,
        **view,
        "hazards": [
            "This document does not record a physical measurement.",
            "No independent root of trust, signature, KMS, HSM, PKI, remote attestation, or hardware trust is present.",
            "measurement_identity digests the uncollected declaration. It is not physical evidence.",
            "recheck_required_before_use stays true. This contract has no clock and does not make evidence eternally valid.",
            "The next implementation step is an executable-pin probe. A version probe stays deferred because it would spawn a process.",
            "A matching digest does not prove that a probe ran.",
        ],
    })


__all__ = [
    "SCHEMA",
    "MEASUREMENT_SCHEMA",
    "EVIDENCE_SCHEMA",
    "READY_STATE",
    "NEXT_IMPLEMENTATION_STEP",
    "derived_probe_requirements",
    "canonical_measurements",
    "canonical_coverage",
    "reconstruct_physical_coverage",
    "probe_result_manifest",
    "probe_result_manifest_id",
    "expected_probe_result_id",
    "expected_probe_result_state_and_blockers",
    "assert_probe_result_integrity",
    "assert_probe_result",
    "build_probe_result_contract",
]
