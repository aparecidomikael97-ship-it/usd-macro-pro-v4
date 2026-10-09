"""AION HUMAN_OWNER-only, explicit-scope Windows silent CNG algorithm check.

Executable on owner Windows ONLY after independent conversational owner
approval for this exact read-only probe and device selection by the
authorized Remote Desktop Commander connection. An opt-in parameter is
NOT cryptographic owner identity and must not be treated as authorization
to enroll private keys, change configuration, resume or install.

Calls exactly the fixed native silent signature-algorithm enumeration core
from #1103, with no key enumeration, no file writes, no zero-flags retry.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import re
import sys
from typing import Any

from atlasquant_aion_native_cng_silent_signature_algorithm_enum_v1 import (
    _base, _probe_silent_signature_algorithms_native_core,
)

PHYSICAL_SCOPE = "OWNER_APPROVED_SINGLE_READONLY_SILENT_SIGNATURE_ENUM_V1"
RECEIPT_SCHEMA = "AION_OWNER_CNG_READONLY_NON_AUTHORITY_CORRELATION_RECEIPT_V1"
_RECEIPT_DOMAIN = b"ATLASQUANT:AION:READONLY_CNG_CHALLENGE_RECEIPT:V1\x00"
_NONCE = re.compile(r"[0-9a-f]{64}\Z")


def observe_owner_silent_signature_algorithms_readonly(
    challenge_nonce: str,
    *,
    explicit_owner_authorization_for_this_probe: bool = False,
    authorized_device_scope: str = "",
) -> dict[str, Any]:
    """One bounded diagnostic, not a protected owner authentication step."""
    if sys.platform != "win32":
        return _base("WINDOWS_REQUIRED")
    if (explicit_owner_authorization_for_this_probe is not True
        or authorized_device_scope != PHYSICAL_SCOPE):
        return _base("EXPLICIT_OWNER_SCOPED_READONLY_AUTHORIZATION_REQUIRED")
    if type(challenge_nonce) is not str or not _NONCE.fullmatch(challenge_nonce):
        return _base("EXPLICIT_256_BIT_CHALLENGE_REQUIRED")
    # Reuse the exact native code approved by CI without spoofing GitHub
    # environment variables or disabling #1103's CI-only wrapper.
    observation = _probe_silent_signature_algorithms_native_core()
    # The read-only observation is wholly sanitized before receipt creation;
    # no raw algorithm names, pointers or private key material may enter it.
    canonical = json.dumps(
        observation, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")
    snapshot_bytes = hashlib.sha256(canonical).digest()
    correlation_bytes = hashlib.sha256(
        _RECEIPT_DOMAIN + bytes.fromhex(challenge_nonce) + snapshot_bytes
    ).digest()
    observation["diagnostic_correlation_receipt"] = {
        "schema": RECEIPT_SCHEMA,
        "scope": PHYSICAL_SCOPE,
        "challenge_nonce": challenge_nonce,
        "sanitized_observation_sha256": "sha256:" + snapshot_bytes.hex(),
        "challenge_binding_sha256": "sha256:" + correlation_bytes.hex(),
        "receipt_signed": False,
        "independently_witnessed": False,
        "owner_identity_attested": False,
        "physical_device_attested": False,
        "replay_prevention_verified": False,
        "trusted_host_anchor_verified": False,
        "physical_sandbox_approved": False,
        "installer_authorized": False,
        "safe_to_resume": False,
    }
    return observation



_RECEIPT_FIELDS = frozenset({
    "schema", "scope", "challenge_nonce", "sanitized_observation_sha256",
    "challenge_binding_sha256", "receipt_signed", "independently_witnessed",
    "owner_identity_attested", "physical_device_attested",
    "replay_prevention_verified", "trusted_host_anchor_verified",
    "physical_sandbox_approved", "installer_authorized", "safe_to_resume",
})
_SHA256_PATTERN = re.compile(r"sha256:[0-9a-f]{64}\Z")


def verify_diagnostic_correlation_receipt(payload: Any) -> dict[str, Any]:
    """Check self-consistency only. Caller could forge both report and digest.

    No independent signer, trusted timestamp, nonce registry, real device
    identity or physical custody is established by this verifier.
    """
    result = {
        "state": "BLOCKED",
        "reason": "RECEIPT_INVALID",
        "correlation_recomputed": False,
        "receipt_is_trusted_evidence": False,
        "owner_identity_verified": False,
        "physical_device_verified": False,
        "replay_prevention_verified": False,
        "installer_authorized": False,
        "safe_to_resume": False,
    }
    if type(payload) is not dict:
        return result
    receipt = payload.get("diagnostic_correlation_receipt")
    if type(receipt) is not dict or set(receipt) != _RECEIPT_FIELDS:
        return result
    if (receipt.get("schema") != RECEIPT_SCHEMA
        or receipt.get("scope") != PHYSICAL_SCOPE
        or type(receipt.get("challenge_nonce")) is not str
        or not _NONCE.fullmatch(receipt["challenge_nonce"])):
        return result
    for field in (
        "receipt_signed", "independently_witnessed", "owner_identity_attested",
        "physical_device_attested", "replay_prevention_verified",
        "trusted_host_anchor_verified", "physical_sandbox_approved",
        "installer_authorized", "safe_to_resume",
    ):
        if receipt[field] is not False:
            return result
    for field in (
        "private_key_created", "private_key_opened", "private_key_enumerated",
        "private_key_enrolled", "host_security_state_modified",
        "installer_authorized", "build_authorized",
        "deploy_authorized", "safe_to_resume",
    ):
        if payload.get(field) is not False:
            return result
    if payload.get("state") not in ("BLOCKED", "SILENT_SIGNATURE_ALGORITHMS_LISTED_UNTRUSTED"):
        return result
    if (type(receipt["sanitized_observation_sha256"]) is not str
        or type(receipt["challenge_binding_sha256"]) is not str
        or not _SHA256_PATTERN.fullmatch(receipt["sanitized_observation_sha256"])
        or not _SHA256_PATTERN.fullmatch(receipt["challenge_binding_sha256"])):
        return result
    observation = dict(payload)
    observation.pop("diagnostic_correlation_receipt")
    try:
        canonical = json.dumps(
            observation, sort_keys=True, separators=(",", ":"),
            ensure_ascii=True, allow_nan=False,
        ).encode("ascii")
    except (ValueError, TypeError, OverflowError, UnicodeError):
        return result
    observation_digest = hashlib.sha256(canonical).digest()
    binding_digest = hashlib.sha256(
        _RECEIPT_DOMAIN + bytes.fromhex(receipt["challenge_nonce"])
        + observation_digest
    ).digest()
    if not hmac.compare_digest(
        receipt["sanitized_observation_sha256"],
        "sha256:" + observation_digest.hex(),
    ):
        return result
    if not hmac.compare_digest(
        receipt["challenge_binding_sha256"],
        "sha256:" + binding_digest.hex(),
    ):
        return result
    result["state"] = "CORRELATION_RECOMPUTED_UNTRUSTED"
    result["reason"] = ""
    result["correlation_recomputed"] = True
    return result


__all__ = (
    "PHYSICAL_SCOPE", "RECEIPT_SCHEMA",
    "observe_owner_silent_signature_algorithms_readonly",
    "verify_diagnostic_correlation_receipt",
)
