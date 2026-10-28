"""A224 LAB: hypothetical independent-security-test catalog, never an execution plan.

Each attack specifies a desired *future* safe behavior, NOT a tested control.
No key, host challenge, cloud call, person, provider, or broker is touched.
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
from labs.a221_independent_evidence_blueprint import CONTROL_PROTOCOLS
from labs.a223_owner_security_priority import (
    PRIORITY, preflight_owner_security_priority,
)


SCHEMA = "ATLASQUANT_AION_SECURITY_PROOF_CATALOG_RESEARCH_V0"
_TOKEN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_HEX = re.compile(r"^[0-9a-f]{64}$")
_FIELDS = frozenset({
    "schema", "owner_id", "tenant_id", "workspace_id",
    "research_priority", "a223_note_digest", "plan_state",
    "owner_approval_state", "selected_model", "provider_selection_state",
    "budget_approval_state", "external_p0_homologated",
    "uncertain_resend_policy", "models_under_review", "test_catalog",
})
_ROW_FIELDS = frozenset({
    "attack_id", "control_id", "model_scope", "nominal_source_role",
    "challenge_kind", "expected_safe_behavior", "execution_state",
    "external_proof_state", "independent_review_state", "remediation_state",
})
# Desired outcomes (questions for future independent proof), not safeguards.
EXPECTED_SAFE_BEHAVIOR = {
    "HOST_READS_OFFLINE_PRIVATE_MATERIAL": "DENY_PRIVATE_MATERIAL_ACCESS",
    "HOST_IMPERSONATES_OFFLINE_CUSTODIAN": "REJECT_CUSTODIAN_IMPERSONATION",
    "HOST_INVOKES_KMS_SIGN": "DENY_HOST_SIGN",
    "HOST_CHANGES_KMS_KEY_POLICY": "DENY_HOST_POLICY_WRITE",
    "HOST_ASSUMES_SIGNER_ROLE": "DENY_HOST_ROLE_ESCALATION",
    "HOST_FORGES_OWNER_APPROVAL": "REJECT_NONINDEPENDENT_APPROVAL",
    "ADMIN_SIGNER_APPROVER_COLLUSION": "ENFORCE_SEPARATE_PRINCIPALS",
    "HOST_REPLAYS_OLD_NONCE": "REJECT_NONCE_REPLAY",
    "HOST_REUSES_REVOKED_ROOT": "REJECT_REVOKED_ROOT",
    "HOST_ERASES_AUDIT_TRAIL": "DETECT_AUDIT_FORK_OR_LOSS",
    "OUTAGE_FORCES_AUTOMATIC_RESEND": "FAIL_CLOSED_WITH_ZERO_AUTO_RESEND",
    "ROOT_SIGNATURE_FORGES_BROKER_EFFECT": "REQUIRE_AUTHORITATIVE_PROVIDER_RECEIPT",
    "HOST_SUBSTITUTES_OTHER_TENANT": "REJECT_CROSS_SCOPE_CLAIM",
}


@dataclass(frozen=True)
class HypotheticalSecurityTest:
    attack_id: str
    control_id: str
    model_scope: str
    nominal_source_role: str
    challenge_kind: str
    expected_safe_behavior: str
    execution_state: str = "NOT_EXECUTED"
    external_proof_state: str = "NOT_OBTAINED"
    independent_review_state: str = "UNASSIGNED"
    remediation_state: str = "NOT_STARTED"


@dataclass(frozen=True)
class SecurityCatalogPreflight:
    catalog_complete: bool
    security_priority_noted: bool
    owner_identity_verified: bool
    owner_signoff_valid: bool
    independent_tests_executed: bool
    independent_proof_accepted: bool
    custody_model_selected: bool
    external_p0_homologated: int
    may_run_external_challenge: bool
    may_contact_person: bool
    may_select_model: bool
    may_commit_budget: bool
    may_provision: bool
    may_generate_key: bool
    may_sign: bool
    may_connect: bool
    may_confirm: bool
    may_auto_resend: bool
    code: str
    catalog_digest: str
    unexecuted_attacks: tuple[str, ...]


def _out(code: str, *, valid: bool = False, digest: str = "") -> SecurityCatalogPreflight:
    return SecurityCatalogPreflight(
        catalog_complete=valid, security_priority_noted=valid,
        owner_identity_verified=False, owner_signoff_valid=False,
        independent_tests_executed=False, independent_proof_accepted=False,
        custody_model_selected=False, external_p0_homologated=0,
        may_run_external_challenge=False, may_contact_person=False,
        may_select_model=False, may_commit_budget=False,
        may_provision=False, may_generate_key=False,
        may_sign=False, may_connect=False, may_confirm=False,
        may_auto_resend=False, code=code, catalog_digest=digest,
        unexecuted_attacks=tuple(sorted(SCENARIOS)) if valid else (),
    )


def hypothetical_security_test_rows() -> tuple[HypotheticalSecurityTest, ...]:
    """Fixed questions, with model-specific scope; absolutely no probes run."""
    if (set(EXPECTED_SAFE_BEHAVIOR) != set(SCENARIOS)
            or {control for _, control in SCENARIOS.values()} != set(CONTROL_PROTOCOLS)
            or len(SCENARIOS) != len(CONTROL_PROTOCOLS)):
        raise ValueError("A220_A221_A224_SECURITY_CATALOG_DRIFT")
    out = []
    for attack_id in sorted(SCENARIOS):
        eligible, control = SCENARIOS[attack_id]
        if eligible == MODELS:
            model_scope = "BOTH"
        elif eligible == frozenset({OFFLINE}):
            model_scope = "OFFLINE_ONLY"
        elif eligible == frozenset({KMS_HSM}):
            model_scope = "KMS_HSM_ONLY"
        else:
            raise ValueError("UNSUPPORTED_A220_MODEL_SCOPE")
        role, kind = CONTROL_PROTOCOLS[control]
        out.append(HypotheticalSecurityTest(
            attack_id=attack_id, control_id=control, model_scope=model_scope,
            nominal_source_role=role, challenge_kind=kind,
            expected_safe_behavior=EXPECTED_SAFE_BEHAVIOR[attack_id],
        ))
    return tuple(out)


def preflight_security_test_catalog(
    candidate: Any,
    *,
    a223_note: Any,
    a222_matrix: Any,
    expected_owner_id: Any,
    expected_tenant_id: Any,
    expected_workspace_id: Any,
) -> SecurityCatalogPreflight:
    """Validate only a paper/lab catalog linked to an unapproved A223 note."""
    if type(candidate) is str:
        try:
            candidate = decode_candidate_json(candidate)
        except (ValueError, TypeError):
            return _out("AMBIGUOUS_OR_OVERSIZED_CATALOG_JSON")
    if type(candidate) is not dict or set(candidate) != _FIELDS:
        return _out("CATALOG_ENVELOPE_NOT_EXACT")
    if candidate["schema"] != SCHEMA:
        return _out("CATALOG_SCHEMA_UNSUPPORTED")

    scope = {
        "owner_id": expected_owner_id,
        "tenant_id": expected_tenant_id,
        "workspace_id": expected_workspace_id,
    }
    if any(type(v) is not str or _TOKEN.fullmatch(v) is None for v in scope.values()):
        return _out("INVALID_EXPECTED_SCOPE")
    if any(type(candidate[k]) is not str or candidate[k] != v for k, v in scope.items()):
        return _out("CATALOG_SCOPE_MISMATCH")
    if candidate["research_priority"] != PRIORITY:
        return _out("SECURITY_FIRST_PRIORITY_REQUIRED")
    if candidate["plan_state"] != "HYPOTHETICAL_TESTS_NOT_EXECUTED":
        return _out("LAB_PLAN_CANNOT_ASSERT_TEST_EXECUTION")
    if candidate["owner_approval_state"] != "NOT_REQUESTED":
        return _out("HOST_CANNOT_ASSERT_OWNER_APPROVAL")
    if candidate["selected_model"] != "NONE":
        return _out("CUSTODY_MODEL_NOT_SELECTED")
    if candidate["provider_selection_state"] != "NO_PROVIDER_SELECTED":
        return _out("PROVIDER_SELECTION_NOT_AUTHORIZED")
    if candidate["budget_approval_state"] != "NOT_REQUESTED":
        return _out("SPENDING_NOT_AUTHORIZED")
    if type(candidate["external_p0_homologated"]) is not int or candidate["external_p0_homologated"] != 0:
        return _out("FORGED_EXTERNAL_P0_HOMOLOGATION")
    if candidate["uncertain_resend_policy"] != "ZERO_AUTO_RESEND":
        return _out("UNCERTAIN_MUST_FAIL_CLOSED")

    models = candidate["models_under_review"]
    if (type(models) is not list or len(models) != 2
            or any(type(m) is not str for m in models)
            or set(models) != {OFFLINE, KMS_HSM}):
        return _out("BOTH_MODELS_MUST_REMAIN_UNSELECTED")

    baseline = preflight_owner_security_priority(
        a223_note, a222_matrix=a222_matrix,
        expected_owner_id=expected_owner_id,
        expected_tenant_id=expected_tenant_id,
        expected_workspace_id=expected_workspace_id,
    )
    if not baseline.research_form_valid or baseline.owner_signoff_valid:
        return _out("A223_UNVERIFIED_PRIORITY_REQUIRED")
    digest = candidate["a223_note_digest"]
    if type(digest) is not str or _HEX.fullmatch(digest) is None or digest != baseline.research_digest:
        return _out("A223_LOCAL_DIGEST_MISMATCH")

    try:
        specs = {row.attack_id: row for row in hypothetical_security_test_rows()}
    except ValueError:
        return _out("A220_A221_A224_CATALOG_DRIFT")
    rows = candidate["test_catalog"]
    if type(rows) is not list or len(rows) != len(specs):
        return _out("SECURITY_TEST_COVERAGE_INCOMPLETE")
    seen: set[str] = set()
    for row in rows:
        if type(row) is not dict or set(row) != _ROW_FIELDS:
            return _out("SECURITY_TEST_ENVELOPE_NOT_EXACT")
        attack_id = row["attack_id"]
        if type(attack_id) is not str or attack_id not in specs:
            return _out("UNKNOWN_SECURITY_ATTACK")
        if attack_id in seen:
            return _out("DUPLICATE_SECURITY_ATTACK")
        seen.add(attack_id)
        spec = specs[attack_id]
        expected = {
            "control_id": spec.control_id,
            "model_scope": spec.model_scope,
            "nominal_source_role": spec.nominal_source_role,
            "challenge_kind": spec.challenge_kind,
            "expected_safe_behavior": spec.expected_safe_behavior,
        }
        if any(type(row[k]) is not str or row[k] != v for k, v in expected.items()):
            return _out("A221_PROTOCOL_OR_MODEL_SCOPE_MISMATCH")
        states = {
            "execution_state": "NOT_EXECUTED",
            "external_proof_state": "NOT_OBTAINED",
            "independent_review_state": "UNASSIGNED",
            "remediation_state": "NOT_STARTED",
        }
        if any(type(row[k]) is not str or row[k] != v for k, v in states.items()):
            return _out("UNEXECUTED_TEST_CANNOT_CLAIM_PROOF")

    canonical = dict(candidate)
    canonical["models_under_review"] = sorted(models)
    canonical["test_catalog"] = sorted(
        (dict(row) for row in rows), key=lambda row: row["attack_id"],
    )
    encoded = json.dumps(
        canonical, ensure_ascii=False, allow_nan=False,
        sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")
    return _out(
        "13_HYPOTHETICAL_SECURITY_TESTS_DEFINED_NONE_EXECUTED_HARD_NO_GO",
        valid=True, digest=sha256(encoded).hexdigest(),
    )


__all__ = [
    "SCHEMA", "EXPECTED_SAFE_BEHAVIOR", "HypotheticalSecurityTest",
    "SecurityCatalogPreflight", "hypothetical_security_test_rows",
    "preflight_security_test_catalog",
]
