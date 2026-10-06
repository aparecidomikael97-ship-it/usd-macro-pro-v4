"""Trusted physical-evidence attestation for AION Developer V1.

A physical probe may produce measurements, but caller-supplied measurements do
not become trusted merely by setting verified=true. This module verifies a
separate Ed25519 attestation against the existing public TrustRootRegistry and
claims a durable nonce exactly once.

The attestation proves who signed which measurement digest and proof set. It
never runs the physical probe, executes code, writes the repository, uses a
private key, merges, deploys or grants production authority.
"""
from __future__ import annotations

import base64
import json
from datetime import datetime, timezone
from hashlib import sha256
from typing import Any, Mapping

from cryptography.exceptions import InvalidSignature

from atlasquant_aion_nonce_registry import PersistentNonceRegistry
from atlasquant_aion_trust_root import TrustRootRegistry

SCHEMA = "ATLASQUANT_AION_PHYSICAL_EVIDENCE_ATTESTATION_V1"
RESULT_SCHEMA = "ATLASQUANT_AION_PHYSICAL_EVIDENCE_VERIFICATION_V1"
MAX_STATEMENT_BYTES = 65_536
REQUIRED_PROOFS = (
    "WINDOWS_PLATFORM_VERIFIED",
    "EXECUTABLE_PINNING_VERIFIED",
    "FINAL_PATH_CONTAINMENT_VERIFIED",
    "FILESYSTEM_ISOLATION_VERIFIED",
    "NETWORK_ISOLATION_VERIFIED",
    "CHILD_PROCESS_POLICY_VERIFIED",
    "RESOURCE_LIMITS_VERIFIED",
    "OUTPUT_LIMITS_VERIFIED",
    "DISK_WRITE_LIMIT_VERIFIED",
    "ENVIRONMENT_ISOLATION_VERIFIED",
    "SYMLINK_BOUNDARY_VERIFIED",
    "HARDLINK_BOUNDARY_VERIFIED",
    "TOCTOU_RECHECK_VERIFIED",
    "SANDBOX_IDENTITY_VERIFIED",
)
ALLOWED_FIELDS = {
    "schema", "attestation_id", "probe_principal_id", "probe_session_id",
    "platform", "handoff_digest", "input_digest", "physical_evidence_digest",
    "verified_proofs", "issued_at", "expires_at", "nonce", "key_id",
    "key_version",
}


def _canonical_bytes(statement: Mapping[str, Any]) -> bytes:
    raw = json.dumps(
        dict(statement), sort_keys=True, ensure_ascii=False,
        separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")
    if len(raw) > MAX_STATEMENT_BYTES:
        raise ValueError("physical attestation oversized")
    return raw


def canonical_attestation_bytes(statement: Mapping[str, Any]) -> bytes:
    if not isinstance(statement, Mapping) or set(statement) != ALLOWED_FIELDS:
        raise ValueError("physical attestation shape mismatch")
    return _canonical_bytes(statement)


def _parse_ts(value: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError("timestamp must be RFC3339 UTC")
    try:
        return datetime.fromisoformat(value[:-1] + "+00:00").astimezone(timezone.utc)
    except Exception as exc:
        raise ValueError("invalid timestamp") from exc


def _decode_signature(value: str) -> bytes:
    if not isinstance(value, str) or not value:
        raise ValueError("signature required")
    try:
        raw = value.encode("ascii")
        sig = base64.urlsafe_b64decode(raw + b"=" * (-len(raw) % 4))
    except Exception as exc:
        raise ValueError("invalid signature encoding") from exc
    if len(sig) != 64:
        raise ValueError("Ed25519 signature must be 64 bytes")
    return sig


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def physical_evidence_digest(evidence: Mapping[str, Any]) -> str:
    if not isinstance(evidence, Mapping):
        raise ValueError("physical evidence must be a mapping")
    material = {
        "platform": str(evidence.get("platform") or "").upper(),
        "handoff_digest": str(evidence.get("handoff_digest") or ""),
        "input_digest": str(evidence.get("input_digest") or ""),
        "probe_principal_id": str(evidence.get("probe_principal_id") or ""),
        "probe_session_id": str(evidence.get("probe_session_id") or ""),
        "proofs": evidence.get("proofs") if isinstance(evidence.get("proofs"), Mapping) else {},
    }
    return "sha256:" + sha256(_canonical_json(material).encode("utf-8")).hexdigest()


def _blocked(*blockers: str, signature_verified: bool = False) -> dict[str, Any]:
    return {
        "schema": RESULT_SCHEMA,
        "state": "BLOCKED",
        "blockers": list(dict.fromkeys(blockers)),
        "trust_root_configured": True,
        "signature_verified": signature_verified,
        "nonce_registered": False,
        "physical_attestation_verified": False,
        "trusted_probe_attestation": False,
        "execution_allowed": False,
        "executes_action": False,
        "private_key_used": False,
    }


def verify_physical_evidence_attestation(
    statement: Any,
    *,
    signature_b64: str,
    trust_roots: TrustRootRegistry,
    nonce_registry: PersistentNonceRegistry,
    now_ts: str,
    expected_handoff_digest: str,
    expected_input_digest: str,
    expected_physical_evidence_digest: str,
) -> dict[str, Any]:
    if not isinstance(trust_roots, TrustRootRegistry):
        result = _blocked("TRUST_ROOT_REGISTRY_INVALID")
        result["trust_root_configured"] = False
        return result
    if not isinstance(nonce_registry, PersistentNonceRegistry):
        return _blocked("NONCE_REGISTRY_INVALID")
    if not isinstance(statement, Mapping):
        return _blocked("PHYSICAL_ATTESTATION_NOT_MAPPING")
    if set(statement) != ALLOWED_FIELDS:
        return _blocked("PHYSICAL_ATTESTATION_SHAPE_MISMATCH")
    data = dict(statement)
    blockers: list[str] = []
    if data.get("schema") != SCHEMA:
        blockers.append("PHYSICAL_ATTESTATION_SCHEMA_MISMATCH")
    for field in (
        "attestation_id", "probe_principal_id", "probe_session_id", "platform",
        "handoff_digest", "input_digest", "physical_evidence_digest", "nonce",
        "key_id", "issued_at", "expires_at",
    ):
        value = data.get(field)
        if not isinstance(value, str) or not value or len(value) > 512:
            blockers.append("PHYSICAL_ATTESTATION_FIELD_INVALID:" + field)
    if data.get("platform") != "WINDOWS":
        blockers.append("PHYSICAL_ATTESTATION_PLATFORM_INVALID")
    version = data.get("key_version")
    if not isinstance(version, int) or isinstance(version, bool) or version < 1:
        blockers.append("PHYSICAL_ATTESTATION_KEY_VERSION_INVALID")
    proofs = data.get("verified_proofs")
    if (
        not isinstance(proofs, list)
        or proofs != sorted(set(proofs))
        or set(proofs) != set(REQUIRED_PROOFS)
    ):
        blockers.append("PHYSICAL_ATTESTATION_PROOF_SET_INVALID")
    for field in ("handoff_digest", "input_digest", "physical_evidence_digest"):
        if not str(data.get(field) or "").startswith("sha256:"):
            blockers.append("PHYSICAL_ATTESTATION_DIGEST_INVALID:" + field)
    if data.get("handoff_digest") != expected_handoff_digest:
        blockers.append("PHYSICAL_ATTESTATION_HANDOFF_MISMATCH")
    if data.get("input_digest") != expected_input_digest:
        blockers.append("PHYSICAL_ATTESTATION_INPUT_MISMATCH")
    if data.get("physical_evidence_digest") != expected_physical_evidence_digest:
        blockers.append("PHYSICAL_ATTESTATION_EVIDENCE_MISMATCH")
    try:
        issued = _parse_ts(data["issued_at"])
        expires = _parse_ts(data["expires_at"])
        now = _parse_ts(now_ts)
    except Exception:
        return _blocked("PHYSICAL_ATTESTATION_TIME_INVALID")
    if issued > now:
        blockers.append("PHYSICAL_ATTESTATION_NOT_YET_VALID")
    if expires <= now or expires <= issued:
        blockers.append("PHYSICAL_ATTESTATION_EXPIRED_OR_INVALID_WINDOW")
    try:
        entry, key_problem = trust_roots.verify_key_available(
            data["key_id"], data["key_version"], now_ts
        )
    except Exception:
        return _blocked("PHYSICAL_ATTESTATION_TRUST_ROOT_FAILURE")
    if key_problem:
        blockers.append(key_problem)
    signature_verified = False
    if not blockers and entry is not None:
        try:
            entry.public_key().verify(_decode_signature(signature_b64), _canonical_bytes(data))
            signature_verified = True
        except (ValueError, InvalidSignature):
            blockers.append("PHYSICAL_ATTESTATION_SIGNATURE_INVALID")
    if blockers:
        return _blocked(*blockers, signature_verified=signature_verified)

    scope = "|".join((
        data["probe_principal_id"], data["probe_session_id"],
        data["handoff_digest"], data["input_digest"], data["physical_evidence_digest"],
    ))
    try:
        claimed = nonce_registry.claim(
            scope=scope, nonce=data["nonce"], expires_at=data["expires_at"], now_ts=now_ts
        )
    except Exception:
        return _blocked("PHYSICAL_ATTESTATION_NONCE_REGISTRY_FAILURE", signature_verified=True)
    if not claimed:
        return _blocked("PHYSICAL_ATTESTATION_NONCE_REPLAYED", signature_verified=True)

    return {
        "schema": RESULT_SCHEMA,
        "state": "VERIFIED",
        "blockers": [],
        "trust_root_configured": True,
        "signature_verified": True,
        "nonce_registered": True,
        "physical_attestation_verified": True,
        "trusted_probe_attestation": True,
        "execution_allowed": False,
        "executes_action": False,
        "private_key_used": False,
        "attestation_id": data["attestation_id"],
        "probe_principal_id": data["probe_principal_id"],
        "probe_session_id": data["probe_session_id"],
        "platform": data["platform"],
        "handoff_digest": data["handoff_digest"],
        "input_digest": data["input_digest"],
        "physical_evidence_digest": data["physical_evidence_digest"],
        "verified_proofs": list(data["verified_proofs"]),
        "key_id": data["key_id"],
        "key_version": data["key_version"],
    }


__all__ = [
    "SCHEMA", "RESULT_SCHEMA", "REQUIRED_PROOFS", "ALLOWED_FIELDS",
    "canonical_attestation_bytes", "physical_evidence_digest",
    "verify_physical_evidence_attestation",
]
