"""AION BUSINESS onboarding and implementation demo V1.

Pure/offline, fixture-only planning layer. It teaches how a client would move
from approved scope to onboarding, sandbox implementation, validation and
delivery without storing credentials or enabling external integrations.
"""
from __future__ import annotations

from hashlib import sha256
from typing import Any, Mapping, Sequence
import json

SCHEMA = "ATLASQUANT_AION_BUSINESS_ONBOARDING_IMPLEMENTATION_DEMO_V1"
VERSION = "1"

PHASES = (
    "ESCOPO",
    "DADOS_E_ACESSOS",
    "INTEGRACOES",
    "SANDBOX",
    "VALIDACAO",
    "ENTREGA_ASSISTIDA",
)

ACCESS_CATEGORIES = (
    "whatsapp_business",
    "email",
    "calendar",
    "crm",
    "forms",
    "payments",
    "social_media",
    "analytics",
)

DEFAULT_VALIDATION = (
    "Escopo revisado com responsável",
    "Dados mínimos identificados",
    "Permissões compatíveis com o escopo",
    "Integrações testadas em sandbox",
    "Fluxos principais validados",
    "Plano de rollback revisado",
    "Suporte/SLA definido",
    "Métricas e fonte de verdade definidas",
)


def _clean(value: Any, limit: int = 500) -> str:
    return " ".join(str(value or "").replace("\x00", "").split())[:limit]


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _seq(value: Any, limit: int = 30) -> list[Any]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    return list(value)[:limit]


def _digest(value: Mapping[str, Any]) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return sha256(raw.encode("utf-8")).hexdigest()


def onboarding_intake(
    *,
    company_name: Any,
    package_label: Any,
    business_owner: Any,
    business_goal: Any,
    requested_channels: Sequence[str] | None = None,
    requested_integrations: Sequence[str] | None = None,
) -> dict[str, Any]:
    company = _clean(company_name, 120)
    package = _clean(package_label, 160)
    owner = _clean(business_owner, 120)
    goal = _clean(business_goal, 500)
    channels = [_clean(x, 120) for x in _seq(requested_channels, 10)]
    integrations = [_clean(x, 120) for x in _seq(requested_integrations, 12)]
    channels = [x for x in channels if x]
    integrations = [x for x in integrations if x]
    missing = [
        name for name, value in (
            ("company_name", company),
            ("package_label", package),
            ("business_owner", owner),
            ("business_goal", goal),
        )
        if not value
    ]
    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": "READY_FOR_PLANNING" if not missing else "INCOMPLETE",
        "company_name": company,
        "package_label": package,
        "business_owner": owner,
        "business_goal": goal,
        "requested_channels": channels,
        "requested_integrations": integrations,
        "missing": missing,
        "real_credentials_supplied": False,
        "runtime_activated": False,
        "executes_action": False,
    }


def minimum_access_plan(
    intake: Mapping[str, Any] | None,
    requested_access: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return least-privilege access placeholders; never accepts secrets."""
    row = _mapping(intake)
    requested = _mapping(requested_access)
    items = []
    for category in ACCESS_CATEGORIES:
        raw = requested.get(category)
        enabled = raw is True
        items.append({
            "category": category,
            "needed": enabled,
            "access_level": "MINIMUM_REQUIRED" if enabled else "NONE",
            "credential_value": None,
            "secret_collection_allowed_here": False,
            "approval_required": enabled,
        })
    return {
        "schema": SCHEMA,
        "state": "PLAN_READY" if row.get("state") == "READY_FOR_PLANNING" else "BLOCKED",
        "principle": "LEAST_PRIVILEGE",
        "items": items,
        "stores_secret": False,
        "external_connection_performed": False,
        "executes_action": False,
    }


def build_implementation_plan(
    intake: Mapping[str, Any] | None,
    access_plan: Mapping[str, Any] | None,
) -> dict[str, Any]:
    row = _mapping(intake)
    access = _mapping(access_plan)
    if row.get("state") != "READY_FOR_PLANNING" or access.get("state") != "PLAN_READY":
        return {
            "schema": SCHEMA,
            "state": "BLOCKED",
            "phases": [],
            "executes_action": False,
        }

    phases = [
        {
            "phase": "ESCOPO",
            "goal": "Confirmar problema, entregas, exclusões, métricas e responsável.",
            "status": "PLANNED",
            "production_change": False,
        },
        {
            "phase": "DADOS_E_ACESSOS",
            "goal": "Definir somente dados e permissões mínimas necessárias.",
            "status": "PLANNED",
            "production_change": False,
        },
        {
            "phase": "INTEGRACOES",
            "goal": "Mapear integrações e testar contratos sem credenciais reais neste demo.",
            "status": "PLANNED",
            "production_change": False,
        },
        {
            "phase": "SANDBOX",
            "goal": "Montar e validar fluxos em ambiente isolado.",
            "status": "PLANNED",
            "production_change": False,
        },
        {
            "phase": "VALIDACAO",
            "goal": "Conferir fluxo, segurança, métricas, suporte e rollback.",
            "status": "PLANNED",
            "production_change": False,
        },
        {
            "phase": "ENTREGA_ASSISTIDA",
            "goal": "Preparar transição futura somente após aprovação operacional separada.",
            "status": "PLANNED",
            "production_change": False,
        },
    ]
    plan = {
        "company_name": row.get("company_name"),
        "package_label": row.get("package_label"),
        "business_owner": row.get("business_owner"),
        "phases": phases,
        "validation_checklist": list(DEFAULT_VALIDATION),
        "sandbox_first": True,
        "human_approval_before_live": True,
        "live_runtime_authorized": False,
        "real_credentials_present": False,
    }
    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": "PLAN_READY",
        "plan": plan,
        "plan_digest": _digest(plan),
        "runtime_activated": False,
        "external_write": False,
        "executes_action": False,
    }


def onboarding_status(
    plan: Mapping[str, Any] | None,
    completed_phases: Sequence[str] | None = None,
) -> dict[str, Any]:
    row = _mapping(plan)
    planned = _mapping(row.get("plan"))
    valid_names = {str(item.get("phase")) for item in _seq(planned.get("phases"), 10) if isinstance(item, Mapping)}
    completed = {
        _clean(item, 80).upper()
        for item in _seq(completed_phases, 10)
        if _clean(item, 80).upper() in valid_names
    }
    total = len(valid_names)
    done = len(completed)
    progress = round(done / total * 100, 1) if total else 0.0
    live_ready = bool(total and done == total)
    return {
        "schema": SCHEMA,
        "state": "DEMO_COMPLETE" if live_ready else "IN_PROGRESS",
        "completed_phases": sorted(completed),
        "completed_count": done,
        "total_phases": total,
        "progress_pct": progress,
        "eligible_for_live_review": live_ready,
        "live_runtime_authorized": False,
        "runtime_activated": False,
        "executes_action": False,
    }


def go_live_review_packet(
    plan: Mapping[str, Any] | None,
    status: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Prepare a review packet only; never approves or activates live runtime."""
    plan_row = _mapping(plan)
    status_row = _mapping(status)
    eligible = bool(
        plan_row.get("state") == "PLAN_READY"
        and status_row.get("state") == "DEMO_COMPLETE"
        and status_row.get("eligible_for_live_review") is True
        and _clean(plan_row.get("plan_digest"), 128)
    )
    return {
        "schema": "ATLASQUANT_AION_BUSINESS_GO_LIVE_REVIEW_PACKET_V1",
        "state": "LIVE_REVIEW_REQUIRED" if eligible else "BLOCKED",
        "eligible_for_human_review": eligible,
        "implementation_plan_digest": _clean(plan_row.get("plan_digest"), 128) if eligible else "",
        "approval_scope": "BUSINESS_LIVE_RUNTIME_ONLY",
        "human_approval_recorded": False,
        "runtime_activation_approved": False,
        "runtime_activated": False,
        "external_actions_authorized": False,
        "payment_authorized": False,
        "publication_authorized": False,
        "executes_action": False,
    }


__all__ = [
    "SCHEMA",
    "VERSION",
    "PHASES",
    "ACCESS_CATEGORIES",
    "DEFAULT_VALIDATION",
    "onboarding_intake",
    "minimum_access_plan",
    "build_implementation_plan",
    "onboarding_status",
    "go_live_review_packet",
]
