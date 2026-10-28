"""A221 LAB: protocol blueprint for independently-sourced proof (not proof).

Nothing here collects evidence, contacts parties, validates actual custody,
approves IAM, performs a cloud call or proves any P0 requirement.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import re
from typing import Any

from atlasquant_aion_external_evidence_intake import decode_candidate_json
from labs.a220_synthetic_root_attack_boundaries import (
    KMS_HSM, MODELS, OFFLINE, SCENARIOS,
)


SCHEMA = "ATLASQUANT_AION_INDEPENDENT_EVIDENCE_BLUEPRINT_RESEARCH_V0"
_TOKEN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_FIELDS = frozenset({
    "schema", "owner_id", "tenant_id", "workspace_id",
    "design_state", "owner_approval_state", "provider_selection_state",
    "external_p0_homologated", "requirements",
})
_REQUIREMENT_FIELDS = frozenset({
    "control_id", "model_scope", "nominal_source_role", "challenge_kind",
    "issuer_identity_state", "reviewer_state", "witness_state",
    "challenge_state", "evidence_state", "contact_state", "cost_state",
})
# Roles and challenges are placeholders, not a real person, company or contract.
CONTROL_PROTOCOLS = {
    "offline_private_material_outside_host": ("OFFLINE_CUSTODY_WITNESS", "OFFLINE_MATERIAL_DENIAL_TEST"),
    "offline_custodian_unreachable_by_host": ("OFFLINE_CUSTODY_WITNESS", "OUT_OF_BAND_CUSTODIAN_CHALLENGE"),
    "kms_host_sign_denied": ("INDEPENDENT_KMS_POLICY_AUDITOR", "RUNTIME_SIGN_DENIAL_PROBE"),
    "kms_host_policy_write_denied": ("INDEPENDENT_KMS_POLICY_AUDITOR", "RUNTIME_POLICY_EDIT_DENIAL_PROBE"),
    "kms_host_role_assumption_denied": ("INDEPENDENT_KMS_POLICY_AUDITOR", "RUNTIME_ROLE_ESCALATION_DENIAL_PROBE"),
    "approval_outside_host": ("OWNER_APPROVAL_AUDITOR", "OUT_OF_BAND_APPROVAL_ORIGIN_TEST"),
    "signer_admin_approver_roles_separate": ("ROLE_SEPARATION_AUDITOR", "SEPARATE_PRINCIPAL_CONFLICT_PROBE"),
    "nonce_checkpoint_outside_host": ("INDEPENDENT_REPLAY_WITNESS", "NONCE_REPLAY_AND_CHECKPOINT_TEST"),
    "revocation_checkpoint_outside_host": ("INDEPENDENT_REVOCATION_WITNESS", "REVOKED_KEY_REPLAY_DENIAL_TEST"),
    "audit_witness_outside_host": ("INDEPENDENT_LOG_WITNESS", "INCLUSION_CONSISTENCY_AND_LOG_LOSS_TEST"),
    "outage_fails_closed_no_resend": ("EXTERNAL_RISK_REVIEWER", "OUTAGE_AND_ACK_LOSS_NO_RESEND_TEST"),
    "provider_receipt_not_substituted_by_root_signature": ("PROVIDER_RECEIPT_AUDITOR", "FINAL_EFFECT_RECEIPT_AND_QUERY_TEST"),
    "scope_isolated": ("INDEPENDENT_TENANT_AUDITOR", "CROSS_TENANT_CLAIM_REJECTION_TEST"),
}


@dataclass(frozen=True)
class IndependentEvidenceBlueprintPreflight:
    blueprint_complete: bool
    a220_scenarios_covered: bool
    independent_root_verified: bool
    independent_witness_verified: bool
    owner_approval_valid: bool
    external_p0_homologated: int
    may_collect_evidence: bool
    may_contact_provider: bool
    may_run_external_challenge: bool
    may_provision: bool
    may_sign: bool
    may_connect: bool
    may_confirm: bool
    code: str
    blueprint_digest: str


def _deny(code: str) -> IndependentEvidenceBlueprintPreflight:
    return IndependentEvidenceBlueprintPreflight(
        blueprint_complete=False, a220_scenarios_covered=False,
        independent_root_verified=False, independent_witness_verified=False,
        owner_approval_valid=False, external_p0_homologated=0,
        may_collect_evidence=False, may_contact_provider=False,
        may_run_external_challenge=False, may_provision=False,
        may_sign=False, may_connect=False, may_confirm=False,
        code=code, blueprint_digest="",
    )


def _model_scope(control_id: str) -> str:
    domains = set()
    for eligible, scenario_control in SCENARIOS.values():
        if scenario_control == control_id:
            domains.update(eligible)
    if domains == MODELS:
        return "BOTH"
    if domains == {OFFLINE}:
        return "OFFLINE_ONLY"
    if domains == {KMS_HSM}:
        return "KMS_HSM_ONLY"
    raise ValueError("A220_CONTROL_COVERAGE_CHANGED")


def preflight_independent_evidence_blueprint(
    candidate: Any,
    *,
    expected_owner_id: Any,
    expected_tenant_id: Any,
    expected_workspace_id: Any,
) -> IndependentEvidenceBlueprintPreflight:
    """Only validates the shape of a *future* proof-gathering plan."""
    if type(candidate) is str:
        try:
            candidate = decode_candidate_json(candidate)
        except (ValueError, TypeError):
            return _deny("AMBIGUOUS_OR_OVERSIZED_BLUEPRINT_JSON")
    if type(candidate) is not dict or set(candidate) != _FIELDS:
        return _deny("BLUEPRINT_ENVELOPE_NOT_EXACT")
    if candidate["schema"] != SCHEMA:
        return _deny("BLUEPRINT_SCHEMA_UNSUPPORTED")

    scope = {
        "owner_id": expected_owner_id,
        "tenant_id": expected_tenant_id,
        "workspace_id": expected_workspace_id,
    }
    if any(type(v) is not str or _TOKEN.fullmatch(v) is None for v in scope.values()):
        return _deny("INVALID_EXPECTED_SCOPE")
    if any(type(candidate[k]) is not str or candidate[k] != v for k, v in scope.items()):
        return _deny("BLUEPRINT_SCOPE_MISMATCH")
    if candidate["design_state"] != "RESEARCH_BLUEPRINT_ONLY":
        return _deny("HOST_CANNOT_APPROVE_EVIDENCE_DESIGN")
    if candidate["owner_approval_state"] != "NOT_REQUESTED":
        return _deny("HOST_CANNOT_ASSERT_OWNER_APPROVAL")
    if candidate["provider_selection_state"] != "NO_PROVIDER_SELECTED":
        return _deny("PROVIDER_SELECTION_NOT_AUTHORIZED")
    if type(candidate["external_p0_homologated"]) is not int or candidate["external_p0_homologated"] != 0:
        return _deny("FALSE_EXTERNAL_P0_HOMOLOGATION")

    expected_controls = set(CONTROL_PROTOCOLS)
    a220_controls = {control for _, control in SCENARIOS.values()}
    if expected_controls != a220_controls:
        return _deny("A220_CONTROL_COVERAGE_DRIFT")

    requirements = candidate["requirements"]
    if type(requirements) is not list or len(requirements) != len(expected_controls):
        return _deny("REQUIRED_PROOF_BLUEPRINT_INCOMPLETE")
    seen: set[str] = set()
    for req in requirements:
        if type(req) is not dict or set(req) != _REQUIREMENT_FIELDS:
            return _deny("EVIDENCE_REQUIREMENT_ENVELOPE_NOT_EXACT")
        control_id = req["control_id"]
        if type(control_id) is not str or control_id not in expected_controls:
            return _deny("UNSUPPORTED_EVIDENCE_CONTROL")
        if control_id in seen:
            return _deny("DUPLICATE_EVIDENCE_CONTROL")
        seen.add(control_id)
        if req["model_scope"] != _model_scope(control_id):
            return _deny("EVIDENCE_SCOPE_MISMATCH")
        role, kind = CONTROL_PROTOCOLS[control_id]
        if req["nominal_source_role"] != role:
            return _deny("EVIDENCE_SOURCE_ROLE_MISMATCH")
        if req["challenge_kind"] != kind:
            return _deny("EVIDENCE_CHALLENGE_KIND_MISMATCH")
        required_states = {
            "issuer_identity_state": "UNVERIFIED",
            "reviewer_state": "UNASSIGNED",
            "witness_state": "NOT_OBTAINED",
            "challenge_state": "NOT_EXECUTED",
            "evidence_state": "NOT_OBTAINED",
            "contact_state": "NOT_CONTACTED",
            "cost_state": "NOT_QUOTED",
        }
        if any(type(req[k]) is not str or req[k] != v for k, v in required_states.items()):
            return _deny("EVIDENCE_NOT_OBTAINED_OR_REVIEWED")
    if seen != expected_controls:
        return _deny("A220_EVIDENCE_REQUIREMENTS_MISSING")

    canonical = dict(candidate)
    canonical["requirements"] = sorted(
        (dict(item) for item in requirements), key=lambda x: x["control_id"],
    )
    encoded = json.dumps(
        canonical, ensure_ascii=False, sort_keys=True,
        allow_nan=False, separators=(",", ":"),
    ).encode("utf-8")
    return IndependentEvidenceBlueprintPreflight(
        blueprint_complete=True, a220_scenarios_covered=True,
        independent_root_verified=False, independent_witness_verified=False,
        owner_approval_valid=False, external_p0_homologated=0,
        may_collect_evidence=False, may_contact_provider=False,
        may_run_external_challenge=False, may_provision=False,
        may_sign=False, may_connect=False, may_confirm=False,
        code="BLUEPRINT_SHAPE_COMPLETE_EXTERNAL_AUTHORITIES_AND_PROOFS_ABSENT",
        blueprint_digest=sha256(encoded).hexdigest(),
    )


__all__ = [
    "SCHEMA", "CONTROL_PROTOCOLS", "IndependentEvidenceBlueprintPreflight",
    "preflight_independent_evidence_blueprint",
]
