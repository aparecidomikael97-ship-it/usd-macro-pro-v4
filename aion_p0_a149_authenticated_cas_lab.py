"""A149 synthetic authenticated witness CAS — LAB ONLY / HARD NO-GO.

This is a deliberately LOCAL mutable SQLite trust-domain experiment, not an
independent authority. A publisher's Ed25519 key is pinned at synthetic genesis;
untrusted requests carry NO trusted public key. Challenges and receipt records
are stored in the SAME SQLite transaction domain as the high-water.
A lost acknowledgment is NEVER grounds for automatic re-publication.
Every read/write is synthetic; no network, provider, Worker, or real effect.

Security still missing: external key custody, authenticated network transport,
independent immutable monotonic storage, key rotation, expiration policy,
actual publisher authorization by HUMAN_OWNER and provider reconciliation.
"""
import base64
import binascii
from contextlib import closing
from dataclasses import dataclass
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import secrets
import sqlite3

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey, Ed25519PublicKey,
)
from aion_p0_a145_checkpoint_verifier_lab import canonical_history_digest
from aion_p0_a146_highwater_gate_lab import HighWater, _validate
from aion_p0_a146_signed_highwater_lab import SignedHighWater, canonical_highwater_bytes

LAB_ONLY = "AION_A149_LOCAL_SYNTHETIC_NOT_PRODUCTION"
REQUEST_DOMAIN = b"AION-A149-PUBLISH-CHALLENGE-LAB-v1\x00"
RECEIPT_DOMAIN = b"AION-A149-RECEIPT-LAB-v1\x00"
DB_NAME = "a149_auth_cas_synthetic.sqlite3"
KEY_NAME = "a149_synthetic_witness_signer.key"
WITNESS_KEY_ID = "a149-witness-synthetic"
_SAFE = re.compile(r"[A-Za-z0-9_-]{1,80}\Z")
_HEX32 = re.compile(r"[0-9a-f]{32}\Z")
_HEX64 = re.compile(r"[0-9a-f]{64}\Z")

META_DDL = ("CREATE TABLE witness_meta (singleton INTEGER PRIMARY KEY CHECK(singleton=1),"
            " ledger_id TEXT NOT NULL, epoch TEXT NOT NULL,"
            " publisher_key_id TEXT NOT NULL, publisher_public_hex TEXT NOT NULL,"
            " sequence INTEGER NOT NULL, history_digest TEXT NOT NULL)")
CHALLENGES_DDL = ("CREATE TABLE challenges (challenge_id TEXT PRIMARY KEY,"
                  " epoch TEXT NOT NULL, expected_sequence INTEGER NOT NULL,"
                  " expected_digest TEXT NOT NULL, consumed INTEGER NOT NULL"
                  " CHECK(consumed IN (0,1))) WITHOUT ROWID")
RECEIPTS_DDL = ("CREATE TABLE receipts (request_id TEXT PRIMARY KEY,"
                " challenge_id TEXT NOT NULL, sequence INTEGER NOT NULL,"
                " history_digest TEXT NOT NULL, request_digest TEXT NOT NULL)"
                " WITHOUT ROWID")
EXPECTED_SCHEMA = {
    "witness_meta": ("table", "witness_meta", META_DDL),
    "challenges": ("table", "challenges", CHALLENGES_DDL),
    "receipts": ("table", "receipts", RECEIPTS_DDL),
}


class A149Denied(RuntimeError):
    pass


@dataclass(frozen=True)
class PublishRequest:
    ledger_id: str
    epoch: str
    publisher_key_id: str
    challenge_id: str
    request_id: str
    expected_sequence: int
    expected_digest: str
    next_sequence: int
    next_digest: str


@dataclass(frozen=True)
class SignedPublishRequest:
    request: PublishRequest
    signature_b64: str


@dataclass(frozen=True)
class PublicationReceipt:
    ledger_id: str
    epoch: str
    request_id: str
    challenge_id: str
    sequence: int
    history_digest: str
    request_digest: str


@dataclass(frozen=True)
class SignedPublicationReceipt:
    receipt: PublicationReceipt
    signature_b64: str


def _require_lab():
    if os.environ.get("AION_LAB_MODE") != "1":
        raise A149Denied("lab_mode_required")
    if os.environ.get("AION_WORKER_ENABLED") != "0":
        raise A149Denied("worker_must_be_disabled")
    if os.environ.get("AION_EXTERNAL_EXECUTION_ENABLED") != "0":
        raise A149Denied("external_execution_must_be_disabled")


def _safe_id(value):
    if type(value) is not str or not _SAFE.fullmatch(value):
        raise A149Denied("invalid_identity")
    return value


def _hex32(value):
    return type(value) is str and _HEX32.fullmatch(value) is not None


def _hex64(value):
    return type(value) is str and _HEX64.fullmatch(value) is not None


def _dumps(values):
    return json.dumps(values, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def _request_values(req):
    if type(req) is not PublishRequest:
        raise A149Denied("invalid_request_type")
    _safe_id(req.ledger_id)
    _safe_id(req.publisher_key_id)
    if not (_hex32(req.epoch) and _hex32(req.challenge_id)
            and _hex32(req.request_id)):
        raise A149Denied("invalid_challenge_or_request_identity")
    if (type(req.expected_sequence) is not int or req.expected_sequence < 0
            or type(req.next_sequence) is not int
            or req.next_sequence != req.expected_sequence + 1):
        raise A149Denied("invalid_sequence_transition")
    if not (_hex64(req.expected_digest) and _hex64(req.next_digest)):
        raise A149Denied("invalid_signed_digest")
    return {key: getattr(req, key) for key in PublishRequest.__dataclass_fields__}


def canonical_publish_request(req):
    return REQUEST_DOMAIN + _dumps(_request_values(req))


def canonical_receipt(receipt):
    if type(receipt) is not PublicationReceipt:
        raise A149Denied("invalid_receipt")
    _safe_id(receipt.ledger_id)
    if not all(_hex32(x) for x in (receipt.epoch, receipt.request_id, receipt.challenge_id)):
        raise A149Denied("invalid_receipt_identity")
    if type(receipt.sequence) is not int or receipt.sequence < 0:
        raise A149Denied("invalid_receipt_sequence")
    if not (_hex64(receipt.history_digest) and _hex64(receipt.request_digest)):
        raise A149Denied("invalid_receipt_digest")
    return RECEIPT_DOMAIN + _dumps(
        {key: getattr(receipt, key) for key in PublicationReceipt.__dataclass_fields__}
    )


def _signature_bytes(value):
    if type(value) is not str:
        raise A149Denied("invalid_signature_encoding")
    try:
        raw = base64.b64decode(value, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise A149Denied("invalid_signature_encoding") from exc
    if len(raw) != 64:
        raise A149Denied("invalid_signature_length")
    return raw


def verify_signed_receipt(*, envelope, pinned_witness_key):
    """Checks only receipt provenance under a caller-pinned synthetic key."""
    if type(envelope) is not SignedPublicationReceipt:
        raise A149Denied("missing_signed_receipt")
    if type(pinned_witness_key) is not bytes or len(pinned_witness_key) != 32:
        raise A149Denied("missing_pinned_witness_key")
    message = canonical_receipt(envelope.receipt)
    signature = _signature_bytes(envelope.signature_b64)
    try:
        Ed25519PublicKey.from_public_bytes(pinned_witness_key).verify(signature, message)
    except (InvalidSignature, ValueError) as exc:
        raise A149Denied("receipt_signature_invalid") from exc
    return envelope.receipt


class AuthenticatedWitnessLAB:
    """Synthetic CAS; publisher key pinned at bootstrap, not in requests."""

    def __init__(self, *, witness_dir, ledger_id):
        _require_lab()
        self.root = Path(witness_dir)
        if self.root.is_symlink() or not self.root.is_dir():
            raise A149Denied("invalid_witness_directory")
        self.ledger_id = _safe_id(ledger_id)
        self.db_path = self.root / DB_NAME
        self.key_path = self.root / KEY_NAME
        if (self.db_path.is_symlink() or not self.db_path.is_file()
                or self.key_path.is_symlink() or not self.key_path.is_file()):
            raise A149Denied("missing_witness_files")
        self.read_head()

    @classmethod
    def bootstrap_synthetic(cls, *, witness_dir, ledger_id,
                            publisher_key_id, publisher_public_key,
                            witness_private_key):
        _require_lab()
        root = Path(witness_dir)
        if root.is_symlink() or not root.is_dir():
            raise A149Denied("invalid_witness_directory")
        _safe_id(ledger_id)
        _safe_id(publisher_key_id)
        if (type(publisher_public_key) is not bytes or len(publisher_public_key) != 32
                or type(witness_private_key) is not bytes or len(witness_private_key) != 32):
            raise A149Denied("invalid_pinned_keys")
        try:
            Ed25519PublicKey.from_public_bytes(publisher_public_key)
            signer = Ed25519PrivateKey.from_private_bytes(witness_private_key)
            public = signer.public_key().public_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PublicFormat.Raw,
            )
            if hmac.compare_digest(public, publisher_public_key):
                raise A149Denied("publisher_and_witness_key_must_differ")
        except ValueError as exc:
            raise A149Denied("invalid_synthetic_keys") from exc
        db_path, key_path = root / DB_NAME, root / KEY_NAME
        if db_path.exists() or db_path.is_symlink() or key_path.exists() or key_path.is_symlink():
            raise A149Denied("rebootstrap_forbidden")
        epoch = secrets.token_hex(16)
        try:
            with key_path.open("xb") as stream:
                stream.write(witness_private_key)
            if os.name == "posix":
                key_path.chmod(0o600)
            with db_path.open("xb"):
                pass
            with closing(sqlite3.connect(db_path, isolation_level=None, timeout=2)) as db:
                db.execute("PRAGMA synchronous=FULL")
                db.execute("BEGIN IMMEDIATE")
                for ddl in (META_DDL, CHALLENGES_DDL, RECEIPTS_DDL):
                    db.execute(ddl)
                db.execute(
                    "INSERT INTO witness_meta VALUES (1,?,?,?,?,?,?)",
                    (ledger_id, epoch, publisher_key_id, publisher_public_key.hex(),
                     0, canonical_history_digest([])),
                )
                db.execute("COMMIT")
        except (OSError, sqlite3.Error) as exc:
            raise A149Denied("synthetic_bootstrap_failed") from exc
        return cls(witness_dir=root, ledger_id=ledger_id)

    def _connect(self, *, writable=False):
        _require_lab()
        if self.db_path.is_symlink() or not self.db_path.is_file():
            raise A149Denied("missing_or_linked_database")
        uri = self.db_path.resolve().as_uri() + ("?mode=rw" if writable else "?mode=ro")
        try:
            db = sqlite3.connect(uri, uri=True, isolation_level=None, timeout=3)
            db.execute("PRAGMA busy_timeout=3000")
            if writable:
                db.execute("PRAGMA synchronous=FULL")
            return db
        except sqlite3.Error as exc:
            raise A149Denied("database_open_failed") from exc

    def _state(self, db):
        try:
            rows = db.execute("SELECT type,name,tbl_name,sql FROM sqlite_master").fetchall()
            if len(rows) != 3 or {row[1] for row in rows} != set(EXPECTED_SCHEMA):
                raise A149Denied("unexpected_schema_objects")
            for kind, name, table, ddl in rows:
                if (kind, table, ddl) != EXPECTED_SCHEMA[name]:
                    raise A149Denied("schema_attestation_failed")
            if db.execute("PRAGMA quick_check").fetchone() != ("ok",):
                raise A149Denied("sqlite_integrity_failed")
            meta = db.execute(
                "SELECT singleton,ledger_id,epoch,publisher_key_id,publisher_public_hex,"
                "sequence,history_digest FROM witness_meta"
            ).fetchall()
            if len(meta) != 1 or meta[0][0] != 1:
                raise A149Denied("invalid_witness_meta")
            _, ledger_id, epoch, key_id, key_hex, seq, digest = meta[0]
            if ledger_id != self.ledger_id or not _hex32(epoch):
                raise A149Denied("identity_or_epoch_mismatch")
            _safe_id(key_id)
            if type(key_hex) is not str or not _hex64(key_hex):
                raise A149Denied("invalid_publisher_key")
            if type(seq) is not int or seq < 0 or not _hex64(digest):
                raise A149Denied("invalid_stored_head")
            if db.execute("SELECT COUNT(*) FROM receipts").fetchone()[0] != seq:
                raise A149Denied("receipt_count_sequence_conflict")
            return {"ledger_id": ledger_id, "epoch": epoch, "publisher_key_id": key_id,
                    "publisher_public_hex": key_hex, "sequence": seq, "digest": digest}
        except sqlite3.Error as exc:
            raise A149Denied("witness_sqlite_validation_error") from exc

    def _signer(self):
        _require_lab()
        if self.key_path.is_symlink() or not self.key_path.is_file():
            raise A149Denied("missing_signer_key")
        try:
            content = self.key_path.read_bytes()
            if len(content) != 32:
                raise A149Denied("invalid_signer_key")
            return Ed25519PrivateKey.from_private_bytes(content)
        except (OSError, ValueError) as exc:
            raise A149Denied("signer_key_read_failed") from exc

    def read_head(self):
        with closing(self._connect()) as db:
            db.execute("BEGIN")
            meta = self._state(db)
            db.execute("COMMIT")
        return meta

    def read_signed_head(self):
        meta = self.read_head()
        anchor = HighWater(self.ledger_id, meta["sequence"], meta["digest"])
        encoded = base64.b64encode(
            self._signer().sign(canonical_highwater_bytes(anchor))
        ).decode("ascii")
        return SignedHighWater(anchor, WITNESS_KEY_ID, encoded)

    def issue_challenge(self):
        """Durable one-time challenge. No rights to publish are conferred."""
        try:
            with closing(self._connect(writable=True)) as db:
                db.execute("BEGIN IMMEDIATE")
                meta = self._state(db)
                challenge_id = secrets.token_hex(16)
                db.execute(
                    "INSERT INTO challenges VALUES (?,?,?,?,0)",
                    (challenge_id, meta["epoch"], meta["sequence"], meta["digest"]),
                )
                db.execute("COMMIT")
                return {"ledger_id": self.ledger_id, "epoch": meta["epoch"],
                        "challenge_id": challenge_id,
                        "publisher_key_id": meta["publisher_key_id"],
                        "expected_sequence": meta["sequence"],
                        "expected_digest": meta["digest"]}
        except sqlite3.Error as exc:
            raise A149Denied("challenge_write_uncertain") from exc

    def publish(self, *, envelope, fault=None):
        """Signed one-time CAS with challenge consumption and receipt atomic.

        Crash after COMMIT loses reply but NOT consumed challenge or durable
        receipt. Retry is NOT authorized: read_receipt is the *only* follow-up.
        """
        if type(envelope) is not SignedPublishRequest:
            raise A149Denied("missing_signed_request")
        request = envelope.request
        payload = canonical_publish_request(request)
        signature = _signature_bytes(envelope.signature_b64)
        if fault is not None and (
            fault not in ("before_commit", "after_commit")
            or os.environ.get("AION_A149_FAULT_LAB") != "1"
        ):
            raise A149Denied("unauthorized_fault_injection")
        try:
            with closing(self._connect(writable=True)) as db:
                db.execute("BEGIN IMMEDIATE")
                meta = self._state(db)
                if request.ledger_id != meta["ledger_id"] or request.epoch != meta["epoch"]:
                    raise A149Denied("request_identity_or_epoch_mismatch")
                if request.publisher_key_id != meta["publisher_key_id"]:
                    raise A149Denied("untrusted_publisher_key_id")
                pinned_key = bytes.fromhex(meta["publisher_public_hex"])
                try:
                    Ed25519PublicKey.from_public_bytes(pinned_key).verify(signature, payload)
                except (InvalidSignature, ValueError) as exc:
                    raise A149Denied("publisher_signature_invalid") from exc
                challenge = db.execute(
                    "SELECT epoch,expected_sequence,expected_digest,consumed FROM challenges"
                    " WHERE challenge_id=?", (request.challenge_id,)
                ).fetchone()
                if challenge is None:
                    raise A149Denied("unknown_witness_challenge")
                if challenge[3] != 0:
                    raise A149Denied("challenge_already_consumed")
                if (challenge[:3] != (
                    request.epoch, request.expected_sequence, request.expected_digest
                )):
                    raise A149Denied("challenge_request_mismatch")
                if (meta["sequence"] != request.expected_sequence
                        or meta["digest"] != request.expected_digest):
                    raise A149Denied("stale_cas_and_history")
                if db.execute("SELECT 1 FROM receipts WHERE request_id=?",
                              (request.request_id,)).fetchone() is not None:
                    raise A149Denied("request_id_reused")
                request_digest = hashlib.sha256(payload).hexdigest()
                db.execute(
                    "INSERT INTO receipts VALUES (?,?,?,?,?)",
                    (request.request_id, request.challenge_id, request.next_sequence,
                     request.next_digest, request_digest),
                )
                db.execute(
                    "UPDATE witness_meta SET sequence=?,history_digest=? WHERE singleton=1",
                    (request.next_sequence, request.next_digest),
                )
                db.execute("UPDATE challenges SET consumed=1 WHERE challenge_id=?",
                           (request.challenge_id,))
                if fault == "before_commit":
                    os._exit(91)
                db.execute("COMMIT")
                if fault == "after_commit":
                    os._exit(92)
            return self.read_receipt(request.request_id)
        except sqlite3.Error as exc:
            raise A149Denied("signed_publish_result_uncertain") from exc

    def read_receipt(self, request_id):
        """Read-only lookup after uncertain response; NEVER re-executes CAS."""
        _require_lab()
        if not _hex32(request_id):
            raise A149Denied("invalid_receipt_id")
        with closing(self._connect()) as db:
            db.execute("BEGIN")
            meta = self._state(db)
            rows = db.execute(
                "SELECT request_id,challenge_id,sequence,history_digest,request_digest"
                " FROM receipts WHERE request_id=?", (request_id,),
            ).fetchall()
            db.execute("COMMIT")
        if len(rows) == 0:
            return None
        if len(rows) != 1:
            raise A149Denied("duplicate_receipt")
        req_id, challenge, seq, digest, signed_request_digest = rows[0]
        receipt = PublicationReceipt(
            meta["ledger_id"], meta["epoch"], req_id, challenge, seq, digest,
            signed_request_digest,
        )
        signature = self._signer().sign(canonical_receipt(receipt))
        return SignedPublicationReceipt(receipt, base64.b64encode(signature).decode("ascii"))
