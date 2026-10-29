"""A223 LAB: record a conversational research priority, never an authorization.

The person chose option 1 (security/control). This is an unverified preference
note from a conversation, NOT identity proof, signoff, a custody decision,
independent evidence, a provider instruction, or an operational capability.
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
from labs.a222_owner_acceptance_matrix import preflight_owner_acceptance_matrix


SCHEMA = "ATLASQUANT_AION_OWNER_SECURITY_PRIORITY_RESEARCH_V0"
PRIORITY = "SECURITY_AND_MAX_CONTROL"
SOURCE = "CONVERSATION_OPTION_1_IDENTITY_UNVERIFIED"
_TOKEN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_HEX = re.compile(r"^[0-9a-f]{64}$")
_FIELDS = frozenset({
    "schema", "owner_id", "tenant_id", "workspace_id",
    "research_priority", "preference_source", "preference_status",
    "a222_matrix_digest", "models_under_review", "research_controls",
    "decision_state", "owner_signoff_state", "chosen_model",
    "provider_selection_state", "budget_approval_state",
    "external_p0_homologated", "uncertain_resend_policy",
})
_CONTROL_FIELDS = frozenset({
    "control_id", "research_question_state", "external_evidence_state",
    "acceptance_state",
})


@dataclass(frozen=True)
class SecurityPriorityPreflight:
    research_form_valid: bool
    conversational_security_priority_noted: bool
    identity_verified: bool
    owner_signoff_valid: bool
    independent_evidence_verified: bool
    root_model_selected: bool
    external_p0_homologated: int
    may_select_model: bool
    may_commit_budget: bool
    may_contact_provider: bool
    may_provision: bool
    may_generate_key: bool
    may_sign: bool
    may_connect: bool
    may_confirm: bool
    may_auto_resend: bool
    code: str
    research_digest: str
    unresolved_controls: tuple[str, ...]


def _result(code: str, *, valid: bool = False, digest: str = "") -> SecurityPriorityPreflight:
    return SecurityPriorityPreflight(
        research_form_valid=valid,
        conversational_security_priority_noted=valid,
        identity_verified=False, owner_signoff_valid=False,
        independent_evidence_verified=False, root_model_selected=False,
        external_p0_homologated=0, may_select_model=False,
        may_commit_budget=False, may_contact_provider=False,
        may_provision=False, may_generate_key=False,
        may_sign=False, may_connect=False, may_confirm=False,
        may_auto_resend=False, code=code, research_digest=digest,
        unresolved_controls=tuple(sorted(CONTROL_PROTOCOLS)) if valid else (),
    )


def preflight_owner_security_priority(
    candidate: Any,
    *,
    a222_matrix: Any,
    expected_owner_id: Any,
    expected_tenant_id: Any,
    expected_workspace_id: Any,
) -> SecurityPriorityPreflight:
    """Check a research-only preference note against an unfilled A222 matrix.

    A valid note merely records the conversation's option 1. Input can be
    entirely forged by a host; there is no external identity or authority.
    """
    if type(candidate) is str:
        try:
            candidate = decode_candidate_json(candidate)
        except (ValueError, TypeError):
            return _result("AMBIGUOUS_OR_OVERSIZED_PRIORITY_JSON")
    if type(candidate) is not dict or set(candidate) != _FIELDS:
        return _result("PRIORITY_ENVELOPE_NOT_EXACT")
    if candidate["schema"] != SCHEMA:
        return _result("PRIORITY_SCHEMA_UNSUPPORTED")

    scope = {
        "owner_id": expected_owner_id,
        "tenant_id": expected_tenant_id,
        "workspace_id": expected_workspace_id,
    }
    if any(type(v) is not str or _TOKEN.fullmatch(v) is None for v in scope.values()):
        return _result("INVALID_EXPECTED_SCOPE")
    if any(type(candidate[k]) is not str or candidate[k] != v for k, v in scope.items()):
        return _result("PRIORITY_SCOPE_MISMATCH")

    if candidate["research_priority"] != PRIORITY:
        return _result("UNRECOGNIZED_CONVERSATIONAL_PRIORITY")
    if candidate["preference_source"] != SOURCE:
        return _result("HOST_CANNOT_ASSERT_AUTHENTICATED_PREFERENCE")
    if candidate["preference_status"] != "NOTED_NOT_AUTHENTICATED":
        return _result("PREFERENCE_NOT_OWNER_SIGNOFF")
    if candidate["decision_state"] != "BOTH_MODELS_UNDER_RESEARCH":
        return _result("CUSTODY_DECISION_NOT_AUTHORIZED")
    if candidate["owner_signoff_state"] != "NOT_REQUESTED":
        return _result("HOST_CANNOT_SIGN_FOR_OWNER")
    if candidate["chosen_model"] != "NONE":
        return _result("CUSTODY_MODEL_CHOICE_NOT_AUTHORIZED")
    if candidate["provider_selection_state"] != "NO_PROVIDER_SELECTED":
        return _result("PROVIDER_SELECTION_NOT_AUTHORIZED")
    if candidate["budget_approval_state"] != "NOT_REQUESTED":
        return _result("SPENDING_NOT_AUTHORIZED")
    if type(candidate["external_p0_homologated"]) is not int or candidate["external_p0_homologated"] != 0:
        return _result("FALSE_EXTERNAL_P0_HOMOLOGATION")
    if candidate["uncertain_resend_policy"] != "ZERO_AUTO_RESEND":
        return _result("UNCERTAIN_MUST_FAIL_CLOSED")

    models = candidate["models_under_review"]
    if (type(models) is not list or len(models) != 2
            or any(type(m) is not str for m in models)
            or set(models) != {OFFLINE, KMS_HSM}):
        return _result("BOTH_UNSELECTED_MODELS_REQUIRED")

    baseline = preflight_owner_acceptance_matrix(
        a222_matrix, expected_owner_id=expected_owner_id,
        expected_tenant_id=expected_tenant_id,
        expected_workspace_id=expected_workspace_id,
    )
    if not baseline.matrix_complete or baseline.owner_signoff_valid:
        return _result("A222_UNFILLED_MATRIX_REQUIRED")
    digest = candidate["a222_matrix_digest"]
    if type(digest) is not str or _HEX.fullmatch(digest) is None or digest != baseline.draft_digest:
        return _result("A222_MATRIX_DIGEST_MISMATCH")

    controls = candidate["research_controls"]
    if type(controls) is not list or len(controls) != len(CONTROL_PROTOCOLS):
        return _result("SECURITY_CONTROL_QUESTIONS_INCOMPLETE")
    seen: set[str] = set()
    for item in controls:
        if type(item) is not dict or set(item) != _CONTROL_FIELDS:
            return _result("SECURITY_CONTROL_ENVELOPE_NOT_EXACT")
        control = item["control_id"]
        if type(control) is not str or control not in CONTROL_PROTOCOLS:
            return _result("UNKNOWN_SECURITY_CONTROL")
        if control in seen:
            return _result("DUPLICATE_SECURITY_CONTROL")
        seen.add(control)
        if (item["research_question_state"] != "OPEN"
                or item["external_evidence_state"] != "NOT_OBTAINED"
                or item["acceptance_state"] != "NOT_REQUESTED"):
            return _result("UNVERIFIED_CONTROL_CANNOT_BE_PASSED")

    # Stable checksum only: it is neither a signature nor identity evidence.
    canonical = dict(candidate)
    canonical["models_under_review"] = sorted(models)
    canonical["research_controls"] = sorted(
        (dict(c) for c in controls), key=lambda c: c["control_id"],
    )
    encoded = json.dumps(
        canonical, ensure_ascii=False, sort_keys=True,
        separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")
    return _result(
        "SECURITY_PRIORITY_NOTED_RESEARCH_ONLY_13_CONTROLS_OPEN_HARD_NO_GO",
        valid=True, digest=sha256(encoded).hexdigest(),
    )


__all__ = [
    "SCHEMA", "PRIORITY", "SOURCE", "SecurityPriorityPreflight",
    "preflight_owner_security_priority",
]
