"""A229 LAB: expose shared failure domains among 12 HOST-CONTROLLED claims.

Declared labels, including supposed upstream parents, are untrusted strings.
Detecting a collision is grounds for caution; no collision is NOT proof of
independent administrators, keys, signers, audit custody or recovery paths.
No external access, verification, signatures, contact or I/O occurs here.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import re
from typing import Any

from atlasquant_aion_external_evidence_intake import decode_candidate_json
from labs.a227_independence_acceptance_contract import INDEPENDENCE_REQUIREMENTS
from labs.a228_partial_evidence_failure_matrix import preflight_partial_independence_failures


SCHEMA = "ATLASQUANT_AION_COMMON_CONTROL_DOMAIN_CLAIMS_UNTRUSTED_V0"
_TOKEN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_HEX = re.compile(r"^[0-9a-f]{64}$")
_FIELDS = frozenset({
    "schema", "owner_id", "tenant_id", "workspace_id",
    "a228_scenario_digest", "study_state", "model_selection_state",
    "owner_signoff_state", "source_contact_state", "claimed_gate_state",
    "external_p0_homologated", "uncertain_resend_policy", "sources",
})
CONTROL_LABEL_FIELDS = (
    "claimed_controller_id", "claimed_ultimate_parent_id",
    "claimed_signing_principal_id", "claimed_audit_store_id",
    "claimed_recovery_principal_id",
)
_SOURCE_FIELDS = frozenset({
    "requirement_id", "nominal_source_id", *CONTROL_LABEL_FIELDS,
    "claim_origin", "issuer_identity_state", "dependency_audit_state",
})


@dataclass(frozen=True)
class ClaimedCommonControlPreflight:
    source_envelope_valid: bool
    untrusted_a228_scenario_bound: bool
    nominal_sources_distinct: bool
    pairwise_overlap_count: int
    same_field_pair_counts: tuple[int, ...]
    cross_role_overlap_pairs: int
    intra_source_role_collapses: int
    affected_requirements: tuple[str, ...]
    actual_control_domains_independent: bool
    actual_issuer_identities_verified: bool
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
    local_claim_digest: str


def _out(code: str, *, valid: bool = False, distinct: bool = False,
         overlaps: int = 0, counts: tuple[int, ...] = (0, 0, 0, 0, 0),
         cross_role: int = 0, internal: int = 0,
         affected: tuple[str, ...] = (), digest: str = "") -> ClaimedCommonControlPreflight:
    return ClaimedCommonControlPreflight(
        source_envelope_valid=valid,
        untrusted_a228_scenario_bound=valid,
        nominal_sources_distinct=distinct if valid else False,
        pairwise_overlap_count=overlaps if valid else 0,
        same_field_pair_counts=counts if valid else (0, 0, 0, 0, 0),
        cross_role_overlap_pairs=cross_role if valid else 0,
        intra_source_role_collapses=internal if valid else 0,
        affected_requirements=affected if valid else (),
        actual_control_domains_independent=False,
        actual_issuer_identities_verified=False,
        external_evidence_accepted=False, owner_signoff_valid=False,
        provider_final_effect_verified=False, external_p0_homologated=0,
        may_accept_security_proof=False, may_select_model=False,
        may_contact_person=False, may_run_external_challenge=False,
        may_commit_budget=False, may_provision=False,
        may_generate_key=False, may_sign=False, may_connect=False,
        may_confirm=False, may_auto_resend=False,
        code=code, local_claim_digest=digest,
    )


def preflight_common_control_claims(
    candidate: Any, *, a228_scenario: Any, a227_contract: Any,
    a226_claims: Any, a225_untrusted_claim: Any, a224_catalog: Any,
    a223_note: Any, a222_matrix: Any, expected_owner_id: Any,
    expected_tenant_id: Any, expected_workspace_id: Any,
) -> ClaimedCommonControlPreflight:
    """Count collisions in *host-provided names*. Never certify independence."""
    if type(candidate) is str:
        try:
            candidate = decode_candidate_json(candidate)
        except (ValueError, TypeError):
            return _out("AMBIGUOUS_OR_OVERSIZED_COMMON_CONTROL_JSON")
    if type(candidate) is not dict or set(candidate) != _FIELDS:
        return _out("COMMON_CONTROL_ENVELOPE_NOT_EXACT")
    if candidate["schema"] != SCHEMA:
        return _out("COMMON_CONTROL_SCHEMA_UNSUPPORTED")

    scope = {
        "owner_id": expected_owner_id,
        "tenant_id": expected_tenant_id,
        "workspace_id": expected_workspace_id,
    }
    if any(type(v) is not str or _TOKEN.fullmatch(v) is None for v in scope.values()):
        return _out("INVALID_EXPECTED_SCOPE")
    if any(type(candidate[k]) is not str or candidate[k] != v for k, v in scope.items()):
        return _out("COMMON_CONTROL_SCOPE_MISMATCH")
    restricted = {
        "study_state": ("HOST_DEPENDENCY_LABEL_STUDY_ONLY", "HOST_CANNOT_ASSERT_REAL_DEPENDENCY_AUDIT"),
        "model_selection_state": ("NO_MODEL_SELECTED", "NO_MODEL_CHOICE_FROM_HOST_LABELS"),
        "owner_signoff_state": ("NOT_REQUESTED", "HOST_CANNOT_ASSERT_OWNER_SIGNOFF"),
        "source_contact_state": ("NOT_CONTACTED", "EXTERNAL_CONTACT_NOT_AUTHORIZED"),
        "claimed_gate_state": ("HARD_NO_GO", "HOST_CANNOT_OVERRIDE_HARD_NO_GO"),
        "uncertain_resend_policy": ("ZERO_AUTO_RESEND", "UNCERTAIN_MUST_FAIL_CLOSED"),
    }
    for field, (state, code) in restricted.items():
        if type(candidate[field]) is not str or candidate[field] != state:
            return _out(code)
    if type(candidate["external_p0_homologated"]) is not int or candidate["external_p0_homologated"] != 0:
        return _out("FALSE_EXTERNAL_P0_CLAIM")

    prior = preflight_partial_independence_failures(
        a228_scenario, a227_contract=a227_contract, a226_claims=a226_claims,
        a225_untrusted_claim=a225_untrusted_claim, a224_catalog=a224_catalog,
        a223_note=a223_note, a222_matrix=a222_matrix,
        expected_owner_id=expected_owner_id,
        expected_tenant_id=expected_tenant_id,
        expected_workspace_id=expected_workspace_id,
    )
    if not prior.scenario_shape_complete or prior.external_evidence_accepted:
        return _out("A228_BLOCKED_SYNTHETIC_SCENARIO_REQUIRED")
    digest = candidate["a228_scenario_digest"]
    if (type(digest) is not str or _HEX.fullmatch(digest) is None
            or digest != prior.synthetic_scenario_digest):
        return _out("A228_LOCAL_SCENARIO_BINDING_MISMATCH")

    nodes = candidate["sources"]
    if type(nodes) is not list or len(nodes) != len(INDEPENDENCE_REQUIREMENTS):
        return _out("TWELVE_CONTROL_SOURCE_CLAIMS_REQUIRED")
    seen_requirements: set[str] = set()
    seen_source_names: set[str] = set()
    for node in nodes:
        if type(node) is not dict or set(node) != _SOURCE_FIELDS:
            return _out("CONTROL_SOURCE_ROW_NOT_EXACT")
        rid = node["requirement_id"]
        if type(rid) is not str or rid not in INDEPENDENCE_REQUIREMENTS:
            return _out("UNKNOWN_CONTROL_REQUIREMENT")
        if rid in seen_requirements:
            return _out("DUPLICATE_CONTROL_REQUIREMENT")
        seen_requirements.add(rid)
        for field in ("nominal_source_id", *CONTROL_LABEL_FIELDS):
            val = node[field]
            if type(val) is not str or _TOKEN.fullmatch(val) is None:
                return _out("INVALID_HOST_CONTROL_LABEL")
        if node["nominal_source_id"] in seen_source_names:
            return _out("DUPLICATE_NOMINAL_SOURCE_LABEL")
        seen_source_names.add(node["nominal_source_id"])
        if node["claim_origin"] != "HOST_SUPPLIED_UNVERIFIED":
            return _out("HOST_CANNOT_CLAIM_INDEPENDENT_CONTROL_ORIGIN")
        if (node["issuer_identity_state"] != "NOT_VERIFIED"
                or node["dependency_audit_state"] != "NOT_OBTAINED"):
            return _out("HOST_CANNOT_PROMOTE_CONTROL_LABELS_TO_PROOF")
    if seen_requirements != set(INDEPENDENCE_REQUIREMENTS):
        return _out("REQUIRED_CONTROL_LABELS_MISSING")

    ordered = sorted(nodes, key=lambda n: n["requirement_id"])
    counts = [0] * len(CONTROL_LABEL_FIELDS)
    overlaps = 0
    cross_role = 0
    internal = 0
    affected: set[str] = set()
    for node in ordered:
        labels = [node[k] for k in CONTROL_LABEL_FIELDS]
        if len(set(labels)) != len(labels):
            internal += 1
            affected.add(node["requirement_id"])
    for idx, a in enumerate(ordered):
        for b in ordered[idx + 1:]:
            a_set = {a[field] for field in CONTROL_LABEL_FIELDS}
            b_set = {b[field] for field in CONTROL_LABEL_FIELDS}
            shared = a_set & b_set
            if not shared:
                continue
            overlaps += 1
            affected.update((a["requirement_id"], b["requirement_id"]))
            for i, field in enumerate(CONTROL_LABEL_FIELDS):
                if a[field] == b[field]:
                    counts[i] += 1
            if any(
                a[left] == b[right]
                for left in CONTROL_LABEL_FIELDS
                for right in CONTROL_LABEL_FIELDS
                if left != right
            ):
                cross_role += 1
    canonical = dict(candidate)
    canonical["sources"] = [dict(node) for node in ordered]
    encoded = json.dumps(
        canonical, sort_keys=True, ensure_ascii=False,
        separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")
    return _out(
        "DECLARED_COMMON_CONTROL_LABELS_EXPOSED" if overlaps or internal
        else "DISTINCT_HOST_LABELS_STILL_NOT_INDEPENDENCE_PROOF",
        valid=True, distinct=True, overlaps=overlaps, counts=tuple(counts),
        cross_role=cross_role, internal=internal,
        affected=tuple(sorted(affected)), digest=sha256(encoded).hexdigest(),
    )


__all__ = [
    "SCHEMA", "CONTROL_LABEL_FIELDS", "ClaimedCommonControlPreflight",
    "preflight_common_control_claims",
]
