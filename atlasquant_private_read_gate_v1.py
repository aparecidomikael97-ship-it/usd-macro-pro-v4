"""Fail-closed gate for legacy private GitHub-backed operational evidence.

Phase-A containment. A server-configured workspace membership is mandatory;
it does NOT implement the future durable B2B tenant/ledger authorization.
Public market providers must not be routed through this private gate.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
from typing import Any, Mapping

from atlasquant_access_control import (
    credential_fingerprint, has_permission, session_is_current,
)

SCOPE_KEY = "atlasquant_private_read_scope_v1"
QUARANTINE_KEY = "atlasquant_private_pending_cross_session_quarantine_v1"
PENDING_KEYS = (
    "atlasquant_shadow_reconciliation_pending",
    "atlasquant_research_evidence_reconciliation_pending",
)
DISPLAY_KEYS = (
    "atlasquant_shadow_samples",
    "atlasquant_shadow_hydrated",
    "atlasquant_shadow_persistence_status",
    "atlasquant_research_evidence_records",
    "atlasquant_research_evidence_hydrated",
    "atlasquant_research_evidence_status",
    "atlasquant_admin_runtime_paper_setup_audit",
    "atlasquant_admin_runtime_paper_setup_audit_status",
    "atlasquant_admin_runtime_paper_setup_audit_hydrated",
    "atlasquant_admin_runtime_model_paper",
    "atlasquant_admin_runtime_model_paper_status",
    "atlasquant_admin_runtime_model_paper_hydrated",
    "atlasquant_last_backtest_intelligence",
    "atlasquant_last_strategy_suite_intelligence",
)


def clear_private_ui_state(state: Any) -> None:
    """Remove private presentation only. NEVER erase unresolved write outcomes."""
    # Legacy code may not have promoted an uncertain status to PENDING_KEY yet.
    # Promote it before removing the displayed status (logout/role change).
    status_pairs = (
        ("atlasquant_shadow_persistence_status", PENDING_KEYS[0]),
        ("atlasquant_research_evidence_status", PENDING_KEYS[1]),
    )
    for status_key, pending_key in status_pairs:
        status = state.get(status_key)
        if isinstance(status, Mapping) and (
            status.get("reason") in {"UNKNOWN_OUTCOME", "CONFLICT", "VALIDATION_REJECTED"}
            or status.get("reconciliation_required") is True
        ):
            if not isinstance(state.get(pending_key), Mapping):
                state[pending_key] = dict(status)
    if any(bool(state.get(k)) for k in PENDING_KEYS):
        state[QUARANTINE_KEY] = True
    for key in (*DISPLAY_KEYS, SCOPE_KEY):
        state.pop(key, None)


def private_read_decision(
    *,
    session: Mapping[str, Any] | None,
    users: Mapping[str, Any] | None,
    auth_required: bool,
    time_valid: bool,
    workspace_id: str,
    memberships: Any,
    policy_generation: str,
) -> tuple[bool, str]:
    """Pure authorization against server-supplied registry and policy inputs."""
    if not auth_required or not time_valid or not isinstance(session, Mapping):
        return False, ""
    if session.get("schema") != "ATLASQUANT_ACCESS_V1":
        return False, ""
    if session.get("role") != "ADMIN" or not has_permission(session, "admin:read"):
        return False, ""
    if not session_is_current(session, users):
        return False, ""
    username = session.get("username")
    if not isinstance(username, str) or not username:
        return False, ""
    if not isinstance(workspace_id, str) or not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]{2,63}", workspace_id):
        return False, ""
    if not isinstance(policy_generation, str) or not re.fullmatch(r"[1-9][0-9]{0,17}", policy_generation):
        return False, ""
    if not isinstance(memberships, dict):
        return False, ""
    members = memberships.get(workspace_id)
    if not isinstance(members, list) or not members or len(members) != len(set(str(x) for x in members)):
        return False, ""
    if any(not isinstance(item, str) or not item.strip() for item in members):
        return False, ""
    if username not in members:
        return False, ""
    fingerprint = credential_fingerprint(users[username])
    if not fingerprint:
        return False, ""
    payload = json.dumps(
        {
            "actor": username, "credential": fingerprint,
            "login_at": session.get("authenticated_at"),
            "workspace": workspace_id, "generation": policy_generation,
            "members": sorted(members),
        },
        sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")
    return True, hashlib.sha256(payload).hexdigest()


def private_read_allowed() -> bool:
    """Revalidate on every read; never trust UI access dictionaries or cache flags."""
    try:
        import streamlit as st
    except Exception:
        return False
    try:
        state = st.session_state
    except Exception:
        return False
    try:
        from atlasquant_access_panel import (
            access_required, configured_users, current_session,
            session_time_status, _setting,
        )
        session = current_session()
        users = configured_users()
        raw_memberships = _setting("ATLASQUANT_PRIVATE_MEMBERSHIPS_JSON", "")
        memberships = json.loads(raw_memberships) if raw_memberships else None
        allowed, binding = private_read_decision(
            session=session,
            users=users,
            auth_required=access_required(),
            time_valid=session_time_status(session, time.time()).get("valid") is True,
            workspace_id=_setting("ATLASQUANT_PRIVATE_WORKSPACE_ID", ""),
            memberships=memberships,
            policy_generation=_setting("ATLASQUANT_PRIVATE_POLICY_GENERATION", ""),
        )
        if not allowed or state.get(QUARANTINE_KEY) is True:
            clear_private_ui_state(state)
            return False
        previous = state.get(SCOPE_KEY)
        # No binding includes pre-migration sessions: NEVER trust cached private
        # rows that were hydrated before this gate existed.
        if previous is None or previous != binding:
            clear_private_ui_state(state)
            if state.get(QUARANTINE_KEY) is True:
                return False
        state[SCOPE_KEY] = binding
        return True
    except Exception:
        clear_private_ui_state(state)
        return False


def require_private_read() -> None:
    if not private_read_allowed():
        raise PermissionError("PRIVATE_READ_DENIED")
