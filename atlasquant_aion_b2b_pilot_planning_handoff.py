"""AION B2B Proposal -> Pilot Planning Handoff V1.

Pure/offline bridge from a non-binding Proposal Draft into the existing
B2B Pilot Operating Contract builder.

The bridge never activates a pilot. It validates identity/scope/evidence,
requires explicit human planning input, constrains pilot scope to proposal scope,
then delegates the actual operating-contract construction to the existing
build_pilot_operating_contract implementation.

No customer contact, CRM write, contract signature, billing, provisioning,
provider call, deploy or production mutation occurs here.
"""
from __future__ import annotations

from hashlib import sha256
from typing import Any, Mapping, Sequence
import json

from atlasquant_aion_b2b_pilot_operating_contract import (
    build_pilot_operating_contract,
)

SCHEMA = "ATLASQUANT_AION_B2B_PILOT_PLANNING_HANDOFF_V1"
PROPOSAL_SCHEMA = "ATLASQUANT_AION_B2B_PROPOSAL_DRAFT_V1"
READINESS_SCHEMA = "ATLASQUANT_AION_B2B_PILOT_READINESS_V1"


def _text(value: Any, limit: int = 420) -> str:
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


def _texts(value: Any, *, limit: int, item_limit: int = 420) -> list[str]:
    if not isinstance(value, (list, tuple)):
        return []
    out: list[str] = []
    for raw in value[:limit]:
        item = _text(raw, item_limit)
        if item and item not in out:
            out.append(item)
    return out


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


def _proposal_blockers(
    proposal_draft: Mapping[str, Any],
    *,
    trusted_scope: Mapping[str, str],
) -> list[str]:
    blockers: list[str] = []

    if proposal_draft.get("schema") != PROPOSAL_SCHEMA:
        blockers.append("PROPOSAL_SCHEMA_INVALID")
    if proposal_draft.get("state") != "DRAFT_FOR_HUMAN_REVIEW":
        blockers.append("PROPOSAL_STATE_INVALID")
    if proposal_draft.get("non_binding") is not True:
        blockers.append("PROPOSAL_MUST_REMAIN_NON_BINDING")
    if proposal_draft.get("owner_review_required") is not True:
        blockers.append("PROPOSAL_OWNER_REVIEW_BOUNDARY_MISSING")

    safe_false = (
        "customer_send_allowed",
        "contract_ready",
        "price_commitment",
        "automatic_proposal_generation",
        "automatic_pricing",
        "automatic_customer_contact",
        "automatic_contract",
        "automatic_billing",
        "automatic_provisioning",
        "crm_write",
        "provider_called",
        "production_mutation",
        "executes_action",
    )
    for key in safe_false:
        if proposal_draft.get(key) is not False:
            blockers.append(f"PROPOSAL_{key.upper()}_UNSAFE")

    proposal = (
        dict(proposal_draft.get("proposal"))
        if isinstance(proposal_draft.get("proposal"), Mapping)
        else {}
    )
    if _scope(proposal) != trusted_scope:
        blockers.append("PROPOSAL_SCOPE_MISMATCH")

    if not _text(proposal_draft.get("proposal_digest"), 180):
        blockers.append("PROPOSAL_DIGEST_REQUIRED")

    pricing = (
        dict(proposal.get("pricing"))
        if isinstance(proposal.get("pricing"), Mapping)
        else {}
    )
    if pricing.get("binding") is not False:
        blockers.append("PROPOSAL_PRICING_MUST_REMAIN_NON_BINDING")

    return blockers


def _readiness_blockers(
    readiness: Mapping[str, Any],
    *,
    trusted_scope: Mapping[str, str],
    candidate_id: str,
    proposal_readiness_digest: str,
) -> list[str]:
    blockers: list[str] = []

    if readiness.get("schema") != READINESS_SCHEMA:
        blockers.append("READINESS_SCHEMA_INVALID")
    if readiness.get("state") != "READY_FOR_OWNER_REVIEW":
        blockers.append("READINESS_STATE_INVALID")
    if readiness.get("decision") != "PILOT_REVIEW_CANDIDATE":
        blockers.append("READINESS_NOT_PILOT_REVIEW_CANDIDATE")
    if readiness.get("human_owner_decision_required") is not True:
        blockers.append("READINESS_OWNER_DECISION_BOUNDARY_MISSING")
    if readiness.get("automatic_acceptance") is not False:
        blockers.append("READINESS_AUTOMATIC_ACCEPTANCE_UNSAFE")
    if readiness.get("automatic_contract") is not False:
        blockers.append("READINESS_AUTOMATIC_CONTRACT_UNSAFE")
    if readiness.get("automatic_billing") is not False:
        blockers.append("READINESS_AUTOMATIC_BILLING_UNSAFE")
    if readiness.get("production_mutation") is not False:
        blockers.append("READINESS_PRODUCTION_BOUNDARY_UNSAFE")
    if readiness.get("executes_action") is not False:
        blockers.append("READINESS_EXECUTION_BOUNDARY_UNSAFE")
    if readiness.get("blockers"):
        blockers.append("READINESS_HAS_BLOCKERS")

    if _text(readiness.get("candidate_id"), 120) != candidate_id:
        blockers.append("READINESS_CANDIDATE_MISMATCH")
    if _scope(readiness.get("scope") if isinstance(readiness.get("scope"), Mapping) else {}) != trusted_scope:
        blockers.append("READINESS_SCOPE_MISMATCH")

    readiness_digest = _text(readiness.get("evidence_digest"), 180)
    if not readiness_digest:
        blockers.append("READINESS_EVIDENCE_DIGEST_REQUIRED")
    if proposal_readiness_digest != readiness_digest:
        blockers.append("PROPOSAL_READINESS_EVIDENCE_MISMATCH")

    return blockers


def _subset_or_block(
    selected: Sequence[str],
    allowed: Sequence[str],
    *,
    blocker: str,
    blockers: list[str],
) -> None:
    allowed_set = set(allowed)
    if any(item not in allowed_set for item in selected):
        blockers.append(blocker)


def build_pilot_planning_handoff(
    *,
    trusted_scope: Mapping[str, Any] | None,
    proposal_draft: Mapping[str, Any] | None,
    readiness: Mapping[str, Any] | None,
    planning_terms: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Create an internal handoff into the existing pilot contract builder."""
    scope = _scope(trusted_scope)
    proposal_result = (
        dict(proposal_draft)
        if isinstance(proposal_draft, Mapping)
        else {}
    )
    readiness_result = (
        dict(readiness)
        if isinstance(readiness, Mapping)
        else {}
    )
    terms = (
        dict(planning_terms)
        if isinstance(planning_terms, Mapping)
        else {}
    )
    blockers: list[str] = []

    if not all(scope.values()):
        blockers.append("TRUSTED_SCOPE_INVALID")

    blockers.extend(
        _proposal_blockers(
            proposal_result,
            trusted_scope=scope,
        )
    )

    proposal = (
        dict(proposal_result.get("proposal"))
        if isinstance(proposal_result.get("proposal"), Mapping)
        else {}
    )
    candidate_id = _text(proposal.get("candidate_id"), 120)
    proposal_id = _text(proposal.get("proposal_id"), 120)
    proposal_digest = _text(proposal_result.get("proposal_digest"), 180)
    proposal_readiness_digest = _text(
        proposal.get("readiness_evidence_digest"),
        180,
    )

    if not candidate_id:
        blockers.append("PROPOSAL_CANDIDATE_ID_REQUIRED")
    if not proposal_id:
        blockers.append("PROPOSAL_ID_REQUIRED")

    blockers.extend(
        _readiness_blockers(
            readiness_result,
            trusted_scope=scope,
            candidate_id=candidate_id,
            proposal_readiness_digest=proposal_readiness_digest,
        )
    )

    human_confirmed = terms.get("human_planning_confirmed") is True
    planner_ref = _text(terms.get("human_pilot_planner_ref"), 320)
    if not human_confirmed:
        blockers.append("EXPLICIT_HUMAN_PILOT_PLANNING_REQUIRED")
    if not planner_ref:
        blockers.append("HUMAN_PILOT_PLANNER_REF_REQUIRED")

    pilot_scope_items = _texts(
        terms.get("pilot_scope_items"),
        limit=16,
        item_limit=500,
    )
    proposal_scope_items = _texts(
        proposal.get("scope_items"),
        limit=16,
        item_limit=500,
    )
    if not pilot_scope_items:
        blockers.append("PILOT_SCOPE_ITEMS_REQUIRED")
    _subset_or_block(
        pilot_scope_items,
        proposal_scope_items,
        blocker="PILOT_SCOPE_EXPANDS_PROPOSAL",
        blockers=blockers,
    )

    objectives = _texts(
        terms.get("objectives"),
        limit=5,
        item_limit=400,
    )
    proposal_objectives = _texts(
        proposal.get("objectives"),
        limit=8,
        item_limit=400,
    )
    if not objectives:
        blockers.append("PILOT_OBJECTIVES_REQUIRED")
    _subset_or_block(
        objectives,
        proposal_objectives,
        blocker="PILOT_OBJECTIVE_NOT_IN_PROPOSAL",
        blockers=blockers,
    )

    quick_wins = _texts(
        terms.get("quick_wins"),
        limit=5,
        item_limit=400,
    )
    proposal_quick_wins = _texts(
        proposal.get("quick_win_candidates"),
        limit=8,
        item_limit=400,
    )
    if not quick_wins:
        blockers.append("PILOT_QUICK_WINS_REQUIRED")
    _subset_or_block(
        quick_wins,
        proposal_quick_wins,
        blocker="PILOT_QUICK_WIN_NOT_IN_PROPOSAL",
        blockers=blockers,
    )

    pilot_id = _text(terms.get("pilot_id"), 120)
    if not pilot_id:
        blockers.append("PILOT_ID_REQUIRED")

    evidence_refs = _texts(
        terms.get("evidence_refs"),
        limit=20,
        item_limit=320,
    )
    if len(evidence_refs) < 2:
        blockers.append("PILOT_PLANNING_EVIDENCE_INSUFFICIENT")

    spec = {
        **scope,
        "pilot_id": pilot_id,
        "candidate_id": candidate_id,
        "duration_days": terms.get("duration_days"),
        "max_monthly_infra_brl": terms.get("max_monthly_infra_brl"),
        "objectives": objectives,
        "quick_wins": quick_wins,
        "kpis": list(terms.get("kpis") or [])
        if isinstance(terms.get("kpis"), (list, tuple))
        else [],
        "stop_conditions": _texts(
            terms.get("stop_conditions"),
            limit=10,
            item_limit=400,
        ),
        "rollback_steps": _texts(
            terms.get("rollback_steps"),
            limit=10,
            item_limit=400,
        ),
        "evidence_refs": list(
            dict.fromkeys(
                [
                    proposal_digest,
                    proposal_readiness_digest,
                    planner_ref,
                    *evidence_refs,
                ]
            )
        ),
    }

    blockers = list(dict.fromkeys(blockers))
    if blockers:
        return {
            "schema": SCHEMA,
            "state": "BLOCKED",
            "scope": scope,
            "proposal_id": proposal_id,
            "candidate_id": candidate_id,
            "pilot_id": pilot_id,
            "blockers": blockers,
            "planning_spec": spec,
            "operating_contract": None,
            "handoff_digest": _digest(
                {
                    "scope": scope,
                    "proposal_digest": proposal_digest,
                    "candidate_id": candidate_id,
                    "pilot_id": pilot_id,
                    "blockers": blockers,
                }
            ),
            "human_owner_approval_required": True,
            "automatic_activation": False,
            "automatic_contract_signature": False,
            "automatic_customer_contact": False,
            "automatic_billing": False,
            "automatic_spend": False,
            "automatic_deploy": False,
            "crm_write": False,
            "provider_called": False,
            "production_mutation": False,
            "executes_action": False,
        }

    contract = build_pilot_operating_contract(
        trusted_scope=scope,
        readiness=readiness_result,
        spec=spec,
    )

    contract_blockers: list[str] = []
    if contract.get("state") != "DRAFT_FOR_OWNER_APPROVAL":
        contract_blockers.append("OPERATING_CONTRACT_NOT_REVIEWABLE")
    if contract.get("activation_state") != "BLOCKED_UNTIL_OWNER_APPROVAL":
        contract_blockers.append("OPERATING_CONTRACT_ACTIVATION_BOUNDARY_INVALID")
    if contract.get("human_owner_approval_required") is not True:
        contract_blockers.append("OPERATING_CONTRACT_OWNER_BOUNDARY_MISSING")
    if contract.get("blockers"):
        contract_blockers.extend(
            f"OPERATING_CONTRACT:{item}"
            for item in list(contract.get("blockers") or [])[:100]
        )

    for key in (
        "automatic_activation",
        "automatic_contract_signature",
        "automatic_customer_contact",
        "automatic_billing",
        "automatic_spend",
        "automatic_deploy",
        "provider_called",
        "production_mutation",
        "executes_action",
    ):
        if contract.get(key) is not False:
            contract_blockers.append(
                f"OPERATING_CONTRACT_{key.upper()}_UNSAFE"
            )

    contract_core = (
        dict(contract.get("contract"))
        if isinstance(contract.get("contract"), Mapping)
        else {}
    )
    if _scope(contract_core) != scope:
        contract_blockers.append("OPERATING_CONTRACT_SCOPE_MISMATCH")
    if _text(contract_core.get("candidate_id"), 120) != candidate_id:
        contract_blockers.append("OPERATING_CONTRACT_CANDIDATE_MISMATCH")
    if proposal_digest not in list(contract_core.get("evidence_refs") or []):
        contract_blockers.append("OPERATING_CONTRACT_PROPOSAL_EVIDENCE_MISSING")

    contract_blockers = list(dict.fromkeys(contract_blockers))
    handoff_material = {
        "scope": scope,
        "proposal_id": proposal_id,
        "proposal_digest": proposal_digest,
        "readiness_digest": proposal_readiness_digest,
        "candidate_id": candidate_id,
        "pilot_id": pilot_id,
        "planner_ref": planner_ref,
        "pilot_scope_items": pilot_scope_items,
        "contract_digest": _text(contract.get("contract_digest"), 180),
    }

    return {
        "schema": SCHEMA,
        "state": (
            "PLANNED_FOR_OWNER_REVIEW"
            if not contract_blockers
            else "BLOCKED"
        ),
        "scope": scope,
        "proposal_id": proposal_id,
        "candidate_id": candidate_id,
        "pilot_id": pilot_id,
        "pilot_scope_items": pilot_scope_items,
        "planning_spec": spec,
        "operating_contract": contract,
        "blockers": contract_blockers,
        "handoff_digest": _digest(handoff_material),
        "human_owner_approval_required": True,
        "activation_state": "BLOCKED_UNTIL_OWNER_APPROVAL",
        "automatic_activation": False,
        "automatic_contract_signature": False,
        "automatic_customer_contact": False,
        "automatic_billing": False,
        "automatic_spend": False,
        "automatic_deploy": False,
        "crm_write": False,
        "provider_called": False,
        "production_mutation": False,
        "executes_action": False,
    }


__all__ = [
    "SCHEMA",
    "PROPOSAL_SCHEMA",
    "READINESS_SCHEMA",
    "build_pilot_planning_handoff",
]
