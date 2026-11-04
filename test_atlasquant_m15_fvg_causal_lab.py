"""Offline contract and causal lifecycle regressions for experimental M15 FVG."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import unittest

from atlasquant_m15_fvg_causal_lab import SCHEMA, scan_m15_fvg
from atlasquant_fx_universe import OFFICIAL_PAIRS

UTC = timezone.utc
NOW = datetime(2026, 11, 4, 18, 0, tzinfo=UTC)


def candle(offset: int, opening: float, high: float, low: float, close: float,
           *, complete: bool = True) -> dict:
    return {
        "time": (datetime(2026, 11, 4, 12, 0, tzinfo=UTC)
                 + timedelta(minutes=15 * offset)).isoformat(),
        "open": opening, "high": high, "low": low, "close": close,
        "complete": complete,
    }


BULL = [
    candle(0, 99, 100, 98, 99.5),
    candle(1, 99.5, 103, 99, 102.5),
    candle(2, 102.5, 104, 102, 103),
]
BEAR = [
    candle(0, 101, 102, 100, 100.5),
    candle(1, 100.5, 101, 97, 97.5),
    candle(2, 97.5, 98, 96, 97),
]


def payload(input_bars: list[dict], **overrides: object) -> dict:
    result = {
        "schema": SCHEMA,
        "state": "OFFLINE_RESEARCH",
        "pair": "EUR/USD",
        "timeframe": "M15",
        "point_size": 0.0001,
        "minimum_gap_points": 0,
        "middle_body_min_fraction": 0.5,
        "bars": deepcopy(input_bars),
    }
    result.update(overrides)
    return result


class M15FVGResearchTests(unittest.TestCase):
    def scan(self, input_bars: list[dict], **overrides: object) -> dict:
        return scan_m15_fvg(payload(input_bars, **overrides), now=NOW)

    def test_bullish_zone_is_created_only_after_third_close(self) -> None:
        out = self.scan(BULL)
        self.assertEqual(out["state"], "RESEARCH_ONLY")
        self.assertEqual(out["zone_count"], 1)
        z = out["zones"][0]
        self.assertEqual(z["direction"], "BULLISH")
        self.assertEqual((z["lower"], z["upper"]), (100, 102))
        self.assertEqual(z["created_at"], "2026-11-04T12:45:00+00:00")
        self.assertEqual(z["status"], "ACTIVE")
        self.assertEqual([e["event"] for e in out["events"]], ["CREATED"])
        self.assertTrue(out["zone_created_after_third_close"])
        self.assertFalse(out["source_authenticated"])
        self.assertFalse(out["trend_verified"])
        self.assertFalse(out["setup_accuracy_verified"])
        self.assertFalse(out["profitability_verified"])
        self.assertFalse(out["publishable"])
        self.assertFalse(out["trade_authorized"])

    def test_all_28_canonical_pairs_accept_causal_import(self) -> None:
        self.assertEqual(len(OFFICIAL_PAIRS), 28)
        for pair in OFFICIAL_PAIRS:
            with self.subTest(pair=pair):
                out = self.scan(BULL, pair=pair)
                self.assertEqual(out["pair"], pair)
                self.assertEqual(out["zone_count"], 1)
                self.assertFalse(out["trade_authorized"])

    def test_bullish_touch_then_close_invalidation_cannot_revert(self) -> None:
        three = self.scan(BULL)
        four = self.scan(BULL + [candle(3, 103, 104, 101, 103.5)])
        five = self.scan(BULL + [candle(3, 103, 104, 101, 103.5),
                                  candle(4, 101, 102, 99.5, 99.8)])
        self.assertEqual(four["zones"][0]["status"], "TOUCHED")
        self.assertEqual(five["zones"][0]["status"], "INVALIDATED_CLOSE")
        self.assertEqual(
            [e["event"] for e in five["events"] if e["id"] == three["zones"][0]["id"]],
            ["CREATED", "TOUCHED", "INVALIDATED_CLOSE"],
        )
        self.assertEqual(three["zones"][0]["created_at"], five["zones"][0]["created_at"])
        self.assertEqual((three["zones"][0]["lower"], three["zones"][0]["upper"]),
                         (five["zones"][0]["lower"], five["zones"][0]["upper"]))

    def test_bullish_full_fill_without_close_invalidation(self) -> None:
        out = self.scan(BULL + [candle(3, 103, 104, 100, 102.5)])
        self.assertEqual(out["zones"][0]["status"], "FULLY_FILLED")

    def test_bearish_mirror_touch_then_close_invalidation(self) -> None:
        out = self.scan(BEAR + [candle(3, 97, 99, 96, 97),
                                candle(4, 99, 102, 98, 101)])
        z = out["zones"][0]
        self.assertEqual(z["direction"], "BEARISH")
        self.assertEqual((z["lower"], z["upper"]), (98, 100))
        self.assertEqual(z["status"], "INVALIDATED_CLOSE")
        self.assertEqual([e["event"] for e in out["events"] if e["id"] == z["id"]],
                         ["CREATED", "TOUCHED", "INVALIDATED_CLOSE"])

    def test_gap_size_and_middle_body_filters(self) -> None:
        self.assertEqual(self.scan(BULL, minimum_gap_points=20001)["zone_count"], 0)
        self.assertEqual(self.scan(BULL, middle_body_min_fraction=1)["zone_count"], 0)
        self.assertEqual(self.scan(BULL, minimum_gap_points=20000)["zone_count"], 1)

    def test_nonconsecutive_triple_never_creates_fvg(self) -> None:
        bars = deepcopy(BULL)
        bars[1]["time"] = candle(2, 1, 2, 0.5, 1)["time"]
        bars[2]["time"] = candle(3, 1, 2, 0.5, 1)["time"]
        out = self.scan(bars)
        self.assertEqual(out["zone_count"], 0)
        self.assertEqual(out["historical_session_gaps"], 1)

    def test_duplicate_time_and_invalid_ohlc_are_blocked(self) -> None:
        bad = deepcopy(BULL)
        bad[2]["time"] = bad[1]["time"]
        self.assertEqual(self.scan(bad)["reason"], "DUPLICATE_OR_MISALIGNED_TIME")
        bad = deepcopy(BULL)
        bad[1]["high"] = bad[1]["low"] - 1
        self.assertEqual(self.scan(bad)["reason"], "OPEN_OR_INVALID_OHLC")

    def test_unclosed_future_and_incomplete_bars_are_blocked(self) -> None:
        self.assertEqual(self.scan(BULL[:2] + [candle(2, 102, 104, 102, 103,
                                                     complete=False)])["reason"],
                         "OPEN_OR_INVALID_OHLC")
        self.assertEqual(scan_m15_fvg(payload(BULL), now=NOW.replace(hour=12, minute=40))[
            "reason"], "FUTURE_OR_UNCLOSED_BAR")
        with self.assertRaises(ValueError):
            scan_m15_fvg(payload(BULL), now=NOW.replace(tzinfo=None))

    def test_invalid_contract_and_sensitive_fields_block(self) -> None:
        cases = [
            (dict(timeframe="H1"), "INVALID_CONTRACT"),
            (dict(state="LIVE"), "INVALID_CONTRACT"),
            (dict(pair="EUR/XYZ"), "INVALID_PAIR"),
            (dict(api_key="do-not-use"), "SENSITIVE_FIELD_NOT_ALLOWED"),
            (dict(point_size=0), "INVALID_FVG_FILTERS"),
            (dict(middle_body_min_fraction=1.01), "INVALID_FVG_FILTERS"),
            (dict(minimum_gap_points=-1), "INVALID_FVG_FILTERS"),
            (dict(minimum_gap_points=float("nan")), "INVALID_FVG_FILTERS"),
            (dict(bars=BULL[:2]), "BAR_COUNT_INVALID"),
        ]
        for update, code in cases:
            with self.subTest(update=update):
                result = self.scan(BULL, **update)
                self.assertEqual(result["state"], "BLOCKED")
                self.assertEqual(result["reason"], code)
                self.assertFalse(result["trade_authorized"])


if __name__ == "__main__":
    unittest.main()
