"""G113 isolated-process witness emulator: synthetic only, never production.

This subprocess and its SQLite file reside on the SAME host and the caller
supplies the signing seed! A host admin can delete/rebootstrap the ledger,
replace keys or rewind it. This is explicitly NOT independent P0 custody.
No network, API, real provider or production Worker occurs in this module.
"""
from __future__ import annotations

import argparse
import base64
from contextlib import closing
import json
from pathlib import Path
import re
import sqlite3
import sys

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from aion_chat.signed_receipt_lab import canonical_bytes

SCHEMA = "AION:G113:PROCESS_WITNESS:V1"
DOMAIN = b"AION:G113:SUBPROCESS_WITNESS:V1\x00"
ISSUER = "g113-same-host-lab"
_HEX = re.compile(r"[a-f0-9]{64}\Z")
_SCOPE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}\Z")
_ENROLL_FIELDS = frozenset({
    "event_id", "original_sha256", "owner_id", "tenant_id", "workspace_id"
})
_RESERVE_FIELDS = _ENROLL_FIELDS | frozenset({
    "challenge", "effect_digest", "idempotency_key"
})
_STATUS_FIELDS = frozenset({"event_id", "challenge"})


class SyntheticWitnessUnavailable(RuntimeError):
    pass


def _validate_fields(payload, required):
    if type(payload) is not dict or set(payload) != required:
        raise SyntheticWitnessUnavailable("G113_EXACT_REQUEST_SCHEMA_REQUIRED")
    for field in required:
        if type(payload[field]) is not str:
            raise SyntheticWitnessUnavailable("G113_BAD_REQUEST_FIELD")
        regex = _SCOPE if field in ("owner_id", "tenant_id", "workspace_id") else _HEX
        if not regex.fullmatch(payload[field]):
            raise SyntheticWitnessUnavailable("G113_BAD_REQUEST_VALUE")


def _open_existing(path):
    if not path.is_file():
        raise SyntheticWitnessUnavailable("G113_WITNESS_MISSING_NO_BOOTSTRAP")
    # mode=rw cannot create a database if the file was removed during open.
    try:
        db = sqlite3.connect(path.resolve().as_uri() + "?mode=rw",
                             uri=True, timeout=3, isolation_level=None)
    except sqlite3.Error as exc:
        raise SyntheticWitnessUnavailable("G113_WITNESS_UNAVAILABLE") from exc
    return db


def _check_schema(db):
    if db.execute("PRAGMA quick_check").fetchone() != ("ok",):
        raise SyntheticWitnessUnavailable("G113_SQLITE_INTEGRITY_DENIED")
    tables = {r[0] for r in db.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    )}
    if tables != {"witness_meta", "event_enrollments"}:
        raise SyntheticWitnessUnavailable("G113_SCHEMA_DENIED")
    row = db.execute("SELECT high_water FROM witness_meta WHERE singleton=1").fetchone()
    if row is None or type(row[0]) is not int or row[0] < 0:
        raise SyntheticWitnessUnavailable("G113_META_DENIED")


def bootstrap(path):
    """Explicit LAB re-enrollment only. Privileged host can misuse it."""
    path = Path(path)
    if not path.parent.is_dir() or path.exists():
        raise SyntheticWitnessUnavailable("G113_EXPLICIT_FRESH_BOOTSTRAP_ONLY")
    try:
        with closing(sqlite3.connect(str(path), timeout=3, isolation_level=None)) as db:
            db.execute("PRAGMA synchronous=FULL")
            db.execute("BEGIN IMMEDIATE")
            db.execute(
                "CREATE TABLE witness_meta("
                "singleton INTEGER PRIMARY KEY CHECK(singleton=1),"
                "high_water INTEGER NOT NULL CHECK(high_water>=0))"
            )
            db.execute("INSERT INTO witness_meta VALUES(1,0)")
            db.execute(
                "CREATE TABLE event_enrollments("
                "event_id TEXT PRIMARY KEY,original_sha256 TEXT NOT NULL,"
                "owner_id TEXT NOT NULL,tenant_id TEXT NOT NULL,"
                "workspace_id TEXT NOT NULL,effect_digest TEXT,"
                "idempotency_key TEXT,sequence INTEGER UNIQUE)"
            )
            db.commit()
    except sqlite3.Error as exc:
        raise SyntheticWitnessUnavailable("G113_BOOTSTRAP_FAILED") from exc
    return {"status": "BOOTSTRAPPED_SYNTHETIC_ONLY"}


def _current_snapshot(db):
    meta = db.execute(
        "SELECT high_water FROM witness_meta WHERE singleton=1"
    ).fetchone()
    if meta is None or type(meta[0]) is not int or meta[0] < 0:
        raise SyntheticWitnessUnavailable("G113_META_UNAVAILABLE")
    count = db.execute(
        "SELECT count(*) FROM event_enrollments WHERE sequence IS NOT NULL"
    ).fetchone()[0]
    if meta[0] != count:
        raise SyntheticWitnessUnavailable("G113_ORDINAL_COUNT_MISMATCH")
    return meta[0], count


def _row(db, event_id):
    return db.execute(
        "SELECT event_id,original_sha256,owner_id,tenant_id,workspace_id,"
        "effect_digest,idempotency_key,sequence FROM event_enrollments "
        "WHERE event_id=?", (event_id,)
    ).fetchone()


def _signed(private_key, request_challenge, status, row, high_water, count, event_id):
    if row is None:
        original, owner, tenant, workspace = "", "", "", ""
        effect, request_id, sequence = "", "", 0
    else:
        original, owner, tenant, workspace = row[1:5]
        effect, request_id, sequence = row[5], row[6], row[7]
        effect = effect or ""
        request_id = request_id or ""
        sequence = sequence or 0
    payload = {
        "schema": SCHEMA, "issuer": ISSUER, "status": status,
        "challenge": request_challenge, "event_id": event_id,
        "original_sha256": original, "owner_id": owner,
        "tenant_id": tenant, "workspace_id": workspace,
        "effect_digest": effect, "idempotency_key": request_id,
        "sequence": sequence, "high_water": high_water, "count": count,
    }
    signature = private_key.sign(DOMAIN + canonical_bytes(payload))
    return {"payload": payload, "signature": base64.b64encode(signature).decode("ascii")}


def execute(path, private_key, action, request):
    """Execute exactly one IPC command in a distinct process, then exit."""
    if action == "bootstrap":
        if request != {}:
            raise SyntheticWitnessUnavailable("G113_BOOTSTRAP_EXACT_EMPTY_BODY")
        return bootstrap(path)
    fields = {
        "enroll": _ENROLL_FIELDS,
        "reserve": _RESERVE_FIELDS,
        "status": _STATUS_FIELDS,
    }.get(action)
    if fields is None:
        raise SyntheticWitnessUnavailable("G113_ACTION_DENIED")
    _validate_fields(request, fields)
    try:
        with closing(_open_existing(Path(path))) as db:
            _check_schema(db)
            if action == "enroll":
                db.execute("BEGIN IMMEDIATE")
                try:
                    previous = _row(db, request["event_id"])
                    if previous is not None:
                        status = ("ALREADY_ENROLLED" if
                                  tuple(previous[1:5]) ==
                                  tuple(request[name] for name in (
                                      "original_sha256", "owner_id", "tenant_id",
                                      "workspace_id")) else "ENROLLMENT_CONFLICT")
                    else:
                        db.execute(
                            "INSERT INTO event_enrollments("
                            "event_id,original_sha256,owner_id,tenant_id,workspace_id)"
                            " VALUES(?,?,?,?,?)",
                            tuple(request[name] for name in (
                                "event_id", "original_sha256", "owner_id",
                                "tenant_id", "workspace_id"))
                        )
                        status = "ENROLLED"
                    db.commit()
                except BaseException:
                    db.rollback()
                    raise
                return {"status": status}

            if action == "reserve":
                db.execute("BEGIN IMMEDIATE")
                try:
                    row = _row(db, request["event_id"])
                    high_water, count = _current_snapshot(db)
                    if row is None:
                        status = "UNKNOWN_EVENT_DENIED"
                    elif tuple(row[1:5]) != tuple(request[name] for name in (
                            "original_sha256", "owner_id", "tenant_id",
                            "workspace_id")):
                        status = "ORIGINAL_IDENTITY_DENIED"
                    elif row[7] is not None:
                        status = "ALREADY_RESERVED"
                    else:
                        next_seq = high_water + 1
                        db.execute(
                            "UPDATE event_enrollments SET "
                            "effect_digest=?,idempotency_key=?,sequence=? "
                            "WHERE event_id=? AND sequence IS NULL",
                            (request["effect_digest"], request["idempotency_key"],
                             next_seq, request["event_id"])
                        )
                        db.execute(
                            "UPDATE witness_meta SET high_water=? WHERE singleton=1",
                            (next_seq,)
                        )
                        high_water, count = next_seq, count + 1
                        status = "RESERVED"
                    db.commit()
                except BaseException:
                    db.rollback()
                    raise
                # Sign only AFTER transaction commit. Lost response cannot
                # erase this persisted reservation; do not resubmit SEND.
                row = _row(db, request["event_id"])
                return _signed(private_key, request["challenge"], status, row,
                               high_water, count, request["event_id"])

            # status reads the current record after a process restart.
            db.execute("BEGIN")
            try:
                high_water, count = _current_snapshot(db)
                row = _row(db, request["event_id"])
                status = ("NOT_FOUND" if row is None else
                          "RESERVED" if row[7] is not None else "ENROLLED")
                result = _signed(private_key, request["challenge"], status,
                                 row, high_water, count, request["event_id"])
            finally:
                db.execute("ROLLBACK")
            return result
    except (sqlite3.Error, OSError) as exc:
        raise SyntheticWitnessUnavailable("G113_WITNESS_STORAGE_FAILED") from exc


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("bootstrap", "enroll", "reserve", "status"))
    parser.add_argument("--db", required=True)
    parser.add_argument("--synthetic-seed", required=True)
    args = parser.parse_args()
    try:
        seed = bytes.fromhex(args.synthetic_seed)
        if len(seed) != 32:
            raise ValueError("synthetic Ed25519 seed must be 32 bytes")
        # The seed is controlled by LAB tests; not a secret or production key.
        signer = Ed25519PrivateKey.from_private_bytes(seed)
        line = sys.stdin.buffer.readline(8193)
        if len(line) > 8192 or not line:
            raise SyntheticWitnessUnavailable("G113_MESSAGE_SIZE_OR_BODY_DENIED")
        request = json.loads(line)
        result = execute(Path(args.db), signer, args.action, request)
        sys.stdout.write(json.dumps(result, separators=(",", ":"), sort_keys=True) + "\n")
        return 0
    except (ValueError, TypeError, json.JSONDecodeError,
            SyntheticWitnessUnavailable) as exc:
        print("G113_SYNTHETIC_WITNESS_DENIED:" + type(exc).__name__, file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
