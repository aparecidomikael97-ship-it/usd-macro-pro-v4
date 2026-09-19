"""AtlasQuant Conviction Calibration Lab V1.

Empirical reliability analysis for directional-score bands using only completed
historical validations. The raw directional score is NOT a probability. This
module reports observed historical hit rates with Wilson intervals and refuses
to label a band calibrated when the sample is too small.
"""
from __future__ import annotations

from math import sqrt
from typing import Any
import math
import pandas as pd
import streamlit as st


BANDS = (
    ("<70", 0.0, 70.0),
    ("70–79", 70.0, 80.0),
    ("80–89", 80.0, 90.0),
    ("90+", 90.0, 101.0),
)


def _num(value: Any) -> float | None:
    try:
        out=float(value)
        return out if math.isfinite(out) else None
    except Exception:
        return None

def _positive_int(value: Any) -> tuple[int,bool]:
    if isinstance(value,bool):
        return 1,False
    try:
        x=float(value)
        if not math.isfinite(x) or not x.is_integer() or x < 1:
            return 1,False
        return int(x),True
    except Exception:
        return 1,False


def score_band(score: Any) -> str:
    x=_num(score)
    if x is None:
        return "SEM SCORE"
    for label,lo,hi in BANDS:
        if lo <= x < hi:
            return label
    return "SEM SCORE"


def wilson_interval(hits: int, n: int, z: float = 1.96) -> tuple[float | None, float | None]:
    if n <= 0:
        return None,None
    p=float(hits)/float(n)
    den=1.0+(z*z/n)
    center=(p+(z*z/(2*n)))/den
    margin=(z*sqrt((p*(1-p)/n)+(z*z/(4*n*n))))/den
    return max(0.0,center-margin)*100.0,min(1.0,center+margin)*100.0


def _completed_rows(df: pd.DataFrame, horizon: str) -> pd.DataFrame:
    if not isinstance(df,pd.DataFrame) or df.empty:
        return pd.DataFrame()
    suf=str(horizon).lower()
    score_col="score_mestre"
    ret_col=f"retorno_{suf}_pct"
    required={score_col,ret_col}
    if not required.issubset(df.columns):
        return pd.DataFrame()
    out=df.copy()
    out[score_col]=pd.to_numeric(out[score_col],errors="coerce")
    out[ret_col]=pd.to_numeric(out[ret_col],errors="coerce")
    valid_score=out[score_col].map(lambda x: bool(pd.notna(x) and math.isfinite(float(x))))
    valid_ret=out[ret_col].map(lambda x: bool(pd.notna(x) and math.isfinite(float(x))))
    out=out[valid_score & valid_ret].copy()
    if out.empty:
        return out
    out["faixa_score"]=out[score_col].map(score_band)
    out["acerto_empirico"]=out[ret_col]>0
    return out


def calibration_table(
    df: pd.DataFrame,
    horizon: str = "24h",
    *,
    min_band_samples: int = 30,
) -> pd.DataFrame:
    threshold,threshold_valid=_positive_int(min_band_samples)
    data=_completed_rows(df,horizon)
    rows=[]
    for label,_,_ in BANDS:
        g=data[data["faixa_score"]==label] if not data.empty else pd.DataFrame()
        n=int(len(g))
        hits=int(g["acerto_empirico"].sum()) if n else 0
        low,high=wilson_interval(hits,n)
        avg_ret=float(g[f"retorno_{str(horizon).lower()}_pct"].mean()) if n else None
        rows.append({
            "Faixa":label,
            "Amostra":n,
            "Acertos":hits,
            "Taxa observada %":None if n==0 else round(hits/n*100.0,2),
            "IC95 baixo %":None if low is None else round(low,2),
            "IC95 alto %":None if high is None else round(high,2),
            "Retorno direcional médio %":None if avg_ret is None else round(avg_ret,4),
            "Amostra suficiente":bool(threshold_valid and n>=threshold),
        })
    return pd.DataFrame(rows)


def calibration_summary(
    table: pd.DataFrame,
    *,
    min_total_samples: int = 100,
) -> dict[str, Any]:
    if not isinstance(table,pd.DataFrame) or table.empty:
        return {
            "total_samples":0,"eligible_bands":0,"monotonic":False,
            "status":"INSUFFICIENT","label":"AMOSTRA INSUFICIENTE",
            "auto_reweight_allowed":False,
        }
    sample_counts=pd.to_numeric(table["Amostra"],errors="coerce")
    samples_valid=bool(sample_counts.notna().all() and sample_counts.map(lambda x: math.isfinite(float(x)) and float(x)>=0).all())
    total_min,total_min_valid=_positive_int(min_total_samples)
    total=int(sample_counts.sum()) if samples_valid else 0
    eligible=table[table["Amostra suficiente"]==True].copy() if samples_valid else table.iloc[0:0].copy()
    rate_series=pd.to_numeric(eligible["Taxa observada %"],errors="coerce").dropna()
    rate_series=rate_series[rate_series.map(math.isfinite)]
    rates=rate_series.tolist()
    monotonic=len(rates)>=2 and all(rates[i+1]>=rates[i] for i in range(len(rates)-1))
    enough=bool(total_min_valid and total>=total_min and len(eligible)>=2)
    if not enough:
        status="INSUFFICIENT"; label="AMOSTRA INSUFICIENTE"
    elif monotonic:
        status="CONSISTENT"; label="CONVICÇÃO COM RELAÇÃO EMPÍRICA CONSISTENTE"
    else:
        status="UNSTABLE"; label="CONVICÇÃO AINDA NÃO MONOTÔNICA"
    return {
        "total_samples":total,
        "eligible_bands":int(len(eligible)),
        "threshold_valid":bool(total_min_valid),
        "monotonic":bool(monotonic),
        "status":status,
        "label":label,
        "auto_reweight_allowed":False,
    }


def render_calibration_lab(
    df: pd.DataFrame,
    *,
    min_band_samples: int = 30,
    min_total_samples: int = 100,
) -> dict[str, Any]:
    st.markdown("### 🎚️ Conviction Calibration Lab")
    st.caption(
        "O Score Mestre continua sendo intensidade/ranking, não probabilidade de lucro. "
        "Aqui mostramos apenas taxa histórica observada em sinais já vencidos."
    )
    horizon=st.selectbox(
        "Horizonte de calibração",
        ["1H","4H","24H"],
        index=2,
        key="atlasquant_calibration_horizon",
    ).lower()
    table=calibration_table(df,horizon,min_band_samples=min_band_samples)
    summary=calibration_summary(table,min_total_samples=min_total_samples)

    c1,c2,c3,c4=st.columns(4)
    c1.metric("Amostras concluídas",summary["total_samples"])
    c2.metric("Faixas utilizáveis",summary["eligible_bands"])
    c3.metric("Relação monotônica","SIM" if summary["monotonic"] else "NÃO")
    c4.metric("Autoajuste de pesos","DESATIVADO")

    st.dataframe(table,width="stretch",hide_index=True)

    if summary["status"]=="INSUFFICIENT":
        st.warning("Amostra insuficiente: não converter score em probabilidade e não alterar pesos.")
    elif summary["status"]=="CONSISTENT":
        st.success("As faixas com amostra suficiente mostram relação empírica crescente neste horizonte. Revisão humana ainda é obrigatória.")
    else:
        st.warning("As faixas não apresentam relação monotônica estável. Convicção não deve ser reinterpretada como probabilidade.")

    st.caption("Autoajuste de pesos/calibração em produção: DESATIVADO por design.")
    return summary
