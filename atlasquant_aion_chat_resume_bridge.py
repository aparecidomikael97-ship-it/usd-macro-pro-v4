"""Scoped, read-only conversation resume bridge for AION Chat.

This layer reconstructs bounded conversational context from the existing
aion_chat store. It never compacts, checkpoints, appends, promotes memory,
calls a provider, executes a tool, or performs an external action.

Its purpose is continuity: reopen the same scoped conversation later and
prepare the relevant recent/checkpoint/retrieved context for the next AION
turn, while making staleness and rehydration explicit.
"""
from __future__ import annotations

from hashlib import sha256
import json
from typing import Any, Mapping

from aion_chat.context import build_conversation_context
from aion_chat.models import Scope
from atlasquant_aion_chat_history_bridge import trusted_context_for_scope
from atlasquant_aion_chat_surface import conversation_identity_binding

SCHEMA = "ATLASQUANT_AION_CHAT_RESUME_CONTEXT_V1"
VERIFY_SCHEMA = "ATLASQUANT_AION_CHAT_RESUME_VERIFY_V1"
MIN_CONTEXT_BYTES = 512
MAX_CONTEXT_BYTES = 2_000_000
MAX_QUERY_CHARS = 2_000
MAX_RECENT_COUNT = 200
MAX_RETRIEVAL_COUNT = 200


def _clean(value: Any, limit: int) -> str:
    return " ".join(str(value or "").replace("\x00", "").split())[:limit]


def _canonical(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
        default=str,
    )


def _digest(value: Any) -> str:
    return sha256(_canonical(value).encode("utf-8")).hexdigest()


def _bounded_int(value: Any, *, minimum: int, maximum: int, name: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be an integer")
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if number < minimum or number > maximum:
        raise ValueError(f"{name} must be {minimum}..{maximum}")
    return number


def _query_fingerprint(query: str) -> str:
    """Bind retrieval intent without persisting raw query in the envelope."""
    return _digest({"query": query})


def _material_for_digest(envelope: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "conversation_id": envelope.get("conversation_id"),
        "identity_binding_digest": envelope.get("identity_binding_digest"),
        "message_count": envelope.get("message_count"),
        "checkpoint_id": envelope.get("checkpoint_id"),
        "summary_id": envelope.get("summary_id"),
        "query_fingerprint": envelope.get("query_fingerprint"),
        "budget_bytes": envelope.get("budget_bytes"),
        "recent_count": envelope.get("recent_count"),
        "retrieval_count": envelope.get("retrieval_count"),
        "context": envelope.get("context"),
    }


def prepare_resume_context(
    store: Any,
    scope: Scope,
    conversation_id: Any,
    *,
    query: Any = "",
    budget_bytes: int = 24_000,
    recent_count: int = 20,
    retrieval_count: int = 8,
) -> dict[str, Any]:
    """Build bounded resume context without mutating chat or Core state."""
    if not isinstance(scope, Scope):
        raise TypeError("trusted Scope required")

    cid = _clean(conversation_id, 120)
    if not cid:
        raise ValueError("conversation_id required")

    budget = _bounded_int(
        budget_bytes,
        minimum=MIN_CONTEXT_BYTES,
        maximum=MAX_CONTEXT_BYTES,
        name="budget_bytes",
    )
    recent_limit = _bounded_int(
        recent_count,
        minimum=1,
        maximum=MAX_RECENT_COUNT,
        name="recent_count",
    )
    retrieval_limit = _bounded_int(
        retrieval_count,
        minimum=1,
        maximum=MAX_RETRIEVAL_COUNT,
        name="retrieval_count",
    )
    clean_query = _clean(query, MAX_QUERY_CHARS)

    conversation = store.get_conversation(scope, cid)
    trusted = trusted_context_for_scope(scope, {"role": "USER"})
    binding = conversation_identity_binding(trusted, cid)
    if binding.get("complete") is not True:
        raise ValueError("identity binding incomplete")

    context = build_conversation_context(
        store,
        scope,
        cid,
        query=clean_query,
        budget_bytes=budget,
        recent_count=recent_limit,
        retrieval_count=retrieval_limit,
    )

    envelope: dict[str, Any] = {
        "schema": SCHEMA,
        "state": (
            "REHYDRATION_REQUIRED"
            if context.get("requires_rehydration") is True
            else "READY"
        ),
        "conversation_id": cid,
        "identity_binding_digest": str(binding.get("binding_digest") or ""),
        "identity_binding_complete": True,
        "message_count": int(conversation.message_count),
        "checkpoint_id": context.get("checkpoint_id"),
        "summary_id": context.get("summary_id"),
        "query_fingerprint": _query_fingerprint(clean_query),
        "query_stored": False,
        "budget_bytes": budget,
        "recent_count": recent_limit,
        "retrieval_count": retrieval_limit,
        "context": context,
        "context_digest": "",
        "automatic_compaction": False,
        "automatic_checkpoint_write": False,
        "core_checkpoint_write": False,
        "automatic_memory_promotion": False,
        "memory_promoted": False,
        "provider_called": False,
        "network_called": False,
        "tool_executed": False,
        "external_action_executed": False,
        "grants_authority": False,
        "executes_action": False,
    }
    envelope["context_digest"] = _digest(_material_for_digest(envelope))
    return envelope


def verify_resume_context(
    store: Any,
    scope: Scope,
    envelope: Mapping[str, Any],
    *,
    query: Any = "",
) -> dict[str, Any]:
    """Rebuild and compare the resume envelope; stale/tampered context fails closed."""
    if not isinstance(scope, Scope):
        raise TypeError("trusted Scope required")
    if not isinstance(envelope, Mapping):
        raise TypeError("resume envelope mapping required")

    blockers: list[str] = []
    supplied = dict(envelope)
    cid = _clean(supplied.get("conversation_id"), 120)
    if supplied.get("schema") != SCHEMA:
        blockers.append("SCHEMA_MISMATCH")
    if not cid:
        blockers.append("CONVERSATION_ID_MISSING")

    supplied_digest = _clean(supplied.get("context_digest"), 64)
    expected_embedded_digest = _digest(_material_for_digest(supplied))
    if supplied_digest != expected_embedded_digest:
        blockers.append("CONTEXT_DIGEST_MISMATCH")
        blockers.append("CONTEXT_STALE_OR_TAMPERED")

    clean_query = _clean(query, MAX_QUERY_CHARS)
    if supplied.get("query_fingerprint") != _query_fingerprint(clean_query):
        blockers.append("QUERY_FINGERPRINT_MISMATCH")

    current: dict[str, Any] | None = None
    if not blockers or blockers == ["CONTEXT_DIGEST_MISMATCH"]:
        try:
            current = prepare_resume_context(
                store,
                scope,
                cid,
                query=clean_query,
                budget_bytes=supplied.get("budget_bytes"),
                recent_count=supplied.get("recent_count"),
                retrieval_count=supplied.get("retrieval_count"),
            )
        except (LookupError, ValueError, TypeError):
            blockers.append("CURRENT_CONTEXT_UNAVAILABLE")

    if current is not None:
        if (
            supplied.get("identity_binding_digest")
            != current.get("identity_binding_digest")
        ):
            blockers.append("IDENTITY_BINDING_MISMATCH")
        if supplied.get("message_count") != current.get("message_count"):
            blockers.append("MESSAGE_COUNT_STALE")
        if supplied.get("checkpoint_id") != current.get("checkpoint_id"):
            blockers.append("CHECKPOINT_STALE")
        if supplied.get("summary_id") != current.get("summary_id"):
            blockers.append("SUMMARY_STALE")
        if supplied_digest != current.get("context_digest"):
            blockers.append("CONTEXT_STALE_OR_TAMPERED")

    blockers = list(dict.fromkeys(blockers))
    return {
        "schema": VERIFY_SCHEMA,
        "state": "CURRENT" if not blockers else "STALE_OR_INVALID",
        "current": not blockers,
        "blockers": blockers,
        "conversation_id": cid,
        "identity_binding_digest": _clean(
            supplied.get("identity_binding_digest"), 64
        ),
        "supplied_context_digest": supplied_digest,
        "current_context_digest": (
            str(current.get("context_digest") or "") if current else ""
        ),
        "automatic_compaction": False,
        "automatic_checkpoint_write": False,
        "memory_promoted": False,
        "provider_called": False,
        "network_called": False,
        "external_action_executed": False,
        "grants_authority": False,
        "executes_action": False,
    }


__all__ = [
    "SCHEMA",
    "VERIFY_SCHEMA",
    "prepare_resume_context",
    "verify_resume_context",
]
