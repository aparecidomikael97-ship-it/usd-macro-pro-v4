"""AION CI-only rooted-owner signed pinned-binary preflight V1.

This module deliberately grants NO process execution authority. It binds the
#1091 signed executable manifest to an owner public key resolved only from a
root-signed registry, checks an enrolled/non-revoked device, and atomically
consumes a durable replay key after every cryptographic/image check succeeds.

All roots/keys/devices used by tests are synthetic fixtures. A passing result
means only "rooted owner binary preflight candidate"; it never permits resume,
installation, build, deployment, network access, or production activation.
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

from atlasquant_aion_windows_signed_binary_ci_negative_intent_v1 import (
    CANDIDATE as BINARY_CANDIDATE,
    canonical_intent,
    check_signed_ci_negative_intent,
)

SCHEMA = "AION_ROOTED_OWNER_SIGNED_BINARY_PREFLIGHT_CI_V1"
REGISTRY_SCHEMA = "ATLASQUANT_AION_OWNER_SIGNED_KEY_REGISTRY_V1"
REGISTRY_PURPOSE = "OWNER_KEY_AND_DEVICE_ENROLLMENT_SNAPSHOT"
REGISTRY_DOMAIN = b"ATLASQUANT:AION:OWNER_KEY_REGISTRY:V1\x00"
STATE = "ROOTED_OWNER_SIGNED_BINARY_PREFLIGHT_CANDIDATE"
_SHA = re.compile(r"sha256:[0-9a-f]{64}\Z")
_NAME = re.compile(r"[a-zA-Z0-9._:-]{1,96}\Z")
MAX_REGISTRY_TTL = 90 * 86400
MAX_REGISTRY_BYTES = 16384
REGISTRY_FIELDS = frozenset({
    "schema", "purpose", "registry_id", "owner_subject", "host_issuer",
    "epoch", "issued_at", "expires_at", "owner_keys", "devices",
})
OWNER_KEY_FIELDS = frozenset({
    "key_id", "public_key_b64", "enrolled_epoch", "revoked_epoch", "supersedes",
})
DEVICE_FIELDS = frozenset({
    "device_id", "binding_digest", "enrolled_epoch", "revoked_epoch",
})


def _sha(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _canonical(value: Mapping[str, Any]) -> bytes:
    return json.dumps(
        dict(value), ensure_ascii=True, sort_keys=True,
        separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")


def _decode_b64(value: Any, size: int) -> bytes:
    if type(value) is not str or not value or len(value) > 256:
        raise ValueError("BAD_BASE64")
    try:
        raw = base64.b64decode(value, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise ValueError("BAD_BASE64") from exc
    if len(raw) != size or base64.b64encode(raw).decode("ascii") != value:
        raise ValueError("BAD_BASE64")
    return raw


def _unique_pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in items:
        if key in result:
            raise ValueError("DUPLICATE_JSON_FIELD")
        result[key] = value
    return result


def _parse_registry(raw: bytes) -> dict[str, Any]:
    if type(raw) is not bytes or not 2 <= len(raw) <= MAX_REGISTRY_BYTES:
        raise ValueError("REGISTRY_BYTES_INVALID")
    try:
        doc = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_pairs)
    except (UnicodeError, ValueError, TypeError) as exc:
        raise ValueError("REGISTRY_JSON_INVALID") from exc
    if type(doc) is not dict or set(doc) != REGISTRY_FIELDS:
        raise ValueError("REGISTRY_FIELDS_INVALID")
    if doc["schema"] != REGISTRY_SCHEMA or doc["purpose"] != REGISTRY_PURPOSE:
        raise ValueError("REGISTRY_SCHEMA_INVALID")
    for field in ("registry_id", "owner_subject", "host_issuer"):
        value = doc[field]
        if type(value) is not str or not _NAME.fullmatch(value):
            raise ValueError("REGISTRY_IDENTITY_INVALID")
    epoch = doc["epoch"]
    issued = doc["issued_at"]
    expires = doc["expires_at"]
    if (
        type(epoch) is not int or epoch < 1
        or type(issued) is not int or type(expires) is not int
        or not (0 < issued < expires <= issued + MAX_REGISTRY_TTL)
    ):
        raise ValueError("REGISTRY_EPOCH_OR_EXPIRY_INVALID")

    owner_keys = doc["owner_keys"]
    if type(owner_keys) is not list or not 1 <= len(owner_keys) <= 12:
        raise ValueError("OWNER_KEYS_INVALID")
    seen_ids: set[str] = set()
    seen_public: set[bytes] = set()
    active_count = 0
    previous: Mapping[str, Any] | None = None
    for item in owner_keys:
        if type(item) is not dict or set(item) != OWNER_KEY_FIELDS:
            raise ValueError("OWNER_KEY_FIELDS_INVALID")
        key_id = item["key_id"]
        if type(key_id) is not str or not _NAME.fullmatch(key_id) or key_id in seen_ids:
            raise ValueError("OWNER_KEY_ID_INVALID")
        seen_ids.add(key_id)
        public = _decode_b64(item["public_key_b64"], 32)
        Ed25519PublicKey.from_public_bytes(public)
        if public in seen_public:
            raise ValueError("OWNER_PUBLIC_KEY_REUSED")
        seen_public.add(public)
        enrolled = item["enrolled_epoch"]
        revoked = item["revoked_epoch"]
        if type(enrolled) is not int or not 1 <= enrolled <= epoch:
            raise ValueError("OWNER_ENROLLED_EPOCH_INVALID")
        if revoked is not None and (
            type(revoked) is not int or not enrolled <= revoked <= epoch
        ):
            raise ValueError("OWNER_REVOKED_EPOCH_INVALID")
        if revoked is None:
            active_count += 1
        if previous is None:
            if item["supersedes"] is not None:
                raise ValueError("ROOT_OWNER_KEY_PREDECESSOR_INVALID")
        else:
            if (
                item["supersedes"] != previous["key_id"]
                or previous["revoked_epoch"] is None
                or previous["revoked_epoch"] > enrolled
                or enrolled <= previous["enrolled_epoch"]
            ):
                raise ValueError("OWNER_KEY_ROTATION_CHAIN_INVALID")
        previous = item
    if active_count != 1:
        raise ValueError("EXACTLY_ONE_ACTIVE_OWNER_KEY_REQUIRED")

    devices = doc["devices"]
    if type(devices) is not list or not 1 <= len(devices) <= 24:
        raise ValueError("DEVICES_INVALID")
    seen_devices: set[str] = set()
    seen_bindings: set[str] = set()
    for device in devices:
        if type(device) is not dict or set(device) != DEVICE_FIELDS:
            raise ValueError("DEVICE_FIELDS_INVALID")
        device_id = device["device_id"]
        binding = device["binding_digest"]
        if (
            type(device_id) is not str or not _NAME.fullmatch(device_id)
            or device_id in seen_devices
        ):
            raise ValueError("DEVICE_ID_INVALID")
        if (
            type(binding) is not str or not _SHA.fullmatch(binding)
            or binding in seen_bindings
        ):
            raise ValueError("DEVICE_BINDING_INVALID")
        seen_devices.add(device_id)
        seen_bindings.add(binding)
        enrolled = device["enrolled_epoch"]
        revoked = device["revoked_epoch"]
        if type(enrolled) is not int or not 1 <= enrolled <= epoch:
            raise ValueError("DEVICE_ENROLLED_EPOCH_INVALID")
        if revoked is not None and (
            type(revoked) is not int or not enrolled <= revoked <= epoch
        ):
            raise ValueError("DEVICE_REVOKED_EPOCH_INVALID")
    return doc


def registry_signing_message(registry: Mapping[str, Any]) -> bytes:
    parsed = _parse_registry(_canonical(registry))
    return REGISTRY_DOMAIN + _canonical(parsed)


def _blocked(reason: str, *, registry_reason: str = "", binary_reason: str = "") -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "state": "BLOCKED",
        "reason": reason,
        "registry_reason": registry_reason,
        "binary_reason": binary_reason,
        "root_registry_verified": False,
        "owner_key_resolved": False,
        "device_enrolled": False,
        "owner_manifest_signature_verified": False,
        "binary_path_digest_bound": False,
        "durable_replay_guard_consumed": False,
        "owner_identity_bound_to_rooted_registry": False,
        "production_owner_identity_verified": False,
        "trusted_host_attached": False,
        "physical_attestation_verified": False,
        "appcontainer_verified": False,
        "network_deny_verified": False,
        "safe_to_resume": False,
        "installer_authorized": False,
        "build_authorized": False,
        "deploy_authorized": False,
    }


class SQLiteBinaryAuthorizationReplayStore:
    """Host-owned replay store for signed binary preflight nonces.

    Durability/uniqueness is provided by SQLite FULL synchronous + IMMEDIATE
    transaction. Real deployment still requires trusted filesystem ACLs and
    anti-rollback storage outside this CI-only implementation.
    """

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
                "CREATE TABLE IF NOT EXISTS binary_authorization_nonces ("
                "nonce_key TEXT PRIMARY KEY,"
                "expires_at INTEGER NOT NULL,"
                "consumed_at INTEGER NOT NULL)"
            )
        finally:
            db.close()

    def consume_once(self, nonce_key: str, *, expires_at: int, now: int) -> bool:
        if type(nonce_key) is not str or not _SHA.fullmatch(nonce_key):
            return False
        if type(expires_at) is not int or type(now) is not int or now > expires_at:
            return False
        db = sqlite3.connect(self._path, timeout=10, isolation_level=None)
        try:
            db.execute("PRAGMA synchronous=FULL")
            db.execute("BEGIN IMMEDIATE")
            try:
                db.execute(
                    "INSERT INTO binary_authorization_nonces"
                    "(nonce_key,expires_at,consumed_at) VALUES(?,?,?)",
                    (nonce_key, expires_at, now),
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


def _verify_registry(
    registry_raw: bytes,
    root_signature_b64: str,
    *,
    pinned_root_public_key: bytes,
    expected_root_fingerprint: str,
    expected_registry_id: str,
    expected_owner_subject: str,
    expected_host_issuer: str,
    expected_device_id: str,
    expected_device_binding_digest: str,
    minimum_registry_epoch: int,
    now: int,
) -> tuple[dict[str, Any] | None, str]:
    try:
        doc = _parse_registry(registry_raw)
    except (ValueError, TypeError, OverflowError):
        return None, "REGISTRY_MALFORMED"
    host_values = (
        expected_root_fingerprint, expected_registry_id, expected_owner_subject,
        expected_host_issuer, expected_device_id, expected_device_binding_digest,
    )
    if any(type(v) is not str for v in host_values):
        return None, "TRUSTED_HOST_EXPECTATIONS_REQUIRED"
    if (
        not _SHA.fullmatch(expected_root_fingerprint)
        or not _SHA.fullmatch(expected_device_binding_digest)
        or not all(_NAME.fullmatch(v) for v in (
            expected_registry_id, expected_owner_subject,
            expected_host_issuer, expected_device_id,
        ))
        or type(minimum_registry_epoch) is not int
        or minimum_registry_epoch < 1
        or type(now) is not int
    ):
        return None, "TRUSTED_HOST_EXPECTATIONS_REQUIRED"
    if (
        doc["registry_id"] != expected_registry_id
        or doc["owner_subject"] != expected_owner_subject
        or doc["host_issuer"] != expected_host_issuer
    ):
        return None, "REGISTRY_IDENTITY_MISMATCH"
    if doc["epoch"] < minimum_registry_epoch:
        return None, "ROLLBACK_BELOW_TRUSTED_FLOOR"
    if not doc["issued_at"] <= now <= doc["expires_at"]:
        return None, "REGISTRY_NOT_CURRENT"
    if (
        type(pinned_root_public_key) is not bytes
        or len(pinned_root_public_key) != 32
        or _sha(pinned_root_public_key) != expected_root_fingerprint
    ):
        return None, "UNPINNED_REGISTRY_ROOT"
    try:
        signature = _decode_b64(root_signature_b64, 64)
        message = REGISTRY_DOMAIN + _canonical(doc)
        Ed25519PublicKey.from_public_bytes(pinned_root_public_key).verify(
            signature, message
        )
    except (ValueError, InvalidSignature, TypeError):
        return None, "REGISTRY_SIGNATURE_INVALID"
    active = [item for item in doc["owner_keys"] if item["revoked_epoch"] is None]
    if len(active) != 1:
        return None, "NO_ACTIVE_OWNER_KEY"
    enrolled = [
        item for item in doc["devices"]
        if (
            item["device_id"] == expected_device_id
            and item["binding_digest"] == expected_device_binding_digest
            and item["revoked_epoch"] is None
        )
    ]
    if len(enrolled) != 1:
        return None, "DEVICE_NOT_ENROLLED_OR_REVOKED"
    key = active[0]
    public = _decode_b64(key["public_key_b64"], 32)
    return {
        "doc": doc,
        "owner_public_key": public,
        "owner_key_id": key["key_id"],
        "owner_key_fingerprint": _sha(public),
        "registry_digest": _sha(message),
    }, ""


def verify_rooted_owner_signed_binary_preflight(
    registry_raw: bytes,
    registry_root_signature_b64: str,
    manifest: Any,
    owner_manifest_signature: Any,
    *,
    pinned_root_public_key: bytes,
    expected_root_fingerprint: str,
    expected_registry_id: str,
    expected_owner_subject: str,
    expected_host_issuer: str,
    expected_device_id: str,
    expected_device_binding_digest: str,
    minimum_registry_epoch: int,
    observed_image_path: Any,
    observed_image_sha256: Any,
    now: int,
    replay_store: SQLiteBinaryAuthorizationReplayStore | None,
) -> dict[str, Any]:
    """Bind #1091's negative executable manifest to rooted owner identity.

    The manifest operation remains QUARANTINE_NORMAL_CHILD_NEVER_RESUME.
    Even a successful rooted signature + replay check is intentionally unable
    to resume or install anything.
    """
    registry, registry_reason = _verify_registry(
        registry_raw, registry_root_signature_b64,
        pinned_root_public_key=pinned_root_public_key,
        expected_root_fingerprint=expected_root_fingerprint,
        expected_registry_id=expected_registry_id,
        expected_owner_subject=expected_owner_subject,
        expected_host_issuer=expected_host_issuer,
        expected_device_id=expected_device_id,
        expected_device_binding_digest=expected_device_binding_digest,
        minimum_registry_epoch=minimum_registry_epoch,
        now=now,
    )
    if registry is None:
        return _blocked("ROOTED_OWNER_REGISTRY_REQUIRED", registry_reason=registry_reason)
    binary = check_signed_ci_negative_intent(
        manifest, owner_manifest_signature, registry["owner_public_key"],
        observed_image_path=observed_image_path,
        observed_image_sha256=observed_image_sha256,
        now=now,
    )
    if binary.get("state") != BINARY_CANDIDATE:
        return _blocked(
            "ROOTED_OWNER_BINARY_SIGNATURE_OR_IMAGE_REJECTED",
            binary_reason=str(binary.get("reason") or "BINARY_CHECK_FAILED"),
        )
    if not isinstance(replay_store, SQLiteBinaryAuthorizationReplayStore):
        return _blocked("DURABLE_REPLAY_STORE_REQUIRED")
    try:
        nonce = manifest["nonce"]
        expires_at = manifest["expires_at"]
        replay_material = (
            b"ATLASQUANT:AION:ROOTED_BINARY_PREFLIGHT:V1\x00"
            + registry["registry_digest"].encode("ascii")
            + b"\x00" + registry["owner_public_key"]
            + b"\x00" + bytes.fromhex(nonce)
            + b"\x00" + canonical_intent(manifest)
        )
    except (KeyError, TypeError, ValueError):
        return _blocked("REPLAY_MATERIAL_INVALID")
    nonce_key = _sha(replay_material)
    if not replay_store.consume_once(nonce_key, expires_at=expires_at, now=now):
        return _blocked("REPLAY_OR_STORE_FAILURE")
    return {
        "schema": SCHEMA,
        "state": STATE,
        "reason": "",
        "registry_reason": "",
        "binary_reason": "",
        "root_registry_verified": True,
        "owner_key_resolved": True,
        "device_enrolled": True,
        "owner_manifest_signature_verified": True,
        "binary_path_digest_bound": True,
        "durable_replay_guard_consumed": True,
        "owner_identity_bound_to_rooted_registry": True,
        "registry_epoch": registry["doc"]["epoch"],
        "registry_digest": registry["registry_digest"],
        "owner_subject": expected_owner_subject,
        "owner_key_id": registry["owner_key_id"],
        "owner_key_fingerprint": registry["owner_key_fingerprint"],
        "device_id": expected_device_id,
        "production_owner_identity_verified": False,
        "trusted_host_attached": False,
        "physical_attestation_verified": False,
        "appcontainer_verified": False,
        "network_deny_verified": False,
        "safe_to_resume": False,
        "installer_authorized": False,
        "build_authorized": False,
        "deploy_authorized": False,
    }


__all__ = [
    "SCHEMA", "STATE", "REGISTRY_SCHEMA", "REGISTRY_PURPOSE",
    "registry_signing_message", "SQLiteBinaryAuthorizationReplayStore",
    "verify_rooted_owner_signed_binary_preflight",
]
