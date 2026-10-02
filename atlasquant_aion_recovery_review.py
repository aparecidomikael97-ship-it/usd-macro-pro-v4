"""Read-only recovery review bridge.

Builds a local allowlisted checkpoint trace and binds it to the recovery
traceability gate. This module never restores, saves, retries, deploys, or
turns evidence into authority.
"""
from __future__ import annotations

from typing import Any, Mapping

from atlasquant_aion_local_executor import execute_local_tool
from atlasquant_aion_local_synthesis import synthesize_local_tool_results
from atlasquant_aion_local_traceability import build_local_traceability
from atlasquant_aion_recovery_traceability_gate import (
    recovery_traceability_readiness,
)

SCHEMA = "ATLASQUANT_AION_RECOVERY_REVIEW_V1"


def build_recovery_review(
    access: Mapping[str, Any] | None,
    current_runtime: Mapping[str, Any] | None,
    candidate: Mapping[str, Any] | None,
    *,
    authenticated_admin: bool = False,
    request_id: Any = "recovery-review",
) -> dict[str, Any]:
    current = dict(current_runtime or {})
    checkpoint = current.get("checkpoint")
    execution = execute_local_tool(
        "aion.checkpoint.inspect",
        access=access,
        authenticated_admin=authenticated_admin is True,
        source_kind="ADMIN",
        runtime_context={"checkpoint": checkpoint},
        request_id=request_id,
    )
    synthesis = synthesize_local_tool_results([execution])
    traceability = build_local_traceability(
        [execution],
        synthesis=synthesis,
    )
    readiness = recovery_traceability_readiness(
        current,
        candidate,
        traceability,
    )
    blockers = list(readiness.get("blockers") or [])
    if execution.get("state") != "SUCCESS":
        blockers.append("CHECKPOINT_INSPECTION_NOT_SUCCESSFUL")
    if traceability.get("security", {}).get("state") != "SAFE_LOCAL":
        blockers.append("TRACEABILITY_NOT_SAFE_LOCAL")
    blockers = list(dict.fromkeys(blockers))
    ready = (
        readiness.get("state") == "READY_FOR_ADMIN_REVIEW"
        and not blockers
    )
    return {
        "schema": SCHEMA,
        "state": "READY_FOR_ADMIN_REVIEW" if ready else "BLOCKED",
        "blockers": blockers,
        "checkpoint_execution_state": str(execution.get("state") or "UNKNOWN"),
        "checkpoint_integrity_state": str(
            (execution.get("result") or {}).get("integrity", {}).get("state")
            or "UNKNOWN"
        ),
        "traceability_state": str(traceability.get("state") or "UNKNOWN"),
        "traceability_security": str(
            traceability.get("security", {}).get("state") or "UNKNOWN"
        ),
        "trace_refs": list(traceability.get("execution_refs") or []),
        "source_keys": list(traceability.get("source_keys") or []),
        "recovery_preflight": dict(readiness.get("recovery_preflight") or {}),
        "receipt": dict(readiness.get("receipt") or {}),
        "receipt_digest": str(readiness.get("receipt_digest") or ""),
        "restore_authorized": False,
        "automatic_restore": False,
        "automatic_retry": False,
        "checkpoint_saved": False,
        "execution_authorized": False,
        "external_action_executed": False,
        "network_called": False,
        "tool_output_is_authority": False,
    }


__all__ = ["SCHEMA", "build_recovery_review"]
