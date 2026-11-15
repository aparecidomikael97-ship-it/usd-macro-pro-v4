"""Standalone no-market-data tests for the FX28 first-M15 duplicate precheck."""
from __future__ import annotations
import tempfile
import unittest
from pathlib import Path
from datetime import datetime,timezone
from types import SimpleNamespace

from atlasquant_trader_fx28_first_m15_no_duplicate_precheck_lab import (
    WINDOW,check_no_prior_attempt_lab,
)
from atlasquant_trader_fx28_ny17_m15_writeonce_capture_lab import collect_window_lab

TERMINAL = r"C:\Program Files\Pepperstone MetaTrader 5\terminal64.exe"
CLOSED = datetime(2026,11,15,22,20,tzinfo=timezone.utc)

class StrictMock:
    TIMEFRAME_M15 = "synthetic-M15"
    def __init__(self, result):
        self.result = result
        self.calls = []
    def initialize(self, **kwargs):
        self.calls.append("initialize")
        return True
    def terminal_info(self):
        self.calls.append("terminal_info")
        return SimpleNamespace(connected=True)
    def symbol_info(self, symbol):
        self.calls.append("symbol_info")
        digits = 3 if symbol.endswith("JPY") else 5
        return SimpleNamespace(name=symbol,currency_base=symbol[:3],
            currency_profit=symbol[3:],digits=digits,
            point=10**(-digits),visible=True)
    def copy_rates_range(self, *args):
        self.calls.append("copy_rates_range")
        return self.result
    def shutdown(self):
        self.calls.append("shutdown")

class TestFirstM15NoDuplicate(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="aq_fx28_m15_preflight_")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "FX28_NY17_M15"
    def check(self):
        out = check_no_prior_attempt_lab(archive_root=self.root)
        self.assertFalse(out["concurrency_safe_atomic_lock_verified"])
        self.assertFalse(out["trading_authorized"])
        self.assertEqual(out["mt5_calls"],0)
        self.assertEqual(out["file_writes"],0)
        return out
    def test_missing_root_does_not_create_it(self):
        self.assertTrue(self.check()["single_attempt_start_precheck_clear"])
        self.assertFalse(self.root.exists())
    def test_empty_root_precheck_clear_but_not_atomic(self):
        self.root.mkdir()
        r=self.check()
        self.assertTrue(r["single_attempt_start_precheck_clear"])
        self.assertEqual(r["existing_candidate_count"],0)
    def test_existing_rehearsal_does_not_block(self):
        self.root.mkdir()
        (self.root/"REHEARSAL_SUN_20261108_D1_foo").mkdir()
        self.assertTrue(self.check()["single_attempt_start_precheck_clear"])
    def test_any_existing_window_archive_blocks(self):
        self.root.mkdir()
        (self.root/(WINDOW+"_20261115T222001000000Z")).mkdir()
        r=self.check()
        self.assertFalse(r["single_attempt_start_precheck_clear"])
        self.assertEqual(r["existing_candidate_count"],1)
        self.assertEqual(r["reason"],"ONE_OR_MORE_PREVIOUS_ATTEMPT_ARTIFACTS_EXIST_NO_SECOND_RUN")
    def test_partial_incomplete_capture_blocks(self):
        self.root.mkdir()
        f=self.root/(WINDOW+"_partial_no_manifest")
        f.mkdir()
        (f/"EURUSD_M15.csv").write_text("HEADER_ONLY",encoding="utf-8")
        self.assertFalse(self.check()["single_attempt_start_precheck_clear"])
    def test_alternate_case_matches_windows(self):
        self.root.mkdir()
        (self.root/(WINDOW.lower()+"_case_variant")).mkdir()
        self.assertFalse(self.check()["single_attempt_start_precheck_clear"])
    def test_existing_window_file_blocks(self):
        self.root.mkdir()
        (self.root/(WINDOW+"_incomplete")).write_text("FAILED",encoding="utf-8")
        self.assertFalse(self.check()["single_attempt_start_precheck_clear"])
    def test_multiple_archives_reported_not_reissued(self):
        self.root.mkdir()
        for i in range(2):
            (self.root/(WINDOW+"_20261115T22200"+str(i)+"Z")).mkdir()
        r=self.check()
        self.assertEqual(r["existing_candidate_count"],2)
        self.assertFalse(r["single_attempt_start_precheck_clear"])
    def test_window_only_directory_also_blocks(self):
        self.root.mkdir()
        (self.root/WINDOW).mkdir()
        self.assertFalse(self.check()["single_attempt_start_precheck_clear"])
    def test_unrelated_prefix_does_not_count(self):
        self.root.mkdir()
        (self.root/"CAMPAIGN_FIRST_D1_20261115_fake").mkdir()
        self.assertTrue(self.check()["single_attempt_start_precheck_clear"])
    def test_file_as_root_blocks(self):
        self.root.write_text("badroot",encoding="utf-8")
        self.assertFalse(self.check()["single_attempt_start_precheck_clear"])
    def test_relative_path_rejected(self):
        result=check_no_prior_attempt_lab(archive_root=Path("FX28_NY17_M15"))
        self.assertFalse(result["single_attempt_start_precheck_clear"])
    def test_unknown_window_rejected(self):
        result=check_no_prior_attempt_lab(archive_root=self.root,window="REHEARSAL_SUN_20261108_D1")
        self.assertFalse(result["single_attempt_start_precheck_clear"])
    def test_capture_from_mock_is_seen_by_guard_before_second_try(self):
        self.root.mkdir()
        api=StrictMock([])
        r=collect_window_lab(api,window=WINDOW,terminal_path=TERMINAL,
            output_root=self.root,clock=lambda:CLOSED)
        self.assertEqual(r["captured_symbols"],28)
        self.assertEqual(api.calls.count("copy_rates_range"),28)
        result=self.check()
        self.assertEqual(result["existing_candidate_count"],1)
        self.assertFalse(result["single_attempt_start_precheck_clear"])

if __name__ == "__main__":unittest.main(verbosity=2)
