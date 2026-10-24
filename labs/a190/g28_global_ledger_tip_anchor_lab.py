"""G28 — global ledger-tip external-anchor *contract*, synthetic LAB only.

The anchor is separate only as an in-process Python object. The key, state
and proof are synthetic. Host compromise, anchor rollback, malicious writer,
external durability, authorization and atomic cross-system reservation are NOT
solved. This code never permits provider send/retry.
"""
from dataclasses import dataclass
import hashlib
import json
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

from g20_independent_witness_recovery_contract_lab import Admission, RecoveryDenied
from g24_challenge_bound_witness_lab import new_challenge


@dataclass(frozen=True)
class GlobalTip:
    sequence: int
    record_count: int
    ledger_digest: str


@dataclass(frozen=True)
class SignedGlobalTip:
    tip: GlobalTip
    challenge: bytes
    trust_root_id: str
    signature: bytes


def read_local_tip(custody) -> GlobalTip:
    """Snapshot of all semantic reservations, not just requested key."""
    # Serialized only for the test harness. A production schema must guarantee
    # that this snapshot is atomic with writers (BEGIN read transaction).
    rows = custody._db.execute(
        "SELECT sequence,semantic_key,phase,journal_digest "
        "FROM custody_records ORDER BY sequence"
    ).fetchall()
    canonical = json.dumps(
        [list(row) for row in rows],
        ensure_ascii=False, separators=(",", ":"),
    ).encode("utf-8")
    return GlobalTip(
        sequence=rows[-1][0] if rows else 0,
        record_count=len(rows),
        ledger_digest=hashlib.sha256(canonical).hexdigest(),
    )


def canonical_tip_response(tip: GlobalTip, challenge: bytes, root: str) -> bytes:
    if not isinstance(challenge, bytes) or len(challenge) != 32:
        raise ValueError("G28_INVALID_NONCE")
    data = {
        "domain": "AION-A190-G28-GLOBAL-LEDGER-TIP-LAB-V1",
        "sequence": tip.sequence,
        "record_count": tip.record_count,
        "ledger_digest": tip.ledger_digest,
        "challenge": challenge.hex(),
        "trust_root_id": root,
    }
    return json.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")


class SimulatedExternalAnchor:
    """Mutable and rollback-capable LAB object; NOT true external custody."""
    def __init__(self, signing_key: Ed25519PrivateKey, root_id: str):
        self.__key = signing_key
        self.root_id = root_id
        self.tip: GlobalTip | None = None

    def advance(self, candidate: GlobalTip) -> GlobalTip:
        if not isinstance(candidate, GlobalTip):
            raise RecoveryDenied("G28_BAD_CANDIDATE_TIP")
        if self.tip is not None:
            if candidate == self.tip:
                return self.tip
            if candidate.sequence <= self.tip.sequence:
                raise RecoveryDenied("G28_NON_MONOTONIC_ANCHOR_ADVANCE")
            if candidate.record_count <= self.tip.record_count:
                raise RecoveryDenied("G28_RECORD_COUNT_NOT_INCREASING")
        if candidate.sequence != candidate.record_count:
            # Constrained synthetic schema: sequential, no deletes/gaps.
            raise RecoveryDenied("G28_CANDIDATE_SEQUENCE_GAP")
        self.tip = candidate
        return candidate

    def challenge_attestation(self, challenge: bytes) -> SignedGlobalTip:
        if self.tip is None:
            raise RecoveryDenied("G28_ANCHOR_MISSING")
        payload = canonical_tip_response(self.tip, challenge, self.root_id)
        return SignedGlobalTip(
            self.tip, challenge, self.root_id, self.__key.sign(payload),
        )


def inspect_recovery_against_anchor(
    *, custody, attestation: SignedGlobalTip | None,
    verifier_challenge: bytes, pinned_public_key: bytes,
    pinned_root_id: str,
) -> Admission:
    """Attestation + global tip match gives only UNCERTAIN (zero auto-resend)."""
    if attestation is None:
        raise RecoveryDenied("G28_ANCHOR_UNAVAILABLE")
    if not isinstance(attestation, SignedGlobalTip):
        raise RecoveryDenied("G28_ANCHOR_MALFORMED")
    if attestation.trust_root_id != pinned_root_id:
        raise RecoveryDenied("G28_ROOT_MISMATCH")
    if attestation.challenge != verifier_challenge:
        raise RecoveryDenied("G28_CHALLENGE_MISMATCH")
    if not isinstance(pinned_public_key, bytes) or len(pinned_public_key) != 32:
        raise RecoveryDenied("G28_TRUST_ROOT_UNPROVISIONED")
    try:
        payload = canonical_tip_response(attestation.tip, verifier_challenge, pinned_root_id)
        Ed25519PublicKey.from_public_bytes(pinned_public_key).verify(
            attestation.signature, payload,
        )
    except (InvalidSignature, ValueError, TypeError) as exc:
        raise RecoveryDenied("G28_ANCHOR_SIGNATURE_INVALID") from exc
    local_tip = read_local_tip(custody)
    if local_tip.sequence != attestation.tip.sequence:
        raise RecoveryDenied("G28_GLOBAL_SEQUENCE_MISMATCH")
    if local_tip.record_count != attestation.tip.record_count:
        raise RecoveryDenied("G28_GLOBAL_COUNT_MISMATCH")
    if local_tip.ledger_digest != attestation.tip.ledger_digest:
        raise RecoveryDenied("G28_GLOBAL_DIGEST_MISMATCH")
    return Admission.UNCERTAIN
