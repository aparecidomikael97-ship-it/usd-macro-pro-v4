"""Shared Loop Governor bridge for scheduled AION worker batches.

Both session and global workers use this read-only preflight before claiming a
lease or executing due local work. It does not grant permission, execute tools,
persist checkpoints, or start workers.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping

from atlasquant_aion_core_voice_automation import CheckpointAutomationAdapter
from atlasquant_aion_loop_governor import govern_agent_plan


SCHEMA = "ATLASQUANT_AION_LOOP_GOVERNOR_BRIDGE_V1"


def govern_due_batch(
    context,
    checkpoint: Mapping[str, Any],
    *,
    current: datetime,
    max_jobs: int,
) -> dict[str, Any]:
    if type(max_jobs) is not int or max_jobs < 1:
        raise ValueError("invalid loop governor batch size")

    scheduler = CheckpointAutomationAdapter(context, checkpoint).snapshot(current)
    due = [
        row for row in list(scheduler.get("schedules") or [])
        if isinstance(row, Mapping) and row.get("due") is True
    ]
    due.sort(key=lambda row: (
        str(row.get("due_at") or ""),
        str(row.get("schedule_id") or ""),
    ))
    selected = due[:max_jobs]
    if not selected:
        return {
            "schema": SCHEMA,
            "state": "NOT_REQUIRED",
            "blockers": [],
            "due_count": 0,
            "selected_count": 0,
            "capabilities": [],
            "grants_permission": False,
            "executes_action": False,
            "starts_worker": False,
        }

    nodes = [{
        "node_id": "worker-batch",
        "parent_id": "",
        "tenant_id": context.tenant_id,
        "workspace_id": context.workspace_id,
        "guardian_risk": "READ",
        "impact": "LOW",
        "uncertainty_pct": 0,
        "reversible": False,
        "external_side_effects": False,
    }]
    capabilities = sorted({
        str(row.get("capability") or "").strip().upper()
        for row in selected
        if str(row.get("capability") or "").strip()
    })
    for capability in capabilities:
        nodes.append({
            "node_id": "cap-" + capability.lower().replace("_", "-"),
            "parent_id": "worker-batch",
            "tenant_id": context.tenant_id,
            "workspace_id": context.workspace_id,
            "guardian_risk": "DRAFT" if capability in {"VOICE", "CONTENT"} else "READ",
            "impact": "LOW",
            "uncertainty_pct": 0,
            "reversible": False,
            "external_side_effects": False,
        })

    decision = govern_agent_plan(
        nodes,
        trusted_context={
            "tenant_id": context.tenant_id,
            "workspace_id": context.workspace_id,
        },
        max_depth=2,
        max_fanout=8,
        max_nodes=16,
        call_limit=max_jobs,
        calls_used=0,
        token_limit=100000,
        tokens_used=0,
        wall_seconds_limit=300,
        wall_seconds_used=0,
        memory_mb_limit=1024,
        memory_mb_used=0,
    )
    decision = dict(decision)
    decision["schema"] = SCHEMA
    decision["due_count"] = len(due)
    decision["selected_count"] = len(selected)
    decision["capabilities"] = capabilities
    decision["grants_permission"] = False
    decision["executes_action"] = False
    decision["starts_worker"] = False
    return decision


__all__ = ["SCHEMA", "govern_due_batch"]
