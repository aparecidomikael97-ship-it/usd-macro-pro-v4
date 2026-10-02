"""Read-only recovery + traceability readiness gate for AION.

This module recomputes recovery preflight and binds it to safe local
traceability. It never restores, saves, retries, deploys, or authorizes action.
"""
from __future__ import annotations

from typing import Any, Mapping
import hashlib
import json

from atlasquant_aion_recovery import recovery_preflight
from atlasquant_aion_local_traceability import SCHEMA as TRACE_SCHEMA

SCHEMA = "ATLASQUANT_AION_RECOVERY_TRACEABILITY_GATE_V1"

def _digest(value: Any) -> str:
    raw = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(raw).hexdigest()

def recovery_traceability_readiness(
    current_runtime: Mapping[str, Any] | None,
    candidate: Mapping[str, Any] | None,
    traceability: Mapping[str, Any] | None,
) -> dict[str, Any]:
    current = dict(current_runtime or {})
    selected = dict(candidate or {})
    trace = dict(traceability or {})
    preflight = recovery_preflight(current, selected)
    blockers: list[str] = []

    if preflight.get("allowed") is not True:
        blockers.append("RECOVERY_PREFLIGHT_BLOCKED")
    if trace.get("schema") != TRACE_SCHEMA:
        blockers.append("TRACEABILITY_SCHEMA_INVALID")
    if str(trace.get("security", {}).get("state") or "").upper() != "SAFE_LOCAL":
        blockers.append("TRACEABILITY_SECURITY_BLOCK")
    if trace.get("contract_consistent") is not True:
        blockers.append("TRACEABILITY_CONTRACT_INCONSISTENT")

    if trace.get("contract_mismatch") is True:
        blockers.append("TRACEABILITY_CONTRACT_MISMATCH")
    if int(trace.get("record_count") or 0) <= 0:
        blockers.append("TRACEABILITY_EVIDENCE_REQUIRED")
    if not list(trace.get("execution_refs") or []):
        blockers.append("TRACEABILITY_EXECUTION_REF_REQUIRED")
    if list(trace.get("conflict_refs") or []):
        blockers.append("TRACEABILITY_CONFLICT")
    if "checkpoint_master" not in set(trace.get("source_keys") or []):
        blockers.append("CHECKPOINT_TRACE_REQUIRED")
    security = dict(trace.get("security") or {})
    if security.get("external_side_effects") is not False:
        blockers.append("TRACEABILITY_EXTERNAL_SIDE_EFFECT_UNKNOWN")
    if any(bool(dict(row).get("authority")) for row in trace.get("records") or []):
        blockers.append("TRACEABILITY_AUTHORITY_FORBIDDEN")

    receipt = {
        "current_runtime_sha": str(current.get("sha") or ""),
        "candidate_revision": str(preflight.get("candidate_revision") or ""),
        "candidate_digest": str(preflight.get("candidate_digest") or ""),
        "candidate_integrity": str(preflight.get("candidate_integrity") or ""),

        "trace_refs": sorted(str(x) for x in trace.get("execution_refs") or []),
        "trace_sources": sorted(str(x) for x in trace.get("source_keys") or []),
        "requires_explicit_admin_approval": True,
        "automatic_restore": False,
    }
    receipt_digest = _digest(receipt)
    ready = not blockers
    return {
        "schema": SCHEMA,
        "state": "READY_FOR_ADMIN_REVIEW" if ready else "BLOCKED",
        "blockers": list(dict.fromkeys(blockers)),
        "recovery_preflight": preflight,
        "traceability_state": str(trace.get("state") or "UNKNOWN"),
        "receipt": receipt,
        "receipt_digest": receipt_digest,
        "recovery_authorized": False,
        "automatic_restore": False,
        "automatic_retry": False,
        "checkpoint_saved": False,
        "external_action_executed": False,
        "network_called": False,
    }

def recovery_traceability_policy() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "recovery_preflight_required": True,
        "traceability_required": True,
        "safe_local_trace_required": True,
        "checkpoint_source_required": True,
        "conflict_blocks_readiness": True,
        "explicit_admin_approval_required": True,
        "automatic_restore": False,
        "automatic_retry": False,
        "execution_authority": False,
    }

__all__ = [
    "SCHEMA",
    "recovery_traceability_readiness",
    "recovery_traceability_policy",
]
