"""G134 process-separated, same-host custody fixture. LAB ONLY; NOT external trust.

This is a subprocess-accessed *local* SQLite witness outside the AION store
directory. It demonstrates which boundaries a genuine independent custodian
must enforce, and why same-host root/admin rollback still defeats this fixture.
Never import as an operational provider, authority, or trusted first-send gate.
"""
from __future__ import annotations

from contextlib import closing
from pathlib import Path
import re
import sqlite3
import sys


ADMITTED = "ADMITTED_LOCAL_PROCESS_LAB_NOT_AUTHORITY"
UNCERTAIN = "DENY_ALREADY_RESERVED_UNCERTAIN_NO_AUTO_RESEND"
LOST_ACK = "ACK_LOST_UNCERTAIN_ZERO_AUTO_RESEND"
UNAVAILABLE = "DENY_CUSTODY_UNAVAILABLE_NO_SEND"
BAD_INPUT = "DENY_UNAUTHENTICATED_INPUT_NO_SEND"
BAD_STATE = "DENY_CUSTODY_INTEGRITY_NO_SEND"

_TOKEN = re.compile(r"[A-Za-z0-9._:-]{1,128}\\Z")
_SHA = re.compile(r"[0-9a-f]{64}\\Z")


def bootstrap_fixture(path: Path) -> None:
    """Explicit lab provisioning; must NEVER run during reservation/recovery."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise RuntimeError("G134_CUSTODY_BOOTSTRAP_EXISTS")
    with closing(sqlite3.connect(path, timeout=3)) as db:
        db.execute("PRAGMA journal_mode=DELETE")
        db.execute(
            "CREATE TABLE custody_state("
            "slot INTEGER PRIMARY KEY CHECK(slot=1),"
            "sequence INTEGER NOT NULL CHECK(sequence >= 0))"
        )
        db.execute("INSERT INTO custody_state(slot,sequence) VALUES(1,0)")
        db.execute(
            "CREATE TABLE reservations("
            "tenant TEXT NOT NULL, event_id TEXT NOT NULL,"
            "payload_sha256 TEXT NOT NULL, request_ref TEXT NOT NULL,"
            "sequence INTEGER UNIQUE NOT NULL,"
            "PRIMARY KEY(tenant,event_id))"
        )
        db.commit()


def reserve_once(path: Path, tenant: str, event_id: str, digest: str,
                 request_ref: str, *, simulate_lost_ack: bool = False) -> str:
    """One atomic LOCAL reservation, with fail-closed unexpected outcomes.

    Caller-controlled tenant/event/digest/authority: no HUMAN_OWNER attestation,
    no external root, no file-descriptor anti-rollback and no provider proof.
    """
    if not all(_TOKEN.fullmatch(v) for v in (tenant, event_id, request_ref)):
        return BAD_INPUT
    if not _SHA.fullmatch(digest):
        return BAD_INPUT
    if not path.is_file():
        return UNAVAILABLE  # fail-closed; NEVER auto-create a new custodian
    try:
        # mode=rw prohibits the implicit creation of a fresh empty database.
        uri = path.resolve().as_uri() + "?mode=rw"
        with closing(sqlite3.connect(uri, uri=True, timeout=3, isolation_level=None)) as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT sequence FROM custody_state WHERE slot=1"
            ).fetchone()
            if row is None or type(row[0]) is not int or row[0] < 0:
                db.rollback()
                return BAD_STATE
            existing = db.execute(
                "SELECT sequence FROM reservations WHERE tenant=? AND event_id=?",
                (tenant, event_id),
            ).fetchone()
            if existing is not None:
                db.rollback()
                return UNCERTAIN  # even same request_ref: no automatic retry
            # Refuse inconsistent or missing historical sequence after corruption.
            maximum, count = db.execute(
                "SELECT COALESCE(MAX(sequence),0), COUNT(*) FROM reservations"
            ).fetchone()
            if maximum != row[0] or count != row[0]:
                db.rollback()
                return BAD_STATE
            next_seq = row[0] + 1
            db.execute(
                "INSERT INTO reservations(tenant,event_id,payload_sha256,request_ref,sequence)"
                " VALUES(?,?,?,?,?)",
                (tenant, event_id, digest, request_ref, next_seq),
            )
            db.execute(
                "UPDATE custody_state SET sequence=? WHERE slot=1 AND sequence=?",
                (next_seq, row[0]),
            )
            db.commit()
            # LAB simulated ACK loss: COMMIT definitely happened; caller cannot
            # infer that no reservation exists merely because no ACK came back.
            return LOST_ACK if simulate_lost_ack else ADMITTED
    except (OSError, sqlite3.Error, ValueError, TypeError):
        return BAD_STATE


def main(argv: list[str]) -> int:
    if len(argv) == 3 and argv[1] == "bootstrap":
        bootstrap_fixture(Path(argv[2]))
        print("G134_EXPLICIT_LOCAL_FIXTURE_BOOTSTRAP")
        return 0
    if len(argv) in (7, 8) and argv[1] == "reserve":
        result = reserve_once(
            Path(argv[2]), argv[3], argv[4], argv[5], argv[6],
            simulate_lost_ack=len(argv) == 8 and argv[7] == "lose-ack",
        )
        print(result)
        return 0
    raise SystemExit("G134_INVALID_LAB_WORKER_ARGUMENTS")


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
