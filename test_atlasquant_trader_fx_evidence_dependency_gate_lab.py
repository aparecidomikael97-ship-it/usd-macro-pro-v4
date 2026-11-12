"""Synthetic regression tests. No live data or independent event provenance."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import unittest

from atlasquant_trader_fx_evidence_dependency_gate_lab import (
    FactorClaim, inspect_fx_evidence_dependency_lab as audit,
)

CUT = datetime(2026, 11, 11, 12, tzinfo=timezone.utc)

def f(fid, root, family="MACRO", side="QUOTE_RELATIVE", captured=CUT-timedelta(minutes=10)):
    return FactorClaim(fid, root, family, side, captured, "a"*64)

def run(factors, **kw):
    return audit(asset=kw.pop("asset", "EUR/USD"),
                 horizon=kw.pop("horizon", "D1"), factors=factors,
                 decision_at_utc=kw.pop("decision", CUT),
                 as_of_utc=kw.pop("now", CUT+timedelta(minutes=2)), **kw)

class DependencyTests(unittest.TestCase):
    def safe(self, result):
        self.assertEqual(result["operational_bias"], "AGUARDAR")
        self.assertIsNone(result["directional_fx_bias"])
        self.assertIsNone(result["calibrated_probability"])
        self.assertIsNone(result["validated_incremental_accuracy"])
        self.assertFalse(result["publishable"])
        self.assertFalse(result["trade_authorized"])
        self.assertFalse(result["live_alert_allowed"])
        self.assertFalse(result["worker_enabled"])
        self.assertFalse(result["scheduler_enabled"])
        self.assertFalse(result["statistical_independence_proven"])
        self.assertFalse(result["root_catalysts_independently_authenticated"])
        self.assertFalse(result["source_and_event_lineage_independently_verified"])
        self.assertFalse(result["minimum_root_threshold_empirically_calibrated"])
        self.assertEqual(result["new_cost_brl"], 0)

    def test_cpi_yields_dxy_three_indicators_one_root_not_three_confirmations(self):
        items=[f("CPI_VALUE", "US_CPI_OCT2026"),
               f("YIELD_MOVE", "US_CPI_OCT2026", "MARKET"),
               f("DXY_MOVE", "US_CPI_OCT2026", "MARKET")]
        x=run(items)
        self.assertEqual(x["factor_count"], 3)
        self.assertEqual(x["claimed_root_catalyst_count"], 1)
        self.assertEqual(x["claimed_distinct_family_count"], 2)
        self.assertEqual(x["state"], "LAB_INSUFFICIENT_DISTINCT_CATALYSTS_ABSTAIN")
        self.assertEqual(x["claimed_root_catalyst_groups"][0]["factor_count"], 3)
        self.safe(x)

    def test_three_roots_two_families_documentary_not_signal(self):
        x=run([f("US_CPI", "US_CPI_OCT2026"),
               f("EU_PMI", "EU_PMI_NOV2026"),
               f("PRICE_REGIME", "MARKET_TREND_NOV2026", "MARKET")])
        self.assertEqual(x["state"], "LAB_DOCUMENTARY_ROOT_DIVERSITY_CANDIDATE_NO_GO")
        self.assertEqual((x["factor_count"],x["claimed_root_catalyst_count"]),(3,3))
        self.safe(x)

    def test_three_roots_same_family_not_enough(self):
        x=run([f("CPI_MAIN", "US_CPI_OCT2026"),
               f("PPI_MAIN", "US_PPI_OCT2026"),
               f("NFP_MAIN", "US_NFP_OCT2026")])
        self.assertEqual(x["state"], "LAB_INSUFFICIENT_DISTINCT_CATALYSTS_ABSTAIN")
        self.safe(x)

    def test_direction_conflict_overrides_root_count(self):
        x=run([f("CPI_MAIN", "US_CPI_OCT2026"),
               f("POLICY_US", "FED_POLICY_NOV2026", "POLICY", "BASE_RELATIVE"),
               f("EU_PMI", "EU_PMI_NOV2026")])
        self.assertEqual(x["state"], "LAB_CONFLICTING_EVIDENCE_ABSTAIN")
        self.safe(x)

    def test_conflict_within_same_root_also_abstains(self):
        x=run([f("CPI_MAIN", "US_CPI_OCT2026"),
               f("CPI_MARKET", "US_CPI_OCT2026", "MARKET", "BASE_RELATIVE")])
        self.assertEqual(x["claimed_root_catalyst_count"],1)
        self.assertEqual(x["state"], "LAB_CONFLICTING_EVIDENCE_ABSTAIN")
        self.safe(x)

    def test_all_neutral_abstains(self):
        x=run([f("US_CPI", "US_CPI_OCT2026", side="NEUTRAL")])
        self.assertEqual(x["state"], "LAB_ONLY_NEUTRAL_FACTORS_ABSTAIN")
        self.safe(x)

    def test_single_factor_abstains(self):
        x=run([f("ONE_FACTOR", "US_CPI_OCT2026")])
        self.assertEqual(x["state"],"LAB_INSUFFICIENT_DISTINCT_CATALYSTS_ABSTAIN")
        self.safe(x)

    def test_duplicate_factor_id_blocks(self):
        x=run([f("US_CPI", "US_CPI_OCT2026"),f("US_CPI", "US_POLICY_NOV2026")])
        self.assertEqual(x["reason"],"INVALID_OR_DUPLICATED_FACTOR_OR_UNATTRIBUTED_ROOT")
        self.safe(x)

    def test_missing_root_unknown_blocks(self):
        x=run([f("US_CPI", "UNKNOWN")])
        self.assertEqual(x["reason"],"INVALID_OR_DUPLICATED_FACTOR_OR_UNATTRIBUTED_ROOT")
        self.safe(x)

    def test_future_capture_blocks(self):
        x=run([f("US_CPI", "US_CPI_OCT2026", captured=CUT+timedelta(seconds=1))])
        self.assertEqual(x["reason"],"SOURCE_CAPTURE_AFTER_DECISION_LOOKAHEAD")
        self.safe(x)

    def test_datetime_naive_blocks(self):
        x=run([f("US_CPI", "US_CPI_OCT2026")],decision=CUT.replace(tzinfo=None))
        self.assertEqual(x["reason"],"INVALID_ASSET_HORIZON_FACTORS_OR_CLOCK")
        self.safe(x)

    def test_asof_earlier_than_decision_blocks(self):
        x=run([f("US_CPI", "US_CPI_OCT2026")],now=CUT-timedelta(minutes=1))
        self.assertEqual(x["reason"],"INVALID_ASSET_HORIZON_FACTORS_OR_CLOCK")
        self.safe(x)

    def test_invalid_asset_blocks(self):
        x=run([f("US_CPI", "US_CPI_OCT2026")],asset="XAU/USD")
        self.assertEqual(x["reason"],"INVALID_ASSET_HORIZON_FACTORS_OR_CLOCK")
        self.safe(x)

    def test_invalid_horizon_blocks(self):
        x=run([f("US_CPI", "US_CPI_OCT2026")],horizon="M1")
        self.assertEqual(x["reason"],"INVALID_ASSET_HORIZON_FACTORS_OR_CLOCK")
        self.safe(x)

    def test_invalid_source_hash_blocks(self):
        x=run([replace(f("US_CPI", "US_CPI_OCT2026"),source_sha256_claim="x")])
        self.assertEqual(x["reason"],"INVALID_OR_DUPLICATED_FACTOR_OR_UNATTRIBUTED_ROOT")
        self.safe(x)

    def test_neutral_does_not_add_direction(self):
        x=run([f("CPI_MAIN", "US_CPI_OCT2026"),
               f("POLICY_MAIN", "FED_POLICY_NOV2026", "POLICY"),
               f("MARKET_MAIN", "MARKET_NOV2026", "MARKET", "NEUTRAL")])
        self.assertEqual(x["state"],"LAB_DOCUMENTARY_ROOT_DIVERSITY_CANDIDATE_NO_GO")
        self.safe(x)

    def test_64_factors_bounds(self):
        items=[f(f"FACT_{i:04d}","US_CPI_OCT2026") for i in range(65)]
        x=run(items)
        self.assertEqual(x["reason"],"INVALID_ASSET_HORIZON_FACTORS_OR_CLOCK")
        self.safe(x)

    def test_broken_family_blocks(self):
        x=run([f("US_CPI", "US_CPI_OCT2026", "FAKE")])
        self.assertEqual(x["reason"],"INVALID_OR_DUPLICATED_FACTOR_OR_UNATTRIBUTED_ROOT")
        self.safe(x)

    def test_float_bool_surprises_do_not_enter_a_probability(self):
        items=[f("CPI_MAIN", "US_CPI_OCT2026"),
               f("YIELD_MAIN", "US_CPI_OCT2026", "MARKET")]
        x=run(items)
        self.assertEqual(x["claimed_root_catalyst_count"],1)
        self.assertIsNone(x["calibrated_probability"])
        self.safe(x)

    def test_one_shared_root_across_seven_pairs_does_not_become_seven_events(self):
        factors=[f("CPI_MAIN", "US_CPI_OCT2026")]
        assets=["EUR/USD","GBP/USD","AUD/USD","NZD/USD","USD/JPY","USD/CHF","USD/CAD"]
        for asset in assets:
            with self.subTest(asset=asset):
                x=run(factors,asset=asset)
                self.assertEqual(x["claimed_root_catalyst_count"],1)
                self.assertEqual(x["state"],"LAB_INSUFFICIENT_DISTINCT_CATALYSTS_ABSTAIN")
                self.safe(x)

if __name__ == "__main__":
    unittest.main()