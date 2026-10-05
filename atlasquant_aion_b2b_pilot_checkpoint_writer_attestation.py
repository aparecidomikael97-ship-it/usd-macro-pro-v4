"""AION B2B Pilot Checkpoint Writer Authority Attestation V1.

Cryptographically verifies that an external checkpoint-writer key acknowledged
the exact B2B pilot decision persistence receipt.

This module never writes Checkpoint Master, never captures a private key and
never authorizes pilot activation. It complements (does not replace) the
separate persistence-content attestation.
"""
from __future__ import annotations

import base64
import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Any, Mapping

from cryptography.exceptions import InvalidSignature

from atlasquant_aion_nonce_registry import PersistentNonceRegistry
from atlasquant_aion_trust_root import TrustRootRegistry

SCHEMA = "ATLASQUANT_AION_B2B_PILOT_CHECKPOINT_WRITER_ATTESTATION_V1"
REQUEST_SCHEMA = "ATLASQUANT_AION_B2B_PILOT_CHECKPOINT_WRITER_REQUEST_V1"
RESULT_SCHEMA = "ATLASQUANT_AION_B2B_PILOT_CHECKPOINT_WRITER_VERIFICATION_V1"
RECEIPT_SCHEMA = "ATLASQUANT_AION_B2B_PILOT_DECISION_CHECKPOINT_RECEIPT_V1"

PURPOSE = "B2B_PILOT_CHECKPOINT_WRITE_RECEIPT_ACKNOWLEDGEMENT"
MECHANISM = "ED25519_EXTERNAL_CHECKPOINT_WRITER_KEY"
MAX_WINDOW_SECONDS = 180

_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{7,159}$")
_NONCE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{15,255}$")
_SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


def _canonical(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
        default=str,
    )


def canonical_writer_attestation_bytes(
    request_body: Mapping[str, Any],
) -> bytes:
    return _canonical(dict(request_body)).encode("utf-8")


def _digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(
        canonical_writer_attestation_bytes(value)
    ).hexdigest()


def _text(value: Any, limit: int = 320) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(value.replace("\x00", "").split())[:limit]


def _parse_ts(value: Any) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError("timestamp must be RFC3339 UTC")
    try:
        return datetime.fromisoformat(
            value[:-1] + "+00:00"
        ).astimezone(timezone.utc)
    except Exception as exc:
        raise ValueError("invalid timestamp") from exc


def _window_blockers(
    *,
    issued_at: Any,
    expires_at: Any,
    now_ts: Any,
) -> list[str]:
    try:
        issued = _parse_ts(issued_at)
        expires = _parse_ts(expires_at)
        now = _parse_ts(now_ts)
    except ValueError:
        return ["CHECKPOINT_WRITER_TIME_INVALID"]

    blockers: list[str] = []
    window = (expires - issued).total_seconds()
    if window <= 0:
        blockers.append("CHECKPOINT_WRITER_WINDOW_INVALID")
    elif window > MAX_WINDOW_SECONDS:
        blockers.append("CHECKPOINT_WRITER_WINDOW_TOO_LONG")
    if issued > now:
        blockers.append("CHECKPOINT_WRITER_NOT_YET_VALID")
    if expires <= now:
        blockers.append("CHECKPOINT_WRITER_REQUEST_EXPIRED")
    return blockers


def _decode_signature(value: Any) -> bytes:
    if not isinstance(value, str) or not value:
        raise ValueError("signature required")
    try:
        raw = value.encode("ascii")
        decoded = base64.urlsafe_b64decode(
            raw + b"=" * (-len(raw) % 4)
        )
    except Exception as exc:
        raise ValueError("invalid signature encoding") from exc
    if len(decoded) != 64:
        raise ValueError("Ed25519 signature must be 64 bytes")
    return decoded


def _public_key_fingerprint(entry: Any) -> str:
    encoded = str(entry.public_key_b64 or "").encode("ascii")
    raw = base64.urlsafe_b64decode(
        encoded + b"=" * (-len(encoded) % 4)
    )
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _receipt_blockers(
    receipt: Mapping[str, Any] | None,
) -> tuple[dict[str, Any], list[str]]:
    row = dict(receipt) if isinstance(receipt, Mapping) else {}
    blockers: list[str] = []

    if row.get("schema") != RECEIPT_SCHEMA:
        blockers.append("CHECKPOINT_RECEIPT_SCHEMA_INVALID")
    if row.get("status") != "CONFIRMED":
        blockers.append("CHECKPOINT_RECEIPT_NOT_CONFIRMED")
    if row.get("storage_target") != "CHECKPOINT_MASTER":
        blockers.append("CHECKPOINT_RECEIPT_TARGET_INVALID")
    if row.get("write_mode") != "EXPLICIT_AUTHORIZED_APPEND":
        blockers.append("CHECKPOINT_RECEIPT_WRITE_MODE_INVALID")
    if row.get("namespace") != "aion_b2b_pilot_owner_decision":
        blockers.append("CHECKPOINT_RECEIPT_NAMESPACE_INVALID")
    if not _text(row.get("event_id"), 160):
        blockers.append("CHECKPOINT_RECEIPT_EVENT_ID_REQUIRED")
    if not _text(row.get("pilot_id"), 120):
        blockers.append("CHECKPOINT_RECEIPT_PILOT_ID_REQUIRED")
    if not _text(row.get("writer_ref"), 240):
        blockers.append("CHECKPOINT_RECEIPT_WRITER_REF_REQUIRED")

    for key in (
        "patch_digest",
        "before_checkpoint_digest",
        "after_checkpoint_digest",
        "decision_record_digest",
    ):
        if not _SHA256_RE.fullmatch(_text(row.get(key), 180)):
            blockers.append(
                "CHECKPOINT_RECEIPT_DIGEST_INVALID:" + key
            )

    if row.get("writer_identity_verified") is not False:
        blockers.append("CHECKPOINT_RECEIPT_PREVERIFIED_WRITER_FORBIDDEN")
    if row.get("pilot_activation_authorized") is not False:
        blockers.append("CHECKPOINT_RECEIPT_ACTIVATION_UNSAFE")
    if row.get("pilot_activated") is not False:
        blockers.append("CHECKPOINT_RECEIPT_ACTIVE_UNSAFE")
    if row.get("external_action_executed") is not False:
        blockers.append("CHECKPOINT_RECEIPT_EXTERNAL_ACTION_UNSAFE")

    supplied = _text(row.get("receipt_digest"), 180)
    body = {
        key: value
        for key, value in row.items()
        if key != "receipt_digest"
    }
    if not _SHA256_RE.fullmatch(supplied):
        blockers.append("CHECKPOINT_RECEIPT_DIGEST_INVALID")
    elif supplied != _digest(body):
        blockers.append("CHECKPOINT_RECEIPT_DIGEST_MISMATCH")

    return row, list(dict.fromkeys(blockers))


def _identity_blockers(
    *,
    ceremony_id: Any,
    nonce: Any,
    key_id: Any,
    key_version: Any,
) -> list[str]:
    blockers: list[str] = []
    if (
        not isinstance(ceremony_id, str)
        or _ID_RE.fullmatch(ceremony_id) is None
    ):
        blockers.append("CHECKPOINT_WRITER_CEREMONY_ID_INVALID")
    if (
        not isinstance(nonce, str)
        or _NONCE_RE.fullmatch(nonce) is None
    ):
        blockers.append("CHECKPOINT_WRITER_NONCE_INVALID")
    if (
        not isinstance(key_id, str)
        or not key_id
        or len(key_id) > 128
    ):
        blockers.append("CHECKPOINT_WRITER_KEY_ID_INVALID")
    if (
        not isinstance(key_version, int)
        or isinstance(key_version, bool)
        or key_version < 1
    ):
        blockers.append("CHECKPOINT_WRITER_KEY_VERSION_INVALID")
    return blockers


def _blocked(*items: str) -> dict[str, Any]:
    return {
        "schema": RESULT_SCHEMA,
        "state": "BLOCKED",
        "blockers": sorted(set(items)),
        "writer_identity_verified": False,
        "writer_authority_verified": False,
        "receipt_binding_verified": False,
        "nonce_registered": False,
        "pilot_activation_authorized": False,
        "pilot_activated": False,
        "checkpoint_write_performed": False,
        "customer_contact_authorized": False,
        "billing_authorized": False,
        "deploy_authorized": False,
        "production_mutation_authorized": False,
        "external_action_executed": False,
        "network_called": False,
        "executes_action": False,
    }


def build_checkpoint_writer_attestation_request(
    *,
    checkpoint_write_receipt: Mapping[str, Any] | None,
    writer_trust_roots: TrustRootRegistry,
    now_ts: str,
    ceremony_id: str,
    nonce: str,
    issued_at: str,
    expires_at: str,
    key_id: str,
    key_version: int,
) -> dict[str, Any]:
    """Prepare an external writer-signature request; performs no signature."""
    receipt, blockers = _receipt_blockers(checkpoint_write_receipt)
    blockers.extend(
        _identity_blockers(
            ceremony_id=ceremony_id,
            nonce=nonce,
            key_id=key_id,
            key_version=key_version,
        )
    )
    blockers.extend(
        _window_blockers(
            issued_at=issued_at,
            expires_at=expires_at,
            now_ts=now_ts,
        )
    )

    entry = None
    if not isinstance(writer_trust_roots, TrustRootRegistry):
        blockers.append("WRITER_TRUST_ROOT_REGISTRY_INVALID")
    elif not blockers:
        try:
            entry, key_problem = writer_trust_roots.verify_key_available(
                key_id,
                key_version,
                now_ts,
            )
        except Exception:
            blockers.append("WRITER_TRUST_ROOT_VERIFICATION_FAILURE")
        else:
            if key_problem:
                blockers.append(f"WRITER_{key_problem}")

    blockers = list(dict.fromkeys(blockers))
    if blockers or entry is None:
        return {
            "schema": SCHEMA,
            "state": "BLOCKED",
            "blockers": blockers
            or ["CHECKPOINT_WRITER_PRECONDITION_FAILED"],
            "request": {},
            "request_digest": "",
            "digest_to_sign": "",
            **{
                key: value
                for key, value in _blocked().items()
                if key not in {"schema", "state", "blockers"}
            },
        }

    body = {
        "schema": REQUEST_SCHEMA,
        "ceremony_id": ceremony_id,
        "purpose": PURPOSE,
        "signature_mechanism": MECHANISM,
        "receipt_digest": receipt["receipt_digest"],
        "storage_target": receipt["storage_target"],
        "namespace": receipt["namespace"],
        "event_id": receipt["event_id"],
        "pilot_id": receipt["pilot_id"],
        "after_checkpoint_digest": receipt["after_checkpoint_digest"],
        "decision_record_digest": receipt["decision_record_digest"],
        "writer_ref": receipt["writer_ref"],
        "issued_at": issued_at,
        "expires_at": expires_at,
        "nonce": nonce,
        "key_id": key_id,
        "key_version": key_version,
        "writer_public_key_fingerprint": _public_key_fingerprint(entry),
        "writer_identity_verified": False,
        "pilot_activation_authorized": False,
        "pilot_activated": False,
        "external_action_executed": False,
    }
    request_digest = _digest(body)
    return {
        "schema": SCHEMA,
        "state": "READY_FOR_EXTERNAL_CHECKPOINT_WRITER_SIGNATURE",
        "blockers": [],
        "request": body,
        "request_digest": request_digest,
        "digest_to_sign": request_digest,
        "writer_identity_verified": False,
        "writer_authority_verified": False,
        "receipt_binding_verified": False,
        "pilot_activation_authorized": False,
        "pilot_activated": False,
        "checkpoint_write_performed": False,
        "external_action_executed": False,
        "network_called": False,
        "executes_action": False,
    }


def _nonce_scope(request: Mapping[str, Any], request_digest: str) -> str:
    material = "|".join(
        (
            "B2B_PILOT_CHECKPOINT_WRITER",
            _text(request.get("pilot_id"), 120),
            _text(request.get("receipt_digest"), 180),
            request_digest,
            _text(request.get("key_id"), 128),
            str(request.get("key_version")),
        )
    )
    if len(material) > 256:
        return "B2B_WRITER|" + hashlib.sha256(
            material.encode("utf-8")
        ).hexdigest()
    return material


def verify_checkpoint_writer_attestation(
    request: Mapping[str, Any] | None,
    *,
    writer_signature_b64: str,
    checkpoint_write_receipt: Mapping[str, Any] | None,
    writer_trust_roots: TrustRootRegistry,
    nonce_registry: PersistentNonceRegistry,
    now_ts: str,
) -> dict[str, Any]:
    """Verify writer key control and exact receipt binding, no write/activation."""
    if not isinstance(request, Mapping):
        return _blocked("CHECKPOINT_WRITER_REQUEST_REQUIRED")
    if not isinstance(writer_trust_roots, TrustRootRegistry):
        return _blocked("WRITER_TRUST_ROOT_REGISTRY_INVALID")
    if not isinstance(nonce_registry, PersistentNonceRegistry):
        return _blocked("CHECKPOINT_WRITER_NONCE_REGISTRY_INVALID")

    presented = dict(request)
    required = {
        "schema",
        "ceremony_id",
        "purpose",
        "signature_mechanism",
        "receipt_digest",
        "storage_target",
        "namespace",
        "event_id",
        "pilot_id",
        "after_checkpoint_digest",
        "decision_record_digest",
        "writer_ref",
        "issued_at",
        "expires_at",
        "nonce",
        "key_id",
        "key_version",
        "writer_public_key_fingerprint",
        "writer_identity_verified",
        "pilot_activation_authorized",
        "pilot_activated",
        "external_action_executed",
    }
    if set(presented) != required:
        return _blocked("CHECKPOINT_WRITER_REQUEST_SHAPE_MISMATCH")

    blockers: list[str] = []
    if presented.get("schema") != REQUEST_SCHEMA:
        blockers.append("CHECKPOINT_WRITER_REQUEST_SCHEMA_INVALID")
    if presented.get("purpose") != PURPOSE:
        blockers.append("CHECKPOINT_WRITER_PURPOSE_INVALID")
    if presented.get("signature_mechanism") != MECHANISM:
        blockers.append("CHECKPOINT_WRITER_MECHANISM_INVALID")
    if presented.get("writer_identity_verified") is not False:
        blockers.append("CHECKPOINT_WRITER_PREVERIFIED_IDENTITY_UNSAFE")
    if presented.get("pilot_activation_authorized") is not False:
        blockers.append("CHECKPOINT_WRITER_ACTIVATION_UNSAFE")
    if presented.get("pilot_activated") is not False:
        blockers.append("CHECKPOINT_WRITER_ACTIVE_UNSAFE")
    if presented.get("external_action_executed") is not False:
        blockers.append("CHECKPOINT_WRITER_EXTERNAL_ACTION_UNSAFE")

    blockers.extend(
        _identity_blockers(
            ceremony_id=presented.get("ceremony_id"),
            nonce=presented.get("nonce"),
            key_id=presented.get("key_id"),
            key_version=presented.get("key_version"),
        )
    )
    blockers.extend(
        _window_blockers(
            issued_at=presented.get("issued_at"),
            expires_at=presented.get("expires_at"),
            now_ts=now_ts,
        )
    )
    if blockers:
        return _blocked(*blockers)

    rebuilt = build_checkpoint_writer_attestation_request(
        checkpoint_write_receipt=checkpoint_write_receipt,
        writer_trust_roots=writer_trust_roots,
        now_ts=now_ts,
        ceremony_id=presented["ceremony_id"],
        nonce=presented["nonce"],
        issued_at=presented["issued_at"],
        expires_at=presented["expires_at"],
        key_id=presented["key_id"],
        key_version=presented["key_version"],
    )
    if rebuilt.get("state") != "READY_FOR_EXTERNAL_CHECKPOINT_WRITER_SIGNATURE":
        result = _blocked("CHECKPOINT_WRITER_REQUEST_REBUILD_BLOCKED")
        result["blockers"] = sorted(
            set(
                result["blockers"]
                + [
                    "REBUILD:" + item
                    for item in rebuilt.get("blockers", [])
                ]
            )
        )
        return result
    if rebuilt.get("request") != presented:
        return _blocked("CHECKPOINT_WRITER_REQUEST_REBUILD_MISMATCH")

    try:
        entry, key_problem = writer_trust_roots.verify_key_available(
            presented["key_id"],
            presented["key_version"],
            now_ts,
        )
    except Exception:
        return _blocked("WRITER_TRUST_ROOT_VERIFICATION_FAILURE")
    if key_problem:
        return _blocked(f"WRITER_{key_problem}")
    if entry is None:
        return _blocked("WRITER_TRUST_KEY_UNKNOWN")
    if (
        presented.get("writer_public_key_fingerprint")
        != _public_key_fingerprint(entry)
    ):
        return _blocked(
            "CHECKPOINT_WRITER_PUBLIC_KEY_FINGERPRINT_MISMATCH"
        )

    try:
        signature = _decode_signature(writer_signature_b64)
        entry.public_key().verify(
            signature,
            canonical_writer_attestation_bytes(presented),
        )
    except (ValueError, InvalidSignature):
        return _blocked("CHECKPOINT_WRITER_SIGNATURE_INVALID")

    request_digest = rebuilt["request_digest"]
    try:
        claimed = nonce_registry.claim(
            scope=_nonce_scope(presented, request_digest),
            nonce=presented["nonce"],
            expires_at=presented["expires_at"],
            now_ts=now_ts,
        )
    except Exception:
        result = _blocked("CHECKPOINT_WRITER_NONCE_REGISTRY_FAILURE")
        result["writer_identity_verified"] = True
        result["receipt_binding_verified"] = True
        return result
    if not claimed:
        result = _blocked("CHECKPOINT_WRITER_NONCE_REPLAYED")
        result["writer_identity_verified"] = True
        result["receipt_binding_verified"] = True
        return result

    return {
        "schema": RESULT_SCHEMA,
        "state": "CHECKPOINT_WRITER_AUTHORITY_ATTESTED",
        "blockers": [],
        "pilot_id": presented["pilot_id"],
        "receipt_digest": presented["receipt_digest"],
        "after_checkpoint_digest": presented["after_checkpoint_digest"],
        "decision_record_digest": presented["decision_record_digest"],
        "event_id": presented["event_id"],
        "writer_ref": presented["writer_ref"],
        "writer_key_id": presented["key_id"],
        "writer_key_version": presented["key_version"],
        "writer_public_key_fingerprint": presented[
            "writer_public_key_fingerprint"
        ],
        "writer_request_digest": request_digest,
        "writer_identity_verified": True,
        "writer_authority_verified": True,
        "receipt_binding_verified": True,
        "nonce_registered": True,
        "pilot_activation_authorized": False,
        "pilot_activated": False,
        "checkpoint_write_performed": False,
        "customer_contact_authorized": False,
        "billing_authorized": False,
        "deploy_authorized": False,
        "production_mutation_authorized": False,
        "external_action_executed": False,
        "network_called": False,
        "executes_action": False,
    }


__all__ = [
    "SCHEMA",
    "REQUEST_SCHEMA",
    "RESULT_SCHEMA",
    "RECEIPT_SCHEMA",
    "PURPOSE",
    "MECHANISM",
    "MAX_WINDOW_SECONDS",
    "canonical_writer_attestation_bytes",
    "build_checkpoint_writer_attestation_request",
    "verify_checkpoint_writer_attestation",
]
