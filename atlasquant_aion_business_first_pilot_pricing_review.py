"""AION BUSINESS first-pilot selection and pricing review V1.

Administrative/read-only bridge between:
- the productized B2B recurring offer;
- explicit candidate-fit inputs;
- pricing/margin economics;
- bounded Pilot Governance.

It never contacts a prospect, changes price, signs, charges, admits a tenant,
activates runtime, deploys, publishes or executes external actions.
"""
from __future__ import annotations

from hashlib import sha256
from typing import Any, Mapping
import json
import math

from atlasquant_aion_business_b2b_revenue_offer import (
    SCHEMA as OFFER_SCHEMA,
    PRIORITY_OFFER_ID,
)
from atlasquant_aion_business_pilot_governance import (
    SCHEMA as PILOT_SCHEMA,
    MAX_CLIENTS,
    MAX_PILOT_DAYS,
)

SCHEMA = "ATLASQUANT_AION_BUSINESS_FIRST_PILOT_PRICING_REVIEW_V1"
VERSION = "1"

CONTACT_PERMISSION_STATES = (
    "UNKNOWN",
    "PERMITTED",
    "OPT_IN",
    "DO_NOT_CONTACT",
)


def _clean(value: Any, limit: int = 500) -> str:
    return " ".join(str(value or "").replace("\x00", "").split())[:limit]


def _num(value: Any, *, minimum: float = 0.0, maximum: float | None = None) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    if not math.isfinite(number) or number < minimum:
        return None
    if maximum is not None and number > maximum:
        return None
    return number


def _digest(value: Any) -> str:
    raw = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return sha256(raw.encode("utf-8")).hexdigest()


def first_pilot_policy() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": "FIRST_PILOT_EVIDENCE_REQUIRED",
        "max_clients": MAX_CLIENTS,
        "max_duration_days": MAX_PILOT_DAYS,
        "priority_offer_id": PRIORITY_OFFER_ID,
        "candidate_auto_selected": False,
        "price_auto_selected": False,
        "discount_auto_applied": False,
        "contact_authorized": False,
        "billing_authorized": False,
        "runtime_authorized": False,
        "executes_action": False,
    }


def candidate_fit_review(
    *,
    candidate_reference: Any,
    segment: Any,
    pain_fit_pct: Any,
    recurring_fit_pct: Any,
    decision_access_pct: Any,
    data_readiness_pct: Any,
    process_volume_fit_pct: Any,
    implementation_readiness_pct: Any,
    minimum_admin_fit_pct: Any,
    contact_permission_state: Any,
) -> dict[str, Any]:
    candidate = _clean(candidate_reference, 120)
    segment_text = _clean(segment, 120)
    permission = _clean(contact_permission_state, 40).upper()
    if permission not in CONTACT_PERMISSION_STATES:
        permission = "UNKNOWN"

    values = {
        "pain_fit_pct": _num(pain_fit_pct, maximum=100),
        "recurring_fit_pct": _num(recurring_fit_pct, maximum=100),
        "decision_access_pct": _num(decision_access_pct, maximum=100),
        "data_readiness_pct": _num(data_readiness_pct, maximum=100),
        "process_volume_fit_pct": _num(process_volume_fit_pct, maximum=100),
        "implementation_readiness_pct": _num(implementation_readiness_pct, maximum=100),
    }
    floor = _num(minimum_admin_fit_pct, maximum=100)

    blockers: list[str] = []
    if not candidate:
        blockers.append("CANDIDATE_REFERENCE_REQUIRED")
    if not segment_text:
        blockers.append("SEGMENT_REQUIRED")
    if any(value is None for value in values.values()):
        blockers.append("FIT_INPUTS_INCOMPLETE")
    if floor is None:
        blockers.append("ADMIN_FIT_FLOOR_INVALID")
    if permission == "DO_NOT_CONTACT":
        blockers.append("DO_NOT_CONTACT")

    if blockers:
        score = None
        ready = False
    else:
        # Explicit, deterministic weighted fit for internal review only.
        score = round(
            0.25 * values["pain_fit_pct"]
            + 0.20 * values["recurring_fit_pct"]
            + 0.15 * values["decision_access_pct"]
            + 0.15 * values["data_readiness_pct"]
            + 0.15 * values["process_volume_fit_pct"]
            + 0.10 * values["implementation_readiness_pct"],
            2,
        )
        ready = score >= floor
        if not ready:
            blockers.append("FIT_BELOW_ADMIN_FLOOR")

    payload = {
        "candidate_reference": candidate,
        "segment": segment_text,
        "fit_inputs": values,
        "minimum_admin_fit_pct": floor,
        "weighted_fit_pct": score,
        "contact_permission_state": permission,
    } if not blockers else {}

    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": "CANDIDATE_FIT_REVIEW_READY" if ready else "CANDIDATE_FIT_REVIEW_BLOCKED",
        "candidate_reference": candidate,
        "segment": segment_text,
        "fit_inputs": values,
        "minimum_admin_fit_pct": floor,
        "weighted_fit_pct": score,
        "contact_permission_state": permission,
        "contact_review_allowed": permission in {"PERMITTED", "OPT_IN"},
        "blockers": blockers,
        "candidate_fit_digest": _digest(payload) if payload else "",
        "candidate_selected": False,
        "contact_authorized": False,
        "executes_action": False,
    }


def pricing_pilot_review(
    offer_economics: Mapping[str, Any] | None,
    *,
    proposed_pilot_monthly_price_brl: Any,
    proposed_pilot_implementation_fee_brl: Any,
) -> dict[str, Any]:
    eco = dict(offer_economics or {}) if isinstance(offer_economics, Mapping) else {}
    monthly = _num(proposed_pilot_monthly_price_brl)
    implementation = _num(proposed_pilot_implementation_fee_brl)

    base_price = _num(eco.get("monthly_price_brl"))
    min_price = _num(eco.get("minimum_sustainable_monthly_price_brl"))
    min_margin = _num(eco.get("minimum_margin_pct"), maximum=100)
    monthly_cost = _num(eco.get("estimated_monthly_cost_brl"))
    implementation_cost = _num(eco.get("estimated_implementation_cost_brl"))

    blockers: list[str] = []
    if eco.get("schema") != OFFER_SCHEMA or eco.get("state") != "OFFER_ECONOMICS_READY":
        blockers.append("BASE_OFFER_ECONOMICS_NOT_READY")
    if monthly is None or monthly <= 0:
        blockers.append("PILOT_MONTHLY_PRICE_INVALID")
    if implementation is None or implementation < 0:
        blockers.append("PILOT_IMPLEMENTATION_FEE_INVALID")
    if any(value is None for value in (base_price, min_price, min_margin, monthly_cost, implementation_cost)):
        blockers.append("BASE_ECONOMICS_FIELDS_MISSING")

    margin_pct = None
    monthly_contribution = None
    implementation_contribution = None
    if not blockers:
        monthly_contribution = round(monthly - monthly_cost, 2)
        margin_pct = round((monthly_contribution / monthly) * 100, 4)
        implementation_contribution = round(implementation - implementation_cost, 2)
        if monthly < min_price:
            blockers.append("PILOT_PRICE_BELOW_SUSTAINABLE_FLOOR")
        if margin_pct < min_margin:
            blockers.append("PILOT_MARGIN_BELOW_ADMIN_FLOOR")
        if implementation_contribution < 0:
            blockers.append("PILOT_IMPLEMENTATION_FEE_BELOW_COST")

    ready = not blockers
    payload = {
        "proposed_pilot_monthly_price_brl": monthly,
        "proposed_pilot_implementation_fee_brl": implementation,
        "margin_pct": margin_pct,
        "base_economics_digest": _clean(eco.get("economics_digest"), 128),
    } if ready else {}

    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": "PILOT_PRICING_REVIEW_READY" if ready else "PILOT_PRICING_REVIEW_BLOCKED",
        "proposed_pilot_monthly_price_brl": monthly,
        "proposed_pilot_implementation_fee_brl": implementation,
        "monthly_contribution_brl": monthly_contribution,
        "margin_pct": margin_pct,
        "implementation_contribution_brl": implementation_contribution,
        "minimum_sustainable_monthly_price_brl": min_price,
        "minimum_margin_pct": min_margin,
        "blockers": blockers,
        "pricing_review_digest": _digest(payload) if payload else "",
        "price_selected": False,
        "discount_applied_automatically": False,
        "billing_authorized": False,
        "executes_action": False,
    }


def first_pilot_review_packet(
    *,
    candidate_review: Mapping[str, Any] | None,
    pricing_review: Mapping[str, Any] | None,
    offer_readiness: Mapping[str, Any] | None,
    pilot_gate_review: Mapping[str, Any] | None,
    pilot_review_packet: Mapping[str, Any] | None,
    requested_by: Any,
) -> dict[str, Any]:
    candidate = dict(candidate_review or {}) if isinstance(candidate_review, Mapping) else {}
    pricing = dict(pricing_review or {}) if isinstance(pricing_review, Mapping) else {}
    offer = dict(offer_readiness or {}) if isinstance(offer_readiness, Mapping) else {}
    pilot_gates = dict(pilot_gate_review or {}) if isinstance(pilot_gate_review, Mapping) else {}
    pilot_packet = dict(pilot_review_packet or {}) if isinstance(pilot_review_packet, Mapping) else {}
    requester = _clean(requested_by, 120)

    gates = {
        "candidate_fit_ready": candidate.get("state") == "CANDIDATE_FIT_REVIEW_READY",
        "pricing_ready": pricing.get("state") == "PILOT_PRICING_REVIEW_READY",
        "offer_ready": (
            offer.get("schema") == OFFER_SCHEMA
            and offer.get("state") == "READY_FOR_ADMIN_SALES_REVIEW"
        ),
        "pilot_governance_ready": (
            pilot_gates.get("schema") == PILOT_SCHEMA
            and pilot_gates.get("state") == "PILOT_REVIEW_REQUIRED"
            and pilot_gates.get("all_mandatory_gates_pass") is True
        ),
        "human_pilot_packet_ready": (
            pilot_packet.get("state") == "HUMAN_PILOT_APPROVAL_REQUIRED"
            and pilot_packet.get("human_approval_recorded") is False
            and pilot_packet.get("pilot_authorized") is False
        ),
        "requested_by_present": bool(requester),
        "contact_permission_not_denied": candidate.get("contact_permission_state") != "DO_NOT_CONTACT",
    }

    blockers = [name for name, passed in gates.items() if not passed]
    ready = not blockers

    payload = {
        "candidate_fit_digest": _clean(candidate.get("candidate_fit_digest"), 128),
        "pricing_review_digest": _clean(pricing.get("pricing_review_digest"), 128),
        "offer_readiness_digest": _clean(offer.get("readiness_digest"), 128),
        "pilot_charter_digest": _clean(pilot_packet.get("charter_digest"), 128),
        "requested_by": requester,
    } if ready else {}

    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": (
            "READY_FOR_ADMIN_FIRST_PILOT_REVIEW"
            if ready
            else "FIRST_PILOT_REVIEW_BLOCKED"
        ),
        "gates": gates,
        "blockers": blockers,
        "requested_by": requester if ready else "",
        "candidate_reference": candidate.get("candidate_reference") if ready else "",
        "segment": candidate.get("segment") if ready else "",
        "proposed_pilot_monthly_price_brl": (
            pricing.get("proposed_pilot_monthly_price_brl") if ready else None
        ),
        "proposed_pilot_implementation_fee_brl": (
            pricing.get("proposed_pilot_implementation_fee_brl") if ready else None
        ),
        "first_pilot_review_digest": _digest(payload) if payload else "",
        "candidate_selected": False,
        "price_approved": False,
        "contact_authorized": False,
        "proposal_send_authorized": False,
        "contract_authorized": False,
        "billing_authorized": False,
        "pilot_authorized": False,
        "runtime_authorized": False,
        "executes_action": False,
    }


__all__ = [
    "SCHEMA",
    "VERSION",
    "CONTACT_PERMISSION_STATES",
    "first_pilot_policy",
    "candidate_fit_review",
    "pricing_pilot_review",
    "first_pilot_review_packet",
]
