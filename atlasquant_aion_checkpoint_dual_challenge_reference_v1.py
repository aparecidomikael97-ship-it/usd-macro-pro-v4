"""AION dual-domain challenge READ verification — offline reference, NO AUTHORITY.

Mathematically binds one synthetic checkpoint source signature and TWO
separately signed challenge responses to the exact owner/tenant/resource,
epoch, sequence, content SHA, and fresh 256-bit nonce.

All public keys, heads, floor and nonce are supplied by the same test/caller.
This is NEVER a proof of independent enrollment, provider custody, current
remote head, protected antirollback, or permission to run the Global Worker.
Do not wire this reference to any production approval gate.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping

from atlasquant_aion_runtime_source_boundary_ref_v1 import (
    SCHEMA as SOURCE_SCHEMA,
    SOURCE_DOMAIN,
    SOURCE_FIELDS,
    _verify_sig,
    _time,
    _valid_resource,
)

SCHEMA = "AION_CHECKPOINT_DUAL_DOMAIN_CHALLENGE_REF_V1"
COORDINATOR_SCHEMA = "AION_CAS_COORDINATOR_CHALLENGE_READ_V1"
ANCHOR_SCHEMA = "AION_INDEPENDENT_ANCHOR_CHALLENGE_READ_V1"
COORDINATOR_DOMAIN = b"ATLASQUANT_AION_COORDINATOR_CHALLENGE_V1\x00"
ANCHOR_DOMAIN = b"ATLASQUANT_AION_SECOND_DOMAIN_CHALLENGE_V1\x00"
NONCE_RE = re.compile(r"[0-9a-f]{64}\Z")
SHA_RE = re.compile(r"[0-9a-f]{40}\Z")
MAX_RESPONSE_AGE_SECONDS = 60
MAX_CLOCK_SKEW_SECONDS = 5
HEAD_FIELDS = frozenset({
    "schema", "owner_id", "tenant_id", "workspace_id",
    "repo", "branch", "path", "content_sha",
    "epoch", "sequence", "challenge_nonce",
    "observed_at", "key_id", "signature",
})

@dataclass(frozen=True)
class ReferencePins:
    """Untrusted in-memory sample, NOT an enrolled/independently held root."""
    owner_id: str
    tenant_id: str
    workspace_id: str
    repo: str
    branch: str
    path: str
    source_key_id: str
    source_public_key: bytes
    coordinator_key_id: str
    coordinator_public_key: bytes
    anchor_key_id: str
    anchor_public_key: bytes
    minimum_epoch: int
    minimum_sequence: int

def _result(reason: str, *, mathematical_match: bool = False) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "status": "REFERENCE_MATCH_UNTRUSTED" if mathematical_match else "BLOCKED",
        "reason": reason,
        "mathematical_match": mathematical_match,
        "checkpoint": None,
        "reader_called": False,
        "source_trust_production_verified": False,
        "coordinator_custody_verified": False,
        "anchor_custody_verified": False,
        "freshness_independently_verified": False,
        "latest_head_independently_verified": False,
        "rollback_protection_production_verified": False,
        "worker_authorized": False,
        "automatic_retry_allowed": False,
        "spending_approved": False,
        "deployment_authorized": False,
    }

def review_challenge_bound_dual_head(
    *,
    config: object,
    pins: ReferencePins | None,
    source_proof: Mapping[str, Any] | None,
    coordinator_head: Mapping[str, Any] | None,
    second_domain_head: Mapping[str, Any] | None,
    challenge_nonce: str,
    now: datetime,
) -> dict[str, Any]:
    """Closed-schema/Ed25519 *mathematical* review, without I/O or permission.

    Critically, a caller can substitute all pins and two fresh signed heads;
    verifying this function cannot establish independent domains.
    """
    if pins is None:
        return _result("SOURCE_ENROLLMENT_ABSENT")
    try:
        if not isinstance(pins, ReferencePins):
            raise ValueError("PINS_TYPE_INVALID")
        if type(challenge_nonce) is not str or not NONCE_RE.fullmatch(challenge_nonce):
            raise ValueError("CHALLENGE_INVALID")
        if type(now) is not datetime or now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("CLOCK_INVALID")
        current = now.astimezone(timezone.utc)
        if not _valid_resource(pins.repo, pins.branch, pins.path):
            raise ValueError("RESOURCE_INVALID")
        binding = {k: getattr(pins, k) for k in (
            "owner_id", "tenant_id", "workspace_id", "repo", "branch", "path",
        )}
        if not all(type(v) is str and 0 < len(v) <= 128 and v.strip() == v
                   for k, v in binding.items() if k not in ("repo", "branch", "path")):
            raise ValueError("SCOPE_INVALID")
        if (getattr(config, "repo", None) != pins.repo
            or getattr(config, "branch", None) != pins.branch
            or getattr(config, "path", None) != pins.path):
            raise ValueError("CONFIG_BINDING_MISMATCH")
        if (type(pins.minimum_epoch) is not int or pins.minimum_epoch < 1
            or type(pins.minimum_sequence) is not int or pins.minimum_sequence < 1):
            raise ValueError("FLOOR_INVALID")
        key_ids = (pins.source_key_id, pins.coordinator_key_id, pins.anchor_key_id)
        keys = (pins.source_public_key, pins.coordinator_public_key, pins.anchor_public_key)
        if (not all(type(k) is str and 0 < len(k) <= 128 for k in key_ids)
            or len(set(key_ids)) != 3 or len(set(keys)) != 3
            or not all(type(key) is bytes and len(key) == 32 for key in keys)):
            raise ValueError("KEY_CUSTODY_NOT_DISTINCT")
        if (not isinstance(source_proof, Mapping) or set(source_proof) != SOURCE_FIELDS
            or not isinstance(coordinator_head, Mapping) or set(coordinator_head) != HEAD_FIELDS
            or not isinstance(second_domain_head, Mapping) or set(second_domain_head) != HEAD_FIELDS):
            raise ValueError("EVIDENCE_SCHEMA_INVALID")
        if (source_proof.get("schema") != SOURCE_SCHEMA
            or source_proof.get("key_id") != pins.source_key_id):
            raise ValueError("SOURCE_IDENTITY_INVALID")
        if not all(
            type(source_proof.get(k)) is str and source_proof[k] == expected
            for k, expected in binding.items()
        ):
            raise ValueError("SOURCE_BINDING_INVALID")
        issued = _time(source_proof.get("issued_at"))
        expiry = _time(source_proof.get("expires_at"))
        if not (issued <= current <= expiry and expiry - issued <= timedelta(minutes=5)):
            raise ValueError("SOURCE_EXPIRED")
        sequence = source_proof.get("sequence")
        sha = source_proof.get("content_sha")
        if type(sequence) is not int or sequence < pins.minimum_sequence:
            raise ValueError("SEQUENCE_ROLLBACK")
        if type(sha) is not str or not SHA_RE.fullmatch(sha):
            raise ValueError("CONTENT_SHA_INVALID")
        for head, schema, key_id, key, domain in (
            (coordinator_head, COORDINATOR_SCHEMA, pins.coordinator_key_id,
             pins.coordinator_public_key, COORDINATOR_DOMAIN),
            (second_domain_head, ANCHOR_SCHEMA, pins.anchor_key_id,
             pins.anchor_public_key, ANCHOR_DOMAIN),
        ):
            if head.get("schema") != schema or head.get("key_id") != key_id:
                raise ValueError("HEAD_IDENTITY_INVALID")
            if not all(type(head.get(k)) is str and head[k] == value
                       for k, value in binding.items()):
                raise ValueError("HEAD_SCOPE_INVALID")
            if (head.get("challenge_nonce") != challenge_nonce
                or type(head.get("challenge_nonce")) is not str):
                raise ValueError("CHALLENGE_REPLAY_OR_MISMATCH")
            if (type(head.get("epoch")) is not int or head["epoch"] < pins.minimum_epoch
                or type(head.get("sequence")) is not int
                or head["sequence"] != sequence):
                raise ValueError("HEAD_EPOCH_SEQUENCE_MISMATCH")
            if type(head.get("content_sha")) is not str or head["content_sha"] != sha:
                raise ValueError("HEAD_SHA_MISMATCH")
            observed = _time(head.get("observed_at"))
            if (observed - current).total_seconds() > MAX_CLOCK_SKEW_SECONDS:
                raise ValueError("FUTURE_WITNESS_RESPONSE")
            if (current - observed).total_seconds() > MAX_RESPONSE_AGE_SECONDS:
                raise ValueError("STALE_WITNESS_RESPONSE")
            _verify_sig(head, key, domain)
        if coordinator_head["epoch"] != second_domain_head["epoch"]:
            raise ValueError("DOMAIN_EPOCH_FORK")
        _verify_sig(source_proof, pins.source_public_key, SOURCE_DOMAIN)
        return _result("TWO_SIGNATURES_MATCH_MATH_ONLY_NOT_AUTHORITY",
                       mathematical_match=True)
    except Exception as exc:
        # Expose only a bounded error class; never reflect payload/token.
        return _result(str(exc) if type(exc) is ValueError else type(exc).__name__)

__all__ = [
    "SCHEMA", "COORDINATOR_SCHEMA", "ANCHOR_SCHEMA",
    "COORDINATOR_DOMAIN", "ANCHOR_DOMAIN", "HEAD_FIELDS",
    "ReferencePins", "review_challenge_bound_dual_head",
]
