"""A211 LAB: compare *claimed* witness checkpoints without accepting authority.

All inputs can be fabricated by a compromised host. Equal snapshots, observer
names, SHA-256-looking values, and a local "owner floor" do NOT establish
independence or cryptographic authenticity. This module performs no I/O and
NEVER authorizes a real-world effect or an Outbox confirmation.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import re
from typing import Any, Mapping


SCHEMA = "ATLASQUANT_AION_WITNESS_CHECKPOINT_DRAFT_V0"
_FIELDS = frozenset({
    "schema", "ledger_id", "owner_root_fingerprint", "sequence",
    "commit_hash", "parent_hash", "subject_digest",
})
_WITNESS_FIELDS = _FIELDS | {"observer_id"}
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_TOKEN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


@dataclass(frozen=True)
class CheckpointCoherence:
    structurally_coherent: bool
    may_confirm: bool
    code: str
    comparison_digest: str


def _deny(code: str) -> CheckpointCoherence:
    return CheckpointCoherence(False, False, code, "")


def _valid(checkpoint: Any, *, observer: bool) -> bool:
    fields = _WITNESS_FIELDS if observer else _FIELDS
    if not isinstance(checkpoint, Mapping) or set(checkpoint) != fields:
        return False
    if checkpoint["schema"] != SCHEMA:
        return False
    for key in ("ledger_id",):
        value = checkpoint[key]
        if not isinstance(value, str) or not _TOKEN.fullmatch(value):
            return False
    if observer:
        value = checkpoint["observer_id"]
        if not isinstance(value, str) or not _TOKEN.fullmatch(value):
            return False
    for key in (
        "owner_root_fingerprint", "commit_hash",
        "parent_hash", "subject_digest",
    ):
        value = checkpoint[key]
        if not isinstance(value, str) or not _HEX64.fullmatch(value):
            return False
    seq = checkpoint["sequence"]
    return type(seq) is int and seq >= 0


def compare_claimed_witness_checkpoints(
    host: Any,
    witness_a: Any,
    witness_b: Any,
    owner_floor: Any,
) -> CheckpointCoherence:
    """Catch some inconsistencies, *never* grant positive trust.

    In a real architecture witnesses must be independently obtained,
    authenticated, and checked against an owner-held antirollback anchor.
    None of those external facts is established by these four inputs.
    """
    if not _valid(host, observer=False) or not _valid(owner_floor, observer=False):
        return _deny("HOST_OR_FLOOR_ENVELOPE_INVALID")
    if not _valid(witness_a, observer=True) or not _valid(witness_b, observer=True):
        return _deny("WITNESS_ENVELOPE_INVALID")
    if witness_a["observer_id"] == witness_b["observer_id"]:
        return _deny("SAME_CLAIMED_OBSERVER")

    checkpoints = (host, witness_a, witness_b, owner_floor)
    if len({cp["ledger_id"] for cp in checkpoints}) != 1:
        return _deny("LEDGER_SCOPE_CONFLICT")
    if len({cp["owner_root_fingerprint"] for cp in checkpoints}) != 1:
        return _deny("OWNER_ROOT_CONFLICT")
    if len({cp["subject_digest"] for cp in checkpoints}) != 1:
        return _deny("SUBJECT_CONFLICT")

    if witness_a["sequence"] != witness_b["sequence"]:
        return _deny("WITNESS_HEIGHT_DISAGREEMENT")
    if (
        witness_a["commit_hash"] != witness_b["commit_hash"]
        or witness_a["parent_hash"] != witness_b["parent_hash"]
    ):
        return _deny("WITNESS_FORK_DETECTED")

    wseq = witness_a["sequence"]
    hseq = host["sequence"]
    fseq = owner_floor["sequence"]
    if hseq < wseq:
        return _deny("HOST_BEHIND_WITNESS")
    if hseq > wseq:
        return _deny("WITNESS_NOT_CAUGHT_UP")
    if host["commit_hash"] != witness_a["commit_hash"]:
        return _deny("HOST_WITNESS_FORK_DETECTED")
    if host["parent_hash"] != witness_a["parent_hash"]:
        return _deny("HOST_PARENT_CONFLICT")
    if hseq < fseq:
        return _deny("OBSERVED_ROLLBACK_BELOW_FLOOR")
    if hseq == fseq and (
        host["commit_hash"] != owner_floor["commit_hash"]
        or host["parent_hash"] != owner_floor["parent_hash"]
    ):
        return _deny("FLOOR_FORK_DETECTED")
    if hseq > fseq + 1:
        return _deny("UNVERIFIED_HISTORY_GAP")
    if hseq == fseq + 1 and host["parent_hash"] != owner_floor["commit_hash"]:
        return _deny("PARENT_CHAIN_BREAK")

    # Comparison commitment only; not signature, attestation, or external
    # evidence. It cannot change may_confirm or allow an Outbox transition.
    canonical = json.dumps(
        {"host": dict(host), "witness_a": dict(witness_a),
         "witness_b": dict(witness_b), "floor": dict(owner_floor)},
        sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")
    return CheckpointCoherence(
        structurally_coherent=True,
        may_confirm=False,
        code="SHAPE_COHERENT_INDEPENDENCE_UNPROVEN",
        comparison_digest=sha256(canonical).hexdigest(),
    )


__all__ = [
    "SCHEMA", "CheckpointCoherence", "compare_claimed_witness_checkpoints",
]
