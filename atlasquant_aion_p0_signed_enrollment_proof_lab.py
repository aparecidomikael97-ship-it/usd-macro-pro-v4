"""P0 HUMAN_OWNER signed enrollment receipt verifier, isolated LAB contract.

Cryptographic verification is useful but NOT independent issuer enrollment.
Trusted issuer root, expected scope, known nonces and high-water mark are
supplied by the caller here, without authenticated custody or durable CAS.
This verifier ALWAYS denies operational owner enrollment, even for a valid
Ed25519 signature. No network, disk IO, key generation, or worker actions.
"""
from __future__ import annotations

import base64
import binascii
from datetime import datetime, timezone
import json
import re
from typing import Any, Mapping

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

SCHEMA = "ATLASQUANT_P0_OWNER_ENROLLMENT_ATTESTATION_LAB_V1"
PURPOSE = "INDEPENDENT_OWNER_CUSTODY_ENROLLMENT_ONLY"
REQUIRED = frozenset({
    "schema", "purpose", "owner_id", "tenant_id", "workspace_id",
    "credential_id", "owner_public_key_sha256", "challenge_nonce",
    "issuer_id", "key_id", "evidence_id", "source_revision",
    "issued_at", "expires_at", "intent",
})
HEX64 = re.compile(r"^sha256:[0-9a-f]{64}$")
IDENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{3,127}$")
NONCE = re.compile(r"^[A-Za-z0-9_-]{24,160}$")


def canonical_receipt_bytes(receipt: Mapping[str, Any]) -> bytes:
    # One protocol-specific signing domain. Never sign arbitrary Python repr.
    return (
        "AION|P0|OWNER_ENROLLMENT_ATTESTATION|V1\n"
        + json.dumps(dict(receipt), sort_keys=True, separators=(",", ":"),
                     ensure_ascii=False, allow_nan=False)
    ).encode("utf-8")


def _decode(raw: Any, length: int) -> bytes:
    if not isinstance(raw, str) or not raw or len(raw) > 256:
        raise ValueError("encoded material invalid")
    if not re.fullmatch(r"[A-Za-z0-9_-]+", raw):
        raise ValueError("non-canonical base64url")
    try:
        out = base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4))
    except (ValueError, binascii.Error) as exc:
        raise ValueError("base64url decode invalid") from exc
    if len(out) != length or base64.urlsafe_b64encode(out).rstrip(b"=").decode() != raw:
        raise ValueError("base64url length/canonical mismatch")
    return out


def _parse(raw: Any) -> datetime | None:
    if not isinstance(raw, str) or not raw.endswith("Z"):
        return None
    try:
        value = datetime.fromisoformat(raw[:-1] + "+00:00")
        if value.utcoffset() is None:
            return None
        return value.astimezone(timezone.utc)
    except (ValueError, OverflowError, TypeError):
        return None


def _out(reason: str, *, checked: bool = False) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "state": "BLOCKED",
        "reason": reason,
        "signature_checked": checked,
        "cryptographic_format_consistent": checked,
        "independent_issuer_custody_verified": False,
        "human_owner_identity_established": False,
        "owner_enrollment_authorized": False,
        "trust_registry_modified": False,
        "owner_decision_authorized": False,
        "worker_armed": False,
        "external_action_executed": False,
        "executes_action": False,
    }


def inspect_signed_enrollment_lab(
    evidence: Mapping[str, Any] | None,
    *,
    pinned_issuer: Mapping[str, Any] | None,
    expected_scope: Mapping[str, str],
    expected_nonce: str,
    expected_fingerprint: str,
    prior_source_revision: int,
    seen_evidence_ids: frozenset[str],
    now: str,
) -> dict[str, Any]:
    """Check a hypothetical independently signed statement; NEVER enroll.

    All external values are synthetic and caller-supplied in LAB. The proof
    that an issuer actually has independent custody CANNOT come from them.
    """
    if not isinstance(evidence, Mapping) or set(evidence) != {"receipt", "signature_b64"}:
        return _out("P0_EVIDENCE_SHAPE_INVALID")
    row = evidence.get("receipt")
    if not isinstance(row, Mapping) or set(row) != REQUIRED:
        return _out("P0_RECEIPT_SHAPE_INVALID")
    row = dict(row)
    if row["schema"] != SCHEMA or row["purpose"] != PURPOSE or row["intent"] != "ENROLL":
        return _out("P0_RECEIPT_DOMAIN_INVALID")
    if not isinstance(pinned_issuer, Mapping) or set(pinned_issuer) != {
        "issuer_id", "key_id", "public_key_b64", "status"
    }:
        return _out("P0_PINNED_ISSUER_UNAVAILABLE")
    if pinned_issuer["status"] != "ACTIVE":
        return _out("P0_ISSUER_NOT_ACTIVE")
    for name in ("issuer_id", "key_id"):
        value = row[name]
        if (not isinstance(value, str) or not IDENT.fullmatch(value)
                or value != pinned_issuer[name]):
            return _out("P0_ISSUER_IDENTITY_MISMATCH")
    if not isinstance(expected_scope, Mapping) or set(expected_scope) != {
        "owner_id", "tenant_id", "workspace_id", "credential_id"
    }:
        return _out("P0_EXPECTED_SCOPE_UNAVAILABLE")
    for name in ("owner_id", "tenant_id", "workspace_id", "credential_id"):
        expected, actual = expected_scope[name], row[name]
        if not isinstance(expected, str) or not expected or actual != expected:
            return _out("P0_SCOPE_MISMATCH")
    if (not isinstance(expected_nonce, str) or not NONCE.fullmatch(expected_nonce)
            or row["challenge_nonce"] != expected_nonce):
        return _out("P0_NONCE_MISMATCH")
    if (not isinstance(expected_fingerprint, str)
            or not HEX64.fullmatch(expected_fingerprint)
            or row["owner_public_key_sha256"] != expected_fingerprint):
        return _out("P0_CREDENTIAL_KEY_MISMATCH")
    evidence_id = row["evidence_id"]
    if not isinstance(evidence_id, str) or not IDENT.fullmatch(evidence_id):
        return _out("P0_EVIDENCE_ID_INVALID")
    if not isinstance(seen_evidence_ids, frozenset):
        return _out("P0_REPLAY_STATE_UNAVAILABLE")
    if evidence_id in seen_evidence_ids:
        return _out("P0_REPLAY_DETECTED")
    revision = row["source_revision"]
    if (type(prior_source_revision) is not int or prior_source_revision < 0
            or type(revision) is not int or revision != prior_source_revision + 1):
        return _out("P0_REVISION_NOT_MONOTONIC")
    issued, expires, current = _parse(row["issued_at"]), _parse(row["expires_at"]), _parse(now)
    if issued is None or expires is None or current is None:
        return _out("P0_TIME_INVALID")
    if (issued > current or current >= expires or expires <= issued
            or (expires - issued).total_seconds() > 180):
        return _out("P0_TIME_WINDOW_INVALID")
    try:
        public_key = Ed25519PublicKey.from_public_bytes(_decode(pinned_issuer["public_key_b64"], 32))
        signature = _decode(evidence["signature_b64"], 64)
        public_key.verify(signature, canonical_receipt_bytes(row))
    except (InvalidSignature, ValueError, TypeError, OverflowError):
        return _out("P0_ATTESTATION_SIGNATURE_INVALID")
    # Even a signed claim has no verified independent issuer custody here.
    # Authenticated enrollment, persisted anti-replay and real device proof
    # require another, owner-approved operational boundary.
    return _out("P0_SIGNATURE_CONSISTENT_BUT_ISSUER_CUSTODY_UNVERIFIED", checked=True)
