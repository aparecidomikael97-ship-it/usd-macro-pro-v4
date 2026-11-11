"""Synthetic contracts only; no MT5 package, terminal, market data or trades."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
import json
import tempfile
import unittest

from atlasquant_trader_ppi_mt5_m15_capture_lab import (
    EXPECTED_EPOCHS, SCHEMA, collect_ppi_mt5_m15_capture_lab as collect,
    load_local_receipt_lab,
)
from atlasquant_trader_ppi_usd_fx_forward_reaction_lab import (
    BASELINE_OPEN_UTC, LAST_REQUIRED_CLOSE_UTC, USD_FX,
    inspect_ppi_fx_m15_forward_reaction_lab,
)


NOW = LAST_REQUIRED_CLOSE_UTC + timedelta(minutes=5)
TERMINAL = r"C:\Program Files\MetaTrader 5\terminal64.exe"


class FakeMT5:
    TIMEFRAME_M15 = 15

    def __init__(self):
        self.calls: list[tuple] = []
        self.connected = True
        self.visible = set(USD_FX)
        self.data = {}
        for sym in USD_FX:
            self.data[sym] = [
                {"time": stamp, "open": 1.1, "high": 1.11, "low": 1.09,
                 "close": 1.1, "tick_volume": 20, "spread": 8, "real_volume": 0}
                for stamp in EXPECTED_EPOCHS
            ]

    def initialize(self, *, path, timeout):
        self.calls.append(("initialize", path, timeout))
        return self.connected

    def terminal_info(self):
        self.calls.append(("terminal_info",))
        return SimpleNamespace(connected=self.connected)

    def symbol_info(self, sym):
        self.calls.append(("symbol_info", sym))
        return SimpleNamespace(visible=sym in self.visible)

    def copy_rates_range(self, sym, timeframe, begin, end):
        self.calls.append(("copy_rates_range", sym, timeframe, begin, end))
        return deepcopy(self.data[sym])

    def shutdown(self):
        self.calls.append(("shutdown",))


class SevenPairCaptureTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name) / "AtlasQuant" / "LAB" / "PPI_20261113_MT5"
        self.api = FakeMT5()

    def run_capture(self, *, now=NOW, terminal=TERMINAL, root=None, api=None):
        return collect(
            self.api if api is None else api,
            terminal_path=terminal,
            output_root=self.root if root is None else root,
            clock=lambda: now,
        )

    def safe(self, result):
        self.assertFalse(result["trade_authorized"])
        self.assertFalse(result["publishable"])
        self.assertFalse(result["scheduler_enabled"])
        self.assertFalse(result["mt5_account_information_accessed"])
        self.assertFalse(result["orders_or_positions_accessed"])
        self.assertFalse(result["symbol_visibility_changed"])
        self.assertFalse(result["broker_identity_independently_authenticated"])
        self.assertFalse(result["candle_utc_independently_authenticated"])
        self.assertFalse(result["point_in_time_market_data_attested"])
        self.assertEqual(result["operational_bias"], "AGUARDAR")
        self.assertEqual(result["new_cost_brl"], 0)

    def blocked(self, result, reason=None):
        self.safe(result)
        self.assertEqual(result["state"], "LAB_PPI_MT5_CAPTURE_BLOCKED")
        self.assertEqual(result["validated_bars"], 0)
        self.assertEqual(result["local_files_written"], 0)
        self.assertFalse(self.root.exists())
        if reason:
            self.assertEqual(result["reason"], reason)

    def test_success_writes_exactly_seven_csv_files_and_manifest(self):
        result = self.run_capture()
        self.safe(result)
        self.assertEqual(result["state"], "LAB_PPI_7PAIR_LOCAL_M15_CANDIDATE_UNATTESTED")
        self.assertEqual(result["validated_symbols"], 7)
        self.assertEqual(result["validated_bars"], 119)
        self.assertEqual(result["local_files_written"], 8)
        folder = Path(result["directory"])
        self.assertEqual(len(list(folder.iterdir())), 8)
        receipt = load_local_receipt_lab(folder)
        self.assertEqual(set(receipt.sha256_by_symbol), set(USD_FX))
        reaction = inspect_ppi_fx_m15_forward_reaction_lab(
            archive_root=folder, receipt=receipt, as_of_utc=NOW)
        self.assertEqual(reaction["state"], "LAB_PPI_FX_7PAIR_FORWARD_REACTION_DOCUMENTARY_NO_GO")
        self.assertEqual(reaction["independent_economic_event_sample_count"], 1)
        self.assertEqual(reaction["operational_bias"], "AGUARDAR")
        self.assertFalse(reaction["trade_authorized"])

    def test_only_frozen_readonly_methods_invoked_with_utc_range(self):
        self.run_capture()
        names = {call[0] for call in self.api.calls}
        self.assertEqual(names, {"initialize", "terminal_info", "symbol_info",
                                 "copy_rates_range", "shutdown"})
        request = next(c for c in self.api.calls if c[0] == "copy_rates_range")
        self.assertEqual(request[3], BASELINE_OPEN_UTC)
        self.assertEqual(request[4], datetime.fromtimestamp(EXPECTED_EPOCHS[-1], timezone.utc))
        self.assertEqual(request[3].utcoffset(), timedelta(0))
        self.assertEqual(request[4].utcoffset(), timedelta(0))
        self.assertEqual(self.api.calls[-1], ("shutdown",))

    def test_pre_event_and_pre_four_hour_close_never_access_mt5(self):
        for now in (BASELINE_OPEN_UTC, LAST_REQUIRED_CLOSE_UTC - timedelta(microseconds=1)):
            with self.subTest(now=now):
                self.blocked(self.run_capture(now=now), "FOUR_HOUR_M15_WINDOW_NOT_YET_CLOSED")
        self.assertEqual(self.api.calls, [])

    def test_missing_timezone_and_invalid_terminal_block_before_access(self):
        self.blocked(self.run_capture(now=NOW.replace(tzinfo=None)), "INVALID_WALL_CLOCK")
        self.blocked(self.run_capture(terminal="./terminal64.exe"), "INVALID_TERMINAL_PATH_OR_LAB_OUTPUT_ROOT")
        self.assertEqual(self.api.calls, [])

    def test_relative_or_wrong_output_folder_block(self):
        self.blocked(self.run_capture(root=Path("/tmp/elsewhere")), "INVALID_TERMINAL_PATH_OR_LAB_OUTPUT_ROOT")
        self.blocked(self.run_capture(root=Path("AtlasQuant/LAB/PPI_20261113_MT5")), "INVALID_TERMINAL_PATH_OR_LAB_OUTPUT_ROOT")
        self.assertEqual(self.api.calls, [])

    def test_mt5_not_connected_blocks_without_writes(self):
        self.api.connected = False
        self.blocked(self.run_capture(), "MT5_TERMINAL_NOT_CONNECTED")
        self.assertEqual([x[0] for x in self.api.calls], ["initialize"])

    def test_symbol_not_visible_blocks_without_autoselect(self):
        self.api.visible.remove("USDCHF")
        result = self.run_capture()
        self.blocked(result, "CANONICAL_SYMBOL_NOT_VISIBLE_NO_AUTO_SELECT")
        self.assertEqual(result["failed_symbol"], "USDCHF")
        self.assertEqual(self.api.calls[-1], ("shutdown",))

    def test_partial_bars_never_write_six_successes(self):
        self.api.data["USDCAD"].pop()
        self.blocked(self.run_capture(), "REQUIRE_EXACTLY_17_M15_BARS")
        self.assertEqual(self.api.calls[-1], ("shutdown",))

    def test_extra_bar_never_truncated_or_trimmed(self):
        self.api.data["EURUSD"].append(deepcopy(self.api.data["EURUSD"][-1]))
        self.blocked(self.run_capture(), "REQUIRE_EXACTLY_17_M15_BARS")

    def test_wrong_utc_epoch_rejected_not_adjusted(self):
        self.api.data["GBPUSD"][3]["time"] += 3600
        self.blocked(self.run_capture(), "PPI_M15_EPOCH_GAP_DUPLICATE_OR_WRONG_TIMEZONE")

    def test_duplicate_or_gap_rejected(self):
        self.api.data["GBPUSD"][4]["time"] = self.api.data["GBPUSD"][3]["time"]
        self.blocked(self.run_capture(), "PPI_M15_EPOCH_GAP_DUPLICATE_OR_WRONG_TIMEZONE")

    def test_ohlc_inconsistency_rejected(self):
        self.api.data["USDJPY"][6]["high"] = 1.0
        self.blocked(self.run_capture(), "PPI_OHLC_INCONSISTENT")

    def test_zero_tick_volume_rejected(self):
        self.api.data["USDCHF"][2]["tick_volume"] = 0
        self.blocked(self.run_capture(), "INVALID_VOLUME_OR_EPOCH")

    def test_negative_spread_rejected(self):
        self.api.data["AUDUSD"][2]["spread"] = -1
        self.blocked(self.run_capture(), "INVALID_VOLUME_OR_EPOCH")

    def test_nonfinite_and_overprecise_prices_rejected(self):
        self.api.data["NZDUSD"][2]["open"] = float("nan")
        self.blocked(self.run_capture(), "PRICE_OUTSIDE_FROZEN_CSV_CONTRACT")
        self.api.data["NZDUSD"][2]["open"] = 1.12345678901
        self.blocked(self.run_capture(), "PRICE_OUTSIDE_FROZEN_CSV_CONTRACT")

    def test_forged_string_price_rejected(self):
        self.api.data["EURUSD"][2]["open"] = "1.1"
        self.blocked(self.run_capture(), "NON_NUMERIC_PRICE")

    def test_existing_timestamp_directory_not_overwritten(self):
        self.root.mkdir(parents=True)
        destination = self.root / ("PPI7_" + NOW.strftime("%Y%m%dT%H%M%S%fZ"))
        destination.mkdir()
        marker = destination / "keep-me.txt"
        marker.write_text("original", encoding="utf-8")
        result = self.run_capture()
        self.safe(result)
        self.assertEqual(result["reason"], "CAPTURE_RUN_ALREADY_EXISTS_NO_OVERWRITE")
        self.assertEqual(marker.read_text(encoding="utf-8"), "original")
        self.assertEqual(self.api.calls, [])

    def test_tampered_archive_is_rejected_downstream(self):
        result = self.run_capture()
        folder = Path(result["directory"])
        receipt = load_local_receipt_lab(folder)
        file = folder / "EURUSD_PPI_20261113_M15.csv"
        file.write_bytes(file.read_bytes() + b"# altered\n")
        downstream = inspect_ppi_fx_m15_forward_reaction_lab(
            archive_root=folder, receipt=receipt, as_of_utc=NOW)
        self.assertEqual(downstream["series_failure"], "ARCHIVE_RAW_SHA256_MISMATCH")
        self.assertEqual(downstream["operational_bias"], "AGUARDAR")

    def test_manifest_extra_cohort_rejected(self):
        result = self.run_capture()
        folder = Path(result["directory"])
        manifest_file = folder / "ppi_mt5_capture_manifest.json"
        manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
        self.assertEqual(manifest["schema"], SCHEMA)
        manifest["sha256_by_symbol"]["EURGBP"] = "a" * 64
        manifest_file.write_text(json.dumps(manifest), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "MANIFEST_SCHEMA_OR_COHORT_MISMATCH"):
            load_local_receipt_lab(folder)


if __name__ == "__main__":
    unittest.main()
