"""Envelope for an important AION action.

This does not replace executor, worker, or developer receipts. It references
their ids and fingerprints. The digest is a canonical integrity fingerprint,
not a signature. The envelope does not execute anything.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from itertools import islice
from typing import Any, Callable, Mapping, Sequence
import json
import unicodedata

from atlasquant_aion_observability import redact_text

SCHEMA = "ATLASQUANT_AION_ACTION_RECEIPT_V1"
ROLES = ("PRIME", "SHADOW", "SENTINEL")


def _clean(value: Any, limit: int = 240) -> str:
    return " ".join(str(value or "").replace("\x00", "").split())[:limit]


def _upper(value: Any, limit: int = 40) -> str:
    return _clean(value, limit).upper()


def _fold(value: Any) -> str:
    raw = unicodedata.normalize("NFKD", str(value or ""))
    return "".join(ch for ch in raw if not unicodedata.combining(ch)).casefold()


def _canonical(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def canonical_fingerprint(payload: Mapping[str, Any]) -> str:
    """SHA-256 of canonical JSON. Integrity fingerprint only, not a signature."""
    return sha256(_canonical(payload).encode("utf-8")).hexdigest()


def _aware(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def _refs(values: Sequence[Any] | None) -> list[str]:
    out = []
    for item in islice(values or (), 40):
        text = _clean(item, 180)
        if text and text not in out:
            out.append(text)
    return out


def _bound(refs: Sequence[str], verifier: Any) -> str:
    rows = list(refs)
    if not rows:
        return "MISSING"
    if not callable(verifier):
        return "UNVERIFIED"
    try:
        result = verifier(rows)
    except Exception:
        return "UNVERIFIED"
    if not isinstance(result, Mapping) or _upper(result.get("state"), 40) != "VERIFIED":
        return "UNVERIFIED"
    bound = _refs(result.get("bound_refs"))
    if sorted(bound) != sorted(rows):
        return "UNVERIFIED"
    return "VERIFIED"


def _child_refs(values: Sequence[Any] | None) -> list[dict[str, str]]:
    out = []
    for raw in islice(values or (), 40):
        if not isinstance(raw, Mapping):
            continue
        receipt_id = _clean(raw.get("receipt_id"), 80)
        fingerprint = _clean(raw.get("fingerprint"), 80)
        schema = _clean(raw.get("schema"), 80)
        if receipt_id and fingerprint:
            out.append({
                "receipt_id": receipt_id,
                "schema": schema,
                "fingerprint": fingerprint,
            })
    return out


def seal_action_receipt(
    payload: Mapping[str, Any] | None,
    *,
    trusted_context: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Build an envelope from trusted scope. Payload identity is not authority."""
    context = dict(trusted_context or {})
    incoming = dict(payload or {})
    result_text = redact_text(incoming.get("result") or incoming.get("result_note") or "")
    assignments = {
        _upper(role, 40): _clean(agent, 160)
        for role, agent in dict(incoming.get("reviewers") or {}).items()
    }
    body = {
        "version": "1",
        "requester_id": _clean(context.get("requester_id") or context.get("actor_id"), 160),
        "tenant_id": _clean(context.get("tenant_id"), 120),
        "workspace_id": _clean(context.get("workspace_id"), 120),
        "task_id": _clean(incoming.get("task_id"), 80),
        "prime_id": _clean(assignments.get("PRIME") or context.get("prime_id"), 160),
        "shadow_id": _clean(assignments.get("SHADOW") or context.get("shadow_id"), 160),
        "sentinel_id": _clean(assignments.get("SENTINEL") or context.get("sentinel_id"), 160),
        "blast_radius": _upper(incoming.get("blast_radius"), 20),
        "policy_ref": _clean(incoming.get("policy_ref"), 180),
        "guardian_state": _upper((incoming.get("guardian") or {}).get("state") if isinstance(incoming.get("guardian"), Mapping) else incoming.get("guardian_state"), 40) or "UNKNOWN",
        "guardian_allowed": (incoming.get("guardian") or {}).get("allowed") if isinstance(incoming.get("guardian"), Mapping) else None,
        "evidence_refs": _refs(incoming.get("evidence_refs")),
        "approval_refs": _refs(incoming.get("approval_refs")),
        "child_receipts": _child_refs(incoming.get("child_receipts")),
        "capability": _upper(incoming.get("capability"), 80),
        "tool_id": _clean(incoming.get("tool_id"), 80).lower(),
        "state": _upper(incoming.get("state"), 40) or "UNKNOWN",
        "result": result_text[:1000],
        "issued_at": _clean(incoming.get("issued_at"), 80),
        "rollback_ref": _clean(incoming.get("rollback_ref"), 180),
        "correlation_id": _clean(incoming.get("correlation_id"), 120),
        "parent_receipt_id": _clean(incoming.get("parent_receipt_id"), 80),
        "parent_fingerprint": _clean(incoming.get("parent_fingerprint"), 80),
    }
    if not isinstance(body["guardian_allowed"], bool):
        body["guardian_allowed"] = None
        body["guardian_state"] = "UNKNOWN"
    fingerprint = canonical_fingerprint(body)
    return {
        "schema": SCHEMA,
        "receipt": {**body, "fingerprint": fingerprint},
        "digest_kind": "CANONICAL_FINGERPRINT",
        "digest_is_signature": False,
        "executes_action": False,
        "secret_redacted": "[REDACTED]" in result_text,
    }


def validate_action_receipt(
    receipt: Mapping[str, Any] | None,
    *,
    trusted_context: Mapping[str, Any] | None,
    seen_correlation_ids: Sequence[Any] | None = None,
    now: datetime | None = None,
    max_age_seconds: int = 900,
    evidence_verifier: Callable[[Sequence[str]], Mapping[str, Any]] | None = None,
    approval_verifier: Callable[[Sequence[str]], Mapping[str, Any]] | None = None,
    policy_verifier: Callable[[Sequence[str]], Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Re-check an envelope. A matching fingerprint is not authorization."""
    raw = dict(receipt or {})
    presented = _clean(raw.get("fingerprint"), 80)
    body = {key: raw.get(key) for key in (
        "version", "requester_id", "tenant_id", "workspace_id", "task_id",
        "prime_id", "shadow_id", "sentinel_id", "blast_radius", "policy_ref",
        "guardian_state", "guardian_allowed", "evidence_refs", "approval_refs",
        "child_receipts", "capability", "tool_id", "state", "result", "issued_at",
        "rollback_ref", "correlation_id", "parent_receipt_id", "parent_fingerprint",
    )}
    for key in ("evidence_refs", "approval_refs"):
        body[key] = list(body[key] or [])
    body["child_receipts"] = list(body["child_receipts"] or [])
    actual = canonical_fingerprint(body)
    context = dict(trusted_context or {})
    blockers: list[str] = []
    if presented != actual:
        blockers.append("FINGERPRINT_MISMATCH")
    if _clean(raw.get("tenant_id"), 120) != _clean(context.get("tenant_id"), 120) or not _clean(context.get("tenant_id"), 120):
        blockers.append("TENANT_MISMATCH")
    if _clean(raw.get("workspace_id"), 120) != _clean(context.get("workspace_id"), 120) or not _clean(context.get("workspace_id"), 120):
        blockers.append("WORKSPACE_MISMATCH")
    assignments = {
        "PRIME": _clean(context.get("prime_id"), 160),
        "SHADOW": _clean(context.get("shadow_id"), 160),
        "SENTINEL": _clean(context.get("sentinel_id"), 160),
    }
    presented_reviewers = {
        "PRIME": _clean(raw.get("prime_id"), 160),
        "SHADOW": _clean(raw.get("shadow_id"), 160),
        "SENTINEL": _clean(raw.get("sentinel_id"), 160),
    }
    for role, agent in presented_reviewers.items():
        expected = assignments[role]
        if agent and agent != expected:
            blockers.append(f"FORGED_REVIEWER:{role}")
    if raw.get("guardian_allowed") is not True or _upper(raw.get("guardian_state"), 40) == "UNKNOWN":
        blockers.append("GUARDIAN_UNKNOWN")
    evidence_status = _bound(_refs(raw.get("evidence_refs")), evidence_verifier)
    approval_status = _bound(_refs(raw.get("approval_refs")), approval_verifier)
    policy_status = _bound([_clean(raw.get("policy_ref"), 180)] if _clean(raw.get("policy_ref"), 180) else [], policy_verifier)
    if evidence_status != "VERIFIED":
        blockers.append("EVIDENCE_" + evidence_status)
    if approval_status != "VERIFIED":
        blockers.append("APPROVAL_" + approval_status)
    if policy_status != "VERIFIED":
        blockers.append("POLICY_" + policy_status)
    correlation = _clean(raw.get("correlation_id"), 120)
    seen = {_clean(item, 120) for item in list(seen_correlation_ids or []) if _clean(item, 120)}
    if not correlation:
        blockers.append("CORRELATION_MISSING")
    elif correlation in seen:
        blockers.append("REPLAY")
    issued = _aware(raw.get("issued_at"))
    current = now if isinstance(now, datetime) and now.tzinfo is not None else None
    if issued is None or current is None or isinstance(max_age_seconds, bool) or not isinstance(max_age_seconds, int):
        blockers.append("TIMESTAMP_INVALID")
    else:
        delta = (current - issued).total_seconds()
        if delta < 0 or delta > max_age_seconds:
            blockers.append("STALE_OR_FUTURE")
    if _clean(raw.get("parent_receipt_id"), 80) and not _clean(raw.get("parent_fingerprint"), 80):
        blockers.append("PARENT_INVALID")
    if "[REDACTED]" not in redact_text(raw.get("result") or "") and _fold(raw.get("result")).find("password=") >= 0:
        blockers.append("SECRET_PRESENT")
    redacted_now = redact_text(raw.get("result") or "")
    if redacted_now != str(raw.get("result") or "") and "[REDACTED]" in redacted_now:
        blockers.append("SECRET_PRESENT")
    return {
        "schema": SCHEMA,
        "state": "INVALID" if blockers else "INFORMATION_ONLY",
        "fingerprint_ok": presented == actual,
        "digest_kind": "CANONICAL_FINGERPRINT",
        "digest_is_signature": False,
        "blockers": list(dict.fromkeys(blockers)),
        "truth_state": "UNKNOWN",
        "authorization": "NONE",
        "executes_action": False,
    }
