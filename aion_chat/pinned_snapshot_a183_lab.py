"""A183 LAB: pinned offline SQLite artifact, never a live-store replacement.

The file descriptor supplies bytes; SQLite deserializes those exact bytes into
:memory:. This avoids claiming stdlib exposes its native VFS handle. Expected
SHA-256 is a retained fixture, not authenticated external provenance. Live WAL,
journals, filesystem persistence and unpinned restore are deliberately denied.
Read budgets bound SQLite VM progress and returned material, not wall-clock
time, total native memory, hostile OS activity or independent custody.
"""
from contextlib import contextmanager
import hashlib
import os
from pathlib import Path
import re
import sqlite3
import stat
from threading import RLock

from aion_chat.store import StorageUnavailableError


class PinnedSQLiteSnapshotLab:
    MAX_BYTES = 16 * 1024 * 1024
    MAX_VM_STEPS = 1_000_000
    MAX_ROWS = 10_000
    MAX_RESULT_BYTES = 4 * 1024 * 1024

    def __init__(self, path, *, expected_sha256,
                 max_vm_steps=MAX_VM_STEPS, max_rows=MAX_ROWS,
                 max_result_bytes=MAX_RESULT_BYTES):
        if type(expected_sha256) is not str or not re.fullmatch("[0-9a-f]{64}",expected_sha256):
            raise StorageUnavailableError("PINNED_SNAPSHOT_DIGEST_REQUIRED")
        for value, ceiling in ((max_vm_steps, self.MAX_VM_STEPS),
                               (max_rows, self.MAX_ROWS),
                               (max_result_bytes, self.MAX_RESULT_BYTES)):
            if type(value) is not int or not 1 <= value <= ceiling:
                raise StorageUnavailableError("SNAPSHOT_POSITIVE_BUDGET_REQUIRED")
        self._max_vm_steps = max_vm_steps
        self._max_rows = max_rows
        self._max_result_bytes = max_result_bytes
        self._lock=RLock()
        self._data=None
        path=Path(path).absolute()
        def chain():
            result=[]
            for node in (path,*path.parents):
                info=node.lstat()
                junction=getattr(node,"is_junction",lambda:False)()
                if stat.S_ISLNK(info.st_mode) or junction:
                    raise StorageUnavailableError("SNAPSHOT_ALIAS_DENIED")
                result.append((info.st_dev,info.st_ino))
            return result
        def no_sidecars():
            for suffix in ("-wal", "-shm", "-journal"):
                try:
                    Path(str(path) + suffix).lstat()
                except FileNotFoundError:
                    continue
                # A dangling alias is still an ambiguous directory entry.
                # Other stat errors propagate to the fail-closed outer handler.
                raise StorageUnavailableError("LIVE_SQLITE_SIDECAR_DENIED")
        fd=None
        try:
            before=chain()
            no_sidecars()
            flags=os.O_RDONLY
            for name in ("O_BINARY","O_CLOEXEC","O_NOFOLLOW","O_NONBLOCK"):
                flags |= getattr(os,name,0)
            fd=os.open(path,flags)
            info=os.fstat(fd)
            if not stat.S_ISREG(info.st_mode) or (info.st_dev,info.st_ino)!=before[0]:
                raise StorageUnavailableError("SNAPSHOT_FD_IDENTITY_MISMATCH")
            if not 100 <= info.st_size <= self.MAX_BYTES:
                raise StorageUnavailableError("SNAPSHOT_SIZE_DENIED")
            parts=[]; total=0
            while True:
                block=os.read(fd,min(65536,self.MAX_BYTES+1-total))
                if not block: break
                total+=len(block)
                if total>self.MAX_BYTES:
                    raise StorageUnavailableError("SNAPSHOT_SIZE_DENIED")
                parts.append(block)
            data=b"".join(parts)
            after=os.fstat(fd)
            fields=("st_dev","st_ino","st_size","st_mtime_ns","st_ctime_ns")
            if tuple(getattr(info,f) for f in fields)!=tuple(getattr(after,f) for f in fields) or chain()!=before:
                raise StorageUnavailableError("SNAPSHOT_CHANGED_DURING_CAPTURE")
            no_sidecars()
            if hashlib.sha256(data).hexdigest()!=expected_sha256:
                raise StorageUnavailableError("SNAPSHOT_DIGEST_MISMATCH")
            if data[:16]!=b"SQLite format 3\0" or data[18:20]!=b"\x01\x01":
                raise StorageUnavailableError("OFFLINE_ROLLBACK_FORMAT_REQUIRED")
            self._data=data
            self.digest=expected_sha256
            # Validate using the actual in-memory SQLite database.
            with self._connection() as db:
                with self._vm_budget(db, self.MAX_VM_STEPS):
                    cursor = db.execute("PRAGMA quick_check(1)")
                    if cursor.fetchone() != ("ok",) or cursor.fetchone() is not None:
                        raise StorageUnavailableError("SNAPSHOT_INTEGRITY_FAILED")
        except StorageUnavailableError:
            self._data = None
            raise
        except (OSError,sqlite3.Error) as exc:
            self._data=None
            raise StorageUnavailableError("SNAPSHOT_UNAVAILABLE") from exc
        finally:
            if fd is not None: os.close(fd)

    def _connection(self):
        @contextmanager
        def opened():
            db=sqlite3.connect(":memory:")
            try:
                if not hasattr(db,"deserialize"):
                    raise StorageUnavailableError("NATIVE_DESERIALIZE_UNAVAILABLE")
                db.deserialize(self._data)
                files = db.execute("PRAGMA database_list")
                if files.fetchone() != (0, "main", "") or files.fetchone() is not None:
                    raise StorageUnavailableError("NATIVE_MEMORY_DATABASE_REQUIRED")
                # Avoid query scratch spilling to disk. This is not an RSS cap.
                db.execute("PRAGMA temp_store=MEMORY")
                self._length_limit(db, self.MAX_RESULT_BYTES)
                yield db
            finally:
                db.close()
        return opened()

    @staticmethod
    def _length_limit(db, budget):
        if not hasattr(db, "setlimit"):
            raise StorageUnavailableError("NATIVE_QUERY_LIMITS_UNAVAILABLE")
        # SQLite checks the length of each value/encoded row before returning
        # it to Python. Aggregate accounting below also includes row/cell costs.
        db.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, budget)

    @staticmethod
    @contextmanager
    def _vm_budget(db, limit):
        steps = 0
        exhausted = False

        def progress():
            nonlocal steps, exhausted
            steps += 1
            exhausted = steps > limit
            return int(exhausted)

        db.set_progress_handler(progress, 1)
        try:
            yield
        except sqlite3.Error as exc:
            if exhausted:
                raise StorageUnavailableError("SNAPSHOT_VM_STEP_BUDGET_EXCEEDED") from exc
            raise
        finally:
            db.set_progress_handler(None, 0)

    @staticmethod
    def _row_bytes(row):
        # Deterministic conservative accounting, not platform-specific RSS.
        total = 64 + 32 * len(row)
        for value in row:
            if value is None:
                continue
            if isinstance(value, (int, float)):
                total += 8
            elif isinstance(value, str):
                total += len(value.encode("utf-8"))
            elif isinstance(value, bytes):
                total += len(value)
            else:
                raise StorageUnavailableError("SNAPSHOT_RESULT_TYPE_DENIED")
        return total

    def rows(self, sql, parameters=()):
        with self._lock:
            if self._data is None:
                raise StorageUnavailableError("SNAPSHOT_CLOSED")
            with self._connection() as db:
                db.execute("PRAGMA query_only=ON")
                self._length_limit(db, self._max_result_bytes)
                def authorize(action,one,two,database,source):
                    if action in (sqlite3.SQLITE_SELECT,sqlite3.SQLITE_READ):
                        return sqlite3.SQLITE_OK
                    if action==sqlite3.SQLITE_FUNCTION and (two or "").lower() in {
                            "count","min","max","length","typeof","coalesce","abs","sum"}:
                        return sqlite3.SQLITE_OK
                    return sqlite3.SQLITE_DENY
                db.set_authorizer(authorize)
                result = []
                total_bytes = 0
                try:
                    with self._vm_budget(db, self._max_vm_steps):
                        cursor = db.execute(sql, parameters)
                        while True:
                            row = cursor.fetchone()
                            if row is None:
                                return result
                            if len(result) >= self._max_rows:
                                raise StorageUnavailableError("SNAPSHOT_ROW_BUDGET_EXCEEDED")
                            total_bytes += self._row_bytes(row)
                            if total_bytes > self._max_result_bytes:
                                raise StorageUnavailableError("SNAPSHOT_RESULT_BYTE_BUDGET_EXCEEDED")
                            result.append(row)
                except sqlite3.Error as exc:
                    if getattr(exc, "sqlite_errorcode", None) == sqlite3.SQLITE_TOOBIG:
                        raise StorageUnavailableError("SNAPSHOT_RESULT_BYTE_BUDGET_EXCEEDED") from exc
                    raise

    def persist(self, *args, **kwargs):
        raise StorageUnavailableError("NATIVE_PERSISTENCE_UNATTESTED_ZERO_AUTO_RESEND")

    backup_to=persist

    def close(self):
        with self._lock:
            self._data=None

