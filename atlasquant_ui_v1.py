"""AtlasQuant UI V1 — professional presentation layer.

This module is presentation-only: no market calculation, API collection or
execution rule is changed here. It can be removed without changing the engine.
"""
from __future__ import annotations

from html import escape
import math
import streamlit as st

UI_VERSION = "0.9"

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

NAVIGATION_GROUPS = (
    ("Operação", ("🎯 Central", "🧭 Painel mestre", "⚡ Decisão", "🗺️ Market Map")),
    ("Mercado", ("💱 Moedas", "🇺🇸 EUA", "🔀 Pares", "🏦 Fed", "📰 Notícias")),
    ("Pesquisa", ("🗂️ Histórico", "🧪 Backtest", "🎙️ Macro Briefing", "🎓 Aprender")),
    ("Sistema", ("🤖 Autopilot", "🧩 Produto", "🛠️ Melhorias")),
    ("Conta", ("👤 Conta", "📱 Instalar", "💼 Vendas")),
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
.aq-section-title {display:flex;align-items:center;gap:9px;margin:1.15rem 0 .55rem;color:var(--aq-text);font-size:1.02rem;font-weight:800}
.aq-section-title:after {content:"";height:1px;flex:1;background:linear-gradient(90deg,var(--aq-line),transparent)}
.aq-state {display:inline-flex;align-items:center;gap:6px;border-radius:999px;padding:5px 9px;font-size:.7rem;font-weight:800;border:1px solid var(--aq-line)}
.aq-state-good{color:var(--aq-good);background:rgba(66,211,146,.08)}
.aq-state-warn{color:var(--aq-warn);background:rgba(242,193,78,.08)}
.aq-state-bad{color:var(--aq-bad);background:rgba(255,107,122,.08)}
.aq-state-info{color:var(--aq-accent);background:rgba(79,163,255,.08)}
.aq-decision-strip{display:grid;grid-template-columns:1fr 1fr 2fr 1fr 1fr;gap:8px;margin:5px 0 14px}
.aq-decision-strip>div{padding:11px 12px;border:1px solid var(--aq-line);border-radius:12px;background:rgba(11,27,47,.64)}
.aq-decision-strip span{display:block;color:var(--aq-muted);font-size:.64rem;font-weight:800;letter-spacing:.08em}
.aq-decision-strip strong{display:block;color:var(--aq-text);font-size:.88rem;margin-top:3px;overflow-wrap:anywhere}
.aq-focus{display:grid;grid-template-columns:1.35fr repeat(3,minmax(0,.72fr));gap:8px;margin:8px 0 12px}
.aq-focus-main,.aq-focus-card{border:1px solid var(--aq-line);border-radius:14px;background:linear-gradient(180deg,rgba(17,39,66,.88),rgba(9,24,43,.78));padding:10px 12px;min-width:0}
.aq-focus-main small,.aq-focus-card small{display:block;color:var(--aq-muted);font-size:.66rem;text-transform:uppercase;letter-spacing:.08em;margin-bottom:3px}
.aq-focus-main strong{display:block;color:var(--aq-text);font-size:.98rem;line-height:1.2}
.aq-focus-main span,.aq-focus-card span{display:block;color:var(--aq-muted);font-size:.72rem;line-height:1.25;margin-top:3px}
.aq-focus-card strong{display:block;color:var(--aq-text);font-size:.78rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.aq-nav-groups{display:flex;gap:7px;align-items:center;overflow-x:auto;scrollbar-width:none;margin:2px 0 9px;padding:2px 1px}
.aq-nav-groups::-webkit-scrollbar{display:none}
.aq-nav-group{flex:0 0 auto;border:1px solid var(--aq-line);border-radius:999px;padding:5px 9px;background:rgba(10,25,44,.56)}
.aq-nav-group strong{color:var(--aq-text);font-size:.69rem}
.aq-nav-group span{color:var(--aq-muted);font-size:.64rem;margin-left:5px}
.aq-nav-groups:before{content:"NAVEGAÇÃO";flex:0 0 auto;color:var(--aq-muted);font-size:.58rem;font-weight:800;letter-spacing:.09em;margin-right:1px}
.aq-context-strip{
  display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px;margin:0 0 14px;
}
.aq-context-strip>div{
  border:1px solid var(--aq-line);border-radius:12px;padding:10px 12px;
  background:linear-gradient(180deg,rgba(15,31,52,.78),rgba(9,23,40,.72));
}
.aq-context-strip span{display:block;color:#9fb0c6;font-size:.62rem;font-weight:800;letter-spacing:.08em}
.aq-context-strip strong{display:block;color:#edf4ff;font-size:.82rem;margin-top:3px;overflow-wrap:anywhere}
[data-testid="stMetric"] {
  background: linear-gradient(180deg, rgba(17,34,57,.80), rgba(11,25,43,.72));
  border: 1px solid var(--aq-line) !important;
  border-radius: 13px !important;
}
[data-testid="stMetric"] > div { padding: .15rem .2rem; }
[data-testid="stMetricValue"] { letter-spacing: -.035em; color: var(--aq-text); }
[data-testid="stMetricLabel"] { color: var(--aq-muted); font-size: .78rem; }
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
  border: 1px solid var(--ux-border, var(--aq-line)) !important;
  background: var(--ux-card, rgba(12,26,44,.48)) !important;
  border-radius: 12px !important;
  overflow: hidden;
}
[data-testid="stExpander"] details > summary {
  background: var(--ux-card, rgba(12,26,44,.48)) !important;
  color: var(--ux-text, var(--aq-text)) !important;
  min-height: 2.75rem;
}
[data-testid="stTabs"] [role="tablist"] {
  padding: 5px;
  background: rgba(8,20,35,.82);
  border: 1px solid var(--aq-line);
  border-radius: 12px;
  display: flex;
  flex-wrap: nowrap;
  overflow-x: auto;
  overscroll-behavior-inline: contain;
  scrollbar-width: none;
  position: sticky;
  top: .2rem;
  z-index: 990;
  backdrop-filter: blur(12px);
}
[data-testid="stTabs"] [role="tablist"]::-webkit-scrollbar { display:none; }
[data-testid="stTabs"] [role="tab"] {
  border-radius: 8px !important;
  flex: 0 0 auto;
  white-space: nowrap;
  min-height: 2.25rem;
  color: #b9c9dc !important;
  font-weight: 650;
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
  .aq-section-title { font-size:.94rem; margin-top:.9rem; }
  .aq-decision-strip{grid-template-columns:repeat(2,minmax(0,1fr))}
  .aq-decision-strip .wide{grid-column:1/-1}
  .aq-context-strip{grid-template-columns:repeat(2,minmax(0,1fr))}
  .aq-focus{grid-template-columns:1fr 1fr}
  .aq-focus-main{grid-column:1/-1}
  .aq-nav-groups{margin-left:-.15rem;margin-right:-.15rem;position:sticky;top:0;z-index:20;padding:6px 4px;background:linear-gradient(180deg,rgba(5,16,30,.96),rgba(5,16,30,.84));backdrop-filter:blur(8px)}
  .aq-nav-groups:before{display:none}
  .aq-nav-group span{display:none}
  .aq-nav-group{padding:5px 8px}
  .aq-focus-main,.aq-focus-card{padding:9px 10px}
  [data-testid="stSidebar"] { min-width: 280px; }
  [data-testid="stTabs"] [role="tablist"] { margin-left:-.25rem; margin-right:-.25rem; border-radius:10px; }
  [data-testid="stTabs"] [role="tab"] { font-size:.74rem; padding-left:.55rem; padding-right:.55rem; min-height:34px; }
  [data-testid="stTabs"] [role="tablist"] { scrollbar-width:none; }
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


def navigation_groups() -> tuple[tuple[str, tuple[str, ...]], ...]:
    """Presentation-only grouping; every existing endpoint remains available."""
    return NAVIGATION_GROUPS


def navigation_groups_html() -> str:
    parts=[]
    for name, items in NAVIGATION_GROUPS:
        label=escape(str(name))
        count=len(items)
        parts.append(
            f'<div class="aq-nav-group"><strong>{label}</strong>'
            f'<span>{count} áreas</span></div>'
        )
    return '<div class="aq-nav-groups" aria-label="Grupos de navegação">'+"".join(parts)+"</div>"


def operation_focus_html(
    *,
    decision: str = "Aguardando leitura",
    market: str = "Contexto em atualização",
    data: str = "Qualidade monitorada",
    safety: str = "Safety Core ativo",
) -> str:
    """Compact decision-first orientation strip; presentation only."""
    return (
        '<div class="aq-focus">'
        '<div class="aq-focus-main"><small>Agora</small>'
        f'<strong>{escape(str(decision))}</strong>'
        '<span>Decisão primeiro; detalhes e evidências abaixo.</span></div>'
        '<div class="aq-focus-card"><small>Mercado</small>'
        f'<strong>{escape(str(market))}</strong><span>Macro + técnico</span></div>'
        '<div class="aq-focus-card"><small>Dados</small>'
        f'<strong>{escape(str(data))}</strong><span>Frescor e cobertura</span></div>'
        '<div class="aq-focus-card"><small>Proteção</small>'
        f'<strong>{escape(str(safety))}</strong><span>Veto independente</span></div>'
        '</div>'
    )


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



def section_title_html(title: str, icon: str = "") -> str:
    return f'<div class="aq-section-title"><span>{escape(str(icon))}</span><span>{escape(str(title))}</span></div>'

def state_badge_html(label: str, tone: str = "info") -> str:
    safe_tone=tone if tone in {"good","warn","bad","info"} else "info"
    return f'<span class="aq-state aq-state-{safe_tone}">{escape(str(label))}</span>'



def context_strip_html(
    fed_tone: str,
    fed_strength: float | int | None,
    data_quality: str,
    environment: str,
) -> str:
    tone=escape(str(fed_tone or "Neutro"))
    quality=escape(str(data_quality or "—"))
    env=escape(str(environment or "LOCAL").upper())
    try:
        strength=float(fed_strength)
        strength_text=f"{strength:+.2f}" if math.isfinite(strength) else "—"
    except Exception:
        strength_text="—"
    return f"""<div class="aq-context-strip">
      <div><span>FED NARRATIVO</span><strong>{tone}</strong></div>
      <div><span>INTENSIDADE FED</span><strong>{strength_text}</strong></div>
      <div><span>QUALIDADE USD</span><strong>{quality}</strong></div>
      <div><span>AMBIENTE</span><strong>{env}</strong></div>
    </div>"""



def decision_strip_html(pair: str, direction: str, decision: str, timing: str, quality: float | int | None = None) -> str:
    p=escape(str(pair or "—")); d=escape(str(direction or "WAIT")); dec=escape(str(decision or "AGUARDAR")); t=escape(str(timing or "—"))
    try:
        q=float(quality)
        q_text=f"{max(0.0,min(100.0,q)):.0f}%" if math.isfinite(q) else "—"
    except Exception:
        q_text="—"
    return f"""<div class="aq-decision-strip">
      <div><span>PAR</span><strong>{p}</strong></div>
      <div><span>DIREÇÃO MACRO</span><strong>{d}</strong></div>
      <div class="wide"><span>ESTADO</span><strong>{dec}</strong></div>
      <div><span>TIMING</span><strong>{t}</strong></div>
      <div><span>QUALIDADE</span><strong>{q_text}</strong></div>
    </div>"""


def apply_atlasquant_theme() -> None:
    st.markdown(ATLASQUANT_CSS, unsafe_allow_html=True)


def render_atlasquant_header(app_version: str, environment: str = "LOCAL") -> None:
    st.markdown(hero_html(app_version, environment), unsafe_allow_html=True)
