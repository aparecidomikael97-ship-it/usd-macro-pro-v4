"""Temporal freshness contract for AtlasQuant data-confidence evidence.

Freshness is descriptive evidence only. CURRENT means the declared source and
clock are recent enough for the supplied TTL; it does not prove agreement,
strategy quality, provider health, or execution authority.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping, Sequence
import math


UNKNOWN = "UNKNOWN"
INVALID = "INVALID"
STALE = "STALE"
CURRENT = "CURRENT"
STATES = (UNKNOWN, INVALID, STALE, CURRENT)


def _aware_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str) and value.strip():
        try:
            parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(timezone.utc)


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _ttl(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        ttl = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(ttl) or ttl <= 0:
        return None
    return ttl


def assess_freshness(
    evidence: Mapping[str, Any] | None,
    *,
    evaluated_at: datetime | str | None = None,
) -> dict[str, Any]:
    """Assess one explicit freshness declaration and fail closed on ambiguity."""
    raw = dict(evidence or {})
    evaluation_raw = evaluated_at if evaluated_at is not None else datetime.now(timezone.utc)
    evaluation = _aware_datetime(evaluation_raw)
    if evaluation is None:
        return {
            "state": INVALID,
            "reason": "Relógio de avaliação inválido",
            "reasons": ["EVALUATED_AT_INVALID"],
            "source": "",
            "observed_at": None,
            "available_at": None,
            "evaluated_at": None,
            "reference_at": None,
            "ttl_minutes": None,
            "age_minutes": None,
            "current": False,
            "agreement_verified": False,
            "execution_authorized": False,
        }

    missing: list[str] = []
    source_raw = raw.get("source")
    source = source_raw.strip() if isinstance(source_raw, str) else ""
    if not source:
        missing.append("SOURCE_UNKNOWN")

    observed_present = "observed_at" in raw and raw.get("observed_at") not in (None, "")
    ttl_present = "ttl_minutes" in raw and raw.get("ttl_minutes") not in (None, "")
    if not observed_present:
        missing.append("OBSERVED_AT_UNKNOWN")
    if not ttl_present:
        missing.append("TTL_UNKNOWN")
    if missing:
        return {
            "state": UNKNOWN,
            "reason": "Evidência temporal incompleta: " + ", ".join(missing),
            "reasons": missing,
            "source": source,
            "observed_at": None,
            "available_at": None,
            "evaluated_at": _iso(evaluation),
            "reference_at": None,
            "ttl_minutes": None,
            "age_minutes": None,
            "current": False,
            "agreement_verified": False,
            "execution_authorized": False,
        }

    observed = _aware_datetime(raw.get("observed_at"))
    ttl = _ttl(raw.get("ttl_minutes"))
    invalid: list[str] = []
    if observed is None:
        invalid.append("OBSERVED_AT_INVALID")
    if ttl is None:
        invalid.append("TTL_INVALID")

    available_present = "available_at" in raw and raw.get("available_at") not in (None, "")
    available = _aware_datetime(raw.get("available_at")) if available_present else None
    if available_present and available is None:
        invalid.append("AVAILABLE_AT_INVALID")

    if invalid:
        return {
            "state": INVALID,
            "reason": "Evidência temporal inválida: " + ", ".join(invalid),
            "reasons": invalid,
            "source": source,
            "observed_at": _iso(observed),
            "available_at": _iso(available),
            "evaluated_at": _iso(evaluation),
            "reference_at": None,
            "ttl_minutes": ttl,
            "age_minutes": None,
            "current": False,
            "agreement_verified": False,
            "execution_authorized": False,
        }

    assert observed is not None and ttl is not None
    if observed > evaluation:
        invalid.append("OBSERVED_AT_IN_FUTURE")
    if available is not None:
        if available < observed:
            invalid.append("AVAILABLE_BEFORE_OBSERVED")
        if available > evaluation:
            invalid.append("AVAILABLE_AT_IN_FUTURE")
    if invalid:
        return {
            "state": INVALID,
            "reason": "Evidência temporal inválida: " + ", ".join(invalid),
            "reasons": invalid,
            "source": source,
            "observed_at": _iso(observed),
            "available_at": _iso(available),
            "evaluated_at": _iso(evaluation),
            "reference_at": None,
            "ttl_minutes": ttl,
            "age_minutes": None,
            "current": False,
            "agreement_verified": False,
            "execution_authorized": False,
        }

    reference = available or observed
    age = (evaluation - reference).total_seconds() / 60.0
    if not math.isfinite(age) or age < 0:
        return {
            "state": INVALID,
            "reason": "Idade temporal inválida",
            "reasons": ["AGE_INVALID"],
            "source": source,
            "observed_at": _iso(observed),
            "available_at": _iso(available),
            "evaluated_at": _iso(evaluation),
            "reference_at": _iso(reference),
            "ttl_minutes": ttl,
            "age_minutes": None,
            "current": False,
            "agreement_verified": False,
            "execution_authorized": False,
        }

    state = CURRENT if age < ttl else STALE
    reason = (
        f"Atual: {age:.1f} min de {ttl:.1f} min"
        if state == CURRENT
        else f"Vencido: {age:.1f} min para TTL de {ttl:.1f} min"
    )
    return {
        "state": state,
        "reason": reason,
        "reasons": [] if state == CURRENT else ["TTL_EXPIRED"],
        "source": source,
        "observed_at": _iso(observed),
        "available_at": _iso(available),
        "evaluated_at": _iso(evaluation),
        "reference_at": _iso(reference),
        "ttl_minutes": round(ttl, 6),
        "age_minutes": round(age, 6),
        "current": state == CURRENT,
        "agreement_verified": False,
        "execution_authorized": False,
    }


def summarize_freshness(reports: Sequence[Mapping[str, Any]] | None) -> dict[str, Any]:
    """Summarize freshness without converting recency into execution authority."""
    rows = [dict(row or {}) for row in (reports or [])]
    counts = {state: 0 for state in STATES}
    reasons: list[str] = []
    ages: list[float] = []

    for row in rows:
        state = str(row.get("state") or UNKNOWN).upper()
        if state not in counts:
            state = INVALID
        counts[state] += 1
        for reason in row.get("reasons", []) or []:
            token = str(reason or "").strip()
            if token and token not in reasons:
                reasons.append(token)
        age = row.get("age_minutes")
        if not isinstance(age, bool):
            try:
                value = float(age)
            except (TypeError, ValueError):
                value = math.nan
            if math.isfinite(value) and value >= 0:
                ages.append(value)

    if not rows:
        overall = UNKNOWN
        if "NO_FRESHNESS_EVIDENCE" not in reasons:
            reasons.append("NO_FRESHNESS_EVIDENCE")
    elif counts[INVALID]:
        overall = INVALID
    elif counts[UNKNOWN]:
        overall = UNKNOWN
    elif counts[STALE]:
        overall = STALE
    else:
        overall = CURRENT

    return {
        "state": overall,
        "total": len(rows),
        "current": counts[CURRENT],
        "stale": counts[STALE],
        "unknown": counts[UNKNOWN],
        "invalid": counts[INVALID],
        "counts": counts,
        "reasons": reasons,
        "oldest_age_min": round(max(ages), 6) if ages else None,
        "freshest_age_min": round(min(ages), 6) if ages else None,
        "all_current": bool(rows) and overall == CURRENT,
        "agreement_verified": False,
        "execution_authorized": False,
        "interpretation": (
            "Atualidade temporal não prova concordância entre fontes e não autoriza operação."
        ),
    }


__all__ = [
    "UNKNOWN",
    "INVALID",
    "STALE",
    "CURRENT",
    "STATES",
    "assess_freshness",
    "summarize_freshness",
]
