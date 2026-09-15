"""AtlasQuant Dashboard V1 — professional market overview.

Presentation and relative-strength radar for the G8 FX universe. It does not
turn ranking intensity into a probability and does not bypass the Safety Core
or the institutional execution gates.
"""
from __future__ import annotations

from typing import Any
import pandas as pd
import streamlit as st

from atlasquant_fx_universe import CURRENCIES, rank_pairs


def strengths_from_ranking(ranking: pd.DataFrame) -> dict[str, float]:
    if not isinstance(ranking, pd.DataFrame):
        raise TypeError("ranking deve ser DataFrame")
    required = {"Código", "Pontuação_Final"}
    if not required.issubset(ranking.columns):
        raise ValueError("ranking sem colunas Código/Pontuação_Final")
    out: dict[str, float] = {}
    for _, row in ranking.iterrows():
        code = str(row["Código"]).strip().upper()
        if code in CURRENCIES:
            out[code] = float(row["Pontuação_Final"])
    missing = [c for c in CURRENCIES if c not in out]
    if missing:
        raise ValueError("Moedas G8 ausentes: " + ", ".join(missing))
    return out


def build_g8_radar(ranking: pd.DataFrame, neutral_band: float = 5.0) -> pd.DataFrame:
    strengths = strengths_from_ranking(ranking)
    rows = []
    for p in rank_pairs(strengths, neutral_band=neutral_band):
        rows.append({
            "Par": p.pair,
            "Direção macro": "COMPRA" if p.side == "BUY" else "VENDA" if p.side == "SELL" else "NEUTRO",
            "Base": p.base,
            "Força base": round(p.base_strength, 1),
            "Cotada": p.quote,
            "Força cotada": round(p.quote_strength, 1),
            "Diferença": round(p.differential, 1),
            "Intensidade relativa": round(p.directional_score, 1),
        })
    return pd.DataFrame(rows)


def radar_summary(radar: pd.DataFrame) -> dict[str, Any]:
    if radar is None or radar.empty:
        return {"total": 0, "directed": 0, "neutral": 0, "top_pair": None, "top_side": None, "top_intensity": None}
    directed = radar[radar["Direção macro"] != "NEUTRO"]
    top = directed.iloc[0] if not directed.empty else radar.iloc[0]
    return {
        "total": int(len(radar)),
        "directed": int(len(directed)),
        "neutral": int((radar["Direção macro"] == "NEUTRO").sum()),
        "top_pair": str(top["Par"]),
        "top_side": str(top["Direção macro"]),
        "top_intensity": float(top["Intensidade relativa"]),
    }


def render_g8_radar(ranking: pd.DataFrame, neutral_band: float = 5.0, top_n: int = 8) -> pd.DataFrame:
    radar = build_g8_radar(ranking, neutral_band=neutral_band)
    summary = radar_summary(radar)

    st.markdown("### 🌐 Radar G8 — 28 pares")
    st.caption(
        "Comparação relativa das 8 moedas principais. A intensidade é um ranking interno, "
        "não uma probabilidade de ganho e não substitui os gates técnicos/operacionais."
    )

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Universo", f"{summary['total']} pares")
    c2.metric("Com viés", summary["directed"])
    c3.metric("Neutros", summary["neutral"])
    c4.metric("Maior desequilíbrio", summary["top_pair"] or "—")

    shown = radar.head(max(1, int(top_n))).copy()
    st.dataframe(shown, use_container_width=True, hide_index=True)
    with st.expander("Ver os 28 pares"):
        st.dataframe(radar, use_container_width=True, hide_index=True)

    st.info(
        "Fluxo operacional: força relativa → filtro macro/qualidade → Safety Core → "
        "confirmação ICT/SMC → plano. Sem confirmação suficiente, o estado continua AGUARDAR/NÃO OPERAR."
    )
    return radar
