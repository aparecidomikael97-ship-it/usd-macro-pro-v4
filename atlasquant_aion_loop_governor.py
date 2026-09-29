"""Multi-agent loop and budget gate.

Reuses `autonomy_budget` and `resource_governor`. It does not start a worker,
grant permission, or execute a step. Depth, fan-out and shared resource
pressure stop the plan before any agent runs.
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence

from atlasquant_aion_fortress import autonomy_budget
from atlasquant_aion_resilience import resource_governor

SCHEMA = "ATLASQUANT_AION_LOOP_GOVERNOR_V1"
DEPTH_CEILING = 4
FANOUT_CEILING = 8
NODE_CEILING = 32


def _clean(value: Any, limit: int = 120) -> str:
    return " ".join(str(value or "").replace("\x00", "").split())[:limit]


def _limit(value: Any, default: int, ceiling: int) -> tuple[int | None, bool]:
    if value is None:
        return default, False
    if isinstance(value, bool) or not isinstance(value, int):
        return None, False
    if value < 1:
        return None, False
    if value > ceiling:
        return ceiling, True
    return value, False


def _metric(value: Any) -> float | None:
    if value is None:
        return 0.0
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def govern_agent_plan(
    nodes: Sequence[Mapping[str, Any]] | None,
    *,
    trusted_context: Mapping[str, Any] | None,
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
    trusted = dict(trusted_context or {})
    tenant = _clean(trusted.get("tenant_id"), 80)
    workspace = _clean(trusted.get("workspace_id"), 80)
    depth_limit, depth_clamped = _limit(max_depth, 3, DEPTH_CEILING)
    fanout_limit, fanout_clamped = _limit(max_fanout, 4, FANOUT_CEILING)
    node_limit, node_clamped = _limit(max_nodes, 16, NODE_CEILING)
    metrics = {
        "call_limit": _metric(call_limit),
        "calls_used": _metric(calls_used),
        "token_limit": _metric(token_limit),
        "tokens_used": _metric(tokens_used),
        "wall_seconds_limit": _metric(wall_seconds_limit),
        "wall_seconds_used": _metric(wall_seconds_used),
        "memory_mb_limit": _metric(memory_mb_limit),
        "memory_mb_used": _metric(memory_mb_used),
    }
    blockers: list[str] = []
    if not tenant or not workspace:
        blockers.append("SCOPE_REQUIRED")
    if depth_limit is None or fanout_limit is None or node_limit is None:
        blockers.append("LIMIT_INVALID")
    if any(item is None for item in metrics.values()):
        blockers.append("RESOURCE_INVALID")
    rows = [dict(item) for item in list(nodes or []) if isinstance(item, Mapping)]
    if len(list(nodes or [])) != len(rows):
        blockers.append("NODE_INVALID")
    if not rows:
        blockers.append("PLAN_EMPTY")
    if node_limit is not None and len(rows) > node_limit:
        blockers.append("NODE_LIMIT")

    by_id: dict[str, Mapping[str, Any]] = {}
    children: dict[str, list[str]] = {}
    roots: list[str] = []
    for row in rows:
        node_id = _clean(row.get("node_id"), 80)
        parent_id = _clean(row.get("parent_id"), 80)
        if not node_id or node_id in by_id:
            blockers.append("DUPLICATE_OR_EMPTY_ID")
            continue
        claimed_tenant = _clean(row.get("tenant_id"), 80)
        claimed_workspace = _clean(row.get("workspace_id"), 80)
        if (claimed_tenant and claimed_tenant != tenant) or (claimed_workspace and claimed_workspace != workspace):
            blockers.append("SCOPE_MISMATCH")
        by_id[node_id] = row
        if parent_id == node_id:
            blockers.append("CYCLE")
        if parent_id:
            children.setdefault(parent_id, []).append(node_id)
        else:
            roots.append(node_id)

    if len(roots) != 1 and rows:
        blockers.append("ROOT_INVALID")
    for parent_id, kids in children.items():
        if parent_id not in by_id:
            blockers.append("DANGLING_PARENT")
        if fanout_limit is not None and len(kids) > fanout_limit:
            blockers.append("FANOUT_LIMIT")

    parent_of = {node_id: _clean(row.get("parent_id"), 80) for node_id, row in by_id.items()}
    if "DUPLICATE_OR_EMPTY_ID" not in blockers:
        for node_id in by_id:
            seen: list[str] = []
            current = node_id
            cycle = False
            while True:
                if current in seen:
                    cycle = True
                    break
                seen.append(current)
                parent = parent_of.get(current, "")
                if not parent or parent not in by_id:
                    break
                current = parent
            if cycle:
                blockers.append("CYCLE")
                if not roots or roots[0] not in seen:
                    blockers.append("UNREACHABLE_NODE")
                continue
            if roots and seen[-1] != roots[0]:
                blockers.append("UNREACHABLE_NODE")
            elif depth_limit is not None and len(seen) > depth_limit:
                blockers.append("DEPTH_LIMIT")

    budgets = []
    if not blockers:
        for node_id, row in by_id.items():
            budget = autonomy_budget(
                guardian_risk=row.get("guardian_risk"),
                uncertainty_pct=row.get("uncertainty_pct", 100),
                impact=row.get("impact", "MEDIUM"),
                reversible=row.get("reversible", False),
                external_side_effects=row.get("external_side_effects", False),
            )
            budgets.append({"node_id": node_id, "mode": budget["mode"], "grants_permission": False})
            if budget["mode"] in {"BLOCKED", "ADMIN_REQUIRED"}:
                blockers.append(f"AUTONOMY_{budget['mode']}")

    resources = None
    if "RESOURCE_INVALID" not in blockers:
        resources = resource_governor(
            "multi_agent_plan",
            call_limit=metrics["call_limit"],
            calls_used=metrics["calls_used"],
            token_limit=metrics["token_limit"],
            tokens_used=metrics["tokens_used"],
            wall_seconds_limit=metrics["wall_seconds_limit"],
            wall_seconds_used=metrics["wall_seconds_used"],
            memory_mb_limit=metrics["memory_mb_limit"],
            memory_mb_used=metrics["memory_mb_used"],
        )
        if resources.get("allow_new_sensitive_work") is not True:
            blockers.append("RESOURCE_BUDGET")

    unique_blockers = list(dict.fromkeys(blockers))
    return {
        "schema": SCHEMA,
        "state": "WITHIN_LIMITS" if not unique_blockers else "BLOCK",
        "blockers": unique_blockers,
        "tenant_id": tenant,
        "workspace_id": workspace,
        "node_count": len(rows),
        "max_depth": depth_limit,
        "max_fanout": fanout_limit,
        "max_nodes": node_limit,
        "limits_clamped": bool(depth_clamped or fanout_clamped or node_clamped),
        "node_budgets": budgets,
        "resource_governor": resources,
        "grants_permission": False,
        "executes_action": False,
        "starts_worker": False,
    }
