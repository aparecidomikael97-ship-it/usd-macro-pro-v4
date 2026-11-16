"""Synthetic MT5 doubles only; never real Pepperstone candles or forecasts."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest

from atlasquant_trader_fx28_ny17_m15_writeonce_capture_lab import (
    PAIRS, WINDOWS, collect_window_lab, verify_archive_lab, SCHEMA,
)

UTC = timezone.utc
HIST = "REHEARSAL_TUE_20261110_D1"
SUN = "REHEARSAL_SUN_20261108_D1"
FUTURE = "CAMPAIGN_FIRST_M15_20261115"
CLOCK = datetime(2026, 11, 14, 22, tzinfo=UTC)
TERMINAL = r"C:\Program Files\Pepperstone MetaTrader 5\terminal64.exe"


class FakeMT5:
    TIMEFRAME_M15 = 15

    def __init__(self, *, gaps=None, defective=None, missing=None):
        self.calls = []
        self.gaps = gaps or {}
        self.defective = defective
        self.missing = missing

    def initialize(self, *, path, timeout):
        self.calls.append("initialize")
        return True

    def terminal_info(self):
        self.calls.append("terminal_info")
        return SimpleNamespace(connected=True)

    def symbol_info(self, symbol):
        self.calls.append("symbol_info")
        if symbol == self.missing:
            return None
        digits = 3 if symbol.endswith("JPY") else 5
        return SimpleNamespace(
            name=symbol, currency_base=symbol[:3],
            currency_profit=symbol[3:], digits=digits,
            point=0.001 if digits == 3 else 0.00001, visible=False)

    def copy_rates_range(self, symbol, timeframe, start, end):
        self.calls.append("copy_rates_range")
        if self.defective == "no_bars" and symbol == "EURUSD":
            return None
        if self.defective == "empty_array" and symbol == "EURUSD":
            return []
        stamps = list(range(int(start.timestamp()), int(end.timestamp()) + 1, 900))
        stamps = [t for t in stamps if t not in self.gaps.get(symbol, set())]
        if self.defective == "duplicate" and symbol == "EURUSD":
            stamps.insert(2, stamps[1])
        if self.defective == "unsorted" and symbol == "EURUSD":
            stamps[0], stamps[1] = stamps[1], stamps[0]
        if self.defective == "bad_ohlc" and symbol == "EURUSD":
            high, low = 1.20, 1.25
        else:
            high, low = 1.25, 1.20
        price = 151.234 if symbol.endswith("JPY") else 1.23456
        if symbol.endswith("JPY"):
            high, low = 151.250, 151.200
        return [{"time":t, "open":price, "high":high, "low":low,
                 "close":price, "tick_volume":1, "spread":0,
                 "real_volume":0} for t in stamps]

    def shutdown(self):
        self.calls.append("shutdown")


class Fx28ReadOnlyWriteOnceTests(unittest.TestCase):
    def run_capture(self, fake, root, *, window=HIST, clock=CLOCK):
        return collect_window_lab(fake, window=window, terminal_path=TERMINAL,
                                  output_root=root, clock=lambda: clock)

    def test_01_nominal_28_pairs_and_frozen_choices(self):
        self.assertEqual(len(PAIRS), 28)
        self.assertEqual(len(set(PAIRS)), 28)
        self.assertEqual(len(WINDOWS), 5)
        self.assertEqual(WINDOWS[FUTURE],
                         ("2026-11-15T22:00:00+00:00",
                          "2026-11-15T22:15:00+00:00"))

    def test_02_future_first_m15_blocks_before_mt5_and_files(self):
        with TemporaryDirectory() as folder:
            root = Path(folder) / "capture"
            api = FakeMT5()
            r = self.run_capture(api, root, window=FUTURE)
            self.assertEqual(r["reason"], "FROZEN_WINDOW_NOT_YET_CLOSED_NO_MT5_IO")
            self.assertEqual(api.calls, [])
            self.assertFalse(root.exists())
            self.assertFalse(r["trade_authorized"])

    def test_03_first_m15_exact_close_synthetic_only(self):
        with TemporaryDirectory() as folder:
            root = Path(folder) / "capture"
            api = FakeMT5()
            r = self.run_capture(api, root, window=FUTURE,
                                 clock=datetime(2026,11,15,22,15,tzinfo=UTC))
            self.assertEqual(r["captured_symbols"], 28)
            self.assertEqual(r["captured_m15_total"], 28)
            self.assertEqual(r["missing_m15_total"], 0)
            self.assertEqual(r["fully_covered_symbols"], 28)
            self.assertEqual(api.calls.count("initialize"), 1)
            self.assertEqual(api.calls.count("shutdown"), 1)
            proof = verify_archive_lab(Path(r["archive_dir"]))
            self.assertEqual(proof["symbol_hashes_verified"], 28)
            self.assertFalse(proof["source_first_seen_attested"])

    def test_04_complete_historical_28x96_writeonce_and_hashes(self):
        with TemporaryDirectory() as folder:
            root=Path(folder) / "capture"
            api=FakeMT5()
            r=self.run_capture(api,root)
            self.assertEqual(r["schema"],SCHEMA)
            self.assertEqual(r["state"],"LAB_FX28_M15_ARCHIVE_COMPLETE_CLAIM_ONLY_NO_GO")
            self.assertEqual(r["captured_symbols"],28)
            self.assertEqual(r["captured_m15_total"],2688)
            self.assertEqual(r["fully_covered_symbols"],28)
            self.assertEqual(len(r["sha256_by_symbol"]),28)
            p=verify_archive_lab(Path(r["archive_dir"]))
            self.assertEqual(p["manifest_sha256"],r["manifest_sha256"])
            self.assertEqual(p["missing_m15_total"],0)
            self.assertEqual(api.calls.count("shutdown"),1)
            self.assertFalse(r["pre_event_forecasts_authenticated"])

            again=FakeMT5()
            duplicate=self.run_capture(again,root)
            self.assertEqual(duplicate["reason"],"WRITE_ONCE_DIRECTORY_ALREADY_EXISTS")
            self.assertEqual(again.calls,[])

    def test_05_missing_internal_bars_preserved_not_interpolated(self):
        with TemporaryDirectory() as folder:
            root=Path(folder) / "capture"
            start=datetime.fromisoformat(WINDOWS[HIST][0])
            gaps={int((start+timedelta(hours=2)).timestamp()),
                  int((start+timedelta(hours=2,minutes=15)).timestamp())}
            r=self.run_capture(FakeMT5(gaps={"GBPUSD":gaps}),root)
            self.assertEqual(r["state"],"LAB_FX28_M15_ARCHIVE_WITH_GAPS_NO_GO")
            self.assertEqual(r["captured_m15_total"],2686)
            self.assertEqual(r["missing_m15_total"],2)
            self.assertEqual(r["fully_covered_symbols"],27)
            audit=verify_archive_lab(Path(r["archive_dir"]))
            self.assertEqual(audit["missing_m15_total"],2)
            self.assertEqual(audit["fully_covered_symbols"],27)

    def test_06_missing_whole_pair_is_not_dropped_from_denominator(self):
        with TemporaryDirectory() as folder:
            root=Path(folder) / "capture"
            r=self.run_capture(FakeMT5(defective="empty_array"),root)
            self.assertEqual(r["captured_symbols"],28)
            self.assertEqual(r["captured_m15_total"],27*96)
            self.assertEqual(r["missing_m15_total"],96)
            self.assertEqual(r["fully_covered_symbols"],27)
            audit=verify_archive_lab(Path(r["archive_dir"]))
            self.assertEqual(audit["symbol_hashes_verified"],28)

    def test_07_missing_symbol_fails_before_any_file_write(self):
        with TemporaryDirectory() as folder:
            root=Path(folder) / "capture"
            api=FakeMT5(missing="EURUSD")
            r=self.run_capture(api,root)
            self.assertEqual(r["reason"],"SYMBOL_METADATA_MISSING_EURUSD")
            self.assertFalse(root.exists())
            self.assertEqual(api.calls[-1],"shutdown")

    def test_08_duplicate_unsorted_and_invalid_ohlc_block(self):
        for defect in ("duplicate","unsorted","bad_ohlc"):
            with self.subTest(defect=defect), TemporaryDirectory() as folder:
                root=Path(folder) / "capture"
                r=self.run_capture(FakeMT5(defective=defect),root)
                self.assertTrue(r["reason"].startswith("READONLY_MT5_OR_CANDLE_CHECK_FAILED"))
                self.assertFalse(root.exists())

    def test_09_hash_tamper_is_detected_without_backfilling(self):
        with TemporaryDirectory() as folder:
            root=Path(folder) / "capture"
            r=self.run_capture(FakeMT5(),root)
            p=Path(r["archive_dir"])/"EURUSD_M15.csv"
            p.write_bytes(p.read_bytes()+b"MODIFIED")
            with self.assertRaisesRegex(ValueError,"CSV_SHA256_MISMATCH_EURUSD"):
                verify_archive_lab(Path(r["archive_dir"]))

    def test_10_full_week_28x480_synthetic_history(self):
        with TemporaryDirectory() as folder:
            root=Path(folder) / "capture"
            window="CAMPAIGN_FIRST_W1_20261115"
            after=datetime(2026,11,20,22,tzinfo=UTC)
            r=self.run_capture(FakeMT5(),root,window=window,clock=after)
            self.assertEqual(r["expected_m15_per_symbol"],480)
            self.assertEqual(r["captured_m15_total"],13440)
            self.assertEqual(verify_archive_lab(Path(r["archive_dir"]))["fully_covered_symbols"],28)

    def test_11_bad_or_naive_clock_and_unknown_window_block_no_io(self):
        cases=[(HIST,datetime(2026,11,14,22)),
               ("UNKNOWN",CLOCK)]
        for window,clock in cases:
            with self.subTest(window=window),TemporaryDirectory() as folder:
                api=FakeMT5()
                r=self.run_capture(api,Path(folder)/"capture",window=window,clock=clock)
                self.assertEqual(api.calls,[])
                self.assertEqual(r["state"],"LAB_FX28_M15_CAPTURE_BLOCKED")
                self.assertFalse(r["trade_authorized"])


    def test_12_none_from_mt5_is_api_failure_not_96_missing_bars(self):
        with TemporaryDirectory() as folder:
            root=Path(folder)/"capture"
            api=FakeMT5(defective="no_bars")
            r=self.run_capture(api,root)
            self.assertEqual(r["state"],"LAB_FX28_M15_CAPTURE_BLOCKED")
            self.assertEqual(r["reason"],"MT5_HISTORY_QUERY_FAILED_NONE_EURUSD")
            self.assertEqual(r["captured_symbols"],0)
            self.assertIsNone(r["missing_m15_total"])
            self.assertFalse(root.exists())
            self.assertEqual(api.calls[-1],"shutdown")

    def test_13_legacy_with_nonempty_archive_is_readable(self):
        import json
        with TemporaryDirectory() as folder:
            root=Path(folder)/"capture"
            r=self.run_capture(FakeMT5(),root)
            path=Path(r["archive_dir"])
            manifest_path=path/"manifest.json"
            m=json.loads(manifest_path.read_text(encoding="utf-8"))
            for row in m["files"].values():
                row.pop("mt5_query_returned_none")
            manifest_path.write_text(json.dumps(m),encoding="utf-8")
            verified=verify_archive_lab(path)
            self.assertEqual(verified["symbol_hashes_verified"],28)
            self.assertEqual(verified["missing_m15_total"],0)

    def test_14_legacy_with_empty_unverified_query_fails_closed(self):
        import json
        with TemporaryDirectory() as folder:
            root=Path(folder)/"capture"
            r=self.run_capture(FakeMT5(defective="empty_array"),root)
            path=Path(r["archive_dir"])
            manifest_path=path/"manifest.json"
            m=json.loads(manifest_path.read_text(encoding="utf-8"))
            m["files"]["EURUSD"].pop("mt5_query_returned_none")
            manifest_path.write_text(json.dumps(m),encoding="utf-8")
            with self.assertRaisesRegex(ValueError,"LEGACY_EMPTY_MT5_QUERY_UNVERIFIABLE_EURUSD"):
                verify_archive_lab(path)

    def test_15_manifest_must_not_claim_none_query_as_verified_market_gap(self):
        import json
        with TemporaryDirectory() as folder:
            root=Path(folder)/"capture"
            r=self.run_capture(FakeMT5(),root)
            path=Path(r["archive_dir"])
            manifest_path=path/"manifest.json"
            m=json.loads(manifest_path.read_text(encoding="utf-8"))
            m["files"]["EURUSD"]["mt5_query_returned_none"]=True
            manifest_path.write_text(json.dumps(m),encoding="utf-8")
            with self.assertRaisesRegex(ValueError,"MANIFEST_CSV_GAP_DISAGREEMENT_EURUSD"):
                verify_archive_lab(path)


    def test_16_endpoint_flags_immutable_against_empty_pair_csv(self):
        """A missing real first/last bar must not be claimed present.

        All rows here are fake MT5 return values; no broker calls.
        """
        import json
        mutations = (
            ("first_expected_open_present", True),
            ("last_expected_open_present", True),
            ("first_expected_open_present", 1),
            ("last_expected_open_present", 0),
            ("first_expected_open_present", "REMOVE"),
            ("last_expected_open_present", "REMOVE"),
        )
        for field, value in mutations:
            with self.subTest(field=field, value=value), TemporaryDirectory() as folder:
                root = Path(folder) / "mock_capture"
                r = self.run_capture(FakeMT5(defective="empty_array"), root)
                self.assertEqual(r["captured_m15_total"], 27 * 96)
                archive = Path(r["archive_dir"])
                manifest_file = archive / "manifest.json"
                m = json.loads(manifest_file.read_text(encoding="utf-8"))
                self.assertIs(m["files"]["EURUSD"]["first_expected_open_present"], False)
                self.assertIs(m["files"]["EURUSD"]["last_expected_open_present"], False)
                if value == "REMOVE":
                    m["files"]["EURUSD"].pop(field)
                else:
                    m["files"]["EURUSD"][field] = value
                manifest_file.write_text(json.dumps(m), encoding="utf-8")
                with self.assertRaisesRegex(
                    ValueError, "MANIFEST_CSV_GAP_DISAGREEMENT_EURUSD"
                ):
                    verify_archive_lab(archive)

    def test_17_first_and_last_wickless_m15_open_timestamps_stay_missing(self):
        """Actual missing M15 opening epochs make both flags false, never shifted."""
        import json
        start = datetime.fromisoformat(WINDOWS[HIST][0])
        end = datetime.fromisoformat(WINDOWS[HIST][1])
        first, last = int(start.timestamp()), int(end.timestamp()) - 900
        with TemporaryDirectory() as folder:
            root = Path(folder) / "mock_capture"
            r = self.run_capture(
                FakeMT5(gaps={"EURUSD": {first, last}}), root
            )
            self.assertEqual(r["missing_m15_total"], 2)
            archive = Path(r["archive_dir"])
            self.assertEqual(verify_archive_lab(archive)["missing_m15_total"], 2)
            m = json.loads((archive / "manifest.json").read_text(encoding="utf-8"))
            self.assertIs(m["files"]["EURUSD"]["first_expected_open_present"], False)
            self.assertIs(m["files"]["EURUSD"]["last_expected_open_present"], False)
            self.assertEqual(m["files"]["EURUSD"]["missing_open_epochs_utc"],
                             [first, last])



if __name__ == "__main__":
    unittest.main()
