"""Label real pre-CPI surveys WITHOUT inventing same-release consensus.

ECB SMA 2026Q3 HICP and NY Fed household 1y-ahead inflation expectations are
real official observations, but NOT forecasts for the September CPI releases.
No fake (3.8-3.2) or (3.7-3.9) surprise, no HTTP or trading.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
from typing import Any

from atlasquant_trader_eurusd_sep2026_policy_inflation_timeline_lab import (
    inspect_eurusd_sep2026_policy_inflation_timeline_lab,
)

SCHEMA = "ATLASQUANT_TRADER_EURUSD_SEP2026_EXPECTATIONS_MISMATCH_GATE_LAB_V1"
CASE_SCHEMA = "ATLASQUANT_TRADER_EURUSD_SEP2026_EXPECTATIONS_MISMATCH_LAB_V1"
CASE_KIND = "TWO_OFFICIAL_SURVEY_RELEASE_REFERENCES_NOT_SEPTEMBER_CPI_EVENT_CONSENSUS"
PINNED_EXPECTATIONS_SHA256 = "5ba011bc33ec0c5f55dcf68cdacdb47377b3e854aca97165a9fac29c9b21929a"
EXPECTED = {
    "EUR": {
        "source_id": "ECB_SMA_SEP2026_HICP_Q3_ANALYST_MEDIAN",
        "agency": "EUROPEAN_CENTRAL_BANK",
        "source_url": "https://www.ecb.europa.eu/stats/ecb_surveys/sma/shared/pdf/ecb.smar260911_september.en.pdf",
        "publication_calendar_date": "2026-09-11",
        "conservative_available_at_utc": "2026-09-12T00:00:00Z",
        "survey_or_analysis_period": "2026-09_SMA_ROUND",
        "forecast_target_period": "2026Q3",
        "forecast_target_granularity": "QUARTERLY",
        "forecast_measure": "EA_HICP_QUARTERLY_YEAR_OVER_YEAR_MEDIAN",
        "respondent_population": "SELECTED_MONETARY_ANALYSTS",
        "median_forecast_percent": 3.2,
        "survey_response_count": 69,
        "reason_not_same_release_consensus": "QUARTERLY_HICP_FORECAST_IS_NOT_EXACT_SEPTEMBER_MONTHLY_HEADLINE_RELEASE",
    },
    "USD": {
        "source_id": "NYFED_SCE_SEP2026_HOUSEHOLD_ONE_YEAR_AHEAD",
        "agency": "FEDERAL_RESERVE_BANK_OF_NEW_YORK",
        "source_url": "https://www.newyorkfed.org/newsevents/news/research/2026/20261007.html",
        "publication_calendar_date": "2026-10-07",
        "conservative_available_at_utc": "2026-10-08T00:00:00Z",
        "survey_or_analysis_period": "2026-09",
        "forecast_target_period": "ONE_YEAR_AHEAD_FROM_SEPTEMBER_2026",
        "forecast_target_granularity": "ROLLING_ONE_YEAR_AHEAD",
        "forecast_measure": "HOUSEHOLD_EXPECTED_OVERALL_INFLATION_MEDIAN",
        "respondent_population": "HOUSEHOLDS",
        "median_forecast_percent": 3.9,
        "survey_response_count": None,
        "reason_not_same_release_consensus": "HOUSEHOLD_ONE_YEAR_AHEAD_EXPECTATION_IS_NOT_SEPTEMBER_2026_US_CPI_U_RELEASE_FORECAST",
    },
}
PROHIBITED = frozenset((
    "USD_CPI_SEP2026_3_7_MINUS_NYFED_SCE_3_9_AS_EVENT_SURPRISE",
    "EUR_HICP_SEP2026_3_8_MINUS_ECB_SMA_Q3_3_2_AS_EVENT_SURPRISE",
    "ECB_SMA_SEP11_AGGREGATE_USED_AS_PRE_SEP10_POLICY_DECISION_CONSENSUS",
    "MARKET_FX_STRENGTH_INFERRED_FROM_SURVEY_LEVEL_ALONE",
))


def _unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in pairs:
        if key in out:
            raise ValueError("duplicate key")
        out[key] = value
    return out


def _base(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_BLOCKED", "reason": reason,
        "expectations_casebook_sha256": None,
        "visible_official_survey_context_not_cpi_consensus": [],
        "visible_survey_currencies": [],
        "latest_documentary_cpi_currencies": [],
        "matched_pre_release_september_cpi_consensus_by_currency": {},
        "september_cpi_surprise_by_currency": {},
        "september_cpi_surprise_verified": False,
        "september_policy_decision_sma_aggregate_pre_event": False,
        "survey_publication_instant_independently_attested": False,
        "survey_original_payload_bytes_archived": False,
        "same_target_period_and_measure_confirmed": False,
        "forecast_population_same_as_market_release_consensus": False,
        "fx_bias": None, "operational_bias": "AGUARDAR",
        "validated_forward_prediction_count": 0,
        "validated_accuracy": None,
        "can_feed_live_radar": False, "trade_authorized": False,
        "publishable": False, "worker_enabled": False,
        "scheduler_enabled": False, "http_requests": 0, "new_cost_brl": 0,
    }


def inspect_eurusd_sep2026_expectations_mismatch_lab(
    expectations_casebook_raw: Any, *, policy_casebook_raw: Any,
    inflation_casebook_raw: Any, as_of_utc: Any,
) -> dict[str, Any]:
    """Expose pre-existing surveys as context; refuse fabricated CPI surprises."""
    out = _base("INVALID_EXPECTATIONS_OR_PRIOR_CHRONOLOGY_OR_CLOCK")
    if (not isinstance(as_of_utc, datetime) or as_of_utc.tzinfo is None
            or as_of_utc.utcoffset() is None
            or not isinstance(expectations_casebook_raw, bytes)
            or not 900 <= len(expectations_casebook_raw) <= 9000
            or sha256(expectations_casebook_raw).hexdigest() != PINNED_EXPECTATIONS_SHA256):
        return out
    now = as_of_utc.astimezone(timezone.utc)
    chronology = inspect_eurusd_sep2026_policy_inflation_timeline_lab(
        policy_casebook_raw, inflation_casebook_raw=inflation_casebook_raw,
        as_of_utc=now,
    )
    if chronology["state"] not in (
        "LAB_PARTIAL_DOCUMENTARY_CONTEXT_NO_DIRECTION",
        "LAB_BOTH_POLICY_AND_SEP_CPI_DOCUMENTARY_CONTEXT_ONLY",
    ):
        return out
    try:
        case = json.loads(
            expectations_casebook_raw.decode("utf-8", "strict"),
            object_pairs_hook=_unique,
            parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite")),
        )
        records = case["records"]
        if (case["schema"] != CASE_SCHEMA or case["kind"] != CASE_KIND
                or case["research_date"] != "2026-11-06"
                or case["source_original_release_bytes_archived"] is not False
                or case["market_consensus_for_exact_september_cpi_release_verified"] is not False
                or case["usable_as_exact_event_consensus"] is not False
                or case["fx_bias_authorized"] is not False
                or frozenset(case["prohibited_calculations"]) != PROHIBITED
                or not isinstance(records, list) or len(records) != 2
                or {r["currency"] for r in records} != set(EXPECTED)):
            return out
        for record in records:
            currency = record["currency"]
            if (any(record[key] != value
                    for key, value in EXPECTED[currency].items())
                    or record["september_2026_monthly_cpi_or_hicp_release_consensus"] is not False
                    or record["september_10_ecb_policy_decision_pre_event_aggregate"] is not False
                    or type(record["median_forecast_percent"]) is not float
                    or (currency == "EUR" and type(record["survey_response_count"]) is not int)
                    or (currency == "USD" and record["survey_response_count"] is not None)):
                return out
    except (UnicodeDecodeError, ValueError, TypeError, KeyError, AttributeError,
            OverflowError, RecursionError):
        return out

    visible = [
        {
            "currency": r["currency"],
            "source_id": r["source_id"],
            "source_url": r["source_url"],
            "publication_calendar_date": r["publication_calendar_date"],
            "target_period": r["forecast_target_period"],
            "target_granularity": r["forecast_target_granularity"],
            "respondent_population": r["respondent_population"],
            "median_survey_expectation_percent_not_cpi_event_consensus": (
                r["median_forecast_percent"]),
            "blocked_as_cpi_release_consensus_reason": r["reason_not_same_release_consensus"],
        }
        for r in records
        if now >= datetime.fromisoformat(
            r["conservative_available_at_utc"].replace("Z", "+00:00"))
    ]
    out.update({
        "state": "LAB_OFFICIAL_SURVEY_CONTEXT_WITH_RELEASE_CONSENSUS_MISMATCH",
        "reason": "REAL_FORECAST_HORIZONS_AND_RELEASE_TARGETS_DIFFER_FROM_CPI_EVENT",
        "expectations_casebook_sha256": sha256(expectations_casebook_raw).hexdigest(),
        "visible_official_survey_context_not_cpi_consensus": visible,
        "visible_survey_currencies": [r["currency"] for r in visible],
        "latest_documentary_cpi_currencies": chronology["inflation_visible_currencies"],
    })
    return out


__all__ = ["SCHEMA", "PINNED_EXPECTATIONS_SHA256",
           "inspect_eurusd_sep2026_expectations_mismatch_lab"]
