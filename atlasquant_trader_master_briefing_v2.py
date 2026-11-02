"""Painel Mestre V2 — briefing auditável a partir do calendário econômico.

Fonte: contrato do calendário AtlasQuant, sem fetch extra. Não infere viés de
moeda, valores não divulgados, geopolítica, notícia ou autorização de trade.
Se o feed estiver incompleto, ausente ou velho, o briefing é INDISPONÍVEL.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from math import isfinite
from typing import Any, Mapping

from atlasquant_trader_opening_collector import brasilia_clock
from atlasquant_trader_economic_calendar import explanation

SCHEMA = "ATLASQUANT_MASTER_BRIEFING_EVIDENCE_V2"
MAX_AGE_SECONDS = 2 * 3600
PRIORITY_TERMS = (
    "cpi", "consumer price", "pce", "ppi", "nonfarm", "payroll",
    "unemployment", "fomc", "rate decision", "interest rate",
    "gdp", "pmi", "ism", "ipca", "selic", "copom", "boj", "ecb",
    "central bank", "jobless claims", "retail sales", "fed",
)
CENTRAL_BANK_TERMS = (
    "interest rate", "rate decision", "fomc", "copom", "selic",
    "federal reserve", "central bank", "boe", "ecb", "boj",
    "pboc", "rba", "rbnz", "boc", "snb",
)


def _timestamp(raw: Any) -> datetime | None:
    if not isinstance(raw, str) or len(raw) > 65:
        return None
    try:
        moment = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except (TypeError, ValueError, OverflowError):
        return None
    return moment.astimezone(timezone.utc) if moment.tzinfo else None


def _number(raw: Any) -> float | None:
    if isinstance(raw, bool):
        return None
    try:
        number = float(raw)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if isfinite(number) and abs(number) <= 1e9 else None


def _is_editorial_priority(event: Mapping[str, Any]) -> bool:
    title = str(event.get("title") or "").lower()
    return any(term in title for term in PRIORITY_TERMS)


def _empty(reason: str, *, day: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "INDISPONÍVEL", "day": day,
        "source": "", "fetched_at": "", "daily_events": 0,
        "week_events": 0, "week_received_total": 0, "week_partial": False,
        "central_bank_events": 0,
        "upcoming_today": 0, "published_today": 0,
        "surprises_today": 0, "priority_events": [],
        "risk_window": [], "week_preview": [], "briefing": [],
        "why_not": reason,
        "trade_authorized": False, "directional_bias": None,
    }


def build_master_briefing(calendar: Any, *, at: datetime | None = None) -> dict[str, Any]:
    """Build evidence-only daily/weekly agenda; never rate decisions as trades."""
    now = at or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("O instante deve conter fuso")
    now = now.astimezone(timezone.utc)
    date_brt = brasilia_clock(now).date()
    result = _empty("Calendário de fonte validada ainda não disponível.", day=date_brt.isoformat())
    if not isinstance(calendar, Mapping) or calendar.get("state") != "READY":
        return result
    source = str(calendar.get("source") or "").strip()
    fetched = _timestamp(calendar.get("fetched_at"))
    if not source or len(source) > 160 or fetched is None:
        return _empty("Fonte ou horário real de coleta ausente.", day=date_brt.isoformat())
    age = (now - fetched).total_seconds()
    if age < -60 or age > MAX_AGE_SECONDS:
        return _empty("Calendário atrasado ou com carimbo de hora futura.", day=date_brt.isoformat())
    if calendar.get("date") != date_brt.isoformat():
        return _empty("O calendário não corresponde ao dia em Brasília.", day=date_brt.isoformat())
    if calendar.get("truncated"):
        return _empty("O calendário de hoje foi limitado; resumo diário bloqueado.",
                      day=date_brt.isoformat())
    week_partial = calendar.get("week_truncated") is True
    today = calendar.get("events")
    week = calendar.get("week_events", [])
    if not isinstance(today, list) or not isinstance(week, list):
        return _empty("Eventos diários ou semanais sem contrato verificável.",
                      day=date_brt.isoformat())
    if len(today) > 120 or len(week) > 120:
        return _empty("A fonte excedeu a capacidade de validação.",
                      day=date_brt.isoformat())
    # Missing total counts is not silently promoted to complete coverage.
    week_total = calendar.get("week_total", 0)
    if (calendar.get("total") != len(today) or not isinstance(week_total, int)
            or isinstance(week_total, bool)
            or (week_partial and week_total <= len(week))
            or (not week_partial and week_total != len(week))):
        return _empty("Contagens do calendário divergentes ou incompletas.",
                      day=date_brt.isoformat())
    confirmed_today = []
    confirmed_week = []
    for item in today:
        if not isinstance(item, Mapping):
            return _empty("Evento do dia com contrato inválido.", day=date_brt.isoformat())
        stamp = _timestamp(item.get("release_utc"))
        if stamp is None or brasilia_clock(stamp).date() != date_brt:
            return _empty("Evento diário com data/hora incorretas.", day=date_brt.isoformat())
        confirmed_today.append((stamp, item))
    for item in week:
        if not isinstance(item, Mapping):
            return _empty("Evento da semana com contrato inválido.", day=date_brt.isoformat())
        stamp = _timestamp(item.get("release_utc"))
        if (stamp is None or not date_brt < brasilia_clock(stamp).date()
                < date_brt + timedelta(days=7)):
            return _empty("Evento semanal fora da janela validada.", day=date_brt.isoformat())
        confirmed_week.append((stamp, item))
    confirmed_today.sort(key=lambda x: x[0])
    confirmed_week.sort(key=lambda x: x[0])
    published = 0
    surprises = 0
    upcoming = 0
    central = 0
    risks: list[dict[str, Any]] = []
    prominent: list[dict[str, Any]] = []
    for stamp, event in confirmed_today:
        title = str(event.get("title") or "Evento não identificado")[:140]
        currency = str(event.get("currency") or "—")[:8]
        if _is_editorial_priority(event):
            prominent.append({
                "name": title,
                "time": brasilia_clock(stamp).strftime("%H:%M"),
                "currency": currency,
                "release_utc": stamp.isoformat(),
                "editorial_only": True,
            })
        if any(term in title.lower() for term in CENTRAL_BANK_TERMS):
            central += 1
        actual = _number(event.get("actual"))
        consensus = _number(event.get("consensus"))
        if stamp <= now and actual is not None:
            published += 1
            if consensus is not None and actual != consensus:
                surprises += 1
        elif stamp > now:
            upcoming += 1
        minutes = (stamp - now).total_seconds() / 60
        if _is_editorial_priority(event) and -30 <= minutes <= 60:
            risks.append({
                "name": title, "currency": currency,
                "time": brasilia_clock(stamp).strftime("%H:%M"),
                "phase": "PRÓXIMO" if minutes > 0 else "DIVULGAÇÃO RECENTE",
            })
    future = [{
        "date": brasilia_clock(stamp).strftime("%d/%m"),
        "time": brasilia_clock(stamp).strftime("%H:%M"),
        "country": str(row.get("country") or "—")[:3],
        "currency": str(row.get("currency") or "—")[:8],
        "name": str(row.get("title") or "—")[:140],
        "consensus": _number(row.get("consensus")),
        "previous": _number(row.get("previous")),
        "priority": _is_editorial_priority(row),
        "period": str(row.get("period") or "")[:50],
        "comparison": str(row.get("comparison") or "")[:12],
        "above": explanation(row)["above"],
        "below": explanation(row)["below"],
        "source": str(row.get("source") or source)[:160],
    } for stamp, row in confirmed_week]
    briefing = [
        f"Agenda de hoje: {len(confirmed_today)} eventos recebidos da fonte; "
        f"{upcoming} ainda aguardam horário de divulgação.",
        f"Divulgações recebidas: {published}; {surprises} acima/abaixo do consenso "
        "quando ambos os números estavam disponíveis.",
        f"Próximos seis dias: {len(confirmed_week)} eventos recebidos. "
        "Uma lista vazia não prova ausência de divulgações no mercado.",
    ]
    if week_partial:
        briefing.append(
            f"Atenção: a lista semanal mostra {len(confirmed_week)} de {week_total} "
            "eventos recebidos; o restante não está disponível nesta visualização."
        )
    if risks:
        briefing.append(
            f"{len(risks)} evento(s) editorialmente relevantes estão perto da divulgação "
            "ou ocorreram nos últimos 30 minutos. Evite inferir direção sem confirmação."
        )
    return {
        "schema": SCHEMA, "state": "VALIDADO", "day": date_brt.isoformat(),
        "source": source, "fetched_at": fetched.isoformat(),
        "daily_events": len(confirmed_today), "week_events": len(confirmed_week),
        "week_received_total": week_total, "week_partial": week_partial,
        "central_bank_events": central,
        "upcoming_today": upcoming, "published_today": published,
        "surprises_today": surprises, "priority_events": prominent[:12],
        "risk_window": risks[:12], "week_preview": future[:80], "briefing": briefing,
        "why_not": "Macro informa contexto; ausência de confirmação técnica e risco bloqueia entrada.",
        "trade_authorized": False, "directional_bias": None,
    }


__all__ = ["SCHEMA", "build_master_briefing"]
