"""Retrospective EUR/USD CPI headline context from two OFFICIAL press pages.

This is a manually transcribed, hash-pinned documentary casebook, NOT a live
data/API capture, historically attested page snapshot, validated FX forecast,
or directly comparable HICP-versus-CPI-U measure. No HTTP, no trade outputs.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
from typing import Any

SCHEMA = "ATLASQUANT_TRADER_EURUSD_SEP2026_OFFICIAL_HEADLINE_CONTEXT_LAB_V1"
KIND = "MANUALLY_TRANSCRIBED_FROM_OFFICIAL_PUBLISHED_RELEASE_PAGES_NOT_ORIGINAL_RESPONSE_BYTES"
PINNED_CASEBOOK_SHA256 = "2636077951a2d8422476bc238cfa6fe9d7fce4a0ef46628a83c5082429abafaf"
EVIDENCE_DATES = {
    "USD": datetime(2026, 10, 15, tzinfo=timezone.utc),
    "EUR": datetime(2026, 10, 17, tzinfo=timezone.utc),
}
EXPECTED = {
    "USD": {
        "agency": "US_BLS",
        "source_url": "https://www.bls.gov/news.release/archives/cpi_10142026.htm",
        "source_document": "CONSUMER_PRICE_INDEX_SEPTEMBER_2026_USDL_26_1574",
        "series": "CPI_U_ALL_ITEMS_12_MONTH_NOT_SEASONALLY_ADJUSTED",
        "release_type": "SEPTEMBER_FINAL_PRESS_RELEASE",
        "publication_calendar_date": "2026-10-14",
        "annual_headline_september_percent": 3.7,
        "annual_headline_august_percent": 3.4,
        "computed_change_in_annual_rate_from_august_pp": 0.3,
    },
    "EUR": {
        "agency": "EUROSTAT",
        "source_url": "https://ec.europa.eu/eurostat/en/web/products-euro-indicators/w/2-16102026-ap",
        "source_document": "EURO_INDICATORS_SEPTEMBER_2026_FULL_RELEASE_16_OCTOBER",
        "series": "EURO_AREA_HICP_HEADLINE_12_MONTH_RATE_EA21_EVOLVING_COMPOSITION",
        "release_type": "SEPTEMBER_FULL_PRESS_RELEASE_NOT_FLASH",
        "publication_calendar_date": "2026-10-16",
        "annual_headline_september_percent": 3.8,
        "annual_headline_august_percent": 3.2,
        "computed_change_in_annual_rate_from_august_pp": 0.6,
    },
}
PROHIBITED = frozenset((
    "HICP_AND_CPI_U_ARE_IDENTICAL_BASKETS_OR_METHODS",
    "EURO_AREA_HIGHER_HEADLINE_INFLATION_PREDICTS_EURUSD_RISE",
    "INFLATION_ACCELERATION_ALONE_PREDICTS_EURUSD_RISE",
    "EARLIER_US_SEPTEMBER_RELEASE_WAS_ALREADY_KNOWN_TO_EURO_AREA_FULL_RELEASE_BEFORE_16_OCTOBER",
    "SEPTEMBER_FULL_RELEASE_AVAILABLE_BEFORE_OFFICIAL_RELEASE_CALENDAR_DATE",
    "MANUAL_TRANSCRIPTION_EQUALS_ORIGINAL_ARCHIVED_RESPONSE",
))


def _unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in pairs:
        if k in out:
            raise ValueError("duplicate JSON key")
        out[k] = v
    return out


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_BLOCKED", "reason": reason,
        "accepted_documentary_casebook_sha256": None,
        "visible_press_release_context": [], "visible_currencies": [],
        "same_observation_month_available_in_both_releases": False,
        "same_statistical_methodology_for_both_currency_headlines": False,
        "historical_original_release_page_bytes_attested": False,
        "independent_release_instant_http_witness": False,
        "source_api_response_captured": False,
        "published_consensus_surprise_verified": False,
        "central_bank_rate_response_verified": False,
        "headline_level_differential_authorized_as_fx_factor": False,
        "fx_bias": None, "operational_bias": "AGUARDAR",
        "validated_forward_prediction_count": 0,
        "validated_accuracy": None,
        "can_feed_live_radar": False, "trade_authorized": False,
        "publishable": False, "worker_enabled": False,
        "scheduler_enabled": False, "http_requests": 0,
        "new_cost_brl": 0,
    }


def inspect_eurusd_sep2026_official_headline_lab(
    casebook_raw: Any, *, as_of_utc: Any,
) -> dict[str, Any]:
    """Show conservatively available official *page references* as of UTC."""
    out = _blocked("INVALID_CASEBOOK_OR_ASOF_OR_OFFICIAL_DOCUMENTARY_FIELDS")
    if (not isinstance(as_of_utc, datetime) or as_of_utc.tzinfo is None
            or as_of_utc.utcoffset() is None
            or not isinstance(casebook_raw, bytes)
            or not 800 <= len(casebook_raw) <= 9000
            or sha256(casebook_raw).hexdigest() != PINNED_CASEBOOK_SHA256):
        return out
    now = as_of_utc.astimezone(timezone.utc)
    try:
        case = json.loads(
            casebook_raw.decode("utf-8", "strict"),
            object_pairs_hook=_unique,
            parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite")),
        )
        observations = case["observations"]
        if (case["schema"] != SCHEMA or case["kind"] != KIND
                or case["research_date"] != "2026-11-06"
                or case["source_page_payload_archived"] is not False
                or case["source_page_original_historical_vintage_attested"] is not False
                or case["methodologically_direct_cross_currency_cpi_level_comparison"] is not False
                or case["validated_forward_prediction_count"] != 0
                or case["inflation_only_forex_bias_authorized"] is not False
                or frozenset(case["prohibited_inferences"]) != PROHIBITED
                or not isinstance(observations, list) or len(observations) != 2
                or {o["currency"] for o in observations} != set(EXPECTED)):
            return out
        for o in observations:
            currency = o["currency"]
            if (o["reference_period"] != "2026-09"
                    or o["previous_reference_period"] != "2026-08"
                    or o["conservative_available_at_utc"] != (
                        EVIDENCE_DATES[currency].strftime("%Y-%m-%dT%H:%M:%SZ"))
                    or o["is_official_api_response_or_historical_pit_receipt"] is not False
                    or any(o[key] != expected for key, expected in EXPECTED[currency].items())):
                return out
            for field in ("annual_headline_september_percent",
                          "annual_headline_august_percent",
                          "computed_change_in_annual_rate_from_august_pp"):
                if type(o[field]) is not float:
                    return out
            if round(o["annual_headline_september_percent"]
                     - o["annual_headline_august_percent"], 1) != (
                         o["computed_change_in_annual_rate_from_august_pp"]):
                return out
    except (UnicodeDecodeError, ValueError, TypeError, KeyError,
            AttributeError, RecursionError, OverflowError):
        return out

    visible = [
        {
            "currency": o["currency"],
            "publication_calendar_date": o["publication_calendar_date"],
            "conservative_available_at_utc": o["conservative_available_at_utc"],
            "reference_period": o["reference_period"],
            "series": o["series"],
            "release_type": o["release_type"],
            "source_url": o["source_url"],
            "annual_headline_september_percent": o["annual_headline_september_percent"],
            "annual_headline_august_percent": o["annual_headline_august_percent"],
            "computed_change_in_annual_rate_from_august_pp": (
                o["computed_change_in_annual_rate_from_august_pp"]),
            "type_of_evidence": "RETROSPECTIVE_OFFICIAL_PRESS_PAGE_REFERENCE_NOT_PIT_RECEIPT",
        }
        for o in observations if now >= EVIDENCE_DATES[o["currency"]]
    ]
    both = {o["currency"] for o in visible} == set(EXPECTED)
    out.update({
        "state": ("LAB_SAME_SEP2026_PERIOD_DOCUMENTARY_HEADLINE_CONTEXT_ONLY"
                  if both else "LAB_INCOMPLETE_SEP2026_DOCUMENTARY_CONTEXT_ONLY"),
        "reason": ("OFFICIAL_PAGE_REFERENCES_NOT_METHOD_ALIGNED_CPI_ORIGINAL_VINTAGES"),
        "accepted_documentary_casebook_sha256": sha256(casebook_raw).hexdigest(),
        "visible_press_release_context": visible,
        "visible_currencies": [o["currency"] for o in visible],
        "same_observation_month_available_in_both_releases": both,
    })
    return out


__all__ = ["SCHEMA", "PINNED_CASEBOOK_SHA256",
           "inspect_eurusd_sep2026_official_headline_lab"]
