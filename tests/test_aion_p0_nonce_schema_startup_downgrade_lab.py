"""P0 LAB: real nonce registry startup must not silently rewrite schema epoch.

RED before patch: _initialize overwrites incompatible/future schema_version,
recreates missing claims/meta tables, and can upgrade a malformed current DB.
Uses ONLY disposable SQLite fixtures. No real owner, issuer, producer or send.
"""
from __future__ import annotations

from contextlib import closing
from pathlib import Path
import sqlite3
import tempfile
import unittest

from atlasquant_aion_nonce_registry import PersistentNonceRegistry, SCHEMA_VERSION

NOW="2026-10-20T20:00:00Z"
EXP="2026-10-20T20:02:00Z"


class NonceRegistryStartupCompatibilityLAB(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix="aion-nonce-schema-lab-")
        self.addCleanup(self.tmp.cleanup)
        self.db=Path(self.tmp.name)/"nonce.sqlite3"

    def create_tables(self, *, schema_version=2, meta=True, claims=True,
                      expiry_column=True, blank_meta=False):
        with closing(sqlite3.connect(self.db)) as conn:
            if claims:
                conn.execute(
                    "CREATE TABLE nonce_claims (scope TEXT NOT NULL,"
                    "nonce TEXT NOT NULL, expires_at TEXT NOT NULL,"
                    + ("expires_at_us INTEGER," if expiry_column else "")
                    + "created_at TEXT NOT NULL,PRIMARY KEY(scope,nonce))"
                )
                if expiry_column:
                    conn.execute(
                        "INSERT INTO nonce_claims(scope,nonce,expires_at,expires_at_us,created_at)"
                        "VALUES ('owner','prior-nonce','2026-10-20T21:00:00Z',"
                        "1792530000000000,'2026-10-20T19:00:00Z')"
                    )
                else:
                    conn.execute(
                        "INSERT INTO nonce_claims(scope,nonce,expires_at,created_at)"
                        "VALUES ('owner','prior-nonce','2026-10-20T21:00:00Z',"
                        "'2026-10-20T19:00:00Z')"
                    )
            if meta:
                conn.execute(
                    "CREATE TABLE nonce_registry_meta (singleton INTEGER PRIMARY KEY "
                    "CHECK(singleton=1),schema_version INTEGER NOT NULL)"
                )
                if not blank_meta:
                    conn.execute(
                        "INSERT INTO nonce_registry_meta(singleton,schema_version) VALUES(1,?)",
                        (schema_version,),
                    )
            conn.commit()

    def raw_version(self):
        with closing(sqlite3.connect(self.db)) as db:
            return db.execute(
                "SELECT schema_version FROM nonce_registry_meta WHERE singleton=1"
            ).fetchone()

    def raw_claim_count(self):
        with closing(sqlite3.connect(self.db)) as db:
            return db.execute("SELECT count(*) FROM nonce_claims").fetchone()[0]

    def test_01_fresh_empty_file_bootstraps_at_current_version(self):
        r=PersistentNonceRegistry(self.db)
        self.assertEqual(r.schema_version(), SCHEMA_VERSION)
        self.assertEqual(r.count(),0)

    def test_02_current_version_existing_nonce_remains_consumed(self):
        r=PersistentNonceRegistry(self.db)
        self.assertTrue(r.claim(scope="owner",nonce="prior-nonce",
                                expires_at=EXP,now_ts=NOW))
        r2=PersistentNonceRegistry(self.db)
        self.assertFalse(r2.claim(scope="owner",nonce="prior-nonce",
                                  expires_at=EXP,now_ts=NOW))
        self.assertEqual(r2.schema_version(),SCHEMA_VERSION)

    def test_03_future_schema_version_does_not_get_downgraded(self):
        self.create_tables(schema_version=SCHEMA_VERSION+1)
        with self.assertRaises(ValueError):
            PersistentNonceRegistry(self.db)
        self.assertEqual(self.raw_version(),(SCHEMA_VERSION+1,))
        self.assertEqual(self.raw_claim_count(),1)

    def test_04_invalid_zero_schema_version_rejected_unmodified(self):
        self.create_tables(schema_version=0)
        with self.assertRaises(ValueError):
            PersistentNonceRegistry(self.db)
        self.assertEqual(self.raw_version(),(0,))

    def test_05_negative_schema_version_rejected_unmodified(self):
        self.create_tables(schema_version=-3)
        with self.assertRaises(ValueError):
            PersistentNonceRegistry(self.db)
        self.assertEqual(self.raw_version(),(-3,))

    def test_06_schema_version_wrong_storage_type_rejected_unmodified(self):
        self.create_tables(schema_version="two")
        with self.assertRaises(ValueError):
            PersistentNonceRegistry(self.db)
        self.assertEqual(self.raw_version(),("two",))

    def test_07_metadata_table_without_singleton_cannot_be_repaired_silently(self):
        self.create_tables(blank_meta=True)
        with self.assertRaises(ValueError):
            PersistentNonceRegistry(self.db)
        self.assertIsNone(self.raw_version())
        self.assertEqual(self.raw_claim_count(),1)

    def test_08_meta_current_but_claims_table_missing_stays_blocked(self):
        self.create_tables(claims=False)
        with self.assertRaises(ValueError):
            PersistentNonceRegistry(self.db)
        with closing(sqlite3.connect(self.db)) as db:
            self.assertIsNone(db.execute(
                "SELECT name FROM sqlite_master WHERE name='nonce_claims'"
            ).fetchone())
        self.assertEqual(self.raw_version(),(SCHEMA_VERSION,))

    def test_09_current_claims_without_meta_cannot_self_reenroll(self):
        self.create_tables(meta=False, expiry_column=True)
        with self.assertRaises(ValueError):
            PersistentNonceRegistry(self.db)
        with closing(sqlite3.connect(self.db)) as db:
            self.assertIsNone(db.execute(
                "SELECT name FROM sqlite_master WHERE name='nonce_registry_meta'"
            ).fetchone())
        self.assertEqual(self.raw_claim_count(),1)

    def test_10_current_meta_with_expiry_column_missing_is_denied(self):
        self.create_tables(schema_version=SCHEMA_VERSION,expiry_column=False)
        with self.assertRaises(ValueError):
            PersistentNonceRegistry(self.db)
        self.assertEqual(self.raw_version(),(SCHEMA_VERSION,))
        self.assertEqual(self.raw_claim_count(),1)

    def test_11_version_one_declared_upgrade_preserves_existing_nonce(self):
        self.create_tables(schema_version=1,expiry_column=False)
        r=PersistentNonceRegistry(self.db)
        self.assertEqual(r.schema_version(),SCHEMA_VERSION)
        self.assertEqual(r.count(),1)
        self.assertFalse(r.claim(scope="owner",nonce="prior-nonce",
                                 expires_at=EXP,now_ts=NOW))
        with closing(sqlite3.connect(self.db)) as conn:
            self.assertTrue(any(x[1]=="expires_at_us" for x in conn.execute(
                "PRAGMA table_info(nonce_claims)"
            ).fetchall()))

    def test_12_legacy_unversioned_pre_v2_format_migrates_existing_nonce(self):
        self.create_tables(meta=False,expiry_column=False)
        r=PersistentNonceRegistry(self.db)
        self.assertEqual(r.schema_version(),SCHEMA_VERSION)
        self.assertEqual(r.count(),1)
        self.assertFalse(r.claim(scope="owner",nonce="prior-nonce",
                                 expires_at=EXP,now_ts=NOW))

    def test_13_corrupt_meta_column_layout_is_not_silently_recreated(self):
        with closing(sqlite3.connect(self.db)) as db:
            db.execute("CREATE TABLE nonce_registry_meta (whatever INTEGER)")
            db.execute("INSERT INTO nonce_registry_meta(whatever) VALUES(27)")
            db.execute("CREATE TABLE nonce_claims (scope TEXT NOT NULL,"
                       "nonce TEXT NOT NULL,expires_at TEXT NOT NULL,"
                       "expires_at_us INTEGER,created_at TEXT NOT NULL,"
                       "PRIMARY KEY(scope,nonce))")
            db.commit()
        with self.assertRaises((ValueError,sqlite3.DatabaseError)):
            PersistentNonceRegistry(self.db)
        with closing(sqlite3.connect(self.db)) as db:
            self.assertEqual(db.execute(
                "SELECT whatever FROM nonce_registry_meta"
            ).fetchone(),(27,))

    def test_14_bad_schema_rejection_never_creates_authorization(self):
        self.create_tables(schema_version=SCHEMA_VERSION+99)
        with self.assertRaises(ValueError):
            PersistentNonceRegistry(self.db)
        self.assertEqual(self.raw_claim_count(),1)
        # Local anti-replay != external witness or owner attestation.
        self.assertFalse(hasattr(PersistentNonceRegistry,"authenticate_owner"))
        self.assertFalse(hasattr(PersistentNonceRegistry,"authorize_dispatch"))


if __name__=="__main__":
    unittest.main()
