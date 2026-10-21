"""AION P0 H0 LAB: cryptographic cross-check of TWO simulated witness receipts.

This module validates Ed25519 bytes under two *caller-supplied* test keys.
It NEVER enrolls issuer keys, authenticates external identities, performs
fresh remote readback, stores nonces, calls a provider, or permits execution.
A fully valid signed fixture is still HARD_NO_GO and cannot stop rollback
of the executor plus caller-supplied pins. Not an authorization API.
"""
from __future__ import annotations

import base64
import binascii
from datetime import datetime, timedelta
import hashlib
import json
import re
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

LAB_SCHEMA = "AION_P0_H0_DUAL_SIGNED_TRANSCRIPT_LAB_V1"
DOMAIN = b"AION_P0_H0_WITNESS_LAB_V1\x00"
RESERVATION = "FIRST_ATTEMPT_RESERVED"
READBACK = "HEAD_READBACK"
RESERVE_SCHEMA = "AION_H0_RESERVATION_TRANSCRIPT_LAB_V1"
READ_SCHEMA = "AION_H0_HEAD_READBACK_TRANSCRIPT_LAB_V1"
COMMON = frozenset((
    "schema", "kind", "issuer_id", "key_id", "scope_digest", "request_id",
    "intent_id", "attempt_nonce", "epoch", "sequence", "head_digest",
    "version_id",
))
RES_FIELDS = COMMON | {"issued_at_utc"}
READ_FIELDS = COMMON | {"reservation_sha256", "challenge_nonce", "observed_at_utc"}
PINS_FIELDS = frozenset((
    "reservation_public_key_b64url", "readback_public_key_b64url",
    "reservation_key_id", "readback_key_id", "issuer_id", "scope_digest",
    "request_id", "intent_id", "attempt_nonce", "challenge_nonce",
    "minimum_epoch", "minimum_sequence", "expected_version_id",
    "expected_head_digest",
))
ENVELOPE_FIELDS = frozenset(("payload", "signature_b64url"))
HEX = re.compile(r"[0-9a-f]{64}\Z")
IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:/@-]{7,127}\Z")
DATE = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z\Z")
AUTHORITY_FALSE = {
    "issuer_independently_enrolled": False,
    "witness_independent_of_executor": False,
    "fresh_external_readback_authenticated": False,
    "external_nonce_durably_reserved": False,
    "credential_revocation_authenticated": False,
    "producer_effect_or_no_effect_authenticated": False,
    "human_owner_authenticated": False,
    "physical_rollback_ruled_out": False,
    "first_external_effect_allowed": False,
    "worker_arming_allowed": False,
    "automatic_retry_allowed": False,
    "external_action_executed": False,
}
PERMANENT_GAPS = (
    "EXTERNAL_ISSUER_NOT_ENROLLED",
    "INDEPENDENT_READBACK_NOT_ESTABLISHED",
    "EXTERNAL_NONCE_CUSTODY_NOT_ESTABLISHED",
    "TRUSTED_FRESHNESS_NOT_ESTABLISHED",
    "PRODUCER_RECEIPT_NOT_AUTHENTICATED",
    "HUMAN_OWNER_NOT_AUTHENTICATED",
    "H0_ROLLBACK_NOT_RULED_OUT",
    "QUALITY_CANONICAL_NOT_GREEN",
)


def canonical_bytes(payload: dict[str, Any]) -> bytes:
    """Domain-separated signed bytes, NOT permission to sign production data."""
    return DOMAIN + json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


def _decode_canonical(value: Any, size: int) -> bytes | None:
    expected_length = 86 if size == 64 else 43
    if (type(value) is not str or len(value) != expected_length
            or not re.fullmatch(r"[A-Za-z0-9_-]+", value)):
        return None
    try:
        raw = base64.b64decode(
            value.encode("ascii") + b"=" * (-len(value) % 4),
            altchars=b"-_", validate=True,
        )
    except (ValueError, binascii.Error, UnicodeError):
        return None
    if (len(raw) != size
            or base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii") != value):
        return None
    return raw


def _date(value: Any) -> datetime | None:
    if type(value) is not str or DATE.fullmatch(value) is None:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return None


def _is_id(value: Any) -> bool:
    return type(value) is str and IDENTIFIER.fullmatch(value) is not None


def _is_hex(value: Any) -> bool:
    return type(value) is str and HEX.fullmatch(value) is not None


def _valid_payload(payload: Any, *, readback: bool) -> bool:
    keys = READ_FIELDS if readback else RES_FIELDS
    if type(payload) is not dict or frozenset(payload) != keys:
        return False
    # Never execute untrusted Python objects' __eq__/__ne__ on schema/kind.
    # Reject them before any canonical JSON serialization or comparisons.
    if type(payload["schema"]) is not str or type(payload["kind"]) is not str:
        return False
    if any(not _is_id(payload[k]) for k in (
        "issuer_id", "key_id", "request_id", "intent_id", "attempt_nonce",
        "version_id",
    )):
        return False
    if not (_is_hex(payload["scope_digest"]) and _is_hex(payload["head_digest"])):
        return False
    if any(type(payload[k]) is not int or not 0 <= payload[k] < 2**63 - 1
           for k in ("epoch", "sequence")):
        return False
    if payload["epoch"] == 0 or payload["sequence"] == 0:
        return False
    if readback:
        if (payload["schema"] != READ_SCHEMA or payload["kind"] != READBACK
                or not _is_hex(payload["reservation_sha256"])
                or not _is_id(payload["challenge_nonce"])
                or _date(payload["observed_at_utc"]) is None):
            return False
    elif (payload["schema"] != RESERVE_SCHEMA or payload["kind"] != RESERVATION
          or _date(payload["issued_at_utc"]) is None):
        return False
    return len(canonical_bytes(payload)) <= 4096


def _verify_envelope(obj: Any, pub: Any, *, readback: bool) -> tuple[dict | None, bytes | None, str | None]:
    if type(obj) is not dict or frozenset(obj) != ENVELOPE_FIELDS:
        return None, None, "ENVELOPE_SHAPE_INVALID"
    payload = obj["payload"]
    if not _valid_payload(payload, readback=readback):
        return None, None, "TRANSCRIPT_INVALID"
    signature = _decode_canonical(obj["signature_b64url"], 64)
    pub_raw = _decode_canonical(pub, 32)
    if signature is None or pub_raw is None:
        return None, None, "SIGNATURE_OR_PUBLIC_KEY_ENCODING_INVALID"
    body = canonical_bytes(payload)
    try:
        Ed25519PublicKey.from_public_bytes(pub_raw).verify(signature, body)
    except (InvalidSignature, ValueError):
        return None, None, "SIGNATURE_INVALID"
    return payload, body, None


def inspect_dual_signed_witness_lab(
    reservation: Any, readback: Any, pinned_fixture: Any, *,
    now_utc: Any,
) -> dict[str, Any]:
    """Cryptographic and causal consistency ONLY, zero external authority."""
    defects: list[str] = []
    if type(pinned_fixture) is not dict or frozenset(pinned_fixture) != PINS_FIELDS:
        defects.append("CALLER_PINS_INVALID")
        pin: dict[str, Any] = {}
    else:
        pin = pinned_fixture
        for key in (
            "reservation_key_id", "readback_key_id", "issuer_id", "request_id",
            "intent_id", "attempt_nonce", "challenge_nonce", "expected_version_id",
        ):
            if not _is_id(pin[key]):
                defects.append("PIN_FIELD_INVALID:" + key)
        for key in ("scope_digest", "expected_head_digest"):
            if not _is_hex(pin[key]):
                defects.append("PIN_FIELD_INVALID:" + key)
        for key in ("minimum_epoch", "minimum_sequence"):
            if (type(pin[key]) is not int or
                    not 0 < pin[key] < 2**63 - 1):
                defects.append("PIN_FIELD_INVALID:" + key)
        left = _decode_canonical(pin["reservation_public_key_b64url"], 32)
        right = _decode_canonical(pin["readback_public_key_b64url"], 32)
        if left is None or right is None:
            defects.append("PINNED_KEY_ENCODING_INVALID")
        elif left == right or pin["reservation_key_id"] == pin["readback_key_id"]:
            defects.append("CLAIMED_WITNESS_ROLES_NOT_SEPARATE")
    now = _date(now_utc)
    if now is None:
        defects.append("CALLER_TIME_INVALID")
    if defects:
        return _blocked(defects, crypto=False)

    a, a_bytes, error_a = _verify_envelope(
        reservation, pin["reservation_public_key_b64url"], readback=False)
    b, _, error_b = _verify_envelope(
        readback, pin["readback_public_key_b64url"], readback=True)
    if error_a:
        defects.append("RESERVATION_" + error_a)
    if error_b:
        defects.append("READBACK_" + error_b)
    if defects or a is None or b is None or a_bytes is None:
        return _blocked(defects, crypto=False)

    for key, pinned in (
        ("issuer_id", "issuer_id"), ("scope_digest", "scope_digest"),
        ("request_id", "request_id"), ("intent_id", "intent_id"),
        ("attempt_nonce", "attempt_nonce"), ("version_id", "expected_version_id"),
        ("head_digest", "expected_head_digest"),
    ):
        if a[key] != pin[pinned] or b[key] != pin[pinned]:
            defects.append("PIN_BINDING_MISMATCH:" + key)
    if (a["key_id"] != pin["reservation_key_id"]
            or b["key_id"] != pin["readback_key_id"]):
        defects.append("ROLE_KEY_BINDING_MISMATCH")
    for key in ("epoch", "sequence", "head_digest", "version_id"):
        if a[key] != b[key]:
            defects.append("SIGNED_HEAD_BINDING_MISMATCH:" + key)
    if (a["epoch"] < pin["minimum_epoch"]
            or a["sequence"] < pin["minimum_sequence"]):
        defects.append("SIGNED_HEAD_BELOW_CALLER_MINIMUM")
    if b["reservation_sha256"] != hashlib.sha256(a_bytes).hexdigest():
        defects.append("READBACK_NOT_BOUND_TO_RESERVATION")
    if b["challenge_nonce"] != pin["challenge_nonce"]:
        defects.append("READBACK_CHALLENGE_MISMATCH")
    issued = _date(a["issued_at_utc"])
    observed = _date(b["observed_at_utc"])
    # Supplied now is NOT a trusted clock or fresh remote readback.
    if (issued is None or observed is None or now is None
            or not issued <= observed <= now
            or observed - issued > timedelta(seconds=180)
            or now - observed > timedelta(seconds=120)):
        defects.append("CALLER_TIME_OR_OBSERVATION_WINDOW_INVALID")
    return _blocked(defects, crypto=True)


def _blocked(defects: list[str], *, crypto: bool) -> dict[str, Any]:
    return {
        "schema": LAB_SCHEMA, "state": "HARD_NO_GO", "allowed": False,
        "simulation_only": True,
        "signature_bytes_valid_under_caller_supplied_keys": crypto,
        "signed_transcripts_consistent_lab": crypto and not defects,
        "defects": tuple(sorted(set(defects))),
        "blockers": PERMANENT_GAPS,
        **AUTHORITY_FALSE,
    }
