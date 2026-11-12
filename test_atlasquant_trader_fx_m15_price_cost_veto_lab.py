"""Synthetic, isolated M15 quote-cost/late-price veto tests; no market observations."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import unittest

from atlasquant_trader_fx_m15_price_cost_veto_lab import (
    ClosedM15Bar, IndicativeBidAskQuote,
    inspect_fx_m15_price_cost_veto_lab as inspect,
)

T = datetime(2026, 11, 11, 13, 30, tzinfo=timezone.utc)
HEX = "a" * 64
QHASH = "b" * 64


def fixture(*, symbol="EUR/USD", side="ALTA"):
    bars = []
    for i in range(21):
        start = T - timedelta(minutes=15 * (21 - i))
        bars.append(ClosedM15Bar(
            opened_at_utc=start, closed_at_utc=start+timedelta(minutes=15),
            received_at_utc=start+timedelta(minutes=15, seconds=1),
            open="1.1000", high="1.1004", low="1.0996", close="1.1000",
            tick_volume=50, batch_sha256_claim=HEX,
        ))
    quote = IndicativeBidAskQuote(
        symbol, T, T+timedelta(seconds=1), "1.10000", "1.10008", QHASH)
    return bars, quote


class PriceCostTests(unittest.TestCase):
    def run_case(self, bars=None, quote=None, asset="EUR/USD", side="ALTA",
                 decision=T+timedelta(seconds=2), now=T+timedelta(minutes=1)):
        b, q = fixture(symbol=asset, side=side)
        return inspect(asset=asset, research_side=side,
                       closed_bars=b if bars is None else bars,
                       quote=q if quote is None else quote,
                       decision_at_utc=decision, as_of_utc=now)

    def safe(self, r):
        self.assertEqual(r["operational_bias"], "AGUARDAR")
        self.assertIsNone(r["fx_bias"])
        self.assertFalse(r["trade_authorized"])
        self.assertFalse(r["publishable"])
        self.assertFalse(r["live_alert_allowed"])
        self.assertFalse(r["worker_enabled"])
        self.assertFalse(r["scheduler_enabled"])
        self.assertFalse(r["bid_ask_quote_is_executable"])
        self.assertFalse(r["full_liquidity_and_depth_verified"])
        self.assertFalse(r["m15_quote_and_bars_source_independently_attested"])
        self.assertIsNone(r["directional_accuracy_validated"])
        self.assertIsNone(r["calibrated_direction_probability"])
        self.assertFalse(r["cost_thresholds_empirically_calibrated"])
        self.assertEqual(r["new_cost_brl"], 0)

    def test_valid_data_context_never_authorizes(self):
        r = self.run_case()
        self.assertEqual(r["state"], "LAB_PRICE_COST_CONTEXT_NOT_VETOED_UNATTESTED")
        self.assertEqual(r["closed_m15_bars_checked"], 21)
        self.assertFalse(r["research_veto"])
        self.safe(r)

    def test_quote_spread_bps_too_wide(self):
        b, q = fixture()
        q = replace(q, ask="1.1020")
        r = self.run_case(bars=b, quote=q)
        self.assertEqual(r["reason"], "SPREAD_BPS_RESEARCH_LIMIT_EXCEEDED")
        self.assertTrue(r["research_veto"])
        self.safe(r)

    def test_spread_large_relative_to_range_even_if_small_bps(self):
        b, q = fixture()
        q = replace(q, ask="1.10020")
        r = self.run_case(bars=b, quote=q)
        self.assertEqual(r["reason"], "SPREAD_RELATIVE_TO_RECENT_RANGE_TOO_HIGH")
        self.safe(r)

    def test_price_already_moved_in_researched_direction(self):
        b, q = fixture()
        q = replace(q, bid="1.10250", ask="1.10258")
        r = self.run_case(bars=b, quote=q)
        self.assertEqual(r["state"], "LAB_PRICE_ALREADY_EXTENDED_VETO")
        self.safe(r)

    def test_price_already_moved_for_sell_side(self):
        b, q = fixture(side="BAIXA")
        q = replace(q, bid="1.09745", ask="1.09753")
        r = self.run_case(bars=b, quote=q, side="BAIXA")
        self.assertEqual(r["state"], "LAB_PRICE_ALREADY_EXTENDED_VETO")
        self.safe(r)

    def test_opposite_price_move_is_not_mislabeled_as_favorable(self):
        b, q = fixture()
        q = replace(q, bid="1.09745", ask="1.09753")
        r = self.run_case(bars=b, quote=q)
        self.assertLess(float(r["favorable_1h_move_atr_documentary"]), 0)
        self.assertFalse(r["research_veto"])
        self.safe(r)

    def test_last_closed_bar_volatility_shock(self):
        b, q = fixture()
        b[-1] = replace(b[-1], high="1.1030", low="1.0970")
        r = self.run_case(bars=b, quote=q)
        self.assertEqual(r["state"], "LAB_VOLATILITY_SHOCK_VETO")
        self.safe(r)

    def test_stale_quote_blocks(self):
        b, q = fixture()
        q = replace(q, observed_at_utc=T-timedelta(seconds=100),
                    received_at_utc=T-timedelta(seconds=99))
        r = self.run_case(bars=b, quote=q)
        self.assertEqual(r["reason"], "STALE_UNAVAILABLE_OR_UNTRACKED_BID_ASK_QUOTE")
        self.safe(r)

    def test_quote_too_slow_to_arrive_blocks(self):
        b, q = fixture()
        q = replace(q, observed_at_utc=T-timedelta(seconds=30),
                    received_at_utc=T)
        r = self.run_case(bars=b, quote=q)
        self.assertEqual(r["reason"], "STALE_UNAVAILABLE_OR_UNTRACKED_BID_ASK_QUOTE")
        self.safe(r)

    def test_quote_claim_after_decision_blocks(self):
        b, q = fixture()
        r = self.run_case(bars=b, quote=q, decision=T)
        self.assertEqual(r["reason"], "STALE_UNAVAILABLE_OR_UNTRACKED_BID_ASK_QUOTE")
        self.safe(r)

    def test_quote_without_bid_or_ask_does_not_use_bar_spread(self):
        b, q = fixture()
        for bid, ask in (("0", "1.10008"), ("1.10009", "1.10008"),
                         ("1.10008", "1.10008"), ("NaN", "1.10008")):
            with self.subTest(bid=bid,ask=ask):
                r = self.run_case(bars=b, quote=replace(q, bid=bid, ask=ask))
                self.assertEqual(r["reason"], "INVALID_CROSSED_OR_ZERO_SPREAD_BID_ASK")
                self.safe(r)

    def test_missing_m15_bar_blocks(self):
        b, q = fixture()
        r = self.run_case(bars=b[:-1], quote=q)
        self.assertEqual(r["reason"], "INVALID_ASSET_OR_DECISION")
        self.safe(r)

    def test_m15_discontinuity_blocks(self):
        b, q = fixture()
        b[7] = replace(b[7], opened_at_utc=b[7].opened_at_utc+timedelta(minutes=15),
                       closed_at_utc=b[7].closed_at_utc+timedelta(minutes=15),
                       received_at_utc=b[7].received_at_utc+timedelta(minutes=15))
        r = self.run_case(bars=b, quote=q)
        self.assertEqual(r["reason"], "M15_MISSING_DUPLICATED_OR_NONCONTIGUOUS_BAR")
        self.safe(r)

    def test_future_bar_capture_blocks(self):
        b, q = fixture()
        b[-1] = replace(b[-1], received_at_utc=T+timedelta(minutes=1))
        r = self.run_case(bars=b, quote=q)
        self.assertEqual(r["reason"], "M15_CLOCK_VOLUME_OR_PROVENANCE_CLAIM_INVALID")
        self.safe(r)

    def test_source_hash_changed_mid_archive_blocks(self):
        b, q = fixture()
        b[4] = replace(b[4], batch_sha256_claim="c"*64)
        r = self.run_case(bars=b, quote=q)
        self.assertEqual(r["reason"], "M15_BATCH_SOURCE_CLAIMS_INCONSISTENT")
        self.safe(r)

    def test_bad_ohlc_blocks(self):
        b, q = fixture()
        b[5] = replace(b[5], low="1.2000")
        r = self.run_case(bars=b, quote=q)
        self.assertEqual(r["reason"], "M15_OHLC_CLAIMS_INVALID")
        self.safe(r)

    def test_fake_zero_volume_blocks(self):
        b, q = fixture()
        b[5] = replace(b[5], tick_volume=0)
        r = self.run_case(bars=b, quote=q)
        self.assertEqual(r["reason"], "M15_CLOCK_VOLUME_OR_PROVENANCE_CLAIM_INVALID")
        self.safe(r)

    def test_currency_orientation_and_quote_asset_checked(self):
        b, q = fixture()
        for asset in ("USD/EUR", "XAU/USD", "EURUSD", "WIN", "NOT/A/PAIR"):
            with self.subTest(asset=asset):
                r = self.run_case(bars=b, quote=q, asset=asset)
                self.assertEqual(r["reason"], "INVALID_ASSET_OR_DECISION")
                self.safe(r)

    def test_future_evaluation_or_naive_clock_blocks(self):
        for kw in ({"now": T-timedelta(seconds=1)},
                   {"decision":T.replace(tzinfo=None)+timedelta(seconds=2)}):
            with self.subTest(kw=kw):
                r = self.run_case(**kw)
                self.assertEqual(r["reason"], "INVALID_ASSET_OR_DECISION")
                self.safe(r)

    def test_no_real_executable_quote_claim_even_on_pass(self):
        for asset in ("EUR/USD", "USD/JPY", "GBP/CHF"):
            b, q = fixture(symbol=asset)
            r = self.run_case(bars=b, quote=q, asset=asset)
            self.assertEqual(r["state"], "LAB_PRICE_COST_CONTEXT_NOT_VETOED_UNATTESTED")
            self.safe(r)


if __name__ == "__main__":
    unittest.main()