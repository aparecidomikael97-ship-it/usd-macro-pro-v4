"""Pure, NO-EXECUTION daily refresh plan for the AtlasQuant Painel Mestre.

This is an auditable proposal for a future external scheduler. Calling these
functions NEVER fetches data, writes files, schedules jobs, enables providers,
activates the AION Worker, or generates a financial-market signal.

All windows use Brasília civil time (UTC-03:00, 2026; no DST in Brazil).
Before enabling any external runner: confirm EODHD entitlement/cost, a global
durable quota ledger, source timeout policy, storage/access control, and an
independent scheduler with logs. The in-memory quota guard is not a global cap.

Three EODHD slots per day reserve one of the default four process budget
slots for demand reads, but cannot guarantee global budget across replicas.
Official BCB/FRED observation read is at most once daily per process.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Mapping

from atlasquant_trader_calendar_quota_guard import configured_cap, permission_enabled
from atlasquant_trader_master_official_series import enabled as official_enabled

SCHEMA = "ATLASQUANT_MASTER_DAILY_REFRESH_PLAN_V1"
BRT = timezone(timedelta(hours=-3), "BRT")
# Tuples represent local HH:MM. Execution has deliberately NOT been implemented.
SLOTS = (
    ("CALENDÁRIO", time(6, 35), "Pré-mercado: agenda e consensos existentes"),
    ("SÉRIES OFICIAIS", time(6, 40), "Período vigente BCB/SGS e FRED (sem mudar frequência)"),
    ("CALENDÁRIO", time(10, 45), "Conferência pós-divulgações da manhã"),
    ("CALENDÁRIO", time(17, 15), "Fechamento: revisões recebidas do calendário"),
)
MAX_SCHEDULED_CALENDAR = 3
MIN_ON_DEMAND_RESERVE = 1


def _aware(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ValueError("Necessário datetime com fuso horário")
    return value.astimezone(BRT)


def day_slots(for_day: date) -> list[dict[str, Any]]:
    if not isinstance(for_day, date) or isinstance(for_day, datetime):
        raise ValueError("Necessário dia civil de Brasília")
    result = []
    for kind, hour, detail in SLOTS:
        at = datetime.combine(for_day, hour, tzinfo=BRT)
        result.append({
            "kind": kind, "at_brt": at.isoformat(),
            "at_utc": at.astimezone(timezone.utc).isoformat(),
            "detail": detail, "state": "PLANEJADO_NÃO_EXECUTADO",
            "has_side_effects": False, "trade_authorized": False,
        })
    return result


def planned_refreshes(*, at: datetime | None = None, days: int = 7,
                      env: Mapping[str, str] | None = None) -> dict[str, Any]:
    """Return a transparent schedule, not an active recurring task."""
    current = _aware(at if at is not None else datetime.now(timezone.utc))
    if isinstance(days, bool) or not isinstance(days, int) or not 1 <= days <= 7:
        raise ValueError("Horizonte permitido: de 1 a 7 dias")
    day = current.date()
    rows = [slot for increment in range(days)
            for slot in day_slots(day + timedelta(days=increment))]
    upcoming = [x for x in rows if datetime.fromisoformat(x["at_brt"]) > current]
    calendar_flag = permission_enabled(dict(env) if env is not None else None)
    official_flag = official_enabled(env)
    cap = configured_cap(dict(env) if env is not None else None)
    if cap >= MAX_SCHEDULED_CALENDAR + MIN_ON_DEMAND_RESERVE:
        budget = "CABE_NO_LIMITE_POR_PROCESSO"
    else:
        budget = "LIMITE_INSUFICIENTE"
    return {
        "schema": SCHEMA, "generated_at_utc": current.astimezone(timezone.utc).isoformat(),
        "date_brt": day.isoformat(), "timezone": "Brasília (UTC-03:00)",
        "horizon_days": days, "slots": rows,
        "next_slot": upcoming[0] if upcoming else None,
        "calendar_slots_per_day": MAX_SCHEDULED_CALENDAR,
        "official_slots_per_day": 1,
        "calendar_process_cap": cap, "on_demand_reserve": MIN_ON_DEMAND_RESERVE,
        "budget_state": budget,
        "calendar_provider_enabled": calendar_flag,
        "official_provider_enabled": official_flag,
        "background_executor_enabled": False,
        "job_scheduled": False,
        "external_requests": 0,
        "state": "NÃO ATIVADO · SIMULAÇÃO DE JANELAS",
        "why_not": (
            "Sem agendador externo autorizado, armazenamento auditável ou "
            "franquia global comprovada. Nenhuma coleta será iniciada por este plano."
        ),
        "aion_worker_enabled": False, "trade_authorized": False,
    }


__all__ = ["SCHEMA", "SLOTS", "BRT", "day_slots", "planned_refreshes"]
