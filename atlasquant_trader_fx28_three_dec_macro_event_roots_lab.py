"""Three scheduled NZD/CHF/JPY macro roots in frozen FX28 NY17 D1/W1.

Source: PUBLIC REFERENCE pages only, not captured original documents or
independently witnessed publication/first-seen. Policy DECISIONS (RBNZ/SNB)
are not the same metric as a Japan corporate goods price index release
(BoJ). Scheduled time is NOT evidence that an announcement happened, what
value it contained, its pre-event consensus, or any signed FX impact.

The Dec 2026 campaign is already frozen at 20 D1 + 4 W1 x 28 = 672 slots.
This overlay never shifts its boundaries. A single event touches 7 pairs
in each horizon; there are 42 root-to-slot associations but only 38 UNIQUE
pair-horizon slots due to overlap. Count 3 release roots, NOT 42 events.
No live market connectivity, no trade, network, IO or backfill.
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
from atlasquant_trader_fx28_rbnz_dec9_event_window_overlay_lab import (
    EVENT_ROOT_ID as RBNZ_ROOT,
    SOURCE_URL as RBNZ_SOURCE,
)

SCHEMA = "ATLASQUANT_FX28_THREE_DEC2026_MACRO_EVENT_ROOT_OVERLAY_LAB_V1"
SNB_ROOT = "SNB_POLICY_DECISION_20261210_0930_ZURICH_SCHEDULE_CLAIM"
BOJ_ROOT = "BOJ_CGPI_NOV2026_20261210_0850_TOKYO_SCHEDULE_CLAIM"
SNB_SOURCE = "https://www.snb.ch/en/services-events/digital-services/event-schedule"
BOJ_SOURCE = "https://www.boj.or.jp/en/about/calendar/index.htm"
SCHEDULE_REFERENCE_ONLY = (
    (RBNZ_ROOT, "NZD", "RBNZ_OCR_POLICY_ANNOUNCEMENT",
     RBNZ_SOURCE, "Pacific/Auckland", (2026, 12, 9, 14, 0),
     "2026-12-09T01:00:00+00:00", "2026-12-08T21:00:00-04:00"),
    (BOJ_ROOT, "JPY", "BOJ_NOV2026_CORPORATE_GOODS_PRICE_INDEX",
     BOJ_SOURCE, "Asia/Tokyo", (2026, 12, 10, 8, 50),
     "2026-12-09T23:50:00+00:00", "2026-12-09T19:50:00-04:00"),
    (SNB_ROOT, "CHF", "SNB_MONETARY_POLICY_ASSESSMENT_PRESS_RELEASE",
     SNB_SOURCE, "Europe/Zurich", (2026, 12, 10, 9, 30),
     "2026-12-10T08:30:00+00:00", "2026-12-10T04:30:00-04:00"),
)


def _utc(value: Any) -> datetime | None:
    if not isinstance(value, datetime) or value.tzinfo is None:
        return None
    try:
        if value.utcoffset() is None or value.microsecond:
            return None
        return value.astimezone(timezone.utc)
    except (TypeError, ValueError, OverflowError):
        return None


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "state": "LAB_FX28_THREE_DEC_EVENT_OVERLAY_BLOCKED_NO_GO",
        "reason": reason,
        "campaign_id": CAMPAIGN_ID,
        "campaign_issue_url": CALENDAR_ISSUE,
        "campaign_start_utc": FROZEN_START_UTC.isoformat(),
        "campaign_end_utc": FROZEN_END_UTC.isoformat(),
        "expected_pair_horizon_slots": EXPECTED_PAIR_HORIZON_SLOTS,
        "source_schedules_are_public_page_references_not_original_bytes": True,
        "source_schedules_independently_first_seen_witnessed": False,
        "calendar_last_revision_independently_authenticated": False,
        "event_results_independently_authenticated": False,
        "pre_event_consensus_available_and_authenticated": False,
        "scheduled_not_same_as_announcement_released": True,
        "boj_cgpi_not_boj_policy_rate_decision": True,
        "rbnz_snb_policy_decisions_do_not_imply_rate_change": True,
        "no_outside_pairs_proved_immune_to_spillover": True,
        "event_root_count": 0,
        "root_to_pair_horizon_associations": 0,
        "unique_pair_horizon_slots_exposed": 0,
        "cross_event_duplicate_slot_associations": 0,
        "multi_root_slot_count": 0,
        "all_672_campaign_slots_unchanged": False,
        "events": [],
        "distinct_slot_exposures": [],
        "model_direction": None,
        "calibrated_probability": None,
        "out_of_sample_accuracy": None,
        "operational_bias": "AGUARDAR",
        "trade_authorized": False,
        "publishable": False,
        "live_alert_allowed": False,
        "worker_enabled": False,
        "scheduler_enabled": False,
        "http_requests": 0,
        "file_writes": 0,
        "new_cost_brl": 0,
        "research_only": True,
    }


def inspect_three_dec2026_macro_event_roots_lab(
    *, inspected_at_utc: Any,
) -> dict[str, Any]:
    """Map exact, CURRENTLY PUBLISHED SCHEDULES, never infer actual news.

    Explicitly retains one root per unique economic release, and groups
    pair-horizon overlaps without counting them as independent events.
    """
    out = _blocked("INVALID_CLOCK_OR_FROZEN_EVENT_SCOPE")
    now = _utc(inspected_at_utc)
    if (now is None or len(CURRENCIES) != 8
            or len(OFFICIAL_PAIRS) != 28
            or len(set(OFFICIAL_PAIRS)) != 28
            or EXPECTED_PAIR_HORIZON_SLOTS != 672):
        return out

    windows = {h: _nominal_windows(h) for h in ("D1", "W1")}
    if (len(windows["D1"]) != 20 or len(windows["W1"]) != 4
            or windows["D1"][0][0] != FROZEN_START_UTC
            or windows["W1"][0][0] != FROZEN_START_UTC
            or windows["D1"][-1][1] != FROZEN_END_UTC
            or windows["W1"][-1][1] != FROZEN_END_UTC):
        out["reason"] = "FROZEN_NY17_CALENDAR_DIVERGED"
        return out

    try:
        cuiaba = ZoneInfo("America/Cuiaba")
        events = []
        exposures: dict[str, dict[str, Any]] = {}
        for root, currency, kind, source, zone, wall, expected_utc, expected_cuiaba in (
            SCHEDULE_REFERENCE_ONLY
        ):
            local = datetime(*wall, tzinfo=ZoneInfo(zone))
            instant = local.astimezone(timezone.utc)
            cuiaba_clock = instant.astimezone(cuiaba)
            if (instant.isoformat() != expected_utc
                    or cuiaba_clock.isoformat() != expected_cuiaba
                    or not FROZEN_START_UTC <= instant < FROZEN_END_UTC):
                out["reason"] = "OFFICIAL_SCHEDULE_TIMEZONE_INTERPRETATION_CHANGED"
                return out

            direct_pairs = tuple(
                pair for pair in OFFICIAL_PAIRS if currency in split_pair(pair)
            )
            if len(direct_pairs) != 7:
                out["reason"] = "DIRECT_CURRENCY_PAIRS_NOT_SEVEN"
                return out

            matching = []
            for horizon in ("D1", "W1"):
                contained = [(start, end) for start, end in windows[horizon]
                             if start <= instant < end]
                if len(contained) != 1:
                    out["reason"] = "EVENT_NOT_IN_EXACTLY_ONE_D1_AND_W1_WINDOW"
                    return out
                start, end = contained[0]
                matching.append({
                    "horizon": horizon,
                    "start_utc": start.isoformat(),
                    "end_utc": end.isoformat(),
                    "pairs_with_direct_currency": 7,
                    "forecast_witness_or_broker_price_authenticated": False,
                })
                for pair in direct_pairs:
                    slot_id = (
                        f"FX28_NY17_{start.strftime('%Y%m%dT%H%MZ')}"
                        f"_{horizon}_{pair}"
                    )
                    if slot_id not in exposures:
                        exposures[slot_id] = {
                            "slot_id": slot_id,
                            "pair": pair,
                            "horizon": horizon,
                            "window_start_utc": start.isoformat(),
                            "window_end_utc": end.isoformat(),
                            "event_roots": [],
                            "event_direction": None,
                            "independently_witnessed": False,
                            "trade_authorized": False,
                        }
                    exposures[slot_id]["event_roots"].append(root)

            events.append({
                "event_root_id": root,
                "currency": currency,
                "metric_type": kind,
                "schedule_reference_url": source,
                "source_is_captured_original": False,
                "first_seen_issuer_timestamp_authenticated": False,
                "scheduled_at_local": local.isoformat(),
                "scheduled_at_utc_interpreted": instant.isoformat(),
                "scheduled_at_cuiaba_interpreted": cuiaba_clock.isoformat(),
                "schedule_status_at_inspection": (
                    "UPCOMING_UNATTESTED_PUBLIC_REFERENCE" if now < instant
                    else "ELAPSED_SCHEDULE_NOT_BACKFILLABLE_FORECAST"
                ),
                "actual_release_observed": False,
                "result_or_rate_change_known": False,
                "signed_fx_effect": None,
                "pre_event_consensus": None,
                "horizon_windows": matching,
                "direct_pair_horizon_associations": 14,
                "one_root_not_fourteen_independent_events": True,
            })
    except (ZoneInfoNotFoundError, OSError, ValueError,
            OverflowError, TypeError):
        out["reason"] = "REQUIRED_IANA_TIMEZONE_DATA_UNAVAILABLE"
        return out

    if len({x["event_root_id"] for x in events}) != 3:
        out["reason"] = "DUPLICATE_ECONOMIC_EVENT_ROOT_ID"
        return out
    slots = [exposures[k] for k in sorted(exposures)]
    associations = sum(len(row["event_roots"]) for row in slots)
    multi = sum(len(row["event_roots"]) > 1 for row in slots)
    if (len(events) != 3 or len(slots) != 38
            or associations != 42 or associations-len(slots) != 4
            or multi != 4
            or any(len(x["event_roots"]) != len(set(x["event_roots"]))
                   or len(x["event_roots"]) > 2 for x in slots)):
        out["reason"] = "EVENT_ROOT_PAIR_HORIZON_EXPOSURE_NOT_RECONCILED"
        return out

    out.update({
        "state": "LAB_FX28_THREE_DEC_EVENTS_RECONCILED_PUBLIC_SCHEDULE_NO_GO",
        "reason": "THREE_NOT_FORTY_TWO_EVENTS_OVERLAPPING_D1_W1_SLOTS",
        "event_root_count": 3,
        "root_to_pair_horizon_associations": 42,
        "unique_pair_horizon_slots_exposed": 38,
        "cross_event_duplicate_slot_associations": 4,
        "multi_root_slot_count": 4,
        "all_672_campaign_slots_unchanged": True,
        "events": events,
        "distinct_slot_exposures": slots,
    })
    return out


__all__ = ("SCHEMA", "SNB_ROOT", "BOJ_ROOT", "SCHEDULE_REFERENCE_ONLY",
           "inspect_three_dec2026_macro_event_roots_lab")
