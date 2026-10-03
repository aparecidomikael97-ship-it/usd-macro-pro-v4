"""Reference-driven ecosystem workspace shells for AtlasQuant/AION.

Presentation only. This module does not execute trades, publish content, spend
money, change credentials, widen RBAC, or call external providers. It gives the
four canonical workspaces one coherent visual language while keeping feature
truth states explicit.
"""
from __future__ import annotations

from html import escape
from typing import Any, Mapping, Sequence

SCHEMA = "ATLASQUANT_ECOSYSTEM_WORKSPACE_UI_V1"

_WORKSPACES: dict[str, dict[str, Any]] = {
    "trader": {
        "title": "Trader",
        "kicker": "MERCADO & ESTRATÉGIA",
        "summary": "Macro direciona. ICT/SMC localiza. O Guardião de Risco pode vetar.",
        "tone": "cyan",
        "hero": "Mercado global, leitura por camadas e execução bloqueada até os gates permitirem.",
        "central_bullets": ("Radar", "Macro & Micro", "ICT / SMC", "Risco"),
    },
    "negocios": {
        "title": "Negócios",
        "kicker": "OPERAÇÃO & RECEITA",
        "summary": "Automação B2B, Revenue Ops, Micro-SaaS, serviços internacionais e produtos digitais próprios.",
        "tone": "teal",
        "hero": "Operação B2B organizada por receita, capacidade, margem, cliente e governança.",
        "central_bullets": ("Automação B2B", "Revenue Ops", "Micro-SaaS", "IA Internacional"),
    },
    "investimentos": {
        "title": "Investimentos",
        "kicker": "PATRIMÔNIO & PLANEJAMENTO",
        "summary": "Comparação, planejamento, risco, renda e crescimento sem execução financeira automática.",
        "tone": "gold",
        "hero": "Visão patrimonial com alocação, liquidez, risco, objetivos e educação financeira.",
        "central_bullets": ("Renda Fixa", "Carteira", "Risco", "Planejamento"),
    },
    "aion": {
        "title": "AION",
        "kicker": "NÚCLEO INTELIGENTE",
        "summary": "Um único AION Core com memória, chat, biblioteca, tarefas, pesquisa e papéis internos.",
        "tone": "violet",
        "hero": "Coordenação, memória e inteligência do ecossistema com autoridade controlada por gates.",
        "central_bullets": ("Chat", "Memória", "Biblioteca", "Checkpoint"),
    },
}

_MODULES: dict[str, tuple[dict[str, str], ...]] = {
    "negocios": (
        {"id": "b2b", "title": "Automação empresarial B2B", "group": "FRENTE PRINCIPAL", "state": "PRÉVIA", "summary": "Workflows, integrações e operação empresarial orientada a automação."},
        {"id": "revenue", "title": "Captação / Revenue Ops", "group": "FRENTE PRINCIPAL", "state": "PRÉVIA", "summary": "Leads, CRM, pipeline, propostas, follow-up e conversão."},
        {"id": "saas", "title": "Micro-SaaS próprio", "group": "FRENTE PRINCIPAL", "state": "PRÉVIA", "summary": "Produto, usuários, recorrência, custos, capacidade e saúde operacional."},
        {"id": "international", "title": "Serviços internacionais de IA", "group": "FRENTE PRINCIPAL", "state": "PRÉVIA", "summary": "Projetos, propostas, clientes estrangeiros, entregas e margem."},
        {"id": "digital", "title": "Produtos digitais próprios", "group": "FRENTE PRINCIPAL", "state": "PRÉVIA", "summary": "Catálogo, entrega, conversão, vendas e desempenho dos ativos próprios."},
        {"id": "finops", "title": "Central Financeira / FinOps", "group": "GOVERNANÇA", "state": "EM CONSTRUÇÃO", "summary": "Cobrança, custos de IA/integrações, margem, inadimplência e rentabilidade."},
        {"id": "success", "title": "Saúde do Cliente", "group": "CLIENT SUCCESS", "state": "EM CONSTRUÇÃO", "summary": "Uso, satisfação, risco de cancelamento e oportunidade de expansão."},
        {"id": "sla", "title": "Suporte / SLA", "group": "OPERAÇÃO", "state": "EM CONSTRUÇÃO", "summary": "Chamados, prioridade, incidentes, histórico e onboarding."},
        {"id": "integrations", "title": "Hub de Integrações", "group": "OPERAÇÃO", "state": "EM CONSTRUÇÃO", "summary": "WhatsApp Business, e-mail, formulários, calendário, CRM, pagamentos e redes."},
        {"id": "privacy", "title": "Auditoria / LGPD", "group": "GOVERNANÇA", "state": "EM CONSTRUÇÃO", "summary": "Consentimento, finalidade, retenção, exportação, acesso, aprovações e rollback."},
        {"id": "team", "title": "Equipe & Acessos", "group": "GOVERNANÇA", "state": "EM CONSTRUÇÃO", "summary": "RBAC, capacidade, quotas, responsabilidades e isolamento por cliente."},
        {"id": "sandbox", "title": "Demo / Sandbox", "group": "SEGURANÇA", "state": "EM CONSTRUÇÃO", "summary": "Ambiente obrigatório de validação antes de liberar oferta ou automação em produção."},
        {"id": "aion-business", "title": "AION Negócios", "group": "AION", "state": "CONECTADO", "summary": "Workspace Business existente do mesmo AION Core, sujeito às permissões atuais."},
    ),
    "investimentos": (
        {"id": "fixed", "title": "Renda Fixa", "group": "CARTEIRA", "state": "CONECTADO", "summary": "Planejamento e comparação de renda, taxas, liquidez e horizonte."},
        {"id": "variable", "title": "Renda Variável", "group": "CARTEIRA", "state": "PRÉVIA", "summary": "Ações, ETFs, exposição, concentração, dividendos e longo prazo."},
        {"id": "funds", "title": "Fundos e Produtos", "group": "CARTEIRA", "state": "PRÉVIA", "summary": "Comparação educacional de produtos por características e perfil de risco."},
        {"id": "allocation", "title": "Carteira & Alocação", "group": "PLANEJAMENTO", "state": "PRÉVIA", "summary": "Distribuição por classes, objetivos, prazo, liquidez e diversificação."},
        {"id": "risk", "title": "Análise de Risco", "group": "PLANEJAMENTO", "state": "PRÉVIA", "summary": "Concentração, volatilidade, liquidez e horizonte sem promessa de retorno."},
        {"id": "planning", "title": "Planejamento", "group": "PLANEJAMENTO", "state": "CONECTADO", "summary": "Metas, projeções e cenários educacionais já presentes na Central Investir."},
        {"id": "income", "title": "Renda & Dividendos", "group": "RENDA", "state": "CONECTADO", "summary": "Estudos de renda, capital necessário e qualidade de ativos de renda."},
        {"id": "growth", "title": "Crescimento", "group": "LONGO PRAZO", "state": "CONECTADO", "summary": "Radar educacional de crescimento no modo avançado."},
        {"id": "reports", "title": "Relatórios Patrimoniais", "group": "RELATÓRIOS", "state": "EM CONSTRUÇÃO", "summary": "Evolução, entradas, rendimentos, distribuição e histórico."},
        {"id": "education", "title": "Educação Financeira", "group": "EDUCAÇÃO", "state": "PRÉVIA", "summary": "Trilhas e explicações para entender produtos, risco e planejamento."},
        {"id": "aion-invest", "title": "AION Investimentos", "group": "AION", "state": "PRÉVIA", "summary": "Explicação, comparação e planejamento; sem executar investimento automaticamente."},
    ),
    "aion": (
        {"id": "chat", "title": "Chat do AION", "group": "CONVERSA", "state": "PRÉVIA", "summary": "Conversa contínua com histórico, arquivos, imagens e tarefas. Implementação funcional rastreada na #537."},
        {"id": "history", "title": "Histórico", "group": "MEMÓRIA", "state": "EM CONSTRUÇÃO", "summary": "Conversas reabríveis, continuidade, busca, paginação e recuperação seletiva."},
        {"id": "memory", "title": "Memória", "group": "MEMÓRIA", "state": "CONECTADO", "summary": "Camadas de memória e continuidade existentes no AION Core, sem prometer contexto infinito."},
        {"id": "tasks", "title": "Tarefas & Execução", "group": "OPERAÇÃO", "state": "CONECTADO", "summary": "Tarefas duráveis e execução sujeita a risco, aprovação e autoridade explícita."},
        {"id": "library", "title": "Biblioteca AION", "group": "CONHECIMENTO", "state": "EM EVOLUÇÃO", "summary": "PDFs, proveniência, validação cruzada, conflito, quarentena e rejeição auditável."},
        {"id": "research", "title": "Pesquisa & Inteligência", "group": "CONHECIMENTO", "state": "CONECTADO", "summary": "Pesquisa e evidência passam pelo mesmo Core e não promovem hipótese a fato."},
        {"id": "checkpoint", "title": "Checkpoint Mestre", "group": "CONTINUIDADE", "state": "CONECTADO", "summary": "Decisões, implementações, validações, pendências, dependências e histórico."},
        {"id": "core", "title": "Núcleo / Orquestração", "group": "CORE", "state": "CONECTADO", "summary": "Um AION Core coordenando papéis, memória, ferramentas, políticas e evidências."},
        {"id": "roles", "title": "8 Papéis Internos", "group": "CORE", "state": "CONECTADO", "summary": "Responsabilidades especializadas do mesmo AION Core; não são oito IAs independentes."},
        {"id": "audit", "title": "Auditoria / Guardião", "group": "SEGURANÇA", "state": "CONECTADO", "summary": "Autoridade, aprovações, evidências, isolamento e veto continuam fail-closed."},
        {"id": "academy", "title": "Academy", "group": "EDUCAÇÃO", "state": "PRÉVIA", "summary": "Trilhas educacionais do ecossistema sob a mesma identidade AION."},
        {"id": "english", "title": "AION English", "group": "EDUCAÇÃO", "state": "PLANEJADO", "summary": "Inglês do A1 ao C1+, progresso persistente e fases futuras de voz/pronúncia. Rastreio #483."},
    ),
}

_SIDE_NAV: dict[str, tuple[str, ...]] = {
    "negocios": (
        "Início", "Visão Geral", "Empresas / Clientes", "Automação B2B", "Leads",
        "Revenue Ops", "CRM", "Propostas", "Follow-up", "Micro-SaaS",
        "Serviços Internacionais", "Produtos Digitais", "Integrações",
        "Financeiro / FinOps", "ROI", "Saúde do Cliente", "SLA / Suporte",
        "Auditoria / LGPD", "Equipe & Acessos", "Demo / Sandbox", "AION Negócios",
    ),
    "investimentos": (
        "Início", "Visão Geral", "Renda Fixa", "Renda Variável", "Fundos",
        "Produtos", "Carteira", "Alocação", "Risco", "Planejamento", "Objetivos",
        "Dividendos", "Longo Prazo", "Relatórios", "Educação Financeira", "AION Investimentos",
    ),
    "aion": (
        "Início", "Chat", "Histórico", "Memória", "Tarefas", "Biblioteca",
        "Pesquisa", "Checkpoint Mestre", "Núcleo", "8 Papéis Internos",
        "Auditoria", "Ferramentas", "Academy", "AION English", "Configurações",
    ),
}

WORKSPACE_CSS = r"""
<style>
.aq-ws-shell{--ws-accent:#57dfff;--ws-accent2:#416dff;--ws-glow:rgba(79,163,255,.18);
  position:relative;overflow:hidden;margin:4px 0 14px;border:1px solid color-mix(in srgb,var(--ws-accent) 34%,transparent);
  border-radius:26px;padding:14px;background:
  radial-gradient(circle at 52% 18%,var(--ws-glow),transparent 28rem),
  linear-gradient(145deg,rgba(5,15,35,.985),rgba(4,11,25,.99));
  box-shadow:0 28px 82px rgba(0,0,0,.38),inset 0 1px 0 rgba(255,255,255,.045)}
.aq-ws-shell[data-workspace="negocios"]{--ws-accent:#49e6b2;--ws-accent2:#1eae8b;--ws-glow:rgba(49,212,166,.17)}
.aq-ws-shell[data-workspace="investimentos"]{--ws-accent:#ffd36a;--ws-accent2:#c88f28;--ws-glow:rgba(226,171,63,.16)}
.aq-ws-shell[data-workspace="aion"]{--ws-accent:#bd8cff;--ws-accent2:#5f7dff;--ws-glow:rgba(156,100,255,.19)}
.aq-ws-shell:before{content:"";position:absolute;inset:0;opacity:.2;pointer-events:none;background-image:
 linear-gradient(color-mix(in srgb,var(--ws-accent) 14%,transparent) 1px,transparent 1px),
 linear-gradient(90deg,color-mix(in srgb,var(--ws-accent) 12%,transparent) 1px,transparent 1px);
 background-size:42px 42px;mask-image:linear-gradient(to bottom,#000,transparent 72%)}
.aq-ws-shell>*{position:relative;z-index:1}.aq-ws-top{display:flex;justify-content:space-between;align-items:center;gap:12px;padding:5px 5px 12px;border-bottom:1px solid rgba(143,180,225,.16)}
.aq-ws-brand{display:flex;align-items:center;gap:10px;color:#fff;font-weight:950;letter-spacing:.04em}
.aq-ws-mark{display:grid;place-items:center;width:34px;height:34px;border-radius:10px;background:linear-gradient(145deg,var(--ws-accent),var(--ws-accent2));color:#06101e;box-shadow:0 0 26px var(--ws-glow);font-weight:1000}
.aq-ws-motto{color:#eef6ff;font-size:.76rem;font-weight:850}.aq-ws-layout{display:grid;grid-template-columns:205px minmax(0,1fr);gap:12px;margin-top:12px}
.aq-ws-side{border:1px solid rgba(123,173,229,.16);border-radius:18px;padding:10px;background:rgba(6,18,39,.78);min-width:0}
.aq-ws-side-kicker{color:var(--ws-accent);font-size:.58rem;font-weight:950;letter-spacing:.12em;padding:3px 7px 8px}
.aq-ws-nav{display:grid;gap:4px}.aq-ws-nav span{display:block;border:1px solid transparent;border-radius:9px;padding:6px 8px;color:#cfe0f3;font-size:.64rem;font-weight:760;line-height:1.2}
.aq-ws-nav span:first-child{border-color:color-mix(in srgb,var(--ws-accent) 36%,transparent);background:color-mix(in srgb,var(--ws-accent) 10%,transparent);color:#fff}
.aq-ws-main{min-width:0}.aq-ws-hero{display:grid;grid-template-columns:minmax(0,1.2fr) 180px;align-items:center;gap:12px;border:1px solid color-mix(in srgb,var(--ws-accent) 28%,transparent);border-radius:20px;padding:16px;background:linear-gradient(145deg,rgba(11,31,63,.92),rgba(7,17,39,.94))}
.aq-ws-kicker{color:var(--ws-accent);font-size:.6rem;font-weight:950;letter-spacing:.14em}.aq-ws-hero h2{margin:.3rem 0 .4rem;color:#fff;font-size:clamp(1.35rem,2.5vw,2rem);letter-spacing:-.02em}
.aq-ws-hero p{margin:0;color:#cadbee;font-size:.75rem;line-height:1.45}.aq-ws-orb{position:relative;width:128px;height:128px;margin:auto;border-radius:50%;border:1px solid color-mix(in srgb,var(--ws-accent) 72%,transparent);background:
 radial-gradient(circle at 35% 28%,color-mix(in srgb,var(--ws-accent) 42%,transparent),transparent 17%),
 radial-gradient(circle at 62% 63%,color-mix(in srgb,var(--ws-accent2) 45%,transparent),transparent 28%),
 radial-gradient(circle,#0a3268,#07162f 64%,#030c1c);
 box-shadow:0 0 34px var(--ws-glow),inset 0 0 34px var(--ws-glow)}
.aq-ws-orb:before,.aq-ws-orb:after{content:"";position:absolute;inset:16%;border-radius:50%;border:1px solid color-mix(in srgb,var(--ws-accent) 52%,transparent);animation:aq-ws-orbit 12s linear infinite}
.aq-ws-orb:before{transform:scaleX(.45)}.aq-ws-orb:after{transform:scaleY(.45);animation-direction:reverse}.aq-ws-orb b{position:absolute;inset:0;display:grid;place-items:center;color:#fff;font-size:2.2rem;text-shadow:0 0 20px var(--ws-accent)}
.aq-ws-section-head{display:flex;align-items:end;justify-content:space-between;gap:10px;margin:14px 2px 8px}.aq-ws-section-head h3{margin:0;color:#fff;font-size:.95rem}.aq-ws-section-head span{color:#8fb2d8;font-size:.62rem}
.aq-ws-modules{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:9px}.aq-ws-card{position:relative;overflow:hidden;min-height:145px;border:1px solid rgba(111,169,234,.19);border-radius:15px;padding:11px;background:linear-gradient(155deg,rgba(12,34,67,.92),rgba(6,18,39,.94));box-shadow:inset 0 1px 0 rgba(255,255,255,.035);transition:transform .22s ease,box-shadow .22s ease,border-color .22s ease}
.aq-ws-card:hover{transform:translateY(-5px);border-color:color-mix(in srgb,var(--ws-accent) 45%,transparent);box-shadow:0 16px 34px rgba(0,0,0,.28),0 0 22px var(--ws-glow)}
.aq-ws-card small{display:block;color:var(--ws-accent);font-size:.54rem;font-weight:950;letter-spacing:.11em}.aq-ws-card h4{margin:.3rem 0 .35rem;color:#fff;font-size:.82rem;line-height:1.25}.aq-ws-card p{margin:0;color:#c8d8eb;font-size:.65rem;line-height:1.38}
.aq-ws-state{display:inline-flex;margin-top:8px;border:1px solid color-mix(in srgb,var(--ws-accent) 32%,transparent);border-radius:999px;padding:3px 7px;color:#edf7ff;font-size:.53rem;font-weight:900;letter-spacing:.05em;background:rgba(5,18,40,.62)}
.aq-ws-state[data-state="CONECTADO"]{color:#79efc1;border-color:rgba(90,225,171,.35)}.aq-ws-state[data-state="PLANEJADO"]{color:#ffd98a;border-color:rgba(255,205,95,.34)}
.aq-ws-state[data-state="EM CONSTRUÇÃO"],.aq-ws-state[data-state="EM EVOLUÇÃO"]{color:#ffd38c;border-color:rgba(255,190,80,.28)}
.aq-ws-connected{margin-top:12px;border-top:1px solid rgba(129,175,226,.16);padding-top:12px}.aq-ws-truth{display:flex;flex-wrap:wrap;gap:6px;margin-top:10px}.aq-ws-truth span{border:1px solid rgba(126,175,230,.2);border-radius:999px;padding:4px 8px;color:#dceafd;font-size:.56rem;font-weight:850;background:rgba(5,18,40,.58)}
.aq-central-reference-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:11px}.aq-central-reference-card{position:relative;overflow:hidden;min-height:315px;border:1px solid rgba(108,167,235,.22);border-radius:21px;padding:15px;background:linear-gradient(155deg,rgba(10,31,62,.94),rgba(5,16,36,.95));transition:transform .22s ease,box-shadow .22s ease}
.aq-central-reference-card:hover{transform:translateY(-5px);box-shadow:0 18px 36px rgba(0,0,0,.3)}.aq-central-reference-card[data-area="negocios"]{border-color:rgba(73,230,178,.26)}.aq-central-reference-card[data-area="investimentos"]{border-color:rgba(255,211,106,.26)}.aq-central-reference-card[data-area="aion"]{border-color:rgba(189,140,255,.3)}
.aq-central-reference-art{display:grid;place-items:center;height:120px;margin:-2px -2px 12px;border:1px solid rgba(126,182,241,.14);border-radius:15px;background:radial-gradient(circle at 50% 38%,rgba(61,135,255,.2),transparent 58%),linear-gradient(145deg,rgba(12,39,78,.75),rgba(7,19,42,.7))}
.aq-central-reference-card h3{margin:.1rem 0 .35rem;color:#fff;font-size:1rem}.aq-central-reference-card p{margin:0;color:#c6d8ec;font-size:.68rem;line-height:1.4;min-height:3.8em}
.aq-central-reference-list{display:grid;grid-template-columns:1fr 1fr;gap:5px;margin:10px 0}.aq-central-reference-list span{border:1px solid rgba(119,174,232,.13);border-radius:8px;padding:5px 6px;color:#ddecfb;font-size:.56rem;font-weight:780;background:rgba(7,20,43,.58)}
.aq-central-reference-cta{display:flex;align-items:center;justify-content:center;border:1px solid rgba(95,174,255,.32);border-radius:10px;min-height:34px;color:#fff;font-size:.66rem;font-weight:900;letter-spacing:.03em;background:linear-gradient(90deg,rgba(26,94,164,.76),rgba(70,69,174,.7))}
@keyframes aq-ws-orbit{from{transform:rotate(0) scaleX(.45)}to{transform:rotate(360deg) scaleX(.45)}}
@media (max-width:1100px){.aq-central-reference-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.aq-ws-modules{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media (max-width:800px){.aq-ws-layout{grid-template-columns:1fr}.aq-ws-side{display:none}.aq-ws-hero{grid-template-columns:1fr}.aq-ws-orb{width:110px;height:110px}.aq-ws-modules{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media (max-width:520px){.aq-ws-shell{padding:9px;border-radius:19px}.aq-ws-top{align-items:flex-start;flex-direction:column}.aq-ws-motto{text-align:left}.aq-central-reference-grid,.aq-ws-modules{grid-template-columns:1fr}.aq-central-reference-card{min-height:0}.aq-ws-card{min-height:0}.aq-ws-hero{padding:12px}}
@media (prefers-reduced-motion:reduce){.aq-ws-card,.aq-central-reference-card{transition:none}.aq-ws-card:hover,.aq-central-reference-card:hover{transform:none}.aq-ws-orb:before,.aq-ws-orb:after{animation:none !important}}
</style>
"""


def _area(value: object) -> str:
    key = str(value or "").strip().casefold()
    aliases = {"business": "negocios", "negócios": "negocios", "investir": "investimentos", "ia": "aion"}
    key = aliases.get(key, key)
    if key not in _WORKSPACES:
        raise ValueError("unknown ecosystem workspace")
    return key


def workspace_spec(area: object) -> dict[str, Any]:
    return dict(_WORKSPACES[_area(area)])


def workspace_modules(area: object) -> tuple[dict[str, str], ...]:
    return tuple(dict(item) for item in _MODULES.get(_area(area), ()))


def central_reference_card_html(area: object, art_html: str = "") -> str:
    key = _area(area)
    spec = _WORKSPACES[key]
    bullets = "".join(f"<span>{escape(str(item))}</span>" for item in spec["central_bullets"])
    return (
        f'<article class="aq-central-reference-card" data-area="{escape(key)}">'
        f'<div class="aq-central-reference-art">{art_html}</div>'
        f'<h3>{escape(spec["title"])}</h3>'
        f'<p>{escape(spec["summary"])}</p>'
        f'<div class="aq-central-reference-list">{bullets}</div>'
        f'<div class="aq-central-reference-cta">ACESSAR {escape(spec["title"].upper())}</div>'
        '</article>'
    )


def workspace_cockpit_html(
    area: object,
    *,
    mode: object = "",
    connected_html: str = "",
    extra_truth: Sequence[str] | None = None,
) -> str:
    key = _area(area)
    if key == "trader":
        raise ValueError("Trader uses atlasquant_premium_shell.trader_cockpit_html")
    spec = _WORKSPACES[key]
    nav = _SIDE_NAV.get(key, ())
    nav_html = "".join(f"<span>{escape(item)}</span>" for item in nav)
    cards = []
    for item in _MODULES.get(key, ()):
        cards.append(
            f'<article class="aq-ws-card" data-module="{escape(item["id"])}" '
            f'data-feature-state="{escape(item["state"])}">'
            f'<small>{escape(item["group"])}</small>'
            f'<h4>{escape(item["title"])}</h4>'
            f'<p>{escape(item["summary"])}</p>'
            f'<span class="aq-ws-state" data-state="{escape(item["state"])}">{escape(item["state"])}</span>'
            '</article>'
        )
    mode_label = str(mode or "").strip() or "SESSÃO ATUAL"
    truth = [
        f"MODO {mode_label.upper()}",
        "SEM EXECUÇÃO AUTOMÁTICA",
        "ESTADOS DE VERDADE ATIVOS",
    ]
    truth.extend(str(item) for item in (extra_truth or ()) if str(item).strip())
    truth_html = "".join(f"<span>{escape(item)}</span>" for item in truth)
    detail = f'<div class="aq-ws-connected">{connected_html}</div>' if connected_html else ""
    return (
        WORKSPACE_CSS
        + f'<section class="aq-ws-shell" data-workspace="{escape(key)}" data-schema="{SCHEMA}">'
        '<div class="aq-ws-top">'
        f'<div class="aq-ws-brand"><span class="aq-ws-mark">A</span><span>ATLASQUANT · {escape(spec["title"].upper())}</span></div>'
        '<div class="aq-ws-motto">Poderoso por dentro. Simples por fora.</div></div>'
        '<div class="aq-ws-layout">'
        f'<aside class="aq-ws-side"><div class="aq-ws-side-kicker">{escape(spec["title"].upper())}</div><div class="aq-ws-nav">{nav_html}</div></aside>'
        '<main class="aq-ws-main">'
        '<section class="aq-ws-hero">'
        f'<div><div class="aq-ws-kicker">{escape(spec["kicker"])}</div><h2>{escape(spec["title"])}</h2><p>{escape(spec["hero"])}</p>'
        f'<div class="aq-ws-truth">{truth_html}</div></div>'
        f'<div class="aq-ws-orb" aria-hidden="true"><b>{escape(spec["title"][:1])}</b></div>'
        '</section>'
        '<div class="aq-ws-section-head"><h3>Áreas do workspace</h3><span>Estrutura pronta para evolução funcional por módulo.</span></div>'
        f'<div class="aq-ws-modules">{"".join(cards)}</div>'
        f'{detail}'
        '</main></div></section>'
    )


__all__ = [
    "SCHEMA",
    "WORKSPACE_CSS",
    "central_reference_card_html",
    "workspace_cockpit_html",
    "workspace_modules",
    "workspace_spec",
]
