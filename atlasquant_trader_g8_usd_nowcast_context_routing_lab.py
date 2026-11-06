"""Route precommitted USD CPI model context to the correct 7 G8 FX crosses.

Macro documentation is not a currency-strength ranking. A USD-only inflation
model cannot determine relative EUR/USD, USD/JPY, or any W1/D1 direction. The
other 21 G8 crosses must not inherit USD context. All 28 retain AGUARDAR.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from atlasquant_fx_universe import CURRENCIES, OFFICIAL_PAIRS, split_pair
from atlasquant_trader_g8_pair_comparability_gate_lab import (
    inspect_g8_pair_comparability_gate_lab,
)
from atlasquant_trader_us_octnov2026_clevelandfed_two_horizons_lab import (
    inspect_us_octnov2026_clevelandfed_two_horizons_lab,
)

SCHEMA = "ATLASQUANT_TRADER_G8_28_PAIRS_USD_PRE_CPI_NOWCAST_CONTEXT_ROUTING_LAB_V1"
EXPECTED_USD_PAIRS = frozenset((
    "EUR/USD", "GBP/USD", "AUD/USD", "NZD/USD",
    "USD/JPY", "USD/CHF", "USD/CAD",
))
ACCEPTED_SOURCE_STATES = frozenset((
    "LAB_TWO_FORECAST_MONTHS_UNAVAILABLE_ASOF",
    "LAB_TWO_SEPARATE_PRE_RELEASE_WINDOWS",
    "LAB_OCT_AFTER_SCHEDULE_NOV_BEFORE_SCHEDULE",
    "LAB_BOTH_RELEASE_SCHEDULES_PASSED_NO_OFFICIAL_ACTUAL",
))


def _base(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_BLOCKED", "reason": reason,
        "as_of_utc": None,
        "pair_count": 0, "usd_pair_count": 0, "non_usd_pair_count": 0,
        "source_forecast_months": [],
        "usd_crosses_with_visible_context": 0,
        "non_usd_crosses_with_usd_context": 0,
        "relative_macro_comparisons_verified": 0,
        "eligible_for_fx_bias_count": 0,
        "pair_rows": [],
        "ranked_currencies": [], "best_pair_of_day": None,
        "validated_forward_prediction_count": 0,
        "validated_accuracy": None,
        "fx_bias": None, "operational_bias": "AGUARDAR",
        "can_feed_live_radar": False, "trade_authorized": False,
        "publishable": False, "worker_enabled": False,
        "scheduler_enabled": False, "http_requests": 0, "new_cost_brl": 0,
    }


def inspect_g8_usd_nowcast_context_routing_lab(
    *, oct_nowcast_receipt_raw: Any, nov_nowcast_receipt_raw: Any,
    eurusd_macro_casebook_raw: Any, gbpjpy_macro_casebook_raw: Any,
    remaining_four_macro_casebook_raw: Any, as_of_utc: Any,
) -> dict[str, Any]:
    """Annotate only the seven crosses containing USD; never produce bias."""
    out = _base("INVALID_CLOCK_UNIVERSE_OR_EVIDENCE_CHAIN")
    if (not isinstance(as_of_utc, datetime) or as_of_utc.tzinfo is None
            or as_of_utc.utcoffset() is None
            or len(CURRENCIES) != 8 or len(OFFICIAL_PAIRS) != 28
            or len(set(OFFICIAL_PAIRS)) != 28
            or {p for p in OFFICIAL_PAIRS if "USD" in split_pair(p)} != EXPECTED_USD_PAIRS):
        return out
    now = as_of_utc.astimezone(timezone.utc)
    forecast = inspect_us_octnov2026_clevelandfed_two_horizons_lab(
        oct_nowcast_receipt_raw, nov_nowcast_receipt_raw, as_of_utc=now,
    )
    macro = inspect_g8_pair_comparability_gate_lab(
        eurusd_casebook_raw=eurusd_macro_casebook_raw,
        gbpjpy_casebook_raw=gbpjpy_macro_casebook_raw,
        remaining_four_casebook_raw=remaining_four_macro_casebook_raw,
        as_of_utc=now,
    )
    if (forecast["state"] not in ACCEPTED_SOURCE_STATES
            or macro["state"] != "LAB_28_PAIR_COMPARABILITY_AUDIT_NO_FX_BIAS"
            or macro["pairs_in_universe"] != 28
            or len(macro["pair_rows"]) != 28
            or {r["pair"] for r in macro["pair_rows"]} != set(OFFICIAL_PAIRS)):
        return out

    forecasts = forecast["forecast_rows_documentary_only"]
    current_months = [x["forecast_month"] for x in forecasts
                      if x["release_window"] == "BEFORE_SCHEDULED_RELEASE"]
    rows = []
    for original in macro["pair_rows"]:
        pair = original["pair"]
        base, quote = split_pair(pair)
        has_usd = base == "USD" or quote == "USD"
        usd_role = "BASE" if base == "USD" else "QUOTE" if quote == "USD" else "NONE"
        visible = bool(forecasts) and has_usd
        rows.append({
            "pair": pair, "base": base, "quote": quote,
            "usd_role": usd_role,
            "historical_cpi_period_audit": original["inflation_period_audit"],
            "usd_pre_cpi_model_context_documentary_only": ([
                {
                    "forecast_month": x["forecast_month"],
                    "model_forecast_yoy_percent": x["model_forecast_yoy_percent"],
                    "scheduled_first_release_utc": x["scheduled_first_release_utc"],
                    "release_window": x["release_window"],
                } for x in forecasts] if visible else []),
            "current_pre_release_usd_forecast_months": (list(current_months) if visible else []),
            "matched_other_currency_same_event_consensus": False,
            "both_currency_pit_forecasts_and_policy_harmonized": False,
            "currency_strength_score": None,
            "relative_macro_score": None,
            "D1": "AGUARDAR", "W1": "AGUARDAR",
            "trade_authorized": False,
        })
    usd_visible = sum(bool(r["usd_pre_cpi_model_context_documentary_only"]) for r in rows)
    non_usd_with_context = sum(bool(r["usd_pre_cpi_model_context_documentary_only"])
                               for r in rows if r["usd_role"] == "NONE")
    if (len(rows) != 28 or sum(r["usd_role"] != "NONE" for r in rows) != 7
            or non_usd_with_context != 0 or usd_visible not in (0, 7)):
        return out
    out.update({
        "state": ("LAB_USD_DOCUMENTARY_CONTEXT_ROUTED_TO_7_CROSSES_NO_FX_BIAS"
                  if forecasts else "LAB_28_PAIRS_NO_PRE_CPI_FORECAST_VISIBLE_ASOF"),
        "reason": "ONE_SIDED_USD_MODEL_FORECAST_DOES_NOT_ESTABLISH_RELATIVE_CURRENCY_STRENGTH",
        "as_of_utc": now.isoformat(),
        "pair_count": 28, "usd_pair_count": 7, "non_usd_pair_count": 21,
        "source_forecast_months": [x["forecast_month"] for x in forecasts],
        "usd_crosses_with_visible_context": usd_visible,
        "non_usd_crosses_with_usd_context": 0,
        "pair_rows": rows,
    })
    return out


__all__ = ["SCHEMA", "EXPECTED_USD_PAIRS",
           "inspect_g8_usd_nowcast_context_routing_lab"]
