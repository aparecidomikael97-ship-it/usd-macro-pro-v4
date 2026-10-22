"""A178 LAB: verify synthetic Ed25519 provider receipts against pinned public keys.

This is NOT a production trust anchor or proof a real provider sent an effect.
The caller supplies the pinned keys, revocations and clock; no external
custodian, reliable clock, H0 rollback prevention or provider keys exist here.
No private keys, network operations or real providers in this module.
"""
from __future__ import annotations

import base64
import binascii
from datetime import datetime, timezone
from hashlib import sha256
import json
import re
from typing import Mapping

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey


SCHEMA = "ATLASQUANT_AION_A178_ED25519_RECEIPT_LAB_V1"
DOMAIN = b"ATLASQUANT:A178:LAB:ED25519_RECEIPT_V1\x00"
KINDS = frozenset({"EFFECT_CONFIRMED", "EFFECT_ZERO"})
FIELDS = frozenset({
    "schema", "kind", "issuer", "key_id", "receipt_id", "nonce",
    "sequence", "issued_at", "expires_at", "idempotency_key",
    "decision_sha256", "owner_id", "tenant_id", "workspace_id",
    "effect_ref",
})
TOKEN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}\Z")
SHA256 = re.compile(r"[a-f0-9]{64}\Z")


def canonical_bytes(value: Mapping) -> bytes:
    """Deterministic signed bytes for a strict JSON map, never a python repr."""
    return json.dumps(
        value, ensure_ascii=True, sort_keys=True,
        separators=(",", ":"), allow_nan=False,
    ).encode("ascii")


def decision_sha256(decision: Mapping) -> str:
    return sha256(canonical_bytes(decision)).hexdigest()


def _utc(value: str) -> datetime:
    if type(value) is not str:
        raise ValueError("timestamp type")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("naive timestamp denied")
    return parsed.astimezone(timezone.utc)


class PinnedEd25519ReceiptLab:
    """Callback compatible with A177 evidence_verifier, fail-closed by default.

    trusted_keys: mapping key_id -> {"issuer": ID, "public_key": raw_32_bytes}
    The configured map is a lab fixture; production MUST pin trust elsewhere.
    """

    def __init__(self, *, trusted_keys: Mapping, revoked_keys=(),
                 high_water: int = 0, now: datetime):
        if type(high_water) is not int or high_water < 0:
            raise ValueError("invalid high water")
        if not isinstance(now, datetime) or now.tzinfo is None:
            raise ValueError("trusted clock required")
        if not isinstance(trusted_keys, Mapping) or not trusted_keys:
            raise ValueError("pinned keys required")
        copied = {}
        for key_id, row in trusted_keys.items():
            if type(key_id) is not str or not TOKEN.fullmatch(key_id):
                raise ValueError("invalid key id")
            if type(row) is not dict or set(row) != {"issuer", "public_key"}:
                raise ValueError("invalid pin metadata")
            issuer, raw = row["issuer"], row["public_key"]
            if type(issuer) is not str or not TOKEN.fullmatch(issuer):
                raise ValueError("invalid pinned issuer")
            if type(raw) is not bytes or len(raw) != 32:
                raise ValueError("invalid Ed25519 public key")
            copied[key_id] = (issuer, Ed25519PublicKey.from_public_bytes(raw))
        revocations = frozenset(revoked_keys)
        if any(type(x) is not str or not TOKEN.fullmatch(x) for x in revocations):
            raise ValueError("invalid revoked key")
        self._pins = copied
        self._revoked = revocations
        self._high_water = high_water
        self._now = now.astimezone(timezone.utc)

    def __call__(self, kind, intent, result) -> bool:
        try:
            return self._check(kind, intent, result)
        except (ValueError, TypeError, KeyError, OverflowError,
                InvalidSignature, binascii.Error, UnicodeError):
            return False

    def _check(self, kind, intent, result) -> bool:
        if type(kind) is not str or kind not in KINDS:
            return False
        if not isinstance(intent, Mapping) or not isinstance(result, Mapping):
            return False
        # Adapter-supplied keys/issuer do not authorize themselves.
        receipt = result.get("receipt")
        if type(receipt) is not dict or set(receipt) != {"payload", "signature"}:
            return False
        payload, signature_b64 = receipt["payload"], receipt["signature"]
        if type(payload) is not dict or set(payload) != FIELDS:
            return False
        if any(type(payload.get(f)) is not str or not TOKEN.fullmatch(payload[f])
               for f in ("issuer", "key_id", "receipt_id", "nonce",
                         "owner_id", "tenant_id", "workspace_id")):
            return False
        if payload["schema"] != SCHEMA or payload["kind"] != kind:
            return False
        if (type(payload["sequence"]) is not int or
                payload["sequence"] <= self._high_water):
            return False
        if type(payload["idempotency_key"]) is not str or not SHA256.fullmatch(
                payload["idempotency_key"]):
            return False
        if type(payload["decision_sha256"]) is not str or not SHA256.fullmatch(
                payload["decision_sha256"]):
            return False
        if type(payload["effect_ref"]) is not str or (
                payload["effect_ref"] and not TOKEN.fullmatch(payload["effect_ref"])):
            return False
        # Validity is checked using the fixture clock, not a provider-asserted
        # clock alone. Neither this clock nor high_water is externally anchored.
        issued, expires = _utc(payload["issued_at"]), _utc(payload["expires_at"])
        if not issued <= self._now <= expires:
            return False
        if expires <= issued or (expires - issued).total_seconds() > 600:
            return False
        key_id = payload["key_id"]
        if key_id not in self._pins or key_id in self._revoked:
            return False
        pinned_issuer, public_key = self._pins[key_id]
        if payload["issuer"] != pinned_issuer:
            return False
        decision = intent.get("decision")
        if not isinstance(decision, Mapping):
            return False
        if (payload["idempotency_key"] != intent.get("idempotency_key") or
                payload["decision_sha256"] != decision_sha256(decision)):
            return False
        for field in ("owner_id", "tenant_id", "workspace_id"):
            if payload[field] != decision.get(field):
                return False
        if kind == "EFFECT_CONFIRMED":
            if (result.get("confirmed") is not True or
                    not payload["effect_ref"] or
                    payload["effect_ref"] != result.get("effect_ref")):
                return False
        else:
            if (result.get("accepted") is not False or
                    result.get("retryable") is not False or
                    payload["effect_ref"] != ""):
                return False
        if type(signature_b64) is not str or len(signature_b64) > 128:
            return False
        signature = base64.b64decode(signature_b64, validate=True)
        if len(signature) != 64:
            return False
        public_key.verify(signature, DOMAIN + canonical_bytes(payload))
        return True


__all__ = ["SCHEMA", "DOMAIN", "PinnedEd25519ReceiptLab",
           "canonical_bytes", "decision_sha256"]
