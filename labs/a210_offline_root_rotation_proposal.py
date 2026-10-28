"""A210 LAB: deterministic offline root-rotation PROPOSAL, never activation.

A semantic hash of a proposal is not a HUMAN_OWNER signature, external witness,
antirollback proof or verified custody. The function NEVER activates a new
trust root, NEVER writes, and NEVER touches ExecutionOutbox or providers.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
import re
from typing import Any, Mapping


SCHEMA = "ATLASQUANT_AION_OFFLINE_ROOT_ROTATION_PROPOSAL_DRAFT_V0"
_FIELDS = frozenset({
    "schema",
    "owner_id",
    "ceremony_id",
    "previous_root_fingerprint",
    "proposed_root_fingerprint",
    "parent_checkpoint_hash",
    "next_checkpoint_sequence",
    "nonce_hex",
    "owner_intent_digest",
    "witness_ref",
    "requested_at",
})
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_TOKEN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


@dataclass(frozen=True)
class RotationProposalPreflight:
    structurally_valid: bool
    may_rotate: bool
    code: str
    proposal_digest: str


def _deny(code: str) -> RotationProposalPreflight:
    return RotationProposalPreflight(False, False, code, "")


def _utc(value: Any) -> datetime:
    if isinstance(value, datetime):
        stamp = value
    elif isinstance(value, str):
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    else:
        raise ValueError("unsupported timestamp")
    if stamp.tzinfo is None or stamp.utcoffset() is None:
        raise ValueError("timestamp must be timezone aware")
    return stamp.astimezone(timezone.utc)


def preflight_rotation_proposal(
    proposal: Any,
    *,
    expected_owner: Any,
    current_root_fingerprint: Any,
    current_checkpoint_hash: Any,
    current_checkpoint_sequence: Any,
    seen_nonces: Any,
    previous_anchor_at: Any,
    observed_at: Any,
) -> RotationProposalPreflight:
    """Validate proposal semantics, not independent owner authorization."""
    if not isinstance(proposal, Mapping) or set(proposal) != _FIELDS:
        return _deny("ROTATION_ENVELOPE_NOT_EXACT")
    if proposal.get("schema") != SCHEMA:
        return _deny("UNSUPPORTED_ROTATION_SCHEMA")

    owner = proposal.get("owner_id")
    if not isinstance(owner, str) or not _TOKEN.fullmatch(owner):
        return _deny("INVALID_OWNER")
    if not isinstance(expected_owner, str) or not _TOKEN.fullmatch(expected_owner):
        return _deny("UNTRUSTED_OWNER_EXPECTATION")
    if owner != expected_owner:
        return _deny("ROTATION_OWNER_MISMATCH")

    for field in ("ceremony_id", "witness_ref"):
        value = proposal.get(field)
        if not isinstance(value, str) or not _TOKEN.fullmatch(value):
            return _deny("INVALID_CEREMONY_OR_WITNESS_REF")

    old = proposal.get("previous_root_fingerprint")
    new = proposal.get("proposed_root_fingerprint")
    if not isinstance(old, str) or not _HEX64.fullmatch(old):
        return _deny("INVALID_PREVIOUS_ROOT")
    if not isinstance(new, str) or not _HEX64.fullmatch(new):
        return _deny("INVALID_PROPOSED_ROOT")
    if not isinstance(current_root_fingerprint, str) or not _HEX64.fullmatch(current_root_fingerprint):
        return _deny("UNTRUSTED_CURRENT_ROOT")
    if old != current_root_fingerprint:
        return _deny("OLD_ROOT_PIN_MISMATCH")
    if old == new:
        return _deny("ROTATION_REUSES_SAME_ROOT")

    parent = proposal.get("parent_checkpoint_hash")
    if not isinstance(parent, str) or not _HEX64.fullmatch(parent):
        return _deny("INVALID_PARENT_CHECKPOINT_HASH")
    if not isinstance(current_checkpoint_hash, str) or not _HEX64.fullmatch(current_checkpoint_hash):
        return _deny("UNTRUSTED_PARENT_CHECKPOINT")
    if parent != current_checkpoint_hash:
        return _deny("PARENT_CHECKPOINT_MISMATCH")

    seq = proposal.get("next_checkpoint_sequence")
    if isinstance(seq, bool) or not isinstance(seq, int) or seq < 1:
        return _deny("INVALID_NEXT_SEQUENCE")
    if isinstance(current_checkpoint_sequence, bool) or not isinstance(current_checkpoint_sequence, int) or current_checkpoint_sequence < 0:
        return _deny("UNTRUSTED_SEQUENCE_ANCHOR")
    if seq != current_checkpoint_sequence + 1:
        return _deny("ROTATION_SEQUENCE_REPLAY_OR_SKIP")

    nonce = proposal.get("nonce_hex")
    intent = proposal.get("owner_intent_digest")
    if not isinstance(nonce, str) or not _HEX64.fullmatch(nonce):
        return _deny("INVALID_CEREMONY_NONCE")
    if not isinstance(intent, str) or not _HEX64.fullmatch(intent):
        return _deny("INVALID_OWNER_INTENT_DIGEST")
    if not isinstance(seen_nonces, (list, tuple, set, frozenset)) or any(
        not isinstance(item, str) or not _HEX64.fullmatch(item) for item in seen_nonces
    ):
        return _deny("UNTRUSTED_NONCE_HISTORY")
    if nonce in seen_nonces:
        return _deny("CEREMONY_NONCE_REPLAY")

    try:
        requested = _utc(proposal.get("requested_at"))
        anchor = _utc(previous_anchor_at)
        observed = _utc(observed_at)
    except (ValueError, OverflowError, TypeError):
        return _deny("INVALID_CEREMONY_TIME")
    if not anchor <= requested <= observed:
        return _deny("CEREMONY_TIME_OUTSIDE_ANCHOR")

    canonical = json.dumps(
        dict(proposal), sort_keys=True, ensure_ascii=False,
        separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")
    commitment = sha256(canonical).hexdigest()
    return RotationProposalPreflight(
        True, False, "PROPOSAL_SHAPE_OK_EXTERNAL_OWNER_APPROVAL_MISSING",
        commitment,
    )


__all__ = ["SCHEMA", "RotationProposalPreflight", "preflight_rotation_proposal"]
