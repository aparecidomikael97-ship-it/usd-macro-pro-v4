"""AtlasQuant Performance Lab V1.

Empirical analysis of completed directional validations. This module is
diagnostic: it does not modify weights, scores, gates or production decisions.
Returns are directional validation returns, not guaranteed/live P&L.
"""
from __future__ import annotations

from math import sqrt
from typing import Any
import math
import pandas as pd
import streamlit as st


def _finite(value: Any) -> float | None:
    try:
        out=float(value)
        return out if math.isfinite(out) else None
    except Exception:
        return None


def _wilson(hits: int, n: int, z: float = 1.96) -> tuple[float | None, float | None]:
    if n <= 0:
        return None, None
    p=float(hits)/float(n)
    den=1.0+(z*z/n)
    center=(p+(z*z/(2*n)))/den
    margin=(z*sqrt((p*(1-p)/n)+(z*z/(4*n*n))))/den
    return max(0.0,center-margin)*100.0, min(1.0,center+margin)*100.0


def _score_band(v: Any) -> str:
    x=_finite(v)
    if x is None: return "Sem score"
    if x >= 90: return "90+"
    if x >= 80: return "80–89"
    if x >= 70: return "70–79"
    return "<70"


def _quality_band(v: Any) -> str:
    if isinstance(v,str):
        v=v.replace("%","").replace(",",".").strip()
    x=_finite(v)
    if x is None: return "Sem qualidade"
    if x >= 75: return "75%+"
    if x >= 60: return "60–74%"
    return "<60%"


def prepare_performance_history(df: pd.DataFrame, horizon: str = "24h") -> pd.DataFrame:
    if not isinstance(df,pd.DataFrame) or df.empty:
        return pd.DataFrame()
    suf=str(horizon).lower()
    retcol=f"retorno_{suf}_pct"
    required={"par","direcao","score_mestre","qualidade",retcol}
    if not required.issubset(df.columns):
        return pd.DataFrame()

    out=df.copy()
    out[retcol]=pd.to_numeric(out[retcol],errors="coerce")
    out["score_mestre"]=pd.to_numeric(out["score_mestre"],errors="coerce")
    out["qualidade_num"]=pd.to_numeric(
        out["qualidade"].astype(str).str.replace("%","",regex=False).str.replace(",",".",regex=False),
        errors="coerce",
    )
    out=out[out[retcol].notna()].copy()
    if out.empty:
        return out
    out["hit"]=out[retcol] > 0
    out["Faixa Score"]=out["score_mestre"].map(_score_band)
    out["Faixa Qualidade"]=out["qualidade_num"].map(_quality_band)
    if "registrado_em" in out.columns:
        out["registrado_em_dt"]=pd.to_datetime(out["registrado_em"],errors="coerce",utc=True)
        out["Mês"]=out["registrado_em_dt"].dt.strftime("%Y-%m")
    return out


def overall_metrics(df: pd.DataFrame, horizon: str = "24h") -> dict[str, Any]:
    data=prepare_performance_history(df,horizon)
    if data.empty:
        return {
            "samples":0,"wins":0,"losses":0,"breakeven":0,"hit_rate_pct":None,
            "mean_return_pct":None,"median_return_pct":None,"std_return_pct":None,
            "max_drawdown_pct_points":None,"wilson_low_pct":None,"wilson_high_pct":None,
        }
    retcol=f"retorno_{str(horizon).lower()}_pct"
    vals=pd.to_numeric(data[retcol],errors="coerce").dropna().astype(float)
    wins=int((vals>0).sum()); losses=int((vals<0).sum()); be=int((vals==0).sum()); n=len(vals)
    low,high=_wilson(wins,n)
    equity=vals.cumsum()
    running_peak=equity.cummax()
    dd=(running_peak-equity)
    return {
        "samples":int(n),
        "wins":wins,
        "losses":losses,
        "breakeven":be,
        "hit_rate_pct":round(wins/n*100.0,2) if n else None,
        "mean_return_pct":round(float(vals.mean()),4) if n else None,
        "median_return_pct":round(float(vals.median()),4) if n else None,
        "std_return_pct":round(float(vals.std(ddof=0)),4) if n else None,
        "max_drawdown_pct_points":round(float(dd.max()),4) if n else None,
        "wilson_low_pct":None if low is None else round(low,2),
        "wilson_high_pct":None if high is None else round(high,2),
    }


def available_dimensions(df: pd.DataFrame) -> list[str]:
    if not isinstance(df,pd.DataFrame) or df.empty:
        return []
    dims=["par","direcao","Faixa Score","Faixa Qualidade"]
    optional=[
        ("sessao","sessao"),("session","session"),("regime","regime"),
        ("setup","setup"),("modelo","modelo"),
    ]
    seen=set(dims)
    for _,col in optional:
        if col in df.columns and col not in seen:
            dims.append(col); seen.add(col)
    if "registrado_em" in df.columns:
        dims.append("Mês")
    return dims


def grouped_metrics(
    df: pd.DataFrame,
    horizon: str,
    dimension: str,
    *,
    min_group_samples: int = 10,
) -> pd.DataFrame:
    data=prepare_performance_history(df,horizon)
    if data.empty or dimension not in data.columns:
        return pd.DataFrame()
    retcol=f"retorno_{str(horizon).lower()}_pct"
    rows=[]
    for value,g in data.groupby(dimension,dropna=False):
        vals=pd.to_numeric(g[retcol],errors="coerce").dropna().astype(float)
        n=int(len(vals))
        if n==0: continue
        wins=int((vals>0).sum())
        low,high=_wilson(wins,n)
        rows.append({
            dimension:str(value),
            "Amostra":n,
            "Acertos":wins,
            "Taxa observada %":round(wins/n*100.0,2),
            "IC95 baixo %":round(low,2) if low is not None else None,
            "IC95 alto %":round(high,2) if high is not None else None,
            "Retorno médio %":round(float(vals.mean()),4),
            "Retorno mediano %":round(float(vals.median()),4),
            "Volatilidade %":round(float(vals.std(ddof=0)),4),
            "Amostra suficiente":bool(n>=int(min_group_samples)),
        })
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values(["Amostra",dimension],ascending=[False,True]).reset_index(drop=True)


def performance_readiness(
    df: pd.DataFrame,
    horizon: str = "24h",
    *,
    min_total_samples: int = 100,
    min_group_samples: int = 30,
) -> dict[str, Any]:
    data=prepare_performance_history(df,horizon)
    total=int(len(data))
    pairs=int(data["par"].nunique()) if not data.empty and "par" in data.columns else 0
    months=int(data["Mês"].nunique()) if not data.empty and "Mês" in data.columns else 0
    per_pair=(data.groupby("par").size() if not data.empty and "par" in data.columns else pd.Series(dtype=int))
    adequately_sampled_pairs=int((per_pair>=int(min_group_samples)).sum()) if not per_pair.empty else 0

    if total < int(min_total_samples):
        status="BUILDING"; label="AMOSTRA EM FORMAÇÃO"
    elif adequately_sampled_pairs < 2:
        status="CONCENTRATED"; label="AMOSTRA CONCENTRADA"
    elif months and months < 3:
        status="SHORT_WINDOW"; label="JANELA TEMPORAL CURTA"
    else:
        status="REVIEWABLE"; label="AMOSTRA ÚTIL PARA REVISÃO"

    return {
        "status":status,
        "label":label,
        "total_samples":total,
        "pairs":pairs,
        "months":months,
        "adequately_sampled_pairs":adequately_sampled_pairs,
        "auto_model_change_allowed":False,
    }


def render_performance_lab(
    df: pd.DataFrame,
    *,
    min_total_samples: int = 100,
    min_group_samples: int = 30,
) -> dict[str, Any]:
    st.markdown("### 📊 AtlasQuant Performance Lab")
    st.caption(
        "Analisa apenas validações históricas concluídas. Taxa observada não é garantia "
        "futura e retorno direcional não equivale necessariamente ao P&L real após custos."
    )
    horizon=st.selectbox(
        "Horizonte",
        ["1H","4H","24H"],
        index=2,
        key="atlasquant_performance_horizon",
    ).lower()
    data=prepare_performance_history(df,horizon)
    readiness=performance_readiness(
        df,horizon,min_total_samples=min_total_samples,min_group_samples=min_group_samples
    )
    metrics=overall_metrics(df,horizon)

    c1,c2,c3,c4=st.columns(4)
    c1.metric("Amostras",metrics["samples"])
    c2.metric("Taxa observada","—" if metrics["hit_rate_pct"] is None else f"{metrics['hit_rate_pct']:.1f}%")
    c3.metric("Retorno médio","—" if metrics["mean_return_pct"] is None else f"{metrics['mean_return_pct']:+.3f}%")
    c4.metric("Estado",readiness["label"])

    if metrics["samples"]:
        st.caption(
            f"IC95 da taxa observada: {metrics['wilson_low_pct']:.1f}%–{metrics['wilson_high_pct']:.1f}% · "
            f"mediana {metrics['median_return_pct']:+.3f}% · "
            f"drawdown acumulado simples {metrics['max_drawdown_pct_points']:.3f} p.p."
        )

    dims=available_dimensions(data)
    if dims:
        dimension=st.selectbox("Quebra de performance",dims,key="atlasquant_performance_dimension")
        grouped=grouped_metrics(
            df,horizon,dimension,min_group_samples=min_group_samples
        )
        if grouped.empty:
            st.info("Sem dados suficientes para esta quebra.")
        else:
            st.dataframe(grouped,width="stretch",hide_index=True)

    if readiness["status"]=="BUILDING":
        st.warning("Amostra ainda pequena. Não alterar pesos, thresholds ou regras com base neste painel.")
    elif readiness["status"] in ("CONCENTRATED","SHORT_WINDOW"):
        st.warning("Amostra existe, mas ainda está concentrada em poucos pares ou em janela temporal curta.")
    else:
        st.success("Amostra já é mais útil para revisão humana e comparação em Shadow Mode.")

    st.caption("Mudança automática de modelo/pesos: DESATIVADA por design.")
    return {"readiness":readiness,"metrics":metrics}
