"""AtlasQuant premium presentation shell.

Visual catalog and design tokens only. Cards navigate to pages that already
exist. This module does not calculate markets, authorize trades, read secrets
or change authentication.
"""
from __future__ import annotations

from html import escape
from typing import Any, Mapping, Sequence

import streamlit as st

from atlasquant_ui_v1 import BEGINNER_OPEN_AREAS

SCHEMA = "ATLASQUANT_PREMIUM_SHELL_V1"
_PENDING_KEY = "atlasquant_premium_nav_target"

# Own palette. Deep ink, warm brass and restrained tide — not a borrowed identity.
TOKENS = {
    "ink": "#07111f",
    "ink_2": "#0c1a2c",
    "surface": "#102338",
    "surface_2": "#17304a",
    "line": "rgba(198, 214, 232, .22)",
    "brass": "#d7b56d",
    "tide": "#8fd0c4",
    "text": "#f5f8fc",
    "text_soft": "#d7e4f2",
    "good": "#3dbe8b",
    "warn": "#e2b657",
    "danger": "#e36b78",
    "info": "#8eb7e8",
}

PREMIUM_CSS = """
<style>
.aq-premium{max-width:100%;overflow-x:hidden;color:#f5f8fc}
.aq-premium-hero{position:relative;overflow:hidden;border:1px solid rgba(198,214,232,.22);border-radius:22px;padding:22px 22px 18px;margin:4px 0 16px;background:
  radial-gradient(circle at 100% 0%, rgba(215,181,109,.16), transparent 34%),
  linear-gradient(145deg, #12283f 0%, #0c1a2c 58%, #10261f 100%);
  box-shadow:0 18px 40px rgba(0,0,0,.28)}
.aq-premium-hero small{display:block;color:#d7b56d;font-weight:800;letter-spacing:.14em;font-size:.68rem}
.aq-premium-hero h2{margin:.35rem 0 .4rem;color:#f5f8fc;font-size:1.72rem;line-height:1.15;font-weight:760}
.aq-premium-hero p{margin:0;max-width:68ch;color:#d7e4f2;font-size:.95rem;line-height:1.45;font-weight:650}
.aq-premium-sector{margin:8px 0 18px}
.aq-premium-sector h3{margin:0 0 10px;color:#f5f8fc;font-size:1.02rem;font-weight:760}
.aq-premium-grid{display:grid;grid-template-columns:1fr;gap:12px}
.aq-premium-card{min-width:0;border:1px solid rgba(198,214,232,.22);border-radius:18px;padding:14px 14px 12px;background:linear-gradient(180deg,rgba(23,48,74,.96),rgba(12,26,44,.94));box-shadow:0 10px 24px rgba(0,0,0,.18);animation:aq-rise .5s ease both}
.aq-premium-card:hover{border-color:rgba(215,181,109,.55);transform:translateY(-2px)}
.aq-premium-card:focus-within{outline:2px solid #d7b56d;outline-offset:3px}
.aq-premium-art{height:74px;border-radius:14px;margin-bottom:10px;background:#0c1a2c;overflow:hidden}
.aq-premium-art svg{width:100%;height:74px;display:block}
.aq-premium-kicker{margin:0;color:#d7b56d;font-size:.68rem;font-weight:800;letter-spacing:.08em;text-transform:uppercase}
.aq-premium-card h4{margin:.2rem 0 .35rem;color:#f5f8fc;font-size:1.12rem;line-height:1.2}
.aq-premium-card p{margin:0;color:#d7e4f2;font-size:.86rem;line-height:1.4;font-weight:650}
.aq-premium-meta{display:flex;flex-wrap:wrap;gap:6px;margin-top:10px}
.aq-badge{display:inline-flex;align-items:center;border-radius:999px;padding:3px 8px;font-size:.72rem;font-weight:800;border:1px solid transparent}
.aq-badge.info{color:#f5f8fc;background:#1d4e89;border-color:#8eb7e8}
.aq-badge.good{color:#f5f8fc;background:#145c40;border-color:#3dbe8b}
.aq-badge.warn{color:#1a1408;background:#e2b657;border-color:#f3deaa}
.aq-badge.danger{color:#fff7f8;background:#8d3140;border-color:#e36b78}
.aq-badge.neutral{color:#f5f8fc;background:#24384f;border-color:#d7e4f2}
.aq-panel{border:1px solid rgba(198,214,232,.22);border-radius:16px;padding:14px 16px;background:#102338;color:#f5f8fc;margin:8px 0 12px}
.aq-panel h3,.aq-panel h4{margin:0 0 6px;color:#f5f8fc}
.aq-panel p,.aq-panel li{color:#d7e4f2;font-weight:650}
.aq-metric{border-radius:14px;padding:10px 12px;background:#17304a;border:1px solid rgba(198,214,232,.2);min-width:0}
.aq-metric small{display:block;color:#d7e4f2;font-weight:750;font-size:.72rem}
.aq-metric strong{display:block;margin-top:3px;color:#f5f8fc;font-size:1.05rem}
.aq-alert{border-radius:12px;padding:10px 12px;margin:8px 0;font-weight:700}
.aq-alert.info{background:#16324f;color:#f5f8fc;border:1px solid #8eb7e8}
.aq-alert.good{background:#12382c;color:#f5f8fc;border:1px solid #3dbe8b}
.aq-alert.warn{background:#3a3118;color:#f8f1dc;border:1px solid #e2b657}
.aq-alert.danger{background:#3d1c24;color:#fff5f6;border:1px solid #e36b78}
.aq-empty,.aq-loading{border:1px dashed rgba(215,228,242,.45);border-radius:14px;padding:14px;color:#d7e4f2;background:#0e1c30}
.aq-radar-live{display:inline-flex;align-items:center;gap:8px;color:#d7e4f2;font-size:.75rem;font-weight:800;margin-top:8px}
.aq-radar-dot{width:8px;height:8px;border-radius:50%;background:#8fd0c4;box-shadow:0 0 0 0 rgba(143,208,196,.6);animation:aq-ping 2.8s ease-out infinite}
.aq-master-rail{display:grid;grid-template-columns:1fr;gap:8px;margin:8px 0 12px}
.aq-master-rail div{border-radius:12px;padding:8px 10px;background:#102338;border:1px solid rgba(198,214,232,.2);color:#f5f8fc;font-size:.78rem;font-weight:750}
.aq-master-rail strong{display:block;color:#d7b56d;font-size:.68rem;letter-spacing:.06em;text-transform:uppercase}
.stApp a{color:#d6e8ff;text-decoration:underline;text-underline-offset:2px;font-weight:750}
.stApp button:focus-visible,.stApp [role="tab"]:focus-visible,.stApp a:focus-visible{outline:2px solid #d7b56d;outline-offset:2px}
.stApp [data-testid="stButton"] button:disabled{color:#d7e4f2 !important;-webkit-text-fill-color:#d7e4f2 !important;background:#1c3048 !important;opacity:1 !important;border-color:rgba(215,181,109,.4) !important}
@media (min-width:760px){.aq-premium-grid{grid-template-columns:1fr 1fr}.aq-master-rail{grid-template-columns:1fr 1fr 1fr}}
@media (min-width:1200px){.aq-premium-grid{grid-template-columns:1fr 1fr 1fr}}
@media (max-width:760px){.aq-premium-hero{padding:16px}.aq-premium-hero h2{font-size:1.35rem}.aq-premium-card:hover{transform:none}}
@keyframes aq-rise{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:none}}
@keyframes aq-ping{0%{box-shadow:0 0 0 0 rgba(143,208,196,.55)}100%{box-shadow:0 0 0 10px rgba(143,208,196,0)}}
@media (prefers-reduced-motion:reduce){
  .aq-premium-card,.aq-radar-dot{animation:none !important}
  .aq-premium-card:hover{transform:none}
}
</style>
"""


def _svg(kind: str) -> str:
    """Original abstract marks. No external asset and no borrowed logo."""
    common = {
        "radar": (
            '<svg viewBox="0 0 320 74" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">'
            '<rect width="320" height="74" fill="#0c1a2c"/>'
            '<circle cx="64" cy="37" r="22" fill="none" stroke="#8fd0c4" stroke-width="1.4"/>'
            '<circle cx="64" cy="37" r="12" fill="none" stroke="#d7b56d" stroke-width="1.2"/>'
            '<path d="M64 37 L84 22" stroke="#f5f8fc" stroke-width="1.4"/>'
            '<circle cx="150" cy="28" r="3" fill="#8fd0c4"/><circle cx="188" cy="46" r="3" fill="#d7b56d"/>'
            '<circle cx="230" cy="24" r="3" fill="#8eb7e8"/><path d="M120 52 H280" stroke="#d7e4f2" stroke-width="1" opacity=".7"/>'
            '</svg>'
        ),
        "command": (
            '<svg viewBox="0 0 320 74" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">'
            '<rect width="320" height="74" fill="#0c1a2c"/>'
            '<rect x="18" y="16" width="70" height="42" rx="8" fill="none" stroke="#d7b56d"/>'
            '<rect x="100" y="16" width="90" height="18" rx="6" fill="#17304a" stroke="#8eb7e8"/>'
            '<rect x="100" y="40" width="90" height="18" rx="6" fill="#17304a" stroke="#8fd0c4"/>'
            '<rect x="204" y="16" width="96" height="42" rx="8" fill="none" stroke="#d7e4f2"/>'
            '</svg>'
        ),
        "macro": (
            '<svg viewBox="0 0 320 74" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">'
            '<rect width="320" height="74" fill="#0c1a2c"/>'
            '<path d="M16 54 C70 50 80 22 130 24 C180 26 190 48 240 40 C270 35 290 28 306 22" fill="none" stroke="#d7b56d" stroke-width="1.6"/>'
            '<circle cx="130" cy="24" r="3" fill="#f5f8fc"/><circle cx="240" cy="40" r="3" fill="#8fd0c4"/>'
            '</svg>'
        ),
        "micro": (
            '<svg viewBox="0 0 320 74" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">'
            '<rect width="320" height="74" fill="#0c1a2c"/>'
            '<rect x="24" y="40" width="18" height="18" fill="#8eb7e8"/><rect x="50" y="28" width="18" height="30" fill="#d7b56d"/>'
            '<rect x="76" y="34" width="18" height="24" fill="#8fd0c4"/><path d="M120 50 H300" stroke="#d7e4f2"/>'
            '</svg>'
        ),
        "geo": (
            '<svg viewBox="0 0 320 74" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">'
            '<rect width="320" height="74" fill="#0c1a2c"/>'
            '<ellipse cx="150" cy="37" rx="70" ry="24" fill="none" stroke="#8eb7e8"/>'
            '<path d="M90 37 H210 M150 14 V60" stroke="#d7e4f2" stroke-width=".8"/>'
            '<circle cx="168" cy="30" r="3" fill="#e2b657"/>'
            '</svg>'
        ),
        "fundamental": (
            '<svg viewBox="0 0 320 74" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">'
            '<rect width="320" height="74" fill="#0c1a2c"/>'
            '<rect x="28" y="18" width="120" height="40" rx="6" fill="none" stroke="#d7b56d"/>'
            '<path d="M40 46 H70 M40 36 H96 M40 26 H84" stroke="#d7e4f2"/>'
            '<circle cx="220" cy="37" r="16" fill="none" stroke="#8fd0c4"/>'
            '</svg>'
        ),
        "calendar": (
            '<svg viewBox="0 0 320 74" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">'
            '<rect width="320" height="74" fill="#0c1a2c"/>'
            '<rect x="28" y="16" width="92" height="44" rx="6" fill="none" stroke="#d7b56d"/>'
            '<path d="M28 30 H120" stroke="#d7b56d"/><circle cx="48" cy="42" r="3" fill="#8fd0c4"/>'
            '<circle cx="68" cy="42" r="3" fill="#8eb7e8"/><circle cx="88" cy="42" r="3" fill="#e2b657"/>'
            '</svg>'
        ),
        "news": (
            '<svg viewBox="0 0 320 74" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">'
            '<rect width="320" height="74" fill="#0c1a2c"/>'
            '<path d="M40 18 H150 V56 H40 Z" fill="none" stroke="#d7e4f2"/>'
            '<path d="M52 30 H136 M52 40 H120 M52 48 H128" stroke="#8eb7e8"/>'
            '<circle cx="220" cy="36" r="14" fill="none" stroke="#e2b657"/>'
            '</svg>'
        ),
        "lab": (
            '<svg viewBox="0 0 320 74" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">'
            '<rect width="320" height="74" fill="#0c1a2c"/>'
            '<path d="M70 16 L90 16 L108 40 V56 H52 V40 Z" fill="none" stroke="#8fd0c4"/>'
            '<path d="M160 50 L190 24 L230 40 L270 18" fill="none" stroke="#d7b56d" stroke-width="1.5"/>'
            '</svg>'
        ),
        "paper": (
            '<svg viewBox="0 0 320 74" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">'
            '<rect width="320" height="74" fill="#0c1a2c"/>'
            '<rect x="36" y="14" width="70" height="46" rx="4" fill="none" stroke="#d7e4f2"/>'
            '<path d="M48 28 H94 M48 38 H86 M48 48 H78" stroke="#8eb7e8"/>'
            '<rect x="140" y="22" width="140" height="30" rx="8" fill="none" stroke="#d7b56d"/>'
            '</svg>'
        ),
        "shield": (
            '<svg viewBox="0 0 320 74" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">'
            '<rect width="320" height="74" fill="#0c1a2c"/>'
            '<path d="M70 16 L110 16 L118 30 V46 C118 56 94 62 70 62 C46 62 22 56 22 46 V30 Z" fill="none" stroke="#8fd0c4"/>'
            '<path d="M58 40 L68 48 L88 30" fill="none" stroke="#d7b56d" stroke-width="1.6"/>'
            '<path d="M160 24 H290 M160 38 H260 M160 52 H230" stroke="#d7e4f2"/>'
            '</svg>'
        ),
        "academy": (
            '<svg viewBox="0 0 320 74" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">'
            '<rect width="320" height="74" fill="#0c1a2c"/>'
            '<path d="M40 40 L110 22 L180 40 L110 56 Z" fill="none" stroke="#d7b56d"/>'
            '<path d="M70 48 V60 H150 V48" fill="none" stroke="#8eb7e8"/>'
            '</svg>'
        ),
        "journal": (
            '<svg viewBox="0 0 320 74" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">'
            '<rect width="320" height="74" fill="#0c1a2c"/>'
            '<rect x="40" y="14" width="86" height="46" rx="6" fill="none" stroke="#d7b56d"/>'
            '<path d="M56 28 H110 M56 38 H104 M56 48 H96" stroke="#d7e4f2"/>'
            '</svg>'
        ),
        "invest": (
            '<svg viewBox="0 0 320 74" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">'
            '<rect width="320" height="74" fill="#0c1a2c"/>'
            '<path d="M30 54 L90 34 L140 44 L210 20 L280 28" fill="none" stroke="#3dbe8b" stroke-width="1.6"/>'
            '<circle cx="210" cy="20" r="3" fill="#d7b56d"/>'
            '</svg>'
        ),
        "business": (
            '<svg viewBox="0 0 320 74" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">'
            '<rect width="320" height="74" fill="#0c1a2c"/>'
            '<rect x="40" y="28" width="36" height="28" fill="none" stroke="#8eb7e8"/>'
            '<rect x="84" y="18" width="36" height="38" fill="none" stroke="#d7b56d"/>'
            '<rect x="128" y="34" width="36" height="22" fill="none" stroke="#8fd0c4"/>'
            '</svg>'
        ),
        "video": (
            '<svg viewBox="0 0 320 74" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">'
            '<rect width="320" height="74" fill="#0c1a2c"/>'
            '<rect x="36" y="16" width="150" height="42" rx="8" fill="none" stroke="#d7e4f2"/>'
            '<path d="M96 28 L126 37 L96 46 Z" fill="#d7b56d"/>'
            '</svg>'
        ),
        "aion": (
            '<svg viewBox="0 0 320 74" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">'
            '<rect width="320" height="74" fill="#0c1a2c"/>'
            '<circle cx="78" cy="37" r="18" fill="none" stroke="#d7b56d"/>'
            '<circle cx="78" cy="37" r="6" fill="#8fd0c4"/>'
            '<path d="M120 37 H200 M200 37 L230 22 M200 37 L230 52" stroke="#d7e4f2"/>'
            '</svg>'
        ),
        "profile": (
            '<svg viewBox="0 0 320 74" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">'
            '<rect width="320" height="74" fill="#0c1a2c"/>'
            '<circle cx="58" cy="30" r="12" fill="none" stroke="#d7e4f2"/>'
            '<path d="M34 58 C38 44 78 44 82 58" fill="none" stroke="#d7b56d"/>'
            '<circle cx="180" cy="37" r="16" fill="none" stroke="#8eb7e8"/>'
            '<path d="M180 28 V37 L188 41" stroke="#f5f8fc"/>'
            '</svg>'
        ),
    }
    return common.get(kind, common["radar"])


# Each card opens an existing page. fast_page is empty when the beginner
# quick shell has no equivalent destination.
PREMIUM_MODULES: tuple[dict[str, str], ...] = (
    {"id":"radar","sector":"Essencial","title":"Radar","motif":"radar","page":"🎯 Radar","fast_page":"🎯 Radar","summary":"Vinte e oito pares Forex, Top 10 dinâmico e rankings separados. O destaque é leitura, não autorização."},
    {"id":"master","sector":"Essencial","title":"Painel Mestre","motif":"command","page":"🧭 Painel mestre","fast_page":"","summary":"Central operacional do universo já calculado neste painel. Não é o mesmo recorte dos 28 pares do Radar."},
    {"id":"macro","sector":"Essencial","title":"Macroeconomia","motif":"macro","page":"🇺🇸 EUA","fast_page":"🎙️ Macro","summary":"Abre a leitura macro que já existe. Juros, surpresas e contexto entram como cenário, não como ordem."},
    {"id":"news","sector":"Essencial","title":"Pré-Notícia","motif":"news","page":"🎙️ Macro Briefing","fast_page":"🎙️ Macro","summary":"O briefing já montado mostra o que observar antes do evento. Não dispara coleta nova nem operação."},
    {"id":"micro","sector":"Leitura","title":"Microeconomia","motif":"micro","page":"💱 Moedas","fast_page":"","summary":"Abre Moedas, a comparação de força que já existe. Não cria um modelo microeconômico novo."},
    {"id":"geo","sector":"Leitura","title":"Geopolítica","motif":"geo","page":"📰 Notícias","fast_page":"","summary":"Abre Notícias. Eventos globais aparecem como contexto da leitura atual, sem fonte nova."},
    {"id":"fundamental","sector":"Leitura","title":"Fundamentalista","motif":"fundamental","page":"🔀 Pares","fast_page":"","summary":"Abre Pares, onde a confluência já calculada fica visível. O cartão não recalcula score."},
    {"id":"calendar","sector":"Leitura","title":"Calendário Econômico","motif":"calendar","page":"🗂️ Histórico","fast_page":"","summary":"Abre Histórico para a evidência temporal já persistida. Não altera o calendário de coleta."},
    {"id":"lab","sector":"Operação","title":"Laboratório / Backtests","motif":"lab","page":"🧪 Backtest","fast_page":"","summary":"Abre o laboratório existente. Replay e métricas continuam os mesmos."},
    {"id":"paper","sector":"Operação","title":"Paper Trading","motif":"paper","page":"🧪 Backtest","fast_page":"","summary":"Não há mesa de execução nesta entrega. O cartão leva ao laboratório e não envia ordem, nem simulada nem real."},
    {"id":"guardian","sector":"Operação","title":"Guardião de Risco","motif":"shield","page":"⚡ Decisão","fast_page":"","summary":"Abre Decisão, onde os gates já calculados aparecem. Não muda limite, exposição nem autorização."},
    {"id":"academy","sector":"Ecossistema","title":"Academia","motif":"academy","page":"🎓 Aprender","fast_page":"🎓 Aprender","summary":"Material de estudo já publicado na área Aprender."},
    {"id":"journal","sector":"Ecossistema","title":"Diário","motif":"journal","page":"🗂️ Histórico","fast_page":"","summary":"Abre Histórico, o registro das leituras anteriores. Não grava um diário novo."},
    {"id":"invest","sector":"Ecossistema","title":"Investimentos","motif":"invest","page":"💰 Investir","fast_page":"💰 Investir","summary":"Abre a central de investimentos já existente, sem executar aplicação."},
    {"id":"business","sector":"Ecossistema","title":"Negócios","motif":"business","page":"💼 Vendas","fast_page":"","summary":"Abre Vendas. Onboarding comercial continua separado de qualquer ordem de mercado."},
    {"id":"video","sector":"Ecossistema","title":"Vídeo / Conteúdo","motif":"video","page":"🎓 Aprender","fast_page":"🎓 Aprender","summary":"O conteúdo em vídeo permanece dentro de Aprender. Nenhum player externo é carregado na home."},
    {"id":"aion","sector":"Ecossistema","title":"AION / Central Administrativa","motif":"aion","page":"🧠 AION","fast_page":"","summary":"Abre a Central AION quando esta sessão já tem essa área. Não amplia permissão nem autenticação."},
    {"id":"profile","sector":"Ecossistema","title":"Perfil / Configurações","motif":"profile","page":"👤 Conta","fast_page":"👤 Conta","summary":"Abre Conta. Credenciais, Render e variáveis de ambiente não são editados aqui."},
)


def status_badge_html(label: str, tone: str = "info") -> str:
    allowed = {"info", "good", "warn", "danger", "neutral"}
    safe = tone if tone in allowed else "neutral"
    return f'<span class="aq-badge {safe}">{escape(str(label))}</span>'


def section_hero_html(kicker: str, title: str, text: str) -> str:
    return (
        '<section class="aq-premium-hero">'
        f"<small>{escape(kicker)}</small>"
        f"<h2>{escape(title)}</h2>"
        f"<p>{escape(text)}</p>"
        "</section>"
    )


def premium_module_card_html(module: Mapping[str, str], *, locked: bool, available: bool) -> str:
    if not available:
        badge = status_badge_html("Fora desta sessão", "neutral")
    elif locked:
        badge = status_badge_html("Prévia no Iniciante", "warn")
    else:
        badge = status_badge_html("Abrir área", "good")
    return (
        '<article class="aq-premium-card">'
        f'<div class="aq-premium-art">{_svg(str(module.get("motif") or "radar"))}</div>'
        f'<p class="aq-premium-kicker">{escape(str(module.get("sector") or ""))}</p>'
        f'<h4>{escape(str(module.get("title") or ""))}</h4>'
        f'<p>{escape(str(module.get("summary") or ""))}</p>'
        f'<div class="aq-premium-meta">{badge}'
        f'{status_badge_html("Clicável", "info")}</div>'
        "</article>"
    )


def navigation_tile_html(title: str, detail: str) -> str:
    return (
        '<div class="aq-metric">'
        f"<small>{escape(title)}</small>"
        f"<strong>{escape(detail)}</strong>"
        "</div>"
    )


def premium_panel_html(title: str, body: str) -> str:
    return f'<section class="aq-panel"><h3>{escape(title)}</h3><p>{escape(body)}</p></section>'


def metric_card_html(label: str, value: str) -> str:
    return navigation_tile_html(label, value)


def alert_card_html(text: str, tone: str = "info") -> str:
    allowed = {"info", "good", "warn", "danger"}
    safe = tone if tone in allowed else "info"
    return f'<div class="aq-alert {safe}" role="status">{escape(text)}</div>'


def empty_state_html(text: str) -> str:
    return f'<div class="aq-empty">{escape(text)}</div>'


def loading_state_html(text: str) -> str:
    return f'<div class="aq-loading" role="status">{escape(text)}</div>'


def beginner_attention_html(row: Mapping[str, Any] | None) -> str:
    """First-layer reading. Uses fields already present on the radar row."""
    data = dict(row or {})
    pair = str(data.get("pair") or "—")
    action = str(data.get("action") or "NÃO OPERAR")
    bias = str(data.get("bias") or "NEUTRO")
    priority = data.get("priority")
    confidence = "sem prioridade" if priority is None else f"{float(priority):.0f}/100 de prioridade interna"
    news = str(data.get("news") or "sem notícia destacada")
    risk = str(data.get("state") or "observação")
    nxt = str(data.get("next_action") or "Aguardar confirmação válida.")
    tiles = "".join((
        metric_card_html("Ativo em atenção", pair),
        metric_card_html("Viés", bias),
        metric_card_html("Confiança", confidence),
        metric_card_html("Operar ou não", action),
        metric_card_html("Risco / estado", risk),
        metric_card_html("Notícia", news),
    ))
    return (
        '<section class="aq-premium" aria-label="Leitura inicial">'
        + premium_panel_html(
            "O que está acontecendo",
            "A primeira camada mostra só a leitura já calculada do Radar. "
            "Compra ou venda é viés de análise. NÃO OPERAR continua bloqueando a entrada.",
        )
        + f'<div class="aq-premium-grid">{tiles}</div>'
        + alert_card_html(f"Próximo passo: {nxt}", "info")
        + "</section>"
    )


def radar_live_html() -> str:
    return (
        '<div class="aq-radar-live" aria-hidden="true">'
        '<span class="aq-radar-dot"></span>'
        "<span>Radar em observação · atualização discreta do snapshot, sem nova coleta</span>"
        "</div>"
    )


def master_command_html(*, operational_count: int) -> str:
    count = max(0, int(operational_count))
    sections = (
        ("Visão geral", "Estado já consolidado"),
        ("Pares monitorados", f"{count} no universo deste painel"),
        ("Scanner", "Técnica já carregada"),
        ("Mapa", "Market Map existente"),
        ("Risco", "Gates atuais"),
        ("Contexto macro", "Viés já calculado"),
        ("Contexto técnico", "H4, H1 e M15"),
        ("Oportunidades", "Priorização, não ordem"),
        ("Alertas", "Avisos desta execução"),
        ("Bloqueios", "O que impede operar"),
        ("Status operacional", "Autorização inalterada"),
    )
    cells = "".join(
        f"<div><strong>{escape(title)}</strong>{escape(detail)}</div>"
        for title, detail in sections
    )
    note = (
        "O Radar Geral monitora 28 pares Forex. Este Painel Mestre usa o universo "
        f"operacional já presente na matriz ({count} pares nesta execução). "
        "São recortes diferentes de propósito. Isso não é erro nem regressão."
    )
    return (
        '<section class="aq-premium" aria-label="Central operacional">'
        + premium_panel_html("Painel Mestre · central operacional", note)
        + f'<div class="aq-master-rail">{cells}</div>'
        + alert_card_html("Nenhuma regra de ranking, gate ou autorização foi alterada por este visual.", "warn")
        + "</section>"
    )


def premium_modules() -> tuple[dict[str, str], ...]:
    return PREMIUM_MODULES


def _destination(module: Mapping[str, str], *, fast: bool) -> str:
    return str(module.get("fast_page") if fast else module.get("page") or "")


def consume_premium_navigation(
    session_state,
    *,
    mode: str,
    available_pages: Sequence[str],
    fast: bool = False,
) -> str:
    """Apply a catalog click before the navigation widget is created."""
    raw = session_state.pop(_PENDING_KEY, None)
    page = str(raw or "").strip()
    pages = [str(item) for item in list(available_pages or [])]
    if not page or page not in pages:
        return ""
    if fast:
        session_state["aq_beginner_page"] = page
    elif str(mode or "").casefold().startswith("avan"):
        session_state["atlasquant_advanced_area"] = page
        session_state["atlasquant_stable_nav_fallback"] = page
    else:
        session_state["atlasquant_beginner_area_full"] = page
        session_state["atlasquant_stable_nav_fallback"] = page
    return page


def catalog_is_home(active_page: str) -> bool:
    """The full catalog is the Radar home. Other areas keep their own workspace."""
    return str(active_page or "🎯 Radar") in {"🎯 Radar"}


def render_premium_catalog(
    *,
    mode: str,
    available_pages: Sequence[str],
    fast: bool = False,
    active_page: str = "",
) -> None:
    """Visual home. Buttons only store a navigation target."""
    pages = {str(item) for item in list(available_pages or [])}
    if not catalog_is_home(active_page):
        st.markdown(PREMIUM_CSS, unsafe_allow_html=True)
        st.markdown(
            premium_panel_html(
                "Central do ecossistema",
                "Você está fora da home. A área aberta continua sendo a mesma de antes.",
            ),
            unsafe_allow_html=True,
        )
        home_target = "🎯 Radar" if "🎯 Radar" in pages else ""
        if home_target and st.button(
            "Voltar à central",
            key="aq_premium_back_home_fast" if fast else "aq_premium_back_home_full",
            width="stretch",
        ):
            st.session_state[_PENDING_KEY] = home_target
            st.rerun()
        return
    beginner = not str(mode or "").casefold().startswith("avan")
    st.markdown(PREMIUM_CSS, unsafe_allow_html=True)
    st.markdown('<div class="aq-premium">', unsafe_allow_html=True)
    if beginner:
        hero = section_hero_html(
            "ATLASQUANT",
            "Central do ecossistema",
            "Comece pelo que está acontecendo. Os setores avançados continuam visíveis, "
            "mas no Iniciante abrem só a prévia já existente.",
        )
    else:
        hero = section_hero_html(
            "ATLASQUANT",
            "Central do ecossistema",
            "Escolha um setor pelo cartão. A área avançada continua a mesma; "
            "mudou a apresentação, não o cálculo.",
        )
    st.markdown(hero, unsafe_allow_html=True)
    current = ""
    for sector in ("Essencial", "Leitura", "Operação", "Ecossistema"):
        modules = [item for item in PREMIUM_MODULES if item["sector"] == sector]
        if not modules:
            continue
        if sector != current:
            st.markdown(f'<div class="aq-premium-sector"><h3>{escape(sector)}</h3></div>', unsafe_allow_html=True)
            current = sector
        for module in modules:
            target = _destination(module, fast=fast)
            available = bool(target) and target in pages
            open_pages = set(BEGINNER_OPEN_AREAS) | {"🎙️ Macro"}
            locked = beginner and available and target not in open_pages
            # Full-app beginner still routes locked pages into the existing preview.
            # The fast shell has no preview workspace, so those cards stay inactive.
            can_open = available and not (fast and locked)
            st.markdown(
                premium_module_card_html(module, locked=locked or not available, available=available),
                unsafe_allow_html=True,
            )
            label = f"Abrir {module['title']}" if can_open else f"{module['title']} · aguardar modo Avançado"
            if st.button(label, key=f"aq_premium_{module['id']}_{'fast' if fast else 'full'}", disabled=not can_open, width="stretch"):
                st.session_state[_PENDING_KEY] = target
                st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)
