"""AtlasQuant UI V1 — professional presentation layer.

This module is presentation-only: no market calculation, API collection or
execution rule is changed here. It can be removed without changing the engine.
"""
from __future__ import annotations

from html import escape
import math
import streamlit as st

UI_VERSION = "0.3"

NAVIGATION_LABELS = (
    "🎯 Central",
    "🧭 Painel mestre",
    "💱 Moedas",
    "🇺🇸 EUA",
    "🔀 Pares",
    "🏦 Fed",
    "🗂️ Histórico",
    "🧪 Backtest",
    "⚡ Decisão",
    "🗺️ Market Map",
    "🎙️ Macro Briefing",
    "🎓 Aprender",
    "🧩 Produto",
    "🛠️ Melhorias",
    "📰 Notícias",
    "🤖 Autopilot",
    "👤 Conta",
    "📱 Instalar",
    "💼 Vendas",
)

ATLASQUANT_CSS = r"""
<style>
:root {
  --aq-bg: #07111f;
  --aq-panel: rgba(14, 28, 48, .78);
  --aq-panel-2: rgba(18, 38, 64, .74);
  --aq-line: rgba(137, 170, 210, .18);
  --aq-text: #edf4ff;
  --aq-muted: #9fb0c6;
  --aq-accent: #4fa3ff;
  --aq-accent-2: #6de2c5;
  --aq-good: #42d392;
  --aq-warn: #f2c14e;
  --aq-bad: #ff6b7a;
}
html { scroll-behavior: smooth; }
.stApp {
  background:
    radial-gradient(circle at 8% -10%, rgba(36, 111, 190, .17), transparent 28%),
    radial-gradient(circle at 88% 2%, rgba(48, 174, 150, .10), transparent 24%),
    linear-gradient(180deg, #081321 0%, #07101d 100%);
}
.stMainBlockContainer { max-width: 1500px; padding-top: 1.15rem; padding-bottom: 2.4rem; }
[data-testid="stSidebar"] {
  background: linear-gradient(180deg, rgba(8,18,32,.98), rgba(9,22,38,.98));
  border-right: 1px solid var(--aq-line);
}
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p { color: var(--aq-muted); }
[data-testid="stSidebar"] [role="radiogroup"] label,
[data-testid="stSidebar"] [data-baseweb="select"] { border-radius: 10px; }
[data-testid="stHeader"] { background: rgba(7,17,31,.76); backdrop-filter: blur(12px); }
.aq-hero {
  position: relative;
  overflow: hidden;
  border: 1px solid var(--aq-line);
  border-radius: 18px;
  padding: 22px 24px 20px;
  margin: 4px 0 15px;
  background:
    linear-gradient(120deg, rgba(20,49,82,.92), rgba(10,25,44,.94) 58%, rgba(10,42,49,.88));
  box-shadow: 0 18px 48px rgba(0,0,0,.20);
}
.aq-hero:after {
  content: "";
  position: absolute;
  width: 280px; height: 280px;
  right: -110px; top: -155px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(79,163,255,.22), transparent 68%);
  pointer-events: none;
}
.aq-kicker {
  color: var(--aq-accent-2);
  font-size: .72rem;
  font-weight: 800;
  letter-spacing: .16em;
  text-transform: uppercase;
  margin-bottom: 7px;
}
.aq-title {
  color: var(--aq-text);
  font-size: clamp(1.65rem, 3vw, 2.45rem);
  font-weight: 800;
  letter-spacing: -.045em;
  line-height: 1.05;
  margin: 0;
}
.aq-subtitle {
  color: var(--aq-muted);
  font-size: .92rem;
  margin-top: 8px;
  max-width: 760px;
}
.aq-badges {
  display: flex;
  flex-wrap: wrap;
  gap: 7px;
  margin-top: 14px;
}
.aq-badge {
  border: 1px solid rgba(148,183,225,.20);
  border-radius: 999px;
  padding: 5px 10px;
  color: #dceaff;
  background: rgba(9,22,38,.52);
  font-size: .73rem;
  font-weight: 650;
}
.aq-dev { color: #f2c14e; border-color: rgba(242,193,78,.34); }
[data-testid="stMetric"] {
  background: linear-gradient(180deg, rgba(17,34,57,.80), rgba(11,25,43,.72));
  border: 1px solid var(--aq-line) !important;
  border-radius: 13px !important;
}
[data-testid="stMetricValue"] { letter-spacing: -.035em; color: var(--aq-text); }
[data-testid="stMetricLabel"] { color: var(--aq-muted); }
[data-testid="stButton"] button {
  border-radius: 10px; min-height: 2.45rem; font-weight: 700;
  border: 1px solid var(--aq-line);
}
[data-testid="stButton"] button[kind="primary"] {
  box-shadow: 0 8px 24px rgba(79,163,255,.16);
}
[data-testid="stDataFrame"] {
  border: 1px solid var(--aq-line);
  border-radius: 12px;
  overflow: hidden;
}
[data-testid="stAlert"] { border-radius: 12px; }
[data-testid="stTextInput"] input,
[data-testid="stNumberInput"] input,
[data-baseweb="select"] > div { border-radius: 10px !important; }
[data-testid="stExpander"] {
  border: 1px solid var(--aq-line) !important;
  background: rgba(12,26,44,.48);
}
[data-testid="stTabs"] [role="tablist"] {
  padding: 5px;
  background: rgba(8,20,35,.74);
  border: 1px solid var(--aq-line);
  border-radius: 12px;
}
[data-testid="stTabs"] [role="tab"] {
  border-radius: 8px !important;
}
[data-testid="stTabs"] [role="tab"][aria-selected="true"] {
  background: rgba(79,163,255,.16) !important;
  color: #f4f8ff !important;
}
@media (max-width: 760px) {
  .stMainBlockContainer { padding-left: .85rem; padding-right: .85rem; padding-top: .7rem; }
  [data-testid="stHorizontalBlock"] { flex-wrap: wrap !important; gap: .55rem !important; }
  [data-testid="stColumn"] { min-width: 150px !important; flex: 1 1 150px !important; }
  .aq-hero { padding: 18px 16px 16px; border-radius: 14px; }
  .aq-subtitle { font-size: .84rem; }
  .aq-badge { font-size: .68rem; padding: 4px 8px; }
}
</style>
"""


def score_semantics(value: float | int | None) -> dict[str, str]:
    """Presentation-only band. It is never a probability or trade approval."""
    try:
        score = float(value)
    except Exception:
        return {"label": "SEM DADO", "tone": "neutral"}
    if not math.isfinite(score):
        return {"label": "SEM DADO", "tone": "neutral"}
    score = max(0.0, min(100.0, score))
    if score >= 75:
        return {"label": "FORTE", "tone": "good"}
    if score >= 55:
        return {"label": "MODERADO", "tone": "info"}
    if score >= 45:
        return {"label": "NEUTRO", "tone": "neutral"}
    if score >= 25:
        return {"label": "FRACO", "tone": "warn"}
    return {"label": "MUITO FRACO", "tone": "bad"}


def navigation_labels() -> tuple[str, ...]:
    return NAVIGATION_LABELS


def hero_html(app_version: str, environment: str = "LOCAL") -> str:
    version = escape(str(app_version))
    env = escape(str(environment).upper())
    return f"""
<div class="aq-hero">
  <div class="aq-kicker">Market Intelligence Platform</div>
  <div class="aq-title">ATLASQUANT</div>
  <div class="aq-subtitle">
    Macro • Quant • Smart Money • AI — direção, qualidade dos dados, timing e risco em uma única leitura.
  </div>
  <div class="aq-badges">
    <span class="aq-badge aq-dev">{env}</span>
    <span class="aq-badge">Engine base {version}</span>
    <span class="aq-badge">Safety Core</span>
    <span class="aq-badge">Fail-closed</span>
    <span class="aq-badge">Auditável</span>
  </div>
</div>
"""


def apply_atlasquant_theme() -> None:
    st.markdown(ATLASQUANT_CSS, unsafe_allow_html=True)


def render_atlasquant_header(app_version: str, environment: str = "LOCAL") -> None:
    st.markdown(hero_html(app_version, environment), unsafe_allow_html=True)
