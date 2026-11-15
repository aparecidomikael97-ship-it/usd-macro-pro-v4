"""Offline tests of a lab-only atomic claim; temp files and synthetic clocks.

No real data, no MT5 I/O, no scheduled task integration or trade action.
"""
from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timedelta,timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import json,unittest,multiprocessing as mp

from atlasquant_trader_fx28_first_m15_atomic_claim_lab import (
    SCHEMA,WINDOW,CLAIM_NAME,claim_once_lab,inspect_claim_lab,
)
CLOSED=datetime(2026,11,15,22,20,tzinfo=timezone.utc)
EARLY=datetime(2026,11,15,22,14,59,tzinfo=timezone.utc)

def _separate_process_claim(path,barrier,result_queue):
    """Spawned worker, not a thread. One shared filesystem claim path."""
    barrier.wait(timeout=20)
    result=claim_once_lab(archive_root=Path(path),clock=lambda:CLOSED)
    result_queue.put(result["exclusive_claim_created"])

class TestFX28AtomicClaim(unittest.TestCase):
    def setUp(self):
        self.temp=TemporaryDirectory(prefix="ATLASQUANT_ATOMIC_CLAIM_MOCK_ONLY_")
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)/"FX28_NY17_M15"
        self.root.mkdir()
    def call(self,clock=lambda:CLOSED):
        return claim_once_lab(archive_root=self.root,clock=clock)
    def test_one_claim_exists_no_replay(self):
        a=self.call()
        b=self.call(clock=lambda:CLOSED+timedelta(minutes=1))
        self.assertTrue(a["exclusive_claim_created"])
        self.assertFalse(b["exclusive_claim_created"])
        self.assertEqual(len(list(self.root.iterdir())),1)
        self.assertEqual(next(self.root.iterdir()).name,CLAIM_NAME)
        self.assertFalse(b["trading_authorized"])
    def test_payload_is_pinned_and_not_trade_permission(self):
        a=self.call()
        record=json.loads((self.root/CLAIM_NAME).read_text(encoding="utf-8"))
        self.assertEqual(record["schema"],SCHEMA)
        self.assertEqual(record["window"],WINDOW)
        self.assertEqual(record["window_open_utc"],"2026-11-15T22:00:00+00:00")
        self.assertFalse(record["trading_authorized"])
        self.assertFalse(a["archive_capture_allowed_by_this_module"])
        self.assertFalse(a["claim_does_not_authenticate_broker_or_market"] is False)
    def test_before_window_close_does_not_claim(self):
        a=self.call(clock=lambda:EARLY)
        self.assertIn("NOT_CLOSED",a["reason"])
        self.assertFalse(list(self.root.iterdir()))
    def test_late_next_day_does_not_claim_or_create_artifacts(self):
        late=datetime(2026,11,16,9,0,tzinfo=timezone.utc)
        r=self.call(clock=lambda:late)
        self.assertEqual(r["reason"],"PROSPECTIVE_CLAIM_AFTER_DEADLINE_NO_BACKFILL")
        self.assertFalse(r["exclusive_claim_created"])
        self.assertFalse(list(self.root.iterdir()))
    def test_exact_deadline_is_exclusive(self):
        deadline=datetime(2026,11,15,23,0,tzinfo=timezone.utc)
        self.assertFalse(self.call(clock=lambda:deadline)["exclusive_claim_created"])
        self.assertFalse(list(self.root.iterdir()))
    def test_one_second_before_deadline_permitted_only_as_local_claim(self):
        last=datetime(2026,11,15,22,59,59,tzinfo=timezone.utc)
        r=self.call(clock=lambda:last)
        self.assertTrue(r["exclusive_claim_created"])
        self.assertFalse(r["claim_does_not_authenticate_broker_or_market"] is False)
    def test_naive_clock_does_not_claim(self):
        a=self.call(clock=lambda:datetime(2026,11,15,22,20))
        self.assertFalse(a["exclusive_claim_created"])
        self.assertFalse(list(self.root.iterdir()))
    def test_invalid_clock_type_does_not_claim(self):
        a=self.call(clock=lambda:None)
        self.assertFalse(a["exclusive_claim_created"])
    def test_missing_root_fails_closed_no_mkdir(self):
        self.root.rmdir()
        a=self.call()
        self.assertFalse(a["exclusive_claim_created"])
        self.assertFalse(self.root.exists())
    def test_root_file_blocks(self):
        self.root.rmdir()
        self.root.write_text("NOT_FOLDER",encoding="utf-8")
        self.assertFalse(self.call()["exclusive_claim_created"])
    def test_relative_root_blocks(self):
        a=claim_once_lab(archive_root=Path("FX28_NY17_M15"),clock=lambda:CLOSED)
        self.assertFalse(a["exclusive_claim_created"])
    def test_existing_partial_window_archive_blocks(self):
        (self.root/(WINDOW+"_20261115T222001000Z")).mkdir()
        a=self.call()
        self.assertFalse(a["exclusive_claim_created"])
        self.assertEqual(a["prior_archive_or_claim_found"],1)
    def test_rehearsals_not_blocked(self):
        (self.root/"REHEARSAL_SUN_20261108_D1_old").mkdir()
        a=self.call()
        self.assertTrue(a["exclusive_claim_created"])
    def test_unsafe_existing_claim_never_replaced(self):
        marker=self.root/CLAIM_NAME
        marker.write_bytes(b"")
        a=self.call()
        self.assertFalse(a["exclusive_claim_created"])
        self.assertEqual(marker.stat().st_size,0)
    def test_no_rollback_after_single_claim(self):
        self.call()
        marker=self.root/CLAIM_NAME
        content=marker.read_bytes()
        for _ in range(3):
            self.assertFalse(self.call()["exclusive_claim_created"])
        self.assertEqual(marker.read_bytes(),content)
    def test_inspection_only_does_not_claim(self):
        a=inspect_claim_lab(archive_root=self.root)
        self.assertTrue(a["single_attempt_start_precheck_clear"])
        self.assertFalse(list(self.root.iterdir()))
    def test_parallel_20_requests_allow_exactly_one(self):
        # All workers share same real temp path and synthetic post-close time.
        with ThreadPoolExecutor(max_workers=20) as pool:
            results=list(pool.map(lambda _:self.call(),range(20)))
        self.assertEqual(sum(v["exclusive_claim_created"] for v in results),1)
        self.assertEqual(len(list(self.root.iterdir())),1)
        self.assertTrue(all(not v["trading_authorized"] for v in results))
    def test_eight_independent_spawned_processes_allow_one(self):
        """True multiprocess contention, not just GIL-controlled threads."""
        ctx=mp.get_context("spawn")
        barrier=ctx.Barrier(8)
        results=ctx.Queue()
        workers=[ctx.Process(target=_separate_process_claim,
            args=(str(self.root),barrier,results)) for _ in range(8)]
        for p in workers:
            p.start()
        for p in workers:
            p.join(timeout=25)
        try:
            self.assertFalse(any(p.is_alive() for p in workers))
            self.assertTrue(all(p.exitcode==0 for p in workers))
            self.assertEqual(sum(results.get(timeout=2) for _ in workers),1)
            self.assertEqual(len(list(self.root.iterdir())),1)
        finally:
            for p in workers:
                if p.is_alive():
                    p.terminate()
                    p.join(timeout=3)
            results.close()
    def test_different_timezone_clock_normalized_to_utc(self):
        tz=timezone(timedelta(hours=-4))
        dt=datetime(2026,11,15,18,20,tzinfo=tz)
        a=self.call(clock=lambda:dt)
        self.assertTrue(a["exclusive_claim_created"])
        data=json.loads((self.root/CLAIM_NAME).read_text(encoding="utf-8"))
        self.assertEqual(data["claimed_at_utc_local_clock_unattested"],CLOSED.isoformat())
if __name__=="__main__":unittest.main(verbosity=2)
