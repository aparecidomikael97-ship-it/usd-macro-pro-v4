"""Explicit local SQLite checkpoint, append-only history and scoped audit journal.

No runtime GitHub writer or legacy checkpoint is invoked. The caller chooses
the local path and owns authentication, filesystem permissions and backups.
"""
from datetime import datetime
import json
from pathlib import Path
import sqlite3
from uuid import uuid4

from atlasquant_aion_observability import new_event
from .context import Context
from .evidence import Origin, digest, safe_text, timestamp, utc


KINDS = frozenset({"DECISION", "REQUIREMENT", "PRIORITY", "CURRENT_STATE",
                   "COMPLETED_TASK", "PENDING_TASK", "EVIDENCE"})
EVENTS = frozenset({"intent_received", "module_selected", "capability_unavailable",
                    "approval_required", "approval_recorded", "memory_read",
                    "memory_write", "error", "completed"})


class ConflictError(ValueError):
    pass


def memory_subject(kind: str, text: str, evidence_refs: tuple[str, ...] = ()) -> dict:
    if kind not in KINDS or not isinstance(evidence_refs, tuple) or len(evidence_refs) > 40:
        raise ValueError("invalid memory record")
    return {"kind": kind, "text": safe_text(text),
            "evidence_refs": [safe_text(x, 500) for x in evidence_refs]}


class CoreStore:
    def __init__(self, path: str | Path):
        # Never silently fall back to ephemeral memory if persistence fails.
        self._db = sqlite3.connect(str(path), timeout=5, isolation_level=None)
        self._db.execute("PRAGMA foreign_keys=ON")
        version = self._db.execute("PRAGMA user_version").fetchone()[0]
        if version not in {0, 1}:
            self._db.close()
            raise ValueError("unsupported checkpoint schema")
        self._db.executescript("""
            CREATE TABLE IF NOT EXISTS core_scopes(scope TEXT PRIMARY KEY, revision INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS core_memory(
                seq INTEGER PRIMARY KEY AUTOINCREMENT, scope TEXT NOT NULL,
                record_id TEXT NOT NULL, version INTEGER NOT NULL, document TEXT NOT NULL,
                UNIQUE(scope, record_id, version));
            CREATE TABLE IF NOT EXISTS core_approvals(
                scope TEXT NOT NULL, approval_id TEXT NOT NULL, version INTEGER NOT NULL,
                document TEXT NOT NULL, PRIMARY KEY(scope, approval_id));
            CREATE TABLE IF NOT EXISTS core_events(
                seq INTEGER PRIMARY KEY AUTOINCREMENT, scope TEXT NOT NULL, document TEXT NOT NULL);
            CREATE INDEX IF NOT EXISTS core_memory_scope ON core_memory(scope, seq);
            CREATE INDEX IF NOT EXISTS core_events_scope ON core_events(scope, seq);
            PRAGMA user_version=1;
        """)
        self.persistent = str(path) != ":memory:"
        self.closed = False

    def close(self):
        self._db.close()
        self.closed = True

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def revision(self, context: Context) -> int:
        row = self._db.execute("SELECT revision FROM core_scopes WHERE scope=?", (context.key,)).fetchone()
        return row[0] if row else 0

    def _event(self, context: Context, event_type: str, now: datetime, result: str = ""):
        if event_type not in EVENTS:
            raise ValueError("unknown core event")
        # No intent, code, evidence payload, exception message or receipt is logged.
        if result not in {"", "OK", "BLOCKED", "UNKNOWN", "UNAVAILABLE", "ERROR"}:
            raise ValueError("invalid event result")
        event = new_event(event_type, event_type, source="AION_CORE_INTELLIGENCE",
                          truth_state="CONFIRMED", created_at=utc(now).isoformat(),
                          task_id=context.task_id, domain=context.domain.value,
                          result=result, evidence={"scope_digest": digest(context.key)})
        self._db.execute("INSERT INTO core_events(scope,document) VALUES(?,?)",
                         (context.key, json.dumps(event)))

    def event(self, context: Context, event_type: str, now: datetime, result: str = ""):
        self._event(context, event_type, now, result)

    def events(self, context: Context, limit: int = 100) -> list[dict]:
        if type(limit) is not int or not 1 <= limit <= 500:
            raise ValueError("invalid event limit")
        rows = self._db.execute("SELECT document FROM core_events WHERE scope=? ORDER BY seq DESC LIMIT ?",
                                (context.key, limit)).fetchall()
        return [json.loads(x[0]) for x in reversed(rows)]

    def history(self, context: Context) -> list[dict]:
        rows = self._db.execute("SELECT document FROM core_memory WHERE scope=? ORDER BY seq",
                                (context.key,)).fetchall()
        return [json.loads(x[0]) for x in rows]

    def read(self, context: Context, now: datetime, *, kind: str | None = None) -> list[dict]:
        if kind is not None and kind not in KINDS:
            raise ValueError("invalid memory kind")
        latest = {}
        for row in self.history(context):
            latest[row["record_id"]] = row
        self._event(context, "memory_read", now, "OK")
        return [row for row in latest.values() if kind is None or row["kind"] == kind]

    def append(self, context: Context, *, kind: str, text: str, origin: Origin,
               source: str, now: datetime, expected_revision: int,
               evidence_refs: tuple[str, ...] = (), record_id: str | None = None,
               approval_id: str | None = None) -> dict:
        subject = memory_subject(kind, text, evidence_refs)
        if not isinstance(origin, Origin) or type(expected_revision) is not int or expected_revision < 0:
            raise ValueError("explicit origin and checkpoint revision required")
        source = safe_text(source, 500)
        if origin != Origin.UNKNOWN and (source.upper() in {"UNKNOWN", "UNAVAILABLE"} or not evidence_refs):
            raise ValueError("classified memory requires source and evidence references")
        created = utc(now).isoformat()
        self._db.execute("BEGIN IMMEDIATE")
        try:
            if self.revision(context) != expected_revision:
                raise ConflictError("checkpoint revision changed")
            if origin == Origin.USER_APPROVED:
                approval = self.approval(context, approval_id or "")
                if (not approval or approval["state"] != "APPROVED"
                        or approval["action"] != "MEMORY_DECISION"
                        or approval["subject_digest"] != digest(subject)
                        or timestamp(approval["expires_at"]) <= utc(now)
                        or approval.get("consumed") is not False):
                    raise ValueError("matching unexpired human approval required")
                approval["consumed"] = True
                self._db.execute("UPDATE core_approvals SET document=? WHERE scope=? AND approval_id=?",
                                 (json.dumps(approval), context.key, approval_id))
            elif approval_id is not None:
                raise ValueError("approval cannot relabel an observation or inference")
            prior = [x for x in self.history(context) if x["record_id"] == record_id] if record_id else []
            if record_id is not None and not prior:
                raise ValueError("record is absent from this context")
            version = prior[-1]["version"] + 1 if prior else 1
            row = {"schema_version": 1, "record_id": record_id or uuid4().hex,
                   "version": version, "checkpoint_revision": expected_revision + 1,
                   **subject, "origin": origin.value, "source": source,
                   "created_at": created, "approval_id": approval_id,
                   "is_approved_decision": origin == Origin.USER_APPROVED,
                   "supersedes_version": version - 1 if prior else None}
            self._db.execute("INSERT INTO core_memory(scope,record_id,version,document) VALUES(?,?,?,?)",
                             (context.key, row["record_id"], version, json.dumps(row)))
            self._db.execute("INSERT INTO core_scopes(scope,revision) VALUES(?,?) "
                             "ON CONFLICT(scope) DO UPDATE SET revision=excluded.revision",
                             (context.key, expected_revision + 1))
            self._event(context, "memory_write", now, "OK")
            self._db.execute("COMMIT")
            return row
        except Exception:
            self._db.execute("ROLLBACK")
            raise

    def checkpoint(self, context: Context, now: datetime) -> dict:
        # A read transaction keeps revision and rows in the same snapshot.
        self._db.execute("BEGIN")
        try:
            out = {"schema": "AION_CORE_CHECKPOINT_V1", "scope": json.loads(context.key),
                   "version": self.revision(context), "exported_at": utc(now).isoformat(),
                   "records": self.history(context), "storage": "LOCAL_SQLITE" if self.persistent else "EPHEMERAL"}
            out["digest"] = digest(out)
            self._db.execute("COMMIT")
            return out
        except Exception:
            self._db.execute("ROLLBACK")
            raise

    def approval(self, context: Context, approval_id: str) -> dict | None:
        row = self._db.execute("SELECT document FROM core_approvals WHERE scope=? AND approval_id=?",
                               (context.key, approval_id)).fetchone()
        return json.loads(row[0]) if row else None

    def _save_approval(self, context: Context, row: dict, *, previous_version: int | None,
                       now: datetime):
        self._db.execute("BEGIN IMMEDIATE")
        try:
            if previous_version is None:
                self._db.execute("INSERT INTO core_approvals VALUES(?,?,?,?)",
                                 (context.key, row["approval_id"], row["version"], json.dumps(row)))
            else:
                count = self._db.execute("UPDATE core_approvals SET version=?,document=? "
                                         "WHERE scope=? AND approval_id=? AND version=?",
                                         (row["version"], json.dumps(row), context.key,
                                          row["approval_id"], previous_version)).rowcount
                if count != 1:
                    raise ConflictError("approval version changed")
            self._event(context, "approval_required" if previous_version is None else "approval_recorded", now)
            self._db.execute("COMMIT")
        except Exception:
            self._db.execute("ROLLBACK")
            raise
