"""A190 G16 — supported SQLite file_control probes via APSW, isolated LAB ONLY.

Unlike G15 process-wide fd enumeration, these invoke sqlite3_file_control on
the ACTUAL connection. Neither result authenticates the host, owner, monotonic
custody or WAL sidecars, and nothing here is a production authorization gate.

The APSW wheel is installed only in G16 CI; production sqlite3 is unchanged.
References: sqlite.org/c3ref/file_control.html and
sqlite.org/c3ref/c_fcntl_begin_atomic_write.html
"""
import ctypes
import sys
from dataclasses import dataclass
from pathlib import Path

import apsw


@dataclass(frozen=True)
class Probe:
    status: str
    native_file_control_supported: bool
    native_connection_tied: bool

    @property
    def homologated(self):
        # Even Windows handle equality is local, not external antirollback.
        return False


def native_sqlite_has_moved(connection):
    """Run SQLite's *same connection* HAS_MOVED operation, not a path guess.

    If the VFS does not support it, MUST fail closed. Zero means only
    'not moved according to this local VFS at this instant'.
    """
    flag = ctypes.c_int(-1)
    try:
        supported = connection.file_control(
            "main", apsw.SQLITE_FCNTL_HAS_MOVED, ctypes.addressof(flag)
        )
    except (apsw.Error, ValueError, TypeError):
        return Probe("G16_NATIVE_HAS_MOVED_ERROR_DENY", False, True)
    if not supported:
        return Probe("G16_NATIVE_HAS_MOVED_UNSUPPORTED_DENY", False, True)
    if flag.value == 1:
        return Probe("G16_NATIVE_HANDLE_MOVED_DENY", True, True)
    if flag.value == 0:
        return Probe("G16_NATIVE_HANDLE_NOT_MOVED_OBSERVATION_ONLY", True, True)
    return Probe("G16_NATIVE_HAS_MOVED_INVALID_DENY", True, True)


def _windows_file_identity(native_handle):
    """Return volume and file index from the OS handle; do not close it."""
    import ctypes.wintypes as w

    class FILETIME(ctypes.Structure):
        _fields_ = [("lo", w.DWORD), ("hi", w.DWORD)]

    class BY_HANDLE_FILE_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("attrs", w.DWORD),
            ("created", FILETIME),
            ("accessed", FILETIME),
            ("modified", FILETIME),
            ("volume", w.DWORD),
            ("size_hi", w.DWORD), ("size_lo", w.DWORD),
            ("links", w.DWORD),
            ("index_hi", w.DWORD), ("index_lo", w.DWORD),
        ]
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    getinfo = kernel.GetFileInformationByHandle
    getinfo.argtypes = [ctypes.c_void_p, ctypes.POINTER(BY_HANDLE_FILE_INFORMATION)]
    getinfo.restype = w.BOOL
    info = BY_HANDLE_FILE_INFORMATION()
    if not getinfo(ctypes.c_void_p(native_handle), ctypes.byref(info)):
        raise OSError(ctypes.get_last_error(), "GetFileInformationByHandle failed")
    return (info.volume, info.index_hi, info.index_lo)


def _windows_anchor_identity(path):
    """Independent path anchor via OS handle, for comparison only."""
    import ctypes.wintypes as w

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    create = kernel.CreateFileW
    create.argtypes = [
        w.LPCWSTR, w.DWORD, w.DWORD, ctypes.c_void_p,
        w.DWORD, w.DWORD, ctypes.c_void_p,
    ]
    create.restype = ctypes.c_void_p
    create_result = create(
        str(Path(path).absolute()), 0x0080, 0x0001 | 0x0002 | 0x0004,
        None, 3, 0, None,
    )
    if create_result in (None, ctypes.c_void_p(-1).value):
        raise OSError(ctypes.get_last_error(), "CreateFileW anchor failed")
    try:
        return _windows_file_identity(create_result)
    finally:
        close = kernel.CloseHandle
        close.argtypes = [ctypes.c_void_p]
        close.restype = w.BOOL
        close(ctypes.c_void_p(create_result))


def win32_native_file_identity(connection, path):
    """Same-connection SQLite Windows HANDLE versus independent OS path HANDLE.

    Unlike procfd deltas, SQLite directly returns the handle of THIS
    connection via documented SQLITE_FCNTL_WIN32_GET_HANDLE. Fail closed on
    unsupported VFS, OS info unavailable, mismatches. Still local only.
    """
    if sys.platform != "win32":
        return Probe("G16_WIN32_ONLY_UNSUPPORTED_DENY", False, False)
    handle = ctypes.c_void_p(None)
    try:
        supported = connection.file_control(
            "main", apsw.SQLITE_FCNTL_WIN32_GET_HANDLE,
            ctypes.addressof(handle),
        )
    except (apsw.Error, ValueError, TypeError):
        return Probe("G16_WIN32_NATIVE_HANDLE_ERROR_DENY", False, True)
    if not supported or not handle.value:
        return Probe("G16_WIN32_NATIVE_HANDLE_UNSUPPORTED_DENY", False, True)
    try:
        native_identity = _windows_file_identity(handle.value)
        path_identity = _windows_anchor_identity(path)
    except (OSError, ValueError):
        return Probe("G16_WIN32_NATIVE_IDENTITY_UNAVAILABLE_DENY", True, True)
    if native_identity != path_identity:
        return Probe("G16_WIN32_SAME_CONNECTION_NATIVE_MISMATCH_DENY", True, True)
    return Probe("G16_WIN32_SAME_CONNECTION_NATIVE_MATCH_LOCAL_ONLY", True, True)
