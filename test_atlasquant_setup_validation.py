import unittest
import pandas as pd

from atlasquant_setup_validation import (
    ReviewThresholds,
    evaluate_setup_for_review,
    build_setup_evidence_map,
    setup_catalog,
)


def evidence(**overrides):
    base={
        "backtest_samples":140,
        "forward_samples":45,
        "expectancy_r":0.18,
        "forward_expectancy_r":0.12,
        "profit_factor":1.35,
        "max_drawdown_r":7.0,
        "positive_fold_pct":75,
        "oos_positive_pct":67,
        "friction_positive_pct":75,
        "parameter_positive_pct":70,
        "regimes":["trend","range"],
        "sessions":["London","New York"],
        "rules_frozen_before_evaluation":True,
        "source_methodology_verified":True,
    }
    base.update(overrides)
    return base


class AtlasQuantSetupValidationTests(unittest.TestCase):
    def test_catalog_contains_existing_and_research_candidates(self):
        ids={x["id"] for x in setup_catalog()}
        self.assertTrue({"bos-choch-ob","fvg","ote","crt","amd-po3"}.issubset(ids))
        self.assertTrue({"breaker-mitigation","session-liquidity-mss","opening-range","volume-profile"}.issubset(ids))

    def test_clear_candidate_can_be_ready_only_for_human_review(self):
        result=evaluate_setup_for_review("session-liquidity-mss",evidence())
        self.assertTrue(result["review_ready"])
        self.assertTrue(result["beginner_review_ready"])
        self.assertTrue(result["manual_review_required"])
        self.assertFalse(result["automatic_beginner_promotion"])
        self.assertFalse(result["automatic_gate_change"])
        self.assertFalse(result["automatic_weight_change"])
        self.assertFalse(result["real_orders_enabled"])

    def test_win_rate_alone_can_never_qualify(self):
        result=evaluate_setup_for_review("fvg",{"win_rate_pct":99})
        self.assertFalse(result["review_ready"])
        self.assertFalse(result["beginner_review_ready"])
        self.assertFalse(result["win_rate_alone_can_qualify"])
        self.assertTrue(result["pending"])

    def test_forward_sample_is_required(self):
        result=evaluate_setup_for_review("ote",evidence(forward_samples=4))
        self.assertFalse(result["review_ready"])
        self.assertTrue(any("Forward/Paper" in x for x in result["pending"]))

    def test_negative_forward_expectancy_blocks_review(self):
        result=evaluate_setup_for_review("fvg",evidence(forward_expectancy_r=-0.01))
        self.assertFalse(result["review_ready"])
        self.assertTrue(any("Forward/Paper" in x for x in result["blockers"]))

    def test_backtest_forward_gap_blocks_overfit_like_divergence(self):
        result=evaluate_setup_for_review(
            "fvg",evidence(expectancy_r=0.50,forward_expectancy_r=0.10)
        )
        self.assertFalse(result["review_ready"])
        self.assertTrue(any("Backtest × Forward/Paper" in x for x in result["blockers"]))

    def test_drawdown_and_robustness_are_required(self):
        result=evaluate_setup_for_review(
            "fvg",
            evidence(max_drawdown_r=30,positive_fold_pct=30,friction_positive_pct=20),
        )
        self.assertFalse(result["review_ready"])
        text=" ".join(result["blockers"])
        self.assertIn("Drawdown",text)
        self.assertIn("Estabilidade temporal",text)
        self.assertIn("custos/fricção",text)

    def test_rules_must_be_frozen_before_evaluation(self):
        result=evaluate_setup_for_review("fvg",evidence(rules_frozen_before_evaluation=False))
        self.assertFalse(result["review_ready"])
        self.assertTrue(any("congeladas" in x for x in result["blockers"]))

    def test_volume_profile_requires_documented_source_methodology(self):
        result=evaluate_setup_for_review(
            "volume-profile",
            evidence(source_methodology_verified=False),
        )
        self.assertFalse(result["review_ready"])
        self.assertTrue(any("fonte/metodologia" in x for x in result["blockers"]))

    def test_advanced_setup_is_not_beginner_ready_even_with_evidence(self):
        result=evaluate_setup_for_review("crt",evidence())
        self.assertTrue(result["review_ready"])
        self.assertFalse(result["beginner_review_ready"])

    def test_nan_negative_and_boolean_counts_fail_closed(self):
        for bad in (float("nan"),-1,True,"bad"):
            with self.subTest(bad=bad):
                result=evaluate_setup_for_review("fvg",evidence(backtest_samples=bad))
                self.assertFalse(result["review_ready"])

    def test_unknown_setup_fails_closed(self):
        result=evaluate_setup_for_review("not-real",evidence())
        self.assertFalse(result["review_ready"])
        self.assertFalse(result["beginner_review_ready"])
        self.assertIn("Setup não cadastrado",result["blockers"])

    def test_thresholds_are_review_thresholds_not_profit_promises(self):
        t=ReviewThresholds()
        self.assertGreaterEqual(t.min_backtest_samples,100)
        self.assertGreaterEqual(t.min_forward_samples,30)
        self.assertGreaterEqual(t.min_regimes,2)
        self.assertGreaterEqual(t.min_sessions,2)

    def test_backtest_and_forward_are_kept_as_distinct_evidence_sources(self):
        frame=pd.DataFrame([{
            "strategy":"FVG","trades":120,"expectancy_r":0.20,"profit_factor":1.4,
            "max_drawdown_r":6.0,"temporal_positive_fold_pct":75,
            "oos_positive_pct":67,"friction_positive_scenario_pct":75,
            "parameter_positive_variant_pct":70,
        }])
        forward_rows=[{
            "setup_id":"fvg","pair":"EUR/USD","observed_at":"2026-09-19T12:00:00Z",
            "session":"London","regime":"trend","direction":"BUY","entry":1.1,
            "stop":1.09,"target":1.12,"result_r":1.0,"data_quality":90,
            "decision_state":"PAPER",
        }]
        mapped=build_setup_evidence_map(
            frame,forward_rows,frozen_setup_ids=["fvg"]
        )
        self.assertEqual(mapped["fvg"]["backtest_samples"],120)
        self.assertEqual(mapped["fvg"]["forward_samples"],1)
        self.assertEqual(mapped["fvg"]["expectancy_r"],0.20)
        self.assertEqual(mapped["fvg"]["forward_expectancy_r"],1.0)
        self.assertTrue(mapped["fvg"]["rules_frozen_before_evaluation"])

    def test_historical_oos_does_not_fake_forward_paper_samples(self):
        frame=pd.DataFrame([{
            "strategy":"OTE","trades":200,"expectancy_r":0.15,"profit_factor":1.3,
            "max_drawdown_r":8.0,"temporal_positive_fold_pct":80,
            "oos_positive_pct":90,"friction_positive_scenario_pct":80,
            "parameter_positive_variant_pct":80,
        }])
        mapped=build_setup_evidence_map(frame,[],frozen_setup_ids=["ote"])
        result=evaluate_setup_for_review("ote",mapped["ote"])
        self.assertFalse(result["review_ready"])
        self.assertIsNone(result["evidence"]["forward_samples"])
        self.assertTrue(any("forward_samples" in x for x in result["pending"]))


if __name__=="__main__":
    unittest.main()
