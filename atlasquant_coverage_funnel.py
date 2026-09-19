"""AtlasQuant Coverage Funnel V1.

Makes capability boundaries explicit across the 28-pair G8 universe.
A pair without the full institutional pipeline is never presented as
operationally executable.
"""
from __future__ import annotations

from typing import Iterable, Any
import math
import pandas as pd
import streamlit as st

from atlasquant_dashboard_v1 import build_g8_radar


DEFAULT_OPERATIONAL_PAIRS=(
    "EUR/USD","GBP/USD","AUD/USD","NZD/USD",
    "USD/JPY","USD/CHF","USD/CAD",
)


def build_coverage_matrix(
    ranking: pd.DataFrame,
    operational_pairs: Iterable[str] = DEFAULT_OPERATIONAL_PAIRS,
    *,
    neutral_band: float = 5.0,
) -> pd.DataFrame:
    radar=build_g8_radar(ranking,neutral_band=neutral_band).copy()
    supported={
        str(x).strip().upper() for x in (operational_pairs or ())
        if str(x).strip()
    }
    radar["Cobertura operacional"]=radar["Par"].map(
        lambda p: "PIPELINE COMPLETO" if str(p).upper() in supported else "RADAR MACRO"
    )
    radar["Pode receber status executável?"]=radar["Par"].map(
        lambda p: "SIM" if str(p).upper() in supported else "NÃO"
    )
    return radar


def coverage_summary(matrix: pd.DataFrame) -> dict[str, Any]:
    if not isinstance(matrix,pd.DataFrame) or matrix.empty:
        return {"total":0,"full":0,"macro_only":0,"coverage_pct":0.0}
    full=int((matrix["Cobertura operacional"]=="PIPELINE COMPLETO").sum())
    total=int(len(matrix))
    return {
        "total":total,
        "full":full,
        "macro_only":total-full,
        "coverage_pct":round(full/total*100.0,1) if total else 0.0,
    }


def expansion_watchlist(matrix: pd.DataFrame, top_n: int = 5) -> pd.DataFrame:
    if not isinstance(matrix,pd.DataFrame) or matrix.empty:
        return pd.DataFrame()
    required={"Cobertura operacional","Par","Direção macro","Diferença","Intensidade relativa"}
    if not required.issubset(matrix.columns):
        return pd.DataFrame()
    x=matrix[matrix["Cobertura operacional"]=="RADAR MACRO"].copy()
    x["Intensidade relativa"]=pd.to_numeric(x["Intensidade relativa"],errors="coerce")
    x=x[x["Intensidade relativa"].map(lambda v: bool(pd.notna(v) and math.isfinite(float(v))))]
    if x.empty:
        return x
    try:
        n=int(top_n)
        if isinstance(top_n,bool) or n<=0: return x.iloc[0:0].copy()
    except Exception:
        return x.iloc[0:0].copy()
    return x.sort_values("Intensidade relativa",ascending=False).head(n)[
        ["Par","Direção macro","Diferença","Intensidade relativa","Cobertura operacional"]
    ].reset_index(drop=True)


def render_coverage_funnel(
    ranking: pd.DataFrame,
    operational_pairs: Iterable[str] = DEFAULT_OPERATIONAL_PAIRS,
    *,
    neutral_band: float = 5.0,
) -> pd.DataFrame:
    matrix=build_coverage_matrix(
        ranking,operational_pairs=operational_pairs,neutral_band=neutral_band
    )
    s=coverage_summary(matrix)
    st.markdown("### 🧭 Cobertura do motor — 28 → pipeline operacional")
    st.caption(
        "Os 28 pares recebem leitura macro relativa. Apenas os pares com pipeline completo "
        "podem avançar para Safety Core, ICT/SMC e status executável."
    )
    c1,c2,c3,c4=st.columns(4)
    c1.metric("Universo macro",s["total"])
    c2.metric("Pipeline completo",s["full"])
    c3.metric("Somente radar macro",s["macro_only"])
    c4.metric("Cobertura operacional",f"{s['coverage_pct']:.1f}%")

    watch=expansion_watchlist(matrix,top_n=5)
    with st.expander("Pares fora do pipeline completo — prioridade técnica de expansão"):
        if watch.empty:
            st.info("Nenhum par pendente de expansão.")
        else:
            st.caption(
                "Ordenação apenas para planejar expansão de infraestrutura. "
                "Não significa recomendação de trade nem autorização operacional."
            )
            st.dataframe(watch,width="stretch",hide_index=True)
    return matrix
