"""A192 laboratory-only authenticated owner chat read bridge.

This module exercises the existing password authenticator and real
SQLiteChatStore in isolation. It does NOT authenticate network sessions,
enroll HUMAN_OWNER, authorize providers, make the underlying store safe
against direct untrusted Scope construction, or satisfy an external P0.

The trusted USERS and OWNER_PROFILES inputs are simulated server-side state,
never caller JSON. Workspaces intentionally omit frozen NEGOCIOS.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from aion_chat.models import Scope
from atlasquant_access_control import AccessUser, authenticate, normalize_username

SCHEMA = "AION_A192_AUTHENTICATED_CHAT_READ_LAB_V1"
PERSONAL_WORKSPACES = frozenset({"aion", "trader", "investimentos"})
_ID_CHARS = frozenset("abcdefghijklmnopqrstuvwxyz0123456789._-")
_MAX_ID = 80


def _safe_id(value: object) -> bool:
    return (
        isinstance(value, str)
        and 3 <= len(value) <= _MAX_ID
        and value[0].isalnum()
        and all(c in _ID_CHARS for c in value)
    )


def _denied(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "state": "DENIED",
        "reason": reason,
        "local_read_performed": False,
        "real_session_authentication_proven": False,
        "operational_authority": False,
        "external_action_authorized": False,
        "data_exposed": False,
        "worker_enabled": False,
        "p0_homologated": 0,
        "hard_no_go": True,
    }


def authenticated_owner_conversation_read(
    store: object,
    *,
    username: object,
    password: object,
    requested_workspace: object,
    conversation_id: object,
    trusted_users: Mapping[str, AccessUser] | None,
    trusted_owner_profiles: Mapping[str, Mapping[str, Any]] | None,
    untrusted_claims: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a small read-only conversation summary after local PASSWORD check.

    Parameters prefixed trusted_* MUST originate in a server-side registry, not
    user messages, web payloads, prompt text, attached files or self-claimed
    'approved' fields. This is NOT a network endpoint nor deployable auth.
    """
    # The intentionally unused untrusted_claims is never a source for Scope,
    # role, workspace entitlement or owner/tenant identity.
    _ = untrusted_claims
    normalized = normalize_username(username) if isinstance(username, str) else ""
    if not normalized or not isinstance(password, str) or not password:
        return _denied("CREDENTIALS_REQUIRED")
    if not isinstance(trusted_users, Mapping) or not isinstance(trusted_owner_profiles, Mapping):
        return _denied("SERVER_REGISTRY_REQUIRED")

    session = authenticate(normalized, password, trusted_users)
    if session is None:
        return _denied("CREDENTIALS_INVALID_OR_INACTIVE")
    if session.get("role") != "ADMIN":
        return _denied("OWNER_ROLE_REQUIRED")

    profile = trusted_owner_profiles.get(normalized)
    if not isinstance(profile, Mapping) or profile.get("active") is not True:
        return _denied("TRUSTED_OWNER_PROFILE_REQUIRED")
    if profile.get("role") != "ADMIN":
        return _denied("TRUSTED_PROFILE_ROLE_MISMATCH")

    owner_id, tenant_id = profile.get("owner_id"), profile.get("tenant_id")
    if not _safe_id(owner_id) or not _safe_id(tenant_id):
        return _denied("TRUSTED_PROFILE_IDENTITY_INVALID")
    workspace = requested_workspace.strip().lower() if isinstance(requested_workspace, str) else ""
    if workspace not in PERSONAL_WORKSPACES:
        return _denied("PERSONAL_WORKSPACE_UNAVAILABLE")
    permitted = profile.get("allowed_workspaces")
    if not isinstance(permitted, (list, tuple, frozenset)) or workspace not in permitted:
        return _denied("WORKSPACE_NOT_ASSIGNED_BY_SERVER")
    if not isinstance(conversation_id, str) or not conversation_id or len(conversation_id) > 120:
        return _denied("INVALID_CONVERSATION_ID")

    # Only HERE is Scope derived from authenticated username + server registry.
    scope = Scope(owner_id, tenant_id, workspace)
    try:
        conv = store.get_conversation(scope, conversation_id)
    except LookupError:
        return _denied("CONVERSATION_NOT_IN_AUTHENTICATED_SCOPE")
    # Exception from an unavailable/broken store must NOT be interpreted as
    # 'not found' and never triggers fallback to another scope.
    return {
        "schema": SCHEMA,
        "state": "LOCAL_READ",
        "reason": "LOCAL_PASSWORD_AUTH_AND_SERVER_SCOPE_MATCH",
        "conversation_id": conv.id,
        "title": conv.title,
        "message_count": conv.message_count,
        "workspace": workspace,
        "local_read_performed": True,
        "real_session_authentication_proven": False,
        "operational_authority": False,
        "external_action_authorized": False,
        "data_exposed": True,
        "worker_enabled": False,
        "p0_homologated": 0,
        "hard_no_go": True,
    }
