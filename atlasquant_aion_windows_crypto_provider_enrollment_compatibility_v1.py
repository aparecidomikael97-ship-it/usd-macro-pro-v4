"""AION Windows trust-anchor crypto-provider architecture PREVIEW gate.

CI only. This gate prevents a dangerous assumption: #1093/#1096 require
Ed25519 signing, while selecting a Windows TPM/CNG provider is NOT evidence
that it supports that exact algorithm or protects the Ed25519 private key.
Only reviews two explicitly separated custody architectures; never creates
keys, activates a provider or elevates trust from a registry observation.
"""
from __future__ import annotations

import json
import re
from typing import Any, Mapping

from atlasquant_aion_windows_host_anchor_readonly_inventory_v1 import (
    SCHEMA as ANCHOR_SCHEMA, BLOCKED as ANCHOR_BLOCKED,
    CANDIDATE as ANCHOR_CANDIDATE,
)

SCHEMA = "AION_WINDOWS_COLLECTOR_ROOT_CRYPTO_ARCHITECTURE_PREFLIGHT_V1"
PURPOSE = "DESIGN_REVIEW_ONLY_NO_KEY_PROVISIONING"
DESIGN_REVIEW = "CRYPTO_ARCHITECTURE_REVIEW_CANDIDATE_UNTRUSTED"
CONTRACT_ROOT_SIGNATURE = "ED25519"
TPM_KSP = "Microsoft Platform Crypto Provider"
MAX_INPUT_BYTES = 4096
_VALID_MODES = {
    "EXTERNAL_INDEPENDENT_ED25519_CUSTODY",
    "TPM_P256_HOST_BINDING_WITH_ED25519_COLLECTOR",
    "DIRECT_TPM_ED25519_UNVERIFIED",
}
_FIELDS = frozenset({
    "schema", "purpose", "proposed_mode", "collector_signature_algorithm",
    "owner_signature_algorithm", "collector_key_source",
    "host_binding_key_algorithm", "windows_key_provider",
    "tpm_ed25519_capability", "cross_algorithm_bridge_state",
    "private_key_provisioning_state", "trusted_policy_anchor_state",
    "owner_approval_state", "physical_key_attestation_state",
    "owner_witness_separation", "rollback_protection_state",
    "review_nonce",
})
_NONCE = re.compile(r"[0-9a-f]{64}\Z")


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "BLOCKED", "reason": reason,
        "design_contract_structurally_consistent": False,
        "ed25519_tpm_direct_support_verified": False,
        "hardware_protected_collector_private_key_verified": False,
        "host_cng_key_provider_verified": False,
        "cross_algorithm_bridge_implemented": False,
        "anchor_independently_protected": False,
        "owner_approval_authenticated": False,
        "witness_independence_verified": False,
        "rollback_protection_verified": False,
        "physical_12_requirements_verified": False,
        "network_16_surfaces_verified": False,
        "collector_key_enrolled": False,
        "installer_authorized": False,
        "build_authorized": False,
        "deploy_authorized": False,
        "safe_to_resume": False,
        "host_security_state_modified": False,
        "private_key_created": False,
    }


def _parse(review_bytes: bytes) -> dict[str, Any]:
    if type(review_bytes) is not bytes or not 2 <= len(review_bytes) <= MAX_INPUT_BYTES:
        raise ValueError("REVIEW_BYTES_INVALID")
    def unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for k, v in pairs:
            if k in result:
                raise ValueError("DUPLICATE_REVIEW_FIELD")
            result[k] = v
        return result
    try:
        review = json.loads(review_bytes.decode("utf-8"), object_pairs_hook=unique)
        canonical = json.dumps(review, sort_keys=True, separators=(",", ":"),
                               ensure_ascii=True, allow_nan=False).encode("utf-8")
    except (UnicodeError, ValueError, TypeError, OverflowError) as exc:
        raise ValueError("REVIEW_JSON_INVALID") from exc
    if type(review) is not dict or set(review) != _FIELDS or canonical != review_bytes:
        raise ValueError("REVIEW_SCHEMA_FIELDS_OR_ENCODING_INVALID")
    if review["schema"] != SCHEMA or review["purpose"] != PURPOSE:
        raise ValueError("REVIEW_PURPOSE_INVALID")
    for field in _FIELDS:
        if type(review[field]) is not str:
            raise ValueError("REVIEW_FIELD_TYPE_INVALID")
    if not _NONCE.fullmatch(review["review_nonce"]):
        raise ValueError("REVIEW_NONCE_INVALID")
    return review


def evaluate_windows_collector_root_crypto_architecture(
    review_bytes: bytes,
    anchor_observation: Mapping[str, Any],
) -> dict[str, Any]:
    """Structural review only, never a provisioner or physical trust verifier.

    The anchor_observation may originate from #1098, but even a correctly
    formatted HKLM value cannot prove secure custody or antirollback.
    """
    try:
        review = _parse(review_bytes)
    except (TypeError, ValueError, OverflowError):
        return _blocked("CRYPTO_REVIEW_INPUT_INVALID")
    if review["proposed_mode"] not in _VALID_MODES:
        return _blocked("CRYPTO_CUSTODY_MODE_UNKNOWN")
    if (review["collector_signature_algorithm"] != CONTRACT_ROOT_SIGNATURE
        or review["owner_signature_algorithm"] != CONTRACT_ROOT_SIGNATURE):
        return _blocked("ED25519_CONTRACT_WOULD_BE_SILENTLY_CHANGED")
    if review["proposed_mode"] == "DIRECT_TPM_ED25519_UNVERIFIED":
        return _blocked("DIRECT_TPM_ED25519_SUPPORT_NOT_ESTABLISHED")

    # Caller must NOT present real-world approval/provisioning as achieved.
    # Such claims belong to a separate independently validated physical gate.
    expected = {
        "tpm_ed25519_capability": "UNVERIFIED",
        "private_key_provisioning_state": "NOT_PROVISIONED",
        "trusted_policy_anchor_state": "NOT_PROVISIONED",
        "owner_approval_state": "NOT_REQUESTED",
        "physical_key_attestation_state": "NOT_COLLECTED",
        "owner_witness_separation": "REQUIRED_NOT_PHYSICALLY_VERIFIED",
        "rollback_protection_state": "NOT_VERIFIED",
    }
    if any(review.get(k) != value for k, value in expected.items()):
        return _blocked("UNSUPPORTED_REAL_WORLD_AUTHORITY_CLAIM")
    if review["proposed_mode"] == "EXTERNAL_INDEPENDENT_ED25519_CUSTODY":
        if any((
            review["collector_key_source"] != "EXTERNAL_SEPARATE_KEY_CUSTODIAN_PROPOSED",
            review["host_binding_key_algorithm"] != "NONE",
            review["windows_key_provider"] != "NONE",
            review["cross_algorithm_bridge_state"] != "NOT_APPLICABLE",
        )):
            return _blocked("EXTERNAL_ED25519_ARCHITECTURE_INCONSISTENT")
        next_gates = (
            "INDEPENDENT_EXTERNAL_ED25519_KEY_CUSTODY",
            "EXTERNAL_SIGNER_OWNER_WITNESS_ROLE_SEPARATION",
            "SIGNED_HOST_POLICY_AND_PROTECTED_ANTIROLLBACK",
            "PHYSICAL_COLLECTOR_ATTESTATION",
        )
    else:
        if any((
            review["collector_key_source"] != "EXTERNAL_ED25519_KEY_UNPROVISIONED",
            review["host_binding_key_algorithm"] != "ECDSA_P256",
            review["windows_key_provider"] != TPM_KSP,
            review["cross_algorithm_bridge_state"] != "NOT_IMPLEMENTED",
        )):
            return _blocked("TPM_P256_ED25519_BRIDGE_ARCHITECTURE_INCONSISTENT")
        next_gates = (
            "PROVE_TPM_PROVIDER_DEVICE_AND_ECDSA_P256_CAPABILITY",
            "DEVELOP_AND_AUDIT_CROSS_ALGORITHM_CHALLENGE_BINDING",
            "INDEPENDENT_ED25519_COLLECTOR_SIGNER_CUSTODY",
            "PROTECTED_HOST_POLICY_AND_REAL_ANTIROLLBACK",
            "PHYSICAL_COLLECTOR_ATTESTATION",
        )
    if type(anchor_observation) is not dict:
        return _blocked("READONLY_ANCHOR_OBSERVATION_REQUIRED")
    if anchor_observation.get("schema") != ANCHOR_SCHEMA:
        return _blocked("ANCHOR_OBSERVATION_SCHEMA_MISMATCH")
    if anchor_observation.get("state") not in (ANCHOR_BLOCKED, ANCHOR_CANDIDATE):
        return _blocked("ANCHOR_OBSERVATION_STATUS_INVALID")
    # Only an absent anchor or a merely syntactic candidate is admissible;
    # attempts to pass a third-party observation as trustworthy are refused.
    for flag in (
        "host_anchor_is_protected", "independent_host_policy_origin_verified",
        "hardware_antirollback_verified", "tpm_binding_verified",
        "registry_acl_verified", "installer_authorized", "safe_to_resume",
        "trust_store_modified", "system_registry_modified",
    ):
        if anchor_observation.get(flag) is not False:
            return _blocked("ANCHOR_OBSERVATION_UNTRUSTED_AUTHORITY_CLAIM")
    if anchor_observation["state"] == ANCHOR_BLOCKED:
        if anchor_observation.get("reason") != "HOST_ANCHOR_ABSENT":
            return _blocked("ANCHOR_OBSERVATION_BLOCKED_UNEXPECTED_REASON")
        additional = "HOST_ANCHOR_ABSENT_MUST_REMAIN_BLOCKED"
    else:
        if anchor_observation.get("reason") != "" or (
            anchor_observation.get("anchor_schema_and_types_valid") is not True
        ):
            return _blocked("ANCHOR_SHAPE_CANDIDATE_MALFORMED")
        additional = "HKLM_FORMAT_ALONE_NOT_TRUSTED"
    return {
        **_blocked(""),
        "state": DESIGN_REVIEW,
        "reason": "",
        "design_contract_structurally_consistent": True,
        "proposed_mode": review["proposed_mode"],
        "unresolved_gates": list(next_gates) + [
            additional,
            "OWNER_APPROVED_ACTUAL_ENROLLMENT_SEPARATELY_REQUIRED",
            "SANDBOX_12_OF_12_PHYSICAL_MEASUREMENTS_REQUIRED",
            "NETWORK_16_OF_16_PHYSICAL_DENIAL_SURFACES_REQUIRED",
        ],
    }


__all__ = [
    "SCHEMA", "PURPOSE", "DESIGN_REVIEW",
    "evaluate_windows_collector_root_crypto_architecture",
]
