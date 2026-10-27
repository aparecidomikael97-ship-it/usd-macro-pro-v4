"""USD-seven to 28 implied context: no evidence inflation or side effects."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from math import exp
import unittest

from atlasquant_instrument_registry import FX_CURRENCIES, FX_28
from atlasquant_trader_precision_lab import PairWindow
from atlasquant_trader_implied_fx28_lab import (
    USD_LEGS, IMPLIED_CROSSES, implied_28_from_7_usd,
    implied_28_from_supplied_cache,
)

T0 = datetime(2026,10,27,12,0,tzinfo=timezone.utc)
T1 = T0 + timedelta(minutes=15)
NOW = T1 + timedelta(minutes=25)
MAX_AGE = timedelta(minutes=30)


def seven_windows(relative=None):
    relative = relative or {c:0.0 for c in FX_CURRENCIES}
    result = {}
    for pair in USD_LEGS:
        raw = relative[pair[:3]] - relative[pair[3:]]
        result[pair] = PairWindow(raw, T0, T1, "test_usd_leg_feed")
    return result


def raw_candle(ts, close):
    return {"datetime": ts.isoformat(), "open": close,
            "high": close * 1.001, "low": close * 0.999, "close": close}


def seven_cache(relative=None):
    relative = relative or {c:0.0 for c in FX_CURRENCIES}
    series = {}
    for pair in USD_LEGS:
        raw = relative[pair[:3]] - relative[pair[3:]]
        key = pair[:3]+"/"+pair[3:]+"|15min"
        series[key] = {
            "fetched_at": (T1+timedelta(minutes=17)).isoformat(),
            "records": [raw_candle(T0-timedelta(minutes=15),1.0),
                        raw_candle(T0,exp(raw))],
        }
    return {"series": series}


class ImpliedFx28ResearchTests(unittest.TestCase):
    def test_01_exactly_seven_usd_observed_and_21_crosses_implied(self):
        self.assertEqual(len(USD_LEGS),7)
        self.assertEqual(len(IMPLIED_CROSSES),21)
        self.assertEqual(set(USD_LEGS)|set(IMPLIED_CROSSES),set(FX_28))

    def test_02_all_flat_returns_are_zero_summed(self):
        res=implied_28_from_7_usd(seven_windows(),now=NOW,max_age=MAX_AGE)
        self.assertTrue(res.research_only)
        self.assertEqual(len(res.pair_context),28)
        self.assertEqual(set(res.currency_scores.values()),{0.0})
        self.assertFalse(res.allows_trading)

    def test_03_latent_currency_differences_recovered(self):
        latent={c:(i-3.5)*0.001 for i,c in enumerate(sorted(FX_CURRENCIES))}
        res=implied_28_from_7_usd(seven_windows(latent),now=NOW,max_age=MAX_AGE)
        self.assertTrue(res.research_only)
        for c in FX_CURRENCIES:
            self.assertAlmostEqual(res.currency_scores[c],latent[c],places=12)
        for pair in FX_28:
            self.assertAlmostEqual(res.pair_context[pair],
                                   latent[pair[:3]]-latent[pair[3:]],places=12)

    def test_04_usd_as_base_orientation_is_inverted_for_jpy(self):
        windows=seven_windows()
        windows["USDJPY"]=PairWindow(0.02,T0,T1,"test_usd_leg_feed")
        res=implied_28_from_7_usd(windows,now=NOW,max_age=MAX_AGE)
        self.assertAlmostEqual(res.pair_context["USDJPY"],0.02)
        self.assertAlmostEqual(res.pair_context["EURJPY"],0.02)
        self.assertAlmostEqual(res.pair_context["EURUSD"],0.0)

    def test_05_each_pair_carries_precise_observed_vs_implied_provenance(self):
        res=implied_28_from_7_usd(seven_windows(),now=NOW,max_age=MAX_AGE)
        self.assertEqual(sum(v=="OBSERVED_USD_LEG" for v in res.origin_by_pair.values()),7)
        self.assertEqual(sum(v=="IMPLIED_CROSS_NOT_QUOTED" for v in res.origin_by_pair.values()),21)
        self.assertNotIn("WIN_RATE",res.status)
        self.assertFalse(res.allows_trading)

    def test_06_missing_one_leg_denies_entire_projection(self):
        windows=seven_windows()
        windows.pop("USDCHF")
        res=implied_28_from_7_usd(windows,now=NOW,max_age=MAX_AGE)
        self.assertFalse(res.research_only)
        self.assertEqual(res.missing_or_invalid,("USDCHF",))
        self.assertEqual(res.pair_context,{})

    def test_07_extra_cross_cannot_be_disguised_as_observed(self):
        windows=seven_windows()
        windows["EURGBP"]=PairWindow(0.01,T0,T1,"test_usd_leg_feed")
        self.assertFalse(implied_28_from_7_usd(windows,now=NOW,max_age=MAX_AGE).research_only)

    def test_08_nonfinite_and_boolean_returns_are_denied(self):
        for bad in (float("nan"),float("inf"),True):
            with self.subTest(bad=str(bad)):
                rows=seven_windows()
                rows["EURUSD"]=PairWindow(bad,T0,T1,"test_usd_leg_feed")
                self.assertFalse(implied_28_from_7_usd(rows,now=NOW,max_age=MAX_AGE).research_only)

    def test_09_stale_and_future_leg_windows_denied(self):
        rows=seven_windows()
        self.assertFalse(implied_28_from_7_usd(
            rows,now=T0,max_age=MAX_AGE).research_only)
        self.assertFalse(implied_28_from_7_usd(
            rows,now=T1+timedelta(hours=2),max_age=MAX_AGE).research_only)

    def test_10_mixed_time_or_feed_denied(self):
        rows=seven_windows()
        rows["EURUSD"]=PairWindow(0.0,T0+timedelta(minutes=1),T1,"test_usd_leg_feed")
        self.assertFalse(implied_28_from_7_usd(rows,now=NOW,max_age=MAX_AGE).research_only)
        rows["EURUSD"]=PairWindow(0.0,T0,T1,"other")
        self.assertFalse(implied_28_from_7_usd(rows,now=NOW,max_age=MAX_AGE).research_only)

    def test_11_cache_observation_seven_is_labeled_implied_not_observed_28(self):
        res=implied_28_from_supplied_cache(seven_cache(),now=NOW,max_age=MAX_AGE)
        self.assertTrue(res.research_only)
        self.assertEqual(len(res.implied_pairs),21)
        self.assertFalse(res.allows_trading)

    def test_12_realistic_empty_cache_must_wait(self):
        res=implied_28_from_supplied_cache({"series":{}},now=NOW,max_age=MAX_AGE)
        self.assertEqual(res.status,"WAIT_NO_CONTEXT")
        self.assertEqual(len(res.missing_or_invalid),7)

    def test_13_compact_alias_tolerated_but_double_alias_denied(self):
        state=seven_cache()
        state["series"]["EURUSD|15min"]=state["series"].pop("EUR/USD|15min")
        self.assertTrue(implied_28_from_supplied_cache(
            state,now=NOW,max_age=MAX_AGE).research_only)
        state["series"]["EUR/USD|15min"]=state["series"]["EURUSD|15min"]
        self.assertFalse(implied_28_from_supplied_cache(
            state,now=NOW,max_age=MAX_AGE).research_only)

    def test_14_corrupt_one_cache_candle_denies_projection(self):
        state=seven_cache()
        state["series"]["USD/JPY|15min"]["records"][-1]["low"]=9999.0
        res=implied_28_from_supplied_cache(state,now=NOW,max_age=MAX_AGE)
        self.assertIn("USDJPY",res.missing_or_invalid)

    def test_15_no_cache_mutations_and_no_secret_or_market_data_access(self):
        state=seven_cache()
        original=deepcopy(state)
        res=implied_28_from_supplied_cache(state,now=NOW,max_age=MAX_AGE)
        self.assertTrue(res.research_only)
        self.assertEqual(state,original)
        self.assertFalse(hasattr(res,"allows_provider_send"))


if __name__=="__main__":
    unittest.main(verbosity=2)
