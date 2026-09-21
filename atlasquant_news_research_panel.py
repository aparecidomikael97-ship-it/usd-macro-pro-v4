"""AtlasQuant Admin lab for pre-news nowcast validation.

The panel works on explicit historical pre-release snapshots. It is a research
tool: it does not call brokers, does not trade news and does not convert data
forecast accuracy into a promise about price reaction.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any
import base64
from io import BytesIO

import pandas as pd
import requests
import streamlit as st

from atlasquant_news_nowcast import HistoricalRelease, validate_historical_release
from atlasquant_live_nowcast import normalize_live_ledger, summarize_live_nowcasts
from atlasquant_runtime_store import require_runtime_branch
from atlasquant_news_backtest import (
    monthly_news_scores,
    simple_month_score,
    walk_forward_news_backtest,
)

SCHEMA="ATLASQUANT_NEWS_RESEARCH_PANEL_V1"
LIVE_NOWCAST_PATH="dados/news_nowcast_predictions_v1.csv"

NEWS_HISTORY_COLUMNS=(
    "indicator",
    "scheduled_at",
    "captured_at",
    "consensus",
    "actual",
    "signal_score",
    "tolerance",
    "unit",
)


@st.cache_data(ttl=300,show_spinner=False)
def load_live_nowcast_runtime(
    *,
    repo:str,
    branch:str,
    token:str,
    max_rows:int=5000,
)->tuple[pd.DataFrame,dict[str,Any]]:
    try:
        safe=require_runtime_branch(branch)
    except Exception as exc:
        return pd.DataFrame(),{
            "ok":False,"reason":"UNSAFE_BRANCH","rows":0,"error":str(exc),
        }
    repo=str(repo or "").strip()
    token=str(token or "").strip()
    if not repo or not token:
        return pd.DataFrame(),{
            "ok":False,"reason":"NOT_CONFIGURED","rows":0,
            "branch":safe,"error":"",
        }
    try:
        response=requests.get(
            f"https://api.github.com/repos/{repo}/contents/{LIVE_NOWCAST_PATH}",
            headers={
                "Authorization":f"Bearer {token}",
                "Accept":"application/vnd.github+json",
                "X-GitHub-Api-Version":"2022-11-28",
            },
            params={"ref":safe},
            timeout=15,
        )
        if response.status_code==404:
            return pd.DataFrame(),{
                "ok":True,"reason":"NOT_FOUND","rows":0,
                "branch":safe,"path":LIVE_NOWCAST_PATH,"error":"",
            }
        response.raise_for_status()
        payload=response.json()
        raw=base64.b64decode(payload.get("content",""))
        frame=pd.read_csv(BytesIO(raw)) if raw else pd.DataFrame()
        if len(frame)>max(1,int(max_rows)):
            frame=frame.tail(max(1,int(max_rows))).reset_index(drop=True)
        frame=normalize_live_ledger(frame)
        return frame,{
            "ok":True,"reason":"LOADED","rows":int(len(frame)),
            "branch":safe,"path":LIVE_NOWCAST_PATH,"error":"",
        }
    except Exception as exc:
        return pd.DataFrame(),{
            "ok":False,"reason":"IO_ERROR","rows":0,
            "branch":safe,"path":LIVE_NOWCAST_PATH,
            "error":f"{type(exc).__name__}: {exc}",
        }


def live_nowcast_table(frame:pd.DataFrame|None)->pd.DataFrame:
    d=normalize_live_ledger(frame)
    if d.empty:
        return pd.DataFrame(columns=[
            "Indicador","Evento","Release","Capturado","Consenso",
            "Score antecedentes","Sinais","Estado","Estimativa",
            "P abaixo","P em linha","P acima","Fechado","Real","Classe",
        ])
    d["_captured"]=pd.to_datetime(d["captured_at"],utc=True,errors="coerce")
    d=d.sort_values("_captured").groupby("event_id",as_index=False).tail(1)
    rows=[]
    for _,row in d.sort_values("scheduled_at").iterrows():
        rows.append({
            "Indicador":row.get("indicator"),
            "Evento":row.get("event_name"),
            "Release":row.get("scheduled_raw_date") or row.get("scheduled_at"),
            "Capturado":row.get("captured_at"),
            "Consenso":row.get("consensus"),
            "Score antecedentes":row.get("signal_score"),
            "Sinais":row.get("signal_count"),
            "Estado":row.get("nowcast_state"),
            "Estimativa":row.get("estimate"),
            "P abaixo":row.get("p_below"),
            "P em linha":row.get("p_inline"),
            "P acima":row.get("p_above"),
            "Fechado":row.get("closed"),
            "Real":row.get("actual"),
            "Classe":row.get("surprise_class"),
        })
    return pd.DataFrame(rows)


def news_history_template_csv()->str:
    return (
        ",".join(NEWS_HISTORY_COLUMNS)+"\n"
        "PAYROLL,2026-08-07T12:30:00Z,2026-08-06T18:00:00Z,150,165,0.55,5,k\n"
        "PAYROLL,2026-09-04T12:30:00Z,2026-09-03T18:00:00Z,155,148,-0.20,5,k\n"
    )


def normalize_news_history_csv(frame:pd.DataFrame|None)->dict[str,Any]:
    if not isinstance(frame,pd.DataFrame) or frame.empty:
        return {
            "schema":SCHEMA,
            "records":[],
            "accepted":0,
            "rejected":0,
            "errors":[],
        }
    by_norm={str(c).strip().casefold():c for c in frame.columns}
    aliases={
        "indicator":("indicator","event","evento","indicador"),
        "scheduled_at":("scheduled_at","release_time","event_time","horario_release"),
        "captured_at":("captured_at","forecast_time","snapshot_time","captura"),
        "consensus":("consensus","estimate","forecast","consenso"),
        "actual":("actual","realized","realizado","atual"),
        "signal_score":("signal_score","leading_score","score_antecedentes"),
        "tolerance":("tolerance","inline_tolerance","tolerancia"),
        "unit":("unit","unidade"),
    }
    rename={}
    for canonical,names in aliases.items():
        if canonical in frame.columns:
            continue
        for name in names:
            actual=by_norm.get(str(name).casefold())
            if actual is not None:
                rename[actual]=canonical
                break
    df=frame.rename(columns=rename).copy()
    required={"indicator","scheduled_at","captured_at","consensus","actual","signal_score"}
    missing=sorted(required-set(df.columns))
    if missing:
        return {
            "schema":SCHEMA,
            "records":[],
            "accepted":0,
            "rejected":len(df),
            "errors":["colunas ausentes: "+", ".join(missing)],
        }

    records=[]
    errors=[]
    for pos,(_,row) in enumerate(df.iterrows(),start=2):
        try:
            scheduled=pd.to_datetime(row.get("scheduled_at"),utc=True,errors="raise")
            captured=pd.to_datetime(row.get("captured_at"),utc=True,errors="raise")
            consensus=float(row.get("consensus"))
            actual=float(row.get("actual"))
            score=float(row.get("signal_score"))
            tolerance=float(row.get("tolerance",0) if pd.notna(row.get("tolerance",0)) else 0)
            if not str(row.get("indicator") or "").strip():
                raise ValueError("indicator vazio")
            records.append(validate_historical_release(HistoricalRelease(
                indicator=str(row.get("indicator")).strip(),
                scheduled_at=scheduled.to_pydatetime(),
                captured_at=captured.to_pydatetime(),
                consensus=consensus,
                actual=actual,
                signal_score=score,
                tolerance=tolerance,
                unit="" if pd.isna(row.get("unit","")) else str(row.get("unit","")),
            )))
        except Exception as exc:
            errors.append(f"linha {pos}: {type(exc).__name__}: {exc}")
    return {
        "schema":SCHEMA,
        "records":records,
        "accepted":len(records),
        "rejected":len(errors),
        "errors":errors,
    }


def build_news_research_report(
    records:list[HistoricalRelease],
    *,
    min_history:int=40,
    min_analogs:int=20,
    bandwidth:float=0.25,
)->dict[str,Any]:
    bt=walk_forward_news_backtest(
        records,
        min_history=min_history,
        min_analogs=min_analogs,
        bandwidth=bandwidth,
    )
    return {
        "schema":SCHEMA,
        "backtest":bt,
        "simple_score":simple_month_score(bt),
        "real_orders_enabled":False,
        "trading_news_enabled":False,
        "market_reaction_scored":False,
        "automatic_weight_change":False,
    }


def render_news_research_lab(
    *,
    repo:str="",
    branch:str="",
    token:str="",
)->dict[str,Any]:
    st.markdown("### 📰 Laboratório Pré-Notícia / Nowcast")
    st.caption(
        "Valida se a estimativa ABOVE / INLINE / BELOW do dado econômico funcionaria "
        "em walk-forward. O teste reconstrói cada previsão apenas com releases já conhecidos."
    )
    st.warning(
        "Acertar o dado não significa acertar o candle. Reação do mercado, revisões, "
        "Fed e precificação serão avaliados em uma camada separada."
    )

    runtime_frame,runtime_status=load_live_nowcast_runtime(
        repo=repo,branch=branch,token=token,
    )
    if runtime_status.get("reason")=="LOADED":
        live_summary=summarize_live_nowcasts(runtime_frame)
        a,b,c1,d=st.columns(4)
        a.metric("Snapshots Live",live_summary.get("snapshots",0))
        b.metric("Releases acompanhados",live_summary.get("events",0))
        c1.metric("Releases fechados",live_summary.get("closed_events",0))
        d.metric("Com distribuição empírica",live_summary.get("with_empirical_distribution",0))
        live_table=live_nowcast_table(runtime_frame)
        if not live_table.empty:
            st.markdown("#### Captura prospectiva automática")
            st.dataframe(live_table,width="stretch",hide_index=True)
        st.caption(
            "Live Nowcast é coleta prospectiva. Pesos antecedentes continuam não calibrados "
            "e nenhuma leitura altera o Radar ou envia ordem automaticamente."
        )
    elif runtime_status.get("reason")=="NOT_FOUND":
        st.info("Live Nowcast ainda não acumulou snapshots na branch runtime.")
    elif runtime_status.get("reason") not in {"NOT_CONFIGURED",None}:
        st.caption(
            "Live Nowcast Runtime indisponível nesta tela: "
            +str(runtime_status.get("reason"))
        )

    st.download_button(
        "⬇️ Modelo de histórico pré-notícia",
        data=news_history_template_csv(),
        file_name="atlasquant_news_nowcast_history_template.csv",
        mime="text/csv",
        key="atlasquant_news_history_template",
    )
    uploaded=st.file_uploader(
        "Histórico de previsões/dados econômicos (CSV)",
        type=["csv"],
        key="atlasquant_news_history_upload",
    )
    if uploaded is None:
        return {
            "schema":SCHEMA,
            "state":"WAITING_HISTORY",
            "real_orders_enabled":False,
        }

    try:
        raw=pd.read_csv(uploaded)
    except Exception as exc:
        st.error(f"CSV inválido: {type(exc).__name__}: {exc}")
        return {
            "schema":SCHEMA,
            "state":"INVALID_CSV",
            "real_orders_enabled":False,
        }

    normalized=normalize_news_history_csv(raw)
    if normalized["errors"]:
        st.warning(
            f"{normalized['rejected']} linha(s) rejeitada(s). "
            "Nenhuma linha inválida é preenchida por chute."
        )
        with st.expander("Ver erros do histórico"):
            for err in normalized["errors"][:30]:
                st.write("- "+err)

    records=list(normalized["records"])
    if not records:
        st.info("Nenhum snapshot histórico válido para testar.")
        return {
            "schema":SCHEMA,
            "state":"NO_VALID_RECORDS",
            "real_orders_enabled":False,
        }

    report=build_news_research_report(records)
    bt=report["backtest"]
    overall=dict(bt.get("overall",{}) or {})
    score=dict(report["simple_score"])

    a,b,c,d=st.columns(4)
    a.metric("Previsões avaliadas",overall.get("forecast_samples",0))
    b.metric("Acerto ABOVE/INLINE/BELOW",score.get("text","sem amostra"))
    accuracy=overall.get("class_accuracy_pct")
    c.metric("Taxa da classificação","—" if accuracy is None else f"{float(accuracy):.1f}%")
    brier=overall.get("average_brier")
    d.metric("Brier médio","—" if brier is None else f"{float(brier):.3f}")

    st.caption(
        "Taxa acima = acerto da classe do DADO, não taxa de gain. "
        "Brier menor é melhor e penaliza excesso de confiança."
    )

    calibration=overall.get("calibration_gap_abs_pct")
    mae=overall.get("numeric_mae")
    x,y=st.columns(2)
    x.metric("Gap confiança × acerto","—" if calibration is None else f"{float(calibration):.1f} p.p.")
    y.metric("Erro numérico médio absoluto","—" if mae is None else f"{float(mae):.3f}")

    monthly=monthly_news_scores(bt)
    if monthly:
        st.markdown("#### Resultado por mês")
        st.dataframe(pd.DataFrame(monthly),width="stretch",hide_index=True)
        st.caption(
            "Exemplo de leitura: 8 de 10 = oito releases classificados corretamente "
            "como acima/em linha/abaixo do consenso. Não significa oito trades vencedores."
        )

    per=bt.get("per_indicator",{}) or {}
    if per:
        rows=[]
        for indicator,metrics in per.items():
            rows.append({
                "Indicador":indicator,
                "Amostra":metrics.get("forecast_samples"),
                "Acertos":metrics.get("class_hits"),
                "Taxa classe %":metrics.get("class_accuracy_pct"),
                "Brier":metrics.get("average_brier"),
                "Confiança média %":metrics.get("average_top_confidence_pct"),
                "Gap calibração p.p.":metrics.get("calibration_gap_abs_pct"),
                "MAE":metrics.get("numeric_mae"),
            })
        st.markdown("#### Por indicador")
        st.dataframe(pd.DataFrame(rows),width="stretch",hide_index=True)

    forecast_rows=pd.DataFrame(bt.get("forecasts",[]) or [])
    if not forecast_rows.empty:
        with st.expander("Ver previsão por release",expanded=False):
            st.dataframe(forecast_rows,width="stretch",hide_index=True)

    skipped=pd.DataFrame(bt.get("skipped",[]) or [])
    if not skipped.empty:
        with st.expander("Releases sem amostra suficiente",expanded=False):
            st.dataframe(skipped,width="stretch",hide_index=True)

    st.info(bt.get("interpretation",""))
    return {
        **report,
        "state":"DONE",
        "accepted_records":normalized["accepted"],
        "rejected_records":normalized["rejected"],
    }


__all__=[
    "SCHEMA","NEWS_HISTORY_COLUMNS","news_history_template_csv",
    "normalize_news_history_csv","build_news_research_report",
    "load_live_nowcast_runtime","live_nowcast_table",
    "render_news_research_lab",
]
