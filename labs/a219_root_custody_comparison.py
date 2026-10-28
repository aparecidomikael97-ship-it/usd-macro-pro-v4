"""A219 LAB: root-custody research comparison, NOT a key or vendor integration.

This pure module has no cloud, hardware, cryptographic signing or financial I/O.
Hypothetical threats remain OPEN, not proof of security or independence.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import re
from typing import Any

from atlasquant_aion_external_evidence_intake import decode_candidate_json


SCHEMA = "ATLASQUANT_AION_ROOT_CUSTODY_COMPARISON_RESEARCH_V0"
MODELS = frozenset({"OWNER_OFFLINE_ROOT", "SEPARATE_DOMAIN_KMS_HSM"})
_FIELDS = frozenset({
    "schema", "owner_id", "tenant_id", "workspace_id",
    "decision_state", "owner_approval_state", "chosen_model",
    "p0_external_homologated", "models",
})
_MODEL_FIELDS = frozenset({
    "model_id", "identity_state", "control_domain",
    "key_material_state", "signing_policy_state", "authorization_separation_state",
    "audit_state", "revocation_state", "recovery_state", "availability_state",
    "cost_state", "research_state",
})
_REQUIRED_STATES = {
    "identity_state": "UNVERIFIED",
    "control_domain": "UNASSIGNED",
    "key_material_state": "NOT_PROVISIONED",
    "signing_policy_state": "NOT_REVIEWED",
    "authorization_separation_state": "NOT_DEMONSTRATED",
    "audit_state": "NOT_OBTAINED",
    "revocation_state": "UNTESTED",
    "recovery_state": "UNTESTED",
    "availability_state": "UNTESTED",
    "cost_state": "NOT_QUOTED",
    "research_state": "HYPOTHETICAL_ONLY",
}
_TOKEN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")

# Scenarios are QUESTIONS TO PROVE, never actual mitigations or attestation.
# (offline question, KMS/HSM question). Both remain unverified.
THREAT_QUESTIONS = {
    "HOST_COMPROMISE": (
        "Is the offline key and every seed/backup unreachable by the host?",
        "Can the compromised host invoke Sign, assume an approving role, or edit policy?",
    ),
    "SIGNER_ADMIN_COLLUSION": (
        "Are custody, ceremony authorization and witness roles separated?",
        "Are administrator, signer and approver roles separated and independently audited?",
    ),
    "ROOT_KEY_LOSS": (
        "Is dual-controlled backup and loss recovery demonstrated without host secrets?",
        "Is key loss/destruction recovery documented without granting host-admin access?",
    ),
    "OUTAGE_OR_CUSTODIAN_ABSENCE": (
        "Does absent human custody fail closed without bypass or auto resend?",
        "Does cloud/provider outage fail closed without a local or cached signing bypass?",
    ),
    "REVOKED_KEY_REPLAY": (
        "Is revocation and prior trust checkpoint maintained outside the host?",
        "Are key disablement/revocation and prior checkpoints verified outside the cloud role?",
    ),
    "AUDIT_ROLLBACK_OR_FORK": (
        "Can a separate observer detect an altered ceremony history?",
        "Can an external observer detect edited provider/key audit logs and forks?",
    ),
    "UNVERIFIED_BROKER_RECEIPT": (
        "Does offline signature remain separate from proof of broker final effect?",
        "Does HSM signature remain separate from proof of broker final effect?",
    ),
    "LIFECYCLE_COST_AND_LIABILITY": (
        "Who owns secure media, key ceremonies, backup and incident responsibilities?",
        "Who owns tenancy, IAM, billing, outages, audit export and incident response?",
    ),
}


@dataclass(frozen=True)
class CustodyComparisonPreflight:
    comparison_complete: bool
    independent_root_verified: bool
    owner_choice_approved: bool
    external_p0_homologated: int
    may_generate_or_import_key: bool
    may_sign: bool
    may_provision: bool
    may_connect: bool
    may_confirm: bool
    code: str
    comparison_digest: str
    unresolved_scenarios: tuple[str, ...]


@dataclass(frozen=True)
class HypotheticalThreatComparison:
    scenario: str
    offline_question: str
    kms_hsm_question: str
    evidence_state: str
    may_activate: bool


def _deny(code: str) -> CustodyComparisonPreflight:
    return CustodyComparisonPreflight(
        comparison_complete=False, independent_root_verified=False,
        owner_choice_approved=False, external_p0_homologated=0,
        may_generate_or_import_key=False, may_sign=False,
        may_provision=False, may_connect=False, may_confirm=False,
        code=code, comparison_digest="", unresolved_scenarios=(),
    )


def hypothetical_threat_comparison(scenario: str) -> HypotheticalThreatComparison:
    """Deterministic research questions. Never simulate an attested pass."""
    if type(scenario) is not str or scenario not in THREAT_QUESTIONS:
        raise ValueError("UNSUPPORTED_HYPOTHETICAL_SCENARIO")
    offline, kms = THREAT_QUESTIONS[scenario]
    return HypotheticalThreatComparison(
        scenario=scenario, offline_question=offline,
        kms_hsm_question=kms, evidence_state="NOT_OBTAINED",
        may_activate=False,
    )


def preflight_root_custody_comparison(
    candidate: Any,
    *,
    expected_owner_id: Any,
    expected_tenant_id: Any,
    expected_workspace_id: Any,
) -> CustodyComparisonPreflight:
    """Accept only both neutral research candidates; never approve either."""
    if type(candidate) is str:
        try:
            candidate = decode_candidate_json(candidate)
        except (ValueError, TypeError):
            return _deny("AMBIGUOUS_OR_OVERSIZED_COMPARISON_JSON")
    if type(candidate) is not dict or set(candidate) != _FIELDS:
        return _deny("COMPARISON_ENVELOPE_NOT_EXACT")
    if candidate["schema"] != SCHEMA:
        return _deny("COMPARISON_SCHEMA_UNSUPPORTED")
    scope = {
        "owner_id": expected_owner_id,
        "tenant_id": expected_tenant_id,
        "workspace_id": expected_workspace_id,
    }
    if any(type(v) is not str or _TOKEN.fullmatch(v) is None for v in scope.values()):
        return _deny("INVALID_EXPECTED_SCOPE")
    if any(type(candidate[k]) is not str or candidate[k] != v for k, v in scope.items()):
        return _deny("COMPARISON_SCOPE_MISMATCH")
    if candidate["decision_state"] != "AWAITING_OWNER_COMPARISON_REVIEW":
        return _deny("PREMATURE_MODEL_DECISION")
    if candidate["owner_approval_state"] != "NOT_REQUESTED":
        return _deny("HOST_ASSERTED_OWNER_APPROVAL")
    if candidate["chosen_model"] != "NONE":
        return _deny("PREMATURE_ROOT_CUSTODY_SELECTION")
    if type(candidate["p0_external_homologated"]) is not int or candidate["p0_external_homologated"] != 0:
        return _deny("FORGED_EXTERNAL_P0_HOMOLOGATION")

    models = candidate["models"]
    if type(models) is not list or len(models) != len(MODELS):
        return _deny("RESEARCH_MODELS_INCOMPLETE")
    seen: set[str] = set()
    for model in models:
        if type(model) is not dict or set(model) != _MODEL_FIELDS:
            return _deny("ROOT_MODEL_ENVELOPE_NOT_EXACT")
        model_id = model["model_id"]
        if type(model_id) is not str or model_id not in MODELS:
            return _deny("UNSUPPORTED_ROOT_MODEL")
        if model_id in seen:
            return _deny("DUPLICATE_ROOT_MODEL")
        seen.add(model_id)
        for field, expected in _REQUIRED_STATES.items():
            if model[field] != expected or type(model[field]) is not str:
                return _deny("ROOT_RESEARCH_STATE_CANNOT_CLAIM_PROOF")
    if seen != MODELS:
        return _deny("ROOT_MODEL_COVERAGE_MISMATCH")

    # Canonical comparison is order-neutral and binds the owner/tenant/workspace;
    # it is a research checksum only, not a signature or external attestation.
    canonical = dict(candidate)
    canonical["models"] = sorted((dict(m) for m in models), key=lambda m: m["model_id"])
    encoded = json.dumps(
        canonical, sort_keys=True, ensure_ascii=False,
        allow_nan=False, separators=(",", ":"),
    ).encode("utf-8")
    return CustodyComparisonPreflight(
        comparison_complete=True, independent_root_verified=False,
        owner_choice_approved=False, external_p0_homologated=0,
        may_generate_or_import_key=False, may_sign=False,
        may_provision=False, may_connect=False, may_confirm=False,
        code="BOTH_MODELS_RESEARCHED_ALL_EXTERNAL_PROOFS_PENDING",
        comparison_digest=sha256(encoded).hexdigest(),
        unresolved_scenarios=tuple(sorted(THREAT_QUESTIONS)),
    )


__all__ = [
    "SCHEMA", "MODELS", "THREAT_QUESTIONS",
    "CustodyComparisonPreflight", "HypotheticalThreatComparison",
    "hypothetical_threat_comparison", "preflight_root_custody_comparison",
]
