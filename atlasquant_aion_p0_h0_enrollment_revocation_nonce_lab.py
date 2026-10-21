"""AION P0 H0 LAB — three SYNTHETIC signed evidence layers, never an authority.

Enrollment root, revocation ledger and nonce custodian public keys are
CALLER-SUPPLIED laboratory fixtures. This verifier does NOT independently
enroll any issuer, prove latest remote state, consume a nonce, authenticate a
real clock or inspect account owners. Valid crypto can NEVER allow an effect.
No network access, persistence, Worker calls, external side effects or retry.
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

SCHEMA = "AION_P0_H0_ENROLL_REVOCATION_NONCE_LAB_V1"
DOMAIN = b"AION_P0_H0_ENROLL_REVOCATION_NONCE_LAB_V1\x00"
ENROLL_SCHEMA = "AION_P0_H0_ISSUER_ENROLLMENT_LAB_V1"
REVOCATION_SCHEMA = "AION_P0_H0_REVOCATION_SNAPSHOT_LAB_V1"
NONCE_SCHEMA = "AION_P0_H0_NONCE_CUSTODY_RECEIPT_LAB_V1"
ROLES = frozenset(("reservation_signer", "readback_witness"))
ENROLL_FIELDS = frozenset((
    "schema", "issuer_id", "scope_digest", "registry_epoch", "registry_seq",
    "registry_version_id", "signed_at_utc", "roles",
))
ROLE_FIELDS = frozenset((
    "role", "key_id", "public_key_b64url", "key_epoch", "status",
))
REVOCATION_FIELDS = frozenset((
    "schema", "issuer_id", "scope_digest", "registry_epoch", "registry_seq",
    "enrollment_sha256", "signed_at_utc", "revoked_key_ids",
    "active_key_ids",
))
NONCE_FIELDS = frozenset((
    "schema", "issuer_id", "scope_digest", "request_id", "intent_id",
    "challenge_nonce", "registry_epoch", "registry_seq",
    "revocation_sha256", "custody_counter", "issued_at_utc",
    "expires_at_utc", "head_digest", "head_sequence",
))
PINS_FIELDS = frozenset((
    "registry_root_public_key_b64url", "custodian_public_key_b64url",
    "issuer_id", "scope_digest", "request_id", "intent_id",
    "challenge_nonce", "minimum_registry_epoch", "minimum_registry_seq",
    "minimum_custody_counter", "expected_head_digest",
    "expected_head_sequence",
))
ENVELOPE_FIELDS = frozenset(("payload", "signature_b64url"))
HEX = re.compile(r"[0-9a-f]{64}\Z")
IDENT = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:/@-]{7,127}\Z")
DATE = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z\Z")
AUTHORITY_FALSE = {
    "issuer_independently_enrolled": False,
    "registry_root_out_of_band_authenticated": False,
    "current_revocation_independently_read": False,
    "key_rotation_independently_attested": False,
    "nonce_issued_outside_executor": False,
    "nonce_uniqueness_durably_proven": False,
    "nonce_atomically_consumed": False,
    "trusted_clock_authenticated": False,
    "latest_head_authenticated": False,
    "independent_administration_authenticated": False,
    "human_owner_authenticated": False,
    "producer_effect_or_no_effect_authenticated": False,
    "first_external_effect_allowed": False,
    "worker_arming_allowed": False,
    "automatic_retry_allowed": False,
    "external_action_executed": False,
}
PERMANENT_BLOCKERS = (
    "CALLER_PINNED_TEST_KEYS_NOT_EXTERNAL_ENROLLMENT",
    "REAL_INDEPENDENT_ROOT_CUSTODY_UNPROVEN",
    "CURRENT_REMOTE_REVOCATION_UNPROVEN",
    "ATOMIC_OFF_HOST_NONCE_CUSTODY_UNPROVEN",
    "TRUSTED_FRESHNESS_AND_LATEST_HEAD_UNPROVEN",
    "PRODUCER_CAUSAL_RECEIPT_UNPROVEN",
    "HUMAN_OWNER_UNAUTHENTICATED",
    "PHYSICAL_ROLLBACK_NOT_RULED_OUT",
    "QUALITY_CANONICAL_NOT_GREEN",
)


def _plain(obj: Any, keys: frozenset[str]) -> bool:
    return (type(obj) is dict and all(type(k) is str for k in obj)
            and frozenset(obj) == keys)


def _ident(v: Any) -> bool:
    return type(v) is str and IDENT.fullmatch(v) is not None


def _hex(v: Any) -> bool:
    return type(v) is str and HEX.fullmatch(v) is not None


def _pos(v: Any) -> bool:
    return type(v) is int and 0 < v < 2**63 - 1


def _date(v: Any) -> datetime | None:
    if type(v) is not str or DATE.fullmatch(v) is None:
        return None
    try:
        return datetime.strptime(v, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return None


def _raw_b64(value: Any, size: int) -> bytes | None:
    if (type(value) is not str or len(value) != (43 if size == 32 else 86)
            or re.fullmatch(r"[A-Za-z0-9_-]+", value) is None):
        return None
    try:
        raw = base64.b64decode(
            value.encode("ascii") + b"=" * (-len(value) % 4),
            altchars=b"-_", validate=True,
        )
    except (ValueError, UnicodeError, binascii.Error):
        return None
    if (len(raw) != size or
            base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii") != value):
        return None
    return raw


def canonical_bytes(payload: dict[str, Any]) -> bytes:
    """Only apply to a payload that passed the strict plain-type schema."""
    return DOMAIN + json.dumps(
        payload, sort_keys=True, separators=(",", ":"),
        ensure_ascii=True, allow_nan=False,
    ).encode("ascii")


def _role_ok(value: Any) -> bool:
    return (
        _plain(value, ROLE_FIELDS)
        and type(value["role"]) is str and value["role"] in ROLES
        and _ident(value["key_id"])
        and _raw_b64(value["public_key_b64url"], 32) is not None
        and _pos(value["key_epoch"])
        and type(value["status"]) is str
        and value["status"] in ("ACTIVE", "REVOKED")
    )


def _enrollment_ok(value: Any) -> bool:
    if not _plain(value, ENROLL_FIELDS):
        return False
    if (type(value["schema"]) is not str or value["schema"] != ENROLL_SCHEMA
            or not _ident(value["issuer_id"]) or not _hex(value["scope_digest"])
            or not _pos(value["registry_epoch"]) or not _pos(value["registry_seq"])
            or not _ident(value["registry_version_id"])
            or _date(value["signed_at_utc"]) is None):
        return False
    roles = value["roles"]
    if (type(roles) is not list or len(roles) != 2 or
            not all(_role_ok(item) for item in roles)):
        return False
    if frozenset(x["role"] for x in roles) != ROLES:
        return False
    if len({x["key_id"] for x in roles}) != 2:
        return False
    if len({x["public_key_b64url"] for x in roles}) != 2:
        return False
    # One registry epoch, distinct role keys, no silent cross-epoch reuse.
    if any(x["key_epoch"] != value["registry_epoch"] for x in roles):
        return False
    return len(canonical_bytes(value)) <= 4096


def _ordered_ids(value: Any) -> bool:
    return (type(value) is list and len(value) <= 16
            and all(_ident(v) for v in value)
            and value == sorted(set(value)))


def _revocation_ok(value: Any) -> bool:
    return (
        _plain(value, REVOCATION_FIELDS)
        and type(value["schema"]) is str
        and value["schema"] == REVOCATION_SCHEMA
        and _ident(value["issuer_id"]) and _hex(value["scope_digest"])
        and _pos(value["registry_epoch"]) and _pos(value["registry_seq"])
        and _hex(value["enrollment_sha256"])
        and _date(value["signed_at_utc"]) is not None
        and _ordered_ids(value["revoked_key_ids"])
        and _ordered_ids(value["active_key_ids"])
        and not (set(value["revoked_key_ids"]) & set(value["active_key_ids"]))
        and len(canonical_bytes(value)) <= 4096
    )


def _nonce_ok(value: Any) -> bool:
    if not _plain(value, NONCE_FIELDS):
        return False
    return (
        type(value["schema"]) is str and value["schema"] == NONCE_SCHEMA
        and all(_ident(value[k]) for k in (
            "issuer_id", "request_id", "intent_id", "challenge_nonce"))
        and all(_hex(value[k]) for k in (
            "scope_digest", "revocation_sha256", "head_digest"))
        and all(_pos(value[k]) for k in (
            "registry_epoch", "registry_seq", "custody_counter", "head_sequence"))
        and _date(value["issued_at_utc"]) is not None
        and _date(value["expires_at_utc"]) is not None
        and len(canonical_bytes(value)) <= 4096
    )


def _envelope(obj: Any, public_key: Any, validator: Any) -> tuple[dict | None, bytes | None, str | None]:
    if not _plain(obj, ENVELOPE_FIELDS):
        return None, None, "ENVELOPE_SHAPE_INVALID"
    payload = obj["payload"]
    if not validator(payload):
        return None, None, "PAYLOAD_INVALID"
    pub = _raw_b64(public_key, 32)
    sig = _raw_b64(obj["signature_b64url"], 64)
    if pub is None or sig is None:
        return None, None, "PUBLIC_KEY_OR_SIGNATURE_ENCODING_INVALID"
    signed_bytes = canonical_bytes(payload)
    try:
        Ed25519PublicKey.from_public_bytes(pub).verify(sig, signed_bytes)
    except (ValueError, InvalidSignature):
        return None, None, "SIGNATURE_INVALID"
    return payload, signed_bytes, None


def _blocked(findings: set[str], crypto: bool) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "HARD_NO_GO", "allowed": False,
        "simulation_only": True,
        "synthetic_signatures_valid_under_caller_keys": crypto,
        "synthetic_policy_consistent_lab": crypto and not findings,
        "findings": tuple(sorted(findings)),
        "blockers": PERMANENT_BLOCKERS,
        **AUTHORITY_FALSE,
    }


def inspect_enrollment_revocation_nonce_lab(
    enrollment: Any, revocation: Any, challenge: Any,
    caller_pinned_fixture: Any, *, now_utc: Any,
) -> dict[str, Any]:
    """Verify a synthetic 3-envelope chain, never enroll or authorize."""
    findings: set[str] = set()
    if not _plain(caller_pinned_fixture, PINS_FIELDS):
        return _blocked({"CALLER_PINS_INVALID"}, False)
    pin = caller_pinned_fixture
    for key in ("issuer_id", "request_id", "intent_id", "challenge_nonce"):
        if not _ident(pin[key]):
            findings.add("PIN_IDENTIFIER_INVALID:" + key)
    for key in ("scope_digest", "expected_head_digest"):
        if not _hex(pin[key]):
            findings.add("PIN_DIGEST_INVALID:" + key)
    for key in ("minimum_registry_epoch", "minimum_registry_seq",
                "minimum_custody_counter", "expected_head_sequence"):
        if not _pos(pin[key]):
            findings.add("PIN_COUNTER_INVALID:" + key)
    root = _raw_b64(pin["registry_root_public_key_b64url"], 32)
    custodian = _raw_b64(pin["custodian_public_key_b64url"], 32)
    if root is None or custodian is None:
        findings.add("PINNED_SIGNER_ENCODING_INVALID")
    elif root == custodian:
        findings.add("PINNED_REGISTRY_CUSTODIAN_KEY_REUSE")
    now = _date(now_utc)
    if now is None:
        findings.add("CALLER_CLOCK_INVALID")
    if findings:
        return _blocked(findings, False)

    a, a_bytes, ea = _envelope(
        enrollment, pin["registry_root_public_key_b64url"], _enrollment_ok)
    b, b_bytes, eb = _envelope(
        revocation, pin["registry_root_public_key_b64url"], _revocation_ok)
    c, _, ec = _envelope(
        challenge, pin["custodian_public_key_b64url"], _nonce_ok)
    for label, error in (("ENROLLMENT", ea), ("REVOCATION", eb), ("CHALLENGE", ec)):
        if error:
            findings.add(label + "_" + error)
    if findings or a is None or b is None or c is None or a_bytes is None or b_bytes is None:
        return _blocked(findings, False)

    for name, payload in (("ENROLLMENT", a), ("REVOCATION", b), ("CHALLENGE", c)):
        for key in ("issuer_id", "scope_digest"):
            if payload[key] != pin[key]:
                findings.add(name + "_PIN_MISMATCH:" + key)
        if payload["registry_epoch"] != a["registry_epoch"]:
            findings.add(name + "_REGISTRY_EPOCH_MISMATCH")
    for name, payload in (("CHALLENGE", c),):
        for key in ("request_id", "intent_id", "challenge_nonce"):
            if payload[key] != pin[key]:
                findings.add(name + "_PIN_MISMATCH:" + key)
    if a["registry_epoch"] < pin["minimum_registry_epoch"]:
        findings.add("REGISTRY_EPOCH_BELOW_CALLER_MINIMUM")
    if b["registry_seq"] < pin["minimum_registry_seq"]:
        findings.add("REVOCATION_SEQ_BELOW_CALLER_MINIMUM")
    if not a["registry_seq"] < b["registry_seq"]:
        findings.add("REVOCATION_NOT_AFTER_ENROLLMENT")
    if c["registry_seq"] != b["registry_seq"]:
        findings.add("CHALLENGE_NOT_BOUND_TO_REVOCATION_SEQUENCE")
    if b["enrollment_sha256"] != hashlib.sha256(a_bytes).hexdigest():
        findings.add("REVOCATION_NOT_BOUND_TO_ENROLLMENT")
    if c["revocation_sha256"] != hashlib.sha256(b_bytes).hexdigest():
        findings.add("CHALLENGE_NOT_BOUND_TO_REVOCATION")
    keys = {x["key_id"] for x in a["roles"]}
    active = {x["key_id"] for x in a["roles"] if x["status"] == "ACTIVE"}
    if set(b["active_key_ids"]) != active:
        findings.add("ACTIVE_ROLE_KEYSET_NOT_MATCHED")
    if any(x["status"] != "ACTIVE" for x in a["roles"]):
        findings.add("ENROLLED_ROLE_REVOKED_OR_INACTIVE")
    if keys & set(b["revoked_key_ids"]):
        findings.add("ENROLLED_KEY_REVOKED")
    if c["custody_counter"] < pin["minimum_custody_counter"]:
        findings.add("CUSTODY_COUNTER_BELOW_CALLER_MINIMUM")
    if c["head_digest"] != pin["expected_head_digest"] or c["head_sequence"] != pin["expected_head_sequence"]:
        findings.add("CHALLENGE_HEAD_BINDING_MISMATCH")

    enroll_date = _date(a["signed_at_utc"])
    revoke_date = _date(b["signed_at_utc"])
    issued = _date(c["issued_at_utc"])
    expires = _date(c["expires_at_utc"])
    # "now" is CALLER-supplied and these windows are NOT evidence of freshness.
    if (enroll_date is None or revoke_date is None or issued is None
            or expires is None or now is None
            or not enroll_date <= revoke_date <= issued <= now <= expires
            or expires - issued > timedelta(seconds=120)
            or issued - revoke_date > timedelta(seconds=120)):
        findings.add("CALLER_TIME_OR_NONCE_WINDOW_INVALID")

    return _blocked(findings, True)
