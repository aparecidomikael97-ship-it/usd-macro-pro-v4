"""Connection-free staged host handle; native SQLite stays thread-affine.

Only materialized store results cross the operation boundary. Each operation
opens and closes its native connection on the calling thread. A handle serializes
operations and close; other handles/processes rely on existing SQLite transactions
and busy_timeout. Ported from isolated Draft #1195, with current SQLiteChatStore owner-thread,
restore/WAL and fail-closed guards retained. It is not a production,
distributed authority or external highwater/producer trust gate.
"""
import sqlite3
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
                    if self._file_identity is not None:
                        try:
                            current = self.path.stat()
                        except OSError as exc:
                            raise StorageUnavailableError("BOUND_DATABASE_UNAVAILABLE") from exc
                        if (current.st_dev, current.st_ino) != self._file_identity:
                            raise StorageUnavailableError("BOUND_DATABASE_REPLACED")
                    store = SQLiteChatStore(self.path)
                    if self._file_identity is None:
                        current = self.path.stat()
                        self._file_identity = (current.st_dev, current.st_ino)
                    return getattr(store, name)(*args, **kwargs)
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
