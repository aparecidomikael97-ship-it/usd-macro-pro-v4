"""A190 G15 LAB ONLY: observable Linux /proc fd heuristic, NOT VFS attestation.

A candidate opened after the snapshot is NOT proven to be the sqlite3.Connection
used by the caller. Other open descriptors (decoys, pooled connections, fd reuse)
can misattribute native identity. Do not import into production authorization.
Only inspect descriptors; never issue a database operation or reopen a path.
"""
import os
import stat
import sys
from dataclasses import dataclass
from pathlib import Path


SQLITE_MAGIC = b"SQLite format 3\x00"


@dataclass(frozen=True)
class Observation:
    status: str
    candidate_count: int
    candidate_identities: tuple

    @property
    def is_native_attestation(self):
        # Intentionally ALWAYS false. A /proc delta is not a VFS file handle.
        return False


def _main_database_fds():
    """Return (fd -> dev,inode) for observable open SQLite *main* files.

    Linux-only implementation. The 16-byte file header is not a trusted
    authority, and fd enumeration cannot associate an fd with a Python
    sqlite3.Connection. Races or disappearing fds are discarded.
    """
    if sys.platform != "linux" or not Path("/proc/self/fd").is_dir():
        return None
    found = {}
    try:
        names = os.listdir("/proc/self/fd")
    except OSError:
        return None
    for name in names:
        if not name.isdecimal():
            continue
        fd = int(name)
        try:
            info = os.fstat(fd)
            if not stat.S_ISREG(info.st_mode):
                continue
            if os.pread(fd, len(SQLITE_MAGIC), 0) != SQLITE_MAGIC:
                continue
            found[fd] = (info.st_dev, info.st_ino)
        except (OSError, ValueError):
            continue
    return found


class LinuxProcFdHeuristic:
    """Evidence of observable fd *changes*, never evidence of which SQLite VFS fd."""

    def __init__(self):
        self.before = _main_database_fds()

    def observe(self, expected_dev_ino):
        after = _main_database_fds()
        if self.before is None or after is None:
            return Observation("UNSUPPORTED_FAIL_CLOSED", 0, ())
        fresh = tuple(sorted(ident for fd, ident in after.items()
                             if self.before.get(fd) != ident))
        if not fresh:
            return Observation("INCONCLUSIVE_NO_NEW_FD", 0, ())
        if len(fresh) != 1:
            return Observation("INCONCLUSIVE_AMBIGUOUS_FDS", len(fresh), fresh)
        if fresh[0] != tuple(expected_dev_ino):
            return Observation("OBSERVED_FD_MISMATCH_NOT_CONNECTION_PROOF", 1, fresh)
        return Observation("CANDIDATE_MATCH_NOT_ATTESTATION", 1, fresh)
