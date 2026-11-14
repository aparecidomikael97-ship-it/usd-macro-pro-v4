"""NZOR true-close clock versus Dec 9 OCR event — pure temporal gate LAB.

Official NZFBF NZOR methodology *January 2026*:
- Final pricing snap at approximately 16:32 New Zealand local time,
  with preclose snapshots from 16:15, and vendor distribution targeted
  no later than 16:55 on a NZ business day.
- This is an end-of-day BENCHMARK, NOT a real-time tick immediately
  before a policy meeting.
RBNZ scheduled OCR meeting release Wed 09 Dec 2026 14:00 Pacific/Auckland
(2026-12-09T01:00:00Z). Therefore:
- Tue Dec 8 16:32 NZDT close = 2026-12-08T03:32Z, BEFORE announcement;
- Wed Dec 9 16:32 NZDT close = 2026-12-09T03:32Z, AFTER announcement.
Never mistake the later same-calendar-date closing benchmark for a
pre-event forecast or use it to infer actual market surprise.

An observation can pass this TIME-ORDER SCREEN only with claimed
publication/capture before both event and as-of; it is NOT source
authenticated, licensed, bid/ask verified, benchmark-convention verified
or predictive. Synthetic hashes/clocks NEVER become real snapshots.
This does not query NZFMA, subscribe, write, trade, issue alerts or
retroactively backfill a prospective commitment.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
import re
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from atlasquant_trader_nzd_rbnz_dec9_meeting_ois_source_gate_lab import (
    NZFBF_NZOR_DEFINITION_URL, NZOR_BENCHMARK_CODE,
)
from atlasquant_trader_nzd_rbnz_dec9_three_bank_forecast_context_lab import (
    EVENT_UTC, RESEARCH_SAFE_VISIBLE_FROM_UTC,
)

SCHEMA = "ATLASQUANT_NZOR_DEC9_CLOSING_BENCHMARK_PREEVENT_CLOCK_LAB_V1"
JAN2026_METHODOLOGY = (
    "https://www.nzfbf.co.nz/files/benchmark-documents/"
    "NZOR-Closing-Rates---Methodology-January-2026.pdf"
)
NZ_ZONE = "Pacific/Auckland"
EVENT_NZ_LOCAL = datetime(2026, 12, 9, 14, 0, 0)
CLOSING_SNAP_NZ = time(16, 32, 0)
TARGET_VENDOR_DISTRIBUTION_NZ = time(16, 55, 0)
ISO_NZ_DATE = re.compile(r"20\d\d-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12]\d|3[01])\Z")
_SHA = re.compile(r"[0-9a-f]{64}\Z")


@dataclass(frozen=True)
class NZORCloseTimingClaim:
    """User-provided evidence claims are NOT independently authenticated."""
    benchmark_code: str
    nz_trade_date: str
    nz_meeting_date: str
    rate_type: str
    issuer_published_at_utc_claim: datetime
    locally_captured_at_utc_claim: datetime
    source_sha256_claim: str


def _clock(value: Any) -> datetime | None:
    if type(value) is not datetime or value.tzinfo is None or value.microsecond:
        return None
    try:
        if value.utcoffset() is None:
            return None
        return value.astimezone(timezone.utc)
    except (ValueError, OverflowError, TypeError):
        return None


def _date(value: Any) -> date | None:
    if type(value) is not str or ISO_NZ_DATE.fullmatch(value) is None:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _base(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "state": "LAB_NZOR_PREEVENT_CLOCK_BLOCKED_NO_GO",
        "reason": reason,
        "nz_timezone": NZ_ZONE,
        "event_utc": EVENT_UTC.isoformat(),
        "event_nz_local_calendar_time": "2026-12-09T14:00:00",
        "source_january_2026_methodology_url": JAN2026_METHODOLOGY,
        "official_benchmark_code": NZOR_BENCHMARK_CODE,
        "official_benchmark_definition_url": NZFBF_NZOR_DEFINITION_URL,
        "nz_closing_snap_nominal_local": "16:32",
        "nz_distributed_by_nominal_local": "16:55",
        "nominal_issuer_closing_is_not_realtime_tick": True,
        "nominal_vendor_distribution_is_not_authenticated_delivery_time": True,
        "nz_business_day_or_public_holiday_independently_validated": False,
        "last_prior_calendar_day_candidate_nz": "2026-12-08",
        "last_prior_day_closing_utc": None,
        "last_prior_day_nominal_distribution_utc": None,
        "dec09_same_day_closing_utc": None,
        "last_prior_day_distribution_to_event_minutes": None,
        "source_trade_date_nz": None,
        "source_closing_utc_calculated": None,
        "claim_issuer_publication_utc": None,
        "claim_local_capture_utc": None,
        "temporal_pre_event_eligibility_only": False,
        "original_quote_bytes_independently_verified": False,
        "original_source_issuer_first_seen_authenticated": False,
        "correct_nzor_maturity_and_ocr_meeting_pair_verified": False,
        "quote_rates_or_bid_ask_authenticated": False,
        "nzfma_data_license_verified": False,
        "vendor_redistribution_rights_verified": False,
        "current_OCR_and_next_OCR_expectation_solved": False,
        "pre_event_OIS_quote_sufficient_to_price_binary_25bp_probability": False,
        "policy_actual_at_dec9_authenticated": False,
        "actual_policy_surprise_basis_points": None,
        "calibrated_directional_fx_probability": None,
        "operational_bias": "AGUARDAR",
        "trade_authorized": False,
        "live_alert_allowed": False,
        "publishable": False,
        "worker_enabled": False,
        "scheduler_enabled": False,
        "http_requests": 0,
        "file_writes": 0,
        "new_cost_brl": 0,
        "research_only": True,
    }


def inspect_nzor_dec9_preevent_clock_lab(
    *, inspected_at_utc: Any, claim: Any = None,
) -> dict[str, Any]:
    out = _base("INVALID_CLOCK_OR_BEFORE_RESEARCH_VISIBILITY")
    checked = _clock(inspected_at_utc)
    if checked is None or checked < RESEARCH_SAFE_VISIBLE_FROM_UTC:
        return out
    try:
        zone = ZoneInfo(NZ_ZONE)
        event_utc_by_iana = EVENT_NZ_LOCAL.replace(
            tzinfo=zone).astimezone(timezone.utc)
        before_close = datetime.combine(
            date(2026, 12, 8), CLOSING_SNAP_NZ,
            tzinfo=zone).astimezone(timezone.utc)
        before_distributed = datetime.combine(
            date(2026, 12, 8), TARGET_VENDOR_DISTRIBUTION_NZ,
            tzinfo=zone).astimezone(timezone.utc)
        after_close = datetime.combine(
            date(2026, 12, 9), CLOSING_SNAP_NZ,
            tzinfo=zone).astimezone(timezone.utc)
    except (ZoneInfoNotFoundError, ValueError, OverflowError, TypeError):
        out["reason"] = "NZ_TIMEZONE_REFERENCE_UNAVAILABLE"
        return out
    if not (event_utc_by_iana == EVENT_UTC
            and before_close < before_distributed < EVENT_UTC < after_close
            and date(2026,12,8).weekday()==1 and date(2026,12,9).weekday()==2
            and NZOR_BENCHMARK_CODE == "NZOR"):
        out["reason"] = "RBNZ_DEC9_NZOR_CLOCK_OR_BENCHMARK_INCONSISTENT"
        return out

    out.update({
        "state": "LAB_NZOR_PREEVENT_SCHEDULE_CLOCK_ONLY_NO_GO",
        "reason": "DETERMINISTIC_NZ_TIME_ORDER_NOT_AUTHENTICATED_MARKET_DATA",
        "last_prior_day_closing_utc": before_close.isoformat(),
        "last_prior_day_nominal_distribution_utc":
            before_distributed.isoformat(),
        "dec09_same_day_closing_utc": after_close.isoformat(),
        "last_prior_day_distribution_to_event_minutes":
            int((EVENT_UTC-before_distributed).total_seconds()/60),
    })
    if claim is None:
        return out
    out["state"] = "LAB_NZOR_CLOSE_CLAIM_TIME_ORDER_REJECTED_NO_GO"
    out["reason"] = "CLAIM_MISSING_OR_INVALID"
    if type(claim) is not NZORCloseTimingClaim:
        return out
    trade = _date(claim.nz_trade_date)
    meeting = _date(claim.nz_meeting_date)
    published = _clock(claim.issuer_published_at_utc_claim)
    captured = _clock(claim.locally_captured_at_utc_claim)
    if (trade is None or meeting != date(2026,12,9)
            or claim.benchmark_code != "NZOR"
            or claim.rate_type != "NZOR_CLOSING_MID"
            or type(claim.source_sha256_claim) is not str
            or _SHA.fullmatch(claim.source_sha256_claim) is None
            or published is None or captured is None):
        return out
    # A holiday cannot be authenticated by a weekday check; this is
    # purely a negative gate, never positive business-day proof.
    if trade.weekday() >= 5:
        out["reason"] = "WEEKEND_NOT_TRADING_DAY"
        return out
    snap = datetime.combine(trade, CLOSING_SNAP_NZ,
                            tzinfo=zone).astimezone(timezone.utc)
    out.update({
        "source_trade_date_nz": trade.isoformat(),
        "source_closing_utc_calculated": snap.isoformat(),
        "claim_issuer_publication_utc": published.isoformat(),
        "claim_local_capture_utc": captured.isoformat(),
    })
    # Published source claim and captured evidence must both predate
    # announcement, and logically occur only after the closing snap.
    # Future data relative to the as-of cut, or after announcement, is
    # rejected. A SHA *claim* is never proof of original source.
    if snap >= EVENT_UTC:
        out["reason"] = "SAME_DAY_CLOSING_POST_RBNZ_DECISION_LOOKAHEAD"
        return out
    if not snap <= published <= captured <= checked:
        out["reason"] = "PUBLICATION_CAPTURE_OR_ASOF_TIME_ORDER_INVALID"
        return out
    if published >= EVENT_UTC or captured >= EVENT_UTC:
        out["reason"] = "QUOTE_OBSERVED_AFTER_EVENT_NOT_PREEVENT"
        return out
    out.update({
        "state": "LAB_NZOR_CLOSE_CLOCK_CLAIMS_CHRONOLOGICALLY_PREEVENT_NO_GO",
        "reason": "TIME_CLAIMS_ONLY_NO_LICENSE_OR_FIRST_SEEN_OR_PRICE",
        "temporal_pre_event_eligibility_only": True,
    })
    return out


__all__ = (
    "SCHEMA", "JAN2026_METHODOLOGY", "NZORCloseTimingClaim",
    "inspect_nzor_dec9_preevent_clock_lab",
)
