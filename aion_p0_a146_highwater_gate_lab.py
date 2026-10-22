"""A146 synthetic high-water witness and fail-closed restart gate (LAB ONLY).

A witness in this module is IN-MEMORY, caller-supplied, and NOT an independently
trusted, durable, or authenticated external authority. No production readiness.
A signed checkpoint can be stale. The high-water must come from a separately
verified, non-rollbackable domain for this protocol to provide real freshness.
"""
from dataclasses import dataclass
import hmac
from threading import Lock

from aion_p0_a145_authenticated_checkpoint_lab import verify_signed_checkpoint
from aion_p0_a145_checkpoint_verifier_lab import CheckpointRejected


class HighWaterRejected(CheckpointRejected):
    pass


@dataclass(frozen=True)
class HighWater:
    ledger_id: str
    sequence: int
    history_digest: str


def _validate(anchor):
    if not isinstance(anchor, HighWater):
        raise HighWaterRejected("missing_or_invalid_highwater")
    if not isinstance(anchor.ledger_id, str) or not anchor.ledger_id:
        raise HighWaterRejected("invalid_highwater_identity")
    if type(anchor.sequence) is not int or anchor.sequence < 0:
        raise HighWaterRejected("invalid_highwater_sequence")
    value = anchor.history_digest
    if not isinstance(value, str) or len(value) != 64 or any(x not in "0123456789abcdef" for x in value):
        raise HighWaterRejected("invalid_highwater_digest")
    return anchor


class SyntheticVolatileWitnessLAB:
    """Volatile in-process CAS simulator. NOT trustworthy anti-rollback storage."""
    def __init__(self):
        self._anchors = {}
        self._lock = Lock()
        self.offline = False

    def publish(self, anchor, *, expected_sequence):
        _validate(anchor)
        with self._lock:
            if self.offline:
                raise HighWaterRejected("witness_unavailable")
            old = self._anchors.get(anchor.ledger_id)
            if old is None:
                if anchor.sequence != 0 or expected_sequence is not None:
                    raise HighWaterRejected("genesis_denied")
            else:
                if type(expected_sequence) is not int or old.sequence != expected_sequence:
                    raise HighWaterRejected("cas_conflict")
                if anchor.sequence == old.sequence:
                    if not hmac.compare_digest(anchor.history_digest, old.history_digest):
                        raise HighWaterRejected("same_sequence_digest_conflict")
                elif anchor.sequence != old.sequence + 1:
                    raise HighWaterRejected("nonmonotonic_or_gap")
            self._anchors[anchor.ledger_id] = anchor
            return True

    def read(self, ledger_id):
        with self._lock:
            if self.offline:
                raise HighWaterRejected("witness_unavailable")
            value = self._anchors.get(ledger_id)
            if value is None:
                raise HighWaterRejected("no_highwater_enrollment")
            return value


def check_restart_gate(*, ledger_id, events, envelope, pinned_keys, read_highwater):
    """Conservative read-only consistency check; NEVER authorizes execution.

    Caller must independently attest read_highwater and its non-rollbackable
    storage. A spoofable callback cannot prove freshness. No implicit rebootstrap,
    automatic resend, external provider calls or cross-system writes.
    """
    if not callable(read_highwater):
        raise HighWaterRejected("witness_reader_missing")
    verify_signed_checkpoint(
        ledger_id=ledger_id, events=events, envelope=envelope, pinned_keys=pinned_keys
    )
    try:
        anchor = _validate(read_highwater(ledger_id))
    except HighWaterRejected:
        raise
    except Exception as exc:
        raise HighWaterRejected("witness_read_failed") from exc
    if not hmac.compare_digest(ledger_id, anchor.ledger_id):
        raise HighWaterRejected("witness_ledger_mismatch")
    sequence = envelope.checkpoint.sequence
    if anchor.sequence > sequence:
        raise HighWaterRejected("signed_checkpoint_rollback")
    if anchor.sequence < sequence:
        # Local durable commit may have happened before external witness ack.
        # The correct answer is UNKNOWN, not automatic repair/resend.
        raise HighWaterRejected("unwitnessed_local_advance")
    if not hmac.compare_digest(anchor.history_digest, envelope.checkpoint.history_digest):
        raise HighWaterRejected("highwater_digest_disagreement")
    return "LAB_READ_ONLY_CONSISTENT_NOT_AUTHORIZED"
