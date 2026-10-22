"""A144 LAB adversarial schema checks. Offline synthetic SQLite only."""
import sqlite3
import os
import shutil
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

    def test_07_extra_view_denies_reopen(self):
        with closing(sqlite3.connect(self.path)) as db:
            db.execute("CREATE VIEW extra_view AS SELECT * FROM reservations")
            db.commit()
        with self.assertRaises(QuotaLabUnavailable):
            self.reopen()

    def test_08_trigger_denies_existing_instance_reservation(self):
        ledger=self.reopen()
        with closing(sqlite3.connect(self.path)) as db:
            db.execute("CREATE TRIGGER extra_trigger AFTER INSERT ON reservations BEGIN SELECT 1; END")
            db.commit()
        self.assertFalse(ledger.reserve("a144runtwo",1))
        with self.assertRaises(QuotaLabUnavailable):
            _=ledger.reserved_units

    def test_09_index_denies_existing_instance_output(self):
        ledger=self.reopen()
        self.assertTrue(ledger.reserve("a144runone",1))
        with closing(sqlite3.connect(self.path)) as db:
            db.execute("CREATE INDEX extra_index ON reservations(units)")
            db.commit()
        self.assertFalse(ledger.record_local_output("a144runone","a"*64))
        with self.assertRaises(QuotaLabUnavailable):
            ledger.reservation_state("a144runone")

    def test_10_attestation_does_not_claim_external_witness(self):
        ledger=self.reopen()
        self.assertFalse(ledger.independent_witness_enrolled)
        self.assertFalse(ledger.external_provider_effect_proven)
        self.assertFalse(ledger.human_owner_verified)
        self.assertFalse(ledger.automatic_retry_allowed)

    def test_11_reopen_rejects_foreign_view_without_schema_repair(self):
        with closing(sqlite3.connect(self.path)) as db:
            db.execute("CREATE VIEW extra_view AS SELECT units FROM reservations")
            db.commit()
        with self.assertRaises(QuotaLabUnavailable):
            self.reopen()
        with closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(db.execute(
                "SELECT COUNT(*) FROM sqlite_master WHERE name='extra_view'"
            ).fetchone(),(1,))

    def test_12_valid_ledger_still_reserves_and_observes_output(self):
        ledger=self.reopen()
        self.assertTrue(ledger.reserve("a144runone",1))
        self.assertTrue(ledger.record_local_output("a144runone","b"*64))
        self.assertEqual(self.reopen().reservation_state("a144runone")["state"],
                         "LOCAL_OUTPUT_OBSERVED")

    def test_13_negative_stale_valid_database_still_accepted_after_restart(self):
        # NEGATIVE SECURITY EVIDENCE: exact schema cannot establish freshness.
        ledger=self.reopen()
        stale=self.lab.parent/"stale_valid_snapshot.sqlite3"
        shutil.copyfile(self.path,stale)
        self.assertTrue(ledger.reserve("a144runone",1))
        os.replace(stale,self.path)
        reopened=self.reopen()
        self.assertEqual(reopened.reserved_units,0)
        self.assertFalse(reopened.independent_witness_enrolled)

    def test_14_negative_manual_rebootstrap_still_resets_local_history(self):
        # NEGATIVE SECURITY EVIDENCE: no independent genesis custody.
        ledger=self.reopen()
        self.assertTrue(ledger.reserve("a144runone",1))
        self.path.unlink()
        fresh=SQLiteLabReservationLedger.bootstrap_synthetic_lab(**self.args)
        self.assertEqual(fresh.reserved_units,0)
        self.assertFalse(fresh.human_owner_verified)

if __name__=="__main__": unittest.main()
