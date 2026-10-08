"""Offline AION owner key registry verification. NOT enrollment or production auth.

A detached Ed25519 root signature authenticates a canonical owner key/device
snapshot *relative to a root already pinned by the trusted host*. A separately
trusted monotonic minimum epoch and wall-clock are REQUIRED to reject stale
snapshots. No credential enrollment, root custody, host identity, Windows ACL,
anti-rollback store, or production authorization is provided here.
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import json
import re
from typing import Any, Mapping

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

SCHEMA = "ATLASQUANT_AION_OWNER_SIGNED_KEY_REGISTRY_V1"
PURPOSE = "OWNER_KEY_AND_DEVICE_ENROLLMENT_SNAPSHOT"
DOMAIN = b"ATLASQUANT:AION:OWNER_KEY_REGISTRY:V1\x00"
REGISTRY_FIELDS = frozenset({
    "schema", "purpose", "registry_id", "owner_subject", "host_issuer",
    "epoch", "issued_at", "expires_at", "owner_keys", "devices",
})
OWNER_KEY_FIELDS = frozenset({
    "key_id", "public_key_b64", "enrolled_epoch",
    "revoked_epoch", "supersedes",
})
DEVICE_FIELDS = frozenset({
    "device_id", "binding_digest", "enrolled_epoch", "revoked_epoch",
})
_NAME = re.compile(r"[a-zA-Z0-9._:-]{1,96}\Z")
_SHA = re.compile(r"sha256:[0-9a-f]{64}\Z")
MAX_SNAPSHOT_BYTES = 16384
MAX_REGISTRY_TTL = 90 * 86400


def _sha(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _b64(value: Any, size: int) -> bytes:
    if type(value) is not str or not value or len(value) > 256:
        raise ValueError("BAD_BASE64")
    try:
        binary = base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("BAD_BASE64") from exc
    if len(binary) != size or base64.b64encode(binary).decode("ascii") != value:
        raise ValueError("BAD_BASE64")
    return binary


def _canonical(doc: Mapping[str, Any]) -> bytes:
    return json.dumps(
        dict(doc), ensure_ascii=True, sort_keys=True,
        separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")


def _unique_pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for name, value in items:
        if name in out:
            raise ValueError("DUPLICATE_JSON_FIELD")
        out[name] = value
    return out


def parse_registry_snapshot(raw: bytes) -> dict[str, Any]:
    """Only strict bounded JSON bytes; reject duplicate keys and extra fields."""
    if type(raw) is not bytes or not 2 <= len(raw) <= MAX_SNAPSHOT_BYTES:
        raise ValueError("REGISTRY_BYTES_INVALID")
    try:
        doc = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_pairs)
    except (UnicodeError, ValueError, TypeError) as exc:
        raise ValueError("REGISTRY_JSON_INVALID") from exc
    if type(doc) is not dict or set(doc) != REGISTRY_FIELDS:
        raise ValueError("REGISTRY_FIELDS_INVALID")
    if doc.get("schema") != SCHEMA or doc.get("purpose") != PURPOSE:
        raise ValueError("REGISTRY_SCHEMA_INVALID")
    for name in ("registry_id", "owner_subject", "host_issuer"):
        if type(doc.get(name)) is not str or not _NAME.fullmatch(doc[name]):
            raise ValueError("REGISTRY_IDENTITY_INVALID")
    epoch, issued, expires = doc["epoch"], doc["issued_at"], doc["expires_at"]
    if (type(epoch) is not int or epoch < 1
        or type(issued) is not int or type(expires) is not int
        or not (0 < issued < expires <= issued + MAX_REGISTRY_TTL)):
        raise ValueError("REGISTRY_EPOCH_OR_EXPIRY_INVALID")

    owner_keys = doc["owner_keys"]
    if type(owner_keys) is not list or not 1 <= len(owner_keys) <= 12:
        raise ValueError("OWNER_KEYS_INVALID")
    used_ids: set[str] = set()
    used_pubs: set[bytes] = set()
    active = 0
    previous: Mapping[str, Any] | None = None
    for item in owner_keys:
        if type(item) is not dict or set(item) != OWNER_KEY_FIELDS:
            raise ValueError("OWNER_KEY_FIELDS_INVALID")
        kid = item.get("key_id")
        if type(kid) is not str or not _NAME.fullmatch(kid) or kid in used_ids:
            raise ValueError("OWNER_KEY_ID_DUPLICATE_OR_INVALID")
        used_ids.add(kid)
        public = _b64(item.get("public_key_b64"), 32)
        try:
            Ed25519PublicKey.from_public_bytes(public)
        except ValueError as exc:
            raise ValueError("OWNER_PUBLIC_KEY_INVALID") from exc
        if public in used_pubs:
            raise ValueError("OWNER_PUBLIC_KEY_REUSED")
        used_pubs.add(public)
        enrolled, revoked = item.get("enrolled_epoch"), item.get("revoked_epoch")
        if type(enrolled) is not int or not 1 <= enrolled <= epoch:
            raise ValueError("OWNER_ENROLLED_EPOCH_INVALID")
        if revoked is not None and (
            type(revoked) is not int or not enrolled <= revoked <= epoch
        ):
            raise ValueError("OWNER_REVOKED_EPOCH_INVALID")
        if revoked is None:
            active += 1
        if previous is None:
            if item.get("supersedes") is not None:
                raise ValueError("ROOT_OWNER_KEY_PREDECESSOR_INVALID")
        else:
            if (item.get("supersedes") != previous["key_id"]
                or previous["revoked_epoch"] is None
                or previous["revoked_epoch"] > enrolled
                or enrolled <= previous["enrolled_epoch"]):
                raise ValueError("OWNER_KEY_ROTATION_CHAIN_INVALID")
        previous = item
    if active > 1:
        raise ValueError("MULTIPLE_ACTIVE_OWNER_KEYS")

    devices = doc["devices"]
    if type(devices) is not list or not 1 <= len(devices) <= 24:
        raise ValueError("DEVICES_INVALID")
    seen_device_ids: set[str] = set()
    seen_binding_digests: set[str] = set()
    for device in devices:
        if type(device) is not dict or set(device) != DEVICE_FIELDS:
            raise ValueError("DEVICE_FIELDS_INVALID")
        did, binding = device.get("device_id"), device.get("binding_digest")
        if (type(did) is not str or not _NAME.fullmatch(did)
            or did in seen_device_ids):
            raise ValueError("DEVICE_ID_DUPLICATE_OR_INVALID")
        if (type(binding) is not str or not _SHA.fullmatch(binding)
            or binding in seen_binding_digests):
            raise ValueError("DEVICE_BINDING_DUPLICATE_OR_INVALID")
        seen_device_ids.add(did)
        seen_binding_digests.add(binding)
        enrolled, revoked = device.get("enrolled_epoch"), device.get("revoked_epoch")
        if type(enrolled) is not int or not 1 <= enrolled <= epoch:
            raise ValueError("DEVICE_ENROLLED_EPOCH_INVALID")
        if revoked is not None and (
            type(revoked) is not int or not enrolled <= revoked <= epoch
        ):
            raise ValueError("DEVICE_REVOKED_EPOCH_INVALID")
    return doc


def root_signing_message(registry: Mapping[str, Any]) -> bytes:
    """Domain-separated canonical bytes for external root signature tooling."""
    parsed = parse_registry_snapshot(_canonical(registry))
    return DOMAIN + _canonical(parsed)


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "state": "BLOCKED",
        "reason": reason,
        "registry_signature_verified": False,
        "owner_key_resolved": False,
        "device_enrolled": False,
        "production_root_authenticated": False,
        "host_identity_authenticated": False,
        "authorizes_execution": False,
        "authorizes_deploy": False,
        "authorizes_payment": False,
    }


def verify_owner_registry_for_host_review(
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
    minimum_epoch: int,
    now_epoch: int,
) -> dict[str, Any]:
    """Check signed snapshot/key rotation/revocation and resolve active key.

    All expected_* and minimum_epoch MUST be established out-of-band
    by the real authenticated host (NOT user/client-controlled).
    Success is a host *review candidate*, NEVER production authorization.
    """
    try:
        doc = parse_registry_snapshot(registry_raw)
    except (ValueError, TypeError, OverflowError):
        return _blocked("REGISTRY_MALFORMED")
    if (any(type(x) is not str for x in (
        expected_root_fingerprint, expected_registry_id, expected_owner_subject,
        expected_host_issuer, expected_device_id, expected_device_binding_digest
    )) or type(minimum_epoch) is not int or minimum_epoch < 1
        or type(now_epoch) is not int):
        return _blocked("TRUSTED_HOST_EXPECTATIONS_REQUIRED")
    if (
        not _SHA.fullmatch(expected_root_fingerprint)
        or not _SHA.fullmatch(expected_device_binding_digest)
        or not all(_NAME.fullmatch(x) for x in (
            expected_registry_id, expected_owner_subject, expected_host_issuer,
            expected_device_id,
        ))
    ):
        return _blocked("TRUSTED_HOST_EXPECTATIONS_REQUIRED")
    if (doc["registry_id"] != expected_registry_id
        or doc["owner_subject"] != expected_owner_subject
        or doc["host_issuer"] != expected_host_issuer):
        return _blocked("REGISTRY_IDENTITY_MISMATCH")
    if doc["epoch"] < minimum_epoch:
        return _blocked("ROLLBACK_BELOW_TRUSTED_FLOOR")
    if not doc["issued_at"] <= now_epoch <= doc["expires_at"]:
        return _blocked("REGISTRY_NOT_CURRENT")
    if (type(pinned_root_public_key) is not bytes
        or len(pinned_root_public_key) != 32
        or _sha(pinned_root_public_key) != expected_root_fingerprint):
        return _blocked("UNPINNED_REGISTRY_ROOT")
    try:
        signature = _b64(root_signature_b64, 64)
        message = DOMAIN + _canonical(doc)
        Ed25519PublicKey.from_public_bytes(pinned_root_public_key).verify(
            signature, message
        )
    except (ValueError, InvalidSignature, TypeError):
        return _blocked("REGISTRY_SIGNATURE_INVALID")

    active_key = [x for x in doc["owner_keys"] if x["revoked_epoch"] is None]
    if len(active_key) != 1:
        return _blocked("NO_ACTIVE_OWNER_KEY")
    enrolled_device = [x for x in doc["devices"]
                       if x["device_id"] == expected_device_id
                       and x["binding_digest"] == expected_device_binding_digest
                       and x["revoked_epoch"] is None]
    if len(enrolled_device) != 1:
        return _blocked("DEVICE_NOT_ENROLLED_OR_REVOKED")
    key = active_key[0]
    owner_key = _b64(key["public_key_b64"], 32)
    return {
        "schema": SCHEMA,
        "state": "SIGNED_REGISTRY_VERIFIED_FOR_HOST_REVIEW",
        "reason": "",
        "registry_signature_verified": True,
        "owner_key_resolved": True,
        "device_enrolled": True,
        "registry_epoch": doc["epoch"],
        "registry_digest": _sha(message),
        "owner_key_id": key["key_id"],
        "owner_key_fingerprint": _sha(owner_key),
        "resolved_owner_public_key": owner_key,  # host-internal ONLY; never expose via UI
        "device_binding_digest": expected_device_binding_digest,
        "production_root_authenticated": False,
        "host_identity_authenticated": False,
        "authorizes_execution": False,
        "authorizes_deploy": False,
        "authorizes_payment": False,
    }


__all__ = [
    "SCHEMA", "PURPOSE", "DOMAIN", "MAX_REGISTRY_TTL",
    "parse_registry_snapshot", "root_signing_message",
    "verify_owner_registry_for_host_review",
]
