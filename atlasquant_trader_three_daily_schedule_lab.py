"""Timezone-safe, offline plan for AtlasQuant's THREE daily refresh windows.

Plans are not jobs. No scheduler, news retrieval, broker access, directional
signal, probability, network request, write or trade is performed.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
import re
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

SCHEMA = "ATLASQUANT_TRADER_THREE_DAILY_BRT_SCHEDULE_LAB_V1"
BASE_TIMEZONE = "America/Sao_Paulo"
USER_TIMEZONE = "America/Cuiaba"
NY_TIMEZONE = "America/New_York"
REFRESH_WINDOWS_BRT = (("MORNING", time(6, 35)),
                       ("MIDDAY", time(10, 45)),
                       ("AFTERNOON", time(17, 15)))
INDICATOR_CHECK_BRT = time(6, 40)
HIGH_IMPACT_BLACKOUT = timedelta(minutes=30)
EVENT_ID = re.compile(r"[A-Z][A-Z0-9_:-]{2,47}\Z")


@dataclass(frozen=True)
class CalendarEventClaim:
    event_id: str
    currency_or_asset: str
    impact: str
    scheduled_at: datetime


def _utc(value: Any) -> datetime | None:
    if (not isinstance(value, datetime) or value.tzinfo is None
            or value.utcoffset() is None or value.microsecond != 0):
        return None
    return value.astimezone(timezone.utc)


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_THREE_DAILY_REFRESH_PLAN_BLOCKED",
        "reason": reason, "reference_date_brt": None,
        "daily_master_refresh_count": 0, "planned_slots": [],
        "indicator_age_check": None,
        "source_event_claim_count": 0,
        "schedule_timezones_calculated": False,
        "calendar_events_independently_authenticated": False,
        "refresh_jobs_actually_scheduled": False,
        "news_fetched": False, "macro_data_fetched": False,
        "new_bias_emitted": False, "validated_accuracy": None,
        "calibrated_probability": None, "operational_bias": "AGUARDAR",
        "can_feed_live_radar": False, "trade_authorized": False,
        "worker_enabled": False, "http_requests": 0, "file_writes": 0,
        "new_cost_brl": 0,
    }


def _time_row(when: datetime, *, user_zone: ZoneInfo,
              ny_zone: ZoneInfo) -> dict[str, str]:
    return {
        "scheduled_brt": when.isoformat(),
        "scheduled_utc": when.astimezone(timezone.utc).isoformat(),
        "scheduled_cuiaba_local": when.astimezone(user_zone).isoformat(),
        "scheduled_new_york_local": when.astimezone(ny_zone).isoformat(),
    }


def plan_three_daily_refreshes_lab(
    *, reference_date_brt: Any, calendar_events: Any = (),
) -> dict[str, Any]:
    """Plan three BRT refreshes plus separate 06:40 indicator-age check.

    A *claimed* high-impact event near a refresh tags risk and abstains from
    signals. Absence of caller events NEVER certifies the full calendar.
    """
    out = _blocked("INVALID_DATE_OR_EVENT_CLAIMS")
    if (not isinstance(reference_date_brt, date)
            or isinstance(reference_date_brt, datetime)
            or not 2020 <= reference_date_brt.year <= 2100
            or not isinstance(calendar_events, (tuple, list))
            or len(calendar_events) > 64):
        return out
    try:
        brt = ZoneInfo(BASE_TIMEZONE)
        user = ZoneInfo(USER_TIMEZONE)
        ny = ZoneInfo(NY_TIMEZONE)
    except ZoneInfoNotFoundError:
        out["reason"] = "REQUIRED_IANA_TIMEZONE_DATABASE_UNAVAILABLE"
        return out
    events: list[tuple[CalendarEventClaim, datetime]] = []
    seen_ids: set[str] = set()
    for claim in calendar_events:
        if (not isinstance(claim, CalendarEventClaim)
                or not isinstance(claim.event_id, str)
                or EVENT_ID.fullmatch(claim.event_id) is None
                or claim.event_id in seen_ids
                or not isinstance(claim.currency_or_asset, str)
                or not 2 <= len(claim.currency_or_asset) <= 32
                or claim.impact not in ("HIGH", "MEDIUM", "LOW")):
            out["reason"] = "UNSUPPORTED_OR_DUPLICATE_CALENDAR_EVENT_CLAIM"
            return out
        at = _utc(claim.scheduled_at)
        if at is None:
            out["reason"] = "CALENDAR_EVENT_CLOCK_MISSING_OR_NAIVE"
            return out
        seen_ids.add(claim.event_id)
        events.append((claim, at))

    planned = []
    for name, hhmm in REFRESH_WINDOWS_BRT:
        when = datetime.combine(reference_date_brt, hhmm, tzinfo=brt)
        at_utc = when.astimezone(timezone.utc)
        # Round-trip avoids silently normalizing nonexistent/ambiguous local
        # wall times in any future schedule revision.
        if at_utc.astimezone(brt).replace(fold=when.fold) != when:
            out["reason"] = "BRT_REFRESH_TIME_NONEXISTENT_OR_AMBIGUOUS"
            return out
        near = sorted(claim.event_id for claim, instant in events
                      if claim.impact == "HIGH"
                      and abs(instant - at_utc) <= HIGH_IMPACT_BLACKOUT)
        row = {
            "refresh_window": name, **_time_row(when, user_zone=user, ny_zone=ny),
            "data_refresh_planned_not_executed": True,
            "risk_high_impact_event_ids_claimed": near,
            "bias_review_status": ("HIGH_IMPACT_BLACKOUT_CLAIM_REVIEW"
                                   if near else "CALENDAR_COMPLETENESS_UNVERIFIED"),
            "bias_publication_allowed": False,
            "operational_bias": "AGUARDAR",
        }
        planned.append(row)
    indicator_at = datetime.combine(reference_date_brt, INDICATOR_CHECK_BRT, tzinfo=brt)
    out.update({
        "state": "LAB_THREE_DAILY_BRT_REFRESH_PLAN_ONLY_NO_GO",
        "reason": "TIMEZONES_PROVISIONALLY_CORRECT_NO_WORKER_SOURCE_OR_BIAS_ATTESTATION",
        "reference_date_brt": reference_date_brt.isoformat(),
        "daily_master_refresh_count": 3,
        "planned_slots": planned,
        "indicator_age_check": {
            **_time_row(indicator_at, user_zone=user, ny_zone=ny),
            "purpose": "CHECK_INDICATOR_FRESHNESS_NOT_AN_EXTRA_BIAS_ALERT",
            "executed": False,
        },
        "source_event_claim_count": len(events),
        "schedule_timezones_calculated": True,
    })
    return out


__all__ = ["SCHEMA", "CalendarEventClaim", "plan_three_daily_refreshes_lab"]
