"""AtlasQuant Trader — evidential read model reconciled with Checkpoint Mestre.

Scope: four approved Trader screens. No feed fetching, trading, Workers,
background writes, billing, score-to-profit mapping, or artificial signals.

Canonical references:
- docs/continuidade/CHECKPOINT_MESTRE_ATLASQUANT_2026-09-22.md
- docs/continuidade/CHECKPOINT_MESTRE_RECONCILIACAO_2026-09-29.md
- Trader reconciliation PR #1473 (T01–T58, documentary / not certified)

Macro = direction; ICT/SMC = location and trigger; risk = when NOT to trade.
All missing, stale or conflicting evidence is fail-closed.
"""
from __future__ import annotations

from datetime import datetime, timezone
from math import isfinite
from typing import Any, Mapping

from atlasquant_fx_universe import CURRENCIES, OFFICIAL_PAIRS

SCHEMA = "ATLASQUANT_TRADER_EVIDENCE_READ_MODEL_V1"
_DAILY_FRESH_SECONDS = 20 * 60
_CALENDAR_FRESH_SECONDS = 2 * 3600
_REQUIRED_TF = ("D1", "H4", "M15")


def _timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip() or len(value) > 60:
        return None
    try:
        point = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError, OverflowError):
        return None
    return point.astimezone(timezone.utc) if point.tzinfo is not None else None


def _age(raw: Any, now: datetime, *, max_seconds: float) -> tuple[str, int | None]:
    stamp = _timestamp(raw)
    if stamp is None:
        return "SEM HORÁRIO", None
    seconds = (now - stamp).total_seconds()
    if seconds < -60:
        return "HORÁRIO INVÁLIDO", None
    minutes = max(0, int(seconds // 60))
    return ("ATUAL" if seconds <= max_seconds else "ATRASADO"), minutes


def _valid_change(value: Any) -> bool:
    if isinstance(value, bool) or not isinstance(value, Mapping):
        return False
    v = value.get("change_pct")
    if isinstance(v, bool):
        return False
    try:
        f = float(v)
    except (ValueError, TypeError, OverflowError):
        return False
    return isfinite(f) and abs(f) <= 100


def _forex(daily_data: Any, now: datetime) -> dict[str, Any]:
    base = {"state": "SEM DADOS", "covered": 0, "total": len(OFFICIAL_PAIRS),
            "currencies_covered": 0, "currencies_total": len(CURRENCIES),
            "updated_at": "", "age_minutes": None,
            "reason": "28 pares monitorados não significam 28 leituras validadas."}
    if not isinstance(daily_data, Mapping) or daily_data.get("state") != "VALIDATED_DAILY":
        return base
    source = str(daily_data.get("source") or "").strip()
    clock, age = _age(daily_data.get("as_of"), now, max_seconds=_DAILY_FRESH_SECONDS)
    if not source or len(source) > 160:
        return {**base, "state": "SEM FONTE", "reason": "Fonte diária não identificada."}
    if clock != "ATUAL":
        return {**base, "state": clock, "age_minutes": age,
                "reason": "Variações diárias sem horário fresco não geram ranking atual."}
    pairs = daily_data.get("pairs")
    currencies = daily_data.get("currencies")
    if not isinstance(pairs, Mapping):
        pairs = {}
    if not isinstance(currencies, Mapping):
        currencies = {}
    pair_codes = set(OFFICIAL_PAIRS)
    fx = sum(1 for pair in pair_codes
             if pair in pairs and _valid_change(pairs[pair])
             and str(pairs[pair].get("bias") or "").upper() in {"ALTA", "BAIXA", "NEUTRO"})
    cc = sum(1 for code in CURRENCIES
             if code in currencies and _valid_change(currencies[code]))
    complete = fx == len(OFFICIAL_PAIRS) and cc == len(CURRENCIES)
    state = "COBERTURA COMPLETA" if complete else "PARCIAL"
    reason = (
        "Universo diário completo; ainda faltam técnica, risco e gatilho para qualquer decisão."
        if complete else
        f"Apenas {fx}/{len(OFFICIAL_PAIRS)} pares e {cc}/{len(CURRENCIES)} moedas com leituras válidas."
    )
    return {**base, "state": state, "covered": fx, "currencies_covered": cc,
            "source": source, "updated_at": str(daily_data["as_of"]),
            "age_minutes": age, "reason": reason}


def _calendar(calendar_data: Any, now: datetime) -> dict[str, Any]:
    base = {"state": "SEM DADOS", "events": 0, "reason":
            "Calendário requer origem, dia de referência e carimbo de atualização."}
    if not isinstance(calendar_data, Mapping) or calendar_data.get("state") != "READY":
        if isinstance(calendar_data, Mapping):
            status = str(calendar_data.get("state") or "").strip()
            if status in {"STALE_PROVIDER", "INCOMPLETE_PROVIDER", "UNAVAILABLE"}:
                return {**base, "state": status, "reason":
                        "Fonte do calendário indisponível, incompleta ou atrasada."}
        return base
    source = str(calendar_data.get("source") or "").strip()
    clock, age = _age(calendar_data.get("fetched_at"), now, max_seconds=_CALENDAR_FRESH_SECONDS)
    try:
        from atlasquant_trader_opening_collector import brasilia_clock
        date_brt = brasilia_clock(now).date().isoformat()
    except (TypeError, ValueError):
        return base
    if not source or calendar_data.get("date") != date_brt or clock != "ATUAL":
        return {**base, "state": "NÃO VALIDADO" if clock == "ATUAL" else clock,
                "reason": "Data, fonte ou coleta diária não comprovada."}
    events = calendar_data.get("events")
    if not isinstance(events, list):
        return base
    if calendar_data.get("truncated") is True:
        return {**base, "state": "INCOMPLETO", "events": len(events),
                "reason": "Lista de eventos truncada; calendário parcial."}
    return {"state": "VALIDADO", "events": len(events), "source": source,
            "age_minutes": age, "reason":
            "Eventos de hoje identificados; impactos seguem condicionais, não sinais."}


def _scanner(technical_data: Any, now: datetime) -> dict[str, Any]:
    base = {"state": "SEM LEITURA", "timeframes": [], "reason":
            "Faltam estrutura D1, confirmação H4 e gatilho M15 verificados."}
    if not isinstance(technical_data, Mapping) or technical_data.get("state") != "VALIDATED_TECHNICAL":
        return base
    symbol = str(technical_data.get("symbol") or "")
    clock, _ = _age(technical_data.get("as_of"), now, max_seconds=15 * 60)
    tf = technical_data.get("timeframes")
    if (symbol not in OFFICIAL_PAIRS or clock != "ATUAL"
            or not str(technical_data.get("source") or "").strip()
            or not isinstance(tf, Mapping)):
        return {**base, "state": "NÃO CONFIRMADO", "reason":
                "Ativo, fonte, horário ou timeframes técnicos não comprovados."}
    available = [key for key in _REQUIRED_TF
                 if isinstance(tf.get(key), Mapping) and
                 tf[key].get("state") == "VERIFIED"]
    if len(available) != len(_REQUIRED_TF):
        return {**base, "state": "PARCIAL", "timeframes": available,
                "reason": "M15 sem gatilho verificado é AGUARDAR, não quase pronto."}
    return {"state": "EM ESTUDO", "timeframes": available,
            "reason": "D1/H4/M15 verificados; ainda sem autorização do Risk Guardian."}


def build_trader_readiness(
    *, daily_data: Any = None, calendar_data: Any = None,
    technical_data: Any = None, at: datetime | None = None,
) -> dict[str, Any]:
    """Explain why the four-screen read-only Trader is or is not ready."""
    now = at or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("O instante de validação exige fuso horário")
    moment = now.astimezone(timezone.utc)
    fx = _forex(daily_data, moment)
    cal = _calendar(calendar_data, moment)
    tech = _scanner(technical_data, moment)
    blockers = []
    if fx["state"] != "COBERTURA COMPLETA":
        blockers.append("Radar Forex: " + fx["reason"])
    if cal["state"] != "VALIDADO":
        blockers.append("Painel Mestre: " + cal["reason"])
    if tech["state"] != "EM ESTUDO":
        blockers.append("Scanner Técnico: " + tech["reason"])
    blockers.append("Risco: nenhum gate de negociação real foi autorizado.")
    return {
        "schema": SCHEMA,
        "checked_at": moment.isoformat(),
        "forex": fx, "calendar": cal, "scanner": tech,
        "decision": {"state": "AGUARDAR", "why_not": blockers,
                     "macro_direction_is_entry": False,
                     "real_orders_enabled": False,
                     "automatic_execution": False},
        "home": {"monitored_fx": len(OFFICIAL_PAIRS),
                 "g8_currencies": len(CURRENCIES), "readiness": "EM DESENVOLVIMENTO"},
    }


__all__ = ["SCHEMA", "build_trader_readiness"]
