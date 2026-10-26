"""G126: best-effort, SAME-PROCESS local SQLite epoch fence (LAB ONLY).

This wrapper adds an explicitly HOST-CONTROLLED pre/post-operation snapshot
to the existing OperationScopedSQLiteChatStore. It observes raw DB, -wal and
-shm bytes and filesystem metadata in a bounded, single-writer test fixture.
It can notice a same-inode byte rollback while THIS wrapper retains its
unmodified epoch. It cannot attest SQLite's internal VFS handle, provide
independent monotonic custody, survive hostile host/restart+epoch rollback,
or make a provider first SEND safe. NEVER integrate into production Worker.
"""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from threading import RLock
import stat

from aion_chat.staged_store import OperationScopedSQLiteChatStore
from aion_chat.store import StorageUnavailableError

MAX_SNAPSHOT_BYTES = 16 * 1024 * 1024


class G126LocalEpochFenceLab:
    """Opt-in, fail-closed local observation; no external trust authority."""

    _READS = OperationScopedSQLiteChatStore._READ_ONLY_METHODS
    _WRITES = OperationScopedSQLiteChatStore._WRITE_SENSITIVE_METHODS
    _ALLOWED = _READS | _WRITES

    def __init__(self, path):
        self.path = Path(path)
        self._lock = RLock()
        self._closed = False
        self._failure = ""
        self._inner = OperationScopedSQLiteChatStore(self.path)
        try:
            self._epoch = self._capture()
        except BaseException:
            self._inner.close()
            raise

    def _capture(self):
        """Observe all THREE local files; this is not a native VFS snapshot."""
        observed = []
        total_bytes = 0
        for suffix in ("", "-wal", "-shm"):
            node = Path(str(self.path) + suffix)
            try:
                before = node.lstat()
            except FileNotFoundError:
                if not suffix:
                    raise StorageUnavailableError("G126_MAIN_DATABASE_MISSING")
                observed.append(None)
                continue
            except OSError as exc:
                raise StorageUnavailableError("G126_LOCAL_FILE_UNAVAILABLE") from exc
            if not stat.S_ISREG(before.st_mode):
                raise StorageUnavailableError("G126_LOCAL_FILE_ALIAS_OR_TYPE_DENIED")
            if before.st_size < 0 or total_bytes + before.st_size > MAX_SNAPSHOT_BYTES:
                raise StorageUnavailableError("G126_LOCAL_SNAPSHOT_BUDGET_DENIED")
            try:
                payload = node.read_bytes()
                after = node.lstat()
            except OSError as exc:
                raise StorageUnavailableError("G126_LOCAL_FILE_UNAVAILABLE") from exc
            marker_before = (before.st_dev, before.st_ino, before.st_size,
                             before.st_ctime_ns, before.st_mtime_ns)
            marker_after = (after.st_dev, after.st_ino, after.st_size,
                            after.st_ctime_ns, after.st_mtime_ns)
            if marker_before != marker_after or len(payload) != before.st_size:
                raise StorageUnavailableError("G126_LOCAL_READ_RACE_DENIED")
            total_bytes += len(payload)
            observed.append((marker_after, sha256(payload).digest()))
        return tuple(observed)

    def close(self):
        with self._lock:
            if not self._closed:
                self._closed = True
                self._inner.close()

    def __getattr__(self, name):
        if name not in self._ALLOWED:
            raise AttributeError(name)

        def fenced_operation(*args, **kwargs):
            with self._lock:
                if self._closed or self._failure:
                    raise StorageUnavailableError(
                        "G126_LOCAL_EPOCH_QUARANTINED:"
                        + ("CLOSED" if self._closed else self._failure)
                    )
                try:
                    before = self._capture()
                    if before != self._epoch:
                        raise StorageUnavailableError(
                            "G126_LOCAL_EPOCH_DRIFT_BEFORE_OPERATION"
                        )
                    result = getattr(self._inner, name)(*args, **kwargs)
                    after = self._capture()
                    if name in self._READS and after != before:
                        # A read might have mixed epochs. Return no result.
                        raise StorageUnavailableError(
                            "G126_LOCAL_EPOCH_CHANGED_DURING_READ"
                        )
                    if name in self._WRITES:
                        # Self-adoption is explicitly NOT an independent seal;
                        # a host admin can rewrite both DB and this Python state.
                        self._epoch = after
                    return result
                except BaseException as exc:
                    # Some methods may have already committed. Latch the
                    # facade; never automatically roll back or retry.
                    self._failure = type(exc).__name__
                    raise

        return fenced_operation
