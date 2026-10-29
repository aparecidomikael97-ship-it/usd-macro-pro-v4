"""A243 signed first-attempt reservation verifier: SYNTHETIC LAB ONLY.

Ed25519 authenticity against a caller-provided root is not independent custody.
Host rollback, root repinning, event-ID ambiguity and direct adapter bypass
remain explicit HARD NO-GO conditions.
"""
from __future__ import annotations

import base64
import binascii
from datetime import datetime, timezone
from hashlib import sha256
import json
import secrets
from typing import Mapping

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey


SCHEMA = "ATLASQUANT_AION_A243_SIGNED_FIRST_ATTEMPT_LAB_V1"
DOMAIN = b"ATLASQUANT:A243:LAB:FIRST_ATTEMPT_V1\x00"
RECEIPT_FIELDS = frozenset({
    "schema", "status", "issuer", "key_id", "challenge",
    "idempotency_key", "effect_digest", "decision_sha256",
    "owner_id", "tenant_id", "workspace_id",
    "sequence", "issued_at", "expires_at",
})


def canonical_bytes(value) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True,
        separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")


def decision_sha256(decision: Mapping) -> str:
    return sha256(canonical_bytes(dict(decision))).hexdigest()


def semantic_effect_digest(decision: Mapping) -> str:
    """Ambiguous LAB heuristic: excludes request/intent technical ID."""
    return sha256(canonical_bytes({
        "schema": "A243:CLAIMED_EFFECT_LAB_V1",
        "owner_id": decision["owner_id"],
        "tenant_id": decision["tenant_id"],
        "workspace_id": decision["workspace_id"],
        "action": decision["action"],
        "aggregate_key": decision["aggregate_key"],
        "payload_digest": decision["payload_digest"],
    })).hexdigest()


def _aware_utc(value):
    if type(value) is not str:
        raise ValueError("timestamp must be string")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamp requires timezone")
    return parsed.astimezone(timezone.utc)


class PinnedFirstAttemptWitnessLab:
    """Synthetic callable for A242 first_attempt_guard; NO real trust root."""

    def __init__(
        self, *, issuer, key_id, public_key, reserve, now,
        high_water=0, revoked=False,
    ):
        if type(issuer) is not str or not issuer or type(key_id) is not str or not key_id:
            raise ValueError("witness identity must be pinned")
        if type(public_key) is not bytes or len(public_key) != 32:
            raise ValueError("raw Ed25519 public key required")
        if not callable(reserve):
            raise TypeError("callable reserve required")
        if type(high_water) is not int or high_water < 0:
            raise ValueError("high_water must be nonnegative integer")
        if type(revoked) is not bool:
            raise ValueError("revoked must be bool")
        if not isinstance(now, datetime) or now.tzinfo is None:
            raise ValueError("aware clock required")
        self._issuer = issuer
        self._key_id = key_id
        self._key = Ed25519PublicKey.from_public_bytes(public_key)
        self._reserve = reserve
        self._now = now.astimezone(timezone.utc)
        self._high_water = high_water
        self._revoked = revoked
        self._seen = set()

    def __call__(self, intent) -> bool:
        try:
            return self._check(intent)
        except (KeyError, ValueError, TypeError, InvalidSignature,
                binascii.Error, UnicodeError, OverflowError, RuntimeError,
                OSError, IndexError, AttributeError):
            return False

    def _check(self, intent) -> bool:
        if self._revoked or not isinstance(intent, Mapping):
            return False
        decision = intent.get("decision")
        if not isinstance(decision, Mapping):
            return False
        key = intent.get("idempotency_key")
        if type(key) is not str or len(key) != 64 or any(
            ch not in "0123456789abcdef" for ch in key
        ):
            return False
        effect_digest = semantic_effect_digest(decision)
        if effect_digest in self._seen:
            return False
        request = {
            "idempotency_key": key,
            "effect_digest": effect_digest,
            "decision_sha256": decision_sha256(decision),
            "owner_id": decision["owner_id"],
            "tenant_id": decision["tenant_id"],
            "workspace_id": decision["workspace_id"],
        }
        challenge = secrets.token_hex(32)
        envelope = self._reserve(challenge, dict(request))
        if type(envelope) is not dict or set(envelope) != {"payload", "signature"}:
            return False
        payload = envelope["payload"]
        if type(payload) is not dict or set(payload) != RECEIPT_FIELDS:
            return False
        if (payload["schema"] != SCHEMA or payload["status"] != "RESERVED"
                or payload["issuer"] != self._issuer
                or payload["key_id"] != self._key_id
                or payload["challenge"] != challenge):
            return False
        if any(payload[name] != expected for name, expected in request.items()):
            return False
        seq = payload["sequence"]
        if type(seq) is not int or seq <= self._high_water:
            return False
        issued = _aware_utc(payload["issued_at"])
        expires = _aware_utc(payload["expires_at"])
        if not (issued <= self._now <= expires):
            return False
        if expires <= issued or (expires - issued).total_seconds() > 90:
            return False
        signature_b64 = envelope["signature"]
        if type(signature_b64) is not str or len(signature_b64) > 128:
            return False
        signature = base64.b64decode(signature_b64, validate=True)
        if len(signature) != 64:
            return False
        self._key.verify(signature, DOMAIN + canonical_bytes(payload))
        self._high_water = seq
        self._seen.add(effect_digest)
        return True


__all__ = [
    "SCHEMA", "DOMAIN", "RECEIPT_FIELDS", "PinnedFirstAttemptWitnessLab",
    "canonical_bytes", "decision_sha256", "semantic_effect_digest",
]
