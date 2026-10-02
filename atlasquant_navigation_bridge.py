"""Guided navigation bridge for AION critical-surface revalidation.

The bridge only stores and consumes explicit navigation requests. It does not
repair components, run deploys, alter market logic, widen permissions or enable
trading execution.
"""
from __future__ import annotations

from typing import Any, Mapping, MutableMapping

SCHEMA = "ATLASQUANT_GUIDED_REVALIDATION_V1"
_REQUEST_KEY = "atlasquant_guided_revalidation_request"
_ACTIVE_KEY = "atlasquant_guided_revalidation_active"
_RESULT_KEY = "atlasquant_guided_revalidation_result"

_TARGETS = {
    "home_radar": {
        "page": "🎯 Radar",
        "mode": "Iniciante",
        "label": "Radar principal",
    },
    "advanced_radar": {
        "page": "🎯 Radar",
        "mode": "Avançado",
        "label": "Radar avançado / Central Institucional",
    },
    "master_panel": {
        "page": "🧭 Painel mestre",
        "mode": "Avançado",
        "label": "Painel Mestre",
    },
}


def _clean(value: Any, limit: int = 120) -> str:
    return str(value or "").strip()[:limit]


def revalidation_target(surface: Any) -> dict[str, str]:
    key = _clean(surface, 80)
    target = _TARGETS.get(key)
    if target is None:
        raise ValueError(f"unknown AtlasQuant surface: {key}")
    return {
        "surface": key,
        "page": target["page"],
        "mode": target["mode"],
        "label": target["label"],
    }


def request_surface_revalidation(
    session_state: MutableMapping[str, Any],
    surface: Any,
    *,
    build_id: Any = "",
) -> dict[str, Any]:
    target = revalidation_target(surface)
    request = {
        "schema": SCHEMA,
        **target,
        "build_id": _clean(build_id, 80),
        "state": "REQUESTED",
        "explicit_user_action": True,
        "executes_action": False,
        "real_orders_enabled": False,
    }
    session_state[_REQUEST_KEY] = request
    return dict(request)


def consume_revalidation_request(
    session_state: MutableMapping[str, Any],
    *,
    available_pages: list[str] | tuple[str, ...],
) -> dict[str, Any] | None:
    raw = session_state.pop(_REQUEST_KEY, None)
    if not isinstance(raw, Mapping):
        return None

    surface = _clean(raw.get("surface"), 80)
    try:
        target = revalidation_target(surface)
    except ValueError:
        return None

    pages = [str(x) for x in list(available_pages or [])]
    if target["page"] not in pages:
        result = {
            "schema": SCHEMA,
            **target,
            "build_id": _clean(raw.get("build_id"), 80),
            "state": "NAVIGATION_BLOCKED",
            "reason": "TARGET_PAGE_UNAVAILABLE",
            "executes_action": False,
            "real_orders_enabled": False,
        }
        session_state[_RESULT_KEY] = result
        return dict(result)

    # This function must be called before the corresponding Streamlit widgets
    # are instantiated in the current rerun.
    session_state["atlasquant_experience_mode"] = target["mode"]
    if target["mode"] == "Avançado":
        session_state["atlasquant_advanced_area"] = target["page"]
    else:
        session_state["atlasquant_beginner_area_full"] = target["page"]
    # The fallback selector uses a separate stable key when atlasquant_ui_v1
    # cannot be imported. Setting it here keeps guided recovery available in
    # degraded presentation mode as well.
    session_state["atlasquant_stable_nav_fallback"] = target["page"]

    active = {
        "schema": SCHEMA,
        **target,
        "build_id": _clean(raw.get("build_id"), 80),
        "state": "NAVIGATED",
        "explicit_user_action": True,
        "executes_action": False,
        "real_orders_enabled": False,
    }
    session_state[_ACTIVE_KEY] = active
    return dict(active)


def active_revalidation(
    session_state: Mapping[str, Any] | None,
) -> dict[str, Any] | None:
    raw = (session_state or {}).get(_ACTIVE_KEY)
    return dict(raw) if isinstance(raw, Mapping) else None


def complete_surface_revalidation(
    session_state: MutableMapping[str, Any],
    surface: Any,
    *,
    build_id: Any,
    succeeded: bool,
    error_type: Any = "",
) -> dict[str, Any] | None:
    active = active_revalidation(session_state)
    if not active:
        return None

    target = revalidation_target(surface)
    if target["surface"] != _clean(active.get("surface"), 80):
        return None

    expected_build = _clean(active.get("build_id"), 80)
    observed_build = _clean(build_id, 80)
    build_matches = bool(expected_build and observed_build and expected_build == observed_build)

    state = "CONFIRMED_OK" if succeeded and build_matches else (
        "BUILD_CHANGED" if not build_matches else "CONFIRMED_ERROR"
    )
    result = {
        "schema": SCHEMA,
        **target,
        "requested_build": expected_build,
        "observed_build": observed_build,
        "build_matches": build_matches,
        "state": state,
        "error_type": _clean(error_type, 120),
        "executes_action": False,
        "real_orders_enabled": False,
    }
    session_state[_RESULT_KEY] = result
    session_state.pop(_ACTIVE_KEY, None)
    return dict(result)


def revalidation_result(
    session_state: Mapping[str, Any] | None,
) -> dict[str, Any] | None:
    raw = (session_state or {}).get(_RESULT_KEY)
    return dict(raw) if isinstance(raw, Mapping) else None


def request_investments_page(
    session_state: MutableMapping[str, Any],
) -> dict[str, Any]:
    """Open the existing Investments page in the current authenticated session.

    Navigation only. The current experience mode is preserved when possible;
    no investment order, transfer, subscription or paid action is executed.
    """
    current_mode = str(session_state.get("atlasquant_experience_mode") or "").strip()
    mode = "Avançado" if current_mode.casefold().startswith("avan") else "Iniciante"
    request = {
        "schema": SCHEMA,
        "surface": "investments",
        "page": "💰 Investir",
        "mode": mode,
        "label": "Renda Fixa / Investimentos",
        "build_id": "",
        "state": "INVESTMENTS_PAGE_REQUESTED",
        "explicit_user_action": True,
        "executes_action": False,
        "real_orders_enabled": False,
    }
    session_state[_REQUEST_KEY] = request
    return dict(request)


def request_return_to_aion(
    session_state: MutableMapping[str, Any],
) -> dict[str, Any]:
    request = {
        "schema": SCHEMA,
        "surface": "aion",
        "page": "🧠 AION",
        "mode": "Avançado",
        "label": "Central AION",
        "build_id": "",
        "state": "RETURN_REQUESTED",
        "explicit_user_action": True,
        "executes_action": False,
        "real_orders_enabled": False,
    }
    session_state[_REQUEST_KEY] = request
    return dict(request)


_AION_WORKSPACE_JUMP_KEY = "aion_admin_workspace_jump"


def request_business_workspace(
    session_state: MutableMapping[str, Any],
) -> dict[str, Any]:
    """Open the existing AION Business workspace in the current session.

    This is navigation only. It does not create a second Business engine,
    persist data, publish listings, spend money, or widen permissions.
    """
    session_state[_AION_WORKSPACE_JUMP_KEY] = "💼 Negócios"
    request = request_return_to_aion(session_state)
    return {
        **request,
        "workspace": "💼 Negócios",
        "state": "BUSINESS_WORKSPACE_REQUESTED",
    }


def consume_navigation_request(
    session_state: MutableMapping[str, Any],
    *,
    available_pages: list[str] | tuple[str, ...],
) -> dict[str, Any] | None:
    raw = session_state.get(_REQUEST_KEY)
    if isinstance(raw, Mapping) and str(raw.get("surface") or "") == "aion":
        session_state.pop(_REQUEST_KEY, None)
        pages = [str(x) for x in list(available_pages or [])]
        if "🧠 AION" not in pages:
            return None
        session_state["atlasquant_experience_mode"] = "Avançado"
        session_state["atlasquant_advanced_area"] = "🧠 AION"
        session_state["atlasquant_stable_nav_fallback"] = "🧠 AION"
        return dict(raw)
    if isinstance(raw, Mapping) and str(raw.get("surface") or "") == "investments":
        session_state.pop(_REQUEST_KEY, None)
        pages = [str(x) for x in list(available_pages or [])]
        page = "💰 Investir"
        if page not in pages:
            return {
                **dict(raw),
                "state": "NAVIGATION_BLOCKED",
                "reason": "TARGET_PAGE_UNAVAILABLE",
            }
        mode = "Avançado" if str(raw.get("mode") or "").casefold().startswith("avan") else "Iniciante"
        session_state["atlasquant_experience_mode"] = mode
        if mode == "Avançado":
            session_state["atlasquant_advanced_area"] = page
        else:
            session_state["atlasquant_beginner_area_full"] = page
            # The authenticated fast-start shell owns a separate radio key.
            # Keep it synchronized so Central -> Investimentos reaches the
            # existing fast 💰 Investir surface instead of falling back to Radar.
            session_state["aq_beginner_page"] = page
        session_state["atlasquant_stable_nav_fallback"] = page
        return dict(raw)
    return consume_revalidation_request(
        session_state,
        available_pages=available_pages,
    )


__all__ = [
    "SCHEMA",
    "revalidation_target",
    "request_surface_revalidation",
    "consume_revalidation_request",
    "consume_navigation_request",
    "active_revalidation",
    "complete_surface_revalidation",
    "revalidation_result",
    "request_return_to_aion",
    "request_investments_page",
    "request_business_workspace",
]
