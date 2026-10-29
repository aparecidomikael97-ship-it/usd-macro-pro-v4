"""Local SQLite staging with scoped identity and explicit resilience controls."""
import base64
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import stat
import time
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


class BackupPublicationUncertainError(StorageUnavailableError):
    """A backup may already be visible; never retry blindly."""


class RestorePublicationUncertainError(StorageUnavailableError):
    """Restore target may have been published: NEVER retry without inspection."""


class StoreCommitOutcomeUncertainError(StorageUnavailableError):
    """Chat message COMMIT may have persisted; block this store, never retry blind."""


def _sync_staging_restore_directory(directory: Path) -> bool:
    """Request a parent-directory fsync on POSIX, or report unsupported.

    False means unsupported on this host; True means the OS call returned.
    Neither value certifies physical power-loss durability or trust in the
    filesystem, disk controller or administrator.
    """
    if os.name != "posix" or not hasattr(os, "O_DIRECTORY"):
        return False
    fd = os.open(str(directory), os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
    return True


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
        # A247 LAB: local crash/ACK-loss veto only; host-admin can tamper.
        self._message_commit_marker = Path(str(self.path) + ".aion-message-commit-pending")
        self._health_state = HEALTHY
        self._health_reason = "OK"
        self.db = None
        self._pathname_identity = None
        try:
            # A local marker is a veto, never a proof of successful COMMIT.
            # No automatic marker deletion/recovery at startup.
            if self._pending_message_commit_fence():
                raise StorageUnavailableError(
                    "staging message COMMIT outcome pending; manual review required"
                )
            # A245 LAB: check the existing pathname both before and after
            # connect(). A rename during connect() must not silently pin the
            # *new* pathname while SQLite still holds the previous file.
            # This does NOT authenticate the native SQLite VFS/FD or protect
            # a newly created path or same-inode rollback from host control.
            try:
                before_connect = self.path.stat(follow_symlinks=False)
            except FileNotFoundError:
                before_connect = None
            if before_connect is not None and (
                not stat.S_ISREG(before_connect.st_mode)
                or int(before_connect.st_ino) <= 0
            ):
                raise StorageUnavailableError(
                    "staging SQLite preconnect pathname is not a regular file"
                )
            self.db = sqlite3.connect(str(self.path), timeout=BUSY_TIMEOUT_MS / 1000)
            self.db.row_factory = sqlite3.Row
            # Staging pathname comparison only; Python sqlite3 does NOT expose
            # an authenticated native VFS/FD identity of the opened handle.
            opened_name = self.path.stat(follow_symlinks=False)
            if not stat.S_ISREG(opened_name.st_mode) or int(opened_name.st_ino) <= 0:
                raise StorageUnavailableError("staging SQLite pathname identity unavailable")
            if before_connect is not None and (
                (before_connect.st_dev, before_connect.st_ino)
                != (opened_name.st_dev, opened_name.st_ino)
            ):
                raise StorageUnavailableError(
                    "staging SQLite pathname changed while opening connection"
                )
            self._pathname_identity = (opened_name.st_dev, opened_name.st_ino)
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

    def _pathname_binding_reason(self):
        """Detect visible pathname replacement; NOT proof of the SQLite FD."""
        if self._pathname_identity is None:
            return "PATH_IDENTITY_NOT_CAPTURED"
        try:
            current = self.path.stat(follow_symlinks=False)
        except OSError:
            return "PATH_MISSING_OR_UNREADABLE"
        if not stat.S_ISREG(current.st_mode):
            return "PATH_NOT_REGULAR"
        if int(current.st_ino) <= 0:
            return "PATH_IDENTITY_UNAVAILABLE"
        if (current.st_dev, current.st_ino) != self._pathname_identity:
            return "PATH_IDENTITY_CHANGED"
        return "OK"

    def _pending_message_commit_fence(self) -> bool:
        """Bounded grace for an in-flight *normal* COMMIT cleanup.

        Avoid falsely treating another concurrent writer's brief marker as a
        persistent failure. No DB access occurs while the marker is visible;
        failure to clear within this bound remains a sticky veto. This is not
        reconciliation of an uncertain external/local effect.
        """
        if not os.path.lexists(self._message_commit_marker):
            return False
        for _ in range(50):
            time.sleep(0.01)
            if not os.path.lexists(self._message_commit_marker):
                return False
        return True

    def _require_open(self):
        if self.db is None:
            raise StorageUnavailableError("staging store is closed")
        if self._health_state == FAILED:
            raise StorageUnavailableError("staging store health is failed")
        if self._pending_message_commit_fence():
            self._health_state = FAILED
            self._health_reason = "MESSAGE_COMMIT_PENDING_ZERO_AUTO_RETRY"
            raise StorageUnavailableError(
                "staging message COMMIT pending; refuse reuse"
            )
        reason = self._pathname_binding_reason()
        if reason != "OK":
            self._health_state = FAILED
            self._health_reason = reason
            raise StorageUnavailableError("staging store pathname binding lost: " + reason)

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
        # A marker can be created by another writer after this handle opened.
        # Allow a bounded grace for a concurrent, successfully completed
        # commit to remove its transient marker; persistent uncertainty vetoes.
        if self._pending_message_commit_fence():
            self._health_state = FAILED
            self._health_reason = "MESSAGE_COMMIT_PENDING_ZERO_AUTO_RETRY"
        # A failed identity/health gate cannot be cleared by a later
        # "healthy" check on the same connection: reopen is required.
        if self._health_state == FAILED:
            return {
                "state": FAILED,
                "reason": self._health_reason,
                "path": str(self.path),
                "journal_mode": "",
                "busy_timeout_ms": 0,
                "quick_check": "not_run",
                "foreign_key_violations": None,
            }
        reason = self._pathname_binding_reason()
        if reason != "OK":
            self._health_state = FAILED
            self._health_reason = reason
            return {
                "state": FAILED,
                "reason": reason,
                "path": str(self.path),
                "journal_mode": "",
                "busy_timeout_ms": 0,
                "quick_check": "not_run",
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
        # Never treat an existing SQLite database, WAL or interrupted backup
        # as an available backup destination. This check is advisory; the
        # atomic hardlink below is the final publish-if-absent gate.
        if any(os.path.lexists(str(destination) + suffix)
               for suffix in ("", "-wal", "-shm", "-journal")):
            raise StorageUnavailableError(
                "backup denied: destination or SQLite sidecars already exist"
            )
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
            # os.replace can detach a live SQLite handle while new readers
            # open a different inode at the same destination pathname.
            # Publish only under a free name; never overwrite any target.
            if any(os.path.lexists(str(destination) + suffix)
                   for suffix in ("", "-wal", "-shm", "-journal")):
                raise StorageUnavailableError(
                    "backup denied: destination or SQLite sidecars appeared"
                )
            try:
                os.link(temp, destination)
            except FileExistsError as exc:
                raise StorageUnavailableError(
                    "backup denied: destination created concurrently"
                ) from exc
            # From here, the destination may be visible even if a later step
            # fails. Fail as UNCERTAIN, retain the published file, and require
            # inspection before any manual recovery or reuse.
            try:
                dirsync_supported = _sync_staging_restore_directory(destination.parent)
                if any(os.path.lexists(str(destination) + suffix)
                       for suffix in ("-wal", "-shm", "-journal")):
                    raise BackupPublicationUncertainError(
                        "BACKUP_PUBLICATION_OUTCOME_UNKNOWN_SIDECAR_ZERO_AUTO_RETRY"
                    )
                before_cleanup = temp.stat()
                published = destination.stat(follow_symlinks=False)
                if (before_cleanup.st_dev, before_cleanup.st_ino) != (
                    published.st_dev, published.st_ino
                ):
                    raise BackupPublicationUncertainError(
                        "BACKUP_PUBLICATION_OUTCOME_UNKNOWN_TARGET_CHANGED_ZERO_AUTO_RETRY"
                    )
                temp.unlink()
            except OSError as exc:
                raise BackupPublicationUncertainError(
                    "BACKUP_PUBLICATION_OUTCOME_UNKNOWN_POST_LINK_IO_ZERO_AUTO_RETRY"
                ) from exc
            return {
                "state": "BACKUP_VERIFIED",
                "source_path": str(self.path),
                "backup_path": str(destination),
                "checkpoint": checkpoint,
                "directory_sync_requested": dirsync_supported,
                "power_loss_durability_verified": False,
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
    def restore_from_backup(cls, backup_path, target_path, *, expected_sha256=None):
        """Publish a verified staging backup only to an unused path; never overwrite.

        Neither a pathname precheck nor this API proves that a compromised host
        has no detached SQLite handles or controls no other copies. This only
        closes the known destructive replacement path, not P0-5/6 overall.
        """
        if expected_sha256 is not None and (
            not isinstance(expected_sha256, str)
            or len(expected_sha256) != 64
            or any(ch not in "0123456789abcdef" for ch in expected_sha256)
        ):
            raise ValueError("expected backup SHA-256 must be 64 lowercase hex characters")
        source = Path(backup_path)
        target = Path(target_path)
        if source.resolve() == target.resolve():
            raise ValueError("restore target must differ from backup")
        # A local .aion-restore-pending marker is a *veto*, not authenticated
        # evidence of successful restore. Never automatically clear/retry it.
        marker = Path(str(target) + ".aion-restore-pending")
        # A live WAL/-shm/-journal is a veto, even when main .db is absent.
        # os.path.lexists also detects dangling symlinks and directories.
        # This preflight is NOT a lock: os.link below provides the final
        # atomic publish-if-absent check against another creator of target.
        if any(os.path.lexists(str(target) + suffix)
               for suffix in ("", "-wal", "-shm", "-journal", ".aion-restore-pending")):
            raise StorageUnavailableError(
                "restore denied: destination or SQLite sidecars already exist"
            )
        source_report = _validate_database_file(source)
        if expected_sha256 is not None and source_report["sha256"] != expected_sha256:
            raise StorageUnavailableError("restore denied: source differs from manifest")
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
            if expected_sha256 is not None and restored_report["sha256"] != expected_sha256:
                raise StorageUnavailableError("restore denied: copied pages differ from manifest")
            # Never use os.replace here: Linux permits a live connection
            # to keep reading an unlinked OLD database while new openers see
            # the NEW file at the same pathname. Windows may reject the swap.
            # Hardlinking a temp file in the same directory publishes ONLY
            # when the destination does not already exist (no TOCTOU replace).
            # This may be unsupported by a filesystem: fail closed instead.
            if any(os.path.lexists(str(target) + suffix)
                   for suffix in ("", "-wal", "-shm", "-journal", ".aion-restore-pending")):
                raise StorageUnavailableError(
                    "restore denied: destination or SQLite sidecars appeared"
                )
            # Create an exclusive local crash fence BEFORE the irreversible
            # pathname publication. If the process exits abruptly at/after
            # this point, a later call must not silently try again.
            # File fsync helps process-crash observation; without an
            # independently synced directory/witness this is NOT proof of
            # power-loss durability or hostile-root tamper resistance.
            with marker.open("xb") as guard:
                guard.write(b"AION_STAGING_RESTORE_PENDING_V0\nNO_AUTO_RETRY\n")
                guard.flush()
                os.fsync(guard.fileno())
            # A file fsync alone does not flush the marker's directory entry.
            # On POSIX, request metadata flush before creating target. On
            # unsupported OSes do NOT claim power-loss durability.
            dirsync_supported = _sync_staging_restore_directory(target.parent)
            os.link(temp, target)
            # Publication may already be visible to other SQLite clients.
            # Any failure AFTER this point is an uncertain outcome, not
            # "nothing happened". Do not delete the published target or retry.
            try:
                # POSIX flush of the newly linked target name; failure after
                # link means the outcome is uncertain and the marker is kept.
                _sync_staging_restore_directory(target.parent)
                if any(os.path.lexists(str(target) + suffix)
                       for suffix in ("-wal", "-shm", "-journal")):
                    raise RestorePublicationUncertainError(
                        "RESTORE_PUBLICATION_OUTCOME_UNKNOWN_SIDECAR_RACE_ZERO_AUTO_RETRY"
                    )
                # A host may rename/swap the just-published target even if
                # the directory preflight passed. This detects a visible
                # replacement, not an authentic VFS handle or a complete lock.
                before_cleanup = temp.stat()
                after_link = target.stat(follow_symlinks=False)
                if (before_cleanup.st_dev, before_cleanup.st_ino) != (
                    after_link.st_dev, after_link.st_ino
                ):
                    raise RestorePublicationUncertainError(
                        "RESTORE_PUBLICATION_OUTCOME_UNKNOWN_TARGET_CHANGED_ZERO_AUTO_RETRY"
                    )
                temp.unlink()
                # Only a fully checked, successful local publication may
                # clear its own marker; any cleanup exception leaves a veto.
                marker.unlink()
                # Persist the unlink request on POSIX where supported.
                # Failure is STILL uncertain: target may already be visible.
                _sync_staging_restore_directory(target.parent)
            except OSError as exc:
                raise RestorePublicationUncertainError(
                    "RESTORE_PUBLICATION_OUTCOME_UNKNOWN_POST_LINK_IO_ZERO_AUTO_RETRY"
                ) from exc
            return {
                "state": "RESTORE_VERIFIED",
                "backup_path": str(source),
                "target_path": str(target),
                "source_sha256": source_report["sha256"],
                "restored_sha256": restored_report["sha256"],
                "size_bytes": restored_report["size_bytes"],
                "directory_sync_requested": dirsync_supported,
                "power_loss_durability_verified": False,
                "manifest_sha256_verified": expected_sha256 is not None,
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
        # Guard the connection before attribute lookup: a closed db handle is None.
        # The check must precede `self.db.execute`, not occur in its arguments.
        requested_scope = self._scope(scope)
        row = self.db.execute(
            "SELECT data FROM conversations WHERE id=? AND owner=? AND tenant=? AND workspace=?",
            (conversation_id, *requested_scope),
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
        self._require_open()
        with self.db:
            c = self.get_conversation(scope, conversation_id)
            c.archived, c.updated_at = True, now()
            self._update(c)
        return c

    def _publish_message_commit_marker(self):
        """Publish local pre-COMMIT veto; never treat as independent custody."""
        try:
            # Under the SQLite IMMEDIATE writer lock, mark the possibility of
            # an attempted COMMIT BEFORE calling commit(). Never overwrite.
            with self._message_commit_marker.open("xb") as marker:
                marker.write(b"AION_STAGING_MESSAGE_COMMIT_PENDING_V0\nNO_AUTO_RETRY\n")
                marker.flush()
                os.fsync(marker.fileno())
            # The directory sync is best-effort across platforms. Windows
            # returns False; neither result certifies power-loss durability.
            _sync_staging_restore_directory(self.path.parent)
        except OSError as exc:
            self._health_state = FAILED
            self._health_reason = "COMMIT_MARKER_PREPARE_UNKNOWN_ZERO_AUTO_RETRY"
            raise StorageUnavailableError(
                "cannot prepare message COMMIT fence; no COMMIT permitted"
            ) from exc

    def _clear_message_commit_marker(self):
        """Clear only after a COMMIT acknowledgement; failed cleanup denies reuse."""
        try:
            self._message_commit_marker.unlink()
            _sync_staging_restore_directory(self.path.parent)
        except OSError as exc:
            self._health_state = FAILED
            self._health_reason = "COMMIT_MARKER_CLEAR_UNKNOWN_ZERO_AUTO_RETRY"
            raise StoreCommitOutcomeUncertainError(
                "message COMMIT succeeded but pending-fence cleanup uncertain"
            ) from exc

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
            # A247: publish the veto before calling COMMIT, while holding
            # BEGIN IMMEDIATE. A crash after a durable COMMIT but before ACK
            # leaves a marker for the next opener to refuse automatically.
            self._publish_message_commit_marker()
            # A246 LAB: once COMMIT is attempted, any missing acknowledgment
            # may conceal a durable write. A best-effort rollback cannot
            # prove that the COMMIT did not happen.
            try:
                self.db.commit()
            except Exception as exc:
                self._health_state = FAILED
                self._health_reason = "COMMIT_OUTCOME_UNKNOWN_ZERO_AUTO_RETRY"
                raise StoreCommitOutcomeUncertainError(
                    "chat COMMIT outcome unknown; this store cannot be reused"
                ) from exc
            self._clear_message_commit_marker()
        except Exception as exc:
            try:
                self.db.rollback()
            except Exception:
                pass
            if (
                not isinstance(exc, StoreCommitOutcomeUncertainError)
                and isinstance(exc, sqlite3.DatabaseError)
                and not isinstance(exc, sqlite3.IntegrityError)
            ):
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
        self._require_open()
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
        self._require_open()
        with self.db:
            prior = self.get_latest_checkpoint(scope, checkpoint.conversation_id)
            if prior and checkpoint.through_sequence <= prior.through_sequence:
                raise ValueError("coverage must advance")
            self._save_record(scope, "checkpoint", checkpoint, checkpoint.through_sequence)
            c = self.get_conversation(scope, checkpoint.conversation_id)
            c.latest_checkpoint = checkpoint.id
            self._update(c)

    def save_context_summary(self, scope, summary):
        self._require_open()
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
