"""P0 LAB: SQLite journal mode cannot silently change nonce claim guarantees.

Adversarial tests against the ACTUAL PersistentNonceRegistry. No production
owner, issuer, provider, worker or real side effects; temp SQLite only.
A valid local WAL DB remains vulnerable to full snapshot rollback (OPEN P0).
"""
from __future__ import annotations

from contextlib import closing
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

import atlasquant_aion_nonce_registry as nonce_mod
from atlasquant_aion_nonce_registry import PersistentNonceRegistry
import test_atlasquant_aion_v224_owner_signature_ceremony as owner

NOW="2026-10-20T19:00:00Z"
EXP="2026-10-20T20:00:00Z"


class NonceJournalModeAndMigrationLAB(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix="aion-p0-nonce-wal-lab-")
        self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/"registry.sqlite3"

    def new(self):
        return PersistentNonceRegistry(self.path)

    def claim(self,registry,nonce):
        return registry.claim(scope="owner.lab",nonce=nonce,
                              now_ts=NOW,expires_at=EXP)

    def mode(self):
        with closing(sqlite3.connect(self.path)) as c:
            return str(c.execute("PRAGMA journal_mode").fetchone()[0]).lower()

    def switch(self,mode):
        with closing(sqlite3.connect(self.path)) as c:
            return str(c.execute("PRAGMA journal_mode="+mode).fetchone()[0]).lower()

    def old_v1(self):
        with closing(sqlite3.connect(self.path)) as c:
            with c:
                c.execute(
                    "CREATE TABLE nonce_claims (scope TEXT NOT NULL,"
                    "nonce TEXT NOT NULL, expires_at TEXT NOT NULL,"
                    "created_at TEXT NOT NULL, PRIMARY KEY(scope,nonce))"
                )
                c.execute(
                    "INSERT INTO nonce_claims(scope,nonce,expires_at,created_at)"
                    " VALUES(?,?,?,?)",("owner.lab","already-used",EXP,NOW)
                )
                c.execute(
                    "CREATE TABLE nonce_registry_meta (singleton INTEGER PRIMARY KEY"
                    " CHECK(singleton=1),schema_version INTEGER NOT NULL)"
                )
                c.execute(
                    "INSERT INTO nonce_registry_meta VALUES(1,1)"
                )

    def test_01_fresh_registry_is_initialized_in_wal_and_full_sync(self):
        r=self.new()
        self.assertEqual(self.mode(),"wal")
        with r._connect() as db:
            self.assertEqual(str(db.execute("PRAGMA journal_mode").fetchone()[0]),"wal")
            self.assertEqual(int(db.execute("PRAGMA synchronous").fetchone()[0]),2)
        self.assertTrue(self.claim(r,"initial"))
        self.assertEqual(r.count(),1)

    def test_02_external_switch_to_delete_denies_new_nonce(self):
        r=self.new()
        self.assertTrue(self.claim(r,"prior"))
        self.assertEqual(self.switch("DELETE"),"delete")
        with self.assertRaisesRegex((RuntimeError,sqlite3.Error),"WAL|wal|journal"):
            self.claim(r,"forbidden-under-delete")
        self.assertFalse(any(row[0]=="forbidden-under-delete" for row in self.rows()))
        self.assertEqual(self.mode(),"delete")

    def test_03_owner_signature_denied_when_journal_downgraded(self):
        r=self.new()
        self.assertEqual(self.switch("DELETE"),"delete")
        key,roots=owner.owner_keypair()
        ev,built=owner.request_for(roots)
        result=owner.verify(built["request"],owner.sign(key,built["request"]),
                            roots,r,e=ev)
        self.assertEqual(result["state"],"BLOCKED")
        self.assertIn("OWNER_SIGNATURE_NONCE_REGISTRY_FAILURE",result["blockers"])
        self.assertFalse(result["owner_decision_ready"])
        self.assertFalse(result["worker_armed"])
        self.assertFalse(result["execution_allowed"])
        self.assertEqual(self.rows(),[])

    def rows(self):
        with closing(sqlite3.connect(self.path)) as c:
            return c.execute("SELECT nonce FROM nonce_claims").fetchall()

    def test_04_contains_denies_read_after_journal_downgrade(self):
        r=self.new()
        self.assertTrue(self.claim(r,"prior"))
        self.assertEqual(self.switch("DELETE"),"delete")
        with self.assertRaisesRegex((RuntimeError,sqlite3.Error),"WAL|wal|journal"):
            r.contains(scope="owner.lab",nonce="prior")

    def test_05_read_claim_denies_after_journal_downgrade(self):
        r=self.new()
        self.assertTrue(self.claim(r,"prior"))
        self.assertEqual(self.switch("TRUNCATE"),"truncate")
        with self.assertRaisesRegex((RuntimeError,sqlite3.Error),"WAL|wal|journal"):
            r.read_claim(scope="owner.lab",nonce="prior")

    def test_06_count_denies_after_journal_downgrade(self):
        r=self.new()
        self.assertEqual(self.switch("DELETE"),"delete")
        with self.assertRaisesRegex((RuntimeError,sqlite3.Error),"WAL|wal|journal"):
            r.count()

    def test_07_schema_version_denies_after_journal_downgrade(self):
        r=self.new()
        self.assertEqual(self.switch("DELETE"),"delete")
        with self.assertRaisesRegex((RuntimeError,sqlite3.Error),"WAL|wal|journal"):
            r.schema_version()

    def test_08_existing_valid_v2_delete_db_can_be_repaired_by_reopen(self):
        r=self.new()
        self.assertTrue(self.claim(r,"prior"))
        self.assertEqual(self.switch("DELETE"),"delete")
        reopened=self.new()
        self.assertEqual(self.mode(),"wal")
        self.assertEqual(reopened.count(),1)
        self.assertFalse(self.claim(reopened,"prior"))

    def test_09_same_db_valid_v1_migrates_and_keeps_consumed_nonce(self):
        self.old_v1()
        self.assertEqual(self.mode(),"delete")
        r=self.new()
        self.assertEqual(self.mode(),"wal")
        self.assertEqual(r.schema_version(),2)
        self.assertFalse(self.claim(r,"already-used"))
        self.assertEqual(r.count(),1)

    def test_10_failed_wal_transition_must_not_commit_v1_migration(self):
        self.old_v1()
        real_connect=sqlite3.connect
        class FailWAL(sqlite3.Connection):
            def execute(self, sql, parameters=()):
                if str(sql).strip().upper()=="PRAGMA JOURNAL_MODE=WAL":
                    raise sqlite3.OperationalError("SIMULATED_WAL_TRANSITION_DENIED")
                return super().execute(sql,parameters)
        def make(*args,**kwargs):
            return real_connect(*args,**kwargs,factory=FailWAL)
        with patch.object(nonce_mod.sqlite3,"connect",side_effect=make):
            with self.assertRaisesRegex(sqlite3.OperationalError,"SIMULATED_WAL_TRANSITION_DENIED"):
                self.new()
        with closing(real_connect(self.path)) as db:
            self.assertEqual(db.execute(
                "SELECT schema_version FROM nonce_registry_meta WHERE singleton=1"
            ).fetchone(),(1,))
            self.assertFalse(any(
                row[1]=="expires_at_us"
                for row in db.execute("PRAGMA table_info(nonce_claims)").fetchall()
            ))
            self.assertEqual(db.execute(
                "SELECT nonce FROM nonce_claims"
            ).fetchall(),[("already-used",)])
        self.assertEqual(self.mode(),"delete")

    def test_11_failed_wal_transition_must_not_create_new_schema(self):
        real_connect=sqlite3.connect
        class FailWAL(sqlite3.Connection):
            def execute(self,sql,parameters=()):
                if str(sql).strip().upper()=="PRAGMA JOURNAL_MODE=WAL":
                    raise sqlite3.OperationalError("SIMULATED_WAL_TRANSITION_DENIED")
                return super().execute(sql,parameters)
        def make(*args,**kwargs):
            return real_connect(*args,**kwargs,factory=FailWAL)
        with patch.object(nonce_mod.sqlite3,"connect",side_effect=make):
            with self.assertRaisesRegex(sqlite3.OperationalError,"SIMULATED_WAL_TRANSITION_DENIED"):
                self.new()
        with closing(real_connect(self.path)) as db:
            self.assertEqual(db.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall(),[])
        # A file may exist after the failed connect; it cannot be silently
        # enrolled on next startup without independent owner approval.
        with self.assertRaises(ValueError):
            self.new()

    def test_12_parallel_claims_after_downgrade_all_fail_no_insert(self):
        r=self.new()
        self.assertEqual(self.switch("DELETE"),"delete")
        def attempt(i):
            try:
                self.claim(r,f"downgraded-{i}")
                return "UNSAFE_TRUE"
            except (RuntimeError,sqlite3.Error):
                return "DENIED"
        with ThreadPoolExecutor(max_workers=8) as pool:
            outcomes=list(pool.map(attempt,range(8)))
        self.assertEqual(outcomes,["DENIED"]*8)
        self.assertEqual(self.rows(),[])
        self.assertEqual(self.mode(),"delete")


if __name__=="__main__":
    unittest.main()
