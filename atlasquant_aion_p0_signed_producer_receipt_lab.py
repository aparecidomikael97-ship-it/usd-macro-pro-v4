"""AION P0 producer receipt Ed25519 signature verifier, LAB ONLY.

All pinned issuer keys, scopes, heads and replay sets are caller-supplied
fixtures. This checks mathematical signature consistency ONLY, NOT true
issuer custody, provider delivery, producer-enforced no-effect fence, or
independently durable high-water/nonce state. Even a valid signature cannot
clear UNKNOWN, authorize retry, or advance the Outbox. No IO or network.
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Any, Mapping

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

SCHEMA = "AION_P0_PRODUCER_RECEIPT_SIGNED_LAB_V1"
KINDS = frozenset(("POSITIVE_COMMITTED", "NEGATIVE_NO_EFFECT_FENCED"))
REQUIRED = frozenset((
    "schema", "kind", "owner_id", "tenant_id", "workspace_id",
    "host_id", "producer_issuer_id", "producer_account_id", "producer_key_id", "producer_key_version", "action_class",
    "intent_digest", "idempotency_key", "attempt", "epoch",
    "witness_sequence", "witness_head", "nonce", "receipt_id",
    "effect_or_fence_ref", "issued_at", "expires_at",
))
SCOPE = frozenset((
    "owner_id", "tenant_id", "workspace_id", "host_id",
    "producer_issuer_id", "producer_account_id", "producer_key_id", "producer_key_version", "action_class",
    "intent_digest", "idempotency_key", "attempt", "epoch",
))
HEX = re.compile(r"^[0-9a-f]{64}$")
TOKEN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
KEY_FIELDS = frozenset(("issuer_id", "key_id", "public_key_b64", "status", "key_version"))


def canonical_receipt_bytes(row: Mapping[str, Any]) -> bytes:
    return (
        "ATLASQUANT|P0|PRODUCER_RECEIPT|DENY_ONLY_LAB|V1\n"
        + json.dumps(dict(row), sort_keys=True, separators=(",", ":"),
                     ensure_ascii=False, allow_nan=False)
    ).encode("utf-8")


def _out(reason: str, *, math_consistent: bool = False) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "state": "BLOCKED",
        "reason": reason,
        "signature_math_consistent": math_consistent,
        "issuer_authenticated": False,
        "independent_witness_verified": False,
        "producer_effect_confirmed": False,
        "producer_no_effect_fence_confirmed": False,
        "nonce_durably_consumed": False,
        "high_water_independently_verified": False,
        "receipt_admitted": False,
        "unknown_outcome_cleared": False,
        "automatic_retry_allowed": False,
        "effect_ledger_authorized": False,
        "saga_advance_authorized": False,
        "writer_called": False,
        "external_action_executed": False,
        "executes_action": False,
    }


def _b64(value: Any, size: int) -> bytes:
    if not isinstance(value, str) or not 1 <= len(value) <= 256:
        raise ValueError("invalid encoding")
    if not re.fullmatch(r"[A-Za-z0-9_-]+", value):
        raise ValueError("not base64url")
    try:
        raw = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
    except (ValueError, binascii.Error) as exc:
        raise ValueError("invalid base64url") from exc
    if (len(raw) != size or
            base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii") != value):
        raise ValueError("noncanonical base64url")
    return raw


def _utc(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.endswith("Z"):
        return None
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
        return parsed.astimezone(timezone.utc)
    except (ValueError, TypeError, OverflowError):
        return None


def inspect_signed_producer_receipt_lab(
    claimed: Mapping[str, Any] | None,
    *,
    pinned_issuer: Mapping[str, Any] | None,
    expected_scope: Mapping[str, Any] | None,
    expected_witness_head: str,
    previous_witness_sequence: int,
    used_receipt_ids: frozenset[str] | None,
    now: str,
) -> dict[str, Any]:
    if (type(claimed) is not dict or any(type(k) is not str for k in claimed)
            or set(claimed) != {"receipt", "signature_b64"}):
        return _out("P0_ENVELOPE_INVALID")
    receipt = claimed["receipt"]
    if type(receipt) is not dict or any(type(k) is not str for k in receipt):
        return _out("P0_RECEIPT_INVALID")
    if set(receipt) != REQUIRED:
        return _out("P0_RECEIPT_FIELDS_INVALID")
    if (type(receipt["schema"]) is not str or receipt["schema"] != SCHEMA
            or type(receipt["kind"]) is not str or receipt["kind"] not in KINDS):
        return _out("P0_DOMAIN_OR_OUTCOME_KIND_INVALID")
    for field in REQUIRED - {"schema", "kind", "attempt", "epoch", "witness_sequence", "producer_key_version", "issued_at", "expires_at"}:
        value = receipt[field]
        if type(value) is not str or len(value) > 128 or not TOKEN.fullmatch(value):
            return _out("P0_FIELD_INVALID:" + field)
    for field in ("intent_digest", "witness_head"):
        if not HEX.fullmatch(receipt[field]):
            return _out("P0_DIGEST_INVALID:" + field)
    for field in ("attempt", "epoch", "witness_sequence", "producer_key_version"):
        value = receipt[field]
        if type(value) is not int or value < 1:
            return _out("P0_COUNTER_INVALID:" + field)
    if (type(expected_scope) is not dict or any(type(k) is not str for k in expected_scope)
            or set(expected_scope) != SCOPE):
        return _out("P0_EXPECTED_SCOPE_UNAVAILABLE")
    for field in SCOPE:
        expected = expected_scope[field]
        if type(expected) is not type(receipt[field]) or expected != receipt[field]:
            return _out("P0_SCOPE_MISMATCH:" + field)
    if (type(pinned_issuer) is not dict or any(type(k) is not str for k in pinned_issuer)
            or set(pinned_issuer) != KEY_FIELDS):
        return _out("P0_ISSUER_PIN_UNAVAILABLE")
    if pinned_issuer["status"] != "ACTIVE":
        return _out("P0_ISSUER_REVOKED_OR_INACTIVE")
    if (type(pinned_issuer["issuer_id"]) is not str or
            receipt["producer_issuer_id"] != pinned_issuer["issuer_id"] or
            type(pinned_issuer["key_version"]) is not int or pinned_issuer["key_version"] < 1):
        return _out("P0_ISSUER_PIN_MISMATCH")
    if type(used_receipt_ids) is not frozenset:
        return _out("P0_REPLAY_STATE_MISSING")
    if receipt["receipt_id"] in used_receipt_ids:
        return _out("P0_RECEIPT_REPLAYED")
    if (type(expected_witness_head) is not str or not HEX.fullmatch(expected_witness_head)
            or expected_witness_head != receipt["witness_head"]):
        return _out("P0_WITNESS_HEAD_MISMATCH")
    if (type(previous_witness_sequence) is not int
            or previous_witness_sequence < 0
            or receipt["witness_sequence"] != previous_witness_sequence + 1):
        return _out("P0_WITNESS_SEQUENCE_ROLLBACK_OR_GAP")
    issued, expires, current = _utc(receipt["issued_at"]), _utc(receipt["expires_at"]), _utc(now)
    if issued is None or expires is None or current is None:
        return _out("P0_TIME_INVALID")
    if (issued > current or current >= expires or expires <= issued
            or (expires - issued).total_seconds() > 180):
        return _out("P0_TIME_WINDOW_INVALID")
    try:
        pub = Ed25519PublicKey.from_public_bytes(_b64(pinned_issuer["public_key_b64"], 32))
        sig = _b64(claimed["signature_b64"], 64)
        pub.verify(sig, canonical_receipt_bytes(receipt))
    except (InvalidSignature, ValueError, TypeError, OverflowError):
        return _out("P0_SIGNATURE_INVALID")
    return _out("P0_CRYPTO_CONSISTENT_EXTERNAL_EFFECT_UNVERIFIED", math_consistent=True)
