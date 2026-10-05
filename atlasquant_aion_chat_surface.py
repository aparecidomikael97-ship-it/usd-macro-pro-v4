"""AION Chat Command Surface V1.

Pure planning contract between the conversational UX and the existing AION Core.
It intentionally does not execute tools, call providers/network, persist memory,
or grant approval. A chat turn is converted into a deterministic, auditable
envelope that exposes what the Core understood and what would have to happen
next in the Golden Path.

Execution remains owned by the existing guarded executors and approval flows.
"""
from __future__ import annotations

from hashlib import sha256
import json
import re
from typing import Any, Mapping, Sequence

from atlasquant_aion_command_orchestrator import orchestrate_local_command
from atlasquant_aion_orchestrator import orchestrate as orchestrate_aion_core

SCHEMA = "ATLASQUANT_AION_CHAT_TURN_V1"
HISTORY_SCHEMA = "ATLASQUANT_AION_CHAT_HISTORY_V1"
IDENTITY_BINDING_SCHEMA = "ATLASQUANT_AION_CHAT_IDENTITY_BINDING_V1"
MAX_MESSAGE_CHARS = 8000
MAX_ATTACHMENTS = 16
MAX_ATTACHMENT_NAME = 240
MAX_ATTACHMENT_MIME = 120
MAX_ATTACHMENT_KIND = 40
MAX_ATTACHMENT_SIZE_BYTES = 512 * 1024 * 1024
MAX_IN_MEMORY_HISTORY_ENTRIES = 2000

_CONTENT_KEYS = frozenset({
    "content", "bytes", "data", "payload", "base64", "text", "body",
})
_SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")


def _clean_with_truncation(value: Any, limit: int) -> tuple[str, bool]:
    normalized = " ".join(str(value or "").replace("\x00", "").split())
    return normalized[:limit], len(normalized) > limit


def _clean(value: Any, limit: int) -> str:
    return _clean_with_truncation(value, limit)[0]


def _message_text(value: Any, limit: int) -> str:
    """Preserve conversational formatting while normalizing line endings/NUL."""
    text = str(value or "").replace("\x00", "")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return text[:limit]


def _stable_id(prefix: str, payload: Mapping[str, Any]) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return prefix + "-" + sha256(raw.encode("utf-8")).hexdigest()[:24].upper()


def _safe_context(context: Mapping[str, Any] | None) -> dict[str, Any]:
    raw = dict(context or {})
    return {
        "role": _clean(raw.get("role") or "USER", 24).upper() or "USER",
        "persona": _clean(raw.get("persona") or "", 80),
        "experience_mode": _clean(raw.get("experience_mode") or "BEGINNER", 24).upper() or "BEGINNER",
        "domain_hint": _clean(raw.get("domain_hint") or "", 80).lower(),
        "tenant_id": _clean(raw.get("tenant_id") or "", 120),
        "workspace_id": _clean(raw.get("workspace_id") or "", 120),
        "actor_id": _clean(raw.get("actor_id") or "", 120),
    }


def conversation_identity_binding(
    context: Mapping[str, Any] | None,
    conversation_id: Any,
) -> dict[str, Any]:
    """Bind a logical conversation to tenant/workspace/actor without granting authority."""
    ctx = _safe_context(context)
    conv_id = _clean(conversation_id, 120)
    material = {
        "schema": IDENTITY_BINDING_SCHEMA,
        "tenant_id": ctx["tenant_id"],
        "workspace_id": ctx["workspace_id"],
        "actor_id": ctx["actor_id"],
        "conversation_id": conv_id,
    }
    complete = all(
        bool(material[key])
        for key in ("tenant_id", "workspace_id", "actor_id", "conversation_id")
    )
    raw = json.dumps(
        material,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return {
        **material,
        "complete": complete,
        "binding_digest": sha256(raw.encode("utf-8")).hexdigest(),
        "grants_authority": False,
        "persists_externally": False,
    }


def normalize_attachment_metadata(
    attachments: Sequence[Mapping[str, Any]] | None,
) -> tuple[dict[str, Any], ...]:
    """Keep bounded metadata only and make every technical truncation explicit."""
    raw_items = list(attachments or [])
    normalized: list[dict[str, Any]] = []
    for raw in raw_items[:MAX_ATTACHMENTS]:
        if not isinstance(raw, Mapping):
            continue

        name, name_truncated = _clean_with_truncation(
            raw.get("name") or raw.get("filename") or "attachment",
            MAX_ATTACHMENT_NAME,
        )
        mime_type, mime_type_truncated = _clean_with_truncation(
            raw.get("mime_type") or raw.get("content_type") or "",
            MAX_ATTACHMENT_MIME,
        )
        mime_type = mime_type.lower()
        kind, kind_truncated = _clean_with_truncation(
            raw.get("kind") or "FILE",
            MAX_ATTACHMENT_KIND,
        )
        kind = kind.upper() or "FILE"

        raw_size = raw.get("size_bytes")
        if raw_size in (None, ""):
            raw_size = raw.get("size") or 0
        size_invalid = isinstance(raw_size, bool)
        try:
            parsed_size = 0 if size_invalid else int(raw_size)
        except (TypeError, ValueError):
            parsed_size = 0
            size_invalid = True
        size = max(0, min(parsed_size, MAX_ATTACHMENT_SIZE_BYTES))
        size_clamped = size_invalid or size != parsed_size

        digest_text, digest_truncated = _clean_with_truncation(
            raw.get("sha256") or "",
            64,
        )
        digest_text = digest_text.lower()
        digest_invalid = bool(digest_text) and not _SHA256_RE.fullmatch(digest_text)
        digest = (
            digest_text
            if not digest_invalid
            and not digest_truncated
            and len(digest_text) == 64
            else ""
        )
        if not digest_text:
            digest_invalid = False

        content_supplied = any(
            key in raw and raw.get(key) not in (None, "", b"")
            for key in _CONTENT_KEYS
        )
        metadata_truncated = any((
            name_truncated,
            mime_type_truncated,
            kind_truncated,
            digest_truncated,
            size_clamped,
        ))
        normalized.append({
            "name": name,
            "mime_type": mime_type,
            "kind": kind,
            "size_bytes": size,
            "sha256": digest,
            "name_truncated": name_truncated,
            "mime_type_truncated": mime_type_truncated,
            "kind_truncated": kind_truncated,
            "size_clamped": size_clamped,
            "sha256_invalid": digest_invalid or digest_truncated,
            "metadata_truncated": metadata_truncated,
            "content_supplied_but_not_accepted": content_supplied,
            "content_accepted": False,
        })
    return tuple(normalized)


def _conversation_id(context: Mapping[str, Any], requested: Any) -> str:
    explicit = _clean(requested, 120)
    if explicit:
        return explicit
    return _stable_id("AION-CONV", {
        "tenant_id": context.get("tenant_id") or "",
        "workspace_id": context.get("workspace_id") or "",
        "actor_id": context.get("actor_id") or "",
        "persona": context.get("persona") or "",
    })


def _empty_turn(
    *,
    context: Mapping[str, Any],
    conversation_id: str,
    identity_binding: Mapping[str, Any],
    turn_index: int,
    reason: str,
) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "state": "REJECTED",
        "reason": reason,
        "conversation_id": conversation_id,
        "identity_binding": dict(identity_binding),
        "identity_binding_digest": _clean(identity_binding.get("binding_digest"), 64),
        "identity_binding_complete": identity_binding.get("complete") is True,
        "turn_index": turn_index,
        "turn_id": _stable_id("AION-TURN", {
            "conversation_id": conversation_id,
            "identity_binding_digest": identity_binding.get("binding_digest") or "",
            "turn_index": turn_index,
            "reason": reason,
        }),
        "message": "",
        "canonical_message": "",
        "message_digest": "",
        "canonical_message_digest": "",
        "attachments": [],
        "context": dict(context),
        "selected_capability": {},
        "local_tool_preview": {},
        "core_preflight": {},
        "approval": {
            "required": False,
            "granted": False,
            "state": "NOT_APPLICABLE",
        },
        "golden_path": [],
        "may_execute": False,
        "execution_authorized": False,
        "external_action_executed": False,
        "provider_called": False,
        "network_called": False,
        "automatic_memory_write": False,
        "automatic_learning_change": False,
        "receipt_created": False,
    }


def build_chat_turn(
    message: Any,
    *,
    context: Mapping[str, Any] | None = None,
    attachments: Sequence[Mapping[str, Any]] | None = None,
    conversation_id: Any = "",
    turn_index: int = 0,
    feature_flags: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a fail-closed chat-turn plan without executing anything."""
    ctx = _safe_context(context)
    conv_id = _conversation_id(ctx, conversation_id)
    identity_binding = conversation_identity_binding(ctx, conv_id)
    try:
        index = max(0, int(turn_index))
    except (TypeError, ValueError):
        index = 0
    text = _message_text(message, MAX_MESSAGE_CHARS)
    if not text.strip():
        return _empty_turn(
            context=ctx,
            conversation_id=conv_id,
            identity_binding=identity_binding,
            turn_index=index,
            reason="EMPTY_MESSAGE",
        )

    canonical_text = _clean(text, MAX_MESSAGE_CHARS)
    raw_attachments = list(attachments or [])
    metadata = normalize_attachment_metadata(raw_attachments)
    attachment_budget = {
        "received_count": len(raw_attachments),
        "accepted_count": len(metadata),
        "max_count": MAX_ATTACHMENTS,
        "overflow": len(raw_attachments) > MAX_ATTACHMENTS,
        "metadata_truncated": any(
            item.get("metadata_truncated") is True for item in metadata
        ),
        "content_rejected": any(
            item.get("content_supplied_but_not_accepted") is True
            for item in metadata
        ),
    }
    core = orchestrate_aion_core(
        canonical_text,
        context={
            "role": ctx["role"],
            "persona": ctx["persona"],
            "experience_mode": ctx["experience_mode"],
            "domain_hint": ctx["domain_hint"],
        },
        feature_flags=feature_flags,
    )
    local = orchestrate_local_command(canonical_text, execute=False)

    core_decision = core.get("decision") if isinstance(core.get("decision"), Mapping) else {}
    blockers = [str(item) for item in list(core_decision.get("blockers") or [])]
    core_state = str(core_decision.get("state") or "BLOCKED").upper()
    local_state = str(local.get("state") or "NO_MATCH").upper()
    requires_approval = bool(
        core_decision.get("requires_human_confirmation") is True
        or "EXPLICIT_APPROVAL_REQUIRED" in blockers
    )

    hard_blockers = [
        item for item in blockers
        if item not in {"EXPLICIT_APPROVAL_REQUIRED", "GUARDIAN_DENIED"}
    ]
    if local_state == "BLOCKED_INTENT":
        state = "BLOCKED"
        reason = "LOCAL_COMMAND_POLICY_BLOCK"
        approval_state = "NOT_SUFFICIENT"
    elif core_state == "BLOCKED" and hard_blockers:
        state = "BLOCKED"
        reason = "CORE_POLICY_BLOCK"
        approval_state = "NOT_SUFFICIENT"
    elif requires_approval:
        state = "WAITING_APPROVAL"
        reason = "EXPLICIT_APPROVAL_REQUIRED"
        approval_state = "REQUIRED"
    elif core_state in {"READY", "REVIEW"}:
        state = "PLANNED"
        reason = "CHAT_TURN_PREFLIGHT_COMPLETE"
        approval_state = "NOT_REQUIRED"
    else:
        state = "BLOCKED"
        reason = "CORE_NOT_READY"
        approval_state = "NOT_SUFFICIENT"

    if attachment_budget["overflow"] is True:
        state = "BLOCKED"
        reason = "ATTACHMENT_BUDGET_EXCEEDED"
        approval_state = "NOT_SUFFICIENT"

    selected = (
        dict(core.get("selected_capability"))
        if isinstance(core.get("selected_capability"), Mapping)
        else {}
    )
    local_tool_ids = [str(item) for item in list(local.get("tool_ids") or []) if str(item)]

    stages = [
        {"stage": "CONVERSATION", "state": "RECEIVED", "executes_action": False},
        {"stage": "INTENT", "state": "ASSESSED", "executes_action": False},
        {
            "stage": "CONTEXT_MEMORY",
            "state": "PLANNED",
            "executes_action": False,
        },
        {
            "stage": "EVIDENCE",
            "state": "PLANNED",
            "executes_action": False,
        },
        {
            "stage": "CAPABILITY",
            "state": "SELECTED" if selected else "UNRESOLVED",
            "capability_id": str(selected.get("capability_id") or ""),
            "executes_action": False,
        },
        {
            "stage": "POLICY",
            "state": "BLOCKED" if state == "BLOCKED" else "CHECKED",
            "blockers": blockers,
            "executes_action": False,
        },
        {
            "stage": "APPROVAL",
            "state": approval_state,
            "executes_action": False,
        },
        {"stage": "EXECUTION", "state": "NOT_STARTED", "executes_action": False},
        {"stage": "VERIFICATION", "state": "NOT_STARTED", "executes_action": False},
        {"stage": "RECEIPT", "state": "NOT_CREATED", "executes_action": False},
        {"stage": "OUTCOME", "state": "NOT_RECORDED", "executes_action": False},
        {"stage": "MEMORY_LESSON", "state": "NOT_PROMOTED", "executes_action": False},
    ]

    message_digest = sha256(text.encode("utf-8")).hexdigest()
    canonical_message_digest = sha256(
        canonical_text.encode("utf-8")
    ).hexdigest()
    turn_id = _stable_id("AION-TURN", {
        "conversation_id": conv_id,
        "identity_binding_digest": identity_binding["binding_digest"],
        "turn_index": index,
        "message_digest": message_digest,
        "attachments": metadata,
    })

    return {
        "schema": SCHEMA,
        "state": state,
        "reason": reason,
        "conversation_id": conv_id,
        "identity_binding": dict(identity_binding),
        "identity_binding_digest": identity_binding["binding_digest"],
        "identity_binding_complete": identity_binding["complete"],
        "turn_index": index,
        "turn_id": turn_id,
        "message": text,
        "canonical_message": canonical_text,
        "message_digest": message_digest,
        "canonical_message_digest": canonical_message_digest,
        "attachments": [dict(item) for item in metadata],
        "attachment_budget": attachment_budget,
        "context": ctx,
        "selected_capability": selected,
        "local_tool_ids": local_tool_ids,
        "local_tool_preview": local,
        "core_preflight": core,
        "approval": {
            "required": requires_approval,
            "granted": False,
            "state": approval_state,
        },
        "golden_path": stages,
        "may_execute": False,
        "execution_authorized": False,
        "external_action_executed": False,
        "provider_called": False,
        "network_called": False,
        "automatic_memory_write": False,
        "automatic_learning_change": False,
        "receipt_created": False,
        "private_chain_of_thought_exposed": False,
    }


def append_chat_history(
    history: Sequence[Mapping[str, Any]] | None,
    turn: Mapping[str, Any],
    *,
    assistant_text: Any = "",
) -> dict[str, Any]:
    """Append one logical pair to the bounded in-memory helper.

    This helper is not the durable product history. The durable scoped chat
    store remains the source for long-lived/unbounded product continuity.
    The in-memory helper never silently drops old rows: when its technical
    budget is exhausted it fails before mutation so the host can use/reopen
    the durable store instead.
    """
    if history is not None and len(history) > MAX_IN_MEMORY_HISTORY_ENTRIES:
        raise ValueError(
            "in-memory history budget exceeded; durable chat store required"
        )
    answer = _message_text(assistant_text, 16000)
    additions = 1 + (1 if answer.strip() else 0)
    if history is not None and len(history) + additions > MAX_IN_MEMORY_HISTORY_ENTRIES:
        raise ValueError(
            "in-memory history budget exceeded; durable chat store required"
        )
    rows = [dict(item) for item in list(history or []) if isinstance(item, Mapping)]
    if len(rows) + additions > MAX_IN_MEMORY_HISTORY_ENTRIES:
        raise ValueError(
            "in-memory history budget exceeded; durable chat store required"
        )

    rows.append({
        "role": "user",
        "turn_id": _clean(turn.get("turn_id") or "", 80),
        "conversation_id": _clean(turn.get("conversation_id") or "", 120),
        "identity_binding_digest": _clean(turn.get("identity_binding_digest") or "", 64),
        "content": _message_text(turn.get("message") or "", MAX_MESSAGE_CHARS),
        "state": _clean(turn.get("state") or "", 40),
    })
    if answer.strip():
        rows.append({
            "role": "assistant",
            "turn_id": _clean(turn.get("turn_id") or "", 80),
            "conversation_id": _clean(turn.get("conversation_id") or "", 120),
            "identity_binding_digest": _clean(turn.get("identity_binding_digest") or "", 64),
            "content": answer,
            "state": "RESPONSE_RECORDED",
        })
    return {
        "schema": HISTORY_SCHEMA,
        "conversation_id": _clean(turn.get("conversation_id") or "", 120),
        "identity_binding_digest": _clean(turn.get("identity_binding_digest") or "", 64),
        "identity_binding_complete": turn.get("identity_binding_complete") is True,
        "entries": rows,
        "entry_count": len(rows),
        "history_budget": {
            "kind": "IN_MEMORY_HELPER_ONLY",
            "max_entries": MAX_IN_MEMORY_HISTORY_ENTRIES,
            "used_entries": len(rows),
            "remaining_entries": MAX_IN_MEMORY_HISTORY_ENTRIES - len(rows),
            "durable_store_required_at_limit": True,
            "rows_dropped": 0,
        },
        "persists_externally": False,
        "automatic_memory_write": False,
    }


__all__ = [
    "SCHEMA",
    "HISTORY_SCHEMA",
    "IDENTITY_BINDING_SCHEMA",
    "MAX_MESSAGE_CHARS",
    "MAX_ATTACHMENTS",
    "MAX_ATTACHMENT_NAME",
    "MAX_ATTACHMENT_MIME",
    "MAX_ATTACHMENT_KIND",
    "MAX_ATTACHMENT_SIZE_BYTES",
    "MAX_IN_MEMORY_HISTORY_ENTRIES",
    "normalize_attachment_metadata",
    "conversation_identity_binding",
    "build_chat_turn",
    "append_chat_history",
]
