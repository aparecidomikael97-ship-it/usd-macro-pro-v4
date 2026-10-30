"""A284 LAB: genuine native-format MT5 export shape, synthetic bars only."""
from datetime import datetime, timedelta, timezone
from unittest import mock
import unittest

import atlasquant_aion_mt5_bars_bridge_lab as a284
from atlasquant_aion_mt5_bars_bridge_lab import (
    SCHEMA, EXPECTED_HEADER, normalize_mt5_bars_tsv,
    preflight_mt5_bars_tsv, research_mt5_bars_tsv,
)
from atlasquant_aion_historical_csv import import_historical_csv

START = datetime(2026, 9, 30, 22, 0)
NOW = datetime(2026, 10, 30, tzinfo=timezone.utc)


def closed_stamp(i, *, period=15, offset=120):
    wall = START + timedelta(minutes=period*i)
    closed = wall.replace(
        tzinfo=timezone(timedelta(minutes=offset))
    ) + timedelta(minutes=period)
    return closed.astimezone(timezone.utc).isoformat()


def sample(rows=240, *, period=15, flat=False, invalid_metadata=None):
    lines = ["\t".join(EXPECTED_HEADER)]
    for i in range(rows):
        wall = START + timedelta(minutes=period*i)
        price = 100.0 if flat else round(100 + ((i % 17) - 8) * 0.2, 4)
        hi, low = round(price + 0.6, 4), round(price - 0.6, 4)
        ticks = "0" if invalid_metadata is None else (
            invalid_metadata if i == 1 else "12"
        )
        fields = [
            wall.strftime("%Y.%m.%d"), wall.strftime("%H:%M:%S"),
            str(price), str(hi), str(low), str(price),
            ticks, "0", "3",
        ]
        lines.append("\t".join(fields))
    return "\n".join(lines) + "\n"


def convert(**kw):
    inputs = {
        "mt5_tsv": sample(), "symbol": "EURUSD", "timeframe": "M15",
        "now": NOW, "server_utc_offset_minutes": 120,
    }
    inputs.update(kw)
    return normalize_mt5_bars_tsv(**inputs)


def preflight(**kw):
    options = {
        "mt5_tsv": sample(), "symbol": "EURUSD", "timeframe": "M15",
        "now": NOW, "server_utc_offset_minutes": 120,
        "validation_start": closed_stamp(120),
    }
    options.update(kw)
    return preflight_mt5_bars_tsv(**options)


def research(**kw):
    options = {
        "mt5_tsv": sample(), "symbol": "EURUSD", "timeframe": "M15",
        "now": NOW, "server_utc_offset_minutes": 120,
        "validation_start": closed_stamp(120),
        "cost_r": 0.1, "slippage_r": 0.05,
        "max_wait_bars": 3, "max_hold_bars": 4,
    }
    options.update(kw)
    return research_mt5_bars_tsv(**options)


class A284NativeMt5BarsBridgeTests(unittest.TestCase):
    def test_01_native_tab_separated_9_column_csv_supported(self):
        result = convert()
        self.assertTrue(result["valid"])
        self.assertEqual(result["schema"], SCHEMA)
        self.assertEqual(result["candle_count"], 240)
        self.assertEqual(result["status"],
                         "MT5_BARS_NORMALIZED_UNATTESTED_HISTORICAL_ONLY")
        self.assertEqual(result["canonical_timestamp_basis"], "CLOSE")
        self.assertTrue(result["canonical_closed_csv"].startswith(
            "closed_at,open,high,low,close\n"
        ))

    def test_02_server_open_time_shifted_to_utc_then_closed(self):
        result = convert()
        self.assertEqual(result["first_closed_at"], closed_stamp(0))
        self.assertEqual(result["last_closed_at"], closed_stamp(239))
        self.assertEqual(result["declared_server_utc_offset_minutes"], 120)
        self.assertTrue(result["fixed_offset_does_not_handle_dst_transition"])

    def test_03_a276_roundtrip_same_normalized_candle_hash(self):
        result = convert()
        parsed = import_historical_csv(
            result["canonical_closed_csv"], symbol="EURUSD",
            timeframe="M15", timestamp_basis="CLOSE", now=NOW,
        )
        self.assertTrue(parsed["valid"])
        self.assertEqual(result["normalized_candles_sha256"],
                         parsed["normalized_candles_sha256"])
        self.assertEqual(result["canonical_csv_sha256"],
                         parsed["raw_csv_sha256"])

    def test_04_offset_is_mandatory_and_never_default_utc(self):
        for value in (None, "120", True, 120.0, 13, 841, -841):
            with self.subTest(value=value):
                result = convert(server_utc_offset_minutes=value)
                self.assertFalse(result["valid"])
                self.assertEqual(result["error"],
                                 "EXPLICIT_SERVER_UTC_OFFSET_REQUIRED")
                self.assertIsNone(result["canonical_closed_csv"])

    def test_05_offset_zero_and_negative_offset_are_explicitly_possible(self):
        zero = convert(server_utc_offset_minutes=0)
        west = convert(server_utc_offset_minutes=-240)
        self.assertTrue(zero["valid"])
        self.assertTrue(west["valid"])
        self.assertEqual(zero["first_closed_at"],
                         closed_stamp(0, offset=0))
        self.assertEqual(west["first_closed_at"],
                         closed_stamp(0, offset=-240))
        self.assertNotEqual(zero["canonical_csv_sha256"],
                            west["canonical_csv_sha256"])

    def test_06_export_format_not_guessed_from_comma_csv(self):
        comma = sample().replace("\t", ",")
        result = convert(mt5_tsv=comma)
        self.assertFalse(result["valid"])
        self.assertEqual(result["error"],
                         "NOT_NATIVE_MT5_NINE_COLUMN_TSV")

    def test_07_no_missing_reordered_or_unexpected_columns(self):
        for text in (
            sample().replace("<TICKVOL>\t<VOL>", "<VOL>\t<TICKVOL>"),
            sample().replace("<SPREAD>", "<SPREAD>\t<EXTRA>"),
            sample().replace("<TIME>", "<TIME_SOURCE>"),
        ):
            with self.subTest(header=text.splitlines()[0][:30]):
                result = convert(mt5_tsv=text)
                self.assertFalse(result["valid"])
                self.assertEqual(result["error"],
                                 "NOT_NATIVE_MT5_NINE_COLUMN_TSV")

    def test_08_negative_or_malformed_volume_spread_metadata_refused(self):
        for value in ("-1", "1.5", "NaN", "Inf", "", "x", "1"*17):
            with self.subTest(value=value[:10]):
                result = convert(mt5_tsv=sample(invalid_metadata=value))
                self.assertFalse(result["valid"])
                self.assertEqual(result["error"], "INVALID_MT5_QUOTE_METADATA")

    def test_09_zero_tick_volume_is_accepted_not_called_real_volume(self):
        result = convert()
        self.assertTrue(result["valid"])
        self.assertFalse(result["volume_represents_real_traded_volume"])
        self.assertFalse(result["spread_represents_verified_execution_cost"])
        self.assertTrue(result["mt5_tick_volume_and_real_volume_not_preserved"])

    def test_10_bad_date_and_time_formats_fail_closed(self):
        raw = sample()
        cases = (
            raw.replace("2026.09.30", "2026-09-30"),
            raw.replace("22:00:00", "22:0:00"),
        )
        for broken in cases:
            with self.subTest(label=broken.splitlines()[1][:25]):
                result = convert(mt5_tsv=broken)
                self.assertFalse(result["valid"])
                self.assertIsNone(result["canonical_closed_csv"])

    def test_11_invalid_calendar_date_rejected(self):
        raw = sample().replace("2026.09.30", "2026.09.31")
        result = convert(mt5_tsv=raw)
        self.assertFalse(result["valid"])
        self.assertEqual(result["error"], "INVALID_MT5_WALL_CLOCK_DATE")

    def test_12_duplicate_or_reordered_open_candle_rejected_by_a276(self):
        lines = sample().splitlines()
        earlier = lines[10].split("\t")
        current = lines[11].split("\t")
        current[0], current[1] = earlier[0], earlier[1]
        lines[11] = "\t".join(current)
        result = convert(mt5_tsv="\n".join(lines) + "\n")
        self.assertFalse(result["valid"])
        self.assertIn("NON_MONOTONIC", result["error"])

    def test_13_unknown_broker_alias_and_expiry_contract_denied(self):
        for symbol in ("EUR/USD", "US100", "BTCUSD", "WINZ26"):
            with self.subTest(symbol=symbol):
                result = convert(symbol=symbol)
                self.assertFalse(result["valid"])
                self.assertTrue(result["error"].startswith(
                    "INVALID_A276_OPEN_BARS:"
                ))

    def test_14_research_id_win_is_not_futures_contract_validation(self):
        result = convert(symbol="WIN")
        self.assertTrue(result["valid"])
        self.assertFalse(result["futures_contract_expiry_verified"])
        self.assertFalse(result["broker_symbol_to_research_id_verified"])

    def test_15_mismatched_chart_timeframe_not_silently_resampled(self):
        result = convert(timeframe="H1")
        self.assertFalse(result["valid"])
        self.assertIn("NON_MONOTONIC", result["error"])

    def test_16_hourly_export_uses_hourly_open_and_close(self):
        result = convert(
            mt5_tsv=sample(period=60), timeframe="H1",
        )
        self.assertTrue(result["valid"])
        self.assertEqual(result["first_closed_at"],
                         closed_stamp(0, period=60))

    def test_17_future_close_candle_denied(self):
        result = convert(now=datetime(2026, 9, 30, 19, tzinfo=timezone.utc))
        self.assertFalse(result["valid"])
        self.assertIn("FUTURE_CANDLE", result["error"])

    def test_18_empty_or_oversized_file_blocked(self):
        for content in ("", "A" * (a284.MAX_MT5_BYTES + 1)):
            with self.subTest(size=len(content)):
                result = convert(mt5_tsv=content)
                self.assertFalse(result["valid"])
                self.assertIsNone(result["canonical_closed_csv"])

    def test_19_short_export_blocks_preflight_and_backtest(self):
        short = sample(rows=80)
        cut = closed_stamp(40)
        checked = preflight(mt5_tsv=short, validation_start=cut)
        self.assertTrue(checked["valid"])
        self.assertFalse(checked["ready_for_offline_research"])
        self.assertEqual(checked["status"], "MT5_OFFLINE_PREFLIGHT_INSUFFICIENT")
        result = research(mt5_tsv=short, validation_start=cut)
        self.assertFalse(result["valid"])
        self.assertIsNone(result["comparison"])

    def test_20_native_to_a283_preflight_keeps_both_hashes(self):
        result = preflight()
        self.assertTrue(result["valid"])
        self.assertTrue(result["ready_for_offline_research"])
        self.assertEqual(result["preflight"]["train"]["candle_count"], 120)
        self.assertEqual(result["preflight"]["holdout"]["candle_count"], 120)
        self.assertEqual(result["preflight"]["raw_csv_sha256"],
                         result["canonical_csv_sha256"])

    def test_21_native_to_a282_comparison_has_no_fake_edge(self):
        result = research()
        self.assertTrue(result["valid"])
        self.assertTrue(result["research_only"])
        self.assertEqual(result["comparison"]["status"],
                         "INSUFFICIENT_HOLDOUT_SAMPLE_FOR_COMPARISON")
        self.assertEqual(len(result["comparison"]["models"]), 3)
        self.assertFalse(result["comparison"]["authorizes_send"])
        self.assertFalse(result["authorizes_send"])

    def test_22_bad_cut_or_cost_never_returns_partial_comparison(self):
        wrong = research(validation_start="2026-10-02T02:16:00+00:00")
        self.assertFalse(wrong["valid"])
        self.assertIsNone(wrong["comparison"])
        bad_cost = research(cost_r=-1)
        self.assertFalse(bad_cost["valid"])
        self.assertIsNone(bad_cost["comparison"])

    def test_23_source_sha_and_canonical_sha_different_and_stable(self):
        first, second = convert(), convert()
        self.assertEqual(first, second)
        self.assertNotEqual(first["source_mt5_sha256"],
                            first["canonical_csv_sha256"])
        self.assertEqual(len(first["source_mt5_sha256"]), 64)
        self.assertEqual(len(first["canonical_csv_sha256"]), 64)

    def test_24_strict_offset_is_not_verified_dst_provenance(self):
        result = research()
        self.assertFalse(result["broker_utc_offset_is_verified"])
        self.assertFalse(result["dst_transitions_verified"])
        self.assertFalse(result["source_export_is_externally_attested"])
        self.assertFalse(result["broker_symbol_to_research_id_verified"])
        self.assertFalse(result["futures_contract_expiry_verified"])

    def test_25_tampered_a283_comparison_digest_stays_blocked(self):
        original = a284.compare_if_preflight_ready_csv
        def tampered(*a, **kw):
            report = original(*a, **kw)
            report["preflights"][0]["raw_csv_sha256"] = "0" * 64
            return report
        with mock.patch.object(a284, "compare_if_preflight_ready_csv",
                               tampered):
            result = research()
        self.assertFalse(result["valid"])
        self.assertEqual(result["error"],
                         "MT5_A283_A282_DIGEST_OR_AUTHORITY_MISMATCH")
        self.assertIsNone(result["comparison"])

    def test_26_no_broker_terminal_new_calls_alerts_orders_or_p0(self):
        for result in (convert(), preflight(), research()):
            self.assertTrue(result["no_data_download"])
            self.assertTrue(result["no_new_data_calls"])
            self.assertTrue(result["no_orders"])
            self.assertTrue(result["no_alerts"])
            self.assertFalse(result["authorizes_send"])
            self.assertEqual(result["p0_homologated"], 0)


if __name__ == "__main__":
    unittest.main()
