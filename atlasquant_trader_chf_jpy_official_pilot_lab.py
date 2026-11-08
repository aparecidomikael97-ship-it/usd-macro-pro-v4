"""CHF/JPY publisher-page research only; no historical-vintage attestation.

The four official sources were researched on 2026-11-08. SNB/FSO and Japan
Statistics Bureau release *dates* are established; exact release times for
those specific publications are not. Their next-day midnight UTC floors are
conservative research cutoffs, not asserted publisher publication times.

The Bank of Japan's October 30 PDF explicitly states 12:02 Japan time.
No prices, forecasts, look-ahead backtests, network calls or trading authority.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

SCHEMA = "ATLASQUANT_TRADER_CHF_JPY_OFFICIAL_PUBLICATION_PILOT_LAB_V1"
RESEARCH_REVIEW_DATE_UTC = "2026-11-08"

OFFICIAL_OBSERVATIONS: dict[str, dict[str, Any]] = {
    "CHF_SNB_POLICY_2026_09": {
        "currency": "CHF", "family": "POLICY", "metric": "SNB_POLICY_RATE_PCT",
        "observation_period": "DECISION_2026-09-24", "stage": "POLICY_DECISION",
        "value_percent": "0.0", "value_qualifier": "POINT_RATE",
        "published_date": "2026-09-24", "release_local": None,
        "availability_floor_utc": "2026-09-25T00:00:00Z",
        "time_evidence": "DATE_ONLY_CONSERVATIVE_NEXT_UTC_DAY",
        "document_url": "https://www.snb.ch/en/publications/communication/press-releases-restricted/pre_20260924",
        "source_page_mutable": False,
    },
    "JPY_NATIONAL_CPI_2026_09": {
        "currency": "JPY", "family": "INFLATION", "metric": "JP_NATIONAL_ALL_ITEMS_CPI_YOY_PCT",
        "observation_period": "2026-09", "stage": "MONTHLY_RELEASE",
        "value_percent": "2.1", "value_qualifier": "YOY_ALL_ITEMS_NOT_CORE",
        "published_date": "2026-10-23", "release_local": None,
        "availability_floor_utc": "2026-10-24T00:00:00Z",
        "time_evidence": "DATE_ONLY_CONSERVATIVE_NEXT_UTC_DAY",
        # Statistics Bureau uses a rotating latest-release page. A later
        # revision or month may replace the text; never use this as P-I-T.
        "document_url": "https://www.stat.go.jp/data/cpi/sokuhou/tsuki/index-z.htm",
        "source_page_mutable": True,
    },
    "JPY_BOJ_OVERNIGHT_GUIDELINE_2026_10": {
        "currency": "JPY", "family": "POLICY", "metric": "BOJ_UNCOLLATERALIZED_OVERNIGHT_CALL_TARGET_PCT",
        "observation_period": "DECISION_2026-10-30", "stage": "POLICY_STATEMENT",
        "value_percent": "1.25", "value_qualifier": "AROUND_TARGET_NOT_FIXED_POINT",
        "published_date": "2026-10-30",
        "release_local": "2026-10-30 12:02 Asia/Tokyo (JST)",
        "availability_floor_utc": "2026-10-30T03:02:00Z",
        "time_evidence": "EXACT_ON_BOJ_POLICY_STATEMENT_PDF_PAGE_3",
        "document_url": "https://www.boj.or.jp/en/mopo/mpmdeci/mpr_2026/k261030a.pdf",
        "source_page_mutable": False,
    },
    "CHF_CPI_2026_10": {
        "currency": "CHF", "family": "INFLATION", "metric": "CH_NATIONAL_CPI_YOY_PCT",
        "observation_period": "2026-10", "stage": "MONTHLY_RELEASE",
        "value_percent": "1.5", "value_qualifier": "YOY_ALL_ITEMS",
        "published_date": "2026-11-03", "release_local": None,
        "availability_floor_utc": "2026-11-04T00:00:00Z",
        "time_evidence": "DATE_ONLY_CONSERVATIVE_NEXT_UTC_DAY",
        "document_url": "https://www.bfs.admin.ch/en/newnsb/UA8hylpLYO6i",
        "source_page_mutable": False,
    },
}


def _utc(raw: str) -> datetime:
    return datetime.fromisoformat(raw.replace("Z", "+00:00")).astimezone(timezone.utc)


def inspect_chf_jpy_official_pilot_lab(*, decision_at_utc: datetime) -> dict[str, Any]:
    """Show researched publisher numbers only past their declared safety floor.

    The source document bodies were NOT captured at each historic release.
    A timing-boundary pass is insufficient for a P-I-T economic vintage.
    """
    if (not isinstance(decision_at_utc, datetime)
            or decision_at_utc.tzinfo is None or decision_at_utc.utcoffset() is None
            or decision_at_utc.microsecond != 0):
        raise ValueError("Require timezone-aware whole-second decision timestamp")
    decision = decision_at_utc.astimezone(timezone.utc)
    observations: dict[str, dict[str, Any]] = {}
    for key, source in sorted(OFFICIAL_OBSERVATIONS.items()):
        after = decision >= _utc(source["availability_floor_utc"])
        observations[key] = {
            "currency": source["currency"], "family": source["family"],
            "metric": source["metric"], "observation_period": source["observation_period"],
            "stage": source["stage"], "published_date": source["published_date"],
            "release_local": source["release_local"],
            "availability_floor_utc": source["availability_floor_utc"],
            "time_evidence": source["time_evidence"],
            "value_qualifier": source["value_qualifier"],
            "document_url": source["document_url"],
            "source_page_mutable": source["source_page_mutable"],
            "publisher_timing_status": (
                "AFTER_CONSERVATIVE_PUBLISHER_BOUNDARY_ONLY" if after
                else "NOT_YET_PUBLIC_BY_BOUNDARY"
            ),
            "research_value_percent": source["value_percent"] if after else None,
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
            r["publisher_timing_status"] == "AFTER_CONSERVATIVE_PUBLISHER_BOUNDARY_ONLY"
            for r in observations.values()),
        "observation_count": len(observations), "observations": observations,
        "historical_capture_attested": False, "point_in_time_backtest_approved": False,
        "macro_cross_currency_comparison_approved": False,
        "forecast_probability": None, "operational_bias": "AGUARDAR",
        "trade_authorized": False, "worker_enabled": False,
        "scheduler_enabled": False, "new_cost_brl": 0,
    }


__all__ = ["SCHEMA", "RESEARCH_REVIEW_DATE_UTC", "OFFICIAL_OBSERVATIONS", "inspect_chf_jpy_official_pilot_lab"]
