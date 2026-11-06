"""Never mistake model nowcasts or long-horizon surveys for CPI event consensus.

Joins already pinned documentary sources and the 28-pair D1/W1 readiness
catalogue. Forecast horizon, population and target indicator are explicit.
No new data fetch, no official CPI actual, no market surprise or FX signal.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from atlasquant_fx_universe import OFFICIAL_PAIRS, split_pair
from atlasquant_trader_g8_cpi_side_by_side_readiness_lab import (
    inspect_g8_cpi_side_by_side_readiness_lab,
)
from atlasquant_trader_eurusd_sep2026_expectations_mismatch_lab import (
    inspect_eurusd_sep2026_expectations_mismatch_lab,
)
from atlasquant_trader_us_octnov2026_clevelandfed_two_horizons_lab import (
    SOURCE_URL as CLEVELAND_MODEL_SOURCE_URL,
    inspect_us_octnov2026_clevelandfed_two_horizons_lab,
)

SCHEMA = "ATLASQUANT_TRADER_G8_CPI_EVENT_CONSENSUS_ELIGIBILITY_LAB_V1"
READINESS_READY = "LAB_28_PAIRS_WITH_TWO_SIDED_CPI_DOCUMENTS_AND_NEXT_EVENTS_NO_BIAS"
SURVEY_READY = "LAB_OFFICIAL_SURVEY_CONTEXT_WITH_RELEASE_CONSENSUS_MISMATCH"
FORECAST_STATES = frozenset((
    "LAB_TWO_SEPARATE_PRE_RELEASE_WINDOWS",
    "LAB_OCT_AFTER_SCHEDULE_NOV_BEFORE_SCHEDULE",
    "LAB_BOTH_RELEASE_SCHEDULES_PASSED_NO_OFFICIAL_ACTUAL",
))
EXPECTED_SURVEYS = {
    "EUR": ("2026Q3", "QUARTERLY", "SELECTED_MONETARY_ANALYSTS", 3.2),
    "USD": ("ONE_YEAR_AHEAD_FROM_SEPTEMBER_2026", "ROLLING_ONE_YEAR_AHEAD", "HOUSEHOLDS", 3.9),
}
EXPECTED_USD_MODELS = (("2026-10", 3.74), ("2026-11", 3.88))
EVENT_CONSENSUS_BLOCKERS = (
    "NO_EXACT_EVENT_ANALYST_CONSENSUS_WITH_PRE_RELEASE_WITNESS",
    "NO_INDEPENDENT_ORIGINAL_SOURCE_BYTES_AND_CAPTURE_TIME",
    "NO_AUTHENTICATED_EVENT_ACTUAL_FOR_SURPRISE",
    "NO_VALIDATED_FX_FORWARD_PRICE_EDGE",
)


def _base(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_BLOCKED", "reason": reason,
        "as_of_utc": None, "research_date": "2026-11-06",
        "pair_count": 0, "source_model_forecast_count": 0,
        "source_mismatched_survey_count": 0,
        "pairs_with_usd_model_context": 0,
        "pairs_with_eur_survey_context": 0,
        "pairs_with_usd_household_context": 0,
        "pairs_with_either_usd_or_eur_context": 0,
        "pairs_without_either_context": 0,
        "exact_pre_event_market_consensus_by_currency": {},
        "official_cpi_actual_for_upcoming_events": {},
        "market_surprises": {}, "model_forecast_errors": {},
        "pair_rows": [], "ranked_currencies": [],
        "best_pair_of_day": None,
        "validated_forward_prediction_count": 0,
        "validated_accuracy": None,
        "fx_bias": None, "operational_bias": "AGUARDAR",
        "can_feed_live_radar": False, "trade_authorized": False,
        "publishable": False, "worker_enabled": False,
        "scheduler_enabled": False, "http_requests": 0, "new_cost_brl": 0,
        "point_in_time_document_origins_independently_witnessed": False,
    }


def inspect_g8_cpi_event_consensus_eligibility_lab(
    *, five_calendar_casebook_raw: Any, three_calendar_casebook_raw: Any,
    eurusd_macro_casebook_raw: Any, gbpjpy_macro_casebook_raw: Any,
    remaining_four_macro_casebook_raw: Any,
    october_us_model_receipt_raw: Any, november_us_model_receipt_raw: Any,
    survey_expectations_casebook_raw: Any,
    september_policy_casebook_raw: Any, september_cpi_casebook_raw: Any,
    as_of_utc: Any,
) -> dict[str, Any]:
    """Assess whether candidate forecasts match the *exact upcoming release*."""
    out = _base("INVALID_CLOCK_OR_UNATTESTED_OR_INCONSISTENT_INPUTS")
    if (not isinstance(as_of_utc, datetime) or as_of_utc.tzinfo is None
            or as_of_utc.utcoffset() is None or len(OFFICIAL_PAIRS) != 28):
        return out
    now = as_of_utc.astimezone(timezone.utc)
    readiness = inspect_g8_cpi_side_by_side_readiness_lab(
        five_calendar_casebook_raw=five_calendar_casebook_raw,
        three_calendar_casebook_raw=three_calendar_casebook_raw,
        eurusd_macro_casebook_raw=eurusd_macro_casebook_raw,
        gbpjpy_macro_casebook_raw=gbpjpy_macro_casebook_raw,
        remaining_four_macro_casebook_raw=remaining_four_macro_casebook_raw,
        as_of_utc=now,
    )
    if readiness["state"] == "LAB_JOIN_NOT_ADMISSIBLE_ASOF":
        out.update({"state": "LAB_CONSENSUS_RESEARCH_NOT_VISIBLE_ASOF",
                    "reason": "RESEARCH_CANNOT_LEAK_BEFORE_2026_11_07_UTC"})
        return out
    if readiness["state"] != READINESS_READY or readiness["pair_count"] != 28:
        return out
    surveys = inspect_eurusd_sep2026_expectations_mismatch_lab(
        survey_expectations_casebook_raw,
        policy_casebook_raw=september_policy_casebook_raw,
        inflation_casebook_raw=september_cpi_casebook_raw,
        as_of_utc=now,
    )
    forecasts = inspect_us_octnov2026_clevelandfed_two_horizons_lab(
        october_us_model_receipt_raw, november_us_model_receipt_raw,
        as_of_utc=now,
    )
    if (surveys["state"] != SURVEY_READY
            or forecasts["state"] not in FORECAST_STATES
            or len(forecasts["forecast_rows_documentary_only"]) != 2
            or len(surveys["visible_official_survey_context_not_cpi_consensus"]) != 2):
        return out
    observations = {s["currency"]: s
                    for s in surveys["visible_official_survey_context_not_cpi_consensus"]}
    model_rows = forecasts["forecast_rows_documentary_only"]
    if (set(observations) != {"EUR", "USD"}
            or tuple((x["forecast_month"], x["model_forecast_yoy_percent"])
                     for x in model_rows) != EXPECTED_USD_MODELS):
        return out
    for currency, (period, granularity, population, value) in EXPECTED_SURVEYS.items():
        s = observations[currency]
        if (s["target_period"] != period
                or s["target_granularity"] != granularity
                or s["respondent_population"] != population
                or s["median_survey_expectation_percent_not_cpi_event_consensus"] != value):
            return out

    usd_context = [{
        "source_kind": "CLEVELAND_FED_STATISTICAL_CPI_NOWCAST_NOT_CONSENSUS",
        "source_url": CLEVELAND_MODEL_SOURCE_URL,
        "target_period": x["forecast_month"],
        "reference_period_type": "MONTH",
        "target_metric": "CPI_U_ALL_ITEMS_HEADLINE_YEAR_OVER_YEAR_PERCENT_CHANGE",
        "target_metric_officially_publishable": (
            False if x["forecast_month"] == "2026-10" else None),
        "metric_availability_reason": (
            "BLS_OCT2025_HEADLINE_BASELINE_NOT_PUBLISHED"
            if x["forecast_month"] == "2026-10" else None),
        "forecast_percent_model_documentary_only": x["model_forecast_yoy_percent"],
        "target_release_scheduled_utc": x["scheduled_first_release_utc"],
        "release_window": x["release_window"],
        "qualifies_as_exact_market_event_consensus": False,
    } for x in model_rows]
    survey_contexts = {
        currency: [{
            "source_kind": ("ECB_SMA_QUARTERLY_ANALYST_MEDIAN_NOT_MONTHLY_EVENT_CONSENSUS"
                            if currency == "EUR"
                            else "NYFED_SCE_HOUSEHOLD_ONE_YEAR_NOT_MONTHLY_EVENT_CONSENSUS"),
            "target_period": s["target_period"],
            "reference_period_type": s["target_granularity"],
            "forecast_percent_survey_documentary_only": (
                s["median_survey_expectation_percent_not_cpi_event_consensus"]),
            "source_url": s["source_url"],
            "blocked_as_event_consensus_reason": s[
                "blocked_as_cpi_release_consensus_reason"],
            "qualifies_as_exact_market_event_consensus": False,
        }] for currency, s in observations.items()
    }

    rows = []
    for original in readiness["pair_rows"]:
        pair = original["pair"]
        base, quote = split_pair(pair)
        candidate_contexts = {
            "BASE": ([*usd_context, *survey_contexts["USD"]] if base == "USD"
                     else list(survey_contexts["EUR"]) if base == "EUR" else []),
            "QUOTE": ([*usd_context, *survey_contexts["USD"]] if quote == "USD"
                      else list(survey_contexts["EUR"]) if quote == "EUR" else []),
        }
        rows.append({
            "pair": pair, "base": base, "quote": quote,
            "base_cpi_documentary_reference_period": (
                original["base_last_documentary_cpi"]["reference_period"]),
            "quote_cpi_documentary_reference_period": (
                original["quote_last_documentary_cpi"]["reference_period"]),
            "next_cpi_date_for_pair": original["next_cpi_date_for_pair"],
            "candidate_expectations_context_by_role": candidate_contexts,
            "market_consensus_for_exact_next_cpi_release_by_role": {
                "BASE": None, "QUOTE": None,
            },
            "actual_minus_market_consensus_percentage_points": None,
            "model_nowcast_ex_post_error_percentage_points": None,
            "missing_prerequisites": [*EVENT_CONSENSUS_BLOCKERS],
            "D1": "AGUARDAR", "W1": "AGUARDAR",
            "relative_macro_score": None, "fx_bias": None,
            "trade_authorized": False,
        })
    usd_n = sum("USD" in (r["base"], r["quote"]) for r in rows)
    eur_n = sum("EUR" in (r["base"], r["quote"]) for r in rows)
    both = sum(set((r["base"], r["quote"])) == {"EUR", "USD"} for r in rows)
    either = usd_n + eur_n - both
    if (len(rows) != 28 or (usd_n, eur_n, both, either) != (7, 7, 1, 13)):
        return out
    out.update({
        "state": "LAB_TWO_MODEL_HORIZONS_TWO_MISMATCHED_SURVEYS_NO_CPI_EVENT_CONSENSUS",
        "reason": "MODEL_AND_LONG_HORIZON_SURVEYS_ARE_NOT_SAME_EVENT_MARKET_FORECAST",
        "as_of_utc": now.isoformat(),
        "pair_count": len(rows),
        "source_model_forecast_count": 2,
        "source_mismatched_survey_count": 2,
        "pairs_with_usd_model_context": usd_n,
        "pairs_with_eur_survey_context": eur_n,
        "pairs_with_usd_household_context": usd_n,
        "pairs_with_either_usd_or_eur_context": either,
        "pairs_without_either_context": 28 - either,
        "pair_rows": rows,
    })
    return out


__all__ = ["SCHEMA", "EXPECTED_USD_MODELS", "EVENT_CONSENSUS_BLOCKERS",
           "inspect_g8_cpi_event_consensus_eligibility_lab"]
