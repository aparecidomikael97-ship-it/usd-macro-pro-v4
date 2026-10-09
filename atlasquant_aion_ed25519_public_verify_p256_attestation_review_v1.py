"""AION Ed25519 PUBLIC signature verification and P-256 attestation REVIEW V1.

Real RFC 8032 signature mathematics via an audited dependency, public keys
and fixed signatures only. No secret keys, sign/generate, Windows native
API, user PC, durable replay ledger, enrollment, install or deployment.

A valid detached signature proves possession of the private key matching
the supplied PUBLIC KEY for exactly the verified message. It never proves
that key belongs to HUMAN_OWNER or an independent collector, nor does it
authenticate its enrollment, freshness, custody, hardware, or authority.
"""
from __future__ import annotations

import hashlib
import hmac
import re
from typing import Any

from cryptography.exceptions import InvalidSignature, UnsupportedAlgorithm
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

SCHEMA = "AION_ED25519_PUBLIC_SIGNATURE_VERIFICATION_RESEARCH_V1"
ATTESTATION_SCHEMA = "AION_P256_ATTESTATION_REQUIREMENTS_REVIEW_V1"
_ROLES = ("HUMAN_OWNER_ED25519", "COLLECTOR_ED25519")
_ROLE_DOMAINS = {
    "HUMAN_OWNER_ED25519": "AION_OWNER_APPROVAL_V1",
    "COLLECTOR_ED25519": "AION_COLLECTOR_INDEPENDENT_WITNESS_V1",
}
_HEX_KEY = re.compile(r"[0-9a-f]{64}\Z")
_HEX_SIG = re.compile(r"[0-9a-f]{128}\Z")
_HEX_SHA = re.compile(r"sha256:[0-9a-f]{64}\Z")
_HEX_MESSAGE = re.compile(r"[0-9a-f]{0,8192}\Z")
_ALWAYS_FALSE = {
    "owner_identity_authenticated": False,
    "collector_identity_authenticated": False,
    "public_key_pinning_trusted": False,
    "independent_custody_verified": False,
    "nonce_freshness_durably_verified": False,
    "anti_replay_durably_verified": False,
    "owner_approval_authorized": False,
    "collector_launch_authorized": False,
    "host_p256_tpm_origin_attested": False,
    "host_p256_nonexportability_verified": False,
    "physical_sandbox_12_of_12_verified": False,
    "physical_network_deny_16_of_16_verified": False,
    "key_creation_authorized": False,
    "key_enrollment_authorized": False,
    "installer_authorized": False,
    "build_authorized": False,
    "deploy_authorized": False,
    "safe_to_resume": False,
}
_ATTESTATION_REQUIREMENTS = (
    "TRUSTED_MANUFACTURER_TPM_EK_CERT_CHAIN_OR_PINNED_EK",
    "INDEPENDENTLY_VERIFIED_AK_OR_EQUIVALENT_ATTESTATION_SIGNER",
    "TPM2_CERTIFY_FOR_EXACT_P256_PUBLIC_KEY",
    "TPM_PUBLIC_AREA_AND_P256_CURVE_ATTRIBUTES_VERIFIED",
    "FIXED_TPM_POLICY_AND_NONEXPORTABILITY_ATTRIBUTES_VERIFIED",
    "CRYPTOGRAPHIC_QUOTE_OR_CERTIFY_SIGNATURE_VERIFIED",
    "FRESH_NONCE_BOUND_TO_ATTESTATION_AND_SIGNATURE",
    "INDEPENDENT_HOST_TRUST_ROOT_AND_DEVICE_BINDING_VERIFIED",
    "REVOCATION_AND_TPM_REPLACEMENT_POLICY_VERIFIED",
    "ATTESTATION_PARSER_CONFORMANCE_AND_NEGATIVE_VECTORS",
)
_RFC_VARIANT = "Ed25519_PURE_RFC8032_NO_CTX_NO_PH"


def _denied(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "BLOCKED", "reason": reason,
        "algorithm": _RFC_VARIANT,
        "signature_mathematically_valid": False,
        "public_key_fingerprint_matched_claim": False,
        "role": None, "verified_message_sha256": None,
        **_ALWAYS_FALSE,
    }


def verify_ed25519_public_signature(
    *, role: Any, public_key_hex: Any, signature_hex: Any,
    message_hex: Any, claimed_public_key_sha256: Any,
    claimed_message_sha256: Any,
) -> dict[str, Any]:
    """Check signature on exact bytes; fingerprints are CALLER claims.

    No key registration/trusted pinning, user identity, challenge uniqueness
    or production authorization. Verification only; no secret key API.
    RFC8032 test vectors can be checked with this primitive.
    """
    out = _denied("MALFORMED_PUBLIC_VERIFICATION_REQUEST")
    if type(role) is not str or role not in _ROLES:
        return out
    if (type(public_key_hex) is not str
        or not _HEX_KEY.fullmatch(public_key_hex)
        or type(signature_hex) is not str
        or not _HEX_SIG.fullmatch(signature_hex)
        or type(message_hex) is not str
        or len(message_hex) % 2 != 0
        or not _HEX_MESSAGE.fullmatch(message_hex)
        or type(claimed_public_key_sha256) is not str
        or not _HEX_SHA.fullmatch(claimed_public_key_sha256)
        or type(claimed_message_sha256) is not str
        or not _HEX_SHA.fullmatch(claimed_message_sha256)):
        return out
    pub = bytes.fromhex(public_key_hex)
    signature = bytes.fromhex(signature_hex)
    message = bytes.fromhex(message_hex)
    pub_digest = "sha256:" + hashlib.sha256(pub).hexdigest()
    msg_digest = "sha256:" + hashlib.sha256(message).hexdigest()
    if not (hmac.compare_digest(pub_digest,claimed_public_key_sha256)
            and hmac.compare_digest(msg_digest,claimed_message_sha256)):
        out["reason"] = "CALLER_CLAIMED_FINGERPRINT_MISMATCH"
        return out
    out["role"] = role
    out["verified_message_sha256"] = msg_digest
    out["public_key_fingerprint_matched_claim"] = True
    try:
        Ed25519PublicKey.from_public_bytes(pub).verify(signature, message)
    except (InvalidSignature, ValueError, TypeError, UnsupportedAlgorithm):
        out["reason"] = "SIGNATURE_VERIFICATION_FAILED"
        return out
    out["state"] = "PUBLIC_KEY_SIGNATURE_MATHEMATICALLY_VALID_UNTRUSTED"
    out["reason"] = ""
    out["signature_mathematically_valid"] = True
    return out


def verify_role_bound_digest_signature(
    *, role: Any, public_key_hex: Any, signature_hex: Any,
    role_intent: Any, claimed_public_key_sha256: Any,
) -> dict[str, Any]:
    """Verify Ed25519 signature of exactly one 32-byte role-intent digest.

    The 32-byte intent digest must be produced from the canonical
    purpose+role+policy+nonce transcript in #1109. This function does NOT
    establish that the transcript was issued by a trusted authority.
    """
    out = _denied("INVALID_ROLE_INTENT_OR_SIGNATURE_REQUEST")
    if type(role) is not str or role not in _ROLES:
        return out
    if (type(role_intent) is not dict
        or set(role_intent) != {
            "algorithm", "role_domain", "unsigned_message_sha256",
            "signature_present", "signature_verified",
        } or role_intent.get("algorithm") != "Ed25519"
        or role_intent.get("role_domain") != _ROLE_DOMAINS[role]
        or type(role_intent.get("unsigned_message_sha256")) is not str
        or not _HEX_SHA.fullmatch(role_intent["unsigned_message_sha256"])
        or role_intent.get("signature_present") is not False
        or role_intent.get("signature_verified") is not False):
        return out
    digest_bytes = bytes.fromhex(role_intent["unsigned_message_sha256"][7:])
    return verify_ed25519_public_signature(
        role=role, public_key_hex=public_key_hex,
        signature_hex=signature_hex, message_hex=digest_bytes.hex(),
        claimed_public_key_sha256=claimed_public_key_sha256,
        claimed_message_sha256="sha256:" + hashlib.sha256(digest_bytes).hexdigest(),
    )


def review_p256_hardware_attestation_requirements(
    *, purported_evidence: Any = None,
) -> dict[str, Any]:
    """Enumerate proof gates, NOT a TPM attestation verifier.

    Even when untrusted evidence is supplied, this module has no EK/AK
    certificate parser, TCG TPM2_Certify signature verifier or hardware
    witness; it MUST NOT assert successful attestation.
    """
    return {
        "schema": ATTESTATION_SCHEMA,
        "state": "HARDWARE_ATTESTATION_UNIMPLEMENTED_BLOCKED",
        "reason": "NO_INDEPENDENT_P256_TPM_ATTESTATION_VERIFIER",
        "evidence_checks_required": list(_ATTESTATION_REQUIREMENTS),
        "evidence_accepted": False,
        "windows_platform_ksp_algorithm_listing_is_tpm_proof": False,
        "enterprise_ca_rsa_attestation_is_p256_proof": False,
        "p256_tpm_origin_verified": False,
        "p256_private_key_nonexportability_verified": False,
        "ek_ak_chain_verified": False,
        "freshness_verified": False,
        "host_binding_verified": False,
        "owner_identity_verified": False,
        "installer_authorized": False,
        "safe_to_resume": False,
    }


__all__ = (
    "SCHEMA", "ATTESTATION_SCHEMA", "verify_ed25519_public_signature",
    "verify_role_bound_digest_signature",
    "review_p256_hardware_attestation_requirements",
)
