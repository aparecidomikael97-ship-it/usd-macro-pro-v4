"""A216 LAB: synthetic two-signature key-custody continuity, NEVER authority.

Checks a host-supplied provisional issuer signature on a host-supplied
leaf public-key certificate, then delegates receipt math to A215. All keys,
certificates, fingerprints and history floors may be fabricated by the host.
No external roots, providers, custody ceremony or trusted clock are queried.
Every result has independent_origin_verified=False and may_confirm=False.
"""
from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from hashlib import sha256
import json
import re
from typing import Any, Mapping

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from atlasquant_aion_external_evidence_intake import (
    make_local_evidence_challenge, decode_candidate_json,
)
from labs.a212_synthetic_signed_effect_preflight import decode_strict_json_receipt
from labs.a215_synthetic_origin_bridge import inspect_synthetic_origin_bridge


SCHEMA = "ATLASQUANT_AION_SYNTHETIC_KEY_CUSTODY_CERT_V0"
DOMAIN = b"ATLASQUANT-AION/A216/SYNTHETIC-KEY-CUSTODY/V0\n"
_FIELDS = frozenset({
    "schema", "owner_id", "tenant_id", "workspace_id", "provider_id",
    "challenge_digest", "witness_root_fingerprint", "leaf_key_sha256",
    "issuer_key_sha256", "serial_id", "key_epoch", "not_before",
    "not_after", "key_status",
})
_SIGNED = _FIELDS | {"issuer_signature_b64"}
_HEX = re.compile(r"^[0-9a-f]{64}$")
_TOKEN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


@dataclass(frozen=True)
class SyntheticCustodyAssessment:
    local_binding_ok: bool
    receipt_signature_math_valid: bool
    custody_signature_math_valid: bool
    independent_origin_verified: bool
    may_confirm: bool
    code: str
    custody_digest: str


def _deny(
    code: str,
    *,
    local_ok: bool = False,
    receipt_math: bool = False,
) -> SyntheticCustodyAssessment:
    return SyntheticCustodyAssessment(
        local_binding_ok=local_ok,
        receipt_signature_math_valid=receipt_math,
        custody_signature_math_valid=False,
        independent_origin_verified=False,
        may_confirm=False,
        code=code,
        custody_digest="",
    )


def _hex(value: Any) -> bool:
    return isinstance(value, str) and _HEX.fullmatch(value) is not None


def _token(value: Any) -> bool:
    return isinstance(value, str) and _TOKEN.fullmatch(value) is not None


def _utc(value: Any, *, allow_datetime: bool = False) -> datetime:
    if isinstance(value, datetime) and allow_datetime:
        stamp = value
    elif isinstance(value, str):
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    else:
        raise ValueError("timestamp must be ISO text")
    if stamp.tzinfo is None or stamp.utcoffset() is None:
        raise ValueError("timezone required")
    return stamp.astimezone(timezone.utc)


def custody_signing_message(statement: Any) -> bytes:
    """Exact A216 synthetic bytes; NOT an X.509/RFC5280 certificate."""
    if not isinstance(statement, Mapping) or set(statement) != _FIELDS:
        raise ValueError("custody statement keys must be exact")
    if statement.get("schema") != SCHEMA:
        raise ValueError("unsupported custody statement")
    for field in ("owner_id", "tenant_id", "workspace_id", "provider_id", "serial_id"):
        if not _token(statement[field]):
            raise ValueError("invalid custody identity")
    for field in (
        "challenge_digest", "witness_root_fingerprint",
        "leaf_key_sha256", "issuer_key_sha256",
    ):
        if not _hex(statement[field]):
            raise ValueError("invalid custody digest")
    if type(statement["key_epoch"]) is not int or statement["key_epoch"] < 1:
        raise ValueError("invalid custody key epoch")
    if statement["key_status"] not in {"ACTIVE", "REVOKED"}:
        raise ValueError("invalid signed key status")
    start = _utc(statement["not_before"])
    end = _utc(statement["not_after"])
    if not start < end or end - start > timedelta(days=7):
        raise ValueError("invalid custody validity interval")
    try:
        canonical = json.dumps(
            dict(statement), sort_keys=True, ensure_ascii=False,
            separators=(",", ":"), allow_nan=False,
        ).encode("utf-8")
    except (ValueError, TypeError) as exc:
        raise ValueError("invalid custody serialization") from exc
    return DOMAIN + canonical


def inspect_synthetic_key_custody(
    outbox_record: Any,
    candidate: Any,
    signed_receipt: Any,
    custody_certificate: Any,
    *,
    candidate_pubkey_bytes: Any,
    provisional_issuer_pubkey_bytes: Any,
    provisional_issuer_fingerprint: Any,
    receipt_nonce_hex: Any,
    observed_at: Any,
    last_witness_sequence: Any,
    seen_provider_event_ids: Any,
    seen_receipt_nonces: Any,
    previous_key_epoch: Any,
    seen_custody_serial_ids: Any,
) -> SyntheticCustodyAssessment:
    """Compare both synthetic signatures; independent provenance is unproven."""
    origin = inspect_synthetic_origin_bridge(
        outbox_record, candidate, signed_receipt,
        candidate_pubkey_bytes=candidate_pubkey_bytes,
        receipt_nonce_hex=receipt_nonce_hex,
        observed_at=observed_at,
        last_witness_sequence=last_witness_sequence,
        seen_provider_event_ids=seen_provider_event_ids,
        seen_receipt_nonces=seen_receipt_nonces,
    )
    if not origin.local_binding_ok or not origin.signature_math_valid or origin.may_confirm:
        return _deny("A215_" + origin.code)

    if isinstance(candidate, str):
        try:
            candidate = decode_candidate_json(candidate)
        except ValueError:
            return _deny("LOCAL_CANDIDATE_AMBIGUOUS")
    if isinstance(custody_certificate, str):
        try:
            custody_certificate = decode_strict_json_receipt(custody_certificate)
        except ValueError:
            return _deny("AMBIGUOUS_CUSTODY_CERTIFICATE", local_ok=True, receipt_math=True)
    if not isinstance(custody_certificate, Mapping) or set(custody_certificate) != _SIGNED:
        return _deny("CUSTODY_ENVELOPE_NOT_EXACT", local_ok=True, receipt_math=True)
    if custody_certificate.get("schema") != SCHEMA:
        return _deny("CUSTODY_SCHEMA_UNSUPPORTED", local_ok=True, receipt_math=True)

    try:
        challenge = make_local_evidence_challenge(outbox_record)
        intent = json.loads(challenge.challenge_json)
    except (ValueError, OverflowError, TypeError):
        return _deny("LOCAL_CHALLENGE_UNAVAILABLE")
    expected = {
        "owner_id": intent["owner_id"],
        "tenant_id": intent["tenant_id"],
        "workspace_id": intent["workspace_id"],
        "provider_id": candidate["provider_id"],
        "challenge_digest": challenge.challenge_digest,
        "witness_root_fingerprint": candidate["witness_root_fingerprint"],
    }
    for field, value in expected.items():
        if custody_certificate[field] != value or type(custody_certificate[field]) is not type(value):
            return _deny("CUSTODY_SCOPE_OR_EFFECT_BINDING_MISMATCH", local_ok=True, receipt_math=True)

    if not isinstance(candidate_pubkey_bytes, bytes) or len(candidate_pubkey_bytes) != 32:
        return _deny("INVALID_LEAF_PUBLIC_KEY", local_ok=True, receipt_math=True)
    if not isinstance(provisional_issuer_pubkey_bytes, bytes) or len(provisional_issuer_pubkey_bytes) != 32:
        return _deny("INVALID_PROVISIONAL_ISSUER_KEY", local_ok=True, receipt_math=True)
    leaf_fp = sha256(candidate_pubkey_bytes).hexdigest()
    issuer_fp = sha256(provisional_issuer_pubkey_bytes).hexdigest()
    if leaf_fp == issuer_fp:
        return _deny("SAME_SIGNER_AND_PROVISIONAL_ISSUER", local_ok=True, receipt_math=True)
    if custody_certificate["leaf_key_sha256"] != leaf_fp or not _hex(custody_certificate["leaf_key_sha256"]):
        return _deny("LEAF_KEY_FINGERPRINT_MISMATCH", local_ok=True, receipt_math=True)
    if not _hex(provisional_issuer_fingerprint) or provisional_issuer_fingerprint != issuer_fp:
        return _deny("UNTRUSTED_PROVISIONAL_PIN_MISMATCH", local_ok=True, receipt_math=True)
    if custody_certificate["issuer_key_sha256"] != issuer_fp or not _hex(custody_certificate["issuer_key_sha256"]):
        return _deny("CERTIFICATE_ISSUER_KEY_MISMATCH", local_ok=True, receipt_math=True)

    if not _token(custody_certificate["serial_id"]):
        return _deny("INVALID_CUSTODY_SERIAL", local_ok=True, receipt_math=True)
    if (
        not isinstance(seen_custody_serial_ids, (set, frozenset, list, tuple))
        or any(not _token(x) for x in seen_custody_serial_ids)
    ):
        return _deny("UNTRUSTED_CUSTODY_SERIAL_HISTORY", local_ok=True, receipt_math=True)
    if custody_certificate["serial_id"] in seen_custody_serial_ids:
        return _deny("CUSTODY_SERIAL_REPLAY", local_ok=True, receipt_math=True)
    if type(previous_key_epoch) is not int or previous_key_epoch < 0:
        return _deny("UNTRUSTED_KEY_EPOCH_FLOOR", local_ok=True, receipt_math=True)
    epoch = custody_certificate["key_epoch"]
    if type(epoch) is not int or epoch <= previous_key_epoch:
        return _deny("CUSTODY_EPOCH_REPLAY_OR_ROLLBACK", local_ok=True, receipt_math=True)
    if epoch > previous_key_epoch + 1:
        return _deny("CUSTODY_EPOCH_HISTORY_GAP", local_ok=True, receipt_math=True)

    try:
        begin = _utc(custody_certificate["not_before"])
        end = _utc(custody_certificate["not_after"])
        event = _utc(candidate["occurred_at"])
        observed = _utc(observed_at, allow_datetime=True)
        message = custody_signing_message({
            field: custody_certificate[field] for field in _FIELDS
        })
    except (ValueError, TypeError, OverflowError, KeyError):
        return _deny("INVALID_SIGNED_CUSTODY_INTERVAL", local_ok=True, receipt_math=True)
    if not begin <= event <= end or event > observed:
        return _deny("LEAF_CERT_NOT_VALID_AT_CLAIMED_EFFECT_TIME", local_ok=True, receipt_math=True)
    if custody_certificate["key_status"] == "REVOKED":
        return _deny("SIGNED_KEY_REVOKED", local_ok=True, receipt_math=True)
    if custody_certificate["key_status"] != "ACTIVE":
        return _deny("INVALID_SIGNED_KEY_STATUS", local_ok=True, receipt_math=True)

    encoded = custody_certificate["issuer_signature_b64"]
    if not isinstance(encoded, str) or len(encoded) > 128:
        return _deny("INVALID_ISSUER_SIGNATURE_ENCODING", local_ok=True, receipt_math=True)
    try:
        signature = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error):
        return _deny("INVALID_ISSUER_SIGNATURE_ENCODING", local_ok=True, receipt_math=True)
    if len(signature) != 64 or base64.b64encode(signature).decode("ascii") != encoded:
        return _deny("INVALID_ISSUER_SIGNATURE_ENCODING", local_ok=True, receipt_math=True)
    try:
        Ed25519PublicKey.from_public_bytes(provisional_issuer_pubkey_bytes).verify(
            signature, message,
        )
    except (InvalidSignature, ValueError, TypeError):
        return _deny("CUSTODY_SIGNATURE_MATH_INVALID", local_ok=True, receipt_math=True)

    # Two signatures may be generated by one malicious host. The provisional
    # issuer was supplied in the same request; it has NO independent custody.
    return SyntheticCustodyAssessment(
        local_binding_ok=True,
        receipt_signature_math_valid=True,
        custody_signature_math_valid=True,
        independent_origin_verified=False,
        may_confirm=False,
        code="SYNTHETIC_TWO_SIGNATURES_VALID_PROVISIONAL_ISSUER_UNTRUSTED",
        custody_digest=sha256(message).hexdigest(),
    )


__all__ = [
    "SCHEMA", "DOMAIN", "SyntheticCustodyAssessment",
    "custody_signing_message", "inspect_synthetic_key_custody",
]
