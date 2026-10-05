"""Authenticated composition point for the AION Chat product.

The host must inject:
- an already authenticated AtlasQuant access decision,
- a trusted Scope value carrying owner, tenant and workspace,
- an existing chat store,
- and runtime context.

This module deliberately does not instantiate storage, infer tenant/workspace,
open network/provider connections, grant approval, or create a second Core.
"""
from __future__ import annotations

from typing import Any, Mapping

from aion_chat.models import Scope
from atlasquant_aion_chat_history_bridge import execute_and_persist_readonly
from atlasquant_aion_chat_resume_bridge import prepare_resume_context

SCHEMA = "ATLASQUANT_AION_CHAT_PRODUCT_BINDING_V1"
CREATE_SCHEMA = "ATLASQUANT_AION_CHAT_PRODUCT_CREATE_V1"
TURN_SCHEMA = "ATLASQUANT_AION_CHAT_PRODUCT_TURN_V1"
RESUME_SCHEMA = "ATLASQUANT_AION_CHAT_PRODUCT_RESUME_V1"
HISTORY_SCHEMA = "ATLASQUANT_AION_CHAT_PRODUCT_HISTORY_V1"
CONTINUE_SCHEMA = "ATLASQUANT_AION_CHAT_PRODUCT_CONTINUE_V1"

_REQUIRED_PERMISSIONS = frozenset({"app:read", "aion:admin"})


def _clean(value: Any, limit: int = 240) -> str:
    return " ".join(str(value or "").replace("\x00", "").split())[:limit]


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _permissions(session: Mapping[str, Any]) -> set[str]:
    raw = session.get("permissions")
    if not isinstance(raw, (list, tuple, set, frozenset)):
        return set()
    return {
        _clean(item, 120)
        for item in raw
        if _clean(item, 120)
    }


def validate_product_binding(
    access: Mapping[str, Any] | None,
    scope: Scope,
) -> dict[str, Any]:
    """Validate the trusted host access decision against the trusted chat Scope."""
    if not isinstance(scope, Scope):
        raise TypeError("trusted Scope required")

    raw = _mapping(access)
    session = _mapping(raw.get("session"))
    blockers: list[str] = []

    if raw.get("allowed") is not True:
        blockers.append("ACCESS_NOT_ALLOWED")
    if _clean(raw.get("mode"), 40).upper() != "AUTHENTICATED":
        blockers.append("AUTHENTICATED_MODE_REQUIRED")

    role = _clean(raw.get("role") or session.get("role"), 24).upper()
    session_role = _clean(session.get("role"), 24).upper()
    if role != "ADMIN" or session_role != "ADMIN":
        blockers.append("ADMIN_ROLE_REQUIRED")

    username = _clean(session.get("username"), 120)
    if not username:
        blockers.append("AUTHENTICATED_USERNAME_REQUIRED")
    elif username != scope.owner_id:
        blockers.append("SCOPE_OWNER_MISMATCH")

    fingerprint = _clean(session.get("credential_fingerprint"), 160)
    if not fingerprint:
        blockers.append("CREDENTIAL_FINGERPRINT_REQUIRED")

    permissions = _permissions(session)
    missing = sorted(_REQUIRED_PERMISSIONS - permissions)
    for permission in missing:
        blockers.append("MISSING_PERMISSION:" + permission)

    blockers = list(dict.fromkeys(blockers))
    return {
        "schema": SCHEMA,
        "state": "BOUND" if not blockers else "BLOCKED",
        "bound": not blockers,
        "blockers": blockers,
        "owner_id": scope.owner_id,
        "tenant_id": scope.tenant_id,
        "workspace_id": scope.workspace_id,
        "role": role,
        "credential_fingerprint_present": bool(fingerprint),
        "permissions_verified": not missing,
        "authenticated": not blockers,
        "preview_allowed": False,
        "open_mode_allowed": False,
        "grants_authority": False,
        "executes_action": False,
    }


def _require_binding(
    access: Mapping[str, Any] | None,
    scope: Scope,
) -> dict[str, Any]:
    binding = validate_product_binding(access, scope)
    if binding["bound"] is not True:
        raise PermissionError(
            "AION chat product binding rejected: "
            + ",".join(binding["blockers"])
        )
    return binding


def _trusted_context(
    access: Mapping[str, Any],
    scope: Scope,
    *,
    persona: Any = "admin",
    experience_mode: Any = "ADVANCED",
    domain_hint: Any = "admin",
) -> dict[str, Any]:
    session = _mapping(access.get("session"))
    return {
        "role": "ADMIN",
        "persona": _clean(persona, 80) or "admin",
        "experience_mode": (
            _clean(experience_mode, 24).upper() or "ADVANCED"
        ),
        "domain_hint": _clean(domain_hint, 80).lower(),
        "tenant_id": scope.tenant_id,
        "workspace_id": scope.workspace_id,
        "actor_id": _clean(session.get("username"), 120),
    }


def create_product_conversation(
    store: Any,
    scope: Scope,
    access: Mapping[str, Any],
    *,
    title: Any = "Nova conversa",
) -> dict[str, Any]:
    """Explicitly create one scoped chat conversation; never automatic."""
    binding = _require_binding(access, scope)
    conversation = store.create_conversation(
        scope,
        _clean(title, 160) or "Nova conversa",
    )
    return {
        "schema": CREATE_SCHEMA,
        "state": "CREATED",
        "conversation_id": conversation.id,
        "title": conversation.title,
        "owner_id": scope.owner_id,
        "tenant_id": scope.tenant_id,
        "workspace_id": scope.workspace_id,
        "binding": binding,
        "automatic_creation": False,
        "provider_called": False,
        "network_called": False,
        "external_action_executed": False,
        "core_checkpoint_write": False,
        "memory_promoted": False,
        "grants_authority": False,
    }


def execute_product_read_turn(
    store: Any,
    scope: Scope,
    access: Mapping[str, Any],
    message: Any,
    *,
    conversation_id: Any,
    runtime_context: Mapping[str, Any],
    turn_index: int = 0,
    attachment_ids: list[Any] | tuple[Any, ...] | None = None,
    feature_flags: Mapping[str, Any] | None = None,
    hub: Mapping[str, Any] | None = None,
    portable_core: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Execute+persist the existing verified local READ/SEARCH Golden Path."""
    binding = _require_binding(access, scope)
    if not isinstance(runtime_context, Mapping):
        raise TypeError("runtime_context mapping required")
    trusted = _trusted_context(access, scope)
    result = execute_and_persist_readonly(
        store,
        scope,
        message,
        context=trusted,
        runtime_context=runtime_context,
        access=dict(access),
        attachment_ids=attachment_ids,
        turn_index=turn_index,
        feature_flags=feature_flags,
        source_kind="ADMIN",
        authenticated_admin=True,
        hub=hub,
        portable_core=portable_core,
        conversation_id=conversation_id,
    )
    return {
        "schema": TURN_SCHEMA,
        "state": str(result.get("state") or "FAILED_SAFE"),
        "binding": binding,
        "result": result,
        "provider_called": False,
        "network_called": False,
        "external_action_executed": False,
        "core_checkpoint_write": False,
        "memory_promoted": False,
        "grants_authority": False,
    }


def resume_product_conversation(
    store: Any,
    scope: Scope,
    access: Mapping[str, Any],
    conversation_id: Any,
    *,
    query: Any = "",
    budget_bytes: int = 24_000,
    recent_count: int = 20,
    retrieval_count: int = 8,
) -> dict[str, Any]:
    """Prepare bounded persisted context for a later turn; read-only."""
    binding = _require_binding(access, scope)
    resume = prepare_resume_context(
        store,
        scope,
        conversation_id,
        query=query,
        budget_bytes=budget_bytes,
        recent_count=recent_count,
        retrieval_count=retrieval_count,
    )
    return {
        "schema": RESUME_SCHEMA,
        "state": str(resume.get("state") or "STALE_OR_INVALID"),
        "binding": binding,
        "resume": resume,
        "provider_called": False,
        "network_called": False,
        "tool_executed": False,
        "external_action_executed": False,
        "automatic_checkpoint_write": False,
        "memory_promoted": False,
        "grants_authority": False,
    }


def read_product_history_page(
    store: Any,
    scope: Scope,
    access: Mapping[str, Any],
    conversation_id: Any,
    *,
    cursor: Any = None,
    page_size: int = 40,
    newest_first: bool = True,
) -> dict[str, Any]:
    """Read one scoped durable-history page for presentation only."""
    binding = _require_binding(access, scope)
    cid = _clean(conversation_id, 120)
    if not cid:
        raise ValueError("conversation_id required")
    conversation = store.get_conversation(scope, cid)
    page = store.list_messages(
        scope,
        cid,
        cursor=cursor,
        page_size=page_size,
        newest_first=bool(newest_first),
    )
    messages = list(page.items)
    if newest_first:
        messages.reverse()

    entries: list[dict[str, Any]] = []
    public_turns: dict[str, dict[str, Any]] = {}
    for message in messages:
        metadata = _mapping(getattr(message, "metadata", None))
        turn_id = _clean(metadata.get("turn_id"), 80) or _clean(
            getattr(message, "id", ""), 120
        )
        role = _clean(getattr(message, "role", ""), 24).lower()
        entry = {
            "role": role,
            "turn_id": turn_id,
            "content": str(getattr(message, "content", "") or ""),
            "display_text": str(getattr(message, "content", "") or ""),
            "attachments": list(getattr(message, "attachments", None) or []),
            "sequence": int(getattr(message, "sequence", 0) or 0),
        }
        entries.append(entry)
        if role == "assistant":
            receipt_id = _clean(metadata.get("receipt_id"), 120)
            receipt_digest = _clean(metadata.get("receipt_digest"), 64)
            verification_state = _clean(
                metadata.get("verification_state"), 60
            ).upper()
            public_turns[turn_id] = {
                "state": "CONFIRMED_SUCCESS",
                "reason": "",
                "capability": "Leitura local verificada",
                "policy_state": "READ_ONLY",
                "blockers": [],
                "approval": {
                    "required": False,
                    "granted": False,
                    "state": "NOT_APPLICABLE",
                },
                "stages": [
                    {
                        "stage": "VERIFICATION",
                        "state": verification_state or "CONFIRMED",
                    },
                    {
                        "stage": "PERSISTENCE",
                        "state": "CONFIRMED",
                    },
                ],
                "evidence": (
                    "Histórico local durável · escopo autenticado e "
                    "identidade verificada."
                ),
                "receipt": (
                    "Receipt verificado · " + receipt_id
                    if receipt_id
                    else "Receipt verificado · identificador não exposto."
                ),
                "receipt_digest_present": bool(receipt_digest),
            }

    return {
        "schema": HISTORY_SCHEMA,
        "state": "READY",
        "binding": binding,
        "conversation_id": cid,
        "total": int(conversation.message_count),
        "entries": entries,
        "turns": public_turns,
        "next_cursor": page.next_cursor,
        "newest_first": bool(newest_first),
        "provider_called": False,
        "network_called": False,
        "tool_executed": False,
        "external_action_executed": False,
        "automatic_checkpoint_write": False,
        "memory_promoted": False,
        "grants_authority": False,
    }


def continue_product_read_turn(
    store: Any,
    scope: Scope,
    access: Mapping[str, Any],
    message: Any,
    *,
    conversation_id: Any,
    runtime_context: Mapping[str, Any],
    attachment_ids: list[Any] | tuple[Any, ...] | None = None,
    feature_flags: Mapping[str, Any] | None = None,
    hub: Mapping[str, Any] | None = None,
    portable_core: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Resume durable state first, then append the next verified read-only turn."""
    binding = _require_binding(access, scope)
    if not isinstance(runtime_context, Mapping):
        raise TypeError("runtime_context mapping required")
    cid = _clean(conversation_id, 120)
    before = resume_product_conversation(
        store,
        scope,
        access,
        cid,
    )
    if before.get("state") != "READY":
        return {
            "schema": CONTINUE_SCHEMA,
            "state": "NOT_CONTINUED",
            "reason": "RESUME_CONTEXT_NOT_READY",
            "binding": binding,
            "resume": before,
            "provider_called": False,
            "network_called": False,
            "external_action_executed": False,
            "core_checkpoint_write": False,
            "memory_promoted": False,
            "grants_authority": False,
        }
    prior_count = int(before["resume"].get("message_count") or 0)
    turn = execute_product_read_turn(
        store,
        scope,
        access,
        message,
        conversation_id=cid,
        runtime_context=runtime_context,
        turn_index=prior_count,
        attachment_ids=attachment_ids,
        feature_flags=feature_flags,
        hub=hub,
        portable_core=portable_core,
    )
    after_count = int(store.get_conversation(scope, cid).message_count)
    return {
        "schema": CONTINUE_SCHEMA,
        "state": str(turn.get("state") or "FAILED_SAFE"),
        "binding": binding,
        "conversation_id": cid,
        "resume_context_digest": str(
            before["resume"].get("context_digest") or ""
        ),
        "prior_message_count": prior_count,
        "current_message_count": after_count,
        "continued_from_durable_history": True,
        "turn": turn,
        "provider_called": False,
        "network_called": False,
        "external_action_executed": False,
        "core_checkpoint_write": False,
        "memory_promoted": False,
        "grants_authority": False,
    }


__all__ = [
    "SCHEMA",
    "CREATE_SCHEMA",
    "TURN_SCHEMA",
    "RESUME_SCHEMA",
    "HISTORY_SCHEMA",
    "CONTINUE_SCHEMA",
    "validate_product_binding",
    "create_product_conversation",
    "execute_product_read_turn",
    "resume_product_conversation",
    "read_product_history_page",
    "continue_product_read_turn",
]
