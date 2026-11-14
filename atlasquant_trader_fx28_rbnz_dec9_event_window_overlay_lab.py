"""Read-only calendar overlay: RBNZ OCR 09 Dec 2026 and frozen FX28 NY17 slots.

A dated PUBLIC reference on the RBNZ official current OCR page reports
"Next update: 2:00pm, 09 Dec 2026". This module interprets that *scheduled*
2pm Pacific/Auckland local time with IANA DST and locates the NY17 D1/W1
windows containing that one prospective event.

The reference is not captured original HTML with SHA, and NO independently
attested issuer first-seen/revision or forecast. Events can move. An OCR
update is not proof that the rate will change. The 14 intersecting slots
represent seven NZD pairs x two overlapping horizons, NOT fourteen
independent economic events or signals. Other pairs can be affected
indirectly; they are not declared unaffected by the event.

Never change the frozen campaign or denominator, issue direction, simulate
a rate/consensus, read network/MT5, send alerts, write files or place orders.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from atlasquant_fx_universe import CURRENCIES, OFFICIAL_PAIRS, split_pair
from atlasquant_trader_fx28_ny17_prospective_campaign_lab import (
    CAMPAIGN_ID, CALENDAR_ISSUE, FROZEN_START_UTC, FROZEN_END_UTC,
    EXPECTED_PAIR_HORIZON_SLOTS, _nominal_windows,
)

SCHEMA = "ATLASQUANT_FX28_RBNZ_DEC9_SCHEDULE_NY17_OVERLAY_LAB_V1"
SOURCE_URL = ("https://www.rbnz.govt.nz/monetary-policy/"
              "about-monetary-policy/the-official-cash-rate")
EVENT_ROOT_ID = "RBNZ_OCR_NEXT_UPDATE_20261209_NZ1400_PUBLIC_REFERENCE_ONLY"
SOURCE_SCHEDULE_TEXT = "Next update: 2:00pm, 09 Dec 2026"
D1 = "D1"
W1 = "W1"


def _utc(value: Any) -> datetime | None:
    if not isinstance(value, datetime) or value.tzinfo is None:
        return None
    try:
        if value.utcoffset() is None or value.microsecond:
            return None
        return value.astimezone(timezone.utc)
    except (ValueError, TypeError, OverflowError):
        return None


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "state": "LAB_RBNZ_EVENT_WINDOW_OVERLAY_BLOCKED_NO_GO",
        "reason": reason,
        "campaign_id": CAMPAIGN_ID,
        "campaign_issue_url": CALENDAR_ISSUE,
        "expected_pair_horizon_slots": EXPECTED_PAIR_HORIZON_SLOTS,
        "frozen_campaign_start_utc": FROZEN_START_UTC.isoformat(),
        "frozen_campaign_end_utc": FROZEN_END_UTC.isoformat(),
        "source_reference_url": SOURCE_URL,
        "scheduled_ocr_update_source_text": SOURCE_SCHEDULE_TEXT,
        "source_url_is_not_captured_original_html": True,
        "source_schedule_first_seen_or_revision_independently_verified": False,
        "official_page_snapshot_locally_sha_verified": False,
        "scheduled_event_is_not_realized_ocr_change": True,
        "official_ocr_actual_at_event": None,
        "pre_event_consensus_verified": False,
        "scheduled_event_utc_interpreted_from_nz_local": None,
        "scheduled_event_at_cuiaba_interpreted": None,
        "scheduled_event_status_at_inspection": None,
        "event_count": 0,
        "event_root_counted_as_one_shared_catalyst": True,
        "direct_nzd_pair_count": 0,
        "overlapping_nominal_window_count": 0,
        "direct_pair_horizon_slots_intersecting_event": 0,
        "all_672_slots_preserved": False,
        "overlapping_window_details": [],
        "direct_pair_horizon_slot_ids": [],
        "other_currency_pairs_proved_unaffected": False,
        "probability_estimated": None,
        "accuracy_measured": None,
        "operational_bias": "AGUARDAR",
        "publishable": False,
        "live_alert_allowed": False,
        "trade_authorized": False,
        "worker_enabled": False,
        "scheduler_enabled": False,
        "http_requests": 0,
        "file_writes": 0,
        "new_cost_brl": 0,
        "research_only": True,
    }


def inspect_rbnz_dec9_event_ny17_relevance_lab(
    *, inspected_at_utc: Any,
) -> dict[str, Any]:
    """Intersect one OFFICIAL PAGE REFERENCE with frozen D1/W1 NY17.

    This is a calendar-warning RESEARCH overlay, not evidence of pre-event
    consensus, published actual, authenticated forecast, or external alerts.
    """
    out = _blocked("INVALID_CLOCK_OR_FROZEN_FX28_CAMPAIGN")
    now = _utc(inspected_at_utc)
    if (now is None
            or len(CURRENCIES) != 8
            or len(set(OFFICIAL_PAIRS)) != 28
            or len(OFFICIAL_PAIRS) != 28
            or EXPECTED_PAIR_HORIZON_SLOTS != 672):
        return out
    windows = {
        horizon: _nominal_windows(horizon)
        for horizon in (D1, W1)
    }
    if (len(windows[D1]) != 20 or len(windows[W1]) != 4
            or windows[D1][0][0] != FROZEN_START_UTC
            or windows[W1][0][0] != FROZEN_START_UTC
            or windows[D1][-1][1] != FROZEN_END_UTC
            or windows[W1][-1][1] != FROZEN_END_UTC):
        out["reason"] = "CAMPAIGN_DATES_OR_HORIZON_INVENTORY_CHANGED"
        return out

    try:
        nz = ZoneInfo("Pacific/Auckland")
        cuiaba = ZoneInfo("America/Cuiaba")
        scheduled_local = datetime(2026, 12, 9, 14, 0, tzinfo=nz)
        scheduled = scheduled_local.astimezone(timezone.utc)
        cuiaba_dt = scheduled.astimezone(cuiaba)
    except (ZoneInfoNotFoundError, OSError, ValueError, OverflowError):
        out["reason"] = "IANA_TIMEZONE_RULES_UNAVAILABLE_NO_FIXED_OFFSET_FALLBACK"
        return out
    if (scheduled.isoformat() != "2026-12-09T01:00:00+00:00"
            or cuiaba_dt.isoformat() != "2026-12-08T21:00:00-04:00"
            or not FROZEN_START_UTC < scheduled < FROZEN_END_UTC):
        out["reason"] = "FROZEN_RBNZ_SCHEDULED_UTC_INSTANT_MISMATCH"
        return out

    nzd_pairs = tuple(
        pair for pair in OFFICIAL_PAIRS if "NZD" in split_pair(pair)
    )
    if len(nzd_pairs) != 7:
        out["reason"] = "NZD_DIRECT_PAIR_UNIVERSE_NOT_SEVEN"
        return out

    details = []
    slot_ids = []
    for horizon in (D1, W1):
        matched = [(start, end) for start, end in windows[horizon]
                   if start <= scheduled < end]
        if len(matched) != 1:
            out["reason"] = "EVENT_NOT_IN_EXACTLY_ONE_WINDOW_PER_HORIZON"
            return out
        start, end = matched[0]
        details.append({
            "horizon": horizon,
            "window_start_utc": start.isoformat(),
            "window_end_utc": end.isoformat(),
            "event_inside_window_not_evidence_of_prediction": True,
            "direct_nzd_pair_slots": 7,
            "overlapping_horizons_are_not_independent_trials": True,
        })
        for pair in nzd_pairs:
            slot_ids.append({
                "slot_id": (
                    f"FX28_NY17_{start.strftime('%Y%m%dT%H%MZ')}_{horizon}_{pair}"
                ),
                "pair": pair,
                "horizon": horizon,
                "risk_event_root_id": EVENT_ROOT_ID,
                "event_is_confirmed_actual_release": False,
                "event_impact_direction": None,
                "event_first_seen_authenticated": False,
                "signal_or_trade_authorized": False,
            })
    if len(details) != 2 or len(slot_ids) != 14 or len({
            s["slot_id"] for s in slot_ids}) != 14:
        out["reason"] = "RBNZ_DIRECT_PAIR_HORIZON_INTERSECTION_MISMATCH"
        return out

    out.update({
        "state": "LAB_RBNZ_EVENT_WINDOW_RELEVANCE_DOCUMENTARY_NO_GO",
        "reason": "ONE_SCHEDULED_EVENT_AFFECTS_SEVEN_NZD_PAIRS_TWO_OVERLAPPING_HORIZONS",
        "scheduled_event_utc_interpreted_from_nz_local": scheduled.isoformat(),
        "scheduled_event_at_cuiaba_interpreted": cuiaba_dt.isoformat(),
        "scheduled_event_status_at_inspection": (
            "FUTURE_PUBLIC_SCHEDULE_CLAIM_UNATTESTED" if now < scheduled
            else "ELAPSED_PUBLIC_SCHEDULE_NOT_HISTORICAL_FORECAST"
        ),
        "event_count": 1,
        "direct_nzd_pair_count": 7,
        "overlapping_nominal_window_count": 2,
        "direct_pair_horizon_slots_intersecting_event": 14,
        "all_672_slots_preserved": True,
        "overlapping_window_details": details,
        "direct_pair_horizon_slot_ids": slot_ids,
    })
    return out


__all__ = (
    "SCHEMA", "SOURCE_URL", "EVENT_ROOT_ID",
    "inspect_rbnz_dec9_event_ny17_relevance_lab",
)
