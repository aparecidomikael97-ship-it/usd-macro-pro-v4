"""AION offline collector-root enrollment CEREMONY PREFLIGHT — synthetic CI only.

Rooted HUMAN_OWNER intent + independently pinned witness + proposed root
proof-of-possession + signed proposed collector snapshot, all exact-bound.
This DOES NOT enroll, activate, write host policy, or verify physical custody.
Host policy arguments must come from independently protected configuration.
"""
from __future__ import annotations

import base64
import hashlib
import re
from typing import Any, Mapping

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from atlasquant_aion_rooted_owner_signed_binary_preflight_ci_v1 import _verify_registry
from atlasquant_aion_rooted_collector_raw_evidence_preflight_v1 import (
    _b64, _check_enrollment, _digest, _strict_json, ENROLL_DOMAIN,
    SQLiteCollectorChallengeReplay,
)

SCHEMA = "AION_OWNER_WITNESS_COLLECTOR_ROOT_CEREMONY_V1"
PURPOSE = "PREPARE_ONLY_NO_ACTIVATION"
STATE = "OWNER_COSIGNED_COLLECTOR_ROOT_PREPARED_UNTRUSTED"
DOMAIN = b"ATLASQUANT:AION:COLLECTOR_ROOT_CEREMONY:V1\x00"
POP_DOMAIN = b"ATLASQUANT:AION:COLLECTOR_ROOT_PROOF_OF_POSSESSION:V1\x00"
REPLAY_DOMAIN = b"ATLASQUANT:AION:COLLECTOR_ROOT_CEREMONY_NONCE:V1\x00"
MAX_BYTES = 6144
MAX_TTL = 120
_HEX64 = re.compile(r"[0-9a-f]{64}\Z")
_SHA = re.compile(r"sha256:[0-9a-f]{64}\Z")
_TAG = re.compile(r"[A-Za-z0-9._:-]{1,96}\Z")
_FIELDS = frozenset({
    "schema", "purpose", "mode", "owner_registry_digest",
    "owner_key_id", "host_binding_digest", "device_binding_digest",
    "registry_id", "host_issuer", "collector_id", "collector_epoch",
    "protected_previous_epoch", "prior_root_fingerprint",
    "proposed_root_public_key_b64", "proposed_root_fingerprint",
    "witness_fingerprint", "collector_binary_digest",
    "collector_manifest_digest", "proposed_snapshot_digest",
    "challenge_nonce", "issued_at", "expires_at",
})


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "BLOCKED", "reason": reason,
        "rooted_owner_signature_checked": False,
        "independent_witness_signature_checked": False,
        "proposed_root_proof_of_possession_checked": False,
        "proposed_snapshot_signature_checked": False,
        "nonce_consumed": False,
        "physical_root_custody_verified": False,
        "trusted_host_policy_mutated": False,
        "root_enrolled_in_production": False,
        "collector_enrolled_in_production": False,
        "collector_launch_authorized": False,
        "physical_attestation_verified": False,
        "network_deny_verified": False,
        "installer_authorized": False,
        "build_authorized": False, "deploy_authorized": False,
        "safe_to_resume": False,
    }


def _valid_sha(v: Any) -> bool:
    return type(v) is str and bool(_SHA.fullmatch(v))


def _valid_tag(v: Any) -> bool:
    return type(v) is str and bool(_TAG.fullmatch(v))


def _check_proposal(raw: bytes, *, now: int) -> dict[str, Any]:
    row = _strict_json(raw, maximum=MAX_BYTES)
    if set(row) != _FIELDS or row["schema"] != SCHEMA or row["purpose"] != PURPOSE:
        raise ValueError("CEREMONY_SCHEMA_OR_FIELDS_INVALID")
    for field in ("owner_registry_digest", "host_binding_digest",
                  "device_binding_digest", "proposed_root_fingerprint",
                  "witness_fingerprint", "collector_binary_digest",
                  "collector_manifest_digest", "proposed_snapshot_digest"):
        if not _valid_sha(row[field]):
            raise ValueError("CEREMONY_DIGEST_INVALID")
    for field in ("owner_key_id", "registry_id", "host_issuer", "collector_id"):
        if not _valid_tag(row[field]):
            raise ValueError("CEREMONY_IDENTITY_INVALID")
    if (type(row["challenge_nonce"]) is not str or
        not _HEX64.fullmatch(row["challenge_nonce"])):
        raise ValueError("CEREMONY_NONCE_INVALID")
    prev, new, issued, expires = (
        row["protected_previous_epoch"], row["collector_epoch"],
        row["issued_at"], row["expires_at"],
    )
    if (type(prev) is not int or prev < 0 or type(new) is not int
        or new != prev + 1 or type(issued) is not int
        or type(expires) is not int or type(now) is not int
        or not 0 < issued <= now <= expires <= issued + MAX_TTL):
        raise ValueError("CEREMONY_EPOCH_OR_WINDOW_INVALID")
    if row["mode"] == "INITIAL_ENROLLMENT":
        if prev != 0 or row["prior_root_fingerprint"] is not None:
            raise ValueError("INITIAL_ENROLLMENT_POLICY_INVALID")
    elif row["mode"] == "ROTATION":
        if prev < 1 or not _valid_sha(row["prior_root_fingerprint"]):
            raise ValueError("ROTATION_POLICY_INVALID")
    else:
        raise ValueError("CEREMONY_MODE_INVALID")
    proposed = _b64(row["proposed_root_public_key_b64"], 32)
    if _digest(proposed) != row["proposed_root_fingerprint"]:
        raise ValueError("PROPOSED_ROOT_FINGERPRINT_MISMATCH")
    return row


def proposal_signing_material(proposal: Mapping[str, Any], *, now: int) -> bytes:
    """For ephemeral CI signing. Accepts no registry/policy writes."""
    import json
    raw = json.dumps(dict(proposal), sort_keys=True, separators=(",", ":"),
                     ensure_ascii=True, allow_nan=False).encode("utf-8")
    _check_proposal(raw, now=now)
    return DOMAIN + raw


def verify_owner_cosigned_collector_root_ceremony(
    proposal_raw: bytes,
    owner_signature_b64: str, witness_signature_b64: str,
    proposed_root_pop_signature_b64: str,
    proposed_snapshot_raw: bytes, proposed_snapshot_signature_b64: str,
    owner_registry_raw: bytes, owner_registry_root_signature_b64: str, *,
    pinned_owner_registry_root_public_key: bytes,
    expected_owner_registry_root_fingerprint: str,
    expected_owner_registry_id: str,
    expected_owner_subject: str, expected_host_issuer: str,
    expected_device_id: str, expected_device_binding_digest: str,
    minimum_owner_registry_epoch: int,
    expected_host_binding_digest: str,
    expected_collector_id: str,
    pinned_independent_witness_public_key: bytes,
    expected_independent_witness_fingerprint: str,
    protected_previous_collector_epoch: int,
    pinned_previous_collector_root_fingerprint: str | None,
    independently_observed_collector_binary_digest: str,
    independently_observed_collector_manifest_digest: str,
    now: int,
    nonce_store: SQLiteCollectorChallengeReplay | None,
) -> dict[str, Any]:
    """Read-only PREPARE gate; never upgrades a proposed root to trusted state."""
    try:
        proposal = _check_proposal(proposal_raw, now=now)
    except (ValueError, TypeError, OverflowError):
        return _blocked("CEREMONY_MALFORMED")
    if (type(protected_previous_collector_epoch) is not int
        or protected_previous_collector_epoch < 0
        or type(pinned_independent_witness_public_key) is not bytes
        or len(pinned_independent_witness_public_key) != 32
        or not all(_valid_sha(v) for v in (
            expected_host_binding_digest, expected_device_binding_digest,
            expected_independent_witness_fingerprint,
            independently_observed_collector_binary_digest,
            independently_observed_collector_manifest_digest,
        )) or not _valid_tag(expected_collector_id)
        or _digest(pinned_independent_witness_public_key)
              != expected_independent_witness_fingerprint):
        return _blocked("INDEPENDENT_HOST_POLICY_MISSING")
    if protected_previous_collector_epoch == 0:
        if pinned_previous_collector_root_fingerprint is not None:
            return _blocked("BOOTSTRAP_PREVIOUS_ROOT_MISMATCH")
    elif not _valid_sha(pinned_previous_collector_root_fingerprint):
        return _blocked("PROTECTED_ROTATION_ROOT_MISSING")
    if (proposal["protected_previous_epoch"] != protected_previous_collector_epoch
        or proposal["collector_epoch"] != protected_previous_collector_epoch + 1
        or proposal["prior_root_fingerprint"] != pinned_previous_collector_root_fingerprint
        or proposal["host_binding_digest"] != expected_host_binding_digest
        or proposal["device_binding_digest"] != expected_device_binding_digest
        or proposal["registry_id"] != expected_owner_registry_id
        or proposal["host_issuer"] != expected_host_issuer
        or proposal["collector_id"] != expected_collector_id
        or proposal["witness_fingerprint"] != expected_independent_witness_fingerprint
        or proposal["collector_binary_digest"]
              != independently_observed_collector_binary_digest
        or proposal["collector_manifest_digest"]
              != independently_observed_collector_manifest_digest):
        return _blocked("PROPOSAL_NOT_EQUAL_INDEPENDENT_HOST_POLICY")

    owner, owner_reason = _verify_registry(
        owner_registry_raw, owner_registry_root_signature_b64,
        pinned_root_public_key=pinned_owner_registry_root_public_key,
        expected_root_fingerprint=expected_owner_registry_root_fingerprint,
        expected_registry_id=expected_owner_registry_id,
        expected_owner_subject=expected_owner_subject,
        expected_host_issuer=expected_host_issuer,
        expected_device_id=expected_device_id,
        expected_device_binding_digest=expected_device_binding_digest,
        minimum_registry_epoch=minimum_owner_registry_epoch,
        now=now,
    )
    if owner is None:
        return _blocked("PREEXISTING_OWNER_TRUST_FAILED:" + owner_reason)
    if (proposal["owner_registry_digest"] != owner["registry_digest"]
        or proposal["owner_key_id"] != owner["owner_key_id"]):
        return _blocked("PROPOSAL_NOT_BOUND_TO_ACTIVE_OWNER")
    proposed_root = _b64(proposal["proposed_root_public_key_b64"], 32)
    if (len({proposed_root, owner["owner_public_key"],
             pinned_independent_witness_public_key,
             pinned_owner_registry_root_public_key}) != 4):
        return _blocked("SEPARATE_SIGNER_ROLES_REQUIRED")
    if (pinned_previous_collector_root_fingerprint is not None
        and proposal["proposed_root_fingerprint"]
              == pinned_previous_collector_root_fingerprint):
        return _blocked("ROOT_ROTATION_REUSES_OLD_KEY")

    try:
        snapshot = _check_enrollment(proposed_snapshot_raw)
    except (ValueError, TypeError, OverflowError):
        return _blocked("PROPOSED_COLLECTOR_SNAPSHOT_INVALID")
    if (snapshot["registry_id"] != proposal["registry_id"]
        or snapshot["host_issuer"] != proposal["host_issuer"]
        or snapshot["host_binding_digest"] != proposal["host_binding_digest"]
        or snapshot["device_binding_digest"] != proposal["device_binding_digest"]
        or snapshot["epoch"] != proposal["collector_epoch"]
        or snapshot["collector"]["collector_id"] != proposal["collector_id"]
        or snapshot["collector"]["manifest_digest"]
            != proposal["collector_manifest_digest"]
        or snapshot["collector"]["binary_digest"]
            != proposal["collector_binary_digest"]
        or snapshot["collector"]["revoked_epoch"] is not None
        or not snapshot["issued_at"] <= now <= snapshot["expires_at"]
        or _digest(proposed_snapshot_raw) != proposal["proposed_snapshot_digest"]):
        return _blocked("PROPOSED_SNAPSHOT_MISMATCH")
    if snapshot["collector"]["enrolled_epoch"] != proposal["collector_epoch"]:
        return _blocked("PROPOSED_SNAPSHOT_ENROLLMENT_EPOCH_MISMATCH")
    if _b64(snapshot["collector"]["public_key_b64"], 32) in {
        proposed_root, owner["owner_public_key"], pinned_independent_witness_public_key,
    }:
        return _blocked("COLLECTOR_SIGNER_ROLE_REUSE")

    try:
        owner_sig = _b64(owner_signature_b64, 64)
        witness_sig = _b64(witness_signature_b64, 64)
        root_pop_sig = _b64(proposed_root_pop_signature_b64, 64)
        snapshot_sig = _b64(proposed_snapshot_signature_b64, 64)
        Ed25519PublicKey.from_public_bytes(owner["owner_public_key"]).verify(
            owner_sig, DOMAIN + proposal_raw)
    except (InvalidSignature, ValueError, TypeError):
        return _blocked("ROOTED_OWNER_APPROVAL_SIGNATURE_INVALID")
    try:
        Ed25519PublicKey.from_public_bytes(
            pinned_independent_witness_public_key).verify(
                witness_sig, DOMAIN + proposal_raw)
    except (InvalidSignature, ValueError, TypeError):
        return _blocked("INDEPENDENT_WITNESS_SIGNATURE_INVALID")
    try:
        Ed25519PublicKey.from_public_bytes(proposed_root).verify(
            root_pop_sig, POP_DOMAIN + proposal_raw)
        Ed25519PublicKey.from_public_bytes(proposed_root).verify(
            snapshot_sig, ENROLL_DOMAIN + proposed_snapshot_raw)
    except (InvalidSignature, ValueError, TypeError):
        return _blocked("PROPOSED_ROOT_PROOF_OR_SNAPSHOT_SIGNATURE_INVALID")
    if not isinstance(nonce_store, SQLiteCollectorChallengeReplay):
        return _blocked("DURABLE_CEREMONY_REPLAY_REQUIRED")
    nonce_key = _digest(
        REPLAY_DOMAIN + bytes.fromhex(proposal["challenge_nonce"]))
    if not nonce_store.consume_once(nonce_key, proposal["expires_at"], now):
        return _blocked("CEREMONY_NONCE_REPLAY_OR_STORE_FAILURE")
    return {
        **_blocked(""),
        "state": STATE, "reason": "",
        "rooted_owner_signature_checked": True,
        "independent_witness_signature_checked": True,
        "proposed_root_proof_of_possession_checked": True,
        "proposed_snapshot_signature_checked": True,
        "nonce_consumed": True,
        "proposal_digest": _digest(DOMAIN + proposal_raw),
        "snapshot_digest": _digest(proposed_snapshot_raw),
        "proposed_root_fingerprint": proposal["proposed_root_fingerprint"],
        "collector_epoch": proposal["collector_epoch"],
    }


__all__ = [
    "SCHEMA", "PURPOSE", "STATE", "DOMAIN", "POP_DOMAIN",
    "proposal_signing_material", "verify_owner_cosigned_collector_root_ceremony",
]
