"""Read-only demo model for the new AION BUSINESS experience.

This module turns the approved BUSINESS scope into a simple client/admin-facing
demo model. It has no provider, network, persistence, billing, publication,
contract, deploy or runtime activation path.

The goal is "Poderoso por dentro. Simples por fora.": complex internal
capabilities are represented as a small number of understandable pillars,
packages and a business radar.
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence

SCHEMA = "ATLASQUANT_AION_BUSINESS_DEMO_V1"
VERSION = "1"

PILLARS = (
    {
        "id": "ATRAIR",
        "label": "Atrair",
        "summary": "Conteúdo, criativos e presença para gerar oportunidades.",
        "client_question": "Como mais pessoas certas chegam até a empresa?",
    },
    {
        "id": "ATENDER",
        "label": "Atender",
        "summary": "Atendimento inicial, FAQ e organização de contatos.",
        "client_question": "Como responder melhor e mais rápido sem perder qualidade?",
    },
    {
        "id": "CONVERTER",
        "label": "Converter",
        "summary": "Qualificação, follow-up, propostas e recuperação de oportunidades.",
        "client_question": "Onde a empresa está perdendo vendas e como recuperar?",
    },
    {
        "id": "RETER",
        "label": "Reter",
        "summary": "Pós-venda, reativação, avaliações e relacionamento recorrente.",
        "client_question": "Como aumentar retorno, indicação e permanência dos clientes?",
    },
)

REVENUE_ENGINES = (
    {
        "id": "B2B_AUTOMATION",
        "label": "Automação B2B & Agentes de IA",
        "summary": "Automação de atendimento, operação e produtividade empresarial.",
    },
    {
        "id": "AION_MICRO_SAAS",
        "label": "Micro-SaaS AION",
        "summary": "Ferramentas próprias recorrentes construídas sobre capacidades validadas.",
    },
    {
        "id": "AI_SERVICES",
        "label": "Serviços de IA",
        "summary": "Diagnóstico, implantação, conteúdo, automações e melhoria operacional.",
    },
    {
        "id": "REVENUE_OPS",
        "label": "Revenue Ops & Captação",
        "summary": "Leads, qualificação, follow-up, conversão, retenção e métricas comerciais.",
    },
    {
        "id": "DIGITAL_PRODUCTS",
        "label": "Produtos Digitais Próprios",
        "summary": "Ativos digitais próprios criados somente após validação de escopo e qualidade.",
    },
)

PACKAGES = (
    {
        "id": "ATENDIMENTO_CONVERSAO",
        "label": "Atendimento & Conversão",
        "components": (
            "Chatbot inteligente",
            "Qualificação de leads",
            "Follow-up automático",
            "Agendamento",
        ),
        "outcome": "Organizar o atendimento e reduzir oportunidades esquecidas.",
    },
    {
        "id": "MARKETING_VENDAS",
        "label": "Marketing & Vendas",
        "components": (
            "Conteúdo e anúncios",
            "Vídeos curtos",
            "Imagens profissionais",
            "Campanhas e acompanhamento de leads",
        ),
        "outcome": "Dar consistência à divulgação e acompanhar melhor as oportunidades.",
    },
    {
        "id": "GESTAO_INTELIGENTE",
        "label": "Gestão Inteligente",
        "components": (
            "CRM / pipeline",
            "Painel de resultados",
            "Automações internas",
            "Relatórios AION",
        ),
        "outcome": "Mostrar o que está acontecendo na empresa sem exigir leitura técnica.",
    },
    {
        "id": "AION_BUSINESS_COMPLETO",
        "label": "AION Business Completo",
        "components": (
            "Atendimento",
            "Vendas",
            "Marketing",
            "Gestão",
        ),
        "outcome": "Concentrar os principais fluxos em uma solução recorrente e acompanhada.",
    },
)

STARTER_OFFER = {
    "id": "AION_PRESENCA_CONVERSAO",
    "label": "AION Presença & Conversão",
    "provisional_name": True,
    "components": (
        "Conteúdo e criativos",
        "Atendimento inicial / FAQ",
        "Reativação e follow-up de leads",
        "Relatório simples de resultados",
    ),
    "commercial_model": "IMPLANTACAO_MAIS_MANUTENCAO",
    "delivery_model": "HIBRIDO_AION_MAIS_SUPERVISAO_HUMANA",
}

CLIENT_JOURNEY = (
    "Prospecção",
    "Diagnóstico",
    "Proposta",
    "Implantação",
    "Mensalidade",
    "Métricas",
    "Upsell",
    "Renovação",
)

PORTAL_SECTIONS = (
    {
        "id": "RADAR",
        "label": "Radar do Negócio",
        "purpose": "Mostrar rapidamente o que está bem, o que exige atenção e as próximas ações.",
    },
    {
        "id": "RESULTADOS",
        "label": "Resultados",
        "purpose": "Leads, agendamentos, conversões, economia de tempo e indicadores acordados.",
    },
    {
        "id": "PLANO",
        "label": "Plano de Ação",
        "purpose": "Prioridades claras, responsáveis e próximos passos.",
    },
    {
        "id": "SUPORTE",
        "label": "Suporte & SLA",
        "purpose": "Chamados, prioridade, histórico, incidentes e acompanhamento.",
    },
)

TRAINING_STEPS = (
    "Entender o problema que o pacote resolve",
    "Saber explicar o que entra e o que não entra",
    "Demonstrar o Radar e o Portal em linguagem simples",
    "Simular perguntas e objeções do cliente",
    "Conduzir diagnóstico, proposta e onboarding",
    "Interpretar métricas e explicar resultados",
    "Reconhecer limites, riscos e quando chamar revisão humana",
)

BUSINESS_DEMO_CSS = """
<style>
.aqb-demo{border:1px solid rgba(242,193,78,.38);border-radius:22px;padding:16px;
background:radial-gradient(circle at 88% 4%,rgba(180,140,255,.19),transparent 32%),
linear-gradient(145deg,rgba(15,25,46,.96),rgba(7,17,31,.96));box-shadow:0 18px 45px rgba(0,0,0,.22)}
.aqb-demo-kicker{font-size:.64rem;font-weight:900;letter-spacing:.14em;color:#f2c14e}
.aqb-demo h2{margin:.3rem 0;color:#fff;font-size:1.35rem}.aqb-demo p{color:#d8e6f5;margin:.25rem 0}
.aqb-chips{display:flex;gap:6px;flex-wrap:wrap;margin:10px 0 12px}.aqb-chip{font-size:.63rem;font-weight:900;
padding:4px 8px;border-radius:999px;border:1px solid rgba(255,255,255,.15);color:#eaf3ff;background:rgba(12,31,52,.75)}
.aqb-chip.good{color:#9cf1da;border-color:rgba(115,241,218,.28)}.aqb-chip.warn{color:#ffe7a3;border-color:rgba(242,193,78,.32)}
.aqb-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px;margin:12px 0}.aqb-card{border:1px solid rgba(150,190,225,.18);
border-radius:14px;padding:10px 11px;background:rgba(10,27,48,.72)}.aqb-card strong{display:block;color:#fff;font-size:.83rem}
.aqb-card span{display:block;color:#cbd9e9;font-size:.71rem;line-height:1.35;margin-top:4px}
.aqb-section{margin-top:14px}.aqb-section-title{color:#fff;font-size:.85rem;font-weight:900;margin-bottom:7px}
.aqb-packages{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px}.aqb-package{border:1px solid rgba(180,140,255,.22);
border-radius:14px;padding:10px;background:rgba(21,24,56,.48)}.aqb-package b{color:#e9dcff;font-size:.8rem}.aqb-package ul{margin:6px 0 0 18px;padding:0;color:#d9e5f4;font-size:.7rem}
.aqb-flow{display:flex;flex-wrap:wrap;gap:5px}.aqb-step{font-size:.67rem;color:#dce7f4;border:1px solid rgba(137,187,225,.2);
border-radius:999px;padding:5px 8px;background:rgba(8,24,43,.7)}
.aqb-radar{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px}.aqb-alert{border-left:3px solid #f2c14e;border-radius:10px;padding:9px 10px;background:rgba(83,57,18,.24)}
.aqb-alert b{display:block;color:#ffe7a3;font-size:.75rem}.aqb-alert span{color:#d8e6f5;font-size:.69rem;line-height:1.35}
.aqb-note{margin-top:10px!important;font-size:.69rem!important;color:#aebfd3!important}
@media(max-width:760px){.aqb-grid{grid-template-columns:1fr 1fr}.aqb-packages{grid-template-columns:1fr}.aqb-radar{grid-template-columns:1fr}}
@media(max-width:430px){.aqb-grid{grid-template-columns:1fr}}
</style>
"""


def _clean(value: Any, limit: int = 240) -> str:
    return " ".join(str(value or "").replace("\x00", "").split())[:limit]


def _number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except Exception:
        return None
    return number if number >= 0 else None


def business_demo_snapshot() -> dict[str, Any]:
    """Canonical overview used by the admin/client demo UI."""
    return {
        "schema": SCHEMA,
        "version": VERSION,
        "title": "AION BUSINESS",
        "tagline": "Poderoso por dentro. Simples por fora.",
        "mode": "DEMO_SANDBOX",
        "certification_state": "CERTIFIED",
        "runtime_state": "OFF",
        "external_actions_state": "OFF",
        "pillars": [dict(item) for item in PILLARS],
        "revenue_engines": [dict(item) for item in REVENUE_ENGINES],
        "packages": [
            {
                **dict(item),
                "components": list(item["components"]),
            }
            for item in PACKAGES
        ],
        "starter_offer": {
            **dict(STARTER_OFFER),
            "components": list(STARTER_OFFER["components"]),
        },
        "client_journey": list(CLIENT_JOURNEY),
        "portal_sections": [dict(item) for item in PORTAL_SECTIONS],
        "training_steps": list(TRAINING_STEPS),
        "legacy_marketplace_primary": False,
        "legacy_marketplace_compatibility_only": True,
        "promises_financial_result": False,
        "executes_action": False,
        "payment_enabled": False,
        "publication_enabled": False,
        "external_contact_enabled": False,
        "runtime_activated": False,
    }


def demo_business_radar(raw: Mapping[str, Any] | None) -> dict[str, Any]:
    """Create a simple radar from explicitly supplied DEMO fixture data."""
    data = dict(raw or {}) if isinstance(raw, Mapping) else {}
    leads = _number(data.get("leads_open"))
    response_hours = _number(data.get("avg_response_hours"))
    abandoned = _number(data.get("abandoned_quotes"))
    returning = _number(data.get("returning_customers_pct"))

    metrics = {
        "leads_open": None if leads is None else int(leads),
        "avg_response_hours": response_hours,
        "abandoned_quotes": None if abandoned is None else int(abandoned),
        "returning_customers_pct": returning,
    }
    missing = [key for key, value in metrics.items() if value is None]
    alerts: list[dict[str, str]] = []

    if response_hours is not None and response_hours > 2:
        alerts.append({
            "area": "ATENDER",
            "severity": "ATTENTION",
            "title": "Tempo de resposta alto",
            "next_action": "Revisar atendimento inicial e distribuição dos contatos.",
        })
    if abandoned is not None and abandoned > 0:
        alerts.append({
            "area": "CONVERTER",
            "severity": "ATTENTION",
            "title": "Orçamentos sem retorno",
            "next_action": "Preparar fluxo de recuperação e follow-up para revisão humana.",
        })
    if leads is not None and leads > 30:
        alerts.append({
            "area": "CONVERTER",
            "severity": "ATTENTION",
            "title": "Fila de leads elevada",
            "next_action": "Priorizar qualificação e definir ordem de atendimento.",
        })
    if returning is not None and returning < 20:
        alerts.append({
            "area": "RETER",
            "severity": "OPPORTUNITY",
            "title": "Retenção pode ser trabalhada",
            "next_action": "Avaliar reativação, pós-venda e programa de relacionamento.",
        })

    if missing:
        state = "INCOMPLETE"
        headline = "Faltam dados para concluir o diagnóstico."
    elif alerts:
        state = "ATTENTION"
        headline = "Há pontos claros para revisar."
    else:
        state = "STABLE"
        headline = "Nenhum alerta básico foi acionado neste fixture."

    return {
        "schema": SCHEMA,
        "mode": "DEMO_FIXTURE",
        "state": state,
        "headline": headline,
        "metrics": metrics,
        "missing": missing,
        "alerts": alerts,
        "is_real_client_data": False,
        "promises_result": False,
        "executes_action": False,
    }


def client_portal_demo(
    company_name: Any = "Empresa Demo",
    *,
    package_id: Any = "ATENDIMENTO_CONVERSAO",
) -> dict[str, Any]:
    """Return the simple client-facing shell, with no live client data."""
    company = _clean(company_name, 120) or "Empresa Demo"
    package_token = _clean(package_id, 80).upper()
    package = next((dict(item) for item in PACKAGES if item["id"] == package_token), None)
    if package is None:
        package = dict(PACKAGES[0])
    return {
        "schema": SCHEMA,
        "mode": "DEMO_ONLY",
        "company_name": company,
        "package": {
            **package,
            "components": list(package["components"]),
        },
        "sections": [dict(item) for item in PORTAL_SECTIONS],
        "client_language": "SIMPLE",
        "technical_complexity_hidden": True,
        "real_client_connected": False,
        "runtime_activated": False,
        "executes_action": False,
    }


def admin_training_demo(step: Any = 1) -> dict[str, Any]:
    """Small training path for Mikael/admin before selling the service."""
    try:
        index = int(step) - 1
    except Exception:
        index = 0
    index = min(max(index, 0), len(TRAINING_STEPS) - 1)
    return {
        "schema": SCHEMA,
        "mode": "TRAINING",
        "current_step": index + 1,
        "total_steps": len(TRAINING_STEPS),
        "instruction": TRAINING_STEPS[index],
        "previous": TRAINING_STEPS[index - 1] if index > 0 else "",
        "next": TRAINING_STEPS[index + 1] if index + 1 < len(TRAINING_STEPS) else "",
        "completion_is_certification": False,
        "executes_action": False,
    }

def _html_escape(value: Any) -> str:
    text = _clean(value, 2000)
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


def business_demo_html() -> str:
    """Responsive HTML shell for the administrator-facing BUSINESS demo."""
    snapshot = business_demo_snapshot()
    radar = demo_business_radar({
        "leads_open": 42,
        "avg_response_hours": 3.5,
        "abandoned_quotes": 8,
        "returning_customers_pct": 12,
    })
    pillars = "".join(
        '<article class="aqb-card"><strong>'
        + _html_escape(item["label"])
        + '</strong><span>'
        + _html_escape(item["summary"])
        + "</span></article>"
        for item in snapshot["pillars"]
    )
    packages = "".join(
        '<article class="aqb-package"><b>'
        + _html_escape(item["label"])
        + "</b><ul>"
        + "".join("<li>" + _html_escape(component) + "</li>" for component in item["components"])
        + "</ul></article>"
        for item in snapshot["packages"]
    )
    flow = "".join(
        '<span class="aqb-step">' + _html_escape(step) + "</span>"
        for step in snapshot["client_journey"]
    )
    alerts = "".join(
        '<article class="aqb-alert"><b>'
        + _html_escape(item["title"])
        + '</b><span>'
        + _html_escape(item["next_action"])
        + "</span></article>"
        for item in radar["alerts"][:3]
    )
    return (
        BUSINESS_DEMO_CSS
        + '<section class="aqb-demo" data-business-demo="true" data-runtime="OFF">'
        + '<div class="aqb-demo-kicker">AION BUSINESS // DEMO SEGURA</div>'
        + "<h2>A empresa bate o olho e entende o que está acontecendo.</h2>"
        + "<p>"
        + _html_escape(snapshot["tagline"])
        + "</p>"
        + '<div class="aqb-chips">'
        + '<span class="aqb-chip good">BUSINESS CERTIFIED</span>'
        + '<span class="aqb-chip warn">SANDBOX / DEMO</span>'
        + '<span class="aqb-chip">RUNTIME OFF</span>'
        + '<span class="aqb-chip">SEM AÇÃO EXTERNA</span>'
        + "</div>"
        + '<div class="aqb-section-title">4 pilares</div><div class="aqb-grid">'
        + pillars
        + "</div>"
        + '<div class="aqb-section"><div class="aqb-section-title">Pacotes para vender solução completa</div>'
        + '<div class="aqb-packages">'
        + packages
        + "</div></div>"
        + '<div class="aqb-section"><div class="aqb-section-title">Jornada comercial</div>'
        + '<div class="aqb-flow">'
        + flow
        + "</div></div>"
        + '<div class="aqb-section"><div class="aqb-section-title">Exemplo do Radar do Negócio · dados fictícios</div>'
        + '<div class="aqb-radar">'
        + alerts
        + "</div></div>"
        + '<p class="aqb-note">Exemplo visual somente. Os números acima são fixtures fictícios, não dados de cliente. '
        + 'Marketplace/dropshipping permanece apenas como compatibilidade legada e não é o foco principal desta nova estrutura.</p>'
        + "</section>"
    )


__all__ = [
    "SCHEMA",
    "VERSION",
    "PILLARS",
    "REVENUE_ENGINES",
    "PACKAGES",
    "STARTER_OFFER",
    "CLIENT_JOURNEY",
    "PORTAL_SECTIONS",
    "TRAINING_STEPS",
    "BUSINESS_DEMO_CSS",
    "business_demo_snapshot",
    "demo_business_radar",
    "client_portal_demo",
    "admin_training_demo",
    "business_demo_html",
]
