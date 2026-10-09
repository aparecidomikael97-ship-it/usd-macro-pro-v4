"""AION Ed25519 owner + collector dual-signature mathematical bridge V1.

Research / CI-only: recompute the existing #1109 canonical three-role
challenge and verify two detached Ed25519 signatures using the #1110
public-key verifier. Never trusts proposal key fingerprints as enrolled
identity; a valid signature is NOT an authorized HUMAN_OWNER decision.

PRODUCTION MODULE NEVER creates/signs private keys, accesses TPM/Windows
or writes state. The host P-256 role is intentionally UNATTESTED/BLOCKED.
"""
from __future__ import annotations

import hashlib
import hmac
import re
from typing import Any

from atlasquant_aion_independent_ed25519_trirole_bridge_contract_v1 import (
    build_unsigned_three_role_challenge,
)
from atlasquant_aion_ed25519_public_verify_p256_attestation_review_v1 import (
    verify_role_bound_digest_signature,
)

SCHEMA = "AION_OWNER_COLLECTOR_DUAL_ED25519_PUBLIC_CRYPTO_BRIDGE_V1"
CANDIDATE = "DUAL_ED25519_SIGNATURES_MATHEMATICALLY_VALID_UNTRUSTED"
_OWNER = "HUMAN_OWNER_ED25519"
_COLLECTOR = "COLLECTOR_ED25519"
_KEY_HEX = re.compile(r"[0-9a-f]{64}\Z")
_SIG_HEX = re.compile(r"[0-9a-f]{128}\Z")
_FALSE_GATES = {
    "trusted_owner_public_key_pinned": False,
    "trusted_collector_public_key_pinned": False,
    "human_owner_identity_authenticated": False,
    "collector_identity_authenticated": False,
    "independent_signer_custody_verified": False,
    "key_enrollment_verified": False,
    "external_signed_owner_approval_verified": False,
    "signed_collector_witness_approved": False,
    "owner_authorization_for_execution": False,
    "policy_generation_durably_verified": False,
    "durable_nonce_issued_and_consumed": False,
    "replay_protection_verified": False,
    "revocation_and_rotation_verified": False,
    "tpm_p256_key_present": False,
    "p256_host_signature_verified": False,
    "p256_tpm_origin_attested": False,
    "p256_nonexportability_verified": False,
    "independent_host_identity_attested": False,
    "host_policy_anchor_verified": False,
    "physical_sandbox_12_of_12_verified": False,
    "physical_network_deny_16_of_16_verified": False,
    "key_creation_authorized": False,
    "key_enrollment_authorized": False,
    "collector_launch_authorized": False,
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
        "owner_signature_mathematically_valid": False,
        "collector_signature_mathematically_valid": False,
        "proposal_fingerprints_match_public_keys_untrusted": False,
        "canonical_transcript_sha256": None,
        "owner_intent_sha256": None,
        "collector_intent_sha256": None,
        "not_an_enrollment_or_replay_protection_proof": True,
        **_FALSE_GATES,
    }


def verify_dual_ed25519_public_signatures_untrusted(
    *, proposal: Any, nonce: Any,
    owner_public_key_hex: Any, owner_signature_hex: Any,
    collector_public_key_hex: Any, collector_signature_hex: Any,
) -> dict[str, Any]:
    """Verify both signatures for their OWN role-specific challenge digests.

    Key identities are matched ONLY against caller-controlled proposal
    fingerprints, not pinned keys from a trusted durable enrollment.
    Replay of exactly the same valid pair will remain mathematically
    valid: this does not track fresh/consumed nonce or policy generation.
    """
    out = _blocked("MALFORMED_DUAL_SIGNATURE_REQUEST")
    for item, pattern in (
        (owner_public_key_hex, _KEY_HEX),
        (collector_public_key_hex, _KEY_HEX),
        (owner_signature_hex, _SIG_HEX),
        (collector_signature_hex, _SIG_HEX),
    ):
        if type(item) is not str or not pattern.fullmatch(item):
            return out
    if owner_public_key_hex == collector_public_key_hex:
        out["reason"] = "DUPLICATE_OWNER_COLLECTOR_PUBLIC_KEY"
        return out
    plan = build_unsigned_three_role_challenge(proposal, nonce)
    if plan["state"] != "THREE_UNSIGNED_ROLE_CHALLENGES_UNTRUSTED":
        out["reason"] = "PROPOSAL_OR_CHALLENGE_NOT_VALIDATED"
        return out
    owner_hash = "sha256:" + hashlib.sha256(
        bytes.fromhex(owner_public_key_hex)).hexdigest()
    collector_hash = "sha256:" + hashlib.sha256(
        bytes.fromhex(collector_public_key_hex)).hexdigest()
    if not (
        hmac.compare_digest(owner_hash, proposal["owner"]["public_key_sha256"])
        and hmac.compare_digest(
            collector_hash, proposal["collector"]["public_key_sha256"])
    ):
        out["reason"] = "PROPOSAL_PUBLIC_KEY_FINGERPRINT_MISMATCH"
        return out
    out["proposal_fingerprints_match_public_keys_untrusted"] = True
    out["canonical_transcript_sha256"] = plan["transcript_sha256"]
    out["owner_intent_sha256"] = plan["role_messages"][_OWNER]["unsigned_message_sha256"]
    out["collector_intent_sha256"] = plan["role_messages"][_COLLECTOR]["unsigned_message_sha256"]
    if out["owner_intent_sha256"] == out["collector_intent_sha256"]:
        out["reason"] = "ROLE_DOMAINS_NOT_INDEPENDENT"
        return out

    owner_result = verify_role_bound_digest_signature(
        role=_OWNER, public_key_hex=owner_public_key_hex,
        signature_hex=owner_signature_hex,
        role_intent=plan["role_messages"][_OWNER],
        claimed_public_key_sha256=owner_hash,
    )
    if owner_result["signature_mathematically_valid"] is not True:
        out["reason"] = "OWNER_ED25519_SIGNATURE_INVALID"
        return out

    collector_result = verify_role_bound_digest_signature(
        role=_COLLECTOR, public_key_hex=collector_public_key_hex,
        signature_hex=collector_signature_hex,
        role_intent=plan["role_messages"][_COLLECTOR],
        claimed_public_key_sha256=collector_hash,
    )
    if collector_result["signature_mathematically_valid"] is not True:
        out["reason"] = "COLLECTOR_ED25519_SIGNATURE_INVALID"
        return out

    out["owner_signature_mathematically_valid"] = True
    out["collector_signature_mathematically_valid"] = True
    out["state"] = CANDIDATE
    out["reason"] = ""
    return out


__all__ = (
    "SCHEMA", "CANDIDATE", "verify_dual_ed25519_public_signatures_untrusted",
)
