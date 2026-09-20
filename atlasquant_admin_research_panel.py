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
from atlasquant_passport_evidence import fuse_operational_evidence
from atlasquant_passport_drift import latest_passport_drift, passport_drift_rows
from atlasquant_setup_journal import setup_forward_summary
from atlasquant_paper_setup_bridge import bridge_paper_audit, load_paper_audit_runtime
from atlasquant_shadow_mode import summarize_shadow
from atlasquant_research_evidence_capture import (
    SESSION_KEY as RESEARCH_SESSION_KEY,
    STATUS_KEY as RESEARCH_STATUS_KEY,
    ensure_research_evidence_hydrated,
    latest_research_evidence,
    persist_session_research_evidence,
    research_evidence_config,
)

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


def _journal_records_from_frame(frame:pd.DataFrame|None)->list[dict[str,Any]]:
    if not isinstance(frame,pd.DataFrame) or frame.empty:
        return []
    rows=[]
    for raw in frame.to_dict("records"):
        row=dict(raw)
        for field in ("hard_blocks","soft_blocks"):
            value=row.get(field)
            if isinstance(value,str):
                row[field]=[
                    part.strip()
                    for part in value.replace(";", "|").split("|")
                    if part.strip()
                ]
        rows.append(row)
    return rows


def _strategy_key(value:object)->str:
    return (
        str(value or "")
        .strip()
        .casefold()
        .replace(" / ","_")
        .replace("/","_")
        .replace(" ","_")
        .replace("+","_")
        .replace("–","_")
        .replace("-","_")
    )


def _match_forward_summary(
    strategy:object,
    summaries:Mapping[str,Mapping[str,Any]]|None,
)->tuple[str|None,dict[str,Any]]:
    data=dict(summaries or {})
    if not data:
        return None,{}
    target=_strategy_key(strategy)
    for setup_id,summary in data.items():
        if _strategy_key(setup_id)==target:
            return str(setup_id),dict(summary or {})
    aliases={
        "fvg":{"fvg"},
        "ote_62_79%":{"ote","ote_62_79","ote_62_79%"},
        "crt":{"crt"},
        "amd_power_of_three":{"amd","amd_po3","power_of_three","po3"},
        "bos_choch_order_block":{"bos_choch_ob","bos_choch_order_block","ob_choch"},
    }
    targets=aliases.get(target,{target})
    for setup_id,summary in data.items():
        if _strategy_key(setup_id) in targets:
            return str(setup_id),dict(summary or {})
    return None,{}


def _resolve_forward_evidence(
    strategy:object,
    runtime_summaries:Mapping[str,Mapping[str,Any]]|None,
    manual_summaries:Mapping[str,Mapping[str,Any]]|None=None,
    *,
    manual_selected:object|None=None,
)->dict[str,Any]:
    runtime=dict(runtime_summaries or {})
    manual=dict(manual_summaries or {})
    source="MANUAL_JOURNAL" if manual else ("RUNTIME_EXPLICIT" if runtime else "NONE")
    summaries=manual if manual else runtime
    matched,summary=_match_forward_summary(strategy,summaries)
    needs_manual_selection=bool(source=="MANUAL_JOURNAL" and summaries and matched is None)
    if needs_manual_selection and manual_selected is not None:
        selected=str(manual_selected)
        if selected in summaries:
            matched=selected
            summary=dict(summaries[selected] or {})
            needs_manual_selection=False
    return {
        "source":source,
        "summaries":summaries,
        "matched_setup":matched,
        "summary":dict(summary or {}),
        "needs_manual_selection":needs_manual_selection,
        "available_setups":sorted(summaries),
        "runtime_cross_setup_reuse":False,
    }


def _research_history_rows(records:list[dict[str,Any]])->list[dict[str,Any]]:
    rows=[]
    for raw in records:
        row=dict(raw)
        evidence=dict(row.get("evidence",{}) or {})
        ladder=dict(evidence.get("evidence_ladder",{}) or {})
        passport=dict(row.get("passport",{}) or {})
        rows.append({
            "strategy":row.get("strategy"),
            "captured_at":row.get("captured_at"),
            "source":row.get("source"),
            "pair":row.get("pair"),
            "passport_state":passport.get("state"),
            "evidence_state":ladder.get("state"),
            "evidence_coverage_pct":ladder.get("evidence_coverage_pct"),
            "evidence_sufficient_pct":ladder.get("evidence_sufficient_pct"),
            "record_id":str(row.get("record_id") or "")[:12],
        })
    return rows


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

    research_records,research_status=ensure_research_evidence_hydrated()

    paper_audit_key="atlasquant_admin_runtime_paper_setup_audit"
    paper_audit_status_key="atlasquant_admin_runtime_paper_setup_audit_status"
    paper_audit_hydrated_key="atlasquant_admin_runtime_paper_setup_audit_hydrated"
    if not bool(st.session_state.get(paper_audit_hydrated_key,False)):
        cfg=research_evidence_config()
        runtime_audit,runtime_status=load_paper_audit_runtime(
            repo=cfg.get("repo",""),
            branch=cfg.get("branch",""),
            token=cfg.get("token",""),
        )
        st.session_state[paper_audit_key]=runtime_audit
        st.session_state[paper_audit_status_key]=runtime_status
        st.session_state[paper_audit_hydrated_key]=True

    if st.button(
        "🔄 Atualizar Paper Audit Runtime",
        key="atlasquant_admin_refresh_paper_setup_audit",
    ):
        cfg=research_evidence_config()
        runtime_audit,runtime_status=load_paper_audit_runtime(
            repo=cfg.get("repo",""),
            branch=cfg.get("branch",""),
            token=cfg.get("token",""),
        )
        st.session_state[paper_audit_key]=runtime_audit
        st.session_state[paper_audit_status_key]=runtime_status
        st.session_state[paper_audit_hydrated_key]=True

    runtime_audit=st.session_state.get(paper_audit_key,pd.DataFrame())
    if not isinstance(runtime_audit,pd.DataFrame):
        runtime_audit=pd.DataFrame()
    runtime_status=dict(st.session_state.get(paper_audit_status_key,{}) or {})
    runtime_bridge=bridge_paper_audit(runtime_audit)

    cat=catalog_summary()
    c1,c2,c3,c4=st.columns(4)
    c1.metric("Modelos catalogados",cat["models"])
    c2.metric("Replays objetivos",cat["objective_replay_ready"])
    c3.metric("Último backtest",snapshot["executed_trades"])
    c4.metric("Contexto completo",snapshot["rich_context_trades"])

    st.caption(
        f"Histórico de pesquisa: {len(research_records)} registro(s) · "
        f"fonte {str(research_status.get('source','session'))} · "
        f"branch {str(research_status.get('branch','—'))}"
    )

    if runtime_status.get("reason")=="LOADED":
        st.caption(
            f"Paper Audit Runtime: {int(runtime_bridge.get('eligible_records',0) or 0)} "
            f"trade(s) com setup explícito elegível(is) de "
            f"{int(runtime_bridge.get('closed_rows',0) or 0)} fechado(s). "
            "Nenhum setup é inferido."
        )

    with st.expander("🗃️ Histórico persistente de evidências",expanded=False):
        history_frame=pd.DataFrame(_research_history_rows(research_records))
        if history_frame.empty:
            st.info("Ainda não há evidência operacional registrada nesta sessão/histórico.")
        else:
            st.dataframe(history_frame.sort_values("captured_at",ascending=False),width="stretch",hide_index=True)
            latest=latest_research_evidence()
            latest_rows=[]
            for strategy,record in sorted(latest.items()):
                evidence=dict(record.get("evidence",{}) or {})
                ladder=dict(evidence.get("evidence_ladder",{}) or {})
                latest_rows.append({
                    "strategy":strategy,
                    "captured_at":record.get("captured_at"),
                    "source":record.get("source"),
                    "evidence_state":ladder.get("state"),
                    "evidence_coverage_pct":ladder.get("evidence_coverage_pct"),
                    "evidence_sufficient_pct":ladder.get("evidence_sufficient_pct"),
                })
            if latest_rows:
                st.markdown("##### Último registro por operacional")
                st.dataframe(pd.DataFrame(latest_rows),width="stretch",hide_index=True)

        if st.button(
            "💾 Persistir evidências da sessão no Runtime",
            key="atlasquant_admin_persist_research_evidence",
            disabled=not bool(research_records),
        ):
            status=persist_session_research_evidence()
            if status.get("ok"):
                if status.get("reason")=="ALREADY_PRESENT":
                    st.info("As evidências desta sessão já estão persistidas.")
                elif status.get("reason")=="NO_RECORDS":
                    st.info("Nenhum registro para persistir.")
                else:
                    st.success(
                        f"Evidência persistida na branch runtime. "
                        f"Novos registros: {int(status.get('added',0) or 0)}."
                    )
            else:
                st.warning(
                    "Persistência externa não disponível agora; os registros permanecem na sessão. "
                    f"Motivo: {status.get('reason','N/D')}."
                )

    drift_rows=passport_drift_rows(research_records)
    if drift_rows:
        st.markdown("#### 📉 Mudança do Passaporte no tempo")
        st.caption(
            "Compara os dois últimos registros de cada operacional. Alerta de mudança pede revisão; "
            "não altera setup, Gate ou peso automaticamente."
        )
        drift_frame=pd.DataFrame(drift_rows)
        st.dataframe(drift_frame,width="stretch",hide_index=True)
        drifts=latest_passport_drift(research_records)
        flagged=[x for x in drifts if x.get("review_required")]
        if flagged:
            st.warning(
                f"{len(flagged)} operacional(is) com mudança relevante para revisão humana. "
                "Isso é diagnóstico de pesquisa, não previsão."
            )

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

    st.markdown("#### 🧪 Cruzar Backtest × Paper/Forward × Shadow")
    st.caption(
        "O Admin pode anexar o Diário Paper/Forward para completar a escada de evidências. "
        "O cruzamento não promove o operacional sozinho."
    )
    runtime_forward_summaries=dict(runtime_bridge.get("summary_by_setup",{}) or {})

    if runtime_status.get("reason")=="LOADED":
        if runtime_bridge.get("explicit_rows",0) and not runtime_bridge.get("eligible_records",0):
            st.warning(
                "O Paper Audit possui tags explícitas, mas ainda faltam campos válidos "
                "(sessão/regime/preços/qualidade) para virar evidência Forward."
            )
        elif not runtime_bridge.get("explicit_rows",0):
            st.info(
                "O Paper Audit atual ainda não tem setup_id explícito. "
                "O AtlasQuant não vai adivinhar o operacional pelo FVG/ICT/resultado."
            )

    journal_file=st.file_uploader(
        "Diário Paper/Forward manual (CSV) — opcional",
        type=["csv"],
        key="atlasquant_admin_forward_journal_csv",
    )
    manual_summaries={}
    if journal_file is not None:
        try:
            journal_frame=pd.read_csv(journal_file)
            manual_summaries=setup_forward_summary(_journal_records_from_frame(journal_frame))
        except Exception as exc:
            st.error(f"Diário Paper/Forward inválido: {type(exc).__name__}: {exc}")
            manual_summaries={}

    resolved_forward=_resolve_forward_evidence(
        backtest.get("strategy"),
        runtime_forward_summaries,
        manual_summaries,
    )
    if resolved_forward["needs_manual_selection"]:
        selected=st.selectbox(
            "Relacionar o Passaporte ao setup do diário manual",
            resolved_forward["available_setups"],
            key="atlasquant_admin_forward_setup_link",
        )
        resolved_forward=_resolve_forward_evidence(
            backtest.get("strategy"),
            runtime_forward_summaries,
            manual_summaries,
            manual_selected=selected,
        )

    matched_setup=resolved_forward["matched_setup"]
    forward_summary=dict(resolved_forward["summary"] or {})
    forward_source=resolved_forward["source"]
    if matched_setup is None and forward_source=="RUNTIME_EXPLICIT" and runtime_forward_summaries:
        st.info(
            "Existe evidência Paper explícita para outros setups, mas não para este operacional. "
            "Ela não será reaproveitada em outro setup."
        )
    if matched_setup is not None:
        st.caption(
            f"Paper/Forward relacionado: {matched_setup} · fonte {forward_source}"
        )

    shadow_samples=list(st.session_state.get("atlasquant_shadow_samples",[]) or [])
    shadow_summary=summarize_shadow(shadow_samples) if shadow_samples else {}
    diagnostics=dict(backtest.get("research_diagnostics",{}) or {})
    ladder=fuse_operational_evidence(
        passport,
        paper_summary=forward_summary,
        temporal_status=diagnostics.get("temporal_status"),
        walk_forward_status=diagnostics.get("walk_forward_status"),
        friction_status=diagnostics.get("friction_status"),
        parameter_status=diagnostics.get("parameter_status"),
        positive_fold_pct=diagnostics.get("positive_fold_pct"),
        oos_positive_pct=diagnostics.get("oos_positive_pct"),
        friction_positive_pct=diagnostics.get("friction_positive_pct"),
        parameter_positive_pct=diagnostics.get("parameter_positive_pct"),
        shadow_summary=shadow_summary,
    )
    st.session_state["atlasquant_last_fused_passport_evidence"]=ladder
    l1,l2,l3,l4=st.columns(4)
    l1.metric("Estado da evidência",str(ladder.get("state","—")))
    l2.metric("Cobertura",f"{float(ladder.get('evidence_coverage_pct',0.0) or 0.0):.0f}%")
    l3.metric("Critérios suficientes",f"{float(ladder.get('evidence_sufficient_pct',0.0) or 0.0):.0f}%")
    l4.metric("Revisão humana","Elegível" if ladder.get("eligible_for_human_review") else "Ainda não")
    ladder_frame=pd.DataFrame(ladder.get("evidence_steps",[]) or [])
    if not ladder_frame.empty:
        st.dataframe(ladder_frame,width="stretch",hide_index=True)
    failures=list(ladder.get("failures",[]) or [])
    if failures:
        st.warning("Etapas ainda pendentes: "+" · ".join(str(x) for x in failures))
    st.caption(ladder.get("interpretation",""))

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
    "_journal_records_from_frame",
    "_match_forward_summary",
    "_resolve_forward_evidence",
    "_research_history_rows",
    "render_admin_research_panel",
]
