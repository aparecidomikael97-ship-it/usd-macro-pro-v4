"""A185 LAB-only stdlib SQLite cached execution and second-connection bypass.

Demonstrates progress_handler on an actual Python sqlite3.Connection without
claiming native VFS, external epoch, Windows ABA, or AION integration.
"""
import sqlite3
import tempfile
from pathlib import Path


def prove() -> None:
    with tempfile.TemporaryDirectory(prefix="a185-python-epoch-") as root:
        path = Path(root) / "test.sqlite"
        guarded = sqlite3.connect(path, timeout=3)
        try:
            mode = guarded.execute("PRAGMA journal_mode=WAL").fetchone()[0].lower()
            assert mode == "wal", mode
            guarded.execute("CREATE TABLE records (id INTEGER PRIMARY KEY, payload TEXT)")
            guarded.execute("INSERT INTO records VALUES (1, 'before')")
            guarded.commit()
            assert guarded.execute("SELECT payload FROM records WHERE id=1").fetchone() == ("before",)

            epoch = {"captured": 1, "authority": 1, "hits": 0}

            def guard() -> int:
                epoch["hits"] += 1
                return int(epoch["captured"] != epoch["authority"])

            guarded.set_progress_handler(guard, 1)
            assert guarded.execute("SELECT payload FROM records WHERE id=1").fetchone() == ("before",)
            epoch["authority"] = 2
            denied = False
            try:
                guarded.execute("SELECT payload FROM records WHERE id=1").fetchone()
            except sqlite3.OperationalError as exc:
                denied = "interrupt" in str(exc).lower()
            assert denied, "prepared/cached SELECT survived denied progress hook"
            assert epoch["hits"] > 0
            print(f"PYTHON_CACHE_REVOKED=DENIED VMCALLS={epoch['hits']}")

            # The raw second connection has no callback/epoch guard: negative control.
            bypass = sqlite3.connect(path, timeout=3)
            try:
                bypass.execute("UPDATE records SET payload='written_by_bypass' WHERE id=1")
                bypass.commit()
            finally:
                bypass.close()
            print("PYTHON_SECOND_CONNECTION_UNGUARDED_WRITE=SUCCEEDED")

            epoch["authority"] = 1
            restored = guarded.execute("SELECT payload FROM records WHERE id=1").fetchone()
            assert restored == ("written_by_bypass",), restored
            print("PYTHON_SECOND_CONNECTION_VALUE=written_by_bypass")
        finally:
            guarded.close()
    print("RESULT=PASS_EXPECTED_NEGATIVE_CONTROLS SECURITY_STATUS=NOT_HOMOLOGATED")


if __name__ == "__main__":
    print(f"PYTHON_SQLITE_VERSION={sqlite3.sqlite_version}")
    prove()
