"""US October 2026 CPI: monthly poll is not an annual CPI surprise.

BLS did not publish the October 2025 headline index, so October 2026
headline year-over-year cannot be compared to a BLS first-print actual.
A pre-release Reuters monthly-consensus claim is kept documentary-only,
not a point-in-time witnessed feed. No live FX decision is produced.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
from typing import Any

from atlasquant_fx_universe import OFFICIAL_PAIRS
from atlasquant_trader_g8_cpi_event_consensus_eligibility_lab import (
    inspect_g8_cpi_event_consensus_eligibility_lab,
)

SCHEMA = "ATLASQUANT_TRADER_US_OCT2026_CPI_MOM_YOY_ALIGNMENT_28_PAIRS_LAB_V1"
RECEIPT_SCHEMA = (
    "ATLASQUANT_TRADER_US_OCT2026_CPI_MOM_YOY_METRIC_AVAILABILITY_CONSENSUS_RECEIPT_LAB_V1"
)
PINNED_RECEIPT_SHA256 = "575dafd01aeac051d5e915fa588abae188a5dc421cb51e6bcf1fb5888121cb21"
ADMISSIBLE = datetime(2026, 11, 7, tzinfo=timezone.utc)
OCT_RELEASE = datetime(2026, 11, 10, 13, 30, tzinfo=timezone.utc)
PARENT_READY = "LAB_TWO_MODEL_HORIZONS_TWO_MISMATCHED_SURVEYS_NO_CPI_EVENT_CONSENSUS"
BLS_FAQ_URL = (
    "https://www.bls.gov/cpi/additional-resources/"
    "2025-federal-government-shutdown-impact-cpi-faq.htm"
)
BLS_CALENDAR_URL = "https://www.bls.gov/schedule/2026/11_sched_list.htm"
REUTERS_URL = "https://www.reuters.com/business/take-five/global-markets-themes-graphic-2026-11-06/"
EXPECTED_TOP = frozenset((
    "schema", "kind", "research_date", "conservative_visible_after_utc",
    "source_original_html_bytes_archived", "source_capture_instant_independently_attested",
    "bls", "analyst_consensus_candidate", "may_calculate_oct2026_yoy_surprise",
    "may_calculate_oct2026_mom_surprise", "may_generate_fx_signal_or_accuracy",
))
EXPECTED_BLS = {
    "source_url": BLS_FAQ_URL,
    "reference_month_for_missing_baseline": "2025-10",
    "missing_baseline": "OCT2025_HEADLINE_ALL_ITEMS_CPI_U_INDEX_NOT_PUBLISHED",
    "affected_current_reference_month": "2026-10",
    "missing_2026_october_headline_yoy": True,
    "most_2026_october_yoy_series_unavailable": True,
    "release_scheduled_utc": "2026-11-10T13:30:00Z",
    "release_calendar_source_url": BLS_CALENDAR_URL,
    "oct2026_actual_mom_observed": None,
    "oct2026_actual_yoy_observed": None,
}
EXPECTED_CONSENSUS = {
    "source_url": REUTERS_URL,
    "source_kind": "REUTERS_REPORTED_ECONOMIST_POLL_PRE_RELEASE",
    "source_article_calendar_date": "2026-11-06",
    "source_article_exact_time_attested": False,
    "target_event": "US_CPI_OCT2026_FIRST_RELEASE",
    "target_period": "2026-10",
    "target_indicator": "CPI_U_ALL_ITEMS_HEADLINE",
    "target_metric": "SEASONALLY_ADJUSTED_MONTH_OVER_MONTH_PERCENT_CHANGE",
    "consensus_mom_percent_as_documentary_claim": "0.3",
    "poll_membership_and_collection_window_independently_attested": False,
    "source_original_html_bytes_archived": False,
    "eligible_as_verified_point_in_time_market_consensus": False,
}


def _unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _base(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_BLOCKED", "reason": reason,
        "as_of_utc": None, "receipt_sha256": None,
        "pair_count": 0, "usd_pair_count": 0, "non_usd_pair_count": 0,
        "oct2026_headline_yoy_bls_publishable": None,
        "oct2026_headline_yoy_model_usable_for_actual_surprise": False,
        "oct2026_headline_mom_reported_poll_percent_document_only": None,
        "oct2026_headline_mom_verified_point_in_time_consensus": None,
        "oct2026_headline_mom_official_actual": None,
        "oct2026_headline_yoy_official_actual": None,
        "oct2026_headline_mom_surprise": None,
        "oct2026_headline_yoy_surprise": None,
        "release_state": "NO_AUTHENTICATED_RELEASE_ACTUAL",
        "pair_rows": [], "ranked_currencies": [], "best_pair_of_day": None,
        "validated_accuracy": None, "validated_forward_prediction_count": 0,
        "fx_bias": None, "operational_bias": "AGUARDAR",
        "source_original_bytes_independently_attested": False,
        "pre_event_poll_collection_time_witnessed": False,
        "can_feed_live_radar": False, "trade_authorized": False,
        "publishable": False, "worker_enabled": False, "scheduler_enabled": False,
        "http_requests": 0, "new_cost_brl": 0,
    }


def inspect_us_oct2026_cpi_metric_availability_consensus_lab(
    *, five_calendar_casebook_raw: Any, three_calendar_casebook_raw: Any,
    eurusd_macro_casebook_raw: Any, gbpjpy_macro_casebook_raw: Any,
    remaining_four_macro_casebook_raw: Any,
    october_us_model_receipt_raw: Any, november_us_model_receipt_raw: Any,
    survey_expectations_casebook_raw: Any,
    september_policy_casebook_raw: Any, september_cpi_casebook_raw: Any,
    oct2026_metric_receipt_raw: Any, as_of_utc: Any,
) -> dict[str, Any]:
    """Audit strict metric and horizon correspondence, never calculate a signal."""
    out = _base("INVALID_CLOCK_PARENT_EVIDENCE_OR_METRIC_RECEIPT")
    if (not isinstance(as_of_utc, datetime) or as_of_utc.tzinfo is None
            or as_of_utc.utcoffset() is None
            or not isinstance(oct2026_metric_receipt_raw, bytes)
            or not 1000 <= len(oct2026_metric_receipt_raw) <= 4000
            or sha256(oct2026_metric_receipt_raw).hexdigest() != PINNED_RECEIPT_SHA256
            or len(OFFICIAL_PAIRS) != 28):
        return out
    now = as_of_utc.astimezone(timezone.utc)
    parent = inspect_g8_cpi_event_consensus_eligibility_lab(
        five_calendar_casebook_raw=five_calendar_casebook_raw,
        three_calendar_casebook_raw=three_calendar_casebook_raw,
        eurusd_macro_casebook_raw=eurusd_macro_casebook_raw,
        gbpjpy_macro_casebook_raw=gbpjpy_macro_casebook_raw,
        remaining_four_macro_casebook_raw=remaining_four_macro_casebook_raw,
        october_us_model_receipt_raw=october_us_model_receipt_raw,
        november_us_model_receipt_raw=november_us_model_receipt_raw,
        survey_expectations_casebook_raw=survey_expectations_casebook_raw,
        september_policy_casebook_raw=september_policy_casebook_raw,
        september_cpi_casebook_raw=september_cpi_casebook_raw,
        as_of_utc=now,
    )
    if parent["state"] == "LAB_CONSENSUS_RESEARCH_NOT_VISIBLE_ASOF":
        out.update({"state": "LAB_US_METRIC_RESEARCH_NOT_VISIBLE_ASOF",
                    "reason": "NO_FUTURE_RESEARCH_LEAK_BEFORE_NOV7_UTC"})
        return out
    if parent["state"] != PARENT_READY or parent["pair_count"] != 28:
        return out
    try:
        receipt = json.loads(
            oct2026_metric_receipt_raw.decode("utf-8", "strict"),
            object_pairs_hook=_unique,
            parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite")),
        )
        if (not isinstance(receipt, dict) or receipt.keys() != EXPECTED_TOP
                or receipt["schema"] != RECEIPT_SCHEMA
                or receipt["kind"] !=
                "RETROSPECTIVE_HUMAN_TRANSCRIPTION_OF_BLS_DATA_GAP_AND_REUTERS_PRE_RELEASE_MOM_POLL"
                or receipt["research_date"] != "2026-11-06"
                or receipt["conservative_visible_after_utc"] != "2026-11-07T00:00:00Z"
                or receipt["source_original_html_bytes_archived"] is not False
                or receipt["source_capture_instant_independently_attested"] is not False
                or receipt["bls"] != EXPECTED_BLS
                or receipt["analyst_consensus_candidate"] != EXPECTED_CONSENSUS
                or receipt["may_calculate_oct2026_yoy_surprise"] is not False
                or receipt["may_calculate_oct2026_mom_surprise"] is not False
                or receipt["may_generate_fx_signal_or_accuracy"] is not False):
            return out
    except (UnicodeDecodeError, ValueError, TypeError, KeyError, AttributeError,
            OverflowError, RecursionError):
        return out
    rows = []
    for old in parent["pair_rows"]:
        usd_role = ("BASE" if old["base"] == "USD"
                    else "QUOTE" if old["quote"] == "USD" else None)
        rows.append({
            "pair": old["pair"], "base": old["base"], "quote": old["quote"],
            "us_currency_role": usd_role,
            "oct2026_us_cpi_yoy_metric_status": (
                "BLS_HEADLINE_YOY_UNAVAILABLE_MISSING_OCT2025_INDEX"
                if usd_role else None),
            "oct2026_us_cpi_mom_reported_consensus_percent_document_only": (
                "0.3" if usd_role else None),
            "oct2026_us_cpi_mom_consensus_verified": False,
            "oct2026_us_cpi_yoy_nowcast_matches_publishable_bls_metric": False,
            "oct2026_us_cpi_mom_actual": None,
            "oct2026_us_cpi_mom_surprise": None,
            "oct2026_us_cpi_yoy_surprise": None,
            "missing_prerequisites": [
                *old["missing_prerequisites"],
                *(["NO_OCT2025_US_ALL_ITEMS_CPI_INDEX_FOR_OCT2026_YOY",
                   "NO_PIT_WITNESSED_REUTERS_POLL_OR_OFFICIAL_OCT2026_MOM_ACTUAL"]
                  if usd_role else []),
            ],
            "D1": "AGUARDAR", "W1": "AGUARDAR",
            "relative_macro_score": None, "fx_bias": None,
            "trade_authorized": False,
        })
    n_usd = sum(r["us_currency_role"] is not None for r in rows)
    if (len(rows) != 28 or len({r["pair"] for r in rows}) != 28
            or n_usd != 7):
        return out
    out.update({
        "state": "LAB_US_OCT2026_YOY_NOT_PUBLISHABLE_MOM_POLL_UNATTESTED_NO_FX_BIAS",
        "reason": "BLS_OCT2025_BASELINE_MISSING_MOM_POLL_IS_UNWITNESSED_DOCUMENTARY_CONTEXT",
        "as_of_utc": now.isoformat(),
        "receipt_sha256": PINNED_RECEIPT_SHA256,
        "pair_count": len(rows), "usd_pair_count": n_usd,
        "non_usd_pair_count": len(rows) - n_usd,
        "oct2026_headline_yoy_bls_publishable": False,
        "oct2026_headline_mom_reported_poll_percent_document_only": "0.3",
        "release_state": ("BEFORE_SCHEDULED_RELEASE_NO_ACTUAL"
                          if now < OCT_RELEASE
                          else "SCHEDULE_PASSED_ACTUAL_STILL_UNAUTHENTICATED"),
        "pair_rows": rows,
    })
    return out


__all__ = ["SCHEMA", "PINNED_RECEIPT_SHA256",
           "inspect_us_oct2026_cpi_metric_availability_consensus_lab"]
