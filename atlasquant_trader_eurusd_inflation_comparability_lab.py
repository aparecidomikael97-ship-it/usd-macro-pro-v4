"""Fail-closed two-currency inflation context for EUR/USD (read-only LAB).

Eurostat HICP YoY and BLS CPI-U NSA-derived YoY are NOT interchangeable.
Observations from different months and methods must never manufacture a
currency strength ranking or an executable EUR/USD directional bias.
"""
from __future__ import annotations

from typing import Any, Mapping
from math import isfinite
import re

SCHEMA = "ATLASQUANT_TRADER_EURUSD_INFLATION_COMPARABILITY_LAB_V1"


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_BLOCKED", "reason": reason,
        "pair": "EUR/USD", "base_currency": "EUR", "quote_currency": "USD",
        "currency_direction_proven": False, "methodologically_comparable": False,
        "causal_macro_explanation_proven": False,
        "release_instant_comparison_proven": False,
        "point_in_time_vintage_verified": False, "consensus_attested": False,
        "price_spot_independently_verified": False,
        "operational_bias": "AGUARDAR", "trade_authorized": False,
        "can_feed_live_radar": False, "worker_enabled": False,
        "scheduler_enabled": False, "publishable": False,
        "external_http_requests": 0, "new_cost_brl": 0,
    }


def compare_eurusd_inflation_context_lab(
    euro: Any, usd: Any,
) -> dict[str, Any]:
    """Summarize supplied parsed snapshots, never fetch or rank currencies."""
    if not isinstance(euro, Mapping) or not isinstance(usd, Mapping):
        return _blocked("MISSING_OR_INVALID_CURRENCY_INPUT")
    if (euro.get("state") != "LAB_EUR_HICP_CURRENT_JSONSTAT_QUARANTINED"
            or euro.get("currency") != "EUR"
            or euro.get("source") != "EUROSTAT"
            or euro.get("source_dataset") != "prc_hicp_minr"):
        return _blocked("EURO_HICP_SOURCE_OR_STATUS_INVALID")
    if (usd.get("state") != "LAB_CURRENT_US_BLS_CPIU_INDEX_QUARANTINED"
            or usd.get("currency") != "USD"
            or usd.get("source") != "US_BLS"
            or usd.get("series_id") != "CUUR0000SA0"):
        return _blocked("US_CPIU_SOURCE_OR_STATUS_INVALID")
    rows = euro.get("historical_months_observed_not_historical_vintages")
    if not isinstance(rows, list) or not rows or len(rows) > 3:
        return _blocked("EUR_HICP_MONTHS_MISSING")
    latest_eur = rows[-1]
    if not isinstance(latest_eur, Mapping):
        return _blocked("EUR_HICP_LATEST_MONTH_INVALID")
    eur_period = latest_eur.get("period")
    eur_rate = latest_eur.get("annual_inflation_percent")
    eur_flag = latest_eur.get("status_flag")
    usd_period = usd.get("latest_period")
    usd_rate = usd.get("derived_yoy_percent_from_same_month_indices")
    period_pattern = r"^[0-9]{4}-(0[1-9]|1[0-2])$"
    if (not isinstance(eur_period, str) or not re.fullmatch(period_pattern, eur_period)
            or not isinstance(usd_period, str) or not re.fullmatch(period_pattern, usd_period)
            or eur_flag not in ("", "e")
            or isinstance(eur_rate, bool) or not isinstance(eur_rate, (int, float))
            or not isfinite(eur_rate)):
        return _blocked("BAD_PERIOD_OR_EURO_INFLATION_VALUE")
    if usd_rate is not None:
        if usd.get("prior_year_month_observed") is not True:
            return _blocked("DERIVED_US_RATE_WITHOUT_PRIOR_YEAR_MONTH")
        try:
            numeric_usd_rate = float(usd_rate)
        except (ValueError, TypeError, OverflowError):
            return _blocked("INVALID_DERIVED_US_RATE")
        if not -50 <= numeric_usd_rate <= 100:
            return _blocked("DERIVED_US_RATE_OUT_OF_BOUNDS")
    same_period = eur_period == usd_period
    blockers = [
        "HICP_VS_CPI_U_METHODS_NOT_EQUIVALENT",
        "MONTHLY_RELEASE_INSTANTS_UNATTESTED",
        "PRE_EVENT_CONSENSUS_MISSING",
        "NO_POINT_IN_TIME_REVISION_EVIDENCE",
        "NO_INDEPENDENT_FX_PRICE_AND_OOS_TEST",
    ]
    if not same_period:
        blockers.insert(0, "LATEST_EURO_AND_US_MONTHS_DIFFER")
    if usd_rate is None:
        blockers.insert(0, "US_SAME_MONTH_PRIOR_YEAR_NOT_AVAILABLE")
    if eur_flag == "e":
        blockers.insert(0, "EUR_LAST_HICP_OBSERVATION_ESTIMATED")
    out = _blocked("TWO_OBSERVATIONS_ARE_NOT_AN_OPERATIONAL_FX_BIAS")
    out.update({
        "state": "LAB_TWO_CURRENCY_INFLATION_EVIDENCE_ONLY",
        "eur": {
            "series": "EUROSTAT_HICP_ECOICOP_V2_YOY",
            "month": eur_period, "observed_yoy_percent_claim": eur_rate,
            "flag": eur_flag,
            "estimate_not_final": eur_flag == "e",
        },
        "usd": {
            "series": "BLS_CPI_U_NSA_INDEX_DERIVED_YOY",
            "month": usd_period, "derived_yoy_percent_claim": usd_rate,
            "prior_year_same_month_observed": bool(usd.get("prior_year_month_observed")),
            "rate_not_direct_bls_api_value": True,
        },
        "observation_months_aligned": same_period,
        "source_http_observations_declared": {
            "EUR": euro.get("current_http_response_observed") is True,
            "USD": usd.get("current_http_response_observed") is True,
        },
        "comparison_blockers": blockers,
        "comparison_difference_percentage_points": None,
        "inflation_ranking_of_currencies": None,
        "news_or_geopolitics_verified": False,
        "economic_fundamentals_fully_covered": False,
    })
    return out


__all__ = ["SCHEMA", "compare_eurusd_inflation_context_lab"]
