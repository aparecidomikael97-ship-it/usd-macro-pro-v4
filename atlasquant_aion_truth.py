"""Reusable AION truth, provenance, freshness and conflict assessment."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping, Sequence
import json
import math

from atlasquant_aion_observability import redact_text

SCHEMA = "ATLASQUANT_AION_TRUTH_ASSESSMENT_V1"
TRUTH_STATES = ("CONFIRMED", "INFERENCE", "HYPOTHESIS", "UNKNOWN")
FRESHNESS_STATES = ("FRESH", "STALE", "UNVERIFIED", "NOT_APPLICABLE")
FUTURE_TOLERANCE_SECONDS = 120
SOURCE_TIERS = {
    "PRIMARY": 1,
    "OFFICIAL_DOCUMENTATION": 2,
    "OFFICIAL_BODY": 3,
    "PAPER": 4,
    "INSTITUTIONAL": 5,
    "RECOGNIZED_MEDIA": 6,
    "SECONDARY": 7,
    "COMMUNITY": 8,
    "UNKNOWN": 9,
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _timestamp(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)
    except Exception:
        return None


def _finite(value: Any) -> float | None:
    try:
        number = float(value)
        return number if math.isfinite(number) else None
    except Exception:
        return None


def _stable(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    except Exception:
        return repr(value)


def _claim_identity(value: Any) -> str:
    return " ".join(str(value or "").casefold().split())


def _sensitivity(item: Mapping[str, Any]) -> str:
    if "time_sensitive" not in item:
        return "UNKNOWN"
    return "TEMPORAL" if bool(item.get("time_sensitive")) else "STABLE"


def normalize_evidence_record(
    raw: Mapping[str, Any],
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    item = dict(raw or {})
    truth = str(item.get("truth_state") or item.get("kind") or "UNKNOWN").upper()
    if truth not in TRUTH_STATES:
        truth = "UNKNOWN"
    source = redact_text(item.get("source") or "").strip()[:240]
    source_tier = str(item.get("source_tier") or "UNKNOWN").upper()
    if source_tier not in SOURCE_TIERS:
        source_tier = "UNKNOWN"
    observed = _timestamp(item.get("timestamp") or item.get("observed_at"))
    ttl = _finite(item.get("ttl_seconds"))
    ttl = None if ttl is None or ttl < 0 else ttl
    current = now or _now()
    sensitivity = _sensitivity(item)
    future = False
    if observed is None:
        age = None
    else:
        delta = (current - observed).total_seconds()
        if delta < -FUTURE_TOLERANCE_SECONDS:
            future = True
            age = None
        else:
            age = max(0.0, delta)
    if sensitivity == "STABLE":
        freshness = "NOT_APPLICABLE"
        stale = False
    elif future:
        freshness = "UNVERIFIED"
        stale = False
    elif observed is None or ttl is None:
        freshness = "UNVERIFIED"
        stale = False
    elif age is not None and age > ttl:
        freshness = "STALE"
        stale = True
    else:
        freshness = "FRESH"
        stale = False
    confidence = _finite(item.get("confidence"))
    confidence = None if confidence is None else round(max(0.0, min(100.0, confidence)), 2)
    issues: list[str] = []
    if not source:
        issues.append("SOURCE_MISSING")
    if sensitivity == "TEMPORAL" and observed is None:
        issues.append("TIMESTAMP_MISSING")
    if sensitivity == "TEMPORAL" and observed is not None and ttl is None and not future:
        issues.append("TTL_MISSING")
    if sensitivity == "UNKNOWN" and freshness == "UNVERIFIED":
        issues.append("FRESHNESS_UNPROVEN")
    if future:
        issues.append("TIMESTAMP_IN_FUTURE")
    if stale:
        issues.append("DATA_STALE")
    if truth == "CONFIRMED" and issues:
        truth = "UNKNOWN"
        issues.append("CONFIRMATION_DOWNGRADED")
    return {
        "claim": redact_text(item.get("claim") or item.get("id") or "claim").strip()[:240],
        "value": item.get("value"),
        "truth_state": truth,
        "source": source or "UNKNOWN",
        "source_ref": redact_text(item.get("source_ref") or item.get("url") or "").strip()[:500],
        "source_tier": source_tier,
        "source_rank": SOURCE_TIERS[source_tier],
        "timestamp": observed.isoformat() if observed else "",
        "ttl_seconds": ttl,
        "age_seconds": None if age is None else round(age, 3),
        "freshness": freshness,
        "stale": stale,
        "confidence": confidence,
        "issues": issues,
    }


def assess_truth(
    evidence: Sequence[Mapping[str, Any]] | None,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    rows = [
        normalize_evidence_record(item, now=now)
        for item in list(evidence or [])
        if isinstance(item, Mapping)
    ]
    grouped: dict[str, set[str]] = {}
    for row in rows:
        if row["truth_state"] != "CONFIRMED":
            continue
        grouped.setdefault(_claim_identity(row["claim"]), set()).add(_stable(row["value"]))
    conflict_claims = sorted(claim for claim, vals in grouped.items() if len(vals) > 1)
    conflict = bool(conflict_claims)
    stale_count = sum(1 for row in rows if row["stale"])
    confirmed = sum(1 for row in rows if row["truth_state"] == "CONFIRMED")
    inference = sum(1 for row in rows if row["truth_state"] == "INFERENCE")
    unknown = sum(1 for row in rows if row["truth_state"] == "UNKNOWN")
    if conflict:
        status = "UNKNOWN"
        conflict_state = "CONFLICT"
        summary = "Fontes confirmadas divergem; nenhuma versão foi escolhida arbitrariamente."
    elif confirmed:
        status = "CONFIRMED"
        conflict_state = "NONE"
        summary = "Há evidência confirmada, proveniente e temporalmente válida."
    elif inference:
        status = "INFERENCE"
        conflict_state = "NONE"
        summary = "A conclusão disponível é inferência; falta confirmação direta."
    elif rows and any(row["truth_state"] == "HYPOTHESIS" for row in rows):
        status = "HYPOTHESIS"
        conflict_state = "NONE"
        summary = "Há somente hipótese ainda não confirmada."
    else:
        status = "UNKNOWN"
        conflict_state = "NONE"
        summary = "Não há evidência suficiente para uma conclusão."

    quality = 0.0
    if rows:
        quality = (
            confirmed * 24
            + inference * 10
            + sum(max(0, 10 - row["source_rank"]) for row in rows)
            - unknown * 12
            - stale_count * 20
            - (35 if conflict else 0)
        )
        quality = max(0.0, min(100.0, quality))
    if conflict:
        quality = min(quality, 30.0)
    label = "HIGH" if quality >= 75 else "MODERATE" if quality >= 45 else "LOW" if quality > 0 else "NONE"
    return {
        "schema": SCHEMA,
        "status": status,
        "confidence": {"score": round(quality, 1), "label": label, "basis": "EVIDENCE_QUALITY"},
        "conflict_state": conflict_state,
        "conflict_claims": conflict_claims,
        "freshness": "STALE" if stale_count else "FRESH" if rows and all(
            row["freshness"] in {"FRESH", "NOT_APPLICABLE"} for row in rows
        ) else "UNVERIFIED",
        "stale_count": stale_count,
        "records": rows,
        "source_references": [
            {"source": row["source"], "source_ref": row["source_ref"], "timestamp": row["timestamp"]}
            for row in rows
        ],
        "reasoning_summary": summary,
        "private_chain_of_thought_exposed": False,
        "executes_action": False,
        "real_orders_enabled": False,
    }


__all__ = [
    "SCHEMA", "TRUTH_STATES", "FRESHNESS_STATES", "SOURCE_TIERS",
    "normalize_evidence_record", "assess_truth", "FUTURE_TOLERANCE_SECONDS",
]
