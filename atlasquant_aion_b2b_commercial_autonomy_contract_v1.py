"""AION B2B Commercial Autonomy Contract V1.

Pure/offline policy contract. It decides whether a proposed commercial action is
eligible inside a HUMAN_OWNER-approved campaign envelope. It never sends a
message, writes CRM, spends money, signs a contract, calls a provider or mutates
production.
"""
from __future__ import annotations

from typing import Any, Mapping

SCHEMA = "ATLASQUANT_AION_B2B_COMMERCIAL_AUTONOMY_V1"

AUTONOMOUS_ACTIONS = frozenset({
    "LEAD_RESEARCH",
    "LEAD_SCORE",
    "OUTREACH_SEND",
    "FOLLOWUP_SEND",
    "QUALIFICATION_DIALOGUE",
    "FAQ_RESPONSE",
    "DIAGNOSTIC_INTAKE",
    "MEETING_SCHEDULE",
    "CRM_FACTUAL_WRITE",
    "PIPELINE_STAGE_UPDATE",
    "PRELIMINARY_PROPOSAL",
    "PILOT_DRAFT",
    "CAMPAIGN_ANALYTICS",
    "CAMPAIGN_PAUSE",
})

OWNER_RESERVED_ACTIONS = frozenset({
    "NEW_NICHE_APPROVAL",
    "CUSTOM_PRICE_COMMITMENT",
    "DISCOUNT_EXCEPTION",
    "CONTRACT_COMMITMENT",
    "LEGAL_LIABILITY_COMMITMENT",
    "BILLING_EXCEPTION",
    "REFUND_EXCEPTION",
    "BUDGET_INCREASE",
    "SECURITY_EXCEPTION",
    "MATERIAL_SCOPE_CHANGE",
    "PRODUCTION_DEPLOY_APPROVAL",
    "CONFIDENTIAL_DATA_RELEASE",
})

REQUIRED_ENVELOPE_FIELDS = (
    "campaign_id",
    "approved_by",
    "niche",
    "allowed_channels",
    "business_hours",
    "contact_rate_cap",
    "followup_cap",
    "approved_claims",
    "approved_offers",
    "opt_out_enforced",
)


def _text(value: Any, limit: int = 240) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(value.replace("\x00", "").split())[:limit]


def _approved_envelope(envelope: Mapping[str, Any] | None) -> tuple[bool, list[str]]:
    data = dict(envelope) if isinstance(envelope, Mapping) else {}
    blockers: list[str] = []
    if data.get("state") != "APPROVED":
        blockers.append("CAMPAIGN_ENVELOPE_NOT_APPROVED")
    for field in REQUIRED_ENVELOPE_FIELDS:
        value = data.get(field)
        if field in {"allowed_channels", "approved_claims", "approved_offers"}:
            if not isinstance(value, (list, tuple)) or not value:
                blockers.append("ENVELOPE_FIELD_MISSING:" + field)
        elif field == "opt_out_enforced":
            if value is not True:
                blockers.append("OPT_OUT_ENFORCEMENT_REQUIRED")
        elif not _text(value, 500) and not isinstance(value, (int, float)):
            blockers.append("ENVELOPE_FIELD_MISSING:" + field)
    return not blockers, list(dict.fromkeys(blockers))


def evaluate_commercial_action(
    *,
    action: Any,
    envelope: Mapping[str, Any] | None,
    contact_state: Any = "ELIGIBLE",
    within_budget: bool = True,
    within_rate_limit: bool = True,
    evidence_sufficient: bool = True,
) -> dict[str, Any]:
    """Return policy eligibility only; never execution authority."""
    normalized = _text(action, 80).upper()
    blockers: list[str] = []

    if normalized in OWNER_RESERVED_ACTIONS:
        blockers.append("HUMAN_OWNER_REQUIRED")
    elif normalized not in AUTONOMOUS_ACTIONS:
        blockers.append("ACTION_NOT_IN_AUTONOMY_CONTRACT")

    envelope_ok, envelope_blockers = _approved_envelope(envelope)
    if not envelope_ok:
        blockers.extend(envelope_blockers)

    contact = _text(contact_state, 40).upper()
    if normalized in {"OUTREACH_SEND", "FOLLOWUP_SEND", "QUALIFICATION_DIALOGUE"}:
        if contact in {"DO_NOT_CONTACT", "OPTED_OUT", "UNKNOWN", "BLOCKED"}:
            blockers.append("CONTACT_NOT_ELIGIBLE")

    if within_rate_limit is not True:
        blockers.append("RATE_LIMIT_EXCEEDED")
    if within_budget is not True:
        blockers.append("BUDGET_BOUNDARY_EXCEEDED")
    if evidence_sufficient is not True and normalized in {
        "FAQ_RESPONSE",
        "PRELIMINARY_PROPOSAL",
        "QUALIFICATION_DIALOGUE",
    }:
        blockers.append("EVIDENCE_INSUFFICIENT")

    blockers = list(dict.fromkeys(blockers))
    eligible = not blockers
    return {
        "schema": SCHEMA,
        "action": normalized,
        "state": "ELIGIBLE" if eligible else "BLOCKED",
        "eligible": eligible,
        "blockers": blockers,
        "requires_human_owner": normalized in OWNER_RESERVED_ACTIONS,
        "campaign_envelope_required": True,
        "grants_authority": False,
        "provider_called": False,
        "message_sent": False,
        "crm_written": False,
        "money_spent": False,
        "contract_signed": False,
        "external_action_executed": False,
    }


__all__ = [
    "SCHEMA",
    "AUTONOMOUS_ACTIONS",
    "OWNER_RESERVED_ACTIONS",
    "REQUIRED_ENVELOPE_FIELDS",
    "evaluate_commercial_action",
]
