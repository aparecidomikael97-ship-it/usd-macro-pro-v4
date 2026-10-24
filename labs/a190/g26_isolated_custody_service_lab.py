"""A190 G26 — isolated witness custody protocol, synthetic LAB only.

The custody server is a separate *object* with a private signing key and
monotonic in-memory records. This demonstrates protocol invariants but NOT
separate hardware, independent operator, non-rollback storage, or trust roots.

NO network listener, no real provider, no production integration.
"""
from dataclasses import dataclass
from typing import Dict, Tuple

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from g20_independent_witness_recovery_contract_lab import WitnessAttestation
from g24_challenge_bound_witness_lab import ChallengeResponse, challenge_payload
from g25_monotonic_custody_contract_lab import TrustedHighWaterMark


class CustodyConflict(RuntimeError):
    pass


@dataclass(frozen=True)
class CustodyRecord:
    semantic_key: str
    sequence: int
    phase: str
    journal_digest: str


class IsolatedCustodyService:
    """In-memory stand-in for a remote trusted, append-only monotonic service."""
    def __init__(self, signing_key: Ed25519PrivateKey, root_id: str):
        if not root_id:
            raise ValueError("root_id required")
        self.__key = signing_key
        self.root_id = root_id
        self.__records: Dict[str, CustodyRecord] = {}
        self.__highest_sequence = 0

    def reserve(self, semantic_key: str, phase: str, journal_digest: str) -> CustodyRecord:
        if not semantic_key or not isinstance(semantic_key, str):
            raise CustodyConflict("G26_INVALID_SEMANTIC_KEY")
        if phase not in {"RESERVED", "UNCERTAIN"}:
            raise CustodyConflict("G26_UNSUPPORTED_PHASE")
        if not isinstance(journal_digest, str) or len(journal_digest) != 64:
            raise CustodyConflict("G26_INVALID_DIGEST")
        existing = self.__records.get(semantic_key)
        if existing is not None:
            if existing.phase == phase and existing.journal_digest == journal_digest:
                return existing  # idempotent exact replay
            raise CustodyConflict("G26_SEMANTIC_REUSE_CONFLICT")
        self.__highest_sequence += 1
        record = CustodyRecord(semantic_key, self.__highest_sequence, phase, journal_digest)
        self.__records[semantic_key] = record
        return record

    def high_water(self, semantic_key: str) -> TrustedHighWaterMark:
        record = self.__records.get(semantic_key)
        if record is None:
            raise CustodyConflict("G26_NO_EXTERNAL_RESERVATION")
        return TrustedHighWaterMark(record.semantic_key, record.sequence,
                                    record.journal_digest)

    def attest(self, semantic_key: str, challenge: bytes) -> ChallengeResponse:
        record = self.__records.get(semantic_key)
        if record is None:
            raise CustodyConflict("G26_NO_EXTERNAL_RESERVATION")
        statement = WitnessAttestation(
            semantic_key=record.semantic_key,
            sequence=record.sequence,
            phase=record.phase,
            journal_digest=record.journal_digest,
            trust_root_id=self.root_id,
            signed_statement=b"g26-custody-record",
        )
        signature = self.__key.sign(challenge_payload(statement, challenge))
        return ChallengeResponse(statement, challenge, signature)
