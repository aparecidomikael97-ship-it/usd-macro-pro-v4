"""Persistent replay-protection registry for AION V2.13.

SQLite is used as a local durable uniqueness boundary. Each claim opens its own
connection and uses BEGIN IMMEDIATE, allowing safe process/thread contention.

Expiry comparisons use integer UTC microseconds rather than lexicographic
timestamp text so fractional-second RFC3339 values cannot expire early.
Consumed nonces remain as local tombstones without automatic expiry pruning:
a forward clock jump must not enable replay after a later clock rollback.
This does NOT detect a complete restoration of a previous SQLite snapshot.
"""
from __future__ import annotations

import re
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

SCHEMA_VERSION = 2
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

    @contextmanager
    def _connect(self):
        """Keep connection lifetime scoped to each operation on every OS.

        sqlite3.Connection.__exit__ only commits/rolls back, it does NOT
        close the handle. Explicit closure prevents retained WAL/DB handles
        and Windows cleanup/share-lock failures. Transaction policy remains
        unchanged: claim() still uses BEGIN IMMEDIATE + explicit COMMIT.
        """
        conn = sqlite3.connect(
            str(self.path), timeout=10.0, isolation_level=None,
        )
        try:
            conn.execute("PRAGMA synchronous=FULL")
            conn.execute("PRAGMA foreign_keys=ON")
            with conn:
                yield conn
        finally:
            conn.close()

    def _initialize(self):
        """Fail closed on an incompatible or partially restored nonce schema.

        Validate BEFORE PRAGMA WAL, CREATE TABLE, ALTER or metadata writes.
        An existing v2 registry is not a blank database merely because one
        of its tables disappeared. The one explicitly supported legacy path
        is v1 (or pre-metadata v1), identified by its missing microsecond
        expiry column. This LOCAL schema check cannot detect full DB rollback.
        """
        with self._connect() as conn:
            # Serialize observation, validation and schema mutation across
            # simultaneous first-start processes. SQLite DDL is transactional.
            conn.execute("BEGIN IMMEDIATE")
            try:
                existing = {
                    str(row[0])
                    for row in conn.execute(
                        "SELECT name FROM sqlite_master WHERE type='table' "
                        "AND name IN ('nonce_claims','nonce_registry_meta')"
                    ).fetchall()
                }
                has_claims = "nonce_claims" in existing
                has_meta = "nonce_registry_meta" in existing
                fields = (
                    {str(row[1]) for row in conn.execute(
                        "PRAGMA table_info(nonce_claims)"
                    ).fetchall()}
                    if has_claims else set()
                )
                old_version = None
                if has_meta:
                    rows = conn.execute(
                        "SELECT singleton, schema_version FROM nonce_registry_meta"
                    ).fetchall()
                    if (
                        not has_claims
                        or len(rows) != 1
                        or type(rows[0][0]) is not int
                        or rows[0][0] != 1
                        or type(rows[0][1]) is not int
                        or rows[0][1] not in (1, SCHEMA_VERSION)
                    ):
                        raise ValueError("nonce registry unsupported or incomplete schema")
                    old_version = rows[0][1]
                elif has_claims:
                    # A pre-v2 registry had no schema metadata AND no
                    # expires_at_us. Existing v2 claims with metadata missing
                    # mean partial restore: never recreate the marker silently.
                    if "expires_at_us" in fields:
                        raise ValueError("nonce registry metadata missing from v2")
                    old_version = 1
                if has_claims and not {
                    "scope", "nonce", "expires_at", "created_at",
                }.issubset(fields):
                    raise ValueError("nonce registry claims columns missing")
                if (old_version == SCHEMA_VERSION
                        and "expires_at_us" not in fields):
                    raise ValueError("nonce registry v2 expiry column missing")

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

                if old_version == 1 and "expires_at_us" not in fields:
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

                if not has_meta:
                    conn.execute(
                        "INSERT INTO nonce_registry_meta(singleton,schema_version) VALUES(1,?)",
                        (SCHEMA_VERSION,),
                    )
                elif old_version == 1:
                    conn.execute(
                        "UPDATE nonce_registry_meta SET schema_version=? WHERE singleton=1",
                        (SCHEMA_VERSION,),
                    )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_nonce_claims_expiry ON nonce_claims(expires_at_us)"
                )

                conn.execute("COMMIT")
            except Exception:
                conn.execute("ROLLBACK")
                raise

            # journal_mode cannot be changed inside the transaction. A
            # different initializer may still hold a new BEGIN IMMEDIATE
            # after our commit, so accept transient busy and retry a bounded
            # number of times. Never silently leave expected WAL mode false.
            if str(conn.execute("PRAGMA journal_mode").fetchone()[0]).lower() != "wal":
                import time
                for _attempt in range(50):
                    try:
                        mode = str(
                            conn.execute("PRAGMA journal_mode=WAL").fetchone()[0]
                        ).lower()
                        if mode == "wal":
                            break
                        raise RuntimeError("nonce registry WAL mode unavailable")
                    except sqlite3.OperationalError as exc:
                        if "locked" not in str(exc).lower():
                            raise
                        time.sleep(0.02)
                else:
                    raise RuntimeError("nonce registry WAL transition still busy")

    def claim(self, *, scope: str, nonce: str, expires_at: str, now_ts: str) -> bool:
        if not isinstance(scope, str) or not scope or len(scope) > 256:
            raise ValueError("invalid nonce scope")
        if not isinstance(nonce, str) or not nonce or len(nonce) > 256:
            raise ValueError("invalid nonce")
        now = _parse_ts(now_ts)
        exp = _parse_ts(expires_at)
        if exp <= now:
            return False
        exp_us = _epoch_us(exp)
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                # A claimed nonce is a consumed, durable tombstone.
                # Never prune it as a side effect of another claim:
                # caller-supplied or rolled-back wall-clock time could
                # otherwise re-admit a previously signed owner request.
                # Retention/compaction needs independent anti-rollback
                # custody and an explicit audited policy. Until then,
                # preserve the original UNIQUE(scope,nonce) boundary.
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
        if not isinstance(scope, str) or not scope or len(scope) > 256:
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
