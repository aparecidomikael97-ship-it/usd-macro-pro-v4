"""A190 G18: Windows exact stdlib SQLite connection native file identity.

Only synthetic temp SQLite databases. The explicit C extension is unsafe for
production and must not be auto-loaded. Windows local file identity is NOT a
trusted external root, durable rollback witness, WAL attestation or owner proof.
"""
import ctypes
from contextlib import closing
import os
from pathlib import Path
import shutil
import sqlite3
import sys
import tempfile
import unittest

EXTENSION = os.environ.get("AION_G18_LAB_EXTENSION", "")
ENTRYPOINT = "sqlite3_aiong18_init"


def _native_identity(db):
    return db.execute("SELECT aion_lab_win32_native_identity()").fetchone()[0]


def _load_explicit_lab_extension(db):
    db.enable_load_extension(True)
    try:
        db.load_extension(EXTENSION, entrypoint=ENTRYPOINT)
    finally:
        db.enable_load_extension(False)


def _path_identity(path):
    """Open independent Windows read-attributes anchor; never borrow SQLite fd."""
    import ctypes.wintypes as wt

    class FILETIME(ctypes.Structure):
        _fields_ = [("low", wt.DWORD), ("high", wt.DWORD)]

    class BY_HANDLE_FILE_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("attributes", wt.DWORD), ("created", FILETIME),
            ("accessed", FILETIME), ("written", FILETIME),
            ("volume", wt.DWORD), ("size_hi", wt.DWORD),
            ("size_lo", wt.DWORD), ("links", wt.DWORD),
            ("index_hi", wt.DWORD), ("index_lo", wt.DWORD),
        ]

    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    open_file = k32.CreateFileW
    open_file.argtypes = [
        wt.LPCWSTR, wt.DWORD, wt.DWORD, ctypes.c_void_p,
        wt.DWORD, wt.DWORD, ctypes.c_void_p,
    ]
    open_file.restype = ctypes.c_void_p
    close_file = k32.CloseHandle
    close_file.argtypes = [ctypes.c_void_p]
    close_file.restype = wt.BOOL
    get_info = k32.GetFileInformationByHandle
    get_info.argtypes = [ctypes.c_void_p, ctypes.POINTER(BY_HANDLE_FILE_INFORMATION)]
    get_info.restype = wt.BOOL

    handle = open_file(str(Path(path).absolute()), 0x80, 0x1 | 0x2 | 0x4,
                       None, 3, 0, None)
    if handle in (None, ctypes.c_void_p(-1).value):
        raise OSError(ctypes.get_last_error(), "G18_ANCHOR_OPEN_DENY")
    try:
        info = BY_HANDLE_FILE_INFORMATION()
        if not get_info(ctypes.c_void_p(handle), ctypes.byref(info)):
            raise OSError(ctypes.get_last_error(), "G18_ANCHOR_FILE_INFO_DENY")
        return f"{info.volume:08x}:{info.index_hi:08x}:{info.index_lo:08x}"
    finally:
        close_file(ctypes.c_void_p(handle))


@unittest.skipUnless(sys.platform == "win32", "Windows native VFS required")
class G18WindowsExactStdlibConnectionTests(unittest.TestCase):
    def setUp(self):
        if not EXTENSION or not Path(EXTENSION).is_file():
            self.fail("G18_EXPLICIT_COMPILED_LAB_EXTENSION_REQUIRED")
        self.tmp = tempfile.TemporaryDirectory(prefix="aion-g18-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.live = self.root / "live.sqlite3"
        self.clone = self.root / "clone.sqlite3"
        with closing(sqlite3.connect(self.live)) as db, db:
            db.execute("PRAGMA journal_mode=DELETE")
            db.execute("CREATE TABLE aion_native_marker_v1(marker TEXT)")
            db.execute("CREATE TABLE synthetic_events(value TEXT)")
            db.execute("INSERT INTO aion_native_marker_v1 VALUES(?)", ("c" * 32,))
            db.execute("INSERT INTO synthetic_events VALUES('original')")
        shutil.copyfile(self.live, self.clone)
        with closing(sqlite3.connect(self.clone)) as db, db:
            db.execute("INSERT INTO synthetic_events VALUES('clone-only')")

    def test_01_native_connection_matches_independent_path_anchor(self):
        with closing(sqlite3.connect(self.live)) as db:
            _load_explicit_lab_extension(db)
            self.assertEqual(_native_identity(db), _path_identity(self.live))
        print("G18_WIN32_EXACT_STDLIB_NATIVE_MATCH=LOCAL_OBSERVATION_ONLY")

    def test_02_same_marker_clone_has_different_native_file_identity(self):
        with closing(sqlite3.connect(self.live)) as good, closing(sqlite3.connect(self.clone)) as rogue:
            _load_explicit_lab_extension(good)
            _load_explicit_lab_extension(rogue)
            self.assertEqual(good.execute("SELECT marker FROM aion_native_marker_v1").fetchone(),
                             rogue.execute("SELECT marker FROM aion_native_marker_v1").fetchone())
            self.assertEqual(good.execute("SELECT count(*) FROM synthetic_events").fetchone()[0], 1)
            self.assertEqual(rogue.execute("SELECT count(*) FROM synthetic_events").fetchone()[0], 2)
            self.assertEqual(_native_identity(good), _path_identity(self.live))
            self.assertNotEqual(_native_identity(rogue), _path_identity(self.live))
        print("G18_WIN32_SAME_MARKER_CLONE=WRONG_NATIVE_FILE_DENIED_BY_COMPARISON")

    def test_03_rogue_preopened_plus_honest_decoy_cannot_spoof_connection(self):
        with closing(sqlite3.connect(self.clone)) as rogue:
            _load_explicit_lab_extension(rogue)
            with closing(sqlite3.connect(self.live)) as decoy:
                _load_explicit_lab_extension(decoy)
                self.assertNotEqual(_native_identity(rogue), _native_identity(decoy))
                self.assertEqual(_native_identity(decoy), _path_identity(self.live))
                self.assertNotEqual(_native_identity(rogue), _path_identity(self.live))
        print("G18_WIN32_PREOPENED_ROGUE_PLUS_DECOY=CONNECTIONS_DISTINGUISHED")

    def test_04_missing_independent_anchor_denies(self):
        with closing(sqlite3.connect(self.live)) as db:
            _load_explicit_lab_extension(db)
            with self.assertRaises(OSError):
                _path_identity(self.root / "not-present.sqlite3")
        print("G18_WIN32_MISSING_ANCHOR=DENY")

    def test_05_memory_database_does_not_fabricate_native_handle(self):
        with closing(sqlite3.connect(":memory:")) as db:
            _load_explicit_lab_extension(db)
            with self.assertRaisesRegex(sqlite3.OperationalError,
                                        "G18_WIN32_NATIVE_HANDLE_UNSUPPORTED_DENY"):
                _native_identity(db)
        print("G18_WIN32_MEMORY_DATABASE=FAIL_CLOSED")

    def test_06_extension_loading_disabled_after_registration(self):
        with closing(sqlite3.connect(self.live)) as db:
            _load_explicit_lab_extension(db)
            with self.assertRaises(sqlite3.OperationalError):
                db.load_extension(EXTENSION, entrypoint=ENTRYPOINT)
            self.assertEqual(_native_identity(db), _path_identity(self.live))
        print("G18_WIN32_FURTHER_NATIVE_LOADS=DENIED")

    def test_07_directonly_disallows_untrusted_sql_view(self):
        with closing(sqlite3.connect(self.live)) as db:
            _load_explicit_lab_extension(db)
            db.execute("CREATE VIEW synthetic_untrusted_view AS SELECT aion_lab_win32_native_identity() AS id")
            with self.assertRaisesRegex(sqlite3.OperationalError, "unsafe use"):
                db.execute("SELECT * FROM synthetic_untrusted_view").fetchall()
        print("G18_WIN32_DIRECTONLY_VIEW=DENIED")

    def test_08_wal_main_file_identity_is_not_sidecar_proof(self):
        with closing(sqlite3.connect(self.live)) as db:
            _load_explicit_lab_extension(db)
            self.assertEqual(db.execute("PRAGMA journal_mode=WAL").fetchone()[0].lower(), "wal")
            with db:
                db.execute("INSERT INTO synthetic_events VALUES('wal')")
            self.assertEqual(_native_identity(db), _path_identity(self.live))
            self.assertEqual(db.execute("SELECT count(*) FROM synthetic_events").fetchone()[0], 2)
        print("G18_WIN32_WAL_MAIN_MATCH=NOT_WAL_SHM_OR_ROLLBACK_ATTESTATION")

    def test_09_two_real_connections_same_file_share_local_identity(self):
        with closing(sqlite3.connect(self.live)) as first, closing(sqlite3.connect(self.live)) as second:
            _load_explicit_lab_extension(first)
            _load_explicit_lab_extension(second)
            self.assertEqual(_native_identity(first), _native_identity(second))
            self.assertEqual(_native_identity(first), _path_identity(self.live))
        print("G18_WIN32_TWO_REAL_CONNECTIONS=SAME_NATIVE_FILE_LOCAL_ONLY")


    def test_10_closed_file_replacement_matches_native_but_wrong_content_red(self):
        """Adversary controls both the local DB and the expected path: native match is NOT integrity."""
        with closing(sqlite3.connect(self.live)) as before:
            original_marker = before.execute("SELECT marker FROM aion_native_marker_v1").fetchone()
            self.assertEqual(before.execute("SELECT count(*) FROM synthetic_events").fetchone()[0], 1)
        self.live.unlink()
        shutil.copyfile(self.clone, self.live)
        with closing(sqlite3.connect(self.live)) as after:
            _load_explicit_lab_extension(after)
            self.assertEqual(after.execute("SELECT marker FROM aion_native_marker_v1").fetchone(),
                             original_marker)
            self.assertEqual(after.execute("SELECT count(*) FROM synthetic_events").fetchone()[0], 2)
            self.assertEqual(_native_identity(after), _path_identity(self.live))
        print("G18_WIN32_CLOSED_FILE_REPLACEMENT=WRONG_CONTENT_NATIVE_MATCH_RED")


if __name__ == "__main__":
    unittest.main()
