"""Verify two synthetic external signatures over calendar document hashes.

The verified math does NOT establish publisher/TLS origin or independent
identity of the two signers. Trust keys are caller-configured, not pinned or
audited by this module. No private key, network call, signing or job runs here.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import re
from typing import Any, Mapping

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from atlasquant_trader_calendar_document_bytes_gate_lab import (
    audit_three_daily_calendar_document_bytes_lab,
)
from atlasquant_trader_official_change_detection_lab import _utc

SCHEMA = "ATLASQUANT_TRADER_CALENDAR_TWO_WITNESS_SIGNATURES_LAB_V1"
ROLES = frozenset(("SOURCE_FETCH_OBSERVER", "INDEPENDENT_REVIEW_OBSERVER"))
CHALLENGE_KEYS = frozenset(("nonce_hex", "issued_at_utc"))
KEY_FIELDS = frozenset(("role", "public_key_hex"))
SIGNATURE_FIELDS = frozenset(("key_id", "role", "signed_at_utc", "signature_hex"))
HEX32 = re.compile(r"^[0-9a-f]{32}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
HEX128 = re.compile(r"^[0-9a-f]{128}$")
KEY_ID = re.compile(r"^[A-Z][A-Z0-9_]{3,47}$")
CHALLENGE_LIFETIME = timedelta(minutes=15)


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_BLOCKED", "reason": reason,
        "document_audit": None, "payload_sha256": None,
        "signature_math_verified": False,
        "distinct_configured_keys_verified": False,
        "independent_signer_identities_verified": False,
        "official_publisher_origin_verified": False,
        "tls_custody_verified": False,
        "witnessed_external_timestamp_verified": False,
        "replay_prevention_operational": False,
        "source_data_real_time_verified": False,
        "three_daily_updates_verified": False,
        "currency_bias": "AGUARDAR", "publishable": False,
        "can_feed_live_radar": False, "trade_authorized": False,
        "worker_enabled": False, "scheduler_enabled": False,
        "external_http_requests": 0, "new_cost_brl": 0,
    }


def _signed_payload(audit: Mapping[str, Any], challenge: Mapping[str, str]) -> bytes:
    """Canonical context-bound signed bytes; no request-supplied payload text."""
    document_review = audit["calendar_review"]
    context = {
        "version": SCHEMA,
        "challenge_nonce_hex": challenge["nonce_hex"],
        "issued_at_utc": challenge["issued_at_utc"],
        "evaluation_at_utc": audit["as_of_utc"],
        "local_document_chain_sha256": audit["local_chain_head_sha256"],
        "document_receipt_count": audit["checked_document_count"],
        "calendar_change_count": document_review["change_count"],
        "claimed_daily_capture_count": document_review["claimed_capture_count"],
        "origin_is_unattested": True,
    }
    encoded = json.dumps(context, sort_keys=True,
                         separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return b"ATLASQUANT_TRADER_LAB_CUSTODY_V1\n" + encoded


def verify_calendar_two_witness_signatures_lab(
    captures: Any, challenge: Any, witnesses: Any,
    configured_public_keys: Any, *, at: datetime,
) -> dict[str, Any]:
    """Recompute supplied bytes, then verify two signatures on one payload.

    This function deliberately has no path to promoting signature math to
    actual source origin, independently established identity or live FX bias.
    """
    if not isinstance(at, datetime) or at.tzinfo is None or at.utcoffset() is None:
        raise ValueError("Timezone-aware evaluation clock required")
    now = at.astimezone(timezone.utc)
    audit = audit_three_daily_calendar_document_bytes_lab(captures, at=now)
    if audit.get("state") != "LAB_DOCUMENT_BYTES_CONSISTENT_UNATTESTED":
        return _blocked("DOCUMENT_BYTES_AUDIT_NOT_ACCEPTABLE")
    if audit["checked_document_count"] == 0:
        return _blocked("NO_DOCUMENTS_TO_WITNESS")

    if not isinstance(challenge, Mapping) or set(challenge) != CHALLENGE_KEYS:
        return _blocked("INVALID_OR_MISSING_CHALLENGE")
    nonce = challenge["nonce_hex"]
    issued = _utc(challenge["issued_at_utc"])
    if (not isinstance(nonce, str) or HEX32.fullmatch(nonce) is None
            or issued is None or issued > now
            or now - issued > CHALLENGE_LIFETIME):
        return _blocked("EXPIRED_OR_INVALID_CHALLENGE")

    if (not isinstance(configured_public_keys, Mapping)
            or len(configured_public_keys) != 2):
        return _blocked("TWO_CONFIGURED_PUBLIC_KEYS_REQUIRED")
    keys = {}
    raw_values = set()
    roles = set()
    for key_id, details in configured_public_keys.items():
        if (not isinstance(key_id, str) or KEY_ID.fullmatch(key_id) is None
                or not isinstance(details, Mapping) or set(details) != KEY_FIELDS
                or not isinstance(details.get("role"), str)
                or details["role"] not in ROLES
                or not isinstance(details.get("public_key_hex"), str)
                or HEX64.fullmatch(details["public_key_hex"]) is None):
            return _blocked("INVALID_OR_UNREVIEWED_KEY_CONFIGURATION")
        value = details["public_key_hex"]
        if value in raw_values or details["role"] in roles:
            return _blocked("PUBLIC_KEYS_OR_SIGNER_ROLES_NOT_DISTINCT")
        try:
            keys[key_id] = (details["role"], Ed25519PublicKey.from_public_bytes(
                bytes.fromhex(value)))
        except (ValueError, TypeError):
            return _blocked("INVALID_ED25519_PUBLIC_KEY")
        raw_values.add(value)
        roles.add(details["role"])
    if roles != ROLES:
        return _blocked("BOTH_WITNESS_ROLES_REQUIRED")

    if not isinstance(witnesses, (list, tuple)) or len(witnesses) != 2:
        return _blocked("TWO_WITNESS_SIGNATURES_REQUIRED")
    payload = _signed_payload(audit, challenge)
    seen = set()
    for witness in witnesses:
        if not isinstance(witness, Mapping) or set(witness) != SIGNATURE_FIELDS:
            return _blocked("UNSUPPORTED_SIGNATURE_FIELDS")
        key_id = witness["key_id"]
        signed_at = _utc(witness["signed_at_utc"])
        signature = witness["signature_hex"]
        if (not isinstance(key_id, str) or key_id not in keys
                or key_id in seen or witness["role"] != keys[key_id][0]
                or signed_at is None or not issued <= signed_at <= now
                or not isinstance(signature, str)
                or HEX128.fullmatch(signature) is None):
            return _blocked("UNKNOWN_DUPLICATE_OR_INVALID_WITNESS")
        seen.add(key_id)
        try:
            keys[key_id][1].verify(bytes.fromhex(signature), payload)
        except (InvalidSignature, ValueError, TypeError):
            return _blocked("INVALID_OR_REPLAYED_WITNESS_SIGNATURE")
    if seen != set(keys):
        return _blocked("MISSING_CONFIGURED_WITNESS")

    result = _blocked("SIGNED_BY_CONFIGURED_KEYS_NOT_INDEPENDENTLY_IDENTIFIED")
    result.update({
        "state": "LAB_TWO_SIGNATURES_MATH_ONLY",
        "as_of_utc": now.isoformat(),
        "document_audit": audit,
        "payload_sha256": sha256(payload).hexdigest(),
        "signature_math_verified": True,
        "distinct_configured_keys_verified": True,
        "configured_key_ids": sorted(keys),
        "note": ("Duas assinaturas Ed25519 matematicamente validas sobre bytes "
                 "documentais nao comprovam independencia dos signatarios, "
                 "origem oficial, TLS, horario testemunhado, nonce consumido "
                 "nem dados em tempo real."),
    })
    return result


__all__ = ["SCHEMA", "verify_calendar_two_witness_signatures_lab"]
