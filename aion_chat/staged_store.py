"""Connection-free staged host handle; native SQLite stays thread-affine.

Only materialized store results cross the operation boundary. Each operation
opens and closes its native connection on the calling thread. A handle serializes
operations and close; other handles/processes rely on existing SQLite transactions
and busy_timeout. This is not a production or distributed authorization gate.
"""
import sqlite3
import stat
from pathlib import Path
from threading import RLock

from .store import FAILED, SQLiteChatStore, StorageUnavailableError


class OperationScopedSQLiteChatStore:
    _METHODS = frozenset({
        "create_conversation", "get_conversation", "list_conversations",
        "search_conversations", "archive_conversation", "append_message",
        "list_messages", "get_message", "add_attachment_metadata",
        "get_attachment", "save_checkpoint", "get_latest_checkpoint",
        "save_context_summary", "get_latest_summary", "retrieve_messages",
        "storage_health", "require_healthy", "wal_checkpoint", "backup_to",
    })

    def __init__(self, path):
        self.path = Path(path)
        self._lock = RLock()
        self._closed = False
        self._failure = ""
        self._file_identity = None
        self.require_healthy()

    def close(self):
        # Wait for any in-flight operation (including its finally/close), then
        # revoke this handle. There is no connection to close on this thread.
        with self._lock:
            self._closed = True

    def _path_identity(self, *, allow_missing):
        """Refuse reparse/symlink/non-file aliases; not physical host attestation.

        lstat does not follow the final symlink. This is a best-effort path
        guard with pre/open/post-operation comparisons, not an atomic OS
        handle pin, external monotonic witness or hostile-host guarantee.
        """
        try:
            info = self.path.lstat()
        except FileNotFoundError as exc:
            if allow_missing:
                return None  # first initialization may create this DB
            raise StorageUnavailableError("BOUND_DATABASE_UNAVAILABLE") from exc
        except OSError as exc:
            raise StorageUnavailableError("BOUND_DATABASE_UNAVAILABLE") from exc
        if stat.S_ISLNK(info.st_mode):
            raise StorageUnavailableError("BOUND_DATABASE_SYMLINK_DENIED")
        if not stat.S_ISREG(info.st_mode):
            raise StorageUnavailableError("BOUND_DATABASE_NOT_REGULAR_FILE")
        return (info.st_dev, info.st_ino)

    def __getattr__(self, name):
        if name not in self._METHODS:
            raise AttributeError(name)

        def operation(*args, **kwargs):
            with self._lock:
                if self._closed or self._failure:
                    reason = "STORE_CLOSED" if self._closed else self._failure
                    if name == "storage_health":
                        return {"state": FAILED, "reason": reason, "path": str(self.path),
                                "journal_mode": "", "busy_timeout_ms": 0,
                                "quick_check": "", "foreign_key_violations": None}
                    raise StorageUnavailableError("staged handle unavailable: " + reason)
                store = None
                try:
                    before = self._path_identity(
                        allow_missing=self._file_identity is None)
                    if (self._file_identity is not None
                            and before != self._file_identity):
                        raise StorageUnavailableError("BOUND_DATABASE_REPLACED")
                    store = SQLiteChatStore(self.path)
                    after_open = self._path_identity(allow_missing=False)
                    if ((before is not None and after_open != before)
                            or (self._file_identity is not None
                                and after_open != self._file_identity)):
                        raise StorageUnavailableError(
                            "BOUND_DATABASE_CHANGED_DURING_OPEN")
                    if self._file_identity is None:
                        self._file_identity = after_open
                    result = getattr(store, name)(*args, **kwargs)
                    if self._path_identity(allow_missing=False) != self._file_identity:
                        # A write may ALREADY have committed. Report UNKNOWN,
                        # latch this facade, and require independent readback;
                        # NEVER retry or treat this as rolled back.
                        raise StorageUnavailableError(
                            "BOUND_DATABASE_CHANGED_DURING_OPERATION")
                    return result
                except sqlite3.DatabaseError as exc:
                    # Constraint rejection/busy is not proof of corruption. Other
                    # database errors stay latched until this handle is revoked.
                    busy = isinstance(exc, sqlite3.OperationalError) and (
                        "locked" in str(exc).lower() or "busy" in str(exc).lower()
                    )
                    if not isinstance(exc, sqlite3.IntegrityError) and not busy:
                        self._failure = "DATABASE_ERROR:" + type(exc).__name__
                    raise
                except StorageUnavailableError as exc:
                    self._failure = type(exc).__name__
                    raise
                finally:
                    if store is not None:
                        if store._health_state == FAILED:
                            self._failure = "DATABASE_FAILED"
                        try:
                            store.close()
                        except Exception as exc:
                            self._failure = "CONNECTION_CLOSE_FAILED"
                            raise StorageUnavailableError(self._failure) from exc

        return operation
