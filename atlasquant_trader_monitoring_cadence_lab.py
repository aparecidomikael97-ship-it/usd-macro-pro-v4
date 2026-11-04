"""NO-RUN three-daily-update cadence for AtlasQuant Trader macro/news.

Preserves the three Brasilia calendar slots already proposed in the Master
refresh plan. As explicitly decided by the owner, intraday polling and future
hourly paid updates are DEFERRED, not enabled by default or implicitly.
No source can be called 'realtime' before its delivery delay is proven.
This module does not schedule, fetch, store, bill or notify anything.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from atlasquant_trader_macro_event_exposure_v2_lab import (
    CALENDAR, REVIEW_DATE,
)

SCHEMA = "ATLASQUANT_TRADER_MONITORING_CADENCE_LAB_V2"
BRT = timezone(timedelta(hours=-3), "BRT")
MT = ZoneInfo("America/Cuiaba")
# Keep aligned with atlasquant_trader_master_refresh_plan.SLOTS calendar rows.
DAILY_FULL_REFRESH = (time(6, 35), time(10, 45), time(17, 15))
# Owner decision: current free phase = 3 updates/day; hourly is future-only.
FUTURE_HOURLY_MINUTES = 60
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
        "schema": SCHEMA, "state": "LAB_THREE_DAILY_ONLY_NOT_RUNNING",
        "as_of_utc": now.isoformat(),
        "three_full_refreshes_per_day": True,
        "daily_full_refresh_target": 3,
        "daily_full_refresh_slots_next_two_days": slots,
        "current_update_mode": "THREE_DAILY_REVIEWS_ONLY",
        "extra_intraday_polls_planned_now": False,
        "active_hourly_refresh": False,
        "active_high_frequency_refresh": False,
        "current_extra_poll_target_minutes": None,
        "future_optional_hourly_target_minutes": FUTURE_HOURLY_MINUTES,
        "future_hourly_requires_owner_approval": True,
        "future_hourly_budget_approved": False,
        "critical_window_before_and_after_minutes": CRITICAL_WINDOW_MINUTES,
        "in_curated_critical_window": bool(critical),
        "curated_critical_event_ids": [e["event_id"] for e in critical],
        "critical_events_prioritized_in_next_full_review_only": True,
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
        "why_not": ("Decisao do proprietario: apenas 3 atualizacoes diarias "
                    "na fase gratuita. 1/h e qualquer monitoramento extra "
                    "precisam de nova autorizacao; horários nao provam "
                    "execucao, custodia ou latencia de noticia."),
    }


__all__ = ["SCHEMA", "DAILY_FULL_REFRESH", "build_monitoring_cadence_lab"]
