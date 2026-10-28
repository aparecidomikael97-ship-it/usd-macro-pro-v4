"""A212 LAB: verify synthetic Ed25519 effect statements, never operational authority.

An authentic signature under a caller-supplied public key proves only that the
corresponding private key signed the precise bytes. It DOES NOT demonstrate an
independent signer, provider effect, owner authorization or safe Outbox state.
Every result has may_confirm=False. No keys are created in this module.
"""
from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
import re
from typing import Any, Mapping

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey


SCHEMA = "ATLASQUANT_AION_SIGNED_EFFECT_STATEMENT_SYNTHETIC_V0"
DOMAIN = b"ATLASQUANT-AION/A212/SYNTHETIC-EFFECT-STATEMENT/V0\n"
_EXPECTED_FIELDS = frozenset({
    "owner_id", "tenant_id", "workspace_id", "operation_kind",
    "intent_digest", "idempotency_key", "provider_id", "witness_root_id",
    "witness_checkpoint_hash", "receipt_nonce_hex", "subject_digest",
})
_SIGNED_FIELDS = _EXPECTED_FIELDS | frozenset({
    "schema", "provider_event_id", "effect_ref", "effect_state",
    "occurred_at", "witness_sequence",
})
_RECEIPT_FIELDS = _SIGNED_FIELDS | {"signature_b64"}
_TOKEN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_HEX64 = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class SyntheticSignatureAssessment:
    mathematically_valid_signature: bool
    may_confirm: bool
    code: str
    statement_digest: str


def _deny(code: str) -> SyntheticSignatureAssessment:
    return SyntheticSignatureAssessment(False, False, code, "")


def _utc(value: Any) -> datetime:
    if not isinstance(value, str):
        raise ValueError("timestamp must be ISO-8601 text")
    stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if stamp.tzinfo is None or stamp.utcoffset() is None:
        raise ValueError("timezone required")
    return stamp.astimezone(timezone.utc)


def _token(value: Any) -> bool:
    return isinstance(value, str) and _TOKEN.fullmatch(value) is not None


def _hex64(value: Any) -> bool:
    return isinstance(value, str) and _HEX64.fullmatch(value) is not None


def signing_message(statement: Any) -> bytes:
    """A212-specific deterministic byte format; NOT RFC 8785 or RFC 9421."""
    if not isinstance(statement, Mapping) or set(statement) != _SIGNED_FIELDS:
        raise ValueError("signed payload keys must be exact")
    if statement.get("schema") != SCHEMA:
        raise ValueError("unknown statement schema")
    if not all(
        _token(statement[name]) for name in (
            "owner_id", "tenant_id", "workspace_id", "operation_kind",
            "provider_id", "witness_root_id", "provider_event_id",
            "effect_ref",
        )
    ):
        raise ValueError("invalid string field")
    if not all(
        _hex64(statement[name]) for name in (
            "intent_digest", "idempotency_key", "witness_checkpoint_hash",
            "receipt_nonce_hex", "subject_digest",
        )
    ):
        raise ValueError("invalid hex field")
    if statement.get("effect_state") != "EFFECT_CONFIRMED":
        raise ValueError("not a claimed confirmed effect")
    if type(statement.get("witness_sequence")) is not int or statement["witness_sequence"] < 1:
        raise ValueError("invalid witness sequence")
    _utc(statement["occurred_at"])
    canonical = json.dumps(
        dict(statement),
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return DOMAIN + canonical


def decode_strict_json_receipt(raw: Any) -> dict[str, Any]:
    """Refuse duplicate keys, oversized JSON and non-finite constants."""
    if not isinstance(raw, str) or len(raw.encode("utf-8")) > 8192:
        raise ValueError("receipt must be UTF-8 JSON <=8192 bytes")

    def unique_pairs(pairs):
        out = {}
        for key, value in pairs:
            if key in out:
                raise ValueError("duplicate key")
            out[key] = value
        return out

    def reject_constant(value):
        raise ValueError("non-finite JSON constant")

    try:
        result = json.loads(
            raw, object_pairs_hook=unique_pairs,
            parse_constant=reject_constant,
        )
    except (ValueError, TypeError) as exc:
        raise ValueError("invalid or ambiguous receipt JSON") from exc
    if not isinstance(result, dict):
        raise ValueError("receipt root must be object")
    return result


def preflight_signed_synthetic_effect(
    receipt: Any,
    *,
    expected: Any,
    candidate_pubkey_bytes: Any,
    authorized_at: Any,
    observed_at: Any,
    last_witness_sequence: Any,
    seen_provider_event_ids: Any,
    seen_receipt_nonces: Any,
) -> SyntheticSignatureAssessment:
    """Validate a synthetic signature and causal bindings; NEVER confirm."""
    if not isinstance(receipt, Mapping) or set(receipt) != _RECEIPT_FIELDS:
        return _deny("RECEIPT_ENVELOPE_NOT_EXACT")
    if not isinstance(expected, Mapping) or set(expected) != _EXPECTED_FIELDS:
        return _deny("EXPECTATION_ENVELOPE_NOT_EXACT")
    if receipt.get("schema") != SCHEMA:
        return _deny("UNSUPPORTED_STATEMENT_SCHEMA")

    for field in _EXPECTED_FIELDS:
        val = expected[field]
        if field in {
            "intent_digest", "idempotency_key", "witness_checkpoint_hash",
            "receipt_nonce_hex", "subject_digest",
        }:
            if not _hex64(val) or not _hex64(receipt[field]):
                return _deny("INVALID_EXPECTED_OR_RECEIPT_BINDING")
        elif not _token(val) or not _token(receipt[field]):
            return _deny("INVALID_EXPECTED_OR_RECEIPT_BINDING")
        if receipt[field] != val:
            return _deny("SIGNED_CAUSAL_BINDING_MISMATCH")

    for field in ("provider_event_id", "effect_ref"):
        if not _token(receipt[field]):
            return _deny("INVALID_PROVIDER_EFFECT_ID")
    if receipt.get("effect_state") != "EFFECT_CONFIRMED":
        return _deny("EFFECT_NOT_CONFIRMED")

    seq = receipt.get("witness_sequence")
    if type(seq) is not int or seq < 1:
        return _deny("INVALID_WITNESS_SEQUENCE")
    if type(last_witness_sequence) is not int or last_witness_sequence < 0:
        return _deny("INVALID_SEQUENCE_FLOOR")
    if seq <= last_witness_sequence:
        return _deny("STALE_WITNESS_SEQUENCE")

    if not isinstance(seen_provider_event_ids, (set, frozenset, list, tuple)) or any(
        not _token(item) for item in seen_provider_event_ids
    ):
        return _deny("INVALID_EVENT_HISTORY")
    if not isinstance(seen_receipt_nonces, (set, frozenset, list, tuple)) or any(
        not _hex64(item) for item in seen_receipt_nonces
    ):
        return _deny("INVALID_NONCE_HISTORY")
    if receipt["provider_event_id"] in seen_provider_event_ids:
        return _deny("PROVIDER_EVENT_REPLAY")
    if receipt["receipt_nonce_hex"] in seen_receipt_nonces:
        return _deny("RECEIPT_NONCE_REPLAY")

    try:
        occurred = _utc(receipt.get("occurred_at"))
        authorized = _utc(authorized_at)
        observed = _utc(observed_at)
    except (ValueError, TypeError, OverflowError):
        return _deny("INVALID_TIME_WINDOW")
    if not authorized <= occurred <= observed:
        return _deny("EFFECT_TIME_OUTSIDE_AUTHORIZATION")

    if not isinstance(candidate_pubkey_bytes, bytes) or len(candidate_pubkey_bytes) != 32:
        return _deny("INVALID_UNATTESTED_PUBLIC_KEY")
    sig = receipt.get("signature_b64")
    if not isinstance(sig, str) or len(sig) > 128:
        return _deny("INVALID_SIGNATURE_ENCODING")
    try:
        decoded = base64.b64decode(sig, validate=True)
    except (ValueError, binascii.Error):
        return _deny("INVALID_SIGNATURE_ENCODING")
    if len(decoded) != 64 or base64.b64encode(decoded).decode("ascii") != sig:
        return _deny("INVALID_SIGNATURE_ENCODING")

    try:
        message = signing_message({
            name: receipt[name] for name in _SIGNED_FIELDS
        })
        Ed25519PublicKey.from_public_bytes(candidate_pubkey_bytes).verify(
            decoded, message,
        )
    except (InvalidSignature, ValueError, TypeError):
        return _deny("SIGNATURE_MATH_NOT_VALID")

    # A correctly verified signature can be entirely host-generated, signed
    # by a test key, or contain a false provider effect claim. Key provenance,
    # real provider effect and external monotonic witness are NOT established.
    return SyntheticSignatureAssessment(
        mathematically_valid_signature=True,
        may_confirm=False,
        code="SIGNATURE_MATH_OK_EXTERNAL_EFFECT_AND_CUSTODY_UNPROVEN",
        statement_digest=sha256(message).hexdigest(),
    )


__all__ = [
    "SCHEMA", "DOMAIN", "SyntheticSignatureAssessment",
    "signing_message", "decode_strict_json_receipt",
    "preflight_signed_synthetic_effect",
]
