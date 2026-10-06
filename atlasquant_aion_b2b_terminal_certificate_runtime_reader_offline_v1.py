"""AION B2B terminal-certificate runtime reader offline V1.

Offline-only, read-only and fail-closed.

Consumes a logical terminal-certificate read-model source and projects the
evidence into exactly one of VERIFIED, MISMATCH, UNAVAILABLE or STALE.

The runtime reader intentionally has no DurableExecutionStore dependency. The
physical durable-store binding lives behind the read-model source adapter.
This layer opens no database path, performs no network/provider fallback,
mutates no durable record and grants no execution authority.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

SCHEMA = "ATLASQUANT_AION_B2B_TERMINAL_CERTIFICATE_RUNTIME_READER_OFFLINE_V1"
MODE = "OFFLINE_READ_ONLY_FAIL_CLOSED_TERMINAL_CERTIFICATE_READER"

READ_STATES = ("VERIFIED", "MISMATCH", "UNAVAILABLE", "STALE")
DEFAULT_MAX_AGE_SECONDS = 300
MAX_MAX_AGE_SECONDS = 86400

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
    "executes_action",
)


def _safe_result(state: str, *, execution_id: str, error_code: str = "", **fields):
    if state not in READ_STATES:
        state = "MISMATCH"
        error_code = error_code or "UNKNOWN_READ_STATE"
    return {
        "schema": SCHEMA,
        "mode": MODE,
        "state": state,
        "execution_id": execution_id,
        "error_code": error_code,
        **fields,
        **{key: False for key in FALSE_FIELDS},
    }


def _parse_utc(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.endswith("Z"):
        return None
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
        return parsed.astimezone(timezone.utc)
    except Exception:
        return None


def read_terminal_certificate_offline(
    *,
    read_model_source: Any,
    execution_id: str,
    owner_id: str,
    tenant_id: str,
    workspace_id: str,
    observed_at: str,
    max_age_seconds: int = DEFAULT_MAX_AGE_SECONDS,
) -> dict[str, Any]:
    """Read one logical certificate projection with no external side effects."""
    clean_execution_id = " ".join(str(execution_id or "").split())[:96]

    read_projection = getattr(
        read_model_source,
        "read_terminal_certificate_projection",
        None,
    )
    if not callable(read_projection):
        return _safe_result(
            "UNAVAILABLE",
            execution_id=clean_execution_id,
            error_code="TERMINAL_CERTIFICATE_READ_MODEL_SOURCE_REQUIRED",
        )
    if not clean_execution_id:
        return _safe_result(
            "UNAVAILABLE",
            execution_id="",
            error_code="EXECUTION_ID_REQUIRED",
        )
    if (
        isinstance(max_age_seconds, bool)
        or not isinstance(max_age_seconds, int)
        or not 1 <= max_age_seconds <= MAX_MAX_AGE_SECONDS
    ):
        return _safe_result(
            "MISMATCH",
            execution_id=clean_execution_id,
            error_code="FRESHNESS_POLICY_INVALID",
        )
    observed = _parse_utc(observed_at)
    if observed is None:
        return _safe_result(
            "MISMATCH",
            execution_id=clean_execution_id,
            error_code="OBSERVED_AT_INVALID",
        )

    try:
        projection = read_projection(
            clean_execution_id,
            owner_id=owner_id,
            tenant_id=tenant_id,
            workspace_id=workspace_id,
        )
    except Exception:
        return _safe_result(
            "UNAVAILABLE",
            execution_id=clean_execution_id,
            error_code="READ_MODEL_PROJECTION_FAILED",
        )

    if not isinstance(projection, dict):
        return _safe_result(
            "MISMATCH",
            execution_id=clean_execution_id,
            error_code="READ_MODEL_PROJECTION_INVALID",
        )

    projection_state = projection.get("state")
    if projection_state in {"MISMATCH", "UNAVAILABLE"}:
        return _safe_result(
            projection_state,
            execution_id=clean_execution_id,
            error_code=str(projection.get("error_code") or "READ_MODEL_FAIL_CLOSED"),
        )
    if projection_state != "VERIFIED":
        return _safe_result(
            "MISMATCH",
            execution_id=clean_execution_id,
            error_code="UNKNOWN_READ_MODEL_STATE",
        )
    if projection.get("projection_is_evidence_not_authority") is not True:
        return _safe_result(
            "MISMATCH",
            execution_id=clean_execution_id,
            error_code="READ_MODEL_AUTHORITY_BOUNDARY_MISSING",
        )

    persisted_at = projection.get("persisted_at")
    persisted = _parse_utc(persisted_at)
    if persisted is None:
        return _safe_result(
            "MISMATCH",
            execution_id=clean_execution_id,
            error_code="CERTIFICATE_PERSISTED_AT_INVALID",
        )
    if observed < persisted:
        return _safe_result(
            "MISMATCH",
            execution_id=clean_execution_id,
            error_code="OBSERVED_AT_BEFORE_CERTIFICATE_PERSISTED_AT",
        )

    age_seconds = int((observed - persisted).total_seconds())
    safe_projection = {
        key: value
        for key, value in projection.items()
        if key not in {
            "schema",
            "mode",
            "state",
            "error_code",
            "execution_id",
            "execution_authority_created",
            "retry_authorized",
            "reopen_authorized",
            "external_effect_authorized",
            "network_called",
            "provider_called",
            "production_mutation_authorized",
            "executes_action",
        }
    }
    safe_projection.update(
        {
            "persisted_at": persisted_at,
            "observed_at": observed_at,
            "age_seconds": age_seconds,
            "max_age_seconds": max_age_seconds,
            "verified_is_evidence_not_authority": True,
        }
    )

    if age_seconds > max_age_seconds:
        return _safe_result(
            "STALE",
            execution_id=clean_execution_id,
            error_code="CERTIFICATE_EVIDENCE_STALE",
            **safe_projection,
        )
    return _safe_result(
        "VERIFIED",
        execution_id=clean_execution_id,
        **safe_projection,
    )


__all__ = [
    "SCHEMA",
    "MODE",
    "READ_STATES",
    "DEFAULT_MAX_AGE_SECONDS",
    "MAX_MAX_AGE_SECONDS",
    "FALSE_FIELDS",
    "read_terminal_certificate_offline",
]
