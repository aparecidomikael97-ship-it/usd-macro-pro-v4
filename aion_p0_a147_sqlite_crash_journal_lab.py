"""A147 isolated SQLite crash/reconciliation journal (SYNTHETIC LAB ONLY).

This lab records durable LOCAL intent reservations, never external effects.
It deliberately has no provider, Worker, send/retry or production interfaces.
Every local reservation remains RESERVED_UNCERTAIN, including after restart.
There is NO atomic transaction shared by SQLite and the external witness.
Signed high-water comparison does not prove trusted independent freshness.
"""
from contextlib import closing
from dataclasses import dataclass
import os
from pathlib import Path
import re
import sqlite3

from aion_p0_a145_checkpoint_verifier_lab import CheckpointRejected
from aion_p0_a146_highwater_gate_lab import HighWaterRejected
from aion_p0_a146_signed_highwater_lab import check_restart_with_signed_highwater

DB_NAME = "a147_synthetic_uncertain.sqlite3"
META_DDL = "CREATE TABLE ledger_meta (singleton INTEGER PRIMARY KEY CHECK(singleton=1), ledger_id TEXT NOT NULL)"
EVENTS_DDL = ("CREATE TABLE events (seq INTEGER PRIMARY KEY,"
              " intent TEXT NOT NULL UNIQUE,"
              " state TEXT NOT NULL CHECK(state='RESERVED_UNCERTAIN'))")
_VALID_ID = re.compile(r"[A-Za-z0-9_-]{1,80}\Z")


class JournalUnavailable(RuntimeError):
    pass


class SimulatedBeforeCommitCrash(RuntimeError):
    pass


@dataclass(frozen=True)
class RecoveryDecision:
    verdict: str
    reason: str
    sequence: int
    automatic_retry_allowed: bool = False
    external_execution_allowed: bool = False


class SyntheticCrashJournalLAB:
    """Explicit synthetic bootstrap, read-only reopen, durable local uncertainty."""

    def __init__(self, *, lab_dir, ledger_id):
        if os.environ.get("AION_LAB_MODE") != "1":
            raise JournalUnavailable("lab_mode_required")
        if type(ledger_id) is not str or not _VALID_ID.fullmatch(ledger_id):
            raise JournalUnavailable("invalid_ledger_id")
        self.lab_dir = Path(lab_dir)
        if self.lab_dir.is_symlink() or not self.lab_dir.is_dir():
            raise JournalUnavailable("missing_or_linked_lab_dir")
        self.path = self.lab_dir / DB_NAME
        self.ledger_id = ledger_id
        # Reopening NEVER creates, repairs or bootstraps anything.
        self.read_events()

    @classmethod
    def bootstrap_synthetic_lab(cls, *, lab_dir, ledger_id):
        if os.environ.get("AION_LAB_MODE") != "1":
            raise JournalUnavailable("lab_mode_required")
        root = Path(lab_dir)
        if root.is_symlink() or not root.is_dir():
            raise JournalUnavailable("missing_or_linked_lab_dir")
        if type(ledger_id) is not str or not _VALID_ID.fullmatch(ledger_id):
            raise JournalUnavailable("invalid_ledger_id")
        path = root / DB_NAME
        if path.exists() or path.is_symlink():
            raise JournalUnavailable("existing_journal_bootstrap_forbidden")
        try:
            # Exclusive file creation: this test-only genesis cannot overwrite an
            # existing ledger. Custody outside this directory remains unproven.
            with path.open("xb"):
                pass
            with closing(sqlite3.connect(path, isolation_level=None, timeout=2)) as db:
                db.execute("PRAGMA synchronous=FULL")
                db.execute("BEGIN IMMEDIATE")
                db.execute(META_DDL)
                db.execute(EVENTS_DDL)
                db.execute("INSERT INTO ledger_meta(singleton,ledger_id) VALUES (1,?)",
                           (ledger_id,))
                db.execute("COMMIT")
        except (OSError, sqlite3.Error) as exc:
            raise JournalUnavailable("synthetic_bootstrap_failed") from exc
        return cls(lab_dir=root, ledger_id=ledger_id)

    def _connect(self, *, writable=False):
        if self.path.is_symlink() or not self.path.is_file():
            raise JournalUnavailable("missing_or_linked_journal")
        uri = self.path.resolve().as_uri() + ("?mode=rw" if writable else "?mode=ro")
        try:
            db = sqlite3.connect(uri, uri=True, timeout=2, isolation_level=None)
            db.execute("PRAGMA busy_timeout=2000")
            if writable:
                db.execute("PRAGMA synchronous=FULL")
            return db
        except sqlite3.Error as exc:
            raise JournalUnavailable("journal_open_failed") from exc

    def _verified_events(self, db):
        expected = {
            "ledger_meta": ("table", "ledger_meta", META_DDL),
            "events": ("table", "events", EVENTS_DDL),
            "sqlite_autoindex_events_1": ("index", "events", None),
        }
        rows = db.execute("SELECT type,name,tbl_name,sql FROM sqlite_master").fetchall()
        if len(rows) != 3 or {row[1] for row in rows} != set(expected):
            raise JournalUnavailable("unexpected_schema_objects")
        for kind, name, table, ddl in rows:
            if (kind, table, ddl) != expected[name]:
                raise JournalUnavailable("journal_schema_changed")
        if db.execute("PRAGMA application_id").fetchone() != (0,):
            raise JournalUnavailable("foreign_application_id")
        if db.execute("PRAGMA quick_check").fetchone() != ("ok",):
            raise JournalUnavailable("sqlite_integrity_failure")
        meta = db.execute("SELECT singleton,ledger_id FROM ledger_meta").fetchall()
        if meta != [(1, self.ledger_id)]:
            raise JournalUnavailable("ledger_identity_or_policy_changed")
        data = db.execute("SELECT seq,intent,state FROM events ORDER BY seq").fetchall()
        if any(type(seq) is not int or seq != i
               or type(intent) is not str or not _VALID_ID.fullmatch(intent)
               or state != "RESERVED_UNCERTAIN"
               for i, (seq, intent, state) in enumerate(data, 1)):
            raise JournalUnavailable("journal_history_invariant_broken")
        return [{"seq": seq, "intent": intent} for seq, intent, _ in data]

    def read_events(self):
        try:
            with closing(self._connect()) as db:
                db.execute("BEGIN")
                rows = self._verified_events(db)
                db.execute("COMMIT")
                return rows
        except sqlite3.Error as exc:
            raise JournalUnavailable("journal_read_failed") from exc

    def reserve_local_uncertain(self, intent, *, fault_before_commit=False):
        """Reserve ONCE, commit locally. Does not call any external provider.

        Even if a commit's result is ambiguous, caller MUST NOT auto-resend.
        The optional fault injects a rollback for controlled tests only.
        """
        if type(intent) is not str or not _VALID_ID.fullmatch(intent):
            raise JournalUnavailable("invalid_intent")
        try:
            with closing(self._connect(writable=True)) as db:
                db.execute("BEGIN IMMEDIATE")
                events = self._verified_events(db)
                if any(e["intent"] == intent for e in events):
                    db.execute("ROLLBACK")
                    return False
                db.execute(
                    "INSERT INTO events(seq,intent,state) VALUES (?,?,?)",
                    (len(events) + 1, intent, "RESERVED_UNCERTAIN"),
                )
                if fault_before_commit:
                    db.execute("ROLLBACK")
                    raise SimulatedBeforeCommitCrash("synthetic_fault_before_commit")
                db.execute("COMMIT")
                return True
        except sqlite3.Error as exc:
            raise JournalUnavailable("reservation_result_uncertain_no_retry") from exc

    def assess_restart(self, *, checkpoint_envelope, checkpoint_pinned_keys,
                       highwater_pinned_keys, read_signed_highwater):
        """Return quarantine or hard block, NEVER a GO/RETRY decision.

        A matching pair of externally signed statements cannot prove freshness
        without an independently trusted, non-rollbackable witness domain.
        """
        try:
            events = self.read_events()
            check_restart_with_signed_highwater(
                ledger_id=self.ledger_id,
                events=events,
                envelope=checkpoint_envelope,
                checkpoint_pinned_keys=checkpoint_pinned_keys,
                highwater_pinned_keys=highwater_pinned_keys,
                read_signed_highwater=read_signed_highwater,
            )
            return RecoveryDecision(
                verdict="LAB_QUARANTINE_MANUAL_REVIEW",
                reason="reserved_effect_unknown" if events else "read_only_genesis_not_authorized",
                sequence=len(events),
            )
        except (JournalUnavailable, CheckpointRejected, HighWaterRejected) as exc:
            return RecoveryDecision(
                verdict="LAB_HARD_BLOCKED",
                reason=str(exc),
                sequence=-1,
            )
