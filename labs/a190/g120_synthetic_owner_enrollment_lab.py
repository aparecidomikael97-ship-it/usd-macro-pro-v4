"""G120 cryptographic verification of a SYNTHETIC owner enrollment (LAB ONLY).

A second Ed25519 signer is intentionally separate from the G114 witness key.
The enrollment is bound to one event_id and the full semantic decision digest.
Both root pins, signing keys and test clocks are still HOST CONTROLLED. This
does not prove a real human's identity, independent approval, hardware root,
or non-replayability after host rollback. No production Worker integration.
"""
from __future__ import annotations

import base64
import binascii
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import re

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from aion_chat.intent_binding_a182_lab import semantic_bytes
from aion_chat.signed_receipt_lab import canonical_bytes


SCHEMA = "AION:G120:SYNTHETIC_OWNER_ENROLLMENT:V1"
ISSUER = "g120-test-owner-enrollment-authority"
AUDIENCE = "AION:G120:OUTBOX_FIRST_ATTEMPT:LAB"
DOMAIN = b"AION:G120:OWNER_ENROLLMENT:V1\x00"
_FIELDS = frozenset({
    "schema", "issuer", "audience", "event_id", "original_sha256",
    "owner_id", "tenant_id", "workspace_id", "action",
    "idempotency_key", "authorization_ref", "policy_version",
    "approval_id", "nonce", "issued_at", "expires_at",
})
_HEX64 = re.compile(r"[0-9a-f]{64}\Z")


def _deny(cause):
    raise ValueError("G120_OWNER_ENROLLMENT_" + cause)


def verify_synthetic_owner_enrollment(
    envelope, *, pinned_public_key, expected_event_id,
    original_decision, now,
):
    """Strictly check a signed, scope-bound and short-lived LAB enrollment.

    Signature under a CALLER-SUPPLIED local pin is not external authentication!
    No state is mutated and no successful check itself authorizes SEND.
    """
    if (type(pinned_public_key) is not bytes
            or len(pinned_public_key) != 32):
        _deny("PUBLIC_PIN_REQUIRED")
    if (type(original_decision) is not dict
            or type(expected_event_id) is not str
            or _HEX64.fullmatch(expected_event_id) is None):
        _deny("ORIGINAL_BINDING_REQUIRED")
    if (not isinstance(now, datetime) or now.tzinfo is None
            or now.utcoffset() is None):
        _deny("TRUSTED_AWARE_CLOCK_REQUIRED")
    if type(envelope) is not dict or set(envelope) != {"payload", "signature"}:
        _deny("SIGNED_ENVELOPE_REQUIRED")
    payload = envelope["payload"]
    if type(payload) is not dict or set(payload) != _FIELDS:
        _deny("EXACT_SCHEMA_REQUIRED")
    if (payload["schema"] != SCHEMA
            or payload["issuer"] != ISSUER
            or payload["audience"] != AUDIENCE):
        _deny("ISSUER_OR_AUDIENCE_MISMATCH")
    if payload["event_id"] != expected_event_id:
        _deny("EVENT_MISMATCH")
    original_digest = sha256(semantic_bytes(original_decision)).hexdigest()
    expected_fields = {
        "original_sha256": original_digest,
        "owner_id": original_decision.get("owner_id"),
        "tenant_id": original_decision.get("tenant_id"),
        "workspace_id": original_decision.get("workspace_id"),
        "action": original_decision.get("action"),
        "idempotency_key": original_decision.get("idempotency_key"),
        "authorization_ref": original_decision.get("authorization_ref"),
        "policy_version": original_decision.get("policy_version"),
    }
    if any(
        type(value) is not str or not value
        or type(payload.get(key)) is not str or payload[key] != value
        for key, value in expected_fields.items()
    ):
        _deny("ORIGINAL_OR_SCOPE_MISMATCH")
    for token in ("approval_id", "nonce"):
        if type(payload[token]) is not str or _HEX64.fullmatch(payload[token]) is None:
            _deny("APPROVAL_ID_OR_NONCE_REQUIRED")
    if (type(payload["issued_at"]) is not str
            or type(payload["expires_at"]) is not str):
        _deny("TIMESTAMP_REQUIRED")
    try:
        issued = datetime.fromisoformat(payload["issued_at"])
        expires = datetime.fromisoformat(payload["expires_at"])
    except ValueError:
        _deny("TIMESTAMP_MALFORMED")
    if (issued.tzinfo is None or issued.utcoffset() is None
            or expires.tzinfo is None or expires.utcoffset() is None):
        _deny("TIMESTAMP_MUST_BE_AWARE")
    issued, expires, now = (
        issued.astimezone(timezone.utc),
        expires.astimezone(timezone.utc),
        now.astimezone(timezone.utc),
    )
    if not (issued <= now <= expires and
            timedelta(0) < expires - issued <= timedelta(minutes=10)):
        _deny("EXPIRED_OR_NOT_YET_VALID")
    try:
        if type(envelope["signature"]) is not str:
            _deny("SIGNATURE_REQUIRED")
        raw_signature = base64.b64decode(envelope["signature"], validate=True)
        if len(raw_signature) != 64:
            _deny("SIGNATURE_LENGTH")
        Ed25519PublicKey.from_public_bytes(pinned_public_key).verify(
            raw_signature, DOMAIN + canonical_bytes(payload)
        )
    except (ValueError, TypeError, InvalidSignature, binascii.Error):
        _deny("SIGNATURE_INVALID")
    return True
