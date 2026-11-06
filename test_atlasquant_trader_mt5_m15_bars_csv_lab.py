"""Zero-network MT5 native Bars CSV tests; all prices are synthetic."""
from datetime import datetime, timedelta
from hashlib import sha256
import unittest

from atlasquant_instrument_registry import FX_28
from atlasquant_trader_mt5_m15_bars_csv_lab import (
    SCHEMA, EXPECTED_HEADER, inspect_mt5_m15_bars_csv_lab as inspect,
)


def make_csv(*, rows=9, delimiter="\t", start="2026.11.02 11:00:00",
             symbol="EURUSD", change=None, bom=False):
    start_time = datetime.strptime(start, "%Y.%m.%d %H:%M:%S")
    result = [delimiter.join(EXPECTED_HEADER)]
    for idx in range(rows):
        time = start_time + timedelta(minutes=15*idx)
        record = [
            time.strftime("%Y.%m.%d"),
            time.strftime("%H:%M:%S"),
            "1.1100", "1.1120", "1.1090", "1.1110",
            str(150+idx), "0", "12",
        ]
        if change and idx in change:
            record = change[idx](record)
        result.append(delimiter.join(record))
    raw = ("\n".join(result) + "\n").encode("utf-8")
    return (b"\xef\xbb\xbf" + raw) if bom else raw


_UNSET = object()


def run(raw=_UNSET, **kwargs):
    options = {"declared_symbol": "EURUSD"}
    options.update(kwargs)
    return inspect(make_csv() if raw is _UNSET else raw, **options)


def edited(column, replacement):
    def mod(row):
        row[column] = replacement
        return row
    return mod


class Mt5M15CsvAuditTests(unittest.TestCase):
    def assert_no_go(self, r):
        for key in (
            "time_values_are_utc_verified",
            "source_broker_identified_independently",
            "symbol_identity_independently_verified",
            "bid_ask_price_side_verified",
            "source_original_export_authenticated",
            "historical_vintage_point_in_time_verified",
            "historical_m15_execution_price_verified",
            "fx_ny_1700_d1w1_aligned",
            "usable_for_directional_backtest",
            "trade_authorized", "can_feed_live_radar", "worker_enabled",
            "scheduler_enabled", "publishable",
        ):
            self.assertFalse(r[key], key)
        self.assertIsNone(r["historical_predictive_accuracy"])
        self.assertIsNone(r["fx_bias"])
        self.assertEqual(r["broker_server_timezone"], "UNKNOWN_UNATTESTED")
        self.assertEqual(r["operational_bias"], "AGUARDAR")
        self.assertEqual((r["http_requests"], r["new_cost_brl"]), (0, 0))

    def test_tab_native_header_and_9_bars_structure(self):
        raw = make_csv()
        r = run(raw)
        self.assertEqual(r["schema"], SCHEMA)
        self.assertEqual(r["state"], "LAB_MT5_M15_CSV_STRUCTURE_VALID_SERVER_CLOCK_UNATTESTED")
        self.assertEqual(r["declared_symbol"], "EURUSD")
        self.assertEqual(r["source_sha256"], sha256(raw).hexdigest())
        self.assertEqual((r["csv_delimiter"], r["row_count"]), ("tab", 9))
        self.assertEqual(r["earliest_server_local_bar"], "2026-11-02T11:00:00")
        self.assertEqual(r["latest_server_local_bar"], "2026-11-02T13:00:00")
        self.assertEqual(r["non_15_minute_gaps_inside_broker_dates"], 0)
        self.assert_no_go(r)

    def test_comma_header_and_utf8_bom_accepted(self):
        raw = make_csv(delimiter=",", bom=True)
        r = run(raw)
        self.assertEqual(r["state"], "LAB_MT5_M15_CSV_STRUCTURE_VALID_SERVER_CLOCK_UNATTESTED")
        self.assertEqual(r["csv_delimiter"], "comma")
        self.assertEqual(r["source_bytes"], len(raw))
        self.assert_no_go(r)

    def test_28_pairs_can_be_declared_but_never_attested_from_csv(self):
        raw = make_csv()
        for symbol in FX_28:
            r = run(raw, declared_symbol=symbol)
            self.assertEqual(r["state"], "LAB_MT5_M15_CSV_STRUCTURE_VALID_SERVER_CLOCK_UNATTESTED")
            self.assertEqual(r["declared_symbol"], symbol)
            self.assertFalse(r["symbol_identity_independently_verified"])
            self.assert_no_go(r)

    def test_missing_one_bar_within_date_is_counted_not_synthesized(self):
        lines = make_csv().decode().splitlines()
        del lines[4]
        r = run(("\n".join(lines) + "\n").encode())
        self.assertEqual(r["row_count"], 8)
        self.assertEqual(r["non_15_minute_gaps_inside_broker_dates"], 1)
        self.assert_no_go(r)

    def test_broker_midnight_and_weekend_are_not_assumed_utc(self):
        raw = make_csv(start="2026.11.01 22:00:00")
        r = run(raw)
        self.assertGreater(r["weekend_dated_bars"], 0)
        self.assertFalse(r["time_values_are_utc_verified"])
        self.assertFalse(r["fx_ny_1700_d1w1_aligned"])

    def test_zero_spread_is_counted_not_taken_as_real_zero_cost(self):
        raw = make_csv(change={0: edited(8, "0")})
        r = run(raw)
        self.assertEqual(r["zero_spread_bars"], 1)
        self.assertFalse(r["bid_ask_price_side_verified"])
        self.assert_no_go(r)

    def test_duplicate_and_unsorted_timestamp_blocked(self):
        raw = make_csv()
        lines = raw.decode().splitlines()
        duplicate = lines[:]
        duplicate[3] = duplicate[2]
        for broken in (duplicate, list(reversed(lines))):
            out = run(("\n".join(broken)+"\n").encode())
            self.assertEqual(out["state"], "LAB_BLOCKED")

    def test_timestamp_not_m15_boundary_rejected(self):
        for replacement in ("11:01:00", "11:13:00", "11:15:01", "25:00:00"):
            r = run(make_csv(change={2: edited(1, replacement)}))
            self.assertEqual(r["state"], "LAB_BLOCKED")

    def test_missing_bad_date_or_time_rejected(self):
        for replacement in ("2026-13-02", "2026/11/02", "2026.02.30", ""):
            r = run(make_csv(change={1: edited(0, replacement)}))
            self.assertEqual(r["state"], "LAB_BLOCKED")

    def test_ohlc_outside_range_rejected(self):
        for idx, price in ((2, "1.1130"), (3, "1.1099"),
                           (4, "1.1111"), (5, "1.1130")):
            r = run(make_csv(change={0: edited(idx, price)}))
            self.assertEqual(r["state"], "LAB_BLOCKED")

    def test_invalid_price_rejected(self):
        for bad in ("NaN", "inf", "-1.1", "1,1100", "1e2", "9999", "", " 1.1"):
            r = run(make_csv(change={0: edited(2, bad)}))
            self.assertEqual(r["state"], "LAB_BLOCKED")

    def test_invalid_volumes_or_spread_rejected(self):
        for column, replacement in ((6, "0"), (6, "1.5"), (7, "-1"),
                                    (7, "NaN"), (8, "-1"), (8, "12.5"),
                                    (8, "1000001")):
            r = run(make_csv(change={0: edited(column, replacement)}))
            self.assertEqual(r["state"], "LAB_BLOCKED")

    def test_bad_header_rejected_instead_of_guessing_format(self):
        raw = make_csv()
        for old in (b"<TIME>", b"<TICKVOL>", b"<SPREAD>"):
            r = run(raw.replace(old, b"<OTHER>", 1))
            self.assertEqual(r["state"], "LAB_BLOCKED")
            self.assertEqual(r["reason"], "NATIVE_MT5_HEADER_NOT_RECOGNIZED")

    def test_missing_unknown_columns_and_internal_blank_row_rejected(self):
        lines = make_csv().decode().splitlines()
        for broken in ([*lines[:3], "", *lines[3:]],
                       [*lines, "2026.11.02"],
                       [*lines, lines[-1]+"\tEXTRA"]):
            r = run(("\n".join(broken) + "\n").encode())
            self.assertEqual(r["state"], "LAB_BLOCKED")

    def test_truncated_snapshot_is_not_filled_with_invented_bars(self):
        lines = make_csv().decode().splitlines()
        r = run(("\n".join(lines[:-1]) + "\n").encode())
        self.assertEqual(r["row_count"], 8)
        self.assert_no_go(r)

    def test_wrong_encoding_or_nulls_rejected(self):
        for raw in (make_csv().decode().encode("utf-16"),
                    b"\x00"+make_csv(), b"\xff"+make_csv()):
            self.assertEqual(run(raw)["state"], "LAB_BLOCKED")

    def test_symbol_and_timeframe_claims_strict(self):
        for wrong in (dict(declared_symbol="XAUUSD"),
                      dict(declared_symbol="EUR/USD"),
                      dict(declared_symbol=None),
                      dict(declared_timeframe="M1"),
                      dict(declared_timeframe="D1")):
            self.assertEqual(run(**wrong)["state"], "LAB_BLOCKED")

    def test_bytes_empty_and_over_limit_denied(self):
        for x in (None, b"", "not bytes", {}, b"bad", b"x"*8_000_001):
            self.assertEqual(run(x)["state"], "LAB_BLOCKED")

    def test_orderless_or_old_broker_data_cannot_be_called_accuracy(self):
        r = run(make_csv(start="2026.10.26 11:00:00"))
        self.assertEqual(r["state"], "LAB_MT5_M15_CSV_STRUCTURE_VALID_SERVER_CLOCK_UNATTESTED")
        self.assertIsNone(r["historical_predictive_accuracy"])
        self.assertFalse(r["usable_for_directional_backtest"])
        self.assert_no_go(r)


    def test_cli_reads_only_selected_file_without_touching_it(self):
        from pathlib import Path
        from tempfile import TemporaryDirectory
        from contextlib import redirect_stdout
        from io import StringIO
        from atlasquant_trader_mt5_m15_bars_csv_lab import main
        with TemporaryDirectory() as tmp:
            file = Path(tmp) / "EURUSD_M15.csv"
            original = make_csv()
            file.write_bytes(original)
            stdout = StringIO()
            with redirect_stdout(stdout):
                code = main(["--csv-file", str(file), "--declared-symbol", "EURUSD"])
            import json
            r = json.loads(stdout.getvalue())
            self.assertEqual(code, 0)
            self.assertEqual(r["state"], "LAB_MT5_M15_CSV_STRUCTURE_VALID_SERVER_CLOCK_UNATTESTED")
            self.assertEqual(r["source_sha256"], sha256(original).hexdigest())
            self.assertEqual(file.read_bytes(), original)
            self.assertEqual([x.name for x in Path(tmp).iterdir()], ["EURUSD_M15.csv"])
            self.assert_no_go(r)

    def test_cli_missing_file_fails_without_creating_it(self):
        from pathlib import Path
        from tempfile import TemporaryDirectory
        from contextlib import redirect_stdout
        from io import StringIO
        from atlasquant_trader_mt5_m15_bars_csv_lab import main
        with TemporaryDirectory() as tmp:
            missing = Path(tmp) / "missing.csv"
            stdout = StringIO()
            with redirect_stdout(stdout):
                code = main(["--csv-file", str(missing), "--declared-symbol", "EURUSD"])
            import json
            r = json.loads(stdout.getvalue())
            self.assertEqual(code, 2)
            self.assertEqual(r["state"], "LAB_BLOCKED")
            self.assertFalse(missing.exists())
            self.assert_no_go(r)

    def test_cli_invalid_symbol_fails_with_no_export_rewriting(self):
        from pathlib import Path
        from tempfile import TemporaryDirectory
        from contextlib import redirect_stdout
        from io import StringIO
        from atlasquant_trader_mt5_m15_bars_csv_lab import main
        with TemporaryDirectory() as tmp:
            file = Path(tmp) / "one.csv"
            payload = make_csv()
            file.write_bytes(payload)
            stdout = StringIO()
            with redirect_stdout(stdout):
                code = main(["--csv-file", str(file), "--declared-symbol", "EUR/EUR"])
            import json
            r = json.loads(stdout.getvalue())
            self.assertEqual(code, 2)
            self.assertEqual(r["state"], "LAB_BLOCKED")
            self.assertEqual(file.read_bytes(), payload)
            self.assert_no_go(r)


if __name__ == "__main__":
    unittest.main()
