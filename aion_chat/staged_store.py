"""Connection-free staged host handle; native SQLite stays thread-affine.

Only materialized store results cross the operation boundary. Each operation
opens and closes its native connection on the calling thread. A handle serializes
operations and close; other handles/processes rely on existing SQLite transactions
and busy_timeout. This is not a production or distributed authorization gate.
"""
import os
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

    # Metadata observation only for methods that do not intentionally write.
    # This is not a transaction snapshot or independent rollback attestation.
    _READ_ONLY_METHODS = frozenset({
        "get_conversation", "list_conversations", "search_conversations",
        "list_messages", "get_message", "get_attachment",
        "get_latest_checkpoint", "get_latest_summary", "retrieve_messages",
        "storage_health", "require_healthy",
    })

    def __init__(self, path):
        self.path = Path(path)
        self._lock = RLock()
        self._closed = False
        self._failure = ""
        self._file_identity = None
        self._parent_identity = None
        self.require_healthy()

    def close(self):
        # Wait for any in-flight operation (including its finally/close), then
        # revoke this handle. There is no connection to close on this thread.
        with self._lock:
            self._closed = True

    def _path_identity(self, *, allow_missing):
        """Refuse reparse/symlink/non-file aliases; not physical host attestation.

        lstat does not follow the final symlink. This is a best-effort path
        guard with pre/open/post-operation comparisons, not atomic native
        SQLite VFS handle pinning, monotonic witness or hostile-host proof.
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

    def _ancestor_chain_identity(self, *, allow_missing):
        """Inspect every parent, including platform-specific directory junctions.

        lstat sees the path component itself (not its symlink target). The
        snapshots are best effort: there is no atomic openat-based native
        SQLite VFS binding or protection against a same-inode ABA swap.
        """
        chain = []
        parent = self.path.parent
        while True:
            try:
                info = parent.lstat()
            except FileNotFoundError as exc:
                if not allow_missing:
                    raise StorageUnavailableError(
                        "BOUND_DATABASE_ANCESTOR_UNAVAILABLE") from exc
                chain.append(None)  # native first bootstrap can create dirs
            except OSError as exc:
                raise StorageUnavailableError(
                    "BOUND_DATABASE_ANCESTOR_UNAVAILABLE") from exc
            else:
                try:
                    is_junction = getattr(parent, "is_junction", None)
                    junction = bool(is_junction()) if callable(is_junction) else False
                except OSError as exc:
                    raise StorageUnavailableError(
                        "BOUND_DATABASE_ANCESTOR_UNAVAILABLE") from exc
                if stat.S_ISLNK(info.st_mode) or junction:
                    raise StorageUnavailableError(
                        "BOUND_DATABASE_ANCESTOR_ALIAS_DENIED")
                if not stat.S_ISDIR(info.st_mode):
                    raise StorageUnavailableError(
                        "BOUND_DATABASE_ANCESTOR_NOT_DIRECTORY")
                chain.append((info.st_dev, info.st_ino))
            if parent.parent == parent:
                break
            parent = parent.parent
        return tuple(chain)

    @staticmethod
    def _compatible_parent_chains(before, after):
        # Only the first initialization may create missing directories.
        return (len(before) == len(after) and all(
            old is None or old == new for old, new in zip(before, after)))

    def _verify_identity_anchor(self, fd, expected):
        """Compare a separately opened OS descriptor to the observed DB path.

        This descriptor pins its *own* inode for the duration of an operation.
        Python sqlite3 does not expose SQLite's internal VFS handle, so this
        does NOT prove the native SQLite connection opened the same inode.
        """
        try:
            info = os.fstat(fd)
        except OSError as exc:
            raise StorageUnavailableError(
                "BOUND_DATABASE_ANCHOR_UNAVAILABLE") from exc
        if not stat.S_ISREG(info.st_mode):
            raise StorageUnavailableError(
                "BOUND_DATABASE_ANCHOR_NOT_REGULAR_FILE")
        if (info.st_dev, info.st_ino) != expected:
            raise StorageUnavailableError("BOUND_DATABASE_ANCHOR_MISMATCH")

    def _open_identity_anchor(self, expected):
        """Open no-follow, nonblocking descriptor when OS flags support it."""
        flags = os.O_RDONLY
        for flag in ("O_BINARY", "O_CLOEXEC", "O_NOFOLLOW", "O_NONBLOCK"):
            flags |= getattr(os, flag, 0)
        try:
            fd = os.open(self.path, flags)
        except OSError as exc:
            raise StorageUnavailableError(
                "BOUND_DATABASE_ANCHOR_UNAVAILABLE") from exc
        try:
            self._verify_identity_anchor(fd, expected)
            return fd
        except BaseException:
            os.close(fd)
            raise

    def _read_snapshot(self, anchor):
        """Detect *observed* read-window metadata drift, including some ABA.

        The independent DB descriptor, parent directory timestamps and WAL/SHM
        sidecar lstat values give a fail-closed heuristic. Timestamp granularity,
        forged metadata, races outside this window and native VFS identity can
        still evade it. Normal concurrent writes can trigger false positives.
        """
        try:
            db = os.fstat(anchor)
            parent = self.path.parent.lstat()
            sidecars = []
            for suffix in ("-wal", "-shm"):
                candidate = Path(str(self.path) + suffix)
                try:
                    entry = candidate.lstat()
                except FileNotFoundError:
                    sidecars.append(None)
                else:
                    sidecars.append((
                        entry.st_dev, entry.st_ino, entry.st_size,
                        entry.st_ctime_ns, entry.st_mtime_ns,
                    ))
            return (
                (db.st_dev, db.st_ino, db.st_size, db.st_nlink,
                 db.st_ctime_ns, db.st_mtime_ns),
                (parent.st_dev, parent.st_ino,
                 parent.st_ctime_ns, parent.st_mtime_ns),
                tuple(sidecars),
            )
        except OSError as exc:
            raise StorageUnavailableError(
                "BOUND_DATABASE_READ_SNAPSHOT_UNAVAILABLE") from exc

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
                anchor = None
                try:
                    parents_before = self._ancestor_chain_identity(
                        allow_missing=self._parent_identity is None)
                    if (self._parent_identity is not None
                            and parents_before != self._parent_identity):
                        raise StorageUnavailableError(
                            "BOUND_DATABASE_ANCESTOR_REPLACED")
                    before = self._path_identity(
                        allow_missing=self._file_identity is None)
                    if (self._file_identity is not None
                            and before != self._file_identity):
                        raise StorageUnavailableError("BOUND_DATABASE_REPLACED")
                    if before is not None:
                        # Hold a separately verified file descriptor across
                        # native SQLite open, operation and native close.
                        anchor = self._open_identity_anchor(before)
                        if (self._ancestor_chain_identity(allow_missing=False)
                                != parents_before):
                            raise StorageUnavailableError(
                                "BOUND_DATABASE_ANCESTOR_CHANGED_BEFORE_OPEN")
                        if self._path_identity(allow_missing=False) != before:
                            raise StorageUnavailableError(
                                "BOUND_DATABASE_CHANGED_BEFORE_OPEN")
                    store = SQLiteChatStore(self.path)
                    parents_after_open = self._ancestor_chain_identity(
                        allow_missing=False)
                    if (not self._compatible_parent_chains(
                            parents_before, parents_after_open)
                            or (self._parent_identity is not None
                                and parents_after_open != self._parent_identity)):
                        raise StorageUnavailableError(
                            "BOUND_DATABASE_ANCESTOR_CHANGED_DURING_OPEN")
                    after_open = self._path_identity(allow_missing=False)
                    if ((before is not None and after_open != before)
                            or (self._file_identity is not None
                                and after_open != self._file_identity)):
                        raise StorageUnavailableError(
                            "BOUND_DATABASE_CHANGED_DURING_OPEN")
                    if anchor is None:
                        # First-ever bootstrap creates the DB during open.
                        anchor = self._open_identity_anchor(after_open)
                    else:
                        self._verify_identity_anchor(anchor, after_open)
                    if self._file_identity is None:
                        self._file_identity = after_open
                    if self._parent_identity is None:
                        self._parent_identity = parents_after_open
                    read_before = (
                        self._read_snapshot(anchor)
                        if name in self._READ_ONLY_METHODS else None
                    )
                    result = getattr(store, name)(*args, **kwargs)
                    if (self._ancestor_chain_identity(allow_missing=False)
                            != self._parent_identity):
                        # A write may ALREADY have committed; no automatic
                        # retry or rollback assumption is permissible.
                        raise StorageUnavailableError(
                            "BOUND_DATABASE_ANCESTOR_CHANGED_DURING_OPERATION")
                    after_operation = self._path_identity(allow_missing=False)
                    if after_operation != self._file_identity:
                        # A write may ALREADY have committed. Report UNKNOWN,
                        # latch this facade, and require independent readback;
                        # NEVER retry or treat this as rolled back.
                        raise StorageUnavailableError(
                            "BOUND_DATABASE_CHANGED_DURING_OPERATION")
                    self._verify_identity_anchor(anchor, after_operation)
                    if (read_before is not None
                            and self._read_snapshot(anchor) != read_before):
                        # A read result may have seen mixed external state.
                        # This failure revokes this facade; it does not claim
                        # to identify who changed the DB or prove rollback.
                        raise StorageUnavailableError(
                            "BOUND_DATABASE_READ_SNAPSHOT_CHANGED")
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
                    try:
                        if store is not None:
                            if store._health_state == FAILED:
                                self._failure = "DATABASE_FAILED"
                            try:
                                store.close()
                            except Exception as exc:
                                self._failure = "CONNECTION_CLOSE_FAILED"
                                raise StorageUnavailableError(self._failure) from exc
                    finally:
                        if anchor is not None:
                            try:
                                os.close(anchor)
                            except OSError as exc:
                                # A prior write may have committed: do not
                                # return ordinary success or attempt replay.
                                self._failure = "BOUND_DATABASE_ANCHOR_CLOSE_FAILED"
                                raise StorageUnavailableError(self._failure) from exc

        return operation
