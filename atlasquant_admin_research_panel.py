"""AtlasQuant Admin Research Intelligence panel.

Administrator-only presentation for operational research evidence. It consumes
already-computed session/backtest data; it does not fetch providers, alter
strategy rules, promote setups, or enable trading.
"""
from __future__ import annotations

from typing import Any, Mapping

import pandas as pd
import streamlit as st

from atlasquant_operational_catalog import catalog_rows, catalog_summary

SCHEMA="ATLASQUANT_ADMIN_RESEARCH_PANEL_V1"


def admin_research_access_allowed(access:Mapping[str,Any]|None)->bool:
    role=str((access or {}).get("role") or "").strip().upper()
    mode=str((access or {}).get("mode") or "").strip().upper()
    # OPEN exists only when the optional authentication gate is disabled.
    # It is useful for private/local development. Production forces auth.
    return role=="ADMIN" or (role=="OPEN" and mode=="OPEN")


def build_admin_research_snapshot(
    *,
    access:Mapping[str,Any]|None,
    last_backtest:Mapping[str,Any]|None,
)->dict[str,Any]:
    allowed=admin_research_access_allowed(access)
    catalog=catalog_summary()
    backtest=dict(last_backtest or {})
    passport=dict(backtest.get("passport",{}) or {})
    diagnoses=list(backtest.get("diagnoses",[]) or [])
    executed=int(backtest.get("executed_trades",0) or 0)
    rich=int(backtest.get("rich_context_trades",0) or 0)
    flags=list(passport.get("evidence_flags",[]) or [])
    return {
        "schema":SCHEMA,
        "allowed":allowed,
        "catalog_models":int(catalog.get("models",0) or 0),
        "catalog_objective_replay_ready":int(catalog.get("objective_replay_ready",0) or 0),
        "last_strategy":str(backtest.get("strategy") or ""),
        "executed_trades":executed,
        "rich_context_trades":rich,
        "context_gap_trades":max(0,executed-rich),
        "passport_state":passport.get("state"),
        "passport_flags":flags,
        "diagnosis_count":len(diagnoses),
        "automatic_promotion":False,
        "automatic_strategy_change":False,
        "real_orders_enabled":False,
    }


def render_admin_research_panel(
    access:Mapping[str,Any]|None,
    *,
    last_backtest:Mapping[str,Any]|None=None,
)->dict[str,Any]:
    backtest=(
        dict(last_backtest)
        if isinstance(last_backtest,Mapping)
        else dict(st.session_state.get("atlasquant_last_backtest_intelligence",{}) or {})
    )
    snapshot=build_admin_research_snapshot(access=access,last_backtest=backtest)

    st.markdown("### 🧠 Admin · Inteligência dos Operacionais")
    st.caption(
        "Matriz Mestre, Passaporte e diagnóstico de gain/loss. "
        "Esta área organiza pesquisa; não promove setup nem envia ordens."
    )

    if not snapshot["allowed"]:
        st.warning("Área reservada ao Administrador.")
        st.caption("Usuários Iniciante/Avançado podem usar suas áreas, mas não recebem controles administrativos.")
        return snapshot

    cat=catalog_summary()
    c1,c2,c3,c4=st.columns(4)
    c1.metric("Modelos catalogados",cat["models"])
    c2.metric("Replays objetivos",cat["objective_replay_ready"])
    c3.metric("Último backtest",snapshot["executed_trades"])
    c4.metric("Contexto completo",snapshot["rich_context_trades"])

    with st.expander("📚 Matriz Mestre ICT / SMC / Price Action",expanded=False):
        frame=pd.DataFrame(catalog_rows())
        display=[
            "model_id","label","family","status","objective_rules_ready","notes"
        ]
        st.dataframe(frame.reindex(columns=display),width="stretch",hide_index=True)
        st.caption(
            "CODED significa que existem regras objetivas/replay. "
            "Não significa VALIDATED, aprovado para Iniciante ou lucrativo."
        )

    if not backtest:
        st.info(
            "Nenhum backtest desta sessão foi enviado ao Copiloto Admin ainda. "
            "Rode um operacional na aba Backtest para alimentar este painel."
        )
        return snapshot

    st.markdown("#### Último Passaporte recebido")
    passport=dict(backtest.get("passport",{}) or {})
    observed=dict(passport.get("observed_metrics",{}) or {})
    coverage=dict(passport.get("coverage",{}) or {})
    p1,p2,p3,p4=st.columns(4)
    p1.metric("Operacional",str(backtest.get("strategy") or "—"))
    p2.metric("Trades",int(observed.get("trades",0) or 0))
    p3.metric("Expectativa",f"{float(observed.get('expectancy_r',0.0) or 0.0):+.2f}R")
    p4.metric("Regimes",int(coverage.get("regimes",0) or 0))

    flags=list(passport.get("evidence_flags",[]) or [])
    if flags:
        st.warning("Ainda falta validar: "+" · ".join(str(x) for x in flags))
    if passport.get("eligible_for_human_review"):
        st.success(
            "O contrato atual considera a evidência suficiente apenas para REVISÃO HUMANA. "
            "Não existe promoção automática."
        )
    else:
        st.info("O operacional ainda não atingiu o contrato de evidência para revisão humana.")

    table=pd.DataFrame(backtest.get("diagnosis_table",[]) or [])
    if not table.empty:
        st.markdown("#### Diagnóstico das operações")
        st.dataframe(table,width="stretch",hide_index=True)
        losses=table[table["outcome"].astype(str).str.upper().eq("LOSS")] if "outcome" in table else pd.DataFrame()
        gains=table[table["outcome"].astype(str).str.upper().eq("GAIN")] if "outcome" in table else pd.DataFrame()
        d1,d2,d3=st.columns(3)
        d1.metric("Gain diagnosticados",len(gains))
        d2.metric("Loss diagnosticados",len(losses))
        d3.metric("Sem contexto completo",snapshot["context_gap_trades"])

    st.warning(
        "Regra do Admin: resultado recente não muda parâmetros sozinho. "
        "Mudanças exigem amostra, estabilidade, walk-forward/paper e revisão humana."
    )
    return snapshot


__all__=[
    "SCHEMA",
    "admin_research_access_allowed",
    "build_admin_research_snapshot",
    "render_admin_research_panel",
]
