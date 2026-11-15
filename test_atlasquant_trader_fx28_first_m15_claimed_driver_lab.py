"""Offline mock tests for optional claimed FX28 M15 driver (NOT deployed)."""
from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone,timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from atlasquant_trader_fx28_first_m15_atomic_claim_lab import CLAIM_NAME,WINDOW
from atlasquant_trader_fx28_first_m15_claimed_driver_lab import run_claimed_first_m15_lab
from test_atlasquant_trader_fx28_first_m15_no_duplicate_precheck_lab import (
    StrictMock,TERMINAL,CLOSED,
)
from test_atlasquant_trader_fx28_first_m15_archive_census_readonly_lab import (
    OneCandleMock,
)

class DriverTests(unittest.TestCase):
    def setUp(self):
        self.tmp=TemporaryDirectory(prefix="AQ_CLAIMED_CAPTURE_MOCK_ONLY_")
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)/"FX28_NY17_M15"
        self.root.mkdir()
    def run_one(self,api,clock=lambda:CLOSED):
        return run_claimed_first_m15_lab(
            api,terminal_path=TERMINAL,output_root=self.root,clock=clock)
    def test_one_empty_cohort_created_as_28_documented_gaps(self):
        mock=StrictMock([])
        r=self.run_one(mock)
        self.assertEqual(r["state"],"LAB_CLAIMED_FIRST_M15_ZERO_PRICE_OBSERVED_NO_GO")
        self.assertEqual(r["reason"],"ZERO_OF_28_NOMINAL_BARS_NO_MARKET_PRICE_NO_RETRY")
        self.assertTrue(r["claim_created"])
        self.assertEqual(r["captured_m15_total"],0)
        self.assertEqual(r["missing_m15_total"],28)
        self.assertEqual(r["semantically_verified_symbols"],28)
        self.assertEqual(mock.calls.count("copy_rates_range"),28)
        self.assertTrue((self.root/CLAIM_NAME).is_file())
        self.assertFalse(r["trade_authorized"])
    def test_fully_observed_28_bars_are_structural_only(self):
        r=self.run_one(OneCandleMock())
        self.assertEqual(r["captured_m15_total"],28)
        self.assertEqual(r["missing_m15_total"],0)
        self.assertEqual(r["state"],"LAB_CLAIMED_FIRST_M15_ARCHIVE_CHECKED_NO_GO")
        self.assertFalse(r["prediction_witness_authenticated"])
        self.assertFalse(r["trade_authorized"])
    def test_partial_observation_is_not_full_capture(self):
        r=self.run_one(OneCandleMock(empty_symbol="EURUSD"))
        self.assertEqual(r["captured_m15_total"],27)
        self.assertEqual(r["missing_m15_total"],1)
        self.assertEqual(r["state"],"LAB_CLAIMED_FIRST_M15_PARTIAL_PRICE_OBSERVED_NO_GO")
        self.assertFalse(r["trade_authorized"])
    def test_no_second_call_to_mt5_after_completed_archive(self):
        first=StrictMock([])
        second=StrictMock([])
        a=self.run_one(first)
        b=self.run_one(second,clock=lambda:CLOSED+timedelta(minutes=1))
        self.assertTrue(a["claim_created"])
        self.assertFalse(b["claim_created"])
        self.assertEqual(second.calls,[])
        self.assertEqual(len(list(self.root.glob(WINDOW+"_*/manifest.json"))),1)
    def test_api_none_failure_does_not_burn_another_attempt(self):
        first=StrictMock(None)
        r=self.run_one(first)
        self.assertTrue(r["claim_created"])
        self.assertEqual(r["state"],"LAB_CLAIMED_FIRST_M15_NO_GO")
        self.assertEqual(r["collector_reason"],"MT5_HISTORY_QUERY_FAILED_NONE_EURUSD")
        self.assertTrue((self.root/CLAIM_NAME).exists())
        second=StrictMock([])
        attempt=self.run_one(second)
        self.assertFalse(attempt["claim_created"])
        self.assertEqual(second.calls,[])
        self.assertFalse(list(self.root.glob(WINDOW+"_*/manifest.json")))
    def test_before_m15_close_no_api_no_claim(self):
        fake=StrictMock([])
        r=self.run_one(fake,clock=lambda:datetime(2026,11,15,22,14,59,tzinfo=timezone.utc))
        self.assertFalse(r["claim_created"])
        self.assertEqual(fake.calls,[])
        self.assertFalse((self.root/CLAIM_NAME).exists())
    def test_next_day_late_m15_never_queries_mt5_or_creates_claim(self):
        fake=StrictMock([])
        late=datetime(2026,11,16,9,0,tzinfo=timezone.utc)
        r=self.run_one(fake,clock=lambda:late)
        self.assertEqual(r["reason"],"PROSPECTIVE_CLAIM_AFTER_DEADLINE_NO_BACKFILL")
        self.assertFalse(r["claim_created"])
        self.assertFalse(fake.calls)
        self.assertFalse((self.root/CLAIM_NAME).exists())
    def test_process_pause_after_claim_blocks_any_late_mt5_api(self):
        times=iter((CLOSED,datetime(2026,11,15,23,0,tzinfo=timezone.utc)))
        api=StrictMock([])
        r=self.run_one(api,clock=lambda:next(times))
        self.assertTrue(r["claim_created"])
        self.assertEqual(r["reason"],
                         "POST_CLAIM_CAPTURE_START_OUTSIDE_DEADLINE_NO_MT5_NO_RETRY")
        self.assertEqual(api.calls,[])
        self.assertTrue((self.root/CLAIM_NAME).exists())
        self.assertFalse(self.run_one(StrictMock([]))["claim_created"])

    def test_capture_finishes_after_deadline_archive_not_prospective(self):
        end=datetime(2026,11,15,23,0,tzinfo=timezone.utc)
        times=iter((CLOSED,CLOSED,CLOSED,end))
        api=OneCandleMock()
        r=self.run_one(api,clock=lambda:next(times))
        self.assertTrue(r["claim_created"])
        self.assertEqual(r["state"],"LAB_CLAIMED_FIRST_M15_NO_GO")
        self.assertEqual(r["reason"],
                         "POST_COLLECT_OUTSIDE_DEADLINE_PROSPECTIVE_REJECTED_NO_RETRY")
        self.assertEqual(r["captured_m15_total"],28)
        self.assertTrue(Path(r["archive_dir"]).exists())
        self.assertTrue((self.root/CLAIM_NAME).exists())
        self.assertFalse(r["trade_authorized"])

    def test_invalid_second_clock_does_not_touch_mt5(self):
        times=iter((CLOSED,None))
        api=StrictMock([])
        r=self.run_one(api,clock=lambda:next(times))
        self.assertTrue(r["claim_created"])
        self.assertEqual(r["reason"],"POST_CLAIM_CLOCK_INVALID_NO_MT5_NO_RETRY")
        self.assertEqual(api.calls,[])
        self.assertTrue((self.root/CLAIM_NAME).exists())

    def test_clock_backward_after_claim_blocks_mt5_before_any_api(self):
        initial=datetime(2026,11,15,22,55,tzinfo=timezone.utc)
        earlier=datetime(2026,11,15,22,40,tzinfo=timezone.utc)
        ticks=iter((initial,earlier))
        mock=StrictMock([])
        result=self.run_one(mock,clock=lambda:next(ticks))
        self.assertTrue(result["claim_created"])
        self.assertEqual(result["reason"],
                         "POST_CLAIM_CLOCK_MOVED_BACKWARDS_NO_MT5_NO_RETRY")
        self.assertEqual(mock.calls,[])
        self.assertTrue((self.root/CLAIM_NAME).exists())

    def test_backward_clock_inside_collector_blocks_before_mt5_initialize(self):
        ticks=iter((CLOSED,CLOSED,CLOSED-timedelta(seconds=1)))
        mock=StrictMock([])
        result=self.run_one(mock,clock=lambda:next(ticks))
        self.assertTrue(result["claim_created"])
        self.assertEqual(result["reason"],
                         "COLLECTOR_CLOCK_REGRESSED_OR_INVALID_NO_MT5_NO_RETRY")
        self.assertEqual(mock.calls,[])
        self.assertTrue((self.root/CLAIM_NAME).exists())

    def test_backward_clock_after_collector_rejects_prospective_status(self):
        newer=CLOSED+timedelta(seconds=20)
        older=CLOSED+timedelta(seconds=10)
        ticks=iter((CLOSED,CLOSED,newer,older))
        mock=OneCandleMock()
        result=self.run_one(mock,clock=lambda:next(ticks))
        self.assertEqual(result["reason"],
                         "POST_COLLECT_CLOCK_MOVED_BACKWARDS_NO_RETRY")
        self.assertEqual(result["captured_m15_total"],28)
        self.assertTrue(Path(result["archive_dir"]).exists())
        self.assertTrue((self.root/CLAIM_NAME).exists())
        self.assertFalse(result["trade_authorized"])

    def test_existing_incomplete_directory_blocks_preclaim(self):
        (self.root/(WINDOW+"_partial")).mkdir()
        fake=StrictMock([])
        r=self.run_one(fake)
        self.assertFalse(r["claim_created"])
        self.assertEqual(fake.calls,[])
    def test_existing_empty_claim_file_blocks(self):
        (self.root/CLAIM_NAME).write_bytes(b"")
        fake=StrictMock([])
        self.assertFalse(self.run_one(fake)["claim_created"])
        self.assertEqual(fake.calls,[])
    def test_concurrent_two_drivers_only_first_queries_mt5(self):
        a,b=StrictMock([]),StrictMock([])
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(self.run_one,(a,b)))
        self.assertEqual(sum(r["claim_created"] for r in results),1)
        self.assertEqual(a.calls.count("copy_rates_range")+b.calls.count("copy_rates_range"),28)
        self.assertEqual(len(list(self.root.glob(WINDOW+"_*/manifest.json"))),1)
    def test_invalid_archive_root_does_not_create_anything(self):
        self.root.rmdir()
        fake=StrictMock([])
        out=self.run_one(fake)
        self.assertFalse(out["claim_created"])
        self.assertFalse(self.root.exists())
        self.assertFalse(fake.calls)
    def test_other_valid_mt5_terminal_rejected_before_claim_or_mt5(self):
        wrong = r"C:\Program Files\Other Broker MetaTrader 5\terminal64.exe"
        fake = StrictMock([])
        result = run_claimed_first_m15_lab(
            fake, terminal_path=wrong, output_root=self.root,
            clock=lambda: CLOSED)
        self.assertEqual(result["reason"],"INVALID_CALL_PARAMETERS_NO_CLAIM")
        self.assertFalse(result["claim_created"])
        self.assertEqual(fake.calls,[])
        self.assertFalse((self.root/CLAIM_NAME).exists())
        # An invalid request does not consume the real frozen attempt.
        self.assertTrue(self.run_one(StrictMock([]))["claim_created"])

    def test_bad_terminal_path_rejected_before_burning_claim(self):
        fake=StrictMock([])
        out=run_claimed_first_m15_lab(fake,terminal_path="BAD",output_root=self.root,clock=lambda:CLOSED)
        self.assertFalse(out["claim_created"])
        self.assertEqual(out["reason"],"INVALID_CALL_PARAMETERS_NO_CLAIM")
        self.assertFalse((self.root/CLAIM_NAME).exists())
        self.assertEqual(fake.calls,[])
        self.assertTrue(self.run_one(StrictMock([]))["claim_created"])
if __name__=="__main__":unittest.main(verbosity=2)
