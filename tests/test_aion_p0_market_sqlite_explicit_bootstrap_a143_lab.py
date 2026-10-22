"""A143: explicit LAB bootstrap MUST be separate from normal open-existing.

No provider, Worker, GitHub writer, production quota, owner identity or external
antirollback witness. All files are temporary synthetic lab databases.
"""
from __future__ import annotations
from contextlib import closing, contextmanager
from pathlib import Path
import os
import shutil
import sqlite3
import tempfile
import unittest

from atlasquant_market_sqlite_quota_a140 import (
    SQLiteLabReservationLedger, QuotaLabUnavailable, DB_FILENAME,
)
from atlasquant_market_boundary_a139 import (
    SyntheticMarketFeed, collect_synthetic_market,
)


class A143ExplicitBootstrapLAB(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base=Path(self.tmp.name)
        self.lab=self.base/"quota"
        self.lab.mkdir()
        self.repo=self.base/"checkout"
        self.repo.mkdir()
        self.output=self.base/"out"
        self.output.mkdir()
        self.path=self.lab/DB_FILENAME
        self.kw={"lab_dir":self.lab,"checkout_root":self.repo,"limit":3}
        self.run="a143runone"

    def open(self):
        return SQLiteLabReservationLedger(**self.kw)

    def bootstrap(self):
        return SQLiteLabReservationLedger.bootstrap_synthetic_lab(**self.kw)

    def test_01_normal_open_missing_db_denies_without_creating(self):
        with self.assertRaises(QuotaLabUnavailable):
            self.open()
        self.assertFalse(self.path.exists())

    def test_02_explicit_lab_bootstrap_creates_first_db(self):
        x=self.bootstrap()
        self.assertTrue(self.path.is_file())
        self.assertEqual(x.reserved_units,0)
        self.assertFalse(x.independent_witness_enrolled)

    def test_03_open_existing_after_explicit_bootstrap_succeeds(self):
        self.bootstrap()
        self.assertEqual(self.open().reserved_units,0)

    def test_04_repeat_bootstrap_existing_db_denied_without_modification(self):
        a=self.bootstrap()
        self.assertTrue(a.reserve(self.run,1))
        before=self.path.read_bytes()
        with self.assertRaises(QuotaLabUnavailable):
            self.bootstrap()
        self.assertEqual(self.path.read_bytes(),before)
        self.assertEqual(self.open().reserved_units,1)

    def test_05_missing_db_after_reservation_cannot_reset_history(self):
        x=self.bootstrap()
        self.assertTrue(x.reserve(self.run,1))
        self.path.unlink()
        with self.assertRaises(QuotaLabUnavailable):
            self.open()
        self.assertFalse(self.path.exists())

    def test_06_crash_restart_like_new_ledger_missing_db_denies(self):
        x=self.bootstrap()
        self.assertTrue(x.reserve(self.run,2))
        self.path.unlink()
        with self.assertRaises(QuotaLabUnavailable):
            self.open()
        self.assertFalse(self.path.exists())

    def test_07_deleted_db_refuses_to_fetch_on_constructor_failure(self):
        self.bootstrap().reserve(self.run,1)
        self.path.unlink()
        feed=SyntheticMarketFeed({"EUR/USD":{"bid":1.1,"ask":1.1002}})
        try:
            ledger=self.open()
        except QuotaLabUnavailable:
            ledger=None
        self.assertIsNone(ledger)
        # Test the actual fail-closed acquisition boundary, not just the
        # absence of a constructed ledger object.
        result=collect_synthetic_market(
            run_id=self.run,symbols=("EUR/USD",),feed=feed,quota=ledger,
            output_dir=self.output,checkout_root=self.repo,
            observed_at="2026-10-21T23:00:00Z",
        )
        self.assertEqual(result["status"],"BLOCKED_NO_PROVIDER_FETCH")
        self.assertEqual(feed.calls,[])
        self.assertEqual(list(self.output.iterdir()),[])

    def test_08_no_implicit_bootstrap_in_regular_constructor(self):
        self.assertFalse(self.path.exists())
        with self.assertRaises(QuotaLabUnavailable):
            SQLiteLabReservationLedger(
                lab_dir=self.lab,checkout_root=self.repo,limit=3,
            )
        self.assertEqual(list(self.lab.iterdir()),[])

    def test_09_corrupted_existing_db_cannot_bootstrap_over(self):
        self.path.write_bytes(b"corrupted db")
        with self.assertRaises(QuotaLabUnavailable):
            self.bootstrap()
        self.assertEqual(self.path.read_bytes(),b"corrupted db")

    def test_10_symlink_db_bootstrap_denied(self):
        target=self.base/"other.db"
        target.write_bytes(b"sensitive")
        try:
            self.path.symlink_to(target)
        except (OSError,NotImplementedError):
            self.skipTest("Symlink unavailable on runner")
        with self.assertRaises((ValueError,QuotaLabUnavailable)):
            self.bootstrap()
        self.assertEqual(target.read_bytes(),b"sensitive")

    def test_11_checkout_inside_bootstrap_denied(self):
        inside=self.repo/"quota"
        inside.mkdir()
        with self.assertRaises(ValueError):
            SQLiteLabReservationLedger.bootstrap_synthetic_lab(
                lab_dir=inside,checkout_root=self.repo,limit=3,
            )
        self.assertEqual(list(inside.iterdir()),[])

    def test_12_sqlite_policy_limit_change_cannot_be_opened(self):
        self.bootstrap()
        with self.assertRaises(QuotaLabUnavailable):
            SQLiteLabReservationLedger(
                lab_dir=self.lab,checkout_root=self.repo,limit=4,
            )

    def test_13_open_existing_preserves_duplicate_denial(self):
        a=self.bootstrap()
        self.assertTrue(a.reserve(self.run,1))
        b=self.open()
        self.assertFalse(b.reserve(self.run,1))
        self.assertEqual(b.reserved_units,1)

    def test_14_open_existing_corrupted_record_denies(self):
        self.bootstrap()
        with closing(sqlite3.connect(self.path)) as db:
            db.execute("DELETE FROM quota_policy")
            db.commit()
        with self.assertRaises(QuotaLabUnavailable):
            self.open()

    def test_15_explicit_bootstrap_not_trusted_owner_authority(self):
        a=self.bootstrap()
        self.assertFalse(a.human_owner_verified)
        self.assertFalse(a.external_provider_effect_proven)
        self.assertFalse(a.independent_witness_enrolled)

    def test_16_manual_rebootstrap_after_deletion_is_still_risk(self):
        # NEGATIVE LIMIT: an attacker/authorized operator with power to call
        # explicit bootstrap can STILL reset local history. This API is not
        # proof of out-of-band custody, owner auth or monotonic epoch.
        a=self.bootstrap()
        self.assertTrue(a.reserve(self.run,1))
        self.path.unlink()
        b=self.bootstrap()
        self.assertEqual(b.reserved_units,0)
        self.assertTrue(b.reserve(self.run,1))

    def test_17_valid_rollback_of_old_db_remains_undetectable_on_reopen(self):
        a=self.bootstrap()
        stale=self.base/"valid-before.sqlite3"
        shutil.copyfile(self.path,stale)
        self.assertTrue(a.reserve(self.run,1))
        os.replace(stale,self.path)
        b=self.open()
        self.assertEqual(b.reserved_units,0)
        self.assertTrue(b.reserve(self.run,1))

    def test_18_failed_bootstrap_of_existing_db_is_non_destructive(self):
        a=self.bootstrap()
        self.assertTrue(a.reserve(self.run,2))
        with self.assertRaises(QuotaLabUnavailable):
            self.bootstrap()
        self.assertEqual(self.open().reserved_units,2)


    def test_19_bootstrap_created_file_replaced_after_exclusive_close_denied(self):
        adversary_dir=self.base/"synthetic_adversary_lab"
        adversary_dir.mkdir()
        malicious_db=SQLiteLabReservationLedger.bootstrap_synthetic_lab(
            lab_dir=adversary_dir,checkout_root=self.repo,limit=3,
        )
        self.assertTrue(malicious_db.reserve("a143otherone",1))
        replacement=adversary_dir/DB_FILENAME
        normal_path_open=Path.open
        swapped=[False]

        @contextmanager
        def substituted_open(path,*args,**kwargs):
            mode=args[0] if args else kwargs.get("mode","r")
            with normal_path_open(path,*args,**kwargs) as handle:
                yield handle
            if path==self.path and mode=="xb":
                # Simulated adversary swaps a fully initialized valid SQLite
                # immediately after exclusive-creation FD closes.
                os.replace(replacement,self.path)
                swapped[0]=True

        from unittest.mock import patch
        with patch.object(Path,"open",substituted_open):
            with self.assertRaises(QuotaLabUnavailable):
                self.bootstrap()
        self.assertTrue(swapped[0])
        # The synthetic attacker had valid schema/policy; only identity of
        # OUR freshly-created FD may reject this substituted source.
        self.assertTrue(self.path.exists())

    def test_20_partial_bootstrap_file_fails_closed_without_self_heal(self):
        self.path.write_bytes(b"")
        with self.assertRaises(QuotaLabUnavailable):
            self.open()
        with self.assertRaises(QuotaLabUnavailable):
            self.bootstrap()
        self.assertEqual(self.path.read_bytes(),b"")


if __name__=="__main__":
    unittest.main()
