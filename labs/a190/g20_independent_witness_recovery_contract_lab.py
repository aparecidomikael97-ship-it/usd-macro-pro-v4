"""A190 G20: offline fail-closed boundary for an INDEPENDENT witness.

A contract, not a production provider. A witness cannot be instantiated here:
the real root must be externally pinned and controlled outside the host.
This module never sends, reconciles, authorizes, or executes any effect.
"""
from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
import json
from typing import Any, Mapping, Protocol


class RecoveryDenied(RuntimeError):
    pass


class Admission(str, Enum):
    DENY = "DENY"
    UNCERTAIN = "UNCERTAIN_ZERO_AUTO_RESEND"


@dataclass(frozen=True)
class WitnessAttestation:
    semantic_key: str
    sequence: int
    phase: str
    journal_digest: str
    trust_root_id: str
    signed_statement: bytes


class IndependentWitness(Protocol):
    def attest_latest(self, semantic_key: str) -> WitnessAttestation: ...
    def verify(self, statement: WitnessAttestation, pinned_root_id: str) -> bool: ...


def canonical_hash(value: Mapping[str, Any]) -> str:
    return sha256(json.dumps(dict(value), sort_keys=True, separators=(",", ":"),
                             ensure_ascii=False).encode("utf-8")).hexdigest()


def recovery_admission(
    *,
    semantic_key: str,
    local_journal: Mapping[str, Any] | None,
    witness: IndependentWitness | None,
    pinned_root_id: str | None,
) -> Admission:
    """Never return SEND/RETRY/CONFIRMED. Only DENY or UNCERTAIN.

    The caller MUST obtain pinned_root_id from a separately trusted deployment
    authority, never from the local journal, caller, or witness response.
    This reference contract cannot verify that independent provisioning exists.
    """
    if not isinstance(semantic_key, str) or not semantic_key.strip():
        raise RecoveryDenied("INVALID_SEMANTIC_KEY")
    if not isinstance(pinned_root_id, str) or not pinned_root_id.strip():
        raise RecoveryDenied("INDEPENDENT_PINNED_ROOT_MISSING")
    if witness is None:
        raise RecoveryDenied("INDEPENDENT_WITNESS_MISSING")
    try:
        statement = witness.attest_latest(semantic_key)
    except Exception as exc:
        raise RecoveryDenied("INDEPENDENT_WITNESS_UNAVAILABLE") from exc
    if not isinstance(statement, WitnessAttestation):
        raise RecoveryDenied("MALFORMED_WITNESS_ATTESTATION")
    if statement.semantic_key != semantic_key:
        raise RecoveryDenied("WITNESS_SEMANTIC_MISMATCH")
    if statement.trust_root_id != pinned_root_id:
        raise RecoveryDenied("WITNESS_ROOT_MISMATCH")
    if type(statement.sequence) is not int or statement.sequence < 1:
        raise RecoveryDenied("WITNESS_SEQUENCE_INVALID")
    if statement.phase not in {"RESERVED", "UNCERTAIN", "CONFIRMED"}:
        raise RecoveryDenied("WITNESS_PHASE_INVALID")
    if not isinstance(statement.signed_statement, bytes) or not statement.signed_statement:
        raise RecoveryDenied("WITNESS_SIGNATURE_MISSING")
    try:
        verified = witness.verify(statement, pinned_root_id)
    except Exception as exc:
        raise RecoveryDenied("WITNESS_SIGNATURE_VERIFICATION_FAILED") from exc
    if verified is not True:
        raise RecoveryDenied("WITNESS_SIGNATURE_UNTRUSTED")
    if local_journal is None:
        raise RecoveryDenied("LOCAL_JOURNAL_MISSING_OR_ROLLED_BACK")
    try:
        local_key = local_journal["semantic_key"]
        local_seq = local_journal["sequence"]
        local_phase = local_journal["phase"]
        local_digest = canonical_hash(local_journal)
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        raise RecoveryDenied("LOCAL_JOURNAL_INVALID") from exc
    if local_key != semantic_key:
        raise RecoveryDenied("LOCAL_SEMANTIC_MISMATCH")
    if type(local_seq) is not int or local_seq != statement.sequence:
        raise RecoveryDenied("LOCAL_SEQUENCE_MISMATCH")
    if local_phase != statement.phase:
        raise RecoveryDenied("LOCAL_PHASE_MISMATCH")
    if local_digest != statement.journal_digest:
        raise RecoveryDenied("LOCAL_DIGEST_MISMATCH")
    return Admission.UNCERTAIN


def first_attempt_admission(*, witness: IndependentWitness | None,
                            pinned_root_id: str | None) -> Admission:
    """NO SEND even with a witness: this reference has no atomic reservation API."""
    if witness is None or not pinned_root_id:
        raise RecoveryDenied("FIRST_ATTEMPT_EXTERNAL_RESERVATION_MISSING")
    raise RecoveryDenied("FIRST_ATTEMPT_ATOMIC_EXTERNAL_RESERVATION_UNIMPLEMENTED")
