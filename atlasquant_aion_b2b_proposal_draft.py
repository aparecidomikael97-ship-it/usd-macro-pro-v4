"""AION B2B Proposal Draft V1.

Pure/offline preliminary proposal builder for AION Negócios.

The builder consumes a completed Diagnostic Intake plus a Pilot Readiness
owner-review candidate. Commercial scope and any indicative pricing must be
supplied explicitly by a human commercial author.

It never sends a proposal, commits pricing, signs a contract, bills, provisions,
deploys, contacts a customer, writes CRM data, or mutates production.
"""
from __future__ import annotations

from hashlib import sha256
from typing import Any, Mapping
import json
import math

SCHEMA = "ATLASQUANT_AION_B2B_PROPOSAL_DRAFT_V1"
DIAGNOSTIC_SCHEMA = "ATLASQUANT_AION_B2B_DIAGNOSTIC_INTAKE_V1"
READINESS_SCHEMA = "ATLASQUANT_AION_B2B_PILOT_READINESS_V1"

PACKAGES = ("ESSENCIAL", "PROFISSIONAL", "COMPLETO")
PRICING_MODES = ("TBD", "INDICATIVE")


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


def _texts(value: Any, *, limit: int, item_limit: int = 500) -> list[str]:
    if not isinstance(value, (list, tuple)):
        return []
    out: list[str] = []
    for raw in value[:limit]:
        item = _text(raw, item_limit)
        if item and item not in out:
            out.append(item)
    return out


def _money(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(out) or out < 0:
        return None
    return round(out, 2)


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


def build_b2b_proposal_draft(
    *,
    trusted_scope: Mapping[str, Any] | None,
    diagnostic: Mapping[str, Any] | None,
    readiness: Mapping[str, Any] | None,
    commercial_terms: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Build a non-binding proposal draft for human review."""
    scope = _scope(trusted_scope)
    diag = dict(diagnostic) if isinstance(diagnostic, Mapping) else {}
    ready = dict(readiness) if isinstance(readiness, Mapping) else {}
    terms = dict(commercial_terms) if isinstance(commercial_terms, Mapping) else {}
    blockers: list[str] = []

    if not all(scope.values()):
        blockers.append("TRUSTED_SCOPE_INVALID")

    if diag.get("schema") != DIAGNOSTIC_SCHEMA:
        blockers.append("DIAGNOSTIC_SCHEMA_INVALID")
    if diag.get("state") != "READY_FOR_HUMAN_SCORING":
        blockers.append("DIAGNOSTIC_NOT_COMPLETE")
    if diag.get("automatic_score_generation") is not False:
        blockers.append("DIAGNOSTIC_SCORE_BOUNDARY_UNSAFE")
    if diag.get("executes_action") is not False:
        blockers.append("DIAGNOSTIC_EXECUTION_BOUNDARY_UNSAFE")

    dossier = (
        dict(diag.get("dossier"))
        if isinstance(diag.get("dossier"), Mapping)
        else {}
    )
    diagnostic_scope = _scope(dossier)
    if diagnostic_scope != scope:
        blockers.append("DIAGNOSTIC_SCOPE_MISMATCH")

    diagnostic_digest = _text(diag.get("diagnostic_digest"), 180)
    if not diagnostic_digest:
        blockers.append("DIAGNOSTIC_DIGEST_REQUIRED")

    candidate_id = _text(dossier.get("candidate_id"), 120)
    company_label = _text(dossier.get("company_label"), 180)
    if not candidate_id:
        blockers.append("CANDIDATE_ID_REQUIRED")
    if not company_label:
        blockers.append("COMPANY_LABEL_REQUIRED")

    if ready.get("schema") != READINESS_SCHEMA:
        blockers.append("READINESS_SCHEMA_INVALID")
    if ready.get("state") != "READY_FOR_OWNER_REVIEW":
        blockers.append("READINESS_STATE_INVALID")
    if ready.get("decision") != "PILOT_REVIEW_CANDIDATE":
        blockers.append("READINESS_NOT_PILOT_REVIEW_CANDIDATE")
    if ready.get("human_owner_decision_required") is not True:
        blockers.append("READINESS_OWNER_DECISION_BOUNDARY_MISSING")
    if ready.get("automatic_acceptance") is not False:
        blockers.append("READINESS_AUTOMATIC_ACCEPTANCE_UNSAFE")
    if ready.get("automatic_contract") is not False:
        blockers.append("READINESS_AUTOMATIC_CONTRACT_UNSAFE")
    if ready.get("automatic_billing") is not False:
        blockers.append("READINESS_AUTOMATIC_BILLING_UNSAFE")
    if ready.get("executes_action") is not False:
        blockers.append("READINESS_EXECUTION_BOUNDARY_UNSAFE")
    if ready.get("blockers"):
        blockers.append("READINESS_HAS_BLOCKERS")

    readiness_candidate_id = _text(ready.get("candidate_id"), 120)
    if readiness_candidate_id != candidate_id:
        blockers.append("READINESS_CANDIDATE_MISMATCH")
    if _scope(ready.get("scope") if isinstance(ready.get("scope"), Mapping) else {}) != scope:
        blockers.append("READINESS_SCOPE_MISMATCH")

    readiness_digest = _text(ready.get("evidence_digest"), 180)
    if not readiness_digest:
        blockers.append("READINESS_EVIDENCE_DIGEST_REQUIRED")

    proposal_id = _text(terms.get("proposal_id"), 120)
    human_author_ref = _text(terms.get("human_commercial_author_ref"), 320)
    human_terms_confirmed = terms.get("human_terms_confirmed") is True
    non_binding = terms.get("non_binding") is True
    package = _text(terms.get("package"), 40).upper()
    pricing_mode = _text(terms.get("pricing_mode"), 40).upper()

    if not proposal_id:
        blockers.append("PROPOSAL_ID_REQUIRED")
    if not human_author_ref:
        blockers.append("HUMAN_COMMERCIAL_AUTHOR_REF_REQUIRED")
    if not human_terms_confirmed:
        blockers.append("EXPLICIT_HUMAN_COMMERCIAL_TERMS_REQUIRED")
    if not non_binding:
        blockers.append("NON_BINDING_DRAFT_REQUIRED")
    if package not in PACKAGES:
        blockers.append("PACKAGE_INVALID")
    if pricing_mode not in PRICING_MODES:
        blockers.append("PRICING_MODE_INVALID")

    scope_items = _texts(terms.get("scope_items"), limit=16)
    exclusions = _texts(terms.get("exclusions"), limit=16)
    implementation_phases = _texts(terms.get("implementation_phases"), limit=10)
    assumptions = _texts(terms.get("assumptions"), limit=16)
    proposal_evidence_refs = _texts(
        terms.get("evidence_refs"), limit=30, item_limit=320
    )

    if len(scope_items) < 3:
        blockers.append("PROPOSAL_SCOPE_INSUFFICIENT")
    if len(exclusions) < 2:
        blockers.append("PROPOSAL_EXCLUSIONS_INSUFFICIENT")
    if len(implementation_phases) < 2:
        blockers.append("IMPLEMENTATION_PHASES_INSUFFICIENT")
    if len(assumptions) < 2:
        blockers.append("PROPOSAL_ASSUMPTIONS_INSUFFICIENT")
    if len(proposal_evidence_refs) < 2:
        blockers.append("PROPOSAL_EVIDENCE_INSUFFICIENT")

    validity_days = terms.get("validity_days")
    if (
        isinstance(validity_days, bool)
        or not isinstance(validity_days, int)
        or validity_days < 1
        or validity_days > 60
    ):
        blockers.append("PROPOSAL_VALIDITY_INVALID")

    setup_fee = _money(terms.get("indicative_setup_fee_brl"))
    monthly_fee = _money(terms.get("indicative_monthly_fee_brl"))
    pricing_basis_ref = _text(terms.get("pricing_basis_ref"), 320)

    if pricing_mode == "INDICATIVE":
        if setup_fee is None:
            blockers.append("INDICATIVE_SETUP_FEE_INVALID")
        if monthly_fee is None:
            blockers.append("INDICATIVE_MONTHLY_FEE_INVALID")
        if not pricing_basis_ref:
            blockers.append("PRICING_BASIS_REF_REQUIRED")
    elif pricing_mode == "TBD":
        if terms.get("indicative_setup_fee_brl") is not None:
            blockers.append("TBD_SETUP_FEE_MUST_BE_EMPTY")
        if terms.get("indicative_monthly_fee_brl") is not None:
            blockers.append("TBD_MONTHLY_FEE_MUST_BE_EMPTY")
        setup_fee = None
        monthly_fee = None
        pricing_basis_ref = ""

    objectives = _texts(dossier.get("objectives"), limit=8)
    quick_wins = _texts(dossier.get("quick_win_candidates"), limit=8)
    constraints = _texts(dossier.get("constraints"), limit=12)

    proposal_core = {
        **scope,
        "proposal_id": proposal_id,
        "candidate_id": candidate_id,
        "company_label": company_label,
        "package": package,
        "pricing": {
            "mode": pricing_mode,
            "indicative_setup_fee_brl": setup_fee,
            "indicative_monthly_fee_brl": monthly_fee,
            "pricing_basis_ref": pricing_basis_ref,
            "currency": "BRL",
            "binding": False,
        },
        "scope_items": scope_items,
        "exclusions": exclusions,
        "implementation_phases": implementation_phases,
        "assumptions": assumptions,
        "objectives": objectives,
        "quick_win_candidates": quick_wins,
        "diagnostic_constraints": constraints,
        "pilot_duration_days": ready.get("pilot_duration_days"),
        "validity_days": (
            validity_days
            if isinstance(validity_days, int) and not isinstance(validity_days, bool)
            else None
        ),
        "diagnostic_digest": diagnostic_digest,
        "readiness_evidence_digest": readiness_digest,
        "human_commercial_author_ref": human_author_ref,
        "evidence_refs": proposal_evidence_refs,
    }

    blockers = list(dict.fromkeys(blockers))
    return {
        "schema": SCHEMA,
        "state": "DRAFT_FOR_HUMAN_REVIEW" if not blockers else "BLOCKED",
        "proposal": proposal_core,
        "blockers": blockers,
        "proposal_digest": _digest(proposal_core),
        "non_binding": True,
        "owner_review_required": True,
        "customer_send_allowed": False,
        "contract_ready": False,
        "price_commitment": False,
        "automatic_proposal_generation": False,
        "automatic_pricing": False,
        "automatic_customer_contact": False,
        "automatic_contract": False,
        "automatic_billing": False,
        "automatic_provisioning": False,
        "crm_write": False,
        "provider_called": False,
        "production_mutation": False,
        "executes_action": False,
    }


__all__ = [
    "SCHEMA",
    "DIAGNOSTIC_SCHEMA",
    "READINESS_SCHEMA",
    "PACKAGES",
    "PRICING_MODES",
    "build_b2b_proposal_draft",
]
