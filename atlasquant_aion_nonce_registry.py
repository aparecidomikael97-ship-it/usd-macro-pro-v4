"""Persistent replay-protection registry for AION V2.13.

SQLite is used as a local durable uniqueness boundary. Each claim opens its own
connection and uses BEGIN IMMEDIATE, allowing safe process/thread contention.

Expiry comparisons use integer UTC microseconds rather than lexicographic
timestamp text so fractional-second RFC3339 values cannot expire early.
"""
from __future__ import annotations

import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

SCHEMA_VERSION = 2
MAX_SCOPE_LENGTH = 512
_TS_RE = re.compile(
    r"^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.(\d{1,6}))?Z$"
)
_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


def _parse_ts(value: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError("timestamp must be RFC3339 UTC")
    match = _TS_RE.fullmatch(value)
    if match is None:
        raise ValueError("timestamp must be RFC3339 UTC")
    year, month, day, hour, minute, second = (int(match.group(i)) for i in range(1, 7))
    fraction = (match.group(7) or "").ljust(6, "0")
    try:
        return datetime(
            year, month, day, hour, minute, second,
            int(fraction or "0"), tzinfo=timezone.utc,
        )
    except ValueError as exc:
        raise ValueError("invalid timestamp") from exc


def _epoch_us(value: datetime) -> int:
    delta = value - _EPOCH
    return (
        delta.days * 86_400_000_000
        + delta.seconds * 1_000_000
        + delta.microseconds
    )


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
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS nonce_claims (
                    scope TEXT NOT NULL,
                    nonce TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    expires_at_us INTEGER,
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

            columns = {
                str(row[1])
                for row in conn.execute("PRAGMA table_info(nonce_claims)").fetchall()
            }
            if "expires_at_us" not in columns:
                conn.execute("ALTER TABLE nonce_claims ADD COLUMN expires_at_us INTEGER")

            rows = conn.execute(
                "SELECT scope, nonce, expires_at FROM nonce_claims WHERE expires_at_us IS NULL"
            ).fetchall()
            for scope, nonce, expires_at in rows:
                expires_us = _epoch_us(_parse_ts(expires_at))
                conn.execute(
                    "UPDATE nonce_claims SET expires_at_us = ? WHERE scope = ? AND nonce = ?",
                    (expires_us, scope, nonce),
                )

            conn.execute(
                "INSERT OR IGNORE INTO nonce_registry_meta(singleton, schema_version) VALUES(1, ?)",
                (SCHEMA_VERSION,),
            )
            conn.execute(
                "UPDATE nonce_registry_meta SET schema_version = ? WHERE singleton = 1",
                (SCHEMA_VERSION,),
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_nonce_claims_expiry ON nonce_claims(expires_at_us)"
            )

    def claim(self, *, scope: str, nonce: str, expires_at: str, now_ts: str) -> bool:
        if not isinstance(scope, str) or not scope or len(scope) > MAX_SCOPE_LENGTH:
            raise ValueError("invalid nonce scope")
        if not isinstance(nonce, str) or not nonce or len(nonce) > 256:
            raise ValueError("invalid nonce")
        now = _parse_ts(now_ts)
        exp = _parse_ts(expires_at)
        if exp <= now:
            return False
        now_us = _epoch_us(now)
        exp_us = _epoch_us(exp)
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                conn.execute(
                    "DELETE FROM nonce_claims WHERE expires_at_us <= ?",
                    (now_us,),
                )
                conn.execute(
                    """
                    INSERT INTO nonce_claims(
                        scope, nonce, expires_at, expires_at_us, created_at
                    ) VALUES(?, ?, ?, ?, ?)
                    """,
                    (scope, nonce, expires_at, exp_us, now_ts),
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

    def read_claim(self, *, scope: str, nonce: str) -> dict[str, str] | None:
        """Read exact durable claim metadata without mutating or pruning state."""
        if not isinstance(scope, str) or not scope or len(scope) > MAX_SCOPE_LENGTH:
            raise ValueError("invalid nonce scope")
        if not isinstance(nonce, str) or not nonce or len(nonce) > 256:
            raise ValueError("invalid nonce")
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT expires_at, created_at
                FROM nonce_claims
                WHERE scope = ? AND nonce = ?
                """,
                (scope, nonce),
            ).fetchone()
        if row is None:
            return None
        return {
            "scope": scope,
            "nonce": nonce,
            "expires_at": str(row[0]),
            "created_at": str(row[1]),
        }

    def count(self) -> int:
        with self._connect() as conn:
            row = conn.execute("SELECT COUNT(*) FROM nonce_claims").fetchone()
        return int(row[0])

    def schema_version(self) -> int:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT schema_version FROM nonce_registry_meta WHERE singleton = 1"
            ).fetchone()
        if row is None:
            raise RuntimeError("nonce registry metadata missing")
        return int(row[0])
