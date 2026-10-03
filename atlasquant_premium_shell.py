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

WORKSPACE_WELCOME = {
    "🎯 Radar": ("RADAR", "Seja bem-vindo ao Radar.", "Visão rápida do mercado, Top 10 e direção já calculada para você começar pelo que importa."),
    "🧭 Painel mestre": ("COMANDO", "Seja bem-vindo ao Painel Mestre.", "Consolide leitura macro, técnica, risco e bloqueios no mesmo cockpit operacional."),
    "💱 Moedas": ("FORÇA RELATIVA", "Seja bem-vindo à área de Moedas.", "Compare força, componentes do score e contexto relativo sem transformar leitura em ordem."),
    "🇺🇸 EUA": ("MACRO EUA", "Seja bem-vindo à leitura dos EUA.", "Juros, inflação, emprego e surpresas econômicas organizados para leitura do USD."),
    "🔀 Pares": ("CONFLUÊNCIA", "Seja bem-vindo à área de Pares.", "Cruze força, contexto e timing do par usando apenas dados já validados nesta execução."),
    "🏦 Fed": ("POLÍTICA MONETÁRIA", "Seja bem-vindo à área do Fed.", "Acompanhe tom, juros e narrativa do banco central com separação entre fato, interpretação e risco."),
    "🗂️ Histórico": ("EVIDÊNCIA", "Seja bem-vindo ao Histórico.", "Revise leituras anteriores, snapshots e rastreabilidade antes de comparar desempenho."),
    "🧪 Backtest": ("LABORATÓRIO", "Seja bem-vindo ao Laboratório de Backtests.", "Teste operacionais, ativos e períodos sem confundir simulação com execução real."),
    "⚡ Decisão": ("GUARDIÃO", "Seja bem-vindo à área de Decisão.", "Veja contexto, gates e motivos para operar ou não operar; autorização real continua separada."),
    "🗺️ Market Map": ("INTERMERCADO", "Seja bem-vindo ao Market Map.", "Enxergue relações entre ativos e contexto intermercado sem inventar causalidade."),
    "🎙️ Macro Briefing": ("BRIEFING", "Seja bem-vindo ao Macro Briefing.", "Receba a leitura resumida do cenário e dos eventos que merecem atenção agora."),
    "🎓 Aprender": ("ACADEMIA", "Seja bem-vindo à Academia.", "Estude macro, ICT/SMC e funcionamento do AtlasQuant em uma trilha mais simples de acompanhar."),
    "🧩 Produto": ("PRODUTO", "Seja bem-vindo à área de Produto.", "Consulte recursos e configurações do ecossistema sem alterar segurança ou produção por esta tela."),
    "🛠️ Melhorias": ("EVOLUÇÃO", "Seja bem-vindo à área de Melhorias.", "Acompanhe validações, estabilidade e evolução técnica com evidência antes de promoção."),
    "📰 Notícias": ("CONTEXTO", "Seja bem-vindo à área de Notícias.", "Organize fatos relevantes por moeda e impacto potencial sem transformar manchete em sinal."),
    "🤖 Autopilot": ("AUTOMAÇÃO", "Seja bem-vindo ao Autopilot.", "Acompanhe monitoramento e runtime com trilha de auditoria; ações externas seguem protegidas."),
    "👤 Conta": ("CONTA", "Seja bem-vindo à sua Conta.", "Gerencie sua experiência de acesso sem expor secrets, infraestrutura ou credenciais de servidor."),
    "📱 Instalar": ("ACESSO", "Seja bem-vindo à área de Instalação.", "Encontre o caminho de acesso ao AtlasQuant de forma simples e compatível com seu dispositivo."),
    "💼 Vendas": ("COMERCIAL", "Seja bem-vindo à área de Vendas.", "Acompanhe onboarding comercial e acesso sem misturar esta área com o cockpit B2B do AION Negócios."),
    "💰 Investir": ("INVESTIMENTOS", "Seja bem-vindo à área de Investimentos.", "Compare alternativas e cenários com foco em evidência, liquidez e risco; movimentação financeira não é executada aqui."),
    "🛟 Suporte": ("SUPORTE", "Seja bem-vindo ao Suporte.", "Use esta área para orientação e diagnóstico sem criar permissões ou atalhos administrativos."),
    "🧠 AION": ("AION CORE", "Seja bem-vindo ao AION.", "Oito núcleos especializados trabalham dentro de um único AION Core para organizar, pesquisar, proteger e coordenar o ecossistema."),
}

PREMIUM_CSS = """
<style>
.stApp{
  background:
    radial-gradient(circle at 84% -10%,rgba(31,91,143,.13),transparent 34rem),
    radial-gradient(circle at -8% 32%,rgba(39,126,113,.08),transparent 30rem),
    #07111f;
}
.aq-premium{max-width:100%;overflow-x:hidden;color:#f5f8fc}
.aq-workspace-welcome{position:relative;overflow:hidden;border:1px solid rgba(143,208,196,.24);border-radius:16px;padding:13px 15px;margin:8px 0 14px;background:linear-gradient(135deg,rgba(16,38,61,.96),rgba(9,25,43,.95));box-shadow:0 10px 28px rgba(0,0,0,.16)}
.aq-workspace-welcome:after{content:"";position:absolute;right:-54px;top:-74px;width:150px;height:150px;border-radius:50%;border:1px solid rgba(215,181,109,.13);box-shadow:0 0 0 24px rgba(143,208,196,.025);pointer-events:none}
.aq-workspace-welcome small{display:block;color:#8fd0c4;font-size:.64rem;font-weight:900;letter-spacing:.14em;text-transform:uppercase}
.aq-workspace-welcome strong{display:block;color:#f5f8fc;font-size:1rem;line-height:1.3;margin-top:3px}
.aq-workspace-welcome p{margin:5px 0 0;color:#d7e4f2;font-size:.8rem;line-height:1.42;max-width:86ch;font-weight:650}
.aq-workspace-welcome .motto{color:#d7b56d;font-size:.7rem;font-weight:900;letter-spacing:.04em}
.aq-premium-hero{position:relative;overflow:hidden;border:1px solid rgba(198,214,232,.22);border-radius:22px;padding:22px 22px 18px;margin:4px 0 16px;background:
  radial-gradient(circle at 100% 0%, rgba(215,181,109,.16), transparent 34%),
  linear-gradient(145deg, #12283f 0%, #0c1a2c 58%, #10261f 100%);
  box-shadow:0 18px 40px rgba(0,0,0,.28)}
.aq-premium-hero small{display:block;color:#d7b56d;font-weight:800;letter-spacing:.14em;font-size:.68rem}
.aq-premium-hero h2{margin:.35rem 0 .4rem;color:#f5f8fc;font-size:1.72rem;line-height:1.15;font-weight:760}
.aq-premium-hero p{margin:0;max-width:68ch;color:#d7e4f2;font-size:.95rem;line-height:1.45;font-weight:650}
.aq-premium-sector{margin:8px 0 18px;min-width:0}
.aq-premium-sector h3{margin:0 0 10px;color:#f5f8fc;font-size:1.02rem;font-weight:760}
.aq-premium-row{display:flex;flex-wrap:nowrap;overflow-x:auto;overflow-y:hidden;scroll-snap-type:x mandatory;gap:12px;width:100%;max-width:100%;min-width:0;-webkit-overflow-scrolling:touch;scrollbar-width:thin;scrollbar-color:#8fd0c4 rgba(198,214,232,.12);padding-bottom:10px}
.aq-premium-row::-webkit-scrollbar{height:8px}
.aq-premium-row::-webkit-scrollbar-track{background:rgba(198,214,232,.08);border-radius:999px}
.aq-premium-row::-webkit-scrollbar-thumb{background:linear-gradient(90deg,#8eb7e8,#8fd0c4);border-radius:999px}
.aq-premium-scroll-hint{margin:-2px 0 8px;color:#9fb4c9;font-size:.72rem;font-weight:750;letter-spacing:.03em}
.aq-premium-scroll-hint b{color:#8fd0c4}

.aq-premium-grid{display:grid;grid-template-columns:1fr;gap:12px}
.aq-premium-card{flex:0 0 340px;scroll-snap-align:start;min-width:0;border:1px solid rgba(198,214,232,.22);border-radius:18px;padding:14px 14px 12px;background:linear-gradient(180deg,rgba(23,48,74,.96),rgba(12,26,44,.94));box-shadow:0 10px 24px rgba(0,0,0,.18);animation:aq-rise .5s ease both}
a.aq-premium-card{display:block;color:inherit;text-decoration:none}
.aq-premium-card:hover{border-color:rgba(215,181,109,.55);transform:translateY(-2px)}
.aq-premium-card:focus-within{outline:2px solid #d7b56d;outline-offset:3px}
.aq-premium-art{position:relative;height:74px;border-radius:14px;margin-bottom:10px;overflow:hidden;background:
  radial-gradient(circle at 20% 18%,rgba(143,208,196,.12),transparent 30%),
  radial-gradient(circle at 84% 20%,rgba(215,181,109,.10),transparent 28%),
  linear-gradient(180deg,#10253d,#091522)}
.aq-premium-art:after{content:"";position:absolute;inset:0;pointer-events:none;opacity:.16;background-image:
  linear-gradient(rgba(142,183,232,.28) 1px,transparent 1px),
  linear-gradient(90deg,rgba(142,183,232,.24) 1px,transparent 1px);background-size:26px 18px}
.aq-premium-art svg{position:relative;z-index:1;width:100%;height:74px;display:block}
.aq-premium-art svg>rect:first-child{fill:rgba(12,26,44,.76)}
.aq-radar-sweep{transform-origin:64px 37px;animation:aq-sweep 4.8s linear infinite}
.aq-premium-kicker{margin:0;color:#d7b56d;font-size:.68rem;font-weight:800;letter-spacing:.08em;text-transform:uppercase}
.aq-premium-card h4{margin:.2rem 0 .35rem;color:#f5f8fc;font-size:1.12rem;line-height:1.2}
.aq-premium-card p{margin:0;color:#d7e4f2;font-size:.86rem;line-height:1.4;font-weight:650}
.aq-premium-meta{display:flex;flex-wrap:wrap;gap:6px;margin-top:10px}
.aq-premium-open{display:inline-flex;margin-top:10px;color:#f5f8fc;font-size:.78rem;font-weight:800}
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
.aq-cockpit-head{position:relative;overflow:hidden;border:1px solid rgba(143,208,196,.25);border-radius:18px;padding:18px 20px;margin:4px 0 16px;background:
  linear-gradient(105deg,rgba(14,39,64,.98),rgba(8,25,43,.98) 62%,rgba(8,43,46,.9));box-shadow:0 18px 46px rgba(0,0,0,.24),inset 0 1px 0 rgba(255,255,255,.04)}
.aq-cockpit-head:after{content:"";position:absolute;right:-34px;top:-62px;width:170px;height:170px;border-radius:50%;border:1px solid rgba(143,208,196,.16);box-shadow:0 0 0 28px rgba(142,183,232,.04),0 0 0 56px rgba(215,181,109,.025);pointer-events:none}
.aq-cockpit-kicker{color:#8fd0c4;font-size:.66rem;font-weight:900;letter-spacing:.16em;text-transform:uppercase}
.aq-cockpit-head h2{color:#fff;margin:.3rem 0 .35rem;font-size:clamp(1.35rem,2.4vw,2rem);letter-spacing:-.025em}
.aq-cockpit-head p{color:#d7e4f2;margin:0;max-width:72ch;font-size:.88rem;font-weight:650}
.aq-cockpit-telemetry{display:flex;flex-wrap:wrap;gap:7px;margin-top:13px;position:relative;z-index:1}
.aq-cockpit-telemetry span{display:inline-flex;gap:5px;align-items:center;border:1px solid rgba(142,183,232,.24);background:rgba(7,17,31,.48);border-radius:999px;padding:5px 9px;color:#eaf2fb;font-size:.68rem;font-weight:800}
.aq-cockpit-telemetry b{color:#d7b56d;font-weight:900}
.stApp [data-testid="stMetric"]{border:1px solid rgba(142,183,232,.2);border-radius:14px;padding:10px 12px;background:linear-gradient(180deg,rgba(19,43,69,.82),rgba(11,29,49,.82));box-shadow:inset 0 1px 0 rgba(255,255,255,.035)}
.stApp [data-testid="stDataFrame"]{border:1px solid rgba(142,183,232,.18);border-radius:13px;overflow:hidden;background:#0c1a2c}
.stApp [data-testid="stSelectbox"] [role="combobox"]:focus-visible{outline:2px solid #d7b56d;outline-offset:2px}
.stApp [data-testid="stButton"] button{transition:transform .16s ease,border-color .16s ease,box-shadow .16s ease}
.stApp [data-testid="stButton"] button:hover:not(:disabled){transform:translateY(-1px);border-color:#8fd0c4 !important;box-shadow:0 8px 20px rgba(0,0,0,.18)}
.stApp a{color:#d6e8ff;text-decoration:underline;text-underline-offset:2px;font-weight:750}
.stApp button:focus-visible,.stApp [role="tab"]:focus-visible,.stApp a:focus-visible{outline:2px solid #d7b56d;outline-offset:2px}
.stApp [data-testid="stButton"] button:disabled{color:#d7e4f2 !important;-webkit-text-fill-color:#d7e4f2 !important;background:#1c3048 !important;opacity:1 !important;border-color:rgba(215,181,109,.4) !important}
@media (min-width:760px){.aq-premium-grid{grid-template-columns:1fr 1fr}.aq-master-rail{grid-template-columns:1fr 1fr 1fr}}
@media (min-width:1200px){.aq-premium-grid{grid-template-columns:1fr 1fr 1fr}}
@media (max-width:760px){.aq-premium-hero,.aq-cockpit-head{padding:15px 16px}.aq-premium-hero h2{font-size:1.35rem}.aq-premium-row .aq-premium-card{flex-basis:86vw}.aq-premium-card:hover,.stApp [data-testid="stButton"] button:hover{transform:none}.aq-cockpit-head:after{opacity:.55}}
@keyframes aq-rise{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:none}}
@keyframes aq-ping{0%{box-shadow:0 0 0 0 rgba(143,208,196,.55)}100%{box-shadow:0 0 0 10px rgba(143,208,196,0)}}
@keyframes aq-sweep{from{transform:rotate(0deg)}to{transform:rotate(360deg)}}
/* Trader reference cockpit — inspired by the approved AtlasQuant visual direction. */
.aq-trader-shell{position:relative;overflow:hidden;margin:4px 0 16px;border:1px solid rgba(69,174,255,.28);border-radius:26px;padding:16px;background:
  radial-gradient(circle at 50% 28%,rgba(49,111,255,.18),transparent 31rem),
  radial-gradient(circle at 86% 18%,rgba(135,72,255,.14),transparent 24rem),
  linear-gradient(145deg,rgba(5,15,35,.98),rgba(5,12,27,.99) 56%,rgba(8,20,43,.98));
  box-shadow:0 28px 80px rgba(0,0,0,.38),inset 0 1px 0 rgba(255,255,255,.045)}
.aq-trader-shell:before{content:"";position:absolute;inset:0;pointer-events:none;opacity:.24;background-image:
  linear-gradient(rgba(65,165,255,.11) 1px,transparent 1px),
  linear-gradient(90deg,rgba(65,165,255,.09) 1px,transparent 1px);background-size:42px 42px;mask-image:linear-gradient(to bottom,black,transparent 72%)}
.aq-trader-shell>*{position:relative;z-index:1}
.aq-trader-topline{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:6px 4px 12px;border-bottom:1px solid rgba(104,180,255,.16)}
.aq-trader-brand{display:flex;align-items:center;gap:10px;color:#fff;font-size:1.02rem;font-weight:900;letter-spacing:.05em}
.aq-trader-brand-mark{display:grid;place-items:center;width:34px;height:34px;border-radius:10px;background:linear-gradient(145deg,#23d8ff,#386dff 58%,#a55bff);box-shadow:0 0 26px rgba(47,149,255,.34);color:#04101e;font-weight:1000}
.aq-trader-motto{color:#eef6ff;font-size:.78rem;font-weight:850;letter-spacing:.02em;text-align:right}
.aq-trader-ticker{display:flex;gap:8px;overflow-x:auto;max-width:100%;padding:11px 2px 8px;scrollbar-width:thin;scrollbar-color:#398cff rgba(255,255,255,.06)}
.aq-trader-ticker::-webkit-scrollbar{height:6px}.aq-trader-ticker::-webkit-scrollbar-thumb{background:#398cff;border-radius:99px}
.aq-trader-tick{flex:0 0 auto;min-width:116px;border:1px solid rgba(82,158,255,.22);border-radius:12px;padding:8px 10px;background:linear-gradient(180deg,rgba(11,30,62,.86),rgba(5,17,37,.9));box-shadow:inset 0 1px 0 rgba(255,255,255,.04)}
.aq-trader-tick small{display:block;color:#8fc8ff;font-size:.59rem;font-weight:900;letter-spacing:.12em}.aq-trader-tick strong{display:block;color:#fff;margin-top:2px;font-size:.82rem}.aq-trader-tick.good strong{color:#59e4af}.aq-trader-tick.warn strong{color:#ff7d91}.aq-trader-tick.neutral strong{color:#dce8f7}
.aq-trader-lenses{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:9px;margin:8px 0 12px}
.aq-trader-lens{border:1px solid rgba(91,159,255,.22);border-radius:12px;padding:9px 10px;background:linear-gradient(180deg,rgba(13,35,69,.84),rgba(7,19,40,.86));text-align:center}
.aq-trader-lens small{display:block;color:#86bfff;font-size:.58rem;font-weight:900;letter-spacing:.11em}.aq-trader-lens strong{display:block;color:#fff;font-size:.76rem;margin-top:2px}
.aq-trader-stage{display:grid;grid-template-columns:minmax(0,.9fr) minmax(250px,1.15fr) minmax(0,.9fr);gap:12px;align-items:stretch;margin:12px 0}
.aq-trader-sidepanel{border:1px solid rgba(67,160,255,.24);border-radius:18px;padding:14px;background:linear-gradient(160deg,rgba(9,30,59,.92),rgba(7,18,38,.94));min-width:0}
.aq-trader-sidepanel small{display:block;color:#73d7ff;font-size:.61rem;font-weight:900;letter-spacing:.12em}.aq-trader-sidepanel h3{margin:.3rem 0 .35rem;color:#fff;font-size:1rem}.aq-trader-sidepanel p{margin:0;color:#cbdcf1;font-size:.75rem;line-height:1.42}
.aq-trader-side-list{display:grid;gap:7px;margin-top:11px}.aq-trader-side-list span{display:flex;align-items:center;justify-content:space-between;gap:8px;border:1px solid rgba(127,184,255,.14);border-radius:9px;padding:7px 8px;color:#e7f1ff;background:rgba(7,18,38,.58);font-size:.68rem;font-weight:800}.aq-trader-side-list b{color:#5ce1ff;font-size:.59rem;letter-spacing:.07em}
.aq-trader-core{display:flex;flex-direction:column;align-items:center;justify-content:center;min-height:300px;border:1px solid rgba(88,161,255,.28);border-radius:22px;padding:14px;background:radial-gradient(circle at 50% 47%,rgba(47,119,255,.24),transparent 45%),linear-gradient(180deg,rgba(9,27,58,.9),rgba(4,14,32,.94));overflow:hidden}
.aq-trader-globe{position:relative;width:190px;height:190px;border-radius:50%;border:1px solid rgba(107,215,255,.72);box-shadow:0 0 28px rgba(45,157,255,.32),inset 0 0 38px rgba(55,118,255,.2);background:
  radial-gradient(circle at 38% 30%,rgba(96,231,255,.33),transparent 18%),
  radial-gradient(circle at 62% 58%,rgba(123,76,255,.3),transparent 22%),
  radial-gradient(circle,#0b3a75 0,#071d42 58%,#041027 100%)}
.aq-trader-globe:before,.aq-trader-globe:after{content:"";position:absolute;inset:16%;border-radius:50%;border:1px solid rgba(91,211,255,.5)}
.aq-trader-globe:before{transform:scaleX(.42);animation:aq-orbit 10s linear infinite}.aq-trader-globe:after{transform:scaleY(.42);animation:aq-orbit-rev 12s linear infinite}
.aq-trader-core-logo{position:absolute;inset:0;display:grid;place-items:center;color:#dff9ff;font-size:3rem;font-weight:1000;text-shadow:0 0 24px #37bfff}
.aq-trader-core h2{margin:12px 0 4px;color:#fff;font-size:1.35rem;text-align:center}.aq-trader-core p{margin:0;color:#cbdcf1;text-align:center;font-size:.76rem;max-width:38ch}.aq-trader-core-status{display:flex;flex-wrap:wrap;justify-content:center;gap:6px;margin-top:10px}.aq-trader-core-status span{border:1px solid rgba(94,181,255,.22);border-radius:999px;padding:4px 8px;color:#e7f4ff;background:rgba(6,20,44,.72);font-size:.59rem;font-weight:850}
.aq-trader-modules-title{display:flex;align-items:end;justify-content:space-between;gap:10px;margin:15px 2px 9px}.aq-trader-modules-title h3{margin:0;color:#fff;font-size:1rem}.aq-trader-modules-title span{color:#8db5df;font-size:.65rem}
.aq-trader-module-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:9px}
.aq-trader-module{position:relative;overflow:hidden;min-width:0;border:1px solid rgba(73,158,255,.24);border-radius:14px;padding:11px;background:linear-gradient(160deg,rgba(11,32,65,.92),rgba(6,18,39,.94));box-shadow:inset 0 1px 0 rgba(255,255,255,.04)}
.aq-trader-module:before{content:"";position:absolute;inset:auto -30px -42px auto;width:92px;height:92px;border-radius:50%;background:radial-gradient(circle,rgba(75,111,255,.18),transparent 66%)}
.aq-trader-module-icon{display:grid;place-items:center;width:34px;height:34px;border:1px solid rgba(93,194,255,.34);border-radius:10px;background:linear-gradient(145deg,rgba(14,86,154,.82),rgba(31,42,105,.88));color:#fff;font-size:1.05rem;box-shadow:0 0 20px rgba(53,140,255,.16)}
.aq-trader-module small{display:block;margin-top:8px;color:#72d8ff;font-size:.55rem;font-weight:900;letter-spacing:.1em}.aq-trader-module h4{margin:.2rem 0 .3rem;color:#fff;font-size:.86rem}.aq-trader-module p{margin:0;color:#c7d8ed;font-size:.66rem;line-height:1.36}.aq-trader-module .state{display:inline-flex;margin-top:8px;border-radius:999px;padding:3px 7px;font-size:.55rem;font-weight:900;border:1px solid rgba(116,195,255,.22);color:#eaf6ff}.aq-trader-module .state.locked{color:#ffe39c;border-color:rgba(255,201,92,.32)}.aq-trader-module .state.off{color:#a9b9cb}
.aq-trader-bottom{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:9px;margin-top:10px}.aq-trader-bottom-card{border:1px solid rgba(71,157,255,.2);border-radius:14px;padding:11px;background:rgba(6,20,43,.8)}.aq-trader-bottom-card small{color:#75d8ff;font-size:.57rem;font-weight:900;letter-spacing:.1em}.aq-trader-bottom-card strong{display:block;color:#fff;margin-top:3px;font-size:.82rem}.aq-trader-bottom-card p{margin:4px 0 0;color:#bcd0e6;font-size:.65rem;line-height:1.35}
@media (max-width:980px){.aq-trader-stage{grid-template-columns:1fr}.aq-trader-core{order:-1;min-height:270px}.aq-trader-module-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.aq-trader-lenses{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media (max-width:560px){.aq-trader-shell{padding:10px;border-radius:19px}.aq-trader-topline{align-items:flex-start;flex-direction:column}.aq-trader-motto{text-align:left}.aq-trader-module-grid,.aq-trader-bottom{grid-template-columns:1fr}.aq-trader-globe{width:150px;height:150px}.aq-trader-core{min-height:245px}.aq-trader-tick{min-width:102px}}
@keyframes aq-orbit{from{transform:scaleX(.42) rotate(0)}to{transform:scaleX(.42) rotate(360deg)}}@keyframes aq-orbit-rev{from{transform:scaleY(.42) rotate(360deg)}to{transform:scaleY(.42) rotate(0)}}
@media (prefers-reduced-motion:reduce){.aq-trader-globe:before,.aq-trader-globe:after{animation:none !important}}

/* Reference-faithful Trader V3: dense cockpit matching the approved composition. */
.aq-trader-shell[data-trader-reference="v3"]{padding:0;border-radius:18px;background:linear-gradient(180deg,#020a17,#020610);min-height:700px}
.aq-trader-v3-grid{display:grid;grid-template-columns:154px minmax(0,1fr);min-height:700px}.aq-trader-v3-side{display:flex;flex-direction:column;padding:10px 7px;border-right:1px solid rgba(48,139,255,.35);background:linear-gradient(180deg,rgba(5,24,52,.98),rgba(2,10,25,.99));box-shadow:inset -12px 0 36px rgba(0,0,0,.3)}
.aq-trader-v3-side-brand{display:flex;align-items:center;gap:7px;padding:2px 7px 10px;color:#fff;font-weight:950;font-size:.78rem;letter-spacing:.08em}.aq-trader-v3-side-brand b{display:grid;place-items:center;width:32px;height:32px;color:#e7fbff;font-size:1.35rem;text-shadow:0 0 16px #32aaff}
.aq-trader-v3-nav{display:grid;gap:2px}.aq-trader-v3-nav span{display:flex;align-items:center;gap:7px;min-height:27px;padding:4px 7px;border:1px solid transparent;border-radius:7px;color:#c7d7eb;font-size:.58rem;font-weight:760}.aq-trader-v3-nav span:first-child{color:#fff;border-color:#2c92ff;background:linear-gradient(90deg,rgba(20,103,205,.78),rgba(7,37,82,.88));box-shadow:0 0 15px rgba(36,133,255,.25)}.aq-trader-v3-nav i{width:15px;text-align:center;color:#7fd8ff;font-style:normal}
.aq-trader-v3-aion{margin-top:auto;border:1px solid #328fff;border-radius:11px;padding:8px;background:linear-gradient(160deg,rgba(18,70,135,.75),rgba(12,22,65,.92));box-shadow:0 0 20px rgba(35,132,255,.18)}.aq-trader-v3-aion strong{display:block;color:#7fe1ff;font-size:.75rem}.aq-trader-v3-aion small{display:block;color:#b8c9df;font-size:.53rem;margin:2px 0 6px}.aq-trader-v3-aion b{display:block;border:1px solid rgba(91,195,255,.38);border-radius:6px;padding:5px;color:#eefaff;font-size:.54rem;text-align:center}
.aq-trader-v3-main{min-width:0;padding:7px 9px 9px;background:radial-gradient(circle at 51% 65%,rgba(26,108,255,.12),transparent 27rem)}
.aq-trader-v3-head{display:grid;grid-template-columns:minmax(170px,.7fr) minmax(260px,1fr) minmax(250px,.75fr);align-items:center;gap:10px;min-height:40px;border-bottom:1px solid rgba(70,157,255,.23)}.aq-trader-v3-title{color:#fff;font-weight:950;font-size:.76rem;letter-spacing:.08em}.aq-trader-v3-motto{text-align:center;color:#fff;font-weight:900;font-size:.77rem}.aq-trader-v3-tools{display:flex;justify-content:flex-end;align-items:center;gap:8px;color:#bed0e8;font-size:.55rem}.aq-trader-v3-search{min-width:125px;border:1px solid rgba(89,156,237,.25);border-radius:7px;padding:5px 8px;color:#627b99;background:rgba(5,17,37,.7)}
.aq-trader-shell[data-trader-reference="v3"] .aq-trader-ticker{padding:6px 0}.aq-trader-shell[data-trader-reference="v3"] .aq-trader-tick{min-width:91px;border-radius:8px;padding:5px 7px}.aq-trader-shell[data-trader-reference="v3"] .aq-trader-tick small{font-size:.48rem}.aq-trader-shell[data-trader-reference="v3"] .aq-trader-tick strong{font-size:.62rem}
.aq-trader-v3-tabs{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:7px;margin:2px 0 7px}.aq-trader-v3-tab{border:1px solid rgba(52,136,244,.48);border-radius:7px;padding:6px 5px;color:#dceaff;text-align:center;font-size:.54rem;font-weight:900;background:linear-gradient(180deg,rgba(13,57,119,.82),rgba(5,25,57,.88));box-shadow:inset 0 0 16px rgba(45,135,255,.08)}.aq-trader-v3-tab:first-child{border-color:#27a5ff;box-shadow:0 0 14px rgba(31,143,255,.25),inset 0 0 15px rgba(32,139,255,.13)}
.aq-trader-v3-media{display:grid;grid-template-columns:1.75fr repeat(3,1fr);gap:7px;margin-bottom:7px}.aq-trader-v3-video{position:relative;overflow:hidden;display:flex;flex-direction:column;justify-content:flex-end;min-height:132px;border:1px solid rgba(56,151,255,.5);border-radius:9px;padding:9px;background:radial-gradient(circle at 50% 34%,rgba(42,122,255,.45),transparent 42%),linear-gradient(150deg,#123b79,#07172f 58%,#050c1d);box-shadow:inset 0 0 28px rgba(41,121,255,.12)}.aq-trader-v3-video.big{min-height:150px}.aq-trader-v3-video:before{content:"▶";position:absolute;left:50%;top:43%;transform:translate(-50%,-50%);display:grid;place-items:center;width:38px;height:38px;border:2px solid #dffaff;border-radius:50%;color:#fff;background:rgba(17,76,162,.58);box-shadow:0 0 18px #2a9bff}.aq-trader-v3-video.badge:after{content:"AO VIVO";position:absolute;left:8px;top:8px;border-radius:4px;padding:3px 6px;background:#ff315d;color:#fff;font-size:.48rem;font-weight:950}.aq-trader-v3-video strong{position:relative;color:#fff;font-size:.73rem;text-align:center}.aq-trader-v3-video small{position:relative;color:#a8bed9;font-size:.48rem;text-align:center;margin-top:2px}
.aq-trader-shell[data-trader-reference="v3"] .aq-trader-module-grid{grid-template-columns:repeat(8,minmax(0,1fr));gap:6px}.aq-trader-shell[data-trader-reference="v3"] .aq-trader-module{min-height:104px;padding:7px;border-radius:9px;text-align:center}.aq-trader-shell[data-trader-reference="v3"] .aq-trader-module-icon{margin:auto;width:31px;height:31px}.aq-trader-shell[data-trader-reference="v3"] .aq-trader-module small{font-size:.43rem;margin-top:5px}.aq-trader-shell[data-trader-reference="v3"] .aq-trader-module h4{font-size:.62rem;margin:.15rem 0}.aq-trader-shell[data-trader-reference="v3"] .aq-trader-module p{font-size:.49rem;line-height:1.24;max-height:2.5em;overflow:hidden}.aq-trader-shell[data-trader-reference="v3"] .aq-trader-module .state{display:none}
.aq-trader-v3-intel{display:grid;grid-template-columns:1fr 1.25fr 1fr;gap:7px;margin-top:7px}.aq-trader-v3-stack{display:grid;gap:6px}.aq-trader-v3-panel{border:1px solid rgba(52,142,250,.32);border-radius:8px;padding:7px;background:linear-gradient(160deg,rgba(7,30,63,.9),rgba(3,14,31,.95));min-height:76px}.aq-trader-v3-panel h4{margin:0 0 5px;color:#dff4ff;font-size:.58rem}.aq-trader-v3-lines{display:grid;gap:3px}.aq-trader-v3-lines span{display:flex;justify-content:space-between;gap:5px;color:#aebfd4;font-size:.46rem}.aq-trader-v3-lines b{color:#62e2ba;font-size:.45rem}.aq-trader-v3-center{position:relative;display:grid;place-items:center;min-height:170px;border:1px solid rgba(46,145,255,.4);border-radius:10px;background:radial-gradient(circle at 50% 55%,rgba(45,132,255,.27),transparent 46%),linear-gradient(180deg,rgba(4,21,48,.92),rgba(2,10,24,.97))}.aq-trader-shell[data-trader-reference="v3"] .aq-trader-globe{width:138px;height:138px}.aq-trader-v3-center-label{position:absolute;bottom:8px;color:#9ec9ef;font-size:.48rem;font-weight:850;letter-spacing:.08em}
.aq-trader-v3-shortcuts{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:6px;margin-top:7px}.aq-trader-v3-shortcut{border:1px solid rgba(58,147,255,.35);border-radius:8px;padding:7px;text-align:center;background:linear-gradient(180deg,rgba(8,37,77,.88),rgba(4,17,38,.92));color:#e8f5ff;font-size:.53rem;font-weight:850}
@media(max-width:1000px){.aq-trader-v3-grid{grid-template-columns:118px minmax(0,1fr)}.aq-trader-v3-media{grid-template-columns:1fr 1fr}.aq-trader-shell[data-trader-reference="v3"] .aq-trader-module-grid{grid-template-columns:repeat(4,minmax(0,1fr))}.aq-trader-v3-intel{grid-template-columns:1fr}.aq-trader-v3-head{grid-template-columns:1fr}.aq-trader-v3-tools{justify-content:flex-start}}
@media(max-width:600px){.aq-trader-v3-grid{grid-template-columns:1fr}.aq-trader-v3-side{display:none}.aq-trader-v3-tabs{grid-template-columns:1fr 1fr}.aq-trader-v3-media{grid-template-columns:1fr}.aq-trader-shell[data-trader-reference="v3"] .aq-trader-module-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.aq-trader-v3-shortcuts{grid-template-columns:1fr 1fr}.aq-trader-v3-main{padding:7px}.aq-trader-v3-motto{text-align:left}}
@media (prefers-reduced-motion:reduce){
  .aq-premium-row{scroll-behavior:auto}
  .aq-premium-card,.aq-radar-dot,.aq-radar-sweep{animation:none !important}
  .aq-premium-card:hover{transform:none}
}
</style>
"""


def workspace_welcome_html(page: object, *, mode: object = "") -> str:
    """Compact area greeting. Presentation only; never grants access or executes actions."""
    key = str(page or "").strip()
    spec = WORKSPACE_WELCOME.get(key)
    if spec is None:
        return ""
    kicker, title, detail = spec
    mode_text = str(mode or "").strip()
    mode_suffix = f" · modo {mode_text}" if mode_text else ""
    return (
        '<section class="aq-workspace-welcome" aria-label="Boas-vindas da área">'
        f"<small>{escape(kicker + mode_suffix)}</small>"
        f"<strong>{escape(title)}</strong>"
        f"<p>{escape(detail)}</p>"
        '<p class="motto">Poderoso por dentro. Simples por fora.</p>'
        "</section>"
    )


def cockpit_header_html(
    title: object,
    summary: object,
    *,
    eyebrow: object = "ATLASQUANT · COMMAND SURFACE",
    telemetry: Mapping[str, object] | None = None,
) -> str:
    chips = "".join(
        f"<span>{escape(str(label))} <b>{escape(str(value))}</b></span>"
        for label, value in dict(telemetry or {}).items()
    )
    return (
        '<section class="aq-cockpit-head">'
        f'<div class="aq-cockpit-kicker">{escape(str(eyebrow))}</div>'
        f"<h2>{escape(str(title))}</h2>"
        f"<p>{escape(str(summary))}</p>"
        f'<div class="aq-cockpit-telemetry">{chips}</div>'
        "</section>"
    )


def _svg(kind: str) -> str:
    """Original abstract marks. No external asset and no borrowed logo."""
    common = {
        "radar": (
            '<svg viewBox="0 0 320 74" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">'
            '<rect width="320" height="74" fill="#0c1a2c"/>'
            '<circle cx="64" cy="37" r="22" fill="none" stroke="#8fd0c4" stroke-width="1.4"/>'
            '<circle cx="64" cy="37" r="12" fill="none" stroke="#d7b56d" stroke-width="1.2"/>'
            '<path class="aq-radar-sweep" d="M64 37 L84 22" stroke="#f5f8fc" stroke-width="1.4"/>'
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
    {"id":"ict","sector":"Leitura","title":"ICT / SMC","motif":"lab","page":"🔀 Pares","fast_page":"","summary":"Estrutura, liquidez e timing técnico aparecem como evidência contextual; o cartão não cria entrada nem ordem."},
    {"id":"calendar","sector":"Leitura","title":"Calendário Econômico","motif":"calendar","page":"🗂️ Histórico","fast_page":"","summary":"Abre Histórico para a evidência temporal já persistida. Não altera o calendário de coleta."},
    {"id":"lab","sector":"Operação","title":"Laboratório / Backtests","motif":"lab","page":"🧪 Backtest","fast_page":"","summary":"Abre o laboratório existente. Replay e métricas continuam os mesmos."},
    {"id":"paper","sector":"Operação","title":"Paper Trading","motif":"paper","page":"🧪 Backtest","fast_page":"","summary":"Não há mesa de execução nesta entrega. O cartão leva ao laboratório e não envia ordem, nem simulada nem real."},
    {"id":"guardian","sector":"Operação","title":"Guardião de Risco","motif":"shield","page":"⚡ Decisão","fast_page":"","summary":"Abre Decisão, onde os gates já calculados aparecem. Não muda limite, exposição nem autorização."},
    {"id":"academy","sector":"Ecossistema","title":"Academia","motif":"academy","page":"🎓 Aprender","fast_page":"🎓 Aprender","summary":"Material de estudo já publicado na área Aprender."},
    {"id":"journal","sector":"Ecossistema","title":"Diário","motif":"journal","page":"🗂️ Histórico","fast_page":"","summary":"Abre Histórico, o registro das leituras anteriores. Não grava um diário novo."},
    {"id":"invest","sector":"Ecossistema","title":"Investimentos","motif":"invest","page":"💰 Investir","fast_page":"💰 Investir","summary":"Abre a central de investimentos já existente, sem executar aplicação."},
    {"id":"business","sector":"Ecossistema","title":"Negócios","motif":"business","page":"🧠 AION","fast_page":"","summary":"Abre o cockpit Business existente no AION. O Portal Comercial 💼 Vendas continua separado."},
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


def premium_module_card_html(
    module: Mapping[str, str],
    *,
    locked: bool,
    available: bool,
    href: str = "",
) -> str:
    title = str(module.get("title") or "Área")
    if not available:
        badge = status_badge_html("Fora desta sessão", "neutral")
        action = ""
    elif locked and not href:
        badge = status_badge_html("Prévia no Iniciante", "warn")
        action = "Disponível no modo Avançado"
    elif locked:
        badge = status_badge_html("Prévia no Iniciante", "warn")
        action = f"Abrir {title}"
    elif href:
        badge = status_badge_html("Abrir área", "good")
        action = f"Abrir {title}"
    else:
        badge = status_badge_html("Acesso disponível", "good")
        action = ""
    body = (
        f'<div class="aq-premium-art">{_svg(str(module.get("motif") or "radar"))}</div>'
        f'<p class="aq-premium-kicker">{escape(str(module.get("sector") or ""))}</p>'
        f'<h4>{escape(str(module.get("title") or ""))}</h4>'
        f'<p>{escape(str(module.get("summary") or ""))}</p>'
        f'<div class="aq-premium-meta">{badge}'
        f'{status_badge_html("Navegação interna", "info")}</div>'
        + (f'<span class="aq-premium-open">{escape(action)}</span>' if action else "")
    )
    if href:
        return f'<a class="aq-premium-card" href="{escape(href, quote=True)}">{body}</a>'
    return f'<article class="aq-premium-card">{body}</article>'


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


def master_surface_state_html(state: object, detail: object, *, build_id: object = "") -> str:
    """Visible state of the Master Panel surface; never grants execution authority."""
    code = str(state or "").strip().upper()
    labels = {
        "READY": ("PRONTO PARA LEITURA", "good"),
        "SNAPSHOT": ("CONTINUIDADE POR SNAPSHOT", "warn"),
        "WAITING": ("AGUARDANDO MATRIZ", "warn"),
        "UNAVAILABLE": ("INDISPONÍVEL", "danger"),
    }
    label, tone = labels.get(code, ("ESTADO NÃO COMPROVADO", "danger"))
    build = "".join(ch for ch in str(build_id or "") if ch.isalnum())[:12]
    build_note = f" · Build {escape(build)}" if build else ""
    return (
        '<section class="aq-panel aq-master-state" role="status" data-master-state="'
        + escape(code or "UNKNOWN")
        + '"><h3>Painel Mestre · '
        + status_badge_html(label, tone)
        + "</h3><p>"
        + escape(str(detail or "Sem detalhe disponível."))
        + build_note
        + "</p></section>"
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


def allowed_premium_target(
    module_id: Any,
    *,
    mode: str,
    available_pages: Sequence[str],
    fast: bool = False,
) -> str:
    """Map a catalog id to an existing page. The raw query value is not a page."""
    wanted = str(module_id or "").strip()
    module = next((item for item in PREMIUM_MODULES if item["id"] == wanted), None)
    if module is None:
        return ""
    target = _destination(module, fast=fast)
    pages = {str(item) for item in list(available_pages or [])}
    if not target or target not in pages:
        return ""
    beginner = not str(mode or "").casefold().startswith("avan")
    open_pages = set(BEGINNER_OPEN_AREAS) | {"🎙️ Macro"}
    locked = beginner and target not in open_pages and target != "🧠 AION"
    if fast and locked:
        return ""
    return target


def pull_premium_card_id(query_params) -> str:
    """Read and clear aq_card. Only a catalog id is returned."""
    if query_params is None:
        return ""
    try:
        raw = query_params.get("aq_card", "")
    except Exception:
        return ""
    if isinstance(raw, (list, tuple)):
        raw = raw[0] if raw else ""
    card = str(raw or "").strip()
    if not card:
        return ""
    try:
        del query_params["aq_card"]
    except Exception:
        pass
    return card


def request_premium_card(
    session_state,
    card_id: Any,
    *,
    mode: str,
    available_pages: Sequence[str],
    fast: bool = False,
) -> str:
    """Store a validated catalog destination. Unknown ids do nothing."""
    target = allowed_premium_target(
        card_id,
        mode=mode,
        available_pages=available_pages,
        fast=fast,
    )
    if not target:
        return ""
    if target == "🧠 AION":
        if str(card_id or "").strip() == "business":
            from atlasquant_navigation_bridge import request_business_workspace
            request_business_workspace(session_state)
        else:
            from atlasquant_navigation_bridge import request_return_to_aion
            request_return_to_aion(session_state)
        return target
    session_state[_PENDING_KEY] = target
    return target


TRADER_REFERENCE_MODULE_IDS = ("macro", "micro", "geo", "fundamental", "ict", "calendar", "news", "master")
TRADER_REFERENCE_ICONS = {
    "macro": "▥", "micro": "⌁", "geo": "◎", "fundamental": "▤",
    "ict": "◈", "calendar": "□", "news": "⚠", "invest": "◆",
}


def _trader_module_lookup() -> dict[str, Mapping[str, str]]:
    return {str(item.get("id") or ""): item for item in PREMIUM_MODULES}


def _trader_score_chip(item: Mapping[str, object]) -> str:
    label = escape(str(item.get("label") or item.get("currency") or "MERCADO"))
    raw = item.get("score", item.get("value"))
    try:
        score = max(0.0, min(100.0, float(raw)))
    except (TypeError, ValueError):
        value = escape(str(raw or "CONTEXTO"))
        return f'<div class="aq-trader-tick neutral"><small>{label}</small><strong>{value}</strong></div>'
    tone = "good" if score >= 55 else ("warn" if score <= 45 else "neutral")
    return (
        f'<div class="aq-trader-tick {tone}"><small>{label}</small>'
        f'<strong>FORÇA {score:.0f}</strong></div>'
    )


def trader_cockpit_html(
    *,
    mode: str,
    available_pages: Sequence[str],
    fast: bool = False,
    ticker_items: Sequence[Mapping[str, object]] | None = None,
) -> str:
    """Use the approved art, with functional card hit regions and scoped menu."""
    from atlasquant_reference_ui import CSS, reference_html
    return "<style>" + CSS.read_text(encoding="utf-8") + "</style>" + reference_html("trader", mode=mode)


def premium_catalog_html(
    *,
    mode: str,
    available_pages: Sequence[str],
    fast: bool = False,
    ticker_items: Sequence[Mapping[str, object]] | None = None,
) -> str:
    """Reference-driven Trader cockpit for the Radar home."""
    return trader_cockpit_html(
        mode=mode,
        available_pages=available_pages,
        fast=fast,
        ticker_items=ticker_items,
    )


def catalog_is_home(active_page: str) -> bool:
    """The full catalog is the Radar home. Other areas keep their own workspace."""
    return str(active_page or "🎯 Radar") in {"🎯 Radar"}


def _render_premium_stateful_controls(
    *,
    mode: str,
    available_pages: Sequence[str],
    fast: bool,
) -> None:
    """Render valid authenticated actions without duplicating the whole visual catalog."""
    pages = [str(item) for item in list(available_pages or [])]
    modules = _trader_module_lookup()

    def launchable(module_ids: Sequence[str]) -> list[tuple[Mapping[str, str], str]]:
        rows: list[tuple[Mapping[str, str], str]] = []
        for module_id in module_ids:
            module = modules.get(str(module_id))
            if not module:
                continue
            target = allowed_premium_target(
                module["id"],
                mode=mode,
                available_pages=pages,
                fast=fast,
            )
            if target:
                rows.append((module, target))
        return rows

    primary = launchable(TRADER_REFERENCE_MODULE_IDS)
    if primary:
        st.caption("Acessos do cockpit")
        columns = st.columns(min(4, len(primary)))
        for index, (module, _target) in enumerate(primary):
            with columns[index % len(columns)]:
                if st.button(
                    str(module["title"]),
                    key=f"aq_trader_primary_{'fast' if fast else 'full'}_{module['id']}",
                    width="stretch",
                ):
                    request_premium_card(
                        st.session_state,
                        module["id"],
                        mode=mode,
                        available_pages=pages,
                        fast=fast,
                    )
                    st.rerun()

    primary_ids = set(TRADER_REFERENCE_MODULE_IDS)
    secondary_ids = [
        str(item["id"]) for item in PREMIUM_MODULES
        if str(item["id"]) not in primary_ids
    ]
    secondary = launchable(secondary_ids)
    if secondary:
        with st.expander("Mais áreas do Trader", expanded=False):
            columns = st.columns(min(4, len(secondary)))
            for index, (module, _target) in enumerate(secondary):
                with columns[index % len(columns)]:
                    if st.button(
                        str(module["title"]),
                        key=f"aq_trader_secondary_{'fast' if fast else 'full'}_{module['id']}",
                        width="stretch",
                    ):
                        request_premium_card(
                            st.session_state,
                            module["id"],
                            mode=mode,
                            available_pages=pages,
                            fast=fast,
                        )
                        st.rerun()


def render_premium_catalog(
    *,
    mode: str,
    available_pages: Sequence[str],
    fast: bool = False,
    active_page: str = "",
    ticker_items: Sequence[Mapping[str, object]] | None = None,
) -> None:
    """Render the catalog on Radar home; elsewhere keep only shared premium CSS."""
    pages = {str(item) for item in list(available_pages or [])}
    if st.session_state.get("aq_reference_connected"):
        st.markdown(PREMIUM_CSS, unsafe_allow_html=True)
        return
    if not catalog_is_home(active_page):
        # Off-home navigation already has the stable selector, contextual welcome
        # and Compass. Keep the premium design tokens without adding a second
        # generic navigation panel or a redundant "back home" action.
        st.markdown(PREMIUM_CSS, unsafe_allow_html=True)
        return
    st.markdown(PREMIUM_CSS, unsafe_allow_html=True)
    st.markdown(
        premium_catalog_html(
            mode=mode,
            available_pages=list(pages),
            fast=fast,
            ticker_items=ticker_items,
        ),
        unsafe_allow_html=True,
    )
    # Clicks are handled directly on the cards by the same-session V2 component.
    # No duplicate navigation strip is mounted below the artwork.
