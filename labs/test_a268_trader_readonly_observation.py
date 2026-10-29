"""A268 Trader-first read-only board; no network, provider, bill or orders."""
from datetime import datetime, timedelta, timezone
from unittest import mock
from pathlib import Path
import inspect
import math
import unittest

from atlasquant_instrument_registry import FX_28, FX_CURRENCIES
from atlasquant_risk_guardian import RiskLimits, RiskState
from atlasquant_aion_trader_observation import (
    SCHEMA, trader_readonly_observation,
)
import atlasquant_trader_resident


NOW = datetime(2026, 10, 29, 18, 0, tzinfo=timezone.utc)


def _row(pair="EURUSD", **change):
    item = {
        "asset": pair, "validated": True,
        "presentation_state": "CURRENT",
        "series_source": "scanner/cache_v110/m15",
        "series_state": "CURRENT",
        "series_as_of": (NOW - timedelta(minutes=20)).isoformat(),
        "series": [1.1501, 1.1511, 1.1520],
        "last_bias": "COMPRA",
    }
    item.update(change)
    return item


def _resident(*rows):
    return {"atlasquant_validated_market_items": list(rows),
            "atlasquant_reference_fx_population": {}}


def _find(board, pair):
    return next(row for row in board["rows"] if row["asset"] == pair)


def _strength(**change):
    example = {
        "scores": {currency: 0.0 for currency in FX_CURRENCIES},
        "source": "synthetic-input-not-provider",
        "as_of": (NOW - timedelta(minutes=2)).isoformat(),
    }
    example["scores"].update({"EUR": 7.0, "USD": 3.0, "JPY": 9.0})
    example.update(change)
    return example


class A268TraderReadOnlyObservationTests(unittest.TestCase):
    def test_01_no_input_never_invents_quotes_signals_or_coverage(self):
        board = trader_readonly_observation({}, now=NOW)
        self.assertEqual(board["schema"], SCHEMA)
        self.assertEqual(len(board["rows"]), 28)
        self.assertEqual(board["fresh_m15_pairs"], 0)
        self.assertFalse(board["all_28_fresh_closed_m15"])
        self.assertTrue(all(x["market_evidence"] == "MISSING" for x in board["rows"]))
        self.assertTrue(all(x["recommendation"] == "NONE_READ_ONLY" for x in board["rows"]))

    def test_02_real_canonical_registry_and_per_pair_m15_are_reused(self):
        board = trader_readonly_observation(_resident(_row()), now=NOW)
        self.assertEqual(tuple(x["asset"] for x in board["rows"]), FX_28)
        self.assertEqual(board["fresh_m15_pairs"], 1)
        self.assertEqual(_find(board, "EURUSD")["market_evidence"], "FRESH_CLOSED_M15")
        self.assertEqual(_find(board, "EURUSD")["timeframes"]["M15"], "FRESH_CLOSED_M15")
        for tf in ("M5", "M30", "H1", "H4", "D1"):
            self.assertEqual(_find(board, "EURUSD")["timeframes"][tf],
                             "NO_SEPARATE_TIMEFRAME_EVIDENCE")
        self.assertEqual(_find(board, "EURUSD")["context_bias_not_signal"], "COMPRA")

    def test_03_recent_snapshot_with_old_technical_series_is_historical(self):
        item = _row(series_as_of=(NOW - timedelta(minutes=71)).isoformat())
        result = trader_readonly_observation(_resident(item), now=NOW)
        self.assertEqual(_find(result, "EURUSD")["market_evidence"], "HISTORICAL_ONLY")
        self.assertEqual(result["fresh_m15_pairs"], 0)

    def test_04_snapshot_current_but_series_marked_stale_is_historical(self):
        item = _row(series_state="HISTORICAL_STALE")
        result = trader_readonly_observation(_resident(item), now=NOW)
        self.assertEqual(_find(result, "EURUSD")["market_evidence"], "HISTORICAL_ONLY")

    def test_05_unverified_quote_cannot_become_current(self):
        for item in (
            _row(validated=False),
            _row(validated=1),
            _row(presentation_state="PREVIEW"),
            _row(series_source="unknown/provider"),
            _row(series=[1.0]),
            _row(series=[0.0, 1.0]),
        ):
            with self.subTest(item=item):
                result = trader_readonly_observation(_resident(item), now=NOW)
                self.assertNotEqual(_find(result, "EURUSD")["market_evidence"],
                                    "FRESH_CLOSED_M15")

    def test_06_future_or_naive_timestamp_never_becomes_live(self):
        for dt in (
            (NOW + timedelta(seconds=1)).isoformat(),
            NOW.replace(tzinfo=None).isoformat(),
            "",
            "garbage",
        ):
            with self.subTest(ts=dt):
                item = _row(series_as_of=dt)
                result = trader_readonly_observation(_resident(item), now=NOW)
                self.assertNotEqual(_find(result, "EURUSD")["market_evidence"],
                                    "FRESH_CLOSED_M15")

    def test_07_closed_m15_from_existing_twelve_cache_is_supported(self):
        item = {
            "asset": "GBPUSD", "validated": True,
            "presentation_state": "CURRENT",
            "series": [1.2, 1.22],
            "quote_source": "twelve_series_v1108 / closed M15",
            "quote_as_of": (NOW - timedelta(minutes=10)).isoformat(),
        }
        result = trader_readonly_observation(_resident(item), now=NOW)
        self.assertEqual(_find(result, "GBPUSD")["market_evidence"],
                         "FRESH_CLOSED_M15")

    def test_08_history_never_promoted_even_with_ambiguous_current_fields(self):
        item = _row(historical_series=[1.0, 1.1])
        result = trader_readonly_observation(_resident(item), now=NOW)
        self.assertNotEqual(_find(result, "EURUSD")["market_evidence"],
                            "FRESH_CLOSED_M15")

    def test_09_alias_duplicate_cannot_count_as_verified_coverage(self):
        result = trader_readonly_observation(
            _resident(_row("EURUSD"), _row("EUR/USD")), now=NOW,
        )
        self.assertEqual(result["duplicate_pairs"], ["EURUSD"])
        self.assertEqual(_find(result, "EURUSD")["market_evidence"],
                         "DUPLICATE_AMBIGUOUS")
        self.assertEqual(result["fresh_m15_pairs"], 0)

    def test_10_all_28_only_when_all_28_individually_current(self):
        all_rows = [_row(pair) for pair in FX_28]
        result = trader_readonly_observation(_resident(*all_rows), now=NOW)
        self.assertTrue(result["all_28_fresh_closed_m15"])
        self.assertEqual(result["fresh_m15_pairs"], 28)
        all_rows[-1] = _row(FX_28[-1], series_as_of=(NOW-timedelta(days=1)).isoformat())
        reduced = trader_readonly_observation(_resident(*all_rows), now=NOW)
        self.assertFalse(reduced["all_28_fresh_closed_m15"])
        self.assertEqual(reduced["fresh_m15_pairs"], 27)

    def test_11_relative_strength_requires_all_eight_currencies(self):
        partial = _strength()
        partial["scores"].pop("JPY")
        result = trader_readonly_observation(_resident(_row()), now=NOW,
                                             currency_strength=partial)
        self.assertEqual(result["relative_strength_status"], "UNAVAILABLE_OR_STALE")
        self.assertEqual(_find(result, "EURUSD")["relative_currency"]["direction"],
                         "UNKNOWN")

    def test_12_relative_strength_is_context_for_every_pair_never_signal(self):
        result = trader_readonly_observation(
            _resident(_row()), now=NOW, currency_strength=_strength(),
        )
        self.assertEqual(result["relative_strength_status"],
                         "FRESH_INPUT_NOT_INDEPENDENTLY_VERIFIED")
        self.assertEqual(_find(result, "EURUSD")["relative_currency"]["direction"],
                         "BASE_STRONGER")
        self.assertEqual(_find(result, "USDJPY")["relative_currency"]["direction"],
                         "QUOTE_STRONGER")
        self.assertEqual(len([
            r for r in result["rows"]
            if r["relative_currency"]["status"] == "UNVERIFIED_INPUT_CONTEXT_ONLY"
        ]), 28)
        self.assertTrue(all(row["recommendation"] == "NONE_READ_ONLY"
                            for row in result["rows"]))

    def test_13_strength_with_nan_bool_future_or_extra_pair_is_rejected(self):
        bad = [
            _strength(scores={**_strength()["scores"], "USD": float("nan")}),
            _strength(scores={**_strength()["scores"], "USD": True}),
            _strength(as_of=(NOW + timedelta(seconds=1)).isoformat()),
            _strength(as_of=(NOW - timedelta(hours=3)).isoformat()),
            _strength(scores={**_strength()["scores"], "PLN": 3}),
            _strength(source=""),
        ]
        for candidate in bad:
            with self.subTest(candidate=str(candidate)[:30]):
                result = trader_readonly_observation(_resident(_row()), now=NOW,
                                                     currency_strength=candidate)
                self.assertEqual(result["relative_strength_status"],
                                 "UNAVAILABLE_OR_STALE")

    def test_14_absent_risk_inputs_always_block_risk_status(self):
        result = trader_readonly_observation(_resident(_row()), now=NOW)
        self.assertEqual(result["risk"]["status"], "UNVERIFIED_BLOCKED")
        self.assertFalse(result["mode"]["real_trading_enabled"])
        self.assertFalse(result["mode"]["authorizes_send"])
        self.assertTrue(result["no_orders"])

    def test_15_existing_risk_guardian_locks_after_daily_loss(self):
        limits = RiskLimits(
            bankroll=10000, max_daily_loss=500, max_loss_per_trade=100,
            max_trades_per_day=3, max_consecutive_losses=3,
            max_open_exposure=2500,
        )
        state = RiskState(daily_pnl=-500, trades_today=2)
        result = trader_readonly_observation(
            _resident(_row()), now=NOW,
            risk_limits=limits, risk_state=state,
        )
        self.assertEqual(result["risk"]["status"], "LIMIT_REACHED_BLOCKED")
        self.assertFalse(result["mode"]["authorizes_send"])

    def test_16_even_when_risk_guardian_not_locked_still_no_orders(self):
        limits = RiskLimits(
            bankroll=10000, max_daily_loss=500, max_loss_per_trade=100,
            max_trades_per_day=3, max_consecutive_losses=3,
            max_open_exposure=2500,
        )
        result = trader_readonly_observation(
            _resident(_row()), now=NOW,
            risk_limits=limits, risk_state=RiskState(),
        )
        self.assertEqual(result["risk"]["status"],
                         "SIMULATION_BUDGET_NOT_LOCKED_STILL_NO_TRADING")
        self.assertTrue(result["no_orders"])
        self.assertFalse(result["mode"]["external_actions_enabled"])

    def test_17_business_frozen_in_view_investments_only_scaffold(self):
        result = trader_readonly_observation({}, now=NOW)
        self.assertEqual(result["mode"]["negocios"], "FROZEN_IN_THIS_READ_MODEL")
        self.assertEqual(result["mode"]["investimentos"], "SCAFFOLD_ONLY")
        self.assertEqual(result["mode"]["trader"], "READ_ONLY")
        self.assertFalse(result["mode"]["new_market_data_requests"])
        self.assertEqual(result["mode"]["p0_homologated"], 0)

    def test_18_resident_hydration_populates_view_without_new_fetch(self):
        snapshot = {"mock_only": True}
        session = {}
        source = _resident(_row())
        with mock.patch.object(
            atlasquant_trader_resident, "resident_trader_state",
            return_value=source,
        ) as producer:
            atlasquant_trader_resident.hydrate_trader_resident_state(session, snapshot)
        producer.assert_called_once_with(snapshot, runtime_status=None)
        self.assertEqual(session["atlasquant_aion_trader_observation"]["schema"], SCHEMA)
        self.assertEqual(
            session["atlasquant_aion_trader_observation"]["fresh_m15_pairs"], 0,
        )
        # Fake 2026 timestamp cannot appear CURRENT at the actual wall clock.
        self.assertEqual(len(session["atlasquant_aion_trader_observation"]["rows"]), 28)

    def test_19_failed_refresh_clears_previously_observed_market(self):
        session = {"atlasquant_aion_trader_observation": {"all_28_fresh_closed_m15": True}}
        with mock.patch.object(
            atlasquant_trader_resident, "resident_trader_state",
            side_effect=ValueError("invalid snapshot"),
        ):
            atlasquant_trader_resident.hydrate_trader_resident_state(session, {})
        self.assertNotIn("atlasquant_aion_trader_observation", session)
        self.assertEqual(session["atlasquant_validated_market_items"], [])

    def test_20_does_not_mutate_inputs_or_suggest_order_execution(self):
        row = _row()
        state = _resident(row)
        original = dict(row)
        result = trader_readonly_observation(state, now=NOW)
        self.assertEqual(row, original)
        self.assertEqual(state["atlasquant_validated_market_items"], [original])
        self.assertTrue(result["no_orders"] and result["no_alerts"])
        self.assertTrue(all(not x["authorizes_order"] for x in result["rows"]))

    def test_21_invalid_now_rejected_and_no_naive_timestamps_accepted(self):
        for time in (NOW.replace(tzinfo=None), "today", None if False else "naive"):
            with self.subTest(value=str(time)):
                with self.assertRaises(ValueError):
                    trader_readonly_observation(_resident(_row()), now=time)

    def test_22_invalid_resident_empty_snapshot_preserves_legacy_exact_keys(self):
        session = {
            "atlasquant_reference_fx_population": {"old": True},
            "atlasquant_validated_market_items": [{"old": True}],
            "atlasquant_aion_trader_observation": {"old": True},
        }
        empty = {
            "atlasquant_reference_fx_population": {},
            "atlasquant_validated_market_items": [],
        }
        with mock.patch.object(
            atlasquant_trader_resident, "resident_trader_state",
            return_value=empty,
        ):
            atlasquant_trader_resident.hydrate_trader_resident_state(session, {})
        self.assertEqual(session, empty)

    def test_23_dxy_and_non_fx_market_rows_do_not_invalidate_real_28fx(self):
        pairs = [_row(pair) for pair in FX_28]
        board = trader_readonly_observation(
            _resident(*pairs, {"asset": "DXY", "score": 10}), now=NOW,
        )
        self.assertEqual(board["fresh_m15_pairs"], 28)
        self.assertTrue(board["all_28_fresh_closed_m15"])
        self.assertEqual(board["unknown_or_invalid_rows"], 1)
        self.assertEqual(len(board["rows"]), 28)

    def test_24_no_provider_network_or_order_imports_in_read_model(self):
        source = inspect.getsource(trader_readonly_observation)
        from atlasquant_aion_trader_observation import __file__ as location
        file = Path(location).read_text(encoding="utf-8")
        for word in (
            "import requests", "import socket", "import subprocess",
            "import MetaTrader5", "import ccxt", "urllib.request",
            "adapter.send(", "ExecutionOutbox(",
        ):
            self.assertNotIn(word, file)
        self.assertNotIn("resident_trader_state(", source)


if __name__ == "__main__":
    unittest.main()
