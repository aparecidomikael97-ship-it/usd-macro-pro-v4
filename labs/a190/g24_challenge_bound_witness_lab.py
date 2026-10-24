"""A190 G24 — challenge-bound Ed25519 witness freshness, isolated LAB.

This rejects a replayed *old response* when a new verifier challenge is used.
It DOES NOT prevent a compromised or rollback-capable witness from signing
old history in response to a fresh challenge. Independent monotonic custody
remains mandatory and unproven.
"""
from dataclasses import dataclass
import json
import secrets
from typing import Mapping

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from g20_independent_witness_recovery_contract_lab import (
    Admission, RecoveryDenied, WitnessAttestation, recovery_admission,
)
from g23_pinned_ed25519_witness_verifier_lab import canonical_attestation_payload


@dataclass(frozen=True)
class ChallengeResponse:
    statement: WitnessAttestation
    challenge: bytes
    signature: bytes


def challenge_payload(statement: WitnessAttestation, challenge: bytes) -> bytes:
    """Domain separated: binds exact signed history statement + challenge."""
    if not isinstance(challenge, bytes) or len(challenge) != 32:
        raise ValueError("G24_CHALLENGE_INVALID")
    payload = {
        "domain": "AION-A190-G24-CHALLENGE-LAB-V1",
        "challenge_hex": challenge.hex(),
        "statement_hex": canonical_attestation_payload(statement).hex(),
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("ascii")


class PinnedChallengeWitness:
    """Synthetic responder. Pin is supplied outside statement, not proof of custody."""
    def __init__(self, response: ChallengeResponse,
                 trusted_public_keys: Mapping[str, bytes],
                 expected_challenge: bytes):
        self.response = response
        self.pins = dict(trusted_public_keys)
        self.expected_challenge = expected_challenge

    def attest_latest(self, semantic_key):
        return self.response.statement

    def verify(self, statement, pinned_root_id):
        if statement != self.response.statement:
            return False
        if self.response.challenge != self.expected_challenge:
            return False
        if statement.trust_root_id != pinned_root_id:
            return False
        key = self.pins.get(pinned_root_id)
        if not isinstance(key, bytes) or len(key) != 32:
            return False
        try:
            Ed25519PublicKey.from_public_bytes(key).verify(
                self.response.signature,
                challenge_payload(statement, self.expected_challenge),
            )
        except (InvalidSignature, TypeError, ValueError):
            return False
        return True


def inspect_freshness(
    *,
    semantic_key: str,
    local_journal,
    witness_response: ChallengeResponse,
    pinned_root_id: str,
    pinned_public_key: bytes,
    challenge: bytes,
) -> Admission:
    """A matching signed challenge permits UNCERTAIN only, never SEND/RETRY."""
    if not isinstance(challenge, bytes) or len(challenge) != 32:
        raise RecoveryDenied("G24_INVALID_CHALLENGE")
    if not isinstance(witness_response, ChallengeResponse):
        raise RecoveryDenied("G24_INVALID_RESPONSE")
    verifier = PinnedChallengeWitness(
        response=witness_response,
        trusted_public_keys={pinned_root_id: pinned_public_key},
        expected_challenge=challenge,
    )
    return recovery_admission(
        semantic_key=semantic_key,
        local_journal=local_journal,
        witness=verifier,
        pinned_root_id=pinned_root_id,
    )


def new_challenge() -> bytes:
    """32 bytes CSPRNG; verifier must generate it, not receive from witness."""
    return secrets.token_bytes(32)
