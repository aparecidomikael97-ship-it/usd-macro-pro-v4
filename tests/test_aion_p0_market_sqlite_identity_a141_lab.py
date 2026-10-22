"""A141 RED-first: SQLite pathname/file identity and junction risk reduction.

No external trust, no provider, no GitHub write, and no claim of atomic
TOCTOU prevention. All files live in temporary LAB fixtures.
"""
from __future__ import annotations

from contextlib import closing
import os
from pathlib import Path
import shutil
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from atlasquant_market_sqlite_quota_a140 import (
    DB_FILENAME, SQLiteLabReservationLedger, QuotaLabUnavailable,
)

class A141StorageIdentityLAB(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.work=Path(self.tmp.name)
        self.lab=self.work/"lab"
        self.lab.mkdir()
        self.checkout=self.work/"checkout"
        self.checkout.mkdir()
        self.run="a141runone"

    def ledger(self,**extra):
        return SQLiteLabReservationLedger(
            lab_dir=extra.get("lab_dir",self.lab),
            checkout_root=extra.get("checkout_root",self.checkout),
            limit=extra.get("limit",3),
        )

    def replace_db(self):
        db=self.lab/DB_FILENAME
        back=self.work/"db-other.sqlite3"
        shutil.copyfile(db,back)
        os.replace(back,db)

    def test_01_ledger_pins_file_and_directory_identity_in_process(self):
        a=self.ledger()
        self.assertIsNotNone(a._db_identity)
        self.assertIsNotNone(a._dir_identity)

    def test_02_replaced_db_after_reservation_blocks_read(self):
        a=self.ledger()
        self.assertTrue(a.reserve(self.run,1))
        self.replace_db()
        with self.assertRaises(QuotaLabUnavailable):
            _=a.reserved_units

    def test_03_replaced_db_after_reservation_blocks_further_reserve(self):
        a=self.ledger()
        self.assertTrue(a.reserve(self.run,1))
        self.replace_db()
        self.assertFalse(a.reserve("a141runtwo",1))

    def test_04_replaced_db_blocks_observation_update(self):
        a=self.ledger()
        self.assertTrue(a.reserve(self.run,1))
        self.replace_db()
        self.assertFalse(a.record_local_output(self.run,"a"*64))

    def test_05_replaced_db_blocks_state_read(self):
        a=self.ledger()
        self.assertTrue(a.reserve(self.run,1))
        self.replace_db()
        with self.assertRaises(QuotaLabUnavailable):
            a.reservation_state(self.run)

    def test_06_renamed_parent_with_new_directory_denied(self):
        a=self.ledger()
        self.assertTrue(a.reserve(self.run,1))
        old=self.work/"lab_old"
        self.lab.rename(old)
        self.lab.mkdir()
        shutil.copyfile(old/DB_FILENAME,self.lab/DB_FILENAME)
        with self.assertRaises(QuotaLabUnavailable):
            a.reservation_state(self.run)

    def test_07_reparse_junction_claim_in_init_denied(self):
        with patch.object(Path,"is_junction",return_value=True):
            with self.assertRaises(ValueError):
                self.ledger()

    def test_08_reparse_junction_claim_at_runtime_denied(self):
        a=self.ledger()
        with patch.object(Path,"is_junction",return_value=True):
            self.assertFalse(a.reserve(self.run,1))

    def test_09_swapped_db_during_sqlite_connect_denied_before_write(self):
        a=self.ledger()
        original=sqlite3.connect
        swapped=[False]
        def attacking_connect(*args,**kwargs):
            if not swapped[0]:
                swapped[0]=True
                self.replace_db()
            return original(*args,**kwargs)
        with patch("atlasquant_market_sqlite_quota_a140.sqlite3.connect",
                   side_effect=attacking_connect):
            self.assertFalse(a.reserve(self.run,1))
        self.assertTrue(swapped[0])
        # Atomicity not claimed; attempted new write must be rejected.
        self.assertEqual(self.ledger().reserved_units,0)

    def test_10_normal_sqlite_use_still_passes(self):
        a=self.ledger()
        self.assertTrue(a.reserve(self.run,1))
        self.assertEqual(a.reserved_units,1)
        self.assertTrue(a.record_local_output(self.run,"a"*64))
        self.assertEqual(a.reservation_state(self.run)["state"],
                         "LOCAL_OUTPUT_OBSERVED")

    def test_11_directory_symlink_after_init_denied(self):
        a=self.ledger()
        old=self.work/"old_lab"
        self.lab.rename(old)
        try:
            self.lab.symlink_to(old,target_is_directory=True)
        except (OSError,NotImplementedError):
            self.skipTest("Symlink creation not available")
        self.assertFalse(a.reserve(self.run,1))

    def test_12_valid_local_db_rollback_still_undetectable_after_new_instance(self):
        # This is intentional proof of an UNFIXED external trust gap.
        a=self.ledger()
        source=self.work/"stale-copy.sqlite3"
        shutil.copyfile(self.lab/DB_FILENAME,source)
        self.assertTrue(a.reserve(self.run,1))
        os.replace(source,self.lab/DB_FILENAME)
        # Existing instance denies after identity replacement:
        self.assertFalse(a.reserve("a141runtwo",1))
        # A *new* instance cannot authenticate historical high-water:
        b=self.ledger()
        self.assertEqual(b.reserved_units,0)
        self.assertTrue(b.reserve(self.run,1))

    def test_13_hardlinked_db_at_init_is_denied(self):
        self.ledger()
        alias=self.work/"hardlink.sqlite3"
        try:
            os.link(self.lab/DB_FILENAME,alias)
        except OSError:
            self.skipTest("Hardlinks not supported on this drive")
        with self.assertRaises(ValueError):
            self.ledger()

    def test_14_identity_guard_does_not_claim_external_authentication(self):
        a=self.ledger()
        self.assertFalse(a.independent_witness_enrolled)
        self.assertFalse(a.external_provider_effect_proven)
        self.assertFalse(a.human_owner_verified)


    def test_15_same_inode_sqlite_content_rewind_blocks_balance_read(self):
        a=self.ledger()
        stale=self.work/"stale-bytes.sqlite3"
        shutil.copyfile(self.lab/DB_FILENAME,stale)
        self.assertTrue(a.reserve(self.run,1))
        identity=(self.lab/DB_FILENAME).stat().st_ino
        # copyfile truncates/writes, preserving current file identity;
        # inode-only checks do NOT detect this.
        shutil.copyfile(stale,self.lab/DB_FILENAME)
        self.assertEqual((self.lab/DB_FILENAME).stat().st_ino,identity)
        with self.assertRaises(QuotaLabUnavailable):
            _=a.reserved_units

    def test_16_same_inode_rewind_denies_any_new_reservation(self):
        a=self.ledger()
        stale=self.work/"stale-bytes.sqlite3"
        shutil.copyfile(self.lab/DB_FILENAME,stale)
        self.assertTrue(a.reserve(self.run,1))
        shutil.copyfile(stale,self.lab/DB_FILENAME)
        self.assertFalse(a.reserve("a141runtwo",1))

    def test_17_new_instance_unprotected_against_in_place_stale_db(self):
        # Negative documented limit: process-only high-water does not have
        # external trust/persistence. A new ledger trusts a valid stale DB.
        a=self.ledger()
        stale=self.work/"stale-bytes.sqlite3"
        shutil.copyfile(self.lab/DB_FILENAME,stale)
        self.assertTrue(a.reserve(self.run,1))
        shutil.copyfile(stale,self.lab/DB_FILENAME)
        b=self.ledger()
        self.assertEqual(b.reserved_units,0)
        self.assertTrue(b.reserve(self.run,1))


    def test_18_reopened_instance_pins_preexisting_history_immediately(self):
        a=self.ledger()
        stale=self.work/"stale.sqlite3"
        shutil.copyfile(self.lab/DB_FILENAME,stale)
        self.assertTrue(a.reserve(self.run,2))
        reopened=self.ledger()
        shutil.copyfile(stale,self.lab/DB_FILENAME)
        self.assertFalse(reopened.reserve("a141runtwo",1))

    def test_19_read_of_other_process_observation_pins_higher_balance(self):
        a=self.ledger()
        self.assertTrue(a.reserve(self.run,1))
        snapshot=self.work/"before-second.sqlite3"
        shutil.copyfile(self.lab/DB_FILENAME,snapshot)
        b=self.ledger()
        self.assertTrue(b.reserve("a141runtwo",1))
        self.assertEqual(a.reservation_state("a141runtwo")["units"],1)
        shutil.copyfile(snapshot,self.lab/DB_FILENAME)
        self.assertFalse(a.reserve("a141runnew",1))

    def test_20_same_sum_old_local_output_state_is_rejected(self):
        a=self.ledger()
        self.assertTrue(a.reserve(self.run,1))
        stale=self.work/"before-observation.sqlite3"
        shutil.copyfile(self.lab/DB_FILENAME,stale)
        self.assertTrue(a.record_local_output(self.run,"a"*64))
        shutil.copyfile(stale,self.lab/DB_FILENAME)
        self.assertFalse(a.record_local_output(self.run,"b"*64))
        with self.assertRaises(QuotaLabUnavailable):
            a.reservation_state(self.run)

    def test_21_same_sum_different_run_id_is_rejected(self):
        a=self.ledger()
        self.assertTrue(a.reserve(self.run,1))
        # All mutations take place in a synthetic temp SQLite fixture.
        with closing(sqlite3.connect(self.lab/DB_FILENAME)) as db:
            db.execute("UPDATE reservations SET run_id=? WHERE run_id=?",
                       ("a141runtwo",self.run))
            db.commit()
        with self.assertRaises(QuotaLabUnavailable):
            a.reservation_state(self.run)
        self.assertFalse(a.reserve("a141runnew",1))

    def test_22_hardlink_added_after_initialization_is_denied(self):
        a=self.ledger()
        link=self.work/"post-init-link.sqlite3"
        try:
            os.link(self.lab/DB_FILENAME,link)
        except OSError:
            self.skipTest("Hardlinks unsupported by filesystem")
        self.assertFalse(a.reserve(self.run,1))
        with self.assertRaises(QuotaLabUnavailable):
            _=a.reserved_units


if __name__=="__main__":
    unittest.main()
