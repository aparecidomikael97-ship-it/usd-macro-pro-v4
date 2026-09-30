"""Deterministic specialist selection for the single AION nucleus.

The router chooses a registered domain profile. It does not execute a tool,
call a provider, widen a parent role, or turn a future runtime capability on.
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence

from atlasquant_aion_capabilities import default_registry
from atlasquant_aion_core_intelligence.registry import Registry
from atlasquant_aion_ecosystem import ecosystem_capabilities, specialist_modules

SCHEMA = "ATLASQUANT_AION_SPECIALIST_ROUTER_V1"
DOMAINS = ("TRADER", "BUSINESS", "INVESTMENTS", "CORE")
PROFILE_IDS = ("TRADER_EXPERT", "BUSINESS_EXPERT", "INVESTMENT_EXPERT", "AION_CORE")

_DOMAIN_ALIASES = {
    "TRADER": "TRADER",
    "TRADING": "TRADER",
    "ATLASQUANT": "TRADER",
    "TRADER_EXPERT": "TRADER",
    "AION TRADER EXPERT": "TRADER",
    "BUSINESS": "BUSINESS",
    "NEGOCIOS": "BUSINESS",
    "BUSINESS_EXPERT": "BUSINESS",
    "AION BUSINESS EXPERT": "BUSINESS",
    "INVESTMENTS": "INVESTMENTS",
    "INVESTIMENTOS": "INVESTMENTS",
    "INVESTMENT": "INVESTMENTS",
    "INVESTMENT_EXPERT": "INVESTMENTS",
    "AION INVESTMENT EXPERT": "INVESTMENTS",
    "CORE": "CORE",
    "AION": "CORE",
    "AION/CORE": "CORE",
    "AION/AI": "CORE",
    "CENTRAL": "CORE",
    "AION_CORE": "CORE",
}
_PROFILE_BY_DOMAIN = {
    "TRADER": "TRADER_EXPERT",
    "BUSINESS": "BUSINESS_EXPERT",
    "INVESTMENTS": "INVESTMENT_EXPERT",
    "CORE": "AION_CORE",
}
_PROFILE_ALIASES = {
    "TRADER_EXPERT": "TRADER_EXPERT",
    "AION TRADER EXPERT": "TRADER_EXPERT",
    "TRADER": "TRADER_EXPERT",
    "BUSINESS_EXPERT": "BUSINESS_EXPERT",
    "AION BUSINESS EXPERT": "BUSINESS_EXPERT",
    "BUSINESS": "BUSINESS_EXPERT",
    "INVESTMENT_EXPERT": "INVESTMENT_EXPERT",
    "AION INVESTMENT EXPERT": "INVESTMENT_EXPERT",
    "INVESTMENTS": "INVESTMENT_EXPERT",
    "AION_CORE": "AION_CORE",
    "AION CORE": "AION_CORE",
    "CORE": "AION_CORE",
    "AION": "AION_CORE",
}
_INTENT_MARKERS = {
    "TRADER": ("trader", "trading", "mercado", "ordem", "radar"),
    "BUSINESS": ("business", "negocio", "negocios", "vendas"),
    "INVESTMENTS": ("investment", "investments", "investimento", "investimentos", "investir"),
    "CORE": ("aion/core", "aion core", "nucleo central"),
}
_LEGACY_SPEC = {
    "TRADER": "TRADER_FUTURE",
    "BUSINESS": "BUSINESS_FUTURE",
    "INVESTMENTS": "INVESTMENTS_FUTURE",
}
_AREA = {
    "TRADER": "atlasquant",
    "BUSINESS": "business",
    "INVESTMENTS": "investments",
    "CORE": "central",
}
_PRIMARY_MODULE = {
    "TRADER": "market",
    "BUSINESS": "business",
    "INVESTMENTS": "invest",
    "CORE": "core",
}
_ALLOWED_ACTIONS = {
    "TRADER": ("read", "analyze"),
    "BUSINESS": ("read", "analyze", "draft"),
    "INVESTMENTS": ("read", "analyze", "compare"),
    "CORE": ("read", "coordinate"),
}
_DENIED_ACTIONS = {
    "TRADER": ("real_trade", "payment", "deploy", "publication", "external_contact"),
    "BUSINESS": ("external_contact", "sign_contract", "spend", "publish", "charge", "payment"),
    "INVESTMENTS": ("move_money", "buy_asset", "sell_asset", "portfolio_mutation", "payment"),
    "CORE": ("real_trade", "payment", "publication", "deploy", "portfolio_mutation", "external_contact"),
}
_FORBIDDEN_TOOLS = frozenset({
    "real_trade", "payment", "publish", "deploy", "deploy_production",
    "external_contact", "sign_contract", "buy_asset", "sell_asset",
})


def _clean(value: Any, limit: int = 160) -> str:
    return " ".join(str(value or "").replace("\x00", "").split())[:limit]


def _fold(value: Any) -> str:
    text = _clean(value, 160).upper()
    for source, target in (("Ó", "O"), ("Õ", "O"), ("Ã", "A"), ("Á", "A"), ("É", "E"), ("Í", "I"), ("Ç", "C"), ("Ê", "E")):
        text = text.replace(source, target)
    return text


def _safety() -> dict[str, Any]:
    return {
        "permissions_expanded": False,
        "external_action_executed": False,
        "real_trading_enabled": False,
        "payment_executed": False,
        "publication_executed": False,
        "deploy_executed": False,
        "tool_called": False,
        "executes_action": False,
        "activates_specialist": False,
        "provider_called": False,
    }


def _unique(values: Sequence[Any] | None, *, upper: bool = False) -> list[str]:
    out: list[str] = []
    for raw in list(values or []):
        text = _fold(raw) if upper else _clean(raw, 120)
        if text and text not in out:
            out.append(text)
    return out


def _domain_tokens(value: Any) -> list[str] | None:
    """Return recognized domains, an empty list, or None when the token is unknown."""
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        found: list[str] = []
        unknown = False
        for item in value:
            part = _domain_tokens(item)
            if part is None:
                unknown = True
                continue
            for domain in part:
                if domain not in found:
                    found.append(domain)
        if unknown and not found:
            return None
        return found
    text = _fold(value)
    if not text:
        return []
    if text in _DOMAIN_ALIASES:
        return [_DOMAIN_ALIASES[text]]
    parts = [part for part in text.replace(",", " ").replace("|", " ").split() if part]
    if len(parts) > 1:
        found = []
        for part in parts:
            if part not in _DOMAIN_ALIASES:
                return None
            domain = _DOMAIN_ALIASES[part]
            if domain not in found:
                found.append(domain)
        return found
    return None


def _intent_domains(intent: Any) -> list[str]:
    text = _fold(intent).lower()
    if not text:
        return []
    found = []
    for domain, markers in _INTENT_MARKERS.items():
        if any(marker in text for marker in markers):
            found.append(domain)
    return found


def _profile_id(value: Any) -> str:
    return _PROFILE_ALIASES.get(_fold(value), "")


def specialist_profiles() -> dict[str, Any]:
    """Registered profiles. Runtime authority stays at the legacy future gate."""
    modules = specialist_modules()
    registry = default_registry()
    runtime = Registry(checkpoint_connected=False)
    profiles = []
    for domain in DOMAINS:
        profile_id = _PROFILE_BY_DOMAIN[domain]
        capability_ids = list(ecosystem_capabilities(_AREA[domain]))
        tools: list[str] = []
        roles: list[str] = []
        for capability_id in capability_ids:
            item = registry.get(capability_id)
            if item is None:
                continue
            for tool in item.allowed_tools:
                if tool not in tools and tool not in _FORBIDDEN_TOOLS:
                    tools.append(tool)
            for role in item.allowed_roles:
                if role not in roles:
                    roles.append(role)
        legacy_name = _LEGACY_SPEC.get(domain, "")
        legacy = runtime.get(legacy_name) if legacy_name else {}
        module_id = _PRIMARY_MODULE[domain]
        profiles.append({
            "profile_id": profile_id,
            "display_name": {
                "TRADER_EXPERT": "AION Trader Expert",
                "BUSINESS_EXPERT": "AION Business Expert",
                "INVESTMENT_EXPERT": "AION Investment Expert",
                "AION_CORE": "AION",
            }[profile_id],
            "domain": domain,
            "domain_recognized": True,
            "profile_registered": True,
            "runtime_capability_available": bool(legacy.get("available", False)) if legacy_name else False,
            "certification_state": "NOT_CERTIFIED",
            "specialist_certified": False,
            "legacy_spec": legacy_name or None,
            "area_id": _AREA[domain],
            "module": modules.get(module_id, ""),
            "supporting_modules": [
                modules[item] for item in {
                    "TRADER": ("market", "macro", "ict", "risk"),
                    "BUSINESS": ("business", "research", "risk"),
                    "INVESTMENTS": ("invest", "research", "risk"),
                    "CORE": ("core", "research", "risk"),
                }[domain]
                if item in modules
            ],
            "capability_ids": capability_ids,
            "allowed_tools": tools,
            "allowed_roles": roles,
            "allowed_actions": list(_ALLOWED_ACTIONS[domain]),
            "denied_actions": list(_DENIED_ACTIONS[domain]),
            "memory_domain": domain,
            "execution_mode": "COORDINATE_ONLY" if domain == "CORE" else "READ_ONLY",
            "inherits_physical_authority": False,
            "independent_ai": False,
        })
    return {
        "schema": SCHEMA,
        "profiles": profiles,
        "independent_ais_created": False,
        "executes_action": False,
        **_safety(),
    }


def _selected_profile(profile_id: str) -> dict[str, Any]:
    for row in specialist_profiles()["profiles"]:
        if row["profile_id"] == profile_id:
            return dict(row)
    return {}


def _envelope(
    *,
    status: str,
    reason: str,
    profile: Mapping[str, Any] | None,
    parent_roles: Sequence[str],
    parent_scopes: Sequence[str],
    parent_tools: Sequence[str],
    candidates: Sequence[str] = (),
) -> dict[str, Any]:
    row = dict(profile or {})
    allowed_roles = list(row.get("allowed_roles") or [])
    allowed_tools = list(row.get("allowed_tools") or [])
    roles = [role for role in allowed_roles if not parent_roles or role in parent_roles]
    tools = [tool for tool in allowed_tools if not parent_tools or tool in parent_tools]
    scopes = [scope for scope in parent_scopes]
    return {
        "schema": SCHEMA,
        "status": status,
        "reason": reason,
        "specialist": row.get("profile_id"),
        "display_name": row.get("display_name"),
        "domain": row.get("domain"),
        "profile": row or None,
        "candidates": list(candidates),
        "domain_recognized": bool(row),
        "profile_registered": bool(row.get("profile_registered")),
        "runtime_capability_available": bool(row.get("runtime_capability_available", False)) if row else False,
        "certification_state": row.get("certification_state", "NOT_CERTIFIED"),
        "capability_ids": list(row.get("capability_ids") or []),
        "memory_domain": row.get("memory_domain"),
        "allowed_tools": tools,
        "allowed_roles": roles,
        "allowed_scopes": scopes,
        "allowed_actions": list(row.get("allowed_actions") or []),
        "denied_actions": list(row.get("denied_actions") or []),
        "execution_mode": row.get("execution_mode"),
        "parent_roles": list(parent_roles),
        "parent_scopes": list(parent_scopes),
        "parent_tools": list(parent_tools),
        "inherits_physical_authority": False,
        "silent_fallback": False,
        **_safety(),
    }


def route_specialist(
    *,
    domain: Any = "",
    workspace: Any = "",
    intent: Any = "",
    requested_specialist: Any = "",
    parent_roles: Sequence[Any] | None = None,
    parent_scopes: Sequence[Any] | None = None,
    parent_tools: Sequence[Any] | None = None,
) -> dict[str, Any]:
    """Select one registered specialist. Unknown, ambiguous and missing stay fail-closed."""
    roles = _unique(parent_roles, upper=True)
    scopes = _unique(parent_scopes)
    tools = _unique(parent_tools)
    requested = _profile_id(requested_specialist) if _clean(requested_specialist) else ""
    if _clean(requested_specialist) and not requested:
        return _envelope(
            status="DEGRADED_SAFE",
            reason="SPECIALIST_NOT_REGISTERED",
            profile=None,
            parent_roles=roles,
            parent_scopes=scopes,
            parent_tools=tools,
        )

    def _present(value: Any) -> bool:
        if isinstance(value, (list, tuple, set)):
            return len(value) > 0
        return bool(_clean(value))

    domain_tokens = _domain_tokens(domain) if _present(domain) else []
    workspace_tokens = _domain_tokens(workspace) if _present(workspace) else []
    if _present(domain) and domain_tokens is None:
        return _envelope(
            status="UNKNOWN",
            reason="DENIED_SAFE",
            profile=None,
            parent_roles=roles,
            parent_scopes=scopes,
            parent_tools=tools,
        )
    if _present(workspace) and workspace_tokens is None and not domain_tokens:
        return _envelope(
            status="UNKNOWN",
            reason="DENIED_SAFE",
            profile=None,
            parent_roles=roles,
            parent_scopes=scopes,
            parent_tools=tools,
        )
    if domain_tokens and workspace_tokens and set(domain_tokens) != set(workspace_tokens):
        return _envelope(
            status="CLARIFICATION_REQUIRED",
            reason="AMBIGUOUS_DOMAIN",
            profile=None,
            parent_roles=roles,
            parent_scopes=scopes,
            parent_tools=tools,
            candidates=[_PROFILE_BY_DOMAIN[item] for item in domain_tokens],
        )
    explicit = list(domain_tokens or workspace_tokens or [])
    if len(explicit) > 1:
        return _envelope(
            status="CLARIFICATION_REQUIRED",
            reason="AMBIGUOUS_DOMAIN",
            profile=None,
            parent_roles=roles,
            parent_scopes=scopes,
            parent_tools=tools,
            candidates=[_PROFILE_BY_DOMAIN[item] for item in explicit],
        )
    hinted = _intent_domains(intent)
    chosen = explicit[0] if explicit else ""
    if chosen and hinted and any(item != chosen for item in hinted):
        return _envelope(
            status="CLARIFICATION_REQUIRED",
            reason="AMBIGUOUS_DOMAIN",
            profile=None,
            parent_roles=roles,
            parent_scopes=scopes,
            parent_tools=tools,
            candidates=[_PROFILE_BY_DOMAIN[item] for item in dict.fromkeys([chosen, *hinted])],
        )
    if not chosen:
        if len(hinted) > 1:
            return _envelope(
                status="CLARIFICATION_REQUIRED",
                reason="AMBIGUOUS_DOMAIN",
                profile=None,
                parent_roles=roles,
                parent_scopes=scopes,
                parent_tools=tools,
                candidates=[_PROFILE_BY_DOMAIN[item] for item in hinted],
            )
        if len(hinted) == 1 and not requested:
            chosen = hinted[0]
        elif not requested:
            return _envelope(
                status="CLARIFICATION_REQUIRED" if not _clean(intent) else "UNKNOWN",
                reason="AMBIGUOUS_DOMAIN" if not _clean(intent) else "DENIED_SAFE",
                profile=None,
                parent_roles=roles,
                parent_scopes=scopes,
                parent_tools=tools,
            )
    profile_id = requested or _PROFILE_BY_DOMAIN.get(chosen, "")
    if requested and chosen and _PROFILE_BY_DOMAIN.get(chosen) != requested:
        return _envelope(
            status="CLARIFICATION_REQUIRED",
            reason="AMBIGUOUS_DOMAIN",
            profile=None,
            parent_roles=roles,
            parent_scopes=scopes,
            parent_tools=tools,
            candidates=[requested, _PROFILE_BY_DOMAIN[chosen]],
        )
    profile = _selected_profile(profile_id)
    if not profile:
        return _envelope(
            status="DEGRADED_SAFE",
            reason="SPECIALIST_NOT_REGISTERED",
            profile=None,
            parent_roles=roles,
            parent_scopes=scopes,
            parent_tools=tools,
        )
    return _envelope(
        status="SELECTED",
        reason="DOMAIN_PROFILE_REGISTERED",
        profile=profile,
        parent_roles=roles,
        parent_scopes=scopes,
        parent_tools=tools,
    )


def evaluate_specialist_request(
    route: Mapping[str, Any] | None,
    *,
    requested_roles: Sequence[Any] | None = None,
    requested_tools: Sequence[Any] | None = None,
    requested_scopes: Sequence[Any] | None = None,
    requested_actions: Sequence[Any] | None = None,
) -> dict[str, Any]:
    """Refuse any role, scope, tool or action outside the selected profile and parent context."""
    selected = dict(route or {})
    profile = selected.get("profile") if isinstance(selected.get("profile"), Mapping) else {}
    parent_roles = set(_unique(selected.get("parent_roles"), upper=True))
    parent_tools = set(_unique(selected.get("parent_tools")))
    parent_scopes = set(_unique(selected.get("parent_scopes")))
    allowed_roles = set(_unique(profile.get("allowed_roles"), upper=True))
    allowed_tools = set(_unique(profile.get("allowed_tools")))
    allowed_actions = set(_unique(profile.get("allowed_actions")))
    denied_actions = set(_unique(profile.get("denied_actions")))
    if parent_roles:
        allowed_roles &= parent_roles
    if parent_tools:
        allowed_tools &= parent_tools
    if parent_scopes:
        allowed_scopes = set(parent_scopes)
    else:
        allowed_scopes = set()

    def _split(requested: Sequence[Any] | None, allowed: set[str], *, upper: bool = False) -> tuple[list[str], list[str]]:
        asked = _unique(requested, upper=upper)
        granted = [item for item in asked if item in allowed and item not in _FORBIDDEN_TOOLS and item not in denied_actions]
        blocked = [item for item in asked if item not in granted]
        return granted, blocked

    granted_roles, blocked_roles = _split(requested_roles, allowed_roles, upper=True)
    granted_tools, blocked_tools = _split(requested_tools, allowed_tools)
    granted_scopes, blocked_scopes = _split(requested_scopes, allowed_scopes)
    granted_actions, blocked_actions = _split(requested_actions, allowed_actions)
    return {
        "schema": SCHEMA,
        "specialist": selected.get("specialist"),
        "granted_roles": granted_roles,
        "blocked_roles": blocked_roles,
        "granted_tools": granted_tools,
        "blocked_tools": blocked_tools,
        "granted_scopes": granted_scopes,
        "blocked_scopes": blocked_scopes,
        "granted_actions": granted_actions,
        "blocked_actions": blocked_actions,
        "role_escalation_blocked": bool(blocked_roles),
        "tool_escalation_blocked": bool(blocked_tools),
        "scope_escalation_blocked": bool(blocked_scopes),
        "role_escalated": False,
        "tool_escalated": False,
        "scope_escalated": False,
        **_safety(),
    }


def present_domain_evidence(
    evidence: Mapping[str, Any] | None,
    *,
    target_domain: Any,
    accessor_profile: Any = "",
) -> dict[str, Any]:
    """Show foreign evidence only to AION Core, without promoting it to a current fact."""
    payload = dict(evidence or {})
    source = _fold(payload.get("domain") or payload.get("memory_domain") or "")
    target = _fold(target_domain)
    accessor = _fold(accessor_profile).replace(" ", "_")
    truth = _clean(payload.get("truth_state") or "UNKNOWN", 40).upper() or "UNKNOWN"
    same_domain = bool(source) and source == target
    explicit = accessor == "AION_CORE" and bool(source) and source != target
    visible = same_domain or explicit or not source
    if source and not same_domain and not explicit:
        visible = False
    return {
        "schema": SCHEMA,
        "visible": visible,
        "source_domain": source,
        "target_domain": target,
        "explicit_cross_domain": explicit,
        "automatic_cross_domain_access": False,
        "promoted": False,
        "used_as_current_fact": False,
        "truth_state": truth if visible else "UNKNOWN",
        "evidence": payload if visible else None,
        "tool_called": False,
        "executes_action": False,
    }


__all__ = [
    "SCHEMA",
    "DOMAINS",
    "PROFILE_IDS",
    "specialist_profiles",
    "route_specialist",
    "evaluate_specialist_request",
    "present_domain_evidence",
]
