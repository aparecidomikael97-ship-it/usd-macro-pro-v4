"""A227 LAB: vendor-neutral requirements for future independent evidence.

This is a *shape-only* preflight for a future acceptance contract, never an
external witness, key, cryptographic verifier or authorization system.
Nothing in this module performs I/O or grants real-world capability.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import re
from typing import Any

from atlasquant_aion_external_evidence_intake import decode_candidate_json
from labs.a226_claimed_source_independence import preflight_claimed_source_independence


SCHEMA = "ATLASQUANT_AION_INDEPENDENT_SOURCE_ACCEPTANCE_CONTRACT_RESEARCH_V0"
_TOKEN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_HEX = re.compile(r"^[0-9a-f]{64}$")
_FIELDS = frozenset({
    "schema", "owner_id", "tenant_id", "workspace_id", "a226_claims_digest",
    "design_state", "owner_signoff_state", "provider_selection_state",
    "source_contact_state", "external_p0_homologated", "uncertain_resend_policy",
    "requirements",
})
_REQUIREMENT_FIELDS = frozenset({
    "requirement_id", "proof_kind", "trust_boundary", "negative_challenge",
    "external_evidence_state", "independent_identity_state", "test_state",
    "reviewer_state",
})

# Each tuple is (evidence kind, external trust boundary, negative challenge).
# These are independently testable requirements, not a list of satisfied controls.
INDEPENDENCE_REQUIREMENTS = {
    "issuer_trust_anchor": (
        "OUT_OF_BAND_ANCHOR_PROVENANCE", "HOST_INDEPENDENT_TRUST_ANCHOR",
        "HOST_SUBSTITUTES_ANCHOR_KEY"),
    "issuer_public_key_binding": (
        "AUTHENTICATED_ISSUER_KEY_BINDING", "EXTERNALLY_AUTHENTICATED_ISSUER",
        "HOST_SWAPS_ISSUER_FINGERPRINT"),
    "effective_control_domain": (
        "ACTUAL_ADMIN_CONTROL_SEPARATION", "HOST_INDEPENDENT_CONTROL_PLANE",
        "TWO_LABELS_ONE_ADMINISTRATOR"),
    "signer_admin_approver_duties": (
        "PRINCIPAL_PERMISSION_SEPARATION", "INDEPENDENT_ACCESS_REVIEW",
        "HOST_ASSUMES_CONFLICTING_ROLES"),
    "out_of_band_nonce": (
        "EXTERNALLY_GENERATED_CHALLENGE", "INDEPENDENT_CHALLENGE_ORIGIN",
        "HOST_REPLAYS_ITS_OWN_NONCE"),
    "replay_rollback_checkpoint": (
        "EXTERNAL_MONOTONIC_CHECKPOINT", "INDEPENDENT_REPLAY_WITNESS",
        "HOST_ROLLS_BACK_CHECKPOINT"),
    "audit_origin_consistency": (
        "EXTERNAL_AUDIT_INCLUSION_AND_CONSISTENCY", "INDEPENDENT_AUDIT_CUSTODY",
        "HOST_REWRITES_AUDIT_HISTORY"),
    "revocation_expiry": (
        "EXTERNAL_REVOCATION_AND_EXPIRY", "INDEPENDENT_REVOCATION_AUTHORITY",
        "HOST_REUSES_REVOKED_ISSUER"),
    "owner_authorization_scope": (
        "OUT_OF_BAND_OWNER_APPROVAL", "INDEPENDENT_OWNER_CHANNEL",
        "HOST_FORGES_OWNER_CONSENT"),
    "provider_final_effect_receipt": (
        "INDEPENDENT_PROVIDER_FINAL_RECEIPT", "PROVIDER_CONTROLLED_RECEIPT_CHANNEL",
        "HOST_SUBSTITUTES_ROOT_SIGNATURE"),
    "outage_uncertain_no_resend": (
        "INDEPENDENT_FAILURE_OUTCOME", "HOST_INDEPENDENT_OUTCOME_REVIEW",
        "ACK_LOSS_TRIGGERS_DUPLICATE_SEND"),
    "owner_tenant_workspace_isolation": (
        "INDEPENDENT_SCOPE_BINDING", "EXTERNAL_SCOPE_ENFORCEMENT",
        "CROSS_TENANT_PROOF_REPLAY"),
}


@dataclass(frozen=True)
class IndependenceContractPreflight:
    contract_shape_complete: bool
    untrusted_a226_claims_bound: bool
    requirements_count: int
    actual_issuer_identity_verified: bool
    actual_domain_independence_verified: bool
    actual_external_challenges_executed: bool
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
    contract_digest: str


def _result(code: str, *, complete: bool = False, bound: bool = False,
            digest: str = "") -> IndependenceContractPreflight:
    return IndependenceContractPreflight(
        contract_shape_complete=complete, untrusted_a226_claims_bound=bound,
        requirements_count=len(INDEPENDENCE_REQUIREMENTS) if complete else 0,
        actual_issuer_identity_verified=False,
        actual_domain_independence_verified=False,
        actual_external_challenges_executed=False,
        external_evidence_accepted=False, owner_signoff_valid=False,
        provider_final_effect_verified=False, external_p0_homologated=0,
        may_accept_security_proof=False, may_select_model=False,
        may_contact_person=False, may_run_external_challenge=False,
        may_commit_budget=False, may_provision=False,
        may_generate_key=False, may_sign=False, may_connect=False,
        may_confirm=False, may_auto_resend=False,
        code=code, contract_digest=digest,
    )


def preflight_independent_source_contract(
    candidate: Any, *, a226_claims: Any, a225_untrusted_claim: Any,
    a224_catalog: Any, a223_note: Any, a222_matrix: Any,
    expected_owner_id: Any, expected_tenant_id: Any,
    expected_workspace_id: Any,
) -> IndependenceContractPreflight:
    """Validate a 12-item *unexecuted* contract, not external evidence."""
    if type(candidate) is str:
        try:
            candidate = decode_candidate_json(candidate)
        except (ValueError, TypeError):
            return _result("AMBIGUOUS_OR_OVERSIZED_CONTRACT_JSON")
    if type(candidate) is not dict or set(candidate) != _FIELDS:
        return _result("CONTRACT_ENVELOPE_NOT_EXACT")
    if candidate["schema"] != SCHEMA:
        return _result("CONTRACT_SCHEMA_UNSUPPORTED")

    scope = {
        "owner_id": expected_owner_id,
        "tenant_id": expected_tenant_id,
        "workspace_id": expected_workspace_id,
    }
    if any(type(v) is not str or _TOKEN.fullmatch(v) is None for v in scope.values()):
        return _result("INVALID_EXPECTED_SCOPE")
    if any(type(candidate[k]) is not str or candidate[k] != v for k, v in scope.items()):
        return _result("CONTRACT_SCOPE_MISMATCH")
    required_states = {
        "design_state": ("RESEARCH_REQUIREMENTS_ONLY", "HOST_CANNOT_SELF_CERTIFY_CONTRACT"),
        "owner_signoff_state": ("NOT_REQUESTED", "HOST_CANNOT_ASSERT_OWNER_SIGNOFF"),
        "provider_selection_state": ("NO_PROVIDER_SELECTED", "VENDOR_SELECTION_NOT_AUTHORIZED"),
        "source_contact_state": ("NOT_CONTACTED", "EXTERNAL_CONTACT_NOT_AUTHORIZED"),
        "uncertain_resend_policy": ("ZERO_AUTO_RESEND", "UNCERTAIN_MUST_FAIL_CLOSED"),
    }
    for name, (value, code) in required_states.items():
        if type(candidate[name]) is not str or candidate[name] != value:
            return _result(code)
    if type(candidate["external_p0_homologated"]) is not int or candidate["external_p0_homologated"] != 0:
        return _result("FALSE_EXTERNAL_P0_CLAIM")

    prior = preflight_claimed_source_independence(
        a226_claims, a225_untrusted_claim=a225_untrusted_claim,
        a224_catalog=a224_catalog, a223_note=a223_note,
        a222_matrix=a222_matrix, expected_owner_id=expected_owner_id,
        expected_tenant_id=expected_tenant_id,
        expected_workspace_id=expected_workspace_id,
    )
    if not prior.two_source_envelope_valid or prior.actual_independent_issuers_verified:
        return _result("A226_UNTRUSTED_CLAIMS_REQUIRED")
    if prior.obvious_claimed_shared_control or not prior.locally_coherent_claims:
        return _result("A226_NOMINAL_CONFLICT_MUST_BE_RESOLVED")
    claimed_digest = candidate["a226_claims_digest"]
    if (type(claimed_digest) is not str or _HEX.fullmatch(claimed_digest) is None
            or claimed_digest != prior.local_comparison_digest):
        return _result("A226_LOCAL_CLAIM_BINDING_MISMATCH")

    rows = candidate["requirements"]
    if type(rows) is not list or len(rows) != len(INDEPENDENCE_REQUIREMENTS):
        return _result("INDEPENDENCE_REQUIREMENTS_INCOMPLETE")
    seen: set[str] = set()
    for row in rows:
        if type(row) is not dict or set(row) != _REQUIREMENT_FIELDS:
            return _result("INDEPENDENCE_REQUIREMENT_ENVELOPE_NOT_EXACT")
        item = row["requirement_id"]
        if type(item) is not str or item not in INDEPENDENCE_REQUIREMENTS:
            return _result("UNKNOWN_INDEPENDENCE_REQUIREMENT")
        if item in seen:
            return _result("DUPLICATE_INDEPENDENCE_REQUIREMENT")
        seen.add(item)
        values = INDEPENDENCE_REQUIREMENTS[item]
        if any(type(row[k]) is not str or row[k] != expected for k, expected in zip(
            ("proof_kind", "trust_boundary", "negative_challenge"), values,
        )):
            return _result("INDEPENDENCE_PROOF_PROTOCOL_MISMATCH")
        missing = {
            "external_evidence_state": "NOT_OBTAINED",
            "independent_identity_state": "NOT_VERIFIED",
            "test_state": "NOT_EXECUTED",
            "reviewer_state": "UNASSIGNED",
        }
        if any(type(row[k]) is not str or row[k] != value for k, value in missing.items()):
            return _result("HOST_CANNOT_PROMOTE_REQUIREMENT_TO_EXTERNAL_PROOF")
    if seen != set(INDEPENDENCE_REQUIREMENTS):
        return _result("INDEPENDENCE_REQUIREMENTS_MISSING")

    canonical = dict(candidate)
    canonical["requirements"] = sorted(
        (dict(row) for row in rows), key=lambda row: row["requirement_id"],
    )
    digest = sha256(json.dumps(
        canonical, sort_keys=True, ensure_ascii=False,
        separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")).hexdigest()
    return _result(
        "CONTRACT_SHAPE_COMPLETE_EXTERNAL_INDEPENDENCE_UNVERIFIED",
        complete=True, bound=True, digest=digest,
    )


__all__ = [
    "SCHEMA", "INDEPENDENCE_REQUIREMENTS", "IndependenceContractPreflight",
    "preflight_independent_source_contract",
]
