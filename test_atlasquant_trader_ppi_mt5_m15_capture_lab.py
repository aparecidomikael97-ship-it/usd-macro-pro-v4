"""Synthetic contracts only; no MT5 package, terminal, market data or trades."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
import json
import tempfile
import unittest

try:
    import numpy as np  # MT5's actual return shape; optional in offline CI.
except ImportError:
    np = None

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
        self.company = "MetaQuotes Software Corp."
        self.specs = {
            sym: {
                "name": sym, "currency_base": sym[:3],
                "currency_profit": sym[3:],
                "digits": 3 if sym.endswith("JPY") else 5,
                "point": 0.001 if sym.endswith("JPY") else 0.00001,
            } for sym in USD_FX
        }
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
        return SimpleNamespace(connected=self.connected, company=self.company)

    def symbol_info(self, sym):
        self.calls.append(("symbol_info", sym))
        return SimpleNamespace(visible=sym in self.visible, **self.specs[sym])

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
        self.assertFalse(result["active_quote_server_independently_verified"])
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
        self.assertEqual(result["validated_bars"], 119, result)
        self.assertEqual(result["local_files_written"], 8)
        self.assertTrue(result["symbol_specs_observed_locally"])
        self.assertEqual(result["terminal_company_observation_untrusted"],
                         "MetaQuotes Software Corp.")
        self.assertEqual(set(result["symbol_specs_claimed_unattested"]), set(USD_FX))
        folder = Path(result["directory"])
        stored = json.loads((folder / "ppi_mt5_capture_manifest.json").read_text("utf-8"))
        self.assertEqual(stored["terminal_company_observation_untrusted"],
                         "MetaQuotes Software Corp.")
        self.assertFalse(stored["active_quote_server_independently_verified"])
        self.assertEqual(stored["symbol_specs_claimed_unattested"]["EURUSD"]["digits_claim"], 5)
        self.assertEqual(stored["symbol_specs_claimed_unattested"]["EURUSD"]["point_quote_units_claim"], "0.00001")
        self.assertEqual(stored["symbol_specs_claimed_unattested"]["USDJPY"]["point_quote_units_claim"], "0.001")

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

    @unittest.skipUnless(np is not None, "numpy absent: MT5 structured-array regression is local-only")
    def test_actual_mt5_numpy_structured_array_shape_roundtrips(self):
        # MetaQuotes' copy_rates_range returns a structured numpy array, not dicts.
        dtype = [("time", "<i8"), ("open", "<f8"), ("high", "<f8"),
                 ("low", "<f8"), ("close", "<f8"), ("tick_volume", "<u8"),
                 ("spread", "<i4"), ("real_volume", "<u8")]
        for sym in USD_FX:
            series = np.zeros(17, dtype=dtype)
            series["time"] = EXPECTED_EPOCHS
            series["open"] = 145.2 if sym.startswith("USD") else 1.12345
            # Brokers return decimal tick prices; synthetic float arithmetic
            # must be rounded to ticks before constructing the test fixture.
            series["high"] = np.round(series["open"] + 0.02, 5)
            series["low"] = np.round(series["open"] - 0.02, 5)
            series["close"] = series["open"]
            series["tick_volume"] = 73
            series["spread"] = 8
            self.api.data[sym] = series

        result = self.run_capture()
        self.safe(result)
        self.assertEqual(result["validated_bars"], 119, result)
        folder = Path(result["directory"])
        receipt = load_local_receipt_lab(folder)
        studied = inspect_ppi_fx_m15_forward_reaction_lab(
            archive_root=folder, receipt=receipt, as_of_utc=NOW)
        self.assertEqual(studied["state"], "LAB_PPI_FX_7PAIR_FORWARD_REACTION_DOCUMENTARY_NO_GO")
        self.assertEqual(set(studied["price_reactions_usd_normalized_bps"]), set(USD_FX))

    @unittest.skipUnless(np is not None, "numpy absent: MT5 structured-array regression is local-only")
    def test_mt5_numpy_structured_array_bad_epoch_does_not_write(self):
        dtype = [("time", "<i8"), ("open", "<f8"), ("high", "<f8"),
                 ("low", "<f8"), ("close", "<f8"), ("tick_volume", "<u8"),
                 ("spread", "<i4"), ("real_volume", "<u8")]
        series = np.zeros(17, dtype=dtype)
        series["time"] = EXPECTED_EPOCHS
        series["time"][8] += 900
        series["open"] = 1.1
        series["high"] = 1.11
        series["low"] = 1.09
        series["close"] = 1.1
        series["tick_volume"] = 32
        self.api.data["NZDUSD"] = series
        self.blocked(self.run_capture(), "PPI_M15_EPOCH_GAP_DUPLICATE_OR_WRONG_TIMEZONE")

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

    def test_symbol_hidden_but_valid_history_is_accepted_without_autoselect(self):
        self.api.visible.remove("USDCHF")
        self.api.visible.remove("NZDUSD")
        result = self.run_capture()
        self.safe(result)
        self.assertEqual(result["validated_bars"], 119)
        self.assertEqual(result["hidden_symbols_read_from_history"],
                         ["NZDUSD", "USDCHF"])
        self.assertFalse(any(call[0] in ("symbol_select", "order_send", "account_info")
                             for call in self.api.calls))
        self.assertEqual(self.api.visible, set(USD_FX) - {"NZDUSD", "USDCHF"})
        self.assertEqual(result["bounded_history_warmup_attempted"], [])

    def test_missing_canonical_symbol_still_blocks_no_auto_selection(self):
        class MissingSymbolMT5(FakeMT5):
            def symbol_info(self, sym):
                if sym == "USDCHF":
                    self.calls.append(("symbol_info", sym))
                    return None
                return super().symbol_info(sym)

        api = MissingSymbolMT5()
        result = self.run_capture(api=api)
        self.blocked(result, "CANONICAL_SYMBOL_MISSING_NO_AUTO_SELECT")
        self.assertEqual(result["failed_symbol"], "USDCHF")
        self.assertEqual(api.calls[-1], ("shutdown",))

    def test_once_empty_history_gets_one_bounded_readonly_warmup(self):
        class LazilyLoadedHistoryMT5(FakeMT5):
            def __init__(self):
                super().__init__()
                self.empty_once = True

            def copy_rates_range(self, sym, timeframe, begin, end):
                rows = super().copy_rates_range(sym, timeframe, begin, end)
                if sym == "GBPUSD" and begin == BASELINE_OPEN_UTC and self.empty_once:
                    self.empty_once = False
                    return []
                return rows

        api = LazilyLoadedHistoryMT5()
        result = self.run_capture(api=api)
        self.safe(result)
        self.assertEqual(result["validated_bars"], 119)
        self.assertEqual(result["bounded_history_warmup_attempted"], ["GBPUSD"])
        gbp_reads = [x for x in api.calls
                     if x[0] == "copy_rates_range" and x[1] == "GBPUSD"]
        self.assertEqual(len(gbp_reads), 3)
        self.assertEqual(gbp_reads[1][3],
                         BASELINE_OPEN_UTC - timedelta(days=2))
        self.assertEqual(gbp_reads[2][3], BASELINE_OPEN_UTC)
        self.assertEqual(api.calls[-1], ("shutdown",))

    def test_permanently_empty_history_still_blocks_without_partial_files(self):
        class NeverLoadedHistoryMT5(FakeMT5):
            def copy_rates_range(self, sym, timeframe, begin, end):
                rows = super().copy_rates_range(sym, timeframe, begin, end)
                if sym == "USDJPY" and begin == BASELINE_OPEN_UTC:
                    return []
                return rows

        api = NeverLoadedHistoryMT5()
        result = self.run_capture(api=api)
        self.blocked(result, "REQUIRE_EXACTLY_17_M15_BARS")
        self.assertEqual(result["failed_symbol"], "USDJPY")
        self.assertEqual(result["bounded_history_warmup_attempted"], ["USDJPY"])
        self.assertEqual(api.calls[-1], ("shutdown",))

    def test_wrong_currency_base_or_profit_cannot_be_mistaken_for_forex_pair(self):
        for attr, bad in (("currency_base", "GBP"), ("currency_profit", "EUR")):
            with self.subTest(attr=attr):
                self.api.specs["EURUSD"][attr] = bad
                result = self.run_capture()
                self.blocked(result, "SYMBOL_BASE_QUOTE_DIGITS_OR_POINT_NOT_VERIFIED")
                self.assertEqual(result["failed_symbol"], "EURUSD")
                self.assertEqual(self.api.calls[-1], ("shutdown",))
                self.api.specs["EURUSD"][attr] = "EUR" if attr == "currency_base" else "USD"

    def test_wrong_name_digits_point_or_nonfinite_point_blocks_before_file_io(self):
        for key, bad in (("name", "EURUSD.a"), ("digits", True),
                         ("digits", 8), ("point", 0.0001),
                         ("point", float("nan")), ("point", "0.00001")):
            with self.subTest(key=key,bad=bad):
                original = self.api.specs["EURUSD"][key]
                self.api.specs["EURUSD"][key] = bad
                result = self.run_capture()
                self.blocked(result, "SYMBOL_BASE_QUOTE_DIGITS_OR_POINT_NOT_VERIFIED")
                self.api.specs["EURUSD"][key] = original

    def test_terminal_company_is_untrusted_and_no_sensitive_terminal_metadata_copied(self):
        self.api.company = "Other Brand MT5"
        result = self.run_capture()
        self.safe(result)
        self.assertTrue(result["symbol_specs_observed_locally"])
        self.assertEqual(result["terminal_company_observation_untrusted"], "Other Brand MT5")
        self.assertFalse(result["active_quote_server_independently_verified"])
        manifest = json.loads((Path(result["directory"]) /
                              "ppi_mt5_capture_manifest.json").read_text("utf-8"))
        self.assertFalse(any(word in manifest for word in
                             ('"account"', '"password"', '"data_path"', '"server"')))

    def test_terminal_company_path_like_value_is_not_stored(self):
        self.api.company = r"C:\\Users\\private"
        result = self.run_capture()
        self.safe(result)
        self.assertIsNone(result["terminal_company_observation_untrusted"])
        manifest = json.loads((Path(result["directory"]) /
                              "ppi_mt5_capture_manifest.json").read_text("utf-8"))
        self.assertIsNone(manifest["terminal_company_observation_untrusted"])

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

    def test_real_binary64_transport_drift_is_normalized_to_quote_tick(self):
        # Observed on AM12: MT5 numpy float64 1.1137299999999999
        # represents the valid five-digit broker quote 1.11373.
        for field in ("open", "high", "low", "close"):
            self.api.data["EURUSD"][0][field] = 1.1137299999999999
        result = self.run_capture()
        self.safe(result)
        self.assertEqual(result["validated_bars"], 119)
        from pathlib import Path
        import csv
        file = Path(result["directory"]) / "EURUSD_PPI_20261113_M15.csv"
        with file.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(rows[0]["open"], "1.11373")
        self.assertEqual(rows[0]["high"], "1.11373")
        self.assertEqual(rows[0]["low"], "1.11373")
        self.assertEqual(rows[0]["close"], "1.11373")

    def test_real_off_quote_tick_data_remains_blocked_without_rounding(self):
        for field in ("open", "high", "low", "close"):
            self.api.data["EURUSD"][0][field] = 1.113736
        self.blocked(self.run_capture(), "PRICE_OUTSIDE_FROZEN_CSV_CONTRACT")

    def test_one_thousandth_of_point_off_tick_is_not_ulp(self):
        # 1.11373001 is close visually but still intentionally off tick.
        for field in ("open", "high", "low", "close"):
            self.api.data["EURUSD"][0][field] = 1.11373001
        self.blocked(self.run_capture(), "PRICE_OUTSIDE_FROZEN_CSV_CONTRACT")

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

    def test_modified_symbol_metadata_manifest_rejected_on_reload(self):
        result = self.run_capture()
        folder = Path(result["directory"])
        path = folder / "ppi_mt5_capture_manifest.json"
        original = json.loads(path.read_text(encoding="utf-8"))
        for field, wrong in (("currency_base_claim", "GBP"),
                             ("currency_profit_claim", "JPY"),
                             ("digits_claim", 4),
                             ("point_quote_units_claim", "0.0001"),
                             ("point_quote_units_claim", "NaN")):
            with self.subTest(field=field, wrong=wrong):
                manifest = deepcopy(original)
                manifest["symbol_specs_claimed_unattested"]["EURUSD"][field] = wrong
                path.write_text(json.dumps(manifest), encoding="utf-8")
                with self.assertRaisesRegex(
                        ValueError, "MANIFEST_SYMBOL_SPECS_OR_BROKER_ATTESTATION_INVALID"):
                    load_local_receipt_lab(folder)

    def test_forged_active_server_attestation_manifest_rejected(self):
        result = self.run_capture()
        folder = Path(result["directory"])
        path = folder / "ppi_mt5_capture_manifest.json"
        original = json.loads(path.read_text(encoding="utf-8"))
        for field in ("active_quote_server_independently_verified",
                      "broker_identity_independently_authenticated"):
            with self.subTest(field=field):
                manifest = deepcopy(original)
                manifest[field] = True
                path.write_text(json.dumps(manifest), encoding="utf-8")
                with self.assertRaisesRegex(
                        ValueError, "MANIFEST_SYMBOL_SPECS_OR_BROKER_ATTESTATION_INVALID"):
                    load_local_receipt_lab(folder)

    def test_manifest_falsified_counts_and_safety_flags_fail_reload(self):
        result = self.run_capture()
        folder = Path(result["directory"])
        path = folder / "ppi_mt5_capture_manifest.json"
        original = json.loads(path.read_text("utf-8"))
        changes = (
            ("symbol_count", 6), ("symbol_count", True),
            ("rows_per_symbol", 16), ("rows_per_symbol", True),
            ("research_only", False), ("operational_bias", "ALTA"),
            ("publishable", True), ("trade_authorized", True),
            ("candle_utc_independently_authenticated", True),
            ("point_in_time_market_data_attested", True),
        )
        for field, wrong in changes:
            with self.subTest(field=field, wrong=wrong):
                altered = deepcopy(original)
                altered[field] = wrong
                path.write_text(json.dumps(altered), encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "MANIFEST_SCHEMA_OR_COHORT_MISMATCH"):
                    load_local_receipt_lab(folder)

    def test_missing_or_oversized_manifest_digest_rejected(self):
        result = self.run_capture()
        folder = Path(result["directory"])
        path = folder / "ppi_mt5_capture_manifest.json"
        original = json.loads(path.read_text("utf-8"))
        for digest in (None, "", "A"*64, "e"*63, 999):
            with self.subTest(digest=digest):
                altered = deepcopy(original)
                altered["sha256_by_symbol"]["EURUSD"] = digest
                path.write_text(json.dumps(altered), encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "MANIFEST_SCHEMA_OR_COHORT_MISMATCH"):
                    load_local_receipt_lab(folder)

    def test_invalid_or_early_manifest_capture_clock_rejected(self):
        result = self.run_capture()
        folder = Path(result["directory"])
        path = folder / "ppi_mt5_capture_manifest.json"
        original = json.loads(path.read_text("utf-8"))
        invalids = ("not a date", 3, NOW.replace(tzinfo=None).isoformat(),
                    (LAST_REQUIRED_CLOSE_UTC-timedelta(minutes=1)).isoformat())
        for wrong in invalids:
            with self.subTest(wrong=wrong):
                altered = deepcopy(original)
                altered["captured_at_utc_local_clock_claim"] = wrong
                path.write_text(json.dumps(altered), encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "MANIFEST_CAPTURE_TIMESTAMP_INVALID"):
                    load_local_receipt_lab(folder)

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
