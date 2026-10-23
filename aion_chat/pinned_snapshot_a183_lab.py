"""A183 LAB: pinned offline SQLite artifact, never a live-store replacement.

The file descriptor supplies bytes; SQLite deserializes those exact bytes into
:memory:. This avoids claiming stdlib exposes its native VFS handle. Expected
SHA-256 is a retained fixture, not authenticated external provenance. Live WAL,
journals, filesystem persistence and unpinned restore are deliberately denied.
"""
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
    def __init__(self, path, *, expected_sha256):
        if type(expected_sha256) is not str or not re.fullmatch("[0-9a-f]{64}",expected_sha256):
            raise StorageUnavailableError("PINNED_SNAPSHOT_DIGEST_REQUIRED")
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
            if any(Path(str(path)+suffix).exists() for suffix in ("-wal","-shm","-journal")):
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
                if db.execute("PRAGMA quick_check").fetchall()!=[("ok",)]:
                    raise StorageUnavailableError("SNAPSHOT_INTEGRITY_FAILED")
        except (OSError,sqlite3.Error) as exc:
            self._data=None
            raise StorageUnavailableError("SNAPSHOT_UNAVAILABLE") from exc
        finally:
            if fd is not None: os.close(fd)

    def _connection(self):
        from contextlib import contextmanager
        @contextmanager
        def opened():
            db=sqlite3.connect(":memory:")
            try:
                if not hasattr(db,"deserialize"):
                    raise StorageUnavailableError("NATIVE_DESERIALIZE_UNAVAILABLE")
                db.deserialize(self._data)
                files=db.execute("PRAGMA database_list").fetchall()
                if files!=[(0,"main","")]:
                    raise StorageUnavailableError("NATIVE_MEMORY_DATABASE_REQUIRED")
                yield db
            finally:
                db.close()
        return opened()

    def rows(self, sql, parameters=()):
        with self._lock:
            if self._data is None:
                raise StorageUnavailableError("SNAPSHOT_CLOSED")
            with self._connection() as db:
                db.execute("PRAGMA query_only=ON")
                def authorize(action,one,two,database,source):
                    if action in (sqlite3.SQLITE_SELECT,sqlite3.SQLITE_READ):
                        return sqlite3.SQLITE_OK
                    if action==sqlite3.SQLITE_FUNCTION and (two or "").lower() in {
                            "count","min","max","length","typeof","coalesce","abs","sum"}:
                        return sqlite3.SQLITE_OK
                    return sqlite3.SQLITE_DENY
                db.set_authorizer(authorize)
                return db.execute(sql,parameters).fetchall()

    def persist(self, *args, **kwargs):
        raise StorageUnavailableError("NATIVE_PERSISTENCE_UNATTESTED_ZERO_AUTO_RESEND")

    backup_to=persist

    def close(self):
        with self._lock:
            self._data=None

