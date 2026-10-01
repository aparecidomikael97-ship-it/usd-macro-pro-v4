"""Offline PostgreSQL DB-API contract tests via sqlite simulation.

No live PostgreSQL, credentials or customer data used. These prove the Python
contract and SQL compatibility in a test double, NOT distributed deployment.
"""
import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing, contextmanager
from pathlib import Path

from aion_core.library_authorization import AuthorizationDenied
from aion_core.library_shared_approval_port import SharedApprovalBurnPort, MIGRATION_POSTGRESQL

SHA = "a" * 64

@contextmanager
def dbconn(path):
    with closing(sqlite3.connect(path)) as con:
        with con:
            yield con



class SQLiteCursorAdapter:
    def __init__(self, cursor):
        self._cursor = cursor

    def execute(self, sql, params):
        self._cursor.execute(sql.replace("%s", "?"), params)

    def fetchone(self):
        return self._cursor.fetchone()

    def close(self):
        self._cursor.close()


class SQLiteConnectionAdapter:
    # Simulate PostgreSQL's explicit transaction configuration.
    autocommit = False

    def __init__(self, path):
        self._db = sqlite3.connect(path, timeout=10, isolation_level="DEFERRED")

    def cursor(self):
        return SQLiteCursorAdapter(self._db.cursor())

    def commit(self):
        self._db.commit()

    def rollback(self):
        self._db.rollback()

    def close(self):
        self._db.close()


class SharedPortTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = str(Path(self.tmp.name) / "synthetic.sqlite3")
        with dbconn(self.path) as con:
            con.execute("""CREATE TABLE aion_library_approval_burns (
                approval_key TEXT PRIMARY KEY, binding_sha256 TEXT NOT NULL,
                burned_at_unix INTEGER NOT NULL)""")
        self.connect = lambda: SQLiteConnectionAdapter(self.path)
        self.port = SharedApprovalBurnPort(connect=self.connect, clock=lambda: 123)

    def burn(self, **kwargs):
        values = dict(issuer="approval-issuer", approval_id="nonce-1", binding_sha256=SHA)
        values.update(kwargs)
        return self.port.burn(**values)

    def test_migration_is_explicit_and_restricted(self):
        self.assertIn("CREATE TABLE aion_library_approval_burns", MIGRATION_POSTGRESQL)
        self.assertIn("PRIMARY KEY", MIGRATION_POSTGRESQL)
        self.assertNotIn("DROP TABLE", MIGRATION_POSTGRESQL)
        self.assertNotIn("GRANT ALL", MIGRATION_POSTGRESQL)

    def test_burn_returns_sha256_digest(self):
        result = self.burn()
        self.assertRegex(result, r"^[a-f0-9]{64}$")

    def test_raw_issuer_and_nonce_are_not_stored(self):
        self.burn()
        with dbconn(self.path) as con:
            rows = con.execute("SELECT * FROM aion_library_approval_burns").fetchall()
        self.assertEqual(len(rows), 1)
        self.assertNotIn("nonce-1", repr(rows))
        self.assertNotIn("approval-issuer", repr(rows))

    def test_prevent_duplicate_id(self):
        self.burn()
        with self.assertRaises(AuthorizationDenied): self.burn()

    def test_prevent_duplicate_even_if_binding_changed(self):
        self.burn()
        with self.assertRaises(AuthorizationDenied): self.burn(binding_sha256="b" * 64)

    def test_independent_instances_use_shared_storage(self):
        self.burn()
        other = SharedApprovalBurnPort(connect=self.connect, clock=lambda: 1000)
        with self.assertRaises(AuthorizationDenied):
            other.burn(issuer="approval-issuer", approval_id="nonce-1", binding_sha256=SHA)

    def test_other_issuer_can_use_same_nonce(self):
        self.burn()
        self.burn(issuer="second-issuer")
        with dbconn(self.path) as con:
            self.assertEqual(con.execute("SELECT count(*) FROM aion_library_approval_burns").fetchone(), (2,))

    def test_other_nonce_can_be_used(self):
        self.burn()
        self.burn(approval_id="nonce-2")

    def test_concurrent_duplicate_only_one_commits(self):
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(lambda _: self._try_burn(), range(8)))
        self.assertEqual(results.count("ok"), 1, results)
        self.assertEqual(results.count("denied"), 7, results)

    def _try_burn(self):
        try:
            self.burn()
        except AuthorizationDenied:
            return "denied"
        return "ok"

    def test_empty_issuer_rejected(self):
        with self.assertRaises(AuthorizationDenied): self.burn(issuer="")

    def test_invalid_issuer_rejected(self):
        with self.assertRaises(AuthorizationDenied): self.burn(issuer="issuer; DROP TABLE x")

    def test_long_issuer_rejected(self):
        with self.assertRaises(AuthorizationDenied): self.burn(issuer="a" * 129)

    def test_invalid_nonce_rejected(self):
        with self.assertRaises(AuthorizationDenied): self.burn(approval_id="a\nb")

    def test_empty_nonce_rejected(self):
        with self.assertRaises(AuthorizationDenied): self.burn(approval_id="")

    def test_invalid_binding_rejected(self):
        with self.assertRaises(AuthorizationDenied): self.burn(binding_sha256="a" * 63)

    def test_uppercase_binding_rejected(self):
        with self.assertRaises(AuthorizationDenied): self.burn(binding_sha256="A" * 64)

    def test_none_fields_rejected(self):
        for args in ({"issuer": None}, {"approval_id": None}, {"binding_sha256": None}):
            with self.subTest(args=args), self.assertRaises(AuthorizationDenied): self.burn(**args)

    def test_bool_clock_rejected(self):
        port = SharedApprovalBurnPort(connect=self.connect, clock=lambda: True)
        with self.assertRaises(AuthorizationDenied): port.burn(issuer="i", approval_id="n", binding_sha256=SHA)

    def test_negative_clock_rejected(self):
        port = SharedApprovalBurnPort(connect=self.connect, clock=lambda: -1)
        with self.assertRaises(AuthorizationDenied): port.burn(issuer="i", approval_id="n", binding_sha256=SHA)

    def test_missing_factory_rejected(self):
        with self.assertRaises(AuthorizationDenied): SharedApprovalBurnPort(connect=None)

    def test_bad_clock_factory_rejected(self):
        with self.assertRaises(AuthorizationDenied): SharedApprovalBurnPort(connect=self.connect, clock="now")

    def test_missing_database_denied(self):
        Path(self.path).unlink()
        with self.assertRaises(AuthorizationDenied): self.burn()

    def test_schema_missing_denied(self):
        with dbconn(self.path) as con:
            con.execute("DROP TABLE aion_library_approval_burns")
        with self.assertRaises(AuthorizationDenied): self.burn()

    def test_factory_failure_denied(self):
        def fail(): raise ConnectionError("private hostname and credentials")
        port = SharedApprovalBurnPort(connect=fail)
        with self.assertRaises(AuthorizationDenied) as ctx:
            port.burn(issuer="i", approval_id="n", binding_sha256=SHA)
        self.assertNotIn("hostname", str(ctx.exception))
        self.assertNotIn("credentials", str(ctx.exception))

    def test_autocommit_rejected_before_insert(self):
        class AutoCommit(SQLiteConnectionAdapter):
            autocommit = True
        port = SharedApprovalBurnPort(connect=lambda: AutoCommit(self.path))
        with self.assertRaises(AuthorizationDenied):
            port.burn(issuer="i", approval_id="n", binding_sha256=SHA)
        with dbconn(self.path) as con:
            self.assertEqual(con.execute("SELECT count(*) FROM aion_library_approval_burns").fetchone(), (0,))

    def test_missing_autocommit_property_denied(self):
        class Unknown:
            def close(self): pass
        port = SharedApprovalBurnPort(connect=Unknown)
        with self.assertRaises(AuthorizationDenied):
            port.burn(issuer="i", approval_id="n", binding_sha256=SHA)

    def test_closed_database_denied(self):
        class Closed(SQLiteConnectionAdapter):
            def __init__(self, path):
                super().__init__(path); self._db.close()
        port = SharedApprovalBurnPort(connect=lambda: Closed(self.path))
        with self.assertRaises(AuthorizationDenied):
            port.burn(issuer="i", approval_id="n", binding_sha256=SHA)

    def test_unique_index_required_if_schema_unsafe(self):
        with dbconn(self.path) as con:
            con.execute("DROP TABLE aion_library_approval_burns")
            con.execute("CREATE TABLE aion_library_approval_burns (approval_key TEXT, binding_sha256 TEXT, burned_at_unix INTEGER)")
        # ON CONFLICT specifies unique key; without index the DB rejects, fail closed.
        with self.assertRaises(AuthorizationDenied): self.burn()


if __name__ == "__main__":
    unittest.main()