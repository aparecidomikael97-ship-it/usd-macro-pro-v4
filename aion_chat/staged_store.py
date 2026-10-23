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

    # A172 narrow directory-rename observation for read-only operations.
    # This is not a transaction snapshot or independent rollback attestation.
    _READ_ONLY_METHODS = frozenset({
        "get_conversation", "list_conversations", "search_conversations",
        "list_messages", "get_message", "get_attachment",
        "get_latest_checkpoint", "get_latest_summary", "retrieve_messages",
        "storage_health", "require_healthy",
    })

    # Only operations which normally mutate SQLite without creating or
    # renaming other files inside the parent folder. backup_to intentionally
    # excluded: its output-file protocol needs a separate transaction gate.
    _WRITE_SENSITIVE_METHODS = frozenset({
        "create_conversation", "archive_conversation", "append_message",
        "add_attachment_metadata", "save_checkpoint",
        "save_context_summary", "wal_checkpoint",
    })

    def __init__(self, path, *, connection_factory=None,
                 require_managed_connection=False):
        # A187 LAB: enforce opt-in admission before require_healthy reopens
        # SQLite. The factory itself remains caller-controlled, not trusted.
        if not isinstance(require_managed_connection, bool):
            raise TypeError("require_managed_connection must be bool")
        if connection_factory is not None and not callable(connection_factory):
            raise TypeError("connection_factory must be callable")
        if require_managed_connection and connection_factory is None:
            raise StorageUnavailableError("A187_MANAGED_CONNECTION_REQUIRED")
        if require_managed_connection and connection_factory is sqlite3.connect:
            raise StorageUnavailableError("A187_NATIVE_DEFAULT_FACTORY_DENIED")
        self._connection_factory = connection_factory
        self._require_managed_connection = require_managed_connection
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

    def _rename_fingerprint(self, anchor):
        """Temporal directory fingerprint; never a native SQLite VFS binding.

        A rename-away-and-back ordinarily changes the parent directory's
        metadata. A normal WAL write generally does not. This observation
        can miss timestamp-level ABA and can flag unrelated directory edits.
        """
        try:
            db = os.fstat(anchor)
            parent = self.path.parent.lstat()
            return (
                (db.st_dev, db.st_ino),
                (parent.st_dev, parent.st_ino,
                 parent.st_ctime_ns, parent.st_mtime_ns),
            )
        except OSError as exc:
            raise StorageUnavailableError(
                "BOUND_DATABASE_FINGERPRINT_UNAVAILABLE") from exc

    def _read_snapshot(self, anchor):
        return self._rename_fingerprint(anchor)

    def _verify_native_declared_path(self, store):
        """Check SQLite's own main filename, NOT its native fd/inode.

        Reject a misdirected connection before invoking a store method.
        database_list is a pathname diagnostic; same-name ABA and VFS/sidecar
        identity remain unproved. Store initialization may already have run.
        """
        rows = store.db.execute("PRAGMA database_list").fetchall()
        main = [row for row in rows if row[1] == "main"]
        expected = os.path.normcase(os.path.abspath(self.path))
        if (len(main) != 1 or not main[0][2]
                or os.path.normcase(os.path.abspath(main[0][2])) != expected
                or any(row[1] not in {"main", "temp"} for row in rows)):
            raise StorageUnavailableError("NATIVE_DATABASE_PATH_MISMATCH")

    def _write_snapshot(self, anchor):
        # A post-write alarm is always UNKNOWN outcome: native SQLite may
        # already have committed; never authorize replay automatically.
        return self._rename_fingerprint(anchor)

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
                    # Preserve the original single-argument constructor
                    # when the LAB factory seam is not being exercised.
                    # Legacy test doubles and existing hosts remain compatible.
                    store = (
                        SQLiteChatStore(self.path)
                        if self._connection_factory is None
                        else SQLiteChatStore(
                            self.path,
                            connection_factory=self._connection_factory,
                            require_managed_connection=self._require_managed_connection,
                        )
                    )
                    self._verify_native_declared_path(store)
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
                    write_before = (
                        self._write_snapshot(anchor)
                        if name in self._WRITE_SENSITIVE_METHODS else None
                    )
                    result = getattr(store, name)(*args, **kwargs)
                    try:
                        self._verify_native_declared_path(store)
                    except StorageUnavailableError as exc:
                        raise StorageUnavailableError(
                            "NATIVE_DATABASE_PATH_POST_OPERATION_OUTCOME_UNKNOWN") from exc
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
                    if (write_before is not None
                            and self._write_snapshot(anchor) != write_before):
                        # Native SQLite may already have persisted this exact
                        # write. The result is uncertain; no automatic retry.
                        raise StorageUnavailableError(
                            "BOUND_DATABASE_WRITE_OUTCOME_UNKNOWN_DIRECTORY_CHANGED")
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
                    if str(exc) in {
                            "BOUND_DATABASE_WRITE_OUTCOME_UNKNOWN_DIRECTORY_CHANGED",
                            "NATIVE_DATABASE_PATH_POST_OPERATION_OUTCOME_UNKNOWN"}:
                        # Preserve the exact hazard for post-error health checks.
                        # Do not convert a possibly committed write into retry.
                        self._failure = str(exc)
                    else:
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
