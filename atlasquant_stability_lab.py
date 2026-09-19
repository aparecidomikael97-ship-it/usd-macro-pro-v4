"""AtlasQuant Stability Lab V1.

Time-stability and market-session diagnostics for completed historical
validations. This module is descriptive only: it never changes model weights,
thresholds, gates or live decisions.
"""
from __future__ import annotations

from math import sqrt
from typing import Any
from zoneinfo import ZoneInfo
import math
import pandas as pd
import streamlit as st

from atlasquant_performance_lab import prepare_performance_history


def _finite(value: Any) -> float | None:
    try:
        out=float(value)
        return out if math.isfinite(out) else None
    except Exception:
        return None

def _positive_int(value: Any, *, minimum: int = 1) -> tuple[int,bool]:
    if isinstance(value,bool):
        return minimum,False
    try:
        x=float(value)
        if not math.isfinite(x) or not x.is_integer() or x < minimum:
            return minimum,False
        return int(x),True
    except Exception:
        return minimum,False


def _wilson(hits: int, n: int, z: float = 1.96) -> tuple[float | None, float | None]:
    if n <= 0:
        return None,None
    p=float(hits)/float(n)
    den=1.0+(z*z/n)
    center=(p+(z*z/(2*n)))/den
    margin=(z*sqrt((p*(1-p)/n)+(z*z/(4*n*n))))/den
    return max(0.0,center-margin)*100.0,min(1.0,center+margin)*100.0


def forex_session(timestamp: Any) -> str:
    """DST-aware session proxy from a UTC timestamp.

    A validation can occur in overlapping sessions; for a single grouping key,
    London/New York overlap receives its own label.
    """
    try:
        ts=pd.to_datetime(timestamp,utc=True,errors="coerce")
        if pd.isna(ts):
            return "Sem horário"
        london=ts.tz_convert(ZoneInfo("Europe/London"))
        newyork=ts.tz_convert(ZoneInfo("America/New_York"))
        tokyo=ts.tz_convert(ZoneInfo("Asia/Tokyo"))
        london_open=8 <= london.hour < 17
        ny_open=8 <= newyork.hour < 17
        tokyo_open=9 <= tokyo.hour < 18
        if london_open and ny_open:
            return "London/NY overlap"
        if london_open:
            return "London"
        if ny_open:
            return "New York"
        if tokyo_open:
            return "Asia/Tokyo"
        return "Fora das sessões principais"
    except Exception:
        return "Sem horário"


def add_stability_dimensions(df: pd.DataFrame, horizon: str = "24h") -> pd.DataFrame:
    data=prepare_performance_history(df,horizon)
    if data.empty:
        return data
    if "registrado_em_dt" in data.columns:
        data=data.copy()
        data["Sessão"]=data["registrado_em_dt"].map(forex_session)
    if "regime" in data.columns:
        data["Regime"]=data["regime"].fillna("Sem regime").astype(str)
    return data


def temporal_folds(
    df: pd.DataFrame,
    horizon: str = "24h",
    *,
    folds: int = 3,
) -> pd.DataFrame:
    data=add_stability_dimensions(df,horizon)
    if data.empty or "registrado_em_dt" not in data.columns:
        return pd.DataFrame()
    data=data[data["registrado_em_dt"].notna()].sort_values("registrado_em_dt").copy()
    n=len(data)
    k,k_valid=_positive_int(folds,minimum=2)
    if not k_valid or n < k:
        return pd.DataFrame()

    # Deterministic chronological folds with near-equal sizes.
    base=n//k
    rem=n%k
    rows=[]
    start=0
    retcol=f"retorno_{str(horizon).lower()}_pct"
    for idx in range(k):
        size=base+(1 if idx<rem else 0)
        g=data.iloc[start:start+size].copy()
        start+=size
        vals=pd.to_numeric(g[retcol],errors="coerce").dropna().astype(float)
        vals=vals[vals.map(math.isfinite)]
        if vals.empty:
            continue
        hits=int((vals>0).sum()); total=int(len(vals))
        low,high=_wilson(hits,total)
        rows.append({
            "Período":f"F{idx+1}",
            "Início":g["registrado_em_dt"].min(),
            "Fim":g["registrado_em_dt"].max(),
            "Amostra":total,
            "Taxa observada %":round(hits/total*100.0,2),
            "IC95 baixo %":round(low,2) if low is not None else None,
            "IC95 alto %":round(high,2) if high is not None else None,
            "Retorno médio %":round(float(vals.mean()),4),
            "Retorno mediano %":round(float(vals.median()),4),
        })
    return pd.DataFrame(rows)


def session_metrics(
    df: pd.DataFrame,
    horizon: str = "24h",
    *,
    min_samples: int = 10,
) -> pd.DataFrame:
    threshold,threshold_valid=_positive_int(min_samples)
    data=add_stability_dimensions(df,horizon)
    if not threshold_valid or data.empty or "Sessão" not in data.columns:
        return pd.DataFrame()
    retcol=f"retorno_{str(horizon).lower()}_pct"
    rows=[]
    for session,g in data.groupby("Sessão",dropna=False):
        vals=pd.to_numeric(g[retcol],errors="coerce").dropna().astype(float)
        vals=vals[vals.map(math.isfinite)]
        n=int(len(vals))
        if not n:
            continue
        hits=int((vals>0).sum())
        low,high=_wilson(hits,n)
        rows.append({
            "Sessão":str(session),
            "Amostra":n,
            "Taxa observada %":round(hits/n*100.0,2),
            "IC95 baixo %":round(low,2) if low is not None else None,
            "IC95 alto %":round(high,2) if high is not None else None,
            "Retorno médio %":round(float(vals.mean()),4),
            "Amostra suficiente":bool(n>=threshold),
        })
    return pd.DataFrame(rows).sort_values(["Amostra","Sessão"],ascending=[False,True]).reset_index(drop=True)


def stability_summary(
    folds_df: pd.DataFrame,
    *,
    min_fold_samples: int = 30,
    max_hit_rate_spread_pp: float = 15.0,
) -> dict[str, Any]:
    if not isinstance(folds_df,pd.DataFrame) or folds_df.empty:
        return {
            "status":"INSUFFICIENT","label":"SEM JANELA TEMPORAL SUFICIENTE",
            "folds":0,"all_folds_sufficient":False,"hit_rate_spread_pp":None,
            "mean_return_sign_consistent":False,"auto_change_allowed":False,
        }
    fold_min,fold_min_valid=_positive_int(min_fold_samples)
    spread_limit=_finite(max_hit_rate_spread_pp)
    thresholds_valid=bool(fold_min_valid and spread_limit is not None and spread_limit>=0)
    rates=pd.to_numeric(folds_df["Taxa observada %"],errors="coerce").dropna()
    rates=rates[rates.map(math.isfinite)]
    rets=pd.to_numeric(folds_df["Retorno médio %"],errors="coerce").dropna()
    rets=rets[rets.map(math.isfinite)]
    samples=pd.to_numeric(folds_df["Amostra"],errors="coerce")
    samples_valid=bool(len(samples)>=2 and samples.notna().all() and samples.map(lambda x: math.isfinite(float(x)) and float(x)>=0).all())
    sufficient=bool(thresholds_valid and samples_valid and (samples>=fold_min).all())
    spread=float(rates.max()-rates.min()) if len(rates) else None
    nonzero=[x for x in rets.tolist() if abs(float(x))>1e-12]
    sign_consistent=bool(
        len(nonzero)>=2 and (all(x>0 for x in nonzero) or all(x<0 for x in nonzero))
    )

    if not sufficient:
        status="INSUFFICIENT"; label="AMOSTRA TEMPORAL INSUFICIENTE"
    elif spread is not None and spread <= spread_limit and sign_consistent:
        status="STABLE"; label="ESTABILIDADE TEMPORAL CONSISTENTE"
    else:
        status="UNSTABLE"; label="INSTABILIDADE ENTRE JANELAS"

    return {
        "status":status,
        "label":label,
        "folds":int(len(folds_df)),
        "all_folds_sufficient":sufficient,
        "thresholds_valid":thresholds_valid,
        "hit_rate_spread_pp":None if spread is None else round(spread,2),
        "mean_return_sign_consistent":sign_consistent,
        "auto_change_allowed":False,
    }


def render_stability_lab(
    df: pd.DataFrame,
    *,
    min_fold_samples: int = 30,
    session_min_samples: int = 10,
) -> dict[str, Any]:
    st.markdown("### 🧪 Stability / Walk-Forward Lab")
    st.caption(
        "Compara janelas cronológicas e sessões com resultados já concluídos. "
        "É diagnóstico de estabilidade, não previsão de desempenho futuro."
    )
    horizon=st.selectbox(
        "Horizonte de estabilidade",
        ["1H","4H","24H"],
        index=2,
        key="atlasquant_stability_horizon",
    ).lower()

    folds=temporal_folds(df,horizon,folds=3)
    summary=stability_summary(folds,min_fold_samples=min_fold_samples)
    sessions=session_metrics(df,horizon,min_samples=session_min_samples)

    c1,c2,c3,c4=st.columns(4)
    c1.metric("Janelas",summary["folds"])
    c2.metric("Amostra por janela","OK" if summary["all_folds_sufficient"] else "INSUFICIENTE")
    c3.metric("Spread taxa","—" if summary["hit_rate_spread_pp"] is None else f"{summary['hit_rate_spread_pp']:.1f} p.p.")
    c4.metric("Estado",summary["label"])

    if not folds.empty:
        st.markdown("#### Walk-forward cronológico")
        st.dataframe(folds,width="stretch",hide_index=True)

    if not sessions.empty:
        st.markdown("#### Performance por sessão")
        st.caption("Sessões calculadas com fusos oficiais e ajuste automático de horário de verão.")
        st.dataframe(sessions,width="stretch",hide_index=True)

    data=add_stability_dimensions(df,horizon)
    if not data.empty and "Regime" in data.columns:
        st.markdown("#### Regime registrado")
        st.caption("Regime só aparece quando o histórico possui esse campo; o Lab não inventa regimes retroativamente.")
        regime_rows=[]
        retcol=f"retorno_{horizon}_pct"
        for regime,g in data.groupby("Regime",dropna=False):
            vals=pd.to_numeric(g[retcol],errors="coerce").dropna().astype(float)
            vals=vals[vals.map(math.isfinite)]
            if len(vals):
                regime_rows.append({
                    "Regime":str(regime),"Amostra":len(vals),
                    "Taxa observada %":round(float((vals>0).mean()*100.0),2),
                    "Retorno médio %":round(float(vals.mean()),4),
                })
        if regime_rows:
            st.dataframe(pd.DataFrame(regime_rows),width="stretch",hide_index=True)

    if summary["status"]=="STABLE":
        st.success("As janelas avaliadas estão relativamente consistentes; qualquer mudança de modelo continua manual.")
    elif summary["status"]=="UNSTABLE":
        st.warning("Há instabilidade temporal relevante. Evite otimizar pesos para uma única janela.")
    else:
        st.warning("Amostra temporal ainda insuficiente para avaliar estabilidade.")

    st.caption("Auto-otimização / auto-promoção: DESATIVADAS por design.")
    return {"summary":summary,"folds":folds,"sessions":sessions}
