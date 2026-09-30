"""AION BUSINESS Trend & Opportunity Intelligence V1.

Evidence-first, offline evaluation layer for business opportunities. It does not
browse the web by itself in this version; it evaluates evidence supplied by an
authorized upstream collector or by demo fixtures. Missing/stale evidence fails
closed and cannot become a confirmed trend.

The module also models a controlled continuous-improvement loop: hypotheses can
be compared against before/after metrics, but no result can automatically modify
production, publish content, spend money, contact clients or activate runtime.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from typing import Any, Mapping, Sequence
import json

SCHEMA = "ATLASQUANT_AION_BUSINESS_TREND_OPPORTUNITY_INTELLIGENCE_V1"
VERSION = "1"
MAX_EVIDENCE = 20
MAX_OPPORTUNITIES = 20
FRESH_DAYS = 30

SOURCE_KINDS = (
    "PUBLIC_WEB",
    "CLIENT_FEEDBACK",
    "INTERNAL_METRIC",
    "MANUAL_RESEARCH",
    "DEMO_FIXTURE",
)

TRUTH_STATES = (
    "UNVERIFIED",
    "DEMO",
    "EVIDENCE_SUPPORTED",
    "STALE",
    "INSUFFICIENT",
)

OPPORTUNITY_STATES = (
    "BLOCKED",
    "WATCH",
    "CANDIDATE",
    "STRONG_CANDIDATE",
)

IMPROVEMENT_STATES = (
    "INSUFFICIENT_EVIDENCE",
    "NO_CLEAR_IMPROVEMENT",
    "IMPROVEMENT_SUPPORTED",
    "REGRESSION_OBSERVED",
)


def _clean(value: Any, limit: int = 500) -> str:
    return " ".join(str(value or "").replace("\x00", "").split())[:limit]


def _number(value: Any, *, maximum: float | None = None) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        n = float(value)
    except Exception:
        return None
    if n < 0:
        return None
    if maximum is not None and n > maximum:
        return None
    return n


def _seq(value: Any, limit: int) -> list[Any]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    return list(value)[:limit]


def _parse_time(value: Any) -> datetime | None:
    token = _clean(value, 80)
    if not token:
        return None
    try:
        parsed = datetime.fromisoformat(token.replace("Z", "+00:00"))
    except Exception:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _digest(value: Mapping[str, Any]) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return sha256(raw.encode("utf-8")).hexdigest()


def normalize_evidence(
    raw: Mapping[str, Any] | None,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    data = dict(raw or {}) if isinstance(raw, Mapping) else {}
    current = now.astimezone(timezone.utc) if isinstance(now, datetime) else datetime.now(timezone.utc)
    source_kind = _clean(data.get("source_kind"), 60).upper()
    if source_kind not in SOURCE_KINDS:
        source_kind = "DEMO_FIXTURE" if data.get("demo") is True else ""
    observed_at = _parse_time(data.get("observed_at"))
    age_days = None
    if observed_at is not None:
        age_days = max(0.0, (current - observed_at).total_seconds() / 86400)

    source = _clean(data.get("source"), 240)
    claim = _clean(data.get("claim"), 600)
    segment = _clean(data.get("segment"), 120)
    confidence = _number(data.get("confidence"), maximum=100)

    complete = bool(source_kind and source and claim and segment and observed_at is not None and confidence is not None)
    fresh = bool(complete and age_days is not None and age_days <= FRESH_DAYS)
    if source_kind == "DEMO_FIXTURE":
        truth_state = "DEMO" if complete else "INSUFFICIENT"
    elif not complete:
        truth_state = "INSUFFICIENT"
    elif not fresh:
        truth_state = "STALE"
    elif confidence >= 60:
        truth_state = "EVIDENCE_SUPPORTED"
    else:
        truth_state = "UNVERIFIED"

    return {
        "source_kind": source_kind,
        "source": source,
        "claim": claim,
        "segment": segment,
        "observed_at": observed_at.isoformat() if observed_at else "",
        "age_days": None if age_days is None else round(age_days, 2),
        "confidence": confidence,
        "truth_state": truth_state,
        "fresh": fresh,
        "complete": complete,
        "demo": source_kind == "DEMO_FIXTURE",
    }


def normalize_opportunity(raw: Mapping[str, Any] | None) -> dict[str, Any]:
    data = dict(raw or {}) if isinstance(raw, Mapping) else {}
    return {
        "name": _clean(data.get("name"), 160),
        "segment": _clean(data.get("segment"), 120),
        "problem": _clean(data.get("problem"), 500),
        "offer": _clean(data.get("offer"), 500),
        "demand_signal": _number(data.get("demand_signal"), maximum=100),
        "pain_intensity": _number(data.get("pain_intensity"), maximum=100),
        "recurring_revenue_fit": _number(data.get("recurring_revenue_fit"), maximum=100),
        "margin_potential": _number(data.get("margin_potential"), maximum=100),
        "implementation_complexity": _number(data.get("implementation_complexity"), maximum=100),
        "support_load": _number(data.get("support_load"), maximum=100),
        "strategic_fit": _number(data.get("strategic_fit"), maximum=100),
    }


def evaluate_opportunity(
    opportunity: Mapping[str, Any] | None,
    evidence: Sequence[Mapping[str, Any]] | None,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    opp = normalize_opportunity(opportunity)
    evidence_rows = [normalize_evidence(item, now=now) for item in _seq(evidence, MAX_EVIDENCE)]
    relevant = [
        row for row in evidence_rows
        if row["segment"] and opp["segment"] and row["segment"].lower() == opp["segment"].lower()
    ]
    supported = [row for row in relevant if row["truth_state"] == "EVIDENCE_SUPPORTED"]
    demo_rows = [row for row in relevant if row["truth_state"] == "DEMO"]
    stale = [row for row in relevant if row["truth_state"] == "STALE"]

    required = (
        "name",
        "segment",
        "problem",
        "offer",
        "demand_signal",
        "pain_intensity",
        "recurring_revenue_fit",
        "margin_potential",
        "implementation_complexity",
        "support_load",
        "strategic_fit",
    )
    missing = [key for key in required if opp.get(key) in (None, "")]

    if missing:
        return {
            "schema": SCHEMA,
            "version": VERSION,
            "state": "BLOCKED",
            "reason": "INCOMPLETE_OPPORTUNITY",
            "missing": missing,
            "score": None,
            "truth_state": "INSUFFICIENT",
            "evidence": evidence_rows,
            "executes_action": False,
        }

    positive = (
        0.22 * opp["demand_signal"]
        + 0.20 * opp["pain_intensity"]
        + 0.18 * opp["recurring_revenue_fit"]
        + 0.14 * opp["margin_potential"]
        + 0.14 * opp["strategic_fit"]
    )
    friction = (
        0.07 * opp["implementation_complexity"]
        + 0.05 * opp["support_load"]
    )
    evidence_bonus = min(12.0, len(supported) * 4.0)
    score = max(0.0, min(100.0, positive - friction + evidence_bonus))

    if supported:
        truth_state = "EVIDENCE_SUPPORTED"
        evidence_quality = "SUPPORTED"
    elif demo_rows:
        truth_state = "DEMO"
        evidence_quality = "DEMO_ONLY"
    elif stale:
        truth_state = "STALE"
        evidence_quality = "STALE"
    else:
        truth_state = "INSUFFICIENT"
        evidence_quality = "INSUFFICIENT"

    if truth_state not in {"EVIDENCE_SUPPORTED", "DEMO"}:
        state = "WATCH" if score >= 55 else "BLOCKED"
    elif score >= 80 and (len(supported) >= 2 or truth_state == "DEMO"):
        state = "STRONG_CANDIDATE"
    elif score >= 65:
        state = "CANDIDATE"
    elif score >= 50:
        state = "WATCH"
    else:
        state = "BLOCKED"

    result = {
        "schema": SCHEMA,
        "version": VERSION,
        "state": state,
        "score": round(score, 1),
        "truth_state": truth_state,
        "evidence_quality": evidence_quality,
        "supported_source_count": len(supported),
        "demo_source_count": len(demo_rows),
        "stale_source_count": len(stale),
        "opportunity": opp,
        "evidence": evidence_rows,
        "recommendation": {
            "STRONG_CANDIDATE": "Preparar experimento controlado antes de transformar em oferta.",
            "CANDIDATE": "Validar com pequeno experimento e feedback de clientes.",
            "WATCH": "Coletar mais evidência antes de investir.",
            "BLOCKED": "Não avançar sem melhorar dados, evidência ou economia da oferta.",
        }[state],
        "automatic_launch": False,
        "automatic_spend": False,
        "automatic_publication": False,
        "automatic_client_contact": False,
        "runtime_activated": False,
        "executes_action": False,
    }
    result["assessment_digest"] = _digest({
        "opportunity": opp,
        "state": state,
        "score": result["score"],
        "truth_state": truth_state,
        "evidence": evidence_rows,
    })
    return result


def rank_opportunities(
    rows: Sequence[Mapping[str, Any]] | None,
    *,
    minimum_state: str = "WATCH",
) -> list[dict[str, Any]]:
    allowed = {
        "BLOCKED": 0,
        "WATCH": 1,
        "CANDIDATE": 2,
        "STRONG_CANDIDATE": 3,
    }
    threshold = allowed.get(_clean(minimum_state, 40).upper(), 1)
    normalized = [dict(x) for x in _seq(rows, MAX_OPPORTUNITIES) if isinstance(x, Mapping)]
    filtered = [x for x in normalized if allowed.get(_clean(x.get("state"), 40).upper(), 0) >= threshold]
    filtered.sort(
        key=lambda x: (
            -allowed.get(_clean(x.get("state"), 40).upper(), 0),
            -(float(x.get("score")) if isinstance(x.get("score"), (int, float)) and not isinstance(x.get("score"), bool) else -1),
            _clean(_mapping(x.get("opportunity")).get("name"), 160),
        )
    )
    return filtered


def improvement_review(
    *,
    hypothesis: Any,
    metric_name: Any,
    before_value: Any,
    after_value: Any,
    sample_size: Any,
    higher_is_better: Any = True,
    minimum_sample: int = 20,
    minimum_change_pct: float = 5.0,
) -> dict[str, Any]:
    hypothesis_text = _clean(hypothesis, 500)
    metric = _clean(metric_name, 120)
    before = _number(before_value)
    after = _number(after_value)
    sample = _number(sample_size, maximum=10_000_000)
    direction = higher_is_better if type(higher_is_better) is bool else None

    complete = bool(
        hypothesis_text and metric and before is not None and after is not None
        and sample is not None and direction is not None
    )
    if not complete or sample < minimum_sample or before == 0:
        return {
            "schema": SCHEMA,
            "state": "INSUFFICIENT_EVIDENCE",
            "change_pct": None,
            "eligible_for_promotion_review": False,
            "automatic_promotion": False,
            "automatic_deploy": False,
            "executes_action": False,
        }

    raw_change = ((after - before) / abs(before)) * 100
    beneficial_change = raw_change if direction else -raw_change

    if beneficial_change >= minimum_change_pct:
        state = "IMPROVEMENT_SUPPORTED"
        eligible = True
    elif beneficial_change <= -minimum_change_pct:
        state = "REGRESSION_OBSERVED"
        eligible = False
    else:
        state = "NO_CLEAR_IMPROVEMENT"
        eligible = False

    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": state,
        "hypothesis": hypothesis_text,
        "metric_name": metric,
        "before_value": before,
        "after_value": after,
        "sample_size": int(sample),
        "higher_is_better": direction,
        "change_pct": round(raw_change, 2),
        "beneficial_change_pct": round(beneficial_change, 2),
        "eligible_for_promotion_review": eligible,
        "automatic_promotion": False,
        "automatic_deploy": False,
        "automatic_publication": False,
        "executes_action": False,
    }


def trend_watch_posture(
    assessments: Sequence[Mapping[str, Any]] | None,
) -> dict[str, Any]:
    rows = [dict(x) for x in _seq(assessments, MAX_OPPORTUNITIES) if isinstance(x, Mapping)]
    strong = sum(1 for x in rows if x.get("state") == "STRONG_CANDIDATE")
    candidates = sum(1 for x in rows if x.get("state") == "CANDIDATE")
    watch = sum(1 for x in rows if x.get("state") == "WATCH")
    blocked = sum(1 for x in rows if x.get("state") == "BLOCKED")
    return {
        "schema": SCHEMA,
        "state": "REVIEW_AVAILABLE" if strong or candidates else "COLLECT_MORE_EVIDENCE",
        "strong_candidates": strong,
        "candidates": candidates,
        "watch": watch,
        "blocked": blocked,
        "continuous_monitoring_desired": True,
        "current_runtime_monitoring_enabled": False,
        "requires_authorized_upstream_collector": True,
        "automatic_launch": False,
        "executes_action": False,
    }


__all__ = [
    "SCHEMA",
    "VERSION",
    "SOURCE_KINDS",
    "TRUTH_STATES",
    "OPPORTUNITY_STATES",
    "IMPROVEMENT_STATES",
    "normalize_evidence",
    "normalize_opportunity",
    "evaluate_opportunity",
    "rank_opportunities",
    "improvement_review",
    "trend_watch_posture",
]
