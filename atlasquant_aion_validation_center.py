"""Deterministic AION validation-center contract.

This module summarizes evidence already present in the current AtlasQuant
session. It never deploys, repairs, authorizes trading, or infers production
health from local/session evidence.
"""
from __future__ import annotations

from typing import Any, Mapping

SCHEMA = "ATLASQUANT_AION_VALIDATION_CENTER_V1"

_SURFACE_ORDER = (
    ("home_radar", "Radar principal"),
    ("advanced_radar", "Radar avançado / Central Institucional"),
    ("master_panel", "Painel Mestre"),
)


def _clean(value: Any, limit: int = 160) -> str:
    return str(value or "").strip()[:limit]


def _surface_map(snapshot: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    out: dict[str, Mapping[str, Any]] = {}
    for item in list(snapshot.get("items", []) or []):
        if isinstance(item, Mapping):
            key = _clean(item.get("id"), 80)
            if key:
                out[key] = item
    return out


def validation_center_snapshot(
    system_context: Mapping[str, Any] | None,
    *,
    runtime_status: Any = "UNKNOWN",
) -> dict[str, Any]:
    system = dict(system_context or {})
    current_build = _clean(system.get("source_build"), 80)
    truth_state = _clean(system.get("truth_state"), 40).upper() or "UNKNOWN"
    critical = (
        dict(system.get("critical_surfaces") or {})
        if isinstance(system.get("critical_surfaces"), Mapping)
        else {}
    )
    surfaces = _surface_map(critical)

    rows: list[dict[str, Any]] = []
    confirmed_surfaces = 0
    for surface_id, label in _SURFACE_ORDER:
        item = surfaces.get(surface_id, {})
        state = _clean(item.get("state"), 40).upper() or "UNKNOWN"
        observed_build = _clean(item.get("build_id"), 80)
        build_matches = bool(
            current_build
            and observed_build
            and observed_build == current_build
            and bool(item.get("build_matches", False))
        )
        confirmed = bool(state == "OK" and build_matches)
        if confirmed:
            confirmed_surfaces += 1
        rows.append({
            "id": surface_id,
            "label": label,
            "state": "CONFIRMED" if confirmed else state,
            "observed_build": observed_build,
            "current_build": current_build,
            "confirmed_current_build": confirmed,
            "next_action": _clean(
                item.get("next_action")
                or f"Abrir {label} no build atual para produzir evidência.",
                300,
            ),
        })

    build_confirmed = bool(current_build and truth_state == "CONFIRMED")
    runtime = _clean(runtime_status, 60).upper() or "UNKNOWN"
    runtime_confirmed = runtime == "CONFIRMED"
    all_critical_confirmed = confirmed_surfaces == len(_SURFACE_ORDER)

    local_session_validated = bool(build_confirmed and all_critical_confirmed)

    production = (
        dict(system.get("production_validation") or {})
        if isinstance(system.get("production_validation"), Mapping)
        else {}
    )
    production_build = _clean(production.get("build_id"), 80)
    production_state = _clean(production.get("state"), 60).upper() or "UNKNOWN"
    production_confirmed = bool(
        production_state == "CONFIRMED"
        and current_build
        and production_build == current_build
    )

    if local_session_validated:
        local_state = "LOCAL_SESSION_VALIDATED"
    elif not build_confirmed:
        local_state = "BUILD_UNCONFIRMED"
    else:
        local_state = "LOCAL_SESSION_INCOMPLETE"

    next_actions: list[str] = []
    for row in rows:
        if not row["confirmed_current_build"]:
            next_actions.append(row["next_action"])
    if not runtime_confirmed:
        next_actions.append(
            "Confirmar o estado do runtime/Checkpoint antes de tratar a memória operacional como validada."
        )
    if not production_confirmed:
        next_actions.append(
            "Validar o deploy de produção separadamente; evidência local não confirma o ambiente publicado."
        )

    return {
        "schema": SCHEMA,
        "current_build": current_build,
        "build_confirmed": build_confirmed,
        "runtime_status": runtime,
        "runtime_confirmed": runtime_confirmed,
        "critical_confirmed": confirmed_surfaces,
        "critical_total": len(_SURFACE_ORDER),
        "critical_all_confirmed": all_critical_confirmed,
        "local_state": local_state,
        "local_session_validated": local_session_validated,
        "production_state": (
            "CONFIRMED_CURRENT_BUILD" if production_confirmed else "NOT_CONFIRMED"
        ),
        "production_confirmed": production_confirmed,
        "production_build": production_build,
        "rows": rows,
        "next_actions": next_actions,
        "deploy_allowed": False,
        "executes_action": False,
        "real_orders_enabled": False,
    }


def validation_center_rows(snapshot: Mapping[str, Any] | None) -> list[dict[str, str]]:
    snap = dict(snapshot or {})
    rows: list[dict[str, str]] = []
    for item in list(snap.get("rows", []) or []):
        if not isinstance(item, Mapping):
            continue
        rows.append({
            "Evidência": _clean(item.get("label"), 120),
            "Estado": _clean(item.get("state"), 60) or "UNKNOWN",
            "Build observado": _clean(item.get("observed_build"), 80) or "—",
            "Build atual": _clean(item.get("current_build"), 80) or "—",
            "Próxima ação": _clean(item.get("next_action"), 300),
        })
    return rows


__all__ = [
    "SCHEMA",
    "validation_center_snapshot",
    "validation_center_rows",
]
