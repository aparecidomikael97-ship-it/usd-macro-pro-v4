"""AION Chat V2 mathematical review of one complete resolved LLM request.

READ-ONLY reference. No private-key enrollment, witness, nonce consumption,
budget debit, provider execution, installation or actual owner authority.
Never accept a V1 approval signature as a V2 approval. The V2 transcript is
domain-separated, versioned and contains the full resolved HTTP request hash.
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
from atlasquant_aion_chat_signed_turn_review_v1 import FALSE_GATES
from atlasquant_aion_model_router import privacy_sensitive
from atlasquant_aion_provider import (
    MAX_PROMPT_CHARS, REQUEST_BOUNDARY_SCHEMA,
    preview_openai_request_binding,
)

SCHEMA = "ATLASQUANT_AION_CHAT_SIGNED_FULL_PROVIDER_REQUEST_REVIEW_V2"
APPROVAL_SCHEMA = "ATLASQUANT_AION_CHAT_OWNER_FULL_REQUEST_APPROVAL_PAYLOAD_V2"
PURPOSE = "REVIEW_ONE_FULL_PAID_MODEL_REQUEST_NO_EXECUTION_V2"
ROLE = "HUMAN_OWNER_ED25519"
DOMAIN = b"ATLASQUANT_AION_CHAT_FULL_REQUEST_APPROVAL_V2\x00"
CANDIDATE = "FULL_REQUEST_SIGNATURE_MATH_VALID_UNTRUSTED"
_HEX64 = re.compile(r"[0-9a-f]{64}\Z")
_HEX128 = re.compile(r"[0-9a-f]{128}\Z")
_TOKEN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,119}\Z")
_PROVIDER = re.compile(r"[a-z][a-z0-9_-]{1,39}\Z")
_KEYS = frozenset({
    "schema", "purpose", "role", "owner_key_id",
    "owner_id", "tenant_id", "workspace_id", "conversation_id",
    "message_id", "request_digest", "source_message_sha256",
    "final_prompt_sha256", "full_provider_request_sha256",
    "provider_id", "model_id", "lane", "endpoint", "max_output_tokens",
    "timeout_seconds_repr", "max_cost_micro_usd", "policy_generation",
    "nonce_hex",
})
_ENVELOPE_KEYS = frozenset({"payload", "signature_hex"})
_PIN_KEYS = frozenset({"key_id", "public_key_hex"})
EXTRA_FALSE_GATES = {
    "full_request_mathematics_is_owner_authority": False,
    "v1_signature_upgraded_to_v2": False,
    "trusted_host_configuration_verified": False,
    "owner_public_key_enrollment_verified": False,
    "owner_key_custody_verified": False,
    "independent_monotonic_witness_verified": False,
    "ledger_restore_rollback_protected": False,
    "real_paid_dispatch_authorized": False,
    "real_budget_reserved": False,
    "real_provider_called": False,
}


def canonical_full_request_approval_v2(payload: Mapping[str, Any]) -> bytes:
    """No implicit V1 fallback and no extraneous fields, even signed ones."""
    if type(payload) is not dict or set(payload) != _KEYS:
        raise ValueError("V2 approval requires its exact closed schema")
    return DOMAIN + json.dumps(
        payload, sort_keys=True, ensure_ascii=False,
        separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")


def _hex(value: Any, pattern: re.Pattern[str]) -> bool:
    return type(value) is str and bool(pattern.fullmatch(value))


def _token(value: Any) -> bool:
    return type(value) is str and bool(_TOKEN.fullmatch(value))


def _result(state: str, reason: str, *, digest: str = "") -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "state": state,
        "reason": reason,
        "public_signature_math_valid": state == CANDIDATE,
        "stored_pending_user_message_matched": state == CANDIDATE,
        "resolved_full_request_matched": state == CANDIDATE,
        "signed_payload_sha256": digest if state == CANDIDATE else "",
        "reference_only": True,
        **FALSE_GATES,
        **EXTRA_FALSE_GATES,
    }


def review_signed_full_provider_request_v2(
    store: Any, scope: Scope, access: Mapping[str, Any] | None,
    *,
    conversation_id: Any, message_id: Any, final_prompt: Any,
    envelope: Any, host_public_pin: Any,
    expected_policy_generation: Any,
    provider_values: Mapping[str, Any] | None,
    host_quote_micro_usd: Any,
) -> dict[str, Any]:
    """Read-only V2 mathematical check of persisted USER message and request.

    host_public_pin, policy generation, provider_values and quote are supplied
    by the test caller; this cannot establish their independent trust. No
    positive result may be passed as request_approved=True to the provider.
    """
    if not isinstance(scope, Scope) or not isinstance(access, Mapping):
        return _result("BLOCKED", "TRUSTED_SCOPE_AND_ACCESS_REQUIRED")
    try:
        binding = validate_product_binding(access, scope)
    except Exception:
        return _result("BLOCKED", "ACCESS_BINDING_UNAVAILABLE")
    if binding.get("bound") is not True:
        return _result("BLOCKED", "SCOPE_AND_SESSION_MISMATCH")
    if (not _token(conversation_id) or not _token(message_id)
        or type(final_prompt) is not str or not final_prompt.strip()
        or final_prompt != final_prompt.strip()
        or len(final_prompt) > MAX_PROMPT_CHARS
        or privacy_sensitive(final_prompt)):
        return _result("BLOCKED", "MESSAGE_OR_CANONICAL_PROMPT_INVALID")
    if (type(expected_policy_generation) is not int
        or not 1 <= expected_policy_generation <= 2**31 - 1):
        return _result("BLOCKED", "HOST_POLICY_GENERATION_INVALID")
    if (type(host_quote_micro_usd) is not int
        or not 1 <= host_quote_micro_usd <= 20_000_000):
        return _result("BLOCKED", "HOST_REFERENCE_QUOTE_INVALID")
    if (type(host_public_pin) is not dict
        or set(host_public_pin) != _PIN_KEYS
        or not _token(host_public_pin["key_id"])
        or not _hex(host_public_pin["public_key_hex"], _HEX64)):
        return _result("BLOCKED", "PUBLIC_PIN_INVALID")
    if (type(envelope) is not dict
        or set(envelope) != _ENVELOPE_KEYS):
        return _result("BLOCKED", "ENVELOPE_SCHEMA_INVALID")
    payload = envelope["payload"]
    if type(payload) is not dict or set(payload) != _KEYS:
        return _result("BLOCKED", "SIGNED_V2_SCHEMA_REQUIRED_NO_V1_FALLBACK")
    if not _hex(envelope["signature_hex"], _HEX128):
        return _result("BLOCKED", "SIGNATURE_FORMAT_INVALID")
    if (payload["schema"] != APPROVAL_SCHEMA
        or payload["purpose"] != PURPOSE
        or payload["role"] != ROLE
        or payload["owner_key_id"] != host_public_pin["key_id"]):
        return _result("BLOCKED", "V2_PURPOSE_ROLE_OR_KEY_MISMATCH")

    token_fields = (
        "owner_id", "tenant_id", "workspace_id",
        "conversation_id", "message_id", "model_id",
    )
    if any(not _token(payload[k]) for k in token_fields):
        return _result("BLOCKED", "V2_IDENTITY_OR_MODEL_INVALID")
    if any(not _hex(payload[k], _HEX64) for k in (
        "request_digest", "source_message_sha256",
        "final_prompt_sha256", "full_provider_request_sha256",
        "nonce_hex",
    )):
        return _result("BLOCKED", "V2_REQUEST_HASH_OR_NONCE_INVALID")
    if (type(payload["provider_id"]) is not str
        or not _PROVIDER.fullmatch(payload["provider_id"])
        or type(payload["lane"]) is not str
        or payload["lane"] not in ("EXTERNAL_FAST", "EXTERNAL_REASONING")
        or type(payload["endpoint"]) is not str
        or not payload["endpoint"].startswith("https://")
        or type(payload["timeout_seconds_repr"]) is not str
        or not payload["timeout_seconds_repr"]
        or len(payload["timeout_seconds_repr"]) > 32
        or type(payload["max_output_tokens"]) is not int
        or not 1 <= payload["max_output_tokens"] <= 8192):
        return _result("BLOCKED", "V2_PROVIDER_PARAMETERS_INVALID")
    if (type(payload["policy_generation"]) is not int
        or payload["policy_generation"] != expected_policy_generation
        or type(payload["max_cost_micro_usd"]) is not int
        or not 1 <= payload["max_cost_micro_usd"] <= 20_000_000
        or host_quote_micro_usd > payload["max_cost_micro_usd"]):
        return _result("BLOCKED", "V2_POLICY_OR_MAX_COST_INVALID")
    if (payload["owner_id"] != scope.owner_id
        or payload["tenant_id"] != scope.tenant_id
        or payload["workspace_id"] != scope.workspace_id
        or payload["conversation_id"] != conversation_id
        or payload["message_id"] != message_id
        or payload["final_prompt_sha256"]
            != sha256(final_prompt.encode("utf-8")).hexdigest()):
        return _result("BLOCKED", "V2_SCOPE_OR_PROMPT_MISMATCH")

    # Independent *trust* of provider_values cannot be proved here. Only
    # mathematical consistency is checked against the actual adapter preview.
    try:
        preview = preview_openai_request_binding(
            final_prompt, lane=payload["lane"], values=provider_values,
        )
    except (ValueError, TypeError, OverflowError, AttributeError):
        return _result("BLOCKED", "PROVIDER_PREVIEW_UNAVAILABLE")
    if (type(preview) is not dict
        or preview.get("schema") != REQUEST_BOUNDARY_SCHEMA
        or preview.get("state") != "BOUND_REQUEST_PREVIEW_UNTRUSTED"):
        return _result("BLOCKED", "PROVIDER_PREVIEW_UNAVAILABLE")
    if (payload["full_provider_request_sha256"] != preview["request_sha256"]
        or payload["final_prompt_sha256"] != preview["final_prompt_sha256"]
        or payload["provider_id"] != preview["provider"]
        or payload["model_id"] != preview["resolved_model"]
        or payload["lane"] != preview["lane"]
        or payload["endpoint"] != preview["endpoint"]
        or payload["max_output_tokens"] != preview["max_output_tokens"]
        or payload["timeout_seconds_repr"] != repr(preview["timeout_seconds"])):
        return _result("BLOCKED", "SIGNED_FULL_REQUEST_OR_RESOLVED_OPTIONS_MISMATCH")

    try:
        conversation = store.get_conversation(scope, conversation_id)
        row = store.get_message(scope, conversation_id, message_id)
    except (LookupError, ValueError, TypeError):
        return _result("BLOCKED", "STORED_USER_TURN_NOT_FOUND")
    except Exception:
        return _result("BLOCKED", "CHAT_STORAGE_UNAVAILABLE")
    if (conversation.id != conversation_id or conversation.archived
        or not isinstance(row, Message)
        or row.id != message_id or row.conversation_id != conversation_id
        or row.role != "user" or row.attachments
        or type(row.content) is not str or type(row.metadata) is not dict):
        return _result("BLOCKED", "STORED_USER_ROW_INVALID")
    meta = row.metadata
    if (set(meta) != {
        "contract", "request_digest", "message_sha256",
        "approval_state", "model_invocation_authorized",
    } or meta["contract"] != PENDING_SCHEMA
        or meta["approval_state"] != "PENDING"
        or meta["model_invocation_authorized"] is not False):
        return _result("BLOCKED", "STORED_USER_TURN_NOT_PENDING")
    if (not _hex(meta["request_digest"], _HEX64)
        or message_id != "aion-pending-model-" + meta["request_digest"]
        or payload["request_digest"] != meta["request_digest"]
        or payload["source_message_sha256"] != meta["message_sha256"]
        or meta["message_sha256"] != sha256(row.content.encode("utf-8")).hexdigest()
        or privacy_sensitive(row.content)):
        return _result("BLOCKED", "STORED_USER_CONTENT_OR_REQUEST_MISMATCH")

    try:
        signed = canonical_full_request_approval_v2(payload)
        Ed25519PublicKey.from_public_bytes(
            bytes.fromhex(host_public_pin["public_key_hex"]),
        ).verify(bytes.fromhex(envelope["signature_hex"]), signed)
    except (InvalidSignature, ValueError, TypeError, OverflowError):
        return _result("BLOCKED", "V2_SIGNATURE_MATH_INVALID")
    return _result(
        CANDIDATE, "V2_MATH_ONLY_NO_OWNER_ENROLLMENT_OR_PROVIDER_AUTHORITY",
        digest=sha256(signed).hexdigest(),
    )


__all__ = [
    "SCHEMA", "APPROVAL_SCHEMA", "PURPOSE", "ROLE", "DOMAIN",
    "CANDIDATE", "EXTRA_FALSE_GATES", "canonical_full_request_approval_v2",
    "review_signed_full_provider_request_v2",
]
