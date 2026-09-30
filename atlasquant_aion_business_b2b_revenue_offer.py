"""AION BUSINESS B2B Revenue Offer V1.

Internal productization and profitability contracts for the first Business
revenue engine: Atendimento & Automação Comercial com AION.

This module composes existing Business capabilities into a sellable-review
package. It never contacts a prospect, signs a contract, invoices, collects
payment, changes a price automatically, provisions a tenant, deploys or
activates runtime.
"""
from __future__ import annotations

from hashlib import sha256
from typing import Any, Mapping
import json
import math

from atlasquant_aion_business_proposal_simulator import PACKAGE_CATALOG
from atlasquant_aion_business_capacity_scale_manager import SCHEMA as CAPACITY_SCHEMA

SCHEMA = "ATLASQUANT_AION_BUSINESS_B2B_REVENUE_OFFER_V1"
VERSION = "1"

PRIORITY_OFFER_ID = "B2B_ATENDIMENTO_AUTOMACAO_COMERCIAL"
PRIORITY_PACKAGE_ID = "ATENDIMENTO_CONVERSAO"

PIPELINE_STAGES = (
    "TARGETING",
    "QUALIFICATION",
    "DIAGNOSTIC",
    "OFFER_REVIEW",
    "PROPOSAL_REVIEW",
    "CONTRACT_REVIEW",
    "ONBOARDING_REVIEW",
    "DELIVERY_REVIEW",
    "CUSTOMER_HEALTH",
    "RENEWAL_EXPANSION_REVIEW",
)

_STAGE_REQUIREMENTS = {
    "QUALIFICATION": ("target_defined", "contact_permission_reviewed"),
    "DIAGNOSTIC": ("prospect_qualified", "diagnostic_inputs_ready"),
    "OFFER_REVIEW": ("diagnostic_complete", "scope_draft_ready"),
    "PROPOSAL_REVIEW": ("offer_economics_ready", "scope_confirmed"),
    "CONTRACT_REVIEW": ("proposal_reviewed", "privacy_terms_reviewed", "sla_defined"),
    "ONBOARDING_REVIEW": ("contract_review_complete", "capacity_ready", "sandbox_ready"),
    "DELIVERY_REVIEW": ("onboarding_checklist_complete", "integrations_healthy"),
    "CUSTOMER_HEALTH": ("delivery_review_complete", "support_ready", "metrics_ready"),
    "RENEWAL_EXPANSION_REVIEW": ("customer_health_reviewed", "finance_reviewed"),
}


def _clean(value: Any, limit: int = 500) -> str:
    return " ".join(str(value or "").replace("\x00", "").split())[:limit]


def _num(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def _digest(value: Any) -> str:
    raw = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return sha256(raw.encode("utf-8")).hexdigest()


def priority_offer_template() -> dict[str, Any]:
    package = PACKAGE_CATALOG[PRIORITY_PACKAGE_ID]
    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": "INTERNAL_OFFER_TEMPLATE_READY",
        "offer_id": PRIORITY_OFFER_ID,
        "package_id": PRIORITY_PACKAGE_ID,
        "label": "AION Atendimento & Automação Comercial",
        "commercial_model": "IMPLEMENTATION_PLUS_MONTHLY_RECURRING",
        "primary_goal": "GENERATE_RECURRING_B2B_CASH_FLOW",
        "pillars": list(package["pillars"]),
        "deliverables": list(package["deliverables"]),
        "positioning": (
            "Organizar atendimento, qualificação, follow-up e próximo passo "
            "com automação controlada, métricas e revisão humana."
        ),
        "result_guarantee": False,
        "automatic_sale": False,
        "automatic_contact": False,
        "automatic_billing": False,
        "executes_action": False,
    }


def calculate_offer_economics(
    *,
    monthly_price_brl: Any,
    estimated_monthly_cost_brl: Any,
    implementation_fee_brl: Any,
    estimated_implementation_cost_brl: Any,
    minimum_margin_pct: Any,
) -> dict[str, Any]:
    price = _num(monthly_price_brl)
    monthly_cost = _num(estimated_monthly_cost_brl)
    implementation_fee = _num(implementation_fee_brl)
    implementation_cost = _num(estimated_implementation_cost_brl)
    floor = _num(minimum_margin_pct)

    blockers: list[str] = []
    if price is None or price <= 0:
        blockers.append("MONTHLY_PRICE_INVALID")
    if monthly_cost is None or monthly_cost < 0:
        blockers.append("MONTHLY_COST_INVALID")
    if implementation_fee is None or implementation_fee < 0:
        blockers.append("IMPLEMENTATION_FEE_INVALID")
    if implementation_cost is None or implementation_cost < 0:
        blockers.append("IMPLEMENTATION_COST_INVALID")
    if floor is None or not 0 <= floor < 100:
        blockers.append("MINIMUM_MARGIN_INVALID")

    if blockers:
        return {
            "schema": SCHEMA,
            "version": VERSION,
            "state": "OFFER_ECONOMICS_BLOCKED",
            "blockers": blockers,
            "automatic_price_change": False,
            "automatic_charge": False,
            "executes_action": False,
        }

    monthly_contribution = round(price - monthly_cost, 2)
    margin_pct = round(monthly_contribution / price * 100, 4)
    implementation_contribution = round(implementation_fee - implementation_cost, 2)
    minimum_sustainable_price = round(
        monthly_cost / (1 - floor / 100),
        2,
    )

    if margin_pct < floor:
        blockers.append("MONTHLY_MARGIN_BELOW_ADMIN_FLOOR")
    if implementation_contribution < 0:
        blockers.append("IMPLEMENTATION_FEE_BELOW_IMPLEMENTATION_COST")

    ready = not blockers
    payload = {
        "monthly_price_brl": round(price, 2),
        "estimated_monthly_cost_brl": round(monthly_cost, 2),
        "implementation_fee_brl": round(implementation_fee, 2),
        "estimated_implementation_cost_brl": round(implementation_cost, 2),
        "minimum_margin_pct": round(floor, 4),
        "margin_pct": margin_pct,
    } if ready else {}

    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": "OFFER_ECONOMICS_READY" if ready else "PRICING_REVIEW_REQUIRED",
        "monthly_price_brl": round(price, 2),
        "estimated_monthly_cost_brl": round(monthly_cost, 2),
        "monthly_contribution_brl": monthly_contribution,
        "margin_pct": margin_pct,
        "minimum_margin_pct": round(floor, 4),
        "minimum_sustainable_monthly_price_brl": minimum_sustainable_price,
        "implementation_fee_brl": round(implementation_fee, 2),
        "estimated_implementation_cost_brl": round(implementation_cost, 2),
        "implementation_contribution_brl": implementation_contribution,
        "blockers": blockers,
        "economics_digest": _digest(payload) if payload else "",
        "price_is_market_validated": False,
        "result_guarantee": False,
        "automatic_price_change": False,
        "automatic_charge": False,
        "executes_action": False,
    }


def _capacity_ready(capacity_plan: Mapping[str, Any] | None) -> bool:
    row = dict(capacity_plan or {}) if isinstance(capacity_plan, Mapping) else {}
    safe = row.get("safe_additional_tenants")
    return bool(
        row.get("schema") == CAPACITY_SCHEMA
        and row.get("state") == "CAPACITY_SCALE_ADMISSION_READY"
        and isinstance(safe, int)
        and not isinstance(safe, bool)
        and safe >= 1
        and row.get("automatic_customer_admission") is False
        and row.get("billing_authorized") is False
        and row.get("executes_action") is False
    )


def offer_readiness(
    economics: Mapping[str, Any] | None,
    capacity_plan: Mapping[str, Any] | None,
    *,
    diagnostic_complete: Any,
    scope_confirmed: Any,
    privacy_terms_reviewed: Any,
    sla_defined: Any,
    demo_sandbox_ready: Any,
    onboarding_checklist_ready: Any,
    support_capacity_ready: Any,
    integrations_healthy: Any,
    finance_guardrails_ready: Any,
) -> dict[str, Any]:
    eco = dict(economics or {}) if isinstance(economics, Mapping) else {}
    gates = {
        "diagnostic_complete": diagnostic_complete is True,
        "scope_confirmed": scope_confirmed is True,
        "economics_ready": eco.get("state") == "OFFER_ECONOMICS_READY",
        "capacity_ready": _capacity_ready(capacity_plan),
        "privacy_terms_reviewed": privacy_terms_reviewed is True,
        "sla_defined": sla_defined is True,
        "demo_sandbox_ready": demo_sandbox_ready is True,
        "onboarding_checklist_ready": onboarding_checklist_ready is True,
        "support_capacity_ready": support_capacity_ready is True,
        "integrations_healthy": integrations_healthy is True,
        "finance_guardrails_ready": finance_guardrails_ready is True,
    }
    blockers = [name for name, passed in gates.items() if not passed]
    ready = not blockers
    payload = {
        "offer_id": PRIORITY_OFFER_ID,
        "economics_digest": _clean(eco.get("economics_digest"), 128),
        "gates": gates,
    } if ready else {}

    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": (
            "READY_FOR_ADMIN_SALES_REVIEW"
            if ready
            else "OFFER_READINESS_BLOCKED"
        ),
        "offer_id": PRIORITY_OFFER_ID,
        "gates": gates,
        "blockers": blockers,
        "readiness_digest": _digest(payload) if payload else "",
        "external_contact_authorized": False,
        "proposal_send_authorized": False,
        "contract_signature_authorized": False,
        "billing_authorized": False,
        "customer_admission_authorized": False,
        "runtime_authorized": False,
        "result_guarantee": False,
        "executes_action": False,
    }


def commercial_pipeline_template() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": "COMMERCIAL_PIPELINE_DEFINED",
        "stages": [
            {
                "order": index + 1,
                "stage": stage,
                "status": "NOT_STARTED",
                "required_evidence": list(_STAGE_REQUIREMENTS.get(stage, ())),
            }
            for index, stage in enumerate(PIPELINE_STAGES)
        ],
        "automatic_stage_advance": False,
        "automatic_contact": False,
        "automatic_contract": False,
        "automatic_billing": False,
        "automatic_onboarding": False,
        "executes_action": False,
    }


def pipeline_transition_review(
    *,
    current_stage: Any,
    target_stage: Any,
    evidence: Mapping[str, Any] | None,
) -> dict[str, Any]:
    current = _clean(current_stage, 80).upper()
    target = _clean(target_stage, 80).upper()
    data = dict(evidence or {}) if isinstance(evidence, Mapping) else {}

    if current not in PIPELINE_STAGES or target not in PIPELINE_STAGES:
        return {
            "schema": SCHEMA,
            "state": "PIPELINE_TRANSITION_BLOCKED",
            "reason": "UNKNOWN_STAGE",
            "executes_action": False,
        }

    current_index = PIPELINE_STAGES.index(current)
    target_index = PIPELINE_STAGES.index(target)
    adjacent = target_index == current_index + 1
    requirements = _STAGE_REQUIREMENTS.get(target, ())
    missing = [key for key in requirements if data.get(key) is not True]
    ready = adjacent and not missing

    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": (
            "PIPELINE_TRANSITION_REVIEW_READY"
            if ready
            else "PIPELINE_TRANSITION_BLOCKED"
        ),
        "current_stage": current,
        "target_stage": target,
        "adjacent_transition": adjacent,
        "required_evidence": list(requirements),
        "missing_evidence": missing,
        "stage_advance_authorized": False,
        "external_action_authorized": False,
        "executes_action": False,
    }


def revenue_priority_snapshot() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": "BUSINESS_REVENUE_PRIORITY_DEFINED",
        "short_term_primary_engine": "BUSINESS_B2B_RECURRING_SERVICES",
        "priority_offer_id": PRIORITY_OFFER_ID,
        "revenue_model": "IMPLEMENTATION_PLUS_MONTHLY_RECURRING",
        "dropshipping_priority": False,
        "trade_is_required_to_fund_ecosystem": False,
        "business_may_fund_ecosystem": True,
        "profitability_measured_per_client": True,
        "capacity_checked_before_onboarding": True,
        "result_guarantee": False,
        "executes_action": False,
    }


__all__ = [
    "SCHEMA",
    "VERSION",
    "PRIORITY_OFFER_ID",
    "PRIORITY_PACKAGE_ID",
    "PIPELINE_STAGES",
    "priority_offer_template",
    "calculate_offer_economics",
    "offer_readiness",
    "commercial_pipeline_template",
    "pipeline_transition_review",
    "revenue_priority_snapshot",
]
