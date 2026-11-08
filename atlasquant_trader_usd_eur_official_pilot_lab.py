"""USD/EUR official-page research pilot; deliberately NOT a trading feature.

Publication date, observation period, indicator definition, release stage and
availability boundary must remain distinct. The numeric values below were
researched on publisher web pages in November 2026; no original point-in-time
document captures or historical revision guarantees accompany them.

All outputs abstain from forecasts, signals, probabilities and backtest approval.
No network calls, broker access, credential access, orders or background tasks.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

SCHEMA = "ATLASQUANT_TRADER_USD_EUR_OFFICIAL_PUBLICATION_PILOT_LAB_V1"
RESEARCH_REVIEW_DATE_UTC = "2026-11-08"  # Not a historic capture timestamp.

# BLS and FOMC pages give specific US/Eastern release times; October is EDT
# (UTC-4). Eurostat and ECB releases below establish dates, not exact times;
# their next-day 00:00 UTC floor is a conservative *inference*, not a claim
# about the actual instant each page was first publicly available.
# Do NOT silently compare US CPI-U with Eurozone HICP as the same index, nor
# the US target RANGE with an ECB deposit-facility POINT rate as equivalent
# policy instruments.
OFFICIAL_OBSERVATIONS: dict[str, dict[str, Any]] = {
    "USD_CPI_2026_09_FINAL": {
        "currency": "USD", "family": "INFLATION", "metric": "US_CPI_U_ALL_ITEMS_12M_PCT",
        "observation_period": "2026-09", "stage": "PUBLISHED_RELEASE",
        "value_percent": "3.7", "rate_shape": None,
        "published_date": "2026-10-14", "release_local": "08:30 America/New_York (EDT)",
        "availability_floor_utc": "2026-10-14T12:30:00Z",
        "time_evidence": "EXACT_PUBLISHER_RELEASE_TIME",
        "document_url": "https://www.bls.gov/news.release/archives/cpi_10142026.htm",
    },
    "EUR_HICP_2026_09_FINAL": {
        "currency": "EUR", "family": "INFLATION", "metric": "EA_HICP_12M_PCT",
        "observation_period": "2026-09", "stage": "FINAL_RELEASE",
        "value_percent": "3.8", "rate_shape": None,
        "published_date": "2026-10-16", "release_local": None,
        "availability_floor_utc": "2026-10-17T00:00:00Z",
        "time_evidence": "PUBLISHER_DATE_ONLY_CONSERVATIVE_NEXT_UTC_DAY",
        "document_url": "https://ec.europa.eu/eurostat/en/web/products-euro-indicators/w/2-16102026-ap",
    },
    "USD_FED_TARGET_2026_10": {
        "currency": "USD", "family": "POLICY", "metric": "FED_FUNDS_TARGET_RANGE_PCT",
        "observation_period": "DECISION_2026-10-28", "stage": "POLICY_STATEMENT",
        "value_percent": None, "rate_shape": "RANGE",
        "range_lower_percent": "3.75", "range_upper_percent": "4.00",
        "published_date": "2026-10-28", "release_local": "14:00 America/New_York (EDT)",
        "availability_floor_utc": "2026-10-28T18:00:00Z",
        "time_evidence": "EXACT_PUBLISHER_RELEASE_TIME",
        "document_url": "https://www.federalreserve.gov/newsevents/pressreleases/monetary20261028a.htm",
    },
    "EUR_ECB_DEPOSIT_RATE_2026_10": {
        "currency": "EUR", "family": "POLICY", "metric": "ECB_DEPOSIT_FACILITY_PCT",
        "observation_period": "DECISION_2026-10-29", "stage": "POLICY_DECISION",
        "value_percent": "2.50", "rate_shape": "POINT",
        "published_date": "2026-10-29", "release_local": None,
        "availability_floor_utc": "2026-10-30T00:00:00Z",
        "time_evidence": "PUBLISHER_DATE_ONLY_CONSERVATIVE_NEXT_UTC_DAY",
        "document_url": "https://www.ecb.europa.eu/press/pr/date/2026/html/ecb.mp261029~9a493adf17.en.html",
    },
    "EUR_HICP_2026_10_FLASH": {
        "currency": "EUR", "family": "INFLATION", "metric": "EA_HICP_12M_PCT",
        "observation_period": "2026-10", "stage": "FLASH_PRELIMINARY",
        "value_percent": "4.0", "rate_shape": None,
        "published_date": "2026-11-04", "release_local": None,
        "availability_floor_utc": "2026-11-05T00:00:00Z",
        "time_evidence": "PUBLISHER_DATE_ONLY_CONSERVATIVE_NEXT_UTC_DAY",
        "document_url": "https://ec.europa.eu/eurostat/web/products-euro-indicators/w/2-04112026-ap",
    },
}


def _parse_utc(raw: str) -> datetime:
    return datetime.fromisoformat(raw.replace("Z", "+00:00")).astimezone(timezone.utc)


def inspect_usd_eur_official_pilot_lab(*, decision_at_utc: datetime) -> dict[str, Any]:
    """Expose publisher research values after conservative availability floors.

    Passing this publication boundary is NOT proof of historical vintage or
    authorisation to use the values in a backtest. This research catalogue
    records what was checked in November, not what the engine knew in October.
    """
    if (not isinstance(decision_at_utc, datetime)
            or decision_at_utc.tzinfo is None
            or decision_at_utc.utcoffset() is None
            or decision_at_utc.microsecond != 0):
        raise ValueError("Require timezone-aware decision time at whole-second precision")
    decision = decision_at_utc.astimezone(timezone.utc)
    records: dict[str, dict[str, Any]] = {}
    for key, source in sorted(OFFICIAL_OBSERVATIONS.items()):
        passed = decision >= _parse_utc(source["availability_floor_utc"])
        records[key] = {
            "currency": source["currency"], "family": source["family"],
            "metric": source["metric"], "observation_period": source["observation_period"],
            "stage": source["stage"], "published_date": source["published_date"],
            "release_local": source["release_local"],
            "availability_floor_utc": source["availability_floor_utc"],
            "time_evidence": source["time_evidence"],
            "document_url": source["document_url"], "rate_shape": source["rate_shape"],
            "publisher_timing_status": (
                "AFTER_CONSERVATIVE_PUBLISHER_BOUNDARY_ONLY"
                if passed else "NOT_YET_PUBLIC_BY_BOUNDARY"
            ),
            "research_value_percent": source["value_percent"] if passed else None,
            "research_range_lower_percent": (
                source.get("range_lower_percent") if passed else None
            ),
            "research_range_upper_percent": (
                source.get("range_upper_percent") if passed else None
            ),
            "original_historical_bytes_archived": False,
            "independent_historical_capture_attested": False,
            "revisions_excluded": False,
            "eligible_for_exante_backtest": False,
        }
    return {
        "schema": SCHEMA, "state": "LAB_OFFICIAL_PAGES_RESEARCH_ONLY",
        "reviewed_on_utc_date": RESEARCH_REVIEW_DATE_UTC,
        "decision_at_utc": decision.isoformat(),
        "publisher_boundary_passed_count": sum(
            row["publisher_timing_status"] == "AFTER_CONSERVATIVE_PUBLISHER_BOUNDARY_ONLY"
            for row in records.values()
        ),
        "observation_count": len(records), "observations": records,
        "historical_capture_attested": False, "point_in_time_backtest_approved": False,
        "macro_cross_currency_comparison_approved": False,
        "forecast_probability": None, "operational_bias": "AGUARDAR",
        "trade_authorized": False, "worker_enabled": False,
        "scheduler_enabled": False, "new_cost_brl": 0,
    }


__all__ = ["SCHEMA", "RESEARCH_REVIEW_DATE_UTC", "OFFICIAL_OBSERVATIONS", "inspect_usd_eur_official_pilot_lab"]
