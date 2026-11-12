"""AUD/CAD official research pilot; release boundaries, not trading evidence.

Publisher values were checked on public primary-source pages on 2026-11-08,
not independently archived at their historical release times. Except the
specific ABS CPI release, a publisher date-only next-UTC-day floor is used.
Policy announcement and effective dates must never be conflated.

No networking, MetaTrader access, account operations, forecasts or trades.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

SCHEMA = "ATLASQUANT_TRADER_AUD_CAD_OFFICIAL_PUBLICATION_PILOT_LAB_V1"
RESEARCH_REVIEW_DATE_UTC = "2026-11-08"

OFFICIAL_OBSERVATIONS: dict[str, dict[str, Any]] = {
    "AUD_CPI_2026_09": {
        "currency": "AUD", "family": "INFLATION", "metric": "AU_CPI_ALL_GROUPS_12M_PCT",
        "observation_period": "2026-09", "stage": "MONTHLY_RELEASE",
        "value_percent": "4.3", "published_date": "2026-10-28",
        "release_local": "2026-10-28 11:30 Australia/Sydney (AEDT)",
        "availability_floor_utc": "2026-10-28T00:30:00Z",
        "time_evidence": "EXACT_ON_ABS_RELEASE_PAGE",
        "effective_date": None,
        "document_url": "https://www.abs.gov.au/media-centre/media-releases/cpi-rose-43-year-september-2026",
    },
    "CAD_CPI_2026_09": {
        "currency": "CAD", "family": "INFLATION", "metric": "CA_CPI_ALL_ITEMS_12M_PCT",
        "observation_period": "2026-09", "stage": "MONTHLY_RELEASE",
        "value_percent": "3.1", "published_date": "2026-10-19",
        "release_local": None, "availability_floor_utc": "2026-10-20T00:00:00Z",
        "time_evidence": "DATE_ONLY_CONSERVATIVE_NEXT_UTC_DAY",
        "effective_date": None,
        "document_url": "https://www150.statcan.gc.ca/n1/daily-quotidien/261019/dq261019a-eng.htm",
    },
    "CAD_BOC_OVERNIGHT_TARGET_2026_10": {
        "currency": "CAD", "family": "POLICY", "metric": "BOC_OVERNIGHT_RATE_TARGET_PCT",
        "observation_period": "DECISION_2026-10-28", "stage": "POLICY_DECISION",
        "value_percent": "2.50", "published_date": "2026-10-28",
        "release_local": None, "availability_floor_utc": "2026-10-29T00:00:00Z",
        "time_evidence": "DATE_ONLY_NEXT_UTC_DAY; ANNOUNCEMENT_SCHEDULE_09_45_ET_NOT_CAPTURE_PROOF",
        "effective_date": None,
        "document_url": "https://www.bankofcanada.ca/2026/10/fad-press-release-2026-10-28/",
        "timing_url": "https://www.bankofcanada.ca/2026/10/fad-announcement-release-mpr-2026-10-28/",
    },
    "AUD_RBA_CASH_TARGET_2026_11": {
        "currency": "AUD", "family": "POLICY", "metric": "RBA_CASH_RATE_TARGET_PCT",
        "observation_period": "DECISION_2026-11-03", "stage": "POLICY_DECISION",
        "value_percent": "4.85", "published_date": "2026-11-03",
        "release_local": None, "availability_floor_utc": "2026-11-04T00:00:00Z",
        "time_evidence": "DATE_ONLY_NEXT_UTC_DAY; GENERAL_14_30_AEDT_POLICY_NOT_RELEASE_PROOF",
        # Effective date is not the release date or the conservative research floor.
        "effective_date": "2026-11-04",
        "document_url": "https://www.rba.gov.au/media-releases/2026/mr-26-30.html",
        "timing_url": "https://www.rba.gov.au/cash-rate-target-overview.html",
    },
}


def _utc(raw: str) -> datetime:
    return datetime.fromisoformat(raw.replace("Z", "+00:00")).astimezone(timezone.utc)


def inspect_aud_cad_official_pilot_lab(*, decision_at_utc: datetime) -> dict[str, Any]:
    """Show research values only after the issuer's conservative timing floor.

    This retrospective catalog is NOT a contemporary historical data vintage.
    Its values must not be adapted into the G8 P-I-T receipt input or scored.
    """
    if (not isinstance(decision_at_utc, datetime)
            or decision_at_utc.tzinfo is None
            or decision_at_utc.utcoffset() is None
            or decision_at_utc.microsecond != 0):
        raise ValueError("An aware whole-second UTC-convertible datetime is required")
    decision = decision_at_utc.astimezone(timezone.utc)
    records: dict[str, dict[str, Any]] = {}
    for key, source in sorted(OFFICIAL_OBSERVATIONS.items()):
        passed = decision >= _utc(source["availability_floor_utc"])
        records[key] = {
            "currency": source["currency"], "family": source["family"],
            "metric": source["metric"], "observation_period": source["observation_period"],
            "stage": source["stage"], "published_date": source["published_date"],
            "effective_date": source["effective_date"],
            "release_local": source["release_local"],
            "availability_floor_utc": source["availability_floor_utc"],
            "time_evidence": source["time_evidence"],
            "document_url": source["document_url"],
            "publisher_timing_status": (
                "AFTER_CONSERVATIVE_PUBLISHER_BOUNDARY_ONLY" if passed
                else "NOT_YET_PUBLIC_BY_BOUNDARY"
            ),
            "research_value_percent": source["value_percent"] if passed else None,
            "original_historical_bytes_archived": False,
            "independent_historical_capture_attested": False,
            "revisions_excluded": False, "eligible_for_exante_backtest": False,
        }
    return {
        "schema": SCHEMA, "state": "LAB_OFFICIAL_PAGES_RESEARCH_ONLY",
        "reviewed_on_utc_date": RESEARCH_REVIEW_DATE_UTC,
        "decision_at_utc": decision.isoformat(),
        "publisher_boundary_passed_count": sum(
            row["publisher_timing_status"] == "AFTER_CONSERVATIVE_PUBLISHER_BOUNDARY_ONLY"
            for row in records.values()),
        "observation_count": len(records), "observations": records,
        "historical_capture_attested": False, "point_in_time_backtest_approved": False,
        "macro_cross_currency_comparison_approved": False,
        "forecast_probability": None, "operational_bias": "AGUARDAR",
        "trade_authorized": False, "worker_enabled": False,
        "scheduler_enabled": False, "new_cost_brl": 0,
    }


__all__ = ["SCHEMA", "RESEARCH_REVIEW_DATE_UTC", "OFFICIAL_OBSERVATIONS", "inspect_aud_cad_official_pilot_lab"]
