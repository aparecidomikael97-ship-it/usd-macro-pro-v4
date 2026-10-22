"""A180: synthetic pre-send witness reservation verifier (LAB ONLY).

A verified reservation must predate calling a provider's send adapter.
The witness, public key pin, clock, sequence and business-effect identity here
are LAB fixtures, NOT independent durable infrastructure.
"""
from __future__ import annotations

import base64
import binascii
from datetime import datetime, timezone
from hashlib import sha256
import secrets
from typing import Mapping

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from aion_chat.signed_receipt_lab import canonical_bytes, decision_sha256


SCHEMA = "ATLASQUANT_AION_A180_FIRST_ATTEMPT_WITNESS_LAB_V1"
DOMAIN = b"ATLASQUANT:A180:LAB:FIRST_ATTEMPT_V1\x00"
RECEIPT_FIELDS = frozenset({
    "schema", "status", "issuer", "key_id", "challenge",
    "idempotency_key", "effect_digest", "decision_sha256",
    "owner_id", "tenant_id", "workspace_id",
    "sequence", "issued_at", "expires_at",
})


def _effect_digest(decision: Mapping) -> str:
    """LAB approximation, excluding technical intent_ref/request ID.

    Identical legitimate business events may collide. Altered payload/scope
    may bypass. Production needs authentic immutable business-event IDs.
    """
    return sha256(canonical_bytes({
        "schema": "A180:CLAIMED_EFFECT_V1",
        "owner_id": decision["owner_id"],
        "tenant_id": decision["tenant_id"],
        "workspace_id": decision["workspace_id"],
        "action": decision["action"],
        "aggregate_key": decision["aggregate_key"],
        "payload_digest": decision["payload_digest"],
    })).hexdigest()


def _parse_time(value):
    if type(value) is not str:
        raise ValueError("timestamp must be a string")
    t = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if t.tzinfo is None:
        raise ValueError("timestamp must include timezone")
    return t.astimezone(timezone.utc)


class PinnedFirstAttemptWitnessLab:
    """Guard callback for A180 Outbox: guard(intent)->literal bool.

    The private signer stays OUTSIDE this verifier. The caller must pin the
    expected public witness key independently (only simulated in LAB).
    """

    def __init__(self, *, issuer, key_id, public_key, reserve,
                 now, high_water=0, revoked=False):
        if (type(issuer) is not str or not issuer or type(key_id) is not str
                or not key_id):
            raise ValueError("witness identity must be pinned")
        if type(public_key) is not bytes or len(public_key) != 32:
            raise ValueError("raw pinned Ed25519 public key required")
        if not callable(reserve):
            raise TypeError("external reservation callback required")
        if type(high_water) is not int or high_water < 0:
            raise ValueError("invalid high_water")
        if type(revoked) is not bool:
            raise ValueError("invalid revocation")
        if not isinstance(now, datetime) or now.tzinfo is None:
            raise ValueError("trusted aware time required")
        self._issuer = issuer
        self._key_id = key_id
        self._key = Ed25519PublicKey.from_public_bytes(public_key)
        self._reserve = reserve
        self._revoked = revoked
        self._high_water = high_water
        self._now = now.astimezone(timezone.utc)
        self._seen = set()

    def __call__(self, intent) -> bool:
        try:
            return self._check(intent)
        except (KeyError, ValueError, TypeError, InvalidSignature,
                binascii.Error, UnicodeError, OverflowError, RuntimeError,
                OSError, IndexError, AttributeError):
            return False

    def _check(self, intent):
        if self._revoked or not isinstance(intent, Mapping):
            return False
        decision = intent.get("decision")
        if not isinstance(decision, Mapping):
            return False
        key = intent.get("idempotency_key")
        if type(key) is not str or len(key) != 64:
            return False
        effect_digest = _effect_digest(decision)
        # Local re-entry is blocked even if a buggy witness hands out a second
        # valid signed reservation in this process. This set is not durable.
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
        if any(payload[name] != wanted for name, wanted in request.items()):
            return False
        sequence = payload["sequence"]
        if type(sequence) is not int or sequence <= self._high_water:
            return False
        issued = _parse_time(payload["issued_at"])
        expires = _parse_time(payload["expires_at"])
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
        self._high_water = sequence
        self._seen.add(effect_digest)
        return True


__all__ = ["SCHEMA", "DOMAIN", "RECEIPT_FIELDS",
           "PinnedFirstAttemptWitnessLab", "_effect_digest"]
