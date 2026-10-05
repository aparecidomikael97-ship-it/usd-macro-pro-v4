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
MAX_MESSAGE_CHARS = 8000
MAX_ATTACHMENTS = 16
MAX_ATTACHMENT_NAME = 240
MAX_ATTACHMENT_SIZE_BYTES = 512 * 1024 * 1024

_CONTENT_KEYS = frozenset({
    "content", "bytes", "data", "payload", "base64", "text", "body",
})
_SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")


def _clean(value: Any, limit: int) -> str:
    return " ".join(str(value or "").replace("\x00", "").split())[:limit]


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


def normalize_attachment_metadata(
    attachments: Sequence[Mapping[str, Any]] | None,
) -> tuple[dict[str, Any], ...]:
    """Keep metadata only. File bodies are never accepted by this contract."""
    normalized: list[dict[str, Any]] = []
    for raw in list(attachments or [])[:MAX_ATTACHMENTS]:
        if not isinstance(raw, Mapping):
            continue
        name = _clean(raw.get("name") or raw.get("filename") or "attachment", MAX_ATTACHMENT_NAME)
        mime_type = _clean(raw.get("mime_type") or raw.get("content_type") or "", 120).lower()
        kind = _clean(raw.get("kind") or "FILE", 40).upper() or "FILE"
        try:
            size = int(raw.get("size_bytes") or raw.get("size") or 0)
        except (TypeError, ValueError):
            size = 0
        size = max(0, min(size, MAX_ATTACHMENT_SIZE_BYTES))
        digest = _clean(raw.get("sha256") or "", 64).lower()
        digest = digest if _SHA256_RE.fullmatch(digest) else ""
        content_supplied = any(
            key in raw and raw.get(key) not in (None, "", b"")
            for key in _CONTENT_KEYS
        )
        normalized.append({
            "name": name,
            "mime_type": mime_type,
            "kind": kind,
            "size_bytes": size,
            "sha256": digest,
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
    turn_index: int,
    reason: str,
) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "state": "REJECTED",
        "reason": reason,
        "conversation_id": conversation_id,
        "turn_index": turn_index,
        "turn_id": _stable_id("AION-TURN", {
            "conversation_id": conversation_id,
            "turn_index": turn_index,
            "reason": reason,
        }),
        "message": "",
        "message_digest": "",
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
    try:
        index = max(0, int(turn_index))
    except (TypeError, ValueError):
        index = 0
    text = _clean(message, MAX_MESSAGE_CHARS)
    if not text:
        return _empty_turn(
            context=ctx,
            conversation_id=conv_id,
            turn_index=index,
            reason="EMPTY_MESSAGE",
        )

    metadata = normalize_attachment_metadata(attachments)
    core = orchestrate_aion_core(
        text,
        context={
            "role": ctx["role"],
            "persona": ctx["persona"],
            "experience_mode": ctx["experience_mode"],
            "domain_hint": ctx["domain_hint"],
        },
        feature_flags=feature_flags,
    )
    local = orchestrate_local_command(text, execute=False)

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
    turn_id = _stable_id("AION-TURN", {
        "conversation_id": conv_id,
        "turn_index": index,
        "message_digest": message_digest,
        "attachments": metadata,
    })

    return {
        "schema": SCHEMA,
        "state": state,
        "reason": reason,
        "conversation_id": conv_id,
        "turn_index": index,
        "turn_id": turn_id,
        "message": text,
        "message_digest": message_digest,
        "attachments": [dict(item) for item in metadata],
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
    """Append a turn without truncating prior conversation history.

    This is an in-memory structure only; durable persistence belongs to a later
    explicitly approved persistence adapter.
    """
    rows = [dict(item) for item in list(history or []) if isinstance(item, Mapping)]
    rows.append({
        "role": "user",
        "turn_id": _clean(turn.get("turn_id") or "", 80),
        "conversation_id": _clean(turn.get("conversation_id") or "", 120),
        "content": _clean(turn.get("message") or "", MAX_MESSAGE_CHARS),
        "state": _clean(turn.get("state") or "", 40),
    })
    answer = _clean(assistant_text, 16000)
    if answer:
        rows.append({
            "role": "assistant",
            "turn_id": _clean(turn.get("turn_id") or "", 80),
            "conversation_id": _clean(turn.get("conversation_id") or "", 120),
            "content": answer,
            "state": "RESPONSE_RECORDED",
        })
    return {
        "schema": HISTORY_SCHEMA,
        "conversation_id": _clean(turn.get("conversation_id") or "", 120),
        "entries": rows,
        "entry_count": len(rows),
        "persists_externally": False,
        "automatic_memory_write": False,
    }


__all__ = [
    "SCHEMA",
    "HISTORY_SCHEMA",
    "MAX_MESSAGE_CHARS",
    "MAX_ATTACHMENTS",
    "normalize_attachment_metadata",
    "build_chat_turn",
    "append_chat_history",
]
