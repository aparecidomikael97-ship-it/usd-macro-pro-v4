"""A145 experimental fail-closed checkpoint comparison.

The caller supplies a trusted, independently authenticated checkpoint.
This module does NOT authenticate the witness, guarantee its freshness,
or establish independent storage. Never use it for production authorization.
"""
from dataclasses import dataclass
import hashlib
import hmac
import json


class CheckpointRejected(RuntimeError):
    pass


@dataclass(frozen=True)
class Checkpoint:
    ledger_id: str
    sequence: int
    history_digest: str


def canonical_history_digest(events):
    payload = json.dumps(events, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def verify_checkpoint(*, ledger_id, events, witness):
    """Fail closed when witness is missing or does not match local state.

    WARNING: witness authenticity, anti-rollback and independence are
    preconditions outside this function, not properties it proves.
    """
    if witness is None or not isinstance(witness, Checkpoint):
        raise CheckpointRejected("missing_or_untrusted_witness")
    if not isinstance(ledger_id, str) or not ledger_id:
        raise CheckpointRejected("invalid_ledger_identity")
    if not isinstance(witness.ledger_id, str) or not witness.ledger_id:
        raise CheckpointRejected("invalid_witness_identity")
    if not hmac.compare_digest(ledger_id, witness.ledger_id):
        raise CheckpointRejected("ledger_identity_mismatch")
    if not isinstance(witness.sequence, int) or isinstance(witness.sequence, bool) or witness.sequence < 0:
        raise CheckpointRejected("invalid_witness_sequence")
    if not isinstance(events, list):
        raise CheckpointRejected("invalid_history")
    if any(not isinstance(e, dict) or type(e.get("seq")) is not int for e in events):
        raise CheckpointRejected("invalid_event")
    sequences = [e["seq"] for e in events]
    if sequences != list(range(1, len(events) + 1)):
        raise CheckpointRejected("non_contiguous_history")
    if len(events) != witness.sequence:
        raise CheckpointRejected("history_sequence_mismatch")
    try:
        actual = canonical_history_digest(events)
    except (TypeError, ValueError, OverflowError, RecursionError) as exc:
        raise CheckpointRejected("noncanonical_history") from exc
    if (not isinstance(witness.history_digest, str) or len(witness.history_digest) != 64
            or any(c not in "0123456789abcdef" for c in witness.history_digest)):
        raise CheckpointRejected("invalid_witness_digest")
    if not hmac.compare_digest(actual, witness.history_digest):
        raise CheckpointRejected("history_digest_mismatch")
    return True
