"""AION B2B terminal-certificate read-model store projection offline V1.

Offline-only, read-only and fail-closed physical adapter.

This module is the only offline layer allowed to know DurableExecutionStore.
It converts the authorized durable snapshot into a safe logical read-model
projection. The runtime reader consumes that projection interface and therefore
does not import, open or query the durable store directly.
"""
from __future__ import annotations

from typing import Any

from atlasquant_aion_durable_execution_kernel import (
    DurableExecutionStore,
    STORE_SCHEMA_VERSION,
)

SCHEMA = "ATLASQUANT_AION_B2B_TERMINAL_CERTIFICATE_READ_MODEL_STORE_PROJECTION_OFFLINE_V1"
MODE = "OFFLINE_READ_ONLY_TERMINAL_CERTIFICATE_READ_MODEL_STORE_PROJECTION"
PROJECTION_STATES = ("VERIFIED", "MISMATCH", "UNAVAILABLE")


def _projection(state: str, *, execution_id: str, error_code: str = "", **fields):
    if state not in PROJECTION_STATES:
        state = "MISMATCH"
        error_code = error_code or "UNKNOWN_PROJECTION_STATE"
    return {
        "schema": SCHEMA,
        "mode": MODE,
        "state": state,
        "execution_id": execution_id,
        "error_code": error_code,
        **fields,
        "projection_is_evidence_not_authority": True,
        "execution_authority_created": False,
        "retry_authorized": False,
        "reopen_authorized": False,
        "external_effect_authorized": False,
        "network_called": False,
        "provider_called": False,
        "production_mutation_authorized": False,
        "executes_action": False,
    }


class DurableTerminalCertificateReadModelSource:
    """Safe logical projection source backed by an already-authorized store."""

    def __init__(self, store: DurableExecutionStore):
        self._store = store

    def read_terminal_certificate_projection(
        self,
        execution_id: str,
        *,
        owner_id: str,
        tenant_id: str,
        workspace_id: str,
    ) -> dict[str, Any]:
        clean_execution_id = " ".join(str(execution_id or "").split())[:96]
        if not isinstance(self._store, DurableExecutionStore):
            return _projection(
                "UNAVAILABLE",
                execution_id=clean_execution_id,
                error_code="DURABLE_EXECUTION_STORE_REQUIRED",
            )
        if not clean_execution_id:
            return _projection(
                "UNAVAILABLE",
                execution_id="",
                error_code="EXECUTION_ID_REQUIRED",
            )

        try:
            version = self._store.store_schema_version()
        except Exception:
            return _projection(
                "UNAVAILABLE",
                execution_id=clean_execution_id,
                error_code="STORE_SCHEMA_VERSION_UNAVAILABLE",
            )
        if version != STORE_SCHEMA_VERSION:
            return _projection(
                "MISMATCH",
                execution_id=clean_execution_id,
                error_code="STORE_SCHEMA_VERSION_MISMATCH",
                observed_store_schema_version=version,
                expected_store_schema_version=STORE_SCHEMA_VERSION,
            )

        try:
            snapshot = self._store.read_terminal_certificate_snapshot(
                clean_execution_id,
                owner_id=owner_id,
                tenant_id=tenant_id,
                workspace_id=workspace_id,
            )
        except Exception:
            return _projection(
                "UNAVAILABLE",
                execution_id=clean_execution_id,
                error_code="DURABLE_SNAPSHOT_READ_FAILED",
            )

        snapshot_state = snapshot.get("state")
        if snapshot_state in {"MISMATCH", "UNAVAILABLE"}:
            return _projection(
                snapshot_state,
                execution_id=clean_execution_id,
                error_code=str(snapshot.get("error_code") or "SNAPSHOT_FAIL_CLOSED"),
            )
        if snapshot_state != "VERIFIED":
            return _projection(
                "MISMATCH",
                execution_id=clean_execution_id,
                error_code="UNKNOWN_SNAPSHOT_STATE",
            )

        scope = dict(snapshot.get("scope") or {})
        finalization = dict(snapshot.get("finalization") or {})
        seal = dict(snapshot.get("audit_seal") or {})
        certificate = dict(snapshot.get("certificate") or {})

        return _projection(
            "VERIFIED",
            execution_id=clean_execution_id,
            owner_id=scope.get("owner_id", ""),
            tenant_id=scope.get("tenant_id", ""),
            workspace_id=scope.get("workspace_id", ""),
            terminal_revision=certificate.get("terminal_revision"),
            final_execution_state=certificate.get("final_execution_state", ""),
            scope_digest=certificate.get("scope_digest", ""),
            finalization_record_digest=certificate.get("finalization_record_digest", ""),
            audit_seal_manifest_digest=certificate.get("audit_seal_manifest_digest", ""),
            audit_seal_record_digest=certificate.get("audit_seal_record_digest", ""),
            certificate_manifest_digest=certificate.get("certificate_manifest_digest", ""),
            certificate_digest=certificate.get("certificate_digest", ""),
            certificate_persistence_record_digest=certificate.get(
                "certificate_persistence_record_digest", ""
            ),
            terminal_evidence_set_digest=certificate.get(
                "terminal_evidence_set_digest", ""
            ),
            finops_observation_digest=certificate.get("finops_observation_digest", ""),
            observability_trace_id=certificate.get("observability_trace_id", ""),
            pre_terminal_audit_chain_digest=certificate.get(
                "pre_terminal_audit_chain_digest", ""
            ),
            audit_chain_digest=seal.get("audit_chain_digest", ""),
            core_execution_state=finalization.get("core_execution_state", ""),
            persisted_at=certificate.get("persisted_at", ""),
        )


__all__ = [
    "SCHEMA",
    "MODE",
    "PROJECTION_STATES",
    "DurableTerminalCertificateReadModelSource",
]
