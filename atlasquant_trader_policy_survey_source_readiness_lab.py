"""Research-only G8 policy-expectations source taxonomy and publication gate.

Survey responses and central-bank narrative are not market OIS quotes.  Public
release dates below were researched on 2026-11-10, without publisher-page
byte archives or historical access-time attestations.  Never backfill the
research into earlier D1/W1 decisions or call these observations live data.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any

from atlasquant_fx_universe import CURRENCIES, OFFICIAL_PAIRS, split_pair

SCHEMA = "ATLASQUANT_TRADER_G8_POLICY_SURVEY_SOURCE_READINESS_LAB_V1"
RESEARCH_VISIBLE_FROM_UTC = datetime(2026, 11, 11, tzinfo=timezone.utc)


@dataclass(frozen=True)
class SourceResearch:
    source_kind: str
    publisher_url: str | None
    published_calendar_day_research: date | None
    cadence_class: str


# Official issuer pages, not captured raw quotes. Publication dates are
# calendar-level research: exact publication instants remain unverified.
SOURCES = {
    "USD": SourceResearch(
        "FED_NY_MARKET_EXPECTATIONS_SURVEY",
        "https://www.newyorkfed.org/markets/market-intelligence/survey-of-market-expectations",
        None, "FOMC_RELATED_POST_MEETING_RESULT_LAG"),
    "EUR": SourceResearch(
        "ECB_MONETARY_ANALYSTS_SURVEY",
        "https://www.ecb.europa.eu/stats/ecb_surveys/sma/html/all-releases.en.html",
        date(2026, 10, 30), "POLICY_MEETING_ROUNDS"),
    "GBP": SourceResearch(
        "BOE_MARKET_PARTICIPANTS_SURVEY",
        "https://www.bankofengland.co.uk/markets/market-intelligence/survey-results/2026/market-participants-survey-results-november-2026",
        None, "POLICY_MEETING_ROUNDS"),
    "CAD": SourceResearch(
        "BOC_MARKET_PARTICIPANTS_SURVEY",
        "https://www.bankofcanada.ca/2026/11/market-participants-survey-third-quarter-of-2026/",
        date(2026, 11, 9), "QUARTERLY"),
    "AUD": SourceResearch(
        "RBA_FINANCIAL_CONDITIONS_COMMENTARY",
        "https://www.rba.gov.au/publications/smp/2026/nov/financial-conditions.html",
        None, "POLICY_REPORT_NARRATIVE_NOT_RAW_OIS_QUOTE"),
    "JPY": SourceResearch(
        "NO_VERIFIED_MARKET_EXPECTATIONS_SOURCE_YET", None, None,
        "UNVERIFIED"),
    "CHF": SourceResearch(
        "NO_VERIFIED_MARKET_EXPECTATIONS_SOURCE_YET", None, None,
        "UNVERIFIED"),
    "NZD": SourceResearch(
        "RBNZ_SURVEY_OF_EXPECTATIONS",
        "https://www.rbnz.govt.nz/hub/home/statistics/series/economic-indicators/survey-of-expectations",
        date(2026, 8, 13), "QUARTERLY"),
}


def _blocked(state: str, reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": state, "reason": reason,
        "as_of_utc": None, "currency_count": 0, "pair_count": 0,
        "survey_context_calendar_dates_researched": 0,
        "currency_rows": [], "pair_rows": [],
        "publisher_bytes_independently_archived": False,
        "exact_publication_instants_independently_verified": False,
        "historical_point_in_time_access_attested": False,
        "market_ois_quotes_independently_authenticated": False,
        "survey_values_are_tradable_market_quotes": False,
        "intraday_three_updates_supported": False,
        "survey_can_feed_three_month_ois_vintages": False,
        "calibrated_direction_probability": None,
        "fx_bias": None, "operational_bias": "AGUARDAR",
        "trade_authorized": False, "publishable": False,
        "scheduler_enabled": False, "http_requests": 0, "file_writes": 0,
        "new_cost_brl": 0,
    }


def inspect_policy_survey_sources_lab(*, as_of_utc: Any) -> dict[str, Any]:
    """Expose known source *types* without turning surveys into live OIS data."""
    out = _blocked("LAB_INVALID_AS_OF", "INVALID_AS_OF_OR_UNIVERSE")
    if (not isinstance(as_of_utc, datetime) or as_of_utc.tzinfo is None
            or as_of_utc.utcoffset() is None or len(CURRENCIES) != 8
            or len(OFFICIAL_PAIRS) != 28 or set(SOURCES) != set(CURRENCIES)):
        return out
    now = as_of_utc.astimezone(timezone.utc)
    if now < RESEARCH_VISIBLE_FROM_UTC:
        return _blocked("LAB_RESEARCH_NOT_VISIBLE_AS_OF",
                        "NO_HISTORIC_RESEARCH_AVAILABILITY_PROOF")
    currency_rows = []
    for currency in CURRENCIES:
        s = SOURCES[currency]
        # Calendar-only publication research receives a next-UTC-day floor.
        # It is never interpreted as a verified exact public release instant.
        day_floor = (datetime.combine(s.published_calendar_day_research + timedelta(days=1),
                                      datetime.min.time(), tzinfo=timezone.utc)
                     if s.published_calendar_day_research is not None else None)
        currency_rows.append({
            "currency": currency, "research_source_kind": s.source_kind,
            "official_source_page": s.publisher_url,
            "cadence_class": s.cadence_class,
            "published_calendar_day_research": (
                s.published_calendar_day_research.isoformat()
                if s.published_calendar_day_research is not None else None),
            "conservative_calendar_publication_floor_utc": (
                day_floor.isoformat() if day_floor is not None else None),
            "date_only_research_visible_in_current_report": (
                day_floor is not None and now >= day_floor),
            "exact_publication_instant_attested": False,
            "market_implied_three_month_rate_attested": False,
            "can_feed_ois_quote_deltas": False,
        })
    rows = {x["currency"]: x for x in currency_rows}
    pair_rows = []
    for pair in OFFICIAL_PAIRS:
        base, quote = split_pair(pair)
        pair_rows.append({
            "pair": pair, "base": base, "quote": quote,
            "base_calendar_date_researched": rows[base]["date_only_research_visible_in_current_report"],
            "quote_calendar_date_researched": rows[quote]["date_only_research_visible_in_current_report"],
            "market_rate_expectation_pair_comparable": False,
            "D1": "AGUARDAR", "W1": "AGUARDAR",
            "can_feed_live_radar": False, "trade_authorized": False,
        })
    out = _blocked("LAB_SURVEY_SOURCE_TYPES_CATALOGUED_NOT_OIS",
                   "SURVEY_PUBLICATION_AND_MARKET_QUOTE_ARE_DISTINCT")
    out.update(as_of_utc=now.isoformat(), currency_count=8, pair_count=28,
               currency_rows=currency_rows, pair_rows=pair_rows,
               survey_context_calendar_dates_researched=sum(
                   x["date_only_research_visible_in_current_report"] for x in currency_rows))
    return out
