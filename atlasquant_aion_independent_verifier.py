"""Independent verification receipts for AION claims.

This module separates a claim producer from the component that verifies it.
Receipts are scoped, evidence-bound, tamper-evident and authority-neutral.
No verifier here executes tools, grants approval, changes permissions or calls
an external provider by itself. Source/model adapters are injected explicitly.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from typing import Any, Callable, Mapping, Sequence

from aion_chat.models import Scope
from atlasquant_aion_observability import redact_text

SCHEMA = "ATLASQUANT_AION_INDEPENDENT_VERIFICATION_V1"
RECEIPT_SCHEMA = "ATLASQUANT_AION_VERIFICATION_RECEIPT_V1"
VERIFIER_KINDS = frozenset({"CODE", "SOURCE_REQUERY", "HUMAN", "INDEPENDENT_MODEL"})
MAX_RECEIPT_AGE_SECONDS = 900
MAX_REFS = 64
MAX_CHECKS = 64


def _clean(value: Any, limit: int = 1000) -> str:
    return " ".join(str(value or "").replace("\x00", "").split())[:limit]


def _canonical(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
        default=str,
    )


def _digest(value: Any) -> str:
    return "sha256:" + sha256(_canonical(value).encode("utf-8")).hexdigest()


def _aware(value: Any | None = None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    if isinstance(value, datetime):
        out = value
    else:
        out = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if out.tzinfo is None:
        raise ValueError("timezone-aware timestamp required")
    return out.astimezone(timezone.utc)


def _refs(values: Sequence[Any] | None) -> list[str]:
    out: list[str] = []
    for raw in list(values or [])[:MAX_REFS * 2]:
        value = _clean(raw, 300)
        if value and value not in out:
            out.append(value)
        if len(out) >= MAX_REFS:
            break
    return out


def _scope(scope: Scope | Mapping[str, Any]) -> dict[str, str]:
    if isinstance(scope, Scope):
        row = {
            "owner_id": scope.owner_id,
            "tenant_id": scope.tenant_id,
            "workspace_id": scope.workspace_id,
        }
    elif isinstance(scope, Mapping):
        row = {
            "owner_id": _clean(scope.get("owner_id") or scope.get("actor_id"), 120),
            "tenant_id": _clean(scope.get("tenant_id"), 120),
            "workspace_id": _clean(scope.get("workspace_id"), 120),
        }
    else:
        raise TypeError("trusted scope required")
    if not all(row.values()):
        raise ValueError("trusted owner/tenant/workspace required")
    return row


def new_verification_request(
    *,
    claim_ref: Any,
    content: Any,
    source_type: Any,
    producer_id: Any,
    producer_fingerprint: Any,
    evidence_refs: Sequence[Any] | None,
    provenance_refs: Sequence[Any] | None,
    scope: Scope | Mapping[str, Any],
    policy_version: Any,
    created_at: Any = None,
) -> dict[str, Any]:
    claim = _clean(claim_ref, 180)
    text = " ".join(str(content or "").replace("\x00", "").split())
    producer = _clean(producer_id, 180)
    producer_fp = _clean(producer_fingerprint, 220)
    policy = _clean(policy_version, 120)
    evidence = _refs(evidence_refs)
    provenance = _refs(provenance_refs)
    if not claim or not text or not producer or not producer_fp or not policy:
        raise ValueError("claim/content/producer/fingerprint/policy required")
    if not evidence or not provenance:
        raise ValueError("evidence and provenance references required")
    safe = redact_text(text)[:8000]
    if "[REDACTED]" in safe:
        raise ValueError("secret-like claim content rejected")
    identity = _scope(scope)
    body = {
        "schema": SCHEMA,
        **identity,
        "claim_ref": claim,
        "content": safe,
        "content_digest": "sha256:" + sha256(text.encode("utf-8")).hexdigest(),
        "source_type": _clean(source_type, 80).upper() or "UNKNOWN",
        "producer_id": producer,
        "producer_fingerprint": producer_fp,
        "evidence_refs": evidence,
        "provenance_refs": provenance,
        "policy_version": policy,
        "created_at": _aware(created_at).isoformat(),
        "authorization": "NONE",
        "executes_action": False,
    }
    body["request_digest"] = _digest(body)
    return body


def _blocked(request: Mapping[str, Any], kind: str, verifier_id: str, *blockers: str) -> dict[str, Any]:
    return {
        "schema": RECEIPT_SCHEMA,
        "state": "BLOCKED",
        "blockers": list(dict.fromkeys(blockers)),
        "request_digest": _clean(request.get("request_digest"), 160),
        "claim_ref": _clean(request.get("claim_ref"), 180),
        "content_digest": _clean(request.get("content_digest"), 160),
        "verification_kind": kind,
        "verifier_id": verifier_id,
        "bound_refs": [],
        "independent": False,
        "receipt_digest": "",
        "authorization": "NONE",
        "action_authorized": False,
        "may_expand_permissions": False,
        "executes_action": False,
    }


def _base_gate(
    request: Mapping[str, Any],
    *,
    verifier_kind: Any,
    verifier_id: Any,
    verifier_fingerprint: Any,
    now: Any = None,
) -> tuple[list[str], str, str, str, datetime]:
    blockers: list[str] = []
    if not isinstance(request, Mapping) or request.get("schema") != SCHEMA:
        blockers.append("REQUEST_SCHEMA_INVALID")
    supplied = _clean(request.get("request_digest"), 160)
    body = dict(request or {})
    body.pop("request_digest", None)
    if supplied != _digest(body):
        blockers.append("REQUEST_DIGEST_MISMATCH")
    kind = _clean(verifier_kind, 40).upper()
    if kind not in VERIFIER_KINDS:
        blockers.append("VERIFIER_KIND_INVALID")
    verifier = _clean(verifier_id, 180)
    verifier_fp = _clean(verifier_fingerprint, 220)
    if not verifier or not verifier_fp:
        blockers.append("VERIFIER_IDENTITY_MISSING")
    if verifier == _clean(request.get("producer_id"), 180):
        blockers.append("PRODUCER_VERIFIER_ID_COLLISION")
    if verifier_fp == _clean(request.get("producer_fingerprint"), 220):
        blockers.append("PRODUCER_VERIFIER_FINGERPRINT_COLLISION")
    current = _aware(now)
    created = _aware(request.get("created_at"))
    age = (current - created).total_seconds()
    if age < 0:
        blockers.append("REQUEST_FROM_FUTURE")
    if age > MAX_RECEIPT_AGE_SECONDS:
        blockers.append("REQUEST_STALE")
    return blockers, kind, verifier, verifier_fp, current


def _seal_receipt(
    request: Mapping[str, Any],
    *,
    kind: str,
    verifier_id: str,
    verifier_fingerprint: str,
    bound_refs: Sequence[Any],
    verification_evidence: Mapping[str, Any],
    verified_at: datetime,
) -> dict[str, Any]:
    refs = _refs(bound_refs)
    expected = _refs(request.get("evidence_refs"))
    if sorted(refs) != sorted(expected):
        return _blocked(request, kind, verifier_id, "BOUND_REFS_MISMATCH")
    evidence = dict(verification_evidence or {})
    body = {
        "schema": RECEIPT_SCHEMA,
        "state": "VERIFIED",
        "blockers": [],
        "owner_id": _clean(request.get("owner_id"), 120),
        "tenant_id": _clean(request.get("tenant_id"), 120),
        "workspace_id": _clean(request.get("workspace_id"), 120),
        "request_digest": request["request_digest"],
        "claim_ref": request["claim_ref"],
        "content_digest": request["content_digest"],
        "policy_version": request["policy_version"],
        "verification_kind": kind,
        "verifier_id": verifier_id,
        "verifier_fingerprint": verifier_fingerprint,
        "producer_id": request["producer_id"],
        "producer_fingerprint": request["producer_fingerprint"],
        "bound_refs": refs,
        "verification_evidence": evidence,
        "verified_at": verified_at.isoformat(),
        "independent": True,
        "authorization": "NONE",
        "action_authorized": False,
        "approval_implied": False,
        "may_expand_permissions": False,
        "executes_action": False,
    }
    body["receipt_digest"] = _digest(body)
    return body


def verify_with_code(
    request: Mapping[str, Any],
    *,
    verifier_id: Any,
    verifier_fingerprint: Any,
    checks: Mapping[str, Any],
    now: Any = None,
) -> dict[str, Any]:
    blockers, kind, verifier, verifier_fp, current = _base_gate(
        request,
        verifier_kind="CODE",
        verifier_id=verifier_id,
        verifier_fingerprint=verifier_fingerprint,
        now=now,
    )
    rows = dict(checks or {})
    if not rows or len(rows) > MAX_CHECKS:
        blockers.append("CODE_CHECKS_INVALID")
    failed = sorted(
        _clean(name, 120)
        for name, value in rows.items()
        if value is not True
    )
    if failed:
        blockers.append("CODE_CHECK_FAILED")
    if blockers:
        out = _blocked(request, kind, verifier, *blockers)
        out["failed_checks"] = failed
        return out
    return _seal_receipt(
        request,
        kind=kind,
        verifier_id=verifier,
        verifier_fingerprint=verifier_fp,
        bound_refs=request["evidence_refs"],
        verification_evidence={
            "checks": {str(k): True for k in sorted(rows)},
            "method": "DETERMINISTIC_CONSTRAINTS",
        },
        verified_at=current,
    )


def verify_with_source_requery(
    request: Mapping[str, Any],
    *,
    verifier_id: Any,
    verifier_fingerprint: Any,
    resolver: Callable[[Sequence[str]], Mapping[str, Any]],
    now: Any = None,
) -> dict[str, Any]:
    blockers, kind, verifier, verifier_fp, current = _base_gate(
        request,
        verifier_kind="SOURCE_REQUERY",
        verifier_id=verifier_id,
        verifier_fingerprint=verifier_fingerprint,
        now=now,
    )
    if not callable(resolver):
        blockers.append("SOURCE_RESOLVER_MISSING")
        result: dict[str, Any] = {}
    else:
        try:
            result = dict(resolver(list(request.get("evidence_refs") or [])) or {})
        except Exception:
            result = {}
            blockers.append("SOURCE_REQUERY_FAILED")
    bound = _refs(result.get("bound_refs") if isinstance(result.get("bound_refs"), (list, tuple)) else [])
    if _clean(result.get("content_digest"), 160) != _clean(request.get("content_digest"), 160):
        blockers.append("SOURCE_CONTENT_DIGEST_MISMATCH")
    if sorted(bound) != sorted(_refs(request.get("evidence_refs"))):
        blockers.append("SOURCE_BOUND_REFS_MISMATCH")
    snapshots = result.get("source_snapshots")
    if not isinstance(snapshots, list) or not snapshots:
        blockers.append("SOURCE_SNAPSHOTS_MISSING")
    if result.get("state") != "VERIFIED":
        blockers.append("SOURCE_NOT_VERIFIED")
    if blockers:
        return _blocked(request, kind, verifier, *blockers)
    return _seal_receipt(
        request,
        kind=kind,
        verifier_id=verifier,
        verifier_fingerprint=verifier_fp,
        bound_refs=bound,
        verification_evidence={
            "source_snapshots": snapshots[:MAX_REFS],
            "method": "SOURCE_REQUERY",
        },
        verified_at=current,
    )


def verify_with_human_review(
    request: Mapping[str, Any],
    *,
    verifier_id: Any,
    verifier_fingerprint: Any,
    reviewed_refs: Sequence[Any],
    review_approved: Any,
    review_ref: Any,
    now: Any = None,
) -> dict[str, Any]:
    blockers, kind, verifier, verifier_fp, current = _base_gate(
        request,
        verifier_kind="HUMAN",
        verifier_id=verifier_id,
        verifier_fingerprint=verifier_fingerprint,
        now=now,
    )
    refs = _refs(reviewed_refs)
    if review_approved is not True:
        blockers.append("HUMAN_REVIEW_NOT_APPROVED")
    if sorted(refs) != sorted(_refs(request.get("evidence_refs"))):
        blockers.append("HUMAN_REVIEW_REFS_MISMATCH")
    review = _clean(review_ref, 180)
    if not review:
        blockers.append("HUMAN_REVIEW_REF_MISSING")
    if blockers:
        return _blocked(request, kind, verifier, *blockers)
    return _seal_receipt(
        request,
        kind=kind,
        verifier_id=verifier,
        verifier_fingerprint=verifier_fp,
        bound_refs=refs,
        verification_evidence={"review_ref": review, "method": "HUMAN_REVIEW"},
        verified_at=current,
    )


def verify_with_independent_model(
    request: Mapping[str, Any],
    *,
    verifier_id: Any,
    verifier_fingerprint: Any,
    evaluator: Callable[[Mapping[str, Any]], Mapping[str, Any]],
    now: Any = None,
) -> dict[str, Any]:
    blockers, kind, verifier, verifier_fp, current = _base_gate(
        request,
        verifier_kind="INDEPENDENT_MODEL",
        verifier_id=verifier_id,
        verifier_fingerprint=verifier_fingerprint,
        now=now,
    )
    if not callable(evaluator):
        blockers.append("MODEL_EVALUATOR_MISSING")
        result: dict[str, Any] = {}
    else:
        try:
            result = dict(evaluator(dict(request)) or {})
        except Exception:
            result = {}
            blockers.append("MODEL_EVALUATION_FAILED")
    bound = _refs(result.get("bound_refs") if isinstance(result.get("bound_refs"), (list, tuple)) else [])
    if result.get("state") != "VERIFIED":
        blockers.append("MODEL_DID_NOT_VERIFY")
    if result.get("independent") is not True:
        blockers.append("MODEL_INDEPENDENCE_NOT_ATTESTED")
    if _clean(result.get("content_digest"), 160) != _clean(request.get("content_digest"), 160):
        blockers.append("MODEL_CONTENT_DIGEST_MISMATCH")
    if sorted(bound) != sorted(_refs(request.get("evidence_refs"))):
        blockers.append("MODEL_BOUND_REFS_MISMATCH")
    if _clean(result.get("verifier_fingerprint"), 220) != verifier_fp:
        blockers.append("MODEL_FINGERPRINT_MISMATCH")
    if blockers:
        return _blocked(request, kind, verifier, *blockers)
    return _seal_receipt(
        request,
        kind=kind,
        verifier_id=verifier,
        verifier_fingerprint=verifier_fp,
        bound_refs=bound,
        verification_evidence={
            "evaluation_ref": _clean(result.get("evaluation_ref"), 180),
            "method": "INDEPENDENT_MODEL",
        },
        verified_at=current,
    )


def validate_verification_receipt(
    receipt: Mapping[str, Any],
    *,
    request: Mapping[str, Any],
    scope: Scope | Mapping[str, Any],
    now: Any = None,
) -> dict[str, Any]:
    blockers: list[str] = []
    if not isinstance(receipt, Mapping) or receipt.get("schema") != RECEIPT_SCHEMA:
        blockers.append("RECEIPT_SCHEMA_INVALID")
        row = dict(receipt or {})
    else:
        row = dict(receipt)
    supplied = _clean(row.get("receipt_digest"), 160)
    body = dict(row)
    body.pop("receipt_digest", None)
    if not supplied or supplied != _digest(body):
        blockers.append("RECEIPT_DIGEST_MISMATCH")
    if row.get("state") != "VERIFIED" or row.get("independent") is not True:
        blockers.append("RECEIPT_NOT_INDEPENDENT_VERIFIED")
    expected_scope = _scope(scope)
    for key, value in expected_scope.items():
        if _clean(row.get(key), 120) != value:
            blockers.append("RECEIPT_SCOPE_MISMATCH")
            break
    if _clean(row.get("request_digest"), 160) != _clean(request.get("request_digest"), 160):
        blockers.append("RECEIPT_REQUEST_MISMATCH")
    if _clean(row.get("content_digest"), 160) != _clean(request.get("content_digest"), 160):
        blockers.append("RECEIPT_CONTENT_MISMATCH")
    if sorted(_refs(row.get("bound_refs"))) != sorted(_refs(request.get("evidence_refs"))):
        blockers.append("RECEIPT_REFS_MISMATCH")
    if _clean(row.get("verifier_fingerprint"), 220) == _clean(request.get("producer_fingerprint"), 220):
        blockers.append("RECEIPT_NOT_INDEPENDENT")
    try:
        age = (_aware(now) - _aware(row.get("verified_at"))).total_seconds()
        if age < 0 or age > MAX_RECEIPT_AGE_SECONDS:
            blockers.append("RECEIPT_STALE_OR_FUTURE")
    except Exception:
        blockers.append("RECEIPT_TIME_INVALID")
    for field in ("action_authorized", "approval_implied", "may_expand_permissions", "executes_action"):
        if row.get(field) is not False:
            blockers.append("RECEIPT_AUTHORITY_CLAIM")
            break
    return {
        "schema": RECEIPT_SCHEMA,
        "state": "VERIFIED" if not blockers else "BLOCKED",
        "blockers": list(dict.fromkeys(blockers)),
        "valid": not blockers,
        "receipt_digest": supplied,
        "request_digest": _clean(row.get("request_digest"), 160),
        "authorization": "NONE",
        "action_authorized": False,
        "executes_action": False,
    }


def as_memory_verifier_result(
    receipt: Mapping[str, Any],
    *,
    request: Mapping[str, Any],
    scope: Scope | Mapping[str, Any],
    now: Any = None,
) -> dict[str, Any]:
    validated = validate_verification_receipt(
        receipt,
        request=request,
        scope=scope,
        now=now,
    )
    if validated["valid"] is not True:
        return {
            "state": "BLOCKED",
            "independent": False,
            "verifier_id": _clean(receipt.get("verifier_id"), 180),
            "bound_refs": [],
            "content_digest": _clean(request.get("content_digest"), 160),
            "receipt_digest": _clean(receipt.get("receipt_digest"), 160),
            "blockers": validated["blockers"],
        }
    return {
        "state": "VERIFIED",
        "independent": True,
        "verifier_id": _clean(receipt.get("verifier_id"), 180),
        "bound_refs": _refs(receipt.get("bound_refs")),
        "content_digest": request["content_digest"],
        "receipt_digest": receipt["receipt_digest"],
        "verification_kind": receipt["verification_kind"],
    }


__all__ = [
    "SCHEMA",
    "RECEIPT_SCHEMA",
    "VERIFIER_KINDS",
    "MAX_RECEIPT_AGE_SECONDS",
    "new_verification_request",
    "verify_with_code",
    "verify_with_source_requery",
    "verify_with_human_review",
    "verify_with_independent_model",
    "validate_verification_receipt",
    "as_memory_verifier_result",
]
