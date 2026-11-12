"""A195: fail-closed Streamlit AION chat identity revalidation at host entrypoints.

This is defense-in-depth on top of the main Streamlit login. It requires the
chat host's access object to match the current session in st.session_state,
which in turn must match the server-configured user registry and timestamps.

Limits: Streamlit session_state and st.secrets are host-trusted, not independent
external HUMAN_OWNER enrollment or cryptographic session custody. No P0 is
homologated and no provider/external effect is enabled by this module.
"""
from __future__ import annotations

from collections.abc import Mapping
import math
import os
import time
from typing import Any

from atlasquant_access_control import (
    ROLE_PERMISSIONS,
    load_users_config,
    session_is_current,
)

SCHEMA = "ATLASQUANT_A195_STREAMLIT_CHAT_HOST_IDENTITY_RECHECK_V1"
SESSION_KEY = "atlasquant_access_session"
REGISTRY_KEY = "ATLASQUANT_USERS_JSON"
MAX_AGE_SECONDS = 12 * 60 * 60
MAX_IDLE_SECONDS = 2 * 60 * 60
_REQUIRED = frozenset({"app:read", "aion:admin"})


def _stop(reason: str) -> None:
    # Avoid leaking tokens/registry/session records into errors or UI.
    raise PermissionError("AION_CHAT_HOST_RECHECK_DENIED:" + reason)


def _registry(st: Any) -> object:
    # Same precedence as atlasquant_access_panel._setting, and fail-closed
    # when no usable server registry is available.
    env_registry = os.getenv(REGISTRY_KEY, "")
    try:
        return st.secrets.get(REGISTRY_KEY, env_registry)
    except Exception:
        return env_registry


def require_chat_host_session(
    st: Any,
    access: Mapping[str, Any] | None,
    *,
    now: float | None = None,
) -> bool:
    """Require current owner ADMIN session before creating *any* chat binding.

    Must be called only inside feature-enabled Streamlit host wrappers. It
    neither constructs/returns Scope nor opens any store, token or provider.
    """
    if not isinstance(access, Mapping):
        _stop("ACCESS_MAPPING_REQUIRED")
    if access.get("allowed") is not True or access.get("mode") != "AUTHENTICATED":
        _stop("AUTHENTICATED_ACCESS_REQUIRED")

    try:
        session_state = st.session_state
        current = session_state.get(SESSION_KEY)
    except Exception:
        _stop("SERVER_SESSION_REQUIRED")
    if not isinstance(current, Mapping):
        _stop("SERVER_SESSION_REQUIRED")
    supplied = access.get("session")
    if not isinstance(supplied, Mapping):
        _stop("BOUND_ACCESS_SESSION_REQUIRED")

    users = load_users_config(_registry(st))
    if not users or not session_is_current(current, users):
        _stop("CURRENT_USER_REGISTRY_MISMATCH")

    # Strong comparison to the server-controlled session, not just role/name.
    if dict(supplied) != dict(current):
        _stop("SESSION_BINDING_MISMATCH")
    if access.get("role") != "ADMIN" or current.get("role") != "ADMIN":
        _stop("OWNER_ADMIN_REQUIRED")

    permissions = current.get("permissions")
    if not isinstance(permissions, (list, tuple, frozenset, set)) or not all(
        isinstance(item, str) for item in permissions
    ):
        _stop("SESSION_PERMISSIONS_REQUIRED")
    if set(permissions) != set(ROLE_PERMISSIONS["ADMIN"]):
        _stop("ROLE_PERMISSIONS_NOT_SERVER_CANONICAL")
    if not _REQUIRED.issubset(permissions):
        _stop("AION_PERMISSIONS_REQUIRED")

    # Same maximum age / idle window used by the UI login. Check again at
    # the chat host boundary, even if the panel issued an earlier decision.
    try:
        clock = float(time.time() if now is None else now)
        issued = float(current.get("authenticated_at"))
        last_seen = float(current.get("last_seen"))
        if (
            not all(math.isfinite(v) for v in (clock, issued, last_seen))
            or issued <= 0
            or last_seen <= 0
            or not issued <= last_seen <= clock
        ):
            raise ValueError("invalid session timestamps")
    except (ValueError, TypeError, OverflowError):
        _stop("INVALID_SESSION_TIME")
    if clock - issued > MAX_AGE_SECONDS:
        _stop("SESSION_MAX_AGE")
    if clock - last_seen > MAX_IDLE_SECONDS:
        _stop("SESSION_IDLE_TIMEOUT")

    return True


__all__ = [
    "SCHEMA", "SESSION_KEY", "REGISTRY_KEY",
    "MAX_AGE_SECONDS", "MAX_IDLE_SECONDS",
    "require_chat_host_session",
]
