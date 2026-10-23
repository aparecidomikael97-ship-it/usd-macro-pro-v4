"""A188 LAB ONLY — broker-process SQLite boundary with untrusted local custody.

No action adapter, external provider, live keys, credential bootstrap or production
integration. This deliberately exhibits raw-file and rollback bypasses. A green
negative-control suite is NOT a P0 security gate or a deploy approval.
"""
from __future__ import annotations

import hashlib
import multiprocessing
import sqlite3
from pathlib import Path
from typing import Any

SCHEMA = "A188_SYNTHETIC_SQLITE_BROKER_LAB_V1"


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _worker(conn: Any, path: str, local_token: str) -> None:
    """Own one SQLite connection inside the child. Never send the handle."""
    db = None
    try:
        db = sqlite3.connect(path, timeout=5.0)
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("PRAGMA busy_timeout=5000")
        db.execute("""CREATE TABLE IF NOT EXISTS lab_reservations (
            request_id TEXT PRIMARY KEY,
            event_id TEXT NOT NULL,
            payload_hash TEXT NOT NULL,
            status TEXT NOT NULL CHECK (status='RESERVED')
        )""")
        db.commit()
        conn.send({"kind": "READY", "schema": SCHEMA})
        while True:
            try:
                msg = conn.recv()
            except EOFError:
                break
            if not isinstance(msg, dict):
                conn.send({"status": "DENIED_INVALID_MESSAGE"})
                continue
            if msg.get("token") != local_token:
                conn.send({"status": "DENIED_UNAUTHENTICATED_LOCAL_TOKEN"})
                continue
            op = msg.get("op")
            if op == "shutdown":
                conn.send({"status": "SHUTDOWN"})
                break
            if op == "reserve":
                key, event, payload = msg.get("request_id"), msg.get("event_id"), msg.get("payload")
                if not all(isinstance(v, str) and 0 < len(v) <= 128 for v in (key, event, payload)):
                    conn.send({"status": "DENIED_INVALID_RESERVATION"})
                    continue
                checksum = _hash(payload)
                with db:
                    row = db.execute(
                        "SELECT event_id,payload_hash FROM lab_reservations WHERE request_id=?",
                        (key,),
                    ).fetchone()
                    if row:
                        result = {"status": "ALREADY_RESERVED" if row == (event, checksum) else "DENIED_REQUEST_CONFLICT"}
                    else:
                        db.execute("INSERT INTO lab_reservations VALUES(?,?,?,'RESERVED')", (key, event, checksum))
                        result = {"status": "RESERVED_LOCAL_ONLY"}
                if msg.get("simulate_ack_loss") is True:
                    # Deliberately lose post-commit ACK. No external action is sent.
                    # Closing the pipe makes the parent retain UNCERTAIN.
                    break
                conn.send(result)
            elif op == "lookup_local":
                key = msg.get("request_id")
                if not isinstance(key, str):
                    conn.send({"status": "DENIED_INVALID_LOOKUP"})
                    continue
                row = db.execute(
                    "SELECT event_id,status FROM lab_reservations WHERE request_id=?", (key,)
                ).fetchone()
                # Explicitly not a receipt of external effect or monotonic witness.
                conn.send({"status": "OBSERVED_LOCAL_UNTRUSTED", "found": bool(row)})
            elif op == "count_local":
                count = db.execute("SELECT COUNT(*) FROM lab_reservations").fetchone()[0]
                conn.send({"status": "LOCAL_COUNT_UNTRUSTED", "count": count})
            else:
                conn.send({"status": "DENIED_UNSUPPORTED_OPERATION"})
    finally:
        if db is not None:
            db.close()
        conn.close()


class BrokerLab:
    """Test controller; same-host parent token is NOT an independent authority."""

    def __init__(self, path: Path, token: str = "synthetic-local-token"):
        self.path = Path(path)
        self.token = token
        ctx = multiprocessing.get_context("spawn")
        parent, child = ctx.Pipe(duplex=True)
        self.conn = parent
        self.process = ctx.Process(target=_worker, args=(child, str(self.path), token))
        self.process.start()
        child.close()
        if not self.conn.poll(12):
            self.close()
            raise RuntimeError("A188_BROKER_BOOT_TIMEOUT")
        ready = self.conn.recv()
        if ready != {"kind": "READY", "schema": SCHEMA}:
            self.close()
            raise RuntimeError("A188_BROKER_NOT_READY")

    def request(self, op: str, *, token: str | None = None, **kwargs: Any) -> dict[str, Any]:
        msg = {"op": op, "token": self.token if token is None else token, **kwargs}
        try:
            self.conn.send(msg)
            if not self.conn.poll(8):
                return {"status": "UNCERTAIN", "auto_resend": False}
            return self.conn.recv()
        except (EOFError, BrokenPipeError, OSError):
            return {"status": "UNCERTAIN", "auto_resend": False}

    def close(self) -> None:
        if self.process.is_alive():
            try:
                if not self.conn.closed:
                    self.request("shutdown")
            except Exception:
                pass
            self.process.join(timeout=5)
            if self.process.is_alive():
                self.process.terminate()
                self.process.join(timeout=5)
        if not self.conn.closed:
            self.conn.close()

    def __enter__(self) -> "BrokerLab":
        return self

    def __exit__(self, _type: Any, _value: Any, _tb: Any) -> None:
        self.close()
