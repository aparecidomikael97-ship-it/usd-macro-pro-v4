"""AION verified-owner entry and same-session navigation bridge, Draft V1.

Only an already trusted host may inject a verified HUMAN_OWNER assertion.
No owner identity is inferred from ADMIN, a display name or a wake word.
This module does not verify cryptographic evidence itself: trusted_host_owner
is a host-origin trust boundary, NOT an authentication credential.
No external app, microphone, provider, file mutation or paid action.
"""
from __future__ import annotations

from datetime import datetime
import re
from typing import Any, Mapping, MutableMapping

from atlasquant_aion_owner_experience_v1 import (
    command_plan,
    owner_binding,
    owner_greeting_plan,
)

SCHEMA = "ATLASQUANT_AION_OWNER_HOST_ENTRY_NAVIGATION_BRIDGE_V1"
# Explicit single-command grammar; compound or ambiguous instructions fail closed.
_NAVIGATION = re.compile(
    r"(?:aion[\s,]+)?(?:abre|abrir|entra|entrar|vai|ir)\s+"
    r"(?:(?:a aba|a|o|na|no|para|pra)\s+)?"
    r"(?P<target>atlasquant|trader|negocios|negócios|investimentos|aion)"
    r"\s*\Z", re.IGNORECASE,
)
_TARGETS = {
    "atlasquant": "central",
    "trader": "trader",
    "negocios": "negocios",
    "negócios": "negocios",
    "investimentos": "investimentos",
    "aion": "aion",
}


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "state": "BLOCKED",
        "reason": reason,
        "owner_ready": False,
        "navigation_requested": False,
        "external_action_authorized": False,
        "execution_confirmed": False,
        "executes_external_action": False,
    }


def prepare_owner_host_entry(
    access: Mapping[str, Any] | None,
    owner_assertion: Mapping[str, Any] | None,
    *,
    trusted_host_owner: bool = False,
    now: datetime | None = None,
    timezone_name: str | None = None,
) -> dict[str, Any]:
    """Safe welcome plan visible only after trusted host and owner binding."""
    if trusted_host_owner is not True:
        return _blocked("TRUSTED_OWNER_HOST_REQUIRED")
    plan = owner_greeting_plan(
        access, owner_assertion, now=now, timezone_name=timezone_name,
        display_name="Mikael",
    )
    if plan.get("state") != "READY" or plan.get("binding", {}).get("bound") is not True:
        return _blocked("HUMAN_OWNER_BINDING_REQUIRED")
    return {
        "schema": SCHEMA,
        "state": "OWNER_ENTRY_READY",
        "reason": "",
        "owner_ready": True,
        "greeting_text": plan["text"],
        "period": plan["period"],
        "binding_digest": plan["binding"]["binding_digest"],
        "greeting_display_only": True,
        "greeting_spoken": False,
        "microphone_active": False,
        "navigation_requested": False,
        "external_action_authorized": False,
        "execution_confirmed": False,
        "executes_external_action": False,
    }


def route_owner_text_navigation(
    session_state: MutableMapping[str, Any],
    access: Mapping[str, Any] | None,
    owner_assertion: Mapping[str, Any] | None,
    *,
    trusted_host_owner: bool = False,
    text: str,
    device: str,
) -> dict[str, Any]:
    """Queue ONLY internal same-session routes; never assume the page opened.

    Call only after a fresh user command received by the trusted host.
    UI input, a cookie or a client-declared 'verified' flag may not set
    trusted_host_owner. External application commands are not dispatched.
    """
    if trusted_host_owner is not True:
        return _blocked("TRUSTED_OWNER_HOST_REQUIRED")
    binding = owner_binding(access, owner_assertion)
    if binding["bound"] is not True:
        return _blocked("HUMAN_OWNER_BINDING_REQUIRED")
    if not isinstance(session_state, MutableMapping):
        return _blocked("TRUSTED_SESSION_STATE_REQUIRED")
    if type(text) is not str or not 1 <= len(text) <= 160:
        return _blocked("FRESH_SINGLE_TEXT_COMMAND_REQUIRED")
    if type(device) is not str or device.upper() not in {"DESKTOP", "MOBILE"}:
        return _blocked("SUPPORTED_DEVICE_REQUIRED")
    normalized = " ".join(text.casefold().strip().split())
    match = _NAVIGATION.fullmatch(normalized)
    if match is None:
        # This is intentionally NOT a generic tool dispatch route.
        return _blocked("INTERNAL_SINGLE_NAVIGATION_ONLY")
    target = _TARGETS[match.group("target")]
    plan = command_plan(text, device=device.upper(), owner_bound=True)
    if not (
        plan.get("state") == "PLANNED"
        and plan.get("kind") == "ATLASQUANT_NAVIGATION"
        and plan.get("target") == target
        and plan.get("adapter_required") == "TRUSTED_HOST_NAVIGATION"
    ):
        return _blocked("OWNER_COMMAND_PLAN_MISMATCH")
    # Import late so the central host can depend on this bridge without cycles.
    from atlasquant_central_hub_ui import request_central_destination
    try:
        request_central_destination(session_state, access, target)
    except (KeyError, TypeError, ValueError):
        return _blocked("CENTRAL_NAVIGATION_REJECTED")
    return {
        "schema": SCHEMA,
        "state": "INTERNAL_NAVIGATION_REQUESTED",
        "reason": "",
        "owner_ready": True,
        "target": target,
        "navigation_requested": True,
        "navigation_confirmed": False,  # host must observe actual UI transition
        "external_action_authorized": False,
        "execution_confirmed": False,
        "executes_external_action": False,
        "auto_retry": False,
    }


__all__ = ["SCHEMA", "prepare_owner_host_entry", "route_owner_text_navigation"]
