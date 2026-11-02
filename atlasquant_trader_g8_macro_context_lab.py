"""LAB-only G8 macro coverage comparison across 28 canonical FX pairs.

Reuses synthetic point-in-time macro releases. Each currency has at most one
predeclared synthetic observation per fundamental GROUP (inflation, jobs,
central-bank policy, activity) to prevent post-hoc cherry-picking.

Compares evidence availability and disagreement, NOT macro strength,
rate differentials, a tradeable currency bias or accuracy in real markets.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Mapping

from atlasquant_fx_universe import CURRENCIES, OFFICIAL_PAIRS, split_pair
from atlasquant_trader_macro_surprise_pit_lab import (
    build_macro_point_in_time_evidence_lab,
)

SCHEMA = "ATLASQUANT_TRADER_G8_MACRO_COMPARISON_LAB_V1"
GROUPS = ("INFLATION", "EMPLOYMENT", "POLICY", "ACTIVITY")
GROUP_BY_INDICATOR = {
    **{x: "INFLATION" for x in ("CPI", "CORE_CPI", "PCE", "CORE_PCE", "PPI")},
    **{x: "EMPLOYMENT" for x in ("NFP", "ADP", "UNEMPLOYMENT", "WAGES")},
    "POLICY_RATE": "POLICY",
    **{x: "ACTIVITY" for x in ("GDP", "PMI", "ISM")},
}
MAX_EVENTS = len(CURRENCIES) * len(GROUPS)
MAX_AGE_DAYS = 90


def _utc(value: Any) -> datetime | None:
    if not isinstance(value, str) or len(value) > 60:
        return None
    try:
        t = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except (ValueError, OverflowError):
        return None
    return t.astimezone(timezone.utc) if t.tzinfo is not None else None


def _deny(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_REJECTED_MACRO_COMPARISON",
        "reason": reason, "currency_matrix": {}, "pair_comparisons": {},
        "synthetic_freeze_evidences": [],
        "real_historical_proven": False, "macro_relative_strength_proven": False,
        "statistical_edge_proven": False, "trade_authorized": False,
        "worker_enabled": False, "scheduler_enabled": False,
    }


def compare_g8_macro_coverage_lab(
    events: Any, *, forecast_issued_at: datetime,
    evaluated_at: datetime, freshness_days: int = MAX_AGE_DAYS,
) -> dict[str, Any]:
    """Render an evidence-coverage matrix without implicit directional scores.

    Expected event rows are exactly:
      {"preliminary": LAB_SYNTHETIC_MACRO_PRE, "actual_release": <fixture or None>}
    A currency/group can have one and only one declared indicator for
    this synthetic research snapshot. Actual + consensus are preserved
    with their original units, never compared as FX levels.
    """
    if not isinstance(forecast_issued_at, datetime) or forecast_issued_at.tzinfo is None:
        raise ValueError("Research cutoff requires an explicit timezone")
    if not isinstance(evaluated_at, datetime) or evaluated_at.tzinfo is None:
        raise ValueError("Evaluation clock requires an explicit timezone")
    if (isinstance(freshness_days, bool) or not isinstance(freshness_days, int)
            or not 1 <= freshness_days <= MAX_AGE_DAYS):
        raise ValueError("LAB freshness must be 1..90 whole days")
    issued = forecast_issued_at.astimezone(timezone.utc)
    now = evaluated_at.astimezone(timezone.utc)
    if issued > now:
        return _deny("Forecast cannot be issued in the future")
    if (not isinstance(events, (list, tuple)) or
            not 1 <= len(events) <= MAX_EVENTS):
        return _deny("No bounded synthetic macro event list")
    index: dict[tuple[str, str], dict[str, Any]] = {}
    identity = set()
    evidences = []
    for item in events:
        if not isinstance(item, Mapping) or set(item) != {"preliminary", "actual_release"}:
            return _deny("Unexpected macro envelope or retrospective field")
        result = build_macro_point_in_time_evidence_lab(
            item["preliminary"], item["actual_release"],
            forecast_issued_at=issued, evaluated_at=now,
        )
        if result["state"] not in (
            "LAB_MACRO_RELEASED_SYNTHETIC", "LAB_MACRO_FUTURE_SCHEDULE_ONLY",
        ):
            return _deny("Macro point-in-time validation failed: " + result["reason"])
        ev = result["freeze_evidence"]
        ccy, indicator = ev["currency"], ev["indicator_id"]
        group = GROUP_BY_INDICATOR.get(indicator)
        if ccy not in CURRENCIES or group not in GROUPS:
            return _deny("Unexpected macro indicator or currency")
        key = (ccy, group)
        event_id = ev["evidence_id"]
        if key in index or event_id in identity:
            return _deny("Duplicate currency/group or macro release; no cherry-picking")
        identity.add(event_id)
        released = ev["kind"] == "MACRO_ACTUAL_RELEASED"
        clock = _utc(ev["released_at_utc"]) if released else None
        if released and (clock is None or clock > issued):
            return _deny("Actual macro release is unavailable at decision")
        planned = _utc(ev["scheduled_release_at_utc"])
        if not released and (
            planned is None or planned <= issued or planned > issued + timedelta(days=30)
        ):
            return _deny("Future release exceeds bounded research calendar")
        age_days = (issued - clock).total_seconds() / 86400 if released else None
        stale = bool(released and age_days > freshness_days)
        index[key] = {
            "evidence_id": event_id, "currency": ccy, "group": group,
            "indicator_id": indicator, "unit": ev["unit"],
            "state": ("STALE_RELEASE" if stale else
                      "RELEASED_BEFORE_CUTOFF" if released else
                      "SCHEDULED_NOT_RELEASED"),
            "source": ev["source"], "previous": ev["previous"],
            "consensus": ev["consensus"],
            "actual": ev.get("actual") if released else None,
            "surprise": ev.get("surprise") if released else None,
            "surprise_comparison": (
                ev.get("surprise_comparison") if released else None
            ),
            "released_at_utc": clock.isoformat() if released else None,
            "captured_at_utc": ev["captured_at_utc"],
            "scheduled_release_at_utc": planned.isoformat() if planned else None,
            "age_days_at_cutoff": round(age_days, 4) if released else None,
            "fresh_for_context_only": released and not stale,
            "currency_direction": "UNDETERMINED",
            "market_price_verified": False,
        }
        evidences.append(ev)
    currencies = {}
    for ccy in CURRENCIES:
        columns = {group: index.get((ccy, group)) for group in GROUPS}
        currencies[ccy] = {
            "groups": columns,
            "fresh_released_groups": sum(
                bool(x and x["fresh_for_context_only"]) for x in columns.values()
            ),
            "pending_groups": sum(
                bool(x and x["state"] == "SCHEDULED_NOT_RELEASED")
                for x in columns.values()
            ),
            "missing_groups": [g for g, value in columns.items() if value is None],
            "currency_macro_side": "UNDETERMINED",
        }
    pair_views = {}
    for pair in OFFICIAL_PAIRS:
        base, quote = split_pair(pair)
        comparisons = {}
        complete = 0
        pending = 0
        for group in GROUPS:
            b = index.get((base, group))
            q = index.get((quote, group))
            if b is None or q is None:
                status = "INSUFFICIENT_BILATERAL_COVERAGE"
            elif (b["state"] == "SCHEDULED_NOT_RELEASED" or
                  q["state"] == "SCHEDULED_NOT_RELEASED"):
                status = "UNRELEASED_EVENT_PENDING"
                pending += 1
            elif not b["fresh_for_context_only"] or not q["fresh_for_context_only"]:
                status = "STALE_BILATERAL_CONTEXT"
            else:
                status = "BOTH_RELEASED_FRESH"
                complete += 1
            comparable_labels = bool(
                status == "BOTH_RELEASED_FRESH" and
                b["indicator_id"] == q["indicator_id"] and b["unit"] == q["unit"]
            )
            if comparable_labels:
                relationship = (
                    "SAME_RELEASE_RELATION" if
                    b["surprise_comparison"] == q["surprise_comparison"]
                    else "DIFFERENT_RELEASE_RELATION"
                )
            else:
                relationship = "NOT_COMPARABLE"
            comparisons[group] = {
                "status": status, "base": b, "quote": q,
                "matching_indicator_and_unit": comparable_labels,
                "surprise_relation": relationship,
                "bullish_or_bearish_currency_inference": "UNDETERMINED",
            }
        pair_views[pair] = {
            "pair": pair, "base_currency": base, "quote_currency": quote,
            "fundamental_groups": comparisons,
            "bilateral_fresh_groups": complete,
            "bilateral_pending_groups": pending,
            "macro_direction": "UNDETERMINED",
            "macro_strength_score": None,
            "rankable_as_signal": False,
        }
    return {
        "schema": SCHEMA, "state": "LAB_SYNTHETIC_G8_MACRO_CONTEXT_ONLY",
        "forecast_issued_at_utc": issued.isoformat(),
        "evaluated_at_utc": now.isoformat(),
        "groups": list(GROUPS), "currency_count": len(currencies),
        "pair_count": len(pair_views), "synthetic_event_count": len(evidences),
        "freshness_days_lab_only": freshness_days,
        "currency_matrix": currencies,
        "pair_comparisons": pair_views,
        "synthetic_freeze_evidences": evidences,
        "automatic_macro_vetoes": [],
        "independent_provider_validation": False,
        "real_historical_proven": False, "macro_relative_strength_proven": False,
        "statistical_edge_proven": False,
        "trade_authorized": False, "worker_enabled": False,
        "scheduler_enabled": False,
        "why_not": "Actual-consensus surprise is not a comparable G8 currency "
                   "strength score; levels, units, reaction regimes and rate "
                   "expectations must be modeled and validated separately.",
    }


__all__ = ["SCHEMA", "GROUPS", "compare_g8_macro_coverage_lab"]
