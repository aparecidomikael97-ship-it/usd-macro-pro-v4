"""A188 LAB ONLY — subprocess SQLite broker, JSON-only IPC, untrusted custody.

This intentionally demonstrates raw SQLite and rollback bypasses. It is NOT
an authenticated root, production sandbox, transaction authority or API server.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import subprocess
import sys
from pathlib import Path
from typing import Any

SCHEMA = "A188_SYNTHETIC_SQLITE_BROKER_LAB_V1"
MAX_MESSAGE = 4096


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _send(obj: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(obj, sort_keys=True) + "\n")
    sys.stdout.flush()


def _worker(path: str, local_token: str) -> None:
    """Own the SQLite handle; accept JSON values, never arbitrary SQL."""
    db = sqlite3.connect(path, timeout=5.0)
    try:
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("PRAGMA busy_timeout=5000")
        db.execute("""CREATE TABLE IF NOT EXISTS lab_reservations (
            request_id TEXT PRIMARY KEY, event_id TEXT NOT NULL,
            payload_hash TEXT NOT NULL, status TEXT NOT NULL CHECK(status='RESERVED')
        )""")
        db.commit()
        _send({"kind": "READY", "schema": SCHEMA})
        while True:
            line = sys.stdin.readline(MAX_MESSAGE + 1)
            if not line:
                break
            if len(line) > MAX_MESSAGE or not line.endswith("\n"):
                _send({"status": "DENIED_OVERSIZED_OR_UNTERMINATED_MESSAGE"})
                break
            try:
                msg = json.loads(line)
            except (ValueError, UnicodeError):
                _send({"status": "DENIED_INVALID_JSON"})
                continue
            if not isinstance(msg, dict):
                _send({"status": "DENIED_INVALID_MESSAGE"})
                continue
            if msg.get("token") != local_token:
                _send({"status": "DENIED_UNAUTHENTICATED_LOCAL_TOKEN"})
                continue
            op = msg.get("op")
            if op == "shutdown":
                _send({"status": "SHUTDOWN"})
                break
            if op == "reserve":
                key, event, payload = msg.get("request_id"), msg.get("event_id"), msg.get("payload")
                if not all(isinstance(v, str) and 0 < len(v) <= 128 for v in (key, event, payload)):
                    _send({"status": "DENIED_INVALID_RESERVATION"})
                    continue
                checksum = _hash(payload)
                with db:
                    row = db.execute("SELECT event_id,payload_hash FROM lab_reservations WHERE request_id=?", (key,)).fetchone()
                    if row:
                        result = {"status": "ALREADY_RESERVED" if row == (event, checksum) else "DENIED_REQUEST_CONFLICT"}
                    else:
                        db.execute("INSERT INTO lab_reservations VALUES(?,?,?,'RESERVED')", (key, event, checksum))
                        result = {"status": "RESERVED_LOCAL_ONLY"}
                if msg.get("simulate_ack_loss") is True:
                    # No actual external effect; simulate missing ACK after commit.
                    break
                _send(result)
            elif op == "lookup_local":
                key = msg.get("request_id")
                if not isinstance(key, str):
                    _send({"status": "DENIED_INVALID_LOOKUP"})
                    continue
                row = db.execute("SELECT 1 FROM lab_reservations WHERE request_id=?", (key,)).fetchone()
                _send({"status": "OBSERVED_LOCAL_UNTRUSTED", "found": bool(row)})
            elif op == "count_local":
                count = db.execute("SELECT COUNT(*) FROM lab_reservations").fetchone()[0]
                _send({"status": "LOCAL_COUNT_UNTRUSTED", "count": count})
            else:
                _send({"status": "DENIED_UNSUPPORTED_OPERATION"})
    finally:
        db.close()


class BrokerLab:
    """Same-host parent retains DB path and synthetic token: NOT independent."""

    def __init__(self, path: Path, token: str = "synthetic-local-token"):
        self.path = Path(path)
        self.token = token
        self.process = subprocess.Popen(
            [sys.executable, "-B", "-u", "-m", "labs.a188.sqlite_process_boundary_lab",
             "--worker", str(self.path), token],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", bufsize=1,
        )
        assert self.process.stdin is not None and self.process.stdout is not None
        line = self.process.stdout.readline()
        if not line:
            error = self.process.stderr.read(2500) if self.process.stderr is not None else ""
            self.close()
            raise RuntimeError("A188_BROKER_START_FAILED: " + error[:300])
        if json.loads(line) != {"kind": "READY", "schema": SCHEMA}:
            self.close()
            raise RuntimeError("A188_BROKER_NOT_READY")

    def request(self, op: str, *, token: str | None = None, **kwargs: Any) -> dict[str, Any]:
        message = {"op": op, "token": self.token if token is None else token, **kwargs}
        try:
            assert self.process.stdin is not None and self.process.stdout is not None
            self.process.stdin.write(json.dumps(message) + "\n")
            self.process.stdin.flush()
            line = self.process.stdout.readline()
            return json.loads(line) if line else {"status": "UNCERTAIN", "auto_resend": False}
        except (BrokenPipeError, OSError, ValueError):
            return {"status": "UNCERTAIN", "auto_resend": False}

    def close(self) -> None:
        if self.process.poll() is None:
            try:
                self.request("shutdown")
            except Exception:
                pass
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5)
        for pipe in (self.process.stdin, self.process.stdout, self.process.stderr):
            if pipe is not None and not pipe.closed:
                pipe.close()

    def __enter__(self) -> "BrokerLab":
        return self

    def __exit__(self, _type: Any, _value: Any, _tb: Any) -> None:
        self.close()


if __name__ == "__main__":
    if len(sys.argv) != 4 or sys.argv[1] != "--worker":
        raise SystemExit("LAB worker only; not a production entrypoint")
    _worker(sys.argv[2], sys.argv[3])
