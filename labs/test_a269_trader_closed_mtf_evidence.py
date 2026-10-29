"""A269: per-timeframe closed candles are separate, locally untrusted inputs."""
from datetime import timedelta, datetime, timezone
import inspect
import math
import unittest
from unittest import mock

from atlasquant_instrument_registry import FX_28
from atlasquant_aion_trader_timeframes import (
    SOURCE, PERIOD_MINUTES, NO_SEPARATE, STALE, INVALID, CONFLICT,
    classify_tf,
)
from atlasquant_aion_trader_observation import trader_readonly_observation
from labs.test_a268_trader_readonly_observation import NOW, _row, _resident, _find
import atlasquant_trader_resident


def candle(at, *, close=1.152, open_=1.151, high=1.154, low=1.150):
    return {
        "closed_at": at.isoformat(), "open": open_, "high": high,
        "low": low, "close": close,
    }


def evidence(tf="M5", *, close=1.152, date=NOW):
    period = timedelta(minutes=PERIOD_MINUTES[tf])
    return {
        "timeframe": tf,
        "source": SOURCE,
        "closed_candles": True,
        "fetched_at": date.isoformat(),
        "bars": [
            candle(date - 2 * period, close=close),
            candle(date - period, close=close),
        ],
    }


def board(input_, *, resident=None):
    return trader_readonly_observation(
        resident if resident is not None else _resident(),
        now=NOW, timeframe_evidence=input_,
    )


class A269ClosedTimeframesTests(unittest.TestCase):
    def test_01_without_new_input_A268_is_backwards_compatible(self):
        row = _row()
        old = trader_readonly_observation(_resident(row), now=NOW)
        new = trader_readonly_observation(
            _resident(row), now=NOW, timeframe_evidence=None,
        )
        self.assertEqual(old, new)
        self.assertEqual(new["fresh_m15_pairs"], 1)
        self.assertNotIn("mtf_coverage", new)

    def test_02_all_six_periods_need_separate_closed_input(self):
        data = {tf: evidence(tf) for tf in PERIOD_MINUTES}
        result = board({"EURUSD": data}, resident=_resident(_row()))
        for tf in PERIOD_MINUTES:
            self.assertEqual(
                _find(result, "EURUSD")["timeframes"][tf],
                "FRESH_CLOSED_M15" if tf == "M15"
                else "INPUT_FRESH_CLOSED_" + tf + "_UNATTESTED",
            )
        self.assertEqual(result["mtf_coverage"], {tf: 1 for tf in PERIOD_MINUTES})
        self.assertEqual(result["fresh_m15_pairs"], 1)
        self.assertFalse(result["mtf_coverage_is_external_attestation"])
        self.assertTrue(result["no_orders"])

    def test_03_one_tf_never_implies_other_timeframes(self):
        result = board({"EURUSD": {"M5": evidence("M5")}})
        item = _find(result, "EURUSD")
        self.assertEqual(item["timeframes"]["M5"], "INPUT_FRESH_CLOSED_M5_UNATTESTED")
        for tf in ("M15", "M30", "H1", "H4", "D1"):
            self.assertEqual(item["timeframes"][tf], "MISSING" if tf == "M15" else NO_SEPARATE)

    def test_04_supplier_claim_cannot_raise_verified_M15_counter(self):
        result = board({pair: {"M15": evidence("M15")} for pair in FX_28})
        self.assertEqual(result["mtf_coverage"]["M15"], 28)
        self.assertEqual(result["fresh_m15_pairs"], 0)
        self.assertFalse(result["all_28_fresh_closed_m15"])
        self.assertTrue(all(x["recommendation"] == "NONE_READ_ONLY" for x in result["rows"]))

    def test_05_matching_resident_M15_keeps_current_legacy_coverage(self):
        result = board(
            {"EURUSD": {"M15": evidence("M15", close=1.152)}},
            resident=_resident(_row()),
        )
        self.assertEqual(result["fresh_m15_pairs"], 1)
        self.assertEqual(_find(result, "EURUSD")["market_evidence"], "FRESH_CLOSED_M15")

    def test_06_different_M15_close_for_same_pair_blocks_both(self):
        result = board(
            {"EURUSD": {"M15": evidence("M15", close=1.22)}},
            resident=_resident(_row()),
        )
        self.assertEqual(result["fresh_m15_pairs"], 0)
        self.assertEqual(_find(result, "EURUSD")["market_evidence"], CONFLICT)

    def test_07_stale_optional_M15_does_not_fallback_to_fresh_resident(self):
        old = evidence("M15")
        old["bars"][-1]["closed_at"] = (NOW - timedelta(hours=3)).isoformat()
        old["bars"][0]["closed_at"] = (NOW - timedelta(hours=4)).isoformat()
        result = board({"EURUSD": {"M15": old}}, resident=_resident(_row()))
        self.assertEqual(_find(result, "EURUSD")["market_evidence"], STALE)
        self.assertEqual(result["fresh_m15_pairs"], 0)
        self.assertEqual(result["historical_m15_pairs"], 1)

    def test_08_future_bar_and_future_fetch_never_current(self):
        for field in ("closed_at", "fetched_at"):
            with self.subTest(field=field):
                row = evidence("M5")
                if field == "closed_at":
                    row["bars"][-1][field] = (NOW + timedelta(minutes=1)).isoformat()
                else:
                    row[field] = (NOW + timedelta(minutes=1)).isoformat()
                self.assertEqual(_find(board({"EURUSD": {"M5": row}}),
                                       "EURUSD")["timeframes"]["M5"], INVALID)

    def test_09_naive_nonparseable_and_missing_time_denied(self):
        for val in ("2026-10-29T17:00:00", "x", "", 0, None):
            with self.subTest(value=val):
                row = evidence("H1")
                row["bars"][-1]["closed_at"] = val
                self.assertEqual(classify_tf(row, "H1", now=NOW)[0], INVALID)

    def test_10_false_closed_metadata_wrong_source_or_wrong_timeframe(self):
        variants = [
            ("closed_candles", False),
            ("closed_candles", "true"),
            ("source", "UNVERIFIED_WEB"),
            ("timeframe", "H4"),
        ]
        for name, value in variants:
            with self.subTest(name=name, val=value):
                row = evidence("M30")
                row[name] = value
                self.assertEqual(classify_tf(row, "M30", now=NOW)[0], INVALID)

    def test_11_malformed_ohlc_and_nonfinite_denied(self):
        for name, value in [
            ("open", True), ("close", 0.0), ("close", float("nan")),
            ("close", float("inf")), ("high", 1.0), ("low", 1.16),
        ]:
            with self.subTest(field=name, value=str(value)):
                item = evidence("M5")
                item["bars"][-1][name] = value
                self.assertEqual(classify_tf(item, "M5", now=NOW)[0], INVALID)

    def test_12_duplicate_out_of_order_or_M5_mislabeled_H4_denied(self):
        for times in (
            (NOW - timedelta(minutes=5), NOW - timedelta(minutes=5)),
            (NOW - timedelta(minutes=5), NOW - timedelta(minutes=10)),
            (NOW - timedelta(minutes=10), NOW - timedelta(minutes=5)),
        ):
            with self.subTest(times=times):
                item = evidence("H4")
                for bar, when in zip(item["bars"], times):
                    bar["closed_at"] = when.isoformat()
                self.assertEqual(classify_tf(item, "H4", now=NOW)[0], INVALID)

    def test_13_closed_bar_after_snapshot_fetch_denied(self):
        item = evidence("M15")
        item["fetched_at"] = (NOW - timedelta(hours=3)).isoformat()
        self.assertEqual(classify_tf(item, "M15", now=NOW)[0], INVALID)

    def test_14_stale_D1_and_H4_are_historical_not_current(self):
        for tf in ("D1", "H4"):
            item = evidence(tf)
            days = 8
            p = timedelta(days=days)
            item["bars"] = [
                candle(NOW - p - timedelta(minutes=PERIOD_MINUTES[tf])),
                candle(NOW - p),
            ]
            result = board({"EURUSD": {tf: item}})
            self.assertEqual(_find(result, "EURUSD")["timeframes"][tf], STALE)

    def test_15_alias_collision_rejected_instead_of_overwrite(self):
        row = evidence("M5")
        result = board({"EURUSD": {"M5": row}, "EUR/USD": {"M5": row}})
        self.assertEqual(result["mtf_input_duplicate_pairs"], ["EURUSD"])
        self.assertEqual(_find(result, "EURUSD")["timeframes"]["M5"], INVALID)
        self.assertEqual(result["mtf_coverage"]["M5"], 0)

    def test_16_extra_unknown_pair_not_counted_as_FX(self):
        result = board({
            "DXY": {"M5": evidence("M5")},
            "EURUSD": {"M5": evidence("M5")},
        })
        self.assertEqual(result["mtf_input_unknown_pairs"], 1)
        self.assertEqual(result["mtf_coverage"]["M5"], 1)
        self.assertEqual(len(result["rows"]), 28)

    def test_17_malformed_root_never_silently_validates_legacy_M15(self):
        for bad in ([], "verified", None, {"X" + str(i): {} for i in range(101)}):
            with self.subTest(kind=type(bad).__name__):
                # None bypasses the optional extension completely, by design.
                if bad is None:
                    continue
                result = board(bad, resident=_resident(_row()))
                self.assertFalse(result["mtf_input_root_valid"])
                self.assertEqual(result["fresh_m15_pairs"], 0)
                self.assertEqual(_find(result, "EURUSD")["market_evidence"], INVALID)

    def test_18_malformed_pair_record_must_not_inherit_fresh_M15(self):
        result = board({"EURUSD": ["fake"]}, resident=_resident(_row()))
        self.assertEqual(_find(result, "EURUSD")["market_evidence"], INVALID)
        self.assertEqual(result["fresh_m15_pairs"], 0)

    def test_19_period_unknown_or_injected_extraneous_field_denied(self):
        result = board({"EURUSD": {"M1": evidence("M5")}})
        self.assertEqual(_find(result, "EURUSD")["timeframes"]["M15"], INVALID)
        item = evidence("M5")
        item["provider_verified"] = True
        result = board({"GBPUSD": {"M5": item}})
        self.assertEqual(_find(result, "GBPUSD")["timeframes"]["M5"], INVALID)

    def test_20_missing_timeframe_does_not_clear_existing_valid_M15(self):
        result = board({"EURUSD": {"H4": evidence("H4")}}, resident=_resident(_row()))
        self.assertEqual(result["fresh_m15_pairs"], 1)
        self.assertEqual(_find(result, "EURUSD")["timeframes"]["M15"], "FRESH_CLOSED_M15")
        self.assertEqual(result["mtf_coverage"]["H4"], 1)

    def test_21_only_28_verified_resident_M15_can_claim_28_current(self):
        result = board(
            {p: {"M15": evidence("M15")} for p in FX_28},
            resident=_resident(*[_row(p) for p in FX_28]),
        )
        self.assertTrue(result["all_28_fresh_closed_m15"])
        bad = {p: {"M15": evidence("M15")} for p in FX_28}
        bad[FX_28[-1]] = {"M15": evidence("M15", close=1.9)}
        denied = board(bad, resident=_resident(*[_row(p) for p in FX_28]))
        self.assertEqual(denied["fresh_m15_pairs"], 27)
        self.assertFalse(denied["all_28_fresh_closed_m15"])

    def test_22_hydration_only_consumes_explicit_supplied_candles(self):
        state = _resident(_row())
        session = {}
        with mock.patch.object(
            atlasquant_trader_resident, "resident_trader_state", return_value=state
        ) as loader:
            atlasquant_trader_resident.hydrate_trader_resident_state(
                session, {"unimportant": True},
                timeframe_evidence={"EURUSD": {"H1": evidence("H1", date=datetime.now(timezone.utc))}},
            )
        loader.assert_called_once()
        obs = session["atlasquant_aion_trader_observation"]
        self.assertEqual(obs["mtf_coverage"]["H1"], 1)
        self.assertTrue(obs["no_orders"])
        self.assertFalse(obs["mode"]["authorizes_send"])

    def test_23_invalid_resident_hydration_still_clears_old_result(self):
        session = {"atlasquant_aion_trader_observation": {"verified": True}}
        with mock.patch.object(
            atlasquant_trader_resident, "resident_trader_state",
            side_effect=ValueError("invalid snapshot")
        ):
            atlasquant_trader_resident.hydrate_trader_resident_state(
                session, {}, timeframe_evidence={"EURUSD": {"M5": evidence("M5")}}
            )
        self.assertNotIn("atlasquant_aion_trader_observation", session)

    def test_24_pure_read_only_no_mutation_of_supplied_candles(self):
        row = evidence("M5")
        input_ = {"EURUSD": {"M5": row}}
        before = repr(input_)
        result = board(input_)
        self.assertEqual(repr(input_), before)
        self.assertTrue(result["no_orders"] and result["no_alerts"])
        self.assertFalse(result["mode"]["real_trading_enabled"])
        self.assertTrue(all(not x["authorizes_order"] for x in result["rows"]))

    def test_25_no_provider_client_order_or_network_in_mtf_source(self):
        import atlasquant_aion_trader_timeframes as module
        source = inspect.getsource(module)
        for phrase in (
            "import requests", "import socket", "import ccxt",
            "import MetaTrader5", "urllib.request", "ExecutionOutbox(",
            "adapter.send(", "fetch_candles(", "resample(",
        ):
            self.assertNotIn(phrase, source)


if __name__ == "__main__":
    unittest.main()
