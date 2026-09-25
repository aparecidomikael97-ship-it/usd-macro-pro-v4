"""Critical AtlasQuant surface health contract.

Tracks only presentation/runtime availability for key UI surfaces. It does not
alter market scores, gates, authorizations, providers or trading execution.

V2 makes observations build-aware so a healthy result from an older source
bundle cannot be presented as proof that the current build rendered correctly.
"""
from __future__ import annotations

from typing import Any, Mapping, MutableMapping

SCHEMA = "ATLASQUANT_CRITICAL_SURFACE_HEALTH_V2"

SURFACES = {
    "home_radar": "Radar principal",
    "advanced_radar": "Radar avançado / Central Institucional",
    "master_panel": "Painel Mestre",
}

_STATE_KEY = "atlasquant_critical_surface_health"


def _safe_error_type(value: Any) -> str:
    if isinstance(value, BaseException):
        return type(value).__name__[:120]
    if isinstance(value, Mapping):
        value = value.get("error_type") or value.get("type") or value.get("reason")
    raw = str(value or "").strip()
    if not raw:
        return ""
    # Keep only the diagnostic class/code. Messages can contain provider,
    # path or credential-adjacent details that do not belong in the UI.
    return raw.split(":", 1)[0].strip()[:120]


def _clean_build_id(value: Any) -> str:
    return str(value or "").strip()[:80]


def _next_action(state: str, label: str) -> str:
    if state == "OK":
        return "Nenhuma ação imediata; manter validação normal do build."
    if state == "DEGRADED":
        return (
            f"Reabrir {label} no build atual. Se a falha repetir, revisar o erro isolado "
            "antes de qualquer validação de produção."
        )
    if state == "UNAVAILABLE":
        return (
            f"Revisar importação/empacotamento de {label} e confirmar que o módulo existe "
            "no build atual antes do deploy."
        )
    if state == "STALE_BUILD":
        return (
            f"Abrir {label} novamente no build atual para substituir a evidência de uma "
            "versão anterior."
        )
    return f"Abrir {label} uma vez neste build para produzir evidência de renderização."


def mark_surface_ok(
    session_state: MutableMapping[str, Any],
    surface: str,
    *,
    build_id: Any = "",
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
        "build_id": _clean_build_id(build_id),
    }
    session_state[_STATE_KEY] = current
    return dict(current[key])


def mark_surface_error(
    session_state: MutableMapping[str, Any],
    surface: str,
    error: Any,
    *,
    build_id: Any = "",
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
        "build_id": _clean_build_id(build_id),
    }
    session_state[_STATE_KEY] = current
    return dict(current[key])


def surface_health_snapshot(
    session_state: Mapping[str, Any] | None,
    *,
    current_build: Any = "",
) -> dict[str, Any]:
    source = dict((session_state or {}).get(_STATE_KEY, {}) or {})
    build_now = _clean_build_id(current_build)
    items: list[dict[str, Any]] = []
    counts = {
        "OK": 0,
        "DEGRADED": 0,
        "UNAVAILABLE": 0,
        "STALE_BUILD": 0,
        "UNKNOWN": 0,
    }
    for key, label in SURFACES.items():
        raw = source.get(key) if isinstance(source.get(key), Mapping) else {}
        observed = bool(raw)
        raw_state = str(raw.get("state") or "UNKNOWN").upper()
        if raw_state not in {"OK", "DEGRADED", "UNAVAILABLE"}:
            raw_state = "UNKNOWN"
        observed_build = _clean_build_id(raw.get("build_id"))

        state = raw_state
        stale_build = bool(
            observed
            and build_now
            and observed_build != build_now
        )
        if stale_build:
            state = "STALE_BUILD"

        if state not in counts:
            state = "UNKNOWN"

        if state == "STALE_BUILD":
            detail = "Evidência pertence a outro build; o estado atual ainda precisa ser observado."
            error_type = ""
        else:
            detail = str(raw.get("detail") or "Ainda não observado nesta sessão.")
            error_type = _safe_error_type(raw.get("error_type"))

        item = {
            "id": key,
            "label": label,
            "state": state,
            "detail": detail,
            "error_type": error_type,
            "build_id": observed_build,
            "current_build": build_now,
            "build_matches": bool(observed_build and build_now and observed_build == build_now),
            "next_action": _next_action(state, label),
            "executes_action": False,
            "real_orders_enabled": False,
        }
        counts[state] += 1
        items.append(item)

    unresolved = (
        counts["DEGRADED"]
        + counts["UNAVAILABLE"]
        + counts["STALE_BUILD"]
        + counts["UNKNOWN"]
    )
    return {
        "schema": SCHEMA,
        "current_build": build_now,
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
