"""AION V2.20 Core Certification contract.

Certification evidence is cryptographically attested with Ed25519 against a
separate public trust-root registry supplied by the trusted host. Caller
booleans/dictionaries cannot self-certify a dimension.

This module never executes production work and never authorizes Core Freeze.
A positive result means only CERTIFICATION_CANDIDATE for explicit owner review.
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

SCHEMA = "ATLASQUANT_AION_CORE_CERTIFICATION_V2"
EVIDENCE_SCHEMA = "ATLASQUANT_AION_CERTIFICATION_EVIDENCE_V1"
CERTIFICATION_VERSION = 2

REQUIRED_DIMENSIONS = (
    "TRUST_ROOT_AUTHORITY",
    "DURABLE_EXECUTION",
    "CAPABILITY_ISOLATION",
    "OPERATIONAL_RESILIENCE",
    "MULTIAGENT_MEMORY_GOVERNANCE",
    "CONSTITUTION_POLICY_KERNEL",
    "PROVIDER_NEUTRAL_MODEL_GATEWAY",
    "END_TO_END",
    "LOAD",
    "CHAOS",
    "RECOVERY",
    "BACKUP_RESTORE",
    "CONCURRENCY",
    "COST_GOVERNANCE",
    "AUDIT_REPLAY",
)

_ALLOWED_SOURCES = {"CI", "TEST_SUITE", "DRILL", "AUDIT"}
_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_SHA_RE = re.compile(r"^[0-9a-f]{40}$")


def _clean(value: Any, limit: int = 256) -> str:
    return " ".join(str(value or "").replace("\x00", "").split())[:limit]


def _canonical(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _canonical_bytes(value: Any) -> bytes:
    return _canonical(value).encode("utf-8")


def _digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _exact_true(value: Any) -> bool:
    return value is True


def _positive_int(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        return None
    return value


def _positive_key_version(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        return None
    return value


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


def _evidence_body(
    dimension: str,
    *,
    source: str,
    run_id: str,
    commit_sha: str,
    test_count: int,
) -> dict[str, Any]:
    return {
        "dimension": dimension,
        "commit_sha": commit_sha,
        "run_id": run_id,
        "test_count": test_count,
        "source": source,
    }


def normalize_evidence(dimension: str, raw: Mapping[str, Any] | None) -> dict[str, Any]:
    """Normalize one evidence row without trusting its self-asserted truth."""
    key = _clean(dimension, 80).upper()
    item = dict(raw or {}) if isinstance(raw, Mapping) else {}

    schema = _clean(item.get("schema"), 100).upper()
    state = _clean(item.get("state"), 40).upper()
    source = _clean(item.get("source"), 80).upper()
    run_id = _clean(item.get("run_id"), 120)
    commit_sha = _clean(item.get("commit_sha"), 64).lower()
    evidence_digest = _clean(item.get("evidence_digest"), 80).lower()
    test_count = _positive_int(item.get("test_count"))
    claimed_verified = _exact_true(item.get("verified"))
    key_id = _clean(item.get("key_id"), 128)
    key_version = _positive_key_version(item.get("key_version"))
    issued_at = _clean(item.get("issued_at"), 64)
    expires_at = _clean(item.get("expires_at"), 64)
    signature_b64 = _clean(item.get("signature_b64"), 256)

    blockers: list[str] = []
    if key not in REQUIRED_DIMENSIONS:
        blockers.append("DIMENSION_UNKNOWN")
    if schema != EVIDENCE_SCHEMA:
        blockers.append("EVIDENCE_SCHEMA_INVALID")
    if state != "VERIFIED":
        blockers.append("EVIDENCE_STATE_NOT_VERIFIED")
    if source not in _ALLOWED_SOURCES:
        blockers.append("EVIDENCE_SOURCE_INVALID")
    if not run_id:
        blockers.append("EVIDENCE_RUN_ID_REQUIRED")
    if not _SHA_RE.fullmatch(commit_sha):
        blockers.append("EVIDENCE_COMMIT_SHA_INVALID")
    if not _DIGEST_RE.fullmatch(evidence_digest):
        blockers.append("EVIDENCE_DIGEST_INVALID")
    if test_count is None:
        blockers.append("EVIDENCE_TEST_COUNT_INVALID")
    if not claimed_verified:
        blockers.append("EVIDENCE_NOT_VERIFIED")
    if not key_id:
        blockers.append("EVIDENCE_KEY_ID_REQUIRED")
    if key_version is None:
        blockers.append("EVIDENCE_KEY_VERSION_INVALID")
    if not issued_at or not expires_at:
        blockers.append("EVIDENCE_TIME_REQUIRED")
    if not signature_b64:
        blockers.append("EVIDENCE_SIGNATURE_REQUIRED")

    if (
        key in REQUIRED_DIMENSIONS
        and source in _ALLOWED_SOURCES
        and run_id
        and _SHA_RE.fullmatch(commit_sha)
        and test_count is not None
        and _DIGEST_RE.fullmatch(evidence_digest)
    ):
        expected_digest = _digest(_evidence_body(
            key,
            source=source,
            run_id=run_id,
            commit_sha=commit_sha,
            test_count=test_count,
        ))
        if evidence_digest != expected_digest:
            blockers.append("EVIDENCE_DIGEST_MISMATCH")

    return {
        "schema": schema,
        "dimension": key,
        "state": state or "UNKNOWN",
        "source": source,
        "run_id": run_id,
        "commit_sha": commit_sha,
        "evidence_digest": evidence_digest,
        "test_count": test_count or 0,
        "claimed_verified": claimed_verified,
        "key_id": key_id,
        "key_version": key_version or 0,
        "issued_at": issued_at,
        "expires_at": expires_at,
        "signature_b64": signature_b64,
        "cryptographically_verified": False,
        "blockers": sorted(set(blockers)),
        "eligible": False,
    }


def _attestation_statement(normalized: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema": EVIDENCE_SCHEMA,
        "dimension": normalized["dimension"],
        "state": normalized["state"],
        "source": normalized["source"],
        "run_id": normalized["run_id"],
        "commit_sha": normalized["commit_sha"],
        "evidence_digest": normalized["evidence_digest"],
        "test_count": normalized["test_count"],
        "verified": normalized["claimed_verified"],
        "key_id": normalized["key_id"],
        "key_version": normalized["key_version"],
        "issued_at": normalized["issued_at"],
        "expires_at": normalized["expires_at"],
    }


def _trust_root_binding(
    rows: Mapping[str, Mapping[str, Any]],
    certification_trust_roots: TrustRootRegistry,
) -> dict[str, Any]:
    """Bind the manifest to the exact public trust roots referenced by evidence."""
    bindings: list[dict[str, Any]] = []
    seen: set[tuple[str, int]] = set()
    for row in rows.values():
        key_id = row.get("key_id")
        key_version = row.get("key_version")
        if (
            not isinstance(key_id, str)
            or not key_id
            or isinstance(key_version, bool)
            or not isinstance(key_version, int)
            or key_version < 1
        ):
            continue
        pair = (key_id, key_version)
        if pair in seen:
            continue
        seen.add(pair)
        entry = certification_trust_roots.lookup(key_id, key_version)
        if entry is None:
            bindings.append({
                "key_id": key_id,
                "key_version": key_version,
                "present": False,
            })
            continue
        bindings.append({
            "key_id": entry.key_id,
            "key_version": entry.key_version,
            "algorithm": entry.algorithm,
            "public_key_b64": entry.public_key_b64,
            "status": entry.status,
            "not_before": entry.not_before,
            "not_after": entry.not_after,
            "revoked": certification_trust_roots.is_revoked(entry),
            "present": True,
        })
    bindings.sort(key=lambda item: (item["key_id"], item["key_version"]))
    return {
        "referenced_key_count": len(bindings),
        "digest": _digest(bindings),
    }


def canonical_evidence_attestation_bytes(
    dimension: str,
    raw: Mapping[str, Any],
) -> bytes:
    """Canonical bytes for an external/offline evidence signer.

    This helper never signs and never uses private-key material.
    """
    row = normalize_evidence(dimension, raw)
    blockers = [
        b for b in row["blockers"]
        if b != "EVIDENCE_SIGNATURE_REQUIRED"
    ]
    if blockers:
        raise ValueError("invalid evidence attestation fields: " + ",".join(blockers))
    return _canonical_bytes(_attestation_statement(row))


def verify_evidence_attestation(
    dimension: str,
    raw: Mapping[str, Any] | None,
    *,
    certification_trust_roots: TrustRootRegistry,
    now_ts: str,
) -> dict[str, Any]:
    """Verify one Ed25519 certification-evidence attestation."""
    row = normalize_evidence(dimension, raw)
    blockers = list(row["blockers"])

    if not isinstance(certification_trust_roots, TrustRootRegistry):
        blockers.append("CERTIFICATION_TRUST_ROOT_INVALID")

    now = None
    issued = None
    expires = None
    if row["issued_at"] and row["expires_at"]:
        try:
            now = _parse_ts(now_ts)
            issued = _parse_ts(row["issued_at"])
            expires = _parse_ts(row["expires_at"])
        except ValueError:
            blockers.append("EVIDENCE_TIME_INVALID")

    if now is not None and issued is not None and expires is not None:
        if issued > now:
            blockers.append("EVIDENCE_NOT_YET_VALID")
        if expires <= now or expires <= issued:
            blockers.append("EVIDENCE_EXPIRED_OR_INVALID_WINDOW")

    entry = None
    if (
        isinstance(certification_trust_roots, TrustRootRegistry)
        and row["key_id"]
        and row["key_version"] > 0
        and not any(b.startswith("EVIDENCE_TIME_") for b in blockers)
    ):
        try:
            entry, problem = certification_trust_roots.verify_key_available(
                row["key_id"], row["key_version"], now_ts
            )
        except Exception:
            blockers.append("CERTIFICATION_TRUST_ROOT_FAILURE")
        else:
            if problem:
                blockers.append("CERTIFICATION_" + problem)

    signature_verified = False
    shape_without_sig = [
        b for b in blockers
        if b not in {"EVIDENCE_SIGNATURE_REQUIRED"}
    ]
    if entry is not None and not shape_without_sig:
        try:
            signature = _decode_signature(row["signature_b64"])
            entry.public_key().verify(
                signature,
                _canonical_bytes(_attestation_statement(row)),
            )
            signature_verified = True
        except (ValueError, InvalidSignature):
            blockers.append("EVIDENCE_SIGNATURE_INVALID")

    blockers = sorted(set(blockers))
    if signature_verified:
        blockers = [b for b in blockers if b != "EVIDENCE_SIGNATURE_REQUIRED"]

    eligible = signature_verified and not blockers
    return {
        **row,
        "cryptographically_verified": signature_verified,
        "verified": eligible,
        "blockers": blockers,
        "eligible": eligible,
    }


def certification_evidence_digest(
    evidence: Mapping[str, Any],
    *,
    certification_trust_roots: TrustRootRegistry,
    now_ts: str,
) -> str:
    if not isinstance(evidence, Mapping):
        raise ValueError("evidence mapping required")
    canonical = {
        key: verify_evidence_attestation(
            key,
            value if isinstance(value, Mapping) else {},
            certification_trust_roots=certification_trust_roots,
            now_ts=now_ts,
        )
        for key, value in sorted(evidence.items())
    }
    return _digest(canonical)


def certify_core(
    evidence: Mapping[str, Any],
    *,
    target_commit_sha: str,
    canonical_gates_green: Any,
    global_worker_readiness_green: Any,
    certification_trust_roots: TrustRootRegistry,
    now_ts: str,
    core_freeze_authorized: Any = False,
) -> dict[str, Any]:
    """Build a certification candidate from signed independent evidence.

    Even a valid cryptographic certificate does not freeze, merge, deploy,
    arm a worker, or grant execution authority.
    """
    target = _clean(target_commit_sha, 64).lower()
    if not _SHA_RE.fullmatch(target):
        raise ValueError("target_commit_sha must be a 40-char git SHA")
    if canonical_gates_green is not True and canonical_gates_green is not False:
        raise ValueError("canonical_gates_green must be exact boolean")
    if global_worker_readiness_green is not True and global_worker_readiness_green is not False:
        raise ValueError("global_worker_readiness_green must be exact boolean")
    if core_freeze_authorized is not True and core_freeze_authorized is not False:
        raise ValueError("core_freeze_authorized must be exact boolean")
    if not isinstance(certification_trust_roots, TrustRootRegistry):
        raise ValueError("certification_trust_roots must be TrustRootRegistry")
    _parse_ts(now_ts)
    if not isinstance(evidence, Mapping):
        raise ValueError("evidence mapping required")

    raw = dict(evidence)
    rows: dict[str, dict[str, Any]] = {}
    blockers: list[str] = []

    unexpected = sorted(
        repr(key)
        for key in raw
        if not isinstance(key, str) or key not in REQUIRED_DIMENSIONS
    )
    if unexpected:
        blockers.append("UNEXPECTED_EVIDENCE_DIMENSION")

    for dimension in REQUIRED_DIMENSIONS:
        value = raw.get(dimension)
        row = verify_evidence_attestation(
            dimension,
            value if isinstance(value, Mapping) else {},
            certification_trust_roots=certification_trust_roots,
            now_ts=now_ts,
        )
        rows[dimension] = row
        if not row["eligible"]:
            blockers.append(f"DIMENSION_NOT_CERTIFIED:{dimension}")
        elif row["commit_sha"] != target:
            blockers.append(f"DIMENSION_COMMIT_MISMATCH:{dimension}")

    trust_binding = _trust_root_binding(rows, certification_trust_roots)

    if canonical_gates_green is not True:
        blockers.append("CANONICAL_GATES_NOT_GREEN")
    if global_worker_readiness_green is not True:
        blockers.append("GLOBAL_WORKER_READINESS_NOT_GREEN")

    total_tests = sum(row["test_count"] for row in rows.values())
    if total_tests < 1000:
        blockers.append("CERTIFICATION_TEST_VOLUME_BELOW_MINIMUM")

    unique = sorted(set(blockers))
    candidate = not unique

    manifest_body = {
        "schema": SCHEMA,
        "version": CERTIFICATION_VERSION,
        "target_commit_sha": target,
        "required_dimensions": list(REQUIRED_DIMENSIONS),
        "evidence": rows,
        "certification_trust_root_key_count": certification_trust_roots.key_count,
        "certification_trust_root_referenced_key_count": trust_binding["referenced_key_count"],
        "certification_trust_root_binding_digest": trust_binding["digest"],
        "canonical_gates_green": canonical_gates_green is True,
        "global_worker_readiness_green": global_worker_readiness_green is True,
        "total_evidence_test_count": total_tests,
        "all_evidence_cryptographically_verified": all(
            row["cryptographically_verified"] for row in rows.values()
        ),
        "blockers": unique,
        "state": "CERTIFICATION_CANDIDATE" if candidate else "BLOCKED",
    }
    manifest_digest = _digest(manifest_body)

    return {
        **manifest_body,
        "manifest_digest": manifest_digest,
        "certification_candidate": candidate,
        "core_complete_candidate": candidate,
        "core_complete_claim_allowed": False,
        "owner_core_complete_review_required": candidate,
        "core_freeze_requested": core_freeze_authorized is True,
        "core_freeze_authorized_by_this_module": False,
        "core_frozen": False,
        "freeze_requires_explicit_owner_action_outside_certification": True,
        "execution_allowed": False,
        "worker_armed": False,
        "merge_authorized": False,
        "deploy_authorized": False,
        "external_action_executed": False,
        "executes_action": False,
    }


def synthetic_evidence_row(
    dimension: str,
    *,
    commit_sha: str,
    run_id: str,
    test_count: int,
    source: str = "TEST_SUITE",
    key_id: str = "test-certification-key",
    key_version: int = 1,
    issued_at: str = "2026-10-04T19:00:00Z",
    expires_at: str = "2026-10-04T21:00:00Z",
) -> dict[str, Any]:
    """Create unsigned evidence-shaped test data.

    This helper deliberately cannot create certification-eligible evidence.
    An external signer must sign canonical_evidence_attestation_bytes().
    """
    key = _clean(dimension, 80).upper()
    target = _clean(commit_sha, 64).lower()
    tests = _positive_int(test_count)
    version = _positive_key_version(key_version)
    if key not in REQUIRED_DIMENSIONS:
        raise ValueError("unknown certification dimension")
    if not _SHA_RE.fullmatch(target):
        raise ValueError("invalid commit sha")
    if not _clean(run_id, 120):
        raise ValueError("run_id required")
    if tests is None:
        raise ValueError("positive test_count required")
    source_key = _clean(source, 80).upper()
    if source_key not in _ALLOWED_SOURCES:
        raise ValueError("invalid evidence source")
    if not _clean(key_id, 128) or version is None:
        raise ValueError("valid certification key required")
    _parse_ts(issued_at)
    _parse_ts(expires_at)

    body = _evidence_body(
        key,
        source=source_key,
        run_id=_clean(run_id, 120),
        commit_sha=target,
        test_count=tests,
    )
    return {
        "schema": EVIDENCE_SCHEMA,
        "state": "VERIFIED",
        "source": source_key,
        "run_id": body["run_id"],
        "commit_sha": target,
        "evidence_digest": _digest(body),
        "test_count": tests,
        "verified": True,
        "key_id": _clean(key_id, 128),
        "key_version": version,
        "issued_at": issued_at,
        "expires_at": expires_at,
        "signature_b64": "",
    }


__all__ = [
    "SCHEMA",
    "EVIDENCE_SCHEMA",
    "CERTIFICATION_VERSION",
    "REQUIRED_DIMENSIONS",
    "normalize_evidence",
    "canonical_evidence_attestation_bytes",
    "verify_evidence_attestation",
    "certification_evidence_digest",
    "certify_core",
    "synthetic_evidence_row",
]
