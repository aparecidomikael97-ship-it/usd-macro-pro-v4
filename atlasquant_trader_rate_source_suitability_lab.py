"""Official rate-source *suitability* ledger, without prices or trade inference.

The source inventory is a fixed documentary classification as reviewed on
2026-11-03. It is NOT a live scraper, validated license opinion, nor an
operational data feed. A rate level, bond yield, OIS forward and exchange-traded
FOMC probability are not interchangeable economic measurements.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

SCHEMA = "ATLASQUANT_TRADER_RATE_SOURCE_SUITABILITY_LAB_V1"
SOURCE_REVIEW_DATE = "2026-11-03"
SOURCES: tuple[dict[str, Any], ...] = (
    {
        "source_id": "BOE_GBP_OIS_DAILY_ARCHIVE",
        "currency": "GBP",
        "source": "BANK_OF_ENGLAND",
        "source_url": "https://www.bankofengland.co.uk/statistics/yield-curves",
        "instrument": "STERLING_SONIA_OIS_INSTANTANEOUS_FORWARD",
        "economic_meaning": "MARKET_IMPLIED_FUTURE_OVERNIGHT_RATE",
        "distribution": "PUBLIC_DOWNLOAD_NO_API",
        "publication": "AIMS_NEXT_BUSINESS_DAY_BY_NOON_UK",
        "rights": "INTERNAL_RESEARCH_ONLY_PENDING_THIRD_PARTY_RIGHTS_REVIEW",
        "paid_api_required": False,
        "actual_observation_ingested": False,
        "rights_cleared_for_live_trader": False,
    },
    {
        "source_id": "ECB_EUR_ESTR_OVERNIGHT",
        "currency": "EUR",
        "source": "ECB",
        "source_url": "https://www.ecb.europa.eu/stats/financial_markets_and_interest_rates/euro_short-term_rate/html/index.en.html",
        "instrument": "EURO_ESTR_ACTUAL_OVERNIGHT_FIXING",
        "economic_meaning": "REALIZED_OVERNIGHT_FUNDING_RATE",
        "distribution": "PUBLIC_NO_FEE_ECB",
        "publication": "NEXT_TARGET_BUSINESS_DAY_08_CET",
        "rights": "ECB_STATES_NO_CHARGE_OR_LICENSE_FOR_ESTR",
        "paid_api_required": False,
        "actual_observation_ingested": False,
        "rights_cleared_for_live_trader": False,
    },
    {
        "source_id": "ECB_EUR_SOVEREIGN_YIELD_FORWARD",
        "currency": "EUR",
        "source": "ECB",
        "source_url": "https://www.ecb.europa.eu/stats/financial_markets_and_interest_rates/euro_area_yield_curves/html/index.en.html",
        "instrument": "EURO_AREA_GOVERNMENT_BOND_DERIVED_FORWARD",
        "economic_meaning": "SOVEREIGN_BOND_TERM_STRUCTURE_WITH_RISK_PREMIA",
        "distribution": "PUBLIC_ECB_SDMX",
        "publication": "TARGET_BUSINESS_DAY_NOON_EUROPE",
        "rights": "ECB_SECTION_DISCLAIMS_USE_TO_IDENTIFY_TRADING_OPPORTUNITIES",
        "paid_api_required": False,
        "actual_observation_ingested": False,
        "rights_cleared_for_live_trader": False,
    },
    {
        "source_id": "CME_USD_FEDWATCH_PAID_API",
        "currency": "USD",
        "source": "CME",
        "source_url": "https://www.cmegroup.com/market-data/market-data-api/fedwatch-api.html",
        "instrument": "FED_FUNDS_FUTURES_DERIVED_FOMC_OUTCOME_PROBABILITY",
        "economic_meaning": "MARKET_IMPLIED_EVENT_OUTCOME_DISTRIBUTION",
        "distribution": "PAID_API_ADVERTISED_FROM_USD_25_MONTH",
        "publication": "API_STREAM_PRODUCT",
        "rights": "PAYMENT_AND_DATA_LICENSE_NOT_AUTHORIZED",
        "paid_api_required": True,
        "actual_observation_ingested": False,
        "rights_cleared_for_live_trader": False,
    },
    {
        "source_id": "NYFED_USD_SOFR_FIXING",
        "currency": "USD",
        "source": "NEW_YORK_FED",
        "source_url": "https://www.newyorkfed.org/markets/reference-rates/sofr",
        "instrument": "US_SECURED_OVERNIGHT_REPO_FIXING",
        "economic_meaning": "REALIZED_SECURED_OVERNIGHT_FUNDING_RATE",
        "distribution": "PUBLIC_REFERENCE_PAGE",
        "publication": "OFFICIAL_HISTORICAL_REFERENCE",
        "rights": "RESEARCH_CONTEXT_NOT_ASSESSED_FOR_PRODUCT_REUSE",
        "paid_api_required": False,
        "actual_observation_ingested": False,
        "rights_cleared_for_live_trader": False,
    },
)
SOURCE_BY_ID = {x["source_id"]: x for x in SOURCES}
REASONS = {
    "PUBLIC_DOWNLOAD_NO_API": "No BoE API; download/archive needs manual custody",
    "PUBLIC_NO_FEE_ECB": "Observed €STR, not a forward policy expectation",
    "PUBLIC_ECB_SDMX": "Sovereign yield contains term and credit risk; ECB section disclaims trading-use purpose",
    "PAID_API_ADVERTISED_FROM_USD_25_MONTH": "CME FedWatch API violates zero-new-cost condition",
    "PUBLIC_REFERENCE_PAGE": "SOFR is realized secured funding, not a policy path",
}


def _fail(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "state": "LAB_RATE_SOURCE_SELECTION_BLOCKED",
        "reason": reason,
        "base": None, "quote": None,
        "market_expectation_comparable": False,
        "expectation_spread_bps": None,
        "expected_repricing_bps": None,
        "fx_bias": None, "fx_probability": None,
        "can_feed_live_radar": False,
        "trade_authorized": False,
        "paid_service_activated": False,
        "worker_enabled": False, "scheduler_enabled": False,
    }


def audit_rate_source_catalog_lab() -> dict[str, Any]:
    """Return five reviewed documentary leads; no source has approved quotes."""
    return {
        "schema": SCHEMA, "state": "LAB_CATALOG_REVIEW_ONLY",
        "reviewed_on": SOURCE_REVIEW_DATE,
        "sources": deepcopy(SOURCES),
        "source_count": len(SOURCES),
        "usable_market_implied_fx_pair_count": 0,
        "all_eight_currencies_covered": False,
        "rights_and_historical_receipts_verified": False,
        "fx_probability": None, "fx_bias": None,
        "can_feed_live_radar": False, "paid_service_activated": False,
        "trade_authorized": False, "worker_enabled": False,
        "scheduler_enabled": False,
    }


def assess_rate_source_pair_lab(base_id: Any, quote_id: Any) -> dict[str, Any]:
    """Classify why two candidate series cannot yet yield a relative FX bias."""
    if (not isinstance(base_id, str) or not isinstance(quote_id, str)
            or base_id not in SOURCE_BY_ID or quote_id not in SOURCE_BY_ID):
        return _fail("Unknown or unreviewed source: no implicit trust")
    a, b = SOURCE_BY_ID[base_id], SOURCE_BY_ID[quote_id]
    if a["currency"] == b["currency"]:
        return _fail("Cannot compare the same currency with itself")
    if a["paid_api_required"] or b["paid_api_required"]:
        return _fail("Paid source excluded under no-new-cost owner mandate")
    if a["economic_meaning"] != b["economic_meaning"]:
        return _fail("Incompatible economic measurements; never subtract or rank")
    if a["instrument"] != b["instrument"]:
        # Same meaning still does not ensure matching collateral, compounding,
        # maturity tenor, release time, market and data license.
        return _fail("Distinct instruments require a documented economic conversion")
    if (not a["actual_observation_ingested"] or not b["actual_observation_ingested"]
            or not a["rights_cleared_for_live_trader"]
            or not b["rights_cleared_for_live_trader"]):
        return _fail("No verifiable matching as-of prices and rights for both currencies")
    # Even in an entirely new source catalog, source suitability alone cannot
    # calculate a return or forecast probability.
    return _fail("Source catalog alone is never a prediction")

__all__ = [
    "SCHEMA", "SOURCES", "audit_rate_source_catalog_lab",
    "assess_rate_source_pair_lab",
]
