"""AION B2B terminal-certificate read-model runtime projection offline V1.

Offline-only, read-only and fail-closed.

Normalizes the already-safe Runtime Reader Offline V1 result into the formal
terminal-certificate read-model field set. This layer never reads the durable
store directly, never calls a provider/network and never creates execution
authority.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import atlasquant_aion_b2b_execution_terminal_certificate_read_model_v1 as contract
import atlasquant_aion_b2b_terminal_certificate_runtime_reader_offline_v1 as reader

SCHEMA = "ATLASQUANT_AION_B2B_TERMINAL_CERTIFICATE_READ_MODEL_RUNTIME_PROJECTION_OFFLINE_V1"
MODE = "OFFLINE_READ_ONLY_FAIL_CLOSED_TERMINAL_CERTIFICATE_READ_MODEL_RUNTIME_PROJECTION"
NEXT_ALLOWED_STEP = "DESIGN_TERMINAL_CERTIFICATE_READ_MODEL_UI_RUNTIME_BINDING_OFFLINE_ONLY"

READ_STATES = contract.READ_MODEL_STATES
DIGEST_ALGORITHM = contract.DIGEST_ALGORITHM
CANONICAL_ENCODING = contract.CANONICAL_ENCODING

FALSE_FIELDS = (
    "execution_authority_created",
    "retry_authorized",
    "reopen_authorized",
    "reconciliation_authorized",
    "rollback_authorized",
    "compensation_authorized",
    "external_effect_authorized",
    "network_called",
    "provider_called",
    "external_action_executed",
    "billing_authorized",
    "billing_executed",
    "customer_contact_authorized",
    "crm_write_authorized",
    "provisioning_authorized",
    "deploy_authorized",
    "production_mutation_authorized",
    "production_mutation_performed",
    "execution_allowed",
    "execution_command_generated",
    "execution_command_executed",
    "executes_action",
)

REQUIRED_EVIDENCE_FIELDS = (
    "final_execution_state",
    "terminal_revision",
    "certificate_manifest_digest",
    "certificate_digest",
    "certificate_persistence_record_digest",
    "finalization_record_digest",
    "audit_seal_manifest_digest",
    "audit_seal_record_digest",
    "terminal_evidence_set_digest",
    "finops_observation_digest",
    "observability_trace_id",
    "pre_terminal_audit_chain_digest",
    "persisted_at",
    "observed_at",
    "age_seconds",
    "max_age_seconds",
)


def _result(
    state: str,
    *,
    execution_id: str,
    error_code: str = "",
    **fields: Any,
) -> dict[str, Any]:
    if state not in READ_STATES:
        state = "MISMATCH"
        error_code = error_code or "UNKNOWN_READ_MODEL_STATE"
    return {
        "schema": SCHEMA,
        "mode": MODE,
        "contract_schema": contract.SCHEMA,
        "schema_version": "1",
        "state": state,
        "certificate_status": state,
        "execution_id": execution_id,
        "error_code": error_code,
        **fields,
        "digest_algorithm": DIGEST_ALGORITHM,
        "canonical_encoding": CANONICAL_ENCODING,
        "read_model_projection_is_evidence_not_authority": True,
        "next_allowed_step": NEXT_ALLOWED_STEP,
        **{key: False for key in FALSE_FIELDS},
    }


def _contains_forbidden_material(value: Any) -> bool:
    forbidden = set(contract.FORBIDDEN_READ_MODEL_MATERIAL)
    if isinstance(value, Mapping):
        for key, item in value.items():
            if str(key) in forbidden:
                return True
            if _contains_forbidden_material(item):
                return True
        return False
    if isinstance(value, (list, tuple, set)):
        return any(_contains_forbidden_material(item) for item in value)
    return False


def project_terminal_certificate_read_model_offline(
    *,
    runtime_reader_result: Mapping[str, Any] | None,
    owner_id: str,
    tenant_id: str,
    workspace_id: str,
) -> dict[str, Any]:
    """Normalize one Runtime Reader result into a safe logical read model."""
    row = dict(runtime_reader_result) if isinstance(runtime_reader_result, Mapping) else {}
    execution_id = " ".join(str(row.get("execution_id") or "").split())[:96]

    if row.get("schema") != reader.SCHEMA:
        return _result(
            "MISMATCH",
            execution_id=execution_id,
            error_code="RUNTIME_READER_SCHEMA_MISMATCH",
        )
    if row.get("mode") != reader.MODE:
        return _result(
            "MISMATCH",
            execution_id=execution_id,
            error_code="RUNTIME_READER_MODE_MISMATCH",
        )

    state = row.get("state")
    if state not in READ_STATES:
        return _result(
            "MISMATCH",
            execution_id=execution_id,
            error_code="RUNTIME_READER_STATE_UNKNOWN",
        )

    for key in reader.FALSE_FIELDS:
        if row.get(key) is not False:
            return _result(
                "MISMATCH",
                execution_id=execution_id,
                error_code="RUNTIME_READER_UNSAFE_AUTHORITY_FIELD:" + key,
            )

    if _contains_forbidden_material(row):
        return _result(
            "MISMATCH",
            execution_id=execution_id,
            error_code="FORBIDDEN_READ_MODEL_MATERIAL_PRESENT",
        )

    if state in {"MISMATCH", "UNAVAILABLE"}:
        return _result(
            state,
            execution_id=execution_id,
            error_code=str(row.get("error_code") or "RUNTIME_READER_FAIL_CLOSED"),
            observed_at=str(row.get("observed_at") or ""),
        )

    if row.get("projection_is_evidence_not_authority") is not True:
        return _result(
            "MISMATCH",
            execution_id=execution_id,
            error_code="SOURCE_PROJECTION_AUTHORITY_BOUNDARY_MISSING",
        )
    if row.get("verified_is_evidence_not_authority") is not True:
        return _result(
            "MISMATCH",
            execution_id=execution_id,
            error_code="RUNTIME_READER_AUTHORITY_BOUNDARY_MISSING",
        )

    expected_scope = {
        "owner_id": owner_id,
        "tenant_id": tenant_id,
        "workspace_id": workspace_id,
    }
    for key, expected in expected_scope.items():
        if row.get(key) != expected:
            return _result(
                "MISMATCH",
                execution_id=execution_id,
                error_code="READ_MODEL_SCOPE_MISMATCH:" + key,
            )

    for key in REQUIRED_EVIDENCE_FIELDS:
        value = row.get(key)
        if value is None or value == "":
            return _result(
                "MISMATCH",
                execution_id=execution_id,
                error_code="READ_MODEL_EVIDENCE_REQUIRED:" + key,
            )

    age_seconds = row.get("age_seconds")
    max_age_seconds = row.get("max_age_seconds")
    if (
        isinstance(age_seconds, bool)
        or isinstance(max_age_seconds, bool)
        or not isinstance(age_seconds, int)
        or not isinstance(max_age_seconds, int)
        or age_seconds < 0
        or max_age_seconds < 1
    ):
        return _result(
            "MISMATCH",
            execution_id=execution_id,
            error_code="READ_MODEL_FRESHNESS_VALUES_INVALID",
        )
    if state == "VERIFIED" and age_seconds > max_age_seconds:
        return _result(
            "MISMATCH",
            execution_id=execution_id,
            error_code="VERIFIED_CANNOT_EXCEED_FRESHNESS_WINDOW",
        )
    if state == "STALE" and age_seconds <= max_age_seconds:
        return _result(
            "MISMATCH",
            execution_id=execution_id,
            error_code="STALE_REQUIRES_EXCEEDED_FRESHNESS_WINDOW",
        )

    return _result(
        state,
        execution_id=execution_id,
        error_code=str(row.get("error_code") or ""),
        owner_id=owner_id,
        tenant_id=tenant_id,
        workspace_id=workspace_id,
        final_execution_state=row["final_execution_state"],
        terminal_revision=row["terminal_revision"],
        certificate_manifest_digest=row["certificate_manifest_digest"],
        certificate_digest=row["certificate_digest"],
        certificate_persistence_record_digest=row[
            "certificate_persistence_record_digest"
        ],
        finalization_record_digest=row["finalization_record_digest"],
        audit_seal_manifest_digest=row["audit_seal_manifest_digest"],
        audit_seal_persistence_record_digest=row["audit_seal_record_digest"],
        terminal_evidence_set_digest=row["terminal_evidence_set_digest"],
        finops_observation_digest=row["finops_observation_digest"],
        observability_trace_id=row["observability_trace_id"],
        pre_terminal_audit_chain_digest=row["pre_terminal_audit_chain_digest"],
        persisted_at=row["persisted_at"],
        observed_at=row["observed_at"],
        age_seconds=age_seconds,
        max_age_seconds=max_age_seconds,
    )


__all__ = [
    "SCHEMA",
    "MODE",
    "NEXT_ALLOWED_STEP",
    "READ_STATES",
    "DIGEST_ALGORITHM",
    "CANONICAL_ENCODING",
    "FALSE_FIELDS",
    "REQUIRED_EVIDENCE_FIELDS",
    "project_terminal_certificate_read_model_offline",
]
