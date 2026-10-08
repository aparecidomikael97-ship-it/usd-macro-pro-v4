"""CI-only rooted collector enrollment and independent raw-evidence verifier.

No real collector key is enrolled here. The enrollment root must be trusted by
an independent host, never supplied by the evidence producer. All signed
material is synthetic in CI. This verifier authenticates *bytes and bindings*,
NOT physical measurements or the truth of collector claims. No Windows API,
network, process execution, installer, or production authority.
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import json
import re
import sqlite3
from pathlib import Path
from typing import Any, Mapping

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from atlasquant_aion_independent_physical_process_attestation_contract_v1 import (
    ATTESTATION_SCHEMA, attestation_signing_message, challenge_digest,
)
from atlasquant_aion_windows_sandbox_physical_probe_plan_evidence_v1 import (
    PROBE_REQUIREMENTS,
)

SCHEMA = "AION_ROOTED_COLLECTOR_RAW_EVIDENCE_PREFLIGHT_V1"
ENROLL_SCHEMA = "AION_COLLECTOR_ROOT_SIGNED_ENROLLMENT_V1"
ENROLL_PURPOSE = "HOST_BOUND_COLLECTOR_SIGNING_KEY_SNAPSHOT"
RAW_SCHEMA = "AION_PHYSICAL_RAW_EVIDENCE_BUNDLE_V1"
CANDIDATE = "ROOTED_COLLECTOR_RAW_EVIDENCE_CANDIDATE_UNTRUSTED"
ENROLL_DOMAIN = b"ATLASQUANT:AION:COLLECTOR_ENROLLMENT:V1\x00"
REPLAY_DOMAIN = b"ATLASQUANT:AION:COLLECTOR_CHALLENGE_NONCE:V1\x00"
_SHA = re.compile(r"sha256:[0-9a-f]{64}\Z")
_TAG = re.compile(r"[A-Za-z0-9._:-]{1,96}\Z")
_ENROLL_FIELDS = frozenset({
    "schema", "purpose", "registry_id", "host_issuer",
    "host_binding_digest", "device_binding_digest", "epoch",
    "issued_at", "expires_at", "collector",
})
_COLLECTOR_FIELDS = frozenset({
    "collector_id", "key_id", "public_key_b64",
    "binary_digest", "manifest_digest", "enrolled_epoch", "revoked_epoch",
})
_RAW_FIELDS = frozenset({"schema", "challenge_digest", "entries"})
_RAW_ENTRY_FIELDS = frozenset({
    "sequence", "requirement", "positive_evidence_b64", "negative_evidence_b64",
})
MAX_ENROLL_BYTES = 8192
MAX_RAW_BYTES = 131072


def _digest(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _canonical(value: Mapping[str, Any]) -> bytes:
    return json.dumps(dict(value), sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("utf-8")


def _unique_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for name, value in pairs:
        if name in out:
            raise ValueError("DUPLICATE_JSON_PROPERTY")
        out[name] = value
    return out


def _strict_json(raw: Any, *, maximum: int) -> dict[str, Any]:
    if type(raw) is not bytes or not 2 <= len(raw) <= maximum:
        raise ValueError("RAW_BYTES_BOUNDS_INVALID")
    try:
        obj = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_pairs)
    except (UnicodeError, ValueError, TypeError) as exc:
        raise ValueError("JSON_INVALID") from exc
    if type(obj) is not dict or _canonical(obj) != raw:
        raise ValueError("NONCANONICAL_JSON")
    return obj


def _b64(value: Any, size: int) -> bytes:
    if type(value) is not str or not value or len(value) > (size * 4 // 3 + 8):
        raise ValueError("BASE64_INVALID")
    try:
        decoded = base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("BASE64_INVALID") from exc
    if len(decoded) != size or base64.b64encode(decoded).decode("ascii") != value:
        raise ValueError("BASE64_INVALID")
    return decoded


def _evidence_bytes(value: Any) -> bytes:
    if type(value) is not str or not value or len(value) > 4096:
        raise ValueError("EVIDENCE_BASE64_INVALID")
    try:
        raw = base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("EVIDENCE_BASE64_INVALID") from exc
    if not 1 <= len(raw) <= 2048 or base64.b64encode(raw).decode("ascii") != value:
        raise ValueError("EVIDENCE_BASE64_INVALID")
    return raw


def _valid_tag(value: Any) -> bool:
    return type(value) is str and bool(_TAG.fullmatch(value))


def _valid_digest(value: Any) -> bool:
    return type(value) is str and bool(_SHA.fullmatch(value))


def _check_enrollment(raw: bytes) -> dict[str, Any]:
    row = _strict_json(raw, maximum=MAX_ENROLL_BYTES)
    if set(row) != _ENROLL_FIELDS or row["schema"] != ENROLL_SCHEMA or row["purpose"] != ENROLL_PURPOSE:
        raise ValueError("ENROLLMENT_SCHEMA_OR_FIELDS_INVALID")
    if not all(_valid_tag(row[field]) for field in ("registry_id", "host_issuer")):
        raise ValueError("ENROLLMENT_IDENTITY_INVALID")
    for field in ("host_binding_digest", "device_binding_digest"):
        if not _valid_digest(row[field]):
            raise ValueError("ENROLLMENT_BINDING_INVALID")
    epoch, issued, expires = row["epoch"], row["issued_at"], row["expires_at"]
    if (type(epoch) is not int or epoch < 1 or type(issued) is not int
        or type(expires) is not int or not 0 < issued < expires <= issued + 86400):
        raise ValueError("ENROLLMENT_TIME_INVALID")
    entry = row["collector"]
    if type(entry) is not dict or set(entry) != _COLLECTOR_FIELDS:
        raise ValueError("COLLECTOR_FIELDS_INVALID")
    if not _valid_tag(entry["collector_id"]) or not _valid_tag(entry["key_id"]):
        raise ValueError("COLLECTOR_ID_INVALID")
    if any(not _valid_digest(entry[f]) for f in ("binary_digest", "manifest_digest")):
        raise ValueError("COLLECTOR_DIGEST_INVALID")
    if type(entry["enrolled_epoch"]) is not int or not 1 <= entry["enrolled_epoch"] <= epoch:
        raise ValueError("COLLECTOR_ENROLLED_EPOCH_INVALID")
    revoked = entry["revoked_epoch"]
    if revoked is not None and (type(revoked) is not int
        or not entry["enrolled_epoch"] <= revoked <= epoch):
        raise ValueError("COLLECTOR_REVOKED_EPOCH_INVALID")
    _b64(entry["public_key_b64"], 32)
    return row


def enrollment_signing_message(record: Mapping[str, Any]) -> bytes:
    """For synthetic fixtures; does not generate or enroll any key."""
    validated = _check_enrollment(_canonical(record))
    return ENROLL_DOMAIN + _canonical(validated)


def _check_raw_bundle(raw: bytes, *, expected_challenge_digest: str,
                      attestation: Mapping[str, Any]) -> None:
    doc = _strict_json(raw, maximum=MAX_RAW_BYTES)
    if set(doc) != _RAW_FIELDS or doc["schema"] != RAW_SCHEMA:
        raise ValueError("RAW_BUNDLE_SCHEMA_INVALID")
    if doc["challenge_digest"] != expected_challenge_digest:
        raise ValueError("RAW_BUNDLE_CHALLENGE_MISMATCH")
    items = doc["entries"]
    if type(items) is not list or len(items) != len(PROBE_REQUIREMENTS):
        raise ValueError("RAW_BUNDLE_REQUIREMENT_COUNT_INVALID")
    bound = attestation.get("requirement_evidence")
    if type(bound) is not list or len(bound) != len(PROBE_REQUIREMENTS):
        raise ValueError("SIGNED_REQUIREMENT_COUNT_INVALID")
    for index, name in enumerate(PROBE_REQUIREMENTS):
        item = items[index]
        if type(item) is not dict or set(item) != _RAW_ENTRY_FIELDS:
            raise ValueError("RAW_ENTRY_FIELDS_INVALID")
        if type(item["sequence"]) is not int or item["sequence"] != index + 1 or item["requirement"] != name:
            raise ValueError("RAW_REQUIREMENT_ORDER_INVALID")
        positive = _evidence_bytes(item["positive_evidence_b64"])
        negative = _evidence_bytes(item["negative_evidence_b64"])
        if positive == negative:
            raise ValueError("RAW_POSITIVE_NEGATIVE_NOT_DISTINCT")
        signed = bound[index]
        if (type(signed) is not dict or type(signed.get("sequence")) is not int
            or signed.get("sequence") != index + 1
            or signed.get("requirement") != name
            or signed.get("positive_evidence_digest") != _digest(positive)
            or signed.get("negative_evidence_digest") != _digest(negative)):
            raise ValueError("SIGNED_RAW_EVIDENCE_DIGEST_MISMATCH")


class SQLiteCollectorChallengeReplay:
    """Single-use *nonce* scoped globally to this contract, not to a mutable
    challenge digest. Host must supply ACL and true anti-rollback in production.
    """
    def __init__(self, path: str | Path):
        name = str(path)
        if not name or name == ":memory:" or name.startswith("file:"):
            raise ValueError("EXPLICIT_DURABLE_DATABASE_REQUIRED")
        self.path = name
        with sqlite3.connect(name, timeout=10, isolation_level=None) as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("PRAGMA synchronous=FULL")
            db.execute("CREATE TABLE IF NOT EXISTS consumed_challenges ("
                       "nonce_key TEXT PRIMARY KEY, expires_at INTEGER NOT NULL)")

    def consume_once(self, nonce_key: str, expiry: int, now: int) -> bool:
        if not _valid_digest(nonce_key) or type(expiry) is not int or type(now) is not int or now > expiry:
            return False
        db = sqlite3.connect(self.path, timeout=10, isolation_level=None)
        try:
            db.execute("PRAGMA synchronous=FULL")
            db.execute("BEGIN IMMEDIATE")
            try:
                db.execute("INSERT INTO consumed_challenges(nonce_key,expires_at) VALUES(?,?)",
                           (nonce_key, expiry))
            except sqlite3.IntegrityError:
                db.rollback()
                return False
            db.commit()
            return True
        except sqlite3.Error:
            if db.in_transaction:
                db.rollback()
            return False
        finally:
            db.close()


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "BLOCKED", "reason": reason,
        "enrollment_root_signature_valid": False,
        "collector_key_resolved_from_registry": False,
        "raw_bundle_bytes_bound": False, "signed_positive_negative_bytes_bound": False,
        "single_use_challenge_consumed": False,
        "root_enrolled_in_production": False,
        "collector_enrolled_in_production": False,
        "raw_evidence_independently_observed": False,
        "physical_attestation_verified": False, "network_deny_verified": False,
        "safe_to_resume": False, "installer_authorized": False,
        "build_authorized": False, "deploy_authorized": False,
    }


def verify_rooted_collector_raw_evidence(
    registry_raw: bytes, registry_root_signature_b64: str,
    challenge: Mapping[str, Any], attestation: Mapping[str, Any],
    collector_signature_b64: str, raw_bundle: bytes, *,
    pinned_enrollment_root_public_key: bytes, expected_root_fingerprint: str,
    expected_registry_id: str, expected_host_issuer: str,
    expected_host_binding_digest: str, expected_device_binding_digest: str,
    expected_collector_id: str, minimum_enrollment_epoch: int, now: int,
    replay_store: SQLiteCollectorChallengeReplay | None,
) -> dict[str, Any]:
    """All 'expected' inputs must come from independent authenticated host policy.

    Never construct this host policy from the untrusted collector's payload.
    Success means only cryptographic/byte consistency, NOT physical attestation.
    """
    try:
        registry = _check_enrollment(registry_raw)
    except (ValueError, TypeError, OverflowError):
        return _blocked("ENROLLMENT_SNAPSHOT_MALFORMED")
    if (type(now) is not int or type(minimum_enrollment_epoch) is not int
        or minimum_enrollment_epoch < 1
        or not all(_valid_tag(x) for x in
                    (expected_registry_id, expected_host_issuer, expected_collector_id))
        or not all(_valid_digest(x) for x in (
            expected_root_fingerprint, expected_host_binding_digest,
            expected_device_binding_digest))):
        return _blocked("INDEPENDENT_HOST_POLICY_REQUIRED")
    if (registry["registry_id"] != expected_registry_id
        or registry["host_issuer"] != expected_host_issuer
        or registry["host_binding_digest"] != expected_host_binding_digest
        or registry["device_binding_digest"] != expected_device_binding_digest
        or registry["collector"]["collector_id"] != expected_collector_id):
        return _blocked("ENROLLMENT_HOST_OR_DEVICE_MISMATCH")
    if registry["epoch"] < minimum_enrollment_epoch:
        return _blocked("ENROLLMENT_ROLLBACK")
    if not registry["issued_at"] <= now <= registry["expires_at"]:
        return _blocked("ENROLLMENT_NOT_CURRENT")
    if registry["collector"]["revoked_epoch"] is not None:
        return _blocked("COLLECTOR_REVOKED")
    if (type(pinned_enrollment_root_public_key) is not bytes
        or len(pinned_enrollment_root_public_key) != 32
        or _digest(pinned_enrollment_root_public_key) != expected_root_fingerprint):
        return _blocked("ENROLLMENT_ROOT_NOT_PINNED")
    try:
        root_signature = _b64(registry_root_signature_b64, 64)
        Ed25519PublicKey.from_public_bytes(pinned_enrollment_root_public_key).verify(
            root_signature, ENROLL_DOMAIN + registry_raw)
    except (ValueError, InvalidSignature, TypeError):
        return _blocked("ENROLLMENT_ROOT_SIGNATURE_INVALID")

    collector_key = _b64(registry["collector"]["public_key_b64"], 32)
    if not isinstance(challenge, Mapping) or not isinstance(attestation, Mapping):
        return _blocked("TRUSTED_CHALLENGE_OR_ATTESTATION_REQUIRED")
    if (challenge.get("host_binding_digest") != expected_host_binding_digest
        or challenge.get("collector_manifest_digest") != registry["collector"]["manifest_digest"]
        or challenge.get("collector_binary_digest") != registry["collector"]["binary_digest"]
        or challenge.get("collector_key_fingerprint") != _digest(collector_key)):
        return _blocked("CHALLENGE_NOT_BOUND_TO_ENROLLED_COLLECTOR")

    try:
        signed_message = attestation_signing_message(
            attestation, challenge=challenge, now=now)
        expected_digest = challenge_digest(challenge)
        if attestation.get("raw_bundle_digest") != _digest(raw_bundle):
            return _blocked("RAW_BUNDLE_SHA256_MISMATCH")
        _check_raw_bundle(raw_bundle, expected_challenge_digest=expected_digest,
                          attestation=attestation)
        sig = _b64(collector_signature_b64, 64)
        Ed25519PublicKey.from_public_bytes(collector_key).verify(sig, signed_message)
    except InvalidSignature:
        return _blocked("COLLECTOR_SIGNATURE_INVALID")
    except (ValueError, TypeError, KeyError, OverflowError):
        return _blocked("ATTESTATION_OR_RAW_EVIDENCE_INVALID")

    if not isinstance(replay_store, SQLiteCollectorChallengeReplay):
        return _blocked("DURABLE_NONCE_STORE_REQUIRED")
    nonce = challenge.get("challenge_nonce")
    if type(nonce) is not str or not re.fullmatch(r"[0-9a-f]{64}", nonce):
        return _blocked("CHALLENGE_NONCE_INVALID")
    nonce_key = _digest(REPLAY_DOMAIN + bytes.fromhex(nonce))
    if not replay_store.consume_once(nonce_key, challenge["expires_at"], now):
        return _blocked("NONCE_REPLAY_OR_STORE_FAILURE")
    return {
        **_blocked(""),
        "state": CANDIDATE, "reason": "",
        "enrollment_root_signature_valid": True,
        "collector_key_resolved_from_registry": True,
        "raw_bundle_bytes_bound": True,
        "signed_positive_negative_bytes_bound": True,
        "single_use_challenge_consumed": True,
        "challenge_digest": expected_digest,
        "raw_bundle_digest": _digest(raw_bundle),
        "collector_key_fingerprint": _digest(collector_key),
        "requirement_count": len(PROBE_REQUIREMENTS),
    }


__all__ = [
    "SCHEMA", "ENROLL_SCHEMA", "ENROLL_PURPOSE", "RAW_SCHEMA",
    "CANDIDATE", "enrollment_signing_message",
    "SQLiteCollectorChallengeReplay", "verify_rooted_collector_raw_evidence",
]
