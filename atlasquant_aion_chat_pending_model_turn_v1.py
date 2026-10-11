"""AION Chat: persist a scoped user turn BEFORE possible future model invocation.

This is a usable staging boundary (SQLite fixture or injected chat store), not
a provider adapter. It NEVER calls a model, verifies HUMAN_OWNER cryptographic
identity, consumes approval, reserves billing, or marks a response as generated.

An authenticated ADMIN session is not HUMAN_OWNER authorization. Every staged
turn is pending and ineligible for automatic execution even if the browser
passes 'approved' or model/flag values to some other UI.
"""
from __future__ import annotations

from hashlib import sha256
import json
import re
from typing import Any, Mapping

from aion_chat.models import Message, Scope
from atlasquant_aion_chat_product_bridge import validate_product_binding
from atlasquant_aion_chat_surface import MAX_MESSAGE_CHARS
from atlasquant_aion_model_router import privacy_sensitive

SCHEMA = "ATLASQUANT_AION_CHAT_PENDING_MODEL_USER_TURN_V1"
STATE = "STAGED_AWAITING_VERIFIABLE_OWNER_APPROVAL"
REQUEST_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{7,79}\Z")
UNTRUSTED_FLAGS = {
    "model_response_generated": False,
    "provider_called": False,
    "network_called": False,
    "billing_authorized": False,
    "billing_executed": False,
    "owner_signature_verified": False,
    "model_invocation_authorized": False,
    "model_invocation_executed": False,
    "external_action_executed": False,
    "core_checkpoint_write": False,
    "automatic_memory_promotion": False,
    "production_storage_attested": False,
    "installer_authorized": False,
    "safe_to_resume": False,
}


def _digest(value: Mapping[str, str]) -> str:
    return sha256(json.dumps(
        dict(value), ensure_ascii=False, sort_keys=True,
        separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")).hexdigest()


def _receipt(state: str, *, scope: Scope, conversation_id: str,
             message_id: str, text_digest: str, request_digest: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "state": state,
        "scope_digest": _digest({
            "owner_id": scope.owner_id, "tenant_id": scope.tenant_id,
            "workspace_id": scope.workspace_id,
        }),
        "conversation_id": conversation_id,
        "message_id": message_id,
        "message_sha256": text_digest,
        "request_digest": request_digest,
        "stored_user_message": True,
        "requires_separate_signed_per_turn_owner_consent": True,
        "trusted_host_store_provenance_attested": False,
        "external_model_path_activated": False,
        **UNTRUSTED_FLAGS,
    }


def _verify_existing(
    row: Any, *, conversation_id: str, message_id: str,
    expected_text: str, request_digest: str,
) -> None:
    if not isinstance(row, Message) or row.id != message_id:
        raise ValueError("stored message identity mismatch")
    if row.conversation_id != conversation_id or row.role != "user":
        raise ValueError("stored message role/conversation mismatch")
    if row.content != expected_text or row.attachments:
        raise ValueError("request replay has different message content or attachments")
    metadata = row.metadata
    if not isinstance(metadata, dict) or set(metadata) != {
        "contract", "request_digest", "message_sha256", "approval_state",
        "model_invocation_authorized",
    }:
        raise ValueError("stored message metadata mismatch")
    if (metadata["contract"] != SCHEMA
        or metadata["request_digest"] != request_digest
        or metadata["message_sha256"] != sha256(expected_text.encode("utf-8")).hexdigest()
        or metadata["approval_state"] != "PENDING"
        or metadata["model_invocation_authorized"] is not False):
        raise ValueError("stored request is not a pending unapproved model turn")


def stage_pending_model_user_turn(
    store: Any, scope: Scope, access: Mapping[str, Any] | None,
    *, conversation_id: Any, request_id: Any, message: Any,
) -> dict[str, Any]:
    """Store exactly one pending scoped USER message; NO MODEL CALL IS POSSIBLE.

    Caller must provide the trusted host's already-authenticated access, Scope
    and an existing transactional store. This API does not read browser flags.
    Its digest is ONLY correlation/anti-confusion, NOT an authenticated receipt.
    Future transport must verify owner signature and atomic nonce + budget CAS
    independently; neither is claimed here.
    """
    if not isinstance(scope, Scope):
        raise TypeError("trusted Scope required")
    if not isinstance(access, Mapping):
        raise PermissionError("trusted authenticated access required")
    binding = validate_product_binding(access, scope)
    if binding.get("bound") is not True:
        raise PermissionError("authenticated owner scope binding required")
    if not callable(getattr(store, "get_conversation", None)) or not callable(
        getattr(store, "get_message", None)
    ) or not callable(getattr(store, "append_message", None)):
        raise TypeError("scoped transactional message store required")
    if type(conversation_id) is not str or not conversation_id or len(conversation_id) > 120:
        raise ValueError("conversation_id invalid")
    if type(request_id) is not str or not REQUEST_ID.fullmatch(request_id):
        raise ValueError("request_id invalid")
    if type(message) is not str or not message.strip() or len(message) > MAX_MESSAGE_CHARS:
        raise ValueError("unmodified nonempty bounded message required")
    # Conservative heuristic, not comprehensive PII certification.
    if privacy_sensitive(message):
        raise ValueError("sensitive content is not eligible for model staging")

    conversation = store.get_conversation(scope, conversation_id)
    if conversation.id != conversation_id or conversation.archived:
        raise ValueError("conversation unavailable for model staging")
    text_digest = sha256(message.encode("utf-8")).hexdigest()
    request_digest = _digest({
        "schema": SCHEMA, "owner_id": scope.owner_id,
        "tenant_id": scope.tenant_id, "workspace_id": scope.workspace_id,
        "conversation_id": conversation_id, "request_id": request_id,
    })
    message_id = "aion-pending-model-" + request_digest
    try:
        existing = store.get_message(scope, conversation_id, message_id)
    except LookupError:
        existing = None

    if existing is not None:
        _verify_existing(
            existing, conversation_id=conversation_id, message_id=message_id,
            expected_text=message, request_digest=request_digest,
        )
        state = "IDEMPOTENT_STAGED"
    else:
        metadata = {
            "contract": SCHEMA,
            "request_digest": request_digest,
            "message_sha256": text_digest,
            "approval_state": "PENDING",
            "model_invocation_authorized": False,
        }
        try:
            store.append_message(scope, Message(
                conversation_id=conversation_id, role="user", content=message,
                id=message_id, attachments=[], metadata=metadata,
                provenance={"source": "AUTHENTICATED_CHAT_MODEL_STAGING",
                            "external_call": False},
                truth_state="USER_TEXT_UNVERIFIED",
            ))
        except Exception:
            # Concurrent duplicate inserts and uncertain commits may have
            # persisted the exact turn. Re-read; never duplicate or swallow
            # divergence. Storage faults still fail closed if not recoverable.
            try:
                existing = store.get_message(scope, conversation_id, message_id)
            except LookupError:
                raise
            _verify_existing(
                existing, conversation_id=conversation_id, message_id=message_id,
                expected_text=message, request_digest=request_digest,
            )
            state = "IDEMPOTENT_STAGED"
        else:
            existing = store.get_message(scope, conversation_id, message_id)
            _verify_existing(
                existing, conversation_id=conversation_id, message_id=message_id,
                expected_text=message, request_digest=request_digest,
            )
            state = STATE
    return _receipt(
        state, scope=scope, conversation_id=conversation_id,
        message_id=message_id, text_digest=text_digest,
        request_digest=request_digest,
    )


__all__ = ["SCHEMA", "STATE", "UNTRUSTED_FLAGS", "stage_pending_model_user_turn"]
