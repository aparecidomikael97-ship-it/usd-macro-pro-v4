"""A225 LAB: classify forged HOST claims; never accept them as independent proof.

All tokens/hashes are attacker-controlled synthetic text, not cryptographic
attestation. No external identity, KMS, offline key, broker, or network I/O.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import re
from typing import Any

from atlasquant_aion_external_evidence_intake import decode_candidate_json
from labs.a220_synthetic_root_attack_boundaries import MODELS, SCENARIOS
from labs.a221_independent_evidence_blueprint import CONTROL_PROTOCOLS
from labs.a224_security_proof_test_catalog import preflight_security_test_catalog


SCHEMA = "ATLASQUANT_AION_FORGED_SECURITY_PROOF_SIMULATION_UNTRUSTED_V0"
_TOKEN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_HEX = re.compile(r"^[0-9a-f]{64}$")
# Untrusted document/tactic labels. None verifies the source or proves a fact.
FORGERY_TACTICS = frozenset({
    "HOST_SELF_ATTESTED_PASS",
    "FORGED_OWNER_SIGNOFF",
    "FAKE_INDEPENDENT_WITNESS",
    "REPLAYED_EVIDENCE_DIGEST",
    "FAKE_PROVIDER_FINAL_RECEIPT",
    "KMS_POLICY_SCREENSHOT_CLAIM",
    "OFFLINE_CUSTODIAN_SCREENSHOT_CLAIM",
    "OUTAGE_RETRY_PRESSURE",
})
_FIELDS = frozenset({
    "schema", "owner_id", "tenant_id", "workspace_id",
    "a224_catalog_digest", "model_id", "attack_id", "control_id",
    "challenge_kind", "claimed_source_role", "forgery_tactic",
    "claim_origin", "claimed_execution_state", "claimed_evidence_digest",
    "claimed_witness_digest", "issuer_identity_state", "external_proof_state",
    "independent_review_state", "owner_approval_state", "provider_receipt_state",
    "external_p0_homologated", "uncertain_resend_policy",
})


@dataclass(frozen=True)
class ForgedProofPreflight:
    local_shape_matches_research_catalog: bool
    hostile_tactic_identified: bool
    owner_identity_verified: bool
    independent_issuer_verified: bool
    independent_witness_verified: bool
    external_proof_accepted: bool
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
    scenario: str
    forgery_tactic: str
    untrusted_claim_digest: str


def _out(
    code: str, *, local_match: bool = False, scenario: str = "",
    forgery_tactic: str = "", digest: str = "",
) -> ForgedProofPreflight:
    return ForgedProofPreflight(
        local_shape_matches_research_catalog=local_match,
        hostile_tactic_identified=local_match,
        owner_identity_verified=False,
        independent_issuer_verified=False, independent_witness_verified=False,
        external_proof_accepted=False, owner_signoff_valid=False,
        provider_final_effect_verified=False, external_p0_homologated=0,
        may_accept_security_proof=False, may_select_model=False,
        may_contact_person=False, may_run_external_challenge=False,
        may_commit_budget=False, may_provision=False,
        may_generate_key=False, may_sign=False, may_connect=False,
        may_confirm=False, may_auto_resend=False,
        code=code, scenario=scenario, forgery_tactic=forgery_tactic,
        untrusted_claim_digest=digest,
    )


def preflight_untrusted_forged_security_proof(
    candidate: Any,
    *,
    a224_catalog: Any,
    a223_note: Any,
    a222_matrix: Any,
    expected_owner_id: Any,
    expected_tenant_id: Any,
    expected_workspace_id: Any,
) -> ForgedProofPreflight:
    """Classify only *locally plausible* synthetic forgeries; always HARD NO-GO.

    A valid result means the hostile text matches a research question, not
    that an attack really happened or that any protection was demonstrated.
    """
    if type(candidate) is str:
        try:
            candidate = decode_candidate_json(candidate)
        except (ValueError, TypeError):
            return _out("AMBIGUOUS_OR_OVERSIZED_FORGED_PROOF_JSON")
    if type(candidate) is not dict or set(candidate) != _FIELDS:
        return _out("FORGED_PROOF_ENVELOPE_NOT_EXACT")
    if candidate["schema"] != SCHEMA:
        return _out("FORGED_PROOF_SCHEMA_UNSUPPORTED")

    scope = {
        "owner_id": expected_owner_id,
        "tenant_id": expected_tenant_id,
        "workspace_id": expected_workspace_id,
    }
    if any(type(v) is not str or _TOKEN.fullmatch(v) is None for v in scope.values()):
        return _out("INVALID_EXPECTED_SCOPE")
    if any(type(candidate[k]) is not str or candidate[k] != v for k, v in scope.items()):
        return _out("FORGED_PROOF_SCOPE_MISMATCH")

    if type(candidate["model_id"]) is not str or candidate["model_id"] not in MODELS:
        return _out("UNKNOWN_CUSTODY_MODEL")
    attack = candidate["attack_id"]
    if type(attack) is not str or attack not in SCENARIOS:
        return _out("UNKNOWN_FORGED_PROOF_SCENARIO")
    eligible, expected_control = SCENARIOS[attack]
    if candidate["model_id"] not in eligible:
        return _out("ATTACK_AND_MODEL_INCOMPATIBLE")
    if candidate["control_id"] != expected_control:
        return _out("CLAIMED_SECURITY_CONTROL_MISMATCH")
    source_role, expected_challenge = CONTROL_PROTOCOLS[expected_control]
    if (candidate["challenge_kind"] != expected_challenge
            or candidate["claimed_source_role"] != source_role):
        return _out("CLAIMED_SOURCE_ROLE_OR_CHALLENGE_MISMATCH")
    tactic = candidate["forgery_tactic"]
    if type(tactic) is not str or tactic not in FORGERY_TACTICS:
        return _out("UNSUPPORTED_FORGERY_TACTIC")

    required = {
        "claim_origin": "HOST_CONTROLLED_UNTRUSTED",
        "claimed_execution_state": "HOST_CLAIMS_PASS_UNVERIFIED",
        "issuer_identity_state": "UNVERIFIED",
        "external_proof_state": "NOT_OBTAINED",
        "independent_review_state": "UNASSIGNED",
        "owner_approval_state": "NOT_REQUESTED",
        "provider_receipt_state": "NOT_OBTAINED",
        "uncertain_resend_policy": "ZERO_AUTO_RESEND",
    }
    for key, value in required.items():
        if type(candidate[key]) is not str or candidate[key] != value:
            return _out("HOST_CLAIM_CANNOT_BECOME_EXTERNAL_PROOF")
    if type(candidate["external_p0_homologated"]) is not int or candidate["external_p0_homologated"] != 0:
        return _out("FORGED_EXTERNAL_P0_HOMOLOGATION")
    for key in ("claimed_evidence_digest", "claimed_witness_digest"):
        if type(candidate[key]) is not str or _HEX.fullmatch(candidate[key]) is None:
            return _out("INVALID_UNTRUSTED_DIGEST")

    base = preflight_security_test_catalog(
        a224_catalog, a223_note=a223_note, a222_matrix=a222_matrix,
        expected_owner_id=expected_owner_id,
        expected_tenant_id=expected_tenant_id,
        expected_workspace_id=expected_workspace_id,
    )
    if not base.catalog_complete or base.independent_proof_accepted:
        return _out("A224_UNEXECUTED_TEST_CATALOG_REQUIRED")
    digest = candidate["a224_catalog_digest"]
    if type(digest) is not str or _HEX.fullmatch(digest) is None or digest != base.catalog_digest:
        return _out("A224_LOCAL_CATALOG_DIGEST_MISMATCH")

    # A matching checksum is entirely forgeable. It MUST NOT authenticate the
    # witness, source, owner, provider receipt, P0 evidence, or custody root.
    canonical = json.dumps(
        candidate, ensure_ascii=False, sort_keys=True,
        separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")
    return _out(
        "HOST_FORGED_PROOF_LOCALLY_WELL_FORMED_BUT_NO_EXTERNAL_PROOF_HARD_NO_GO",
        local_match=True, scenario=attack, forgery_tactic=tactic,
        digest=sha256(canonical).hexdigest(),
    )


__all__ = [
    "SCHEMA", "FORGERY_TACTICS", "ForgedProofPreflight",
    "preflight_untrusted_forged_security_proof",
]
