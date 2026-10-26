"""G128 OS-principal native SQLite probe: ephemeral CI users, LAB ONLY.

The Python file is public/accessible on a test runner. The SQLite database
resides in a *separate* directory guarded by actual filesystem ACLs. Caller
principal must be checked using the OS identity command, not an input claim.

PASS means an unprivileged second OS account was blocked, not that AION,
SQLite native VFS, cloud root or a hostile local administrator is secure.
No real AION data, broker, provider, secrets, network or production hooks.
"""
from __future__ import annotations

import os
from pathlib import Path
import sqlite3
import subprocess
import sys


def principal() -> str:
    result = subprocess.run(["whoami"], capture_output=True, text=True, check=True)
    return result.stdout.strip().split("\\")[-1].lower()


def must_be(expected: str) -> None:
    actual = principal()
    if actual != expected.lower():
        raise AssertionError(
            f"G128_PRINCIPAL_MISMATCH: expected={expected.lower()} actual={actual}"
        )


def read_conversation_count(db_path: Path) -> int:
    # The same read-only SQLite URI must work for owner and be denied to app.
    ro_uri = db_path.resolve().as_uri() + "?mode=ro"
    connection = sqlite3.connect(ro_uri, uri=True)
    try:
        return connection.execute("SELECT count(*) FROM custody_probe").fetchone()[0]
    finally:
        connection.close()


def owner(db_path: Path, expected: str, create: bool) -> None:
    must_be(expected)
    if create and db_path.exists():
        raise AssertionError("G128_REFUSE_TO_OVERWRITE_EXISTING_DB")
    if not create and not db_path.is_file():
        raise AssertionError("G128_DB_NOT_PRESENT")

    with sqlite3.connect(str(db_path)) as connection:
        connection.execute(
            "CREATE TABLE IF NOT EXISTS custody_probe "
            "(id INTEGER PRIMARY KEY, marker TEXT NOT NULL)"
        )
        connection.execute(
            "INSERT INTO custody_probe(marker) VALUES (?)",
            ("synthetic-ephemeral-os-principal",),
        )
    count = read_conversation_count(db_path)
    if count < 1:
        raise AssertionError("G128_OWNER_SQLITE_READ_WRITE_NOT_CONFIRMED")
    # Verify direct native file access as an additional baseline.
    if len(db_path.read_bytes()) < 100:
        raise AssertionError("G128_OWNER_FILE_NOT_READABLE")
    print(f"G128_OWNER_NATIVE_SQLITE_READ_WRITE=ALLOWED rows={count}", flush=True)


def deny_expected(fn, marker: str, *, sqlite_case: bool = False) -> None:
    try:
        fn()
    except PermissionError:
        print(f"G128_APP_{marker}=OS_DENIED", flush=True)
        return
    except sqlite3.OperationalError as exc:
        msg = str(exc).lower()
        if sqlite_case and any(
            value in msg for value in (
                "unable to open", "permission", "readonly", "access is denied"
            )
        ):
            print(f"G128_APP_{marker}=OS_DENIED", flush=True)
            return
        raise AssertionError(
            f"G128_UNEXPECTED_SQLITE_FAILURE_{marker}: {type(exc).__name__}"
        ) from exc
    raise AssertionError(f"G128_APP_{marker}=BYPASS_SUCCEEDED_NOT_P0")


def sqlite_read(db_path: Path) -> None:
    # Actually open and query SQLite with its own VFS and a preexisting schema.
    count = read_conversation_count(db_path)
    raise AssertionError(f"G128_APP_SQLITE_READ_BYPASS={count}")


def sqlite_write(db_path: Path) -> None:
    # The guarded directory already contains a valid SQLite DB. Do not create
    # or modify any outside path. If unexpectedly permitted, fail the CI gate.
    connection = sqlite3.connect(str(db_path))
    try:
        connection.execute(
            "INSERT INTO custody_probe(marker) VALUES ('unexpected-app-write')"
        )
        connection.commit()
        raise AssertionError("G128_APP_SQLITE_WRITE_BYPASS_SUCCEEDED")
    finally:
        connection.close()


def app(db_path: Path, expected: str) -> None:
    must_be(expected)
    if not db_path.is_absolute():
        raise AssertionError("G128_REQUIRES_ABSOLUTE_DB_PATH")
    # This function must execute under an actual distinct OS account, confirmed
    # by must_be(), with each native file/SQLite path really exercised.
    deny_expected(lambda: db_path.read_bytes(), "RAW_READ")
    deny_expected(lambda: os.close(os.open(db_path, os.O_RDWR)), "RAW_WRITE")
    deny_expected(lambda: sqlite_read(db_path), "SQLITE_READ", sqlite_case=True)
    deny_expected(lambda: sqlite_write(db_path), "SQLITE_WRITE", sqlite_case=True)
    print("G128_SEPARATE_LOW_PRIVILEGE_OS_PRINCIPAL=PROVEN_ONLY", flush=True)


def main() -> int:
    if len(sys.argv) != 4:
        raise SystemExit("usage: g128_os_principal_probe_lab.py owner-init|owner-check|app <absolute-db> <principal>")
    action, path, expected = sys.argv[1:]
    db_path = Path(path).resolve(strict=False)
    if not db_path.is_absolute():
        raise AssertionError("G128_ABSOLUTE_DB_PATH_REQUIRED")
    if action == "owner-init":
        owner(db_path, expected, create=True)
    elif action == "owner-check":
        owner(db_path, expected, create=False)
    elif action == "app":
        app(db_path, expected)
    else:
        raise AssertionError("G128_UNKNOWN_ACTION")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
