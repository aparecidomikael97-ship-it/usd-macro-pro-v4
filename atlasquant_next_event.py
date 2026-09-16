"""AtlasQuant structured next-event view.

Normalizes already-available macro calendar data without inventing release
times. Exact countdowns are exposed only when an explicit timestamp exists.
"""
from __future__ import annotations

from datetime import timezone
from typing import Any, Mapping
import pandas as pd
import streamlit as st


EXACT_TIME_KEYS=(
    "scheduled_at",
    "datetime_utc",
    "timestamp_utc",
    "event_time_utc",
)


def _now(now_utc: Any = None) -> pd.Timestamp:
    if now_utc is None:
        return pd.Timestamp.now(tz="UTC")
    ts=pd.to_datetime(now_utc,utc=True,errors="coerce")
    if pd.isna(ts):
        return pd.Timestamp.now(tz="UTC")
    return ts


def _parse_exact(event: Mapping[str,Any]) -> pd.Timestamp | None:
    for key in EXACT_TIME_KEYS:
        value=event.get(key)
        if value in (None,""):
            continue
        ts=pd.to_datetime(value,utc=True,errors="coerce")
        if not pd.isna(ts):
            return ts
    return None


def _parse_date(event: Mapping[str,Any]) -> pd.Timestamp | None:
    for key in ("data","date","data_txt"):
        value=event.get(key)
        if value in (None,""):
            continue
        try:
            if key=="data_txt":
                ts=pd.to_datetime(value,dayfirst=True,errors="coerce")
            else:
                ts=pd.to_datetime(value,errors="coerce")
        except Exception:
            continue
        if not pd.isna(ts):
            return pd.Timestamp(ts).normalize()
    return None


def normalize_next_event(
    event: Mapping[str,Any] | None,
    *,
    now_utc: Any = None,
) -> dict[str,Any]:
    e=dict(event or {})
    if not e or e.get("disponivel") is False:
        return {
            "available":False,
            "state":"UNKNOWN",
            "label":"SEM EVENTO ESTRUTURADO",
            "minutes_to_event":None,
            "safety_minutes":None,
            "exact_time":False,
        }

    now=_now(now_utc)
    exact=_parse_exact(e)
    date_only=_parse_date(e)
    name=str(e.get("evento",e.get("name","Evento macro")) or "Evento macro")
    impact=str(e.get("impacto",e.get("impact","—")) or "—").upper()
    source=str(e.get("fonte",e.get("source","—")) or "—")
    kind=str(e.get("tipo",e.get("type","—")) or "—")

    minutes=None
    days=None
    exact_time=exact is not None
    if exact_time:
        minutes=(exact-now).total_seconds()/60.0
        days=(exact.normalize()-now.normalize()).days
        if minutes < 0:
            state="PASSED"; label="EVENTO JÁ PASSOU — ATUALIZAR CONTEXTO"
        elif minutes <= 15:
            state="CRITICAL"; label="EVENTO IMINENTE"
        elif minutes <= 240:
            state="NEAR"; label="EVENTO PRÓXIMO"
        elif days == 0:
            state="TODAY"; label="EVENTO HOJE"
        elif days == 1:
            state="TOMORROW"; label="EVENTO AMANHÃ"
        else:
            state="SCHEDULED"; label="EVENTO AGENDADO"
        display_date=exact.strftime("%d/%m/%Y %H:%M UTC")
    elif date_only is not None:
        today=now.tz_convert(None).normalize()
        days=int((date_only-today).days)
        if days < 0:
            state="PASSED"; label="DATA DO EVENTO JÁ PASSOU — ATUALIZAR"
        elif days == 0:
            state="DATE_ONLY_TODAY"; label="EVENTO HOJE · HORÁRIO NÃO ESTRUTURADO"
        elif days == 1:
            state="DATE_ONLY_TOMORROW"; label="EVENTO AMANHÃ · HORÁRIO NÃO ESTRUTURADO"
        else:
            state="DATE_ONLY"; label="DATA CONFIRMADA · HORÁRIO NÃO ESTRUTURADO"
        display_date=date_only.strftime("%d/%m/%Y")
    else:
        state="UNKNOWN_TIME"; label="EVENTO IDENTIFICADO · DATA/HORÁRIO INSUFICIENTES"
        display_date="—"

    high_impact=impact in {"MÁXIMO","MAXIMO","ALTO","HIGH","MAXIMUM"}
    safety_minutes=minutes if exact_time and high_impact and minutes is not None and minutes >= 0 else None

    if exact_time and minutes is not None and minutes >= 0:
        if minutes < 60:
            countdown=f"{minutes:.0f} min"
        elif minutes < 1440:
            countdown=f"{minutes/60.0:.1f} h"
        else:
            countdown=f"{minutes/1440.0:.1f} d"
    else:
        countdown=None

    if state in {"CRITICAL","NEAR"} and high_impact:
        guidance="Aguardar o evento e nova confirmação/frescor antes de confiar no timing anterior."
    elif state in {"DATE_ONLY_TODAY","DATE_ONLY_TOMORROW"} and high_impact:
        guidance="Não inventar countdown: confirmar horário oficial antes de liberar timing próximo ao evento."
    elif state=="PASSED":
        guidance="Atualizar dados e contexto antes de reutilizar o estado anterior."
    else:
        guidance="Manter o evento como contexto; o Safety Core continua responsável pelos bloqueios operacionais."

    return {
        "available":True,
        "name":name,
        "impact":impact,
        "source":source,
        "type":kind,
        "state":state,
        "label":label,
        "display_date":display_date,
        "exact_time":exact_time,
        "minutes_to_event":None if minutes is None else round(float(minutes),2),
        "days_to_event":days,
        "countdown":countdown,
        "safety_minutes":None if safety_minutes is None else float(safety_minutes),
        "guidance":guidance,
    }


def render_next_event(event: Mapping[str,Any] | None) -> dict[str,Any]:
    info=normalize_next_event(event)
    st.markdown("### 📅 Próximo evento macro")
    st.caption("Horário e countdown só aparecem quando há timestamp estruturado; o painel não inventa hora de release.")

    if not info["available"]:
        st.warning("Nenhum próximo evento macro estruturado disponível.")
        return info

    c1,c2,c3,c4=st.columns(4)
    c1.metric("Evento",info["name"])
    c2.metric("Quando",info["display_date"])
    c3.metric("Impacto",info["impact"])
    c4.metric("Countdown",info["countdown"] or "—")

    if info["state"] in {"CRITICAL","NEAR","DATE_ONLY_TODAY"}:
        st.warning(info["label"])
    elif info["state"]=="PASSED":
        st.error(info["label"])
    else:
        st.info(info["label"])

    st.caption(f"Fonte: {info['source']} · Tipo: {info['type']}")
    st.caption(info["guidance"])
    return info
