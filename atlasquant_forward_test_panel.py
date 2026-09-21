"""Backtest-tab presentation of prospective Model Paper evidence.

Consumes an already persisted runtime summary. It never fetches market data,
changes a strategy, promotes a setup, or enables an order.
"""
from __future__ import annotations

from typing import Any, Mapping
import pandas as pd
import streamlit as st

TIMEFRAME_ORDER=("M15","M30","H1","H4","D1","W1")


def _mapping(value:Any)->dict[str,Any]:
    return dict(value) if isinstance(value,Mapping) else {}


def forward_timeframe_rows(summary:Mapping[str,Any]|None)->list[dict[str,Any]]:
    src=_mapping(summary)
    by_tf=_mapping(src.get("by_timeframe"))
    ready=_mapping(_mapping(src.get("timeframe_execution_readiness")).get("by_timeframe"))
    rows=[]
    for tf in TIMEFRAME_ORDER:
        obs=_mapping(by_tf.get(tf))
        readiness=_mapping(ready.get(tf))
        hard=_mapping(obs.get("hard_block_reasons"))
        soft=_mapping(obs.get("soft_block_reasons"))
        tf_blocks=_mapping(obs.get("timeframe_block_reasons"))
        reasons={**hard}
        for key,val in soft.items():
            reasons[f"SOFT · {key}"]=val
        for key,val in tf_blocks.items():
            if key and key!="SOURCE_EQUALS_EXECUTION":
                reasons[f"TF · {key}"]=val
        top=" · ".join(
            f"{name} ({count})"
            for name,count in sorted(reasons.items(),key=lambda kv:(-int(kv[1]),str(kv[0])))[:3]
        )
        rows.append({
            "Timeframe":tf,
            "Candles exatos":int(readiness.get("pairs_with_exact_data",0) or 0),
            "Pares Paper prontos":int(readiness.get("pairs_paper_ready",0) or 0),
            "Candidatos":int(obs.get("candidates",0) or 0),
            "Bloq. contexto":int(obs.get("blocked_context",0) or 0),
            "Bloq. dados":int(obs.get("blocked_data",0) or 0),
            "Bloq. timeframe":int(obs.get("blocked_timeframe",0) or 0),
            "Pendentes":int(obs.get("pending",0) or 0),
            "Abertos":int(obs.get("open",0) or 0),
            "Fechados":int(obs.get("closed",0) or 0),
            "Wins":int(obs.get("wins",0) or 0),
            "Losses":int(obs.get("losses",0) or 0),
            "Net R":float(obs.get("net_r",0.0) or 0.0),
            "Principais bloqueios":top or "—",
        })
    return rows


def forward_setup_rows(summary:Mapping[str,Any]|None)->list[dict[str,Any]]:
    by_setup=_mapping(_mapping(summary).get("by_setup"))
    rows=[]
    for setup_id,raw in sorted(by_setup.items()):
        obs=_mapping(raw)
        rows.append({
            "Operacional":str(setup_id),
            "Candidatos":int(obs.get("candidates",0) or 0),
            "Bloq. contexto":int(obs.get("blocked_context",0) or 0),
            "Bloq. timeframe":int(obs.get("blocked_timeframe",0) or 0),
            "Pendentes":int(obs.get("pending",0) or 0),
            "Abertos":int(obs.get("open",0) or 0),
            "Fechados":int(obs.get("closed",0) or 0),
            "Wins":int(obs.get("wins",0) or 0),
            "Losses":int(obs.get("losses",0) or 0),
            "Win Rate %":float(obs.get("win_rate_pct",0.0) or 0.0),
            "Net R":float(obs.get("net_r",0.0) or 0.0),
        })
    return rows


def render_forward_test_panel(
    summary:Mapping[str,Any]|None,
    *,
    source_label:str="",
)->dict[str,Any]:
    src=_mapping(summary)
    st.markdown("### 📡 Paper / Forward Test ao vivo")
    st.caption(
        "Resultados prospectivos do mercado real, separados do Backtest histórico. "
        "Só contam operações que passaram leitura, direção, filtros e gatilho; "
        "timeframe inferior nunca substitui o timeframe de execução."
    )
    if not src:
        st.info("Resumo do Paper/Forward ainda não disponível neste carregamento.")
        return {"available":False,"real_orders_enabled":False}

    c1,c2,c3,c4,c5=st.columns(5)
    c1.metric("Candidatos",int(src.get("candidates_total",0) or 0))
    c2.metric("Bloqueados",int(src.get("blocked_context",0) or 0)+int(src.get("blocked_data",0) or 0)+int(src.get("blocked_timeframe",0) or 0))
    c3.metric("Abertos",int(src.get("open_positions",0) or 0))
    c4.metric("Fechados",int(src.get("closed_trades",0) or 0))
    c5.metric("Net R",f"{float(src.get('net_r_after_friction',src.get('net_r',0.0)) or 0.0):+.2f}R")

    tf_rows=forward_timeframe_rows(src)
    st.markdown("#### Por timeframe")
    st.dataframe(pd.DataFrame(tf_rows),width="stretch",hide_index=True)

    setup_rows=forward_setup_rows(src)
    if setup_rows:
        st.markdown("#### Por operacional")
        st.dataframe(pd.DataFrame(setup_rows),width="stretch",hide_index=True)

    total_closed=int(src.get("closed_trades",0) or 0)
    if total_closed<=0:
        st.warning(
            "Ainda não há trades fechados no Model Paper. Isso não é falha: os candidatos "
            "continuam sendo recusados quando o alinhamento obrigatório não está completo."
        )
    if source_label:
        st.caption(f"Fonte do runtime: {source_label}")

    return {
        "available":True,
        "closed_trades":total_closed,
        "timeframes":tf_rows,
        "setups":setup_rows,
        "automatic_execution":False,
        "real_orders_enabled":False,
    }


__all__=["TIMEFRAME_ORDER","forward_timeframe_rows","forward_setup_rows","render_forward_test_panel"]
