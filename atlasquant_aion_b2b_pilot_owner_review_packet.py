"""AION B2B Pilot Owner Review Packet V1.

Pure/offline evidence packet for a HUMAN_OWNER to review a planned B2B pilot.

This module deliberately does not implement owner approval. The existing AION
owner-decision mechanism is scoped to Core Freeze and is not reused here.

The packet verifies that Proposal Draft, Pilot Readiness and Pilot Planning
Handoff all refer to the same candidate/scope/evidence chain, then exposes a
decision-support summary with owner_decision=UNDECIDED.

No signature, approval record, pilot activation, customer contact, billing,
CRM write, provider call, deploy or production mutation occurs here.
"""
from __future__ import annotations

from hashlib import sha256
from typing import Any, Mapping
import json

SCHEMA = "ATLASQUANT_AION_B2B_PILOT_OWNER_REVIEW_PACKET_V1"
PROPOSAL_SCHEMA = "ATLASQUANT_AION_B2B_PROPOSAL_DRAFT_V1"
READINESS_SCHEMA = "ATLASQUANT_AION_B2B_PILOT_READINESS_V1"
HANDOFF_SCHEMA = "ATLASQUANT_AION_B2B_PILOT_PLANNING_HANDOFF_V1"


def _text(value: Any, limit: int = 500) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(value.replace("\x00", "").split())[:limit]


def _scope(raw: Mapping[str, Any] | None) -> dict[str, str]:
    data = dict(raw) if isinstance(raw, Mapping) else {}
    return {
        "owner_id": _text(data.get("owner_id"), 120),
        "tenant_id": _text(data.get("tenant_id"), 120),
        "workspace_id": _text(data.get("workspace_id"), 120),
    }


def _number(value: Any) -> int | float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return value


def _canonical(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )


def _digest(value: Any) -> str:
    return "sha256:" + sha256(_canonical(value).encode("utf-8")).hexdigest()


def build_pilot_owner_review_packet(
    *,
    trusted_scope: Mapping[str, Any] | None,
    proposal_draft: Mapping[str, Any] | None,
    readiness: Mapping[str, Any] | None,
    pilot_handoff: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Build an evidence-bound owner review packet without recording a decision."""
    scope = _scope(trusted_scope)
    proposal_result = dict(proposal_draft) if isinstance(proposal_draft, Mapping) else {}
    readiness_result = dict(readiness) if isinstance(readiness, Mapping) else {}
    handoff = dict(pilot_handoff) if isinstance(pilot_handoff, Mapping) else {}
    blockers: list[str] = []

    if not all(scope.values()):
        blockers.append("TRUSTED_SCOPE_INVALID")

    if proposal_result.get("schema") != PROPOSAL_SCHEMA:
        blockers.append("PROPOSAL_SCHEMA_INVALID")
    if proposal_result.get("state") != "DRAFT_FOR_HUMAN_REVIEW":
        blockers.append("PROPOSAL_STATE_INVALID")
    if proposal_result.get("non_binding") is not True:
        blockers.append("PROPOSAL_NON_BINDING_BOUNDARY_INVALID")
    if proposal_result.get("owner_review_required") is not True:
        blockers.append("PROPOSAL_OWNER_REVIEW_BOUNDARY_MISSING")
    for key in (
        "customer_send_allowed",
        "contract_ready",
        "price_commitment",
        "automatic_customer_contact",
        "automatic_contract",
        "automatic_billing",
        "automatic_provisioning",
        "crm_write",
        "provider_called",
        "production_mutation",
        "executes_action",
    ):
        if proposal_result.get(key) is not False:
            blockers.append(f"PROPOSAL_{key.upper()}_UNSAFE")

    proposal = (
        dict(proposal_result.get("proposal"))
        if isinstance(proposal_result.get("proposal"), Mapping)
        else {}
    )
    if _scope(proposal) != scope:
        blockers.append("PROPOSAL_SCOPE_MISMATCH")

    proposal_id = _text(proposal.get("proposal_id"), 120)
    candidate_id = _text(proposal.get("candidate_id"), 120)
    company_label = _text(proposal.get("company_label"), 180)
    proposal_digest = _text(proposal_result.get("proposal_digest"), 180)
    proposal_readiness_digest = _text(
        proposal.get("readiness_evidence_digest"),
        180,
    )
    if not proposal_id:
        blockers.append("PROPOSAL_ID_REQUIRED")
    if not candidate_id:
        blockers.append("CANDIDATE_ID_REQUIRED")
    if not company_label:
        blockers.append("COMPANY_LABEL_REQUIRED")
    if not proposal_digest:
        blockers.append("PROPOSAL_DIGEST_REQUIRED")

    if readiness_result.get("schema") != READINESS_SCHEMA:
        blockers.append("READINESS_SCHEMA_INVALID")
    if readiness_result.get("state") != "READY_FOR_OWNER_REVIEW":
        blockers.append("READINESS_STATE_INVALID")
    if readiness_result.get("decision") != "PILOT_REVIEW_CANDIDATE":
        blockers.append("READINESS_NOT_PILOT_REVIEW_CANDIDATE")
    if readiness_result.get("human_owner_decision_required") is not True:
        blockers.append("READINESS_OWNER_DECISION_BOUNDARY_MISSING")
    if readiness_result.get("automatic_acceptance") is not False:
        blockers.append("READINESS_AUTOMATIC_ACCEPTANCE_UNSAFE")
    if readiness_result.get("automatic_contract") is not False:
        blockers.append("READINESS_AUTOMATIC_CONTRACT_UNSAFE")
    if readiness_result.get("automatic_billing") is not False:
        blockers.append("READINESS_AUTOMATIC_BILLING_UNSAFE")
    if readiness_result.get("production_mutation") is not False:
        blockers.append("READINESS_PRODUCTION_BOUNDARY_UNSAFE")
    if readiness_result.get("executes_action") is not False:
        blockers.append("READINESS_EXECUTION_BOUNDARY_UNSAFE")
    if readiness_result.get("blockers"):
        blockers.append("READINESS_HAS_BLOCKERS")
    if _scope(readiness_result.get("scope") if isinstance(readiness_result.get("scope"), Mapping) else {}) != scope:
        blockers.append("READINESS_SCOPE_MISMATCH")
    if _text(readiness_result.get("candidate_id"), 120) != candidate_id:
        blockers.append("READINESS_CANDIDATE_MISMATCH")

    readiness_digest = _text(readiness_result.get("evidence_digest"), 180)
    if not readiness_digest:
        blockers.append("READINESS_EVIDENCE_DIGEST_REQUIRED")
    if proposal_readiness_digest != readiness_digest:
        blockers.append("PROPOSAL_READINESS_EVIDENCE_MISMATCH")

    if handoff.get("schema") != HANDOFF_SCHEMA:
        blockers.append("PILOT_HANDOFF_SCHEMA_INVALID")
    if handoff.get("state") != "PLANNED_FOR_OWNER_REVIEW":
        blockers.append("PILOT_HANDOFF_STATE_INVALID")
    if handoff.get("activation_state") != "BLOCKED_UNTIL_OWNER_APPROVAL":
        blockers.append("PILOT_HANDOFF_ACTIVATION_BOUNDARY_INVALID")
    if handoff.get("human_owner_approval_required") is not True:
        blockers.append("PILOT_HANDOFF_OWNER_BOUNDARY_MISSING")
    if _scope(handoff.get("scope") if isinstance(handoff.get("scope"), Mapping) else {}) != scope:
        blockers.append("PILOT_HANDOFF_SCOPE_MISMATCH")
    if _text(handoff.get("proposal_id"), 120) != proposal_id:
        blockers.append("PILOT_HANDOFF_PROPOSAL_MISMATCH")
    if _text(handoff.get("candidate_id"), 120) != candidate_id:
        blockers.append("PILOT_HANDOFF_CANDIDATE_MISMATCH")

    for key in (
        "automatic_activation",
        "automatic_contract_signature",
        "automatic_customer_contact",
        "automatic_billing",
        "automatic_spend",
        "automatic_deploy",
        "crm_write",
        "provider_called",
        "production_mutation",
        "executes_action",
    ):
        if handoff.get(key) is not False:
            blockers.append(f"PILOT_HANDOFF_{key.upper()}_UNSAFE")

    handoff_digest = _text(handoff.get("handoff_digest"), 180)
    if not handoff_digest:
        blockers.append("PILOT_HANDOFF_DIGEST_REQUIRED")

    contract = (
        dict(handoff.get("operating_contract"))
        if isinstance(handoff.get("operating_contract"), Mapping)
        else {}
    )
    if contract.get("state") != "DRAFT_FOR_OWNER_APPROVAL":
        blockers.append("OPERATING_CONTRACT_STATE_INVALID")
    if contract.get("activation_state") != "BLOCKED_UNTIL_OWNER_APPROVAL":
        blockers.append("OPERATING_CONTRACT_ACTIVATION_BOUNDARY_INVALID")
    if contract.get("human_owner_approval_required") is not True:
        blockers.append("OPERATING_CONTRACT_OWNER_BOUNDARY_MISSING")
    if contract.get("automatic_activation") is not False:
        blockers.append("OPERATING_CONTRACT_AUTOMATIC_ACTIVATION_UNSAFE")
    if contract.get("executes_action") is not False:
        blockers.append("OPERATING_CONTRACT_EXECUTION_BOUNDARY_UNSAFE")

    contract_core = (
        dict(contract.get("contract"))
        if isinstance(contract.get("contract"), Mapping)
        else {}
    )
    if _scope(contract_core) != scope:
        blockers.append("OPERATING_CONTRACT_SCOPE_MISMATCH")
    if _text(contract_core.get("candidate_id"), 120) != candidate_id:
        blockers.append("OPERATING_CONTRACT_CANDIDATE_MISMATCH")
    if _text(contract_core.get("readiness_evidence_digest"), 180) != readiness_digest:
        blockers.append("OPERATING_CONTRACT_READINESS_EVIDENCE_MISMATCH")
    if proposal_digest not in list(contract_core.get("evidence_refs") or []):
        blockers.append("OPERATING_CONTRACT_PROPOSAL_EVIDENCE_MISSING")

    pilot_id = _text(handoff.get("pilot_id"), 120)
    if not pilot_id or pilot_id != _text(contract_core.get("pilot_id"), 120):
        blockers.append("PILOT_ID_MISMATCH")

    pricing = (
        dict(proposal.get("pricing"))
        if isinstance(proposal.get("pricing"), Mapping)
        else {}
    )
    if pricing.get("binding") is not False:
        blockers.append("PROPOSAL_PRICING_BINDING_UNSAFE")

    kpis = [
        dict(item)
        for item in list(contract_core.get("kpis") or [])[:20]
        if isinstance(item, Mapping)
    ]
    stop_conditions = [
        _text(item, 420)
        for item in list(contract_core.get("stop_conditions") or [])[:20]
        if _text(item, 420)
    ]
    rollback_steps = [
        _text(item, 420)
        for item in list(contract_core.get("rollback_steps") or [])[:20]
        if _text(item, 420)
    ]
    pilot_scope_items = [
        _text(item, 420)
        for item in list(handoff.get("pilot_scope_items") or [])[:20]
        if _text(item, 420)
    ]

    kpi_summary = []
    for item in kpis:
        kpi_summary.append(
            {
                "metric_id": _text(item.get("metric_id"), 100),
                "label": _text(item.get("label"), 180),
                "unit": _text(item.get("unit"), 80),
                "direction": _text(item.get("direction"), 20).upper(),
                "baseline": _number(item.get("baseline")),
                "target": _number(item.get("target")),
            }
        )

    summary = {
        "proposal": {
            "proposal_id": proposal_id,
            "company_label": company_label,
            "package": _text(proposal.get("package"), 60),
            "pricing_mode": _text(pricing.get("mode"), 40).upper(),
            "indicative_setup_fee_brl": _number(
                pricing.get("indicative_setup_fee_brl")
            ),
            "indicative_monthly_fee_brl": _number(
                pricing.get("indicative_monthly_fee_brl")
            ),
            "pricing_binding": False,
            "non_binding": True,
        },
        "readiness": {
            "decision": _text(readiness_result.get("decision"), 80),
            "acceptance_score": _number(readiness_result.get("acceptance_score")),
            "risk_score": _number(readiness_result.get("risk_score")),
            "priority_score": _number(readiness_result.get("priority_score")),
            "planned_monthly_infra_brl": _number(
                readiness_result.get("planned_monthly_infra_brl")
            ),
        },
        "pilot": {
            "pilot_id": pilot_id,
            "duration_days": _number(contract_core.get("duration_days")),
            "max_monthly_infra_brl": _number(
                contract_core.get("max_monthly_infra_brl")
            ),
            "scope_items": pilot_scope_items,
            "kpis": kpi_summary,
            "stop_conditions": stop_conditions,
            "rollback_steps": rollback_steps,
            "activation_state": "BLOCKED_UNTIL_OWNER_APPROVAL",
        },
        "evidence": {
            "proposal_digest": proposal_digest,
            "readiness_evidence_digest": readiness_digest,
            "pilot_handoff_digest": handoff_digest,
            "operating_contract_digest": _text(
                contract.get("contract_digest"),
                180,
            ),
        },
    }

    blockers = list(dict.fromkeys(blockers))
    checklist = {
        "scope_bound": not any(
            "SCOPE_MISMATCH" in item for item in blockers
        ),
        "candidate_bound": not any(
            "CANDIDATE_MISMATCH" in item for item in blockers
        ),
        "proposal_non_binding": (
            proposal_result.get("non_binding") is True
            and pricing.get("binding") is False
        ),
        "readiness_positive": (
            readiness_result.get("decision") == "PILOT_REVIEW_CANDIDATE"
            and readiness_result.get("state") == "READY_FOR_OWNER_REVIEW"
        ),
        "activation_blocked": (
            handoff.get("activation_state") == "BLOCKED_UNTIL_OWNER_APPROVAL"
            and contract.get("activation_state") == "BLOCKED_UNTIL_OWNER_APPROVAL"
        ),
        "stop_conditions_present": len(stop_conditions) >= 3,
        "rollback_present": len(rollback_steps) >= 2,
        "kpis_present": len(kpi_summary) >= 3,
    }

    packet_material = {
        "scope": scope,
        "candidate_id": candidate_id,
        "summary": summary,
        "checklist": checklist,
    }

    return {
        "schema": SCHEMA,
        "state": "READY_FOR_OWNER_REVIEW" if not blockers else "BLOCKED",
        "scope": scope,
        "candidate_id": candidate_id,
        "summary": summary,
        "checklist": checklist,
        "blockers": blockers,
        "packet_digest": _digest(packet_material),
        "owner_decision": "UNDECIDED",
        "owner_decision_recorded": False,
        "owner_approval_recorded": False,
        "owner_signature_requested": False,
        "owner_signature_verified": False,
        "decision_mechanism_reused_from_core_freeze": False,
        "human_owner_decision_required": True,
        "pilot_activation_authorized": False,
        "automatic_activation": False,
        "automatic_customer_contact": False,
        "automatic_contract_signature": False,
        "automatic_billing": False,
        "automatic_spend": False,
        "automatic_deploy": False,
        "crm_write": False,
        "provider_called": False,
        "production_mutation": False,
        "grants_authority": False,
        "executes_action": False,
    }


__all__ = [
    "SCHEMA",
    "PROPOSAL_SCHEMA",
    "READINESS_SCHEMA",
    "HANDOFF_SCHEMA",
    "build_pilot_owner_review_packet",
]
