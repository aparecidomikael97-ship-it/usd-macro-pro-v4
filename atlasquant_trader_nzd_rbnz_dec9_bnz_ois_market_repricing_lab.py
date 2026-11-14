"""NZD Dec 9 OCR market-repricing timeline — secondary BNZ reporting ONLY.

Dated BNZ original PDF reports quote approximate probability of a +25bp OCR
hike at the SAME Dec 9, 2026 meeting:
  29 Oct 2026: around 85% (post-October MPR Outlook for Borrowers, p1)
  02 Nov 2026: around 80% (Markets Outlook, p6)
  09 Nov 2026: around 65% (Markets Outlook, p4).
These values are BNZ's SECONDARY interpretations of market/OIS pricing
with cited Bloomberg data; not locally sourced OIS price/contract metadata,
not market polling, not bank research forecast probabilities, and not
the independent first-seen of the PDFs on their claimed publication days.

Contrast: ANZ/BNZ/Westpac make THEIR OWN +25bp forecasts in Dec; that
does not imply 100% probability. One event root NZD DEC 09 across 7 FX28
directly linked pairs and D1+W1, not 21 independent macro events.

RBNZ 2024 Analytical Note AN2024/08 recommends meeting-date OIS or monthly
OIS for policy surprise. 90-day bank bills have credit risk; 2y swaps
contain path/term premia and are not clean single-meeting probabilities.
A surprise is actual OCR minus *immediately pre-event market expectation*,
never the estimate published weeks earlier. The lab may present a binary
scenario calculation for teaching, NEVER a tradable signal or actual
event-day surprise.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

from atlasquant_trader_nzd_rbnz_dec9_three_bank_forecast_context_lab import (
    EVENT_UTC, RESEARCH_SAFE_VISIBLE_FROM_UTC,
)

SCHEMA = "ATLASQUANT_RBNZ_DEC9_BNZ_OIS_MARKET_REPORT_TIMELINE_LAB_V1"
SOURCE_PUBLISHER = "BNZ"
SOURCE_UNDERLYING_MARKET_DATA = "BLOOMBERG_REPORTER_SOURCE_NOT_RELICENSED"
REFERENCE_METHODOLOGY_URL = (
    "https://www.rbnz.govt.nz/-/media/project/sites/rbnz/files/"
    "publications/analytical-notes/2024/"
    "financial-market-reaction-to-ocr-surprises.pdf"
)
CURRENT_OCR_PCT_CLAIM = "2.75"
HYPOTHETICAL_HIKE_BPS = 25


@dataclass(frozen=True)
class SourceSnapshot:
    report_day: date
    pdf_url: str
    page_one_indexed: int
    hike_probability_approx_pct: int
    comment: str


SNAPSHOTS = (
    SourceSnapshot(
        date(2026, 10, 29),
        "https://www.bnz.co.nz/assets/markets/research/202610-OFB.pdf?"
        "203497951332bd49d5ed1172ff2c266ed3d4774e=",
        1, 85,
        "BNZ secondary swap-market estimate after surprise October HOLD",
    ),
    SourceSnapshot(
        date(2026, 11, 2),
        "https://www.bnz.co.nz/assets/markets/research/20261102_BNZMO.pdf?"
        "864e4d3e3c30aa3aa9b10b9bf3e38fb4eb9f887f=",
        6, 80,
        "BNZ secondary market estimate before Q3 NZ weak employment release",
    ),
    SourceSnapshot(
        date(2026, 11, 9),
        "https://www.bnz.co.nz/assets/markets/research/20261109_BNZMO-v2.pdf?"
        "461461917d84fa9f5d027387b59329e258f8c950=",
        4, 65,
        "BNZ secondary market estimate after weak Q3 NZ employment and risk repricing",
    ),
)


def _utc(value: Any) -> datetime | None:
    if (type(value) is not datetime or value.tzinfo is None
            or value.microsecond != 0):
        return None
    try:
        if value.utcoffset() is None:
            return None
        return value.astimezone(timezone.utc)
    except (ValueError, TypeError, OverflowError):
        return None


def _base(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "state": "LAB_RBNZ_MARKET_REPRICING_INPUT_BLOCKED_NO_GO",
        "reason": reason,
        "target_event_utc": EVENT_UTC.isoformat(),
        "research_visible_floor_utc": RESEARCH_SAFE_VISIBLE_FROM_UTC.isoformat(),
        "reference_issuer_methodology": REFERENCE_METHODOLOGY_URL,
        "market_secondary_report_publisher": SOURCE_PUBLISHER,
        "underlying_quote_provider_claim_not_relicensed":
            SOURCE_UNDERLYING_MARKET_DATA,
        "source_report_count": 0,
        "independent_source_publisher_count": 0,
        "unique_issuer_policy_event_roots": 1,
        "market_probability_snapshots": [],
        "net_change_percentage_points_approx": None,
        "difference_in_last_interval_pp_approx": None,
        "confidence_declined_while_bank_base_case_hike": False,
        "not_actual_ois_contract_quotes": True,
        "not_representative_economist_survey": True,
        "not_bank_forecast_hike_probability": True,
        "not_nzd_appreciation_probability": True,
        "not_exact_snapshot_market_close_times": True,
        "pdf_document_raw_bytes_archived": False,
        "underlying_ois_quote_bytes_archived": False,
        "publisher_first_seen_utc_authenticated": False,
        "point_in_time_intraday_market_snapshot_authenticated": False,
        "immediate_pre_dec9_ois_quote_verified": False,
        "meeting_date_ois_contract_identity_verified": False,
        "relevant_pre_event_broker_fx_bid_ask_verified": False,
        "actual_dec9_ocr_verified": False,
        "retrospective_october_95pct_hike_was_not_guarantee": True,
        "conditional_binary_scenarios_only": None,
        "actual_policy_surprise_basis_points": None,
        "calibrated_nzd_fx_probability": None,
        "market_direction": None,
        "backtest_accuracy": None,
        "operational_bias": "AGUARDAR",
        "trade_authorized": False,
        "live_alert_allowed": False,
        "publishable": False,
        "scheduler_enabled": False,
        "worker_enabled": False,
        "http_requests": 0,
        "file_writes": 0,
        "new_cost_brl": 0,
        "research_only": True,
    }


def inspect_bnz_reported_ocr_market_repricing_lab(
    *, as_of_utc: Any, snapshots: Any = None,
) -> dict[str, Any]:
    """Only disclosed dated BNZ reports, never live OIS or FX.
    
    Explicit snapshots argument supports synthetic test injection. Both
    publisher date and quote date are approximate, not first-seen.
    """
    out = _base("BAD_AS_OF_OR_RESEARCH_NOT_AVAILABLE_THEN")
    now = _utc(as_of_utc)
    if now is None or now < RESEARCH_SAFE_VISIBLE_FROM_UTC:
        return out
    snaps = SNAPSHOTS if snapshots is None else snapshots
    if (type(snaps) is not tuple or len(snaps) != 3
            or any(type(x) is not SourceSnapshot for x in snaps)):
        out["reason"] = "THREE_VALIDATED_REPORT_ROWS_REQUIRED"
        return out
    if (tuple(x.report_day for x in snaps) !=
            (date(2026,10,29),date(2026,11,2),date(2026,11,9))
            or len({x.pdf_url for x in snaps}) != 3
            or any(not x.pdf_url.startswith(
                    "https://www.bnz.co.nz/assets/markets/research/")
                   or type(x.page_one_indexed) is not int
                   or x.page_one_indexed not in (1,4,6)
                   or type(x.hike_probability_approx_pct) is not int
                   or not 0 <= x.hike_probability_approx_pct <= 100
                   or len(x.comment) > 160
                   for x in snaps)):
        out["reason"] = "REPORT_PUBLISHER_DATE_PROVENANCE_OR_NUMBER_INVALID"
        return out
    values = tuple(x.hike_probability_approx_pct for x in snaps)
    if values != (85,80,65):
        out["reason"] = "MARKET_PROBABILITY_SOURCE_VINTAGE_MISMATCH"
        return out

    rows = [{
        "report_calendar_date_claim": x.report_day.isoformat(),
        "original_bank_pdf_url": x.pdf_url,
        "publisher_pdf_page_one_indexed": x.page_one_indexed,
        "underlying_market_venue": SOURCE_UNDERLYING_MARKET_DATA,
        "reported_dec9_25bp_hike_probability_approx_pct":
            x.hike_probability_approx_pct,
        "meaning": "APPROX_MEETING_HIKE_ODDS_REPORTED_FROM_OIS_PRICING",
        "comment": x.comment,
        "pre_event_market_quote_bid_ask_or_settlement_verified": False,
        "quote_exact_time_in_original_market_feed": None,
        "publisher_document_sha256": None,
        "publisher_first_seen_authenticated": False,
        "not_fx_pair_probability": True,
    } for x in snaps]

    # Educational, simplistically binary world with HOLD at 0bp or HIKE at
    # 25bp. This is NOT the actual event OIS, may omit alternative outcomes,
    # settlement convention/term premia, and is 30 days before the meeting.
    # Returned for the most recent publisher number ONLY while future.
    illustration = None
    if now < EVENT_UTC:
        p = Decimal(values[-1]) / Decimal("100")
        expected_bp = p * Decimal(HYPOTHETICAL_HIKE_BPS)
        illustration = {
            "market_quote_is_not_directly_observed": True,
            "two_outcomes_only_assumed": ["HOLD_0_BPS","HIKE_25_BPS"],
            "referenced_approx_bn_z_probability_pct": values[-1],
            "hypothetical_expected_change_basis_points":
                format(expected_bp, ".2f"),
            "if_hike_25bp_surprise_basis_points_hypothetical":
                format(Decimal(25)-expected_bp, ".2f"),
            "if_hold_0bp_surprise_basis_points_hypothetical":
                format(-expected_bp, ".2f"),
            "scenario_is_not_actual_pre_meeting_ois_or_prediction": True,
            "cannot_be_used_for_fx_bias": True,
        }
    out.update({
        "state": (
            "LAB_RBNZ_SECONDARY_MARKET_REPRICING_RESEARCH_PRE_DEC9_NO_GO"
            if now < EVENT_UTC else
            "LAB_RBNZ_RESEARCH_AFTER_DEC9_CANNOT_BACKFILL_SURPRISE_NO_GO"
        ),
        "reason": "SECONDARY_BNZ_PRICING_VS_THREE_FORECASTS_NO_TRADE",
        "source_report_count": 3,
        "independent_source_publisher_count": 1,
        "market_probability_snapshots": rows,
        "net_change_percentage_points_approx": values[-1]-values[0],
        "difference_in_last_interval_pp_approx": values[-1]-values[-2],
        "confidence_declined_while_bank_base_case_hike": True,
        "conditional_binary_scenarios_only": illustration,
    })
    return out


__all__ = (
    "SCHEMA","SNAPSHOTS","SourceSnapshot","REFERENCE_METHODOLOGY_URL",
    "inspect_bnz_reported_ocr_market_repricing_lab",
)
