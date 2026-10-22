"""A150 operator-pinned policy + expiring challenge lease (SYNTHETIC LAB ONLY).

This is NOT a production witness. OperatorPinnedPolicy is an out-of-band
TRUST PRECONDITION supplied by the test harness, not authenticated here.
Keys, policy, epoch, witness SQLite, lease clock and machine remain synthetic.
No real HUMAN_OWNER identity, key custody, independent monotonic witness,
trusted external clock, signed revocation, provider or Worker integration.

A149's old unguarded API remains callable in its LAB: A150 is a separate
EXPERIMENTAL engine, not a drop-in security patch for all A149 callers.
A valid lease only says the simulated clock was inside a bounded interval.
A legitimate signed CAS receipt NEVER establishes provider effect.
"""
import base64
from contextlib import closing
from dataclasses import dataclass
import hashlib
import hmac
import os
from pathlib import Path
import secrets
import sqlite3
import time

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey, Ed25519PublicKey,
)

from aion_p0_a149_authenticated_cas_lab import (
    A149Denied, AuthenticatedWitnessLAB, CHALLENGES_DDL, DB_NAME, EXPECTED_SCHEMA,
    KEY_NAME, META_DDL, RECEIPTS_DDL, PublicationReceipt, PublishRequest,
    SignedPublishRequest, SignedPublicationReceipt, _hex32, _hex64,
    _request_values, _require_lab, _safe_id, _signature_bytes,
    canonical_publish_request, canonical_receipt,
)
from aion_p0_a145_checkpoint_verifier_lab import canonical_history_digest

LEASE_DDL = (
    "CREATE TABLE challenge_lease (challenge_id TEXT PRIMARY KEY,"
    " issued_ns INTEGER NOT NULL, expires_ns INTEGER NOT NULL) WITHOUT ROWID"
)
CLOCK_DDL = (
    "CREATE TABLE witness_clock (singleton INTEGER PRIMARY KEY CHECK(singleton=1),"
    " floor_ns INTEGER NOT NULL)"
)
SCHEMA = {
    **EXPECTED_SCHEMA,
    "challenge_lease": ("table", "challenge_lease", LEASE_DDL),
    "witness_clock": ("table", "witness_clock", CLOCK_DDL),
}
NANOSECONDS_PER_SECOND = 1_000_000_000
DEFAULT_LEASE_SECONDS = 30
MAX_LEASE_SECONDS = 300


@dataclass(frozen=True)
class OperatorPinnedPolicyLAB:
    """Trusted IN MEMORY by the test harness, never from the witness response."""
    ledger_id: str
    epoch: str
    publisher_key_id: str
    publisher_public_key: bytes
    witness_public_key: bytes


def _validate_policy(policy):
    if type(policy) is not OperatorPinnedPolicyLAB:
        raise A149Denied("external_policy_required")
    _safe_id(policy.ledger_id)
    _safe_id(policy.publisher_key_id)
    if not _hex32(policy.epoch):
        raise A149Denied("external_epoch_missing")
    if (type(policy.publisher_public_key) is not bytes
            or len(policy.publisher_public_key) != 32
            or type(policy.witness_public_key) is not bytes
            or len(policy.witness_public_key) != 32):
        raise A149Denied("invalid_external_public_keys")
    if hmac.compare_digest(policy.publisher_public_key, policy.witness_public_key):
        raise A149Denied("publisher_witness_key_reused")
    return policy


class LeasedPinnedWitnessLAB(AuthenticatedWitnessLAB):
    """A150 standalone test-only witness with strict schema and lease expiry."""

    def __init__(self, *, witness_dir, ledger_id, pinned_policy,
                 clock_ns=None, lease_seconds=DEFAULT_LEASE_SECONDS):
        self.policy = _validate_policy(pinned_policy)
        if ledger_id != self.policy.ledger_id:
            raise A149Denied("policy_ledger_mismatch")
        if type(lease_seconds) is not int or not 1 <= lease_seconds <= MAX_LEASE_SECONDS:
            raise A149Denied("invalid_lease_seconds")
        self.lease_seconds = lease_seconds
        if clock_ns is not None and not callable(clock_ns):
            raise A149Denied("invalid_clock_source")
        # Clock is injectable ONLY for synthetic fault scenarios.
        self.clock_ns = clock_ns if clock_ns is not None else time.time_ns
        super().__init__(witness_dir=witness_dir, ledger_id=ledger_id)

    @classmethod
    def bootstrap_synthetic(cls, *, witness_dir, ledger_id,
                            publisher_key_id, publisher_public_key,
                            witness_private_key, clock_ns=None, lease_seconds=30):
        """Synthetic genesis only; cannot attest an independent operator."""
        _require_lab()
        if clock_ns is not None and not callable(clock_ns):
            raise A149Denied("invalid_clock_source")
        now_function = clock_ns if clock_ns is not None else time.time_ns
        now_ns = now_function()
        if type(now_ns) is not int or now_ns <= 0:
            raise A149Denied("invalid_clock_value")
        # Bootstrap A149's unchanged toy schema, before this subclass's
        # additional two policy tables are created. We do not alter A149.
        base = AuthenticatedWitnessLAB.bootstrap_synthetic(
            witness_dir=witness_dir,
            ledger_id=ledger_id,
            publisher_key_id=publisher_key_id,
            publisher_public_key=publisher_public_key,
            witness_private_key=witness_private_key,
        )
        try:
            with closing(sqlite3.connect(base.db_path, timeout=3, isolation_level=None)) as db:
                db.execute("PRAGMA synchronous=FULL")
                db.execute("BEGIN IMMEDIATE")
                db.execute(LEASE_DDL)
                db.execute(CLOCK_DDL)
                db.execute("INSERT INTO witness_clock VALUES (1,?)", (now_ns,))
                db.execute("COMMIT")
        except sqlite3.Error as exc:
            raise A149Denied("lease_schema_bootstrap_failed") from exc
        signer = Ed25519PrivateKey.from_private_bytes(witness_private_key)
        witness_public = signer.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        original = base.read_head if False else None  # no re-use of legacy engine
        # Read the epoch from the already-committed genesis via read-only sqlite.
        with closing(sqlite3.connect(
            base.db_path.resolve().as_uri() + "?mode=ro", uri=True
        )) as db:
            epoch = db.execute(
                "SELECT epoch FROM witness_meta WHERE singleton=1"
            ).fetchone()[0]
        policy = OperatorPinnedPolicyLAB(
            ledger_id=ledger_id, epoch=epoch,
            publisher_key_id=publisher_key_id,
            publisher_public_key=publisher_public_key,
            witness_public_key=witness_public,
        )
        return cls(
            witness_dir=witness_dir, ledger_id=ledger_id,
            pinned_policy=policy, clock_ns=clock_ns, lease_seconds=lease_seconds,
        )

    def _now(self):
        try:
            now_ns = self.clock_ns()
        except Exception as exc:
            raise A149Denied("lease_clock_unavailable") from exc
        if type(now_ns) is not int or now_ns <= 0 or now_ns > 2**63 - 1:
            raise A149Denied("invalid_clock_value")
        return now_ns

    def _state(self, db):
        """Validate exact V150 schema, then DB enrollment vs out-of-band policy."""
        try:
            rows = db.execute("SELECT type,name,tbl_name,sql FROM sqlite_master").fetchall()
            if len(rows) != len(SCHEMA) or {x[1] for x in rows} != set(SCHEMA):
                raise A149Denied("unexpected_a150_schema_objects")
            for kind, name, table, ddl in rows:
                if (kind, table, ddl) != SCHEMA[name]:
                    raise A149Denied("a150_schema_attestation_failed")
            if db.execute("PRAGMA quick_check").fetchone() != ("ok",):
                raise A149Denied("a150_sqlite_integrity_failed")
            metas = db.execute(
                "SELECT singleton,ledger_id,epoch,publisher_key_id,publisher_public_hex,"
                " sequence,history_digest FROM witness_meta"
            ).fetchall()
            if len(metas) != 1 or metas[0][0] != 1:
                raise A149Denied("invalid_a150_witness_meta")
            _, ledger_id, epoch, pub_id, pub_hex, seq, digest = metas[0]
            p = self.policy
            if (ledger_id != p.ledger_id or epoch != p.epoch
                    or pub_id != p.publisher_key_id
                    or pub_hex != p.publisher_public_key.hex()):
                raise A149Denied("external_pin_mismatch")
            if type(seq) is not int or seq < 0 or not _hex64(digest):
                raise A149Denied("invalid_stored_head")
            if db.execute("SELECT COUNT(*) FROM receipts").fetchone()[0] != seq:
                raise A149Denied("receipt_count_sequence_conflict")
            clocks = db.execute(
                "SELECT singleton,floor_ns FROM witness_clock"
            ).fetchall()
            if (len(clocks) != 1 or clocks[0][0] != 1
                    or type(clocks[0][1]) is not int or clocks[0][1] <= 0):
                raise A149Denied("invalid_clock_floor")
            bad_leases = db.execute(
                "SELECT COUNT(*) FROM challenges c LEFT JOIN challenge_lease l"
                " ON c.challenge_id=l.challenge_id"
                " WHERE l.challenge_id IS NULL"
            ).fetchone()[0]
            orphan_leases = db.execute(
                "SELECT COUNT(*) FROM challenge_lease l LEFT JOIN challenges c"
                " ON c.challenge_id=l.challenge_id"
                " WHERE c.challenge_id IS NULL"
            ).fetchone()[0]
            corrupt_leases = db.execute(
                "SELECT COUNT(*) FROM challenge_lease"
                " WHERE typeof(issued_ns)!='integer' OR typeof(expires_ns)!='integer'"
                " OR issued_ns<=0 OR expires_ns<=issued_ns"
                " OR expires_ns-issued_ns>?",
                (MAX_LEASE_SECONDS * NANOSECONDS_PER_SECOND,)
            ).fetchone()[0]
            if bad_leases or orphan_leases or corrupt_leases:
                raise A149Denied("lease_integrity_failure")
            return {
                "ledger_id": ledger_id, "epoch": epoch,
                "publisher_key_id": pub_id, "publisher_public_hex": pub_hex,
                "sequence": seq, "digest": digest, "clock_floor_ns": clocks[0][1],
            }
        except sqlite3.Error as exc:
            raise A149Denied("a150_sqlite_validation_failed") from exc

    def _signer(self):
        signer = super()._signer()
        actual = signer.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        if not hmac.compare_digest(actual, self.policy.witness_public_key):
            raise A149Denied("external_witness_signer_pin_mismatch")
        return signer

    def _clock_checked(self, db, meta):
        now_ns = self._now()
        if now_ns < meta["clock_floor_ns"]:
            raise A149Denied("clock_rewind_detected")
        db.execute("UPDATE witness_clock SET floor_ns=? WHERE singleton=1", (now_ns,))
        return now_ns

    def issue_challenge(self):
        """Atomic lease issuance and monotonic local-clock-floor update."""
        try:
            with closing(self._connect(writable=True)) as db:
                db.execute("BEGIN IMMEDIATE")
                meta = self._state(db)
                now_ns = self._clock_checked(db, meta)
                challenge_id = secrets.token_hex(16)
                expires = now_ns + self.lease_seconds * NANOSECONDS_PER_SECOND
                if expires > 2**63 - 1:
                    raise A149Denied("lease_clock_overflow")
                db.execute(
                    "INSERT INTO challenges VALUES (?,?,?,?,0)",
                    (challenge_id, meta["epoch"], meta["sequence"], meta["digest"]),
                )
                db.execute(
                    "INSERT INTO challenge_lease VALUES (?,?,?)",
                    (challenge_id, now_ns, expires),
                )
                db.execute("COMMIT")
                return {
                    "ledger_id": self.ledger_id, "epoch": meta["epoch"],
                    "challenge_id": challenge_id,
                    "publisher_key_id": meta["publisher_key_id"],
                    "expected_sequence": meta["sequence"],
                    "expected_digest": meta["digest"],
                    "lease_issued_ns": now_ns, "lease_expires_ns": expires,
                }
        except sqlite3.Error as exc:
            raise A149Denied("lease_issue_result_uncertain") from exc

    def publish(self, *, envelope, fault=None):
        """Single SQLite transaction: pin + signature + lease + CAS + receipt.

        Does not allow automatic retry after uncertain outcome.
        Injection exists only with AION_A150_FAULT_LAB=1.
        """
        _require_lab()
        if type(envelope) is not SignedPublishRequest:
            raise A149Denied("missing_signed_request")
        req = envelope.request
        payload = canonical_publish_request(req)
        sig = _signature_bytes(envelope.signature_b64)
        if fault is not None and (
            fault not in ("before_commit", "after_commit")
            or os.environ.get("AION_A150_FAULT_LAB") != "1"
        ):
            raise A149Denied("unauthorized_fault_injection")
        try:
            with closing(self._connect(writable=True)) as db:
                db.execute("BEGIN IMMEDIATE")
                meta = self._state(db)
                now_ns = self._clock_checked(db, meta)
                if req.ledger_id != meta["ledger_id"] or req.epoch != meta["epoch"]:
                    raise A149Denied("request_identity_or_epoch_mismatch")
                if req.publisher_key_id != meta["publisher_key_id"]:
                    raise A149Denied("untrusted_publisher_key_id")
                try:
                    Ed25519PublicKey.from_public_bytes(
                        self.policy.publisher_public_key
                    ).verify(sig, payload)
                except (InvalidSignature, ValueError) as exc:
                    raise A149Denied("publisher_signature_invalid") from exc
                row = db.execute(
                    "SELECT c.epoch,c.expected_sequence,c.expected_digest,c.consumed,"
                    " l.issued_ns,l.expires_ns FROM challenges c"
                    " JOIN challenge_lease l ON c.challenge_id=l.challenge_id"
                    " WHERE c.challenge_id=?",
                    (req.challenge_id,),
                ).fetchone()
                if row is None:
                    raise A149Denied("missing_or_unleased_challenge")
                epoch, prev_seq, prev_digest, used, issued_ns, expiry_ns = row
                if used != 0:
                    raise A149Denied("challenge_already_consumed")
                if now_ns < issued_ns:
                    raise A149Denied("lease_not_yet_valid_clock_rewind")
                if now_ns >= expiry_ns:
                    raise A149Denied("challenge_lease_expired")
                if (epoch, prev_seq, prev_digest) != (
                    req.epoch, req.expected_sequence, req.expected_digest
                ):
                    raise A149Denied("challenge_request_mismatch")
                if (meta["sequence"], meta["digest"]) != (
                    req.expected_sequence, req.expected_digest
                ):
                    raise A149Denied("stale_cas_and_history")
                if db.execute(
                    "SELECT 1 FROM receipts WHERE request_id=?", (req.request_id,)
                ).fetchone() is not None:
                    raise A149Denied("request_id_reused")
                request_digest = hashlib.sha256(payload).hexdigest()
                db.execute(
                    "INSERT INTO receipts VALUES (?,?,?,?,?)",
                    (req.request_id, req.challenge_id, req.next_sequence,
                     req.next_digest, request_digest),
                )
                db.execute(
                    "UPDATE witness_meta SET sequence=?,history_digest=? WHERE singleton=1",
                    (req.next_sequence, req.next_digest),
                )
                db.execute("UPDATE challenges SET consumed=1 WHERE challenge_id=?",
                           (req.challenge_id,))
                if fault == "before_commit":
                    os._exit(101)
                db.execute("COMMIT")
                if fault == "after_commit":
                    os._exit(102)
            return self.read_receipt(req.request_id)
        except sqlite3.Error as exc:
            raise A149Denied("lease_publish_result_uncertain") from exc
