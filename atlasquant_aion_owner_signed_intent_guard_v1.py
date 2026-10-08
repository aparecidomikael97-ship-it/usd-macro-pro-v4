"""AION V1 signed intent guard: a fresh owner proof is NOT a blank cheque.

CI-only integration: verify a SECOND Ed25519 signature over an exact operation,
exact navigation text and exact signed-owner proof. No owner signing key here.
No host/OS/UI integration, no credential enrolment, no external application.
The real authenticated host MUST independently establish all policy fields.
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import json
from typing import Any, Mapping, MutableMapping
from datetime import datetime

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from atlasquant_aion_trusted_owner_host_crypto_proof_v1 import signing_message
from atlasquant_aion_owner_proof_navigation_composition_v1 import (
    TrustedOwnerHostPolicy,
    plan_verified_owner_greeting,
    request_verified_owner_navigation,
)

SCHEMA = "AION_OWNER_SIGNED_OPERATION_INTENT_V1"
PURPOSE = "OWNER_UI_INTERNAL_OPERATION_ONLY"
SCOPE_NAV = "NAVIGATE_INTERNAL"
SCOPE_GREETING = "DISPLAY_GREETING"
_FIELDS = frozenset({
    "schema", "purpose", "scope", "command", "proof_digest",
    "session_binding_digest", "device_binding_digest", "device",
    "issuer", "audience", "nonce", "issued_at", "expires_at",
})
_DOMAIN = b"ATLASQUANT:AION:OWNER_UI_SIGNED_INTENT:V1\x00"


def _sha256(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _valid_intent(intent: Any) -> bool:
    if not isinstance(intent, Mapping) or set(intent) != _FIELDS:
        return False
    if intent.get("schema") != SCHEMA or intent.get("purpose") != PURPOSE:
        return False
    if intent.get("scope") not in (SCOPE_NAV, SCOPE_GREETING):
        return False
    cmd = intent.get("command")
    if type(cmd) is not str or len(cmd) > 160:
        return False
    if intent["scope"] == SCOPE_GREETING and cmd != "":
        return False
    if intent["scope"] == SCOPE_NAV and not cmd:
        return False
    for field in ("proof_digest", "session_binding_digest", "device_binding_digest"):
        val = intent.get(field)
        if (type(val) is not str or not val.startswith("sha256:")
            or len(val) != 71 or any(c not in "0123456789abcdef" for c in val[7:])):
            return False
    for field in ("issuer", "audience"):
        val = intent.get(field)
        if type(val) is not str or not 1 <= len(val) <= 120:
            return False
    if intent.get("device") not in ("DESKTOP", "MOBILE"):
        return False
    nonce = intent.get("nonce")
    if (type(nonce) is not str or len(nonce) != 64
        or any(c not in "0123456789abcdef" for c in nonce)):
        return False
    i, e = intent.get("issued_at"), intent.get("expires_at")
    if type(i) is not int or type(e) is not int or not 0 < i < e <= i + 120:
        return False
    return True


def signed_intent_message(intent: Mapping[str, Any]) -> bytes:
    """Exact domain-separated bytes for an EXTERNAL signer (not provided)."""
    if not _valid_intent(intent):
        raise ValueError("invalid signed owner intent")
    return _DOMAIN + json.dumps(
        dict(intent), sort_keys=True, ensure_ascii=True,
        separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")


def _reject(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "BLOCKED", "reason": reason,
        "owner_ready": False, "navigation_requested": False,
        "navigation_confirmed": False, "greeting_spoken": False,
        "microphone_active": False, "signed_intent_bound": False,
        "external_action_authorized": False,
        "execution_confirmed": False, "trusted_host_attached": False,
    }


def _check_intent(
    owner_payload: Mapping[str, Any] | None,
    intent: Mapping[str, Any] | None,
    intent_signature_b64: Any,
    *, policy: TrustedOwnerHostPolicy,
    scope: str, text: str,
    now_epoch: int,
) -> tuple[str, str]:
    """Check BEFORE consuming owner nonce or mutating navigation state."""
    if not isinstance(policy, TrustedOwnerHostPolicy):
        return "", "TRUSTED_HOST_POLICY_REQUIRED"
    if not _valid_intent(intent):
        return "", "INTENT_SHAPE_INVALID"
    if intent["scope"] != scope:
        return "", "WRONG_INTENT_SCOPE"
    if type(text) is not str or intent["command"] != text:
        return "", "INTENT_COMMAND_MISMATCH"
    if policy.device not in ("DESKTOP", "MOBILE"):
        return "", "TRUSTED_DEVICE_REQUIRED"
    try:
        proof_message = signing_message(owner_payload)
    except (ValueError, TypeError):
        return "", "OWNER_PROOF_PAYLOAD_INVALID"
    if (
        intent["proof_digest"] != _sha256(proof_message)
        or intent["nonce"] != owner_payload["nonce"]
        or intent["issued_at"] != owner_payload["issued_at"]
        or intent["expires_at"] != owner_payload["expires_at"]
        or intent["session_binding_digest"] != policy.expected_session_binding_digest
        or intent["device_binding_digest"] != policy.expected_device_binding_digest
        or intent["device"] != policy.device
        or intent["issuer"] != policy.expected_issuer
        or intent["audience"] != policy.expected_audience
    ):
        return "", "INTENT_CONTEXT_MISMATCH"
    if type(now_epoch) is not int or not intent["issued_at"] <= now_epoch <= intent["expires_at"]:
        return "", "INTENT_EXPIRED_OR_FUTURE"
    key = policy.pinned_owner_public_key
    pin = policy.expected_pinned_key_fingerprint
    if type(key) is not bytes or len(key) != 32 or _sha256(key) != pin:
        return "", "HOST_OWNER_KEY_NOT_PINNED"
    if type(intent_signature_b64) is not str or not 1 <= len(intent_signature_b64) <= 160:
        return "", "INTENT_SIGNATURE_INVALID"
    try:
        sig = base64.b64decode(intent_signature_b64, validate=True)
        if len(sig) != 64 or base64.b64encode(sig).decode("ascii") != intent_signature_b64:
            return "", "INTENT_SIGNATURE_INVALID"
        message = signed_intent_message(intent)
        Ed25519PublicKey.from_public_bytes(key).verify(sig, message)
    except (InvalidSignature, ValueError, TypeError, binascii.Error):
        return "", "INTENT_SIGNATURE_INVALID"
    return _sha256(message), ""


def request_intent_bound_navigation(
    session_state: MutableMapping[str, Any],
    access: Mapping[str, Any] | None,
    owner_payload: Mapping[str, Any] | None,
    owner_signature_b64: str,
    intent: Mapping[str, Any] | None,
    intent_signature_b64: str,
    *,
    policy: TrustedOwnerHostPolicy,
    now_epoch: int,
    text: str,
) -> dict[str, Any]:
    """Only exact signed command can reach same-session internal route."""
    if not isinstance(session_state, MutableMapping):
        return _reject("TRUSTED_SESSION_STATE_REQUIRED")
    fingerprint, reason = _check_intent(
        owner_payload, intent, intent_signature_b64,
        policy=policy, scope=SCOPE_NAV, text=text, now_epoch=now_epoch,
    )
    if reason:
        return _reject(reason)
    result = request_verified_owner_navigation(
        session_state, access, owner_payload, owner_signature_b64,
        policy=policy, now_epoch=now_epoch, text=text,
    )
    if result.get("state") != "INTERNAL_NAVIGATION_REQUESTED":
        return _reject("OWNER_PROOF_OR_INTERNAL_ROUTE_DENIED")
    return {
        **result,
        "schema": SCHEMA,
        "signed_intent_bound": True,
        "signed_intent_digest": fingerprint,
        "navigation_confirmed": False,
        "external_action_authorized": False,
        "execution_confirmed": False,
        "trusted_host_attached": False,
    }


def plan_intent_bound_greeting(
    access: Mapping[str, Any] | None,
    owner_payload: Mapping[str, Any] | None,
    owner_signature_b64: str,
    intent: Mapping[str, Any] | None,
    intent_signature_b64: str,
    *,
    policy: TrustedOwnerHostPolicy,
    now_epoch: int,
    now: datetime | None = None,
    timezone_name: str | None = None,
) -> dict[str, Any]:
    """Only signed display greeting (no command) can plan a greeting."""
    fingerprint, reason = _check_intent(
        owner_payload, intent, intent_signature_b64,
        policy=policy, scope=SCOPE_GREETING, text="", now_epoch=now_epoch,
    )
    if reason:
        return _reject(reason)
    result = plan_verified_owner_greeting(
        access, owner_payload, owner_signature_b64,
        policy=policy, now_epoch=now_epoch, now=now,
        timezone_name=timezone_name,
    )
    if result.get("state") != "OWNER_ENTRY_READY":
        return _reject("OWNER_PROOF_OR_GREETING_DENIED")
    return {
        **result,
        "schema": SCHEMA,
        "signed_intent_bound": True,
        "signed_intent_digest": fingerprint,
        "greeting_spoken": False,
        "microphone_active": False,
        "navigation_confirmed": False,
        "external_action_authorized": False,
        "execution_confirmed": False,
        "trusted_host_attached": False,
    }


__all__ = [
    "SCHEMA", "PURPOSE", "SCOPE_NAV", "SCOPE_GREETING",
    "signed_intent_message", "request_intent_bound_navigation",
    "plan_intent_bound_greeting",
]
