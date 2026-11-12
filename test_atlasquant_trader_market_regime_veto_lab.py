"""Synthetic tests; run with real repo imports in CI, no network or trading."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import unittest

from atlasquant_fx_universe import OFFICIAL_PAIRS
from atlasquant_trader_selective_bias_gate_lab import BiasObservation
from atlasquant_trader_market_regime_veto_lab import (
    ClosedMarketBar, inspect_market_regime_veto_lab as check,
)

UTC = timezone.utc
D1_AT = datetime(2026, 11, 6, 12, tzinfo=UTC)
W1_AT = datetime(2026, 11, 3, 12, tzinfo=UTC)
NOW = datetime(2026, 11, 8, 12, tzinfo=UTC)
EVAL = datetime(2026, 11, 7, 11, tzinfo=UTC)


def candidate(asset="EUR/USD", side="ALTA"):
    return BiasObservation(asset=asset, horizon="D1", evaluated_at=EVAL,
        weekly=side, daily=side, grade_0_to_10=8.5,
        macro_captured_at=EVAL-timedelta(hours=2), snapshot_sha256="a"*64)


def candles(tf, mode="UP", n=46):
    interval = timedelta(days=7 if tf == "W1" else 1)
    last_start = (datetime(2026, 10, 26, tzinfo=UTC) if tf == "W1"
                  else datetime(2026, 11, 4, tzinfo=UTC))
    base = Decimal("1.200000")
    rows = []
    for i in range(n):
        start = last_start-(n-1-i)*interval
        before = base
        if mode == "UP" or mode == "SHOCK":
            base += Decimal("0.01")
        elif mode == "DOWN":
            base -= Decimal("0.01")
        elif mode == "RANGE":
            base += Decimal("0.01") if i % 2 else Decimal("-0.01")
        elif mode == "TRANSITION":
            base += Decimal("0.01") if i % 4 != 0 else Decimal("-0.01")
        elif mode == "FLAT":
            pass
        lo = min(before, base)-Decimal("0.002")
        hi = max(before, base)+Decimal("0.002")
        if mode == "SHOCK" and i == n-1:
            lo -= Decimal("0.20")
            hi += Decimal("0.20")
        rows.append(ClosedMarketBar(start,start+interval,start+interval+timedelta(minutes=1),
                         str(before),str(hi),str(lo),str(base),"a"*64))
    return rows


def evaluation(*, d1=None,w1=None,side="ALTA",asset="EUR/USD",**changes):
    params={"candidate":candidate(asset,side),
            "bars_by_horizon":{"D1":candles("D1") if d1 is None else d1,
                               "W1":candles("W1") if w1 is None else w1},
            "decision_at_by_horizon":{"D1":D1_AT,"W1":W1_AT},
            "as_of_utc":NOW}
    params.update(changes)
    return check(**params)


class RegimeLabTests(unittest.TestCase):
    def assert_no_live(self,r):
        self.assertEqual(r["operational_bias"],"AGUARDAR")
        for key in ("publishable","live_alert_allowed","trade_authorized","worker_enabled",
                    "scheduler_enabled","historical_broker_prices_independently_authenticated",
                    "price_archive_pit_independently_authenticated",
                    "risk_off_from_cross_asset_flows_verified",
                    "incremental_accuracy_improvement_validated"):
            self.assertFalse(r[key],key)
        self.assertIsNone(r["calibrated_direction_probability"])
        self.assertIsNone(r["validated_directional_accuracy"])
        self.assertIsNone(r["fx_bias"])
        self.assertEqual((r["http_requests"],r["new_cost_brl"]),(0,0))

    def test_aligned_trends_are_documentary_not_live_signal(self):
        r=evaluation()
        self.assertFalse(r["research_veto"])
        self.assertEqual(r["state"],"LAB_REGIME_ALIGNMENT_DOCUMENTARY_NOT_LIVE")
        self.assertEqual(r["W1"]["regime"],"TREND")
        self.assertEqual(r["D1"]["direction_documentary"],"ALTA")
        self.assert_no_live(r)

    def test_downtrend_matches_bearish_not_bullish(self):
        down=candles("D1","DOWN"); wdown=candles("W1","DOWN")
        self.assertFalse(evaluation(d1=down,w1=wdown,side="BAIXA")["research_veto"])
        r=evaluation(d1=down,w1=wdown)
        self.assertTrue(r["research_veto"])
        self.assertIn("D1_TREND_CONTRADICTS_CANDIDATE",r["blockers"])
        self.assertIn("W1_TREND_CONTRADICTS_CANDIDATE",r["blockers"])
        self.assert_no_live(r)

    def test_range_requires_abstention(self):
        r=evaluation(d1=candles("D1","RANGE"))
        self.assertTrue(r["research_veto"])
        self.assertEqual(r["D1"]["regime"],"RANGE")
        self.assert_no_live(r)

    def test_transition_requires_abstention(self):
        r=evaluation(w1=candles("W1","TRANSITION"))
        self.assertTrue(r["research_veto"])
        self.assertEqual(r["W1"]["regime"],"TRANSITION")
        self.assert_no_live(r)

    def test_shock_not_mislabeled_risk_off(self):
        r=evaluation(d1=candles("D1","SHOCK"))
        self.assertEqual(r["D1"]["regime"],"VOLATILITY_SHOCK")
        self.assertFalse(r["D1"]["risk_off_verified"])
        self.assertTrue(r["research_veto"])
        self.assert_no_live(r)

    def test_flat_prices_cannot_claim_trend(self):
        r=evaluation(d1=candles("D1","FLAT"))
        self.assertTrue(r["research_veto"])
        self.assertEqual(r["D1"]["reason"],"NO_PRICE_MOVEMENT_FOR_EFFICIENCY")
        self.assert_no_live(r)

    def test_missing_w1_fails_closed(self):
        r=evaluation(w1=[])
        self.assertTrue(r["research_veto"])
        self.assertIn("W1_MISSING_OR_INSUFFICIENT_CLOSED_BARS",r["blockers"])
        self.assert_no_live(r)

    def test_missing_entire_evidence_fails_closed(self):
        r=evaluation(bars_by_horizon=None)
        self.assertTrue(r["research_veto"])
        self.assertEqual(r["reason"],"MARKET_REGIME_BARS_MISSING_OR_WRONG_HORIZONS")
        self.assert_no_live(r)

    def test_all_28_crosses_no_live(self):
        for asset in OFFICIAL_PAIRS:
            with self.subTest(asset=asset):
                self.assert_no_live(evaluation(asset=asset))

    def test_cannot_treat_indexes_as_fx(self):
        for a in ("WIN","WDO","NAS100","US500","US30","EURUSD"):
            self.assertTrue(evaluation(asset=a)["research_veto"])

    def test_partial_unclosed_candle_is_rejected(self):
        d=candles("D1"); d[-1]=replace(d[-1],closed_at=D1_AT+timedelta(days=1))
        r=evaluation(d1=d)
        self.assertIn("D1_INVALID_OR_LOOKAHEAD_BAR_TIMESTAMPS",r["blockers"])
        self.assert_no_live(r)

    def test_snapshot_recorded_after_cutoff_is_rejected(self):
        d=candles("D1"); d[-1]=replace(d[-1],recorded_at=D1_AT+timedelta(seconds=1))
        r=evaluation(d1=d)
        self.assertIn("D1_INVALID_OR_LOOKAHEAD_BAR_TIMESTAMPS",r["blockers"])

    def test_naive_or_future_decision_is_blocked(self):
        for clock in (datetime(2026,11,6,12),NOW+timedelta(hours=1)):
            r=evaluation(decision_at_by_horizon={"D1":clock,"W1":W1_AT})
            self.assertTrue(r["research_veto"])
            self.assert_no_live(r)

    def test_wrong_w1_d1_decision_order(self):
        r=evaluation(decision_at_by_horizon={"D1":W1_AT,"W1":D1_AT})
        self.assertTrue(r["research_veto"])

    def test_duplicate_or_reversed_candles_blocked(self):
        d=candles("D1"); d[-1]=d[-2]
        r=evaluation(d1=d)
        self.assertIn("D1_UNREVIEWED_BAR_GAP_OR_ORDER",r["blockers"])

    def test_bad_ohlc_and_nan_are_rejected(self):
        for changes in ({"high":"0.1"},{"close":"NaN"},{"low":"-1"},
                        {"open":0.1},{"high":"Infinity"}):
            with self.subTest(changes=changes):
                d=candles("D1");d[-1]=replace(d[-1],**changes)
                r=evaluation(d1=d)
                self.assertIn("D1_INVALID_OHLC_OR_ASOF_CLAIMS",r["blockers"])
                self.assert_no_live(r)

    def test_hash_is_claim_only_and_invalid_hash_rejected(self):
        d=candles("D1");d[-1]=replace(d[-1],source_sha256_claim="bad")
        r=evaluation(d1=d)
        self.assertIn("D1_INVALID_OR_LOOKAHEAD_BAR_TIMESTAMPS",r["blockers"])
        self.assertFalse(evaluation()["historical_broker_prices_independently_authenticated"])

    def test_stale_last_bar(self):
        d=candles("D1")
        d=[replace(x,opened_at=x.opened_at-timedelta(days=100),
                   closed_at=x.closed_at-timedelta(days=100),
                   recorded_at=x.recorded_at-timedelta(days=100)) for x in d]
        r=evaluation(d1=d)
        self.assertIn("D1_LAST_CLOSED_BAR_TOO_OLD",r["blockers"])

    def test_gap_requires_review(self):
        d=candles("D1")
        d=d[:10]+[replace(x,opened_at=x.opened_at+timedelta(days=8),
                          closed_at=x.closed_at+timedelta(days=8),
                          recorded_at=x.recorded_at+timedelta(days=8)) for x in d[10:]]
        r=evaluation(d1=d)
        self.assertIn("D1_UNREVIEWED_BAR_GAP_OR_ORDER",r["blockers"])

    def test_corrupt_or_short_series(self):
        for s in ([],[None]*32,123,list(range(31)),list(range(181))):
            r=evaluation(d1=s)
            self.assertTrue(r["research_veto"])
            self.assert_no_live(r)

    def test_conflicting_w1_d1_side(self):
        c=replace(candidate(),weekly="BAIXA")
        self.assertTrue(evaluation(candidate=c)["research_veto"])

    def test_extreme_scale_change_fails_closed_without_decimal_exception(self):
        d=candles("D1")
        # Tiny but finite historic prices, then a wildly different current price.
        tiny=Decimal("0.000000000000000000000001")
        for i,b in enumerate(d[:-1]):
            p=tiny+Decimal(i)*Decimal("0.00000000000000000000000001")
            d[i]=replace(b,open=str(p),high=str(p+Decimal("0.00000000000000000000000002")),
                            low=str(p-Decimal("0.000000000000000000000000005")),close=str(p))
        d[-1]=replace(d[-1],open="1",high="1",low="0.5",close="0.9")
        r=evaluation(d1=d)
        self.assertTrue(r["research_veto"])
        self.assertEqual(r["D1"]["reason"],"EXTREME_PRICE_SCALE_OR_VOLATILITY_REQUIRES_REVIEW")
        self.assert_no_live(r)

    def test_importing_old_retrospective_bars_after_cutoff_is_blocked(self):
        w=candles("W1")
        w=[replace(x, recorded_at=NOW) for x in w]
        r=evaluation(w1=w)
        self.assertIn("W1_INVALID_OR_LOOKAHEAD_BAR_TIMESTAMPS",r["blockers"])
        self.assert_no_live(r)

    def test_mismatched_broker_weeks_blocked(self):
        w=candles("W1")
        w[-1]=replace(w[-1],opened_at=w[-1].opened_at+timedelta(days=1),
            closed_at=w[-1].closed_at+timedelta(days=1),
            recorded_at=w[-1].recorded_at+timedelta(days=1))
        r=evaluation(w1=w)
        self.assertIn("W1_UNREVIEWED_BAR_GAP_OR_ORDER",r["blockers"])

if __name__ == '__main__':
    unittest.main()
