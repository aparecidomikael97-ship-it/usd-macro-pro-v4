"""A190 G25: monotonic witness high-water mark admission, isolated LAB.

An externally provisioned, independently monotonic floor is REQUIRED. This
module cannot provide such a floor; all tests use synthetic in-memory custody.
No production integration, provider dispatch, or first-send admission.
"""
from dataclasses import dataclass
from typing import Mapping

from g20_independent_witness_recovery_contract_lab import (
    Admission, RecoveryDenied, WitnessAttestation, recovery_admission,
)
from g24_challenge_bound_witness_lab import (
    ChallengeResponse, PinnedChallengeWitness,
)


@dataclass(frozen=True)
class TrustedHighWaterMark:
    """External monotonic fact, not derived from SQLite or signed response."""
    semantic_key: str
    sequence: int
    journal_digest: str


def inspect_monotonic_recovery(
    *,
    semantic_key: str,
    local_journal: Mapping,
    witness_response: ChallengeResponse,
    pinned_root_id: str,
    pinned_public_key: bytes,
    verifier_challenge: bytes,
    external_high_water: TrustedHighWaterMark | None,
) -> Admission:
    """No SEND/RETRY result, even when every check matches."""
    if external_high_water is None:
        raise RecoveryDenied("G25_EXTERNAL_MONOTONIC_FLOOR_MISSING")
    if not isinstance(external_high_water, TrustedHighWaterMark):
        raise RecoveryDenied("G25_EXTERNAL_MONOTONIC_FLOOR_MALFORMED")
    if external_high_water.semantic_key != semantic_key:
        raise RecoveryDenied("G25_EXTERNAL_SEMANTIC_MISMATCH")
    if type(external_high_water.sequence) is not int or external_high_water.sequence < 1:
        raise RecoveryDenied("G25_EXTERNAL_SEQUENCE_INVALID")
    if not isinstance(external_high_water.journal_digest, str) or len(external_high_water.journal_digest) != 64:
        raise RecoveryDenied("G25_EXTERNAL_DIGEST_INVALID")
    if not isinstance(witness_response, ChallengeResponse):
        raise RecoveryDenied("G25_WITNESS_RESPONSE_INVALID")
    statement: WitnessAttestation = witness_response.statement
    if statement.sequence < external_high_water.sequence:
        raise RecoveryDenied("G25_WITNESS_BELOW_EXTERNAL_FLOOR")
    if statement.sequence > external_high_water.sequence:
        raise RecoveryDenied("G25_EXTERNAL_FLOOR_STALE_OR_UNVERIFIED")
    if statement.journal_digest != external_high_water.journal_digest:
        raise RecoveryDenied("G25_EXTERNAL_DIGEST_CONFLICT")
    # The floor MUST come from independent trust; a host-controlled value
    # creates a false sense of security (explicitly tested as RED).
    verifier = PinnedChallengeWitness(
        response=witness_response,
        trusted_public_keys={pinned_root_id: pinned_public_key},
        expected_challenge=verifier_challenge,
    )
    return recovery_admission(
        semantic_key=semantic_key,
        local_journal=local_journal,
        witness=verifier,
        pinned_root_id=pinned_root_id,
    )
