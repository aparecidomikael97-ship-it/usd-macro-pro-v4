"""A226 LAB: two coherent HOST reports are NOT independent authorities.

Even separate names, roles, checksums, or stated domains are attacker supplied.
This function has no external transport, key verification, side effects or I/O.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import re
from typing import Any

from atlasquant_aion_external_evidence_intake import decode_candidate_json
from labs.a225_untrusted_security_proof_rejection import (
    preflight_untrusted_forged_security_proof,
)


SCHEMA = "ATLASQUANT_AION_TWO_SOURCE_INDEPENDENCE_CLAIMS_UNTRUSTED_V0"
_TOKEN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_HEX = re.compile(r"^[0-9a-f]{64}$")
_FIELDS = frozenset({
    "schema", "owner_id", "tenant_id", "workspace_id",
    "a225_untrusted_claim_digest", "study_state", "owner_approval_state",
    "provider_receipt_state", "external_p0_homologated",
    "uncertain_resend_policy", "source_a", "source_b",
})
_SOURCE_FIELDS = frozenset({
    "source_id", "claimed_controller_id", "claimed_signing_principal_id",
    "claimed_audit_store_id", "claim_digest", "claim_origin",
    "claim_result_state", "issuer_identity_state", "trust_domain_proof_state",
    "independent_receipt_state",
})


@dataclass(frozen=True)
class ClaimedIndependencePreflight:
    two_source_envelope_valid: bool
    locally_coherent_claims: bool
    obvious_claimed_shared_control: bool
    repeated_claimed_controller: bool
    repeated_claimed_signing_principal: bool
    repeated_claimed_audit_store: bool
    actual_independent_issuers_verified: bool
    actual_domain_separation_verified: bool
    owner_anchor_verified: bool
    independent_evidence_accepted: bool
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
    local_comparison_digest: str


def _out(
    code: str, *, valid: bool = False, coherent: bool = False,
    shared_controller: bool = False, shared_signer: bool = False,
    shared_audit: bool = False, digest: str = "",
) -> ClaimedIndependencePreflight:
    return ClaimedIndependencePreflight(
        two_source_envelope_valid=valid,
        locally_coherent_claims=coherent,
        obvious_claimed_shared_control=(shared_controller or shared_signer or shared_audit),
        repeated_claimed_controller=shared_controller,
        repeated_claimed_signing_principal=shared_signer,
        repeated_claimed_audit_store=shared_audit,
        actual_independent_issuers_verified=False,
        actual_domain_separation_verified=False,
        owner_anchor_verified=False, independent_evidence_accepted=False,
        owner_signoff_valid=False, provider_final_effect_verified=False,
        external_p0_homologated=0,
        may_accept_security_proof=False, may_select_model=False,
        may_contact_person=False, may_run_external_challenge=False,
        may_commit_budget=False, may_provision=False,
        may_generate_key=False, may_sign=False, may_connect=False,
        may_confirm=False, may_auto_resend=False,
        code=code, local_comparison_digest=digest,
    )


def preflight_claimed_source_independence(
    candidate: Any,
    *,
    a225_untrusted_claim: Any,
    a224_catalog: Any,
    a223_note: Any,
    a222_matrix: Any,
    expected_owner_id: Any,
    expected_tenant_id: Any,
    expected_workspace_id: Any,
) -> ClaimedIndependencePreflight:
    """Compare two host-controlled descriptions, NEVER verify independence."""
    if type(candidate) is str:
        try:
            candidate = decode_candidate_json(candidate)
        except (ValueError, TypeError):
            return _out("AMBIGUOUS_OR_OVERSIZED_SOURCE_CLAIMS_JSON")
    if type(candidate) is not dict or set(candidate) != _FIELDS:
        return _out("SOURCE_CLAIMS_ENVELOPE_NOT_EXACT")
    if candidate["schema"] != SCHEMA:
        return _out("SOURCE_CLAIMS_SCHEMA_UNSUPPORTED")

    scope = {
        "owner_id": expected_owner_id,
        "tenant_id": expected_tenant_id,
        "workspace_id": expected_workspace_id,
    }
    if any(type(v) is not str or _TOKEN.fullmatch(v) is None for v in scope.values()):
        return _out("INVALID_EXPECTED_SCOPE")
    if any(type(candidate[k]) is not str or candidate[k] != v for k, v in scope.items()):
        return _out("SOURCE_CLAIMS_SCOPE_MISMATCH")

    if candidate["study_state"] != "TWO_HOST_CONTROLLED_CLAIMS_ONLY":
        return _out("HOST_CANNOT_SELF_CERTIFY_INDEPENDENCE")
    if candidate["owner_approval_state"] != "NOT_REQUESTED":
        return _out("HOST_CANNOT_ASSERT_OWNER_SIGNOFF")
    if candidate["provider_receipt_state"] != "NOT_OBTAINED":
        return _out("HOST_CANNOT_FORGE_PROVIDER_RECEIPT")
    if type(candidate["external_p0_homologated"]) is not int or candidate["external_p0_homologated"] != 0:
        return _out("FALSE_EXTERNAL_P0_CLAIM")
    if candidate["uncertain_resend_policy"] != "ZERO_AUTO_RESEND":
        return _out("UNCERTAIN_MUST_FAIL_CLOSED")

    sources = []
    for key in ("source_a", "source_b"):
        s = candidate[key]
        if type(s) is not dict or set(s) != _SOURCE_FIELDS:
            return _out("SOURCE_DESCRIPTION_NOT_EXACT")
        for name in (
            "source_id", "claimed_controller_id", "claimed_signing_principal_id",
            "claimed_audit_store_id",
        ):
            if type(s[name]) is not str or _TOKEN.fullmatch(s[name]) is None:
                return _out("INVALID_HOST_CLAIMED_SOURCE_IDENTITY")
        if type(s["claim_digest"]) is not str or _HEX.fullmatch(s["claim_digest"]) is None:
            return _out("INVALID_UNTRUSTED_SOURCE_DIGEST")
        required = {
            "claim_origin": "HOST_SUPPLIED_UNVERIFIED",
            "claim_result_state": "HOST_CLAIMS_PASSED",
            "issuer_identity_state": "NOT_VERIFIED",
            "trust_domain_proof_state": "NOT_OBTAINED",
            "independent_receipt_state": "NOT_OBTAINED",
        }
        if any(type(s[name]) is not str or s[name] != value for name, value in required.items()):
            return _out("HOST_CANNOT_ELEVATE_NOMINAL_SOURCE_TO_AUTHORITY")
        sources.append(s)
    a, b = sources
    if a["source_id"] == b["source_id"]:
        return _out("DUPLICATE_NOMINAL_SOURCE_ID")

    base = preflight_untrusted_forged_security_proof(
        a225_untrusted_claim,
        a224_catalog=a224_catalog, a223_note=a223_note,
        a222_matrix=a222_matrix,
        expected_owner_id=expected_owner_id,
        expected_tenant_id=expected_tenant_id,
        expected_workspace_id=expected_workspace_id,
    )
    if not base.local_shape_matches_research_catalog or base.external_proof_accepted:
        return _out("A225_UNTRUSTED_CLAIM_REQUIRED")
    digest = candidate["a225_untrusted_claim_digest"]
    if type(digest) is not str or _HEX.fullmatch(digest) is None or digest != base.untrusted_claim_digest:
        return _out("A225_UNTRUSTED_CLAIM_DIGEST_MISMATCH")

    shared_controller = a["claimed_controller_id"] == b["claimed_controller_id"]
    shared_signer = a["claimed_signing_principal_id"] == b["claimed_signing_principal_id"]
    shared_audit = a["claimed_audit_store_id"] == b["claimed_audit_store_id"]
    coherent = a["claim_digest"] == b["claim_digest"]

    # Sorting handles swapped source slots; the checksum is still untrusted.
    canonical = {
        **{k: v for k, v in candidate.items() if k not in ("source_a", "source_b")},
        "sources": sorted((dict(a), dict(b)), key=lambda s: s["source_id"]),
    }
    encoded = json.dumps(
        canonical, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, allow_nan=False,
    ).encode("utf-8")
    if shared_controller or shared_signer or shared_audit:
        code = "EXPLICIT_SHARED_HOST_LABELS_NOT_INDEPENDENT"
    elif not coherent:
        code = "HOST_CLAIMS_DISAGREE_NO_INDEPENDENT_PROOF"
    else:
        code = "TWO_COHERENT_DISTINCT_HOST_LABELS_INDEPENDENCE_UNPROVEN"
    return _out(
        code, valid=True, coherent=coherent,
        shared_controller=shared_controller, shared_signer=shared_signer,
        shared_audit=shared_audit, digest=sha256(encoded).hexdigest(),
    )


__all__ = [
    "SCHEMA", "ClaimedIndependencePreflight",
    "preflight_claimed_source_independence",
]
