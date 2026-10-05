"""Scoped persistence bridge for verified AION read-only chat turns.

This module reuses the existing aion_chat store. It does not create a second
conversation database, a second memory system, or a new authority path.

Only a Golden Path result that is already CONFIRMED_SUCCESS and structurally
verified may be written. The write is local chat history only. It does not
promote memory, save a Core checkpoint, grant approval, call a provider, or
perform an external action.
"""
from __future__ import annotations

from hashlib import sha256
import json
from typing import Any, Mapping, Sequence

from aion_chat.models import Message, Scope
from aion_chat.privacy import redact
from atlasquant_aion_chat_golden_path import execute_readonly_golden_path
from atlasquant_aion_chat_surface import conversation_identity_binding

SCHEMA = "ATLASQUANT_AION_CHAT_HISTORY_BRIDGE_V1"
MAX_ASSISTANT_TEXT = 16_000


def _clean(value: Any, limit: int = 1200) -> str:
    return " ".join(str(value or "").replace("\x00", "").split())[:limit]


def _canonical(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )


def _digest(value: Any) -> str:
    return sha256(_canonical(value).encode("utf-8")).hexdigest()


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def trusted_context_for_scope(
    scope: Scope,
    context: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return chat context whose identity fields come only from trusted Scope."""
    if not isinstance(scope, Scope):
        raise TypeError("trusted Scope required")
    raw = dict(context or {})
    expected = {
        "tenant_id": scope.tenant_id,
        "workspace_id": scope.workspace_id,
        "actor_id": scope.owner_id,
    }
    for key, wanted in expected.items():
        supplied = _clean(raw.get(key), 120)
        if supplied and supplied != wanted:
            raise ValueError(f"context {key} crosses trusted scope")
    return {
        "role": _clean(raw.get("role") or "USER", 24).upper() or "USER",
        "persona": _clean(raw.get("persona") or "", 80),
        "experience_mode": _clean(
            raw.get("experience_mode") or "BEGINNER", 24
        ).upper() or "BEGINNER",
        "domain_hint": _clean(raw.get("domain_hint") or "", 80).lower(),
        **expected,
    }


def _receipt_digest_valid(receipt: Mapping[str, Any]) -> bool:
    supplied = _clean(receipt.get("receipt_digest"), 64)
    if len(supplied) != 64:
        return False
    body = dict(receipt)
    body.pop("receipt_digest", None)
    return supplied == _digest(body)


def validate_verified_read_result(
    scope: Scope,
    result: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate the full result before any durable history write."""
    if not isinstance(scope, Scope):
        raise TypeError("trusted Scope required")
    if not isinstance(result, Mapping):
        raise TypeError("golden result mapping required")

    blockers: list[str] = []
    turn = _mapping(result.get("turn"))
    verification = _mapping(result.get("verification"))
    receipt = _mapping(result.get("receipt"))
    conversation_id = _clean(result.get("conversation_id"), 120)
    binding_digest = _clean(result.get("identity_binding_digest"), 64)

    if result.get("state") != "CONFIRMED_SUCCESS":
        blockers.append("GOLDEN_PATH_NOT_CONFIRMED")
    if result.get("receipt_created") is not True:
        blockers.append("RECEIPT_NOT_CREATED")
    if verification.get("verified") is not True:
        blockers.append("EXECUTION_NOT_VERIFIED")
    if not conversation_id:
        blockers.append("CONVERSATION_ID_MISSING")

    trusted_context = trusted_context_for_scope(
        scope,
        {
            "role": _mapping(turn.get("context")).get("role"),
            "persona": _mapping(turn.get("context")).get("persona"),
            "experience_mode": _mapping(turn.get("context")).get("experience_mode"),
            "domain_hint": _mapping(turn.get("context")).get("domain_hint"),
        },
    )
    expected_binding = conversation_identity_binding(
        trusted_context,
        conversation_id,
    )
    turn_context = _mapping(turn.get("context"))

    if expected_binding.get("complete") is not True:
        blockers.append("TRUSTED_SCOPE_BINDING_INCOMPLETE")
    if binding_digest != str(expected_binding.get("binding_digest") or ""):
        blockers.append("RESULT_IDENTITY_BINDING_MISMATCH")
    if _clean(turn.get("identity_binding_digest"), 64) != binding_digest:
        blockers.append("TURN_IDENTITY_BINDING_MISMATCH")
    if _clean(verification.get("identity_binding_digest"), 64) != binding_digest:
        blockers.append("VERIFICATION_IDENTITY_BINDING_MISMATCH")
    if _clean(receipt.get("identity_binding_digest"), 64) != binding_digest:
        blockers.append("RECEIPT_IDENTITY_BINDING_MISMATCH")

    for key, wanted in (
        ("tenant_id", scope.tenant_id),
        ("workspace_id", scope.workspace_id),
        ("actor_id", scope.owner_id),
    ):
        if _clean(turn_context.get(key), 120) != wanted:
            blockers.append("TURN_SCOPE_MISMATCH:" + key.upper())

    if receipt.get("read_only") is not True:
        blockers.append("RECEIPT_NOT_READ_ONLY")
    if receipt.get("local_only") is not True:
        blockers.append("RECEIPT_NOT_LOCAL_ONLY")
    if receipt.get("authorization") != "NONE":
        blockers.append("RECEIPT_CLAIMS_AUTHORIZATION")
    if receipt.get("grants_authority") is not False:
        blockers.append("RECEIPT_AUTHORITY_FLAG_NOT_FALSE")
    if receipt.get("external_action_executed") is not False:
        blockers.append("RECEIPT_EXTERNAL_ACTION_FLAG_NOT_FALSE")
    if receipt.get("network_called") is not False:
        blockers.append("RECEIPT_NETWORK_FLAG_NOT_FALSE")
    if receipt.get("provider_called") is not False:
        blockers.append("RECEIPT_PROVIDER_FLAG_NOT_FALSE")
    if receipt.get("persisted_externally") is not False:
        blockers.append("RECEIPT_EXTERNAL_PERSISTENCE_FLAG_NOT_FALSE")
    if receipt.get("memory_written") is not False:
        blockers.append("RECEIPT_MEMORY_WRITE_FLAG_NOT_FALSE")
    if not _receipt_digest_valid(receipt):
        blockers.append("RECEIPT_DIGEST_INVALID")

    if result.get("external_action_executed") is not False:
        blockers.append("RESULT_EXTERNAL_ACTION_FLAG_NOT_FALSE")
    if result.get("provider_called") is not False:
        blockers.append("RESULT_PROVIDER_FLAG_NOT_FALSE")
    if result.get("network_called") is not False:
        blockers.append("RESULT_NETWORK_FLAG_NOT_FALSE")
    if result.get("automatic_memory_write") is not False:
        blockers.append("RESULT_MEMORY_WRITE_FLAG_NOT_FALSE")
    if result.get("automatic_learning_change") is not False:
        blockers.append("RESULT_LEARNING_FLAG_NOT_FALSE")

    blockers = list(dict.fromkeys(blockers))
    return {
        "schema": SCHEMA,
        "state": "VALID" if not blockers else "INVALID",
        "valid": not blockers,
        "blockers": blockers,
        "conversation_id": conversation_id,
        "turn_id": _clean(turn.get("turn_id"), 80),
        "identity_binding_digest": binding_digest,
        "receipt_id": _clean(receipt.get("receipt_id"), 80),
        "receipt_digest": _clean(receipt.get("receipt_digest"), 64),
        "trusted_scope": {
            "owner_id": scope.owner_id,
            "tenant_id": scope.tenant_id,
            "workspace_id": scope.workspace_id,
        },
        "grants_authority": False,
        "executes_action": False,
    }


def _message_id(turn_id: str, role: str) -> str:
    token = sha256(f"{turn_id}|{role}".encode("utf-8")).hexdigest()[:24].upper()
    return f"AION-CHAT-{role.upper()}-{token}"


def _optional_message(store: Any, scope: Scope, cid: str, mid: str):
    try:
        return store.get_message(scope, cid, mid)
    except LookupError:
        return None


def _assert_existing(
    existing: Message,
    *,
    role: str,
    content: str,
    turn_id: str,
    binding_digest: str,
) -> None:
    if existing.role != role:
        raise ValueError("idempotency collision: role mismatch")
    if existing.content != redact(content):
        raise ValueError("idempotency collision: content mismatch")
    metadata = dict(existing.metadata or {})
    if metadata.get("turn_id") != turn_id:
        raise ValueError("idempotency collision: turn mismatch")
    if metadata.get("identity_binding_digest") != binding_digest:
        raise ValueError("idempotency collision: identity mismatch")


def _assistant_text(result: Mapping[str, Any]) -> str:
    response = result.get("response")
    if isinstance(response, str) and response.strip():
        return response.strip()[:MAX_ASSISTANT_TEXT]
    execution = _mapping(result.get("execution"))
    summary = execution.get("summary")
    if isinstance(summary, str) and summary.strip():
        return summary.strip()[:MAX_ASSISTANT_TEXT]
    return "Leitura local concluída e verificada estruturalmente."


def persist_verified_read_result(
    store: Any,
    scope: Scope,
    result: Mapping[str, Any],
    *,
    attachment_ids: Sequence[Any] | None = None,
) -> dict[str, Any]:
    """Persist a verified user/assistant pair into the existing scoped chat store."""
    validation = validate_verified_read_result(scope, result)
    if validation["valid"] is not True:
        raise ValueError(
            "verified read result rejected: " + ",".join(validation["blockers"])
        )

    cid = validation["conversation_id"]
    store.get_conversation(scope, cid)
    turn = _mapping(result.get("turn"))
    receipt = _mapping(result.get("receipt"))
    binding_digest = validation["identity_binding_digest"]
    turn_id = validation["turn_id"]
    attachments = [
        _clean(item, 120)
        for item in list(attachment_ids or [])
        if _clean(item, 120)
    ]
    for attachment_id in attachments:
        store.get_attachment(scope, cid, attachment_id)

    user_text = str(turn.get("message") or "")
    assistant_text = _assistant_text(result)
    user_id = _message_id(turn_id, "user")
    assistant_id = _message_id(turn_id, "assistant")

    user_metadata = {
        "contract": SCHEMA,
        "turn_id": turn_id,
        "identity_binding_digest": binding_digest,
        "message_digest": _clean(turn.get("message_digest"), 64),
        "golden_path_state": str(result.get("state") or ""),
        "automatic_memory_promotion": False,
        "automatic_checkpoint_write": False,
    }
    assistant_metadata = {
        "contract": SCHEMA,
        "turn_id": turn_id,
        "identity_binding_digest": binding_digest,
        "receipt_id": validation["receipt_id"],
        "receipt_digest": validation["receipt_digest"],
        "verification_state": str(_mapping(result.get("verification")).get("state") or ""),
        "semantic_truth_verified": receipt.get("semantic_truth_verified") is True,
        "automatic_memory_promotion": False,
        "automatic_checkpoint_write": False,
    }
    provenance = {
        "source": "AION_CHAT_GOLDEN_PATH_READONLY",
        "receipt_id": validation["receipt_id"],
        "receipt_digest": validation["receipt_digest"],
        "tool_ids": list(receipt.get("tool_ids") or []),
        "identity_binding_digest": binding_digest,
        "local_only": True,
        "read_only": True,
        "grants_authority": False,
    }

    existing_user = _optional_message(store, scope, cid, user_id)
    existing_assistant = _optional_message(store, scope, cid, assistant_id)

    if existing_user is not None:
        _assert_existing(
            existing_user,
            role="user",
            content=user_text,
            turn_id=turn_id,
            binding_digest=binding_digest,
        )
    if existing_assistant is not None:
        _assert_existing(
            existing_assistant,
            role="assistant",
            content=assistant_text,
            turn_id=turn_id,
            binding_digest=binding_digest,
        )

    user_written = False
    assistant_written = False
    if existing_user is None:
        try:
            existing_user = store.append_message(
                scope,
                Message(
                    cid,
                    "user",
                    user_text,
                    id=user_id,
                    attachments=attachments,
                    metadata=user_metadata,
                    provenance={
                        "source": "AION_CHAT_COMMAND_SURFACE",
                        "identity_binding_digest": binding_digest,
                        "local_only": True,
                    },
                    truth_state="USER_INPUT",
                ),
            )
            user_written = True
        except Exception as exc:
            return {
                "schema": SCHEMA,
                "state": "FAILED_SAFE",
                "reason": "USER_HISTORY_WRITE_FAILED",
                "error_type": type(exc).__name__,
                "conversation_id": cid,
                "turn_id": turn_id,
                "identity_binding_digest": binding_digest,
                "user_persisted": False,
                "assistant_persisted": False,
                "checkpoint_written": False,
                "memory_promoted": False,
                "external_action_executed": False,
            }

    if existing_assistant is None:
        try:
            existing_assistant = store.append_message(
                scope,
                Message(
                    cid,
                    "assistant",
                    assistant_text,
                    id=assistant_id,
                    metadata=assistant_metadata,
                    provenance=provenance,
                    truth_state="UNKNOWN",
                ),
            )
            assistant_written = True
        except Exception as exc:
            return {
                "schema": SCHEMA,
                "state": "PARTIAL_PERSISTENCE_RETRY_REQUIRED",
                "reason": "ASSISTANT_HISTORY_WRITE_FAILED",
                "error_type": type(exc).__name__,
                "conversation_id": cid,
                "turn_id": turn_id,
                "identity_binding_digest": binding_digest,
                "user_message_id": user_id,
                "assistant_message_id": assistant_id,
                "user_persisted": True,
                "assistant_persisted": False,
                "checkpoint_written": False,
                "memory_promoted": False,
                "external_action_executed": False,
            }

    state = "PERSISTED" if user_written or assistant_written else "IDEMPOTENT"
    return {
        "schema": SCHEMA,
        "state": state,
        "reason": "VERIFIED_READ_HISTORY_STORED",
        "conversation_id": cid,
        "turn_id": turn_id,
        "identity_binding_digest": binding_digest,
        "user_message_id": user_id,
        "assistant_message_id": assistant_id,
        "user_sequence": int(existing_user.sequence),
        "assistant_sequence": int(existing_assistant.sequence),
        "receipt_id": validation["receipt_id"],
        "receipt_digest": validation["receipt_digest"],
        "user_persisted": True,
        "assistant_persisted": True,
        "local_history_persisted": True,
        "persisted_externally": False,
        "checkpoint_written": False,
        "memory_promoted": False,
        "automatic_checkpoint_write": False,
        "automatic_memory_promotion": False,
        "grants_authority": False,
        "external_action_executed": False,
    }


def execute_and_persist_readonly(
    store: Any,
    scope: Scope,
    message: Any,
    *,
    context: Mapping[str, Any] | None = None,
    runtime_context: Mapping[str, Any] | None = None,
    access: Mapping[str, Any] | None = None,
    attachment_ids: Sequence[Any] | None = None,
    turn_index: int = 0,
    feature_flags: Mapping[str, Any] | None = None,
    source_kind: Any = "ADMIN",
    authenticated_admin: bool = False,
    hub: Mapping[str, Any] | None = None,
    portable_core: Mapping[str, Any] | None = None,
    conversation_id: Any,
) -> dict[str, Any]:
    """Run the verified local read path and persist only its chat history pair."""
    trusted = trusted_context_for_scope(scope, context)
    cid = _clean(conversation_id, 120)
    store.get_conversation(scope, cid)

    result = execute_readonly_golden_path(
        message,
        context=trusted,
        runtime_context=runtime_context,
        access=access,
        attachments=None,
        conversation_id=cid,
        turn_index=turn_index,
        feature_flags=feature_flags,
        source_kind=source_kind,
        authenticated_admin=authenticated_admin,
        hub=hub,
        portable_core=portable_core,
    )
    if result.get("state") != "CONFIRMED_SUCCESS":
        return {
            "schema": SCHEMA,
            "state": "NOT_PERSISTED",
            "reason": "GOLDEN_PATH_NOT_CONFIRMED",
            "golden_result": result,
            "local_history_persisted": False,
            "checkpoint_written": False,
            "memory_promoted": False,
            "external_action_executed": False,
        }

    persistence = persist_verified_read_result(
        store,
        scope,
        result,
        attachment_ids=attachment_ids,
    )
    return {
        "schema": SCHEMA,
        "state": (
            "CONFIRMED_AND_PERSISTED"
            if persistence.get("state") in {"PERSISTED", "IDEMPOTENT"}
            else "PERSISTENCE_INCOMPLETE"
        ),
        "golden_result": result,
        "persistence": persistence,
        "external_action_executed": False,
        "provider_called": False,
        "network_called": False,
        "checkpoint_written": False,
        "memory_promoted": False,
    }


__all__ = [
    "SCHEMA",
    "trusted_context_for_scope",
    "validate_verified_read_result",
    "persist_verified_read_result",
    "execute_and_persist_readonly",
]
