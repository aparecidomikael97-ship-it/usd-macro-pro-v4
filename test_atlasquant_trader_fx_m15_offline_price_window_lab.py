"""Zero-cost, zero-broker M15 price replay acceptance and refusal tests."""
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import unittest

from atlasquant_trader_fx_m15_offline_price_window_lab import (
    SCHEMA, EXPORT_SCHEMA, SOURCE_ID,
    inspect_fx_m15_event_window_lab as inspect,
)

EVENT = datetime(2026, 10, 28, 18, 0, tzinfo=timezone.utc)
CAPTURE = datetime(2026, 11, 5, 2, 35, tzinfo=timezone.utc)
AS_OF = CAPTURE + timedelta(minutes=1)
START = int(EVENT.timestamp()) - 4 * 900


def bars(*, count=8, start=START, symbol="EURUSD"):
    return [{"time": start + i * 900, "open": "1.1100",
             "high": "1.1120", "low": "1.1090", "close": "1.1110",
             "tick_volume": 123 + i, "spread": 15, "real_volume": 0}
            for i in range(count)]


def payload(*, rows=None, **overrides):
    obj = {"schema": EXPORT_SCHEMA, "source_id": SOURCE_ID, "symbol": "EURUSD",
           "timeframe": "M15", "timestamp_unit": "unix_seconds_utc",
           "price_basis": "BROKER_REPORTED_UNVERIFIED",
           "bars": bars() if rows is None else rows}
    obj.update(overrides)
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode()


_UNSET = object()


def run(raw=_UNSET, **kwargs):
    args = {"expected_symbol": "EURUSD", "captured_at_utc": CAPTURE,
            "as_of_utc": AS_OF, "event_at_utc": EVENT}
    args.update(kwargs)
    return inspect(payload() if raw is _UNSET else raw, **args)


class M15WindowContractTests(unittest.TestCase):
    def test_complete_aligned_m15_window_is_still_unverified(self):
        raw = payload()
        r = run(raw)
        self.assertEqual(r["schema"], SCHEMA)
        self.assertEqual(r["state"], "LAB_M15_EVENT_WINDOW_STRUCTURALLY_COMPLETE_UNVERIFIED")
        self.assertEqual(r["raw_sha256"], sha256(raw).hexdigest())
        self.assertEqual(r["pre_event_closed_bars"], 4)
        self.assertEqual(r["post_event_closed_bars"], 4)
        self.assertFalse(r["excluded_event_straddling_bar"])
        self.assertEqual(r["event_at_utc"], EVENT.isoformat())
        self.assertEqual(r["first_bar_open_utc"], "2026-10-28T17:00:00+00:00")
        self.assertEqual(r["last_bar_open_utc"], "2026-10-28T18:45:00+00:00")

    def test_straddling_candle_is_excluded_not_counted_as_pre_event(self):
        t = EVENT + timedelta(minutes=7)
        r = run(payload(rows=bars(count=9)), event_at_utc=t)
        self.assertEqual(r["state"], "LAB_M15_EVENT_WINDOW_STRUCTURALLY_COMPLETE_UNVERIFIED")
        self.assertTrue(r["excluded_event_straddling_bar"])
        self.assertEqual(r["pre_event_closed_bars"], 4)
        self.assertEqual(r["post_event_closed_bars"], 4)

    def test_synthetic_price_is_never_trading_authority(self):
        for r in (run(), run(b"malformed")):
            for field in ("historical_point_in_time_eligible", "m15_trade_ready",
                          "historical_backtest_accuracy_verified",
                          "independent_execution_prices_verified",
                          "price_side_broker_attested",
                          "broker_identity_independently_verified",
                          "timestamp_origin_independently_verified",
                          "can_feed_live_radar", "trade_authorized",
                          "publishable", "worker_enabled", "scheduler_enabled"):
                self.assertIs(r[field], False, field)
            self.assertIsNone(r["fx_bias"])
            self.assertEqual(r["operational_bias"], "AGUARDAR")
            self.assertEqual(r["new_cost_brl"], 0)

    def test_reject_missing_pre_post_bar(self):
        for count in (0, 3, 7):
            self.assertEqual(run(payload(rows=bars(count=count)))["state"], "LAB_BLOCKED")

    def test_reject_hole_in_pre_window(self):
        b = bars(count=10, start=START - 900)
        del b[2]
        self.assertEqual(run(payload(rows=b))["reason"],
                         "M15_WINDOW_GAPS_OR_AMBIGUOUS_EVENT_BAR")

    def test_reject_hole_in_post_window(self):
        b = bars(count=9)
        del b[5]
        self.assertEqual(run(payload(rows=b))["reason"],
                         "M15_WINDOW_GAPS_OR_AMBIGUOUS_EVENT_BAR")

    def test_reject_missing_event_straddle_candle(self):
        b = bars(count=10)
        del b[4]
        self.assertEqual(run(payload(rows=b), event_at_utc=EVENT + timedelta(minutes=5))["reason"],
                         "M15_WINDOW_GAPS_OR_AMBIGUOUS_EVENT_BAR")

    def test_reject_duplicate_or_unsorted_bars(self):
        for rows in (
            [*bars(count=7), bars(count=8)[-2]],
            list(reversed(bars())),
        ):
            self.assertEqual(run(payload(rows=rows))["state"], "LAB_BLOCKED")

    def test_reject_non_m15_or_bad_utc_seconds(self):
        for delta in (1, 60, 300):
            b = bars()
            b[3]["time"] += delta
            self.assertEqual(run(payload(rows=b))["state"], "LAB_BLOCKED")

    def test_reject_open_incomplete_or_future_candle(self):
        recent_start = int(CAPTURE.timestamp() // 900) * 900
        b = bars(count=8, start=recent_start - 7 * 900)
        self.assertEqual(run(payload(rows=b))["state"], "LAB_BLOCKED")

    def test_reject_corrupt_ohlc(self):
        for field, value in (("high", "1.1099"), ("low", "1.1111"),
                             ("open", "1.1130"), ("close", "1.1130")):
            b = bars()
            b[4][field] = value
            self.assertEqual(run(payload(rows=b))["state"], "LAB_BLOCKED")

    def test_reject_float_and_nonfinite_prices(self):
        for value in (1.11, "NaN", "Infinity", "-1", "1,1120", "1e2",
                      "0", "", " 1.11", "9999", None):
            b = bars()
            b[0]["close"] = value
            self.assertEqual(run(payload(rows=b))["state"], "LAB_BLOCKED")

    def test_reject_bad_spread_volume_types(self):
        for key, value in (("tick_volume", 0), ("tick_volume", True),
                           ("spread", -1), ("spread", 2.5),
                           ("real_volume", -1), ("real_volume", "0")):
            b = bars()
            b[0][key] = value
            self.assertEqual(run(payload(rows=b))["state"], "LAB_BLOCKED")

    def test_reject_claimed_source_or_timeframe_drift(self):
        for update in ({"timeframe": "H1"}, {"symbol": "GBPUSD"},
                       {"timestamp_unit": "server_local"},
                       {"price_basis": "VERIFIED_BID"},
                       {"source_id": "UNKNOWN"}, {"schema": "OLD"}):
            self.assertEqual(run(payload(**update))["state"], "LAB_BLOCKED")

    def test_eight_g8_currencies_but_pair_orientation_must_match(self):
        self.assertEqual(run(payload(symbol="EURUSD"), expected_symbol="USDEUR")["state"],
                         "LAB_BLOCKED")
        self.assertEqual(run(payload(), expected_symbol="EURJPY")["state"], "LAB_BLOCKED")
        self.assertEqual(run(payload(), expected_symbol="XAUUSD")["state"], "LAB_BLOCKED")
        self.assertEqual(run(payload(), expected_symbol="USDUSD")["state"], "LAB_BLOCKED")

    def test_reject_naive_reversed_or_future_clocks(self):
        for args in (dict(captured_at_utc=datetime(2026, 11, 5)),
                     dict(as_of_utc=CAPTURE - timedelta(seconds=1)),
                     dict(event_at_utc=datetime(2026, 11, 6, tzinfo=timezone.utc)),
                     dict(event_at_utc=None)):
            self.assertEqual(run(**args)["state"], "LAB_BLOCKED")

    def test_reject_json_duplicate_keys_and_extra_columns(self):
        raw = payload().replace(b'"timeframe":"M15",', b'"timeframe":"M15","timeframe":"M15",')
        self.assertEqual(run(raw)["state"], "LAB_BLOCKED")
        b = bars()
        b[0]["bid_ask_proven"] = True
        self.assertEqual(run(payload(rows=b))["state"], "LAB_BLOCKED")

    def test_reject_malformed_types_and_excess_bytes(self):
        for raw in (None, {}, b"", b"no", b"\xff" * 200,
                    b"x" * (900_001)):
            self.assertEqual(run(raw)["state"], "LAB_BLOCKED")


if __name__ == "__main__":
    unittest.main()
