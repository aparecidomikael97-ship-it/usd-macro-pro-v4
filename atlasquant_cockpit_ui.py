"""AtlasQuant cockpit UI shell.

This module is intentionally isolated from production routing. It defines the
approved visual/navigation contract and a render helper that can be wired into
Streamlit after AION/Core validation, without changing Core authority.
"""
from __future__ import annotations

from html import escape
from typing import Any, Mapping

MOTTO = "Poderoso por dentro. Simples por fora."

MODULE_CARDS = (
    {"id": "radar", "label": "Radar", "subtitle": "Visão de Mercado", "icon": "◎", "route": "/radar"},
    {"id": "macro", "label": "Macroeconomia", "subtitle": "Cenário Global", "icon": "▥", "route": "/macro"},
    {"id": "micro", "label": "Microeconomia", "subtitle": "Dados e Setores", "icon": "▤", "route": "/micro"},
    {"id": "geopolitica", "label": "Geopolítica", "subtitle": "Riscos e Cenários", "icon": "◉", "route": "/geopolitica"},
    {"id": "fundamentalista", "label": "Fundamentalista", "subtitle": "Análise de Ativos", "icon": "⌁", "route": "/fundamentalista"},
    {"id": "ict_smc", "label": "ICT / SMC", "subtitle": "Estrutura de Mercado", "icon": "◇", "route": "/ict-smc"},
    {"id": "calendario", "label": "Calendário Econômico", "subtitle": "Eventos e Indicadores", "icon": "▦", "route": "/calendario"},
    {"id": "pre_noticia", "label": "Pré-Notícia", "subtitle": "Sinais Antecipados", "icon": "≋", "route": "/pre-noticia"},
    {"id": "laboratorio", "label": "Backtests / Laboratório", "subtitle": "Valide Estratégias", "icon": "⚗", "route": "/laboratorio"},
    {"id": "paper", "label": "Paper Trading", "subtitle": "Simulador Profissional", "icon": "▣", "route": "/paper-trading"},
    {"id": "risco", "label": "Guardião de Risco", "subtitle": "Proteção e Consistência", "icon": "⬡", "route": "/guardiao-risco"},
    {"id": "investimentos", "label": "Investimentos", "subtitle": "Carteiras e Alocação", "icon": "▥", "route": "/investimentos"},
    {"id": "aion", "label": "Central AION", "subtitle": "Inteligência Integrada", "icon": "◌", "route": "/aion"},
    {"id": "admin", "label": "Administração", "subtitle": "Gestão do Ecossistema", "icon": "⚙", "route": "/admin"},
    {"id": "videos", "label": "Studio / Vídeos", "subtitle": "Conteúdo Premium", "icon": "▶", "route": "/videos"},
    {"id": "negocios", "label": "Negócios", "subtitle": "Oportunidades", "icon": "▧", "route": "/negocios"},
    {"id": "memoria", "label": "Memória / Checkpoint", "subtitle": "Histórico e Evolução", "icon": "⬢", "route": "/memoria"},
    {"id": "seguranca", "label": "Segurança", "subtitle": "Proteção Total", "icon": "⬟", "route": "/seguranca"},
    {"id": "academy", "label": "Academy", "subtitle": "Cursos e Tutoriais", "icon": "⌂", "route": "/academy"},
    {"id": "treasury", "label": "Treasury & Growth", "subtitle": "Caixa, Reserva e Crescimento", "icon": "◍", "route": "/treasury-growth"},
)

VIDEO_SURFACES = (
    {
        "id": "weekly_outlook",
        "label": "Análise da Semana",
        "schedule": "segunda_cedo",
        "format": "longo",
        "coverage": ("Forex", "Cripto", "Índices", "Macro"),
        "transparency": "cenarios_e_riscos",
    },
    {
        "id": "daily_outlook",
        "label": "Análise do Dia",
        "schedule": "segunda_a_sexta_cedo",
        "format": "curto",
        "coverage": ("Panorama", "Eventos", "Riscos", "Oportunidades"),
        "transparency": "expectativa_explicita",
    },
    {
        "id": "daily_close",
        "label": "Fechamento do Dia",
        "schedule": "segunda_a_sexta_fim_do_dia",
        "format": "curto",
        "coverage": ("Previsto", "Realizado", "Mudanças de Contexto"),
        "transparency": "comparar_previsto_realizado",
    },
    {
        "id": "weekly_close",
        "label": "Fechamento Semanal",
        "schedule": "sexta_fim_do_dia",
        "format": "completo",
        "coverage": ("Cenário de Segunda", "Resultado da Semana", "Acertos", "Erros", "Mudanças"),
        "transparency": "sem_maquiar_resultado",
    },
)

FLOATING_TABS = (
    "Visão Geral",
    "Análise da Semana",
    "Análise do Dia",
    "Fechamento do Dia",
    "Fechamento Semanal",
)

LAYOUT_ZONES = (
    "identity_and_status",
    "market_ticker",
    "floating_context_tabs",
    "video_command_deck",
    "ecosystem_module_grid",
    "holographic_global_core",
    "intelligence_panels",
    "bottom_action_dock",
)

FLOATING_PANELS = (
    {"id": "risk_map", "label": "Mapa de Risco Global", "surface": "geopolitics"},
    {"id": "market_bias", "label": "Viés Atual do Mercado", "surface": "market"},
    {"id": "economic_calendar", "label": "Calendário Econômico", "surface": "macro"},
    {"id": "live_news", "label": "Notícias em Tempo Real", "surface": "news"},
    {"id": "aion_voice", "label": "AION", "surface": "assistant"},
)

COCKPIT_CSS = r"""
<style>
:root {
  --aq-bg:#040817; --aq-panel:rgba(6,18,47,.82); --aq-line:#1bc8ff;
  --aq-violet:#9d4dff; --aq-cyan:#36e6ff; --aq-warm:#ff9d42; --aq-text:#eef8ff;
}
.aq-cockpit { background:radial-gradient(circle at 50% -10%,#133b7d 0,#07142d 38%,#030713 76%);
  color:var(--aq-text); border:1px solid rgba(54,230,255,.28); border-radius:24px;
  padding:18px; box-shadow:0 24px 90px rgba(0,0,0,.5), inset 0 0 70px rgba(27,200,255,.05);
  perspective:1200px; }
.aq-motto { text-align:center; font-size:clamp(20px,2.2vw,34px); font-weight:800; letter-spacing:.02em;
  text-shadow:0 0 22px rgba(54,230,255,.75); margin:2px 0 16px; }
.aq-tabs { display:flex; gap:10px; overflow-x:auto; padding:8px 4px 14px; position:sticky; top:0; z-index:8; }
.aq-tab { white-space:nowrap; padding:10px 16px; border:1px solid rgba(54,230,255,.6); border-radius:12px;
  background:linear-gradient(180deg,rgba(22,61,122,.9),rgba(6,18,47,.86)); box-shadow:0 9px 25px rgba(0,94,255,.22); }
.aq-grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(180px,1fr)); gap:14px; }
.aq-video-deck { display:grid; grid-template-columns:minmax(300px,2.1fr) repeat(3,minmax(180px,1fr)); gap:14px;
  margin:4px 0 18px; align-items:stretch; }
.aq-video-deck .aq-card:first-child { min-height:210px; }
.aq-panel-grid { display:grid; grid-template-columns:1.45fr 1fr 1fr; gap:14px; margin-top:18px; }
.aq-panel { min-height:150px; border-radius:18px; border:1px solid rgba(54,230,255,.42);
  background:linear-gradient(160deg,rgba(4,15,42,.94),rgba(11,27,66,.86));
  box-shadow:inset 0 0 30px rgba(54,230,255,.05),0 14px 30px rgba(0,0,0,.28); padding:16px; }
.aq-card { position:relative; min-height:120px; padding:16px; border-radius:18px; border:1px solid rgba(54,230,255,.5);
  background:linear-gradient(145deg,rgba(16,39,89,.94),rgba(8,12,35,.9)); box-shadow:0 16px 30px rgba(0,0,0,.3),
  0 0 24px rgba(50,154,255,.13); transform:translateZ(0); transition:transform .22s ease,box-shadow .22s ease,border-color .22s ease; }
.aq-card:hover { transform:translateY(-7px) rotateX(1.5deg); border-color:#d85cff;
  box-shadow:0 22px 40px rgba(0,0,0,.38),0 0 28px rgba(157,77,255,.32); }
.aq-icon { font-size:34px; color:var(--aq-cyan); filter:drop-shadow(0 0 12px rgba(54,230,255,.7)); }
.aq-label { font-size:18px; font-weight:800; margin-top:10px; } .aq-sub { opacity:.78; font-size:13px; }
.aq-video { border-color:rgba(255,157,66,.55); }
.aq-video .aq-icon { color:#ffb15b; filter:drop-shadow(0 0 12px rgba(255,157,66,.55)); }
.aq-holo { margin-top:18px; min-height:220px; border-radius:50% 50% 20px 20px; display:grid; place-items:center;
  background:radial-gradient(circle,rgba(54,230,255,.26),rgba(54,230,255,.06) 38%,transparent 64%);
  border-top:1px solid rgba(54,230,255,.45); color:#bff8ff; letter-spacing:.18em; text-transform:uppercase; }
@media (max-width:1100px){ .aq-video-deck,.aq-panel-grid{grid-template-columns:1fr 1fr;} }
@media (max-width:720px){ .aq-video-deck,.aq-panel-grid{grid-template-columns:1fr;} }
@media (prefers-reduced-motion:reduce){ .aq-card{transition:none}.aq-card:hover{transform:none} }
</style>
"""


def cockpit_contract() -> dict[str, Any]:
    """Serializable contract for the approved shell."""
    return {
        "motto": MOTTO,
        "modules": [dict(row) for row in MODULE_CARDS],
        "videos": [dict(row) for row in VIDEO_SURFACES],
        "floating_tabs": list(FLOATING_TABS),
        "layout_zones": list(LAYOUT_ZONES),
        "floating_panels": [dict(row) for row in FLOATING_PANELS],
        "routes": {row["id"]: row["route"] for row in MODULE_CARDS},
        "style": "spaceship_cockpit_hangar_digital",
        "principle": "deep_inside_simple_outside",
        "production_wired": False,
    }


def _card_html(row: Mapping[str, Any], *, video: bool = False) -> str:
    kind = " aq-video" if video else ""
    return (
        f'<div class="aq-card{kind}" data-module="{escape(str(row.get("id") or ""))}" '
        f'data-route="{escape(str(row.get("route") or ""))}">'
        f'<div class="aq-icon">{escape(str(row.get("icon") or ("▶" if video else "◇")))}</div>'
        f'<div class="aq-label">{escape(str(row.get("label") or ""))}</div>'
        f'<div class="aq-sub">{escape(str(row.get("subtitle") or row.get("schedule") or ""))}</div>'
        "</div>"
    )


def cockpit_html() -> str:
    module_html = "".join(_card_html(row) for row in MODULE_CARDS)
    video_html = "".join(_card_html(row, video=True) for row in VIDEO_SURFACES)
    tabs = "".join(f'<div class="aq-tab">{escape(tab)}</div>' for tab in FLOATING_TABS)
    panels = "".join(
        '<div class="aq-panel">'
        f'<div class="aq-label">{escape(str(row["label"]))}</div>'
        f'<div class="aq-sub">{escape(str(row["surface"]))}</div>'
        '</div>'
        for row in FLOATING_PANELS
    )
    return (
        COCKPIT_CSS
        + '<section class="aq-cockpit">'
        + f'<div class="aq-motto">{escape(MOTTO)}</div>'
        + f'<div class="aq-tabs">{tabs}</div>'
        + '<h3>Comando de Mercado & Vídeos</h3>'
        + f'<div class="aq-video-deck">{video_html}</div>'
        + f'<div class="aq-grid">{module_html}</div>'
        + '<div class="aq-holo">AtlasQuant · Central AION · Visão Global</div>'
        + f'<div class="aq-panel-grid">{panels}</div>'
        + "</section>"
    )


def render_cockpit_shell(st_module: Any) -> None:
    """Render the isolated cockpit shell through a Streamlit-like object."""
    st_module.markdown(cockpit_html(), unsafe_allow_html=True)


__all__ = [
    "MOTTO", "MODULE_CARDS", "VIDEO_SURFACES", "FLOATING_TABS",
    "LAYOUT_ZONES", "FLOATING_PANELS",
    "COCKPIT_CSS", "cockpit_contract", "cockpit_html", "render_cockpit_shell",
]
