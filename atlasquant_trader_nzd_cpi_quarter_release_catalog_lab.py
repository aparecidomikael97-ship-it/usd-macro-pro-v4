"""NZ quarterly CPI publication-page inventory, strictly research only.

Four individual Stats NZ CPI releases were inspected on 2026-11-08. Their
observation quarters are distinct from publication dates, and a present-day
release page does not attest to archived original bytes at the issue second.

The monthly Selected Price Indexes (SPI) available in 2026 are NOT the
quarterly all-groups headline CPI; do not substitute those for this series.
No economic bias, source-data ingestion, price join, backtest or trade.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

SCHEMA = "ATLASQUANT_TRADER_NZD_CPI_QUARTER_RELEASE_CATALOG_LAB_V1"
REVIEWED_DATE_UTC = "2026-11-08"
HORIZONS = ("D1", "W1")
INDEX_URL = "https://www.stats.govt.nz/indicators/consumers-price-index-cpi/"

# Present-day research-page numbers, not captured original release vintages.
# The two date-only floors are next-day UTC, not asserted release clock times.
RELEASES: tuple[dict[str, str], ...] = (
    {
        "period": "2025-Q4", "release_date_nz": "2026-01-23",
        "release_local_time": "NOT_ESTABLISHED_FOR_THIS_RELEASE",
        "availability_floor_utc": "2026-01-24T00:00:00Z",
        "time_evidence": "DATE_ONLY_NEXT_UTC_DAY_RESEARCH_CUTOFF",
        "cpi_yoy_pct_on_current_release_pages": "3.1",
        "url": "https://www.stats.govt.nz/information-releases/consumers-price-index-december-2025-quarter/",
    },
    {
        "period": "2026-Q1", "release_date_nz": "2026-04-21",
        "release_local_time": "NOT_ESTABLISHED_FOR_THIS_RELEASE",
        "availability_floor_utc": "2026-04-22T00:00:00Z",
        "time_evidence": "DATE_ONLY_NEXT_UTC_DAY_RESEARCH_CUTOFF",
        "cpi_yoy_pct_on_current_release_pages": "3.1",
        "url": "https://www.stats.govt.nz/information-releases/consumers-price-index-march-2026-quarter/",
    },
    {
        "period": "2026-Q2", "release_date_nz": "2026-07-21",
        "release_local_time": "10:45 Pacific/Auckland (NZST)",
        "availability_floor_utc": "2026-07-20T22:45:00Z",
        "time_evidence": "PUBLISHER_RELEASE_PAGE_CLOCK_RESEARCH_ONLY",
        "cpi_yoy_pct_on_current_release_pages": "4.1",
        "url": "https://www.stats.govt.nz/information-releases/consumers-price-index-june-2026-quarter/",
    },
    {
        "period": "2026-Q3", "release_date_nz": "2026-10-22",
        "release_local_time": "10:45 Pacific/Auckland (NZDT)",
        "availability_floor_utc": "2026-10-21T21:45:00Z",
        "time_evidence": "PUBLISHER_RELEASE_PAGE_CLOCK_RESEARCH_ONLY",
        "cpi_yoy_pct_on_current_release_pages": "3.7",
        "url": "https://www.stats.govt.nz/information-releases/consumers-price-index-september-2026-quarter/",
    },
)


def _parse_utc(s: str) -> datetime:
    # Never infer the executor's timezone for an incomplete source timestamp.
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def _blocked() -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_NZD_CPI_QUARTER_RESEARCH_BLOCKED",
        "decision_at_utc": None, "horizon": None,
        "records": {}, "research_available_count": 0,
        "original_issue_vintage_attested": False,
        "historical_backtest_approved": False,
        "operational_bias": "AGUARDAR", "forecast_probability": None,
        "trade_authorized": False, "worker_enabled": False,
        "scheduler_enabled": False, "http_requests": 0, "new_cost_brl": 0,
    }


def inspect_nzd_cpi_quarter_release_catalog_lab(
    *, decision_at_utc: datetime, horizon: str,
) -> dict[str, Any]:
    """Allow only retrospective research at conservative publisher cutoffs.

    Do not pass publisher-page research to a backtest as if it were original
    issue-time data. Timing floor alone cannot prove contemporaneous content.
    """
    out = _blocked()
    if (horizon not in HORIZONS or not isinstance(decision_at_utc, datetime)
            or decision_at_utc.tzinfo is None or decision_at_utc.utcoffset() is None
            or decision_at_utc.microsecond != 0):
        return out
    decision = decision_at_utc.astimezone(timezone.utc)
    rows = {}
    try:
        for release in RELEASES:
            available = decision >= _parse_utc(release["availability_floor_utc"])
            if release["period"] in rows:
                return _blocked()
            rows[release["period"]] = {
                "economic_observation_period": release["period"],
                "publisher_release_date_nz": release["release_date_nz"],
                "publisher_local_release_clock": release["release_local_time"],
                "conservative_availability_floor_utc": release["availability_floor_utc"],
                "time_evidence": release["time_evidence"],
                "official_release_page_url": release["url"],
                "research_available_by_publisher_boundary": available,
                "research_cpi_yoy_pct": (
                    release["cpi_yoy_pct_on_current_release_pages"] if available else None),
                "downloadable_assets_listed_on_release_page": True,
                "downloaded_original_release_assets_attested": False,
                "historical_original_issue_vintage_attested": False,
                "backtest_approved": False,
            }
    except (KeyError, TypeError, ValueError):
        return _blocked()
    out.update({
        "state": "LAB_NZD_QUARTERLY_CPI_PUBLISHER_RESEARCH_ONLY",
        "decision_at_utc": decision.isoformat(), "horizon": horizon,
        "currency": "NZD", "family": "INFLATION",
        "metric": "ALL_GROUPS_CPI_ANNUAL_PCT_QUARTERLY",
        "reviewed_on_utc_date": REVIEWED_DATE_UTC,
        "official_index_url": INDEX_URL,
        "monthly_cpi_in_2026": False,
        "monthly_selected_price_indexes_not_headline_cpi": True,
        "monthly_headline_cpi_announced_from_year": 2027,
        "records": rows,
        "research_available_count": sum(
            x["research_available_by_publisher_boundary"] for x in rows.values()),
    })
    return out


__all__ = ["SCHEMA", "RELEASES", "HORIZONS", "inspect_nzd_cpi_quarter_release_catalog_lab"]
