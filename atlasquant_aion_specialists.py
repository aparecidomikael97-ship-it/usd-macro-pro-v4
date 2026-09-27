"""Specialist dispatch contracts for the AION orchestrator.

Specialists share the Capability Registry and existing AtlasQuant modules.
Dispatch is planning-only and falls back to safe local explanation when a
provider/tool is unavailable.
"""
from __future__ import annotations

from typing import Any, Mapping

from atlasquant_aion_capabilities import CapabilityRegistry, default_registry
from atlasquant_aion_ecosystem import specialist_modules

SCHEMA = "ATLASQUANT_AION_SPECIALISTS_V1"

# Generated from the canonical ecosystem registry. Dispatch still does not execute tools.
SPECIALIST_MODULES = specialist_modules()


def specialist_catalog(registry: CapabilityRegistry | None = None) -> dict[str, Any]:
    reg = registry or default_registry()
    rows: dict[str, dict[str, Any]] = {}
    for capability in reg.list():
        specialist = capability.specialist
        row = rows.setdefault(specialist, {
            "specialist": specialist,
            "module": SPECIALIST_MODULES.get(specialist, ""),
            "capabilities": [],
            "shared_infrastructure": True,
            "independent_permissions": False,
        })
        row["capabilities"].append(capability.capability_id)
    return {
        "schema": SCHEMA,
        "specialists": [rows[key] for key in sorted(rows)],
        "specialist_count": len(rows),
        "duplicate_infrastructure_created": False,
        "executes_action": False,
    }


def plan_specialist_dispatch(
    orchestration: Mapping[str, Any] | None,
    *,
    runtime_availability: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    state = dict(orchestration or {})
    capability = (
        dict(state.get("selected_capability"))
        if isinstance(state.get("selected_capability"), Mapping)
        else {}
    )
    specialist = str(capability.get("specialist") or "")
    availability = dict(runtime_availability or {})
    module = SPECIALIST_MODULES.get(specialist, "")
    module_state = str(availability.get(specialist) or ("AVAILABLE" if module else "UNAVAILABLE")).upper()
    tools = [str(x) for x in list(capability.get("allowed_tools") or [])]
    unavailable_tools = [
        tool for tool in tools
        if str(availability.get(tool) or "AVAILABLE").upper() not in {"AVAILABLE", "READY", "LOCAL_READY"}
    ]
    blockers = []
    if not specialist or not module:
        blockers.append("SPECIALIST_NOT_REGISTERED")
    if module_state not in {"AVAILABLE", "READY", "LOCAL_READY"}:
        blockers.append("SPECIALIST_UNAVAILABLE")
    if unavailable_tools:
        blockers.append("TOOL_UNAVAILABLE")

    if blockers:
        dispatch_state = "DEGRADED_SAFE"
        fallback = {
            "id": "local.truthful_summary",
            "mode": "READ_ONLY",
            "reason": "Especialista/ferramenta indisponível; resumir somente evidência já presente.",
            "may_invent_missing_result": False,
        }
    else:
        dispatch_state = "READY"
        fallback = None
    return {
        "schema": SCHEMA,
        "state": dispatch_state,
        "specialist": specialist,
        "module": module,
        "capability_id": str(capability.get("capability_id") or ""),
        "tools": tools,
        "unavailable_tools": unavailable_tools,
        "blockers": blockers,
        "fallback": fallback,
        "provider_called": False,
        "tool_called": False,
        "permissions_expanded": False,
        "executes_action": False,
        "real_orders_enabled": False,
    }


__all__ = ["SCHEMA", "SPECIALIST_MODULES", "specialist_catalog", "plan_specialist_dispatch"]
