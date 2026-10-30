"""A276: no live or provider authority can emerge from untrusted CSV."""
from datetime import datetime, timezone, timedelta
import unittest

from atlasquant_aion_historical_csv import (
    ALLOWED_SYMBOLS, MAX_CANDLES, MAX_CSV_BYTES, SCHEMA, import_historical_csv,
)
from atlasquant_instrument_registry import FX_28
from atlasquant_aion_trader_nonfx import SYMBOLS, FUTURE_ROOTS
from atlasquant_operational_backtest import normalize_candles

NOW = datetime(2026, 10, 30, 1, 0, tzinfo=timezone.utc)
HEADER = "time,open,high,low,close"
ROW1 = "2026-10-30T00:00:00+00:00,1.10,1.20,1.00,1.15"
ROW2 = "2026-10-30T00:15:00+00:00,1.15,1.25,1.10,1.20"
VALID = "\n".join((HEADER, ROW1, ROW2, ""))


def intake(csv=VALID, **overrides):
    args = {
        "symbol": "EURUSD", "timeframe": "M15",
        "timestamp_basis": "OPEN", "now": NOW,
    }
    args.update(overrides)
    return import_historical_csv(csv, **args)


class A276HistoricalCsvTests(unittest.TestCase):
    def assert_rejected(self, csv=VALID, *, reason=None, **kw):
        result = intake(csv, **kw)
        self.assertFalse(result["valid"])
        self.assertEqual(result["status"], "INVALID_UNVERIFIED_HISTORICAL_CSV")
        self.assertEqual(result["candles"], [])
        self.assertEqual(result["candle_count"], 0)
        self.assertFalse(result["authorizes_send"])
        self.assertTrue(result["no_orders"])
        self.assertEqual(result["p0_homologated"], 0)
        if reason:
            self.assertEqual(result["error"], reason)

    def test_01_universe_is_exact_fx_and_existing_radar_nonfx(self):
        self.assertEqual(ALLOWED_SYMBOLS, set(FX_28) | set(SYMBOLS))
        self.assertEqual(len(ALLOWED_SYMBOLS), 35)
        self.assertEqual(FUTURE_ROOTS, {"WIN", "WDO"})

    def test_02_utc_close_times_are_explicit_not_assumed_live(self):
        result = intake()
        self.assertEqual(result["schema"], SCHEMA)
        self.assertTrue(result["valid"])
        self.assertEqual(result["status"], "HISTORICAL_ONLY_UNATTESTED")
        self.assertEqual(result["candle_count"], 2)
        self.assertEqual(result["first_closed_at"], "2026-10-30T00:15:00+00:00")
        self.assertEqual(result["last_closed_at"], "2026-10-30T00:30:00+00:00")
        self.assertEqual(result["candles"][0]["open"], 1.10)
        self.assertEqual(len(result["raw_csv_sha256"]), 64)
        self.assertEqual(len(result["normalized_candles_sha256"]), 64)
        for key in ("source_is_externally_attested", "provider_mapping_verified",
                    "contract_expiry_verified", "backtest_results_generated",
                    "authorizes_send"):
            self.assertFalse(result[key])
        for key in ("historical_only", "no_live_gate_effect", "no_orders",
                    "no_alerts", "no_new_data_calls"):
            self.assertTrue(result[key])
        self.assertEqual(result["p0_homologated"], 0)

    def test_03_close_basis_does_not_add_a_period(self):
        result = intake(VALID.replace("time,", "closed_at,", 1),
                        timestamp_basis="CLOSE")
        self.assertTrue(result["valid"])
        self.assertEqual(result["first_closed_at"], "2026-10-30T00:00:00+00:00")
        self.assertEqual(result["last_closed_at"], "2026-10-30T00:15:00+00:00")

    def test_04_datetime_and_optional_volume_accepted(self):
        data = VALID.replace("time,open,high,low,close", "datetime,open,high,low,close,volume")
        data = data.replace("1.15\n", "1.15,0\n").replace("1.20\n", "1.20,123.5\n")
        result = intake(data)
        self.assertTrue(result["valid"])
        self.assertEqual(result["candles"][0]["volume"], 0)
        self.assertEqual(result["candles"][1]["volume"], 123.5)

    def test_05_compatibility_with_existing_research_candle_normalizer(self):
        import pandas as pd
        result = intake()
        frame = normalize_candles(pd.DataFrame(result["candles"]))
        self.assertEqual(len(frame), 2)
        self.assertEqual(float(frame.iloc[-1]["close"]), 1.20)

    def test_06_all_35_are_research_only_even_futures_roots(self):
        for symbol in ALLOWED_SYMBOLS:
            with self.subTest(symbol=symbol):
                result = intake(symbol=symbol)
                self.assertTrue(result["valid"])
                self.assertFalse(result["provider_mapping_verified"])
                self.assertFalse(result["contract_expiry_verified"])
                self.assertFalse(result["authorizes_send"])
                self.assertEqual(result["asset_class"],
                                 "FOREX" if symbol in FX_28 else
                                 "UNRESOLVED_FUTURE_ROOT" if symbol in FUTURE_ROOTS
                                 else "INDEX_REFERENCE")

    def test_07_unrecognized_aliases_and_contracts_refused(self):
        for symbol in ("US100", "EUR/USD", "FX:EURUSD", "WINZ26", "WDOX26",
                       "BTCUSD", "", 123, None):
            with self.subTest(symbol=symbol):
                self.assert_rejected(symbol=symbol,
                                     reason="UNKNOWN_SYMBOL_TIMEFRAME_OR_BASIS")

    def test_08_timeframe_and_basis_explicit(self):
        for kw in ({"timeframe": "M1"}, {"timeframe": "m15"},
                   {"timeframe": 15}, {"timestamp_basis": None},
                   {"timestamp_basis": "UNKNOWN"}, {"timestamp_basis": 1}):
            with self.subTest(kw=kw):
                self.assert_rejected(reason="UNKNOWN_SYMBOL_TIMEFRAME_OR_BASIS", **kw)

    def test_09_untrusted_nontext_and_non_native_input_refused(self):
        class MaliciousText(str):
            def __str__(self):
                raise AssertionError("must not call hostile __str__")
        for data in (b"csv", None, ["fake"], MaliciousText(VALID), "a\x00b",
                     "\ud800"):
            with self.subTest(data_type=type(data).__name__):
                self.assert_rejected(data)

    def test_10_missing_timezone_or_invalid_date_refused(self):
        for stamp in ("2026-10-30T00:00:00", "30/10/2026 00:00",
                      "yesterday", ""):
            with self.subTest(stamp=stamp):
                self.assert_rejected(VALID.replace("2026-10-30T00:00:00+00:00", stamp),
                                     reason="INVALID_TIMESTAMP")

    def test_11_invalid_now_never_introduces_system_time_fallback(self):
        self.assert_rejected(now=None, reason="INVALID_NOW")
        self.assert_rejected(now=NOW.replace(tzinfo=None), reason="INVALID_NOW")
        self.assert_rejected(now="2026-10-30", reason="INVALID_NOW")

    def test_12_future_open_candle_rejected_before_close(self):
        self.assert_rejected(now=datetime(2026, 10, 30, 0, 20, tzinfo=timezone.utc),
                             reason="FUTURE_CANDLE")

    def test_13_duplicate_reverse_or_too_close_timestamps_are_rejected(self):
        for stamp in ("2026-10-30T00:00:00+00:00",
                      "2026-10-29T23:00:00+00:00",
                      "2026-10-30T00:10:00+00:00"):
            data = VALID.replace("2026-10-30T00:15:00+00:00", stamp)
            with self.subTest(stamp=stamp):
                self.assert_rejected(data, reason="NON_MONOTONIC_OR_TOO_CLOSE")

    def test_14_market_gaps_are_historical_not_synthetic_bars(self):
        data = VALID.replace("2026-10-30T00:15:00+00:00",
                             "2026-10-30T00:45:00+00:00")
        self.assertTrue(intake(data)["valid"])
        self.assertEqual(intake(data)["candle_count"], 2)

    def test_15_nan_infinity_overflow_negative_and_zero_ohlc_refused(self):
        for value in ("NaN", "Inf", "-Inf", "1e309", "-2", "0",
                      "=cmd()", "not-a-price"):
            with self.subTest(value=value):
                data = VALID.replace(",1.10,1.20,1.00,1.15", f",{value},1.20,1.00,1.15")
                self.assert_rejected(data, reason="INVALID_OHLC")

    def test_16_high_low_candle_geometry_is_mandatory(self):
        self.assert_rejected(VALID.replace("1.10,1.20,1.00,1.15",
                                           "1.10,1.12,1.00,1.15"),
                             reason="INVALID_OHLC_GEOMETRY")
        self.assert_rejected(VALID.replace("1.10,1.20,1.00,1.15",
                                           "1.10,1.20,1.12,1.15"),
                             reason="INVALID_OHLC_GEOMETRY")

    def test_17_headers_are_exact_unique_and_widths_enforced(self):
        for data, reason in (
            (VALID.replace("time,", "clock,", 1), "INVALID_HEADER"),
            (VALID.replace("time,open", "time,time", 1), "INVALID_HEADER"),
            (VALID.replace("time,open", "time,OPEN", 1), "INVALID_HEADER"),
            (VALID.replace("1.10,1.20,1.00,1.15", "1.10,1.20,1.00"), "INVALID_ROW_WIDTH"),
            ("", "CSV_SIZE_LIMIT"),
            ("time,open,high,low,close\n", "INSUFFICIENT_CANDLES"),
        ):
            with self.subTest(reason=reason):
                self.assert_rejected(data, reason=reason)

    def test_18_volume_failclosed(self):
        for vol in ("-1", "Inf", "NaN", ""):
            data = VALID.replace(HEADER, HEADER + ",volume")
            data = data.replace("1.15\n", "1.15," + vol + "\n")
            data = data.replace("1.20\n", "1.20,2\n")
            with self.subTest(vol=vol):
                self.assert_rejected(data, reason="INVALID_VOLUME")

    def test_19_file_size_bounded(self):
        self.assert_rejected("x" * (MAX_CSV_BYTES + 1), reason="CSV_SIZE_LIMIT")

    def test_20_row_count_bounded_with_no_partial_success(self):
        first = "2026-01-01T00:00:00+00:00,1,1,1,1"
        many = HEADER + "\n" + "\n".join([first] * (MAX_CANDLES + 1))
        self.assert_rejected(many, reason="NON_MONOTONIC_OR_TOO_CLOSE")

    def test_21_truncated_rows_do_not_yield_partial_data(self):
        self.assert_rejected(VALID + "2026-10-30T00:30:00+00:00,1.2,1.3",
                             reason="INVALID_ROW_WIDTH")

    def test_22_digest_is_deterministic_and_raw_input_tampering_detectable(self):
        a, b = intake(), intake()
        self.assertEqual(a["raw_csv_sha256"], b["raw_csv_sha256"])
        self.assertEqual(a["normalized_candles_sha256"],
                         b["normalized_candles_sha256"])
        different = intake(VALID.replace("1.25", "1.26"))
        self.assertTrue(different["valid"])
        self.assertNotEqual(a["raw_csv_sha256"], different["raw_csv_sha256"])
        self.assertNotEqual(a["normalized_candles_sha256"],
                            different["normalized_candles_sha256"])

    def test_23_time_zone_offsets_normalized(self):
        data = VALID.replace("+00:00", "-04:00").replace(
            "2026-10-30T00:00:00", "2026-10-29T20:00:00"
        ).replace("2026-10-30T00:15:00", "2026-10-29T20:15:00")
        self.assertEqual(intake(data)["candles"], intake()["candles"])


if __name__ == "__main__":
    unittest.main()
