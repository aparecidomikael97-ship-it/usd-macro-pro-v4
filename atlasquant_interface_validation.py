"""Build-scoped interface validation mission for AtlasQuant/AION.

Summarizes the three critical presentation surfaces using already-observed
runtime evidence. It never probes production, repairs components, changes
permissions, deploys code or enables trading.
"""
from __future__ import annotations

from typing import Any, Mapping

SCHEMA = "ATLASQUANT_INTERFACE_VALIDATION_MISSION_V1"

ORDER = ("home_radar", "master_panel", "advanced_radar")


def _clean(value: Any, limit: int = 180) -> str:
    return str(value or "").strip()[:limit]


def interface_validation_mission(
    critical_surfaces: Mapping[str, Any] | None,
) -> dict[str, Any]:
    snapshot = dict(critical_surfaces or {})
    build_id = _clean(snapshot.get("current_build"), 80)
    raw_items = [
        dict(x) for x in list(snapshot.get("items", []) or [])
        if isinstance(x, Mapping)
    ]
    by_id = {_clean(x.get("id"), 80): x for x in raw_items}

    rows: list[dict[str, Any]] = []
    counts = {
        "OK": 0,
        "DEGRADED": 0,
        "UNAVAILABLE": 0,
        "STALE_BUILD": 0,
        "UNKNOWN": 0,
    }

    for surface in ORDER:
        item = by_id.get(surface, {})
        state = _clean(item.get("state"), 40).upper() or "UNKNOWN"
        if state not in counts:
            state = "UNKNOWN"

        observed_build = _clean(item.get("build_id"), 80)
        build_matches = bool(
            build_id
            and observed_build
            and observed_build == build_id
            and state == "OK"
        )
        # Even if an upstream caller accidentally reports OK from another build,
        # this mission refuses to count it as current-build evidence.
        effective_state = state
        if state == "OK" and build_id and observed_build != build_id:
            effective_state = "STALE_BUILD"
        counts[effective_state] += 1

        rows.append({
            "surface": surface,
            "label": _clean(item.get("label") or surface),
            "state": effective_state,
            "observed_build": observed_build,
            "current_build": build_id,
            "build_matches": bool(
                build_id and observed_build and observed_build == build_id
            ),
            "confirmed_current_build": bool(
                effective_state == "OK" and build_matches
            ),
            "next_action": _clean(
                item.get("next_action")
                or "Revalidar esta tela no build atual pelo fluxo guiado do AION.",
                500,
            ),
        })

    confirmed = sum(1 for row in rows if row["confirmed_current_build"])
    failed = sum(
        1 for row in rows
        if row["state"] in {"DEGRADED", "UNAVAILABLE"}
    )
    stale = sum(1 for row in rows if row["state"] == "STALE_BUILD")
    unknown = sum(1 for row in rows if row["state"] == "UNKNOWN")
    total = len(ORDER)
    remaining = total - confirmed

    if not build_id:
        state = "UNKNOWN"
        truth_state = "UNKNOWN"
    elif failed:
        state = "ATTENTION"
        truth_state = "CONFIRMED"
    elif confirmed == total:
        state = "COMPLETE"
        truth_state = "CONFIRMED"
    elif confirmed:
        state = "IN_PROGRESS"
        truth_state = "CONFIRMED"
    else:
        state = "NOT_STARTED"
        truth_state = "CONFIRMED"

    next_row = next(
        (row for row in rows if not row["confirmed_current_build"]),
        None,
    )
    progress_pct = round((confirmed / total) * 100.0, 1) if total else 0.0

    return {
        "schema": SCHEMA,
        "state": state,
        "truth_state": truth_state,
        "build_id": build_id,
        "total": total,
        "confirmed": confirmed,
        "remaining": remaining,
        "failed": failed,
        "stale": stale,
        "unknown": unknown,
        "progress_pct": progress_pct,
        "rows": rows,
        "next_surface": str((next_row or {}).get("surface") or ""),
        "next_label": str((next_row or {}).get("label") or ""),
        "next_action": str((next_row or {}).get("next_action") or ""),
        "all_confirmed_current_build": bool(
            build_id and confirmed == total
        ),
        "executes_action": False,
        "automatic_repair": False,
        "automatic_deploy": False,
        "real_orders_enabled": False,
    }


__all__ = ["SCHEMA", "ORDER", "interface_validation_mission"]
