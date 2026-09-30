"""AION BUSINESS Customer Success + SLA Demo V1.

Pure/offline and fixture-only. It models client health, support/SLA posture,
renewal readiness and expansion opportunities without contacting a client,
charging, publishing, modifying production or activating runtime.
"""
from __future__ import annotations

from hashlib import sha256
from typing import Any, Mapping, Sequence
import json

SCHEMA = "ATLASQUANT_AION_BUSINESS_CUSTOMER_SUCCESS_SLA_DEMO_V1"
VERSION = "1"

PRIORITIES = {
    "P1": {"label": "Crítica", "target_hours": 1},
    "P2": {"label": "Alta", "target_hours": 4},
    "P3": {"label": "Normal", "target_hours": 24},
    "P4": {"label": "Baixa", "target_hours": 72},
}

HEALTH_STATES = ("CRITICAL", "AT_RISK", "WATCH", "HEALTHY")
PAYMENT_STATES = ("UNKNOWN", "CURRENT", "OVERDUE_DEMO")


def _clean(value: Any, limit: int = 500) -> str:
    return " ".join(str(value or "").replace("\x00", "").split())[:limit]


def _number(value: Any, *, min_value: float = 0, max_value: float | None = None) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except Exception:
        return None
    if number < min_value:
        return None
    if max_value is not None and number > max_value:
        return None
    return number


def _exact_bool(value: Any) -> bool | None:
    return value if type(value) is bool else None


def _digest(value: Mapping[str, Any]) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return sha256(raw.encode("utf-8")).hexdigest()


def normalize_customer_signals(raw: Mapping[str, Any] | None) -> dict[str, Any]:
    data = dict(raw or {}) if isinstance(raw, Mapping) else {}
    normalized = {
        "company_name": _clean(data.get("company_name"), 120) or "Empresa Demo",
        "usage_pct": _number(data.get("usage_pct"), max_value=100),
        "goals_progress_pct": _number(data.get("goals_progress_pct"), max_value=100),
        "satisfaction_score": _number(data.get("satisfaction_score"), min_value=1, max_value=5),
        "days_since_last_activity": _number(data.get("days_since_last_activity"), max_value=3650),
        "open_tickets": _number(data.get("open_tickets"), max_value=100000),
        "critical_incidents": _number(data.get("critical_incidents"), max_value=100000),
        "onboarding_complete": _exact_bool(data.get("onboarding_complete")),
        "monthly_review_done": _exact_bool(data.get("monthly_review_done")),
        "payment_state": (
            _clean(data.get("payment_state"), 40).upper()
            if _clean(data.get("payment_state"), 40).upper() in PAYMENT_STATES
            else "UNKNOWN"
        ),
        "renewal_days": _number(data.get("renewal_days"), max_value=3650),
        "notes": _clean(data.get("notes"), 1200),
    }
    observed_fields = [
        key for key, value in normalized.items()
        if key not in {"company_name", "notes"} and value is not None
    ]
    normalized["observed_fields"] = observed_fields
    normalized["coverage_pct"] = round(len(observed_fields) / 9 * 100, 1)
    normalized["truth_state"] = "DEMO_USER_INPUT"
    normalized["real_client_verified"] = False
    return normalized


def customer_health(raw: Mapping[str, Any] | None) -> dict[str, Any]:
    signals = normalize_customer_signals(raw)
    score = 100
    flags: list[dict[str, str]] = []

    usage = signals["usage_pct"]
    if usage is not None:
        if usage < 20:
            score -= 35
            flags.append({"severity": "HIGH", "code": "LOW_USAGE", "message": "Uso muito baixo do serviço."})
        elif usage < 50:
            score -= 18
            flags.append({"severity": "MEDIUM", "code": "USAGE_WATCH", "message": "Uso abaixo do esperado."})

    goals = signals["goals_progress_pct"]
    if goals is not None:
        if goals < 25:
            score -= 25
            flags.append({"severity": "HIGH", "code": "GOALS_STALLED", "message": "Progresso dos objetivos está baixo."})
        elif goals < 60:
            score -= 12
            flags.append({"severity": "MEDIUM", "code": "GOALS_WATCH", "message": "Objetivos precisam de acompanhamento."})

    satisfaction = signals["satisfaction_score"]
    if satisfaction is not None:
        if satisfaction <= 2:
            score -= 30
            flags.append({"severity": "HIGH", "code": "LOW_SATISFACTION", "message": "Satisfação baixa no exercício."})
        elif satisfaction < 4:
            score -= 12
            flags.append({"severity": "MEDIUM", "code": "SATISFACTION_WATCH", "message": "Satisfação pede revisão."})

    inactivity = signals["days_since_last_activity"]
    if inactivity is not None:
        if inactivity > 30:
            score -= 25
            flags.append({"severity": "HIGH", "code": "INACTIVE", "message": "Longo período sem atividade."})
        elif inactivity > 14:
            score -= 10
            flags.append({"severity": "MEDIUM", "code": "ACTIVITY_WATCH", "message": "Atividade recente está baixa."})

    incidents = signals["critical_incidents"]
    if incidents is not None and incidents > 0:
        score -= min(40, int(incidents) * 20)
        flags.append({"severity": "HIGH", "code": "CRITICAL_INCIDENT", "message": "Existe incidente crítico no exercício."})

    if signals["onboarding_complete"] is False:
        score -= 15
        flags.append({"severity": "MEDIUM", "code": "ONBOARDING_INCOMPLETE", "message": "Onboarding ainda não terminou."})

    if signals["monthly_review_done"] is False:
        score -= 8
        flags.append({"severity": "LOW", "code": "REVIEW_PENDING", "message": "Revisão mensal ainda não foi concluída."})

    if signals["payment_state"] == "OVERDUE_DEMO":
        score -= 15
        flags.append({"severity": "MEDIUM", "code": "PAYMENT_OVERDUE_DEMO", "message": "Inadimplência apenas demonstrativa."})

    score = max(0, min(score, 100))
    if score < 35:
        state = "CRITICAL"
    elif score < 60:
        state = "AT_RISK"
    elif score < 80:
        state = "WATCH"
    else:
        state = "HEALTHY"

    result = {
        "schema": SCHEMA,
        "version": VERSION,
        "state": state,
        "health_score": score,
        "signals": signals,
        "flags": flags,
        "churn_risk": state in {"CRITICAL", "AT_RISK"},
        "real_client_verified": False,
        "executes_action": False,
    }
    result["health_digest"] = _digest({
        "company_name": signals["company_name"],
        "observed_fields": signals["observed_fields"],
        "score": score,
        "flags": flags,
    })
    return result


def sla_ticket(
    *,
    title: Any,
    priority: Any,
    age_hours: Any,
    status: Any = "OPEN",
) -> dict[str, Any]:
    token = _clean(priority, 20).upper()
    if token not in PRIORITIES:
        token = "P3"
    title_text = _clean(title, 240)
    age = _number(age_hours, max_value=100000)
    target = PRIORITIES[token]["target_hours"]
    breach = age is not None and age > target
    return {
        "schema": SCHEMA,
        "mode": "DEMO_TICKET",
        "title": title_text or "Chamado Demo",
        "priority": token,
        "priority_label": PRIORITIES[token]["label"],
        "target_hours": target,
        "age_hours": age,
        "status": _clean(status, 40).upper() or "OPEN",
        "sla_state": "BREACHED_DEMO" if breach else "WITHIN_TARGET_DEMO",
        "sent_to_support": False,
        "external_write": False,
        "executes_action": False,
    }


def success_plan(health: Mapping[str, Any] | None) -> dict[str, Any]:
    row = dict(health or {}) if isinstance(health, Mapping) else {}
    flags = row.get("flags") if isinstance(row.get("flags"), Sequence) else []
    actions = []
    seen = set()
    mappings = {
        "LOW_USAGE": "Agendar revisão de adoção e identificar barreiras de uso.",
        "USAGE_WATCH": "Revisar recursos pouco utilizados e treinamento necessário.",
        "GOALS_STALLED": "Revisar objetivo, métrica e escopo antes de expandir.",
        "GOALS_WATCH": "Comparar progresso com o plano de ação do período.",
        "LOW_SATISFACTION": "Priorizar conversa de sucesso do cliente antes de qualquer upsell.",
        "SATISFACTION_WATCH": "Coletar feedback específico sobre fricções.",
        "INACTIVE": "Investigar inatividade antes de presumir churn.",
        "ACTIVITY_WATCH": "Confirmar se a rotina de uso está adequada.",
        "CRITICAL_INCIDENT": "Resolver incidente crítico antes de outras iniciativas.",
        "ONBOARDING_INCOMPLETE": "Concluir onboarding e validações pendentes.",
        "REVIEW_PENDING": "Executar revisão mensal do serviço.",
        "PAYMENT_OVERDUE_DEMO": "Revisar situação comercial em ambiente real com responsável autorizado.",
    }
    for flag in flags:
        if not isinstance(flag, Mapping):
            continue
        code = _clean(flag.get("code"), 80)
        action = mappings.get(code)
        if action and action not in seen:
            actions.append({"source": code, "action": action, "status": "PENDING_REVIEW"})
            seen.add(action)
    if not actions:
        actions.append({
            "source": "HEALTHY_BASELINE",
            "action": "Manter acompanhamento, métricas e revisão periódica.",
            "status": "PENDING_REVIEW",
        })
    return {
        "schema": SCHEMA,
        "state": "PLAN_READY",
        "health_state": _clean(row.get("state"), 40) or "UNKNOWN",
        "actions": actions,
        "executes_action": False,
    }


def expansion_opportunity(health: Mapping[str, Any] | None) -> dict[str, Any]:
    row = dict(health or {}) if isinstance(health, Mapping) else {}
    signals = row.get("signals") if isinstance(row.get("signals"), Mapping) else {}
    state = _clean(row.get("state"), 40).upper()
    usage = signals.get("usage_pct")
    goals = signals.get("goals_progress_pct")
    satisfaction = signals.get("satisfaction_score")
    incidents = signals.get("critical_incidents")

    eligible = bool(
        state == "HEALTHY"
        and isinstance(usage, (int, float)) and not isinstance(usage, bool) and usage >= 70
        and isinstance(goals, (int, float)) and not isinstance(goals, bool) and goals >= 70
        and isinstance(satisfaction, (int, float)) and not isinstance(satisfaction, bool) and satisfaction >= 4
        and (incidents in (0, 0.0, None))
    )
    return {
        "schema": SCHEMA,
        "state": "EXPANSION_REVIEW_AVAILABLE" if eligible else "NO_UPSELL_NOW",
        "eligible_for_human_review": eligible,
        "reason": (
            "Cliente saudável no exercício; pode avaliar expansão somente se houver necessidade real."
            if eligible else
            "Priorize saúde, adoção e objetivos antes de oferecer expansão."
        ),
        "automatic_upsell": False,
        "executes_action": False,
    }


def renewal_readiness(health: Mapping[str, Any] | None) -> dict[str, Any]:
    row = dict(health or {}) if isinstance(health, Mapping) else {}
    signals = row.get("signals") if isinstance(row.get("signals"), Mapping) else {}
    days = signals.get("renewal_days")
    state = _clean(row.get("state"), 40).upper()
    if not isinstance(days, (int, float)) or isinstance(days, bool):
        return {
            "schema": SCHEMA,
            "state": "UNKNOWN",
            "review_window": False,
            "renewal_authorized": False,
            "executes_action": False,
        }
    review_window = days <= 60
    return {
        "schema": SCHEMA,
        "state": "REVIEW_REQUIRED" if review_window else "NOT_DUE",
        "review_window": review_window,
        "days_to_renewal": int(days),
        "health_state": state or "UNKNOWN",
        "recommended_focus": (
            "Resolver riscos antes de conversar sobre renovação."
            if state in {"CRITICAL", "AT_RISK"} else
            "Revisar valor entregue, métricas e próximos objetivos."
        ),
        "renewal_authorized": False,
        "automatic_renewal": False,
        "executes_action": False,
    }


__all__ = [
    "SCHEMA",
    "VERSION",
    "PRIORITIES",
    "HEALTH_STATES",
    "PAYMENT_STATES",
    "normalize_customer_signals",
    "customer_health",
    "sla_ticket",
    "success_plan",
    "expansion_opportunity",
    "renewal_readiness",
]
