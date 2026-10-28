"""A220: hypothetical root-attack boundary simulator, no external authority.

No device, provider API, IAM, signing, secrets, receipts or network I/O.
Every protection is only a HOST-SUPPLIED ASSUMPTION and proves nothing.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import re
from typing import Any

from atlasquant_aion_external_evidence_intake import decode_candidate_json


SCHEMA = "ATLASQUANT_AION_ROOT_ATTACK_SIMULATION_UNTRUSTED_V0"
OFFLINE = "OWNER_OFFLINE_ROOT"
KMS_HSM = "SEPARATE_DOMAIN_KMS_HSM"
MODELS = frozenset({OFFLINE, KMS_HSM})
_SCOPE = ("owner_id", "tenant_id", "workspace_id")
_ENVELOPE = frozenset({
    "schema", *_SCOPE, "model_id", "attack_id",
    "attacker_origin", "assumptions_state", "owner_approval_state",
    "external_p0_homologated", "controls",
})
_CONTROLS = frozenset({
    "offline_private_material_outside_host",
    "offline_custodian_unreachable_by_host",
    "kms_host_sign_denied",
    "kms_host_policy_write_denied",
    "kms_host_role_assumption_denied",
    "approval_outside_host",
    "signer_admin_approver_roles_separate",
    "nonce_checkpoint_outside_host",
    "revocation_checkpoint_outside_host",
    "audit_witness_outside_host",
    "outage_fails_closed_no_resend",
    "provider_receipt_not_substituted_by_root_signature",
    "scope_isolated",
})
_ALL = MODELS
# Scenario --> (applicable models, assumption under attack).
SCENARIOS = {
    "HOST_READS_OFFLINE_PRIVATE_MATERIAL": (frozenset({OFFLINE}), "offline_private_material_outside_host"),
    "HOST_IMPERSONATES_OFFLINE_CUSTODIAN": (frozenset({OFFLINE}), "offline_custodian_unreachable_by_host"),
    "HOST_INVOKES_KMS_SIGN": (frozenset({KMS_HSM}), "kms_host_sign_denied"),
    "HOST_CHANGES_KMS_KEY_POLICY": (frozenset({KMS_HSM}), "kms_host_policy_write_denied"),
    "HOST_ASSUMES_SIGNER_ROLE": (frozenset({KMS_HSM}), "kms_host_role_assumption_denied"),
    "HOST_FORGES_OWNER_APPROVAL": (_ALL, "approval_outside_host"),
    "ADMIN_SIGNER_APPROVER_COLLUSION": (_ALL, "signer_admin_approver_roles_separate"),
    "HOST_REPLAYS_OLD_NONCE": (_ALL, "nonce_checkpoint_outside_host"),
    "HOST_REUSES_REVOKED_ROOT": (_ALL, "revocation_checkpoint_outside_host"),
    "HOST_ERASES_AUDIT_TRAIL": (_ALL, "audit_witness_outside_host"),
    "OUTAGE_FORCES_AUTOMATIC_RESEND": (_ALL, "outage_fails_closed_no_resend"),
    "ROOT_SIGNATURE_FORGES_BROKER_EFFECT": (_ALL, "provider_receipt_not_substituted_by_root_signature"),
    "HOST_SUBSTITUTES_OTHER_TENANT": (_ALL, "scope_isolated"),
}
_TOKEN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


@dataclass(frozen=True)
class SyntheticAttackResult:
    scenario_applicable: bool
    assumption_says_blocked: bool
    synthetic_gap_detected: bool
    independently_verified: bool
    owner_approval_valid: bool
    external_p0_homologated: int
    may_generate_key: bool
    may_sign: bool
    may_provision: bool
    may_connect: bool
    may_confirm: bool
    may_auto_resend: bool
    code: str
    attacked_control: str
    assumption_digest: str


def _deny(code: str) -> SyntheticAttackResult:
    return SyntheticAttackResult(
        scenario_applicable=False, assumption_says_blocked=False,
        synthetic_gap_detected=False, independently_verified=False,
        owner_approval_valid=False, external_p0_homologated=0,
        may_generate_key=False, may_sign=False, may_provision=False,
        may_connect=False, may_confirm=False, may_auto_resend=False,
        code=code, attacked_control="", assumption_digest="",
    )


def simulate_untrusted_root_attack(
    candidate: Any,
    *,
    expected_owner_id: Any,
    expected_tenant_id: Any,
    expected_workspace_id: Any,
) -> SyntheticAttackResult:
    """Compares one synthetic assumption with one hostile scenario.

    A 'blocked' result asserts only that the user-provided assumption was True;
    it is not proof that IAM, key custody, approvers or logs really enforce it.
    All results always forbid real operations and financial confirmation.
    """
    if type(candidate) is str:
        try:
            candidate = decode_candidate_json(candidate)
        except (TypeError, ValueError):
            return _deny("AMBIGUOUS_OR_OVERSIZED_ATTACK_JSON")
    if type(candidate) is not dict or set(candidate) != _ENVELOPE:
        return _deny("ATTACK_ENVELOPE_NOT_EXACT")
    if candidate["schema"] != SCHEMA:
        return _deny("ATTACK_SCHEMA_UNSUPPORTED")

    scope = dict(zip(_SCOPE, (expected_owner_id, expected_tenant_id, expected_workspace_id)))
    if any(type(v) is not str or _TOKEN.fullmatch(v) is None for v in scope.values()):
        return _deny("INVALID_EXPECTED_SCOPE")
    if any(type(candidate[k]) is not str or candidate[k] != v for k, v in scope.items()):
        return _deny("SYNTHETIC_SCOPE_MISMATCH")

    if candidate["model_id"] not in MODELS or type(candidate["model_id"]) is not str:
        return _deny("UNKNOWN_ROOT_MODEL")
    attack_id = candidate["attack_id"]
    if type(attack_id) is not str or attack_id not in SCENARIOS:
        return _deny("UNKNOWN_ATTACK_SCENARIO")
    applicable, control = SCENARIOS[attack_id]
    if candidate["model_id"] not in applicable:
        return _deny("SCENARIO_ROOT_MODEL_MISMATCH")
    if candidate["attacker_origin"] != "HOST_CONTROLLED":
        return _deny("ATTACKER_ORIGIN_NOT_HOST_BOUND")
    if candidate["assumptions_state"] != "FICTIONAL_UNVERIFIED_ONLY":
        return _deny("UNTRUSTED_ASSUMPTIONS_CANNOT_BECOME_FACT")
    if candidate["owner_approval_state"] != "NOT_REQUESTED":
        return _deny("HOST_ASSERTED_OWNER_APPROVAL")
    if type(candidate["external_p0_homologated"]) is not int or candidate["external_p0_homologated"] != 0:
        return _deny("FALSE_EXTERNAL_P0_CLAIM")

    controls = candidate["controls"]
    if type(controls) is not dict or set(controls) != _CONTROLS:
        return _deny("SYNTHETIC_CONTROL_MATRIX_NOT_EXACT")
    if any(type(value) is not bool for value in controls.values()):
        return _deny("SYNTHETIC_CONTROL_MUST_BE_BOOLEAN")

    # The actor (host) controls this entire test input, so even all True is
    # neither independent proof nor authorization.
    assumed_block = controls[control]
    digest = sha256(json.dumps(
        candidate, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, allow_nan=False,
    ).encode("utf-8")).hexdigest()
    return SyntheticAttackResult(
        scenario_applicable=True,
        assumption_says_blocked=assumed_block,
        synthetic_gap_detected=not assumed_block,
        independently_verified=False, owner_approval_valid=False,
        external_p0_homologated=0, may_generate_key=False,
        may_sign=False, may_provision=False, may_connect=False,
        may_confirm=False, may_auto_resend=False,
        code=("SYNTHETIC_ASSUMPTION_BLOCKS_SCENARIO_NOT_PROOF" if assumed_block
              else "SYNTHETIC_ATTACK_REVEALS_ASSUMED_CONTROL_GAP"),
        attacked_control=control, assumption_digest=digest,
    )


__all__ = [
    "SCHEMA", "OFFLINE", "KMS_HSM", "MODELS", "SCENARIOS",
    "SyntheticAttackResult", "simulate_untrusted_root_attack",
]
