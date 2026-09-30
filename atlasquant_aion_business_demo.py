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
    "business_demo_snapshot",
    "demo_business_radar",
    "client_portal_demo",
    "admin_training_demo",
]
