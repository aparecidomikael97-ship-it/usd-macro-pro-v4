"""Offline Ed25519 receipt check for FX forecast entries; never a time proof.

The caller supplies the public key/fingerprint, alleged server acceptance time,
and original forecast claims. A valid signature proves only that the holder of
that key signed the bytes; it does not establish who owns the key, whether the
key was pinned before an event, or whether the server clock was truthful.
"""
from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
import re
from typing import Any

from atlasquant_trader_fx_forecast_precommit_lab import (
    ForecastPrecommitClaim, verify_fx_precommit_receipts_lab,
)

SCHEMA = "ATLASQUANT_TRADER_FX_SIGNED_FORECAST_RECEIPT_LAB_V1"
RECEIPT_SCOPE = "ATLASQUANT_FX_FORECAST_ENTRY_ED25519_V1"
_HEX64 = re.compile(r"[0-9a-f]{64}\Z")
_NONCE = re.compile(r"[0-9a-f]{32,64}\Z")
_ID = re.compile(r"[A-Z0-9][A-Z0-9_-]{2,63}\Z")


@dataclass(frozen=True)
class SignedTimestampReceiptClaim:
    receipt_id: str
    signer_id: str
    opportunity_id: str
    entry_sha256_claim: str
    nonce_hex: str
    accepted_at: datetime
    signature_b64: str


def _utc(value: Any) -> datetime | None:
    if (not isinstance(value, datetime) or value.tzinfo is None
            or value.utcoffset() is None or value.microsecond != 0):
        return None
    return value.astimezone(timezone.utc)


def _hex64(value: Any) -> bool:
    return isinstance(value, str) and _HEX64.fullmatch(value) is not None


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_SIGNED_RECEIPT_BLOCKED",
        "reason": reason, "opportunity_id": None,
        "receipt_id": None, "signed_entry_sha256": None,
        "signed_acceptance_time_claim_utc": None,
        "locally_valid_precommit_chain": False,
        "detached_ed25519_signature_valid_for_supplied_key": False,
        "supplied_public_key_matches_supplied_fingerprint": False,
        "signed_time_claim_precedes_outcome": False,
        "signer_identity_independently_authenticated": False,
        "public_key_previously_pinned_independently": False,
        "timestamp_authority_independently_trusted": False,
        "server_clock_independently_authenticated": False,
        "historical_pre_event_prediction_proven": False,
        "economic_vintages_independently_verified": False,
        "can_feed_validated_backtest": False,
        "validated_accuracy": None, "calibrated_probability": None,
        "operational_bias": "AGUARDAR", "publishable": False,
        "trade_authorized": False, "worker_enabled": False,
        "scheduler_enabled": False, "http_requests": 0,
        "file_writes": 0, "new_cost_brl": 0,
    }


def canonical_signed_receipt_payload_lab(receipt: Any) -> bytes | None:
    """Exact bytes for a detached Ed25519 signature, without signature field."""
    if not isinstance(receipt, SignedTimestampReceiptClaim):
        return None
    accepted = _utc(receipt.accepted_at)
    if (accepted is None or not isinstance(receipt.receipt_id, str)
            or _ID.fullmatch(receipt.receipt_id) is None
            or not isinstance(receipt.signer_id, str)
            or _ID.fullmatch(receipt.signer_id) is None
            or not isinstance(receipt.opportunity_id, str)
            or _ID.fullmatch(receipt.opportunity_id) is None
            or not _hex64(receipt.entry_sha256_claim)
            or not isinstance(receipt.nonce_hex, str)
            or _NONCE.fullmatch(receipt.nonce_hex) is None
            or len(receipt.nonce_hex) % 2 != 0):
        return None
    payload = {
        "scope": RECEIPT_SCOPE,
        "receipt_id": receipt.receipt_id,
        "signer_id": receipt.signer_id,
        "opportunity_id": receipt.opportunity_id,
        "entry_sha256": receipt.entry_sha256_claim,
        "nonce_hex": receipt.nonce_hex,
        "accepted_at_claim_utc": accepted.isoformat().replace("+00:00", "Z"),
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True).encode("ascii")


def inspect_signed_fx_receipt_lab(
    forecast_records: Any, chain_entries: Any, chain_head_sha256: Any,
    *, opportunity_id: Any, signed_receipt: Any,
    expected_nonce_hex: Any, expected_signer_id: Any,
    supplied_public_key_raw: Any, supplied_public_key_sha256: Any,
    evaluated_at_utc: Any,
) -> dict[str, Any]:
    """Audit a detached signature against a caller-supplied key and chronology.

    Even a passing result MUST remain UNATTESTED without an external,
    independently established signing-key trust root and timestamp policy.
    """
    out = _blocked("INVALID_EVALUATION_OR_RECEIPT_ARGUMENTS")
    evaluated = _utc(evaluated_at_utc)
    if (evaluated is None or not isinstance(opportunity_id, str)
            or not isinstance(signed_receipt, SignedTimestampReceiptClaim)):
        return out
    pre = verify_fx_precommit_receipts_lab(
        forecast_records, chain_entries, chain_head_sha256,
        evaluated_at_utc=evaluated_at_utc)
    if pre["state"] != "LAB_PRECOMMIT_RECEIPTS_LOCALLY_MATCH_UNATTESTED":
        out["reason"] = "FORECAST_CHAIN_NOT_LOCALLY_VERIFIED"
        return out
    out["locally_valid_precommit_chain"] = True
    matches = [r for r in forecast_records if isinstance(r, ForecastPrecommitClaim)
               and r.opportunity_id == opportunity_id]
    refs = [v for v in pre["chain_entries"] if v["opportunity_id"] == opportunity_id]
    if len(matches) != 1 or len(refs) != 1:
        out["reason"] = "FORECAST_OPPORTUNITY_NOT_FOUND"
        return out
    row, entry = matches[0], refs[0]
    out["opportunity_id"] = opportunity_id
    out["receipt_id"] = signed_receipt.receipt_id
    accepted = _utc(signed_receipt.accepted_at)
    issued = _utc(row.prediction_issued_at)
    outcome_start = _utc(row.outcome_start_at)
    if (accepted is None or signed_receipt.opportunity_id != opportunity_id
            or signed_receipt.entry_sha256_claim != entry["entry_sha256_claim"]
            or signed_receipt.signer_id != expected_signer_id
            or signed_receipt.nonce_hex != expected_nonce_hex):
        out["reason"] = "RECEIPT_ENTRY_SIGNER_OR_NONCE_MISMATCH"
        return out
    if not issued <= accepted < outcome_start or accepted > evaluated:
        out["reason"] = "SIGNED_TIME_CLAIM_NOT_IN_PRE_EVENT_WINDOW"
        return out
    out["signed_time_claim_precedes_outcome"] = True
    out["signed_acceptance_time_claim_utc"] = accepted.isoformat().replace("+00:00", "Z")
    payload = canonical_signed_receipt_payload_lab(signed_receipt)
    if payload is None:
        out["reason"] = "INVALID_CANONICAL_RECEIPT_FIELDS"
        return out
    if (not isinstance(supplied_public_key_raw, bytes)
            or len(supplied_public_key_raw) != 32
            or not _hex64(supplied_public_key_sha256)
            or sha256(supplied_public_key_raw).hexdigest() != supplied_public_key_sha256):
        out["reason"] = "PUBLIC_KEY_OR_CALLER_FINGERPRINT_INVALID"
        return out
    out["supplied_public_key_matches_supplied_fingerprint"] = True
    if not isinstance(signed_receipt.signature_b64, str):
        out["reason"] = "INVALID_DETACHED_SIGNATURE_ENCODING"
        return out
    try:
        signature = base64.b64decode(signed_receipt.signature_b64, validate=True)
    except (ValueError, binascii.Error):
        out["reason"] = "INVALID_DETACHED_SIGNATURE_ENCODING"
        return out
    if len(signature) != 64:
        out["reason"] = "INVALID_DETACHED_SIGNATURE_SIZE"
        return out
    try:
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    except ImportError:
        out["reason"] = "CRYPTOGRAPHY_VERIFIER_UNAVAILABLE_NO_FALLBACK"
        return out
    try:
        Ed25519PublicKey.from_public_bytes(supplied_public_key_raw).verify(signature, payload)
    except (InvalidSignature, ValueError):
        out["reason"] = "DETACHED_SIGNATURE_DOES_NOT_VERIFY"
        return out

    out.update({
        "state": "LAB_SIGNED_RECEIPT_CRYPTO_MATCH_UNTRUSTED_SIGNER",
        "reason": "VALID_SIGNATURE_FOR_CALLER_KEY_NOT_AN_INDEPENDENT_TIMESTAMP_ATTESTATION",
        "signed_entry_sha256": entry["entry_sha256_claim"],
        "detached_ed25519_signature_valid_for_supplied_key": True,
    })
    return out


__all__ = ["SCHEMA", "RECEIPT_SCOPE", "SignedTimestampReceiptClaim",
           "canonical_signed_receipt_payload_lab", "inspect_signed_fx_receipt_lab"]
