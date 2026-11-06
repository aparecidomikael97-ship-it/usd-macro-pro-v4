"""Synthetic-only tests: post-NFP bps are NOT a market prediction or hit."""
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
import json
import unittest

from atlasquant_trader_fx_m15_offline_price_window_lab import EXPORT_SCHEMA, SOURCE_ID
from atlasquant_trader_us_nfp_m15_reaction_lab import (
    EVENT_AT, SCHEMA, inspect_us_nfp_m15_reaction_lab as inspect,
)

CASEBOOK = Path(__file__).parent.joinpath(
    "docs/continuidade/TRADER_US_NFP_OCT2026_PREPOST_DOCUMENTARY_CASE_LAB.json"
).read_bytes()
CAPTURE = EVENT_AT + timedelta(minutes=65)
ASOF = CAPTURE + timedelta(minutes=1)
START = int(EVENT_AT.timestamp()) - 4 * 900


def bars(*, base="1.1000", final="1.1011"):
    rows = []
    for i in range(8):
        value = final if i == 7 else base
        high = "151.0000" if base.startswith("150") else "1.1200"
        low = "149.0000" if base.startswith("150") else "1.0800"
        rows.append({"time": START + i * 900, "open": base,
                     "high": high, "low": low, "close": value,
                     "tick_volume": 123 + i, "spread": 15,
                     "real_volume": 0})
    return rows


def payload(*, pair="EUR/USD", rows=None, **changes):
    obj = {"schema": EXPORT_SCHEMA, "source_id": SOURCE_ID,
           "symbol": pair.replace("/", ""), "timeframe": "M15",
           "timestamp_unit": "unix_seconds_utc",
           "price_basis": "BROKER_REPORTED_UNVERIFIED",
           "bars": bars() if rows is None else rows}
    obj.update(changes)
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode()


_DEFAULT = object()


def run(raw=_DEFAULT, **updates):
    args = {"nfp_casebook_raw": CASEBOOK, "expected_pair": "EUR/USD",
            "captured_at_utc": CAPTURE, "as_of_utc": ASOF}
    args.update(updates)
    return inspect(mt5_m15_raw=payload() if raw is _DEFAULT else raw, **args)


class NfpM15PostEventArithmeticLabTests(unittest.TestCase):
    def test_pair_up_usd_quote_exact_reciprocal_not_negated_bps(self):
        raw = payload()
        result = run(raw)
        self.assertEqual(result["schema"], SCHEMA)
        self.assertEqual(result["state"], "LAB_POST_NFP_M15_CLAIMED_PRICE_ARITHMETIC_ONLY")
        self.assertEqual(result["pair"], "EUR/USD")
        self.assertEqual(result["usd_side"], "QUOTE")
        self.assertEqual(result["post_nfp_pair_return_bps_unverified"], "10.00")
        self.assertEqual(result["usd_oriented_post_nfp_return_bps_unverified"], "-9.99")
        self.assertEqual(result["mt5_claimed_export_sha256"], sha256(raw).hexdigest())
        self.assertEqual(result["pre_event_reference_close_at_utc"], EVENT_AT.isoformat())
        self.assertEqual(result["post_event_first_hour_close_at_utc"],
                         (EVENT_AT + timedelta(hours=1)).isoformat())

    def test_usd_base_preserves_return_sign_and_magnitude(self):
        raw = payload(pair="USD/JPY", rows=bars(base="150.0000", final="150.1500"))
        r = run(raw, expected_pair="USD/JPY")
        self.assertEqual(r["state"], "LAB_POST_NFP_M15_CLAIMED_PRICE_ARITHMETIC_ONLY")
        self.assertEqual(r["usd_side"], "BASE")
        self.assertEqual(r["post_nfp_pair_return_bps_unverified"], "10.00")
        self.assertEqual(r["usd_oriented_post_nfp_return_bps_unverified"], "10.00")

    def test_usd_quote_falling_rate_means_usd_relative_appreciation_arithmetic(self):
        b = bars(final="1.0989")
        r = run(payload(rows=b))
        self.assertEqual(r["post_nfp_pair_return_bps_unverified"], "-10.00")
        self.assertEqual(r["usd_oriented_post_nfp_return_bps_unverified"], "10.01")

    def test_unchanged_price_does_not_imply_predictive_success(self):
        r = run(payload(rows=bars(final="1.1000")))
        self.assertEqual(r["post_nfp_pair_return_bps_unverified"], "0.00")
        self.assertEqual(r["usd_oriented_post_nfp_return_bps_unverified"], "0.00")
        self.assertEqual(r["validated_prediction_count"], 0)

    def test_never_promotes_to_forecast_signal_or_operational_radar(self):
        for r in (run(), run(b"invalid")):
            for field in (
                "market_source_and_broker_identity_authenticated",
                "broker_timestamp_and_price_side_independently_verified",
                "historical_price_vintage_independently_verified",
                "reuters_consensus_vintage_independently_witnessed",
                "reaction_attributable_to_nfp_verified",
                "bid_ask_spread_slippage_execution_verified",
                "d1_w1_forecast_registered_before_event",
                "directional_backtest_accuracy_verified", "trade_authorized",
                "can_feed_live_radar", "publishable", "worker_enabled",
                "scheduler_enabled",
            ):
                self.assertIs(r[field], False, field)
            self.assertEqual(r["operational_bias"], "AGUARDAR")
            self.assertIsNone(r["fx_bias"])
            self.assertIsNone(r["usd_macro_strength"])
            self.assertIsNone(r["validated_accuracy"])
            self.assertEqual(r["validated_prediction_count"], 0)
            self.assertEqual(r["http_requests"], 0)
            self.assertEqual(r["new_cost_brl"], 0)

    def test_requires_oct2026_documentary_case_fixed_and_post_bls(self):
        obj = json.loads(CASEBOOK)
        obj["records"][2]["reported_values"]["nonfarm_payroll_forecast_persons_sa"] = "40000"
        changed = json.dumps(obj).encode()
        for value in (None, b"corrupt", changed):
            r = run(nfp_casebook_raw=value)
            self.assertEqual(r["state"], "LAB_BLOCKED")
            self.assertEqual(r["reason"], "NFP_DOCUMENTARY_RELEASE_NOT_AVAILABLE_OR_CHANGED")

    def test_asof_before_official_release_is_not_a_post_event_measurement(self):
        r = run(captured_at_utc=EVENT_AT - timedelta(minutes=1),
                as_of_utc=EVENT_AT - timedelta(seconds=1))
        self.assertEqual(r["state"], "LAB_BLOCKED")
        self.assertEqual(r["reason"], "NFP_DOCUMENTARY_RELEASE_NOT_AVAILABLE_OR_CHANGED")

    def test_14_30_candle_close_must_exist_before_capture(self):
        r = run(captured_at_utc=EVENT_AT + timedelta(minutes=59),
                as_of_utc=EVENT_AT + timedelta(minutes=59))
        self.assertEqual(r["state"], "LAB_BLOCKED")
        self.assertEqual(r["reason"], "BROKER_M15_EXPORTED_WINDOW_INVALID_OR_INCOMPLETE")

    def test_broker_window_missing_one_post_bar_is_blocked(self):
        b = bars()
        del b[-1]
        self.assertEqual(run(payload(rows=b))["state"], "LAB_BLOCKED")

    def test_broker_window_gap_is_blocked(self):
        b = bars()
        b[-1]["time"] += 900
        self.assertEqual(run(payload(rows=b))["state"], "LAB_BLOCKED")

    def test_duplicate_json_keys_blocked_upstream(self):
        raw = payload().replace(b'"timeframe":"M15",',
                                b'"timeframe":"M15","timeframe":"M15",')
        self.assertEqual(run(raw)["state"], "LAB_BLOCKED")

    def test_inaccurate_timestamp_unit_is_blocked(self):
        self.assertEqual(run(payload(timestamp_unit="server_local"))["state"],
                         "LAB_BLOCKED")

    def test_symbol_mismatch_and_price_basis_false_claims_are_blocked(self):
        for raw in (payload(pair="GBP/USD"), payload(price_basis="VERIFIED_BID")):
            self.assertEqual(run(raw)["state"], "LAB_BLOCKED")

    def test_non_usd_pair_and_unknown_pair_are_blocked(self):
        for pair in ("EUR/JPY", "XAU/USD", "USD/EUR", "USD/USD", None):
            self.assertEqual(run(expected_pair=pair)["state"], "LAB_BLOCKED")

    def test_clock_naive_reversed_and_non_datetime_are_blocked(self):
        for changes in (
            {"captured_at_utc": datetime(2026, 11, 6, 14, 35)},
            {"as_of_utc": CAPTURE - timedelta(seconds=1)},
            {"as_of_utc": "2026-11-06T14:36:00Z"},
            {"captured_at_utc": None},
        ):
            self.assertEqual(run(**changes)["state"], "LAB_BLOCKED")

    def test_unreasonably_large_claimed_move_requires_human_review(self):
        b = bars(final="1.2200")
        b[-1]["high"] = "1.2300"
        r = run(payload(rows=b))
        self.assertEqual(r["state"], "LAB_BLOCKED")
        self.assertEqual(r["reason"], "OUTLIER_CLAIMED_FIRST_HOUR_FX_MOVE_NEEDS_SOURCE_REVIEW")

    def test_non_broker_float_price_is_blocked(self):
        b = bars()
        b[0]["close"] = 1.10
        self.assertEqual(run(payload(rows=b))["state"], "LAB_BLOCKED")


if __name__ == "__main__":
    unittest.main()
