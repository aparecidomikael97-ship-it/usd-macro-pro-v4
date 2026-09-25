"""AION Portable Core contracts.

Provider-neutral registry for the AION central shell and its workspaces.
AtlasQuant is one workspace of the AION ecosystem rather than the AION's only
identity. This module performs no network I/O and never activates a connector.

Security rules:
- one central shell may route to many isolated workspaces;
- workspace identity, permissions and connector scopes stay explicit;
- external connectors start disabled;
- no connector receives ADMIN sovereignty automatically;
- real trading is not exposed as a portable capability.
"""
from __future__ import annotations

from hashlib import sha256
from typing import Any, Mapping, Sequence
import json
import re

SCHEMA = "ATLASQUANT_AION_PORTABLE_CORE_V1"
PORTABLE_CORE_VERSION = "1.0"

WORKSPACE_STATES = ("ACTIVE_LOCAL", "READY", "PLANNED", "DISABLED")
CONNECTOR_PROTOCOLS = ("NATIVE", "API", "MCP", "FILE", "WEBHOOK")
CONNECTOR_STATES = ("DISABLED", "CONFIGURED", "READY", "DEGRADED")
_ALLOWED_ID = re.compile(r"^[a-z0-9][a-z0-9._-]{1,63}$")

DEFAULT_WORKSPACES = (
    {
        "workspace_id": "central",
        "label": "AION Central",
        "kind": "CORE",
        "state": "ACTIVE_LOCAL",
        "isolated_context": True,
        "admin_only": True,
        "entry_key": "central",
    },
    {
        "workspace_id": "atlasquant",
        "label": "AtlasQuant",
        "kind": "TRADING_PLATFORM",
        "state": "ACTIVE_LOCAL",
        "isolated_context": True,
        "admin_only": False,
        "entry_key": "atlasquant",
    },
    {
        "workspace_id": "studio",
        "label": "Studio",
        "kind": "CREATIVE",
        "state": "READY",
        "isolated_context": True,
        "admin_only": True,
        "entry_key": "studio",
    },
    {
        "workspace_id": "business",
        "label": "Negócios",
        "kind": "BUSINESS",
        "state": "READY",
        "isolated_context": True,
        "admin_only": True,
        "entry_key": "business",
    },
    {
        "workspace_id": "development",
        "label": "Desenvolvimento",
        "kind": "DEVELOPMENT",
        "state": "READY",
        "isolated_context": True,
        "admin_only": True,
        "entry_key": "development",
    },
    {
        "workspace_id": "administration",
        "label": "Administração",
        "kind": "ADMIN",
        "state": "READY",
        "isolated_context": True,
        "admin_only": True,
        "entry_key": "administration",
    },
)


def _clean(value: Any, limit: int = 300) -> str:
    return " ".join(str(value or "").replace("\x00", "").split())[:limit]


def _stable_digest(payload: Any) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    return sha256(raw.encode("utf-8")).hexdigest()[:24]


def _safe_id(value: Any) -> str:
    text = _clean(value, 64).lower()
    if not _ALLOWED_ID.fullmatch(text):
        raise ValueError("invalid portable id")
    return text


def normalize_workspace(raw: Mapping[str, Any]) -> dict[str, Any]:
    item = dict(raw or {})
    wid = _safe_id(item.get("workspace_id"))
    state = _clean(item.get("state"), 40).upper()
    if state not in WORKSPACE_STATES:
        state = "PLANNED"
    return {
        "workspace_id": wid,
        "label": _clean(item.get("label"), 100) or wid,
        "kind": _clean(item.get("kind"), 80).upper() or "GENERAL",
        "state": state,
        "isolated_context": bool(item.get("isolated_context", True)),
        "admin_only": bool(item.get("admin_only", True)),
        "entry_key": _safe_id(item.get("entry_key") or wid),
        "external_action_authority": False,
        "real_trading_enabled": False,
    }


def normalize_workspaces(rows: Sequence[Mapping[str, Any]] | None) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in list(rows or [])[:100]:
        if not isinstance(raw, Mapping):
            continue
        try:
            item = normalize_workspace(raw)
        except Exception:
            continue
        if item["workspace_id"] in seen:
            continue
        seen.add(item["workspace_id"])
        out.append(item)
    return out


def new_connector(
    connector_id: Any,
    *,
    label: Any,
    protocol: Any,
    workspace_id: Any,
    state: Any = "DISABLED",
    scopes: Sequence[Any] | None = None,
    secret_refs: Sequence[Any] | None = None,
    external_side_effects: bool = False,
) -> dict[str, Any]:
    cid = _safe_id(connector_id)
    workspace = _safe_id(workspace_id)
    proto = _clean(protocol, 30).upper()
    if proto not in CONNECTOR_PROTOCOLS:
        raise ValueError("unsupported connector protocol")
    normalized_state = _clean(state, 30).upper()
    if normalized_state not in CONNECTOR_STATES:
        normalized_state = "DISABLED"

    scope_rows: list[str] = []
    for scope in list(scopes or [])[:50]:
        text = _clean(scope, 100)
        if text and text not in scope_rows:
            scope_rows.append(text)

    refs: list[str] = []
    for ref in list(secret_refs or [])[:30]:
        text = _clean(ref, 160)
        lowered = text.casefold()
        if lowered.startswith(("sk-", "ghp_", "github_pat_", "bearer ")) or "-----begin private key-----" in lowered:
            raise ValueError("secret value detected where connector secret reference was expected")
        if text and text not in refs:
            refs.append(text)

    return {
        "connector_id": cid,
        "label": _clean(label, 100) or cid,
        "protocol": proto,
        "workspace_id": workspace,
        "state": normalized_state,
        "scopes": scope_rows,
        "secret_refs": refs,
        "external_side_effects": bool(external_side_effects),
        "configuration_ready": normalized_state == "READY",
        "enabled": False,
        "activation_approved": False,
        "requires_guardian": True,
        "requires_proof_of_safety_for_sensitive_actions": True,
        "may_expand_own_permissions": False,
        "real_trading_enabled": False,
    }


def normalize_connectors(rows: Sequence[Mapping[str, Any]] | None) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in list(rows or [])[:200]:
        if not isinstance(raw, Mapping):
            continue
        try:
            item = new_connector(
                raw.get("connector_id"),
                label=raw.get("label"),
                protocol=raw.get("protocol"),
                workspace_id=raw.get("workspace_id"),
                state=raw.get("state"),
                scopes=raw.get("scopes") if isinstance(raw.get("scopes"), (list, tuple)) else [],
                secret_refs=raw.get("secret_refs") if isinstance(raw.get("secret_refs"), (list, tuple)) else [],
                external_side_effects=bool(raw.get("external_side_effects", False)),
            )
        except Exception:
            continue
        if item["connector_id"] in seen:
            continue
        seen.add(item["connector_id"])
        out.append(item)
    return out


def default_portable_core() -> dict[str, Any]:
    workspaces = normalize_workspaces(DEFAULT_WORKSPACES)
    connectors: list[dict[str, Any]] = []
    return {
        "schema": SCHEMA,
        "version": PORTABLE_CORE_VERSION,
        "identity": "AION",
        "central_shell": {
            "single_entry": True,
            "entry_key": "central",
            "mobile_ready": True,
            "desktop_ready": True,
            "pwa_target": True,
            "email_is_storage": False,
        },
        "workspaces": workspaces,
        "connectors": connectors,
        "workspace_isolation_required": True,
        "vendor_lock_in_required": False,
        "external_connectors_default_enabled": False,
        "real_trading_enabled": False,
        "digest": portable_core_digest(workspaces, connectors),
    }


def normalize_portable_core(raw: Mapping[str, Any] | None) -> dict[str, Any]:
    item = dict(raw or {})
    workspaces = normalize_workspaces(item.get("workspaces") if isinstance(item.get("workspaces"), (list, tuple)) else [])
    if not workspaces:
        workspaces = normalize_workspaces(DEFAULT_WORKSPACES)
    connectors = normalize_connectors(item.get("connectors") if isinstance(item.get("connectors"), (list, tuple)) else [])
    known = {x["workspace_id"] for x in workspaces}
    connectors = [x for x in connectors if x["workspace_id"] in known]
    return {
        "schema": SCHEMA,
        "version": PORTABLE_CORE_VERSION,
        "identity": "AION",
        "central_shell": {
            "single_entry": True,
            "entry_key": "central",
            "mobile_ready": True,
            "desktop_ready": True,
            "pwa_target": True,
            "email_is_storage": False,
        },
        "workspaces": workspaces,
        "connectors": connectors,
        "workspace_isolation_required": True,
        "vendor_lock_in_required": False,
        "external_connectors_default_enabled": False,
        "real_trading_enabled": False,
        "digest": portable_core_digest(workspaces, connectors),
    }


def portable_core_digest(
    workspaces: Sequence[Mapping[str, Any]] | None,
    connectors: Sequence[Mapping[str, Any]] | None,
) -> str:
    payload = {
        "workspaces": normalize_workspaces(workspaces),
        "connectors": normalize_connectors(connectors),
    }
    return _stable_digest(payload)


def central_entry_contract(*, authenticated_admin: bool, query_key: Any = "aion") -> dict[str, Any]:
    """Describe one-link routing without creating a deployment or domain."""
    key = _safe_id(query_key)
    return {
        "schema": SCHEMA,
        "single_link": True,
        "query_key": key,
        "query_value": "1",
        "target_workspace": "central",
        "admin_authenticated": bool(authenticated_admin),
        "allowed": bool(authenticated_admin),
        "reason": "ADMIN_CENTRAL_READY" if authenticated_admin else "ADMIN_AUTHENTICATION_REQUIRED",
        "creates_domain": False,
        "deploys_app": False,
        "executes_action": False,
    }


def portable_core_summary(raw: Mapping[str, Any] | None) -> dict[str, Any]:
    state = normalize_portable_core(raw)
    connectors = state["connectors"]
    return {
        "schema": SCHEMA,
        "workspaces": len(state["workspaces"]),
        "active_local_workspaces": sum(1 for x in state["workspaces"] if x["state"] == "ACTIVE_LOCAL"),
        "connectors": len(connectors),
        "ready_connectors": sum(1 for x in connectors if x["state"] == "READY"),
        "external_side_effect_connectors": sum(1 for x in connectors if x["external_side_effects"]),
        "single_entry": True,
        "pwa_target": True,
        "real_trading_enabled": False,
        "digest": state["digest"],
    }


__all__ = [
    "SCHEMA",
    "PORTABLE_CORE_VERSION",
    "WORKSPACE_STATES",
    "CONNECTOR_PROTOCOLS",
    "CONNECTOR_STATES",
    "DEFAULT_WORKSPACES",
    "normalize_workspace",
    "normalize_workspaces",
    "new_connector",
    "normalize_connectors",
    "default_portable_core",
    "normalize_portable_core",
    "portable_core_digest",
    "central_entry_contract",
    "portable_core_summary",
]
