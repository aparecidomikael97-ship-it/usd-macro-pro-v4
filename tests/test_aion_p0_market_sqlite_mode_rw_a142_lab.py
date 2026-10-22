"""A142 adversarial SQLite URI mode=rw and no implicit recreation.

Uses only offline SQLite files under TemporaryDirectory and synthetic monkeypatches.
Never calls real providers, Github Contents API, Worker, restore or deployments.
"""
from __future__ import annotations

from contextlib import closing
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from atlasquant_market_sqlite_quota_a140 import (
    DB_FILENAME, SQLiteLabReservationLedger, QuotaLabUnavailable,
)


class A142SQLiteNoImplicitCreateLAB(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.checkout=self.root/"checkout"
        self.checkout.mkdir()
        # Spaces, #, % and & exercise percent-encoding on Windows and Ubuntu.
        self.lab=self.root/"quota folder#100%&case"
        self.lab.mkdir()
        self.key="a142runone"

    @property
    def db_path(self):
        return self.lab/DB_FILENAME

    def ledger(self):
        return SQLiteLabReservationLedger(
            lab_dir=self.lab,checkout_root=self.checkout,limit=3,
        )

    def test_01_existing_file_sqlite_connection_is_uri_mode_rw(self):
        ledger=self.ledger()
        true_connect=sqlite3.connect
        captured=[]
        def capture(*args,**kwargs):
            captured.append((args,dict(kwargs)))
            return true_connect(*args,**kwargs)
        with patch("atlasquant_market_sqlite_quota_a140.sqlite3.connect",
                   side_effect=capture):
            self.assertTrue(ledger.reserve(self.key,1))
        self.assertGreater(len(captured),0)
        for args,kw in captured:
            self.assertEqual(kw.get("uri"),True)
            self.assertIn("mode=rw",args[0])
            self.assertIn("file:",args[0])

    def test_02_path_encoded_so_query_fragments_do_not_change_mode(self):
        ledger=self.ledger()
        self.assertTrue(ledger.reserve(self.key,1))
        self.assertEqual(ledger.reserved_units,1)

    def test_03_removed_during_connect_not_automatically_recreated(self):
        ledger=self.ledger()
        true_connect=sqlite3.connect
        removed=[False]
        def remove_then_connect(*args,**kw):
            if not removed[0]:
                removed[0]=True
                self.db_path.unlink()
            return true_connect(*args,**kw)
        with patch("atlasquant_market_sqlite_quota_a140.sqlite3.connect",
                   side_effect=remove_then_connect):
            self.assertFalse(ledger.reserve(self.key,1))
        self.assertTrue(removed[0])
        self.assertFalse(self.db_path.exists(),"SQLite re-created lost quota DB!")

    def test_04_removed_database_not_recreated_on_read(self):
        ledger=self.ledger()
        self.db_path.unlink()
        with self.assertRaises(QuotaLabUnavailable):
            _=ledger.reserved_units
        self.assertFalse(self.db_path.exists())

    def test_05_removed_database_not_recreated_on_output_receipt(self):
        ledger=self.ledger()
        self.assertTrue(ledger.reserve(self.key,1))
        self.db_path.unlink()
        self.assertFalse(ledger.record_local_output(self.key,"a"*64))
        self.assertFalse(self.db_path.exists())

    def test_06_missing_database_must_not_reset_history_on_same_instance(self):
        ledger=self.ledger()
        self.assertTrue(ledger.reserve(self.key,1))
        self.db_path.unlink()
        self.assertFalse(ledger.reserve("a142runtwo",1))
        self.assertFalse(self.db_path.exists())

    def test_07_existing_db_open_and_reserve_remain_functional(self):
        ledger=self.ledger()
        self.assertTrue(ledger.reserve(self.key,2))
        self.assertFalse(ledger.reserve("a142runtwo",2))
        self.assertTrue(ledger.record_local_output(self.key,"b"*64))
        self.assertEqual(ledger.reservation_state(self.key)["state"],
                         "LOCAL_OUTPUT_OBSERVED")

    def test_08_missing_preexisting_db_creation_only_on_explicit_init(self):
        a=self.ledger()
        self.assertTrue(self.db_path.is_file())
        self.assertEqual(a.reserved_units,0)
        self.assertFalse(a.reserve("",1))

    def test_09_recreate_with_new_object_still_not_trusted_history(self):
        # Explicit negative characterization: a new object can create an empty
        # DB if the old file disappears, so this is NOT production protection.
        a=self.ledger()
        self.assertTrue(a.reserve(self.key,1))
        self.db_path.unlink()
        b=self.ledger()
        self.assertEqual(b.reserved_units,0)
        self.assertTrue(b.reserve(self.key,1))

    def test_10_database_file_no_unexpected_creation_after_connection_error(self):
        ledger=self.ledger()
        self.db_path.unlink()
        self.assertFalse(ledger.reserve("a142runtwo",1))
        self.assertFalse(self.db_path.exists())

    def test_11_untrusted_script_must_not_get_token_or_provider_authority(self):
        ledger=self.ledger()
        self.assertFalse(ledger.independent_witness_enrolled)
        self.assertFalse(ledger.human_owner_verified)
        self.assertFalse(ledger.external_provider_effect_proven)


if __name__=="__main__":
    unittest.main()
