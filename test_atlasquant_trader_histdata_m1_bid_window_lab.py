"""HistData fixed EST, Bid-only, no-volume M1-to-M15 event tests."""
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import unittest

from atlasquant_trader_histdata_m1_bid_window_lab import (
    EST_FIXED, SCHEMA, inspect_histdata_m1_bid_window_lab as inspect,
)

EVENT = datetime(2026, 10, 28, 18, 0, tzinfo=timezone.utc)
CAPTURE = datetime(2026, 11, 5, 3, tzinfo=timezone.utc)
AS_OF = CAPTURE + timedelta(minutes=1)
NAME = "DAT_ASCII_EURUSD_M1_202610.csv"


def lines(*, event=EVENT, count=120, start_delta_minutes=-60):
    start = event + timedelta(minutes=start_delta_minutes)
    vals = []
    for i in range(count):
        est = (start + timedelta(minutes=i)).astimezone(EST_FIXED)
        vals.append(est.strftime("%Y%m%d %H%M%S") +
                    ";1.110000;1.111000;1.109000;1.110500;0")
    return vals


def blob(rows=None, **kwargs):
    return ("\n".join(lines(**kwargs) if rows is None else rows) + "\n").encode()


_UNSET = object()


def run(raw=_UNSET, **kwargs):
    args = dict(filename=NAME, expected_symbol="EURUSD",
                captured_at_utc=CAPTURE, as_of_utc=AS_OF,
                event_at_utc=EVENT)
    args.update(kwargs)
    return inspect(blob() if raw is _UNSET else raw, **args)


class HistDataM1BidWindowTests(unittest.TestCase):
    def test_full_120_m1_creates_eight_complete_but_unverified_m15(self):
        raw = blob()
        r = run(raw)
        self.assertEqual(r["schema"], SCHEMA)
        self.assertEqual(r["state"],
                         "LAB_HISTDATA_BID_M15_WINDOW_STRUCTURALLY_COMPLETE_UNVERIFIED")
        self.assertEqual(r["source_raw_sha256"], sha256(raw).hexdigest())
        self.assertEqual(r["first_m1_open_utc"], "2026-10-28T17:00:00+00:00")
        self.assertEqual(r["last_m1_open_utc"], "2026-10-28T18:59:00+00:00")
        self.assertEqual(r["total_m1_rows"], 120)
        self.assertEqual(r["pre_event_full_m15_bars"], 4)
        self.assertEqual(r["post_event_full_m15_bars"], 4)
        self.assertFalse(r["excluded_event_straddling_m15"])

    def test_mid_candle_event_excludes_15_minute_straddler(self):
        r = run(blob(count=135), event_at_utc=EVENT + timedelta(minutes=7))
        self.assertEqual(r["state"],
                         "LAB_HISTDATA_BID_M15_WINDOW_STRUCTURALLY_COMPLETE_UNVERIFIED")
        self.assertTrue(r["excluded_event_straddling_m15"])

    def test_fixed_est_summer_is_plus_five_utc_not_plus_four(self):
        jul = datetime(2026, 7, 28, 18, tzinfo=timezone.utc)
        r = run(blob(event=jul), event_at_utc=jul,
                filename="DAT_ASCII_EURUSD_M1_202607.csv")
        self.assertEqual(r["state"],
                         "LAB_HISTDATA_BID_M15_WINDOW_STRUCTURALLY_COMPLETE_UNVERIFIED")
        self.assertEqual(r["first_m1_open_utc"], "2026-07-28T17:00:00+00:00")
        self.assertTrue(r["source_applies_no_daylight_saving"])

    def test_bid_only_no_ask_spread_volume_license_or_trade(self):
        for r in (run(), run(b"garbage")):
            self.assertEqual(r["bar_price_side"], "BID")
            for flag in ("ask_prices_present", "spread_at_event_known", "volume_known",
                         "downloaded_source_authenticity_verified",
                         "market_data_product_license_verified",
                         "historical_point_in_time_eligible", "m15_execution_price_verified",
                         "historical_backtest_accuracy_verified", "trade_authorized",
                         "can_feed_live_radar", "publishable", "worker_enabled",
                         "scheduler_enabled"):
                self.assertIs(r[flag], False, flag)
            self.assertIsNone(r["fx_bias"])
            self.assertEqual(r["operational_bias"], "AGUARDAR")
            self.assertEqual(r["new_cost_brl"], 0)

    def test_m1_gap_in_required_window_never_filled(self):
        row = lines()
        del row[17]
        self.assertEqual(run(blob(rows=row))["reason"],
                         "M1_MISSING_IN_REQUIRED_M15_WINDOW_NO_FILL")

    def test_straddling_m1_missing_when_event_non_aligned(self):
        row = lines(count=135)
        del row[64]
        self.assertEqual(run(blob(rows=row), event_at_utc=EVENT+timedelta(minutes=7))["reason"],
                         "M1_MISSING_IN_REQUIRED_M15_WINDOW_NO_FILL")

    def test_duplicate_or_reversed_minutes_denied(self):
        rows = lines()
        for bad in ([rows[0], rows[0]] + rows[2:], list(reversed(rows))):
            self.assertEqual(run(blob(rows=bad))["state"], "LAB_BLOCKED")

    def test_reject_changed_volume_or_false_tick_volume(self):
        rows = lines()
        rows[2] = rows[2][:-1] + "1"
        self.assertEqual(run(blob(rows=rows))["state"], "LAB_BLOCKED")

    def test_reject_bad_ohlc_price(self):
        for replacement in ("1.099000", "NaN", "-1", "1,11", "1e4", ""):
            rows = lines()
            rows[10] = rows[10].replace("1.111000", replacement)
            self.assertEqual(run(blob(rows=rows))["state"], "LAB_BLOCKED")

    def test_reject_invalid_low_or_close_above_high(self):
        for search, replacement in (("1.109000", "1.115000"),
                                    ("1.110500", "1.113000")):
            rows = lines()
            rows[15] = rows[15].replace(search, replacement)
            self.assertEqual(run(blob(rows=rows))["state"], "LAB_BLOCKED")

    def test_reject_missing_or_invalid_est_minute(self):
        for stamp in ("20261028 126000", "20261028 120030", "20261032 120000",
                      "2026.10.28,12:00"):
            rows = lines()
            rows[0] = stamp + ";1.110000;1.111000;1.109000;1.110500;0"
            self.assertEqual(run(blob(rows=rows))["state"], "LAB_BLOCKED")

    def test_reject_mixed_month_in_one_file(self):
        rows = lines()
        rows[0] = rows[0].replace("20261028", "20260928")
        self.assertEqual(run(blob(rows=rows))["state"], "LAB_BLOCKED")

    def test_reject_wrong_pair_file_schema_and_suffix(self):
        for name in ("DAT_ASCII_GBPUSD_M1_202610.csv", "DAT_MT_EURUSD_M1_202610.csv",
                     "DAT_ASCII_EURUSD_T_202610.csv", "DAT_ASCII_EURUSD_M1_202613.csv"):
            self.assertEqual(run(filename=name)["state"], "LAB_BLOCKED")

    def test_reject_wrong_currencies_or_direction(self):
        for symbol in ("USDEUR", "XAUUSD", "USDUSD", "EURJPY"):
            self.assertEqual(run(expected_symbol=symbol)["state"], "LAB_BLOCKED")

    def test_reject_future_capture_naive_or_event_after_as_of(self):
        for args in (dict(captured_at_utc=datetime(2026, 11, 5)),
                     dict(as_of_utc=CAPTURE-timedelta(minutes=2)),
                     dict(event_at_utc=datetime(2026, 11, 6, tzinfo=timezone.utc)),
                     dict(event_at_utc=None)):
            self.assertEqual(run(**args)["state"], "LAB_BLOCKED")

    def test_reject_data_future_relative_capture(self):
        late = datetime(2026, 11, 5, 3, tzinfo=timezone.utc)
        raw = blob(event=late, count=120)
        self.assertEqual(run(raw, filename="DAT_ASCII_EURUSD_M1_202611.csv")["state"],
                         "LAB_BLOCKED")

    def test_reject_wrong_delimiters_unicode_or_headers(self):
        for raw in (blob().replace(b";", b",", 3), b"header\n"+blob(),
                    blob()+b"\xff", b"", None, "CSV"):
            self.assertEqual(run(raw)["state"], "LAB_BLOCKED")

    def test_reject_too_few_rows_no_invented_history(self):
        self.assertEqual(run(blob(rows=lines(count=90)))["state"], "LAB_BLOCKED")


if __name__ == "__main__":
    unittest.main()
