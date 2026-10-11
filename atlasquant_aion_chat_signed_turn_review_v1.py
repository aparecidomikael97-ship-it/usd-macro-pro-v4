"""AION Chat V1: review a detached per-turn Ed25519 signature, NO EXECUTION.

This read-only mathematical verifier connects an actual staged USER row to the
exact approved model prompt/route/cost cap. It NEVER enrolls a signer,
consumes a nonce, reserves budget, calls a model or permits paid inference.
The public key is injected independently by a host, but this module cannot
prove trusted enrollment/custody, nor prevent that host from supplying a fake
pin. All operational authorization flags are ALWAYS false.
"""
from __future__ import annotations

from hashlib import sha256
import json
import re
from typing import Any, Mapping

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from aion_chat.models import Message, Scope
from atlasquant_aion_chat_product_bridge import validate_product_binding
from atlasquant_aion_chat_pending_model_turn_v1 import SCHEMA as PENDING_SCHEMA
from atlasquant_aion_model_router import privacy_sensitive
from atlasquant_aion_provider import MAX_PROMPT_CHARS

SCHEMA = "ATLASQUANT_AION_CHAT_SIGNED_MODEL_TURN_REVIEW_V1"
APPROVAL_SCHEMA = "ATLASQUANT_AION_CHAT_OWNER_MODEL_APPROVAL_PAYLOAD_V1"
PURPOSE = "APPROVE_ONE_PAID_MODEL_TEXT_TURN_REVIEW_ONLY"
ROLE = "HUMAN_OWNER_ED25519"
DOMAIN = b"ATLASQUANT_AION_CHAT_OWNER_MODEL_APPROVAL_V1\x00"
CANDIDATE = "SIGNED_TURN_MATH_VALID_UNTRUSTED"
_HEX64 = re.compile(r"[0-9a-f]{64}\Z")
_HEX128 = re.compile(r"[0-9a-f]{128}\Z")
_TOKEN = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9._:-]{0,119}\Z")
_PROVIDER = re.compile(r"[a-z][a-z0-9_-]{1,39}\Z")
_KEYS = frozenset({
    "schema", "purpose", "role", "owner_key_id",
    "owner_id", "tenant_id", "workspace_id", "conversation_id",
    "message_id", "request_digest", "source_message_sha256",
    "final_prompt_sha256", "provider_id", "model_id", "lane",
    "max_cost_micro_usd", "policy_generation", "nonce_hex",
})
_ENVELOPE = frozenset({"payload", "signature_hex"})
_PIN = frozenset({"key_id", "public_key_hex"})
FALSE_GATES = {
    "enrolled_owner_key_verified": False,
    "human_owner_identity_verified": False,
    "owner_custody_verified": False,
    "independent_trust_root_verified": False,
    "nonce_freshness_durably_verified": False,
    "nonce_reserved_or_consumed": False,
    "anti_replay_verified": False,
    "policy_generation_durably_verified": False,
    "budget_atomic_reservation_verified": False,
    "model_pricing_current_verified": False,
    "usd_brl_fx_verified": False,
    "external_model_request_approved": False,
    "model_invocation_authorized": False,
    "model_invocation_executed": False,
    "provider_called": False,
    "network_called": False,
    "billing_authorized": False,
    "billing_executed": False,
    "model_output_generated": False,
    "model_output_persisted": False,
    "core_checkpoint_write": False,
    "external_action_executed": False,
    "installer_authorized": False,
    "safe_to_resume": False,
}


def canonical_approval_message(payload: Mapping[str, Any]) -> bytes:
    """Domain-separated, canonical UTF-8 bytes. Strict schema checked first."""
    if type(payload) is not dict or set(payload) != _KEYS:
        raise ValueError("approval payload must have exact V1 schema")
    return DOMAIN + json.dumps(
        payload, sort_keys=True, ensure_ascii=False,
        separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")


def _out(state: str, reason: str, *, message_hash: str = "") -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "state": state,
        "reason": reason,
        "public_signature_math_valid": state == CANDIDATE,
        "scope_and_stored_message_matched": state == CANDIDATE,
        "signed_payload_sha256": message_hash if state == CANDIDATE else "",
        "reference_only": True,
        "requires_independent_owner_enrollment": True,
        "requires_durable_nonce_and_budget_reservation": True,
        **FALSE_GATES,
    }


def _hex(value: Any, pattern: re.Pattern[str]) -> bool:
    return type(value) is str and bool(pattern.fullmatch(value))


def _token(value: Any) -> bool:
    return type(value) is str and bool(_TOKEN.fullmatch(value))


def review_signed_pending_model_turn(
    store: Any, scope: Scope, access: Mapping[str, Any] | None,
    *,
    conversation_id: Any, message_id: Any, final_prompt: Any,
    envelope: Any, host_public_pin: Any, expected_policy_generation: Any,
) -> dict[str, Any]:
    """Check one staged user message and signed proposed intent, without side effects.

    host_public_pin and expected_policy_generation MUST come from an independent
    trusted server-side registry when integrated. This research layer cannot
    authenticate their enrollment or the host itself. Even VALID signature
    mathematics never becomes actual approval, spending or one-time consumption.
    """
    if not isinstance(scope, Scope) or not isinstance(access, Mapping):
        return _out("BLOCKED", "TRUSTED_SCOPE_AND_ACCESS_REQUIRED")
    binding = validate_product_binding(access, scope)
    if binding.get("bound") is not True:
        return _out("BLOCKED", "SCOPE_AND_AUTHENTICATED_SESSION_MISMATCH")
    if (not _token(conversation_id) or not _token(message_id)
        or type(final_prompt) is not str or not final_prompt.strip()
        or len(final_prompt) > MAX_PROMPT_CHARS
        or privacy_sensitive(final_prompt)):
        return _out("BLOCKED", "MESSAGE_SCOPE_OR_PROMPT_INVALID")
    if (type(expected_policy_generation) is not int
        or not 1 <= expected_policy_generation <= 2**31-1):
        return _out("BLOCKED", "TRUSTED_POLICY_GENERATION_REQUIRED")
    if type(host_public_pin) is not dict or set(host_public_pin) != _PIN:
        return _out("BLOCKED", "INDEPENDENT_PUBLIC_PIN_REQUIRED")
    if (not _token(host_public_pin["key_id"])
        or not _hex(host_public_pin["public_key_hex"], _HEX64)):
        return _out("BLOCKED", "PUBLIC_PIN_INVALID")
    if type(envelope) is not dict or set(envelope) != _ENVELOPE:
        return _out("BLOCKED", "SIGNED_ENVELOPE_SCHEMA_INVALID")
    payload = envelope["payload"]
    if type(payload) is not dict or set(payload) != _KEYS:
        return _out("BLOCKED", "SIGNED_PAYLOAD_SCHEMA_INVALID")
    if not _hex(envelope["signature_hex"], _HEX128):
        return _out("BLOCKED", "SIGNATURE_ENCODING_INVALID")
    if (payload["schema"] != APPROVAL_SCHEMA
        or payload["purpose"] != PURPOSE
        or payload["role"] != ROLE
        or payload["owner_key_id"] != host_public_pin["key_id"]):
        return _out("BLOCKED", "PURPOSE_ROLE_OR_KEY_ID_MISMATCH")
    for field in ("owner_id","tenant_id","workspace_id","conversation_id",
                  "message_id","provider_id","model_id","nonce_hex",
                  "request_digest","source_message_sha256","final_prompt_sha256"):
        if type(payload[field]) is not str:
            return _out("BLOCKED", "SIGNED_FIELD_TYPE_INVALID")
    if any(not _token(payload[field]) for field in (
        "owner_id","tenant_id","workspace_id","conversation_id","message_id","model_id",
    )):
        return _out("BLOCKED", "IDENTITY_OR_MODEL_TOKEN_INVALID")
    if (not _PROVIDER.fullmatch(payload["provider_id"])
        or payload["lane"] not in ("EXTERNAL_FAST","EXTERNAL_REASONING")
        or type(payload["lane"]) is not str):
        return _out("BLOCKED", "EXTERNAL_ROUTE_INVALID")
    if (type(payload["max_cost_micro_usd"]) is not int
        or not 1 <= payload["max_cost_micro_usd"] <= 20_000_000
        or type(payload["policy_generation"]) is not int
        or payload["policy_generation"] != expected_policy_generation):
        return _out("BLOCKED", "COST_CAP_OR_POLICY_INVALID")
    if not all(_hex(payload[field], _HEX64) for field in (
        "nonce_hex","request_digest","source_message_sha256","final_prompt_sha256"
    )):
        return _out("BLOCKED", "SIGNED_DIGEST_OR_NONCE_INVALID")
    if (payload["owner_id"] != scope.owner_id
        or payload["tenant_id"] != scope.tenant_id
        or payload["workspace_id"] != scope.workspace_id
        or payload["conversation_id"] != conversation_id
        or payload["message_id"] != message_id
        or payload["final_prompt_sha256"] != sha256(final_prompt.encode("utf-8")).hexdigest()):
        return _out("BLOCKED", "SIGNED_SCOPE_OR_PROMPT_MISMATCH")

    try:
        conversation = store.get_conversation(scope, conversation_id)
        row = store.get_message(scope, conversation_id, message_id)
    except (LookupError, ValueError, TypeError):
        return _out("BLOCKED", "STORED_USER_TURN_NOT_FOUND")
    except Exception:
        return _out("BLOCKED", "STORAGE_UNAVAILABLE")
    if (conversation.id != conversation_id or conversation.archived
        or not isinstance(row, Message)
        or row.id != message_id or row.conversation_id != conversation_id
        or row.role != "user" or row.attachments
        or not isinstance(row.metadata, dict)):
        return _out("BLOCKED", "STORED_ROW_OR_CONVERSATION_INVALID")
    meta = row.metadata
    if (set(meta) != {
        "contract","request_digest","message_sha256","approval_state",
        "model_invocation_authorized",
    } or meta["contract"] != PENDING_SCHEMA
        or meta["approval_state"] != "PENDING"
        or meta["model_invocation_authorized"] is not False):
        return _out("BLOCKED", "USER_TURN_NOT_PENDING")
    if (not _hex(meta["request_digest"], _HEX64)
        or message_id != "aion-pending-model-" + meta["request_digest"]
        or meta["request_digest"] != payload["request_digest"]
        or meta["message_sha256"] != sha256(row.content.encode("utf-8")).hexdigest()
        or meta["message_sha256"] != payload["source_message_sha256"]
        or privacy_sensitive(row.content)):
        return _out("BLOCKED", "STORED_CONTENT_OR_REQUEST_MISMATCH")
    try:
        message_bytes = canonical_approval_message(payload)
        Ed25519PublicKey.from_public_bytes(
            bytes.fromhex(host_public_pin["public_key_hex"])
        ).verify(bytes.fromhex(envelope["signature_hex"]), message_bytes)
    except (InvalidSignature, ValueError, TypeError, OverflowError):
        return _out("BLOCKED", "OWNER_SIGNATURE_MATH_INVALID")
    return _out(
        CANDIDATE, "MATHEMATICALLY_VALID_ONLY_NOT_TRUSTED_OWNER_AUTHORIZATION",
        message_hash=sha256(message_bytes).hexdigest(),
    )


__all__ = [
    "SCHEMA","APPROVAL_SCHEMA","PURPOSE","ROLE","DOMAIN","CANDIDATE",
    "FALSE_GATES","canonical_approval_message","review_signed_pending_model_turn",
]
