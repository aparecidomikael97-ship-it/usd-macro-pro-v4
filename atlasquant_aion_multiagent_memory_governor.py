"""AION V2.17 multi-agent and memory governance.

Composes the existing Loop Governor and Memory Contract with explicit supervisor,
deadline, cost, delegation-lineage, TTL, confidence and retention rules.

This module is governance only. It does not start agents, grant capabilities,
promote memory to authority, delete audit history or execute external actions.
"""
from __future__ import annotations

from datetime import datetime, timezone
import math
from typing import Any, Mapping, Sequence

from atlasquant_aion_loop_governor import govern_agent_plan
from atlasquant_aion_memory_contract import (
    MemoryContractRecord,
    create_memory_record,
    memory_contract_digest,
    operational_decision,
)

SCHEMA = "ATLASQUANT_AION_MULTIAGENT_MEMORY_GOVERNANCE_V1"
PLAN_SCHEMA = "ATLASQUANT_AION_MULTIAGENT_GOVERNOR_V1"
MEMORY_SCHEMA = "ATLASQUANT_AION_MEMORY_GOVERNANCE_V1"
TOMBSTONE_SCHEMA = "ATLASQUANT_AION_MEMORY_EXPIRY_TOMBSTONE_V1"


def _clean(value: Any, limit: int = 256) -> str:
    return " ".join(str(value or "").replace("\x00", "").split())[:limit]


def _parse_ts(value: Any) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError("RFC3339 UTC timestamp required")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00").astimezone(timezone.utc)
    except Exception as exc:
        raise ValueError("invalid RFC3339 UTC timestamp") from exc
    return parsed


def _money(value: Any, name: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be numeric")
    try:
        number = float(value)
    except Exception as exc:
        raise ValueError(f"{name} must be numeric") from exc
    if not math.isfinite(number) or number < 0:
        raise ValueError(f"{name} must be finite and non-negative")
    return number


def _confidence(value: Any) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except Exception:
        return None
    if not math.isfinite(number) or not 0 <= number <= 100:
        return None
    return number


def govern_multiagent_session(
    nodes: Sequence[Mapping[str, Any]] | None,
    *,
    trusted_context: Mapping[str, Any],
    supervisor_id: Any,
    allowed_capabilities: Sequence[Any],
    now_ts: str,
    session_deadline_at: str,
    cost_limit_usd: Any,
    cost_used_usd: Any = 0.0,
    max_depth: Any = 3,
    max_fanout: Any = 4,
    max_nodes: Any = 16,
    call_limit: Any = 100,
    calls_used: Any = 0,
    token_limit: Any = 100000,
    tokens_used: Any = 0,
    wall_seconds_limit: Any = 300,
    wall_seconds_used: Any = 0,
    memory_mb_limit: Any = 1024,
    memory_mb_used: Any = 0,
) -> dict[str, Any]:
    """Govern one multi-agent plan before any agent is started."""
    malformed: list[str] = []
    if nodes is None:
        raw_nodes = []
    elif isinstance(nodes, (list, tuple)):
        raw_nodes = list(nodes)
    else:
        raw_nodes = []
        malformed.append("PLAN_NODES_INVALID")

    rows = []
    for index, item in enumerate(raw_nodes):
        if not isinstance(item, Mapping):
            malformed.append(f"PLAN_NODE_NOT_MAPPING:{index}")
            continue
        rows.append(dict(item))

    trusted_context_valid = isinstance(trusted_context, Mapping)
    trusted = dict(trusted_context) if trusted_context_valid else {}

    base = govern_agent_plan(
        rows,
        trusted_context=trusted,
        max_depth=max_depth,
        max_fanout=max_fanout,
        max_nodes=max_nodes,
        call_limit=call_limit,
        calls_used=calls_used,
        token_limit=token_limit,
        tokens_used=tokens_used,
        wall_seconds_limit=wall_seconds_limit,
        wall_seconds_used=wall_seconds_used,
        memory_mb_limit=memory_mb_limit,
        memory_mb_used=memory_mb_used,
    )
    blockers = list(malformed) + list(base.get("blockers") or [])
    if not trusted_context_valid:
        blockers.append("TRUSTED_CONTEXT_INVALID")

    supervisor = _clean(supervisor_id, 120)
    if not supervisor:
        blockers.append("SUPERVISOR_REQUIRED")

    try:
        now = _parse_ts(now_ts)
        session_deadline = _parse_ts(session_deadline_at)
    except ValueError:
        now = None
        session_deadline = None
        blockers.append("SESSION_TIME_INVALID")
    if now is not None and session_deadline is not None and session_deadline <= now:
        blockers.append("SESSION_DEADLINE_EXCEEDED")

    if isinstance(allowed_capabilities, (list, tuple, set, frozenset)):
        allowed = {
            _clean(item, 120).lower()
            for item in allowed_capabilities
            if _clean(item, 120)
        }
    else:
        allowed = set()
        blockers.append("ALLOWED_CAPABILITIES_INVALID")
    if not allowed:
        blockers.append("ALLOWED_CAPABILITIES_REQUIRED")

    try:
        cost_limit = _money(cost_limit_usd, "cost_limit_usd")
        cost_used = _money(cost_used_usd, "cost_used_usd")
    except ValueError:
        cost_limit = 0.0
        cost_used = 0.0
        blockers.append("COST_BUDGET_INVALID")
    if cost_limit <= 0:
        blockers.append("COST_LIMIT_REQUIRED")
    if cost_used > cost_limit > 0:
        blockers.append("COST_BUDGET_ALREADY_EXCEEDED")

    roots = [row for row in rows if not _clean(row.get("parent_id"), 120)]
    if len(roots) == 1 and supervisor:
        if _clean(roots[0].get("node_id"), 120) != supervisor:
            blockers.append("SUPERVISOR_ROOT_MISMATCH")

    estimated_total = 0.0
    for row in rows:
        node_id = _clean(row.get("node_id"), 120)
        parent_id = _clean(row.get("parent_id"), 120)
        delegated_by = _clean(row.get("delegated_by"), 120)
        requested_capability = _clean(row.get("requested_capability"), 120).lower()

        if parent_id:
            if delegated_by != parent_id:
                blockers.append(f"DELEGATION_LINEAGE_MISMATCH:{node_id or 'UNKNOWN'}")
        elif delegated_by:
            blockers.append(f"ROOT_DELEGATION_INVALID:{node_id or 'UNKNOWN'}")

        if not requested_capability:
            blockers.append(f"CAPABILITY_SCOPE_MISSING:{node_id or 'UNKNOWN'}")
        elif requested_capability not in allowed:
            blockers.append(f"CAPABILITY_ESCALATION_REQUESTED:{node_id or 'UNKNOWN'}")

        node_deadline_raw = row.get("deadline_at")
        try:
            node_deadline = _parse_ts(node_deadline_raw)
        except ValueError:
            blockers.append(f"NODE_DEADLINE_INVALID:{node_id or 'UNKNOWN'}")
        else:
            if now is not None and node_deadline <= now:
                blockers.append(f"NODE_DEADLINE_EXPIRED:{node_id or 'UNKNOWN'}")
            if session_deadline is not None and node_deadline > session_deadline:
                blockers.append(f"NODE_DEADLINE_EXCEEDS_SESSION:{node_id or 'UNKNOWN'}")

        try:
            estimated_total += _money(row.get("estimated_cost_usd"), "estimated_cost_usd")
        except ValueError:
            blockers.append(f"NODE_COST_INVALID:{node_id or 'UNKNOWN'}")

    projected_cost = cost_used + estimated_total
    if cost_limit > 0 and projected_cost > cost_limit:
        blockers.append("COST_BUDGET_EXCEEDED")

    unique = list(dict.fromkeys(blockers))
    return {
        "schema": PLAN_SCHEMA,
        "state": "WITHIN_GOVERNANCE" if not unique else "BLOCK",
        "blockers": unique,
        "supervisor_id": supervisor,
        "trusted_tenant_id": _clean(trusted.get("tenant_id"), 120),
        "trusted_workspace_id": _clean(trusted.get("workspace_id"), 120),
        "allowed_capabilities": sorted(allowed),
        "session_deadline_at": session_deadline_at,
        "cost_limit_usd": round(cost_limit, 6),
        "cost_used_usd": round(cost_used, 6),
        "estimated_plan_cost_usd": round(estimated_total, 6),
        "projected_cost_usd": round(projected_cost, 6),
        "loop_governor": base,
        "delegation_lineage_verified": not any(
            item.startswith("DELEGATION_LINEAGE_MISMATCH")
            or item.startswith("ROOT_DELEGATION_INVALID")
            for item in unique
        ),
        "supervisor_binding_verified": "SUPERVISOR_ROOT_MISMATCH" not in unique
        and "SUPERVISOR_REQUIRED" not in unique,
        "capability_requests_within_host_ceiling": not any(
            item.startswith("CAPABILITY_ESCALATION_REQUESTED")
            or item.startswith("CAPABILITY_SCOPE_MISSING")
            for item in unique
        ),
        "grants_permission": False,
        "execution_allowed": False,
        "starts_worker": False,
        "starts_agent": False,
        "tool_called": False,
        "executes_action": False,
    }


def govern_memory_use(
    record: MemoryContractRecord,
    *,
    now_ts: str,
    trusted_tenant_id: Any = "",
    trusted_persona_id: Any = "",
    minimum_confidence_pct: Any = 70.0,
) -> dict[str, Any]:
    """Decide whether a versioned memory may inform operational reasoning.

    Operational memory can inform reasoning but can never grant permission.
    """
    if not isinstance(record, MemoryContractRecord):
        raise TypeError("trusted MemoryContractRecord required")

    now = _parse_ts(now_ts)
    base = operational_decision(record)
    blockers = list(base.get("blockers") or [])

    tenant = _clean(trusted_tenant_id, 120)
    persona = _clean(trusted_persona_id, 120)
    scoped_tenant = _clean(record.scope.get("tenant_id"), 120)
    scoped_persona = _clean(record.scope.get("persona_id"), 120)

    if scoped_tenant:
        if not tenant:
            blockers.append("TRUSTED_TENANT_REQUIRED")
        elif tenant != scoped_tenant:
            blockers.append("TENANT_SCOPE_MISMATCH")
    if record.namespace == "TENANT" and not scoped_tenant:
        blockers.append("TENANT_SCOPE_MISSING")

    if scoped_persona or record.namespace == "PERSONA":
        if not persona:
            blockers.append("TRUSTED_PERSONA_REQUIRED")
        elif persona != scoped_persona:
            blockers.append("PERSONA_SCOPE_MISMATCH")

    threshold = _confidence(minimum_confidence_pct)
    if threshold is None:
        raise ValueError("minimum_confidence_pct invalid")
    confidence = _confidence(record.metadata.get("confidence_pct"))
    if confidence is None:
        blockers.append("CONFIDENCE_MISSING_OR_INVALID")
    elif confidence < threshold:
        blockers.append("CONFIDENCE_BELOW_THRESHOLD")

    valid_from_raw = record.metadata.get("valid_from")
    expires_raw = record.metadata.get("expires_at")
    valid_from = None
    expires = None

    if valid_from_raw:
        try:
            valid_from = _parse_ts(valid_from_raw)
        except ValueError:
            blockers.append("VALID_FROM_INVALID")
    if expires_raw:
        try:
            expires = _parse_ts(expires_raw)
        except ValueError:
            blockers.append("EXPIRES_AT_INVALID")

    if valid_from is not None and valid_from > now:
        blockers.append("MEMORY_NOT_YET_VALID")
    if expires is not None:
        if valid_from is not None and expires <= valid_from:
            blockers.append("MEMORY_VALIDITY_WINDOW_INVALID")
        if expires <= now:
            blockers.append("MEMORY_EXPIRED")
    elif record.retention in {"SESSION", "PROJECT"}:
        blockers.append("EXPIRY_REQUIRED_FOR_BOUNDED_RETENTION")

    conflict_refs = record.metadata.get("conflict_refs")
    if conflict_refs not in (None, [], ()):
        if not isinstance(conflict_refs, (list, tuple)):
            blockers.append("CONFLICT_METADATA_INVALID")
        elif any(_clean(x, 200) for x in conflict_refs):
            blockers.append("UNRESOLVED_CONFLICT_METADATA")

    if record.retention == "LEGAL_HOLD":
        retention_action = "LEGAL_HOLD"
    elif "MEMORY_EXPIRED" in blockers:
        retention_action = "EXPIRE_TO_AUDIT_TOMBSTONE"
    elif record.retention == "UNTIL_SUPERSEDED":
        retention_action = "KEEP_UNTIL_SUPERSEDED"
    else:
        retention_action = "KEEP"

    unique = list(dict.fromkeys(blockers))
    allowed = not unique and base.get("allowed_for_operational_use") is True
    return {
        "schema": MEMORY_SCHEMA,
        "state": "USABLE" if allowed else "BLOCKED",
        "memory_id": record.memory_id,
        "record_digest": memory_contract_digest(record),
        "validation_state": record.validation_state,
        "retention": record.retention,
        "sensitivity": record.sensitivity,
        "version": record.version,
        "trusted_tenant_id": tenant,
        "trusted_persona_id": persona,
        "scoped_tenant_id": scoped_tenant,
        "scoped_persona_id": scoped_persona,
        "confidence_pct": confidence,
        "minimum_confidence_pct": threshold,
        "valid_from": _clean(valid_from_raw, 80),
        "expires_at": _clean(expires_raw, 80),
        "retention_action": retention_action,
        "allowed_for_operational_use": allowed,
        "blockers": unique,
        "grants_permission": False,
        "grants_authority": False,
        "changes_policy": False,
        "execution_allowed": False,
        "external_action_executed": False,
        "deletes_history": False,
        "executes_action": False,
    }


def build_expiry_tombstone(
    record: MemoryContractRecord,
    *,
    now_ts: str,
    reason: Any = "TTL_EXPIRED",
) -> dict[str, Any]:
    """Build, but do not persist, a versioned tombstone for an expired record."""
    if not isinstance(record, MemoryContractRecord):
        raise TypeError("trusted MemoryContractRecord required")
    if record.retention == "LEGAL_HOLD":
        raise ValueError("LEGAL_HOLD memory cannot be expiry-tombstoned")

    now = _parse_ts(now_ts)
    expires_raw = record.metadata.get("expires_at")
    if not expires_raw:
        raise ValueError("expires_at required for expiry tombstone")
    expires = _parse_ts(expires_raw)
    if now < expires:
        raise ValueError("memory has not expired")

    tombstone = create_memory_record(
        namespace=record.namespace,
        memory_class=record.memory_class,
        content="",
        scope=record.scope,
        provenance_ids=record.provenance_ids,
        version=record.version + 1,
        previous_version=record.memory_id,
        evidence_refs=record.evidence_refs,
        validation_state="OUTDATED",
        retention=record.retention,
        sensitivity=record.sensitivity,
        rollback_pointer=record.memory_id,
        tombstone=True,
        created_at=now_ts,
        metadata={
            "tombstone_of": record.memory_id,
            "expired_at": now_ts,
            "expiry_reason": _clean(reason, 240) or "TTL_EXPIRED",
            "previous_digest": memory_contract_digest(record),
            "audit_history_preserved": "true",
        },
    )
    return {
        "schema": TOMBSTONE_SCHEMA,
        "state": "TOMBSTONE_PREPARED",
        "original_memory_id": record.memory_id,
        "original_digest": memory_contract_digest(record),
        "tombstone": tombstone.as_dict(),
        "deletes_original": False,
        "audit_history_preserved": True,
        "automatic_persist": False,
        "automatic_delete": False,
        "execution_allowed": False,
        "executes_action": False,
    }


__all__ = [
    "SCHEMA",
    "PLAN_SCHEMA",
    "MEMORY_SCHEMA",
    "TOMBSTONE_SCHEMA",
    "govern_multiagent_session",
    "govern_memory_use",
    "build_expiry_tombstone",
]
