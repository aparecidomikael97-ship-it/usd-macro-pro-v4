import unittest

from atlasquant_aion_learning import (
    confidence_calibration,
    error_pattern_summary,
    evaluate_learning_experiment,
    learning_digest,
    learning_summary,
    new_learning_episode,
    new_learning_experiment,
    new_research_reference,
    settle_learning_episode,
    upsert_learning_episode,
)


class AtlasQuantAionControlledLearningTests(unittest.TestCase):
    def test_prediction_episode_is_open_and_non_executing(self):
        item = new_learning_episode(
            "Payroll direction",
            forecast_type="DIRECTIONAL",
            prediction="USD_UP",
            confidence_pct=72,
            model_version="aion-v1",
            evidence_refs=["calendar:123", "fred:payroll"],
            created_at="2026-09-24T12:00:00+00:00",
        )
        self.assertEqual(item["state"], "OPEN")
        self.assertEqual(item["forecast_confidence_pct"], 72.0)
        self.assertEqual(
            item["confidence_meaning"],
            "FORECAST_SELF_CONFIDENCE_NOT_PROFIT_PROBABILITY",
        )
        self.assertFalse(item["automatic_weight_change"])
        self.assertFalse(item["automatic_rule_change"])
        self.assertFalse(item["real_orders_enabled"])

    def test_categorical_settlement_records_match(self):
        item = new_learning_episode(
            "CPI scenario",
            forecast_type="CATEGORICAL",
            prediction="USD_UP",
            confidence_pct=70,
            created_at="2026-09-24T12:00:00+00:00",
        )
        settled = settle_learning_episode(
            item,
            actual_outcome="USD_UP",
            settled_at="2026-09-24T14:00:00+00:00",
        )
        self.assertEqual(settled["state"], "SETTLED")
        self.assertEqual(settled["evaluation"], "MATCH")
        self.assertTrue(settled["correct"])
        self.assertEqual(settled["error_cause"], "UNKNOWN")

    def test_error_cause_is_not_confirmed_unless_explicit(self):
        item = new_learning_episode(
            "Market reaction",
            prediction="RISK_ON",
            confidence_pct=80,
            created_at="2026-09-24T12:00:00+00:00",
        )
        settled = settle_learning_episode(
            item,
            actual_outcome="RISK_OFF",
            error_cause="NEWS_SHOCK",
            error_cause_confirmed=False,
        )
        self.assertFalse(settled["correct"])
        self.assertEqual(settled["error_cause"], "NEWS_SHOCK")
        self.assertEqual(settled["error_cause_truth"], "UNKNOWN")

    def test_numeric_episode_records_error_and_tolerance(self):
        item = new_learning_episode(
            "Payroll nowcast",
            forecast_type="NUMERIC",
            prediction="210k",
            numeric_prediction=210,
            numeric_tolerance=15,
            confidence_pct=65,
            created_at="2026-09-24T12:00:00+00:00",
        )
        settled = settle_learning_episode(item, actual_numeric=232)
        self.assertFalse(settled["correct"])
        self.assertEqual(settled["evaluation"], "MISMATCH")
        self.assertEqual(settled["absolute_error"], 22.0)
        self.assertEqual(settled["signed_error"], 22.0)

    def test_confidence_calibration_uses_only_settled_boolean_outcomes(self):
        rows = []
        for idx, (conf, pred, actual) in enumerate([
            (90, "UP", "UP"),
            (90, "UP", "DOWN"),
            (60, "UP", "UP"),
            (40, "DOWN", "DOWN"),
        ]):
            item = new_learning_episode(
                f"case-{idx}",
                prediction=pred,
                confidence_pct=conf,
                created_at=f"2026-09-24T12:0{idx}:00+00:00",
            )
            rows.append(settle_learning_episode(item, actual_outcome=actual))
        report = confidence_calibration(rows)
        self.assertEqual(report["samples"], 4)
        self.assertIsNotNone(report["mean_absolute_calibration_gap_pct"])
        self.assertFalse(report["confidence_is_profit_probability"])
        self.assertFalse(report["auto_recalibration_allowed"])

    def test_error_summary_counts_only_confirmed_causes_as_causal_learning(self):
        rows = []
        for idx, confirmed in enumerate((True, False)):
            item = new_learning_episode(
                f"error-{idx}",
                prediction="UP",
                confidence_pct=75,
                created_at=f"2026-09-24T13:0{idx}:00+00:00",
            )
            rows.append(settle_learning_episode(
                item,
                actual_outcome="DOWN",
                error_cause="REGIME_SHIFT",
                error_cause_confirmed=confirmed,
            ))
        summary = error_pattern_summary(rows)
        self.assertEqual(summary["errors"], 2)
        self.assertEqual(summary["confirmed_cause_counts"]["REGIME_SHIFT"], 1)
        self.assertEqual(summary["errors_without_confirmed_cause"], 1)
        self.assertFalse(summary["causality_inferred_automatically"])

    def test_research_reference_points_to_backtest_without_live_effect(self):
        ref = new_research_reference(
            "BACKTEST",
            "snapshot-abc",
            strategy="ICT_AMD",
            summary="100 trades, research only",
            created_at="2026-09-24T12:00:00+00:00",
        )
        self.assertEqual(ref["kind"], "BACKTEST")
        self.assertTrue(ref["research_only"])
        self.assertTrue(ref["no_live_gate_effect"])
        self.assertFalse(ref["automatic_promotion"])

    def test_experiment_needs_more_evidence_when_oos_is_small(self):
        exp = new_learning_experiment(
            "champion-v1",
            "challenger-v2",
            rationale="Improve calibration.",
            created_at="2026-09-24T12:00:00+00:00",
        )
        evaluated = evaluate_learning_experiment(
            exp,
            champion_metrics={
                "expectancy_r":0.10,
                "max_drawdown_r":4.0,
                "calibration_error_pct":12,
                "false_alert_rate_pct":20,
            },
            challenger_metrics={
                "oos_samples":40,
                "expectancy_r":0.20,
                "max_drawdown_r":3.0,
                "calibration_error_pct":8,
                "false_alert_rate_pct":15,
            },
            shadow_summary={
                "eligible_for_manual_review":True,
                "critical_mismatches":0,
            },
        )
        self.assertEqual(evaluated["state"], "NEED_MORE_EVIDENCE")
        self.assertFalse(evaluated["evaluation"]["automatic_promotion"])

    def test_experiment_becomes_human_review_candidate_only_when_all_gates_pass(self):
        exp = new_learning_experiment(
            "champion-v1",
            "challenger-v2",
            rationale="Reduce false alerts and calibration error.",
            created_at="2026-09-24T12:00:00+00:00",
        )
        evaluated = evaluate_learning_experiment(
            exp,
            champion_metrics={
                "expectancy_r":0.10,
                "max_drawdown_r":4.0,
                "calibration_error_pct":12,
                "false_alert_rate_pct":20,
            },
            challenger_metrics={
                "oos_samples":150,
                "expectancy_r":0.15,
                "max_drawdown_r":3.5,
                "calibration_error_pct":9,
                "false_alert_rate_pct":17,
            },
            shadow_summary={
                "eligible_for_manual_review":True,
                "critical_mismatches":0,
            },
        )
        self.assertEqual(evaluated["state"], "HUMAN_REVIEW_CANDIDATE")
        self.assertTrue(evaluated["evaluation"]["eligible_for_human_review"])
        self.assertFalse(evaluated["evaluation"]["automatic_promotion"])
        self.assertFalse(evaluated["production_change_allowed"])

    def test_challenger_is_rejected_when_any_non_degradation_gate_fails(self):
        exp = new_learning_experiment(
            "champion-v1",
            "challenger-v2",
            rationale="Try higher sensitivity.",
            created_at="2026-09-24T12:00:00+00:00",
        )
        evaluated = evaluate_learning_experiment(
            exp,
            champion_metrics={
                "expectancy_r":0.10,
                "max_drawdown_r":4.0,
                "calibration_error_pct":12,
                "false_alert_rate_pct":20,
            },
            challenger_metrics={
                "oos_samples":150,
                "expectancy_r":0.16,
                "max_drawdown_r":5.0,
                "calibration_error_pct":10,
                "false_alert_rate_pct":18,
            },
            shadow_summary={
                "eligible_for_manual_review":True,
                "critical_mismatches":0,
            },
        )
        self.assertEqual(evaluated["state"], "REJECTED_FOR_NOW")
        failed = [x["check"] for x in evaluated["evaluation"]["checks"] if not x["passed"]]
        self.assertIn("DRAWDOWN_NON_DEGRADATION", failed)

    def test_summary_and_digest_are_stable_and_do_not_change_rules(self):
        episode = new_learning_episode(
            "case",
            prediction="UP",
            confidence_pct=70,
            created_at="2026-09-24T12:00:00+00:00",
        )
        rows = upsert_learning_episode([], episode)
        ref = new_research_reference(
            "BACKTEST",
            "snap-1",
            created_at="2026-09-24T12:00:00+00:00",
        )
        summary = learning_summary(rows, [], [ref])
        self.assertEqual(summary["episodes"], 1)
        self.assertEqual(summary["research_references"], 1)
        self.assertFalse(summary["automatic_learning_changes"])
        d1 = learning_digest(rows, [], [ref])
        d2 = learning_digest(rows, [], [ref])
        self.assertEqual(d1, d2)


if __name__ == "__main__":
    unittest.main()
