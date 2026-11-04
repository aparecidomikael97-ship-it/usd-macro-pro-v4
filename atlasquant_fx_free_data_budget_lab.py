"""Offline free-tier Forex data capacity estimator (no API or token).

Conservative 24h worst-case scheduling math for Twelve Data Basic terms
observed on 2026-11-04. Limits are a dated research assumption, not a
live entitlement, license, authenticated provider, or billing authorization.
"""
from __future__ import annotations

from math import ceil
from typing import Any, Sequence

from atlasquant_fx_universe import OFFICIAL_PAIRS

SCHEMA = "ATLASQUANT_FX_FREE_RESEARCH_BUDGET_LAB_V1"
ASSUMPTION_DATE = "2026-11-04"
API_CREDITS_PER_MINUTE = 8
API_CREDITS_PER_DAY = 800
TIME_SERIES_CREDITS_PER_SYMBOL = 1
REFERENCE_URL = "https://twelvedata.com/pricing"
EUR_ANCHORS = frozenset(pair for pair in OFFICIAL_PAIRS if "EUR" in pair.split("/"))
UNIVERSE = frozenset(OFFICIAL_PAIRS)


def _base(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "state": "BLOCKED",
        "reason": reason,
        "assumptions_as_of": ASSUMPTION_DATE,
        "provider_plan_claim": "TWELVE_DATA_BASIC_FREE_RESEARCH_UNVERIFIED",
        "limits_source": REFERENCE_URL,
        "api_credits_per_minute": API_CREDITS_PER_MINUTE,
        "api_credits_per_day": API_CREDITS_PER_DAY,
        "credits_per_symbol_per_poll": TIME_SERIES_CREDITS_PER_SYMBOL,
        "publishable": False,
        "display_authorized": False,
        "provider_authenticated": False,
        "data_coverage_verified": False,
        "price_accuracy_verified": False,
        "market_data_connected": False,
        "trade_authorized": False,
    }


def estimate_free_fx_collection(
    symbols: Sequence[str], *, poll_minutes: int,
) -> dict[str, Any]:
    """Estimate *one-symbol-one-credit* /time_series sampling, 24h per day.

    A batch request does not waive per-symbol credits. Results are merely
    capacity research and cannot be promoted to the operational 28-pair Radar.
    """
    blocked = _base("INVALID_RESEARCH_REQUEST")
    if not isinstance(symbols, (list, tuple)):
        return blocked
    selected = tuple(symbols)
    if (not selected or len(selected) > 28 or
            any(not isinstance(s, str) for s in selected) or
            len(set(selected)) != len(selected) or
            not set(selected).issubset(UNIVERSE)):
        return blocked
    if (isinstance(poll_minutes, bool) or not isinstance(poll_minutes, int)
            or poll_minutes <= 0 or poll_minutes > 1440
            or 1440 % poll_minutes != 0):
        return blocked
    polls = 1440 // poll_minutes
    count = len(selected)
    total = polls * count * TIME_SERIES_CREDITS_PER_SYMBOL
    minute_windows = ceil(count / API_CREDITS_PER_MINUTE)
    daily_fits = total <= API_CREDITS_PER_DAY
    simultaneous_fits = count <= API_CREDITS_PER_MINUTE
    eur_only = set(selected) == EUR_ANCHORS
    full_28 = set(selected) == UNIVERSE
    if not daily_fits:
        state, reason = "BLOCKED", "EXCEEDS_FREE_DAILY_CREDITS"
    elif not simultaneous_fits:
        state, reason = "BLOCKED", "CANNOT_COLLECT_WITHIN_ONE_MINUTE_QUOTA"
    else:
        state, reason = "RESEARCH_CAPACITY_ONLY", "CAPACITY_FITS_LICENSE_AND_COVERAGE_UNVERIFIED"
    out = _base(reason)
    out.update({
        "state": state,
        "poll_minutes": poll_minutes,
        "polls_per_24h": polls,
        "selected_pairs": list(selected),
        "observed_pair_slots": count,
        "credits_per_24h": total,
        "remaining_credits_per_24h": max(0, API_CREDITS_PER_DAY - total),
        "minute_quota_windows_for_all_pairs": minute_windows,
        "fits_daily_credit_budget": daily_fits,
        "fits_one_minute_capture": simultaneous_fits,
        "all_28_direct_pair_slots": full_28,
        "seven_eur_anchor_slots": eur_only,
        "other_crosses_mathematically_derivable": 21 if eur_only else 0,
        "derived_crosses_are_independent_quotes": False,
        "operational_m15_radar_ready": False,
        "notice": (
            "Capacity estimate only. Basic non-display terms, symbol/interval "
            "entitlement and independent market prices require separate proof."
        ),
    })
    return out


__all__ = ["SCHEMA", "EUR_ANCHORS", "estimate_free_fx_collection"]
