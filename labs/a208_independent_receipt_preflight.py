"""A208 LAB: structural preflight for a future independent effect receipt.

This does NOT verify cryptographic custody, does NOT authorize dispatch,
does NOT attest provider state, and is NOT wired into ExecutionOutbox.
Every returned decision has may_confirm=False, including a valid shape.

Proof of independent signer provenance and antirollback is an external P0.
No host-supplied verified flag, callback or synthetic signature can replace it.
"""
from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import re
from typing import Any, Mapping


SCHEMA = "ATLASQUANT_AION_INDEPENDENT_EFFECT_RECEIPT_DRAFT_V0"
_RECEIPT_KEYS = frozenset({
    "schema",
    "owner_id",
    "tenant_id",
    "workspace_id",
    "idempotency_key",
    "intent_digest",
    "provider_id",
    "provider_event_id",
    "effect_ref",
    "effect_state",
    "occurred_at",
    "witness_root_id",
    "witness_sequence",
    "witness_signature_b64",
})
_BOUND_FIELDS = (
    "owner_id",
    "tenant_id",
    "workspace_id",
    "idempotency_key",
    "intent_digest",
    "provider_id",
    "witness_root_id",
)
_TOKEN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class ReceiptPreflight:
    structural_valid: bool
    may_confirm: bool
    code: str


def _reject(code: str) -> ReceiptPreflight:
    return ReceiptPreflight(False, False, code)


def _utc(value: Any) -> datetime:
    if isinstance(value, datetime):
        stamp = value
    elif isinstance(value, str):
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    else:
        raise ValueError("timestamp must be ISO-8601")
    if stamp.tzinfo is None or stamp.utcoffset() is None:
        raise ValueError("timestamp must be timezone aware")
    return stamp.astimezone(timezone.utc)


def parse_receipt_json(raw: str) -> dict[str, Any]:
    """Reject ambiguous duplicate JSON keys before checking the schema."""
    if not isinstance(raw, str):
        raise ValueError("receipt must be a JSON string")

    def unique_pairs(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate receipt JSON key")
            result[key] = value
        return result

    try:
        parsed = json.loads(raw, object_pairs_hook=unique_pairs)
    except (ValueError, TypeError) as exc:
        raise ValueError("invalid or ambiguous receipt JSON") from exc
    if not isinstance(parsed, dict):
        raise ValueError("receipt must be a JSON object")
    return parsed


def preflight_receipt(
    receipt: Any,
    *,
    expected: Mapping[str, Any],
    observed_at: Any,
    authorized_at: Any,
    last_witness_sequence: int,
) -> ReceiptPreflight:
    """Check syntax and binding only. NEVER issue a confirmation authority."""
    if not isinstance(receipt, Mapping) or not isinstance(expected, Mapping):
        return _reject("INVALID_ENVELOPE")
    if set(receipt) != _RECEIPT_KEYS:
        return _reject("RECEIPT_FIELDS_NOT_EXACT")
    if receipt.get("schema") != SCHEMA:
        return _reject("UNSUPPORTED_RECEIPT_SCHEMA")

    for field in _BOUND_FIELDS:
        value = receipt.get(field)
        want = expected.get(field)
        if not isinstance(value, str) or not _TOKEN.fullmatch(value):
            return _reject("INVALID_BOUND_FIELD")
        if not isinstance(want, str) or not _TOKEN.fullmatch(want):
            return _reject("UNTRUSTED_OR_MISSING_EXPECTATION")
        if value != want:
            return _reject("SCOPE_OR_INTENT_MISMATCH")

    for field in ("idempotency_key", "intent_digest"):
        if not _SHA256.fullmatch(receipt[field]):
            return _reject("INVALID_INTENT_DIGEST_OR_KEY")

    for field in ("provider_event_id", "effect_ref"):
        value = receipt.get(field)
        if not isinstance(value, str) or not _TOKEN.fullmatch(value):
            return _reject("INVALID_EFFECT_IDENTIFIER")

    if receipt.get("effect_state") != "EFFECT_CONFIRMED":
        return _reject("NOT_A_CONFIRMED_EFFECT")

    seq = receipt.get("witness_sequence")
    if isinstance(seq, bool) or not isinstance(seq, int) or seq < 1:
        return _reject("INVALID_WITNESS_SEQUENCE")
    if isinstance(last_witness_sequence, bool) or not isinstance(last_witness_sequence, int) or last_witness_sequence < 0:
        return _reject("UNTRUSTED_SEQUENCE_FLOOR")
    if seq <= last_witness_sequence:
        return _reject("STALE_OR_REPLAYED_SEQUENCE")

    raw_signature = receipt.get("witness_signature_b64")
    if not isinstance(raw_signature, str) or not 1 <= len(raw_signature) <= 8192:
        return _reject("INVALID_SIGNATURE_ENCODING")
    try:
        decoded = base64.b64decode(raw_signature, validate=True)
    except (ValueError, binascii.Error):
        return _reject("INVALID_SIGNATURE_ENCODING")
    if len(decoded) < 64:
        return _reject("SIGNATURE_SHAPE_TOO_SHORT")

    try:
        stamp = _utc(receipt.get("occurred_at"))
        start = _utc(authorized_at)
        observed = _utc(observed_at)
    except (ValueError, OverflowError, TypeError):
        return _reject("INVALID_TIMESTAMP")
    if not start <= stamp <= observed:
        return _reject("EFFECT_TIME_OUTSIDE_AUTHORIZED_WINDOW")

    # A syntactically plausible signature is still fully forgeable.
    # No authority is granted until an independently pinned verifier,
    # provider receipt, immutable witness and antirollback proof exist.
    return ReceiptPreflight(
        structural_valid=True,
        may_confirm=False,
        code="STRUCTURE_OK_EXTERNAL_CUSTODY_UNVERIFIED",
    )


__all__ = [
    "SCHEMA",
    "ReceiptPreflight",
    "parse_receipt_json",
    "preflight_receipt",
]
