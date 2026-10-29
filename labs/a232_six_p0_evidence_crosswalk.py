"""A232 LAB: map A231 unexecuted proof questions onto six historical P0 gates.

A matching label or a green CI does not close a P0. P0-5 (native SQLite
read identity) has no external-control checklist substitute. P0-6 requires
native write/commit guarantees in addition to external reconciliation.
Pure read-only schema validation; no keys, vendor, owner or provider I/O.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import re
from typing import Any

from atlasquant_aion_external_evidence_intake import decode_candidate_json
from labs.a227_independence_acceptance_contract import INDEPENDENCE_REQUIREMENTS
from labs.a231_external_control_proof_plan import (
    CHALLENGE_KINDS, preflight_external_control_proof_plan,
)

SCHEMA = "ATLASQUANT_AION_SIX_P0_EVIDENCE_CROSSWALK_UNTRUSTED_V0"
_TOKEN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_HEX = re.compile(r"^[0-9a-f]{64}$")
_FIELDS = frozenset({
    "schema", "owner_id", "tenant_id", "workspace_id", "a231_plan_digest",
    "matrix_state", "owner_signoff_state", "source_contact_state",
    "claimed_gate_state", "external_p0_homologated", "uncertain_resend_policy",
    "p0_gates",
})
_GATE_FIELDS = frozenset({
    "p0_id", "missing_primary_evidence", "supporting_a231_requirements",
    "missing_nonchecklist_gates", "external_evidence_state",
    "native_evidence_state", "independent_review_state", "acceptance_state",
})
# Historical P0 definitions, taken from AION_P0_MATRIZ_PENDENCIAS_20261022:
# owner, provider receipts, original attempt, reboot H0, SQLite read, SQLite write.
# Mapping indicates research relevance, NOT evidence satisfaction.
P0_DEFINITIONS = {
    "P0-1": (
        "HUMAN_OWNER_INDEPENDENT_IDENTITY_AND_REVOCATION",
        ("issuer_trust_anchor", "issuer_public_key_binding", "effective_control_domain",
         "signer_admin_approver_duties", "revocation_expiry",
         "owner_authorization_scope", "owner_tenant_workspace_isolation"),
        ("REAL_OWNER_ENROLLMENT", "OUT_OF_BAND_OWNER_SIGNOFF"),
    ),
    "P0-2": (
        "AUTHENTICATED_PROVIDER_FINAL_EFFECT_RECEIPT",
        ("issuer_trust_anchor", "issuer_public_key_binding",
         "signer_admin_approver_duties", "audit_origin_consistency",
         "revocation_expiry", "provider_final_effect_receipt"),
        ("REAL_PROVIDER_RECEIPT_PROVENANCE", "INDEPENDENT_PROVIDER_RECONCILIATION"),
    ),
    "P0-3": (
        "ORIGINAL_INTENT_BEFORE_SEND_NO_DUPLICATE",
        ("out_of_band_nonce", "replay_rollback_checkpoint", "owner_authorization_scope",
         "provider_final_effect_receipt", "outage_uncertain_no_resend",
         "owner_tenant_workspace_isolation"),
        ("AUTHENTIC_BUSINESS_EVENT_IDENTITY", "DURABLE_PRE_SEND_RESERVATION"),
    ),
    "P0-4": (
        "INDEPENDENT_H0_MONOTONIC_ANTI_ROLLBACK_CUSTODY",
        ("effective_control_domain", "out_of_band_nonce",
         "replay_rollback_checkpoint", "audit_origin_consistency",
         "revocation_expiry", "outage_uncertain_no_resend"),
        ("INDEPENDENT_MONOTONIC_WITNESS", "REAL_REBOOT_RECOVERY_CHALLENGE"),
    ),
    "P0-5": (
        "NATIVE_SQLITE_READ_FILE_IDENTITY_AND_VFS",
        (),
        ("ATOMIC_NATIVE_SQLITE_READ_HANDLE", "HOSTILE_ABA_AND_SAME_INODE_READ_TEST"),
    ),
    "P0-6": (
        "NATIVE_SQLITE_WRITE_COMMIT_OUTCOME_AND_RECOVERY",
        ("provider_final_effect_receipt", "outage_uncertain_no_resend"),
        ("ATOMIC_NATIVE_SQLITE_WRITE_HANDLE", "POST_COMMIT_OUTCOME_RECONCILIATION",
         "BACKUP_RESTORE_AND_SIDECAR_VALIDATION"),
    ),
}


@dataclass(frozen=True)
class SixP0CrosswalkPreflight:
    shape_complete: bool
    untrusted_a231_bound: bool
    p0_gates_documented: int
    p0_gates_homologated: int
    supporting_challenge_cells: tuple[int, ...]
    unmapped_challenge_cells: int
    native_sqlite_read_proven: bool
    native_sqlite_write_proven: bool
    independent_owner_verified: bool
    independent_provider_receipt_verified: bool
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
    local_matrix_digest: str


def _out(code: str, *, valid: bool = False,
         counts: tuple[int, ...] = (), unmapped: int = 0,
         digest: str = "") -> SixP0CrosswalkPreflight:
    return SixP0CrosswalkPreflight(
        shape_complete=valid, untrusted_a231_bound=valid,
        p0_gates_documented=6 if valid else 0, p0_gates_homologated=0,
        supporting_challenge_cells=counts if valid else (),
        unmapped_challenge_cells=unmapped if valid else 0,
        native_sqlite_read_proven=False, native_sqlite_write_proven=False,
        independent_owner_verified=False,
        independent_provider_receipt_verified=False,
        external_evidence_accepted=False, owner_signoff_valid=False,
        provider_final_effect_verified=False, external_p0_homologated=0,
        may_accept_security_proof=False, may_select_model=False,
        may_contact_person=False, may_run_external_challenge=False,
        may_commit_budget=False, may_provision=False,
        may_generate_key=False, may_sign=False, may_connect=False,
        may_confirm=False, may_auto_resend=False,
        code=code, local_matrix_digest=digest if valid else "",
    )


def preflight_six_p0_crosswalk(
    candidate: Any, *, a231_plan: Any, a230_rewrite: Any, a229_graph: Any,
    a228_scenario: Any, a227_contract: Any, a226_claims: Any,
    a225_untrusted_claim: Any, a224_catalog: Any, a223_note: Any,
    a222_matrix: Any, expected_owner_id: Any, expected_tenant_id: Any,
    expected_workspace_id: Any,
) -> SixP0CrosswalkPreflight:
    """Validate an unexecuted historical crosswalk, never authorize activation."""
    if type(candidate) is str:
        try:
            candidate = decode_candidate_json(candidate)
        except (ValueError, TypeError):
            return _out("AMBIGUOUS_OR_OVERSIZED_P0_MATRIX_JSON")
    if type(candidate) is not dict or set(candidate) != _FIELDS:
        return _out("P0_MATRIX_ENVELOPE_NOT_EXACT")
    if candidate["schema"] != SCHEMA:
        return _out("P0_MATRIX_SCHEMA_UNSUPPORTED")
    scope = {
        "owner_id": expected_owner_id,
        "tenant_id": expected_tenant_id,
        "workspace_id": expected_workspace_id,
    }
    if any(type(v) is not str or _TOKEN.fullmatch(v) is None for v in scope.values()):
        return _out("INVALID_EXPECTED_SCOPE")
    if any(type(candidate[k]) is not str or candidate[k] != v for k, v in scope.items()):
        return _out("P0_MATRIX_SCOPE_MISMATCH")
    states = {
        "matrix_state": ("RESEARCH_CROSSWALK_ONLY", "HOST_CANNOT_HOMOLOGATE_P0_MATRIX"),
        "owner_signoff_state": ("NOT_REQUESTED", "HOST_CANNOT_ASSERT_OWNER_SIGNOFF"),
        "source_contact_state": ("NOT_CONTACTED", "HOST_CANNOT_CLAIM_SOURCE_CONTACT"),
        "claimed_gate_state": ("HARD_NO_GO", "HOST_CANNOT_OVERRIDE_HARD_NO_GO"),
        "uncertain_resend_policy": ("ZERO_AUTO_RESEND", "UNCERTAIN_ZERO_AUTO_RESEND_REQUIRED"),
    }
    for field, (expected, code) in states.items():
        if type(candidate[field]) is not str or candidate[field] != expected:
            return _out(code)
    if type(candidate["external_p0_homologated"]) is not int or candidate["external_p0_homologated"] != 0:
        return _out("FALSE_EXTERNAL_P0_HOMOLOGATION")
    if type(a231_plan) is not dict:
        return _out("A231_UNTRUSTED_PLAN_OBJECT_REQUIRED")

    previous = preflight_external_control_proof_plan(
        a231_plan, a230_rewrite=a230_rewrite, a229_graph=a229_graph,
        a228_scenario=a228_scenario, a227_contract=a227_contract,
        a226_claims=a226_claims, a225_untrusted_claim=a225_untrusted_claim,
        a224_catalog=a224_catalog, a223_note=a223_note,
        a222_matrix=a222_matrix, expected_owner_id=expected_owner_id,
        expected_tenant_id=expected_tenant_id,
        expected_workspace_id=expected_workspace_id,
    )
    if not previous.plan_shape_complete or previous.external_evidence_accepted:
        return _out("A231_BLOCKED_UNEXECUTED_PROOF_PLAN_REQUIRED")
    bind = candidate["a231_plan_digest"]
    if (type(bind) is not str or _HEX.fullmatch(bind) is None
            or bind != previous.local_plan_digest):
        return _out("A231_LOCAL_MATRIX_BINDING_MISMATCH")
    gates = candidate["p0_gates"]
    if type(gates) is not list or len(gates) != 6:
        return _out("SIX_P0_GATES_REQUIRED")
    seen: set[str] = set()
    for gate in gates:
        if type(gate) is not dict or set(gate) != _GATE_FIELDS:
            return _out("P0_GATE_ROW_NOT_EXACT")
        pid = gate["p0_id"]
        if type(pid) is not str or pid not in P0_DEFINITIONS:
            return _out("UNKNOWN_P0_GATE")
        if pid in seen:
            return _out("DUPLICATE_P0_GATE")
        seen.add(pid)
        title, requirements, extra = P0_DEFINITIONS[pid]
        if (gate["missing_primary_evidence"] != title
                or type(gate["supporting_a231_requirements"]) is not list
                or gate["supporting_a231_requirements"] != list(requirements)
                or type(gate["missing_nonchecklist_gates"]) is not list
                or gate["missing_nonchecklist_gates"] != list(extra)):
            return _out("P0_EVIDENCE_CROSSWALK_MISMATCH")
        if any(type(gate[k]) is not str or gate[k] != v for k, v in (
            ("external_evidence_state", "NOT_OBTAINED"),
            ("native_evidence_state", "NOT_PROVEN"),
            ("independent_review_state", "NOT_DONE"),
            ("acceptance_state", "HARD_NO_GO"),
        )):
            return _out("HOST_CANNOT_ASSERT_P0_EVIDENCE_OR_ACCEPTANCE")
    if seen != set(P0_DEFINITIONS):
        return _out("REQUIRED_P0_GATE_MISSING")
    covered = set()
    counts = []
    for _, (_, requirements, _) in P0_DEFINITIONS.items():
        counts.append(len(requirements) * len(CHALLENGE_KINDS))
        covered.update(requirements)
    if covered != set(INDEPENDENCE_REQUIREMENTS):
        return _out("UNMAPPED_A231_REQUIREMENT_IN_CONTRACT")
    canonical = dict(candidate)
    canonical["p0_gates"] = [dict(gate) for gate in sorted(gates, key=lambda g: g["p0_id"])]
    payload = json.dumps(canonical, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=False, allow_nan=False).encode("utf-8")
    return _out("SIX_P0_MAPPED_ZERO_INDEPENDENT_PROOFS_AND_NATIVE_GATES_OPEN",
                valid=True, counts=tuple(counts), unmapped=0,
                digest=sha256(payload).hexdigest())


__all__ = ["SCHEMA", "P0_DEFINITIONS", "SixP0CrosswalkPreflight",
           "preflight_six_p0_crosswalk"]
