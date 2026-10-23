"""A189 LAB ONLY — local SQLite ledger and *untrusted* JSON sequence witness.

Demonstrate independent-file rollback detection and its fundamental failure
against a same-host attacker able to roll back both files or forge the witness.
This is NOT a trusted monotonic counter, a signature, a receipt, an OS sandbox,
a VFS pin, a remote service or an AION runtime integration.
"""
from __future__ import annotations

from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import sqlite3
from uuid import uuid4

WITNESS_SCHEMA = "A189_SYNTHETIC_LOCAL_UNTRUSTED_V1"


class GateClosed(RuntimeError):
    """Do not reauthorize/retry on missing, inconsistent or unverifiable custody."""


def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def _digest(value: object) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


class LocalWitnessLab:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.db_path = self.root / "intents.sqlite"
        self.witness_path = self.root / "epoch.local.json"

    def _rows(self, conn: sqlite3.Connection) -> list[list[object]]:
        return [list(row) for row in conn.execute(
            "SELECT seq,request_id,event_id,payload_hash FROM reservations ORDER BY seq"
        ).fetchall()]

    def _state(self, conn: sqlite3.Connection) -> dict[str, object]:
        rows = self._rows(conn)
        return {"schema": WITNESS_SCHEMA, "seq": int(rows[-1][0]) if rows else 0,
                "digest": _digest(rows)}

    def _witness(self) -> dict[str, object]:
        try:
            raw = self.witness_path.read_bytes()
        except OSError as exc:
            raise GateClosed("A189_WITNESS_UNAVAILABLE") from exc
        if len(raw) > 1024:
            raise GateClosed("A189_WITNESS_INVALID")
        try:
            value = json.loads(raw)
        except (ValueError, UnicodeError) as exc:
            raise GateClosed("A189_WITNESS_INVALID") from exc
        if not isinstance(value, dict) or set(value) != {"schema", "seq", "digest"}:
            raise GateClosed("A189_WITNESS_INVALID")
        if value["schema"] != WITNESS_SCHEMA or type(value["seq"]) is not int or value["seq"] < 0:
            raise GateClosed("A189_WITNESS_INVALID")
        if not isinstance(value["digest"], str) or len(value["digest"]) != 64:
            raise GateClosed("A189_WITNESS_INVALID")
        return value

    def _assert_matched(self, conn: sqlite3.Connection) -> dict[str, object]:
        current = self._state(conn)
        if current != self._witness():
            raise GateClosed("A189_ROLLBACK_OR_DIVERGENCE_DENIED")
        return current

    def _publish_witness(self, value: dict[str, object]) -> None:
        # Best-effort same-host fsync, NOT a cross-file atomic commit or
        # a power-loss/hostile-host monotonicity guarantee.
        temp = self.witness_path.with_name(self.witness_path.name + ".tmp-" + uuid4().hex)
        try:
            with temp.open("xb") as f:
                f.write(_canonical(value))
                f.flush()
                os.fsync(f.fileno())
            os.replace(temp, self.witness_path)
        finally:
            temp.unlink(missing_ok=True)

    def bootstrap_synthetic(self) -> None:
        """Manual LAB-only genesis. It deliberately cannot silently re-enroll."""
        if self.db_path.exists() or self.witness_path.exists():
            raise GateClosed("A189_REENROLLMENT_REQUIRES_MANUAL_REVIEW")
        self.root.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.db_path)) as db:
            db.execute("PRAGMA journal_mode=DELETE")
            db.execute("""CREATE TABLE reservations (
                seq INTEGER PRIMARY KEY,
                request_id TEXT NOT NULL UNIQUE,
                event_id TEXT NOT NULL UNIQUE,
                payload_hash TEXT NOT NULL
            )""")
            db.commit()
            initial = self._state(db)
        self._publish_witness(initial)

    def admission(self) -> dict[str, object]:
        if not self.db_path.is_file():
            raise GateClosed("A189_DB_UNAVAILABLE")
        with closing(sqlite3.connect(self.db_path)) as db:
            state = self._assert_matched(db)
        return {"status": "ADMITTED_LOCAL_UNTRUSTED", "seq": state["seq"]}

    def reserve(self, request_id: str, event_id: str, payload: str, *,
                fail_after_db_commit: bool = False,
                lose_ack_after_witness: bool = False) -> dict[str, object]:
        if not all(type(s) is str and 0 < len(s) <= 128 for s in (request_id, event_id, payload)):
            raise GateClosed("A189_INVALID_INTENT")
        if not self.db_path.is_file():
            raise GateClosed("A189_DB_UNAVAILABLE")
        try:
            with closing(sqlite3.connect(self.db_path, timeout=3.0)) as db:
                db.execute("BEGIN IMMEDIATE")
                state = self._assert_matched(db)
                checksum = _digest({"payload": payload})
                row = db.execute(
                    "SELECT event_id,payload_hash FROM reservations WHERE request_id=?",
                    (request_id,),
                ).fetchone()
                if row:
                    db.rollback()
                    return {"status": "ALREADY_RESERVED_LOCAL" if row == (event_id, checksum)
                            else "DENIED_REQUEST_CONFLICT", "auto_resend": False}
                if db.execute("SELECT 1 FROM reservations WHERE event_id=?", (event_id,)).fetchone():
                    db.rollback()
                    return {"status": "DENIED_EVENT_ALREADY_RESERVED", "auto_resend": False}
                db.execute(
                    "INSERT INTO reservations(seq,request_id,event_id,payload_hash) VALUES(?,?,?,?)",
                    (int(state["seq"]) + 1, request_id, event_id, checksum),
                )
                next_state = self._state(db)
                db.commit()
                # From now on DB and local witness may diverge. Never retry a
                # reservation or an external effect just because ACK is absent.
                if fail_after_db_commit:
                    return {"status": "UNCERTAIN", "auto_resend": False}
                try:
                    self._publish_witness(next_state)
                except OSError:
                    return {"status": "UNCERTAIN", "auto_resend": False}
                if lose_ack_after_witness:
                    return {"status": "UNCERTAIN", "auto_resend": False}
                return {"status": "RESERVED_LOCAL_ONLY", "seq": next_state["seq"],
                        "auto_resend": False}
        except sqlite3.DatabaseError as exc:
            raise GateClosed("A189_SQLITE_GATE_UNAVAILABLE") from exc
