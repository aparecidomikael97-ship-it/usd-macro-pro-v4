"""NO-RUN monitoring cadence proposal for AtlasQuant Trader macro/news.

Preserves the three Brasilia calendar slots already proposed in the Master
refresh plan, and adds a non-executable faster *target* around critical events.
No source can be called 'realtime' before its actual delivery delay is proven.
This module does not schedule, fetch, store, bill or notify anything.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from atlasquant_trader_macro_event_exposure_v2_lab import (
    CALENDAR, REVIEW_DATE,
)

SCHEMA = "ATLASQUANT_TRADER_MONITORING_CADENCE_LAB_V1"
BRT = timezone(timedelta(hours=-3), "BRT")
MT = ZoneInfo("America/Cuiaba")
# Keep aligned with atlasquant_trader_master_refresh_plan.SLOTS calendar rows.
DAILY_FULL_REFRESH = (time(6, 35), time(10, 45), time(17, 15))
GENERAL_POLL_TARGET_MINUTES = 15
CRITICAL_POLL_TARGET_MINUTES = 5
CRITICAL_WINDOW_MINUTES = 120


def build_monitoring_cadence_lab(*, at: datetime) -> dict[str, Any]:
    if (not isinstance(at, datetime) or at.tzinfo is None
            or at.utcoffset() is None):
        raise ValueError("Timezone-aware evaluation is required")
    now = at.astimezone(timezone.utc)
    local_day = now.astimezone(BRT).date()
    slots = []
    for offset in (0, 1):
        day = local_day + timedelta(days=offset)
        for clock in DAILY_FULL_REFRESH:
            expected = datetime.combine(day, clock, tzinfo=BRT)
            slots.append({
                "at_brt": expected.isoformat(),
                "at_mato_grosso": expected.astimezone(MT).isoformat(),
                "at_utc": expected.astimezone(timezone.utc).isoformat(),
                "state": "PLANNED_NOT_EXECUTED", "run_receipt_verified": False,
            })
    critical = []
    if now.date() >= REVIEW_DATE:
        for event in CALENDAR:
            if event["time_precision"] != "SCHEDULED_MINUTE":
                continue
            when = datetime.fromisoformat(
                event["earliest_at_utc"].replace("Z", "+00:00"))
            if abs((when - now).total_seconds()) <= CRITICAL_WINDOW_MINUTES * 60:
                critical.append({"event_id": event["event_id"],
                                 "currency": event["currency"],
                                 "scheduled_at_utc": when.isoformat()})
    return {
        "schema": SCHEMA, "state": "LAB_POLICY_ONLY_NOT_RUNNING",
        "as_of_utc": now.isoformat(),
        "three_full_refreshes_per_day": True,
        "daily_full_refresh_target": 3,
        "daily_full_refresh_slots_next_two_days": slots,
        "general_source_check_target_minutes": GENERAL_POLL_TARGET_MINUTES,
        "near_critical_release_check_target_minutes": CRITICAL_POLL_TARGET_MINUTES,
        "critical_window_before_and_after_minutes": CRITICAL_WINDOW_MINUTES,
        "in_curated_critical_window": bool(critical),
        "curated_critical_event_ids": [e["event_id"] for e in critical],
        "target_poll_minutes_now": (CRITICAL_POLL_TARGET_MINUTES if critical
                                    else GENERAL_POLL_TARGET_MINUTES),
        "source_rate_limits_reviewed": False,
        "source_terms_and_commercial_license_checked": False,
        "full_g8_calendar_coverage": False,
        "news_feed_latency_measured": False,
        "realtime_delivery_verified": False,
        "three_daily_runs_actually_verified": False,
        "durable_change_history_available": False,
        "alert_delivery_verified": False,
        "calendar_changes_automatically_ingested": False,
        "news_live": False, "scheduler_enabled": False,
        "worker_enabled": False, "aion_worker_enabled": False,
        "paid_api_enabled": False, "paid_provider_charged": False,
        "new_external_requests": 0, "trade_authorized": False,
        "can_feed_live_radar": False,
        "why_not": ("Alvos de verificacao e horarios nao provam execucao nem "
                    "latencia. Ativacao requer permissao das fontes, agendador "
                    "duravel, cota, log de mudancas, custos e auditoria."),
    }


__all__ = ["SCHEMA", "DAILY_FULL_REFRESH", "build_monitoring_cadence_lab"]
