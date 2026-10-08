"""AION host-owner crypto verification V1: offline signed proof and durable replay guard.

This is NOT a login server: it must only be called by the trusted authenticated
host with an independently enrolled/pinned owner public key, a verified session
binding and a host-owned SQLite replay database. Never take trust inputs from
a browser request. No owner signing/private-key enrollment or OS changes occur.
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

from atlasquant_aion_owner_experience_v1 import owner_binding

SCHEMA = "AION_TRUSTED_OWNER_SESSION_PROOF_V1"
PURPOSE = "HUMAN_OWNER_SESSION_HOST_BINDING"
EXPECTED_FIELDS = frozenset({
    "schema", "purpose", "principal", "subject", "issuer", "audience",
    "session_binding_digest", "device_binding_digest",
    "key_fingerprint", "nonce", "issued_at", "expires_at",
})
_SHA256 = re.compile(r"sha256:[0-9a-f]{64}\Z")
_NONCE = re.compile(r"[0-9a-f]{64}\Z")
_TAG = re.compile(r"[a-zA-Z0-9._:/-]{1,150}\Z")
SUBJECT_MAX = 120
MAX_TTL_SECONDS = 120


def _digest_bytes(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _canonical(obj: Mapping[str, Any]) -> bytes:
    return json.dumps(dict(obj), ensure_ascii=True, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def signing_message(payload: Mapping[str, Any]) -> bytes:
    """Domain-separated bytes for external HUMAN_OWNER signer; no private key here."""
    if not isinstance(payload, Mapping) or set(payload) != EXPECTED_FIELDS:
        raise ValueError("wrong owner proof fields")
    if not _valid_payload(payload):
        raise ValueError("invalid owner proof payload")
    return b"ATLASQUANT:AION:OWNER_HOST_PROOF:V1\x00" + _canonical(payload)


def _valid_payload(p: Mapping[str, Any]) -> bool:
    if p.get("schema") != SCHEMA or p.get("purpose") != PURPOSE:
        return False
    if p.get("principal") != "HUMAN_OWNER":
        return False
    for k in ("subject", "issuer", "audience"):
        v = p.get(k)
        if type(v) is not str or not v or len(v) > SUBJECT_MAX:
            return False
        if k != "subject" and not _TAG.fullmatch(v):
            return False
    for k in ("session_binding_digest", "device_binding_digest", "key_fingerprint"):
        if type(p.get(k)) is not str or not _SHA256.fullmatch(p[k]):
            return False
    if type(p.get("nonce")) is not str or not _NONCE.fullmatch(p["nonce"]):
        return False
    if type(p.get("issued_at")) is not int or type(p.get("expires_at")) is not int:
        return False
    return (0 < p["issued_at"] < p["expires_at"]
            and p["expires_at"] - p["issued_at"] <= MAX_TTL_SECONDS)


def _decode_signature(value: Any) -> bytes:
    if type(value) is not str or not value or len(value) > 160:
        raise ValueError("invalid signature encoding")
    try:
        data = base64.b64decode(value, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise ValueError("invalid signature encoding") from exc
    if len(data) != 64 or base64.b64encode(data).decode("ascii") != value:
        raise ValueError("noncanonical signature")
    return data


class SQLiteOwnerNonceRegistry:
    """Explicit host-controlled durable nonce store. NEVER default to ':memory:'.

    Assumes trusted OS permissions/ACLs on path/parent and single owner account.
    This store provides atomic uniqueness, NOT independent key enrollment.
    """
    def __init__(self, db_path: str | Path):
        path = str(db_path)
        if not path or path == ":memory:" or path.startswith("file:"):
            raise ValueError("explicit durable local DB path required")
        self._path = path
        db = sqlite3.connect(path, timeout=10, isolation_level=None)
        try:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("PRAGMA synchronous=FULL")
            db.execute(
                "CREATE TABLE IF NOT EXISTS owner_proof_nonces ("
                "nonce_key TEXT PRIMARY KEY,"
                "expires_at INTEGER NOT NULL,"
                "consumed_at INTEGER NOT NULL)"
            )
        finally:
            db.close()

    def consume_once(self, nonce_key: str, *, expires_at: int, now: int) -> bool:
        """Insert atomically before returning any verified assertion."""
        if not isinstance(nonce_key, str) or not _SHA256.fullmatch(nonce_key):
            return False
        if type(expires_at) is not int or type(now) is not int or now > expires_at:
            return False
        db = sqlite3.connect(self._path, timeout=10, isolation_level=None)
        try:
            db.execute("PRAGMA synchronous=FULL")
            db.execute("BEGIN IMMEDIATE")
            try:
                db.execute(
                    "INSERT INTO owner_proof_nonces(nonce_key,expires_at,consumed_at)"
                    " VALUES(?,?,?)", (nonce_key, expires_at, now)
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
        "schema": SCHEMA, "state": "BLOCKED", "reason": reason,
        "verified": False, "owner_assertion": None,
        "authorizes_execution": False, "authorizes_deploy": False,
        "authorizes_payment": False, "trusted_host_attached": False,
    }


def verify_host_owner_proof(
    access: Mapping[str, Any] | None,
    payload: Mapping[str, Any] | None,
    signature_b64: str,
    *,
    pinned_owner_public_key: bytes,
    expected_pinned_key_fingerprint: str,
    expected_session_binding_digest: str,
    expected_device_binding_digest: str,
    expected_issuer: str,
    expected_audience: str,
    now_epoch: int,
    nonce_registry: SQLiteOwnerNonceRegistry | None,
) -> dict[str, Any]:
    """Verify detached owner signature, exact session/device, and atomically burn nonce.

    All expected_* inputs MUST be independently trusted SERVER-SIDE values.
    This is necessary but not sufficient for owner proof in a deployed system:
    real key enrollment, Windows ACL/FIDO2, session provenance and OS security
    must still be reviewed and wired by the trusted host.
    """
    if not isinstance(payload, Mapping) or set(payload) != EXPECTED_FIELDS:
        return _blocked("INVALID_PAYLOAD_SHAPE")
    if not _valid_payload(payload):
        return _blocked("INVALID_PAYLOAD")
    if type(now_epoch) is not int or not (
        payload["issued_at"] <= now_epoch <= payload["expires_at"]
        and now_epoch - payload["issued_at"] <= MAX_TTL_SECONDS
    ):
        return _blocked("PROOF_EXPIRED_OR_FUTURE")
    if any(type(x) is not str for x in (
        expected_pinned_key_fingerprint, expected_session_binding_digest,
        expected_device_binding_digest, expected_issuer, expected_audience,
    )):
        return _blocked("HOST_POLICY_INVALID")
    if (not _SHA256.fullmatch(expected_session_binding_digest)
        or not _SHA256.fullmatch(expected_device_binding_digest)
        or not _SHA256.fullmatch(expected_pinned_key_fingerprint)
        or not expected_issuer or not expected_audience):
        return _blocked("HOST_POLICY_INVALID")
    if payload["issuer"] != expected_issuer or payload["audience"] != expected_audience:
        return _blocked("WRONG_ISSUER_OR_AUDIENCE")
    if (payload["session_binding_digest"] != expected_session_binding_digest
        or payload["device_binding_digest"] != expected_device_binding_digest):
        return _blocked("SESSION_OR_DEVICE_MISMATCH")
    if type(pinned_owner_public_key) is not bytes or len(pinned_owner_public_key) != 32:
        return _blocked("PUBLIC_KEY_INVALID")
    fingerprint = _digest_bytes(pinned_owner_public_key)
    if fingerprint != expected_pinned_key_fingerprint or payload["key_fingerprint"] != fingerprint:
        return _blocked("UNPINNED_OWNER_KEY")
    try:
        signature = _decode_signature(signature_b64)
        message = signing_message(payload)
        Ed25519PublicKey.from_public_bytes(pinned_owner_public_key).verify(signature, message)
    except (ValueError, InvalidSignature, TypeError):
        return _blocked("INVALID_OWNER_SIGNATURE")
    # No server-issued authenticated ADMIN session -> no owner assertion.
    candidate = {
        "verified": True, "principal": "HUMAN_OWNER",
        "subject": payload["subject"], "issuer": payload["issuer"],
    }
    binding = owner_binding(access, candidate)
    if binding.get("bound") is not True:
        return _blocked("AUTHENTICATED_OWNER_SESSION_REQUIRED")
    if not isinstance(nonce_registry, SQLiteOwnerNonceRegistry):
        return _blocked("DURABLE_REPLAY_STORE_REQUIRED")
    nonce_key = _digest_bytes(pinned_owner_public_key + bytes.fromhex(payload["nonce"]))
    if not nonce_registry.consume_once(
        nonce_key, expires_at=payload["expires_at"], now=now_epoch
    ):
        return _blocked("REPLAY_OR_STORE_FAILURE")
    return {
        "schema": SCHEMA,
        "state": "CRYPTO_PROOF_VERIFIED_FOR_TRUSTED_HOST_REVIEW",
        "reason": "",
        "verified": True,
        "owner_assertion": candidate,
        "binding_digest": binding["binding_digest"],
        "proof_digest": _digest_bytes(message),
        "owner_key_fingerprint": fingerprint,
        "authorizes_execution": False,
        "authorizes_deploy": False,
        "authorizes_payment": False,
        "trusted_host_attached": False,  # real host integration separate
    }


__all__ = [
    "SCHEMA", "PURPOSE", "EXPECTED_FIELDS", "MAX_TTL_SECONDS",
    "signing_message", "SQLiteOwnerNonceRegistry", "verify_host_owner_proof",
]
