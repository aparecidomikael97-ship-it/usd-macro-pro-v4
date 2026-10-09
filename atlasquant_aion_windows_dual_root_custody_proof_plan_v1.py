"""AION Windows dual-root custody proof design V1 — PREPARE / NO CRYPTO EXECUTION.

This module performs deterministic, purely structural architecture review
for the owner-observed CNG Platform KSP algorithm-advertisement result.
It NEVER creates, reads, enrolls, signs with or attests any private key.
It NEVER promotes a capability listing or an unsigned SHA256 correlation
receipt to hardware-custody, HUMAN_OWNER, or installation authority.

The intended future architecture has separately governed Ed25519 owner /
collector identity and an optional ECDSA P-256 device-binding key. A real
TPM P-256 key MUST NOT be inferred from a CNG algorithm advertisement.
Microsoft enterprise CA TPM key attestation is documented RSA-only; it is
not a shortcut for P-256 attestation.
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any

SCHEMA = "AION_WINDOWS_DUAL_ROOT_CUSTODY_PROOF_PLAN_V1"
PROPOSAL = "EXTERNAL_ED25519_PLUS_OPTIONAL_P256_DEVICE_BINDING_REVIEW_ONLY"
OBSERVATION_SCHEMA = "AION_CNG_SILENT_SIGNATURE_ALGORITHM_ENUM_CI_V1"
CORRELATION_SCHEMA = "AION_OWNER_CNG_READONLY_NON_AUTHORITY_CORRELATION_RECEIPT_V1"
TRANSCRIPT_SCHEMA = "AION_WINDOWS_OWNER_HOST_BINDING_TRANSCRIPT_DRAFT_V1"
PURPOSE = "BIND_OWNER_COLLECTOR_TO_INDEPENDENTLY_ATTESTED_HOST_ONLY_IF_VERIFIED"
_DOMAIN = b"ATLASQUANT:AION:DUAL_ROOT_DRAFT_TRANSCRIPT:V1\x00"
_HASH = re.compile(r"sha256:[0-9a-f]{64}\Z")
_NONCE = re.compile(r"[0-9a-f]{64}\Z")
_OBS_FALSE = (
    "actual_no_ui_physically_verified", "owner_pc_execution_authorized_by_code",
    "independently_attested_provider_identity", "tpm_presence_verified",
    "tpm_ed25519_key_custody_verified", "p256_tpm_key_custody_verified",
    "algorithm_provisionability_verified", "key_nonexportability_verified",
    "private_key_created", "private_key_opened", "private_key_enumerated",
    "private_key_enrolled", "host_security_state_modified",
    "physical_attestation_verified", "network_deny_verified",
    "collector_launch_authorized", "installer_authorized",
    "build_authorized", "deploy_authorized", "safe_to_resume",
)
_NEVER_TRUSTED = {
    "owner_ed25519_private_key_custody_independently_verified": False,
    "owner_ed25519_signature_verified": False,
    "p256_private_key_generated": False,
    "p256_private_key_nonexportable_verified": False,
    "p256_tpm_origin_attested": False,
    "p256_challenge_signature_verified": False,
    "tpm_ek_chain_verified": False,
    "rsa_only_enterprise_ca_attests_p256": False,
    "host_binding_bridge_implemented": False,
    "cryptographic_role_separation_verified": False,
    "nonce_uniqueness_durable_verified": False,
    "hardware_antirollback_verified": False,
    "protected_host_policy_anchor_verified": False,
    "human_owner_identity_attested": False,
    "physical_sandbox_12_of_12_verified": False,
    "physical_network_deny_16_of_16_verified": False,
    "collector_launch_authorized": False,
    "key_enrollment_authorized": False,
    "installer_authorized": False,
    "build_authorized": False,
    "deploy_authorized": False,
    "safe_to_resume": False,
    "host_security_state_modified": False,
}


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "state": "BLOCKED",
        "reason": reason,
        "proposed_architecture": None,
        "algorithm_roles": {
            "owner_identity": "ED25519_EXTERNAL_INDEPENDENT",
            "host_binding": "ECDSA_P256_TPM_PROOF_PENDING",
            "enterprise_ca_tpm_attestation": "RSA_ONLY_NOT_P256_PROOF",
        },
        "requires_explicit_separate_provisioning_approval": True,
        "requires_independent_hardware_key_attestation_design": True,
        "requires_independent_ed25519_custodian": True,
        **_NEVER_TRUSTED,
    }


def review_owner_cng_observation_for_dual_root_plan(
    observed: Any,
) -> dict[str, Any]:
    """Describe a proposed architecture from an UNTRUSTED public observation.

    This never validates the device itself. The input is adversary-controlled
    metadata and must never be treated as signed, replay-proof or anchored.
    """
    out = _blocked("OBSERVATION_INVALID_OR_UNTRUSTED")
    if type(observed) is not dict:
        return out
    if (observed.get("schema") != OBSERVATION_SCHEMA
        or observed.get("state") != "SILENT_SIGNATURE_ALGORITHMS_LISTED_UNTRUSTED"
        or observed.get("reason") != ""
        or observed.get("provider_name") != "Microsoft Platform Crypto Provider"
        or observed.get("requested_operation") != "NCRYPT_SIGNATURE_OPERATION"
        or observed.get("query_flags") != "NCRYPT_SILENT_FLAG"
        or observed.get("enumeration_failure_category") is not None):
        return out
    statuses = observed.get("target_algorithm_names")
    if (type(statuses) is not dict
        or set(statuses) != {"ECDSA_P256", "ED25519"}
        or statuses["ECDSA_P256"] != "LISTED"
        or statuses["ED25519"] != "NOT_LISTED"):
        return out
    if (type(observed.get("algorithm_name_count")) is not int
        or not (1 <= observed["algorithm_name_count"] <= 64)
        or observed.get("provider_handle_released") is not True
        or observed.get("result_buffer_released") is not True
        or observed.get("provider_ui_suppression_requested") is not True):
        return out
    for name in ("provider_open_status", "enumeration_status",
                 "provider_free_status", "buffer_free_status"):
        s = observed.get(name)
        if (type(s) is not dict or s.get("status_hex") != "0x00000000"
            or s.get("classification") != "ADVERTISED"):
            return out
    if any(observed.get(flag) is not False for flag in _OBS_FALSE):
        return out
    receipt = observed.get("diagnostic_correlation_receipt")
    if (type(receipt) is not dict
        or receipt.get("schema") != CORRELATION_SCHEMA
        or receipt.get("receipt_signed") is not False
        or receipt.get("independently_witnessed") is not False
        or receipt.get("trusted_host_anchor_verified") is not False
        or receipt.get("installer_authorized") is not False
        or receipt.get("safe_to_resume") is not False):
        return out
    # This is intentionally *not* the cryptographic verifier of the
    # unsigned receipt. Recomputing a hash is not owner authentication.
    out["state"] = "CUSTODY_ARCHITECTURE_REVIEW_CANDIDATE_UNTRUSTED"
    out["reason"] = ""
    out["proposed_architecture"] = PROPOSAL
    return out


_TRANSCRIPT_FIELDS = frozenset({
    "nonce", "owner_ed25519_public_key_sha256", "host_p256_public_key_sha256",
    "collector_binary_sha256", "policy_sha256", "generation",
})


def build_unsigned_dual_root_transcript_draft(fields: Any) -> dict[str, Any]:
    """Prepare strictly typed challenge transcript bytes/hash; never sign.

    The returned digest is a design sample and not a key custody proof,
    signed challenge, timestamp, durable anti-replay witness or installation
    permit. Keys are *public key fingerprints* only, never private keys.
    """
    out = {
        "schema": TRANSCRIPT_SCHEMA,
        "state": "BLOCKED",
        "reason": "INVALID_DRAFT_INPUT",
        "purpose": PURPOSE,
        "draft_sha256": None,
        "draft_canonical_json": None,
        "transcript_signed": False,
        "owner_signature_verified": False,
        "host_signature_verified": False,
        "tpm_origin_verified": False,
        "nonce_replay_protected": False,
        "authorized_for_provisioning": False,
        "safe_to_resume": False,
    }
    if type(fields) is not dict or set(fields) != _TRANSCRIPT_FIELDS:
        return out
    if (type(fields["nonce"]) is not str or not _NONCE.fullmatch(fields["nonce"])
        or type(fields["generation"]) is not int
        or not 0 <= fields["generation"] < 2**32):
        return out
    for field in _TRANSCRIPT_FIELDS - {"nonce", "generation"}:
        if type(fields[field]) is not str or not _HASH.fullmatch(fields[field]):
            return out
    if (fields["owner_ed25519_public_key_sha256"]
        == fields["host_p256_public_key_sha256"]):
        return out
    transcript = {
        "schema": TRANSCRIPT_SCHEMA,
        "purpose": PURPOSE,
        **fields,
    }
    raw = json.dumps(
        transcript, sort_keys=True, ensure_ascii=True,
        separators=(",", ":"), allow_nan=False,
    ).encode("ascii")
    out["state"] = "UNSIGNED_DRAFT_TRANSCRIPT_UNTRUSTED"
    out["reason"] = ""
    out["draft_sha256"] = "sha256:" + hashlib.sha256(_DOMAIN + raw).hexdigest()
    out["draft_canonical_json"] = raw.decode("ascii")
    return out


__all__ = (
    "SCHEMA", "PROPOSAL", "TRANSCRIPT_SCHEMA",
    "review_owner_cng_observation_for_dual_root_plan",
    "build_unsigned_dual_root_transcript_draft",
)
