import unittest
from datetime import datetime, timedelta, timezone

from atlasquant_fx_universe import (
    CURRENCIES, OFFICIAL_PAIRS, evaluate_pair, pair_differential, invert_pair, rank_pairs, universe_integrity
)
from atlasquant_safety_core import SafetyInput, evaluate_safety
from atlasquant_data_confidence import Observation, reconcile_numeric
from atlasquant_consensus import Evidence, aggregate_consensus
from atlasquant_journal import make_decision_record, attach_trade_result, summarize_trades, make_blocked_record, to_csv
from atlasquant_release_guard import ReleaseEvidence, assess_release, should_rollback


class FxUniverseTests(unittest.TestCase):
    def setUp(self):
        self.s = {"USD":80,"EUR":60,"GBP":75,"JPY":35,"CHF":50,"CAD":45,"AUD":55,"NZD":40}

    def test_universe_is_8_by_28_unique(self):
        self.assertEqual(len(CURRENCIES), 8)
        self.assertEqual(len(OFFICIAL_PAIRS), 28)
        self.assertTrue(universe_integrity()["valid"])

    def test_inversion_symmetry(self):
        d = pair_differential("GBP/CAD", self.s)
        inv = pair_differential(invert_pair("GBP/CAD"), self.s)
        self.assertAlmostEqual(d, -inv)

    def test_cross_not_usd_only(self):
        row = evaluate_pair("EUR/NZD", self.s)
        self.assertEqual(row.side, "BUY")
        self.assertEqual(row.differential, 20)

    def test_ranking_has_all_pairs(self):
        self.assertEqual(len(rank_pairs(self.s)), 28)


class SafetyTests(unittest.TestCase):
    def test_fail_closed_missing_freshness(self):
        out = evaluate_safety(SafetyInput(95, None, True))
        self.assertTrue(out["blocked"])
        self.assertEqual(out["traffic_light"], "RED")

    def test_major_event_blocks(self):
        out = evaluate_safety(SafetyInput(95, True, True, major_event_minutes=8))
        self.assertTrue(out["blocked"])

    def test_technical_not_ready_is_wait_not_buy_signal(self):
        out = evaluate_safety(SafetyInput(95, True, True, technical_ready=False))
        self.assertFalse(out["blocked"])
        self.assertEqual(out["state"], "WAIT_CONFIRMATION")


class DataConfidenceTests(unittest.TestCase):
    def test_sources_confirm(self):
        now = datetime.now(timezone.utc)
        obs = [Observation("A", 4.20, now), Observation("B", 4.205, now - timedelta(minutes=2))]
        out = reconcile_numeric(obs, now=now, absolute_tolerance=.01)
        self.assertTrue(out["confirmed"])
        self.assertIsNotNone(out["golden_value"])

    def test_sources_disagree_fail_closed(self):
        now = datetime.now(timezone.utc)
        obs = [Observation("A", 4.2, now), Observation("B", 5.2, now)]
        out = reconcile_numeric(obs, now=now, absolute_tolerance=.01)
        self.assertFalse(out["confirmed"])
        self.assertIsNone(out["golden_value"])


class ConsensusTests(unittest.TestCase):
    def test_group_dedup_reduces_double_counting(self):
        ev = [Evidence("rates",1,10), Evidence("rates",1,10), Evidence("macro",-1,1), Evidence("news",-1,1)]
        out = aggregate_consensus(ev, min_active_groups=3, decision_threshold=.25)
        self.assertEqual(out["active_groups"], 3)
        self.assertEqual(out["side"], "SELL")

    def test_insufficient_independent_groups_neutral(self):
        out = aggregate_consensus([Evidence("macro",1), Evidence("rates",1)], min_active_groups=3)
        self.assertEqual(out["side"], "NEUTRAL")
        self.assertFalse(out["sufficient_independence"])


class JournalTests(unittest.TestCase):
    def test_metrics_and_blocked_registry(self):
        d = make_decision_record(asset="GBP/CAD", side="BUY", directional_score=82, data_quality=96, engine_version="AQ-0.1")
        rows = [
            attach_trade_result(d, outcome="GAIN", r_multiple=2),
            attach_trade_result(d, outcome="LOSS", r_multiple=-1),
            attach_trade_result(d, outcome="GAIN", r_multiple=1.5, spread_cost_r=.1),
        ]
        m = summarize_trades(rows)
        self.assertEqual(m["trades"], 3)
        self.assertEqual(m["wins"], 2)
        self.assertEqual(m["losses"], 1)
        self.assertGreater(m["profit_factor"], 1)
        b = make_blocked_record(asset="EUR/USD", reasons=["CPI em 5 min"], engine_version="AQ-0.1")
        self.assertEqual(b["side"], "NO_TRADE")
        self.assertIn("decision_id", to_csv(rows))


class ReleaseGuardTests(unittest.TestCase):
    def test_core_update_requires_shadow(self):
        ev = ReleaseEvidence(300, 0, 0, True, True, shadow_samples=20)
        out = assess_release(ev, core_model_change=True, min_shadow_samples_for_core=100)
        self.assertTrue(out["staging_ok"])
        self.assertFalse(out["eligible_for_manual_promotion"])
        self.assertFalse(out["automatic_core_promotion"])

    def test_critical_failure_rolls_back(self):
        out = should_rollback(app_boot_ok=True, health_check_ok=True, data_integrity_breach=True)
        self.assertTrue(out["rollback"])


if __name__ == "__main__":
    unittest.main()
