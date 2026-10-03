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
        "central_bullets": (
            "TradingView / Gráficos", "Radar de Mercado", "Análise Macro", "Geopolítica",
            "Calendário Econômico", "Laboratório de Estratégias", "Salas e Vídeos", "Ferramentas Avançadas",
        ),
    },
    "negocios": {
        "title": "Negócios",
        "kicker": "OPERAÇÃO & RECEITA",
        "summary": "Automação B2B, Revenue Ops, Micro-SaaS, serviços internacionais e produtos digitais próprios.",
        "tone": "teal",
        "hero": "Operação B2B organizada por receita, capacidade, margem, cliente e governança.",
        "central_bullets": (
            "Automação Empresarial B2B", "CRM e Gestão de Clientes", "Revenue Ops / Captação",
            "Atendimento e Suporte", "Integrações de Negócio", "Relatórios e ROI",
            "Implantação e Acompanhamento", "Portal do Cliente",
        ),
    },
    "investimentos": {
        "title": "Investimentos",
        "kicker": "PATRIMÔNIO & PLANEJAMENTO",
        "summary": "Comparação, planejamento, risco, renda e crescimento sem execução financeira automática.",
        "tone": "gold",
        "hero": "Visão patrimonial com alocação, liquidez, risco, objetivos e educação financeira.",
        "central_bullets": (
            "Renda Fixa", "Renda Variável", "Fundos e Produtos", "Carteira e Alocação",
            "Análise de Risco", "Relatórios Patrimoniais", "Educação Financeira", "Planejamento",
        ),
    },
    "aion": {
        "title": "AION",
        "kicker": "NÚCLEO INTELIGENTE",
        "summary": "Um único AION Core com memória, chat, biblioteca, tarefas, pesquisa e papéis internos.",
        "tone": "violet",
        "hero": "Coordenação, memória e inteligência do ecossistema com autoridade controlada por gates.",
        "central_bullets": (
            "Assistente Inteligente", "Análise e Recomendações", "Automação de Tarefas",
            "Conexão com todas as áreas", "Memória e Conhecimento", "Suporte à Decisão",
            "Auditoria / Checkpoint", "Evolução Contínua",
        ),
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
.aq-ws-hero p{margin:0;color:#cadbee;font-size:.75rem;line-height:1.45}
.aq-ws-hero-visual{position:relative;overflow:hidden;width:100%;height:158px;border:1px solid color-mix(in srgb,var(--ws-accent) 44%,transparent);border-radius:16px;background:
 radial-gradient(circle at 68% 42%,color-mix(in srgb,var(--ws-accent) 34%,transparent),transparent 30%),
 linear-gradient(145deg,rgba(8,28,58,.96),rgba(4,12,28,.99));box-shadow:inset 0 0 30px var(--ws-glow),0 0 24px var(--ws-glow)}
.aq-ws-hero-visual:before,.aq-ws-hero-visual:after{content:"";position:absolute;pointer-events:none}
.aq-ws-shell[data-workspace="negocios"] .aq-ws-hero-visual:before{left:18px;right:18px;bottom:22px;height:72px;background:
 linear-gradient(90deg,transparent 0 4%,#e58e1f 4% 11%,transparent 11% 15%,#ffad2f 15% 25%,transparent 25% 31%,#d77a19 31% 42%,transparent 42% 100%);clip-path:polygon(0 100%,0 62%,11% 62%,11% 43%,24% 43%,24% 23%,36% 23%,36% 55%,49% 55%,49% 35%,61% 35%,61% 12%,74% 12%,74% 52%,87% 52%,87% 30%,100% 30%,100% 100%)}
.aq-ws-shell[data-workspace="negocios"] .aq-ws-hero-visual:after{left:22px;right:22px;top:26px;height:70px;border-top:3px solid #ffb143;transform:skewY(-7deg);box-shadow:0 -11px 20px rgba(255,146,43,.15)}
.aq-ws-shell[data-workspace="investimentos"] .aq-ws-hero-visual:before{left:20px;right:20px;bottom:22px;height:82px;background:linear-gradient(90deg,#6a4710 0 9%,transparent 9% 13%,#9b6b17 13% 24%,transparent 24% 29%,#b77d1f 29% 42%,transparent 42% 47%,#d7982b 47% 61%,transparent 61% 67%,#f0b845 67% 82%,transparent 82%);clip-path:polygon(0 100%,0 67%,9% 67%,9% 56%,24% 56%,24% 45%,42% 45%,42% 33%,61% 33%,61% 20%,82% 20%,82% 8%,100% 8%,100% 100%)}
.aq-ws-shell[data-workspace="investimentos"] .aq-ws-hero-visual:after{width:88px;height:88px;border-radius:50%;right:32px;top:24px;border:1px solid rgba(255,218,109,.72);box-shadow:0 0 30px rgba(255,188,64,.25),inset 0 0 26px rgba(255,183,52,.16);background:repeating-linear-gradient(90deg,transparent 0 11px,rgba(255,218,109,.12) 11px 12px)}
.aq-ws-shell[data-workspace="aion"] .aq-ws-hero-visual:before{width:96px;height:122px;right:28px;top:18px;border:2px solid #b980ff;border-radius:54% 46% 46% 54%/42% 42% 58% 58%;background:
 radial-gradient(circle at 58% 34%,#d8bcff 0 3px,transparent 4px),
 linear-gradient(145deg,rgba(112,54,203,.68),rgba(22,20,75,.75));box-shadow:0 0 36px rgba(171,92,255,.32)}
.aq-ws-shell[data-workspace="aion"] .aq-ws-hero-visual:after{width:116px;height:116px;border-radius:50%;left:34px;top:22px;border:1px solid rgba(82,170,255,.65);background:
 repeating-radial-gradient(circle,rgba(84,180,255,.12) 0 1px,transparent 1px 10px),
 radial-gradient(circle,rgba(56,128,255,.32),rgba(18,27,83,.14) 58%,transparent 60%);box-shadow:0 0 34px rgba(63,140,255,.18)}
.aq-ws-kpis{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px;margin:10px 0 0}.aq-ws-kpi{border:1px solid color-mix(in srgb,var(--ws-accent) 26%,transparent);border-radius:11px;padding:8px 9px;background:rgba(4,15,33,.72);box-shadow:inset 0 0 18px var(--ws-glow)}.aq-ws-kpi small{display:block;color:#8faaca;font-size:.5rem;font-weight:800;letter-spacing:.06em}.aq-ws-kpi strong{display:block;margin-top:3px;color:#f6fbff;font-size:.68rem}
.aq-ws-orb{position:relative;width:128px;height:128px;margin:auto;border-radius:50%;border:1px solid color-mix(in srgb,var(--ws-accent) 72%,transparent);background:
 radial-gradient(circle at 35% 28%,color-mix(in srgb,var(--ws-accent) 42%,transparent),transparent 17%),
 radial-gradient(circle at 62% 63%,color-mix(in srgb,var(--ws-accent2) 45%,transparent),transparent 28%),
 radial-gradient(circle,#0a3268,#07162f 64%,#030c1c);
 box-shadow:0 0 34px var(--ws-glow),inset 0 0 34px var(--ws-glow)}
.aq-ws-orb:before,.aq-ws-orb:after{content:"";position:absolute;inset:16%;border-radius:50%;border:1px solid color-mix(in srgb,var(--ws-accent) 52%,transparent);animation:aq-ws-orbit 12s linear infinite}
.aq-ws-orb:before{transform:scaleX(.45)}.aq-ws-orb:after{transform:scaleY(.45);animation-direction:reverse}.aq-ws-orb b{position:absolute;inset:0;display:grid;place-items:center;color:#fff;font-size:2.2rem;text-shadow:0 0 20px var(--ws-accent)}
.aq-ws-section-head{display:flex;align-items:end;justify-content:space-between;gap:10px;margin:14px 2px 8px}.aq-ws-section-head h3{margin:0;color:#fff;font-size:.95rem}.aq-ws-section-head span{color:#8fb2d8;font-size:.62rem}
.aq-ws-modules{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:9px}.aq-ws-card{position:relative;overflow:hidden;min-height:145px;border:1px solid color-mix(in srgb,var(--ws-accent) 22%,rgba(111,169,234,.19));border-radius:15px;padding:11px;background:
 radial-gradient(circle at 100% 0%,var(--ws-glow),transparent 44%),
 linear-gradient(155deg,rgba(12,34,67,.94),rgba(6,18,39,.96));box-shadow:inset 0 1px 0 rgba(255,255,255,.035);transition:transform .22s ease,box-shadow .22s ease,border-color .22s ease}
.aq-ws-card:hover{transform:translateY(-5px);border-color:color-mix(in srgb,var(--ws-accent) 45%,transparent);box-shadow:0 16px 34px rgba(0,0,0,.28),0 0 22px var(--ws-glow)}
.aq-ws-card small{display:block;color:var(--ws-accent);font-size:.54rem;font-weight:950;letter-spacing:.11em}.aq-ws-card h4{margin:.3rem 0 .35rem;color:#fff;font-size:.82rem;line-height:1.25}.aq-ws-card p{margin:0;color:#c8d8eb;font-size:.65rem;line-height:1.38}
.aq-ws-state{display:inline-flex;margin-top:8px;border:1px solid color-mix(in srgb,var(--ws-accent) 32%,transparent);border-radius:999px;padding:3px 7px;color:#edf7ff;font-size:.53rem;font-weight:900;letter-spacing:.05em;background:rgba(5,18,40,.62)}
.aq-ws-state[data-state="CONECTADO"]{color:#79efc1;border-color:rgba(90,225,171,.35)}.aq-ws-state[data-state="PLANEJADO"]{color:#ffd98a;border-color:rgba(255,205,95,.34)}
.aq-ws-state[data-state="EM CONSTRUÇÃO"],.aq-ws-state[data-state="EM EVOLUÇÃO"]{color:#ffd38c;border-color:rgba(255,190,80,.28)}
.aq-ws-connected{margin-top:12px;border-top:1px solid rgba(129,175,226,.16);padding-top:12px}.aq-ws-truth{display:flex;flex-wrap:wrap;gap:6px;margin-top:10px}.aq-ws-truth span{border:1px solid rgba(126,175,230,.2);border-radius:999px;padding:4px 8px;color:#dceafd;font-size:.56rem;font-weight:850;background:rgba(5,18,40,.58)}
.aq-central-reference-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px;align-items:stretch}.aq-central-reference-card{--card-accent:#28a8ff;--card-glow:rgba(40,168,255,.28);position:relative;overflow:hidden;display:flex;flex-direction:column;min-height:520px;border:1px solid color-mix(in srgb,var(--card-accent) 62%,transparent);border-radius:16px;padding:0 14px 14px;background:linear-gradient(180deg,rgba(5,17,36,.98),rgba(3,10,23,.985));box-shadow:0 16px 38px rgba(0,0,0,.34),inset 0 0 28px rgba(30,104,190,.05);transition:transform .22s ease,box-shadow .22s ease,border-color .22s ease}
.aq-central-reference-card[data-area="negocios"]{--card-accent:#34e3a4;--card-glow:rgba(52,227,164,.24)}.aq-central-reference-card[data-area="investimentos"]{--card-accent:#f0bd58;--card-glow:rgba(240,189,88,.24)}.aq-central-reference-card[data-area="aion"]{--card-accent:#c05cff;--card-glow:rgba(192,92,255,.27)}
.aq-central-reference-card:hover{transform:translateY(-5px);box-shadow:0 22px 46px rgba(0,0,0,.42),0 0 26px var(--card-glow)}
.aq-central-reference-art{position:relative;display:grid;place-items:center;height:174px;margin:0 -14px 20px;border:0;border-bottom:1px solid color-mix(in srgb,var(--card-accent) 46%,transparent);border-radius:15px 15px 0 0;background:
 radial-gradient(circle at 50% 48%,var(--card-glow),transparent 48%),
 linear-gradient(145deg,rgba(11,39,79,.92),rgba(4,14,31,.97));overflow:hidden}
.aq-central-reference-art:before{content:"";position:absolute;inset:0;pointer-events:none;opacity:.32;background-image:
 linear-gradient(color-mix(in srgb,var(--card-accent) 12%,transparent) 1px,transparent 1px),
 linear-gradient(90deg,color-mix(in srgb,var(--card-accent) 10%,transparent) 1px,transparent 1px);background-size:24px 24px;mask-image:linear-gradient(to bottom,#000,transparent 85%)}
.aq-central-reference-art:after{content:"";position:absolute;inset:auto 0 0;height:52%;background:linear-gradient(180deg,transparent,rgba(1,6,16,.76));pointer-events:none}.aq-central-reference-art .aq-central-art{width:100%;height:100%;object-fit:cover;filter:drop-shadow(0 0 20px var(--card-glow)) saturate(1.18)}
.aq-central-reference-icon{position:absolute;left:16px;top:151px;z-index:3;display:grid;place-items:center;width:46px;height:46px;border:1px solid color-mix(in srgb,var(--card-accent) 75%,white 5%);border-radius:12px;background:linear-gradient(145deg,color-mix(in srgb,var(--card-accent) 34%,#071426),#07101f);box-shadow:0 0 24px var(--card-glow),inset 0 1px 0 rgba(255,255,255,.18);color:#fff;font-size:1.05rem;font-weight:950}
.aq-central-reference-card h3{margin:.35rem 0 .3rem;color:#fff;font-size:1.22rem;letter-spacing:.01em;text-transform:uppercase}.aq-central-reference-card p{margin:0;color:#aebdd2;font-size:.70rem;line-height:1.42;min-height:3.1em}
.aq-central-reference-list{display:grid;grid-template-columns:1fr;gap:4px;margin:12px 0 14px;padding-top:10px;border-top:1px solid rgba(130,174,225,.12)}.aq-central-reference-list span{position:relative;border:0;border-radius:0;padding:3px 4px 3px 18px;color:#d9e4f2;font-size:.62rem;font-weight:720;background:transparent}.aq-central-reference-list span:before{content:"◈";position:absolute;left:2px;top:2px;color:var(--card-accent);font-size:.63rem}
.aq-central-reference-card{text-decoration:none;color:inherit;cursor:pointer}
.aq-central-reference-card:focus-visible{outline:2px solid var(--card-accent);outline-offset:3px}
.aq-central-reference-cta{display:flex;align-items:center;justify-content:center;margin-top:auto;border:1px solid color-mix(in srgb,var(--card-accent) 68%,transparent);border-radius:9px;min-height:42px;color:#fff;font-size:.68rem;font-weight:900;letter-spacing:.03em;background:linear-gradient(90deg,color-mix(in srgb,var(--card-accent) 22%,#071426),rgba(6,17,37,.92));box-shadow:0 0 18px var(--card-glow)}
@keyframes aq-ws-orbit{from{transform:rotate(0) scaleX(.45)}to{transform:rotate(360deg) scaleX(.45)}}
@media (max-width:1100px){.aq-central-reference-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.aq-ws-modules{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media (max-width:800px){.aq-ws-layout{grid-template-columns:1fr}.aq-ws-side{display:none}.aq-ws-hero{grid-template-columns:1fr}.aq-ws-orb{width:110px;height:110px}.aq-ws-hero-visual{height:140px}.aq-ws-kpis{grid-template-columns:repeat(2,minmax(0,1fr))}.aq-ws-modules{grid-template-columns:repeat(2,minmax(0,1fr))}}
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
    icons = {"trader": "↗", "negocios": "▦", "investimentos": "◫", "aion": "✦"}
    return (
        f'<a class="aq-central-reference-card" data-area="{escape(key)}" '
        f'href="?aq_central={escape(key, quote=True)}" aria-label="Acessar {escape(spec["title"])}">'
        f'<div class="aq-central-reference-art">{art_html}</div>'
        f'<span class="aq-central-reference-icon" aria-hidden="true">{escape(icons.get(key, "◇"))}</span>'
        f'<h3>{escape(spec["title"])}</h3>'
        f'<p>{escape(spec["summary"])}</p>'
        f'<div class="aq-central-reference-list">{bullets}</div>'
        f'<div class="aq-central-reference-cta">ACESSAR {escape(spec["title"].upper())} <span aria-hidden="true">→</span></div>'
        '</a>'
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
    module_count = len(_MODULES.get(key, ()))
    connected_count = sum(1 for item in _MODULES.get(key, ()) if item.get("state") == "CONECTADO")
    preview_count = sum(1 for item in _MODULES.get(key, ()) if item.get("state") == "PRÉVIA")
    kpi_labels = {
        "negocios": ("Módulos", "Conectados", "Prévias", "Tenant"),
        "investimentos": ("Módulos", "Conectados", "Prévias", "Execução"),
        "aion": ("Módulos", "Conectados", "Prévias", "Core"),
    }
    kpi_values = {
        "negocios": (str(module_count), str(connected_count), str(preview_count), "ISOLADO"),
        "investimentos": (str(module_count), str(connected_count), str(preview_count), "BLOQUEADA"),
        "aion": (str(module_count), str(connected_count), str(preview_count), "ÚNICO"),
    }
    labels = kpi_labels[key]
    values = kpi_values[key]
    kpis = "".join(
        f'<div class="aq-ws-kpi"><small>{escape(label)}</small><strong>{escape(value)}</strong></div>'
        for label, value in zip(labels, values)
    )
    truth = [
        f"MODO {mode_label.upper()}",
        "SEM EXECUÇÃO AUTOMÁTICA",
        "ESTADOS DE VERDADE ATIVOS",
    ]
    if key == "negocios":
        truth.extend(("TENANT ISOLADO", "PUBLICAÇÃO REQUER APROVAÇÃO"))
    elif key == "investimentos":
        truth.extend(("SEM ORDEM AUTOMÁTICA", "SEM PROMESSA DE RETORNO"))
    elif key == "aion":
        truth.extend(("AUTORIDADE CONTROLADA", "AÇÕES SENSÍVEIS REQUEREM GATE"))
    for item in (extra_truth or ()):
        value = str(item).strip()
        if value and value not in truth:
            truth.append(value)
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
        f'<div class="aq-ws-truth">{truth_html}</div><div class="aq-ws-kpis">{kpis}</div></div>'
        f'<div class="aq-ws-hero-visual" data-scene="{escape(key)}" aria-hidden="true"><div class="aq-ws-orb"><b>{escape(spec["title"][:1])}</b></div></div>'
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
