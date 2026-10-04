"""AION V2.13 cryptographic authority verifier.

Verifies externally provisioned Ed25519 authority statements against a local
public trust-root registry and persistent nonce registry.

This verifier never performs the external action. A verified authority grant is
still distinct from human approval and execution readiness.
"""
from __future__ import annotations

import base64
import json
from datetime import datetime, timezone
from typing import Any, Mapping

from cryptography.exceptions import InvalidSignature

from atlasquant_aion_nonce_registry import PersistentNonceRegistry
from atlasquant_aion_trust_root import TrustRootRegistry

SCHEMA = "ATLASQUANT_AION_AUTHORITY_STATEMENT_V1"
RESULT_SCHEMA = "ATLASQUANT_AION_AUTHORITY_VERIFICATION_V1"
MAX_STATEMENT_BYTES = 65_536
MAX_CAPABILITIES = 64
ALLOWED_FIELDS = {
    "schema", "statement_id", "authority_id", "subject_id", "tenant_id",
    "domain", "policy_id", "capabilities", "issued_at", "expires_at",
    "nonce", "key_id", "key_version", "grant_kind",
}
REQUIRED_BINDINGS = ("subject_id", "tenant_id", "domain", "policy_id")
GRANT_KIND = "CAPABILITY_GRANT"


def _parse_ts(value: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError("timestamp must be RFC3339 UTC")
    try:
        return datetime.fromisoformat(value[:-1] + "+00:00").astimezone(timezone.utc)
    except Exception as exc:
        raise ValueError("invalid timestamp") from exc


def _canonical_bytes(statement: Mapping[str, Any]) -> bytes:
    raw = json.dumps(
        dict(statement),
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    if len(raw) > MAX_STATEMENT_BYTES:
        raise ValueError("authority statement oversized")
    return raw


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


def _blocked(*blockers: str, trust_root_configured=True) -> dict[str, Any]:
    return {
        "schema": RESULT_SCHEMA,
        "state": "BLOCKED",
        "blockers": sorted(set(blockers)),
        "trust_root_configured": bool(trust_root_configured),
        "signature_verified": False,
        "binding_verified": False,
        "nonce_registered": False,
        "authority_verified": False,
        "execution_authority_granted": False,
        "execution_allowed": False,
        "approval_implied": False,
        "executes_action": False,
        "network_called": False,
        "private_key_used": False,
    }


def verify_authority_statement(
    statement: Any,
    *,
    signature_b64: str,
    trust_roots: TrustRootRegistry,
    nonce_registry: PersistentNonceRegistry,
    now_ts: str,
    expected_binding: Mapping[str, str],
) -> dict[str, Any]:
    blockers: list[str] = []
    if not isinstance(statement, Mapping):
        return _blocked("AUTHORITY_STATEMENT_NOT_MAPPING")
    if set(statement) != ALLOWED_FIELDS:
        return _blocked("AUTHORITY_STATEMENT_SHAPE_MISMATCH")
    data = dict(statement)
    if data.get("schema") != SCHEMA:
        blockers.append("AUTHORITY_SCHEMA_MISMATCH")
    if data.get("grant_kind") != GRANT_KIND:
        blockers.append("AUTHORITY_GRANT_KIND_INVALID")

    for field in ("statement_id", "authority_id", "subject_id", "tenant_id", "domain",
                  "policy_id", "nonce", "key_id", "issued_at", "expires_at"):
        value = data.get(field)
        if not isinstance(value, str) or not value or len(value) > 256:
            blockers.append(f"AUTHORITY_FIELD_INVALID:{field}")

    version = data.get("key_version")
    if not isinstance(version, int) or isinstance(version, bool) or version < 1:
        blockers.append("AUTHORITY_KEY_VERSION_INVALID")

    caps = data.get("capabilities")
    if (
        not isinstance(caps, list)
        or len(caps) > MAX_CAPABILITIES
        or any(not isinstance(v, str) or not v or len(v) > 256 for v in caps)
        or (isinstance(caps, list) and len(caps) != len(set(caps)))
    ):
        blockers.append("AUTHORITY_CAPABILITIES_INVALID")

    if blockers:
        return _blocked(*blockers)

    try:
        now = _parse_ts(now_ts)
        issued = _parse_ts(data["issued_at"])
        expires = _parse_ts(data["expires_at"])
    except ValueError:
        return _blocked("AUTHORITY_TIME_INVALID")

    if issued > now:
        blockers.append("AUTHORITY_NOT_YET_VALID")
    if expires <= now or expires <= issued:
        blockers.append("AUTHORITY_EXPIRED_OR_INVALID_WINDOW")

    if not isinstance(expected_binding, Mapping):
        blockers.append("AUTHORITY_BINDING_EXPECTATION_INVALID")
    else:
        for field in REQUIRED_BINDINGS:
            expected = expected_binding.get(field)
            if not isinstance(expected, str) or not expected:
                blockers.append(f"AUTHORITY_BINDING_EXPECTATION_MISSING:{field}")
            elif data[field] != expected:
                blockers.append(f"AUTHORITY_BINDING_MISMATCH:{field}")

    entry = None
    if not blockers:
        entry, key_problem = trust_roots.verify_key_available(
            data["key_id"], data["key_version"], now_ts
        )
        if key_problem:
            blockers.append(key_problem)

    signature_verified = False
    if not blockers and entry is not None:
        try:
            signature = _decode_signature(signature_b64)
            entry.public_key().verify(signature, _canonical_bytes(data))
            signature_verified = True
        except (ValueError, InvalidSignature):
            blockers.append("AUTHORITY_SIGNATURE_INVALID")

    if blockers:
        result = _blocked(*blockers)
        result["signature_verified"] = signature_verified
        return result

    scope = "|".join((
        data["authority_id"], data["subject_id"], data["tenant_id"],
        data["domain"], data["policy_id"],
    ))
    claimed = nonce_registry.claim(
        scope=scope,
        nonce=data["nonce"],
        expires_at=data["expires_at"],
        now_ts=now_ts,
    )
    if not claimed:
        result = _blocked("AUTHORITY_NONCE_REPLAYED")
        result["signature_verified"] = True
        result["binding_verified"] = True
        return result

    return {
        "schema": RESULT_SCHEMA,
        "state": "VERIFIED",
        "blockers": [],
        "trust_root_configured": True,
        "signature_verified": True,
        "binding_verified": True,
        "nonce_registered": True,
        "authority_verified": True,
        "execution_authority_granted": True,
        "execution_allowed": False,
        "approval_implied": False,
        "executes_action": False,
        "network_called": False,
        "private_key_used": False,
        "authority_id": data["authority_id"],
        "subject_id": data["subject_id"],
        "tenant_id": data["tenant_id"],
        "domain": data["domain"],
        "policy_id": data["policy_id"],
        "capabilities": sorted(data["capabilities"]),
        "key_id": data["key_id"],
        "key_version": data["key_version"],
        "statement_id": data["statement_id"],
    }


def canonical_statement_bytes(statement: Mapping[str, Any]) -> bytes:
    """Public helper for offline signers/tests. Does not sign anything."""
    if not isinstance(statement, Mapping) or set(statement) != ALLOWED_FIELDS:
        raise ValueError("authority statement shape mismatch")
    return _canonical_bytes(statement)
