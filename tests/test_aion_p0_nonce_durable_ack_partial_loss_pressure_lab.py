"""AION P0: SQLite durable-ack and partial-loss adversarial characterizations.

The real registry MUST NEVER return True unless a consumed nonce exists
after its transaction, and MUST NOT silently bootstrap damaged existing DBs.
All assets are TEMP synthetic SQLite. A GREEN H0 partial-loss case does NOT
prove full DB rollback detection or independent owner/issuer authority.
"""
from __future__ import annotations

from contextlib import closing, contextmanager
from pathlib import Path
from unittest.mock import patch
import sqlite3
import tempfile
import unittest

from atlasquant_aion_nonce_registry import PersistentNonceRegistry
import test_atlasquant_aion_v224_owner_signature_ceremony as v224

NOW="2026-10-20T15:00:00Z"
END="2026-10-20T15:05:00Z"


class NonceDurableAckAndPartialLossLAB(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix="aion-nonce-durable-ack-")
        self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name)
        self.db=self.base/"nonce.sqlite3"
        self.registry=PersistentNonceRegistry(self.db)

    def claim(self,nonce="DEMO-nonce",*,scope="synthetic-owner"):
        return self.registry.claim(
            scope=scope,nonce=nonce,now_ts=NOW,expires_at=END
        )

    def sql(self,statement):
        with closing(sqlite3.connect(self.db)) as c:
            with c:
                c.execute(statement)

    def count_raw(self):
        with closing(sqlite3.connect(self.db)) as c:
            return int(c.execute("SELECT COUNT(*) FROM nonce_claims").fetchone()[0])

    def trigger_ignore(self):
        self.sql(
            "CREATE TRIGGER silently_ignore_claim BEFORE INSERT ON nonce_claims "
            "BEGIN SELECT RAISE(IGNORE); END"
        )

    def trigger_delete(self):
        self.sql(
            "CREATE TRIGGER silently_delete_claim AFTER INSERT ON nonce_claims "
            "BEGIN DELETE FROM nonce_claims WHERE scope=NEW.scope AND nonce=NEW.nonce; END"
        )

    def drop_both(self,*,sentinel=False):
        with closing(sqlite3.connect(self.db)) as c:
            with c:
                if sentinel:
                    c.execute("CREATE TABLE audit_sentinel (entry TEXT NOT NULL)")
                    c.execute("INSERT INTO audit_sentinel(entry) VALUES('do not erase')")
                c.execute("DROP TABLE nonce_claims")
                c.execute("DROP TABLE nonce_registry_meta")

    def test_01_nominal_claim_ack_matches_readback(self):
        self.assertTrue(self.claim())
        self.assertTrue(self.registry.contains(scope="synthetic-owner",nonce="DEMO-nonce"))
        self.assertEqual(self.count_raw(),1)
        self.assertFalse(self.claim())

    def test_02_before_insert_ignore_cannot_produce_false_durable_ack(self):
        self.trigger_ignore()
        with self.assertRaisesRegex((RuntimeError,sqlite3.Error),"not durably written|not durable after commit|write|unauthorized trigger"):
            self.claim("never-written")
        self.assertEqual(self.count_raw(),0)

    def test_03_after_insert_delete_cannot_produce_false_durable_ack(self):
        self.trigger_delete()
        with self.assertRaisesRegex((RuntimeError,sqlite3.Error),"not durably written|not durable after commit|write|unauthorized trigger"):
            self.claim("deleted-in-the-same-transaction")
        self.assertEqual(self.count_raw(),0)

    def test_04_ignored_write_cannot_claim_success_twice(self):
        self.trigger_ignore()
        for _ in range(2):
            with self.assertRaises((RuntimeError,sqlite3.Error)):
                self.claim("attempted-twice")
        self.assertEqual(self.count_raw(),0)

    def test_05_post_insert_delete_cannot_claim_success_twice(self):
        self.trigger_delete()
        for _ in range(2):
            with self.assertRaises((RuntimeError,sqlite3.Error)):
                self.claim("attempted-twice")
        self.assertEqual(self.count_raw(),0)

    def test_06_owner_v224_cannot_be_ready_when_nonce_was_not_durable(self):
        self.trigger_ignore()
        key,roots=v224.owner_keypair()
        evidence,built=v224.request_for(roots)
        self.assertEqual(built["state"],"READY_FOR_EXTERNAL_OWNER_SIGNATURE")
        result=v224.verify(
            built["request"],v224.sign(key,built["request"]),
            roots,self.registry,e=evidence,
        )
        self.assertEqual(result["state"],"BLOCKED")
        self.assertIn("OWNER_SIGNATURE_NONCE_REGISTRY_FAILURE",result["blockers"])
        self.assertFalse(result["owner_decision_ready"])
        self.assertFalse(result["worker_armed"])
        self.assertFalse(result["execution_allowed"])
        self.assertEqual(self.count_raw(),0)

    def test_07_existing_db_both_registry_tables_lost_denied(self):
        self.assertTrue(self.claim("prior-consumed"))
        self.drop_both(sentinel=True)
        with self.assertRaises(ValueError):
            PersistentNonceRegistry(self.db)
        with closing(sqlite3.connect(self.db)) as c:
            names={r[0] for r in c.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()}
            self.assertNotIn("nonce_claims",names)
            self.assertNotIn("nonce_registry_meta",names)
            self.assertEqual(c.execute(
                "SELECT entry FROM audit_sentinel"
            ).fetchone(),("do not erase",))

    def test_08_existing_db_empty_after_both_table_deletions_denied(self):
        self.assertTrue(self.claim("prior-consumed"))
        self.drop_both()
        with self.assertRaises(ValueError):
            PersistentNonceRegistry(self.db)
        with closing(sqlite3.connect(self.db)) as c:
            self.assertEqual(c.execute(
                "SELECT count(*) FROM sqlite_master WHERE type='table'"
            ).fetchone()[0],0)

    def test_09_existing_empty_zero_byte_file_is_not_new_enrollment(self):
        untouched=self.base/"zero-file.sqlite3"
        untouched.touch(exist_ok=False)
        with self.assertRaises(ValueError):
            PersistentNonceRegistry(untouched)
        with closing(sqlite3.connect(untouched)) as c:
            self.assertEqual(c.execute(
                "SELECT count(*) FROM sqlite_master WHERE type='table'"
            ).fetchone()[0],0)

    def test_10_truly_missing_path_bootstraps_for_lab_only(self):
        path=self.base/"fresh-path.sqlite3"
        self.assertFalse(path.exists())
        first=PersistentNonceRegistry(path)
        self.assertEqual(first.count(),0)
        self.assertTrue(path.exists())
        self.assertTrue(first.claim(
            scope="synthetic-owner",nonce="legitimate",
            now_ts=NOW,expires_at=END,
        ))

    def test_11_nonunique_storage_integrity_error_does_not_look_like_replay(self):
        self.sql(
            "CREATE TRIGGER synthetic_abort BEFORE INSERT ON nonce_claims "
            "BEGIN SELECT RAISE(ABORT,'SIMULATED_DISK_IO_WRITE_ERROR'); END"
        )
        # The new fail-closed schema gate may reject the trigger before
        # its synthetic IntegrityError executes. Both paths must deny.
        with self.assertRaises((sqlite3.IntegrityError,RuntimeError)):
            self.claim("not-duplicate")
        self.assertEqual(self.count_raw(),0)

    def test_12_disk_full_db_page_budget_preserves_original_sqlite_full(self):
        original=self.registry._connect
        @contextmanager
        def capped_pages():
            with original() as c:
                pages=int(c.execute("PRAGMA page_count").fetchone()[0])
                max_pages=int(c.execute(
                    "PRAGMA max_page_count="+str(pages)
                ).fetchone()[0])
                self.assertEqual(max_pages,pages)
                yield c
        with patch.object(self.registry,"_connect",capped_pages):
            exception=None
            for n in range(160):
                try:
                    self.claim("b"+str(n)+"X"*245)
                except sqlite3.OperationalError as exc:
                    exception=exc
                    break
            self.assertIsNotNone(exception,"Synthetic SQLite page limit did not fill")
            self.assertEqual(
                getattr(exception,"sqlite_errorcode",None),sqlite3.SQLITE_FULL,
                "Original SQLITE_FULL code must not be replaced by rollback error",
            )
        # The failed transaction must not have been accepted as a fresh nonce.
        self.assertFalse(self.registry.contains(
            scope="synthetic-owner",nonce="b"+str(n)+"X"*245
        ))

    def test_13_reader_does_not_authorize_replay_after_expired_tombstones(self):
        self.assertTrue(self.claim("keep-this"))
        # Disk pressure alone cannot purge a claim.
        with closing(sqlite3.connect(self.db)) as reader:
            reader.execute("BEGIN")
            self.assertEqual(reader.execute(
                "SELECT COUNT(*) FROM nonce_claims"
            ).fetchone()[0],1)
            for n in range(32):
                self.assertTrue(self.claim(f"record-{n}"))
            self.assertTrue(self.registry.contains(
                scope="synthetic-owner",nonce="keep-this",
            ))
        self.assertFalse(self.claim("keep-this"))

    def test_14_sqlite_wal_and_db_bytes_are_reported_without_claiming_cap(self):
        for n in range(64):
            self.assertTrue(self.claim("latin-"+str(n)+"z"*200))
        sizes={extension: (self.db.with_name(self.db.name+extension).stat().st_size
                            if self.db.with_name(self.db.name+extension).exists() else 0)
               for extension in ("","-wal","-shm")}
        self.assertGreater(sizes[""],0)
        self.assertGreater(self.registry.count(),0)
        # MAX_NONCE_CLAIMS is a row cap and provides NO physical byte bound.
        self.assertGreaterEqual(sum(sizes.values()),sizes[""])
        self.assertFalse(hasattr(self.registry,"independent_highwater_witness"))

    def test_15_corrupted_db_bytes_do_not_turn_into_bootstrap(self):
        self.assertTrue(self.claim("original"))
        self.db.write_bytes(b"NOT-A-SQLITE-HEADER" + b"\xff"*100)
        with self.assertRaises(sqlite3.DatabaseError):
            PersistentNonceRegistry(self.db)
        self.assertEqual(self.db.read_bytes()[:19],b"NOT-A-SQLITE-HEADER")

    def test_16_missing_registry_file_still_cannot_prove_independent_H0(self):
        # Known OPEN boundary, never interpret local DB re-creation as owner
        # authentication or proof of no external effect.
        self.assertFalse(hasattr(self.registry,"enroll_external_issuer"))
        self.assertFalse(hasattr(self.registry,"independent_antirollback"))
        self.assertFalse(hasattr(self.registry,"authorize_external_dispatch"))


    def test_17_report_real_ascii_vs_unicode_sqlite_bytes(self):
        measurements={}
        for kind in ("ascii","utf8"):
            other=self.base/f"{kind}.sqlite3"
            reg=PersistentNonceRegistry(other)
            for n in range(80):
                prefix="a"*120 if kind=="ascii" else "🐢"*120
                self.assertTrue(reg.claim(
                    scope="synthetic-owner",nonce=f"{kind}-{n:03d}-{prefix}",
                    now_ts=NOW,expires_at=END,
                ))
            self.assertEqual(reg.count(),80)
            measurements[kind]=other.stat().st_size
            self.assertGreater(measurements[kind],0)
        # Same number of logical claims can require dramatically different
        # physical file sizes; MAX_NONCE_CLAIMS is NOT a byte budget.
        self.assertGreater(measurements["utf8"],measurements["ascii"])
        print("AION_LAB_NONCE_DB_BYTES "+str(measurements),flush=True)

    def test_18_pinned_reader_wal_growth_is_observed_not_pruned(self):
        self.assertTrue(self.claim("before-reader"))
        with closing(sqlite3.connect(self.db)) as reader:
            reader.execute("BEGIN")
            self.assertEqual(reader.execute(
                "SELECT COUNT(*) FROM nonce_claims"
            ).fetchone()[0],1)
            for n in range(96):
                self.assertTrue(self.claim(f"wal-pressure-{n:03d}-"+("Z"*175)))
            wal=self.db.with_name(self.db.name+"-wal")
            self.assertTrue(wal.exists())
            wal_bytes=wal.stat().st_size
            self.assertGreater(wal_bytes,0)
            print("AION_LAB_NONCE_WAL_BYTES_PINNED_READER "+str(wal_bytes),flush=True)
            self.assertEqual(self.registry.count(),97)
        self.assertFalse(self.claim("before-reader"))


if __name__ == "__main__":
    unittest.main()
