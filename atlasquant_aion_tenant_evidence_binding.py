"""Integrity binding for tenant persistence evidence.

Evidence records bind a named invariant to a subject digest and a test-result
digest. They remain non-authoritative and can only support admin review.
"""
from __future__ import annotations

from typing import Any, Mapping
import hashlib
import json
import re

SCHEMA = "ATLASQUANT_AION_TENANT_EVIDENCE_BINDING_V1"
EVIDENCE_KINDS = (
    "IDENTITY_REGISTRY",
    "ACL_STORE",
    "DURABLE_STORE",
    "TENANT_E2E",
    "BACKUP_RESTORE",
    "REVOCATION_REPLAY",
)
_DIGEST = re.compile(r"^sha256:[a-f0-9]{64}$")

def _canonical(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")

def _record_digest(payload: Mapping[str, Any]) -> str:
    return "sha256:" + hashlib.sha256(_canonical(dict(payload))).hexdigest()

def build_evidence_record(
    kind: Any,
    *,
    subject_digest: Any,
    result_digest: Any,
    test_count: Any,
    status: Any = "PASS",
    producer: Any = "LOCAL_TEST_SUITE_V1",
    scope: Any = "tenant/workspace",
) -> dict[str, Any]:
    key = str(kind or "").strip().upper()
    if key not in EVIDENCE_KINDS:
        raise ValueError("unknown tenant evidence kind")

    subject = str(subject_digest or "").strip().lower()
    result = str(result_digest or "").strip().lower()
    state = str(status or "").strip().upper()
    source = str(producer or "").strip()[:120]
    evidence_scope = str(scope or "").strip().lower()
    if not _DIGEST.fullmatch(subject):
        raise ValueError("invalid subject digest")
    if not _DIGEST.fullmatch(result):
        raise ValueError("invalid result digest")
    try:
        count = int(test_count)
    except Exception as exc:
        raise ValueError("invalid test count") from exc
    if count <= 0:
        raise ValueError("test count must be positive")
    if state not in {"PASS", "FAIL"}:
        raise ValueError("invalid evidence status")
    if evidence_scope != "tenant/workspace":
        raise ValueError("invalid evidence scope")
    if not source:
        raise ValueError("producer required")

    payload = {
        "schema": SCHEMA,
        "kind": key,
        "status": state,
        "scope": evidence_scope,
        "subject_digest": subject,
        "result_digest": result,
        "test_count": count,
        "producer": source,
        "authority": False,
        "automatic_activation": False,
    }
    return {**payload, "digest": _record_digest(payload)}

def validate_evidence_record(
    raw: Mapping[str, Any] | None,
    *,
    expected_kind: Any,
) -> dict[str, Any]:
    row = dict(raw or {})
    key = str(expected_kind or "").strip().upper()
    reasons: list[str] = []
    if key not in EVIDENCE_KINDS:
        reasons.append("EXPECTED_KIND_INVALID")
    if row.get("schema") != SCHEMA:
        reasons.append("SCHEMA_INVALID")

    if str(row.get("kind") or "").strip().upper() != key:
        reasons.append("KIND_MISMATCH")
    if str(row.get("status") or "").strip().upper() not in {"PASS", "FAIL"}:
        reasons.append("STATUS_INVALID")
    if str(row.get("scope") or "").strip().lower() != "tenant/workspace":
        reasons.append("SCOPE_INVALID")
    if not _DIGEST.fullmatch(str(row.get("subject_digest") or "").strip().lower()):
        reasons.append("SUBJECT_DIGEST_INVALID")
    if not _DIGEST.fullmatch(str(row.get("result_digest") or "").strip().lower()):
        reasons.append("RESULT_DIGEST_INVALID")
    try:
        count = int(row.get("test_count"))
    except Exception:
        count = 0
    if count <= 0:
        reasons.append("TEST_COUNT_INVALID")
    if not str(row.get("producer") or "").strip():
        reasons.append("PRODUCER_REQUIRED")
    if row.get("authority") is not False:
        reasons.append("AUTHORITY_FORBIDDEN")
    if row.get("automatic_activation") is not False:
        reasons.append("AUTO_ACTIVATION_FORBIDDEN")

    supplied = str(row.get("digest") or "").strip().lower()
    payload = dict(row)
    payload.pop("digest", None)
    expected = _record_digest(payload) if not reasons else ""
    if not _DIGEST.fullmatch(supplied):
        reasons.append("EVIDENCE_DIGEST_INVALID")
    elif expected and supplied != expected:
        reasons.append("EVIDENCE_DIGEST_MISMATCH")
    return {
        "valid": not reasons,
        "reasons": reasons,
        "kind": key,
        "status": str(row.get("status") or "").strip().upper() or "MISSING",
        "scope": str(row.get("scope") or "").strip().lower(),
        "digest": supplied if not reasons else "",
        "subject_digest": str(row.get("subject_digest") or "").strip().lower(),
        "result_digest": str(row.get("result_digest") or "").strip().lower(),
        "test_count": count,
        "authority": False,
    }

__all__ = [
    "SCHEMA",
    "EVIDENCE_KINDS",
    "build_evidence_record",
    "validate_evidence_record",
]
