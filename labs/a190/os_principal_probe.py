"""A190 G1 LAB: OS-principal probe for a synthetic SQLite file.

Only evaluates OS access separation between two real, lower-privilege accounts.
Never claims protection against the host administrator, the OS, rollback,
WAL/SHM replacement or any external AION effect.
"""
from contextlib import closing
import os
from pathlib import Path
import sqlite3
import subprocess
import sys


def identity():
    if os.name == "nt":
        proc = subprocess.run(["whoami", "/user"], capture_output=True, text=True, check=True)
        return proc.stdout.strip().replace("\n", " | ")
    return "euid=" + str(os.geteuid())


def init_owner(database):
    database.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(database, timeout=5)) as db:
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("CREATE TABLE IF NOT EXISTS a190_probe (id INTEGER PRIMARY KEY, value TEXT)")
        db.execute("INSERT INTO a190_probe(value) VALUES ('owner-first')")
        db.commit()
    with closing(sqlite3.connect(database, timeout=5)) as db:
        assert db.execute("SELECT count(*) FROM a190_probe").fetchone()[0] == 1
        db.execute("INSERT INTO a190_probe(value) VALUES ('owner-second')")
        db.commit()
        assert db.execute("SELECT count(*) FROM a190_probe").fetchone()[0] == 2
    print("A190_G1_LEGITIMATE_OWNER_SQLITE_READ_WRITE=SUCCESS " + identity())


def attack(database):
    assert database.is_absolute(), "must use an absolute synthetic path"
    results = []

    def attempt(name, action):
        try:
            action()
        except (OSError, sqlite3.Error) as exc:
            print("A190_G1_" + name + "=OS_DENIED error=" + type(exc).__name__)
            results.append(True)
            return
        raise AssertionError("A190_G1_" + name + "=UNSAFE_ACCESS_GRANTED")

    def raw_read():
        with database.open("rb") as f:
            f.read(1)

    def sql_read():
        with closing(sqlite3.connect(database.as_uri() + "?mode=ro", uri=True, timeout=2)) as db:
            db.execute("SELECT count(*) FROM a190_probe").fetchone()

    def sql_write():
        with closing(sqlite3.connect(database.as_uri() + "?mode=rw", uri=True, timeout=2)) as db:
            db.execute("INSERT INTO a190_probe(value) VALUES ('ATTACKER')")
            db.commit()

    attempt("RAW_READ", raw_read)
    attempt("SQL_SELECT", sql_read)
    attempt("SQL_INSERT", sql_write)
    attempt("DB_RENAME", lambda: os.replace(database, database.with_suffix(".moved")))
    assert len(results) == 4
    print("A190_G1_DISTINCT_PRINCIPAL_DENIALS=4_OF_4 " + identity())
    print("A190_G1_WAL_SHM_SAME_INODE_ADMIN_ROOT=NOT_EXERCISED_OR_NOT_ATTESTED")


def main():
    if len(sys.argv) != 3 or sys.argv[1] not in {"init", "attack"}:
        raise SystemExit("Usage: python -m labs.a190.os_principal_probe init|attack ABSOLUTE_SYNTHETIC_DB")
    database = Path(sys.argv[2])
    if not database.is_absolute():
        raise SystemExit("A190_ABSOLUTE_PATH_REQUIRED")
    if sys.argv[1] == "init":
        init_owner(database)
    else:
        attack(database)


if __name__ == "__main__":
    main()
