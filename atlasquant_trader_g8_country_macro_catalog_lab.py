"""AtlasQuant Trader: G8 country-specific macro research candidates (offline LAB).

This is a *proposal*, not a validated policy, live rate feed, macro strength
model, release calendar, authenticated vendor lineage or trading advice.
The four groups must be preselected and historically audited before OOS.
Country-specific inflation cadences and the EUR harmonised index matter.

No I/O, HTTP, network, real forecasts, active workers or trading.
"""
from __future__ import annotations

from atlasquant_fx_universe import CURRENCIES, OFFICIAL_PAIRS
from atlasquant_trader_g8_macro_context_lab import (
    GROUPS, GROUP_BY_INDICATOR,
)
from atlasquant_trader_g8_macro_selection_lab import METHOD as SELECTION_METHOD
from atlasquant_trader_macro_surprise_pit_lab import INDICATORS, UNITS

SCHEMA = "ATLASQUANT_TRADER_COUNTRY_MACRO_CANDIDATES_LAB_V1"
CANDIDATE_STATUS = "RESEARCH_CANDIDATE_REQUIRES_REVIEW"
CATEGORIES = ("MONTHLY", "QUARTERLY", "EVENT_DRIVEN")
# SOURCE URLs are only shown where provider documentation has been
# checked in this LAB research round. Other producer names remain leads.
# None of these are authorized as historical data ingestors or proven vintages.
COUNTRY_CONFIG = {
    "USD": {
        "country": "United States", "inflation": "CPI",
        "inflation_publisher": "US Bureau of Labor Statistics",
        "employment_publisher": "US Bureau of Labor Statistics",
        "policy_publisher": "Federal Reserve", "activity_publisher": "US Bureau of Economic Analysis",
        "inflation_cadence": "MONTHLY", "employment_cadence": "MONTHLY",
        "inflation_url": "", "policy_name": "Fed target policy rate (definition under review)",
    },
    "EUR": {
        "country": "Euro area", "inflation": "HICP",
        "inflation_publisher": "Eurostat", "employment_publisher": "Eurostat",
        "policy_publisher": "European Central Bank", "activity_publisher": "Eurostat",
        "inflation_cadence": "MONTHLY", "employment_cadence": "MONTHLY",
        "inflation_url": "https://ec.europa.eu/eurostat/web/hicp/information-data",
        "policy_name": "ECB deposit facility rate (candidate)",
    },
    "GBP": {
        "country": "United Kingdom", "inflation": "CPI",
        "inflation_publisher": "Office for National Statistics",
        "employment_publisher": "Office for National Statistics",
        "policy_publisher": "Bank of England", "activity_publisher": "Office for National Statistics",
        "inflation_cadence": "MONTHLY", "employment_cadence": "MONTHLY",
        "inflation_url": "", "policy_name": "Bank Rate (candidate)",
    },
    "JPY": {
        "country": "Japan", "inflation": "CPI",
        "inflation_publisher": "Statistics Bureau of Japan",
        "employment_publisher": "Statistics Bureau of Japan",
        "policy_publisher": "Bank of Japan", "activity_publisher": "Cabinet Office of Japan",
        "inflation_cadence": "MONTHLY", "employment_cadence": "MONTHLY",
        "inflation_url": "", "policy_name": "BOJ short-term policy rate (definition under review)",
    },
    "CHF": {
        "country": "Switzerland", "inflation": "CPI",
        "inflation_publisher": "Swiss Federal Statistical Office",
        "employment_publisher": "SECO",
        "policy_publisher": "Swiss National Bank", "activity_publisher": "SECO",
        "inflation_cadence": "MONTHLY", "employment_cadence": "MONTHLY",
        "inflation_url": "", "policy_name": "SNB policy rate (candidate)",
    },
    "CAD": {
        "country": "Canada", "inflation": "CPI",
        "inflation_publisher": "Statistics Canada",
        "employment_publisher": "Statistics Canada",
        "policy_publisher": "Bank of Canada", "activity_publisher": "Statistics Canada",
        "inflation_cadence": "MONTHLY", "employment_cadence": "MONTHLY",
        "inflation_url": "", "policy_name": "BoC target overnight rate (candidate)",
    },
    "AUD": {
        "country": "Australia", "inflation": "CPI",
        "inflation_publisher": "Australian Bureau of Statistics",
        "employment_publisher": "Australian Bureau of Statistics",
        "policy_publisher": "Reserve Bank of Australia",
        "activity_publisher": "Australian Bureau of Statistics",
        "inflation_cadence": "MONTHLY", "employment_cadence": "MONTHLY",
        "inflation_url": (
            "https://www.abs.gov.au/statistics/economy/price-indexes-and-inflation/"
            "consumer-price-index-australia/latest-release"
        ),
        "policy_name": "RBA cash rate target (candidate)",
    },
    "NZD": {
        "country": "New Zealand", "inflation": "CPI",
        "inflation_publisher": "Stats NZ", "employment_publisher": "Stats NZ",
        "policy_publisher": "Reserve Bank of New Zealand",
        "activity_publisher": "Stats NZ",
        "inflation_cadence": "QUARTERLY", "employment_cadence": "QUARTERLY",
        "inflation_url": "https://www.stats.govt.nz/indicators/consumers-price-index-cpi/",
        "policy_name": "RBNZ Official Cash Rate (candidate)",
    },
}
GROUP_LABELS = {
    "INFLATION": ("CPI", "PERCENT", "MONTHLY", "CPI_YOY_PERCENT"),
    "EMPLOYMENT": ("UNEMPLOYMENT", "PERCENT", "MONTHLY", "UNEMPLOYMENT_RATE_PERCENT"),
    "POLICY": ("POLICY_RATE", "PERCENT", "EVENT_DRIVEN", "RATE_LEVEL_PERCENT"),
    "ACTIVITY": ("GDP", "PERCENT", "QUARTERLY", "GDP_QOQ_DEFINITION_UNVERIFIED"),
}
GROUP_AGENCY_KEYS = {
    "INFLATION": "inflation_publisher", "EMPLOYMENT": "employment_publisher",
    "POLICY": "policy_publisher", "ACTIVITY": "activity_publisher",
}


def build_g8_country_macro_candidate_catalog_lab() -> dict:
    """Produce 32 non-approved indicator suggestions, no external data access."""
    if set(COUNTRY_CONFIG) != set(CURRENCIES):
        raise ValueError("Country mapping is not complete G8 FX universe")
    rows = []
    for currency in CURRENCIES:
        config = COUNTRY_CONFIG[currency]
        for group in GROUPS:
            indicator, unit, cadence, measure = GROUP_LABELS[group]
            if group == "INFLATION":
                indicator = config["inflation"]
                cadence = config["inflation_cadence"]
                measure = ("HICP_YOY_PERCENT_FLASH_FINAL_STAGE_UNSELECTED"
                           if indicator == "HICP" else "CPI_YOY_PERCENT")
            if group == "EMPLOYMENT":
                cadence = config["employment_cadence"]
            if indicator not in INDICATORS or GROUP_BY_INDICATOR.get(indicator) != group:
                raise ValueError("Catalog indicator has no compatible LAB parser")
            if unit not in UNITS or cadence not in CATEGORIES:
                raise ValueError("Catalog unit or cadence invalid")
            publisher = config[GROUP_AGENCY_KEYS[group]]
            if group == "POLICY":
                definition = config["policy_name"]
            elif group == "ACTIVITY":
                definition = "GDP: calendar, seasonality and country QoQ method need review"
            elif group == "INFLATION" and currency == "EUR":
                definition = "Euro-area HICP: flash/final/revision stage NOT selected"
            elif group == "INFLATION" and currency == "NZD":
                definition = "NZ quarterly CPI in 2026; monthly CPI is planned for 2027"
            else:
                definition = measure + ": base-year/vintage/consensus need review"
            rows.append({
                "currency": currency, "country": config["country"],
                "group": group, "indicator_id": indicator,
                "unit": unit, "publisher_candidate": publisher,
                "cadence_candidate": cadence,
                "measure_definition": measure,
                "release_definition_note": definition,
                "source_info_url": (
                    config["inflation_url"] if group == "INFLATION" else ""
                ),
                "research_status": CANDIDATE_STATUS,
                "vintage_and_consensus_verified": False,
                "publisher_response_attested": False,
                "license_for_automated_reuse_verified": False,
                "release_calendar_verified": False,
                "allowed_for_live_bias": False,
            })
    if (len(rows) != len(CURRENCIES) * len(GROUPS) or
            len({(x["currency"], x["group"]) for x in rows}) != len(rows)):
        raise ValueError("Candidate research slots duplicated")
    return {
        "schema": SCHEMA, "state": "LAB_COUNTRY_MACRO_CANDIDATES_UNAPPROVED",
        "currency_count": len(CURRENCIES), "pair_count": len(OFFICIAL_PAIRS),
        "candidate_slots": len(rows),
        "candidates": rows,
        "research_selection_approved": False,
        "real_macro_records_verified": False,
        "predictive_edge_proven": False,
        "automatic_macro_direction": "UNDETERMINED",
        "worker_enabled": False, "scheduler_enabled": False,
        "trade_authorized": False,
        "risk_note": "Quarterly NZD CPI is not a missing monthly release; "
                     "EUR HICP is not national CPI; GDP QoQ and central-bank "
                     "policy levels need definition checks before comparing "
                     "countries. Proposed producers are research leads only.",
    }


def draft_g8_country_macro_policy_lab(
    *, policy_id: str, registered_at_utc: str, experiment_start_at_utc: str,
) -> dict:
    """Build a SYNTHETIC policy DOCUMENT template; never freeze or approve it.

    Actual policy freeze requires separate review via the existing
    freeze_g8_macro_indicator_policy_lab API, with valid research clock.
    Caller timestamps are untrusted; this draft is NOT a precommitment.
    """
    catalog = build_g8_country_macro_candidate_catalog_lab()
    choices = []
    for x in catalog["candidates"]:
        why = (f"LAB candidate {x['currency']} {x['group']}: "
               f"{x['indicator_id']} via {x['publisher_candidate']}; "
               "review release cadence/vintages before actual use")
        choices.append({
            "currency": x["currency"], "group": x["group"],
            "indicator_id": x["indicator_id"], "unit": x["unit"],
            "rationale": why[:250],
        })
    return {
        "schema": SCHEMA, "state": "LAB_COUNTRY_MACRO_POLICY_TEMPLATE_NOT_FROZEN",
        "policy_document": {
            "state": "LAB_SYNTHETIC_G8_MACRO_POLICY",
            "method_id": SELECTION_METHOD, "policy_id": policy_id,
            "registered_at_utc": registered_at_utc,
            "experiment_start_at_utc": experiment_start_at_utc,
            "selections": choices,
        },
        "source_catalog": catalog["state"],
        "precommitment_verified": False,
        "review_and_user_approval_required": True,
        "real_historical_data_verified": False,
        "trade_authorized": False, "worker_enabled": False,
        "scheduler_enabled": False,
    }


__all__ = [
    "SCHEMA", "CANDIDATE_STATUS",
    "build_g8_country_macro_candidate_catalog_lab",
    "draft_g8_country_macro_policy_lab",
]
