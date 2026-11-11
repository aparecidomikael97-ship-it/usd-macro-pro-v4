"""Retrospective US October 2026 CPI vs pre-event *reported* preview, LAB ONLY.

This reader checks raw BLS HTML with the previously audited local parser.
The older preview is only a post-event discovered, reported consensus claim,
not independently witnessed pre-event poll bytes. A signed/accurate original
first-release timeline and a point-in-time replay are NOT proven here.
No score, FX prediction, trade, or deployment comes from this module.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import re
from typing import Any

from atlasquant_trader_us_oct2026_cpi_release_text_guard_lab import (
    ClaimedBLSHtmlReceipt, RELEASE_FLOOR_UTC,
    inspect_bls_oct2026_release_text_lab,
)

SCHEMA = "ATLASQUANT_TRADER_US_OCT2026_CPI_DOCUMENTARY_PREVIEW_COMPARE_LAB_V1"
PREVIEW_URL = (
    "https://www.fxstreet.com/analysis/us-cpi-preview-moderation-on-the-horizon-"
    "but-underlying-pressures-linger-202611092231"
)
# Source *says* its posting clock is 2026-11-09 22:31:21 UTC.
# We retrieved this content after the BLS event; it is not a pre-event capture.
PREVIEW_PUBLISHED_CLOCK_CLAIM = datetime(2026, 11, 9, 22, 31, 21, tzinfo=timezone.utc)
# We never backdate the research to Nov 9/10.
DOCUMENTARY_RESEARCH_VISIBLE_FROM_UTC = datetime(2026, 11, 11, tzinfo=timezone.utc)
_PCT = re.compile(r"(?:0|[1-9][0-9]?)\.(?:[0-9]{1,3})\Z")


@dataclass(frozen=True)
class ReportedPreviewClaim:
    source_url: str
    published_at_utc_claim: datetime
    metric: str
    headline_consensus_pct_claim: str
    core_consensus_pct_claim: str
    source_bytes_archived_before_event: bool = False
    first_publication_attested: bool = False
    Reuters_poll_witnessed_before_event: bool = False


def _pct(value: Any) -> Decimal | None:
    if not isinstance(value, str) or _PCT.fullmatch(value) is None:
        return None
    try:
        v = Decimal(value)
    except InvalidOperation:
        return None
    return v if v.is_finite() and Decimal("0") <= v < Decimal("10") else None


def _utc(value: Any) -> datetime | None:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        return None
    return value.astimezone(timezone.utc)


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "state": "LAB_DOCUMENTARY_COMPARISON_BLOCKED",
        "reason": reason,
        "underlying_BLS_body_local_parsed": False,
        "source_preview_reported_before_event_calendar": False,
        "preview_first_publication_independently_attested": False,
        "preview_bytes_preserved_pre_event": False,
        "pre_event_poll_methodology_witnessed": False,
        "actual_BLS_first_release_attested": False,
        "headline_actual_monthly_sa_pct_document_claim": None,
        "core_actual_monthly_sa_pct_document_claim": None,
        "headline_pre_event_reported_consensus_pct_claim": None,
        "core_pre_event_reported_consensus_pct_claim": None,
        "headline_retrospective_difference_pp_claim": None,
        "core_retrospective_difference_pp_claim": None,
        "official_yoy_headline_2026_10": None,
        "official_yoy_core_2026_10": None,
        "statistically_verified_surprise": None,
        "directional_usd_signal": None,
        "eurusd_directional_bias": None,
        "direction_probability": None,
        "validated_accuracy": None,
        "operational_bias": "AGUARDAR",
        "can_feed_live_radar": False,
        "historical_point_in_time_verified": False,
        "backtest_eligible": False,
        "trade_authorized": False,
        "publishable": False,
        "worker_enabled": False,
        "scheduler_enabled": False,
        "new_cost_brl": 0,
        "http_requests": 0,
    }


def inspect_oct2026_cpi_documentary_comparison_lab(
    *, raw_bls_html: Any, bls_receipt: Any,
    preview: Any, as_of_utc: Any,
) -> dict[str, Any]:
    """Only calculate a retrospective arithmetic difference in percentage points.

    Even a self-consistent BLS file and a dated preview cannot independently
    establish a witnessed pre-release polling window, initial source bytes,
    or the information set the trader had at the exact 08:30 ET event.
    """
    out = _blocked("INVALID_CLOCK_OR_PREVIEW_OR_BLS_BODY")
    now = _utc(as_of_utc)
    if now is None or now < DOCUMENTARY_RESEARCH_VISIBLE_FROM_UTC:
        out["reason"] = "RESEARCH_NOT_AVAILABLE_AT_HISTORICAL_DECISION"
        return out
    if not isinstance(preview, ReportedPreviewClaim):
        return out
    publication = _utc(preview.published_at_utc_claim)
    if (preview.source_url != PREVIEW_URL
            or publication != PREVIEW_PUBLISHED_CLOCK_CLAIM
            or publication >= RELEASE_FLOOR_UTC
            or preview.metric != "CPI_U_SA_MONTH_OVER_MONTH_PERCENT_CHANGE"
            or preview.source_bytes_archived_before_event is not False
            or preview.first_publication_attested is not False
            or preview.Reuters_poll_witnessed_before_event is not False):
        out["reason"] = "PREVIEW_SOURCE_CLOCK_METRIC_OR_PROVENANCE_UNSUPPORTED"
        return out
    h, c = _pct(preview.headline_consensus_pct_claim), _pct(preview.core_consensus_pct_claim)
    if h != Decimal("0.3") or c != Decimal("0.2"):
        out["reason"] = "REPORTED_PRE_EVENT_CONSENSUS_VALUES_NOT_MATCHING_DOCUMENTED_PREVIEW"
        return out
    if not isinstance(bls_receipt, ClaimedBLSHtmlReceipt):
        return out
    parsed = inspect_bls_oct2026_release_text_lab(
        raw_html=raw_bls_html, receipt=bls_receipt, as_of_utc=now)
    if (parsed.get("state") != "LAB_BLS_HTML_MONTHLY_CONTEXT_UNATTESTED"
            or parsed.get("data_extracted_from_supplied_html_body") is not True
            or parsed.get("headline_yoy_reported_missing_oct2025_baseline") is not True
            or parsed.get("usd_pair_count") != 7):
        out["reason"] = "BLS_RAW_HTML_OR_MONTHLY_METRICS_NOT_ADMISSIBLE"
        return out
    actual_h = _pct(parsed.get("headline_oct2026_sa_mom_pct_body_claim"))
    actual_c = _pct(parsed.get("core_oct2026_sa_mom_pct_body_claim"))
    if actual_h is None or actual_c is None:
        return out
    out.update({
        "state": "LAB_RETROSPECTIVE_DOCUMENTARY_DIFFERENCE_NO_PIT_SIGNAL",
        "reason": "BLS_SAVED_HTML_AND_PRE_EVENT_PREVIEW_AS_RESEARCH_ONLY_NOT_WITNESSED_FEEDS",
        "underlying_BLS_body_local_parsed": True,
        "source_preview_reported_before_event_calendar": True,
        "headline_actual_monthly_sa_pct_document_claim": str(actual_h),
        "core_actual_monthly_sa_pct_document_claim": str(actual_c),
        "headline_pre_event_reported_consensus_pct_claim": str(h),
        "core_pre_event_reported_consensus_pct_claim": str(c),
        "headline_retrospective_difference_pp_claim": str(actual_h - h),
        "core_retrospective_difference_pp_claim": str(actual_c - c),
    })
    return out


__all__ = [
    "SCHEMA", "PREVIEW_URL", "PREVIEW_PUBLISHED_CLOCK_CLAIM",
    "DOCUMENTARY_RESEARCH_VISIBLE_FROM_UTC", "ReportedPreviewClaim",
    "inspect_oct2026_cpi_documentary_comparison_lab",
]