"""A233 LAB: real, disposable SQLite native file/commit counterexamples.

No production data, network, external effects or activation. These probes
demonstrate open P0-5/6; they are not VFS integration or a production fix.
"""
from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import shutil
import sqlite3
from tempfile import TemporaryDirectory


@dataclass(frozen=True)
class SameInodeRollback:
    original: int
    updated: int
    after_restore: int
    path_unchanged: bool
    inode_unchanged: bool
    restored_sha_matches_old_bytes: bool
    native_read_identity_proven: bool = False
    p0_5_homologated: bool = False


@dataclass(frozen=True)
class WalBackupComparison:
    live_count: int
    main_only_copy_count: int
    sqlite_backup_count: int
    wal_sidecar_present: bool
    native_write_identity_proven: bool = False
    p0_6_homologated: bool = False


@dataclass(frozen=True)
class LostCommitAcknowledgment:
    persisted_rows: int
    reported_state: str
    can_auto_retry: bool
    external_effect_verified: bool = False
    p0_6_homologated: bool = False


def _db_value(path: Path) -> int:
    with closing(sqlite3.connect(str(path))) as db:
        return int(db.execute("SELECT value FROM state WHERE id=1").fetchone()[0])


def probe_same_inode_restore() -> SameInodeRollback:
    """Same path and inode can contain old state; file reopened after restore.

    This does NOT claim to reproduce a live-handle ABA/VFS attack.
    """
    with TemporaryDirectory(prefix="a233-native-") as raw:
        path = Path(raw) / "state.db"
        with closing(sqlite3.connect(str(path))) as db:
            db.execute("PRAGMA journal_mode=DELETE")
            db.execute("CREATE TABLE state (id INTEGER PRIMARY KEY, value INTEGER)")
            db.execute("INSERT INTO state VALUES (1, 1)")
            db.commit()
        original = _db_value(path)
        saved_bytes = path.read_bytes()
        old_sha = hashlib.sha256(saved_bytes).hexdigest()
        before = path.stat()
        with closing(sqlite3.connect(str(path))) as db:
            db.execute("UPDATE state SET value=2 WHERE id=1")
            db.commit()
        updated = _db_value(path)
        if original != 1 or updated != 2:
            raise AssertionError("unexpected disposable SQLite fixture state")
        with path.open("r+b") as handle:
            handle.write(saved_bytes)
            handle.truncate(len(saved_bytes))
            handle.flush()
            os.fsync(handle.fileno())
        after = path.stat()
        return SameInodeRollback(
            original=original, updated=updated,
            after_restore=_db_value(path), path_unchanged=path.exists(),
            inode_unchanged=(before.st_dev, before.st_ino) ==
                            (after.st_dev, after.st_ino),
            restored_sha_matches_old_bytes=(
                hashlib.sha256(path.read_bytes()).hexdigest() == old_sha
            ),
        )


def probe_wal_backup_comparison() -> WalBackupComparison:
    """SQLite's public backup API sees committed WAL frames; raw .db copy may not.

    A consistent backup is NOT proof of native VFS identity or anti-rollback.
    """
    with TemporaryDirectory(prefix="a233-wal-") as raw:
        root = Path(raw)
        path = root / "source.db"
        main_only = root / "raw-copy.db"
        backed_up = root / "sqlite-backup.db"
        with closing(sqlite3.connect(str(path))) as db:
            mode = str(db.execute("PRAGMA journal_mode=WAL").fetchone()[0]).lower()
            if mode != "wal":
                raise AssertionError("WAL unavailable in SQLite fixture")
            db.execute("CREATE TABLE state (id INTEGER PRIMARY KEY, value INTEGER)")
            db.execute("INSERT INTO state VALUES (1, 1)")
            db.commit()
            checkpoint = db.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
            if checkpoint[0] != 0:
                raise AssertionError("fixture WAL checkpoint was busy")
            db.execute("INSERT INTO state VALUES (2, 2)")
            db.commit()
            live = int(db.execute("SELECT count(*) FROM state").fetchone()[0])
            wal_path = root / "source.db-wal"
            wal_exists = wal_path.is_file() and wal_path.stat().st_size > 0
            shutil.copyfile(path, main_only)
            with closing(sqlite3.connect(str(backed_up))) as target:
                db.backup(target)
                target.commit()
            with closing(sqlite3.connect(str(main_only))) as bare:
                copy_count = int(bare.execute("SELECT count(*) FROM state").fetchone()[0])
            with closing(sqlite3.connect(str(backed_up))) as proper:
                backup_count = int(proper.execute("SELECT count(*) FROM state").fetchone()[0])
        return WalBackupComparison(
            live_count=live, main_only_copy_count=copy_count,
            sqlite_backup_count=backup_count, wal_sidecar_present=wal_exists,
        )


def probe_commit_ack_lost() -> LostCommitAcknowledgment:
    """Real SQLite COMMIT followed by synthetically lost application ACK.

    Not a simulated power loss and not an external payment or other effect.
    """
    with TemporaryDirectory(prefix="a233-ack-") as raw:
        path = Path(raw) / "state.db"
        with closing(sqlite3.connect(str(path))) as db:
            db.execute("CREATE TABLE state (id INTEGER PRIMARY KEY, value INTEGER)")
            db.commit()
            try:
                db.execute("INSERT INTO state VALUES (1, 7)")
                db.commit()
                raise TimeoutError("synthetic application ACK lost after commit")
            except TimeoutError:
                observed = "UNCERTAIN"
        with closing(sqlite3.connect(str(path))) as readback:
            rows = int(readback.execute("SELECT count(*) FROM state").fetchone()[0])
        return LostCommitAcknowledgment(
            persisted_rows=rows, reported_state=observed, can_auto_retry=False,
        )


__all__ = [
    "SameInodeRollback", "WalBackupComparison", "LostCommitAcknowledgment",
    "probe_same_inode_restore", "probe_wal_backup_comparison",
    "probe_commit_ack_lost",
]
