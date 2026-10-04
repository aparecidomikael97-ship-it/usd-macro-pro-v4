"""Persistent replay-protection registry for AION V2.13.

SQLite is used as a local durable uniqueness boundary. Each claim opens its own
connection and uses BEGIN IMMEDIATE, allowing safe process/thread contention.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

SCHEMA_VERSION = 1


def _parse_ts(value: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError("timestamp must be RFC3339 UTC")
    try:
        return datetime.fromisoformat(value[:-1] + "+00:00").astimezone(timezone.utc)
    except Exception as exc:
        raise ValueError("invalid timestamp") from exc


class PersistentNonceRegistry:
    def __init__(self, db_path: str | Path):
        self.path = Path(db_path)
        if self.path.exists() and self.path.is_symlink():
            raise ValueError("nonce registry must not be a symlink")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self):
        conn = sqlite3.connect(str(self.path), timeout=10.0, isolation_level=None)
        conn.execute("PRAGMA synchronous=FULL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _initialize(self):
        with self._connect() as conn:
            # WAL mode is persistent for the database. Set it once during
            # initialization instead of on every competing claim connection.
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS nonce_claims (
                    scope TEXT NOT NULL,
                    nonce TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (scope, nonce)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS nonce_registry_meta (
                    singleton INTEGER PRIMARY KEY CHECK(singleton = 1),
                    schema_version INTEGER NOT NULL
                )
                """
            )
            conn.execute(
                "INSERT OR IGNORE INTO nonce_registry_meta(singleton, schema_version) VALUES(1, ?)",
                (SCHEMA_VERSION,),
            )

    def claim(self, *, scope: str, nonce: str, expires_at: str, now_ts: str) -> bool:
        if not isinstance(scope, str) or not scope or len(scope) > 256:
            raise ValueError("invalid nonce scope")
        if not isinstance(nonce, str) or not nonce or len(nonce) > 256:
            raise ValueError("invalid nonce")
        now = _parse_ts(now_ts)
        exp = _parse_ts(expires_at)
        if exp <= now:
            return False
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                conn.execute("DELETE FROM nonce_claims WHERE expires_at <= ?", (now_ts,))
                conn.execute(
                    "INSERT INTO nonce_claims(scope, nonce, expires_at, created_at) VALUES(?, ?, ?, ?)",
                    (scope, nonce, expires_at, now_ts),
                )
                conn.execute("COMMIT")
                return True
            except sqlite3.IntegrityError:
                conn.execute("ROLLBACK")
                return False
            except Exception:
                conn.execute("ROLLBACK")
                raise

    def contains(self, *, scope: str, nonce: str) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM nonce_claims WHERE scope = ? AND nonce = ?",
                (scope, nonce),
            ).fetchone()
        return row is not None

    def count(self) -> int:
        with self._connect() as conn:
            row = conn.execute("SELECT COUNT(*) FROM nonce_claims").fetchone()
        return int(row[0])
