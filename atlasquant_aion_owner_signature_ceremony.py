"""AION V2.24 owner signature ceremony and verification.

This layer verifies explicit external owner signatures over the exact V2.23
persistence-attested state. It does not capture a signature, does not interpret
chat text as approval, does not record an owner decision, and does not freeze or
execute anything.

A verified signature proves owner control of an approved public verification
key and acknowledgement of the exact challenge. Decision recording remains a
separate layer.
"""
from __future__ import annotations

from datetime import datetime, timezone
import base64
import hashlib
import json
import re
from typing import Any, Mapping

from cryptography.exceptions import InvalidSignature

from atlasquant_aion_external_persistence_attestation import (
    SIGNING_SCHEMA as V223_SIGNING_SCHEMA,
    verify_external_checkpoint_persistence,
)
from atlasquant_aion_nonce_registry import PersistentNonceRegistry
from atlasquant_aion_trust_root import TrustRootRegistry

SCHEMA = "ATLASQUANT_AION_OWNER_SIGNATURE_CEREMONY_V1"
REQUEST_SCHEMA = "ATLASQUANT_AION_OWNER_SIGNATURE_REQUEST_V1"
RESULT_SCHEMA = "ATLASQUANT_AION_OWNER_SIGNATURE_VERIFICATION_V1"
SIGNATURE_PURPOSE = "OWNER_IDENTITY_AND_STATE_ACKNOWLEDGEMENT"
SIGNATURE_MECHANISM = "ED25519_EXTERNAL_OWNER_KEY"
EXPECTED_OWNER_ID = "HUMAN_OWNER"
EXPECTED_TENANT_ID = "atlasquant-owner"
MAX_SIGNATURE_WINDOW_SECONDS = 180
_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{7,159}$")
_NONCE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{15,255}$")
_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


def _canonical(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def canonical_owner_signature_bytes(request_body: Mapping[str, Any]) -> bytes:
    """Canonical bytes that an external owner signer must sign."""
    return _canonical(dict(request_body)).encode("utf-8")


def _digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_owner_signature_bytes(value)).hexdigest()


def _owner_public_key_fingerprint(entry: Any) -> str:
    raw = entry.public_key().public_bytes_raw()
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _parse_ts(value: Any) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError("timestamp must be RFC3339 UTC")
    try:
        return datetime.fromisoformat(value[:-1] + "+00:00").astimezone(timezone.utc)
    except Exception as exc:
        raise ValueError("invalid timestamp") from exc


def _decode_signature(value: Any) -> bytes:
    if not isinstance(value, str) or not value:
        raise ValueError("signature required")
    try:
        raw = value.encode("ascii")
        decoded = base64.urlsafe_b64decode(raw + b"=" * (-len(raw) % 4))
    except Exception as exc:
        raise ValueError("invalid signature encoding") from exc
    if len(decoded) != 64:
        raise ValueError("Ed25519 signature must be 64 bytes")
    return decoded


def _blocked(*blockers: str) -> dict[str, Any]:
    return {
        "schema": RESULT_SCHEMA,
        "state": "BLOCKED",
        "blockers": sorted(set(blockers)),
        "owner_signature_verified": False,
        "owner_identity_verified": False,
        "state_binding_verified": False,
        "nonce_registered": False,
        "owner_decision_ready": False,
        "owner_decision": "UNDECIDED",
        "core_freeze_authorized": False,
        "core_frozen": False,
        "checkpoint_saved": False,
        "merge_authorized": False,
        "deploy_authorized": False,
        "execution_allowed": False,
        "worker_armed": False,
        "external_action_executed": False,
        "signature_capture_performed": False,
        "network_called": False,
        "executes_action": False,
    }


def _request_window_blockers(
    *,
    issued_at: Any,
    expires_at: Any,
    now_ts: Any,
) -> list[str]:
    blockers: list[str] = []
    try:
        issued = _parse_ts(issued_at)
        expires = _parse_ts(expires_at)
        now = _parse_ts(now_ts)
    except ValueError:
        return ["OWNER_SIGNATURE_TIME_INVALID"]
    window = (expires - issued).total_seconds()
    if window <= 0:
        blockers.append("OWNER_SIGNATURE_WINDOW_INVALID")
    elif window > MAX_SIGNATURE_WINDOW_SECONDS:
        blockers.append("OWNER_SIGNATURE_WINDOW_TOO_LONG")
    if issued > now:
        blockers.append("OWNER_SIGNATURE_NOT_YET_VALID")
    if expires <= now:
        blockers.append("OWNER_SIGNATURE_EXPIRED")
    return blockers


def _validate_request_identity(
    *,
    ceremony_id: Any,
    nonce: Any,
    key_id: Any,
    key_version: Any,
) -> list[str]:
    blockers: list[str] = []
    if not isinstance(ceremony_id, str) or _ID_RE.fullmatch(ceremony_id) is None:
        blockers.append("OWNER_SIGNATURE_CEREMONY_ID_INVALID")
    if not isinstance(nonce, str) or _NONCE_RE.fullmatch(nonce) is None:
        blockers.append("OWNER_SIGNATURE_NONCE_INVALID")
    if (
        not isinstance(key_id, str)
        or not key_id
        or len(key_id) > 128
    ):
        blockers.append("OWNER_SIGNATURE_KEY_ID_INVALID")
    if (
        not isinstance(key_version, int)
        or isinstance(key_version, bool)
        or key_version < 1
    ):
        blockers.append("OWNER_SIGNATURE_KEY_VERSION_INVALID")
    return blockers


def build_owner_signature_request(
    *,
    checkpoint_master: Mapping[str, Any] | None,
    preflight: Mapping[str, Any] | None,
    certification_manifest: Mapping[str, Any] | None,
    certification_trust_roots: TrustRootRegistry,
    expected_target_commit_sha: str,
    runtime_result: Mapping[str, Any] | None,
    write_receipt: Mapping[str, Any] | None,
    owner_trust_roots: TrustRootRegistry,
    now_ts: str,
    ceremony_id: str,
    nonce: str,
    issued_at: str,
    expires_at: str,
    key_id: str,
    key_version: int,
) -> dict[str, Any]:
    """Rebuild V2.23 and prepare a deterministic external-signature request."""
    blockers = _validate_request_identity(
        ceremony_id=ceremony_id,
        nonce=nonce,
        key_id=key_id,
        key_version=key_version,
    )
    blockers.extend(
        _request_window_blockers(
            issued_at=issued_at,
            expires_at=expires_at,
            now_ts=now_ts,
        )
    )

    owner_entry = None
    if not isinstance(owner_trust_roots, TrustRootRegistry):
        blockers.append("OWNER_TRUST_ROOT_REGISTRY_INVALID")
    elif not blockers:
        try:
            owner_entry, key_problem = owner_trust_roots.verify_key_available(
                key_id,
                key_version,
                now_ts,
            )
        except Exception:
            blockers.append("OWNER_TRUST_ROOT_VERIFICATION_FAILURE")
        else:
            if key_problem:
                blockers.append(f"OWNER_{key_problem}")

    v223 = verify_external_checkpoint_persistence(
        checkpoint_master=checkpoint_master,
        preflight=preflight,
        certification_manifest=certification_manifest,
        certification_trust_roots=certification_trust_roots,
        expected_target_commit_sha=expected_target_commit_sha,
        runtime_result=runtime_result,
        write_receipt=write_receipt,
        now_ts=now_ts,
    )
    if v223.get("state") != "READY_FOR_OWNER_SIGNATURE_CEREMONY":
        blockers.append("V223_PERSISTENCE_ATTESTATION_NOT_READY")
        blockers.extend(
            f"V223:{item}" for item in v223.get("blockers", [])
        )
    if v223.get("signature_material_ready") is not True:
        blockers.append("V223_SIGNATURE_MATERIAL_NOT_READY")
    if not _SHA256_RE.fullmatch(str(v223.get("digest_to_sign") or "")):
        blockers.append("V223_DIGEST_TO_SIGN_INVALID")

    target = str(expected_target_commit_sha or "").strip().lower()
    if not _SHA_RE.fullmatch(target):
        blockers.append("OWNER_SIGNATURE_TARGET_SHA_INVALID")

    unique = sorted(set(blockers))
    if unique:
        return {
            "schema": SCHEMA,
            "state": "BLOCKED",
            "blockers": unique,
            "request": {},
            "request_digest": "",
            "signature_capture_performed": False,
            "owner_signature_verified": False,
            "owner_decision_ready": False,
            "owner_decision": "UNDECIDED",
            "core_freeze_authorized": False,
            "core_frozen": False,
            "execution_allowed": False,
            "worker_armed": False,
            "external_action_executed": False,
            "network_called": False,
        }

    v223_challenge = v223["signature_challenge"]
    if v223_challenge.get("schema") != V223_SIGNING_SCHEMA:
        return {
            **_blocked("V223_SIGNATURE_CHALLENGE_SCHEMA_INVALID"),
            "request": {},
            "request_digest": "",
        }

    body = {
        "schema": REQUEST_SCHEMA,
        "ceremony_id": ceremony_id,
        "owner_id": EXPECTED_OWNER_ID,
        "tenant_id": EXPECTED_TENANT_ID,
        "signature_purpose": SIGNATURE_PURPOSE,
        "signature_mechanism": SIGNATURE_MECHANISM,
        "target_commit_sha": target,
        "v223_digest_to_sign": v223["digest_to_sign"],
        "v223_runtime_sha": str(v223_challenge.get("runtime_sha") or ""),
        "v223_runtime_checkpoint_digest": str(
            v223_challenge.get("runtime_checkpoint_digest") or ""
        ),
        "v223_runtime_binding_digest": str(
            v223_challenge.get("runtime_binding_digest") or ""
        ),
        "v222_preflight_challenge_digest": str(
            v223_challenge.get("v222_preflight_challenge_digest") or ""
        ),
        "issued_at": issued_at,
        "expires_at": expires_at,
        "nonce": nonce,
        "key_id": key_id,
        "key_version": key_version,
        "owner_public_key_fingerprint": _owner_public_key_fingerprint(owner_entry),
        "owner_decision": "UNDECIDED",
        "core_freeze_authorized": False,
        "core_frozen": False,
        "execution_allowed": False,
        "worker_armed": False,
        "external_action_executed": False,
    }
    request_digest = _digest(body)
    return {
        "schema": SCHEMA,
        "state": "READY_FOR_EXTERNAL_OWNER_SIGNATURE",
        "blockers": [],
        "request": body,
        "request_digest": request_digest,
        "digest_to_sign": request_digest,
        "signature_capture_performed": False,
        "owner_signature_verified": False,
        "owner_decision_ready": False,
        "owner_decision": "UNDECIDED",
        "core_freeze_authorized": False,
        "core_frozen": False,
        "checkpoint_saved": False,
        "merge_authorized": False,
        "deploy_authorized": False,
        "execution_allowed": False,
        "worker_armed": False,
        "external_action_executed": False,
        "network_called": False,
        "executes_action": False,
        "v223_reverified": True,
    }


def verify_owner_signature(
    request: Mapping[str, Any] | None,
    *,
    signature_b64: str,
    owner_trust_roots: TrustRootRegistry,
    nonce_registry: PersistentNonceRegistry,
    checkpoint_master: Mapping[str, Any] | None,
    preflight: Mapping[str, Any] | None,
    certification_manifest: Mapping[str, Any] | None,
    certification_trust_roots: TrustRootRegistry,
    expected_target_commit_sha: str,
    runtime_result: Mapping[str, Any] | None,
    write_receipt: Mapping[str, Any] | None,
    now_ts: str,
) -> dict[str, Any]:
    """Verify explicit owner signature while keeping decision and freeze separate."""
    if not isinstance(request, Mapping):
        return _blocked("OWNER_SIGNATURE_REQUEST_REQUIRED")
    if not isinstance(owner_trust_roots, TrustRootRegistry):
        return _blocked("OWNER_TRUST_ROOT_REGISTRY_INVALID")
    if not isinstance(nonce_registry, PersistentNonceRegistry):
        return _blocked("OWNER_NONCE_REGISTRY_INVALID")

    presented = dict(request)
    if set(presented) != {
        "schema",
        "ceremony_id",
        "owner_id",
        "tenant_id",
        "signature_purpose",
        "signature_mechanism",
        "target_commit_sha",
        "v223_digest_to_sign",
        "v223_runtime_sha",
        "v223_runtime_checkpoint_digest",
        "v223_runtime_binding_digest",
        "v222_preflight_challenge_digest",
        "issued_at",
        "expires_at",
        "nonce",
        "key_id",
        "key_version",
        "owner_public_key_fingerprint",
        "owner_decision",
        "core_freeze_authorized",
        "core_frozen",
        "execution_allowed",
        "worker_armed",
        "external_action_executed",
    }:
        return _blocked("OWNER_SIGNATURE_REQUEST_SHAPE_MISMATCH")

    blockers: list[str] = []
    if presented.get("schema") != REQUEST_SCHEMA:
        blockers.append("OWNER_SIGNATURE_REQUEST_SCHEMA_INVALID")
    if presented.get("owner_id") != EXPECTED_OWNER_ID:
        blockers.append("OWNER_SIGNATURE_OWNER_ID_MISMATCH")
    if presented.get("tenant_id") != EXPECTED_TENANT_ID:
        blockers.append("OWNER_SIGNATURE_TENANT_ID_MISMATCH")
    if presented.get("signature_purpose") != SIGNATURE_PURPOSE:
        blockers.append("OWNER_SIGNATURE_PURPOSE_INVALID")
    if presented.get("signature_mechanism") != SIGNATURE_MECHANISM:
        blockers.append("OWNER_SIGNATURE_MECHANISM_INVALID")
    if presented.get("owner_decision") != "UNDECIDED":
        blockers.append("OWNER_DECISION_MUST_REMAIN_UNDECIDED")
    for field in (
        "core_freeze_authorized",
        "core_frozen",
        "execution_allowed",
        "worker_armed",
        "external_action_executed",
    ):
        if presented.get(field) is not False:
            blockers.append(f"OWNER_SIGNATURE_UNSAFE_FIELD:{field}")

    blockers.extend(
        _validate_request_identity(
            ceremony_id=presented.get("ceremony_id"),
            nonce=presented.get("nonce"),
            key_id=presented.get("key_id"),
            key_version=presented.get("key_version"),
        )
    )
    blockers.extend(
        _request_window_blockers(
            issued_at=presented.get("issued_at"),
            expires_at=presented.get("expires_at"),
            now_ts=now_ts,
        )
    )

    if blockers:
        return _blocked(*blockers)

    rebuilt = build_owner_signature_request(
        checkpoint_master=checkpoint_master,
        preflight=preflight,
        certification_manifest=certification_manifest,
        certification_trust_roots=certification_trust_roots,
        expected_target_commit_sha=expected_target_commit_sha,
        runtime_result=runtime_result,
        write_receipt=write_receipt,
        owner_trust_roots=owner_trust_roots,
        now_ts=now_ts,
        ceremony_id=presented["ceremony_id"],
        nonce=presented["nonce"],
        issued_at=presented["issued_at"],
        expires_at=presented["expires_at"],
        key_id=presented["key_id"],
        key_version=presented["key_version"],
    )
    if rebuilt.get("state") != "READY_FOR_EXTERNAL_OWNER_SIGNATURE":
        result = _blocked("OWNER_SIGNATURE_REQUEST_REBUILD_BLOCKED")
        result["blockers"] = sorted(set(
            result["blockers"]
            + [f"REBUILD:{item}" for item in rebuilt.get("blockers", [])]
        ))
        return result
    if rebuilt.get("request") != presented:
        return _blocked("OWNER_SIGNATURE_REQUEST_REBUILD_MISMATCH")

    try:
        entry, key_problem = owner_trust_roots.verify_key_available(
            presented["key_id"],
            presented["key_version"],
            now_ts,
        )
    except Exception:
        return _blocked("OWNER_TRUST_ROOT_VERIFICATION_FAILURE")
    if key_problem:
        return _blocked(f"OWNER_{key_problem}")
    if entry is None:
        return _blocked("OWNER_TRUST_KEY_UNKNOWN")
    if presented.get("owner_public_key_fingerprint") != _owner_public_key_fingerprint(entry):
        return _blocked("OWNER_PUBLIC_KEY_FINGERPRINT_MISMATCH")

    signature_verified = False
    try:
        signature = _decode_signature(signature_b64)
        entry.public_key().verify(
            signature,
            canonical_owner_signature_bytes(presented),
        )
        signature_verified = True
    except (ValueError, InvalidSignature):
        return _blocked("OWNER_SIGNATURE_INVALID")

    scope = "|".join((
        "OWNER_SIGNATURE",
        EXPECTED_OWNER_ID,
        EXPECTED_TENANT_ID,
        presented["key_id"],
        str(presented["key_version"]),
    ))
    try:
        claimed = nonce_registry.claim(
            scope=scope,
            nonce=presented["nonce"],
            expires_at=presented["expires_at"],
            now_ts=now_ts,
        )
    except Exception:
        result = _blocked("OWNER_SIGNATURE_NONCE_REGISTRY_FAILURE")
        result["owner_signature_verified"] = signature_verified
        result["owner_identity_verified"] = signature_verified
        result["state_binding_verified"] = signature_verified
        return result
    if not claimed:
        result = _blocked("OWNER_SIGNATURE_NONCE_REPLAYED")
        result["owner_signature_verified"] = True
        result["owner_identity_verified"] = True
        result["state_binding_verified"] = True
        return result

    return {
        "schema": RESULT_SCHEMA,
        "state": "READY_FOR_EXPLICIT_OWNER_DECISION",
        "blockers": [],
        "owner_signature_verified": True,
        "owner_identity_verified": True,
        "state_binding_verified": True,
        "nonce_registered": True,
        "owner_key_id": presented["key_id"],
        "owner_key_version": presented["key_version"],
        "request_digest": rebuilt["request_digest"],
        "v223_digest_to_sign": presented["v223_digest_to_sign"],
        "owner_decision_ready": True,
        "owner_decision": "UNDECIDED",
        "signature_active": True,
        "signature_capture_performed": False,
        "signature_performed_by_this_module": False,
        "core_freeze_authorized": False,
        "core_frozen": False,
        "checkpoint_saved": False,
        "merge_authorized": False,
        "deploy_authorized": False,
        "execution_allowed": False,
        "worker_armed": False,
        "external_action_executed": False,
        "network_called": False,
        "executes_action": False,
        "approval_implied": False,
        "generic_chat_instruction_accepted_as_signature": False,
    }


__all__ = [
    "SCHEMA",
    "REQUEST_SCHEMA",
    "RESULT_SCHEMA",
    "SIGNATURE_PURPOSE",
    "SIGNATURE_MECHANISM",
    "EXPECTED_OWNER_ID",
    "EXPECTED_TENANT_ID",
    "MAX_SIGNATURE_WINDOW_SECONDS",
    "canonical_owner_signature_bytes",
    "build_owner_signature_request",
    "verify_owner_signature",
]
