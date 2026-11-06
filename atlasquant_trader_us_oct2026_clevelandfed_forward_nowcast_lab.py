"""First *prospective* Cleveland Fed US CPI model-nowcast paper receipt.

Official HTML text was inspected on Nov 6, before the Nov 10 scheduled CPI.
The number is manual transcription, not raw-HTML archive or a timestamp proof.
This is model context, never analyst consensus or a trading signal. Offline only.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
from typing import Any

SCHEMA = "ATLASQUANT_TRADER_US_OCT2026_CLEVELANDFED_FORWARD_MODEL_GATE_LAB_V1"
CASE_SCHEMA = "ATLASQUANT_TRADER_US_OCT2026_CLEVELANDFED_FORWARD_MODEL_RECEIPT_LAB_V1"
PINNED_RECEIPT_SHA256 = "2377e65480e4069b23e8c58643ca3e344b561ce5702b82eb3c0877267605343f"
SOURCE_URL = "https://www.clevelandfed.org/indicators-and-data/inflation-nowcasting"
BLS_SCHEDULE_URL = "https://www.bls.gov/schedule/2026/11_sched_list.htm"
AVAILABLE_UTC = datetime(2026, 11, 7, 0, 0, tzinfo=timezone.utc)
RELEASE_UTC = datetime(2026, 11, 10, 13, 30, tzinfo=timezone.utc)
PROHIBITED = frozenset((
    "CONFLATE_MODEL_NOWCAST_WITH_ANALYST_EVENT_CONSENSUS",
    "FILL_ACTUAL_BEFORE_NOV10_BLS_RELEASE",
    "TREAT_PAGE_UPDATE_DATE_AS_EXACT_CAPTURE_INSTANT",
    "COMPUTE_FX_DIRECTION_FROM_MODEL_FORECAST_ALONE",
    "CLAIM_80_PERCENT_OR_90_PERCENT_FORECAST_ACCURACY",
))
REQUIRED = frozenset((
    "schema", "kind", "research_calendar_date", "conservative_visible_after_utc",
    "source_institution", "source_url", "source_page_row",
    "source_page_updated_calendar_date", "source_consulted_calendar_date",
    "target_currency", "target_reference_month", "target_indicator",
    "forecast_class", "source_transcribed_forecast_percent",
    "source_original_html_bytes_archived", "source_original_html_sha256",
    "exact_retrieval_instant_independently_attested",
    "source_row_primary_web_text_inspected",
    "first_release_calendar_schedule_url", "first_release_scheduled_utc",
    "first_release_actual_observed", "first_release_actual_headline_cpi_yoy_percent",
    "release_result_document_sha256", "may_compute_ex_post_model_error",
    "may_compute_market_surprise", "may_infer_fx_direction", "prohibited",
))


def _unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for name, value in pairs:
        if name in out:
            raise ValueError("duplicate casebook key")
        out[name] = value
    return out


def _base() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "state": "LAB_BLOCKED", "reason": "INVALID_RECEIPT_OR_CLOCK",
        "pinned_receipt_sha256": None,
        "research_calendar_date": None,
        "source_updated_calendar_date_not_capture_instant": None,
        "target_indicator": None,
        "forecast_class": None,
        "model_nowcast_percent_documentary_only": None,
        "model_nowcast_visible_before_release": False,
        "original_html_snapshot_archived": False,
        "exact_retrieval_instant_independently_attested": False,
        "first_bls_release_scheduled_utc": None,
        "first_bls_actual_headline_yoy_percent": None,
        "model_error_percentage_points": None,
        "analyst_consensus_percent": None,
        "release_surprise_percentage_points": None,
        "validated_forward_prediction_count": 0,
        "validated_accuracy": None,
        "fx_bias": None, "operational_bias": "AGUARDAR",
        "can_feed_live_radar": False, "trade_authorized": False,
        "publishable": False, "worker_enabled": False,
        "scheduler_enabled": False, "http_requests": 0, "new_cost_brl": 0,
    }


def inspect_us_oct2026_clevelandfed_forward_nowcast_lab(
    receipt_raw: Any, *, as_of_utc: Any,
) -> dict[str, Any]:
    """Expose a documentary forecast only after conservative as-of, no actual."""
    out = _base()
    if (not isinstance(as_of_utc, datetime) or as_of_utc.tzinfo is None
            or as_of_utc.utcoffset() is None
            or not isinstance(receipt_raw, bytes)
            or not 900 <= len(receipt_raw) <= 3600
            or sha256(receipt_raw).hexdigest() != PINNED_RECEIPT_SHA256):
        return out
    try:
        record = json.loads(
            receipt_raw.decode("utf-8", "strict"), object_pairs_hook=_unique,
            parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite")),
        )
        if (not isinstance(record, dict) or set(record) != REQUIRED
                or record["schema"] != CASE_SCHEMA
                or record["kind"] != "OFFICIAL_WEB_TEXT_MANUAL_PRE_RELEASE_MODEL_NOWCAST_CAPTURE_NOT_MARKET_CONSENSUS"
                or record["source_institution"] != "FEDERAL_RESERVE_BANK_OF_CLEVELAND"
                or record["source_url"] != SOURCE_URL
                or record["source_page_row"] != "INFLATION_YEAR_OVER_YEAR_OCTOBER_2026_CPI_HEADLINE"
                or record["research_calendar_date"] != "2026-11-06"
                or record["source_page_updated_calendar_date"] != "2026-11-06"
                or record["source_consulted_calendar_date"] != "2026-11-06"
                or record["target_currency"] != "USD"
                or record["target_reference_month"] != "2026-10"
                or record["target_indicator"] != "US_HEADLINE_CPI_YEAR_OVER_YEAR_NON_SEASONALLY_ADJUSTED"
                or record["forecast_class"] != "STATISTICAL_MODEL_NOWCAST_NOT_ANALYST_CONSENSUS"
                or type(record["source_transcribed_forecast_percent"]) is not float
                or record["source_transcribed_forecast_percent"] != 3.74
                or record["source_original_html_bytes_archived"] is not False
                or record["source_original_html_sha256"] is not None
                or record["exact_retrieval_instant_independently_attested"] is not False
                or record["source_row_primary_web_text_inspected"] is not True
                or record["first_release_calendar_schedule_url"] != BLS_SCHEDULE_URL
                or record["first_release_actual_observed"] is not False
                or record["first_release_actual_headline_cpi_yoy_percent"] is not None
                or record["release_result_document_sha256"] is not None
                or record["may_compute_ex_post_model_error"] is not False
                or record["may_compute_market_surprise"] is not False
                or record["may_infer_fx_direction"] is not False
                or frozenset(record["prohibited"]) != PROHIBITED
                or datetime.fromisoformat(record["conservative_visible_after_utc"].replace("Z", "+00:00")) != AVAILABLE_UTC
                or datetime.fromisoformat(record["first_release_scheduled_utc"].replace("Z", "+00:00")) != RELEASE_UTC):
            return out
    except (UnicodeDecodeError, TypeError, ValueError, KeyError, AttributeError,
            OverflowError, RecursionError):
        return out

    now = as_of_utc.astimezone(timezone.utc)
    visible = now >= AVAILABLE_UTC
    pre_release = AVAILABLE_UTC <= now < RELEASE_UTC
    out.update({
        "state": ("LAB_PRE_RELEASE_MODEL_FORECAST_CONTEXT_ONLY" if pre_release
                  else "LAB_AWAIT_OFFICIAL_FIRST_RELEASE_NO_EX_POST_COMPARISON" if visible
                  else "LAB_NOT_YET_AVAILABLE_ASOF"),
        "reason": ("MANUAL_SOURCE_TRANSCRIPTION_NO_ORIGINAL_HTML" if visible
                   else "SOURCE_RESEARCH_MUST_NOT_LEAK_BACKWARD"),
        "pinned_receipt_sha256": PINNED_RECEIPT_SHA256,
        "research_calendar_date": record["research_calendar_date"] if visible else None,
        "source_updated_calendar_date_not_capture_instant": (
            record["source_page_updated_calendar_date"] if visible else None),
        "target_indicator": record["target_indicator"] if visible else None,
        "forecast_class": record["forecast_class"] if visible else None,
        "model_nowcast_percent_documentary_only": (
            record["source_transcribed_forecast_percent"] if visible else None),
        "model_nowcast_visible_before_release": pre_release,
        "first_bls_release_scheduled_utc": (
            record["first_release_scheduled_utc"] if visible else None),
    })
    return out


__all__ = ["SCHEMA", "PINNED_RECEIPT_SHA256",
           "inspect_us_oct2026_clevelandfed_forward_nowcast_lab"]
