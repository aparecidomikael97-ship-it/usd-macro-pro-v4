"""Streamlit calendar panel for USD Macro Pro.

Pure parsing/normalization rules live in calendar_core.py. This module keeps UI,
network access and caching separate so tests do not need Streamlit installed.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from typing import Any, Callable

import pandas as pd
import requests

from calendar_core import MONTHS, TextParser, eod_row, parse_fomc, upcoming, value_text
from atlasquant_indicator_scenarios import indicator_scenario_guide

try:  # Allows unit tests to import this module even outside Streamlit.
    import streamlit as st
except ImportError:  # pragma: no cover - exercised only in minimal test envs
    st = None

FED_URL = "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm"
EOD_URL = "https://eodhd.com/financial-apis/economic-events-data-api"
SNAPSHOT_DATE = "2026-09-13"

# Verified against the official Fed calendar on SNAPSHOT_DATE. Snapshot is a
# safety fallback only; live Fed parsing remains the primary source.
FOMC_SNAPSHOT = [
    "2026-01-28", "2026-03-18", "2026-04-29", "2026-06-17",
    "2026-07-29", "2026-09-16", "2026-10-28", "2026-12-09",
]
FOMC_SNAPSHOT_2027 = [
    "2027-01-27", "2027-03-17", "2027-04-28", "2027-06-09",
    "2027-07-28", "2027-09-15", "2027-10-27", "2027-12-08",
]
FOMC_PROJECTION_DATES = {
    "2026-03-18", "2026-06-17", "2026-09-16", "2026-12-09",
    "2027-03-17", "2027-06-09", "2027-09-15", "2027-12-08",
}


def _cache_data(*, ttl: int, show_spinner: bool = False):
    """Use Streamlit cache in production and a compatible identity in tests."""
    if st is not None:
        return st.cache_data(ttl=ttl, show_spinner=show_spinner)

    def decorator(func):
        func.clear = lambda: None
        return func

    return decorator


def _snapshot_rows() -> list[dict[str, str]]:
    rows = []
    for d in FOMC_SNAPSHOT + FOMC_SNAPSHOT_2027:
        rows.append(
            {
                "date": d,
                "event": "FOMC · Decisão de juros",
                "details": "Com projeções econômicas" if d in FOMC_PROJECTION_DATES else "Reunião programada",
            }
        )
    return rows


@_cache_data(ttl=21600, show_spinner=False)
def fed_schedule() -> tuple[list[dict[str, str]], str, str]:
    try:
        response = requests.get(FED_URL, timeout=12, headers={"User-Agent": "USD-Macro-Pro/1.0"})
        response.raise_for_status()
        rows = parse_fomc(response.text)
        if not rows:
            raise ValueError("Calendar structure not recognized")
        return rows, "", datetime.now(ZoneInfo("UTC")).isoformat()
    except Exception:
        return (
            _snapshot_rows(),
            f"Fed indisponível nesta consulta. Exibindo cópia verificada em {SNAPSHOT_DATE}, "
            "limitada a 2026–2027; confirme possíveis alterações na fonte oficial.",
            "",
        )


@_cache_data(ttl=900, show_spinner=False)
def eod_events(key: str, start: str, end: str) -> tuple[list[dict[str, Any]], str]:
    if not key:
        return [], "EODHD não configurado: calendário ampliado e consenso indisponíveis."
    try:
        response = requests.get(
            "https://eodhd.com/api/economic-events",
            params={
                "api_token": key,
                "from": start,
                "to": end,
                "country": "US",
                "limit": 1000,
                "offset": 0,
                "fmt": "json",
            },
            timeout=15,
        )
        response.raise_for_status()
        data = response.json()
        if isinstance(data, dict):
            if data.get("error") or data.get("message"):
                raise ValueError("API error")
            data = data.get("data", [])
        if not isinstance(data, list):
            raise ValueError("Unexpected API response")
        warning = "A fonte atingiu 1.000 registros; a lista pode estar incompleta." if len(data) >= 1000 else ""
        return data, warning
    except Exception as exc:
        return [], f"Agenda EODHD indisponível ({type(exc).__name__}). As fontes oficiais continuam separadas."


def render_calendar(releases: dict[str, Any], fetch_dates: Callable[[Any], list[Any]], eod_key: str = "", key: str = "calendar") -> None:
    if st is None:
        raise RuntimeError("Streamlit não está instalado; render_calendar só pode ser usado na interface do app.")

    st.subheader("📅 Agenda econômica · EUA")
    controls = st.columns([1, 1.3])
    days = controls[0].selectbox(
        "Período", [7, 30, 90], index=1,
        format_func=lambda d: f"Próximos {d} dias", key=key + "_days",
    )
    timezone = controls[1].selectbox(
        "Fuso para horários confirmados",
        ["America/Cuiaba", "America/Sao_Paulo", "America/New_York", "UTC"],
        key=key + "_zone",
    )
    today = datetime.now(ZoneInfo(timezone)).date()
    extended = st.checkbox(
        "Incluir outros eventos e consenso da EODHD",
        value=False,
        disabled=not bool(eod_key),
        key=key + "_eod",
    )

    if st.button("Atualizar agenda", key=key + "_refresh"):
        fed_schedule.clear()
        eod_events.clear()
        if hasattr(fetch_dates, "clear"):
            fetch_dates.clear()

    rows: list[dict[str, Any]] = []
    missing: list[str] = []
    for event, release in releases.items():
        try:
            dates = fetch_dates(release) or []
        except Exception:
            dates = []
        if not dates:
            missing.append(event)
        for dt in dates:
            rows.append(
                {
                    "Data": dt,
                    "Evento": event,
                    "Horário": "Não informado",
                    "Prioridade": "Principal",
                    "Fonte": f"FRED · {release}",
                    "Anterior": "—",
                    "Consenso": "—",
                    "Realizado": "—",
                    "Detalhes": "Data de release; horário não fornecido pela FRED",
                }
            )

    fed, fed_warning, fetched = fed_schedule()
    for item in fed:
        rows.append(
            {
                "Data": item["date"],
                "Evento": item["event"],
                "Horário": "Não informado",
                "Prioridade": "Principal",
                "Fonte": "Fed · cópia salva" if fed_warning else "Federal Reserve",
                "Anterior": "—",
                "Consenso": "—",
                "Realizado": "—",
                "Detalhes": item["details"],
            }
        )

    if fed_warning:
        st.warning(fed_warning)
    elif fetched:
        st.caption("Agenda do Fed consultada em " + pd.Timestamp(fetched).tz_convert(timezone).strftime("%d/%m/%Y %H:%M"))

    if missing:
        st.warning("Sem resposta da FRED para: " + ", ".join(missing) + ". Cobertura parcial.")

    if extended:
        extra, error = eod_events(eod_key, today.isoformat(), (today + timedelta(days=days)).isoformat())
        rows.extend(r for raw in extra if (r := eod_row(raw, timezone)) is not None)
        if error:
            st.warning(error)
        elif not extra:
            st.info("A EODHD não retornou eventos nesta janela; isso não confirma ausência de eventos.")

    selected = upcoming(rows, today, days)
    if selected:
        first = selected[0]
        a, b, c = st.columns([2, 1, 1])
        a.metric("Próximo evento listado", first["Evento"])
        b.metric("Data", first["Data"].strftime("%d/%m/%Y"))
        c.metric("Faltam", "Hoje" if first["Em dias"] == 0 else f"{first['Em dias']} dias")

        near = [r for r in selected if r["Em dias"] <= 1 and r.get("Prioridade") == "Principal"]
        if near:
            st.warning(
                "Evento principal hoje ou amanhã: "
                + ", ".join(sorted({r["Evento"] for r in near}))
                + ". Confira o horário na fonte."
            )
        else:
            st.info("Agenda informativa. A ausência de eventos próximos nesta lista não confirma uma janela livre de risco.")

        df = pd.DataFrame(selected)
        df["Data"] = df["Data"].map(lambda dt: dt.strftime("%d/%m/%Y"))
        columns = ["Data", "Em dias", "Evento", "Horário", "Fonte"]
        if extended:
            columns += ["Anterior", "Consenso", "Realizado"]
        st.dataframe(df[columns], hide_index=True, width="stretch")

        with st.expander("🎓 Como interpretar anterior, consenso e atual",expanded=False):
            st.markdown(
                "**Anterior** = última leitura disponível antes do release.  \n"
                "**Consenso** = expectativa agregada antes da divulgação.  \n"
                "**Atual** = número publicado agora.  \n"
                "A surpresa é medida contra o consenso; revisões e componentes também importam."
            )
            event_options=list(dict.fromkeys(str(r.get("Evento","")) for r in selected if str(r.get("Evento","")).strip()))
            if event_options:
                chosen=st.selectbox(
                    "Indicador/evento para entender",
                    event_options,
                    key=key+"_education_event",
                )
                guide=indicator_scenario_guide(chosen)
                if guide.get("recognized"):
                    st.markdown(f"#### {guide['title']}")
                    for scenario in ("ABOVE","INLINE","BELOW"):
                        item=guide["scenarios"][scenario]
                        st.markdown(f"**{item['label']}:** {item['macro_context']}")
                    st.warning("Cuidado: "+str(guide.get("caveat","")))
                    st.caption(guide["interpretation"])
                else:
                    st.info(guide["interpretation"])
            st.caption(
                "O AtlasQuant não usa uma regra universal 'acima = sobe'. "
                "Cada indicador tem lógica própria e a reação depende do contexto."
            )

        with st.expander("Detalhes e cobertura da agenda"):
            st.dataframe(df[["Evento", "Prioridade", "Detalhes"]], hide_index=True, width="stretch")
            st.caption(
                "Prioridade é uma categoria editorial do app, não uma previsão de volatilidade. "
                "Fontes são mantidas separadas para não misturar períodos, unidades ou consensos de eventos semelhantes."
            )
    else:
        st.info(
            "Nenhum evento retornado para este período. Amplie a janela e confira as fontes; "
            "não significa ausência de risco."
        )

    st.caption(
        "Datas sem horário não são convertidas de fuso. Eventos de hoje podem já ter ocorrido. "
        "Discursos, eventos extraordinários e outros países não têm cobertura garantida. "
        "Esta agenda não altera automaticamente os sinais do scanner."
    )
    st.markdown(
        f"[Agenda oficial do Fed]({FED_URL}) · "
        "[Calendário FRED](https://fred.stlouisfed.org/releases/calendar) · "
        f"[Dados e consenso EODHD]({EOD_URL})"
    )
    st.caption(
        "Consulta da tela: "
        + datetime.now(ZoneInfo(timezone)).strftime("%d/%m/%Y %H:%M")
        + f" · {timezone} · cache FRED: 30 min; Fed: 6 h; EODHD: 15 min"
    )
