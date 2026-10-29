"""A222 LAB: owner's unfilled custody acceptance matrix, no owner decision.

No automatic ranking, signoff, delegation, vendor, spending, keys, or effects.
A valid document proves only that all *questions* are present.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import re
from typing import Any

from atlasquant_aion_external_evidence_intake import decode_candidate_json
from labs.a220_synthetic_root_attack_boundaries import KMS_HSM, OFFLINE
from labs.a221_independent_evidence_blueprint import CONTROL_PROTOCOLS


SCHEMA = "ATLASQUANT_AION_OWNER_ACCEPTANCE_MATRIX_RESEARCH_V0"
CRITERIA = frozenset({
    "CONTROL_INDEPENDENCE", "KEY_RECOVERY", "OUTAGE_CONTINUITY",
    "CUSTODY_BURDEN", "AUDIT_VERIFIABILITY", "REVOCATION_AND_ROTATION",
    "ONGOING_COSTS", "OPERATIONAL_FIT",
})
ROLES = frozenset({
    "OWNER_DECISION_MAKER", "OFFLINE_KEY_CUSTODIAN",
    "KMS_POLICY_ADMIN", "KMS_SIGN_OPERATOR", "INDEPENDENT_WITNESS",
    "RISK_REVIEWER", "PROVIDER_RECEIPT_AUDITOR",
})
_TOKEN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_ENVELOPE = frozenset({
    "schema", "owner_id", "tenant_id", "workspace_id",
    "decision_state", "owner_signoff_state", "selected_model",
    "budget_approval_state", "external_p0_homologated",
    "models_under_review", "criteria", "roles", "evidence_gates",
})
_CRITERION_FIELDS = frozenset({
    "criterion_id", "priority_state", "offline_assessment",
    "kms_hsm_assessment", "owner_preference_state", "evidence_confidence",
})
_ROLE_FIELDS = frozenset({
    "role_id", "assignment_state", "identity_proof_state",
    "contact_state", "authority_state",
})
_GATE_FIELDS = frozenset({
    "control_id", "review_state", "external_evidence_state", "acceptance_state",
})


@dataclass(frozen=True)
class OwnerAcceptanceMatrixPreflight:
    matrix_complete: bool
    owner_preferences_recorded: bool
    responsibilities_assigned: bool
    external_proof_accepted: bool
    owner_signoff_valid: bool
    external_p0_homologated: int
    may_select_model: bool
    may_commit_budget: bool
    may_contact_provider: bool
    may_provision: bool
    may_sign: bool
    may_connect: bool
    may_confirm: bool
    code: str
    draft_digest: str
    unresolved_criteria: tuple[str, ...]


def _deny(code: str) -> OwnerAcceptanceMatrixPreflight:
    return OwnerAcceptanceMatrixPreflight(
        matrix_complete=False, owner_preferences_recorded=False,
        responsibilities_assigned=False, external_proof_accepted=False,
        owner_signoff_valid=False, external_p0_homologated=0,
        may_select_model=False, may_commit_budget=False,
        may_contact_provider=False, may_provision=False,
        may_sign=False, may_connect=False, may_confirm=False,
        code=code, draft_digest="", unresolved_criteria=(),
    )


def preflight_owner_acceptance_matrix(
    candidate: Any,
    *,
    expected_owner_id: Any,
    expected_tenant_id: Any,
    expected_workspace_id: Any,
) -> OwnerAcceptanceMatrixPreflight:
    """Validate an UNFILLED owner review form, never owner consent."""
    if type(candidate) is str:
        try:
            candidate = decode_candidate_json(candidate)
        except (ValueError, TypeError):
            return _deny("AMBIGUOUS_OR_OVERSIZED_OWNER_MATRIX_JSON")
    if type(candidate) is not dict or set(candidate) != _ENVELOPE:
        return _deny("OWNER_MATRIX_ENVELOPE_NOT_EXACT")
    if candidate["schema"] != SCHEMA:
        return _deny("OWNER_MATRIX_SCHEMA_UNSUPPORTED")
    expected = {
        "owner_id": expected_owner_id,
        "tenant_id": expected_tenant_id,
        "workspace_id": expected_workspace_id,
    }
    if any(type(v) is not str or _TOKEN.fullmatch(v) is None for v in expected.values()):
        return _deny("INVALID_EXPECTED_SCOPE")
    if any(type(candidate[k]) is not str or candidate[k] != v for k, v in expected.items()):
        return _deny("OWNER_MATRIX_SCOPE_MISMATCH")
    if candidate["decision_state"] != "AWAITING_OWNER_PRIORITIES":
        return _deny("OWNER_DECISION_CANNOT_BE_SELF_ASSERTED")
    if candidate["owner_signoff_state"] != "NOT_REQUESTED":
        return _deny("HOST_CANNOT_SIGN_FOR_OWNER")
    if candidate["selected_model"] != "NONE":
        return _deny("NO_CUSTODY_MODEL_AUTHORIZED")
    if candidate["budget_approval_state"] != "NOT_REQUESTED":
        return _deny("BUDGET_COMMITMENT_NOT_AUTHORIZED")
    if type(candidate["external_p0_homologated"]) is not int or candidate["external_p0_homologated"] != 0:
        return _deny("FORGED_EXTERNAL_P0_HOMOLOGATION")

    models = candidate["models_under_review"]
    if type(models) is not list or len(models) != 2 or any(type(x) is not str for x in models):
        return _deny("BOTH_RESEARCH_MODELS_REQUIRED")
    if set(models) != {OFFLINE, KMS_HSM}:
        return _deny("BOTH_RESEARCH_MODELS_REQUIRED")

    criteria = candidate["criteria"]
    if type(criteria) is not list or len(criteria) != len(CRITERIA):
        return _deny("OWNER_CRITERIA_INCOMPLETE")
    seen_criteria: set[str] = set()
    for row in criteria:
        if type(row) is not dict or set(row) != _CRITERION_FIELDS:
            return _deny("OWNER_CRITERION_ENVELOPE_NOT_EXACT")
        criterion = row["criterion_id"]
        if type(criterion) is not str or criterion not in CRITERIA:
            return _deny("UNKNOWN_OWNER_CRITERION")
        if criterion in seen_criteria:
            return _deny("DUPLICATE_OWNER_CRITERION")
        seen_criteria.add(criterion)
        required = {
            "priority_state": "UNRANKED",
            "offline_assessment": "NOT_ASSESSED",
            "kms_hsm_assessment": "NOT_ASSESSED",
            "owner_preference_state": "NOT_PROVIDED",
            "evidence_confidence": "NO_EXTERNAL_EVIDENCE",
        }
        if any(type(row[k]) is not str or row[k] != v for k, v in required.items()):
            return _deny("HOST_ASSIGNED_OWNER_PRIORITY_OR_SCORE")

    roles = candidate["roles"]
    if type(roles) is not list or len(roles) != len(ROLES):
        return _deny("OWNER_RESPONSIBILITY_ROLES_INCOMPLETE")
    seen_roles: set[str] = set()
    for row in roles:
        if type(row) is not dict or set(row) != _ROLE_FIELDS:
            return _deny("RESPONSIBILITY_ENVELOPE_NOT_EXACT")
        role_id = row["role_id"]
        if type(role_id) is not str or role_id not in ROLES:
            return _deny("UNKNOWN_RESPONSIBILITY_ROLE")
        if role_id in seen_roles:
            return _deny("DUPLICATE_RESPONSIBILITY_ROLE")
        seen_roles.add(role_id)
        required = {
            "assignment_state": "UNASSIGNED",
            "identity_proof_state": "NOT_OBTAINED",
            "contact_state": "NOT_CONTACTED",
            "authority_state": "NO_AUTHORITY_GRANTED",
        }
        if any(type(row[k]) is not str or row[k] != v for k, v in required.items()):
            return _deny("UNAPPROVED_ROLE_ASSIGNMENT")

    gates = candidate["evidence_gates"]
    expected_gates = set(CONTROL_PROTOCOLS)
    if type(gates) is not list or len(gates) != len(expected_gates):
        return _deny("EXTERNAL_EVIDENCE_GATES_INCOMPLETE")
    seen_gates: set[str] = set()
    for row in gates:
        if type(row) is not dict or set(row) != _GATE_FIELDS:
            return _deny("EVIDENCE_GATE_ENVELOPE_NOT_EXACT")
        gate_id = row["control_id"]
        if type(gate_id) is not str or gate_id not in expected_gates:
            return _deny("UNKNOWN_A221_EVIDENCE_GATE")
        if gate_id in seen_gates:
            return _deny("DUPLICATE_EVIDENCE_GATE")
        seen_gates.add(gate_id)
        required = {
            "review_state": "NOT_STARTED",
            "external_evidence_state": "NOT_OBTAINED",
            "acceptance_state": "NOT_REQUESTED",
        }
        if any(type(row[k]) is not str or row[k] != v for k, v in required.items()):
            return _deny("UNREVIEWED_PROOF_CANNOT_BE_ACCEPTED")

    # All arrays have fixed lengths and unique known IDs; canonicalize order.
    canonical = dict(candidate)
    for field, key in (
        ("criteria", "criterion_id"), ("roles", "role_id"),
        ("evidence_gates", "control_id"),
    ):
        canonical[field] = sorted((dict(x) for x in candidate[field]), key=lambda r: r[key])
    canonical["models_under_review"] = sorted(models)
    encoded = json.dumps(
        canonical, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, allow_nan=False,
    ).encode("utf-8")
    return OwnerAcceptanceMatrixPreflight(
        matrix_complete=True, owner_preferences_recorded=False,
        responsibilities_assigned=False, external_proof_accepted=False,
        owner_signoff_valid=False, external_p0_homologated=0,
        may_select_model=False, may_commit_budget=False,
        may_contact_provider=False, may_provision=False,
        may_sign=False, may_connect=False, may_confirm=False,
        code="OWNER_MATRIX_FORM_COMPLETE_ALL_DECISIONS_AND_P0_PROOFS_PENDING",
        draft_digest=sha256(encoded).hexdigest(),
        unresolved_criteria=tuple(sorted(CRITERIA)),
    )


__all__ = [
    "SCHEMA", "CRITERIA", "ROLES", "OwnerAcceptanceMatrixPreflight",
    "preflight_owner_acceptance_matrix",
]
