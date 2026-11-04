"""Causal FVG -> hypothetical R replay: synthetic data, no external access."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import unittest

from atlasquant_m15_fvg_r_link_lab import SCHEMA, link_fvg_to_r

UTC = timezone.utc
NOW = datetime(2026, 11, 4, 16, tzinfo=UTC)
START = datetime(2026, 11, 4, 12, tzinfo=UTC)


def candle(i: int, opening: float, high: float, low: float, close: float) -> dict:
    return {"time": (START + timedelta(minutes=i * 15)).isoformat(),
            "open": opening, "high": high, "low": low, "close": close,
            "complete": True}


BULL = [
    candle(0, 99, 100, 98, 99.5),
    candle(1, 99.5, 103, 99, 102.5),
    candle(2, 102.5, 104, 102, 103),
    candle(3, 103, 105, 102.5, 104.5),
    candle(4, 104.5, 106, 104, 105.8),
]
BEAR = [
    candle(0, 101, 102, 100, 100.5),
    candle(1, 100.5, 101, 97, 97.5),
    candle(2, 97.5, 98, 96, 97),
    candle(3, 97, 97, 94.5, 95),
]


def request(bars: list[dict] | None = None, **changes: object) -> dict:
    data = {
        "schema": SCHEMA, "state": "OFFLINE_RESEARCH",
        "timeframe": "M15", "pair": "EUR/USD", "signal_bar_index": 2,
        "fvg_filters": {"point_size": 0.01, "minimum_gap_points": 0,
                        "middle_body_min_fraction": 0.5},
        "risk_plan": {"stop_mid": 101, "target_mid": 105.5,
                      "spread_points_assumed": 2, "slippage_points_assumed": 1},
        "bars": deepcopy(BULL if bars is None else bars),
    }
    data.update(changes)
    return data


class FVGToRLinkTests(unittest.TestCase):
    def scan(self, data: dict) -> dict:
        return link_fvg_to_r(data, now=NOW)

    def test_bullish_formation_prefix_and_next_open_entry(self) -> None:
        data = request()
        original = deepcopy(data)
        out = self.scan(data)
        self.assertEqual(data, original)
        self.assertEqual(out["state"], "RESEARCH_ONLY")
        self.assertTrue(out["fvg_formation_geometry_verified"])
        self.assertEqual(out["fvg"]["created_at"], "2026-11-04T12:45:00+00:00")
        self.assertEqual((out["fvg"]["lower"], out["fvg"]["upper"]), (100, 102))
        self.assertEqual(out["fvg"]["status"], "ACTIVE")
        self.assertEqual(out["scenario"]["entry_bar_start"], "2026-11-04T12:45:00+00:00")
        self.assertEqual(out["scenario"]["side"], "BUY")
        self.assertEqual(out["scenario"]["outcome"], "TARGET")
        self.assertFalse(out["source_authenticated"])
        self.assertFalse(out["signal_causal_verified"])
        self.assertFalse(out["trend_verified"])
        self.assertFalse(out["spread_slippage_verified"])
        self.assertFalse(out["setup_accuracy_verified"])
        self.assertFalse(out["profitability_verified"])
        self.assertFalse(out["publishable"])
        self.assertFalse(out["trade_authorized"])

    def test_future_bar_does_not_change_formation_provenance(self) -> None:
        full = self.scan(request())
        shortened = self.scan(request(BULL[:4]))
        self.assertEqual(full["fvg"], shortened["fvg"])
        self.assertEqual(shortened["scenario"]["outcome"], "UNRESOLVED_NO_EXIT")
        self.assertEqual(full["scenario"]["outcome"], "TARGET")

    def test_bearish_side_is_derived_from_formed_zone(self) -> None:
        sample = request(BEAR)
        sample["risk_plan"].update({"stop_mid": 101, "target_mid": 95})
        out = self.scan(sample)
        self.assertEqual(out["state"], "RESEARCH_ONLY")
        self.assertEqual(out["fvg"]["direction"], "BEARISH")
        self.assertEqual(out["scenario"]["side"], "SELL")
        self.assertEqual(out["scenario"]["outcome"], "TARGET")

    def test_no_fvg_at_selected_index_is_blocked(self) -> None:
        sample = request()
        sample["bars"][2] = candle(2, 100, 104, 99, 103)
        self.assertEqual(self.scan(sample)["reason"], "NO_FVG_FORMED_AT_SIGNAL_CLOSE")

    def test_wrong_or_future_formation_index_is_blocked(self) -> None:
        for i in (-1, 1, 4, True, "2"):
            with self.subTest(i=i):
                self.assertEqual(self.scan(request(signal_bar_index=i))["reason"],
                                 "INVALID_FORMATION_INDEX")

    def test_replay_uses_stop_first_if_bar_hits_both(self) -> None:
        sample = request(BULL[:4])
        sample["bars"][3] = candle(3, 103, 107, 100, 104)
        out = self.scan(sample)
        self.assertEqual(out["scenario"]["outcome"], "AMBIGUOUS_STOP_FIRST")
        self.assertEqual(out["scenario"]["net_r"], -1)

    def test_missing_costs_and_bad_risk_are_blocked(self) -> None:
        for risk, code in [
            ({"stop_mid": 101, "target_mid": 105.5,
              "spread_points_assumed": 2}, "MISSING_EXPLICIT_FILTERS_OR_RISK"),
            ({"stop_mid": 106, "target_mid": 105.5,
              "spread_points_assumed": 2, "slippage_points_assumed": 1},
             "REPLAY_INVALID_RISK_GEOMETRY"),
        ]:
            with self.subTest(risk=risk):
                out = self.scan(request(risk_plan=risk))
                self.assertEqual(out["state"], "BLOCKED")
                self.assertEqual(out["reason"], code)

    def test_incomplete_misordered_and_future_bars_block(self) -> None:
        partial = request()
        partial["bars"][4]["complete"] = False
        self.assertEqual(self.scan(partial)["reason"], "OPEN_BAR_NOT_ALLOWED")
        duplicate = request()
        duplicate["bars"][3]["time"] = duplicate["bars"][2]["time"]
        self.assertEqual(self.scan(duplicate)["reason"], "REPLAY_M15_GAP_OR_ORDER")
        future = request()
        future["bars"][4]["time"] = "2026-11-04T16:00:00+00:00"
        self.assertEqual(self.scan(future)["reason"], "REPLAY_FUTURE_OR_OPEN_BAR")

    def test_secrets_wrong_pair_and_contract_fail_closed(self) -> None:
        cases = [
            (dict(api_key="do-not-use"), "SENSITIVE_FIELD_NOT_ALLOWED"),
            (dict(pair="USD/EUR"), "INVALID_PAIR"),
            (dict(state="LIVE"), "INVALID_CONTRACT"),
            (dict(side="SELL"), "UNEXPECTED_OR_MISSING_FIELD"),
            (dict(source_authenticated=True), "UNEXPECTED_OR_MISSING_FIELD"),
        ]
        for updates, expected in cases:
            with self.subTest(updates=updates):
                out = self.scan(request(**updates))
                self.assertEqual(out["reason"], expected)
                self.assertFalse(out["trade_authorized"])

    def test_missing_last_candle_and_naive_clock_are_blocked(self) -> None:
        self.assertEqual(self.scan(request(BULL[:3]))["reason"], "INVALID_BAR_COUNT")
        with self.assertRaises(ValueError):
            link_fvg_to_r(request(), now=NOW.replace(tzinfo=None))


if __name__ == "__main__":
    unittest.main()
