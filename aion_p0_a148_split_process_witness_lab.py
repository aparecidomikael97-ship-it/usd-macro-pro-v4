"""A148 TEST-ONLY witness in a separate PROCESS and local filesystem directory.

This is an adversarial simulation, NOT an independent trusted service.
The witness SQLite file and the Ed25519 private key are on the SAME MACHINE,
are both mutable, and can be snapshotted/rolled back by its operator.
There is no authenticated external transport, key custody, sealed monotonic
counter, independent availability, or production integration.

All endpoints are local subprocess JSON/stdin; NO NETWORK and NO provider.
Client must pre-pin the witness's public key OUTSIDE witness responses.
"""
import base64
import binascii
from contextlib import closing
import json
import os
from pathlib import Path
import re
import sqlite3
import sys

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from aion_p0_a145_checkpoint_verifier_lab import canonical_history_digest
from aion_p0_a146_highwater_gate_lab import HighWater, HighWaterRejected, _validate
from aion_p0_a146_signed_highwater_lab import SignedHighWater, canonical_highwater_bytes

_DB = "a148_volatile_trust_domain.sqlite3"
_KEY = "a148_synthetic_signer.key"
_DDL = ("CREATE TABLE witness_head (singleton INTEGER PRIMARY KEY CHECK(singleton=1),"
        " ledger_id TEXT NOT NULL, sequence INTEGER NOT NULL,"
        " history_digest TEXT NOT NULL)")
_ID = re.compile(r"[A-Za-z0-9_-]{1,80}\Z")
_KEY_ID = "a148-synthetic-key"
LAB_MARKER = "A148_SPLIT_PROCESS_SYNTHETIC_NOT_INDEPENDENT"


class WitnessUnavailable(HighWaterRejected):
    pass


def _lab_required():
    if os.environ.get("AION_LAB_MODE") != "1":
        raise WitnessUnavailable("lab_mode_required")
    if os.environ.get("AION_WORKER_ENABLED") != "0":
        raise WitnessUnavailable("worker_must_be_disabled")
    if os.environ.get("AION_EXTERNAL_EXECUTION_ENABLED") != "0":
        raise WitnessUnavailable("external_execution_must_be_disabled")


def _directory(folder):
    root = Path(folder)
    if root.is_symlink() or not root.is_dir():
        raise WitnessUnavailable("invalid_witness_directory")
    return root


def _valid_id(ledger_id):
    if type(ledger_id) is not str or not _ID.fullmatch(ledger_id):
        raise WitnessUnavailable("invalid_ledger_id")


class SeparateProcessWitnessLAB:
    """SQLite CAS and test-only Ed25519 signer. NOT rollback-protected."""

    def __init__(self, *, witness_dir, ledger_id):
        _lab_required()
        _valid_id(ledger_id)
        self.root = _directory(witness_dir)
        self.ledger_id = ledger_id
        self.db_path = self.root / _DB
        self.key_path = self.root / _KEY
        if (self.db_path.is_symlink() or not self.db_path.is_file()
                or self.key_path.is_symlink() or not self.key_path.is_file()):
            raise WitnessUnavailable("missing_witness_db_or_key")
        self.read()

    @classmethod
    def bootstrap_synthetic(cls, *, witness_dir, ledger_id, private_key_raw):
        _lab_required()
        _valid_id(ledger_id)
        root = _directory(witness_dir)
        db_path, key_path = root / _DB, root / _KEY
        if db_path.exists() or db_path.is_symlink() or key_path.exists() or key_path.is_symlink():
            raise WitnessUnavailable("witness_rebootstrap_forbidden")
        if type(private_key_raw) is not bytes or len(private_key_raw) != 32:
            raise WitnessUnavailable("invalid_synthetic_key")
        try:
            Ed25519PrivateKey.from_private_bytes(private_key_raw)
            with key_path.open("xb") as out:
                out.write(private_key_raw)
            if os.name == "posix":
                key_path.chmod(0o600)
            with db_path.open("xb"):
                pass
            with closing(sqlite3.connect(db_path, isolation_level=None, timeout=2)) as db:
                db.execute("PRAGMA synchronous=FULL")
                db.execute("BEGIN IMMEDIATE")
                db.execute(_DDL)
                db.execute(
                    "INSERT INTO witness_head(singleton,ledger_id,sequence,history_digest)"
                    " VALUES (1,?,?,?)",
                    (ledger_id, 0, canonical_history_digest([])),
                )
                db.execute("COMMIT")
        except (OSError, sqlite3.Error, ValueError) as exc:
            raise WitnessUnavailable("synthetic_witness_bootstrap_failed") from exc
        return cls(witness_dir=root, ledger_id=ledger_id)

    def _connect(self, *, writable=False):
        _lab_required()
        if self.db_path.is_symlink() or not self.db_path.is_file():
            raise WitnessUnavailable("witness_database_missing")
        uri = self.db_path.resolve().as_uri() + ("?mode=rw" if writable else "?mode=ro")
        try:
            db = sqlite3.connect(uri, uri=True, timeout=2, isolation_level=None)
            if writable:
                db.execute("PRAGMA synchronous=FULL")
            return db
        except sqlite3.Error as exc:
            raise WitnessUnavailable("witness_database_open_failed") from exc

    def _validate_db(self, db):
        try:
            schema = db.execute(
                "SELECT type,name,tbl_name,sql FROM sqlite_master"
            ).fetchall()
            if schema != [("table", "witness_head", "witness_head", _DDL)]:
                raise WitnessUnavailable("unexpected_witness_schema")
            if db.execute("PRAGMA quick_check").fetchone() != ("ok",):
                raise WitnessUnavailable("witness_database_corrupt")
            records = db.execute(
                "SELECT singleton,ledger_id,sequence,history_digest FROM witness_head"
            ).fetchall()
            if len(records) != 1 or records[0][0] != 1:
                raise WitnessUnavailable("witness_head_missing_or_extra")
            row = records[0]
            head = HighWater(row[1], row[2], row[3])
            _validate(head)
            if head.ledger_id != self.ledger_id:
                raise WitnessUnavailable("witness_identity_mismatch")
            return head
        except sqlite3.Error as exc:
            raise WitnessUnavailable("witness_validation_failure") from exc

    def _sign(self, head):
        _lab_required()
        if self.key_path.is_symlink() or not self.key_path.is_file():
            raise WitnessUnavailable("signer_key_missing_or_symlinked")
        try:
            secret = self.key_path.read_bytes()
            if len(secret) != 32:
                raise WitnessUnavailable("signer_key_invalid")
            signer = Ed25519PrivateKey.from_private_bytes(secret)
            signature = signer.sign(canonical_highwater_bytes(head))
            return SignedHighWater(head, _KEY_ID, base64.b64encode(signature).decode("ascii"))
        except (OSError, ValueError) as exc:
            raise WitnessUnavailable("signing_failure") from exc

    def read(self):
        with closing(self._connect()) as db:
            db.execute("BEGIN")
            head = self._validate_db(db)
            db.execute("COMMIT")
        return self._sign(head)

    def publish(self, *, anchor, expected_sequence, fault=None):
        """Atomic *LOCAL WITNESS* CAS, not a transaction with the local journal.

        publish does not verify caller authorization. Synthetic simulator only.
        If test fault is injected after COMMIT, response is intentionally lost.
        """
        _lab_required()
        _validate(anchor)
        if anchor.ledger_id != self.ledger_id:
            raise WitnessUnavailable("publish_identity_mismatch")
        if type(expected_sequence) is not int or expected_sequence < 0:
            raise WitnessUnavailable("invalid_cas_expectation")
        if fault is not None and (fault not in ("crash_before_commit", "crash_after_commit")
                                  or os.environ.get("AION_A148_FAULT_LAB") != "1"):
            raise WitnessUnavailable("unauthorized_fault_injection")
        try:
            with closing(self._connect(writable=True)) as db:
                db.execute("BEGIN IMMEDIATE")
                old = self._validate_db(db)
                if old.sequence != expected_sequence:
                    raise WitnessUnavailable("witness_cas_conflict")
                if anchor.sequence == old.sequence:
                    if anchor.history_digest != old.history_digest:
                        raise WitnessUnavailable("witness_same_sequence_conflict")
                elif anchor.sequence != old.sequence + 1:
                    raise WitnessUnavailable("witness_nonmonotonic_or_gap")
                if anchor != old:
                    db.execute(
                        "UPDATE witness_head SET sequence=?,history_digest=? WHERE singleton=1",
                        (anchor.sequence, anchor.history_digest),
                    )
                if fault == "crash_before_commit":
                    os._exit(81)  # test-only abrupt process death
                db.execute("COMMIT")
                if fault == "crash_after_commit":
                    os._exit(82)  # committed but acknowledgment lost
            return self._sign(anchor)
        except sqlite3.Error as exc:
            raise WitnessUnavailable("witness_publish_uncertain") from exc


def _reject_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise WitnessUnavailable("duplicate_request_field")
        result[key] = value
    return result


def run_cli():
    try:
        _lab_required()
        request = json.load(sys.stdin, object_pairs_hook=_reject_duplicate_keys)
        if type(request) is not dict or set(request) - {"operation", "directory", "ledger_id",
                                                        "sequence", "history_digest",
                                                        "expected_sequence", "fault"}:
            raise WitnessUnavailable("invalid_request_shape")
        if set(("operation", "directory", "ledger_id")) - set(request):
            raise WitnessUnavailable("missing_request_field")
        witness = SeparateProcessWitnessLAB(
            witness_dir=request["directory"], ledger_id=request["ledger_id"]
        )
        if request["operation"] == "read":
            if set(request) != {"operation", "directory", "ledger_id"}:
                raise WitnessUnavailable("invalid_read_request")
            signed = witness.read()
        elif request["operation"] == "publish":
            required = {"operation", "directory", "ledger_id", "sequence",
                        "history_digest", "expected_sequence"}
            if set(request) not in (required, required | {"fault"}):
                raise WitnessUnavailable("invalid_publish_request")
            signed = witness.publish(
                anchor=HighWater(request["ledger_id"], request["sequence"], request["history_digest"]),
                expected_sequence=request["expected_sequence"], fault=request.get("fault")
            )
        else:
            raise WitnessUnavailable("unsupported_operation")
        result = {"marker": LAB_MARKER, "ledger_id": signed.anchor.ledger_id,
                  "sequence": signed.anchor.sequence,
                  "history_digest": signed.anchor.history_digest,
                  "key_id": signed.key_id, "signature_b64": signed.signature_b64}
        print(json.dumps(result, sort_keys=True), flush=True)
        return 0
    except (WitnessUnavailable, HighWaterRejected, TypeError, ValueError, OSError,
            sqlite3.Error, json.JSONDecodeError) as exc:
        print(json.dumps({"error": str(exc), "marker": LAB_MARKER}), flush=True)
        return 2


if __name__ == "__main__":
    sys.exit(run_cli())
