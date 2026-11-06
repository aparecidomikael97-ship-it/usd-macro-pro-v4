"""Compare availability of TWO distinct forward CPI model forecast horizons.

October and November 2026 source rows were consulted on Nov 6, before both
scheduled BLS releases. They are NOT event consensus, official CPI, model
errors, or USD direction. No network or execution.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
from typing import Any

from atlasquant_trader_us_oct2026_clevelandfed_forward_nowcast_lab import (
    PINNED_RECEIPT_SHA256 as OCT_RECEIPT_SHA256,
    inspect_us_oct2026_clevelandfed_forward_nowcast_lab,
)

SCHEMA = "ATLASQUANT_TRADER_US_OCTNOV2026_CLEVELANDFED_TWO_HORIZONS_GATE_LAB_V1"
NOV_CASE_SCHEMA = "ATLASQUANT_TRADER_US_NOV2026_CLEVELANDFED_EARLY_MODEL_RECEIPT_LAB_V1"
PINNED_NOV_RECEIPT_SHA256 = "1d33f530dc7ac98b319b683e96dfcf9cdb68db485ee622899ee4e2da18fe150e"
SOURCE_URL = "https://www.clevelandfed.org/indicators-and-data/inflation-nowcasting"
DEC_BLS_SCHEDULE_URL = "https://www.bls.gov/schedule/2026/12_sched_list.htm"
RESEARCH_AVAILABLE = datetime(2026, 11, 7, tzinfo=timezone.utc)
OCT_BLS_RELEASE = datetime(2026, 11, 10, 13, 30, tzinfo=timezone.utc)
NOV_BLS_RELEASE = datetime(2026, 12, 10, 13, 30, tzinfo=timezone.utc)
PROHIBITED = frozenset((
    "CONFUSE_NOVEMBER_MODEL_HORIZON_WITH_OCTOBER_CPI_RELEASE",
    "CONFLATE_MODEL_NOWCAST_WITH_ANALYST_EVENT_CONSENSUS",
    "FILL_ACTUAL_BEFORE_DEC10_BLS_RELEASE",
    "TREAT_PAGE_UPDATE_DATE_AS_EXACT_CAPTURE_INSTANT",
    "INFER_USD_STRENGTH_FROM_CROSS_HORIZON_INFLATION_LEVELS",
))


def _unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in pairs:
        if key in out:
            raise ValueError("duplicate")
        out[key] = value
    return out


def _base() -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_BLOCKED",
        "reason": "INVALID_FORECAST_VINTAGE_OR_CLOCK_OR_PARENT",
        "oct_receipt_sha256": None, "nov_receipt_sha256": None,
        "forecast_rows_documentary_only": [],
        "forecast_months_visible": [],
        "source_is_two_separate_forecast_horizons": False,
        "oct_vs_nov_inflation_level_delta": None,
        "source_page_original_html_archived": False,
        "exact_source_capture_instant_independently_attested": False,
        "official_first_release_actual_by_month": {},
        "model_error_by_month": {},
        "market_consensus_by_month": {},
        "market_surprise_by_month": {},
        "usd_strength_score": None,
        "fx_bias": None, "operational_bias": "AGUARDAR",
        "validated_forward_prediction_count": 0, "validated_accuracy": None,
        "can_feed_live_radar": False, "trade_authorized": False,
        "publishable": False, "worker_enabled": False,
        "scheduler_enabled": False, "http_requests": 0, "new_cost_brl": 0,
    }


def inspect_us_octnov2026_clevelandfed_two_horizons_lab(
    oct_receipt_raw: Any, nov_receipt_raw: Any, *, as_of_utc: Any,
) -> dict[str, Any]:
    """Two forecast months, each with its own first-release boundary."""
    out = _base()
    if (not isinstance(as_of_utc, datetime) or as_of_utc.tzinfo is None
            or as_of_utc.utcoffset() is None
            or not isinstance(nov_receipt_raw, bytes)
            or not 900 <= len(nov_receipt_raw) <= 4000
            or sha256(nov_receipt_raw).hexdigest() != PINNED_NOV_RECEIPT_SHA256):
        return out
    now = as_of_utc.astimezone(timezone.utc)
    oct_result = inspect_us_oct2026_clevelandfed_forward_nowcast_lab(
        oct_receipt_raw, as_of_utc=now,
    )
    if oct_result["state"] not in (
        "LAB_NOT_YET_AVAILABLE_ASOF", "LAB_PRE_RELEASE_MODEL_FORECAST_CONTEXT_ONLY",
        "LAB_AWAIT_OFFICIAL_FIRST_RELEASE_NO_EX_POST_COMPARISON",
    ) or oct_result["pinned_receipt_sha256"] != OCT_RECEIPT_SHA256:
        return out
    try:
        nov = json.loads(nov_receipt_raw.decode("utf-8", "strict"),
                         object_pairs_hook=_unique,
                         parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite")))
        if (not isinstance(nov, dict) or len(nov) != 27
                or nov["schema"] != NOV_CASE_SCHEMA
                or nov["kind"] != "SECOND_DISTINCT_FUTURE_HORIZON_OFFICIAL_WEB_TEXT_MANUAL_MODEL_NOWCAST_CAPTURE"
                or nov["research_calendar_date"] != "2026-11-06"
                or nov["source_institution"] != "FEDERAL_RESERVE_BANK_OF_CLEVELAND"
                or nov["source_url"] != SOURCE_URL
                or nov["source_page_row"] != "INFLATION_YEAR_OVER_YEAR_NOVEMBER_2026_CPI_HEADLINE"
                or nov["source_page_updated_calendar_date"] != "2026-11-06"
                or nov["source_consulted_calendar_date"] != "2026-11-06"
                or nov["target_currency"] != "USD"
                or nov["target_reference_month"] != "2026-11"
                or nov["target_indicator"] != "US_HEADLINE_CPI_YEAR_OVER_YEAR_NON_SEASONALLY_ADJUSTED"
                or nov["forecast_class"] != "STATISTICAL_MODEL_NOWCAST_NOT_ANALYST_CONSENSUS"
                or type(nov["source_transcribed_forecast_percent"]) is not float
                or nov["source_transcribed_forecast_percent"] != 3.88
                or nov["source_original_html_bytes_archived"] is not False
                or nov["source_original_html_sha256"] is not None
                or nov["exact_retrieval_instant_independently_attested"] is not False
                or nov["source_row_primary_web_text_inspected"] is not True
                or nov["first_release_calendar_schedule_url"] != DEC_BLS_SCHEDULE_URL
                or nov["first_release_actual_observed"] is not False
                or nov["first_release_actual_headline_cpi_yoy_percent"] is not None
                or nov["release_result_document_sha256"] is not None
                or nov["may_compute_ex_post_model_error"] is not False
                or nov["may_compute_market_surprise"] is not False
                or nov["may_infer_fx_direction"] is not False
                or frozenset(nov["prohibited"]) != PROHIBITED
                or datetime.fromisoformat(nov["conservative_visible_after_utc"].replace("Z", "+00:00")) != RESEARCH_AVAILABLE
                or datetime.fromisoformat(nov["first_release_scheduled_utc"].replace("Z", "+00:00")) != NOV_BLS_RELEASE):
            return out
    except (UnicodeDecodeError, TypeError, ValueError, KeyError, AttributeError,
            OverflowError, RecursionError):
        return out

    visible = now >= RESEARCH_AVAILABLE
    rows = []
    if visible:
        rows = [{
            "forecast_month": "2026-10",
            "model_forecast_yoy_percent": oct_result["model_nowcast_percent_documentary_only"],
            "scheduled_first_release_utc": "2026-11-10T13:30:00Z",
            "release_window": ("BEFORE_SCHEDULED_RELEASE" if now < OCT_BLS_RELEASE
                               else "AFTER_SCHEDULED_RELEASE_NO_AUTHENTICATED_ACTUAL"),
        }, {
            "forecast_month": "2026-11",
            "model_forecast_yoy_percent": nov["source_transcribed_forecast_percent"],
            "scheduled_first_release_utc": nov["first_release_scheduled_utc"],
            "release_window": ("BEFORE_SCHEDULED_RELEASE" if now < NOV_BLS_RELEASE
                               else "AFTER_SCHEDULED_RELEASE_NO_AUTHENTICATED_ACTUAL"),
        }]
    out.update({
        "state": ("LAB_TWO_FORECAST_MONTHS_UNAVAILABLE_ASOF" if not visible
                  else "LAB_TWO_SEPARATE_PRE_RELEASE_WINDOWS" if now < OCT_BLS_RELEASE
                  else "LAB_OCT_AFTER_SCHEDULE_NOV_BEFORE_SCHEDULE" if now < NOV_BLS_RELEASE
                  else "LAB_BOTH_RELEASE_SCHEDULES_PASSED_NO_OFFICIAL_ACTUAL"),
        "reason": ("RESEARCH_CANNOT_LEAK_BACKWARD" if not visible
                   else "TWO_VINTAGES_FORECAST_ONLY_NO_AUTHENTICATED_BLS_ACTUAL"),
        "oct_receipt_sha256": OCT_RECEIPT_SHA256,
        "nov_receipt_sha256": PINNED_NOV_RECEIPT_SHA256,
        "forecast_rows_documentary_only": rows,
        "forecast_months_visible": [r["forecast_month"] for r in rows],
        "source_is_two_separate_forecast_horizons": visible,
    })
    return out


__all__ = ["SCHEMA", "PINNED_NOV_RECEIPT_SHA256",
           "inspect_us_octnov2026_clevelandfed_two_horizons_lab"]
