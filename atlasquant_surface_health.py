"""Critical AtlasQuant surface health contract.

Tracks only presentation/runtime availability for key UI surfaces. It does not
alter market scores, gates, authorizations, providers or trading execution.
"""
from __future__ import annotations

from typing import Any, Mapping, MutableMapping

SCHEMA = "ATLASQUANT_CRITICAL_SURFACE_HEALTH_V1"

SURFACES = {
    "home_radar": "Radar principal",
    "advanced_radar": "Radar avançado / Central Institucional",
    "master_panel": "Painel Mestre",
}

_STATE_KEY = "atlasquant_critical_surface_health"


def _safe_error_type(value: Any) -> str:
    if isinstance(value, Mapping):
        value = value.get("error_type") or value.get("type") or value.get("reason")
    raw = str(value or "").strip()
    return raw[:120] if raw else ""


def mark_surface_ok(
    session_state: MutableMapping[str, Any],
    surface: str,
    *,
    detail: str = "Renderização concluída nesta sessão.",
) -> dict[str, Any]:
    key = str(surface or "").strip()
    if key not in SURFACES:
        raise ValueError(f"unknown AtlasQuant surface: {key}")
    current = dict(session_state.get(_STATE_KEY, {}) or {})
    current[key] = {
        "state": "OK",
        "label": SURFACES[key],
        "detail": str(detail or "Renderização concluída nesta sessão."),
        "error_type": "",
    }
    session_state[_STATE_KEY] = current
    return dict(current[key])


def mark_surface_error(
    session_state: MutableMapping[str, Any],
    surface: str,
    error: Any,
    *,
    unavailable: bool = False,
    detail: str = "",
) -> dict[str, Any]:
    key = str(surface or "").strip()
    if key not in SURFACES:
        raise ValueError(f"unknown AtlasQuant surface: {key}")
    error_type = _safe_error_type(error) or "UNKNOWN"
    current = dict(session_state.get(_STATE_KEY, {}) or {})
    current[key] = {
        "state": "UNAVAILABLE" if unavailable else "DEGRADED",
        "label": SURFACES[key],
        "detail": str(
            detail
            or (
                "Componente indisponível neste carregamento."
                if unavailable
                else "Falha isolada nesta sessão; demais áreas permanecem disponíveis."
            )
        ),
        "error_type": error_type,
    }
    session_state[_STATE_KEY] = current
    return dict(current[key])


def surface_health_snapshot(
    session_state: Mapping[str, Any] | None,
) -> dict[str, Any]:
    source = dict((session_state or {}).get(_STATE_KEY, {}) or {})
    items: list[dict[str, Any]] = []
    counts = {"OK": 0, "DEGRADED": 0, "UNAVAILABLE": 0, "UNKNOWN": 0}
    for key, label in SURFACES.items():
        raw = source.get(key) if isinstance(source.get(key), Mapping) else {}
        state = str(raw.get("state") or "UNKNOWN").upper()
        if state not in counts:
            state = "UNKNOWN"
        item = {
            "id": key,
            "label": label,
            "state": state,
            "detail": str(raw.get("detail") or "Ainda não observado nesta sessão."),
            "error_type": _safe_error_type(raw.get("error_type")),
            "executes_action": False,
            "real_orders_enabled": False,
        }
        counts[state] += 1
        items.append(item)
    unresolved = counts["DEGRADED"] + counts["UNAVAILABLE"] + counts["UNKNOWN"]
    return {
        "schema": SCHEMA,
        "items": items,
        "counts": counts,
        "all_ok": unresolved == 0,
        "has_unresolved": unresolved > 0,
        "executes_action": False,
        "real_orders_enabled": False,
    }


__all__ = [
    "SCHEMA",
    "SURFACES",
    "mark_surface_ok",
    "mark_surface_error",
    "surface_health_snapshot",
]
