"""GBP/NZD publisher-page research pilot: no historical archive or trade authority.

Four 2026 official publication pages were manually reviewed. The publisher
release date, the *economic observation period*, and the date we inspected
the pages are independent facts. A publisher time does not prove that the
specific bytes were captured then or that the page has never been revised.

No network calls, prices, forecasts, P-I-T attestations, scores or orders.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from atlasquant_trader_nzd_ocr_decision_index_lab import INDEX_URL as RBNZ_DECISION_INDEX_URL

SCHEMA = "ATLASQUANT_TRADER_GBP_NZD_OFFICIAL_PUBLICATION_PILOT_LAB_V1"
RESEARCH_REVIEW_DATE_UTC = "2026-11-08"  # Date of research, NOT a capture receipt.

# Values and release timing checked against official publisher sites.
# For BOE, a general 12-noon publication policy was found, but the specific
# release page only confirms the *date*. A next-day cutoff is used instead.
# For RBNZ, 2pm is the current-rate page's update time, not proof of a
# contemporaneously archived 2026-10-28 monetary-policy document.
PILOT = {
    "GBP_CPI_2026_09": {
        "currency": "GBP", "family": "INFLATION", "metric": "CPI_12_MONTH_PCT",
        "observation_period": "2026-09", "value_percent": "3.5",
        "release_local": "2026-10-21 07:00 Europe/London (BST)",
        "availability_floor_utc": "2026-10-21T06:00:00Z",
        "time_evidence": "EXACT_ON_OFFICIAL_RELEASE_PAGE",
        "document_url": "https://www.ons.gov.uk/economy/inflationandpriceindices/bulletins/consumerpriceinflation/september2026",
        "timing_url": "https://www.ons.gov.uk/releases/consumerpriceinflationukseptember2026",
    },
    "NZD_CPI_2026_Q3": {
        "currency": "NZD", "family": "INFLATION", "metric": "CPI_12_MONTH_PCT",
        "observation_period": "2026-Q3", "value_percent": "3.7",
        "release_local": "2026-10-22 10:45 Pacific/Auckland (NZDT)",
        "availability_floor_utc": "2026-10-21T21:45:00Z",
        "time_evidence": "EXACT_ON_OFFICIAL_RELEASE_PAGE",
        "document_url": "https://www.stats.govt.nz/information-releases/consumers-price-index-september-2026-quarter/",
        "timing_url": "https://www.stats.govt.nz/information-releases/consumers-price-index-september-2026-quarter/",
    },
    "GBP_BANK_RATE_2026_11": {
        "currency": "GBP", "family": "POLICY", "metric": "POLICY_RATE_PCT",
        "observation_period": "DECISION_2026-11-05", "value_percent": "4.0",
        "release_local": "2026-11-05 (time on release page not established)",
        # Conservative next-day UTC boundary; this is NOT a publication time.
        "availability_floor_utc": "2026-11-06T00:00:00Z",
        "time_evidence": "DATE_ONLY_USE_NEXT_DAY; GENERAL_POLICY_12_NOON",
        "document_url": "https://www.bankofengland.co.uk/monetary-policy-summary-and-minutes/2026/november-2026",
        "timing_url": "https://www.bankofengland.co.uk/monetary-policy",
    },
    "NZD_OCR_2026_10": {
        "currency": "NZD", "family": "POLICY", "metric": "POLICY_RATE_PCT",
        "observation_period": "DECISION_2026-10-28", "value_percent": "2.75",
        "release_local": "2026-10-28 14:00 Pacific/Auckland (NZDT)",
        "availability_floor_utc": "2026-10-28T01:00:00Z",
        "time_evidence": "CURRENT_RATE_PAGE_LAST_UPDATED_TIME_NOT_ORIGINAL_ARCHIVE",
        "document_url": "https://www.rbnz.govt.nz/news-and-events/news/2026/10/ocr-held-at-2-75-percent",
        "timing_url": "https://www.rbnz.govt.nz/monetary-policy/about-monetary-policy/the-official-cash-rate",
        # Independent publisher cross-reference for the DECISION and value,
        # not independent release-second proof or original issue-time bytes.
        # RBNZ warns that its historic index updates with a 24-hour lag.
        "decision_history_index_url": RBNZ_DECISION_INDEX_URL,
        "decision_history_index_delay_hours": 24,
    },
}


def _utc(raw: str) -> datetime:
    return datetime.fromisoformat(raw.replace("Z", "+00:00")).astimezone(timezone.utc)


def inspect_gbp_nzd_publisher_pilot_lab(*, decision_at_utc: datetime) -> dict[str, Any]:
    """Show only research values past conservative publisher timing boundaries.

    This does NOT give a historic as-of receipt: there is no archived original
    file, independent capture timestamp, or proof of revision-free vintage.
    """
    if (not isinstance(decision_at_utc, datetime)
            or decision_at_utc.tzinfo is None
            or decision_at_utc.utcoffset() is None
            or decision_at_utc.microsecond != 0):
        raise ValueError("A timezone-aware cutoff at whole-second precision is required")
    decision = decision_at_utc.astimezone(timezone.utc)
    records: dict[str, dict[str, Any]] = {}
    for key, source in sorted(PILOT.items()):
        available_by_official_timing = decision >= _utc(source["availability_floor_utc"])
        records[key] = {
            "currency": source["currency"], "family": source["family"],
            "metric": source["metric"], "observation_period": source["observation_period"],
            "document_url": source["document_url"], "timing_url": source["timing_url"],
            "decision_history_index_url": source.get("decision_history_index_url"),
            "decision_history_index_delay_hours": source.get("decision_history_index_delay_hours"),
            "release_local": source["release_local"],
            "availability_floor_utc": source["availability_floor_utc"],
            "time_evidence": source["time_evidence"],
            "publisher_timing_status": (
                "AFTER_CONSERVATIVE_PUBLISHER_BOUNDARY_ONLY"
                if available_by_official_timing else "NOT_YET_PUBLIC_BY_BOUNDARY"
            ),
            "research_value_percent": (
                source["value_percent"] if available_by_official_timing else None
            ),
            "original_document_bytes_archived": False,
            "independent_historical_capture_attested": False,
            "revisions_excluded": False,
            "eligible_for_exante_backtest": False,
        }
    return {
        "schema": SCHEMA, "state": "LAB_OFFICIAL_PAGES_RESEARCH_ONLY",
        "reviewed_on_utc_date": RESEARCH_REVIEW_DATE_UTC,
        "decision_at_utc": decision.isoformat(),
        "publisher_boundary_passed_count": sum(
            record["research_value_percent"] is not None for record in records.values()
        ),
        "observation_count": len(records), "observations": records,
        "original_document_bytes_archived": False,
        "historical_capture_attested": False,
        "point_in_time_backtest_approved": False,
        "forecast_probability": None, "operational_bias": "AGUARDAR",
        "trade_authorized": False, "worker_enabled": False,
        "scheduler_enabled": False, "new_cost_brl": 0,
    }


__all__ = ["SCHEMA", "RESEARCH_REVIEW_DATE_UTC", "PILOT", "inspect_gbp_nzd_publisher_pilot_lab"]
