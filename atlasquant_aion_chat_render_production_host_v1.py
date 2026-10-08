"""Trusted Streamlit host binding for production AION Chat PostgreSQL.

The host is the only layer allowed to resolve approved runtime configuration
from Streamlit secrets / process environment. The storage implementation itself
remains configuration-injected.

Production persistence is OFF unless the explicit activation flag is true.
When off, this module returns None and the existing default/staging path remains
unchanged.
"""
from __future__ import annotations

import os
import re
from typing import Any, Mapping

from aion_chat.models import Scope
from atlasquant_aion_chat_product_bridge import validate_product_binding
from atlasquant_aion_chat_render_production_composition_v1 import (
    ENABLED_KEY,
    HOST_KEY,
    PORT_KEY,
    DATABASE_KEY,
    USER_KEY,
    PASSWORD_KEY,
    SSLMODE_KEY,
    CURSOR_KEY,
    build_production_chat_store,
)


SCHEMA = "ATLASQUANT_AION_CHAT_RENDER_PRODUCTION_HOST_V1"
TENANT_KEY = "AION_CHAT_PRODUCTION_TENANT_ID"
WORKSPACE_KEY = "AION_CHAT_PRODUCTION_WORKSPACE_ID"

_ALLOWED_ENVIRONMENTS = frozenset({"PRODUCTION", "RUNTIME", "TEST"})
_SAFE_SCOPE_TOKEN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,95}$")
_TRUE = frozenset({"1", "true", "yes", "on", "sim"})


def _clean(value: Any, limit: int = 4096) -> str:
    return str(value or "").strip()[:limit]


def _enabled(value: Any) -> bool:
    return _clean(value, 20).lower() in _TRUE


def production_feature_enabled(config: Mapping[str, Any] | None) -> bool:
    return _enabled(dict(config or {}).get(ENABLED_KEY))


def _scope_token(value: Any, name: str) -> str:
    text = _clean(value, 96)
    if not _SAFE_SCOPE_TOKEN.fullmatch(text):
        raise ValueError(f"{name} must be an explicit safe scope token")
    return text


def _authenticated_scope(
    access: Mapping[str, Any] | None,
    config: Mapping[str, Any],
) -> Scope:
    raw = dict(access or {})
    session = (
        dict(raw.get("session"))
        if isinstance(raw.get("session"), Mapping)
        else {}
    )

    if raw.get("allowed") is not True:
        raise PermissionError("production chat requires allowed authenticated access")
    if _clean(raw.get("mode"), 40).upper() != "AUTHENTICATED":
        raise PermissionError("production chat requires AUTHENTICATED mode")
    if _clean(raw.get("role"), 24).upper() != "ADMIN":
        raise PermissionError("production chat requires ADMIN access")
    if _clean(session.get("role"), 24).upper() != "ADMIN":
        raise PermissionError("production chat requires ADMIN session")

    owner = _scope_token(session.get("username"), "owner_id")
    tenant = _scope_token(config.get(TENANT_KEY), "tenant_id")
    workspace = _scope_token(config.get(WORKSPACE_KEY), "workspace_id")
    scope = Scope(owner, tenant, workspace)

    binding = validate_product_binding(raw, scope)
    if binding.get("bound") is not True:
        raise PermissionError(
            "production chat product binding rejected: "
            + ",".join(binding.get("blockers") or [])
        )
    return scope


def build_production_runtime_context() -> dict[str, Any]:
    """Production persistence context with external execution still disabled."""
    from atlasquant_aion_memory import default_checkpoint

    return {
        "checkpoint": default_checkpoint(),
        "host_mode": "RENDER_PRODUCTION_PERSISTENCE",
        "production_persistence": True,
        "provider_enabled": False,
        "external_provider_network_enabled": False,
        "worker_enabled": False,
        "external_actions_enabled": False,
        "core_mutation_enabled": False,
    }


def build_production_host_binding(
    access: Mapping[str, Any] | None,
    *,
    config: Mapping[str, Any] | None,
    environment: Any,
    runtime_context: Mapping[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Build the product binding only when explicitly activated."""
    cfg = dict(config or {})
    if not production_feature_enabled(cfg):
        return None

    env = _clean(environment, 40).upper()
    if env not in _ALLOWED_ENVIRONMENTS:
        raise PermissionError(
            "production AION Chat persistence is disabled in this environment"
        )

    scope = _authenticated_scope(access, cfg)
    store, storage_binding = build_production_chat_store(
        cfg,
        environment="TEST" if env == "TEST" else "PRODUCTION",
    )
    runtime = (
        dict(runtime_context)
        if isinstance(runtime_context, Mapping)
        else build_production_runtime_context()
    )

    return {
        "schema": SCHEMA,
        "state": "PRODUCTION_BOUND",
        "scope": scope,
        "store": store,
        "runtime_context": runtime,
        "conversation_id": "",
        "feature_flag": ENABLED_KEY,
        "feature_enabled": True,
        "environment": env,
        "storage_binding": storage_binding,
        "storage_health": storage_binding.get("health", {}),
        "production_store_activated": True,
        "provider_called": False,
        "external_provider_network_enabled": False,
        "worker_armed": False,
        "external_action_executed": False,
        "core_checkpoint_write": False,
        "grants_authority": False,
    }


def streamlit_production_config(st: Any) -> dict[str, str]:
    """Resolve only approved AION Chat production configuration keys."""
    keys = (
        ENABLED_KEY,
        HOST_KEY,
        PORT_KEY,
        DATABASE_KEY,
        USER_KEY,
        PASSWORD_KEY,
        SSLMODE_KEY,
        CURSOR_KEY,
        TENANT_KEY,
        WORKSPACE_KEY,
    )
    out: dict[str, str] = {}
    for key in keys:
        value = ""
        try:
            value = st.secrets.get(key, os.getenv(key, ""))
        except Exception:
            value = os.getenv(key, "")
        out[key] = str(value or "").strip()
    return out


def build_streamlit_production_binding(
    st: Any,
    access: Mapping[str, Any] | None,
    *,
    environment: Any,
) -> dict[str, Any] | None:
    """Host-facing production entrypoint for the real Streamlit shell."""
    config = streamlit_production_config(st)
    if not production_feature_enabled(config):
        return None
    return build_production_host_binding(
        access,
        config=config,
        environment=environment,
    )


__all__ = [
    "SCHEMA",
    "TENANT_KEY",
    "WORKSPACE_KEY",
    "production_feature_enabled",
    "build_production_runtime_context",
    "build_production_host_binding",
    "streamlit_production_config",
    "build_streamlit_production_binding",
]
