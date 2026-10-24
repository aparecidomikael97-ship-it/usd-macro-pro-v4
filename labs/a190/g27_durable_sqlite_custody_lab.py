"""A190 G27: persistent SQLite custody LAB with transaction-level monotonicity.

Separate DB file and BEGIN IMMEDIATE protect process restart and concurrent
local writers. Same-host rollback, database deletion, cloned history, signing
key theft and externally untrusted key provisioning remain UNSOLVED.
This module is LAB-only. Never wire into AION production or dispatch.
"""
from pathlib import Path
import sqlite3

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from g20_independent_witness_recovery_contract_lab import WitnessAttestation
from g24_challenge_bound_witness_lab import ChallengeResponse, challenge_payload
from g25_monotonic_custody_contract_lab import TrustedHighWaterMark
from g26_isolated_custody_service_lab import CustodyConflict, CustodyRecord


class DurableCustodyLab:
    """Local file persistence only, NOT independent or rollback-resistant."""
    def __init__(self, path: Path, signing_key: Ed25519PrivateKey, root_id: str):
        if not root_id or not isinstance(root_id, str):
            raise ValueError("G27_INVALID_ROOT")
        self.path = Path(path)
        self.root_id = root_id
        self._signer = signing_key
        self._db = sqlite3.connect(str(self.path), timeout=5, isolation_level=None)
        self._db.execute("PRAGMA busy_timeout=5000")
        self._db.execute("PRAGMA synchronous=FULL")
        # Deliberately avoid WAL for test snapshot clarity; does not establish
        # antirollback or handle AION operational WAL/SHM requirements.
        self._db.execute("PRAGMA journal_mode=DELETE")
        self._db.execute(
            "CREATE TABLE IF NOT EXISTS custody_records ("
            "sequence INTEGER PRIMARY KEY AUTOINCREMENT,"
            "semantic_key TEXT NOT NULL UNIQUE,"
            "phase TEXT NOT NULL,"
            "journal_digest TEXT NOT NULL)"
        )

    def close(self):
        self._db.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def reserve(self, semantic_key: str, phase: str, journal_digest: str) -> CustodyRecord:
        if not isinstance(semantic_key, str) or not semantic_key:
            raise CustodyConflict("G27_INVALID_SEMANTIC_KEY")
        if phase not in {"RESERVED", "UNCERTAIN"}:
            raise CustodyConflict("G27_INVALID_PHASE")
        if not isinstance(journal_digest, str) or len(journal_digest) != 64:
            raise CustodyConflict("G27_INVALID_DIGEST")
        try:
            int(journal_digest, 16)
        except ValueError as exc:
            raise CustodyConflict("G27_INVALID_DIGEST") from exc
        self._db.execute("BEGIN IMMEDIATE")
        try:
            existing = self._db.execute(
                "SELECT sequence,phase,journal_digest FROM custody_records "
                "WHERE semantic_key=?", (semantic_key,)
            ).fetchone()
            if existing:
                seq, old_phase, old_digest = existing
                if (phase, journal_digest) != (old_phase, old_digest):
                    raise CustodyConflict("G27_SEMANTIC_REUSE_CONFLICT")
                result = CustodyRecord(semantic_key, seq, old_phase, old_digest)
            else:
                cursor = self._db.execute(
                    "INSERT INTO custody_records (semantic_key,phase,journal_digest) "
                    "VALUES (?,?,?)", (semantic_key, phase, journal_digest)
                )
                result = CustodyRecord(semantic_key, cursor.lastrowid, phase, journal_digest)
            self._db.execute("COMMIT")
            return result
        except BaseException:
            self._db.execute("ROLLBACK")
            raise

    def read(self, semantic_key: str) -> CustodyRecord:
        row = self._db.execute(
            "SELECT sequence,phase,journal_digest FROM custody_records "
            "WHERE semantic_key=?", (semantic_key,)
        ).fetchone()
        if row is None:
            raise CustodyConflict("G27_CUSTODY_RESERVATION_MISSING")
        return CustodyRecord(semantic_key, *row)

    def high_water(self, semantic_key: str) -> TrustedHighWaterMark:
        row = self.read(semantic_key)
        return TrustedHighWaterMark(row.semantic_key, row.sequence, row.journal_digest)

    def attest(self, semantic_key: str, challenge: bytes) -> ChallengeResponse:
        row = self.read(semantic_key)
        statement = WitnessAttestation(
            semantic_key=row.semantic_key, sequence=row.sequence,
            phase=row.phase, journal_digest=row.journal_digest,
            trust_root_id=self.root_id, signed_statement=b"g27-lab-record",
        )
        return ChallengeResponse(
            statement=statement,
            challenge=challenge,
            signature=self._signer.sign(challenge_payload(statement, challenge)),
        )
