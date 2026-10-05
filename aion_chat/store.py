"""Local SQLite staging with scoped identity and explicit resilience controls."""
import base64
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import sqlite3
from typing import Protocol
from uuid import uuid4

from .models import Attachment, ContextSummary, Conversation, ConversationCheckpoint, Message, Page, Scope, now
from .privacy import redact


BUSY_TIMEOUT_MS = 5_000
WAL_AUTOCHECKPOINT_PAGES = 1_000
HEALTHY = "healthy"
DEGRADED = "degraded"
RECOVERING = "recovering"
FAILED = "failed"


class StorageUnavailableError(RuntimeError):
    """Raised when a staging store cannot prove a safe local storage state."""


class AionChatStore(Protocol):
    def create_conversation(self, scope: Scope, title="Nova conversa", metadata=None) -> Conversation: ...
    def get_conversation(self, scope: Scope, conversation_id: str) -> Conversation: ...
    def list_conversations(self, scope: Scope, cursor=None, page_size=30, **filters) -> Page: ...
    def search_conversations(self, scope: Scope, query: str, **filters) -> Page: ...
    def archive_conversation(self, scope: Scope, conversation_id: str) -> Conversation: ...
    def append_message(self, scope: Scope, message: Message) -> Message: ...
    def list_messages(self, scope: Scope, conversation_id: str, cursor=None, page_size=50, **options) -> Page: ...
    def get_message(self, scope: Scope, conversation_id: str, message_id: str) -> Message: ...
    def add_attachment_metadata(self, scope: Scope, attachment: Attachment) -> Attachment: ...
    def get_attachment(self, scope: Scope, conversation_id: str, attachment_id: str) -> Attachment: ...
    def save_checkpoint(self, scope: Scope, checkpoint: ConversationCheckpoint): ...
    def get_latest_checkpoint(self, scope: Scope, conversation_id: str): ...
    def save_context_summary(self, scope: Scope, summary: ContextSummary): ...
    def get_latest_summary(self, scope: Scope, conversation_id: str): ...
    def retrieve_messages(self, scope: Scope, conversation_id: str, query: str, **options): ...


def dump(value):
    return json.dumps(redact(asdict(value)), ensure_ascii=False, separators=(",", ":"))


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _validate_database_file(path: Path) -> dict:
    if not path.is_file():
        raise StorageUnavailableError("database file unavailable")
    db = None
    try:
        db = sqlite3.connect(str(path), timeout=5)
        quick = str(db.execute("PRAGMA quick_check").fetchone()[0] or "")
        foreign = db.execute("PRAGMA foreign_key_check").fetchall()
        if quick.lower() != "ok" or foreign:
            raise StorageUnavailableError("database integrity validation failed")
        return {
            "quick_check": quick,
            "foreign_key_violations": len(foreign),
            "size_bytes": path.stat().st_size,
            "sha256": _file_sha256(path),
        }
    except (sqlite3.DatabaseError, OSError) as exc:
        raise StorageUnavailableError("database integrity validation failed") from exc
    finally:
        if db is not None:
            db.close()


class SQLiteChatStore:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._health_state = HEALTHY
        self._health_reason = "OK"
        self.db = None
        try:
            self.db = sqlite3.connect(str(self.path), timeout=BUSY_TIMEOUT_MS / 1000)
            self.db.row_factory = sqlite3.Row
            self.db.executescript(f"""
            PRAGMA foreign_keys=ON;
            PRAGMA journal_mode=WAL;
            PRAGMA busy_timeout={BUSY_TIMEOUT_MS};
            PRAGMA wal_autocheckpoint={WAL_AUTOCHECKPOINT_PAGES};
            CREATE TABLE IF NOT EXISTS conversations(id TEXT PRIMARY KEY, owner TEXT NOT NULL,
                tenant TEXT NOT NULL, workspace TEXT NOT NULL, updated TEXT NOT NULL,
                archived INTEGER NOT NULL, title TEXT NOT NULL, data TEXT NOT NULL);
            CREATE INDEX IF NOT EXISTS scope_recency ON conversations(owner,tenant,workspace,archived,updated,id);
            CREATE TABLE IF NOT EXISTS messages(id TEXT PRIMARY KEY,cid TEXT NOT NULL REFERENCES conversations(id),
                seq INTEGER NOT NULL,content TEXT NOT NULL,data TEXT NOT NULL,UNIQUE(cid,seq));
            CREATE INDEX IF NOT EXISTS message_history ON messages(cid,seq);
            CREATE TABLE IF NOT EXISTS records(id TEXT PRIMARY KEY,cid TEXT NOT NULL REFERENCES conversations(id),
                kind TEXT NOT NULL,seq INTEGER NOT NULL,data TEXT NOT NULL);
            CREATE INDEX IF NOT EXISTS record_history ON records(cid,kind,seq,id);
            """)
            report = self.storage_health(deep=True)
            if report["state"] != HEALTHY:
                raise StorageUnavailableError(
                    "staging store failed startup integrity gate: " + report["reason"]
                )
        except (sqlite3.DatabaseError, OSError, StorageUnavailableError) as exc:
            self._health_state = FAILED
            self._health_reason = type(exc).__name__
            if self.db is not None:
                try:
                    self.db.close()
                except Exception:
                    pass
            self.db = None
            if isinstance(exc, StorageUnavailableError):
                raise
            raise StorageUnavailableError("staging store unavailable") from exc

    def close(self):
        if self.db is not None:
            self.db.close()
            self.db = None

    def _require_open(self):
        if self.db is None:
            raise StorageUnavailableError("staging store is closed")
        if self._health_state == FAILED:
            raise StorageUnavailableError("staging store health is failed")

    def storage_health(self, *, deep=False):
        if self.db is None:
            return {
                "state": FAILED,
                "reason": "STORE_CLOSED",
                "path": str(self.path),
                "journal_mode": "",
                "busy_timeout_ms": 0,
                "quick_check": "",
                "foreign_key_violations": None,
            }
        try:
            journal = str(self.db.execute("PRAGMA journal_mode").fetchone()[0] or "").lower()
            busy = int(self.db.execute("PRAGMA busy_timeout").fetchone()[0] or 0)
            quick = "not_run"
            foreign_count = 0
            if deep:
                quick = str(self.db.execute("PRAGMA quick_check").fetchone()[0] or "")
                foreign_count = len(self.db.execute("PRAGMA foreign_key_check").fetchall())
            state = HEALTHY
            reasons = []
            if journal != "wal":
                state = DEGRADED
                reasons.append("JOURNAL_MODE_NOT_WAL")
            if busy < BUSY_TIMEOUT_MS:
                state = DEGRADED
                reasons.append("BUSY_TIMEOUT_TOO_LOW")
            if deep and quick.lower() != "ok":
                state = FAILED
                reasons.append("QUICK_CHECK_FAILED")
            if deep and foreign_count:
                state = FAILED
                reasons.append("FOREIGN_KEY_VIOLATION")
            self._health_state = state
            self._health_reason = ",".join(reasons) if reasons else "OK"
            return {
                "state": state,
                "reason": self._health_reason,
                "path": str(self.path),
                "journal_mode": journal,
                "busy_timeout_ms": busy,
                "wal_autocheckpoint_pages": int(
                    self.db.execute("PRAGMA wal_autocheckpoint").fetchone()[0] or 0
                ),
                "quick_check": quick,
                "foreign_key_violations": foreign_count,
            }
        except sqlite3.DatabaseError as exc:
            self._health_state = FAILED
            self._health_reason = type(exc).__name__
            return {
                "state": FAILED,
                "reason": "DATABASE_ERROR:" + type(exc).__name__,
                "path": str(self.path),
                "journal_mode": "",
                "busy_timeout_ms": 0,
                "quick_check": "error",
                "foreign_key_violations": None,
            }

    def require_healthy(self):
        report = self.storage_health(deep=True)
        if report["state"] != HEALTHY:
            raise StorageUnavailableError(
                "staging store is not healthy: " + str(report["reason"])
            )
        return report

    def wal_checkpoint(self, mode="PASSIVE"):
        self._require_open()
        normalized = str(mode or "").upper()
        if normalized not in {"PASSIVE", "FULL", "RESTART", "TRUNCATE"}:
            raise ValueError("invalid WAL checkpoint mode")
        try:
            row = self.db.execute(f"PRAGMA wal_checkpoint({normalized})").fetchone()
            report = {
                "mode": normalized,
                "busy": int(row[0]),
                "log_frames": int(row[1]),
                "checkpointed_frames": int(row[2]),
            }
            if report["busy"]:
                self._health_state = DEGRADED
                self._health_reason = "WAL_CHECKPOINT_BUSY"
            return report
        except sqlite3.DatabaseError as exc:
            self._health_state = FAILED
            self._health_reason = type(exc).__name__
            raise StorageUnavailableError("WAL checkpoint failed") from exc

    def backup_to(self, destination):
        """Create an online SQLite backup after a FULL WAL checkpoint and verify it."""
        self.require_healthy()
        destination = Path(destination)
        if destination.resolve() == self.path.resolve():
            raise ValueError("backup destination must differ from live database")
        destination.parent.mkdir(parents=True, exist_ok=True)
        checkpoint = self.wal_checkpoint("FULL")
        if checkpoint["busy"]:
            raise StorageUnavailableError("backup refused while WAL checkpoint is busy")

        temp = destination.with_name(destination.name + ".tmp-" + uuid4().hex)
        target = None
        try:
            target = sqlite3.connect(str(temp), timeout=BUSY_TIMEOUT_MS / 1000)
            self.db.backup(target)
            target.commit()
            target.close()
            target = None
            verified = _validate_database_file(temp)
            os.replace(temp, destination)
            return {
                "state": "BACKUP_VERIFIED",
                "source_path": str(self.path),
                "backup_path": str(destination),
                "checkpoint": checkpoint,
                **verified,
            }
        except (sqlite3.DatabaseError, OSError, StorageUnavailableError) as exc:
            if target is not None:
                try:
                    target.close()
                except Exception:
                    pass
            try:
                temp.unlink(missing_ok=True)
            except Exception:
                pass
            if isinstance(exc, StorageUnavailableError):
                raise
            raise StorageUnavailableError("verified SQLite backup failed") from exc

    @classmethod
    def restore_from_backup(cls, backup_path, target_path):
        """Restore a verified backup atomically; never replace target on invalid input."""
        source = Path(backup_path)
        target = Path(target_path)
        if source.resolve() == target.resolve():
            raise ValueError("restore target must differ from backup")
        source_report = _validate_database_file(source)
        target.parent.mkdir(parents=True, exist_ok=True)
        temp = target.with_name(target.name + ".restore-" + uuid4().hex)
        source_db = None
        target_db = None
        try:
            source_db = sqlite3.connect(str(source), timeout=BUSY_TIMEOUT_MS / 1000)
            target_db = sqlite3.connect(str(temp), timeout=BUSY_TIMEOUT_MS / 1000)
            source_db.backup(target_db)
            target_db.commit()
            target_db.close()
            target_db = None
            source_db.close()
            source_db = None
            restored_report = _validate_database_file(temp)
            os.replace(temp, target)
            return {
                "state": "RESTORE_VERIFIED",
                "backup_path": str(source),
                "target_path": str(target),
                "source_sha256": source_report["sha256"],
                "restored_sha256": restored_report["sha256"],
                "size_bytes": restored_report["size_bytes"],
            }
        except (sqlite3.DatabaseError, OSError, StorageUnavailableError) as exc:
            for db in (target_db, source_db):
                if db is not None:
                    try:
                        db.close()
                    except Exception:
                        pass
            try:
                temp.unlink(missing_ok=True)
            except Exception:
                pass
            if isinstance(exc, StorageUnavailableError):
                raise
            raise StorageUnavailableError("verified SQLite restore failed") from exc

    def _record_database_error(self, exc):
        text = str(exc or "").lower()
        if isinstance(exc, sqlite3.OperationalError) and (
            "locked" in text or "busy" in text
        ):
            self._health_state = DEGRADED
            self._health_reason = "DATABASE_BUSY"
        else:
            self._health_state = FAILED
            self._health_reason = type(exc).__name__

    def _scope(self, scope):
        self._require_open()
        if not isinstance(scope, Scope):
            raise TypeError("trusted Scope required")
        return scope.owner_id, scope.tenant_id, scope.workspace_id

    def get_conversation(self, scope, conversation_id):
        row = self.db.execute(
            "SELECT data FROM conversations WHERE id=? AND owner=? AND tenant=? AND workspace=?",
            (conversation_id, *self._scope(scope)),
        ).fetchone()
        if row is None:
            raise LookupError("conversation unavailable")
        return Conversation(**json.loads(row[0]))

    def _update(self, c):
        self.db.execute(
            "UPDATE conversations SET updated=?,archived=?,title=?,data=? WHERE id=?",
            (c.updated_at, c.archived, c.title, dump(c), c.id),
        )

    def create_conversation(self, scope, title="Nova conversa", metadata=None):
        self._scope(scope)
        c = Conversation(**asdict(scope), title=redact(title), metadata=redact(metadata or {}))
        try:
            with self.db:
                self.db.execute(
                    "INSERT INTO conversations VALUES (?,?,?,?,?,?,?,?)",
                    (c.id, *self._scope(scope), c.updated_at, c.archived, c.title, dump(c)),
                )
        except sqlite3.DatabaseError as exc:
            self._record_database_error(exc)
            raise
        return c

    def _cursor_key(self, scope, spec):
        return hashlib.sha256(json.dumps([self._scope(scope), spec], sort_keys=True).encode()).hexdigest()

    def _encode(self, scope, spec, boundary):
        return base64.urlsafe_b64encode(json.dumps([self._cursor_key(scope, spec), boundary]).encode()).decode()

    def _decode(self, scope, spec, cursor):
        try:
            key, boundary = json.loads(base64.urlsafe_b64decode(cursor))
            if key != self._cursor_key(scope, spec):
                raise ValueError()
            return boundary
        except Exception as exc:
            raise ValueError("invalid cursor for scope/query") from exc

    @staticmethod
    def _size(size):
        if not isinstance(size, int) or not 1 <= size <= 200:
            raise ValueError("page_size must be 1..200; this is not a history limit")
        return size

    def list_conversations(self, scope, cursor=None, page_size=30, *, query="", tag=None, since=None, until=None, archived=False):
        size = self._size(page_size)
        spec = ["conversations", query, tag, since, until, archived]
        sql = "SELECT c.* FROM conversations c WHERE owner=? AND tenant=? AND workspace=? AND archived=?"
        args = [*self._scope(scope), archived]
        if query:
            sql += " AND (instr(lower(title),lower(?))>0 OR EXISTS(SELECT 1 FROM messages m WHERE m.cid=c.id AND instr(lower(m.content),lower(?))>0) OR EXISTS(SELECT 1 FROM json_each(c.data,'$.metadata.tags') WHERE instr(lower(value),lower(?))>0))"
            args += [query, query, query]
        if tag:
            sql += " AND EXISTS(SELECT 1 FROM json_each(c.data,'$.metadata.tags') WHERE value=?)"
            args.append(tag)
        for value, op in ((since, ">="), (until, "<=")):
            if value:
                sql += f" AND updated{op}?"
                args.append(value)
        if cursor:
            updated, cid = self._decode(scope, spec, cursor)
            sql += " AND (updated,id)<(?,?)"
            args += [updated, cid]
        rows = self.db.execute(sql + " ORDER BY updated DESC,id DESC LIMIT ?", [*args, size + 1]).fetchall()
        items = [Conversation(**json.loads(r["data"])) for r in rows[:size]]
        nxt = self._encode(scope, spec, [rows[size - 1]["updated"], rows[size - 1]["id"]]) if len(rows) > size else None
        return Page(items, nxt)

    def search_conversations(self, scope, query, **filters):
        return self.list_conversations(scope, query=query, **filters)

    def archive_conversation(self, scope, conversation_id):
        with self.db:
            c = self.get_conversation(scope, conversation_id)
            c.archived, c.updated_at = True, now()
            self._update(c)
        return c

    def append_message(self, scope, message):
        if message.role not in {"user", "assistant", "system", "task"}:
            raise ValueError("invalid role")
        self._require_open()
        try:
            self.db.execute("BEGIN IMMEDIATE")
            c = self.get_conversation(scope, message.conversation_id)
            for aid in message.attachments:
                self.get_attachment(scope, c.id, aid)
            message = Message(**redact(asdict(message)))
            message.sequence = c.message_count + 1
            self.db.execute(
                "INSERT INTO messages VALUES (?,?,?,?,?)",
                (message.id, c.id, message.sequence, message.content, dump(message)),
            )
            c.message_count, c.updated_at = message.sequence, now()
            self._update(c)
            self.db.commit()
        except Exception as exc:
            try:
                self.db.rollback()
            except Exception:
                pass
            if isinstance(exc, sqlite3.DatabaseError) and not isinstance(exc, sqlite3.IntegrityError):
                self._record_database_error(exc)
            raise
        return message

    def list_messages(self, scope, conversation_id, cursor=None, page_size=50, *, newest_first=False):
        self.get_conversation(scope, conversation_id)
        size = self._size(page_size)
        spec = ["messages", conversation_id, newest_first]
        sql, args = "SELECT * FROM messages WHERE cid=?", [conversation_id]
        if cursor:
            sql += " AND seq" + ("<?" if newest_first else ">?")
            args.append(self._decode(scope, spec, cursor))
        order = "DESC" if newest_first else "ASC"
        rows = self.db.execute(sql + f" ORDER BY seq {order} LIMIT ?", [*args, size + 1]).fetchall()
        items = [Message(**json.loads(r["data"])) for r in rows[:size]]
        return Page(items, self._encode(scope, spec, items[-1].sequence) if len(rows) > size else None)

    def get_message(self, scope, conversation_id, message_id):
        self.get_conversation(scope, conversation_id)
        row = self.db.execute(
            "SELECT data FROM messages WHERE cid=? AND id=?",
            (conversation_id, message_id),
        ).fetchone()
        if not row:
            raise LookupError("message unavailable")
        return Message(**json.loads(row[0]))

    def _save_record(self, scope, kind, value, seq=0):
        c = self.get_conversation(scope, value.conversation_id)
        if not isinstance(seq, int) or not 0 <= seq <= c.message_count:
            raise ValueError("invalid coverage sequence")
        self.db.execute(
            "INSERT INTO records VALUES (?,?,?,?,?)",
            (value.id, c.id, kind, seq, dump(value)),
        )

    def add_attachment_metadata(self, scope, attachment):
        from .attachments import validate_metadata
        validate_metadata(attachment)
        with self.db:
            self._save_record(scope, "attachment", attachment)
        return attachment

    def get_attachment(self, scope, conversation_id, attachment_id):
        self.get_conversation(scope, conversation_id)
        row = self.db.execute(
            "SELECT data FROM records WHERE cid=? AND id=? AND kind='attachment'",
            (conversation_id, attachment_id),
        ).fetchone()
        if not row:
            raise LookupError("attachment unavailable")
        return Attachment(**json.loads(row[0]))

    def _latest(self, scope, cid, kind, model):
        self.get_conversation(scope, cid)
        row = self.db.execute(
            "SELECT data FROM records WHERE cid=? AND kind=? ORDER BY seq DESC,id DESC LIMIT 1",
            (cid, kind),
        ).fetchone()
        return model(**json.loads(row[0])) if row else None

    def get_latest_checkpoint(self, scope, conversation_id):
        return self._latest(scope, conversation_id, "checkpoint", ConversationCheckpoint)

    def save_checkpoint(self, scope, checkpoint):
        with self.db:
            prior = self.get_latest_checkpoint(scope, checkpoint.conversation_id)
            if prior and checkpoint.through_sequence <= prior.through_sequence:
                raise ValueError("coverage must advance")
            self._save_record(scope, "checkpoint", checkpoint, checkpoint.through_sequence)
            c = self.get_conversation(scope, checkpoint.conversation_id)
            c.latest_checkpoint = checkpoint.id
            self._update(c)

    def save_context_summary(self, scope, summary):
        with self.db:
            for mid in summary.source_message_ids:
                if self.get_message(scope, summary.conversation_id, mid).sequence > summary.through_sequence:
                    raise ValueError("source beyond coverage")
            self._save_record(scope, "summary", summary, summary.through_sequence)

    def get_latest_summary(self, scope, conversation_id):
        return self._latest(scope, conversation_id, "summary", ContextSummary)

    def retrieve_messages(self, scope, conversation_id, query, *, before_sequence, limit=10):
        self.get_conversation(scope, conversation_id)
        self._size(limit)
        rows = self.db.execute(
            "SELECT data FROM messages WHERE cid=? AND seq<? AND instr(lower(content),lower(?))>0 ORDER BY seq DESC LIMIT ?",
            (conversation_id, before_sequence, query, limit),
        ).fetchall() if query.strip() else []
        return [Message(**json.loads(r[0])) for r in rows]
