"""AION B2B terminal-certificate runtime reader offline V1.

Offline-only, read-only and fail-closed.

Consumes the already-authorized DurableExecutionStore instance and projects a
terminal certificate snapshot into exactly one of:
VERIFIED, MISMATCH, UNAVAILABLE or STALE.

This layer never opens a database path itself, performs no network/provider
fallback, mutates no durable record and grants no execution authority.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from atlasquant_aion_durable_execution_kernel import (
    DurableExecutionStore,
    STORE_SCHEMA_VERSION,
)

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
    store: DurableExecutionStore,
    execution_id: str,
    owner_id: str,
    tenant_id: str,
    workspace_id: str,
    observed_at: str,
    max_age_seconds: int = DEFAULT_MAX_AGE_SECONDS,
) -> dict[str, Any]:
    """Read and project one terminal certificate with no external side effects."""
    clean_execution_id = " ".join(str(execution_id or "").split())[:96]

    if not isinstance(store, DurableExecutionStore):
        return _safe_result(
            "UNAVAILABLE",
            execution_id=clean_execution_id,
            error_code="DURABLE_EXECUTION_STORE_REQUIRED",
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
        version = store.store_schema_version()
    except Exception:
        return _safe_result(
            "UNAVAILABLE",
            execution_id=clean_execution_id,
            error_code="STORE_SCHEMA_VERSION_UNAVAILABLE",
        )
    if version != STORE_SCHEMA_VERSION:
        return _safe_result(
            "MISMATCH",
            execution_id=clean_execution_id,
            error_code="STORE_SCHEMA_VERSION_MISMATCH",
            observed_store_schema_version=version,
            expected_store_schema_version=STORE_SCHEMA_VERSION,
        )

    try:
        snapshot = store.read_terminal_certificate_snapshot(
            clean_execution_id,
            owner_id=owner_id,
            tenant_id=tenant_id,
            workspace_id=workspace_id,
        )
    except Exception:
        return _safe_result(
            "UNAVAILABLE",
            execution_id=clean_execution_id,
            error_code="DURABLE_SNAPSHOT_READ_FAILED",
        )

    snapshot_state = snapshot.get("state")
    if snapshot_state in {"MISMATCH", "UNAVAILABLE"}:
        return _safe_result(
            snapshot_state,
            execution_id=clean_execution_id,
            error_code=str(snapshot.get("error_code") or "SNAPSHOT_FAIL_CLOSED"),
        )
    if snapshot_state != "VERIFIED":
        return _safe_result(
            "MISMATCH",
            execution_id=clean_execution_id,
            error_code="UNKNOWN_SNAPSHOT_STATE",
        )

    scope = dict(snapshot.get("scope") or {})
    finalization = dict(snapshot.get("finalization") or {})
    seal = dict(snapshot.get("audit_seal") or {})
    certificate = dict(snapshot.get("certificate") or {})

    persisted_at = certificate.get("persisted_at")
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
    projection = {
        "owner_id": scope.get("owner_id", ""),
        "tenant_id": scope.get("tenant_id", ""),
        "workspace_id": scope.get("workspace_id", ""),
        "terminal_revision": certificate.get("terminal_revision"),
        "final_execution_state": certificate.get("final_execution_state", ""),
        "scope_digest": certificate.get("scope_digest", ""),
        "finalization_record_digest": certificate.get("finalization_record_digest", ""),
        "audit_seal_manifest_digest": certificate.get("audit_seal_manifest_digest", ""),
        "audit_seal_record_digest": certificate.get("audit_seal_record_digest", ""),
        "certificate_manifest_digest": certificate.get("certificate_manifest_digest", ""),
        "certificate_digest": certificate.get("certificate_digest", ""),
        "certificate_persistence_record_digest": certificate.get(
            "certificate_persistence_record_digest", ""
        ),
        "terminal_evidence_set_digest": certificate.get(
            "terminal_evidence_set_digest", ""
        ),
        "finops_observation_digest": certificate.get("finops_observation_digest", ""),
        "observability_trace_id": certificate.get("observability_trace_id", ""),
        "pre_terminal_audit_chain_digest": certificate.get(
            "pre_terminal_audit_chain_digest", ""
        ),
        "audit_chain_digest": seal.get("audit_chain_digest", ""),
        "core_execution_state": finalization.get("core_execution_state", ""),
        "persisted_at": persisted_at,
        "observed_at": observed_at,
        "age_seconds": age_seconds,
        "max_age_seconds": max_age_seconds,
        "verified_is_evidence_not_authority": True,
    }

    if age_seconds > max_age_seconds:
        return _safe_result(
            "STALE",
            execution_id=clean_execution_id,
            error_code="CERTIFICATE_EVIDENCE_STALE",
            **projection,
        )
    return _safe_result(
        "VERIFIED",
        execution_id=clean_execution_id,
        **projection,
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
