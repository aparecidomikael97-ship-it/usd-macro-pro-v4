"""MT5 read-only XAUUSD exporter tests using a fake terminal, no actual MT5."""
from datetime import datetime, timezone
import gzip
from hashlib import sha256
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

from atlasquant_mt5_xauusd_closedbar_capture_lab import (
    REQUESTS, collect_xauusd_closedbar_snapshot_lab as collect,
)

AT = datetime(2026, 11, 10, 12, 0, tzinfo=timezone.utc)
WIN_TERMINAL = r"C:\Program Files\MetaTrader 5\terminal64.exe"


def series(count, step):
    start = int(AT.timestamp()) - count * step
    return [{
        "time": start + i * step,
        "open": 3900.0 + i / 10000,
        "high": 3901.0 + i / 10000,
        "low": 3899.0 + i / 10000,
        "close": 3900.2 + i / 10000,
        "tick_volume": 100, "spread": 2, "real_volume": 0,
    } for i in range(count)]


class FakeMT5:
    TIMEFRAME_M15 = 15
    TIMEFRAME_D1 = 1440
    TIMEFRAME_W1 = 10080

    def __init__(self):
        self.calls = []
        self.connected = True
        self.visible = True
        self.initialize_result = True
        self.shutdown_raises = False
        self.series_by_frame = {
            self.TIMEFRAME_M15: series(3000, 900),
            self.TIMEFRAME_D1: series(500, 86400),
            self.TIMEFRAME_W1: series(200, 604800),
        }

    def initialize(self, *, path, timeout):
        self.calls.append(("initialize", path, timeout))
        return self.initialize_result

    def terminal_info(self):
        self.calls.append(("terminal_info",))
        return SimpleNamespace(connected=self.connected)

    def symbol_info(self, symbol):
        self.calls.append(("symbol_info", symbol))
        return SimpleNamespace(visible=self.visible)

    def copy_rates_from_pos(self, symbol, frame, start_pos, count):
        self.calls.append(("copy_rates_from_pos", symbol, frame, start_pos, count))
        assert symbol == "XAUUSD" and start_pos == 1
        return self.series_by_frame[frame]

    def shutdown(self):
        self.calls.append(("shutdown",))
        if self.shutdown_raises:
            raise RuntimeError("fake shutdown exception")


class XauUsdMt5CaptureLabTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="atlasquant_xau_mt5_")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "AtlasQuant" / "LAB" / "MT5_Snapshots"
        self.api = FakeMT5()

    def run_capture(self, *, terminal=WIN_TERMINAL, root=None):
        return collect(self.api, terminal_path=terminal,
                       output_root=self.root if root is None else root,
                       clock=lambda: AT)

    def no_trade(self, result):
        self.assertIs(result["mt5_account_information_accessed"], False)
        self.assertIs(result["orders_or_positions_accessed"], False)
        self.assertIs(result["symbol_visibility_changed"], False)
        self.assertIs(result["broker_identity_independently_authenticated"], False)
        self.assertIs(result["historical_point_in_time_verified"], False)
        self.assertIsNone(result["gold_bias"])
        self.assertIsNone(result["validated_accuracy"])
        self.assertIsNone(result["calibrated_probability"])
        self.assertEqual(result["operational_bias"], "AGUARDAR")
        self.assertIs(result["trade_authorized"], False)
        self.assertIs(result["publishable"], False)
        self.assertEqual(result["new_cost_brl"], 0)
        for call in self.api.calls:
            self.assertIn(call[0], {"initialize", "terminal_info", "symbol_info",
                                    "copy_rates_from_pos", "shutdown"})

    def blocked(self, r, reason):
        self.assertEqual(r["state"], "LAB_XAUUSD_CAPTURE_BLOCKED")
        self.assertEqual(r["reason"], reason)
        self.assertEqual(r["series_count"], 0)
        self.assertEqual(r["local_files_written"], 0)
        self.assertFalse(self.root.exists())
        self.no_trade(r)

    def test_all_3700_bars_written_only_after_successful_read(self):
        r = self.run_capture()
        self.assertEqual(r["state"], "LAB_XAUUSD_LOCAL_3700_CLOSED_BAR_CANDIDATE_UNATTESTED")
        self.assertEqual(r["series_count"], 3)
        self.assertEqual(r["verified_local_bars"], 3700)
        self.assertEqual(r["local_files_written"], 4)
        directory = Path(r["directory"])
        self.assertEqual(directory.parent, self.root)
        self.assertEqual(len(list(directory.iterdir())), 4)
        manifest = json.loads((directory / "xauusd_manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["symbol"], "XAUUSD")
        self.assertFalse(manifest["trade_authorized"])
        self.assertEqual([v["returned"] for v in manifest["records"]], [3000, 500, 200])
        self.assertEqual([v["bar_position_start"] for v in manifest["records"]], [1] * 3)
        for v in manifest["records"]:
            raw = gzip.decompress((directory / v["snapshot_file"]).read_bytes())
            self.assertEqual(sha256(raw).hexdigest(), v["sha256_uncompressed_csv"])
            self.assertEqual(len(raw.splitlines()) - 1, v["returned"])
        self.assertEqual([x for x in self.api.calls if x[0] == "copy_rates_from_pos"],
                         [("copy_rates_from_pos", "XAUUSD", tf, 1, n)
                          for (_, n, _), tf in zip(REQUESTS, (15, 1440, 10080))])
        self.assertEqual(self.api.calls[-1][0], "shutdown")
        self.no_trade(r)

    def test_invalid_terminal_path_does_not_initialize(self):
        for path in ("terminal64.exe", "/usr/bin/terminal64.exe", r"C:\..\terminal64.exe"):
            r = self.run_capture(terminal=path)
            self.blocked(r, "INVALID_TERMINAL_PATH_OR_LAB_OUTPUT_ROOT")
        self.assertEqual(self.api.calls, [])

    def test_output_root_must_be_scoped_to_atlasquant_lab(self):
        r = self.run_capture(root=Path(self.temp.name))
        self.blocked(r, "INVALID_TERMINAL_PATH_OR_LAB_OUTPUT_ROOT")
        self.assertEqual(self.api.calls, [])

    def test_mt5_initialization_failure_is_fail_closed(self):
        self.api.initialize_result = False
        self.blocked(self.run_capture(), "MT5_INITIALIZATION_FAILED")

    def test_disconnected_terminal_rejected(self):
        self.api.connected = False
        self.blocked(self.run_capture(), "MT5_TERMINAL_NOT_CONNECTED")
        self.assertEqual(self.api.calls[-1], ("shutdown",))

    def test_invisible_gold_symbol_does_not_get_selected_automatically(self):
        self.api.visible = False
        self.blocked(self.run_capture(), "XAUUSD_NOT_VISIBLE_NO_AUTO_SELECT")
        self.assertEqual(self.api.calls[-1], ("shutdown",))

    def test_all_three_frames_must_be_full_before_any_write(self):
        self.api.series_by_frame[self.api.TIMEFRAME_W1].pop()
        self.blocked(self.run_capture(), "W1:CLOSED_BAR_COUNT_INCOMPLETE")

    def test_ohlc_invalid_in_one_frame_blocks_all_files(self):
        self.api.series_by_frame[self.api.TIMEFRAME_D1][20]["high"] = 100.0
        self.blocked(self.run_capture(), "D1:BAR_OHLC_INCONSISTENT")

    def test_duplicate_bar_epoch_blocks_all_files(self):
        bars = self.api.series_by_frame[self.api.TIMEFRAME_M15]
        bars[101]["time"] = bars[100]["time"]
        self.blocked(self.run_capture(), "M15:BAR_TIME_DUPLICATE_OR_OUT_OF_ORDER")

    def test_negative_volume_rejected(self):
        self.api.series_by_frame[self.api.TIMEFRAME_W1][0]["spread"] = -1
        self.blocked(self.run_capture(), "W1:BAR_VOLUME_OR_SPREAD_INVALID")

    def test_bar_reported_in_future_rejected(self):
        self.api.series_by_frame[self.api.TIMEFRAME_M15][-1]["time"] = int(AT.timestamp()) + 300
        self.blocked(self.run_capture(), "M15:BAR_OPEN_REPORTED_AFTER_CAPTURE_CLOCK")

    def test_failed_shutdown_does_not_write_files(self):
        self.api.shutdown_raises = True
        self.blocked(self.run_capture(), "MT5_SHUTDOWN_FAILED_NO_ARCHIVE")

    def test_second_run_same_stamp_never_overwrites_first(self):
        first = self.run_capture()
        self.assertEqual(first["local_files_written"], 4)
        manifest = Path(first["directory"]) / "xauusd_manifest.json"
        before = manifest.read_bytes()
        second = self.run_capture()
        self.assertEqual(second["reason"], "CAPTURE_RUN_DIRECTORY_ALREADY_EXISTS_NO_OVERWRITE")
        self.assertEqual(second["local_files_written"], 0)
        self.assertEqual(manifest.read_bytes(), before)
        self.no_trade(second)

    def test_weekend_style_gap_is_counted_not_imputed(self):
        bars = self.api.series_by_frame[self.api.TIMEFRAME_D1]
        # Move all later daily bars two days further into the past to leave a
        # gap while keeping the latest bar no later than the collector clock.
        for item in bars[:100]:
            item["time"] -= 2 * 86400
        r = self.run_capture()
        self.assertEqual(r["state"], "LAB_XAUUSD_LOCAL_3700_CLOSED_BAR_CANDIDATE_UNATTESTED")
        d1 = next(x for x in r["records"] if x["timeframe"] == "D1")
        self.assertGreater(d1["larger_than_nominal_gaps_needing_calendar_review"], 0)
        self.no_trade(r)


if __name__ == "__main__":
    unittest.main()
