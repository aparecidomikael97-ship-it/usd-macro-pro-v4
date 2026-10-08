"""AION Windows *CI-negative only* signed executable binding V1.

Verifies Ed25519 signature over one exact launch intent, then compares the
observed suspended-process image path and SHA-256 to signed values.
Never grants owner authority: the trust root and nonce registry are NOT
established here. CI keys are generated only for ephemeral test fixtures.
"""
from __future__ import annotations

from hashlib import sha256
import json
import ntpath
import re
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

SCHEMA = "AION_WINDOWS_SIGNED_BINARY_CI_NEGATIVE_INTENT_V1"
OPERATION = "QUARANTINE_NORMAL_CHILD_NEVER_RESUME"
MAX_AGE_SECONDS = 120
FIELDS = frozenset({
    "schema", "operation", "nonce", "image_path",
    "image_sha256", "issued_at", "expires_at",
    "expected_token_verdict",
})
DIGEST_PATTERN = re.compile(r"^[0-9a-f]{64}$")
NONCE_PATTERN = re.compile(r"^[0-9a-f]{32}$")
DRIVE_PATH = re.compile(r"^[A-Za-z]:\\")
CANDIDATE = "SIGNED_CI_NEGATIVE_BINARY_CANDIDATE_UNTRUSTED"
BLOCKED = "BLOCKED"


def canonical_intent(intent: dict[str, Any]) -> bytes:
    return json.dumps(
        intent, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")


def _result(reason: str, state: str = BLOCKED) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": state, "reason": reason,
        "signature_cryptographically_valid": state == CANDIDATE,
        "image_identity_candidate": state == CANDIDATE,
        "trusted_root_verified": False,
        "nonce_durability_verified": False,
        "process_handle_origin_verified": False,
        "physical_attestation_verified": False,
        "appcontainer_verified": False,
        "network_deny_verified": False,
        "safe_to_resume": False,
        "installer_authorized": False,
        "build_authorized": False,
        "deploy_authorized": False,
    }


def check_signed_ci_negative_intent(
    manifest: Any, signature: Any, public_key: Any,
    *,
    observed_image_path: Any,
    observed_image_sha256: Any,
    now: Any,
) -> dict[str, Any]:
    """Validate signed, scoped, short-lived candidate; NEVER permit launch.

    A caller-provided public key is NOT an owner root. No registry/replay
    protection is implemented. A forged claimant with its own key is only a
    cryptographic fixture match, not trusted host authorization.
    """
    if type(manifest) is not dict or set(manifest) != FIELDS:
        return _result("EXACT_SIGNED_MANIFEST_FIELDS_REQUIRED")
    if manifest["schema"] != SCHEMA or manifest["operation"] != OPERATION:
        return _result("CI_NEGATIVE_ONLY_OPERATION_REQUIRED")
    if manifest["expected_token_verdict"] != "TOKEN_NOT_APPCONTAINER":
        return _result("NORMAL_CHILD_DENIAL_ONLY")
    if (
        type(manifest["nonce"]) is not str
        or not NONCE_PATTERN.fullmatch(manifest["nonce"])
    ):
        return _result("NONCE_FORMAT_INVALID")
    path = manifest["image_path"]
    if (
        type(path) is not str or len(path) > 900
        or not DRIVE_PATH.match(path)
        or ntpath.normpath(path) != path
        or "\x00" in path
    ):
        return _result("PINNED_WINDOWS_PATH_REQUIRED")
    digest = manifest["image_sha256"]
    if type(digest) is not str or not DIGEST_PATTERN.fullmatch(digest):
        return _result("PINNED_SHA256_REQUIRED")
    issued, expires = manifest["issued_at"], manifest["expires_at"]
    if (
        type(issued) is not int or type(expires) is not int
        or type(now) is not int or issued > expires
        or expires - issued > MAX_AGE_SECONDS
        or issued > now or now > expires
    ):
        return _result("SIGNATURE_WINDOW_INVALID_OR_EXPIRED")
    if (
        type(observed_image_path) is not str
        or ntpath.normcase(ntpath.normpath(observed_image_path)) != ntpath.normcase(path)
    ):
        return _result("SUSPENDED_PROCESS_IMAGE_PATH_MISMATCH")
    if (
        type(observed_image_sha256) is not str
        or not DIGEST_PATTERN.fullmatch(observed_image_sha256)
        or observed_image_sha256 != digest
    ):
        return _result("SUSPENDED_PROCESS_IMAGE_DIGEST_MISMATCH")
    if type(signature) is not bytes or len(signature) != 64:
        return _result("SIGNATURE_FORMAT_INVALID")
    if type(public_key) is not bytes or len(public_key) != 32:
        return _result("PUBLIC_KEY_FORMAT_INVALID")
    try:
        Ed25519PublicKey.from_public_bytes(public_key).verify(
            signature, canonical_intent(manifest),
        )
    except (ValueError, InvalidSignature):
        return _result("ED25519_SIGNATURE_INVALID")
    return _result(
        "SIGNED_FIXTURE_MATCH_ONLY_NO_OWNER_TRUST_ANCHOR", CANDIDATE,
    )


def digest_bytes(value: bytes) -> str:
    return sha256(value).hexdigest()


__all__ = [
    "SCHEMA", "FIELDS", "OPERATION", "BLOCKED", "CANDIDATE",
    "canonical_intent", "check_signed_ci_negative_intent", "digest_bytes",
]
