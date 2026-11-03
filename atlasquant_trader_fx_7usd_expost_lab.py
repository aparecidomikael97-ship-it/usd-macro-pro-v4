"""Research-only, ex-post G8 relative-return algebra from seven USD legs.

This module can describe movements implied by a quarantined legacy cache.
It CANNOT prove that any candle close was available at the timestamp printed
in the legacy JSON, nor that derived crosses are independent market quotes.
It does not create a forecast, bias, top-10, confidence score, trading signal,
live data connection or real accuracy metric.
"""
from __future__ import annotations

from datetime import datetime, timezone
from math import isfinite, log
from typing import Any, Mapping

from atlasquant_fx_universe import CURRENCIES, OFFICIAL_PAIRS, split_pair
from atlasquant_trader_fx_legacy_cache_audit_lab import (
    USD_LEGS, audit_legacy_fx_daily_cache_lab,
)

SCHEMA = "ATLASQUANT_FX_7_USD_LEGS_EXPOST_LAB_V1"
PAIRS = tuple(USD_LEGS)
MAX_LOOKBACK_RECORDS = 2000


def _instant(value: Any) -> datetime | None:
    if not isinstance(value, str) or not 10 <= len(value) <= 60:
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except (ValueError, OverflowError):
        return None
    return parsed.astimezone(timezone.utc) if parsed.tzinfo is not None else None


def _value(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    f = float(value)
    return f if isfinite(f) and 0 < f <= 1e8 else None


def _refuse(reason: str, audit: Mapping[str, Any] | None = None) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_REJECTED_NO_EXPOST_VIEW",
        "reason": reason, "leg_coverage": len(PAIRS),
        "candle_audit_state": audit.get("state") if audit else None,
        "relative_currency_moves_bp": {},
        "pair_views": {},
        "legacy_usd_leg_series": 0,
        "algebraically_implied_pairs": 0,
        "daily_bias_validated": False, "monthly_bias_validated": False,
        "weekly_bias_validated": False,
        "historical_oos_proven": False, "market_data_verified": False,
        "trading_enabled": False, "worker_enabled": False,
        "scheduler_enabled": False,
    }


def describe_7usd_legs_expost_lab(
    payload: Any, *, start_utc: str, end_utc: str, at: datetime,
) -> dict[str, Any]:
    """Describe close-to-close past movement; no causal prediction is produced.

    The caller specifies two historical bar labels (UTC with explicit
    offsets). These are NOT independently attested bar close times. The full
    cache must pass structural checks; only the seven observed USD crosses
    are accepted. 21 other pair returns remain mathematical implications.
    """
    if not isinstance(at, datetime) or at.tzinfo is None:
        raise ValueError("Research evaluation must have explicit timezone")
    now = at.astimezone(timezone.utc)
    start, end = _instant(start_utc), _instant(end_utc)
    if start is None or end is None or not start < end <= now:
        return _refuse("Historical window missing, reversed or future-dated")
    if not isinstance(payload, Mapping) or not isinstance(payload.get("pairs"), Mapping):
        return _refuse("Legacy cache missing pairs")
    raw = payload["pairs"]
    if set(raw) != set(PAIRS):
        return _refuse("This view requires exactly the seven observed canonical USD legs")
    audit = audit_legacy_fx_daily_cache_lab(payload, at=now)
    if (not audit["aligned_candle_dates"] or
            any(not audit["pairs"].get(pair, {}).get("structurally_valid", False)
                for pair in PAIRS)):
        return _refuse("Invalid/sparse/unordered/asynchronous USD-leg cache", audit)
    deltas: dict[str, float] = {}
    observations = None
    for pair in PAIRS:
        rows = raw[pair]["records"]
        if not isinstance(rows, list) or not 2 <= len(rows) <= MAX_LOOKBACK_RECORDS:
            return _refuse("Insufficient or oversized historical candle list", audit)
        by_instant = {_instant(row["datetime"]): row for row in rows}
        if None in by_instant or start not in by_instant or end not in by_instant:
            return _refuse("Specified endpoints are not both observed in every USD leg", audit)
        first, last = by_instant[start], by_instant[end]
        a, b = _value(first.get("close")), _value(last.get("close"))
        if a is None or b is None:
            return _refuse("Invalid historical closing prices", audit)
        delta = log(b / a)
        if not isfinite(delta) or abs(delta) > 0.5:
            return _refuse("Unbounded historical leg movement", audit)
        deltas[pair] = delta
        if observations is None:
            observations = len(rows)
    # For each non-USD currency C, g[USD/C] is positive when USD strengthens.
    # If the observed market convention is C/USD, invert that log-return.
    dollar_over = {}
    for pair in PAIRS:
        base, quote = split_pair(pair)
        if base == "USD":
            dollar_over[quote] = deltas[pair]
        elif quote == "USD":
            dollar_over[base] = -deltas[pair]
        else:
            return _refuse("Unexpected non-dollar instrument", audit)
    if set(dollar_over) != set(CURRENCIES) - {"USD"}:
        return _refuse("Insufficient currency coverage from dollar legs", audit)
    # Gauge-invariant centered reconstruction: sum_c x_c = 0 and
    # x_USD - x_c = observed USD/c log-return for each other currency.
    usd = sum(dollar_over.values()) / len(CURRENCIES)
    factors = {"USD": usd}
    for cc, r in dollar_over.items():
        factors[cc] = usd - r
    if abs(sum(factors.values())) > 1e-10:
        return _refuse("Failed centered-currency invariant", audit)
    pairs = {}
    for pair in OFFICIAL_PAIRS:
        a, b = split_pair(pair)
        derived = pair not in PAIRS
        reconstructed = factors[a] - factors[b]
        if not derived and abs(reconstructed - deltas[pair]) > 1e-10:
            return _refuse("Observed leg failed algebraic parity", audit)
        pairs[pair] = {
            "change_bp": round(reconstructed * 10000, 5),
            "classification": ("IMPLIED_ALGEBRAIC_NOT_INDEPENDENT"
                               if derived else "OBSERVED_LEG_UNVERIFIED_CACHE"),
            "observed_independently": False,  # provenance never attested
            "historically_available_at_bar_time_verified": False,
        }
    order = sorted(CURRENCIES, key=lambda c: (-factors[c], c))
    return {
        "schema": SCHEMA, "state": "LAB_EXPOST_UNVERIFIED_DESCRIPTIVE",
        "start_bar_label_utc": start.isoformat(),
        "end_bar_label_utc": end.isoformat(),
        "evaluated_at_utc": now.isoformat(),
        "source_file_not_provider_evidence": True,
        "bar_labels_are_attested_close_times": False,
        "historical_price_availability_verified": False,
        "legacy_usd_leg_series": len(PAIRS),
        "algebraically_implied_pairs": len(OFFICIAL_PAIRS) - len(PAIRS),
        "independently_verified_market_quotes": 0,
        "relative_currency_moves_bp": {
            cc: round(factors[cc] * 10000, 5) for cc in CURRENCIES
        },
        "expost_relative_order_not_a_forecast": order,
        "pair_views": pairs,
        "leg_coverage": len(PAIRS),
        "bars_per_leg": observations,
        "weekend_bar_labels_flagged": audit["weekend_dated_bars"],
        "audit_blockers": audit["blockers"],
        "candle_audit_state": audit["state"],
        "daily_bias_validated": False, "weekly_bias_validated": False,
        "monthly_bias_validated": False,
        "historical_oos_proven": False, "market_data_verified": False,
        "trading_enabled": False, "worker_enabled": False,
        "scheduler_enabled": False,
        "why_not": "Seven USD-leg close labels cannot independently attest 28"
                   " prices, historical availability, market origin or directional accuracy.",
    }


__all__ = ["SCHEMA", "PAIRS", "describe_7usd_legs_expost_lab"]
