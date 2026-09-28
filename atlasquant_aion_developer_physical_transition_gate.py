"""Physical transition gate for a future DESIGN to physical-operation boundary.

This is a barrier. It does not execute, apply a patch, write the filesystem,
open a shell, spawn a process, mutate git, merge, deploy, trade, or run a
physical probe.

Design READY on Builder, Preflight, Patch Validation, Runner, Command Policy,
Executable Pinning, Environment, OS Sandbox and Probe Result does not release
physical operation. A stored source-bound proof record does not release it
either. The gate replays the transient patch through the source-bound
consumption gate and then keeps the transition blocked: there is no external
provenance source, so ``independent_external_verification`` stays false and
the state stays ``PHYSICAL_TRANSITION_BLOCKED``.

Caller input cannot promote that state. Unknown or missing fields fail closed.
No execution flag becomes true.
"""
from __future__ import annotations

import json
from typing import Any, Mapping

from atlasquant_aion_developer_builder_sandbox import (
    READY_STATE as BUILDER_READY,
    assert_builder_sandbox_request_integrity,
)
from atlasquant_aion_developer_command_policy import assert_command_policy_provenance
from atlasquant_aion_developer_executable_pinning import (
    PINNING_READY_STATE,
    assert_environment_contract_integrity,
    assert_executable_pinning_spec_integrity,
)
from atlasquant_aion_developer_manifest import stable_digest
from atlasquant_aion_developer_os_sandbox_contract import (
    READY_STATE as OS_READY,
    assert_os_sandbox_contract,
)
from atlasquant_aion_developer_os_sandbox_probe_result import (
    READY_STATE as PROBE_READY,
    assert_probe_result,
)
from atlasquant_aion_developer_patch_validation import (
    READY_STATE as PATCH_READY,
    assert_patch_validation_integrity,
)
from atlasquant_aion_developer_sandbox_preflight import (
    READY_STATE as PREFLIGHT_READY,
    assert_sandbox_preflight_integrity,
)
from atlasquant_aion_developer_source_bound_consumption_gate import (
    SCHEMA as CONSUMPTION_SCHEMA,
    assert_source_bound_consumption_gate,
)
from atlasquant_aion_developer_source_bound_patch_proof import (
    READY_STATE as SOURCE_BOUND_PATCH_MATCH,
    SCHEMA as PROOF_SCHEMA,
)

SCHEMA = "ATLASQUANT_AION_DEVELOPER_PHYSICAL_TRANSITION_GATE_V1"
STRUCTURAL_READY = "STRUCTURAL_READY"
SOURCE_BOUND_READY = "SOURCE_BOUND_READY"
EXTERNAL_PROVENANCE_MISSING = "EXTERNAL_PROVENANCE_MISSING"
PHYSICAL_TRANSITION_BLOCKED = "PHYSICAL_TRANSITION_BLOCKED"
_DESIGN_NOT_PHYSICAL = "design READY does not release physical transition"
_STORED_PROOF_NOT_RECEIPT = "stored source-bound proof is not a consumption receipt"
_STALE_RECEIPT = "stale consumption receipt"
_RECEIPT_MISMATCH = "consumption receipt does not match the transient patch"
_REMAINS_BLOCKED = "physical transition remains blocked"
_INDEPENDENT_CANNOT_BE_CLAIMED = "independent external verification cannot be claimed"
_EXECUTION_CANNOT_BE_AUTHORIZED = "physical execution cannot be authorized"
_RUNNER_READY = "READY_FOR_RUNNER_DESIGN_REVIEW"
_POLICY_READY = "READY_FOR_EXECUTABLE_PINNING_REVIEW"
_ENVIRONMENT_READY = "ENVIRONMENT_DECLARED"
_FALSE_FLAGS = (
    "patch_applied",
    "execution_authorized",
    "executor_attached",
    "commands_executed",
    "writes_files",
    "filesystem_write_authorized",
    "runs_tests",
    "network_called",
    "subprocess_called",
    "shell_authorized",
    "git_mutation_authorized",
    "automatic_commit",
    "automatic_merge",
    "automatic_deploy",
    "production_change_allowed",
    "real_trading_enabled",
    "physical_execution_authorized",
    "physical_probe_authorized",
    "physical_probe_executed",
    "physical_probe_passed",
    "physical_proof_verified",
    "symlink_physical_boundary_verified",
    "hardlink_physical_boundary_verified",
    "tool_output_is_authority",
    "independent_external_verification",
    "caller_can_promote_state",
    "design_ready_releases_physical_transition",
    "stored_proof_releases_physical_transition",
    "stored_receipt_releases_physical_transition",
    "patch_text_included",
)
_TRUE_FLAGS = (
    "consumption_replay_performed",
    "external_provenance_required",
    "physical_transition_remains_blocked",
    "content_binding_requires_external_verification",
)
_ID_FIELDS = (
    "builder_request_id",
    "preflight_id",
    "validation_id",
    "patch_digest",
    "patch_manifest_id",
    "baseline_ref",
    "candidate_ref",
    "consumption_id",
    "replay_proof_id",
    "runner_contract_id",
    "command_policy_id",
    "pinning_spec_id",
    "environment_digest",
    "content_attestation_id",
    "os_sandbox_contract_id",
    "probe_result_id",
)
_RECEIPT_LINEAGE = (
    "builder_request_id",
    "preflight_id",
    "validation_id",
    "patch_digest",
    "patch_manifest_id",
    "baseline_ref",
    "candidate_ref",
    "replay_proof_id",
)
_CONTRACT_KEYS = frozenset({
    "schema",
    "transition_id",
    "state",
    "structural_readiness",
    "source_bound_readiness",
    "external_provenance",
}) | frozenset(_ID_FIELDS) | frozenset(_FALSE_FLAGS) | frozenset(_TRUE_FLAGS)
_MANIFEST_KEYS = tuple(sorted(_CONTRACT_KEYS - {"transition_id"}))


def _reject_closed(document: Mapping[str, Any], allowed: frozenset[str], label: str) -> None:
    unknown = sorted(set(document) - allowed)
    if unknown:
        raise ValueError(f"unknown {label} field {unknown[0]}")
    missing = sorted(allowed - set(document))
    if missing:
        raise ValueError(f"{label} is missing {missing[0]}")


def _require_token(value: Any, expected: str, label: str) -> None:
    if value != expected:
        raise ValueError(f"{label} is not {expected}")


def physical_transition_manifest(decision: Mapping[str, Any]) -> dict[str, Any]:
    """Authority fields of a transition decision. ``transition_id`` is not an input."""
    if not isinstance(decision, Mapping):
        raise ValueError("physical transition decision must be an object")
    return {key: decision.get(key) for key in _MANIFEST_KEYS}


def expected_physical_transition_id(decision: Mapping[str, Any]) -> str:
    """Digest the transition manifest. A caller-supplied id is not an input."""
    return stable_digest(
        physical_transition_manifest(decision),
        prefix="DEVPHYGATE-",
        length=24,
    )


def _environment_digest(environment: Mapping[str, Any]) -> str:
    """Digest the sealed environment contract. The caller cannot supply this."""
    return stable_digest(dict(environment), prefix="DEVENV-", length=24)


def _reject_caller_claims(caller_claims: Mapping[str, Any]) -> None:
    if caller_claims.get("independent_external_verification") is True:
        raise ValueError(_INDEPENDENT_CANNOT_BE_CLAIMED)
    if caller_claims.get("physical_execution_authorized") is True:
        raise ValueError(_EXECUTION_CANNOT_BE_AUTHORIZED)
    if "state" in caller_claims:
        raise ValueError(_REMAINS_BLOCKED)
    if not caller_claims:
        return
    field = sorted(caller_claims)[0]
    raise ValueError(f"caller physical transition claim is not authority: {field}")


def _require_dependency(name: str, value: Any) -> None:
    if value is None or not isinstance(value, Mapping):
        raise ValueError(f"physical transition dependency is missing: {name}")


def _require_ref(name: str, value: Any) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"physical transition dependency is missing: {name}")
    return value


def _is_stored_proof(receipt: Any) -> bool:
    if receipt == SOURCE_BOUND_PATCH_MATCH:
        return True
    if not isinstance(receipt, Mapping):
        return False
    if receipt.get("schema") == PROOF_SCHEMA:
        return True
    return set(receipt) <= {"state"} and receipt.get("state") == SOURCE_BOUND_PATCH_MATCH


def _reject_presented_receipt(receipt: Any) -> None:
    if receipt is None:
        return
    if _is_stored_proof(receipt) or not isinstance(receipt, Mapping):
        raise ValueError(_STORED_PROOF_NOT_RECEIPT)
    if receipt.get("schema") != CONSUMPTION_SCHEMA:
        raise ValueError(_RECEIPT_MISMATCH)
    if receipt.get("independent_external_verification") is True:
        raise ValueError(_INDEPENDENT_CANNOT_BE_CLAIMED)
    if receipt.get("physical_execution_authorized") is True:
        raise ValueError(_EXECUTION_CANNOT_BE_AUTHORIZED)


def _require_design_ready(name: str, document: Mapping[str, Any], expected: str) -> None:
    if document.get("state") != expected:
        raise ValueError(f"design document is not structurally ready: {name}")


def _bind_presented_receipt(receipt: Mapping[str, Any], fresh: Mapping[str, Any]) -> None:
    unknown = sorted(set(receipt) - set(fresh))
    if unknown:
        raise ValueError(f"unknown physical transition authority field {unknown[0]}")
    if set(fresh) - set(receipt):
        raise ValueError(_RECEIPT_MISMATCH)
    for field in _RECEIPT_LINEAGE:
        if receipt.get(field) != fresh.get(field):
            raise ValueError(_RECEIPT_MISMATCH)
    for field in set(fresh) - {"consumption_id"}:
        if receipt.get(field) != fresh.get(field):
            raise ValueError(_RECEIPT_MISMATCH)
    if receipt.get("consumption_id") != fresh.get("consumption_id"):
        raise ValueError(_STALE_RECEIPT)


def assert_physical_transition_record(decision: Mapping[str, Any]) -> str:
    """Reject any transition record that is not the blocked classification.

    Recomputing ``transition_id`` after promoting the state, claiming
    independent verification, or setting an execution flag does not open the
    gate. This check does not execute anything.
    """
    if not isinstance(decision, Mapping):
        raise ValueError("physical transition decision must be an object")
    if decision.get("schema") != SCHEMA:
        raise ValueError("invalid physical transition decision")
    _reject_closed(decision, _CONTRACT_KEYS, "physical transition record")
    if decision.get("independent_external_verification") is not False:
        raise ValueError(_INDEPENDENT_CANNOT_BE_CLAIMED)
    if decision.get("physical_execution_authorized") is not False:
        raise ValueError(_EXECUTION_CANNOT_BE_AUTHORIZED)
    for field in _FALSE_FLAGS:
        if decision.get(field) is not False:
            raise ValueError(f"physical transition cannot claim {field}")
    for field in _TRUE_FLAGS:
        if decision.get(field) is not True:
            raise ValueError(f"physical transition record requires {field}")
    if decision.get("state") != PHYSICAL_TRANSITION_BLOCKED:
        raise ValueError(_REMAINS_BLOCKED)
    _require_token(
        decision.get("structural_readiness"),
        STRUCTURAL_READY,
        "structural readiness",
    )
    _require_token(
        decision.get("source_bound_readiness"),
        SOURCE_BOUND_READY,
        "source-bound readiness",
    )
    if decision.get("external_provenance") != EXTERNAL_PROVENANCE_MISSING:
        raise ValueError(_INDEPENDENT_CANNOT_BE_CLAIMED)
    for field in _ID_FIELDS:
        value = decision.get(field)
        if not isinstance(value, str) or not value:
            raise ValueError(f"{field} is required")
    if decision.get("transition_id") != expected_physical_transition_id(decision):
        raise ValueError("physical transition id mismatch")
    return str(decision.get("transition_id"))


def evaluate_physical_transition_gate(
    builder_request: Any,
    preflight: Any,
    patch_validation: Any,
    runner_contract: Any,
    command_policy: Any,
    pinning_spec: Any,
    environment_contract: Any,
    os_sandbox_contract: Any,
    probe_result: Any,
    patch_text: Any,
    *,
    baseline_ref: Any,
    candidate_ref: Any,
    content_attestation: Any,
    consumption_receipt: Any = None,
    **caller_claims: Any,
) -> dict[str, Any]:
    """Validate the design chain and keep physical transition blocked.

    A fresh source-bound consumption replay is required. A stored proof is
    not a receipt. A presented consumption receipt must match that replay and
    still does not authorize execution. ``independent_external_verification``
    has no true path in this contract.
    """
    _reject_caller_claims(caller_claims)
    dependencies = (
        ("builder_request", builder_request),
        ("preflight", preflight),
        ("patch_validation", patch_validation),
        ("runner_contract", runner_contract),
        ("command_policy", command_policy),
        ("pinning_spec", pinning_spec),
        ("environment_contract", environment_contract),
        ("os_sandbox_contract", os_sandbox_contract),
        ("probe_result", probe_result),
        ("content_attestation", content_attestation),
    )
    for name, value in dependencies:
        _require_dependency(name, value)
    baseline = _require_ref("baseline_ref", baseline_ref)
    candidate = _require_ref("candidate_ref", candidate_ref)
    if _is_stored_proof(consumption_receipt) or (
        consumption_receipt is not None and not isinstance(consumption_receipt, Mapping)
    ):
        raise ValueError(_STORED_PROOF_NOT_RECEIPT)
    if not isinstance(patch_text, str) or not patch_text:
        raise ValueError(_DESIGN_NOT_PHYSICAL)
    _reject_presented_receipt(consumption_receipt)

    assert_builder_sandbox_request_integrity(builder_request)
    assert_sandbox_preflight_integrity(preflight, builder_request)
    assert_patch_validation_integrity(patch_validation, builder_request, preflight)
    assert_command_policy_provenance(
        command_policy,
        runner_contract,
        builder_request,
        preflight,
        patch_validation,
        content_attestation,
    )
    assert_executable_pinning_spec_integrity(pinning_spec)
    assert_environment_contract_integrity(environment_contract)
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
    assert_probe_result(
        probe_result,
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
    _require_design_ready("builder_request", builder_request, BUILDER_READY)
    _require_design_ready("preflight", preflight, PREFLIGHT_READY)
    _require_design_ready("patch_validation", patch_validation, PATCH_READY)
    _require_design_ready("runner_contract", runner_contract, _RUNNER_READY)
    _require_design_ready("command_policy", command_policy, _POLICY_READY)
    _require_design_ready("pinning_spec", pinning_spec, PINNING_READY_STATE)
    _require_design_ready("environment_contract", environment_contract, _ENVIRONMENT_READY)
    _require_design_ready("os_sandbox_contract", os_sandbox_contract, OS_READY)
    _require_design_ready("probe_result", probe_result, PROBE_READY)

    fresh = assert_source_bound_consumption_gate(
        builder_request,
        preflight,
        patch_validation,
        patch_text,
        baseline_ref=baseline,
        candidate_ref=candidate,
    )
    if fresh.get("independent_external_verification") is not False:
        raise ValueError(_INDEPENDENT_CANNOT_BE_CLAIMED)
    if fresh.get("physical_execution_authorized") is not False:
        raise ValueError(_EXECUTION_CANNOT_BE_AUTHORIZED)
    if consumption_receipt is not None:
        _bind_presented_receipt(consumption_receipt, fresh)
    if fresh.get("baseline_ref") != baseline or fresh.get("candidate_ref") != candidate:
        raise ValueError("revision refs differ")

    decision = {
        "schema": SCHEMA,
        "transition_id": "",
        "state": PHYSICAL_TRANSITION_BLOCKED,
        "structural_readiness": STRUCTURAL_READY,
        "source_bound_readiness": SOURCE_BOUND_READY,
        "external_provenance": EXTERNAL_PROVENANCE_MISSING,
        "builder_request_id": fresh["builder_request_id"],
        "preflight_id": fresh["preflight_id"],
        "validation_id": fresh["validation_id"],
        "patch_digest": fresh["patch_digest"],
        "patch_manifest_id": fresh["patch_manifest_id"],
        "baseline_ref": fresh["baseline_ref"],
        "candidate_ref": fresh["candidate_ref"],
        "consumption_id": fresh["consumption_id"],
        "replay_proof_id": fresh["replay_proof_id"],
        "runner_contract_id": runner_contract["runner_contract_id"],
        "command_policy_id": command_policy["command_policy_id"],
        "pinning_spec_id": pinning_spec["pinning_spec_id"],
        "environment_digest": _environment_digest(environment_contract),
        "content_attestation_id": content_attestation["content_attestation_id"],
        "os_sandbox_contract_id": os_sandbox_contract["os_sandbox_contract_id"],
        "probe_result_id": probe_result["probe_result_id"],
        **{field: True for field in _TRUE_FLAGS},
        **{field: False for field in _FALSE_FLAGS},
    }
    decision["transition_id"] = expected_physical_transition_id(decision)
    assert_physical_transition_record(decision)
    rendered = json.dumps(decision)
    if patch_text in rendered:
        raise ValueError("physical transition decision must not retain the transient patch")
    if decision.get("state") != PHYSICAL_TRANSITION_BLOCKED:
        raise ValueError(_REMAINS_BLOCKED)
    if decision.get("independent_external_verification") is not False:
        raise ValueError(_INDEPENDENT_CANNOT_BE_CLAIMED)
    for field in _FALSE_FLAGS:
        if decision.get(field) is not False:
            raise ValueError(f"physical transition cannot claim {field}")
    return decision


__all__ = [
    "SCHEMA",
    "STRUCTURAL_READY",
    "SOURCE_BOUND_READY",
    "EXTERNAL_PROVENANCE_MISSING",
    "PHYSICAL_TRANSITION_BLOCKED",
    "physical_transition_manifest",
    "expected_physical_transition_id",
    "assert_physical_transition_record",
    "evaluate_physical_transition_gate",
]
