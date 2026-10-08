"""Fail-closed HOST-PINNED policy provenance for AION collector PREPARE.

CI-only, pure data/cryptography. No system trust store mutation, no physical
key custody claim, no production anchor creation or key enrollment.

Crucial trust boundary: pinned authority root, exact policy digest, and policy
epoch MUST be obtained from a pre-existing protected host source wholly
independent of these bytes and the collector. Caller-supplied values alone
do not establish independence or hardware/OS protection.
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import json
import re
from typing import Any, Mapping

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from atlasquant_aion_owner_cosigned_collector_root_ceremony_v1 import (
    STATE as CEREMONY_PREPARED,
    verify_owner_cosigned_collector_root_ceremony,
)
from atlasquant_aion_rooted_collector_raw_evidence_preflight_v1 import (
    SQLiteCollectorChallengeReplay,
)

SCHEMA = "AION_PROTECTED_HOST_COLLECTOR_POLICY_PREFLIGHT_V1"
POLICY_SCHEMA = "AION_HOST_COLLECTOR_TRUST_POLICY_SNAPSHOT_V1"
POLICY_PURPOSE = "READ_ONLY_COLLECTOR_CEREMONY_POLICY"
STATE = "HOST_ANCHORED_COLLECTOR_CEREMONY_PREPARED_UNTRUSTED"
POLICY_DOMAIN = b"ATLASQUANT:AION:PROTECTED_HOST_POLICY:V1\x00"
POLICY_MAX_BYTES = 8192
POLICY_MAX_TTL = 86400
_POLICY_FIELDS = frozenset({
    "schema", "purpose", "authority_id",
    "policy_epoch", "previous_policy_digest",
    "issued_at", "expires_at",
    "owner_registry_root_fingerprint", "owner_registry_id",
    "owner_subject", "owner_host_issuer",
    "owner_device_id", "minimum_owner_registry_epoch",
    "host_binding_digest", "device_binding_digest",
    "collector_id", "protected_collector_epoch",
    "previous_collector_root_fingerprint",
    "witness_public_key_b64", "witness_fingerprint",
    "approved_collector_binary_digest", "approved_collector_manifest_digest",
})
_TAG = re.compile(r"[A-Za-z0-9._:-]{1,96}\Z")
_SHA = re.compile(r"sha256:[0-9a-f]{64}\Z")


def _sha(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "state": "BLOCKED",
        "reason": reason,
        "authority_signature_valid": False,
        "policy_digest_matches_protected_anchor": False,
        "policy_epoch_matches_protected_anchor": False,
        "ceremony_prepared_cryptographically": False,
        "protected_host_source_independently_verified": False,
        "hardware_antirollback_verified": False,
        "owner_real_identity_enrolled": False,
        "collector_root_enrolled_in_production": False,
        "collector_launch_authorized": False,
        "physical_attestation_verified": False,
        "network_deny_verified": False,
        "safe_to_resume": False,
        "installer_authorized": False,
        "build_authorized": False,
        "deploy_authorized": False,
        "host_trust_state_modified": False,
    }


def _tag(value: Any) -> bool:
    return type(value) is str and bool(_TAG.fullmatch(value))


def _digest(value: Any) -> bool:
    return type(value) is str and bool(_SHA.fullmatch(value))


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for name, value in pairs:
        if name in result:
            raise ValueError("DUPLICATE_PROPERTY")
        result[name] = value
    return result


def _parse(raw: bytes) -> dict[str, Any]:
    if type(raw) is not bytes or not 2 <= len(raw) <= POLICY_MAX_BYTES:
        raise ValueError("POLICY_BYTES_INVALID")
    try:
        policy = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs)
        canonical = json.dumps(
            policy, sort_keys=True, separators=(",", ":"),
            ensure_ascii=True, allow_nan=False,
        ).encode("utf-8")
    except (UnicodeError, ValueError, TypeError, OverflowError) as exc:
        raise ValueError("POLICY_JSON_INVALID") from exc
    if type(policy) is not dict or set(policy) != _POLICY_FIELDS or raw != canonical:
        raise ValueError("POLICY_NOT_CANONICAL_OR_FIELDS_INVALID")
    if policy["schema"] != POLICY_SCHEMA or policy["purpose"] != POLICY_PURPOSE:
        raise ValueError("POLICY_PURPOSE_INVALID")

    for name in (
        "authority_id", "owner_registry_id", "owner_subject",
        "owner_host_issuer", "owner_device_id", "collector_id",
    ):
        if not _tag(policy[name]):
            raise ValueError("POLICY_IDENTITY_INVALID")
    for name in (
        "owner_registry_root_fingerprint", "host_binding_digest",
        "device_binding_digest", "witness_fingerprint",
        "approved_collector_binary_digest", "approved_collector_manifest_digest",
    ):
        if not _digest(policy[name]):
            raise ValueError("POLICY_DIGEST_INVALID")
    policy_epoch = policy["policy_epoch"]
    previous_policy = policy["previous_policy_digest"]
    if type(policy_epoch) is not int or policy_epoch < 1:
        raise ValueError("POLICY_EPOCH_INVALID")
    if policy_epoch == 1:
        if previous_policy is not None:
            raise ValueError("POLICY_GENESIS_PREDECESSOR_INVALID")
    elif not _digest(previous_policy):
        raise ValueError("POLICY_PREDECESSOR_MISSING")
    owner_epoch = policy["minimum_owner_registry_epoch"]
    collector_epoch = policy["protected_collector_epoch"]
    if (type(owner_epoch) is not int or owner_epoch < 1
        or type(collector_epoch) is not int or collector_epoch < 0):
        raise ValueError("POLICY_TRUST_FLOOR_INVALID")
    prior = policy["previous_collector_root_fingerprint"]
    if collector_epoch == 0:
        if prior is not None:
            raise ValueError("COLLECTOR_GENESIS_ROOT_MISMATCH")
    elif not _digest(prior):
        raise ValueError("COLLECTOR_ROTATION_ROOT_MISSING")
    issued, expires = policy["issued_at"], policy["expires_at"]
    if (type(issued) is not int or type(expires) is not int
        or not 0 < issued < expires <= issued + POLICY_MAX_TTL):
        raise ValueError("POLICY_LIFETIME_INVALID")
    witness = _decode_key(policy["witness_public_key_b64"])
    if _sha(witness) != policy["witness_fingerprint"]:
        raise ValueError("POLICY_WITNESS_FINGERPRINT_MISMATCH")
    return policy


def _decode_key(value: Any) -> bytes:
    if type(value) is not str or not 1 <= len(value) <= 48:
        raise ValueError("PUBLIC_KEY_ENCODING_INVALID")
    try:
        raw = base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("PUBLIC_KEY_ENCODING_INVALID") from exc
    if len(raw) != 32 or base64.b64encode(raw).decode("ascii") != value:
        raise ValueError("PUBLIC_KEY_ENCODING_INVALID")
    return raw


def _decode_signature(value: Any) -> bytes:
    if type(value) is not str or not 1 <= len(value) <= 96:
        raise ValueError("SIGNATURE_ENCODING_INVALID")
    try:
        raw = base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("SIGNATURE_ENCODING_INVALID") from exc
    if len(raw) != 64 or base64.b64encode(raw).decode("ascii") != value:
        raise ValueError("SIGNATURE_ENCODING_INVALID")
    return raw


def host_policy_signing_material(policy: Mapping[str, Any]) -> bytes:
    """For ephemeral CI fixtures only; does not create a trusted anchor."""
    raw = json.dumps(
        dict(policy), sort_keys=True, separators=(",", ":"),
        ensure_ascii=True, allow_nan=False,
    ).encode("utf-8")
    _parse(raw)
    return POLICY_DOMAIN + raw


def verify_anchored_host_policy_and_collector_ceremony(
    policy_raw: bytes,
    authority_signature_b64: str,
    ceremony_proposal_raw: bytes,
    owner_signature_b64: str,
    witness_signature_b64: str,
    proposed_root_pop_signature_b64: str,
    proposed_snapshot_raw: bytes,
    proposed_snapshot_signature_b64: str,
    owner_registry_raw: bytes,
    owner_registry_root_signature_b64: str,
    *,
    # All three must come from a protected source OUTSIDE collector/repository:
    independently_pinned_policy_authority_public_key: bytes,
    expected_policy_authority_fingerprint: str,
    protected_exact_policy_digest: str,
    protected_exact_policy_epoch: int,
    # An independently pinned owner registry root must match signed policy:
    independently_pinned_owner_registry_root_public_key: bytes,
    now: int,
    ceremony_nonce_store: SQLiteCollectorChallengeReplay | None,
) -> dict[str, Any]:
    """Verify authenticity relative to pins, then prepare only; never enroll."""
    try:
        policy = _parse(policy_raw)
    except (ValueError, TypeError, OverflowError):
        return _blocked("HOST_POLICY_MALFORMED")
    if (type(independently_pinned_policy_authority_public_key) is not bytes
        or len(independently_pinned_policy_authority_public_key) != 32
        or type(independently_pinned_owner_registry_root_public_key) is not bytes
        or len(independently_pinned_owner_registry_root_public_key) != 32
        or type(protected_exact_policy_epoch) is not int
        or protected_exact_policy_epoch < 1
        or not _digest(expected_policy_authority_fingerprint)
        or not _digest(protected_exact_policy_digest)
        or type(now) is not int):
        return _blocked("PREEXISTING_HOST_PINS_REQUIRED")
    if _sha(independently_pinned_policy_authority_public_key) != expected_policy_authority_fingerprint:
        return _blocked("HOST_POLICY_AUTHORITY_KEY_UNPINNED")
    if policy["policy_epoch"] != protected_exact_policy_epoch:
        return _blocked("HOST_POLICY_EPOCH_ROLLBACK_OR_MISMATCH")
    current_digest = _sha(POLICY_DOMAIN + policy_raw)
    if current_digest != protected_exact_policy_digest:
        return _blocked("HOST_POLICY_DIGEST_NOT_PROTECTED")
    if not policy["issued_at"] <= now <= policy["expires_at"]:
        return _blocked("HOST_POLICY_STALE")
    if _sha(independently_pinned_owner_registry_root_public_key) != policy["owner_registry_root_fingerprint"]:
        return _blocked("OWNER_REGISTRY_ROOT_NOT_IN_SIGNED_POLICY")
    witness = _decode_key(policy["witness_public_key_b64"])
    if len({
        independently_pinned_policy_authority_public_key,
        independently_pinned_owner_registry_root_public_key,
        witness,
    }) != 3:
        return _blocked("HOST_POLICY_SIGNER_ROLE_COLLISION")
    try:
        Ed25519PublicKey.from_public_bytes(
            independently_pinned_policy_authority_public_key
        ).verify(
            _decode_signature(authority_signature_b64),
            POLICY_DOMAIN + policy_raw,
        )
    except (InvalidSignature, ValueError, TypeError):
        return _blocked("HOST_POLICY_AUTHORITY_SIGNATURE_INVALID")
    result = verify_owner_cosigned_collector_root_ceremony(
        ceremony_proposal_raw,
        owner_signature_b64, witness_signature_b64,
        proposed_root_pop_signature_b64,
        proposed_snapshot_raw, proposed_snapshot_signature_b64,
        owner_registry_raw, owner_registry_root_signature_b64,
        pinned_owner_registry_root_public_key=independently_pinned_owner_registry_root_public_key,
        expected_owner_registry_root_fingerprint=policy["owner_registry_root_fingerprint"],
        expected_owner_registry_id=policy["owner_registry_id"],
        expected_owner_subject=policy["owner_subject"],
        expected_host_issuer=policy["owner_host_issuer"],
        expected_device_id=policy["owner_device_id"],
        expected_device_binding_digest=policy["device_binding_digest"],
        minimum_owner_registry_epoch=policy["minimum_owner_registry_epoch"],
        expected_host_binding_digest=policy["host_binding_digest"],
        expected_collector_id=policy["collector_id"],
        pinned_independent_witness_public_key=witness,
        expected_independent_witness_fingerprint=policy["witness_fingerprint"],
        protected_previous_collector_epoch=policy["protected_collector_epoch"],
        pinned_previous_collector_root_fingerprint=policy["previous_collector_root_fingerprint"],
        independently_observed_collector_binary_digest=policy["approved_collector_binary_digest"],
        independently_observed_collector_manifest_digest=policy["approved_collector_manifest_digest"],
        now=now,
        nonce_store=ceremony_nonce_store,
    )
    if result["state"] != CEREMONY_PREPARED:
        return _blocked("CEREMONY_REJECTED:" + str(result.get("reason", "UNKNOWN")))
    return {
        **_blocked(""),
        "state": STATE,
        "reason": "",
        "authority_signature_valid": True,
        "policy_digest_matches_protected_anchor": True,
        "policy_epoch_matches_protected_anchor": True,
        "ceremony_prepared_cryptographically": True,
        "verified_policy_digest": current_digest,
        "verified_policy_epoch": policy["policy_epoch"],
        "prepared_ceremony_digest": result["proposal_digest"],
    }


__all__ = [
    "SCHEMA", "POLICY_SCHEMA", "POLICY_PURPOSE", "STATE", "POLICY_DOMAIN",
    "host_policy_signing_material",
    "verify_anchored_host_policy_and_collector_ceremony",
]
