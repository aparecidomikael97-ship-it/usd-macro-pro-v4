"""A140 RED-first: durable LAB quota reservation, unknown outcomes, no retry.

All paths are ephemeral test directories. No provider calls, GitHub write,
business logic deployment, live checkpoint, Worker, or paid usage.
"""
from __future__ import annotations

from contextlib import closing
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from atlasquant_market_sqlite_quota_a140 import (
    SQLiteLabReservationLedger, QuotaLabUnavailable, DB_FILENAME,
)
from atlasquant_market_boundary_a139 import (
    SyntheticMarketFeed, collect_synthetic_market,
)


class A140SQLiteLedgerAdversarialLAB(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)/"checkout"
        self.root.mkdir()
        self.lab=Path(self.tmp.name)/"quota"
        self.lab.mkdir()
        self.out=Path(self.tmp.name)/"out"
        self.out.mkdir()
        self.feed=SyntheticMarketFeed({"EUR/USD":{"bid":1.1,"ask":1.1002}})
        self.run="labrun140x"
        self.observed="2026-10-21T23:00:00Z"

    def ledger(self,*,limit=3,lab=None,root=None):
        return SQLiteLabReservationLedger(
            lab_dir=self.lab if lab is None else lab,
            checkout_root=self.root if root is None else root,
            limit=limit,
        )

    def collect(self,ledger,*,feed=None,run_id=None):
        return collect_synthetic_market(
            run_id=self.run if run_id is None else run_id,
            symbols=("EUR/USD",),
            feed=self.feed if feed is None else feed,
            quota=ledger,
            output_dir=self.out,
            checkout_root=self.root,
            observed_at=self.observed,
        )

    def test_01_db_created_only_in_isolated_lab_dir(self):
        a=self.ledger()
        self.assertTrue((self.lab/DB_FILENAME).is_file())
        self.assertFalse((self.root/"dados/aion/checkpoint_master.json").exists())
        self.assertFalse(a.independent_witness_enrolled)

    def test_02_ledger_initially_empty_and_limit_fixed(self):
        a=self.ledger(limit=3)
        self.assertEqual(a.reserved_units,0)
        self.assertEqual(a.limit,3)

    def test_03_reservation_survives_object_restart(self):
        self.assertTrue(self.ledger().reserve(self.run,2))
        other=self.ledger()
        self.assertEqual(other.reserved_units,2)
        self.assertEqual(other.reservation_state(self.run)["state"],"RESERVED_UNCERTAIN")

    def test_04_same_run_id_cannot_reserve_after_restart(self):
        self.assertTrue(self.ledger().reserve(self.run,1))
        self.assertFalse(self.ledger().reserve(self.run,1))
        self.assertEqual(self.ledger().reserved_units,1)

    def test_05_changed_units_same_id_also_denied(self):
        self.assertTrue(self.ledger().reserve(self.run,1))
        self.assertFalse(self.ledger().reserve(self.run,2))

    def test_06_quota_limit_never_exceeded(self):
        a=self.ledger(limit=2)
        self.assertTrue(a.reserve(self.run,2))
        self.assertFalse(a.reserve("labrun140y",1))
        self.assertEqual(self.ledger(limit=2).reserved_units,2)

    def test_07_policy_limit_increase_requires_migration(self):
        self.ledger(limit=2)
        with self.assertRaises(QuotaLabUnavailable):
            self.ledger(limit=3)

    def test_08_policy_limit_decrease_also_requires_review(self):
        self.ledger(limit=3)
        with self.assertRaises(QuotaLabUnavailable):
            self.ledger(limit=2)

    def test_09_invalid_empty_run_id_denied(self):
        self.assertFalse(self.ledger().reserve("",1))

    def test_10_path_traversal_run_id_denied(self):
        self.assertFalse(self.ledger().reserve("../../checkpoint",1))

    def test_11_invalid_integer_units_denied(self):
        a=self.ledger()
        for units in (0,-1,True,False,1.5,"2",101):
            self.assertFalse(a.reserve(self.run,units))
        self.assertEqual(a.reserved_units,0)

    def test_12_invalid_limits_denied(self):
        for limit in (0,-1,101,True,1.5,"2"):
            with self.assertRaises(ValueError):
                self.ledger(limit=limit)

    def test_13_lab_within_checkout_denied(self):
        new=self.root/"lab"
        new.mkdir()
        with self.assertRaises(ValueError):
            self.ledger(lab=new)

    def test_14_lab_equal_checkout_denied(self):
        with self.assertRaises(ValueError):
            self.ledger(lab=self.root)

    def test_15_direct_symlink_lab_denied(self):
        link=Path(self.tmp.name)/"link"
        try: link.symlink_to(self.lab,target_is_directory=True)
        except (OSError,NotImplementedError): self.skipTest("symlinks unavailable")
        with self.assertRaises(ValueError):
            self.ledger(lab=link)

    def test_16_symlink_db_denied_before_open(self):
        elsewhere=Path(self.tmp.name)/"elsewhere"
        elsewhere.write_text("PRIVATE")
        try: (self.lab/DB_FILENAME).symlink_to(elsewhere)
        except (OSError,NotImplementedError): self.skipTest("symlinks unavailable")
        with self.assertRaises(ValueError):
            self.ledger()
        self.assertEqual(elsewhere.read_text(),"PRIVATE")

    def test_17_corrupted_db_fails_closed(self):
        (self.lab/DB_FILENAME).write_bytes(b"invalid sqlite data")
        with self.assertRaises(QuotaLabUnavailable):
            self.ledger()

    def test_18_truncated_meta_fails_closed(self):
        self.ledger()
        with closing(sqlite3.connect(self.lab/DB_FILENAME)) as db:
            db.execute("DELETE FROM quota_policy")
            db.commit()
        with self.assertRaises(QuotaLabUnavailable):
            self.ledger()

    def test_19_unknown_schema_fails_closed(self):
        self.ledger()
        with closing(sqlite3.connect(self.lab/DB_FILENAME)) as db:
            db.execute("UPDATE quota_policy SET schema='ATTACKER_UPGRADE'")
            db.commit()
        with self.assertRaises(QuotaLabUnavailable):
            self.ledger()

    def test_20_concurrent_duplicate_reservation_only_one_wins(self):
        self.ledger(limit=2)
        def reserve(_):
            return self.ledger(limit=2).reserve(self.run,1)
        with ThreadPoolExecutor(max_workers=5) as pool:
            outcomes=list(pool.map(reserve,range(5)))
        self.assertEqual(outcomes.count(True),1)
        self.assertEqual(self.ledger(limit=2).reserved_units,1)

    def test_21_concurrent_distinct_ids_respect_cap(self):
        self.ledger(limit=2)
        def reserve(i):
            return self.ledger(limit=2).reserve(f"labrun140_{i:04d}",1)
        with ThreadPoolExecutor(max_workers=5) as pool:
            results=list(pool.map(reserve,range(8)))
        self.assertEqual(sum(results),2)
        self.assertEqual(self.ledger(limit=2).reserved_units,2)

    def test_22_record_local_output_requires_existing_reservation(self):
        a=self.ledger()
        self.assertFalse(a.record_local_output(self.run,"a"*64))

    def test_23_record_local_output_rejects_invalid_hash(self):
        a=self.ledger()
        self.assertTrue(a.reserve(self.run,1))
        for h in ("abc","g"*64,None,True):
            self.assertFalse(a.record_local_output(self.run,h))
        self.assertEqual(a.reservation_state(self.run)["state"],"RESERVED_UNCERTAIN")

    def test_24_successful_local_output_state_survives_reopen(self):
        a=self.ledger()
        self.assertTrue(a.reserve(self.run,1))
        self.assertTrue(a.record_local_output(self.run,"a"*64))
        state=self.ledger().reservation_state(self.run)
        self.assertEqual(state["state"],"LOCAL_OUTPUT_OBSERVED")
        self.assertEqual(state["payload_sha256"],"a"*64)
        self.assertEqual(self.ledger().reserved_units,1)

    def test_25_second_observation_is_not_accepted(self):
        a=self.ledger()
        self.assertTrue(a.reserve(self.run,1))
        self.assertTrue(a.record_local_output(self.run,"a"*64))
        self.assertFalse(a.record_local_output(self.run,"a"*64))
        self.assertFalse(a.record_local_output(self.run,"b"*64))

    def test_26_reservation_is_never_refunded_after_read_timeout(self):
        a=self.ledger()
        f=SyntheticMarketFeed({"EUR/USD":TimeoutError("mock uncertain")})
        result=self.collect(a,feed=f)
        self.assertEqual(result["status"],"UNCERTAIN_NO_AUTOMATIC_RETRY")
        self.assertEqual(self.ledger().reserved_units,1)
        self.assertEqual(self.ledger().reservation_state(self.run)["state"],"RESERVED_UNCERTAIN")
        self.assertEqual(f.calls,["EUR/USD"])

    def test_27_restart_prevents_fetch_after_timeout(self):
        a=self.ledger()
        f=SyntheticMarketFeed({"EUR/USD":TimeoutError("mock uncertain")})
        self.collect(a,feed=f)
        next_feed=SyntheticMarketFeed({"EUR/USD":{"bid":1.1,"ask":1.1002}})
        result=self.collect(self.ledger(),feed=next_feed)
        self.assertEqual(result["status"],"BLOCKED_NO_PROVIDER_FETCH")
        self.assertEqual(next_feed.calls,[])

    def test_28_integrated_collector_creates_local_only_output(self):
        result=self.collect(self.ledger())
        self.assertEqual(result["status"],"SYNTHETIC_OUTPUT_NOT_LIVE")
        self.assertTrue((self.out/result["filename"]).is_file())
        self.assertEqual(self.ledger().reservation_state(self.run)["state"],"LOCAL_OUTPUT_OBSERVED")

    def test_29_integrated_sha_observation_matches_envelope(self):
        result=self.collect(self.ledger())
        saved=json.loads((self.out/result["filename"]).read_text())
        state=self.ledger().reservation_state(self.run)
        self.assertEqual(state["payload_sha256"],saved["payload_sha256"])

    def test_30_repeated_integrated_run_fails_before_feed(self):
        self.collect(self.ledger())
        before=list(self.feed.calls)
        result=self.collect(self.ledger())
        self.assertEqual(result["status"],"BLOCKED_NO_PROVIDER_FETCH")
        self.assertEqual(before,self.feed.calls)

    def test_31_corrupt_database_after_init_blocks_before_provider(self):
        a=self.ledger()
        (self.lab/DB_FILENAME).write_bytes(b"destroyed synthetic db")
        result=self.collect(a)
        self.assertNotEqual(result["status"],"SYNTHETIC_OUTPUT_NOT_LIVE")
        self.assertEqual(self.feed.calls,[])

    def test_32_database_locked_reservation_does_not_fetch(self):
        a=self.ledger()
        with closing(sqlite3.connect(self.lab/DB_FILENAME,timeout=0,isolation_level=None)) as conn:
            conn.execute("BEGIN EXCLUSIVE")
            try:
                result=self.collect(a)
                self.assertEqual(result["status"],"BLOCKED_NO_PROVIDER_FETCH")
                self.assertEqual(self.feed.calls,[])
            finally:
                conn.rollback()

    def test_33_no_implicit_expansion_after_reopen(self):
        self.ledger(limit=1).reserve(self.run,1)
        self.assertFalse(self.ledger(limit=1).reserve("labrun140y",1))

    def test_34_lab_ledger_cannot_claim_provider_effect_or_human_owner(self):
        a=self.ledger()
        self.assertFalse(a.independent_witness_enrolled)
        self.assertFalse(a.external_provider_effect_proven)
        self.assertFalse(a.human_owner_verified)

    def test_35_db_outcome_transition_is_not_proof_of_provider_effect(self):
        a=self.ledger()
        a.reserve(self.run,1)
        a.record_local_output(self.run,"a"*64)
        self.assertEqual(a.reservation_state(self.run)["state"],"LOCAL_OUTPUT_OBSERVED")
        self.assertFalse(a.external_provider_effect_proven)


if __name__=="__main__":
    unittest.main()
