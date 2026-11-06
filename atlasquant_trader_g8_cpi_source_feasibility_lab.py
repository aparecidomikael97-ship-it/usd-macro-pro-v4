"""Offline source-feasibility audit for G8 CPI (OECD/Eurostat/ABS/NZ).

This pins RESEARCH METADATA, not raw CPI payloads or original historical
release vintages. Source routing is hypothetical until each dataset series,
frequency, publication clock and licensing is independently verified.
No HTTP calls, inflation numbers, policy comparisons, FX ranking or bias.
"""
from __future__ import annotations

from hashlib import sha256
import json
from typing import Any

from atlasquant_fx_universe import CURRENCIES, OFFICIAL_PAIRS, split_pair

SCHEMA = "ATLASQUANT_TRADER_G8_OECD_EUROSTAT_CPI_SOURCE_FEASIBILITY_LAB_V1"
KIND = "OFFICIAL_DOCUMENTATION_REFERENCES_NOT_API_CAPTURED_NOT_PIT_ATTESTED"
FIXED_CASEBOOK_SHA256 = "0b0d150ab7d61c3ed82e1b5b631dd7594dff5beea146d34e593e069d2a003f16"
SOURCE_IDS = (
    "OECD_CPI_COICOP_1999", "OECD_CPI_COICOP_2018",
    "EUROSTAT_HICP_FIRST_PUBLISHED", "ABS_COMPLETE_MONTHLY_2025_TRANSITION",
    "STATSNZ_QUARTERLY_2026_MONTHLY_PLANNED_2027",
)
EXPECTED_CURRENCIES = ("EUR", "USD", "GBP", "JPY", "CHF", "AUD", "CAD", "NZD")
REQUIREMENTS = (
    "DATASET_SERIES_KEYS_AND_COUNTRY_COVERAGE_VERIFY",
    "OECD_1999_VS_2018_METHOD_AND_TRANSITION_CHECK",
    "AUSTRALIA_OECD_VS_ABS_MONTHLY_FREQUENCY_RECONCILIATION",
    "NEW_ZEALAND_QUARTERLY_VS_MONTHLY_COMPATIBILITY",
    "EURO_AREA_HICP_FIRST_PUBLISHED_SCHEMA_CHECK",
    "API_ORIGINAL_RESPONSE_RECEIPT_AND_PUBLISH_TIME",
    "HISTORICAL_VINTAGE_AND_PRE_EVENT_EXPECTATIONS",
    "DATA_USE_AND_REDISTRIBUTION_LICENSE_VERIFY",
)


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_BLOCKED", "reason": reason,
        "accepted_casebook_sha256": None,
        "candidate_source_count": 0,
        "candidate_source_identifiers": [],
        "currency_count": 0, "pair_count": 0,
        "currencies_with_domestic_monthly_2026_cpi_claim": [],
        "currencies_with_domestic_quarterly_2026_cpi_claim": [],
        "currency_source_routes_are_hypothetical": {},
        "all_28_pairs_have_identical_frequency_and_method_verified": False,
        "all_8_currencies_monthly_2026_verified": False,
        "oecd_current_api_is_historical_pit_vintage": False,
        "eurostat_first_published_is_full_historical_release_clock": False,
        "oecd_currency_level_series_responses_verified": False,
        "commercial_redistribution_verified": False,
        "next_experiment": None, "prerequisites_not_met": list(REQUIREMENTS),
        "validated_prediction_count": 0, "validated_accuracy": None,
        "ranked_currencies": [], "best_pair_of_day": None,
        "fx_bias": None, "operational_bias": "AGUARDAR",
        "can_feed_live_radar": False, "trade_authorized": False,
        "publishable": False, "worker_enabled": False,
        "scheduler_enabled": False, "http_requests": 0, "new_cost_brl": 0,
    }


def _no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out = {}
    for key, value in pairs:
        if key in out:
            raise ValueError("Duplicate key")
        out[key] = value
    return out


def inspect_g8_cpi_source_feasibility_lab(raw: Any) -> dict[str, Any]:
    """Inventory candidates without fetching or trusting their numeric data."""
    out = _blocked("INVALID_PINNED_RESEARCH_CASEBOOK_OR_G8_UNIVERSE")
    if (not isinstance(raw, bytes) or not 300 <= len(raw) <= 16000
            or sha256(raw).hexdigest() != FIXED_CASEBOOK_SHA256
            or len(CURRENCIES) != 8 or len(OFFICIAL_PAIRS) != 28
            or set(CURRENCIES) != set(EXPECTED_CURRENCIES)):
        return out
    try:
        case = json.loads(raw.decode("utf-8", "strict"),
                          object_pairs_hook=_no_duplicates,
                          parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite")))
        sources, routes = case["sources"], case["routes"]
        if (case["schema"] != SCHEMA or case["kind"] != KIND
                or case["research_date"] != "2026-11-06"
                or case["source_api_responses_archived"] is not False
                or case["source_dataset_coverage_per_currency_verified"] is not False
                or case["original_historical_release_vintages_attested"] is not False
                or case["source_redistribution_rights_verified"] is not False
                or tuple(s["source_id"] for s in sources) != SOURCE_IDS
                or tuple(r["currency"] for r in routes) != EXPECTED_CURRENCIES
                or any(s["full_g8_monthly_2026_coverage_verified"] is not False or
                       s["historical_first_publication_archived_for_all_g8"] is not False
                       for s in sources)
                or any(r["oecd_specific_series_verified"] is not False or
                       r["pit_release_clock_independently_attested"] is not False
                       for r in routes)
                or any(r["primary_research_source_id"] not in SOURCE_IDS
                       for r in routes)
                or case["future_nzd_monthly_2027_already_published_in_2026"] is not False
                or len(case["conflicts_and_limitations"]) != 6
                or len({frozenset(split_pair(p)) for p in OFFICIAL_PAIRS}) != 28):
            return out
        domestic_monthly = [r["currency"] for r in routes
                            if r["domestic_release_frequency_2026"] == "MONTHLY"]
        domestic_quarterly = [r["currency"] for r in routes
                              if r["domestic_release_frequency_2026"] == "QUARTERLY"]
        if (len(domestic_monthly) != 7 or domestic_quarterly != ["NZD"]
                or case["planned_next_experiment"] !=
                   "EUROSTAT_HICP_FIRST_PUBLISHED_SCHEMA_AND_GEO_EA20_READONLY_CHECK"):
            return out
    except (TypeError, ValueError, KeyError, AttributeError, UnicodeDecodeError,
            RecursionError):
        return out
    out.update({
        "state": "LAB_G8_CPI_SOURCE_CANDIDATES_FOUND_BUT_NOT_PIT_READY",
        "reason": "OECD_SOURCE_SCHEMA_COVERAGE_AND_EUROSTAT_VINTAGE_NOT_ATTESTED",
        "accepted_casebook_sha256": sha256(raw).hexdigest(),
        "candidate_source_count": len(sources),
        "candidate_source_identifiers": list(SOURCE_IDS),
        "currency_count": len(CURRENCIES), "pair_count": len(OFFICIAL_PAIRS),
        "currencies_with_domestic_monthly_2026_cpi_claim": domestic_monthly,
        "currencies_with_domestic_quarterly_2026_cpi_claim": domestic_quarterly,
        "currency_source_routes_are_hypothetical": {
            r["currency"]: r["primary_research_source_id"] for r in routes},
        "next_experiment": case["planned_next_experiment"],
    })
    return out


__all__ = ["SCHEMA", "FIXED_CASEBOOK_SHA256", "REQUIREMENTS",
           "inspect_g8_cpi_source_feasibility_lab"]
