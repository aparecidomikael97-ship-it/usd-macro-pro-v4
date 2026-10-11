"""Offline reference: source-bound checkpoint admission, not production authority.

The trust snapshot MUST originate from an independently authenticated, monotonic
authority outside GitHub, the checkpoint payload, browser and session state.
Constructing this snapshot inside the requesting process is NOT enrollment,
independent custody or antirollback proof. This module neither activates
workers nor fetches a trusted source. Production callers MUST NOT treat a
self-supplied trust snapshot as authority.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Mapping

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

SCHEMA = "AION_CHECKPOINT_SOURCE_BINDING_REF_V1"
WITNESS_SCHEMA = "AION_CHECKPOINT_WITNESS_HEAD_REF_V1"
SOURCE_DOMAIN = b"ATLASQUANT_CHECKPOINT_SOURCE_BINDING_V1\x00"
WITNESS_DOMAIN = b"ATLASQUANT_CHECKPOINT_MONOTONIC_WITNESS_V1\x00"
MAX_EVIDENCE_BYTES = 4096
MAX_AGE_SECONDS = 300
SHA40 = re.compile(r"[0-9a-f]{40}\Z")
REPO = re.compile(r"[A-Za-z0-9_.-]{1,100}/[A-Za-z0-9_.-]{1,100}\Z")
PATH = re.compile(r"[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*\Z")


@dataclass(frozen=True)
class IndependentlyPinnedSource:
    """Reference input, NOT self-authenticating trusted enrollment.

    The floor and observed_at must be supplied by an authenticated *current*
    monotonic witness outside the rollback domain of the GitHub branch.
    """

    owner_id: str
    tenant_id: str
    workspace_id: str
    repo: str
    branch: str
    path: str
    source_key_id: str
    source_public_key: bytes
    witness_key_id: str
    witness_public_key: bytes
    floor_sequence: int
    floor_observed_at: datetime


SOURCE_FIELDS = frozenset({
    "schema", "owner_id", "tenant_id", "workspace_id", "repo", "branch",
    "path", "content_sha", "sequence", "issued_at", "expires_at",
    "key_id", "signature",
})
WITNESS_FIELDS = frozenset({
    "schema", "owner_id", "tenant_id", "workspace_id", "repo", "branch",
    "path", "content_sha", "sequence", "observed_at", "key_id", "signature",
})


def canonical_bytes(record: Mapping[str, Any], *, domain: bytes) -> bytes:
    return domain + json.dumps(
        {k: v for k, v in record.items() if k != "signature"},
        ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False,
    ).encode("ascii")


def _time(value: object) -> datetime:
    if type(value) is not str or len(value) > 40 or not value.endswith("Z"):
        raise ValueError("TIME_FORMAT")
    t = datetime.fromisoformat(value[:-1] + "+00:00")
    if t.tzinfo is None or t.utcoffset() != timedelta(0):
        raise ValueError("TIME_ZONE")
    return t


def _deny(reason: str, *, reader_called: bool = False) -> dict[str, Any]:
    return {
        "status": "BLOCKED",
        "reason": reason,
        "admitted": False,
        "reader_called": reader_called,
        "checkpoint": None,
        "source_trust_production_verified": False,
        "worker_authorized": False,
        "automatic_retry_allowed": False,
    }


def _valid_resource(repo: str, branch: str, path: str) -> bool:
    if not (
        type(repo) is str and REPO.fullmatch(repo)
        and type(branch) is str and branch == "atlasquant-runtime"
        and type(path) is str and PATH.fullmatch(path)
        and len(path) <= 255
    ):
        return False
    return all(piece not in {".", ".."} for piece in path.split("/"))


def _verify_sig(
    evidence: Mapping[str, Any], key: bytes, domain: bytes
) -> None:
    signature = evidence.get("signature")
    if type(signature) is not str or len(signature) != 128:
        raise ValueError("SIGNATURE_FORMAT")
    if any(c not in "0123456789abcdef" for c in signature):
        raise ValueError("SIGNATURE_FORMAT")
    if type(key) is not bytes or len(key) != 32:
        raise ValueError("PIN_INVALID")
    raw = canonical_bytes(evidence, domain=domain)
    if len(raw) > MAX_EVIDENCE_BYTES:
        raise ValueError("OVERSIZE")
    Ed25519PublicKey.from_public_bytes(key).verify(bytes.fromhex(signature), raw)


def verify_source_preflight(
    config: object,
    *,
    source_proof: Mapping[str, Any] | None,
    witness_head: Mapping[str, Any] | None,
    trusted: IndependentlyPinnedSource | None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Verify two independent signatures *before* any checkpoint GET.

    No claim about external independence is made; callers must attest that
    independently and this function never changes production flags.
    """
    if trusted is None:
        return _deny("SOURCE_TRUST_UNAVAILABLE")
    try:
        if not isinstance(trusted, IndependentlyPinnedSource):
            raise ValueError("PIN_INVALID")
        current = now or datetime.now(timezone.utc)
        if not isinstance(current, datetime) or current.tzinfo is None:
            raise ValueError("CLOCK_UNTRUSTED")
        current = current.astimezone(timezone.utc)
        age = (current - trusted.floor_observed_at).total_seconds()
        if (trusted.floor_observed_at.tzinfo is None
            or age < 0 or age > MAX_AGE_SECONDS):
            raise ValueError("MONOTONIC_FLOOR_STALE")
        if type(trusted.floor_sequence) is not int or trusted.floor_sequence < 1:
            raise ValueError("MONOTONIC_FLOOR_INVALID")
        if not _valid_resource(trusted.repo, trusted.branch, trusted.path):
            raise ValueError("RESOURCE_INVALID")
        if not all(
            type(x) is str and 0 < len(x) <= 128 and x.strip() == x
            for x in (
                trusted.owner_id, trusted.tenant_id, trusted.workspace_id,
                trusted.source_key_id, trusted.witness_key_id,
            )
        ):
            raise ValueError("SCOPE_INVALID")
        if (trusted.source_key_id == trusted.witness_key_id
            or trusted.source_public_key == trusted.witness_public_key):
            raise ValueError("WITNESS_NOT_SEPARATE")
        if (
            getattr(config, "repo", None) != trusted.repo
            or getattr(config, "branch", None) != trusted.branch
            or getattr(config, "path", None) != trusted.path
        ):
            raise ValueError("CONFIG_SOURCE_MISMATCH")
        if (not isinstance(source_proof, Mapping)
            or set(source_proof) != SOURCE_FIELDS
            or not isinstance(witness_head, Mapping)
            or set(witness_head) != WITNESS_FIELDS):
            raise ValueError("PROOF_MISSING_OR_AMBIGUOUS")
        shared = {
            "owner_id": trusted.owner_id, "tenant_id": trusted.tenant_id,
            "workspace_id": trusted.workspace_id, "repo": trusted.repo,
            "branch": trusted.branch, "path": trusted.path,
        }
        for row in (source_proof, witness_head):
            if any(type(row.get(k)) is not str or row[k] != v for k, v in shared.items()):
                raise ValueError("SCOPE_MISMATCH")
            if type(row.get("sequence")) is not int or row["sequence"] < trusted.floor_sequence:
                raise ValueError("ROLLBACK_OR_SEQUENCE_INVALID")
            sha = row.get("content_sha")
            if type(sha) is not str or not SHA40.fullmatch(sha):
                raise ValueError("SHA_INVALID")
        if source_proof["sequence"] != witness_head["sequence"]:
            raise ValueError("WITNESS_SEQUENCE_MISMATCH")
        if source_proof["content_sha"] != witness_head["content_sha"]:
            raise ValueError("WITNESS_SHA_MISMATCH")
        if (source_proof["schema"] != SCHEMA
            or source_proof["key_id"] != trusted.source_key_id
            or witness_head["schema"] != WITNESS_SCHEMA
            or witness_head["key_id"] != trusted.witness_key_id):
            raise ValueError("PROOF_IDENTITY_MISMATCH")
        issued = _time(source_proof.get("issued_at"))
        expires = _time(source_proof.get("expires_at"))
        witnessed = _time(witness_head.get("observed_at"))
        if not (
            issued <= current <= expires
            and timedelta(0) < expires - issued <= timedelta(seconds=MAX_AGE_SECONDS)
            and witnessed <= current
            and current - witnessed <= timedelta(seconds=MAX_AGE_SECONDS)
        ):
            raise ValueError("PROOF_EXPIRED_OR_FUTURE")
        _verify_sig(source_proof, trusted.source_public_key, SOURCE_DOMAIN)
        _verify_sig(witness_head, trusted.witness_public_key, WITNESS_DOMAIN)
        return {
            "status": "REFERENCE_VERIFIED",
            "admitted": True,
            "reader_called": False,
            "content_sha": source_proof["content_sha"],
            "sequence": source_proof["sequence"],
            "source_trust_production_verified": False,
            "worker_authorized": False,
            "automatic_retry_allowed": False,
        }
    except Exception as exc:
        # Error details (including any untrusted payloads) are not returned.
        return _deny(type(exc).__name__ if not isinstance(exc, ValueError) else str(exc))


def guarded_checkpoint_reference_read(
    config: object,
    *,
    source_proof: Mapping[str, Any] | None = None,
    witness_head: Mapping[str, Any] | None = None,
    trusted: IndependentlyPinnedSource | None = None,
    reader: Callable[[object], Mapping[str, Any]] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Demonstration wrapper. No production path invokes this yet.

    The caller must provide an independently authenticated trust snapshot and
    safe reader. Passing this reference DOES NOT authorize a Worker tick.
    """
    admission = verify_source_preflight(
        config, source_proof=source_proof,
        witness_head=witness_head, trusted=trusted, now=now,
    )
    if not admission["admitted"]:
        return admission
    if reader is None:
        return _deny("READER_UNAVAILABLE")
    try:
        result = reader(config)
        if not isinstance(result, Mapping):
            return _deny("READ_RESPONSE_INVALID", reader_called=True)
        if (result.get("status") != "CONFIRMED"
            or type(result.get("sha")) is not str
            or result["sha"] != admission["content_sha"]
            or not isinstance(result.get("checkpoint"), Mapping)
            or not isinstance(result.get("integrity"), Mapping)
            or result["integrity"].get("state") != "CONFIRMED"):
            return _deny("READBACK_NOT_BOUND", reader_called=True)
        return {
            "status": "REFERENCE_VERIFIED",
            "admitted": True,
            "reader_called": True,
            "checkpoint": dict(result["checkpoint"]),
            "content_sha": admission["content_sha"],
            "sequence": admission["sequence"],
            "source_trust_production_verified": False,
            "worker_authorized": False,
            "automatic_retry_allowed": False,
        }
    except Exception:
        return _deny("READ_EXCEPTION", reader_called=True)


__all__ = [
    "SCHEMA", "WITNESS_SCHEMA", "SOURCE_DOMAIN", "WITNESS_DOMAIN",
    "IndependentlyPinnedSource", "canonical_bytes",
    "verify_source_preflight", "guarded_checkpoint_reference_read",
]
