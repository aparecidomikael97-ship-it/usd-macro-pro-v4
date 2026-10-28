"""A228 LAB: 12-way synthetic failure campaign, always HARD NO-GO.

One or eleven host-claimed passes never cancel even one simulated failure.
All rows are synthetic. No issuer, signer, HSM, network, owner or broker is
contacted, authenticated or authorized by this module.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import re
from typing import Any

from atlasquant_aion_external_evidence_intake import decode_candidate_json
from labs.a227_independence_acceptance_contract import (
    INDEPENDENCE_REQUIREMENTS, preflight_independent_source_contract,
)


SCHEMA = "ATLASQUANT_AION_PARTIAL_INDEPENDENCE_FAILURES_UNTRUSTED_V0"
_TOKEN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_HEX = re.compile(r"^[0-9a-f]{64}$")
_FIELDS = frozenset({
    "schema", "owner_id", "tenant_id", "workspace_id",
    "a227_contract_digest", "study_state", "model_selection_state",
    "owner_signoff_state", "source_contact_state", "claimed_gate_state",
    "external_p0_homologated", "uncertain_resend_policy", "outcomes",
})
_OUTCOME_FIELDS = frozenset({
    "requirement_id", "simulated_outcome", "negative_challenge",
    "claim_origin", "external_evidence_state", "independent_verification_state",
})
CLAIMED_PASS = "HOST_CLAIMS_PASS_UNVERIFIED"
SIMULATED_FAILURE = "SYNTHETIC_NEGATIVE_TEST_FAILED"


@dataclass(frozen=True)
class SyntheticFailureMatrixPreflight:
    scenario_shape_complete: bool
    untrusted_a227_contract_bound: bool
    simulated_failures: int
    host_claimed_passes: int
    independent_passes_verified: int
    actual_independent_source_verified: bool
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
    synthetic_scenario_digest: str


def _out(code: str, *, complete: bool = False, failures: int = 0,
         claimed_passes: int = 0, digest: str = "") -> SyntheticFailureMatrixPreflight:
    return SyntheticFailureMatrixPreflight(
        scenario_shape_complete=complete,
        untrusted_a227_contract_bound=complete,
        simulated_failures=failures if complete else 0,
        host_claimed_passes=claimed_passes if complete else 0,
        independent_passes_verified=0,
        actual_independent_source_verified=False,
        external_evidence_accepted=False,
        owner_signoff_valid=False, provider_final_effect_verified=False,
        external_p0_homologated=0,
        may_accept_security_proof=False, may_select_model=False,
        may_contact_person=False, may_run_external_challenge=False,
        may_commit_budget=False, may_provision=False,
        may_generate_key=False, may_sign=False, may_connect=False,
        may_confirm=False, may_auto_resend=False,
        code=code, synthetic_scenario_digest=digest,
    )


def preflight_partial_independence_failures(
    candidate: Any, *, a227_contract: Any, a226_claims: Any,
    a225_untrusted_claim: Any, a224_catalog: Any, a223_note: Any,
    a222_matrix: Any, expected_owner_id: Any, expected_tenant_id: Any,
    expected_workspace_id: Any,
) -> SyntheticFailureMatrixPreflight:
    """Inspect *claims* for a synthetic 12-way matrix; never verify passes."""
    if type(candidate) is str:
        try:
            candidate = decode_candidate_json(candidate)
        except (ValueError, TypeError):
            return _out("AMBIGUOUS_OR_OVERSIZED_FAILURE_MATRIX_JSON")
    if type(candidate) is not dict or set(candidate) != _FIELDS:
        return _out("FAILURE_MATRIX_ENVELOPE_NOT_EXACT")
    if candidate["schema"] != SCHEMA:
        return _out("FAILURE_MATRIX_SCHEMA_UNSUPPORTED")

    scope = {
        "owner_id": expected_owner_id,
        "tenant_id": expected_tenant_id,
        "workspace_id": expected_workspace_id,
    }
    if any(type(v) is not str or _TOKEN.fullmatch(v) is None for v in scope.values()):
        return _out("INVALID_EXPECTED_SCOPE")
    if any(type(candidate[k]) is not str or candidate[k] != v for k, v in scope.items()):
        return _out("FAILURE_MATRIX_SCOPE_MISMATCH")
    restricted = {
        "study_state": ("SYNTHETIC_FAILURE_CAMPAIGN_ONLY", "CANNOT_SELF_CERTIFY_REAL_TEST"),
        "model_selection_state": ("NO_MODEL_SELECTED", "CANNOT_SELECT_MODEL_IN_LAB"),
        "owner_signoff_state": ("NOT_REQUESTED", "HOST_CANNOT_ASSERT_OWNER_SIGNOFF"),
        "source_contact_state": ("NOT_CONTACTED", "EXTERNAL_CONTACT_NOT_AUTHORIZED"),
        "claimed_gate_state": ("HARD_NO_GO", "HOST_CANNOT_OVERRIDE_HARD_NO_GO"),
        "uncertain_resend_policy": ("ZERO_AUTO_RESEND", "UNCERTAIN_MUST_FAIL_CLOSED"),
    }
    for field, (value, error) in restricted.items():
        if type(candidate[field]) is not str or candidate[field] != value:
            return _out(error)
    if type(candidate["external_p0_homologated"]) is not int or candidate["external_p0_homologated"] != 0:
        return _out("FALSE_EXTERNAL_P0_CLAIM")

    previous = preflight_independent_source_contract(
        a227_contract, a226_claims=a226_claims,
        a225_untrusted_claim=a225_untrusted_claim,
        a224_catalog=a224_catalog, a223_note=a223_note,
        a222_matrix=a222_matrix, expected_owner_id=expected_owner_id,
        expected_tenant_id=expected_tenant_id,
        expected_workspace_id=expected_workspace_id,
    )
    if not previous.contract_shape_complete or previous.external_evidence_accepted:
        return _out("A227_UNVERIFIED_CONTRACT_REQUIRED")
    binding = candidate["a227_contract_digest"]
    if (type(binding) is not str or _HEX.fullmatch(binding) is None
            or binding != previous.contract_digest):
        return _out("A227_LOCAL_CONTRACT_BINDING_MISMATCH")

    rows = candidate["outcomes"]
    if type(rows) is not list or len(rows) != len(INDEPENDENCE_REQUIREMENTS):
        return _out("TWELVE_OUTCOMES_REQUIRED")
    seen: set[str] = set()
    failures = 0
    claimed_passes = 0
    for row in rows:
        if type(row) is not dict or set(row) != _OUTCOME_FIELDS:
            return _out("OUTCOME_ROW_ENVELOPE_NOT_EXACT")
        requirement_id = row["requirement_id"]
        if type(requirement_id) is not str or requirement_id not in INDEPENDENCE_REQUIREMENTS:
            return _out("OUTCOME_REQUIREMENT_UNKNOWN")
        if requirement_id in seen:
            return _out("OUTCOME_REQUIREMENT_DUPLICATE")
        seen.add(requirement_id)
        if row["claim_origin"] != "HOST_SIMULATED_UNTRUSTED":
            return _out("HOST_OUTCOME_CANNOT_CLAIM_INDEPENDENT_ORIGIN")
        if (type(row["external_evidence_state"]) is not str
                or row["external_evidence_state"] != "NOT_OBTAINED"
                or type(row["independent_verification_state"]) is not str
                or row["independent_verification_state"] != "NOT_VERIFIED"):
            return _out("HOST_OUTCOME_CANNOT_PROMOTE_EXTERNAL_PROOF")
        if row["simulated_outcome"] == SIMULATED_FAILURE:
            failures += 1
            expected_challenge = INDEPENDENCE_REQUIREMENTS[requirement_id][2]
        elif row["simulated_outcome"] == CLAIMED_PASS:
            claimed_passes += 1
            expected_challenge = "NONE"
        else:
            return _out("OUTCOME_CANNOT_CLAIM_VERIFIED_SUCCESS")
        if type(row["negative_challenge"]) is not str or row["negative_challenge"] != expected_challenge:
            return _out("NEGATIVE_CHALLENGE_MISMATCH")
    if seen != set(INDEPENDENCE_REQUIREMENTS):
        return _out("REQUIRED_OUTCOMES_MISSING")
    if failures == 0:
        return _out("ZERO_FAILURES_DO_NOT_PROVE_INDEPENDENCE")

    canonical = dict(candidate)
    canonical["outcomes"] = sorted(
        (dict(row) for row in rows), key=lambda row: row["requirement_id"],
    )
    digest = sha256(json.dumps(
        canonical, sort_keys=True, ensure_ascii=False,
        allow_nan=False, separators=(",", ":"),
    ).encode("utf-8")).hexdigest()
    return _out(
        "SIMULATED_FAILURES_BLOCK_ALL_HOST_CLAIMED_PASSES",
        complete=True, failures=failures, claimed_passes=claimed_passes,
        digest=digest,
    )


__all__ = [
    "SCHEMA", "CLAIMED_PASS", "SIMULATED_FAILURE",
    "SyntheticFailureMatrixPreflight", "preflight_partial_independence_failures",
]
