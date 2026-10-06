"""OPS-only AION Core V1 freeze ceremony contract.

This module is administrative closure tooling, not Core intelligence.
It never loads private keys, never writes runtime state, and never authorizes
merge, deploy, or Global Worker activation.
"""
from __future__ import annotations

import base64
import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Any, Mapping

from cryptography.exceptions import InvalidSignature

from atlasquant_aion_trust_root import TrustRootRegistry

TARGET = "662eab4dc4f5bb009fa1ca89f87530df74d30ddf"
REQUEST_SCHEMA = "AION_CORE_V1_CORE_FREEZE_EXECUTION_REQUEST_V1"
FREEZE_RECORD_SCHEMA = "ATLASQUANT_AION_CORE_FREEZE_RECORD_V1"
FREEZE_RESULT_SCHEMA = "ATLASQUANT_AION_CORE_FREEZE_PERSISTENCE_ATTESTATION_V1"
NAMESPACE = "aion_core_freeze_v1"
EXPECTED_OWNER_ID = "HUMAN_OWNER"
EXPECTED_TENANT_ID = "atlasquant-owner"
PURPOSE = "AION_CORE_V1_FREEZE_EXECUTION"
MECHANISM = "EXTERNAL_ED25519_OWNER_SIGNATURE"
MAX_WINDOW_SECONDS = 180
_SAFE_ID = re.compile(r"^[A-Za-z0-9._:-]{8,160}$")
_SAFE_NONCE = re.compile(r"^[A-Za-z0-9._:-]{16,256}$")
_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_SHA256 = re.compile(r"^sha256:[0-9a-f]{64}$")


def canonical(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical(value)).hexdigest()


def signature_digest(signature_b64: str) -> str:
    raw = decode_signature(signature_b64)
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def decode_signature(value: str) -> bytes:
    if not isinstance(value, str) or not value:
        raise ValueError("signature required")
    try:
        raw = base64.urlsafe_b64decode((value + "=" * ((4 - len(value) % 4) % 4)).encode("ascii"))
    except Exception as exc:
        raise ValueError("invalid signature encoding") from exc
    if len(raw) != 64:
        raise ValueError("Ed25519 signature must be 64 bytes")
    return raw


def parse_ts(value: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise ValueError("timestamp required")
    raw = value[:-1] + "+00:00" if value.endswith("Z") else value
    parsed = datetime.fromisoformat(raw)
    if parsed.tzinfo is None:
        raise ValueError("timezone required")
    return parsed.astimezone(timezone.utc)


def public_key_fingerprint(public_key_b64: str) -> str:
    raw = base64.urlsafe_b64decode((public_key_b64 + "=" * ((4 - len(public_key_b64) % 4) % 4)).encode("ascii"))
    if len(raw) != 32:
        raise ValueError("Ed25519 public key must be 32 bytes")
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def validate_v226_approve(v226: Mapping[str, Any] | None) -> tuple[dict[str, Any] | None, list[str]]:
    blockers: list[str] = []
    row = dict(v226 or {}) if isinstance(v226, Mapping) else {}
    if row.get("state") != "OWNER_DECISION_RECORD_PERSISTENCE_ATTESTED_APPROVE":
        blockers.append("V226_APPROVE_ATTESTATION_REQUIRED")
    if row.get("owner_decision") != "APPROVE_CORE_FREEZE":
        blockers.append("V226_APPROVE_DECISION_REQUIRED")
    if row.get("owner_decision_recorded") is not True:
        blockers.append("V226_OWNER_DECISION_NOT_RECORDED")
    if row.get("decision_record_persisted") is not True:
        blockers.append("V226_DECISION_RECORD_NOT_PERSISTED")
    if row.get("persistence_attested") is not True:
        blockers.append("V226_PERSISTENCE_NOT_ATTESTED")
    if row.get("core_freeze_ceremony_eligible") is not True:
        blockers.append("V226_FREEZE_NOT_ELIGIBLE")
    if row.get("core_freeze_execution_authorized") is not False:
        blockers.append("V226_FREEZE_EXECUTION_MUST_REMAIN_UNAUTHORIZED")
    if row.get("core_frozen") is not False:
        blockers.append("V226_CORE_MUST_NOT_ALREADY_BE_FROZEN")
    for field in ("merge_authorized", "deploy_authorized", "worker_armed"):
        if row.get(field) is not False:
            blockers.append(f"V226_UNSAFE_FIELD:{field}")

    material = row.get("core_freeze_ceremony_material")
    supplied = str(row.get("digest_to_core_freeze_ceremony") or "")
    if not isinstance(material, Mapping):
        blockers.append("V226_FREEZE_MATERIAL_REQUIRED")
        material = {}
    if not _SHA256.fullmatch(supplied):
        blockers.append("V226_FREEZE_DIGEST_INVALID")
    elif digest(material) != supplied:
        blockers.append("V226_FREEZE_DIGEST_MISMATCH")

    if material:
        if material.get("target_commit_sha") != TARGET:
            blockers.append("V226_TARGET_MISMATCH")
        if material.get("decision") != "APPROVE_CORE_FREEZE":
            blockers.append("V226_MATERIAL_DECISION_MISMATCH")
        if material.get("core_freeze_ceremony_eligible") is not True:
            blockers.append("V226_MATERIAL_NOT_ELIGIBLE")
        if material.get("core_freeze_execution_authorized") is not False:
            blockers.append("V226_MATERIAL_EXECUTION_ALREADY_AUTHORIZED")
        if material.get("core_frozen") is not False:
            blockers.append("V226_MATERIAL_ALREADY_FROZEN")
        if not _SHA40.fullmatch(str(material.get("decision_runtime_sha") or "")):
            blockers.append("V226_DECISION_RUNTIME_SHA_INVALID")
        if not str(material.get("decision_runtime_digest") or ""):
            blockers.append("V226_DECISION_RUNTIME_DIGEST_REQUIRED")
        if not str(material.get("decision_record_digest") or ""):
            blockers.append("V226_DECISION_RECORD_DIGEST_REQUIRED")

    unique = sorted(set(blockers))
    return (dict(material) if not unique else None), unique


def build_freeze_request(
    v226: Mapping[str, Any] | None,
    *,
    owner_trust_roots: TrustRootRegistry,
    now_ts: str,
    ceremony_id: str,
    nonce: str,
    issued_at: str,
    expires_at: str,
    key_id: str,
    key_version: int,
) -> dict[str, Any]:
    blockers: list[str] = []
    material, material_blockers = validate_v226_approve(v226)
    blockers.extend(material_blockers)

    if not isinstance(owner_trust_roots, TrustRootRegistry):
        blockers.append("OWNER_TRUST_ROOT_REGISTRY_INVALID")
    if not isinstance(ceremony_id, str) or not _SAFE_ID.fullmatch(ceremony_id):
        blockers.append("FREEZE_CEREMONY_ID_INVALID")
    if not isinstance(nonce, str) or not _SAFE_NONCE.fullmatch(nonce):
        blockers.append("FREEZE_NONCE_INVALID")
    if not isinstance(key_id, str) or not key_id or len(key_id) > 128:
        blockers.append("FREEZE_KEY_ID_INVALID")
    if isinstance(key_version, bool) or not isinstance(key_version, int) or key_version < 1:
        blockers.append("FREEZE_KEY_VERSION_INVALID")

    try:
        now = parse_ts(now_ts)
        issued = parse_ts(issued_at)
        expires = parse_ts(expires_at)
        if expires <= issued or (expires - issued).total_seconds() > MAX_WINDOW_SECONDS:
            blockers.append("FREEZE_SIGNATURE_WINDOW_INVALID")
        if now < issued or now > expires:
            blockers.append("FREEZE_SIGNATURE_WINDOW_NOT_CURRENT")
    except Exception:
        blockers.append("FREEZE_SIGNATURE_TIME_INVALID")

    entry = None
    if isinstance(owner_trust_roots, TrustRootRegistry) and not blockers:
        try:
            entry, problem = owner_trust_roots.verify_key_available(key_id, key_version, now_ts)
        except Exception:
            blockers.append("OWNER_TRUST_ROOT_VERIFICATION_FAILURE")
        else:
            if problem:
                blockers.append(f"OWNER_{problem}")

    unique = sorted(set(blockers))
    if unique or material is None or entry is None:
        return {
            "schema": REQUEST_SCHEMA,
            "state": "BLOCKED",
            "blockers": unique or ["FREEZE_REQUEST_PRECONDITION_FAILED"],
            "request": {},
            "request_digest": "",
            "digest_to_sign": "",
            "core_frozen": False,
            "merge_authorized": False,
            "deploy_authorized": False,
            "worker_armed": False,
            "executes_action": False,
        }

    body = {
        "schema": REQUEST_SCHEMA,
        "ceremony_id": ceremony_id,
        "owner_id": EXPECTED_OWNER_ID,
        "tenant_id": EXPECTED_TENANT_ID,
        "purpose": PURPOSE,
        "signature_mechanism": MECHANISM,
        "target_commit_sha": TARGET,
        "v226_freeze_material_digest": str(v226["digest_to_core_freeze_ceremony"]),
        "decision_record_digest": str(material["decision_record_digest"]),
        "decision_runtime_sha": str(material["decision_runtime_sha"]),
        "decision_runtime_digest": str(material["decision_runtime_digest"]),
        "decision_write_intent_id": str(material.get("decision_write_intent_id") or ""),
        "owner_decision": "APPROVE_CORE_FREEZE",
        "key_id": key_id,
        "key_version": key_version,
        "owner_public_key_fingerprint": public_key_fingerprint(entry.public_key_b64),
        "issued_at": issued_at,
        "expires_at": expires_at,
        "nonce": nonce,
        "core_freeze_ceremony_eligible": True,
        "core_freeze_execution_authorized": False,
        "core_frozen": False,
        "merge_authorized": False,
        "deploy_authorized": False,
        "worker_armed": False,
        "execution_allowed": False,
        "external_action_executed": False,
    }
    request_digest = digest(body)
    return {
        "schema": REQUEST_SCHEMA,
        "state": "READY_FOR_EXTERNAL_CORE_FREEZE_SIGNATURE",
        "blockers": [],
        "request": body,
        "request_digest": request_digest,
        "digest_to_sign": request_digest,
        "core_frozen": False,
        "merge_authorized": False,
        "deploy_authorized": False,
        "worker_armed": False,
        "executes_action": False,
    }


def verify_freeze_signature(
    request: Mapping[str, Any] | None,
    *,
    signature_b64: str,
    owner_trust_roots: TrustRootRegistry,
    v226: Mapping[str, Any] | None,
    now_ts: str,
) -> dict[str, Any]:
    if not isinstance(request, Mapping):
        return {"state": "BLOCKED", "blockers": ["FREEZE_REQUEST_REQUIRED"]}

    presented = dict(request)
    rebuilt = build_freeze_request(
        v226,
        owner_trust_roots=owner_trust_roots,
        now_ts=now_ts,
        ceremony_id=presented.get("ceremony_id"),
        nonce=presented.get("nonce"),
        issued_at=presented.get("issued_at"),
        expires_at=presented.get("expires_at"),
        key_id=presented.get("key_id"),
        key_version=presented.get("key_version"),
    )
    if rebuilt.get("state") != "READY_FOR_EXTERNAL_CORE_FREEZE_SIGNATURE":
        return {"state": "BLOCKED", "blockers": ["FREEZE_REQUEST_REBUILD_BLOCKED", *rebuilt.get("blockers", [])]}
    if rebuilt.get("request") != presented:
        return {"state": "BLOCKED", "blockers": ["FREEZE_REQUEST_REBUILD_MISMATCH"]}

    try:
        entry, problem = owner_trust_roots.verify_key_available(
            presented["key_id"], presented["key_version"], now_ts
        )
        if problem or entry is None:
            return {"state": "BLOCKED", "blockers": [f"OWNER_{problem or 'TRUST_KEY_UNKNOWN'}"]}
        if presented.get("owner_public_key_fingerprint") != public_key_fingerprint(entry.public_key_b64):
            return {"state": "BLOCKED", "blockers": ["OWNER_PUBLIC_KEY_FINGERPRINT_MISMATCH"]}
        entry.public_key().verify(decode_signature(signature_b64), canonical(presented))
    except (ValueError, InvalidSignature, KeyError):
        return {"state": "BLOCKED", "blockers": ["CORE_FREEZE_SIGNATURE_INVALID"]}

    return {
        "schema": "AION_CORE_V1_CORE_FREEZE_SIGNATURE_VERIFICATION_V1",
        "state": "CORE_FREEZE_SIGNATURE_VERIFIED",
        "blockers": [],
        "request_digest": rebuilt["request_digest"],
        "signature_digest": signature_digest(signature_b64),
        "owner_key_id": presented["key_id"],
        "owner_key_version": presented["key_version"],
        "nonce": presented["nonce"],
        "expires_at": presented["expires_at"],
        "source_runtime_sha": presented["decision_runtime_sha"],
        "v226_freeze_material_digest": presented["v226_freeze_material_digest"],
        "core_freeze_execution_authorized": True,
        "core_frozen": False,
        "merge_authorized": False,
        "deploy_authorized": False,
        "worker_armed": False,
        "executes_action": False,
    }
