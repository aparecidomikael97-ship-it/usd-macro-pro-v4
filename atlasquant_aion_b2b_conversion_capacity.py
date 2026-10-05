"""AION B2B pilot-to-managed-service conversion and capacity gate.

Pure/offline decision support. It recommends a package tier and evaluates
commercial margin/capacity evidence after a healthy pilot. It never signs,
renews, bills, provisions, deploys, changes scope, or contacts a customer.
"""
from __future__ import annotations

from hashlib import sha256
from typing import Any, Mapping, Sequence
import json
import math

SCHEMA = "ATLASQUANT_AION_B2B_CONVERSION_CAPACITY_V1"
PACKAGES = ("ESSENCIAL", "PROFISSIONAL", "COMPLETO")
NEED_TRACKS = ("ATENDIMENTO_CONVERSAO", "MARKETING_VENDAS", "GESTAO_INTELIGENTE")


def _text(value: Any, limit: int = 320) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(value.replace("\x00", "").split())[:limit]


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _positive_int(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


def _scope(raw: Mapping[str, Any] | None) -> dict[str, str]:
    data = dict(raw) if isinstance(raw, Mapping) else {}
    return {
        "owner_id": _text(data.get("owner_id"), 120),
        "tenant_id": _text(data.get("tenant_id"), 120),
        "workspace_id": _text(data.get("workspace_id"), 120),
    }


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _digest(value: Any) -> str:
    return "sha256:" + sha256(_canonical(value).encode("utf-8")).hexdigest()


def _refs(value: Any, limit: int = 50) -> list[str]:
    if not isinstance(value, (list, tuple)):
        return []
    out: list[str] = []
    for raw in value[:limit]:
        item = _text(raw, 320)
        if item and item not in out:
            out.append(item)
    return out


def _normalized_unique(value: Any, allowed: Sequence[str], limit: int) -> list[str]:
    if not isinstance(value, (list, tuple)):
        return []
    out: list[str] = []
    allowed_set = set(allowed)
    for raw in value[:limit]:
        item = _text(raw, 100).upper()
        if item in allowed_set and item not in out:
            out.append(item)
    return out


def recommend_package(
    *,
    need_tracks: Sequence[str],
    integration_count: int,
    channel_count: int,
    requested_capacity_units: int,
) -> str:
    needs = len(set(need_tracks))
    if needs <= 1 and integration_count <= 2 and channel_count <= 2 and requested_capacity_units <= 25:
        return "ESSENCIAL"
    if needs <= 2 and integration_count <= 5 and channel_count <= 4 and requested_capacity_units <= 60:
        return "PROFISSIONAL"
    return "COMPLETO"


def evaluate_conversion_capacity(
    *,
    trusted_scope: Mapping[str, Any],
    pilot_outcome: Mapping[str, Any],
    commercial: Mapping[str, Any],
    capacity: Mapping[str, Any],
    policy: Mapping[str, Any],
) -> dict[str, Any]:
    trusted = _scope(trusted_scope)
    blockers: list[str] = []
    review_reasons: list[str] = []

    if not all(trusted.values()):
        blockers.append("TRUSTED_SCOPE_INVALID")

    outcome = dict(pilot_outcome) if isinstance(pilot_outcome, Mapping) else {}
    if outcome.get("state") != "HEALTHY":
        blockers.append("PILOT_OUTCOME_NOT_HEALTHY")
    if outcome.get("decision") != "CONTINUE_REVIEW_CANDIDATE":
        blockers.append("PILOT_NOT_CONTINUE_REVIEW_CANDIDATE")
    if outcome.get("blockers"):
        blockers.append("PILOT_OUTCOME_HAS_BLOCKERS")
    if outcome.get("hard_stop_reasons"):
        blockers.append("PILOT_OUTCOME_HAS_HARD_STOP")
    if outcome.get("owner_review_required") is not True:
        blockers.append("OUTCOME_OWNER_REVIEW_BOUNDARY_MISSING")
    if not _text(outcome.get("evidence_digest"), 180):
        blockers.append("PILOT_OUTCOME_EVIDENCE_DIGEST_REQUIRED")

    commercial_data = dict(commercial) if isinstance(commercial, Mapping) else {}
    if _scope(commercial_data) != trusted:
        blockers.append("COMMERCIAL_SCOPE_MISMATCH")

    customer_id = _text(commercial_data.get("customer_id"), 120)
    if not customer_id:
        blockers.append("CUSTOMER_ID_REQUIRED")

    need_tracks = _normalized_unique(commercial_data.get("need_tracks"), NEED_TRACKS, 3)
    if not need_tracks:
        blockers.append("NEED_TRACK_REQUIRED")

    integration_count = _positive_int(commercial_data.get("integration_count"))
    channel_count = _positive_int(commercial_data.get("channel_count"))
    requested_capacity_units = _positive_int(commercial_data.get("requested_capacity_units"))
    if integration_count is None:
        blockers.append("INTEGRATION_COUNT_INVALID")
    if channel_count is None:
        blockers.append("CHANNEL_COUNT_INVALID")
    if requested_capacity_units is None or requested_capacity_units < 1:
        blockers.append("REQUESTED_CAPACITY_INVALID")

    monthly_price = _number(commercial_data.get("monthly_price_brl"))
    monthly_service_cost = _number(commercial_data.get("expected_monthly_service_cost_brl"))
    implementation_price = _number(commercial_data.get("implementation_price_brl"))
    implementation_cost = _number(commercial_data.get("expected_implementation_cost_brl"))
    for name, value in (
        ("MONTHLY_PRICE", monthly_price),
        ("MONTHLY_SERVICE_COST", monthly_service_cost),
        ("IMPLEMENTATION_PRICE", implementation_price),
        ("IMPLEMENTATION_COST", implementation_cost),
    ):
        if value is None or value < 0:
            blockers.append(f"{name}_INVALID")

    evidence_refs = _refs(commercial_data.get("evidence_refs"))
    if len(evidence_refs) < 4:
        blockers.append("COMMERCIAL_EVIDENCE_INSUFFICIENT")

    policy_data = dict(policy) if isinstance(policy, Mapping) else {}
    if policy_data.get("state") != "VERIFIED":
        blockers.append("COMMERCIAL_POLICY_NOT_VERIFIED")
    if _scope(policy_data) != trusted:
        blockers.append("COMMERCIAL_POLICY_SCOPE_MISMATCH")
    min_margin_pct = _number(policy_data.get("min_monthly_gross_margin_pct"))
    max_portfolio_utilization_pct = _number(policy_data.get("max_portfolio_utilization_pct"))
    max_single_customer_share_pct = _number(policy_data.get("max_single_customer_capacity_share_pct"))
    if min_margin_pct is None or min_margin_pct < 0 or min_margin_pct > 100:
        blockers.append("MIN_MARGIN_POLICY_INVALID")
    if max_portfolio_utilization_pct is None or max_portfolio_utilization_pct <= 0 or max_portfolio_utilization_pct > 100:
        blockers.append("MAX_PORTFOLIO_UTILIZATION_POLICY_INVALID")
    if max_single_customer_share_pct is None or max_single_customer_share_pct <= 0 or max_single_customer_share_pct > 100:
        blockers.append("MAX_SINGLE_CUSTOMER_SHARE_POLICY_INVALID")

    cap = dict(capacity) if isinstance(capacity, Mapping) else {}
    if _scope(cap) != trusted:
        blockers.append("CAPACITY_SCOPE_MISMATCH")
    current_customers = _positive_int(cap.get("active_customer_count"))
    max_customers = _positive_int(cap.get("max_active_customers"))
    current_units = _positive_int(cap.get("current_capacity_units"))
    max_units = _positive_int(cap.get("max_capacity_units"))
    for key, value in (
        ("ACTIVE_CUSTOMER_COUNT", current_customers),
        ("MAX_ACTIVE_CUSTOMERS", max_customers),
        ("CURRENT_CAPACITY_UNITS", current_units),
        ("MAX_CAPACITY_UNITS", max_units),
    ):
        if value is None:
            blockers.append(f"{key}_INVALID")
    if max_customers == 0:
        blockers.append("MAX_ACTIVE_CUSTOMERS_MUST_BE_POSITIVE")
    if max_units == 0:
        blockers.append("MAX_CAPACITY_UNITS_MUST_BE_POSITIVE")

    monthly_contribution: float | None = None
    monthly_margin_pct: float | None = None
    implementation_contribution: float | None = None
    if monthly_price is not None and monthly_service_cost is not None:
        monthly_contribution = round(monthly_price - monthly_service_cost, 2)
        if monthly_price > 0:
            monthly_margin_pct = round((monthly_contribution / monthly_price) * 100.0, 2)
    if implementation_price is not None and implementation_cost is not None:
        implementation_contribution = round(implementation_price - implementation_cost, 2)

    projected_customers: int | None = None
    projected_units: int | None = None
    portfolio_utilization_pct: float | None = None
    single_customer_share_pct: float | None = None
    if current_customers is not None:
        projected_customers = current_customers + 1
    if current_units is not None and requested_capacity_units is not None:
        projected_units = current_units + requested_capacity_units
    if projected_units is not None and max_units:
        portfolio_utilization_pct = round(projected_units / max_units * 100.0, 2)
    if requested_capacity_units is not None and max_units:
        single_customer_share_pct = round(requested_capacity_units / max_units * 100.0, 2)

    if projected_customers is not None and max_customers is not None and projected_customers > max_customers:
        review_reasons.append("CUSTOMER_COUNT_CAPACITY_EXCEEDED")
    if projected_units is not None and max_units is not None and projected_units > max_units:
        review_reasons.append("CAPACITY_UNITS_EXCEEDED")
    if (
        portfolio_utilization_pct is not None
        and max_portfolio_utilization_pct is not None
        and portfolio_utilization_pct > max_portfolio_utilization_pct
    ):
        review_reasons.append("PORTFOLIO_UTILIZATION_POLICY_EXCEEDED")
    if (
        single_customer_share_pct is not None
        and max_single_customer_share_pct is not None
        and single_customer_share_pct > max_single_customer_share_pct
    ):
        review_reasons.append("SINGLE_CUSTOMER_CAPACITY_SHARE_EXCEEDED")
    if (
        monthly_margin_pct is not None
        and min_margin_pct is not None
        and monthly_margin_pct < min_margin_pct
    ):
        review_reasons.append("MONTHLY_MARGIN_BELOW_POLICY")
    if implementation_contribution is not None and implementation_contribution < 0:
        review_reasons.append("IMPLEMENTATION_CONTRIBUTION_NEGATIVE")

    recommended_package = None
    if integration_count is not None and channel_count is not None and requested_capacity_units:
        recommended_package = recommend_package(
            need_tracks=need_tracks,
            integration_count=integration_count,
            channel_count=channel_count,
            requested_capacity_units=requested_capacity_units,
        )

    if blockers:
        state = "BLOCKED"
        decision = "BLOCKED"
    elif any(
        reason in review_reasons
        for reason in (
            "CUSTOMER_COUNT_CAPACITY_EXCEEDED",
            "CAPACITY_UNITS_EXCEEDED",
            "PORTFOLIO_UTILIZATION_POLICY_EXCEEDED",
            "SINGLE_CUSTOMER_CAPACITY_SHARE_EXCEEDED",
        )
    ):
        state = "CAPACITY_HOLD"
        decision = "CAPACITY_REVIEW"
    elif review_reasons:
        state = "COMMERCIAL_HOLD"
        decision = "REPRICE_OR_RESCOPE_REVIEW"
    else:
        state = "REVIEWABLE"
        decision = "COMMERCIAL_REVIEW_CANDIDATE"

    evidence = {
        "customer_id": customer_id,
        "scope": trusted,
        "pilot_outcome_digest": _text(outcome.get("evidence_digest"), 180),
        "recommended_package": recommended_package,
        "need_tracks": need_tracks,
        "monthly_price_brl": monthly_price,
        "expected_monthly_service_cost_brl": monthly_service_cost,
        "monthly_margin_pct": monthly_margin_pct,
        "implementation_contribution_brl": implementation_contribution,
        "projected_customer_count": projected_customers,
        "projected_capacity_units": projected_units,
        "portfolio_utilization_pct": portfolio_utilization_pct,
        "single_customer_capacity_share_pct": single_customer_share_pct,
        "commercial_evidence_refs": evidence_refs,
    }

    return {
        "schema": SCHEMA,
        "state": state,
        "decision": decision,
        "customer_id": customer_id,
        "recommended_package": recommended_package,
        "need_tracks": need_tracks,
        "monthly_contribution_brl": monthly_contribution,
        "monthly_gross_margin_pct": monthly_margin_pct,
        "implementation_contribution_brl": implementation_contribution,
        "projected_active_customer_count": projected_customers,
        "projected_capacity_units": projected_units,
        "portfolio_utilization_pct": portfolio_utilization_pct,
        "single_customer_capacity_share_pct": single_customer_share_pct,
        "review_reasons": list(dict.fromkeys(review_reasons)),
        "blockers": list(dict.fromkeys(blockers)),
        "evidence_digest": _digest(evidence),
        "owner_commercial_approval_required": True,
        "automatic_conversion": False,
        "automatic_package_change": False,
        "automatic_pricing_change": False,
        "automatic_contract": False,
        "automatic_billing": False,
        "automatic_provisioning": False,
        "automatic_customer_contact": False,
        "automatic_deploy": False,
        "production_mutation": False,
        "executes_action": False,
    }


__all__ = [
    "SCHEMA",
    "PACKAGES",
    "NEED_TRACKS",
    "recommend_package",
    "evaluate_conversion_capacity",
]
