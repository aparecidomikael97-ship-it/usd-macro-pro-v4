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
from atlasquant_weekly_profile import analyze_weekly_extremes
from atlasquant_behavior_shift import BehaviorStats, detect_behavior_shift

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


def normalize_weekly_research_csv(frame:pd.DataFrame|None)->pd.DataFrame:
    if not isinstance(frame,pd.DataFrame) or frame.empty:
        return pd.DataFrame(columns=["datetime","high","low"])
    out=frame.copy()
    aliases={
        "datetime":("datetime","date","data","time","timestamp"),
        "high":("high","max","maxima","máxima"),
        "low":("low","min","minima","mínima"),
    }
    by_norm={str(c).strip().casefold():c for c in out.columns}
    rename={}
    for canonical,names in aliases.items():
        if canonical in out.columns:
            continue
        for name in names:
            actual=by_norm.get(str(name).strip().casefold())
            if actual is not None:
                rename[actual]=canonical
                break
    out=out.rename(columns=rename)
    if not {"datetime","high","low"}.issubset(out.columns):
        return pd.DataFrame(columns=["datetime","high","low"])
    return out[["datetime","high","low"]].copy()


_BEHAVIOR_FIELDS=(
    "sample_size","london_expansion_pct","new_york_expansion_pct",
    "sweep_followthrough_pct","reversal_after_sweep_pct",
    "level_reaction_pct","average_range",
)

def behavior_stats_from_frame(frame:pd.DataFrame|None)->tuple[BehaviorStats|None,BehaviorStats|None]:
    if not isinstance(frame,pd.DataFrame) or frame.empty or "window" not in frame.columns:
        return None,None
    normalized=frame.copy()
    normalized["window"]=normalized["window"].astype(str).str.strip().str.casefold()
    def build(name:str)->BehaviorStats|None:
        rows=normalized[normalized["window"].eq(name)]
        if rows.empty:
            return None
        row=rows.iloc[-1]
        try:
            return BehaviorStats(
                sample_size=int(row["sample_size"]),
                london_expansion_pct=float(row["london_expansion_pct"]),
                new_york_expansion_pct=float(row["new_york_expansion_pct"]),
                sweep_followthrough_pct=float(row["sweep_followthrough_pct"]),
                reversal_after_sweep_pct=float(row["reversal_after_sweep_pct"]),
                level_reaction_pct=float(row["level_reaction_pct"]),
                average_range=float(row["average_range"]),
            )
        except Exception:
            return None
    return build("baseline"),build("recent")


def behavior_template_csv()->str:
    header="window,"+",".join(_BEHAVIOR_FIELDS)
    baseline="baseline,100,50,45,60,30,55,100"
    recent="recent,30,50,45,60,30,55,100"
    return header+"\n"+baseline+"\n"+recent+"\n"


def render_admin_research_panel(
    access:Mapping[str,Any]|None,
    *,
    last_backtest:Mapping[str,Any]|None=None,
    last_suite:Mapping[str,Any]|None=None,
)->dict[str,Any]:
    backtest=(
        dict(last_backtest)
        if isinstance(last_backtest,Mapping)
        else dict(st.session_state.get("atlasquant_last_backtest_intelligence",{}) or {})
    )
    suite=(
        dict(last_suite)
        if isinstance(last_suite,Mapping)
        else dict(st.session_state.get("atlasquant_last_strategy_suite_intelligence",{}) or {})
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

    with st.expander("📅 Perfil Semanal · pesquisa estatística",expanded=False):
        st.caption(
            "Teste a hipótese de high/low semanal por dia usando dados históricos. "
            "O laboratório mede a amostra; não assume terça/quarta como regra institucional."
        )
        weekly_file=st.file_uploader(
            "OHLC diário para Perfil Semanal (CSV)",
            type=["csv"],
            key="atlasquant_admin_weekly_profile_csv",
        )
        if weekly_file is not None:
            try:
                weekly_raw=pd.read_csv(weekly_file)
                weekly_frame=normalize_weekly_research_csv(weekly_raw)
                weekly=analyze_weekly_extremes(weekly_frame)
            except Exception as exc:
                st.error(f"Perfil semanal inválido: {type(exc).__name__}: {exc}")
            else:
                w1,w2,w3=st.columns(3)
                w1.metric("Semanas válidas",weekly.get("weeks",0))
                tw_high=weekly.get("tuesday_wednesday_high_pct")
                tw_low=weekly.get("tuesday_wednesday_low_pct")
                w2.metric("High terça/quarta","—" if tw_high is None else f"{float(tw_high):.1f}%")
                w3.metric("Low terça/quarta","—" if tw_low is None else f"{float(tw_low):.1f}%")
                rows=pd.DataFrame(weekly.get("rows",[]) or [])
                if not rows.empty:
                    st.dataframe(rows,width="stretch",hide_index=True)
                st.caption(weekly.get("interpretation",""))

    with st.expander("🔄 Detector de Mudança de Comportamento",expanded=False):
        st.caption(
            "Compara uma janela baseline com uma janela recente de estatísticas observáveis. "
            "Não tenta adivinhar intenção oculta das instituições."
        )
        st.download_button(
            "⬇️ Modelo CSV de comportamento",
            data=behavior_template_csv(),
            file_name="atlasquant_behavior_shift_template.csv",
            mime="text/csv",
            key="atlasquant_admin_behavior_template",
        )
        behavior_file=st.file_uploader(
            "Baseline + recente (CSV)",
            type=["csv"],
            key="atlasquant_admin_behavior_csv",
        )
        if behavior_file is not None:
            try:
                behavior_frame=pd.read_csv(behavior_file)
                baseline,recent=behavior_stats_from_frame(behavior_frame)
                if baseline is None or recent is None:
                    raise ValueError("CSV precisa ter uma linha baseline e uma recent com todas as métricas")
                shift=detect_behavior_shift(baseline,recent)
            except Exception as exc:
                st.error(f"Detector de comportamento inválido: {type(exc).__name__}: {exc}")
            else:
                s1,s2=st.columns(2)
                s1.metric("Estado",shift.get("state","—"))
                s2.metric("Mudanças relevantes",shift.get("change_count",0))
                changes=pd.DataFrame(shift.get("changes",[]) or [])
                if not changes.empty:
                    st.dataframe(changes,width="stretch",hide_index=True)
                st.caption(shift.get("interpretation",""))

    if suite:
        passport_rows=pd.DataFrame(suite.get("passport_rows",[]) or [])
        if not passport_rows.empty:
            st.markdown("#### Comparador · Passaportes dos operacionais")
            st.dataframe(passport_rows,width="stretch",hide_index=True)
            st.caption(
                "A comparação descreve evidência observada. O Admin não transforma ranking "
                "histórico em promoção automática."
            )

    if not backtest:
        if not suite:
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

    causes=pd.DataFrame(backtest.get("cause_summary",[]) or [])
    if not causes.empty:
        st.markdown("#### Padrões recorrentes de gain/loss")
        st.dataframe(causes,width="stretch",hide_index=True)
        st.caption(
            "Associações recorrentes ajudam a investigar o operacional, mas não provam causalidade."
        )

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
    "normalize_weekly_research_csv",
    "behavior_stats_from_frame",
    "behavior_template_csv",
    "render_admin_research_panel",
]
