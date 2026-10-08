"""AION CI-only independent physical-process attestation contract V1.

Data/crypto only. This module does NOT launch a process, inspect Windows, open a
socket, alter a profile/firewall, or collect physical evidence. It defines a
trusted-host challenge, an independently signed collector envelope, canonical
binding to all 12 #1049 physical requirements, and durable one-time challenge
consumption.

A cryptographically valid envelope is still only an UNTRUSTED CANDIDATE until
the collector key is really enrolled, its binary/manifest are independently
trusted, raw evidence is reviewed, and the physical measurements are performed.
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

from atlasquant_aion_windows_sandbox_physical_probe_plan_evidence_v1 import (
    PROBE_REQUIREMENTS,
)

CHALLENGE_SCHEMA = "AION_INDEPENDENT_PHYSICAL_PROCESS_CHALLENGE_V1"
ATTESTATION_SCHEMA = "AION_INDEPENDENT_PHYSICAL_PROCESS_ATTESTATION_V1"
PURPOSE = "INDEPENDENT_PHYSICAL_PROCESS_EVIDENCE"
CANDIDATE = "SIGNED_PHYSICAL_PROCESS_EVIDENCE_CANDIDATE_UNTRUSTED"
CHALLENGE_DOMAIN = b"ATLASQUANT:AION:PHYSICAL_PROCESS_CHALLENGE:V1\x00"
ATTESTATION_DOMAIN = b"ATLASQUANT:AION:PHYSICAL_PROCESS_ATTESTATION:V1\x00"
MAX_CHALLENGE_TTL = 120
MAX_ATTESTATION_TTL = 60
_SHA = re.compile(r"sha256:[0-9a-f]{64}\Z")
_HEX64 = re.compile(r"[0-9a-f]{64}\Z")
_NONCE = re.compile(r"[0-9a-f]{64}\Z")
_REF = re.compile(r"[a-zA-Z0-9._:/-]{1,240}\Z")

CHALLENGE_FIELDS = frozenset({
    "schema", "purpose", "challenge_nonce",
    "owner_preflight_digest", "sandbox_preflight_digest", "probe_plan_digest",
    "host_binding_digest", "collector_manifest_digest", "collector_binary_digest",
    "collector_key_fingerprint", "expected_image_path_digest",
    "expected_image_sha256", "issued_at", "expires_at",
})
ATTESTATION_FIELDS = frozenset({
    "schema", "challenge_digest", "challenge_nonce", "collector_key_fingerprint",
    "observed_image_path_digest", "observed_image_sha256",
    "file_identity_digest", "process_handle_provenance_digest",
    "token_evidence_digest", "job_evidence_digest",
    "requirement_evidence", "raw_bundle_ref", "raw_bundle_digest",
    "collected_at", "valid_until",
})
REQUIREMENT_EVIDENCE_FIELDS = frozenset({
    "sequence", "requirement", "positive_evidence_digest", "negative_evidence_digest",
})


def _sha(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _canonical(value: Mapping[str, Any]) -> bytes:
    return json.dumps(
        dict(value), ensure_ascii=True, sort_keys=True,
        separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")


def _decode_signature(value: Any) -> bytes:
    if type(value) is not str or not value or len(value) > 160:
        raise ValueError("SIGNATURE_ENCODING_INVALID")
    try:
        raw = base64.b64decode(value, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise ValueError("SIGNATURE_ENCODING_INVALID") from exc
    if len(raw) != 64 or base64.b64encode(raw).decode("ascii") != value:
        raise ValueError("SIGNATURE_ENCODING_INVALID")
    return raw


def _strict_sha(value: Any, label: str) -> str:
    if type(value) is not str or not _SHA.fullmatch(value):
        raise ValueError(label + "_INVALID")
    return value


def _validate_challenge(challenge: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(challenge, Mapping) or set(challenge) != CHALLENGE_FIELDS:
        raise ValueError("CHALLENGE_FIELDS_INVALID")
    row = dict(challenge)
    if row["schema"] != CHALLENGE_SCHEMA or row["purpose"] != PURPOSE:
        raise ValueError("CHALLENGE_SCHEMA_INVALID")
    if type(row["challenge_nonce"]) is not str or not _NONCE.fullmatch(row["challenge_nonce"]):
        raise ValueError("CHALLENGE_NONCE_INVALID")
    for field in (
        "owner_preflight_digest", "sandbox_preflight_digest", "probe_plan_digest",
        "host_binding_digest", "collector_manifest_digest", "collector_binary_digest",
        "collector_key_fingerprint", "expected_image_path_digest",
    ):
        _strict_sha(row[field], field.upper())
    if type(row["expected_image_sha256"]) is not str or not _HEX64.fullmatch(row["expected_image_sha256"]):
        raise ValueError("EXPECTED_IMAGE_SHA256_INVALID")
    issued, expires = row["issued_at"], row["expires_at"]
    if (
        type(issued) is not int or type(expires) is not int
        or not (0 < issued < expires <= issued + MAX_CHALLENGE_TTL)
    ):
        raise ValueError("CHALLENGE_WINDOW_INVALID")
    return row


def challenge_signing_material(challenge: Mapping[str, Any]) -> bytes:
    """Canonical host challenge bytes to hash/bind into physical evidence."""
    return CHALLENGE_DOMAIN + _canonical(_validate_challenge(challenge))


def challenge_digest(challenge: Mapping[str, Any]) -> str:
    return _sha(challenge_signing_material(challenge))


def build_physical_process_challenge(
    *,
    challenge_nonce: str,
    owner_preflight_digest: str,
    sandbox_preflight_digest: str,
    probe_plan_digest: str,
    host_binding_digest: str,
    collector_manifest_digest: str,
    collector_binary_digest: str,
    collector_key_fingerprint: str,
    expected_image_path_digest: str,
    expected_image_sha256: str,
    issued_at: int,
    expires_at: int,
) -> dict[str, Any]:
    """Build strict host challenge; does not generate randomness or grant authority."""
    row = {
        "schema": CHALLENGE_SCHEMA,
        "purpose": PURPOSE,
        "challenge_nonce": challenge_nonce,
        "owner_preflight_digest": owner_preflight_digest,
        "sandbox_preflight_digest": sandbox_preflight_digest,
        "probe_plan_digest": probe_plan_digest,
        "host_binding_digest": host_binding_digest,
        "collector_manifest_digest": collector_manifest_digest,
        "collector_binary_digest": collector_binary_digest,
        "collector_key_fingerprint": collector_key_fingerprint,
        "expected_image_path_digest": expected_image_path_digest,
        "expected_image_sha256": expected_image_sha256,
        "issued_at": issued_at,
        "expires_at": expires_at,
    }
    return _validate_challenge(row)


def _validate_requirement_evidence(items: Any) -> list[dict[str, Any]]:
    if type(items) is not list or len(items) != len(PROBE_REQUIREMENTS):
        raise ValueError("CANONICAL_REQUIREMENT_COUNT_REQUIRED")
    out: list[dict[str, Any]] = []
    for sequence, expected in enumerate(PROBE_REQUIREMENTS, start=1):
        item = items[sequence - 1]
        if type(item) is not dict or set(item) != REQUIREMENT_EVIDENCE_FIELDS:
            raise ValueError("REQUIREMENT_EVIDENCE_FIELDS_INVALID")
        if item["sequence"] != sequence or item["requirement"] != expected:
            raise ValueError("CANONICAL_REQUIREMENT_ORDER_REQUIRED")
        positive = _strict_sha(
            item["positive_evidence_digest"], "POSITIVE_EVIDENCE_DIGEST"
        )
        negative = _strict_sha(
            item["negative_evidence_digest"], "NEGATIVE_EVIDENCE_DIGEST"
        )
        if positive == negative:
            raise ValueError("POSITIVE_NEGATIVE_EVIDENCE_MUST_DIFFER")
        out.append(dict(item))
    return out


def _validate_attestation(
    attestation: Mapping[str, Any],
    *,
    challenge: Mapping[str, Any],
    now: int,
) -> dict[str, Any]:
    if not isinstance(attestation, Mapping) or set(attestation) != ATTESTATION_FIELDS:
        raise ValueError("ATTESTATION_FIELDS_INVALID")
    row = dict(attestation)
    if row["schema"] != ATTESTATION_SCHEMA:
        raise ValueError("ATTESTATION_SCHEMA_INVALID")
    trusted_challenge = _validate_challenge(challenge)
    expected_challenge_digest = challenge_digest(trusted_challenge)
    if row["challenge_digest"] != expected_challenge_digest:
        raise ValueError("CHALLENGE_DIGEST_MISMATCH")
    if row["challenge_nonce"] != trusted_challenge["challenge_nonce"]:
        raise ValueError("CHALLENGE_NONCE_MISMATCH")
    if row["collector_key_fingerprint"] != trusted_challenge["collector_key_fingerprint"]:
        raise ValueError("COLLECTOR_KEY_FINGERPRINT_MISMATCH")
    if row["observed_image_path_digest"] != trusted_challenge["expected_image_path_digest"]:
        raise ValueError("OBSERVED_IMAGE_PATH_MISMATCH")
    if row["observed_image_sha256"] != trusted_challenge["expected_image_sha256"]:
        raise ValueError("OBSERVED_IMAGE_SHA256_MISMATCH")
    _strict_sha(row["challenge_digest"], "CHALLENGE_DIGEST")
    for field in (
        "collector_key_fingerprint", "observed_image_path_digest",
        "file_identity_digest", "process_handle_provenance_digest",
        "token_evidence_digest", "job_evidence_digest", "raw_bundle_digest",
    ):
        _strict_sha(row[field], field.upper())
    if type(row["observed_image_sha256"]) is not str or not _HEX64.fullmatch(row["observed_image_sha256"]):
        raise ValueError("OBSERVED_IMAGE_SHA256_INVALID")
    row["requirement_evidence"] = _validate_requirement_evidence(row["requirement_evidence"])
    if type(row["raw_bundle_ref"]) is not str or not _REF.fullmatch(row["raw_bundle_ref"]):
        raise ValueError("RAW_BUNDLE_REF_INVALID")
    collected, valid_until = row["collected_at"], row["valid_until"]
    if (
        type(collected) is not int or type(valid_until) is not int or type(now) is not int
        or collected < trusted_challenge["issued_at"]
        or valid_until > trusted_challenge["expires_at"]
        or not (collected <= now <= valid_until)
        or not (collected < valid_until <= collected + MAX_ATTESTATION_TTL)
    ):
        raise ValueError("ATTESTATION_WINDOW_INVALID")
    return row


def attestation_signing_message(
    attestation: Mapping[str, Any],
    *,
    challenge: Mapping[str, Any],
    now: int,
) -> bytes:
    validated = _validate_attestation(attestation, challenge=challenge, now=now)
    return ATTESTATION_DOMAIN + _canonical(validated)


class SQLitePhysicalAttestationReplayStore:
    """Durable single-use challenge store for independently signed envelopes."""

    def __init__(self, db_path: str | Path):
        path = str(db_path)
        if not path or path == ":memory:" or path.startswith("file:"):
            raise ValueError("explicit durable DB path required")
        self._path = path
        db = sqlite3.connect(path, timeout=10, isolation_level=None)
        try:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("PRAGMA synchronous=FULL")
            db.execute(
                "CREATE TABLE IF NOT EXISTS physical_attestation_challenges ("
                "replay_key TEXT PRIMARY KEY,"
                "expires_at INTEGER NOT NULL,"
                "consumed_at INTEGER NOT NULL)"
            )
        finally:
            db.close()

    def consume_once(self, replay_key: str, *, expires_at: int, now: int) -> bool:
        if type(replay_key) is not str or not _SHA.fullmatch(replay_key):
            return False
        if type(expires_at) is not int or type(now) is not int or now > expires_at:
            return False
        db = sqlite3.connect(self._path, timeout=10, isolation_level=None)
        try:
            db.execute("PRAGMA synchronous=FULL")
            db.execute("BEGIN IMMEDIATE")
            try:
                db.execute(
                    "INSERT INTO physical_attestation_challenges"
                    "(replay_key,expires_at,consumed_at) VALUES(?,?,?)",
                    (replay_key, expires_at, now),
                )
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
        "schema": ATTESTATION_SCHEMA,
        "state": "BLOCKED",
        "reason": reason,
        "challenge_bound": False,
        "collector_signature_cryptographically_valid": False,
        "collector_key_pinned": False,
        "image_identity_bound": False,
        "canonical_12_requirements_bound": False,
        "positive_negative_evidence_bound": False,
        "challenge_replay_consumed": False,
        "collector_key_enrolled_in_production": False,
        "collector_binary_independently_trusted": False,
        "raw_evidence_independently_reviewed": False,
        "physical_probe_executed": False,
        "physical_attestation_verified": False,
        "windows_sandbox_verified": False,
        "network_deny_verified": False,
        "safe_to_resume": False,
        "installer_authorized": False,
        "build_authorized": False,
        "deploy_authorized": False,
    }


def verify_independent_physical_process_attestation(
    challenge: Mapping[str, Any],
    attestation: Mapping[str, Any],
    collector_signature_b64: str,
    *,
    pinned_collector_public_key: bytes,
    expected_collector_key_fingerprint: str,
    now: int,
    replay_store: SQLitePhysicalAttestationReplayStore | None,
) -> dict[str, Any]:
    """Verify collector signature + exact host challenge + 12 evidence bindings.

    Success is intentionally an untrusted cryptographic candidate. This module
    cannot know whether the collector really ran on the owner PC, whether raw
    evidence is truthful, or whether the pinned key was enrolled securely.
    """
    try:
        trusted_challenge = _validate_challenge(challenge)
    except (ValueError, TypeError, OverflowError):
        return _blocked("TRUSTED_CHALLENGE_INVALID")
    if type(expected_collector_key_fingerprint) is not str or not _SHA.fullmatch(
        expected_collector_key_fingerprint
    ):
        return _blocked("TRUSTED_COLLECTOR_FINGERPRINT_REQUIRED")
    if (
        trusted_challenge["collector_key_fingerprint"]
        != expected_collector_key_fingerprint
    ):
        return _blocked("COLLECTOR_FINGERPRINT_CHALLENGE_MISMATCH")
    if (
        type(pinned_collector_public_key) is not bytes
        or len(pinned_collector_public_key) != 32
        or _sha(pinned_collector_public_key) != expected_collector_key_fingerprint
    ):
        return _blocked("UNPINNED_COLLECTOR_KEY")
    try:
        validated = _validate_attestation(attestation, challenge=trusted_challenge, now=now)
        signature = _decode_signature(collector_signature_b64)
        message = ATTESTATION_DOMAIN + _canonical(validated)
        Ed25519PublicKey.from_public_bytes(pinned_collector_public_key).verify(
            signature, message
        )
    except (ValueError, InvalidSignature, TypeError, OverflowError) as exc:
        reason = str(exc) or "ATTESTATION_OR_SIGNATURE_INVALID"
        return _blocked(reason)
    if not isinstance(replay_store, SQLitePhysicalAttestationReplayStore):
        return _blocked("DURABLE_CHALLENGE_REPLAY_STORE_REQUIRED")
    replay_key = _sha(
        b"ATLASQUANT:AION:PHYSICAL_ATTESTATION_REPLAY:V1\x00"
        + validated["challenge_digest"].encode("ascii")
        + b"\x00"
        + expected_collector_key_fingerprint.encode("ascii")
    )
    if not replay_store.consume_once(
        replay_key,
        expires_at=trusted_challenge["expires_at"],
        now=now,
    ):
        return _blocked("CHALLENGE_REPLAY_OR_STORE_FAILURE")
    return {
        "schema": ATTESTATION_SCHEMA,
        "state": CANDIDATE,
        "reason": "",
        "challenge_bound": True,
        "collector_signature_cryptographically_valid": True,
        "collector_key_pinned": True,
        "image_identity_bound": True,
        "canonical_12_requirements_bound": True,
        "positive_negative_evidence_bound": True,
        "challenge_replay_consumed": True,
        "challenge_digest": validated["challenge_digest"],
        "collector_key_fingerprint": expected_collector_key_fingerprint,
        "raw_bundle_digest": validated["raw_bundle_digest"],
        "requirement_count": len(PROBE_REQUIREMENTS),
        "collector_key_enrolled_in_production": False,
        "collector_binary_independently_trusted": False,
        "raw_evidence_independently_reviewed": False,
        "physical_probe_executed": False,
        "physical_attestation_verified": False,
        "windows_sandbox_verified": False,
        "network_deny_verified": False,
        "safe_to_resume": False,
        "installer_authorized": False,
        "build_authorized": False,
        "deploy_authorized": False,
    }


__all__ = [
    "CHALLENGE_SCHEMA", "ATTESTATION_SCHEMA", "PURPOSE", "CANDIDATE",
    "MAX_CHALLENGE_TTL", "MAX_ATTESTATION_TTL",
    "build_physical_process_challenge", "challenge_digest",
    "challenge_signing_material", "attestation_signing_message",
    "SQLitePhysicalAttestationReplayStore",
    "verify_independent_physical_process_attestation",
]
