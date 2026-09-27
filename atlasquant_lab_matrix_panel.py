"""Streamlit presentation for the fail-closed Laboratório matrix."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping, Sequence

import pandas as pd
import streamlit as st

from atlasquant_lab_matrix import (
    LAB_TIMEFRAMES,
    TRADING_STYLES,
    TRADING_STYLE_LABELS,
    evidence_rows_from_research_records,
    lab_matrix,
)
from atlasquant_research_evidence_capture import SESSION_KEY
from atlasquant_setup_validation import SETUP_CATALOG


def _display(value: Any, suffix: str = "") -> str:
    if value is None or value == "":
        return "N/D"
    if isinstance(value, float):
        return f"{value:.2f}{suffix}"
    return f"{value}{suffix}"


def evidence_period_rows(
    evidence_rows: Sequence[Mapping[str, Any]] | None,
    frequency: str,
) -> list[dict[str, Any]]:
    """Return recorded rows labelled by month/year; never derive missing metrics."""
    mode = str(frequency or "").upper()
    if mode not in {"MONTH", "YEAR"}:
        return []
    out = []
    for raw in list(evidence_rows or []):
        row = dict(raw)
        timestamp = str(row.get("executed_at") or "").strip()
        try:
            moment = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        except (TypeError, ValueError):
            continue
        period = moment.strftime("%Y-%m") if mode == "MONTH" else moment.strftime("%Y")
        out.append({
            "Período": period,
            "Ativo": row.get("asset") or "N/D",
            "Setup": row.get("setup_id") or "N/D",
            "Timeframe": row.get("timeframe") or "N/D",
            "Trades": row.get("samples"),
            "Win rate %": row.get("win_rate_pct"),
            "Expectancy R": row.get("expectancy_r"),
            "Profit factor": row.get("profit_factor"),
            "Drawdown R": row.get("max_drawdown_r"),
            "Resultado líquido": row.get("net_result"),
            "Fonte": row.get("source") or "N/D",
            "Versão da regra": row.get("rules_version") or "N/D",
        })
    return sorted(out, key=lambda item: (item["Período"], str(item["Setup"]), str(item["Timeframe"])))


def render_lab_matrix_panel(
    research_records: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    records = (
        list(research_records)
        if research_records is not None
        else list(st.session_state.get(SESSION_KEY, []) or [])
    )
    evidence_rows = evidence_rows_from_research_records(records)
    matrix = lab_matrix(evidence_rows)

    st.markdown("### 🧬 Laboratório · Matriz de Pesquisa")
    st.caption(
        "M15, M30, H1, H4, D1 e Semanal separados por classe e setup. "
        "A matriz lê somente evidências registradas nesta sessão/runtime; célula vazia continua SEM EVIDÊNCIA."
    )
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Combinações", len(matrix["cells"]))
    c2.metric("Com evidência completa", matrix["counts"]["EVIDENCIA_REGISTRADA"])
    c3.metric("Evidência parcial", matrix["counts"]["EVIDENCIA_INCOMPLETA"])
    c4.metric("Bloqueadas", matrix["counts"]["BLOQUEADO"])
    st.info(
        "PPR permanece BLOQUEADO por falta de definição objetiva. "
        "Nenhum resultado promove setup, altera Gate ou habilita ordem real."
    )

    style = st.selectbox(
        "Classe operacional",
        list(TRADING_STYLES),
        format_func=lambda value: TRADING_STYLE_LABELS[value],
        key="atlasquant_lab_matrix_style",
    )
    timeframe_options = [
        tf for tf in LAB_TIMEFRAMES
        if any(c["timeframe"] == tf and c["trading_style"] == style for c in matrix["cells"])
    ]
    timeframe = st.selectbox(
        "Timeframe",
        timeframe_options,
        format_func=lambda value: "Semanal" if value == "W1" else value,
        key="atlasquant_lab_matrix_timeframe",
    )
    filtered = [
        cell for cell in matrix["cells"]
        if cell["trading_style"] == style and cell["timeframe"] == timeframe
    ]
    table = pd.DataFrame([{
        "Setup": cell["setup_name"],
        "Família": cell["family"],
        "Estado": cell["state"],
        "Ativo": cell["asset"] or "N/D",
        "Trades": _display(cell["metrics"]["samples"]),
        "Win rate": _display(cell["metrics"]["win_rate_pct"], "%"),
        "Expectancy": _display(cell["metrics"]["expectancy_r"], "R"),
        "Profit factor": _display(cell["metrics"]["profit_factor"]),
        "Drawdown": _display(cell["metrics"]["max_drawdown_r"], "R"),
        "Resultado líquido": _display(cell["metrics"]["net_result"]),
        "Período": (
            f"{cell['period_start'] or 'N/D'} → {cell['period_end'] or 'N/D'}"
        ),
        "Fonte": cell["source"] or "N/D",
        "Versão": cell["rules_version"] or "N/D",
        "Motivo/bloqueador": cell["reason"],
    } for cell in filtered])
    st.dataframe(table, width="stretch", hide_index=True)

    with st.expander("Regras, evidência e status de pesquisa"):
        st.dataframe(pd.DataFrame([{
            "Setup": item["name"],
            "Família": item["family"],
            "Status": item["status"],
            "Regras": "PENDENTES" if item.get("definition_pending") else "CATALOGADAS",
            "Bloqueador/nota": item["notes"],
        } for item in SETUP_CATALOG]), width="stretch", hide_index=True)
        st.caption(
            "As regras devem ser congeladas antes da avaliação. Resultado observado não reescreve a regra."
        )

    monthly = evidence_period_rows(evidence_rows, "MONTH")
    yearly = evidence_period_rows(evidence_rows, "YEAR")
    with st.expander("Comparação mês a mês e ano a ano"):
        if len({row["Período"] for row in monthly}) >= 2:
            st.markdown("#### Mês a mês")
            st.dataframe(pd.DataFrame(monthly), width="stretch", hide_index=True)
        else:
            st.info("Mês a mês indisponível: são necessários registros em pelo menos dois meses.")
        if len({row["Período"] for row in yearly}) >= 2:
            st.markdown("#### Ano a ano")
            st.dataframe(pd.DataFrame(yearly), width="stretch", hide_index=True)
        else:
            st.info("Ano a ano indisponível: são necessários registros em pelo menos dois anos.")

    return {
        "schema": matrix["schema"],
        "records": len(records),
        "adapted_evidence": len(evidence_rows),
        "counts": dict(matrix["counts"]),
        "real_orders_enabled": False,
        "automatic_promotion": False,
    }


__all__ = ["evidence_period_rows", "render_lab_matrix_panel"]
