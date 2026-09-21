"""AtlasQuant Dashboard V1 — professional market overview.

Presentation and relative-strength radar for the G8 FX universe. It does not
turn ranking intensity into a probability and does not bypass the Safety Core
or the institutional execution gates.
"""
from __future__ import annotations

from html import escape
import math
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
            try:
                score=float(row["Pontuação_Final"])
            except Exception:
                raise ValueError(f"Pontuação inválida para {code}")
            if not math.isfinite(score):
                raise ValueError(f"Pontuação não finita para {code}")
            out[code] = score
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


def market_pulse_html(summary: dict[str, Any]) -> str:
    total=int(summary.get("total",0) or 0); directed=int(summary.get("directed",0) or 0); neutral=int(summary.get("neutral",0) or 0)
    pair=escape(str(summary.get("top_pair") or "—")); side=escape(str(summary.get("top_side") or "NEUTRO"))
    try: intensity=float(summary.get("top_intensity") or 0.0)
    except Exception: intensity=0.0
    return f"""<div class="aq-pulse">
<div><span class="aq-pulse-kicker">VISÃO DO MERCADO</span><strong>{directed}/{total}</strong><small>pares com viés</small></div>
<div><span>Maior desequilíbrio</span><strong>{pair}</strong><small>{side} · intensidade {intensity:.0f}/100</small></div>
<div><span>Neutros</span><strong>{neutral}</strong><small>aguardando vantagem relativa</small></div>
<div><span>Execução</span><strong>PROTEGIDA</strong><small>confirmação técnica obrigatória</small></div>
</div>"""

def focus_rows(radar: pd.DataFrame, top_n: int = 3) -> list[dict[str, Any]]:
    if radar is None or radar.empty:
        return []
    try:
        n=int(top_n)
        if isinstance(top_n,bool) or n<0:
            n=0
    except Exception:
        n=0
    rows = radar[radar["Direção macro"].isin(["COMPRA", "VENDA"])].head(n)
    out = []
    for _, row in rows.iterrows():
        out.append({
            "pair": str(row["Par"]),
            "side": str(row["Direção macro"]),
            "base_strength": float(row["Força base"]),
            "quote_strength": float(row["Força cotada"]),
            "difference": float(row["Diferença"]),
            "intensity": float(row["Intensidade relativa"]),
            "operational_state": "AGUARDAR CONFIRMAÇÃO",
        })
    return out


def focus_card_html(row: dict[str, Any]) -> str:
    pair = escape(str(row.get("pair", "—")))
    side = escape(str(row.get("side", "NEUTRO")).upper())
    state = escape(str(row.get("operational_state", "AGUARDAR CONFIRMAÇÃO")))
    try:
        base = float(row.get("base_strength", 0.0))
        quote = float(row.get("quote_strength", 0.0))
        diff = float(row.get("difference", 0.0))
        intensity = float(row.get("intensity", 0.0))
    except Exception:
        base = quote = diff = intensity = 0.0
    side_class = "buy" if side == "COMPRA" else "sell" if side == "VENDA" else "neutral"
    return f"""
<div class="aq-focus-card {side_class}">
  <div class="aq-focus-top">
    <span class="aq-focus-pair">{pair}</span>
    <span class="aq-focus-side">{side}</span>
  </div>
  <div class="aq-focus-score">{intensity:.0f}<span>/100</span></div>
  <div class="aq-focus-label">intensidade relativa</div>
  <div class="aq-focus-meta">
    <span>Base <b>{base:.1f}</b></span>
    <span>Cotada <b>{quote:.1f}</b></span>
    <span>Dif. <b>{diff:+.1f}</b></span>
  </div>
  <div class="aq-focus-state">🟡 {state}</div>
</div>
"""


DASHBOARD_CSS = """
<style>
.aq-pulse{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:9px;margin:4px 0 16px}
.aq-pulse>div{padding:13px 14px;border:1px solid rgba(137,170,210,.18);border-radius:13px;background:rgba(11,27,47,.66)}
.aq-pulse span,.aq-pulse small{display:block;color:#d4e1f0;font-size:.73rem;font-weight:650}
.aq-pulse strong{display:block;color:#edf4ff;font-size:1.02rem;margin:3px 0}
.aq-pulse-kicker{color:#6de2c5!important;font-weight:800;letter-spacing:.08em}
@media(max-width:760px){.aq-pulse{grid-template-columns:repeat(2,minmax(0,1fr))}.aq-focus-card{min-height:160px}}
.aq-focus-card{
  border:1px solid rgba(137,170,210,.18); border-radius:15px; padding:16px 17px;
  min-height:178px; background:linear-gradient(180deg,rgba(17,34,57,.88),rgba(10,24,41,.82));
  box-shadow:0 12px 30px rgba(0,0,0,.12); margin-bottom:8px;
}
.aq-focus-card.buy{border-top:3px solid #42d392}
.aq-focus-card.sell{border-top:3px solid #ff6b7a}
.aq-focus-card.neutral{border-top:3px solid #9fb0c6}
.aq-focus-top{display:flex;justify-content:space-between;align-items:center;gap:8px}
.aq-focus-pair{font-size:1.05rem;font-weight:800;color:#edf4ff}
.aq-focus-side{font-size:.72rem;font-weight:800;letter-spacing:.08em;color:#dceaff}
.aq-focus-score{font-size:2rem;font-weight:850;color:#edf4ff;margin-top:12px;line-height:1}
.aq-focus-score span{font-size:.82rem;color:#d4e1f0;font-weight:750}
.aq-focus-label{font-size:.74rem;color:#d4e1f0;font-weight:700;margin-top:4px}
.aq-focus-meta{display:flex;gap:12px;flex-wrap:wrap;margin-top:14px;color:#d4e1f0;font-size:.76rem;font-weight:650}
.aq-focus-meta b{color:#edf4ff}
.aq-focus-state{margin-top:14px;padding-top:10px;border-top:1px solid rgba(137,170,210,.14);font-size:.75rem;font-weight:750;color:#f2c14e}
</style>
"""


def render_focus_cards(radar: pd.DataFrame, top_n: int = 3) -> None:
    rows = focus_rows(radar, top_n=top_n)
    st.markdown(DASHBOARD_CSS, unsafe_allow_html=True)
    st.markdown("### 🎯 Melhores leituras macro agora")
    st.caption(
        "Ranking por desequilíbrio relativo. Estes cards indicam onde olhar primeiro; "
        "não são ordem de entrada. O timing permanece aguardando confirmação técnica."
    )
    if not rows:
        st.info("NÃO HÁ LEITURA DIRECIONAL SUFICIENTE AGORA.")
        return
    cols = st.columns(len(rows))
    for col, row in zip(cols, rows):
        with col:
            st.markdown(focus_card_html(row), unsafe_allow_html=True)


def render_g8_radar(ranking: pd.DataFrame, neutral_band: float = 5.0, top_n: int = 8) -> pd.DataFrame:
    radar = build_g8_radar(ranking, neutral_band=neutral_band)
    summary = radar_summary(radar)

    st.markdown(DASHBOARD_CSS + market_pulse_html(summary), unsafe_allow_html=True)

    mode = st.radio(
        "Visualização",
        ["Básico", "Pro"],
        horizontal=True,
        key="atlasquant_view_mode",
        help="Básico destaca o essencial. Pro abre a leitura completa dos 28 pares.",
    )
    render_focus_cards(radar, top_n=3)

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
    st.dataframe(shown, width="stretch", hide_index=True)

    if mode == "Pro":
        st.markdown("#### 🔎 Leitura completa")
        st.dataframe(radar, width="stretch", hide_index=True)
    else:
        with st.expander("Ver os 28 pares"):
            st.dataframe(radar, width="stretch", hide_index=True)

    st.info(
        "Fluxo operacional: força relativa → filtro macro/qualidade → Safety Core → "
        "confirmação ICT/SMC → plano. Sem confirmação suficiente, o estado continua AGUARDAR/NÃO OPERAR."
    )
    return radar
