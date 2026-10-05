"""Feature-flagged host composition for the staged durable AION Chat UI.

This is the only staging host that may construct the local SQLite chat store.
It is disabled by default, rejects production, requires an authenticated ADMIN
session and requires explicit tenant/workspace/staging-directory configuration.

It does not call providers, connectors, network endpoints or production stores.
"""
from __future__ import annotations

from hashlib import sha256
import os
from pathlib import Path
import re
from typing import Any, Mapping

from aion_chat.models import Scope
from aion_chat.store import HEALTHY, SQLiteChatStore, StorageUnavailableError
from atlasquant_aion_chat_product_bridge import validate_product_binding
from atlasquant_aion_chat_storage_resilience import (
    STAGING_RPO_SECONDS,
    STAGING_RTO_SECONDS,
)

SCHEMA = "ATLASQUANT_AION_CHAT_STAGED_HOST_V2"
FLAG = "ATLASQUANT_AION_CHAT_STAGED_PRODUCT"
TENANT_KEY = "ATLASQUANT_AION_CHAT_STAGED_TENANT_ID"
WORKSPACE_KEY = "ATLASQUANT_AION_CHAT_STAGED_WORKSPACE_ID"
DIRECTORY_KEY = "ATLASQUANT_AION_CHAT_STAGED_DIR"
_ALLOWED_ENVIRONMENTS = frozenset(
    {"LOCAL", "DEVELOPMENT", "DEV", "STAGING", "TEST", "QA"}
)
_SAFE_SCOPE_TOKEN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,95}$")
_STORE_PREFIX = "aq_aion_chat_staged_store_"
_ACTIVE_SCOPE_KEY = "aq_aion_chat_staged_active_scope"


def _clean(value: Any, limit: int = 240) -> str:
    return " ".join(str(value or "").replace("\x00", "").split())[:limit]


def _bool(value: Any) -> bool:
    return _clean(value, 20).lower() in {"1", "true", "yes", "on", "sim"}


def _config_value(config: Mapping[str, Any], key: str) -> str:
    return _clean(config.get(key), 2048)


def staged_feature_enabled(config: Mapping[str, Any] | None) -> bool:
    return _bool(dict(config or {}).get(FLAG))


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
        raise PermissionError("staged chat requires allowed authenticated access")
    if _clean(raw.get("mode"), 40).upper() != "AUTHENTICATED":
        raise PermissionError("staged chat requires AUTHENTICATED mode")
    if _clean(raw.get("role"), 24).upper() != "ADMIN":
        raise PermissionError("staged chat requires ADMIN access")
    if _clean(session.get("role"), 24).upper() != "ADMIN":
        raise PermissionError("staged chat requires ADMIN session")

    username = _scope_token(session.get("username"), "owner_id")
    tenant = _scope_token(_config_value(config, TENANT_KEY), "tenant_id")
    workspace = _scope_token(
        _config_value(config, WORKSPACE_KEY),
        "workspace_id",
    )
    scope = Scope(username, tenant, workspace)
    binding = validate_product_binding(raw, scope)
    if binding.get("bound") is not True:
        raise PermissionError(
            "staged chat product binding rejected: "
            + ",".join(binding.get("blockers") or [])
        )
    return scope


def _session_binding_digest(
    access: Mapping[str, Any] | None,
    scope: Scope,
) -> str:
    raw = dict(access or {})
    session = (
        dict(raw.get("session"))
        if isinstance(raw.get("session"), Mapping)
        else {}
    )
    fingerprint = _clean(session.get("credential_fingerprint"), 240)
    if not fingerprint:
        raise PermissionError("credential fingerprint required for staged binding")
    material = "|".join(
        [
            scope.owner_id,
            scope.tenant_id,
            scope.workspace_id,
            fingerprint,
        ]
    ).encode("utf-8")
    return sha256(material).hexdigest()


def _staging_directory(config: Mapping[str, Any]) -> Path:
    raw = _config_value(config, DIRECTORY_KEY)
    if not raw:
        raise ValueError("explicit staged chat directory required")
    if raw.startswith("file:") or "://" in raw:
        raise ValueError("staged chat directory must be a local filesystem path")
    path = Path(raw)
    if not path.is_absolute():
        raise ValueError("staged chat directory must be absolute")
    return path


def _scope_digest(scope: Scope) -> str:
    material = "|".join(
        [scope.owner_id, scope.tenant_id, scope.workspace_id]
    ).encode("utf-8")
    return sha256(material).hexdigest()[:24]


def _holder_key(scope: Scope) -> str:
    return _STORE_PREFIX + _scope_digest(scope)


def _store_path(scope: Scope, root: Path) -> Path:
    return root / ("aion-chat-" + _scope_digest(scope) + ".sqlite3")


def close_all_staged_host_stores(session_state: Any) -> int:
    """Close every staged SQLite handle in the current UI session."""
    closed = 0
    keys = [
        key
        for key in list(session_state.keys())
        if str(key).startswith(_STORE_PREFIX)
    ]
    for key in keys:
        holder = session_state.pop(key, None)
        if not isinstance(holder, Mapping):
            continue
        store = holder.get("store")
        if isinstance(store, SQLiteChatStore):
            try:
                store.close()
            finally:
                closed += 1
    session_state.pop(_ACTIVE_SCOPE_KEY, None)
    return closed


def _validate_live_store(store: SQLiteChatStore) -> dict[str, Any]:
    health = store.storage_health(deep=True)
    if health.get("state") != HEALTHY:
        try:
            store.close()
        finally:
            raise StorageUnavailableError(
                "staged host refused unhealthy local store: "
                + str(health.get("reason") or "UNKNOWN")
            )
    return health


def get_or_create_staged_store(
    session_state: Any,
    scope: Scope,
    root: Path,
    *,
    session_binding_digest: str = "",
) -> SQLiteChatStore:
    """Keep one healthy local staging handle for the active authenticated scope."""
    key = _holder_key(scope)
    expected = str(_store_path(scope, root))
    expected_binding = _clean(session_binding_digest, 64)

    active = _clean(session_state.get(_ACTIVE_SCOPE_KEY), 160)
    if active and active != key:
        close_all_staged_host_stores(session_state)

    holder = session_state.get(key)
    if isinstance(holder, Mapping):
        existing = holder.get("store")
        existing_path = str(holder.get("path") or "")
        existing_binding = _clean(holder.get("session_binding_digest"), 64)
        if (
            existing_path == expected
            and existing_binding == expected_binding
            and isinstance(existing, SQLiteChatStore)
        ):
            _validate_live_store(existing)
            session_state[_ACTIVE_SCOPE_KEY] = key
            return existing
        if isinstance(existing, SQLiteChatStore):
            try:
                existing.close()
            except Exception:
                pass
        session_state.pop(key, None)

    store = SQLiteChatStore(expected)
    _validate_live_store(store)
    session_state[key] = {
        "schema": SCHEMA,
        "path": expected,
        "store": store,
        "session_binding_digest": expected_binding,
    }
    session_state[_ACTIVE_SCOPE_KEY] = key
    return store


def close_staged_host_store(
    session_state: Any,
    scope: Scope,
) -> bool:
    """QA/staging lifecycle helper. It closes only the scoped injected handle."""
    key = _holder_key(scope)
    holder = session_state.pop(key, None)
    if not isinstance(holder, Mapping):
        return False
    store = holder.get("store")
    if isinstance(store, SQLiteChatStore):
        store.close()
        if session_state.get(_ACTIVE_SCOPE_KEY) == key:
            session_state.pop(_ACTIVE_SCOPE_KEY, None)
        return True
    return False


def build_staged_runtime_context() -> dict[str, Any]:
    """Create the explicit local staging runtime context, never a live provider."""
    from atlasquant_aion_memory import default_checkpoint

    return {
        "checkpoint": default_checkpoint(),
        "host_mode": "STAGED_LOCAL",
        "provider_enabled": False,
        "network_enabled": False,
        "production_persistence": False,
    }


def build_staged_host_binding(
    session_state: Any,
    access: Mapping[str, Any] | None,
    *,
    config: Mapping[str, Any] | None,
    environment: Any,
    runtime_context: Mapping[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Resolve a complete product binding or return None when the flag is off."""
    cfg = dict(config or {})
    if not staged_feature_enabled(cfg):
        return None

    env = _clean(environment, 40).upper()
    if env not in _ALLOWED_ENVIRONMENTS:
        raise PermissionError(
            "staged durable chat is disabled outside explicit non-production environments"
        )

    scope = _authenticated_scope(access, cfg)
    session_binding = _session_binding_digest(access, scope)
    root = _staging_directory(cfg)
    runtime = (
        dict(runtime_context)
        if isinstance(runtime_context, Mapping)
        else build_staged_runtime_context()
    )
    store = get_or_create_staged_store(
        session_state,
        scope,
        root,
        session_binding_digest=session_binding,
    )
    health = _validate_live_store(store)

    return {
        "schema": SCHEMA,
        "state": "STAGED_BOUND",
        "scope": scope,
        "store": store,
        "runtime_context": runtime,
        "conversation_id": "",
        "feature_flag": FLAG,
        "feature_enabled": True,
        "environment": env,
        "staging_store_path": str(_store_path(scope, root)),
        "storage_health": health,
        "staging_rpo_seconds": STAGING_RPO_SECONDS,
        "staging_rto_seconds": STAGING_RTO_SECONDS,
        "session_binding_digest": session_binding,
        "local_sqlite_only": True,
        "production_store_activated": False,
        "provider_called": False,
        "network_called": False,
        "external_action_executed": False,
        "grants_authority": False,
    }


def streamlit_staged_config(st: Any) -> dict[str, str]:
    """Read only the four staged-host configuration keys."""
    out: dict[str, str] = {}
    for key in (FLAG, TENANT_KEY, WORKSPACE_KEY, DIRECTORY_KEY):
        value = ""
        try:
            value = st.secrets.get(key, os.getenv(key, ""))
        except Exception:
            value = os.getenv(key, "")
        out[key] = str(value or "").strip()
    return out


def build_streamlit_staged_binding(
    st: Any,
    access: Mapping[str, Any] | None,
    *,
    environment: Any,
) -> dict[str, Any] | None:
    """Host-facing entrypoint used by the real Streamlit shell."""
    config = streamlit_staged_config(st)
    return build_staged_host_binding(
        st.session_state,
        access,
        config=config,
        environment=environment,
    )


__all__ = [
    "SCHEMA",
    "FLAG",
    "TENANT_KEY",
    "WORKSPACE_KEY",
    "DIRECTORY_KEY",
    "staged_feature_enabled",
    "get_or_create_staged_store",
    "close_staged_host_store",
    "close_all_staged_host_stores",
    "build_staged_runtime_context",
    "build_staged_host_binding",
    "streamlit_staged_config",
    "build_streamlit_staged_binding",
]
