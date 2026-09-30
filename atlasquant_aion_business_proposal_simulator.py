"""AION BUSINESS diagnostic and proposal simulator V1.

Pure/offline and draft-only. It turns explicitly supplied demo inputs into a
structured diagnostic, a simple client radar, a package fit and a professional
proposal draft. It never contacts a client, sets a final price, signs a contract,
charges, publishes, deploys or activates runtime.
"""
from __future__ import annotations

from hashlib import sha256
from typing import Any, Mapping, Sequence
import json
import re

SCHEMA = "ATLASQUANT_AION_BUSINESS_DIAGNOSTIC_PROPOSAL_SIMULATOR_V1"
VERSION = "1"
MAX_CHANNELS = 8
MAX_GOALS = 8

PACKAGE_CATALOG = {
    "ATENDIMENTO_CONVERSAO": {
        "label": "Atendimento & Conversão",
        "pillars": ("ATENDER", "CONVERTER"),
        "deliverables": (
            "Atendimento inicial / FAQ dentro do escopo aprovado",
            "Qualificação de leads",
            "Follow-up em fluxo controlado",
            "Agendamento ou definição de próximo passo",
            "Radar simples de atendimento e conversão",
        ),
    },
    "MARKETING_VENDAS": {
        "label": "Marketing & Vendas",
        "pillars": ("ATRAIR", "CONVERTER"),
        "deliverables": (
            "Plano de conteúdo e criativos",
            "Biblioteca inicial de peças e mensagens",
            "Acompanhamento de leads originados por campanhas",
            "Relatório simples de desempenho",
        ),
    },
    "GESTAO_INTELIGENTE": {
        "label": "Gestão Inteligente",
        "pillars": ("CONVERTER", "RETER"),
        "deliverables": (
            "Pipeline / CRM operacional",
            "Painel de resultados",
            "Relatórios AION",
            "Rotinas internas de acompanhamento",
            "Plano de ação por prioridade",
        ),
    },
    "AION_BUSINESS_COMPLETO": {
        "label": "AION Business Completo",
        "pillars": ("ATRAIR", "ATENDER", "CONVERTER", "RETER"),
        "deliverables": (
            "Diagnóstico e onboarding",
            "Atendimento e qualificação",
            "Follow-up e conversão",
            "Conteúdo / presença conforme escopo",
            "Radar e Portal do Cliente",
            "Manutenção, métricas e evolução controlada",
        ),
    },
}

PILLAR_LABELS = {
    "ATRAIR": "Atrair",
    "ATENDER": "Atender",
    "CONVERTER": "Converter",
    "RETER": "Reter",
}

_SHA = re.compile(r"^[0-9a-f]{64}$")


def _clean(value: Any, limit: int = 500) -> str:
    return " ".join(str(value or "").replace("\x00", "").split())[:limit]


def _number(value: Any, *, maximum: float | None = None) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except Exception:
        return None
    if number < 0:
        return None
    if maximum is not None and number > maximum:
        return None
    return number


def _bool_or_none(value: Any) -> bool | None:
    return value if type(value) is bool else None


def _list(values: Any, *, limit: int) -> list[str]:
    if not isinstance(values, Sequence) or isinstance(values, (str, bytes, bytearray)):
        return []
    out: list[str] = []
    for item in list(values)[:limit]:
        token = _clean(item, 120)
        if token and token not in out:
            out.append(token)
    return out


def _digest(value: Mapping[str, Any]) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return sha256(raw.encode("utf-8")).hexdigest()


def normalize_business_intake(raw: Mapping[str, Any] | None) -> dict[str, Any]:
    data = dict(raw or {}) if isinstance(raw, Mapping) else {}
    company = _clean(data.get("company_name"), 120)
    segment = _clean(data.get("segment"), 120)
    channels = _list(data.get("channels"), limit=MAX_CHANNELS)
    goals = _list(data.get("goals"), limit=MAX_GOALS)

    normalized = {
        "company_name": company,
        "segment": segment,
        "channels": channels,
        "goals": goals,
        "weekly_leads": _number(data.get("weekly_leads"), maximum=1_000_000),
        "avg_response_hours": _number(data.get("avg_response_hours"), maximum=720),
        "abandoned_quotes_monthly": _number(data.get("abandoned_quotes_monthly"), maximum=1_000_000),
        "returning_customers_pct": _number(data.get("returning_customers_pct"), maximum=100),
        "content_posts_monthly": _number(data.get("content_posts_monthly"), maximum=10_000),
        "has_followup_process": _bool_or_none(data.get("has_followup_process")),
        "has_crm": _bool_or_none(data.get("has_crm")),
        "has_sla": _bool_or_none(data.get("has_sla")),
        "tracks_conversion": _bool_or_none(data.get("tracks_conversion")),
        "notes": _clean(data.get("notes"), 1500),
    }
    required_missing = [name for name in ("company_name", "segment") if not normalized[name]]
    evidence_fields = (
        "weekly_leads",
        "avg_response_hours",
        "abandoned_quotes_monthly",
        "returning_customers_pct",
        "content_posts_monthly",
        "has_followup_process",
        "has_crm",
        "has_sla",
        "tracks_conversion",
    )
    observed = [name for name in evidence_fields if normalized[name] is not None]
    normalized["required_missing"] = required_missing
    normalized["observed_fields"] = observed
    normalized["evidence_coverage_pct"] = round(len(observed) / len(evidence_fields) * 100, 1)
    normalized["truth_state"] = "DEMO_USER_INPUT"
    normalized["real_client_verified"] = False
    return normalized


def _issue(
    pillar: str,
    severity: str,
    title: str,
    evidence: str,
    recommendation: str,
) -> dict[str, str]:
    return {
        "pillar": pillar,
        "pillar_label": PILLAR_LABELS[pillar],
        "severity": severity,
        "title": title,
        "evidence": evidence,
        "recommendation": recommendation,
    }


def diagnose_business(raw: Mapping[str, Any] | None) -> dict[str, Any]:
    intake = normalize_business_intake(raw)
    if intake["required_missing"]:
        return {
            "schema": SCHEMA,
            "version": VERSION,
            "state": "INCOMPLETE",
            "intake": intake,
            "issues": [],
            "pillar_scores": {},
            "missing": list(intake["required_missing"]),
            "truth_state": "DEMO_USER_INPUT",
            "executes_action": False,
        }

    issues: list[dict[str, str]] = []
    response = intake["avg_response_hours"]
    abandoned = intake["abandoned_quotes_monthly"]
    returning = intake["returning_customers_pct"]
    posts = intake["content_posts_monthly"]
    weekly = intake["weekly_leads"]

    if response is not None and response > 2:
        severity = "HIGH" if response > 6 else "MEDIUM"
        issues.append(_issue(
            "ATENDER", severity, "Tempo de resposta elevado",
            f"Entrada informada: {response:.1f} hora(s) em média.",
            "Revisar triagem, FAQ, prioridade e distribuição dos contatos.",
        ))
    if intake["has_sla"] is False:
        issues.append(_issue(
            "ATENDER", "MEDIUM", "Atendimento sem SLA definido",
            "Entrada informada: não existe SLA.",
            "Definir tempo-alvo, prioridade e regra de escalonamento.",
        ))
    if abandoned is not None and abandoned > 0:
        severity = "HIGH" if abandoned >= 15 else "MEDIUM"
        issues.append(_issue(
            "CONVERTER", severity, "Orçamentos sem retorno",
            f"Entrada informada: {int(abandoned)} orçamento(s) abandonado(s)/mês.",
            "Criar fluxo de recuperação e follow-up sujeito a revisão humana.",
        ))
    if intake["has_followup_process"] is False:
        issues.append(_issue(
            "CONVERTER", "HIGH", "Ausência de processo de follow-up",
            "Entrada informada: follow-up não estruturado.",
            "Definir cadência, responsáveis, critérios de pausa e próximos passos.",
        ))
    if intake["has_crm"] is False:
        issues.append(_issue(
            "CONVERTER", "MEDIUM", "Pipeline sem CRM estruturado",
            "Entrada informada: CRM ausente.",
            "Centralizar estágio, origem, responsável e próximo passo dos leads.",
        ))
    if intake["tracks_conversion"] is False:
        issues.append(_issue(
            "CONVERTER", "MEDIUM", "Conversão não medida",
            "Entrada informada: conversão não acompanhada.",
            "Definir indicadores mínimos e fonte confiável antes de otimizar.",
        ))
    if posts is not None and posts < 4:
        issues.append(_issue(
            "ATRAIR", "MEDIUM", "Presença de conteúdo irregular",
            f"Entrada informada: {int(posts)} publicação(ões)/mês.",
            "Avaliar calendário de conteúdo e criativos coerentes com o negócio.",
        ))
    if returning is not None and returning < 20:
        issues.append(_issue(
            "RETER", "MEDIUM", "Retenção / reativação pode ser trabalhada",
            f"Entrada informada: {returning:.1f}% de clientes retornando.",
            "Avaliar pós-venda, reativação, avaliações e relacionamento.",
        ))
    if weekly is not None and weekly >= 100 and intake["has_followup_process"] is not True:
        issues.append(_issue(
            "CONVERTER", "HIGH", "Volume alto sem acompanhamento proporcional",
            f"Entrada informada: {int(weekly)} lead(s)/semana.",
            "Priorizar qualificação e fila por intenção/urgência.",
        ))

    weights = {"HIGH": 35, "MEDIUM": 20, "LOW": 10}
    pillar_scores = {}
    for pillar in PILLAR_LABELS:
        points = sum(weights.get(item["severity"], 0) for item in issues if item["pillar"] == pillar)
        score = max(0, 100 - min(points, 100))
        pillar_scores[pillar] = {
            "label": PILLAR_LABELS[pillar],
            "health_score": score,
            "state": "ATTENTION" if points >= 35 else "WATCH" if points else "STABLE",
        }

    high = sum(1 for item in issues if item["severity"] == "HIGH")
    medium = sum(1 for item in issues if item["severity"] == "MEDIUM")
    state = "ATTENTION_HIGH" if high else "ATTENTION" if medium else "STABLE"

    result = {
        "schema": SCHEMA,
        "version": VERSION,
        "state": state,
        "intake": intake,
        "issues": issues,
        "pillar_scores": pillar_scores,
        "issue_count": len(issues),
        "high_priority_count": high,
        "truth_state": "DEMO_USER_INPUT",
        "real_client_verified": False,
        "promises_result": False,
        "executes_action": False,
    }
    result["diagnostic_digest"] = _digest({
        "company": intake["company_name"],
        "segment": intake["segment"],
        "observed_fields": intake["observed_fields"],
        "issues": issues,
    })
    return result


def recommend_package(diagnostic: Mapping[str, Any] | None) -> dict[str, Any]:
    row = dict(diagnostic or {}) if isinstance(diagnostic, Mapping) else {}
    issues = row.get("issues") if isinstance(row.get("issues"), Sequence) else []
    pillars = {str(item.get("pillar") or "") for item in issues if isinstance(item, Mapping)}
    high = sum(1 for item in issues if isinstance(item, Mapping) and item.get("severity") == "HIGH")

    if len(pillars) >= 3 or (len(pillars) >= 2 and high >= 2):
        package_id = "AION_BUSINESS_COMPLETO"
    elif pillars.intersection({"ATENDER", "CONVERTER"}):
        package_id = "ATENDIMENTO_CONVERSAO"
    elif "ATRAIR" in pillars:
        package_id = "MARKETING_VENDAS"
    elif "RETER" in pillars:
        package_id = "GESTAO_INTELIGENTE"
    else:
        package_id = "ATENDIMENTO_CONVERSAO"

    package = PACKAGE_CATALOG[package_id]
    return {
        "schema": SCHEMA,
        "state": "DRAFT_FIT",
        "package_id": package_id,
        "package_label": package["label"],
        "pillars": list(package["pillars"]),
        "deliverables": list(package["deliverables"]),
        "reason": (
            "Encaixe preliminar baseado somente nos gargalos informados no simulador. "
            "Empresa real exige diagnóstico e validação antes da proposta."
        ),
        "price": None,
        "price_state": "TO_DEFINE_AFTER_SCOPE",
        "promises_result": False,
        "executes_action": False,
    }


def client_radar(diagnostic: Mapping[str, Any] | None) -> dict[str, Any]:
    row = dict(diagnostic or {}) if isinstance(diagnostic, Mapping) else {}
    scores = row.get("pillar_scores") if isinstance(row.get("pillar_scores"), Mapping) else {}
    cards = []
    for pillar in ("ATRAIR", "ATENDER", "CONVERTER", "RETER"):
        score = scores.get(pillar) if isinstance(scores.get(pillar), Mapping) else {}
        cards.append({
            "pillar": pillar,
            "label": PILLAR_LABELS[pillar],
            "health_score": int(score.get("health_score") or 0),
            "state": str(score.get("state") or "UNKNOWN"),
        })
    issues = row.get("issues") if isinstance(row.get("issues"), Sequence) else []
    next_actions = [
        {
            "title": _clean(item.get("title"), 180),
            "recommendation": _clean(item.get("recommendation"), 400),
            "severity": _clean(item.get("severity"), 30),
        }
        for item in issues[:5]
        if isinstance(item, Mapping)
    ]
    return {
        "schema": SCHEMA,
        "mode": "DEMO_RADAR",
        "headline": (
            "Veja primeiro onde agir."
            if next_actions else
            "Nenhum alerta básico foi acionado pelos dados informados."
        ),
        "cards": cards,
        "next_actions": next_actions,
        "data_source": "DEMO_USER_INPUT",
        "real_client_verified": False,
        "executes_action": False,
    }


def build_proposal_draft(
    diagnostic: Mapping[str, Any] | None,
    package_fit: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    diag = dict(diagnostic or {}) if isinstance(diagnostic, Mapping) else {}
    intake = diag.get("intake") if isinstance(diag.get("intake"), Mapping) else {}
    if diag.get("state") == "INCOMPLETE" or not intake.get("company_name"):
        return {
            "schema": SCHEMA,
            "state": "BLOCKED_INCOMPLETE_DIAGNOSTIC",
            "proposal": {},
            "executes_action": False,
        }
    fit = dict(package_fit or {}) if isinstance(package_fit, Mapping) else recommend_package(diag)
    company = _clean(intake.get("company_name"), 120)
    segment = _clean(intake.get("segment"), 120)
    issues = diag.get("issues") if isinstance(diag.get("issues"), Sequence) else []
    issue_titles = [_clean(item.get("title"), 180) for item in issues if isinstance(item, Mapping)]
    deliverables = _list(fit.get("deliverables"), limit=20)

    proposal = {
        "title": f"Proposta preliminar AION Business — {company}",
        "company": company,
        "segment": segment,
        "status": "DRAFT_NOT_SENT",
        "objective": (
            "Organizar os gargalos identificados no diagnóstico e criar uma operação mais simples "
            "de acompanhar, com implantação e manutenção recorrente dentro do escopo aprovado."
        ),
        "diagnostic_summary": issue_titles[:8],
        "recommended_package": _clean(fit.get("package_label"), 160),
        "deliverables": deliverables,
        "implementation_phases": [
            "1. Validação do diagnóstico e escopo",
            "2. Onboarding, acessos mínimos e métricas",
            "3. Implantação em sandbox / ambiente controlado",
            "4. Validação com responsável da empresa",
            "5. Entrada assistida em operação após gates aplicáveis",
        ],
        "monthly_maintenance": [
            "Acompanhamento do funcionamento dentro do escopo",
            "Suporte e incidentes",
            "Revisão das métricas acordadas",
            "Ajustes controlados de fluxos",
            "Relatório periódico e próximos passos",
        ],
        "success_metrics_to_agree": [
            "Tempo médio de resposta",
            "Leads qualificados",
            "Follow-ups executados após autorização operacional",
            "Agendamentos / próximos passos",
            "Conversão quando houver fonte confiável",
            "Economia de tempo quando mensurável",
        ],
        "commercial_terms": {
            "implementation_price": "A DEFINIR APÓS ESCOPO",
            "monthly_maintenance": "A DEFINIR APÓS ESCOPO",
            "minimum_term": "A DEFINIR",
            "taxes_and_fees": "A DEFINIR",
        },
        "exclusions": [
            "Garantia de aumento de vendas ou lucro",
            "Ações fora do escopo contratado",
            "Uso de dados sem permissão adequada",
            "Publicação, cobrança ou contato automático sem autorização operacional",
        ],
        "next_step": "Revisar diagnóstico, confirmar escopo e somente então preparar proposta comercial final.",
        "sent": False,
        "signed": False,
        "payment_requested": False,
        "runtime_activated": False,
    }
    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": "DRAFT_READY",
        "proposal": proposal,
        "proposal_digest": _digest(proposal),
        "promises_result": False,
        "executes_action": False,
        "external_write": False,
    }


def proposal_text(draft: Mapping[str, Any] | None) -> str:
    row = dict(draft or {}) if isinstance(draft, Mapping) else {}
    proposal = row.get("proposal") if isinstance(row.get("proposal"), Mapping) else {}
    if row.get("state") != "DRAFT_READY" or not proposal:
        return ""
    lines = [
        proposal["title"],
        "",
        "OBJETIVO",
        proposal["objective"],
        "",
        "DIAGNÓSTICO PRELIMINAR",
    ]
    lines.extend(f"- {item}" for item in proposal["diagnostic_summary"])
    lines.extend([
        "",
        "PACOTE RECOMENDADO",
        proposal["recommended_package"],
        "",
        "ENTREGAS PREVISTAS",
    ])
    lines.extend(f"- {item}" for item in proposal["deliverables"])
    lines.extend(["", "IMPLANTAÇÃO"])
    lines.extend(f"- {item}" for item in proposal["implementation_phases"])
    lines.extend(["", "MANUTENÇÃO MENSAL"])
    lines.extend(f"- {item}" for item in proposal["monthly_maintenance"])
    lines.extend([
        "",
        "CONDIÇÕES COMERCIAIS",
        "- Implantação: A DEFINIR APÓS ESCOPO",
        "- Manutenção mensal: A DEFINIR APÓS ESCOPO",
        "",
        "PRÓXIMO PASSO",
        proposal["next_step"],
        "",
        "RASCUNHO INTERNO — NÃO ENVIADO / NÃO ASSINADO",
    ])
    return "\n".join(lines)


__all__ = [
    "SCHEMA",
    "VERSION",
    "PACKAGE_CATALOG",
    "PILLAR_LABELS",
    "normalize_business_intake",
    "diagnose_business",
    "recommend_package",
    "client_radar",
    "build_proposal_draft",
    "proposal_text",
]
