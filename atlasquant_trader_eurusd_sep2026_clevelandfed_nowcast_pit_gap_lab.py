"""Quarantine Cleveland Fed model nowcasts without an attested Sep-2026 vintage.

An official model's *existence* is documented. Its October 13, 2026
September-CPI forecast value and original daily publication receipt are not.
Never infer that value from today's mutable website or from third-party news.
No HTTP, orders, confidence claim, scheduler, or live radar.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
from typing import Any

from atlasquant_trader_eurusd_sep2026_expectations_mismatch_lab import (
    inspect_eurusd_sep2026_expectations_mismatch_lab,
)

SCHEMA = "ATLASQUANT_TRADER_EURUSD_SEP2026_CLEVELANDFED_MODEL_NOWCAST_PIT_GAP_GATE_LAB_V1"
CASE_SCHEMA = "ATLASQUANT_TRADER_EURUSD_SEP2026_CLEVELANDFED_NOWCAST_PIT_GAP_LAB_V1"
PINNED_REFERENCE_SHA256 = "e1159f6bd481e32ff92bac29af63640b83d55518ca3df179038e38249cc22139"
SOURCE_URL = "https://www.clevelandfed.org/indicators-and-data/inflation-nowcasting"
PROHIBITED = frozenset((
    "BACKFILL_CURRENT_LIVE_NOWCAST_AS_OCT13_HISTORICAL_VINTAGE",
    "CONFLATE_CLEVELANDFED_MODEL_NOWCAST_WITH_MARKET_CONSENSUS",
    "ESTIMATE_SEP_CPI_MODEL_ERROR_WITHOUT_ORIGINAL_PRE_RELEASE_VALUE",
    "CONVERT_CPI_MODEL_ERROR_INTO_VERIFIED_FX_DIRECTION",
    "TREAT_NEWS_REPRINT_AS_ATTESTED_OFFICIAL_ORIGINAL_VINTAGE",
))
MINIMUM_KEYS = frozenset((
    "schema", "kind", "research_date", "conservative_research_available_at_utc",
    "source_name", "source_url", "forecast_type", "update_cadence",
    "supported_target_currency", "target_reference_period", "target_measure",
    "supported_measure_class_from_official_description",
    "requested_historical_vintage_calendar_date",
    "us_september_cpi_release_calendar_date",
    "exact_historical_nowcast_value_from_original_official_oct13_snapshot_verified",
    "exact_historical_publication_instant_independently_attested",
    "original_oct13_snapshot_bytes_archived", "oct13_vintage_sha256",
    "oct13_headline_yoy_nowcast_percent",
    "market_consensus_for_sep2026_cpi_release_verified",
    "may_compute_sep2026_cpi_model_error", "may_compute_sep2026_cpi_event_surprise",
    "fx_direction_authorized", "prohibited_calculations",
))


def _unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for name, value in pairs:
        if name in out:
            raise ValueError("duplicate field")
        out[name] = value
    return out


def _base(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_BLOCKED", "reason": reason,
        "reference_sha256": None,
        "visible_official_model_metadata": None,
        "source_is_model_not_market_consensus": False,
        "exact_oct13_sep2026_cpi_nowcast_verified": False,
        "oct13_model_nowcast_percent": None,
        "us_september_cpi_model_error_percentage_points": None,
        "matched_pre_release_market_consensus_by_currency": {},
        "september_cpi_surprise_by_currency": {},
        "latest_documentary_cpi_currencies": [],
        "historical_point_in_time_forecast_count": 0,
        "fx_bias": None, "operational_bias": "AGUARDAR",
        "validated_forward_prediction_count": 0,
        "validated_accuracy": None,
        "can_feed_live_radar": False, "trade_authorized": False,
        "publishable": False, "worker_enabled": False,
        "scheduler_enabled": False, "http_requests": 0, "new_cost_brl": 0,
    }


def inspect_eurusd_sep2026_clevelandfed_nowcast_pit_gap_lab(
    reference_raw: Any, *, expectations_casebook_raw: Any,
    policy_casebook_raw: Any, inflation_casebook_raw: Any, as_of_utc: Any,
) -> dict[str, Any]:
    """A reference can appear, but never an unauthenticated forecast value."""
    out = _base("INVALID_REFERENCE_OR_PRIOR_EVIDENCE_OR_CLOCK")
    if (not isinstance(as_of_utc, datetime) or as_of_utc.tzinfo is None
            or as_of_utc.utcoffset() is None
            or not isinstance(reference_raw, bytes)
            or not 900 <= len(reference_raw) <= 4000
            or sha256(reference_raw).hexdigest() != PINNED_REFERENCE_SHA256):
        return out
    now = as_of_utc.astimezone(timezone.utc)
    prior = inspect_eurusd_sep2026_expectations_mismatch_lab(
        expectations_casebook_raw, policy_casebook_raw=policy_casebook_raw,
        inflation_casebook_raw=inflation_casebook_raw, as_of_utc=now,
    )
    if prior["state"] != "LAB_OFFICIAL_SURVEY_CONTEXT_WITH_RELEASE_CONSENSUS_MISMATCH":
        return out
    try:
        case = json.loads(
            reference_raw.decode("utf-8", "strict"), object_pairs_hook=_unique,
            parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite")),
        )
        if (not isinstance(case, dict) or set(case) != MINIMUM_KEYS
                or case["schema"] != CASE_SCHEMA
                or case["kind"] != "OFFICIAL_MODEL_DESCRIPTION_WITHOUT_ATTESTED_SEPTEMBER_2026_PRE_RELEASE_DAILY_VINTAGE"
                or case["research_date"] != "2026-11-06"
                or case["source_url"] != SOURCE_URL
                or case["forecast_type"] != "MODEL_NOWCAST_NOT_PROFESSIONAL_FORECASTER_CONSENSUS"
                or case["target_reference_period"] != "2026-09"
                or case["target_measure"] != "US_HEADLINE_CPI_U_YEAR_OVER_YEAR_NON_SEASONALLY_ADJUSTED_PERCENT"
                or case["requested_historical_vintage_calendar_date"] != "2026-10-13"
                or case["us_september_cpi_release_calendar_date"] != "2026-10-14"
                or any(case[key] is not False for key in (
                    "exact_historical_nowcast_value_from_original_official_oct13_snapshot_verified",
                    "exact_historical_publication_instant_independently_attested",
                    "original_oct13_snapshot_bytes_archived",
                    "market_consensus_for_sep2026_cpi_release_verified",
                    "may_compute_sep2026_cpi_model_error",
                    "may_compute_sep2026_cpi_event_surprise",
                    "fx_direction_authorized",
                ))
                or case["oct13_vintage_sha256"] is not None
                or case["oct13_headline_yoy_nowcast_percent"] is not None
                or frozenset(case["prohibited_calculations"]) != PROHIBITED):
            return out
        available = datetime.fromisoformat(
            case["conservative_research_available_at_utc"].replace("Z", "+00:00")
        )
        if available != datetime(2026, 11, 7, tzinfo=timezone.utc):
            return out
    except (UnicodeDecodeError, ValueError, TypeError, KeyError, AttributeError,
            OverflowError, RecursionError):
        return out

    visible = now >= available
    out.update({
        "state": ("LAB_REFERENCE_VISIBLE_NO_ATTESTED_PRE_CPI_VINTAGE" if visible
                  else "LAB_REFERENCE_NOT_YET_AVAILABLE_ASOF"),
        "reason": ("NO_AUTHENTICATED_ORIGINAL_OCT13_DAILY_MODEL_VALUE" if visible
                   else "NOV6_RESEARCH_MUST_NOT_LEAK_BACKWARD"),
        "reference_sha256": PINNED_REFERENCE_SHA256,
        "visible_official_model_metadata": ({
            "source_url": SOURCE_URL,
            "forecast_type": case["forecast_type"],
            "update_cadence": case["update_cadence"],
            "target_period": case["target_reference_period"],
            "potentially_comparable_measure": case["target_measure"],
            "historical_value_and_publication_receipt": "NOT_ATTESTED",
        } if visible else None),
        "source_is_model_not_market_consensus": visible,
        "latest_documentary_cpi_currencies": prior["latest_documentary_cpi_currencies"],
    })
    return out


__all__ = ["SCHEMA", "PINNED_REFERENCE_SHA256",
           "inspect_eurusd_sep2026_clevelandfed_nowcast_pit_gap_lab"]
