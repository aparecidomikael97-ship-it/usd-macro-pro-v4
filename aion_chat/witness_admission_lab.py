"""A179 LAB: require fresh independently signed witness admission per receipt.

Synthetic signatures only. This code cannot prove who provisioned either key,
whether the witness is independent, or whether its durable state survived a
rollback. It is not wired to an operational AION Worker.
"""
from __future__ import annotations

import binascii
import base64
from datetime import datetime, timezone
from hashlib import sha256
import secrets
from typing import Mapping

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from aion_chat.signed_receipt_lab import (
    PinnedEd25519ReceiptLab, canonical_bytes,
)

SCHEMA = "ATLASQUANT_AION_A179_WITNESS_ADMISSION_LAB_V1"
DOMAIN = b"ATLASQUANT:A179:LAB:WITNESS_ADMISSION_V1\x00"
FIELDS = frozenset({
    "schema", "issuer", "key_id", "challenge", "receipt_sha256",
    "trust_sha256", "kind", "idempotency_key", "receipt_id",
    "receipt_sequence", "witness_sequence", "issued_at", "expires_at",
    "admission",
})
KINDS = frozenset({"EFFECT_CONFIRMED", "EFFECT_ZERO"})


def _timestamp(s):
    if type(s) is not str:
        raise ValueError("timestamp string required")
    value = datetime.fromisoformat(s.replace("Z", "+00:00"))
    if value.tzinfo is None:
        raise ValueError("timezone required")
    return value.astimezone(timezone.utc)


def _keyring_hash(trusted_keys, revoked_keys):
    rows = []
    for key_id, cfg in sorted(trusted_keys.items()):
        rows.append({
            "key_id": key_id,
            "issuer": cfg["issuer"],
            "public_key_hex": cfg["public_key"].hex(),
        })
    return sha256(canonical_bytes({
        "schema": "A179:PINS_V1",
        "keys": rows,
        "revoked": sorted(revoked_keys),
    })).hexdigest()


class WitnessedReceiptGateLab:
    """Composite gate with two distinct pins, fresh challenge and deny-on-loss.

    witness_provider(challenge, request) must return a signed admission.
    The provider does not receive the witness's private signing key.
    """
    def __init__(
        self, *, trusted_provider_keys, provider_revoked=(),
        witness_key_id, witness_issuer, witness_public_key,
        witness_provider, witness_revoked=False, high_water=0,
        now: datetime,
    ):
        if type(witness_key_id) is not str or not witness_key_id:
            raise ValueError("witness key ID required")
        if type(witness_issuer) is not str or not witness_issuer:
            raise ValueError("witness issuer required")
        if type(witness_public_key) is not bytes or len(witness_public_key) != 32:
            raise ValueError("raw witness key required")
        if not callable(witness_provider):
            raise TypeError("witness provider callback required")
        if type(witness_revoked) is not bool:
            raise TypeError("revocation bool required")
        if type(high_water) is not int or high_water < 0:
            raise ValueError("invalid witness high-water")
        self._provider_verifier = PinnedEd25519ReceiptLab(
            trusted_keys=trusted_provider_keys,
            revoked_keys=provider_revoked, high_water=0, now=now,
        )
        # It is not sufficient for a "second signature" to reuse the very
        # same provider key: reject identical public keys even in LAB.
        if witness_public_key in (
            x["public_key"] for x in trusted_provider_keys.values()
        ):
            raise ValueError("WITNESS_KEY_NOT_SEPARATE")
        self._trusted_hash = _keyring_hash(
            trusted_provider_keys, provider_revoked,
        )
        self._witness_key = Ed25519PublicKey.from_public_bytes(
            witness_public_key)
        self._witness_key_id = witness_key_id
        self._witness_issuer = witness_issuer
        self._witness_provider = witness_provider
        self._witness_revoked = witness_revoked
        self._last_witness_sequence = high_water
        self._local_seen = set()
        if not isinstance(now, datetime) or now.tzinfo is None:
            raise ValueError("trusted clock required")
        self._now = now.astimezone(timezone.utc)

    @property
    def trust_digest(self):
        return self._trusted_hash

    def __call__(self, kind, intent, result):
        try:
            return self._admit(kind, intent, result)
        except (KeyError, ValueError, TypeError, OverflowError, IndexError,
                binascii.Error, InvalidSignature, UnicodeError, OSError,
                RuntimeError):
            return False

    def _admit(self, kind, intent, result):
        if kind not in KINDS or not isinstance(result, Mapping):
            return False
        if not self._provider_verifier(kind, intent, result):
            return False
        if self._witness_revoked:
            return False
        receipt = result["receipt"]
        payload = receipt["payload"]
        receipt_id = payload["receipt_id"]
        if receipt_id in self._local_seen:
            return False
        receipt_hash = sha256(canonical_bytes(receipt)).hexdigest()
        challenge = secrets.token_hex(32)
        request = {
            "kind": kind,
            "idempotency_key": intent["idempotency_key"],
            "receipt_id": receipt_id,
            "receipt_sequence": payload["sequence"],
            "receipt_sha256": receipt_hash,
            "trust_sha256": self._trusted_hash,
        }
        witness = self._witness_provider(challenge, dict(request))
        if type(witness) is not dict or set(witness) != {"payload", "signature"}:
            return False
        attestation = witness["payload"]
        if type(attestation) is not dict or set(attestation) != FIELDS:
            return False
        if (attestation["schema"] != SCHEMA or
                attestation["issuer"] != self._witness_issuer or
                attestation["key_id"] != self._witness_key_id or
                attestation["challenge"] != challenge or
                attestation["admission"] != "RESERVED"):
            return False
        if any(attestation[k] != request[k] for k in request):
            return False
        sequence = attestation["witness_sequence"]
        if type(sequence) is not int or sequence <= self._last_witness_sequence:
            return False
        if type(attestation["receipt_sequence"]) is not int:
            return False
        issued = _timestamp(attestation["issued_at"])
        expires = _timestamp(attestation["expires_at"])
        if not (issued <= self._now <= expires):
            return False
        if not (expires > issued and (expires-issued).total_seconds() <= 90):
            return False
        sig_text = witness["signature"]
        if type(sig_text) is not str or len(sig_text) > 128:
            return False
        signature = base64.b64decode(sig_text, validate=True)
        if len(signature) != 64:
            return False
        self._witness_key.verify(signature, DOMAIN + canonical_bytes(attestation))
        self._last_witness_sequence = sequence
        self._local_seen.add(receipt_id)
        return True


__all__ = ["SCHEMA", "DOMAIN", "WitnessedReceiptGateLab"]
