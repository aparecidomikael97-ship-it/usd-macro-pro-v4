"""AION V2.25 explicit owner decision record.

This layer records an explicit HUMAN_OWNER APPROVE/DENY choice only after:
1. rebuilding the current V2.24 owner-signature request;
2. cryptographically verifying the V2.24 identity/state signature; and
3. verifying a second external signature over the decision itself.

Decision recording remains separate from Core Freeze execution. Even an
APPROVE_CORE_FREEZE decision never freezes the Core, never merges/deploys, never
arms the worker and never performs an external action.
"""
from __future__ import annotations

import base64
import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Any, Mapping

from cryptography.exceptions import InvalidSignature

from atlasquant_aion_checkpoint_master import reconstruct_checkpoint
from atlasquant_aion_nonce_registry import PersistentNonceRegistry
from atlasquant_aion_owner_signature_ceremony import (
    EXPECTED_OWNER_ID,
    EXPECTED_TENANT_ID,
    REQUEST_SCHEMA as V224_REQUEST_SCHEMA,
    SIGNATURE_PURPOSE as V224_SIGNATURE_PURPOSE,
    build_owner_signature_request,
    canonical_owner_signature_bytes,
)
from atlasquant_aion_trust_root import TrustRootRegistry

SCHEMA = "ATLASQUANT_AION_OWNER_DECISION_RECORD_V1"
REQUEST_SCHEMA = "ATLASQUANT_AION_OWNER_DECISION_REQUEST_V1"
RESULT_SCHEMA = "ATLASQUANT_AION_OWNER_DECISION_VERIFICATION_V1"
DECISION_PURPOSE = "CORE_FREEZE_EXPLICIT_OWNER_DECISION"
DECISION_SIGNATURE_MECHANISM = "ED25519_EXTERNAL_OWNER_KEY"
DECISIONS = ("APPROVE_CORE_FREEZE", "DENY_CORE_FREEZE")
MAX_DECISION_WINDOW_SECONDS = 180
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
    )


def canonical_owner_decision_bytes(request_body: Mapping[str, Any]) -> bytes:
    return _canonical(dict(request_body)).encode("utf-8")


def _digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_owner_decision_bytes(value)).hexdigest()


def _signature_digest(signature_b64: str) -> str:
    raw = _decode_signature(signature_b64)
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _public_key_fingerprint(entry: Any) -> str:
    encoded = str(entry.public_key_b64 or "").encode("ascii")
    raw = base64.urlsafe_b64decode(encoded + b"=" * (-len(encoded) % 4))
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


def _window_blockers(*, issued_at: Any, expires_at: Any, now_ts: Any) -> list[str]:
    blockers: list[str] = []
    try:
        issued = _parse_ts(issued_at)
        expires = _parse_ts(expires_at)
        now = _parse_ts(now_ts)
    except ValueError:
        return ["OWNER_DECISION_TIME_INVALID"]
    window = (expires - issued).total_seconds()
    if window <= 0:
        blockers.append("OWNER_DECISION_WINDOW_INVALID")
    elif window > MAX_DECISION_WINDOW_SECONDS:
        blockers.append("OWNER_DECISION_WINDOW_TOO_LONG")
    if issued > now:
        blockers.append("OWNER_DECISION_NOT_YET_VALID")
    if expires <= now:
        blockers.append("OWNER_DECISION_EXPIRED")
    return blockers


def _identity_blockers(
    *,
    ceremony_id: Any,
    nonce: Any,
    key_id: Any,
    key_version: Any,
    decision: Any,
) -> list[str]:
    blockers: list[str] = []
    if not isinstance(ceremony_id, str) or _ID_RE.fullmatch(ceremony_id) is None:
        blockers.append("OWNER_DECISION_CEREMONY_ID_INVALID")
    if not isinstance(nonce, str) or _NONCE_RE.fullmatch(nonce) is None:
        blockers.append("OWNER_DECISION_NONCE_INVALID")
    if not isinstance(key_id, str) or not key_id or len(key_id) > 128:
        blockers.append("OWNER_DECISION_KEY_ID_INVALID")
    if (
        not isinstance(key_version, int)
        or isinstance(key_version, bool)
        or key_version < 1
    ):
        blockers.append("OWNER_DECISION_KEY_VERSION_INVALID")
    if decision not in DECISIONS:
        blockers.append("OWNER_DECISION_CHOICE_INVALID")
    return blockers


def _blocked(*blockers: str) -> dict[str, Any]:
    return {
        "schema": RESULT_SCHEMA,
        "state": "BLOCKED",
        "blockers": sorted(set(blockers)),
        "owner_identity_signature_verified": False,
        "owner_decision_signature_verified": False,
        "owner_decision_recorded": False,
        "owner_decision": "UNDECIDED",
        "core_freeze_approved": False,
        "core_freeze_denied": False,
        "core_freeze_execution_authorized": False,
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
    }


def _verify_v224_identity_signature(
    v224_request: Mapping[str, Any] | None,
    *,
    v224_signature_b64: str,
    owner_trust_roots: TrustRootRegistry,
    checkpoint_master: Mapping[str, Any] | None,
    preflight: Mapping[str, Any] | None,
    certification_manifest: Mapping[str, Any] | None,
    certification_trust_roots: TrustRootRegistry,
    expected_target_commit_sha: str,
    runtime_result: Mapping[str, Any] | None,
    write_receipt: Mapping[str, Any] | None,
    now_ts: str,
) -> tuple[dict[str, Any] | None, list[str]]:
    blockers: list[str] = []
    if not isinstance(v224_request, Mapping):
        return None, ["V224_OWNER_SIGNATURE_REQUEST_REQUIRED"]
    if not isinstance(owner_trust_roots, TrustRootRegistry):
        return None, ["OWNER_TRUST_ROOT_REGISTRY_INVALID"]

    presented = dict(v224_request)
    if presented.get("schema") != V224_REQUEST_SCHEMA:
        blockers.append("V224_OWNER_SIGNATURE_REQUEST_SCHEMA_INVALID")
    if presented.get("owner_id") != EXPECTED_OWNER_ID:
        blockers.append("V224_OWNER_ID_MISMATCH")
    if presented.get("tenant_id") != EXPECTED_TENANT_ID:
        blockers.append("V224_TENANT_ID_MISMATCH")
    if presented.get("signature_purpose") != V224_SIGNATURE_PURPOSE:
        blockers.append("V224_SIGNATURE_PURPOSE_INVALID")
    if presented.get("owner_decision") != "UNDECIDED":
        blockers.append("V224_OWNER_DECISION_NOT_UNDECIDED")
    if blockers:
        return None, blockers

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
        ceremony_id=presented.get("ceremony_id"),
        nonce=presented.get("nonce"),
        issued_at=presented.get("issued_at"),
        expires_at=presented.get("expires_at"),
        key_id=presented.get("key_id"),
        key_version=presented.get("key_version"),
    )
    if rebuilt.get("state") != "READY_FOR_EXTERNAL_OWNER_SIGNATURE":
        blockers.append("V224_OWNER_SIGNATURE_REQUEST_REBUILD_BLOCKED")
        blockers.extend(f"V224:{item}" for item in rebuilt.get("blockers", []))
        return None, blockers
    if rebuilt.get("request") != presented:
        return None, ["V224_OWNER_SIGNATURE_REQUEST_REBUILD_MISMATCH"]

    try:
        entry, key_problem = owner_trust_roots.verify_key_available(
            presented["key_id"],
            presented["key_version"],
            now_ts,
        )
    except Exception:
        return None, ["OWNER_TRUST_ROOT_VERIFICATION_FAILURE"]
    if key_problem:
        return None, [f"OWNER_{key_problem}"]
    if entry is None:
        return None, ["OWNER_TRUST_KEY_UNKNOWN"]
    if presented.get("owner_public_key_fingerprint") != _public_key_fingerprint(entry):
        return None, ["V224_OWNER_PUBLIC_KEY_FINGERPRINT_MISMATCH"]

    try:
        signature = _decode_signature(v224_signature_b64)
        entry.public_key().verify(
            signature,
            canonical_owner_signature_bytes(presented),
        )
    except (ValueError, InvalidSignature):
        return None, ["V224_OWNER_SIGNATURE_INVALID"]

    return {
        "request": presented,
        "request_digest": rebuilt["request_digest"],
        "signature_digest": _signature_digest(v224_signature_b64),
        "owner_key_id": presented["key_id"],
        "owner_key_version": presented["key_version"],
        "owner_public_key_fingerprint": presented["owner_public_key_fingerprint"],
        "v223_digest_to_sign": presented["v223_digest_to_sign"],
    }, []


def build_owner_decision_request(
    *,
    v224_request: Mapping[str, Any] | None,
    v224_signature_b64: str,
    owner_trust_roots: TrustRootRegistry,
    checkpoint_master: Mapping[str, Any] | None,
    preflight: Mapping[str, Any] | None,
    certification_manifest: Mapping[str, Any] | None,
    certification_trust_roots: TrustRootRegistry,
    expected_target_commit_sha: str,
    runtime_result: Mapping[str, Any] | None,
    write_receipt: Mapping[str, Any] | None,
    now_ts: str,
    decision: str,
    ceremony_id: str,
    nonce: str,
    issued_at: str,
    expires_at: str,
    key_id: str,
    key_version: int,
) -> dict[str, Any]:
    """Prepare a decision-specific request only after V2.24 identity verification."""
    blockers = _identity_blockers(
        ceremony_id=ceremony_id,
        nonce=nonce,
        key_id=key_id,
        key_version=key_version,
        decision=decision,
    )
    blockers.extend(
        _window_blockers(
            issued_at=issued_at,
            expires_at=expires_at,
            now_ts=now_ts,
        )
    )

    identity, identity_blockers = _verify_v224_identity_signature(
        v224_request,
        v224_signature_b64=v224_signature_b64,
        owner_trust_roots=owner_trust_roots,
        checkpoint_master=checkpoint_master,
        preflight=preflight,
        certification_manifest=certification_manifest,
        certification_trust_roots=certification_trust_roots,
        expected_target_commit_sha=expected_target_commit_sha,
        runtime_result=runtime_result,
        write_receipt=write_receipt,
        now_ts=now_ts,
    )
    blockers.extend(identity_blockers)

    decision_entry = None
    if isinstance(owner_trust_roots, TrustRootRegistry) and not blockers:
        try:
            decision_entry, key_problem = owner_trust_roots.verify_key_available(
                key_id,
                key_version,
                now_ts,
            )
        except Exception:
            blockers.append("OWNER_TRUST_ROOT_VERIFICATION_FAILURE")
        else:
            if key_problem:
                blockers.append(f"OWNER_{key_problem}")

    unique = sorted(set(blockers))
    if unique or identity is None or decision_entry is None:
        return {
            "schema": SCHEMA,
            "state": "BLOCKED",
            "blockers": unique or ["OWNER_DECISION_PRECONDITION_FAILED"],
            "request": {},
            "request_digest": "",
            "digest_to_sign": "",
            "owner_identity_signature_verified": False,
            "owner_decision_signature_verified": False,
            "owner_decision_recorded": False,
            "owner_decision": "UNDECIDED",
            "core_freeze_execution_authorized": False,
            "core_frozen": False,
            "execution_allowed": False,
            "worker_armed": False,
            "external_action_executed": False,
        }

    body = {
        "schema": REQUEST_SCHEMA,
        "ceremony_id": ceremony_id,
        "owner_id": EXPECTED_OWNER_ID,
        "tenant_id": EXPECTED_TENANT_ID,
        "decision_purpose": DECISION_PURPOSE,
        "decision_signature_mechanism": DECISION_SIGNATURE_MECHANISM,
        "decision": decision,
        "target_commit_sha": str(expected_target_commit_sha).strip().lower(),
        "v224_request_digest": identity["request_digest"],
        "v224_signature_digest": identity["signature_digest"],
        "v223_digest_to_sign": identity["v223_digest_to_sign"],
        "identity_key_id": identity["owner_key_id"],
        "identity_key_version": identity["owner_key_version"],
        "identity_public_key_fingerprint": identity["owner_public_key_fingerprint"],
        "decision_key_id": key_id,
        "decision_key_version": key_version,
        "decision_public_key_fingerprint": _public_key_fingerprint(decision_entry),
        "issued_at": issued_at,
        "expires_at": expires_at,
        "nonce": nonce,
        "owner_decision_recorded": False,
        "core_freeze_execution_authorized": False,
        "core_freeze_authorized": False,
        "core_frozen": False,
        "merge_authorized": False,
        "deploy_authorized": False,
        "execution_allowed": False,
        "worker_armed": False,
        "external_action_executed": False,
    }
    request_digest = _digest(body)
    return {
        "schema": SCHEMA,
        "state": "READY_FOR_EXTERNAL_OWNER_DECISION_SIGNATURE",
        "blockers": [],
        "request": body,
        "request_digest": request_digest,
        "digest_to_sign": request_digest,
        "owner_identity_signature_verified": True,
        "owner_decision_signature_verified": False,
        "owner_decision_recorded": False,
        "owner_decision": "UNDECIDED",
        "core_freeze_execution_authorized": False,
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
    }


def _checkpoint_patch_candidate(
    verified_decision: Mapping[str, Any],
    *,
    checkpoint_master: Mapping[str, Any],
) -> dict[str, Any]:
    current = reconstruct_checkpoint(checkpoint_master)
    record = {
        "schema": RESULT_SCHEMA,
        "state": verified_decision["state"],
        "owner_decision_recorded": True,
        "owner_decision": verified_decision["owner_decision"],
        "decision_request_digest": verified_decision["decision_request_digest"],
        "decision_signature_digest": verified_decision["decision_signature_digest"],
        "core_freeze_approved": verified_decision["core_freeze_approved"],
        "core_freeze_denied": verified_decision["core_freeze_denied"],
        "core_freeze_execution_authorized": False,
        "core_freeze_authorized": False,
        "core_frozen": False,
        "execution_allowed": False,
        "worker_armed": False,
        "external_action_executed": False,
    }
    event_id = "aion-core-owner-decision-" + hashlib.sha256(
        canonical_owner_decision_bytes(record)
    ).hexdigest()[:32]
    return {
        "schema": "ATLASQUANT_AION_OWNER_DECISION_CHECKPOINT_PATCH_V1",
        "state": "PATCH_CANDIDATE",
        "expected_revision": current["revision"],
        "recommended_event_id": event_id,
        "patch": {"aion_core_owner_decision": record},
        "patch_digest": _digest({"aion_core_owner_decision": record}),
        "requires_explicit_checkpoint_save": True,
        "automatic_checkpoint_write": False,
        "checkpoint_saved": False,
        "core_freeze_execution_authorized": False,
        "core_frozen": False,
        "execution_allowed": False,
        "external_action_executed": False,
    }


def verify_owner_decision(
    request: Mapping[str, Any] | None,
    *,
    decision_signature_b64: str,
    v224_request: Mapping[str, Any] | None,
    v224_signature_b64: str,
    owner_trust_roots: TrustRootRegistry,
    decision_nonce_registry: PersistentNonceRegistry,
    checkpoint_master: Mapping[str, Any] | None,
    preflight: Mapping[str, Any] | None,
    certification_manifest: Mapping[str, Any] | None,
    certification_trust_roots: TrustRootRegistry,
    expected_target_commit_sha: str,
    runtime_result: Mapping[str, Any] | None,
    write_receipt: Mapping[str, Any] | None,
    now_ts: str,
) -> dict[str, Any]:
    """Verify the decision-specific signature and record only the decision."""
    if not isinstance(request, Mapping):
        return _blocked("OWNER_DECISION_REQUEST_REQUIRED")
    if not isinstance(owner_trust_roots, TrustRootRegistry):
        return _blocked("OWNER_TRUST_ROOT_REGISTRY_INVALID")
    if not isinstance(decision_nonce_registry, PersistentNonceRegistry):
        return _blocked("OWNER_DECISION_NONCE_REGISTRY_INVALID")

    presented = dict(request)
    expected_fields = {
        "schema",
        "ceremony_id",
        "owner_id",
        "tenant_id",
        "decision_purpose",
        "decision_signature_mechanism",
        "decision",
        "target_commit_sha",
        "v224_request_digest",
        "v224_signature_digest",
        "v223_digest_to_sign",
        "identity_key_id",
        "identity_key_version",
        "identity_public_key_fingerprint",
        "decision_key_id",
        "decision_key_version",
        "decision_public_key_fingerprint",
        "issued_at",
        "expires_at",
        "nonce",
        "owner_decision_recorded",
        "core_freeze_execution_authorized",
        "core_freeze_authorized",
        "core_frozen",
        "merge_authorized",
        "deploy_authorized",
        "execution_allowed",
        "worker_armed",
        "external_action_executed",
    }
    if set(presented) != expected_fields:
        return _blocked("OWNER_DECISION_REQUEST_SHAPE_MISMATCH")

    blockers: list[str] = []
    if presented.get("schema") != REQUEST_SCHEMA:
        blockers.append("OWNER_DECISION_REQUEST_SCHEMA_INVALID")
    if presented.get("owner_id") != EXPECTED_OWNER_ID:
        blockers.append("OWNER_DECISION_OWNER_ID_MISMATCH")
    if presented.get("tenant_id") != EXPECTED_TENANT_ID:
        blockers.append("OWNER_DECISION_TENANT_ID_MISMATCH")
    if presented.get("decision_purpose") != DECISION_PURPOSE:
        blockers.append("OWNER_DECISION_PURPOSE_INVALID")
    if presented.get("decision_signature_mechanism") != DECISION_SIGNATURE_MECHANISM:
        blockers.append("OWNER_DECISION_SIGNATURE_MECHANISM_INVALID")
    blockers.extend(
        _identity_blockers(
            ceremony_id=presented.get("ceremony_id"),
            nonce=presented.get("nonce"),
            key_id=presented.get("decision_key_id"),
            key_version=presented.get("decision_key_version"),
            decision=presented.get("decision"),
        )
    )
    blockers.extend(
        _window_blockers(
            issued_at=presented.get("issued_at"),
            expires_at=presented.get("expires_at"),
            now_ts=now_ts,
        )
    )
    for field in (
        "owner_decision_recorded",
        "core_freeze_execution_authorized",
        "core_freeze_authorized",
        "core_frozen",
        "merge_authorized",
        "deploy_authorized",
        "execution_allowed",
        "worker_armed",
        "external_action_executed",
    ):
        if presented.get(field) is not False:
            blockers.append(f"OWNER_DECISION_UNSAFE_FIELD:{field}")

    if blockers:
        return _blocked(*blockers)

    rebuilt = build_owner_decision_request(
        v224_request=v224_request,
        v224_signature_b64=v224_signature_b64,
        owner_trust_roots=owner_trust_roots,
        checkpoint_master=checkpoint_master,
        preflight=preflight,
        certification_manifest=certification_manifest,
        certification_trust_roots=certification_trust_roots,
        expected_target_commit_sha=expected_target_commit_sha,
        runtime_result=runtime_result,
        write_receipt=write_receipt,
        now_ts=now_ts,
        decision=presented["decision"],
        ceremony_id=presented["ceremony_id"],
        nonce=presented["nonce"],
        issued_at=presented["issued_at"],
        expires_at=presented["expires_at"],
        key_id=presented["decision_key_id"],
        key_version=presented["decision_key_version"],
    )
    if rebuilt.get("state") != "READY_FOR_EXTERNAL_OWNER_DECISION_SIGNATURE":
        result = _blocked("OWNER_DECISION_REQUEST_REBUILD_BLOCKED")
        result["blockers"] = sorted(set(
            result["blockers"]
            + [f"REBUILD:{item}" for item in rebuilt.get("blockers", [])]
        ))
        return result
    if rebuilt.get("request") != presented:
        return _blocked("OWNER_DECISION_REQUEST_REBUILD_MISMATCH")

    try:
        entry, key_problem = owner_trust_roots.verify_key_available(
            presented["decision_key_id"],
            presented["decision_key_version"],
            now_ts,
        )
    except Exception:
        return _blocked("OWNER_TRUST_ROOT_VERIFICATION_FAILURE")
    if key_problem:
        return _blocked(f"OWNER_{key_problem}")
    if entry is None:
        return _blocked("OWNER_TRUST_KEY_UNKNOWN")
    if (
        presented.get("decision_public_key_fingerprint")
        != _public_key_fingerprint(entry)
    ):
        return _blocked("OWNER_DECISION_PUBLIC_KEY_FINGERPRINT_MISMATCH")

    try:
        signature = _decode_signature(decision_signature_b64)
        entry.public_key().verify(
            signature,
            canonical_owner_decision_bytes(presented),
        )
    except (ValueError, InvalidSignature):
        return _blocked("OWNER_DECISION_SIGNATURE_INVALID")

    scope = "|".join((
        "OWNER_DECISION",
        EXPECTED_OWNER_ID,
        EXPECTED_TENANT_ID,
        presented["target_commit_sha"],
        presented["v224_request_digest"],
        presented["decision_key_id"],
        str(presented["decision_key_version"]),
    ))
    try:
        claimed = decision_nonce_registry.claim(
            scope=scope,
            nonce=presented["nonce"],
            expires_at=presented["expires_at"],
            now_ts=now_ts,
        )
    except Exception:
        result = _blocked("OWNER_DECISION_NONCE_REGISTRY_FAILURE")
        result["owner_identity_signature_verified"] = True
        result["owner_decision_signature_verified"] = True
        return result
    if not claimed:
        result = _blocked("OWNER_DECISION_NONCE_REPLAYED")
        result["owner_identity_signature_verified"] = True
        result["owner_decision_signature_verified"] = True
        return result

    decision = presented["decision"]
    approved = decision == "APPROVE_CORE_FREEZE"
    denied = decision == "DENY_CORE_FREEZE"
    result = {
        "schema": RESULT_SCHEMA,
        "state": (
            "OWNER_DECISION_RECORDED_APPROVE"
            if approved
            else "OWNER_DECISION_RECORDED_DENY"
        ),
        "blockers": [],
        "owner_identity_signature_verified": True,
        "owner_decision_signature_verified": True,
        "owner_decision_recorded": True,
        "owner_decision": decision,
        "decision_request_digest": rebuilt["request_digest"],
        "decision_signature_digest": _signature_digest(decision_signature_b64),
        "decision_nonce_registered": True,
        "core_freeze_approved": approved,
        "core_freeze_denied": denied,
        "core_freeze_execution_authorized": False,
        "core_freeze_authorized": False,
        "core_frozen": False,
        "requires_separate_core_freeze_ceremony": approved,
        "checkpoint_saved": False,
        "merge_authorized": False,
        "deploy_authorized": False,
        "execution_allowed": False,
        "worker_armed": False,
        "external_action_executed": False,
        "network_called": False,
        "executes_action": False,
        "generic_chat_instruction_accepted_as_decision": False,
        "decision_signature_performed_by_this_module": False,
    }
    result["checkpoint_patch_candidate"] = _checkpoint_patch_candidate(
        result,
        checkpoint_master=checkpoint_master,
    )
    return result


__all__ = [
    "SCHEMA",
    "REQUEST_SCHEMA",
    "RESULT_SCHEMA",
    "DECISION_PURPOSE",
    "DECISION_SIGNATURE_MECHANISM",
    "DECISIONS",
    "MAX_DECISION_WINDOW_SECONDS",
    "canonical_owner_decision_bytes",
    "build_owner_decision_request",
    "verify_owner_decision",
]
