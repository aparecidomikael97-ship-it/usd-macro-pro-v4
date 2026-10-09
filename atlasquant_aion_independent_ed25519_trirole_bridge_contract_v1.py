"""AION three-role custody and host-bridge PROTOCOL DESIGN V1.

PREPARE ONLY. No native Windows calls, no keys, no cryptographic signatures,
no verification of hardware or HUMAN_OWNER, no network, no storage writes.

Three distinct roles are required:
  HUMAN_OWNER_ED25519 (explicit owner policy approval),
  COLLECTOR_ED25519 (independent collector witness),
  HOST_ECDSA_P256 (optional host-binding proof, independently attested).

The THIRD role may never satisfy the first or second signature requirement.
A self-described key fingerprint, custody proposal or unsigned transcript
is not identity proof, signature proof, TPM evidence or deploy authority.
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any

SCHEMA = "AION_INDEPENDENT_ED25519_TRIROLE_BRIDGE_DESIGN_V1"
BINDING_SCHEMA = "AION_TRIROLE_UNSIGNED_BINDING_TRANSCRIPTS_V1"
PURPOSE = "OWNER_COLLECTOR_HOST_BINDING_PROPOSAL_NOT_AUTHORIZATION"
_ROLES = (
    "HUMAN_OWNER_ED25519", "COLLECTOR_ED25519", "HOST_ECDSA_P256",
)
_ALGORITHMS = {
    "HUMAN_OWNER_ED25519": "Ed25519",
    "COLLECTOR_ED25519": "Ed25519",
    "HOST_ECDSA_P256": "ECDSA_P256_SHA256",
}
_DOMAINS = {
    "HUMAN_OWNER_ED25519": "AION_OWNER_APPROVAL_V1",
    "COLLECTOR_ED25519": "AION_COLLECTOR_INDEPENDENT_WITNESS_V1",
    "HOST_ECDSA_P256": "AION_HOST_BINDING_NON_AUTHORITY_V1",
}
_HEX = re.compile(r"sha256:[0-9a-f]{64}\Z")
_NONCE = re.compile(r"[0-9a-f]{64}\Z")
_IDENTIFIER = re.compile(r"[A-Za-z0-9_.-]{8,72}\Z")
_PLAN_FIELDS = frozenset({
    "schema", "owner", "collector", "host",
    "collector_binary_sha256", "policy_sha256",
    "policy_generation", "estimated_monthly_brl",
})
_KEY_ROLE_FIELDS = frozenset({
    "role", "algorithm", "public_key_sha256", "custody_boundary",
    "custodian_id", "verification_state",
})
_OWNER_BOUNDARY = frozenset({
    "OWNER_HELD_INDEPENDENT_DEVICE_CANDIDATE",
    "INDEPENDENT_REMOTE_TRUST_DOMAIN_CANDIDATE",
})
_COLLECTOR_BOUNDARY = frozenset({
    "SEPARATE_COLLECTOR_SIGNER_DOMAIN_CANDIDATE",
    "INDEPENDENT_COLLECTOR_REMOTE_CUSTODIAN_CANDIDATE",
})
_HOST_BOUNDARY = "WINDOWS_PLATFORM_TPM_P256_CANDIDATE_UNATTESTED"
_UNVERIFIED = "NOT_CRYPTOGRAPHICALLY_VERIFIED"
_FALSE_GATES = {
    "ed25519_owner_private_key_custody_verified": False,
    "ed25519_collector_private_key_custody_verified": False,
    "owner_signature_cryptographically_verified": False,
    "collector_signature_cryptographically_verified": False,
    "signers_independently_attested": False,
    "custodian_independence_cryptographically_verified": False,
    "p256_private_key_present": False,
    "p256_tpm_origin_independently_verified": False,
    "p256_nonexportability_independently_verified": False,
    "p256_host_signature_cryptographically_verified": False,
    "tpm_ek_ak_attestation_verified": False,
    "rsa_enterprise_ca_certificate_proves_p256": False,
    "durable_nonce_replay_prevention_verified": False,
    "durable_monotonic_policy_generation_verified": False,
    "revocation_and_rotation_verified": False,
    "protected_trust_anchor_verified": False,
    "hardware_antirollback_verified": False,
    "physical_sandbox_12_of_12_verified": False,
    "network_deny_16_of_16_verified": False,
    "machine_identity_verified": False,
    "key_creation_authorized": False,
    "key_enrollment_authorized": False,
    "collector_launch_authorized": False,
    "installer_authorized": False,
    "build_authorized": False,
    "deploy_authorized": False,
    "safe_to_resume": False,
    "host_security_state_modified": False,
}
_EVIDENCE_STEPS = (
    "OWNER_ED25519_INDEPENDENT_CUSTODY_PROOF",
    "COLLECTOR_ED25519_INDEPENDENT_CUSTODY_PROOF",
    "OWNER_AND_COLLECTOR_SIGNATURE_VERIFICATION",
    "P256_HOST_KEY_ORIGIN_AND_NONEXPORTABILITY_ATTESTATION",
    "P256_HOST_SIGNATURE_VERIFICATION_WITH_PINNED_KEY",
    "INDEPENDENT_HOST_ATTESTATION_VERIFIER_AND_TRUST_ANCHOR",
    "DURABLE_NONCE_ISSUANCE_AND_SPENT_NONCE_LEDGER",
    "DURABLE_POLICY_GENERATION_AND_ANTIROLLBACK",
    "REVOKE_ROTATE_COMPROMISE_RECOVERY_DRILLS",
    "OWNER_SIGNED_SEPARATE_KEY_PROVISIONING_DECISION",
    "PHYSICAL_SANDBOX_12_OF_12",
    "PHYSICAL_NETWORK_DENY_16_OF_16",
)


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "state": "BLOCKED",
        "reason": reason,
        "candidate": None,
        "key_roles": list(_ROLES),
        "evidence_required": list(_EVIDENCE_STEPS),
        "budget_is_unverified_estimate": True,
        "independent_hardware_attestation_design_required": True,
        "separate_key_provisioning_owner_approval_required": True,
        **_FALSE_GATES,
    }


def _valid_role(item: Any, *, role: str) -> bool:
    if type(item) is not dict or set(item) != _KEY_ROLE_FIELDS:
        return False
    if (item.get("role") != role
        or item.get("algorithm") != _ALGORITHMS[role]
        or type(item.get("public_key_sha256")) is not str
        or not _HEX.fullmatch(item["public_key_sha256"])
        or type(item.get("custodian_id")) is not str
        or not _IDENTIFIER.fullmatch(item["custodian_id"])
        or item.get("verification_state") != _UNVERIFIED):
        return False
    boundary = item.get("custody_boundary")
    if role == "HUMAN_OWNER_ED25519":
        return type(boundary) is str and boundary in _OWNER_BOUNDARY
    if role == "COLLECTOR_ED25519":
        return type(boundary) is str and boundary in _COLLECTOR_BOUNDARY
    return type(boundary) is str and boundary == _HOST_BOUNDARY


def review_three_role_custody_design(proposal: Any) -> dict[str, Any]:
    """Require strict separation but NEVER accept self-attested actual proof."""
    out = _blocked("INVALID_OR_UNVERIFIED_CUSTODY_PROPOSAL")
    if type(proposal) is not dict or set(proposal) != _PLAN_FIELDS:
        return out
    if proposal["schema"] != SCHEMA:
        return out
    for name, role in (("owner", _ROLES[0]), ("collector", _ROLES[1]),
                       ("host", _ROLES[2])):
        if not _valid_role(proposal[name], role=role):
            return out
    fingerprints = [proposal[k]["public_key_sha256"]
                    for k in ("owner", "collector", "host")]
    custodians = [proposal[k]["custodian_id"]
                  for k in ("owner", "collector", "host")]
    if len(set(fingerprints)) != 3 or len(set(custodians)) != 3:
        return out
    if (type(proposal["collector_binary_sha256"]) is not str
        or not _HEX.fullmatch(proposal["collector_binary_sha256"])
        or type(proposal["policy_sha256"]) is not str
        or not _HEX.fullmatch(proposal["policy_sha256"])
        or type(proposal["policy_generation"]) is not int
        or not 0 <= proposal["policy_generation"] < 2**32
        or type(proposal["estimated_monthly_brl"]) is not int
        or not 0 <= proposal["estimated_monthly_brl"] <= 200):
        return out
    out["state"] = "THREE_ROLE_CUSTODY_DESIGN_CANDIDATE_UNTRUSTED"
    out["reason"] = ""
    out["candidate"] = "INDEPENDENT_ED25519_OWNER_AND_COLLECTOR_WITH_UNATTESTED_P256"
    return out


def build_unsigned_three_role_challenge(proposal: Any, nonce: Any) -> dict[str, Any]:
    """Build three separate message hashes, NOT signatures/crypto verification.

    A real verifier MUST pin public keys and prove two independent Ed25519
    signatures, then independently verify a separately attested P256 host
    key/signature; this module explicitly does NONE of these operations.
    """
    out = {
        "schema": BINDING_SCHEMA,
        "state": "BLOCKED",
        "reason": "CUSTODY_PROPOSAL_OR_NONCE_INVALID",
        "transcript_sha256": None,
        "public_nonce": None,
        "role_messages": {},
        "role_message_signed": False,
        "owner_signature_verified": False,
        "collector_signature_verified": False,
        "host_signature_verified": False,
        "host_key_attested": False,
        "replay_prevention_verified": False,
        "bridge_implemented": False,
        "installer_authorized": False,
        "safe_to_resume": False,
    }
    plan = review_three_role_custody_design(proposal)
    if (plan["state"] != "THREE_ROLE_CUSTODY_DESIGN_CANDIDATE_UNTRUSTED"
        or type(nonce) is not str or not _NONCE.fullmatch(nonce)):
        return out
    core = {
        "schema": BINDING_SCHEMA,
        "purpose": PURPOSE,
        "nonce": nonce,
        "policy_generation": proposal["policy_generation"],
        "collector_binary_sha256": proposal["collector_binary_sha256"],
        "policy_sha256": proposal["policy_sha256"],
        "role_public_key_sha256": {
            name: proposal[name]["public_key_sha256"]
            for name in ("owner", "collector", "host")
        },
    }
    serialized = json.dumps(
        core, sort_keys=True, ensure_ascii=True, separators=(",", ":"),
        allow_nan=False,
    ).encode("ascii")
    transcript = hashlib.sha256(
        b"ATLASQUANT:AION:TRIROLE_TRANSCRIPT:V1\x00" + serialized
    ).digest()
    role_messages = {}
    for role in _ROLES:
        msg = hashlib.sha256(
            b"ATLASQUANT:AION:TRIROLE_ROLE_INTENT:V1\x00"
            + _DOMAINS[role].encode("ascii") + b"\x00"
            + _ALGORITHMS[role].encode("ascii") + b"\x00" + transcript
        ).hexdigest()
        role_messages[role] = {
            "algorithm": _ALGORITHMS[role],
            "role_domain": _DOMAINS[role],
            "unsigned_message_sha256": "sha256:" + msg,
            "signature_present": False,
            "signature_verified": False,
        }
    out.update({
        "state": "THREE_UNSIGNED_ROLE_CHALLENGES_UNTRUSTED",
        "reason": "",
        "transcript_sha256": "sha256:" + transcript.hex(),
        "public_nonce": nonce,
        "role_messages": role_messages,
    })
    return out


__all__ = (
    "SCHEMA", "BINDING_SCHEMA", "PURPOSE",
    "review_three_role_custody_design",
    "build_unsigned_three_role_challenge",
)
