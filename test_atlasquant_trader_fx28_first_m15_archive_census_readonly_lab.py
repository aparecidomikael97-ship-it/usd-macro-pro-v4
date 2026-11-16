"""Offline FX28 M15 archive postflight census regression, synthetic MT5 only.

All writes are by the existing lab collector into auto-removed temp folders.
The census itself only reads. Never fetch prices, contact MT5 or trade.
"""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import json, unittest

from atlasquant_trader_fx28_first_m15_archive_census_readonly_lab import (
    WINDOW, inspect_first_m15_archive_census_lab as audit,
)
from atlasquant_trader_fx28_ny17_m15_writeonce_capture_lab import collect_window_lab
from atlasquant_trader_fx28_first_m15_atomic_claim_lab import CLAIM_NAME, claim_once_lab
from test_atlasquant_trader_fx28_first_m15_no_duplicate_precheck_lab import (
    StrictMock, TERMINAL, CLOSED,
)
UTC = timezone.utc
EARLY = datetime(2026,11,15,22,14,59,tzinfo=UTC)
STAMPED = datetime(2026,11,15,22,20,12,123456,tzinfo=UTC)

class OneCandleMock(StrictMock):
    def __init__(self, *, empty_symbol=None):
        super().__init__([])
        self.empty_symbol=empty_symbol
    def copy_rates_range(self, symbol, timeframe, start, end):
        self.calls.append("copy_rates_range")
        if self.empty_symbol == symbol:
            return []
        jpy=symbol.endswith("JPY")
        base=151.234 if jpy else 1.23456
        delta=0.005 if jpy else 0.00005
        return [{
            "time":int(start.timestamp()),
            "open":base,
            "high":round(base+delta,5),
            "low":round(base-delta,5),
            "close":base,
            "tick_volume":8,
            "spread":2,
            "real_volume":0,
        }]

class FX28M15ArchiveCensusTests(unittest.TestCase):
    def setUp(self):
        self.tmp=TemporaryDirectory(prefix="AQ_FIRST_M15_CENSUS_SYNTH_")
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)/"FX28_NY17_M15"
    def inspect(self,at=CLOSED):
        out=audit(archive_root=self.root,inspected_at_utc=at)
        self.assertEqual(out["expected_pair_count"],28)
        self.assertEqual(out["expected_candles_in_frozen_window"],28)
        self.assertFalse(out["trade_authorized"])
        self.assertFalse(out["publishable"])
        self.assertFalse(out["broker_source_independently_authenticated"])
        self.assertFalse(out["pre_event_forecast_witness_checked"])
        self.assertTrue(out["campaign_672_slots_untouched"])
        self.assertEqual((out["mt5_calls"],out["file_writes"],out["http_requests"]),(0,0,0))
        return out
    def mock_archive(self,api=None,stamp=CLOSED):
        fake=api if api is not None else StrictMock([])
        result=collect_window_lab(
            fake,window=WINDOW,terminal_path=TERMINAL,
            output_root=self.root,clock=lambda:stamp)
        return fake,result
    def test_01_before_closed_no_read_archive_or_create_root(self):
        r=self.inspect(at=EARLY)
        self.assertEqual(r["state"],"LAB_FX28_FIRST_M15_WINDOW_NOT_CLOSED_NO_GO")
        self.assertFalse(self.root.exists())
    def test_02_missing_root_unknown_not_claim_no_attempt(self):
        r=self.inspect()
        self.assertEqual(r["state"],"LAB_FX28_FIRST_M15_ARCHIVE_NOT_OBSERVED_NO_GO")
        self.assertEqual(r["candidate_window_artifact_count"],0)
        self.assertFalse(self.root.exists())
    def test_03_empty_root_no_archive_still_unknown(self):
        self.root.mkdir()
        r=self.inspect()
        self.assertEqual(r["candidate_window_artifact_count"],0)
        self.assertEqual(r["source_observation_class"],"UNKNOWN")
    def test_04_all_28_empty_arrays_are_price_insufficient_not_complete(self):
        api,res=self.mock_archive()
        self.assertEqual(api.calls.count("copy_rates_range"),28)
        self.assertEqual(res["missing_m15_total"],28)
        r=self.inspect()
        self.assertEqual(r["candidate_window_artifact_count"],1)
        self.assertEqual(r["symbol_hashes_verified"],28)
        self.assertEqual(r["m15_rows_semantically_verified"],0)
        self.assertEqual(r["missing_expected_m15_open_count"],28)
        self.assertTrue(r["all_28_nominal_m15_missing"])
        self.assertEqual(r["state"],"LAB_FX28_FIRST_M15_ALL_28_MISSING_PRICE_INSUFFICIENT_NO_GO")
    def test_05_actual_microsecond_capture_name_is_allowed(self):
        api,res=self.mock_archive(stamp=STAMPED)
        self.assertEqual(res["captured_symbols"],28)
        r=self.inspect(at=STAMPED+timedelta(seconds=1))
        self.assertEqual(r["state"],"LAB_FX28_FIRST_M15_ALL_28_MISSING_PRICE_INSUFFICIENT_NO_GO")
    def test_06_one_none_api_failure_not_convertible_to_gaps(self):
        api,res=self.mock_archive(StrictMock(None))
        self.assertEqual(res["reason"],"MT5_HISTORY_QUERY_FAILED_NONE_EURUSD")
        self.assertFalse(self.root.exists())
        self.assertEqual(api.calls.count("copy_rates_range"),1)
        self.assertEqual(self.inspect()["candidate_window_artifact_count"],0)
        self.assertEqual(self.inspect()["missing_expected_m15_open_count"],None)
    def test_07_one_valid_bar_per_pair_still_not_broker_attested(self):
        _,res=self.mock_archive(OneCandleMock())
        self.assertEqual(res["captured_m15_total"],28)
        r=self.inspect()
        self.assertEqual(r["state"],"LAB_FX28_FIRST_M15_STRUCTURAL_BARS_ONLY_NO_GO")
        self.assertEqual((r["m15_rows_semantically_verified"],r["missing_expected_m15_open_count"]),(28,0))
        self.assertFalse(r["broker_source_independently_authenticated"])
    def test_08_one_pair_missing_keeps_denominator_28(self):
        _,res=self.mock_archive(OneCandleMock(empty_symbol="EURUSD"))
        self.assertEqual(res["missing_m15_total"],1)
        r=self.inspect()
        self.assertEqual(r["state"],"LAB_FX28_FIRST_M15_PARTIAL_MISSING_PRICE_NO_GO")
        self.assertEqual((r["m15_rows_semantically_verified"],r["missing_expected_m15_open_count"]),(27,1))
    def test_09_duplicate_candidate_directory_blocks_even_if_one_verified(self):
        self.mock_archive()
        (self.root/(WINDOW+"_second_attempt_partial")).mkdir()
        r=self.inspect()
        self.assertEqual(r["candidate_window_artifact_count"],2)
        self.assertEqual(r["reason"],"MULTIPLE_WINDOW_ARTIFACTS_NO_GO_NO_SECOND_CAPTURE")
        self.assertEqual(r["symbol_hashes_verified"],0)
    def test_10_single_partial_directory_does_not_claim_no_bars(self):
        self.root.mkdir()
        (self.root/(WINDOW+"_20261115T221959000000Z")).mkdir()
        r=self.inspect()
        self.assertEqual(r["candidate_window_artifact_count"],1)
        self.assertEqual(r["reason"],"ARCHIVE_INSPECTION_EXCEPTION_FAIL_CLOSED")
        self.assertIsNone(r["all_28_nominal_m15_missing"])
    def test_11_bad_archive_name_blocks(self):
        self.root.mkdir()
        (self.root/(WINDOW+"_invalid_timestamp")).mkdir()
        r=self.inspect()
        self.assertEqual(r["reason"],"WINDOW_ARCHIVE_NAME_NOT_CANONICAL")
    def test_12_mutated_csv_hash_is_blocked(self):
        _,res=self.mock_archive()
        folder=Path(res["archive_dir"])
        with (folder/"EURUSD_M15.csv").open("ab") as f:
            f.write(b"extra byte")
        r=self.inspect()
        self.assertEqual(r["reason"],"ARCHIVE_INSPECTION_EXCEPTION_FAIL_CLOSED")
    def test_13_mutated_manifest_gap_flag_is_blocked(self):
        _,res=self.mock_archive()
        f=Path(res["archive_dir"])/"manifest.json"
        manifest=json.loads(f.read_text(encoding="utf-8"))
        manifest["files"]["EURUSD"]["first_expected_open_present"]=True
        f.write_text(json.dumps(manifest),encoding="utf-8")
        r=self.inspect()
        self.assertEqual(r["reason"],"ARCHIVE_INSPECTION_EXCEPTION_FAIL_CLOSED")
    def test_14_modified_manifest_capture_clock_mismatch_is_blocked(self):
        _,res=self.mock_archive()
        f=Path(res["archive_dir"])/"manifest.json"
        manifest=json.loads(f.read_text(encoding="utf-8"))
        manifest["retrieved_at_utc_local_clock_claim"]="2026-11-15T22:20:01+00:00"
        f.write_text(json.dumps(manifest),encoding="utf-8")
        r=self.inspect()
        self.assertEqual(r["reason"],"ARCHIVE_NAME_AND_RETRIEVAL_CLOCK_DISAGREE")
    def test_15_name_claims_archive_before_window_close(self):
        _,res=self.mock_archive()
        path=Path(res["archive_dir"])
        path.rename(self.root/(WINDOW+"_20261115T221000000000Z"))
        r=self.inspect()
        self.assertEqual(r["reason"],"ARCHIVE_NAMED_TIME_OUTSIDE_COMPLETED_WINDOW")
    def test_16_rehearsal_does_not_count_as_first_real_window(self):
        self.root.mkdir()
        (self.root/"REHEARSAL_SUN_20261108_D1_20261108T222000000000Z").mkdir()
        r=self.inspect()
        self.assertEqual(r["candidate_window_artifact_count"],0)
    def test_17_wrong_window_only_directory_is_rejected(self):
        self.root.mkdir()
        (self.root/WINDOW).mkdir()
        r=self.inspect()
        self.assertEqual(r["reason"],"WINDOW_ARCHIVE_NAME_NOT_CANONICAL")
    def test_18_future_inspection_clock_naive_rejected(self):
        r=audit(archive_root=self.root,inspected_at_utc=datetime(2026,11,15,22,30))
        self.assertEqual(r["reason"],"INVALID_ROOT_OR_INSPECTION_CLOCK")
    def test_19_root_symlink_rejected_where_system_allows(self):
        self.root.parent.mkdir(exist_ok=True)
        target=self.root.parent/"target";target.mkdir()
        try:self.root.symlink_to(target,target_is_directory=True)
        except (OSError,NotImplementedError) as exc:self.skipTest("No symlink privilege: "+str(exc))
        r=audit(archive_root=self.root,inspected_at_utc=CLOSED)
        self.assertEqual(r["reason"],"INVALID_ROOT_OR_INSPECTION_CLOCK")
    def test_20_no_markets_or_network_in_report(self):
        self.mock_archive()
        r=self.inspect()
        self.assertIsNone(r["validated_accuracy"])
        self.assertIsNone(r["valid_directional_bias"])
        self.assertEqual(r["source_observation_class"],"28_VALID_EMPTY_ARRAY_CLAIMS_LOCAL_ONLY")

    def test_21_valid_claim_marker_and_one_archive_is_not_duplicate(self):
        self.root.mkdir()
        claim=claim_once_lab(archive_root=self.root,clock=lambda:STAMPED)
        self.assertTrue(claim["exclusive_claim_created"])
        _,capture=self.mock_archive(stamp=STAMPED)
        self.assertEqual(capture["missing_m15_total"],28)
        r=self.inspect(at=STAMPED+timedelta(seconds=1))
        self.assertTrue(r["attempt_claim_marker_present"])
        self.assertEqual(len(r["attempt_claim_marker_sha256"]),64)
        self.assertEqual(r["candidate_window_artifact_count"],1)
        self.assertEqual(r["state"],"LAB_FX28_FIRST_M15_ALL_28_MISSING_PRICE_INSUFFICIENT_NO_GO")
        self.assertFalse(r["broker_source_independently_authenticated"])
    def test_22_claim_without_archive_is_no_go_and_no_retry(self):
        self.root.mkdir()
        claim=claim_once_lab(archive_root=self.root,clock=lambda:STAMPED)
        self.assertTrue(claim["exclusive_claim_created"])
        r=self.inspect(at=STAMPED+timedelta(seconds=1))
        self.assertTrue(r["attempt_claim_marker_present"])
        self.assertEqual(r["candidate_window_artifact_count"],0)
        self.assertEqual(r["reason"],"ATTEMPT_CLAIM_EXISTS_WITHOUT_ARCHIVE_NO_RETRY")
        self.assertIsNone(r["all_28_nominal_m15_missing"])
    def test_23_corrupt_claim_and_valid_archive_must_block(self):
        self.mock_archive(stamp=STAMPED)
        (self.root/CLAIM_NAME).write_text("invalid json",encoding="utf-8")
        r=self.inspect(at=STAMPED+timedelta(seconds=1))
        self.assertEqual(r["state"],"LAB_FX28_FIRST_M15_ARCHIVE_CENSUS_BLOCKED_NO_GO")
        self.assertEqual(r["symbol_hashes_verified"],0)
        self.assertIsNone(r["missing_expected_m15_open_count"])
    def test_24_claim_with_two_archives_remains_duplicate(self):
        self.root.mkdir()
        self.assertTrue(claim_once_lab(archive_root=self.root,clock=lambda:STAMPED)["exclusive_claim_created"])
        self.mock_archive(stamp=STAMPED)
        (self.root/(WINDOW+"_second_attempt_partial")).mkdir()
        r=self.inspect(at=STAMPED+timedelta(seconds=1))
        self.assertEqual(r["candidate_window_artifact_count"],2)
        self.assertEqual(r["reason"],"MULTIPLE_WINDOW_ARTIFACTS_NO_GO_NO_SECOND_CAPTURE")

if __name__=="__main__":
    unittest.main(verbosity=2)
