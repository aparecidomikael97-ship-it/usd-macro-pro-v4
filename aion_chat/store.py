"""Local SQLite staging with scoped identity and explicit resilience controls."""
import base64
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import stat
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
# A LAB resource budget, not a backup size guarantee for an activated service.
MAX_RECOVERY_BYTES = 16 * 1024 * 1024

# A deliberately narrow recovery format matching this store's emitted DDL.
# This is not a general SQLite schema equivalence/compatibility validator.
_CHAT_RECOVERY_DDL = {
    "conversations": """CREATE TABLE conversations(id TEXT PRIMARY KEY, owner TEXT NOT NULL,
        tenant TEXT NOT NULL, workspace TEXT NOT NULL, updated TEXT NOT NULL,
        archived INTEGER NOT NULL, title TEXT NOT NULL, data TEXT NOT NULL)""",
    "messages": """CREATE TABLE messages(id TEXT PRIMARY KEY,cid TEXT NOT NULL REFERENCES conversations(id),
        seq INTEGER NOT NULL,content TEXT NOT NULL,data TEXT NOT NULL,UNIQUE(cid,seq))""",
    "records": """CREATE TABLE records(id TEXT PRIMARY KEY,cid TEXT NOT NULL REFERENCES conversations(id),
        kind TEXT NOT NULL,seq INTEGER NOT NULL,data TEXT NOT NULL)""",
}
_CHAT_RECOVERY_INDEX_DDL = {
    "scope_recency": "CREATE INDEX scope_recency ON conversations(owner,tenant,workspace,archived,updated,id)",
    "message_history": "CREATE INDEX message_history ON messages(cid,seq)",
    "record_history": "CREATE INDEX record_history ON records(cid,kind,seq,id)",
}


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


class _ValidatedDatabaseReport(dict):
    """Public metadata plus the exact locally validated bytes, never provenance."""

    def __init__(self, data, **metadata):
        super().__init__(metadata)
        self._data = data


def _recovery_path_chain(path, *, missing=False):
    """Reject observable aliases; this is not a native SQLite VFS attestation."""
    result = []
    for node in (path, *path.parents):
        try:
            info = node.lstat()
        except FileNotFoundError:
            if missing:
                result.append(None)
                continue
            raise
        if stat.S_ISLNK(info.st_mode) or getattr(node, "is_junction", lambda: False)():
            raise StorageUnavailableError("RECOVERY_ALIAS_DENIED")
        if not info.st_ino:
            raise StorageUnavailableError("RECOVERY_FILE_IDENTITY_UNAVAILABLE")
        result.append((info.st_dev, info.st_ino))
    return tuple(result)


def _deny_recovery_sidecars(path):
    for suffix in ("-wal", "-shm", "-journal"):
        try:
            Path(str(path) + suffix).lstat()
        except FileNotFoundError:
            continue
        raise StorageUnavailableError("RECOVERY_SIDECAR_AMBIGUITY")


def _recovery_file_state(info):
    return tuple(getattr(info, field) for field in (
        "st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns"))


def _recovery_ddl_tokens(sql):
    """Allow ASCII keyword case/spacing only; deny unsupported SQL syntax.

    No removal of comments, quoting, literals or token boundaries is attempted.
    Equivalent alternative DDL can therefore be rejected intentionally.
    """
    if not isinstance(sql, str):
        return None
    tokens, end = [], 0
    for match in re.finditer(r"[A-Za-z_][A-Za-z_0-9]*|[(),]", sql):
        if sql[end:match.start()].strip(" \t\r\n\f\v"):
            return None
        tokens.append(match.group().upper())
        end = match.end()
    if sql[end:].strip(" \t\r\n\f\v"):
        return None
    return tuple(tokens)


def _validate_database_bytes(data):
    if not 100 <= len(data) <= MAX_RECOVERY_BYTES:
        raise StorageUnavailableError("RECOVERY_SIZE_DENIED")
    if data[:16] != b"SQLite format 3\0" or data[18:20] != b"\x01\x01":
        raise StorageUnavailableError("RECOVERY_OFFLINE_ROLLBACK_FORMAT_REQUIRED")
    db = None
    try:
        db = sqlite3.connect(":memory:")
        if not hasattr(db, "deserialize"):
            raise StorageUnavailableError("RECOVERY_NATIVE_DESERIALIZE_REQUIRED")
        db.deserialize(data)
        db.execute("PRAGMA trusted_schema=OFF")
        db.execute("PRAGMA query_only=ON")
        budget = 10_000

        def progress():
            nonlocal budget
            budget -= 1
            return int(budget <= 0)

        db.set_progress_handler(progress, 1_000)
        if db.execute("PRAGMA database_list").fetchall() != [(0, "main", "")]:
            raise StorageUnavailableError("RECOVERY_NATIVE_MEMORY_REQUIRED")
        quick = db.execute("PRAGMA quick_check").fetchmany(2)
        foreign = db.execute("PRAGMA foreign_key_check").fetchmany(1)
        if quick != [("ok",)] or foreign:
            raise StorageUnavailableError("database integrity validation failed")
        # Reject arbitrary SQLite databases and executable schema constructs.
        # Additional ordinary tables (e.g. Outbox/Saga) are permitted, without
        # claiming general application-level compatibility of their contents.
        schema = db.execute("SELECT type, name, sql FROM sqlite_schema").fetchmany(1_001)
        if len(schema) > 1_000 or any(
            kind in {"trigger", "view"} or "CREATE VIRTUAL TABLE" in (sql or "").upper()
            for kind, _, sql in schema
        ):
            raise StorageUnavailableError("RECOVERY_SCHEMA_DENIED")
        tables = {name: sql for kind, name, sql in schema if kind == "table"}
        indexes = {name: sql for kind, name, sql in schema if kind == "index"}
        for table, expected_ddl in _CHAT_RECOVERY_DDL.items():
            if _recovery_ddl_tokens(tables.get(table)) != _recovery_ddl_tokens(expected_ddl):
                raise StorageUnavailableError("RECOVERY_CHAT_DDL_DENIED")
            # Explicit indexes can also add uniqueness or failing expressions
            # without changing table_info/FKs. Permit only the emitted forms.
            for row in db.execute(f"PRAGMA index_list({table})"):
                if row[3] == "c":
                    expected_index = _CHAT_RECOVERY_INDEX_DDL.get(row[1])
                    if (expected_index is None or _recovery_ddl_tokens(indexes.get(row[1]))
                            != _recovery_ddl_tokens(expected_index)):
                        raise StorageUnavailableError("RECOVERY_CHAT_INDEX_DDL_DENIED")
        required = {
            "conversations": {
                "id": ("TEXT", 0, 1), "owner": ("TEXT", 1, 0),
                "tenant": ("TEXT", 1, 0), "workspace": ("TEXT", 1, 0),
                "updated": ("TEXT", 1, 0), "archived": ("INTEGER", 1, 0),
                "title": ("TEXT", 1, 0), "data": ("TEXT", 1, 0)},
            "messages": {
                "id": ("TEXT", 0, 1), "cid": ("TEXT", 1, 0),
                "seq": ("INTEGER", 1, 0), "content": ("TEXT", 1, 0),
                "data": ("TEXT", 1, 0)},
            "records": {
                "id": ("TEXT", 0, 1), "cid": ("TEXT", 1, 0),
                "kind": ("TEXT", 1, 0), "seq": ("INTEGER", 1, 0),
                "data": ("TEXT", 1, 0)},
        }
        for table, expected in required.items():
            actual = {row[1]: (row[2].upper(), row[3], row[5])
                      for row in db.execute(f"PRAGMA table_info({table})")}
            if any(actual.get(name) != spec for name, spec in expected.items()):
                raise StorageUnavailableError("RECOVERY_CHAT_SCHEMA_REQUIRED")
        for table in ("messages", "records"):
            if not any(row[2:5] == ("conversations", "cid", "id")
                       for row in db.execute(f"PRAGMA foreign_key_list({table})")):
                raise StorageUnavailableError("RECOVERY_CHAT_FOREIGN_KEY_REQUIRED")
        unique_message_sequence = False
        for row in db.execute("PRAGMA index_list(messages)").fetchall():
            if row[2] and not row[4]:
                escaped = row[1].replace('"', '""')
                columns = [item[2] for item in db.execute(f'PRAGMA index_info("{escaped}")')]
                unique_message_sequence |= columns == ["cid", "seq"]
        if not unique_message_sequence:
            raise StorageUnavailableError("RECOVERY_MESSAGE_SEQUENCE_UNIQUENESS_REQUIRED")
        return _ValidatedDatabaseReport(
            data, quick_check="ok", foreign_key_violations=0,
            size_bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
    except (sqlite3.Error, OSError) as exc:
        raise StorageUnavailableError("database integrity validation failed") from exc
    finally:
        if db is not None:
            db.close()


def _validate_database_file(path: Path) -> dict:
    """Capture once without SQLite filename reopening/creation, then validate.

    Our fd supplies the bytes consumed by the in-memory SQLite connection. It
    does not identify a live store's native VFS handle, prove freshness, exclude
    same-host ABA, or supply independently monotonic custody.
    """
    path = Path(path).absolute()
    fd = None
    try:
        before = _recovery_path_chain(path)
        _deny_recovery_sidecars(path)
        flags = os.O_RDONLY
        for option in ("O_BINARY", "O_CLOEXEC", "O_NOFOLLOW", "O_NONBLOCK"):
            flags |= getattr(os, option, 0)
        fd = os.open(path, flags)
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
                or (info.st_dev, info.st_ino) != before[0]):
            raise StorageUnavailableError("RECOVERY_FD_IDENTITY_MISMATCH")
        if not 100 <= info.st_size <= MAX_RECOVERY_BYTES:
            raise StorageUnavailableError("RECOVERY_SIZE_DENIED")
        parts, total = [], 0
        while True:
            block = os.read(fd, min(65_536, MAX_RECOVERY_BYTES + 1 - total))
            if not block:
                break
            parts.append(block)
            total += len(block)
            if total > MAX_RECOVERY_BYTES:
                raise StorageUnavailableError("RECOVERY_SIZE_DENIED")
        if (_recovery_file_state(info) != _recovery_file_state(os.fstat(fd))
                or _recovery_path_chain(path) != before or total != info.st_size):
            raise StorageUnavailableError("RECOVERY_CHANGED_DURING_CAPTURE")
        _deny_recovery_sidecars(path)
        return _validate_database_bytes(b"".join(parts))
    except (OSError, sqlite3.Error) as exc:
        raise StorageUnavailableError("database file unavailable") from exc
    finally:
        if fd is not None:
            os.close(fd)


def _publish_database_report(report, destination):
    """Publish only captured bytes; late failure means uncertain local outcome.

    Existing target must be quiescent/offline. Sidecar/path checks cannot prove
    that another process holds no live DELETE-mode connection or prevent a
    privileged host from replacing bytes after verification. File fsync is not
    a portable power-loss/directory durability or independent custody claim.
    """
    if not isinstance(report, _ValidatedDatabaseReport):
        raise StorageUnavailableError("RECOVERY_CAPTURE_REQUIRED")
    data = report._data
    if hashlib.sha256(data).hexdigest() != report.get("sha256"):
        raise StorageUnavailableError("RECOVERY_CAPTURE_DIGEST_MISMATCH")
    destination = Path(destination).absolute()
    _recovery_path_chain(destination, missing=True)
    destination.parent.mkdir(parents=True, exist_ok=True)
    before = _recovery_path_chain(destination, missing=True)
    _deny_recovery_sidecars(destination)
    target_state = None
    if before[0] is not None:
        info = destination.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise StorageUnavailableError("RECOVERY_TARGET_FILE_REQUIRED")
        target_state = _recovery_file_state(info)
    temp = destination.with_name(destination.name + ".publish-" + uuid4().hex)
    fd = None
    publication_attempted = False
    try:
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        for option in ("O_BINARY", "O_CLOEXEC", "O_NOFOLLOW"):
            flags |= getattr(os, option, 0)
        fd = os.open(temp, flags, 0o600)
        identity = os.fstat(fd)
        pending = memoryview(data)
        while pending:
            written = os.write(fd, pending)
            if written <= 0:
                raise StorageUnavailableError("RECOVERY_WRITE_INCOMPLETE")
            pending = pending[written:]
        os.fsync(fd)
        after = os.fstat(fd)
        os.close(fd)
        fd = None
        captured = _validate_database_file(temp)
        if ((identity.st_dev, identity.st_ino) != _recovery_path_chain(temp)[0]
                or captured._data != data or after.st_size != len(data)):
            raise StorageUnavailableError("RECOVERY_OUTPUT_CHANGED")
        if _recovery_path_chain(destination, missing=True) != before:
            raise StorageUnavailableError("RECOVERY_TARGET_CHANGED")
        if target_state is not None and _recovery_file_state(destination.lstat()) != target_state:
            raise StorageUnavailableError("RECOVERY_TARGET_CHANGED")
        _deny_recovery_sidecars(destination)
        # An exception/lost response from replace cannot prove no effect.
        publication_attempted = True
        os.replace(temp, destination)
        final = _validate_database_file(destination)
        if final._data != data:
            raise StorageUnavailableError("RECOVERY_PUBLISHED_BYTES_CHANGED")
        return final
    except (OSError, sqlite3.Error, StorageUnavailableError) as exc:
        if publication_attempted:
            raise StorageUnavailableError(
                "RECOVERY_PUBLICATION_UNCERTAIN_ZERO_AUTO_RESEND") from exc
        if isinstance(exc, StorageUnavailableError):
            raise
        raise StorageUnavailableError("verified SQLite publication failed") from exc
    finally:
        if fd is not None:
            os.close(fd)
        try:
            temp.unlink(missing_ok=True)
        except OSError:
            pass


class SQLiteChatStore:
    def __init__(self, path, *, connection_factory=None,
                 require_managed_connection=False):
        # A187 LAB: fail closed before creating a file/parent if a HOST opts in
        # to mandatory factory admission. This does NOT authenticate a factory
        # or constrain raw sqlite3.connect elsewhere in the same host.
        if not isinstance(require_managed_connection, bool):
            raise TypeError("require_managed_connection must be bool")
        if connection_factory is not None and not callable(connection_factory):
            raise TypeError("connection_factory must be callable")
        if require_managed_connection and connection_factory is None:
            raise StorageUnavailableError("A187_MANAGED_CONNECTION_REQUIRED")
        if require_managed_connection and connection_factory is sqlite3.connect:
            raise StorageUnavailableError("A187_NATIVE_DEFAULT_FACTORY_DENIED")
        self._connection_factory = (
            sqlite3.connect if connection_factory is None else connection_factory
        )
        self._require_managed_connection = require_managed_connection
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._health_state = HEALTHY
        self._health_reason = "OK"
        self.db = None
        try:
            self.db = self._connection_factory(str(self.path), timeout=BUSY_TIMEOUT_MS / 1000)
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
            target = self._connection_factory(str(temp), timeout=BUSY_TIMEOUT_MS / 1000)
            self.db.backup(target)
            target.commit()
            # A backup artifact must be standalone, with no live WAL to replay.
            if str(target.execute("PRAGMA journal_mode=DELETE").fetchone()[0]).lower() != "delete":
                raise StorageUnavailableError("RECOVERY_OFFLINE_BACKUP_REQUIRED")
            target.close()
            target = None
            verified = _validate_database_file(temp)
            _publish_database_report(verified, destination)
            try:
                temp.unlink(missing_ok=True)
            except OSError:
                pass
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
        """Restore captured offline bytes; post-publication failure is uncertain.

        This validates local structure/content, not age, external provenance or
        a monotonic antirollback history. The target must be offline/quiescent.
        """
        source = Path(backup_path)
        target = Path(target_path)
        if source.resolve() == target.resolve():
            raise ValueError("restore target must differ from backup")
        source_report = _validate_database_file(source)
        try:
            restored_report = _publish_database_report(source_report, target)
            return {
                "state": "RESTORE_VERIFIED",
                "backup_path": str(source),
                "target_path": str(target),
                "source_sha256": source_report["sha256"],
                "restored_sha256": restored_report["sha256"],
                "size_bytes": restored_report["size_bytes"],
            }
        except (sqlite3.DatabaseError, OSError, StorageUnavailableError) as exc:
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
