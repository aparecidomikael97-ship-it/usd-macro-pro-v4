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
import stat
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock

SCHEMA_VERSION = 2
# Conservative non-authorizing LOCAL admission ceiling. This is a count
# limit, not a guarantee of on-disk bytes. No automatic tombstone eviction.
MAX_NONCE_CLAIMS = 100_000
# Serialize fresh-file recognition and SQLite bootstrap inside a single
# Python process. Independent processes cannot share this lock: if a second
# process sees an unfinished existing DB, fail closed instead of re-enrolling.
_BOOTSTRAP_LOCK = RLock()
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
        with _BOOTSTRAP_LOCK:
            if self.path.is_symlink():
                raise ValueError("nonce registry must not be a symlink")
            # Do not confuse another initializer's temporary empty schema
            # (same process) with damaged history. Existing empty databases
            # still fail closed; cross-process partial first-start also
            # fails closed until a valid completed schema is observable.
            self._bootstrap_if_missing = not self.path.exists()
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._ready = False
            self._initialize()
            self._file_identity = self._current_file_identity()
            self._ready = True

    def _current_file_identity(self):
        """Snapshot same-host path identity, NOT a trusted rollback witness.

        Reject symlinks/non-regular files before opening any SQLite handle.
        A local attacker who can replace the whole file can also restore
        snapshots: this only prevents silent path target drift in an instance.
        """
        try:
            st = self.path.lstat()
        except OSError as exc:
            raise RuntimeError("nonce registry file identity unavailable") from exc
        if not stat.S_ISREG(st.st_mode) or self.path.is_symlink():
            raise RuntimeError("nonce registry file path not regular")
        return (st.st_dev, st.st_ino)

    @staticmethod
    def _reject_triggers(conn):
        """No user-defined triggers may rewrite consumed owner nonce history."""
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='trigger' "
            "AND tbl_name IN ('nonce_claims','nonce_registry_meta') LIMIT 1"
        ).fetchone()
        if row is not None:
            raise RuntimeError("nonce registry schema has unauthorized trigger")

    @contextmanager
    def _connect(self):
        """Keep connection lifetime scoped to each operation on every OS.

        sqlite3.Connection.__exit__ only commits/rolls back, it does NOT
        close the handle. Explicit closure prevents retained WAL/DB handles
        and Windows cleanup/share-lock failures. Transaction policy remains
        unchanged: claim() still uses BEGIN IMMEDIATE + explicit COMMIT.
        """
        if getattr(self, "_ready", False):
            if self._current_file_identity() != self._file_identity:
                raise RuntimeError("nonce registry file identity changed")
        conn = sqlite3.connect(
            str(self.path), timeout=10.0, isolation_level=None,
        )
        try:
            conn.execute("PRAGMA synchronous=FULL")
            conn.execute("PRAGMA foreign_keys=ON")
            if getattr(self, "_ready", False):
                if self._current_file_identity() != self._file_identity:
                    raise RuntimeError("nonce registry file identity changed")
                self._reject_triggers(conn)
            # Every authorization/readback call after initialization must
            # reject an externally downgraded journal; never assume startup
            # WAL mode is permanent. Startup itself legitimately negotiates
            # WAL for a fresh or V1 registry.
            if getattr(self, "_ready", False):
                mode = str(conn.execute("PRAGMA journal_mode").fetchone()[0]).lower()
                if mode != "wal":
                    raise RuntimeError("nonce registry WAL journal mode downgraded")
            with conn:
                yield conn
        finally:
            conn.close()

    def _inspect_schema(self, conn):
        """Validate nonce schema without mutating tables or deleting history.

        This check runs twice: before the journal transition, and again
        under the write lock immediately before a permitted migration.
        """
        existing = {
            str(row[0])
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name IN ('nonce_claims','nonce_registry_meta')"
            ).fetchall()
        }
        has_claims = "nonce_claims" in existing
        has_meta = "nonce_registry_meta" in existing
        self._reject_triggers(conn)
        if not has_claims and not has_meta and not self._bootstrap_if_missing:
            raise ValueError("existing nonce registry tables missing; recovery denied")
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
            if "expires_at_us" in fields:
                raise ValueError("nonce registry metadata missing from v2")
            old_version = 1
        if has_claims and not {
            "scope", "nonce", "expires_at", "created_at",
        }.issubset(fields):
            raise ValueError("nonce registry claims columns missing")
        if old_version == SCHEMA_VERSION and "expires_at_us" not in fields:
            raise ValueError("nonce registry v2 expiry column missing")
        return has_meta, old_version, fields

    @staticmethod
    def _rollback_if_open(conn):
        """Do not replace original SQLITE_FULL with a spurious rollback error."""
        if conn.in_transaction:
            try:
                conn.execute("ROLLBACK")
            except sqlite3.Error:
                pass

    @staticmethod
    def _ensure_wal(conn):
        """Establish WAL BEFORE any schema/claim migration is committed."""
        mode = str(conn.execute("PRAGMA journal_mode").fetchone()[0]).lower()
        if mode == "wal":
            return
        import time
        for _attempt in range(50):
            try:
                changed = str(
                    conn.execute("PRAGMA journal_mode=WAL").fetchone()[0]
                ).lower()
                if changed != "wal":
                    raise RuntimeError("nonce registry WAL mode unavailable")
                return
            except sqlite3.OperationalError as exc:
                if "locked" not in str(exc).lower():
                    raise
                time.sleep(0.02)
        raise RuntimeError("nonce registry WAL transition still busy")

    def _initialize(self):
        """Validate before journal negotiation and migrate only AFTER WAL.

        A V1 migration must not commit before successful WAL admission. Each
        validation occurs under BEGIN IMMEDIATE; inspect again after the
        journal transition to defeat intervening schema changes. Incomplete
        bootstrap by a separate process may fail closed rather than invent
        a missing nonce history. Full snapshot rollback remains OPEN H0.
        """
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                self._inspect_schema(conn)
                conn.execute("COMMIT")
            except Exception:
                self._rollback_if_open(conn)
                raise

            # SQLite disallows journal_mode changes inside an active
            # transaction. No metadata or table migration was performed
            # before the following WAL negotiation.
            self._ensure_wal(conn)

            conn.execute("BEGIN IMMEDIATE")
            try:
                has_meta, old_version, fields = self._inspect_schema(conn)
                if str(conn.execute("PRAGMA journal_mode").fetchone()[0]).lower() != "wal":
                    raise RuntimeError("nonce registry WAL mode not active")

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
                self._rollback_if_open(conn)
                raise

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
                # Recheck under the same write transaction: another process
                # cannot change journal_mode while our claim is active.
                if str(conn.execute("PRAGMA journal_mode").fetchone()[0]).lower() != "wal":
                    raise RuntimeError("nonce registry WAL journal mode downgraded")
                if self._current_file_identity() != self._file_identity:
                    raise RuntimeError("nonce registry file identity changed")
                self._reject_triggers(conn)
                # This local quota is a fail-closed admission ceiling, NOT
                # a pruning policy. Check under BEGIN IMMEDIATE so parallel
                # processes cannot admit past the cap. A known consumed nonce
                # remains a replay (False), even when at capacity. Preserve
                # all historic tombstones including expired ones.
                if conn.execute(
                    "SELECT 1 FROM nonce_claims WHERE scope=? AND nonce=?",
                    (scope, nonce),
                ).fetchone() is not None:
                    conn.execute("ROLLBACK")
                    return False
                used = int(conn.execute(
                    "SELECT COUNT(*) FROM nonce_claims"
                ).fetchone()[0])
                if used >= MAX_NONCE_CLAIMS:
                    raise RuntimeError(
                        "nonce registry capacity exhausted; no tombstone eviction"
                    )
                # Tombstone retention intentionally grows; count is not an
                # on-disk byte budget. Full-backup rollback is still OPEN P0.
                inserted = conn.execute(
                    """
                    INSERT INTO nonce_claims(
                        scope, nonce, expires_at, expires_at_us, created_at
                    ) VALUES(?, ?, ?, ?, ?)
                    """,
                    (scope, nonce, expires_at, exp_us, now_ts),
                )
                # SQLite triggers can silently IGNORE an INSERT or DELETE
                # its row without raising. Never report owner nonce usage
                # based only on a successful execute() call.
                expected = (expires_at, exp_us, now_ts)
                if inserted.rowcount != 1 or conn.execute(
                    "SELECT expires_at,expires_at_us,created_at FROM nonce_claims "
                    "WHERE scope=? AND nonce=?",
                    (scope, nonce),
                ).fetchone() != expected:
                    raise RuntimeError("nonce claim not durably written")
                conn.execute("COMMIT")
                # Local same-DB readback is NOT an independent H0 witness.
                if conn.execute(
                    "SELECT expires_at,expires_at_us,created_at FROM nonce_claims "
                    "WHERE scope=? AND nonce=?",
                    (scope, nonce),
                ).fetchone() != expected:
                    raise RuntimeError("nonce claim not durable after commit")
                return True
            except Exception:
                # Not even an unexpected storage failure implies replay.
                # SQLITE_FULL/IOERR may have automatically rolled back;
                # never replace the causal error with a second ROLLBACK error.
                if conn.in_transaction:
                    try:
                        conn.execute("ROLLBACK")
                    except sqlite3.Error:
                        pass
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
