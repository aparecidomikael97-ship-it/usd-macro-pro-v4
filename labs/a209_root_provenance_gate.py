"""A209 LAB: root-of-trust provenance gate, deliberately deny-only.

This module performs STRUCTURAL checks on a claimed offline root manifest.
It cannot prove an external HUMAN_OWNER ceremony, independent custody,
hardware-protected private key, trusted public root, or monotonic timestamp.

Every result has independently_attested=False and may_confirm=False.
No provider, network, SQLite mutation, secrets or Worker are used.
"""
from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass
from datetime import datetime, timezone
import re
from typing import Any, Mapping

from labs.a208_independent_receipt_preflight import parse_receipt_json


SCHEMA = "ATLASQUANT_AION_ROOT_PROVENANCE_DRAFT_V0"
_FIELDS = frozenset({
    "schema",
    "owner_id",
    "public_root_fingerprint",
    "claimed_origin",
    "ceremony_ref",
    "external_witness_ref",
    "checkpoint_seq",
    "checkpoint_hash",
    "previous_checkpoint_hash",
    "sealed_at",
    "owner_signature_b64",
})
_UNTRUSTED_ORIGINS = frozenset({
    "environment",
    "host_file",
    "host_callback",
    "runtime_generated",
    "local_database",
})
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_TOKEN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,159}$")


@dataclass(frozen=True)
class RootGateDecision:
    structurally_consistent: bool
    independently_attested: bool
    may_confirm: bool
    code: str


def _deny(code: str, *, shape: bool = False) -> RootGateDecision:
    return RootGateDecision(shape, False, False, code)


def _utc(value: Any) -> datetime:
    if isinstance(value, datetime):
        stamp = value
    elif isinstance(value, str):
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    else:
        raise ValueError("unsupported time")
    if stamp.tzinfo is None or stamp.utcoffset() is None:
        raise ValueError("naive time")
    return stamp.astimezone(timezone.utc)


def inspect_claimed_root(
    claim: Any,
    *,
    expected_owner: Any,
    expected_public_root_fingerprint: Any,
    last_checkpoint_sequence: Any,
    observed_at: Any,
) -> RootGateDecision:
    """No amount of self-reported metadata becomes independent attestation."""
    if not isinstance(claim, Mapping) or set(claim) != _FIELDS:
        return _deny("ROOT_ENVELOPE_NOT_EXACT")
    if claim.get("schema") != SCHEMA:
        return _deny("UNSUPPORTED_ROOT_SCHEMA")

    owner = claim.get("owner_id")
    if not isinstance(owner, str) or not _TOKEN.fullmatch(owner):
        return _deny("INVALID_OWNER")
    if not isinstance(expected_owner, str) or not _TOKEN.fullmatch(expected_owner):
        return _deny("UNTRUSTED_OWNER_EXPECTATION")
    if owner != expected_owner:
        return _deny("OWNER_ROOT_SCOPE_MISMATCH")

    root_hash = claim.get("public_root_fingerprint")
    if not isinstance(root_hash, str) or not _HEX64.fullmatch(root_hash):
        return _deny("INVALID_ROOT_FINGERPRINT")
    if not isinstance(expected_public_root_fingerprint, str) or not _HEX64.fullmatch(expected_public_root_fingerprint):
        return _deny("UNTRUSTED_ROOT_EXPECTATION")
    if root_hash != expected_public_root_fingerprint:
        return _deny("ROOT_FINGERPRINT_MISMATCH")

    origin = claim.get("claimed_origin")
    if isinstance(origin, str) and origin in _UNTRUSTED_ORIGINS:
        return _deny("ROOT_SOURCE_CONTROLLED_BY_HOST")
    if origin != "claimed_external_sealed":
        return _deny("ROOT_ORIGIN_UNKNOWN")

    for field in ("ceremony_ref", "external_witness_ref"):
        value = claim.get(field)
        if not isinstance(value, str) or not _TOKEN.fullmatch(value):
            return _deny("INVALID_CEREMONY_OR_WITNESS_REF")

    seq = claim.get("checkpoint_seq")
    if isinstance(seq, bool) or not isinstance(seq, int) or seq < 1:
        return _deny("INVALID_CHECKPOINT_SEQUENCE")
    if isinstance(last_checkpoint_sequence, bool) or not isinstance(last_checkpoint_sequence, int) or last_checkpoint_sequence < 0:
        return _deny("UNTRUSTED_CHECKPOINT_FLOOR")
    if seq <= last_checkpoint_sequence:
        return _deny("STALE_OR_REPLAYED_ROOT_CHECKPOINT")

    for field in ("checkpoint_hash", "previous_checkpoint_hash"):
        value = claim.get(field)
        if not isinstance(value, str) or not _HEX64.fullmatch(value):
            return _deny("INVALID_CHECKPOINT_HASH")

    raw = claim.get("owner_signature_b64")
    if not isinstance(raw, str) or not 1 <= len(raw) <= 8192:
        return _deny("INVALID_OWNER_SIGNATURE_SHAPE")
    try:
        signature_bytes = base64.b64decode(raw, validate=True)
    except (ValueError, binascii.Error):
        return _deny("INVALID_OWNER_SIGNATURE_SHAPE")
    if len(signature_bytes) < 64:
        return _deny("OWNER_SIGNATURE_SHAPE_TOO_SHORT")

    try:
        sealed = _utc(claim.get("sealed_at"))
        observed = _utc(observed_at)
    except (ValueError, TypeError, OverflowError):
        return _deny("INVALID_SEAL_TIME")
    if sealed > observed:
        return _deny("ROOT_SEALED_IN_FUTURE")

    # Syntax alone cannot authenticate who owns the root, who held the
    # signing key, whether the witness is independent, or a rollback.
    return _deny("ROOT_STRUCTURE_OK_PROVENANCE_UNVERIFIED", shape=True)


__all__ = ["SCHEMA", "RootGateDecision", "inspect_claimed_root", "parse_receipt_json"]
