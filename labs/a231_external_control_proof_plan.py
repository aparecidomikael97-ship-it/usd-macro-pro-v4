"""A231 LAB: sixty *unrequested* out-of-host proof challenges, never authority.

A host-written checklist cannot establish signer custody, administrative
independence, owner consent or the provenance of any external evidence.
This module is pure, read-only and deliberately never has a positive trust path.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import re
from typing import Any

from atlasquant_aion_external_evidence_intake import decode_candidate_json
from labs.a227_independence_acceptance_contract import INDEPENDENCE_REQUIREMENTS
from labs.a229_common_control_domain_claims import CONTROL_LABEL_FIELDS
from labs.a230_host_label_rewrite import preflight_host_label_rewrite

SCHEMA = "ATLASQUANT_AION_EXTERNAL_CONTROL_PROOF_PLAN_UNTRUSTED_V0"
_TOKEN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_HEX = re.compile(r"^[0-9a-f]{64}$")
CHALLENGE_KINDS = {
    "claimed_controller_id": "OUT_OF_HOST_ADMIN_AUTHORITY_ATTESTATION",
    "claimed_ultimate_parent_id": "OUT_OF_HOST_UPSTREAM_AUTHORITY_ATTESTATION",
    "claimed_signing_principal_id": "OUT_OF_HOST_SIGNER_CUSTODY_ATTESTATION",
    "claimed_audit_store_id": "OUT_OF_HOST_AUDIT_CUSTODY_ATTESTATION",
    "claimed_recovery_principal_id": "OUT_OF_HOST_RECOVERY_CONTROL_ATTESTATION",
}
assert tuple(CHALLENGE_KINDS) == CONTROL_LABEL_FIELDS
_FIELDS = frozenset({
    "schema", "owner_id", "tenant_id", "workspace_id",
    "a230_local_claim_digest", "plan_state", "owner_signoff_state",
    "model_selection_state", "source_contact_state", "claimed_gate_state",
    "external_p0_homologated", "uncertain_resend_policy", "challenges",
})
_CHALLENGE_FIELDS = frozenset({
    "requirement_id", "control_domain", "challenge_kind",
    "challenge_nonce_state", "issuer_identity_state",
    "independent_witness_state", "external_acquisition_state",
    "evidence_state", "reviewer_state",
})
_CHALLENGE_STATES = {
    "challenge_nonce_state": "NOT_ISSUED",
    "issuer_identity_state": "NOT_VERIFIED",
    "independent_witness_state": "NOT_VERIFIED",
    "external_acquisition_state": "NOT_REQUESTED",
    "evidence_state": "NOT_OBTAINED",
    "reviewer_state": "NOT_ASSIGNED",
}


@dataclass(frozen=True)
class ExternalControlProofPlanPreflight:
    plan_shape_complete: bool
    untrusted_a230_bound: bool
    planned_challenges: int
    external_challenges_executed: int
    real_control_domains_independently_verified: int
    actual_issuer_identity_verified: bool
    actual_control_domains_independent: bool
    external_evidence_accepted: bool
    owner_signoff_valid: bool
    provider_final_effect_verified: bool
    external_p0_homologated: int
    may_accept_security_proof: bool
    may_select_model: bool
    may_contact_person: bool
    may_run_external_challenge: bool
    may_commit_budget: bool
    may_provision: bool
    may_generate_key: bool
    may_sign: bool
    may_connect: bool
    may_confirm: bool
    may_auto_resend: bool
    code: str
    local_plan_digest: str


def _out(code: str, *, complete: bool = False, digest: str = "") -> ExternalControlProofPlanPreflight:
    return ExternalControlProofPlanPreflight(
        plan_shape_complete=complete,
        untrusted_a230_bound=complete,
        planned_challenges=60 if complete else 0,
        external_challenges_executed=0,
        real_control_domains_independently_verified=0,
        actual_issuer_identity_verified=False,
        actual_control_domains_independent=False,
        external_evidence_accepted=False,
        owner_signoff_valid=False,
        provider_final_effect_verified=False,
        external_p0_homologated=0,
        may_accept_security_proof=False, may_select_model=False,
        may_contact_person=False, may_run_external_challenge=False,
        may_commit_budget=False, may_provision=False,
        may_generate_key=False, may_sign=False, may_connect=False,
        may_confirm=False, may_auto_resend=False,
        code=code, local_plan_digest=digest if complete else "",
    )


def preflight_external_control_proof_plan(
    candidate: Any, *, a230_rewrite: Any, a229_graph: Any,
    a228_scenario: Any, a227_contract: Any, a226_claims: Any,
    a225_untrusted_claim: Any, a224_catalog: Any, a223_note: Any,
    a222_matrix: Any, expected_owner_id: Any, expected_tenant_id: Any,
    expected_workspace_id: Any,
) -> ExternalControlProofPlanPreflight:
    """Validate an unexecuted 12 x 5 checklist; never acquire any proof."""
    if type(candidate) is str:
        try:
            candidate = decode_candidate_json(candidate)
        except (TypeError, ValueError):
            return _out("AMBIGUOUS_OR_OVERSIZED_PROOF_PLAN_JSON")
    if type(candidate) is not dict or set(candidate) != _FIELDS:
        return _out("PROOF_PLAN_ENVELOPE_NOT_EXACT")
    if candidate["schema"] != SCHEMA:
        return _out("PROOF_PLAN_SCHEMA_UNSUPPORTED")
    scope = {
        "owner_id": expected_owner_id,
        "tenant_id": expected_tenant_id,
        "workspace_id": expected_workspace_id,
    }
    if any(type(v) is not str or _TOKEN.fullmatch(v) is None for v in scope.values()):
        return _out("INVALID_EXPECTED_SCOPE")
    if any(type(candidate[k]) is not str or candidate[k] != v for k, v in scope.items()):
        return _out("PROOF_PLAN_SCOPE_MISMATCH")
    states = {
        "plan_state": ("HOST_WRITTEN_UNEXECUTED_PLAN_ONLY", "HOST_CANNOT_CLAIM_CHALLENGES_EXECUTED"),
        "owner_signoff_state": ("NOT_REQUESTED", "HOST_CANNOT_ASSERT_OWNER_SIGNOFF"),
        "model_selection_state": ("NO_MODEL_SELECTED", "HOST_CANNOT_SELECT_MODEL"),
        "source_contact_state": ("NOT_CONTACTED", "HOST_CANNOT_CLAIM_SOURCE_CONTACT"),
        "claimed_gate_state": ("HARD_NO_GO", "HOST_CANNOT_OVERRIDE_HARD_NO_GO"),
        "uncertain_resend_policy": ("ZERO_AUTO_RESEND", "UNCERTAIN_ZERO_AUTO_RESEND_REQUIRED"),
    }
    for field, (expected, code) in states.items():
        if type(candidate[field]) is not str or candidate[field] != expected:
            return _out(code)
    if type(candidate["external_p0_homologated"]) is not int or candidate["external_p0_homologated"] != 0:
        return _out("FALSE_EXTERNAL_P0_HOMOLOGATION")

    if type(a230_rewrite) is not dict or type(a229_graph) is not dict:
        return _out("A230_UNTRUSTED_RESEARCH_INPUTS_REQUIRED")
    prior = preflight_host_label_rewrite(
        a230_rewrite, a229_graph=a229_graph, a228_scenario=a228_scenario,
        a227_contract=a227_contract, a226_claims=a226_claims,
        a225_untrusted_claim=a225_untrusted_claim, a224_catalog=a224_catalog,
        a223_note=a223_note, a222_matrix=a222_matrix,
        expected_owner_id=expected_owner_id,
        expected_tenant_id=expected_tenant_id,
        expected_workspace_id=expected_workspace_id,
    )
    if not prior.rewrite_graph_valid or prior.external_evidence_accepted:
        return _out("A230_BLOCKED_UNTRUSTED_PLAN_REQUIRED")
    binding = candidate["a230_local_claim_digest"]
    if (type(binding) is not str or _HEX.fullmatch(binding) is None
            or binding != prior.local_claim_digest):
        return _out("A230_LOCAL_PLAN_BINDING_MISMATCH")

    rows = candidate["challenges"]
    if type(rows) is not list or len(rows) != len(INDEPENDENCE_REQUIREMENTS) * len(CHALLENGE_KINDS):
        return _out("SIXTY_UNEXECUTED_CHALLENGES_REQUIRED")
    seen: set[tuple[str, str]] = set()
    for row in rows:
        if type(row) is not dict or set(row) != _CHALLENGE_FIELDS:
            return _out("PROOF_CHALLENGE_ROW_NOT_EXACT")
        rid, domain = row["requirement_id"], row["control_domain"]
        if type(rid) is not str or rid not in INDEPENDENCE_REQUIREMENTS:
            return _out("UNKNOWN_INDEPENDENCE_REQUIREMENT")
        if type(domain) is not str or domain not in CHALLENGE_KINDS:
            return _out("UNKNOWN_CONTROL_DOMAIN")
        pair = (rid, domain)
        if pair in seen:
            return _out("DUPLICATE_CONTROL_PROOF_CHALLENGE")
        seen.add(pair)
        if type(row["challenge_kind"]) is not str or row["challenge_kind"] != CHALLENGE_KINDS[domain]:
            return _out("CONTROL_DOMAIN_CHALLENGE_KIND_MISMATCH")
        for field, expected in _CHALLENGE_STATES.items():
            if type(row[field]) is not str or row[field] != expected:
                return _out("HOST_CANNOT_ASSERT_EXTERNAL_CHALLENGE_PROOF_OR_REVIEW")
    if seen != {(rid, domain) for rid in INDEPENDENCE_REQUIREMENTS for domain in CHALLENGE_KINDS}:
        return _out("REQUIRED_INDEPENDENCE_CHALLENGE_MISSING")
    canonical = dict(candidate)
    canonical["challenges"] = [dict(row) for row in sorted(
        rows, key=lambda row: (row["requirement_id"], row["control_domain"]))]
    encoded = json.dumps(canonical, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=False, allow_nan=False).encode("utf-8")
    return _out("SIXTY_EXTERNAL_PROOFS_NOT_OBTAINED", complete=True,
                digest=sha256(encoded).hexdigest())


__all__ = ["SCHEMA", "CHALLENGE_KINDS", "ExternalControlProofPlanPreflight",
           "preflight_external_control_proof_plan"]
