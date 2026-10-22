"""A144 LAB adversarial schema checks. Offline synthetic SQLite only."""
import sqlite3
import tempfile
import unittest
from pathlib import Path
from contextlib import closing
from atlasquant_market_sqlite_quota_a140 import SQLiteLabReservationLedger, QuotaLabUnavailable, DB_FILENAME

class A144SchemaAttestationLAB(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root=Path(self.temp.name)
        self.lab=root/"quota"; self.lab.mkdir()
        self.checkout=root/"checkout"; self.checkout.mkdir()
        self.args=dict(lab_dir=self.lab,checkout_root=self.checkout,limit=3)
        SQLiteLabReservationLedger.bootstrap_synthetic_lab(**self.args)
        self.path=self.lab/DB_FILENAME

    def reopen(self):
        return SQLiteLabReservationLedger(**self.args)

    def test_01_extra_trigger_must_block_reopen(self):
        with closing(sqlite3.connect(self.path)) as db:
            db.execute("CREATE TRIGGER evil AFTER INSERT ON reservations BEGIN UPDATE quota_policy SET configured_limit=3; END")
            db.commit()
        with self.assertRaises(QuotaLabUnavailable): self.reopen()

    def test_02_extra_table_must_block_reopen(self):
        with closing(sqlite3.connect(self.path)) as db:
            db.execute("CREATE TABLE shadow_reservations (x TEXT)")
            db.commit()
        with self.assertRaises(QuotaLabUnavailable): self.reopen()

    def test_03_missing_primary_key_must_block_reopen(self):
        with closing(sqlite3.connect(self.path)) as db:
            db.execute("ALTER TABLE reservations RENAME TO old_reservations")
            db.execute("CREATE TABLE reservations(run_id TEXT,units INTEGER,state TEXT,payload_sha256 TEXT)")
            db.execute("INSERT INTO reservations SELECT * FROM old_reservations")
            db.execute("DROP TABLE old_reservations")
            db.commit()
        with self.assertRaises(QuotaLabUnavailable): self.reopen()

    def test_04_extra_index_must_block_reopen(self):
        with closing(sqlite3.connect(self.path)) as db:
            db.execute("CREATE INDEX shadow_index ON reservations(state)")
            db.commit()
        with self.assertRaises(QuotaLabUnavailable): self.reopen()

    def test_05_legitimate_existing_schema_and_reservation(self):
        a=self.reopen()
        self.assertTrue(a.reserve("a144runone",1))
        self.assertEqual(self.reopen().reserved_units,1)

    def test_06_foreign_application_id_must_block_reopen(self):
        with closing(sqlite3.connect(self.path)) as db:
            db.execute("PRAGMA application_id=123456")
            db.commit()
        with self.assertRaises(QuotaLabUnavailable): self.reopen()

if __name__=="__main__": unittest.main()
