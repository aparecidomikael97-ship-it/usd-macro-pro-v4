"""AION BUSINESS Commercial Acquisition & Client Journey Demo V1.

Offline/demo-only commercial orchestration for prospecting, landing-page content,
lead qualification, outreach drafts, contract/onboarding handoff and content
planning. Nothing is published or sent, no contract is signed, no invoice is
issued and no client portal is provisioned by this module.
"""
from __future__ import annotations

from hashlib import sha256
from typing import Any, Mapping, Sequence
import json

SCHEMA = "ATLASQUANT_AION_BUSINESS_COMMERCIAL_ACQUISITION_DEMO_V1"
VERSION = "1"

CHANNELS = (
    "SITE_LANDING_PAGE",
    "CONTENT_SOCIAL",
    "REFERRALS",
    "LOCAL_PROSPECTING",
    "PARTNERS",
    "EVENTS",
)

CONTACT_PERMISSION_STATES = (
    "UNKNOWN",
    "PERMITTED_DEMO",
    "OPT_IN_DEMO",
    "DO_NOT_CONTACT",
)

FUNNEL_STAGES = (
    "PROSPECT",
    "QUALIFIED",
    "DIAGNOSTIC",
    "PROPOSAL_DRAFT",
    "CONTRACT_REVIEW",
    "ONBOARDING_READY",
)

CONTRACT_STATES = (
    "NOT_STARTED",
    "DRAFT_ONLY",
    "REVIEW_REQUIRED",
    "READY_FOR_SIGNATURE_REVIEW",
)

CONTENT_TYPES = (
    "EDUCATIONAL",
    "DEMO",
    "FAQ",
    "PROBLEM_SOLUTION",
    "CASE_STUDY_VERIFIED_ONLY",
)


def _clean(value: Any, limit: int = 500) -> str:
    return " ".join(str(value or "").replace("\x00", "").split())[:limit]


def _num(value: Any, *, maximum: float = 100.0) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        n = float(value)
    except Exception:
        return None
    if n < 0 or n > maximum:
        return None
    return n


def _seq(value: Any, limit: int = 20) -> list[Any]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    return list(value)[:limit]


def _digest(value: Mapping[str, Any]) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return sha256(raw.encode("utf-8")).hexdigest()


def build_channel_plan(segment: Any, *, channels: Sequence[str] | None = None) -> dict[str, Any]:
    segment_text = _clean(segment, 120) or "Negócio local"
    requested = [_clean(x, 60).upper() for x in _seq(channels, 10)]
    selected = [x for x in requested if x in CHANNELS]
    if not selected:
        selected = ["SITE_LANDING_PAGE", "CONTENT_SOCIAL", "REFERRALS", "LOCAL_PROSPECTING"]
    plays = {
        "SITE_LANDING_PAGE": "Página simples com problema, solução, demo e CTA para diagnóstico.",
        "CONTENT_SOCIAL": "Conteúdo educativo, demonstrações e perguntas frequentes sem promessa de resultado.",
        "REFERRALS": "Programa de indicação com regra e comissão somente após definição comercial.",
        "LOCAL_PROSPECTING": "Lista de empresas-alvo para pesquisa e revisão antes de qualquer contato.",
        "PARTNERS": "Parcerias com prestadores complementares, sempre com escopo e responsabilidade definidos.",
        "EVENTS": "Participação em eventos/comunidades para gerar conversas e diagnósticos.",
    }
    return {
        "schema": SCHEMA,
        "version": VERSION,
        "segment": segment_text,
        "channels": [{"id": c, "play": plays[c]} for c in selected],
        "automatic_contact": False,
        "automatic_publication": False,
        "automatic_spend": False,
        "executes_action": False,
    }


def build_landing_page_brief(
    *,
    segment: Any,
    offer_name: Any,
    primary_problem: Any,
    package_summary: Any,
) -> dict[str, Any]:
    segment_text = _clean(segment, 120)
    offer = _clean(offer_name, 160)
    problem = _clean(primary_problem, 500)
    package = _clean(package_summary, 600)
    missing = [
        k for k,v in (
            ("segment", segment_text),
            ("offer_name", offer),
            ("primary_problem", problem),
            ("package_summary", package),
        )
        if not v
    ]
    if missing:
        return {
            "schema": SCHEMA,
            "state": "INCOMPLETE",
            "missing": missing,
            "brief": {},
            "executes_action": False,
        }
    brief = {
        "headline": f"{offer}: torne o processo de {segment_text} mais simples de acompanhar.",
        "problem": problem,
        "solution": package,
        "sections": [
            "Problema que resolvemos",
            "Como funciona",
            "O que o cliente recebe",
            "Demo do Radar / Portal",
            "Perguntas frequentes",
            "CTA: solicitar diagnóstico",
        ],
        "cta": "Solicitar diagnóstico",
        "proof_rule": "Usar somente casos, métricas e depoimentos verificáveis.",
        "prohibited_claims": [
            "garantia de vendas",
            "garantia de lucro",
            "resultado sem fonte",
            "cliente fictício apresentado como real",
        ],
        "publication_state": "DRAFT_ONLY",
    }
    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": "DRAFT_READY",
        "brief": brief,
        "brief_digest": _digest(brief),
        "automatic_publication": False,
        "executes_action": False,
    }


def qualify_prospect(raw: Mapping[str, Any] | None) -> dict[str, Any]:
    data = dict(raw or {}) if isinstance(raw, Mapping) else {}
    company = _clean(data.get("company_name"), 120)
    segment = _clean(data.get("segment"), 120)
    permission = _clean(data.get("contact_permission_state"), 40).upper()
    if permission not in CONTACT_PERMISSION_STATES:
        permission = "UNKNOWN"

    pain = _num(data.get("pain_fit"))
    urgency = _num(data.get("urgency"))
    recurring_fit = _num(data.get("recurring_fit"))
    decision_access = _num(data.get("decision_maker_access"))
    data_readiness = _num(data.get("data_readiness"))

    values = [pain, urgency, recurring_fit, decision_access, data_readiness]
    if not company or not segment or any(v is None for v in values):
        return {
            "schema": SCHEMA,
            "state": "INCOMPLETE",
            "score": None,
            "company_name": company,
            "segment": segment,
            "contact_permission_state": permission,
            "automatic_contact": False,
            "executes_action": False,
        }
    score = (
        0.30 * pain
        + 0.20 * urgency
        + 0.20 * recurring_fit
        + 0.15 * decision_access
        + 0.15 * data_readiness
    )
    if score >= 75:
        state = "QUALIFIED"
    elif score >= 55:
        state = "NURTURE"
    else:
        state = "LOW_FIT"

    contact_review_allowed = permission in {"PERMITTED_DEMO", "OPT_IN_DEMO"}
    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": state,
        "score": round(score, 1),
        "company_name": company,
        "segment": segment,
        "contact_permission_state": permission,
        "contact_review_allowed": contact_review_allowed,
        "automatic_contact": False,
        "automatic_send": False,
        "executes_action": False,
    }


def outreach_draft(
    prospect: Mapping[str, Any] | None,
    *,
    sender_name: Any = "Mikael",
) -> dict[str, Any]:
    row = dict(prospect or {}) if isinstance(prospect, Mapping) else {}
    company = _clean(row.get("company_name"), 120)
    segment = _clean(row.get("segment"), 120)
    sender = _clean(sender_name, 120) or "Equipe AION"
    permission = _clean(row.get("contact_permission_state"), 40).upper()
    if row.get("state") not in {"QUALIFIED", "NURTURE"}:
        return {
            "schema": SCHEMA,
            "state": "BLOCKED_LOW_FIT",
            "draft": "",
            "sent": False,
            "executes_action": False,
        }
    if permission == "DO_NOT_CONTACT":
        return {
            "schema": SCHEMA,
            "state": "BLOCKED_DO_NOT_CONTACT",
            "draft": "",
            "sent": False,
            "executes_action": False,
        }
    draft = (
        f"Olá, equipe da {company}. Sou {sender}. Estou estudando como empresas de {segment} "
        "podem reduzir gargalos de atendimento e acompanhamento com processos mais simples. "
        "Se fizer sentido para vocês, posso apresentar um diagnóstico demonstrativo sem compromisso "
        "para entendermos onde existe perda de tempo ou oportunidade."
    )
    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": "DRAFT_REVIEW_REQUIRED",
        "draft": draft,
        "permission_state": permission,
        "requires_human_review": True,
        "sent": False,
        "automatic_send": False,
        "executes_action": False,
    }


def build_contract_handoff(
    *,
    company_name: Any,
    proposal_ready: Any,
    scope_confirmed: Any,
    privacy_terms_reviewed: Any,
    sla_defined: Any,
    commercial_terms_defined: Any,
) -> dict[str, Any]:
    company = _clean(company_name, 120)
    checks = {
        "proposal_ready": proposal_ready is True,
        "scope_confirmed": scope_confirmed is True,
        "privacy_terms_reviewed": privacy_terms_reviewed is True,
        "sla_defined": sla_defined is True,
        "commercial_terms_defined": commercial_terms_defined is True,
    }
    complete = bool(company and all(checks.values()))
    state = "READY_FOR_SIGNATURE_REVIEW" if complete else "REVIEW_REQUIRED"
    flow = [
        {"stage": "DIAGNOSTIC", "status": "COMPLETE" if checks["proposal_ready"] else "PENDING"},
        {"stage": "PROPOSAL_DRAFT", "status": "COMPLETE" if checks["proposal_ready"] else "PENDING"},
        {"stage": "SCOPE_REVIEW", "status": "COMPLETE" if checks["scope_confirmed"] else "PENDING"},
        {"stage": "PRIVACY_LGPD_REVIEW", "status": "COMPLETE" if checks["privacy_terms_reviewed"] else "PENDING"},
        {"stage": "SLA_REVIEW", "status": "COMPLETE" if checks["sla_defined"] else "PENDING"},
        {"stage": "COMMERCIAL_TERMS", "status": "COMPLETE" if checks["commercial_terms_defined"] else "PENDING"},
        {"stage": "SIGNATURE", "status": "NOT_EXECUTED"},
        {"stage": "BILLING_SETUP", "status": "NOT_EXECUTED"},
        {"stage": "ONBOARDING", "status": "NOT_STARTED"},
    ]
    return {
        "schema": SCHEMA,
        "version": VERSION,
        "company_name": company,
        "state": state,
        "checks": checks,
        "flow": flow,
        "contract_state": "READY_FOR_SIGNATURE_REVIEW" if complete else "REVIEW_REQUIRED",
        "contract_signed": False,
        "invoice_issued": False,
        "payment_collected": False,
        "client_portal_state": "TO_PROVISION_AFTER_APPROVED_ONBOARDING",
        "runtime_activated": False,
        "executes_action": False,
    }


def build_content_plan(
    *,
    segment: Any,
    weeks: int = 4,
    verified_case_available: Any = False,
) -> dict[str, Any]:
    segment_text = _clean(segment, 120) or "Negócio local"
    safe_weeks = max(1, min(int(weeks or 1), 12))
    items = []
    themes = [
        ("EDUCATIONAL", "Erro comum que faz empresas perderem tempo no atendimento."),
        ("DEMO", "Demonstração do Radar: como enxergar gargalos sem tela complicada."),
        ("FAQ", "Como funciona implantação + manutenção mensal."),
        ("PROBLEM_SOLUTION", "Lead sem retorno: como organizar acompanhamento."),
    ]
    if verified_case_available is True:
        themes.append(("CASE_STUDY_VERIFIED_ONLY", "Caso real com métricas verificadas e contexto completo."))
    for week in range(1, safe_weeks + 1):
        kind, theme = themes[(week - 1) % len(themes)]
        items.append({
            "week": week,
            "content_type": kind,
            "segment": segment_text,
            "theme": theme,
            "status": "DRAFT",
        })
    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": "PLAN_READY",
        "items": items,
        "verified_case_available": verified_case_available is True,
        "automatic_generation_to_public": False,
        "automatic_publication": False,
        "approval_required_before_publish": True,
        "executes_action": False,
    }


def commercial_funnel_snapshot(stages: Mapping[str, Any] | None) -> dict[str, Any]:
    data = dict(stages or {}) if isinstance(stages, Mapping) else {}
    counts = {}
    for stage in FUNNEL_STAGES:
        raw = data.get(stage)
        if isinstance(raw, bool):
            value = 0
        else:
            try:
                value = int(raw or 0)
            except Exception:
                value = 0
        counts[stage] = max(0, value)
    return {
        "schema": SCHEMA,
        "version": VERSION,
        "counts": counts,
        "total_prospects": counts["PROSPECT"],
        "diagnostics": counts["DIAGNOSTIC"],
        "proposal_drafts": counts["PROPOSAL_DRAFT"],
        "onboarding_ready": counts["ONBOARDING_READY"],
        "real_contacts_sent": 0,
        "real_contracts_signed": 0,
        "real_payments_collected": 0,
        "truth_state": "DEMO_USER_INPUT",
        "executes_action": False,
    }


__all__ = [
    "SCHEMA",
    "VERSION",
    "CHANNELS",
    "CONTACT_PERMISSION_STATES",
    "FUNNEL_STAGES",
    "CONTRACT_STATES",
    "CONTENT_TYPES",
    "build_channel_plan",
    "build_landing_page_brief",
    "qualify_prospect",
    "outreach_draft",
    "build_contract_handoff",
    "build_content_plan",
    "commercial_funnel_snapshot",
]
