import unittest
from datetime import date, datetime, timedelta, timezone

import pandas as pd

from atlasquant_operational_catalog import (
    catalog_summary,
    master_operational_catalog,
    model_by_id,
    transition_allowed,
)
from atlasquant_decision_stack import (
    EvidenceSignal,
    deduplicate_evidence,
    evaluate_decision_stack,
)
from atlasquant_operational_passport import (
    OperationalPassportInput,
    build_operational_passport,
)
from atlasquant_weekly_profile import analyze_weekly_extremes
from atlasquant_behavior_shift import BehaviorStats, detect_behavior_shift
from atlasquant_post_trade_diagnosis import (
    DecisionSnapshot,
    DuringTradeEvent,
    TradeOutcome,
    diagnose_trade,
    validate_point_in_time,
)


class OperationalCatalogTests(unittest.TestCase):
    def test_existing_objective_replays_are_coded_but_not_auto_validated(self):
        for model_id in ("BOS_CHOCH_OB","FVG","OTE","CRT","AMD_PO3"):
            model=model_by_id(model_id)
            self.assertIsNotNone(model)
            self.assertEqual(model.status,"CODED")
            self.assertTrue(model.objective_rules_ready)
            self.assertTrue(model.replay_module)

    def test_planned_models_do_not_masquerade_as_implemented(self):
        self.assertEqual(model_by_id("SILVER_BULLET").status,"CONCEPT")
        self.assertEqual(model_by_id("TURTLE_SOUP").status,"CONCEPT")
        self.assertEqual(model_by_id("UNICORN").status,"CONCEPT")
        self.assertFalse(model_by_id("SILVER_BULLET").objective_rules_ready)

    def test_catalog_is_explicitly_non_exhaustive_and_not_profit_claim(self):
        summary=catalog_summary()
        self.assertGreaterEqual(summary["models"],15)
        self.assertFalse(summary["exhaustive_claim"])
        self.assertIn("não significa validação",summary["interpretation"].lower())

    def test_validation_cannot_jump_lifecycle(self):
        self.assertFalse(transition_allowed("CONCEPT","VALIDATED"))
        self.assertFalse(transition_allowed("CODED","VALIDATED"))
        self.assertTrue(transition_allowed("CODED","BACKTESTED"))
        self.assertTrue(transition_allowed("BACKTESTED","PAPER"))
        self.assertTrue(transition_allowed("PAPER","VALIDATED"))
        self.assertTrue(transition_allowed("VALIDATED","PAUSED"))

    def test_catalog_ids_are_unique(self):
        ids=[x.model_id for x in master_operational_catalog()]
        self.assertEqual(len(ids),len(set(ids)))


class DecisionStackTests(unittest.TestCase):
    def test_duplicate_price_event_is_counted_once(self):
        rows=[
            EvidenceSignal("smc-sweep","SMC","BULLISH",70,"same-sweep","liquidity sweep"),
            EvidenceSignal("ict-sweep","ICT","BULLISH",85,"same-sweep","same sweep in ICT vocabulary"),
            EvidenceSignal("pa-rejection","PRICE_ACTION","BULLISH",60,"rejection","price rejection"),
        ]
        out=deduplicate_evidence(rows)
        self.assertEqual(len(out["signals"]),2)
        self.assertEqual(out["duplicate_count"],1)
        ids={x.evidence_id for x in out["signals"]}
        self.assertIn("ict-sweep",ids)
        self.assertNotIn("smc-sweep",ids)

    def test_cross_layer_conflict_is_visible_and_not_hidden_by_score(self):
        out=evaluate_decision_stack([
            EvidenceSignal("macro","FUNDAMENTAL","BULLISH",85,"macro"),
            EvidenceSignal("structure","SMC","BEARISH",80,"structure"),
            EvidenceSignal("trigger","PRICE_ACTION","BEARISH",70,"trigger"),
        ])
        self.assertTrue(out["cross_layer_conflict"])
        self.assertEqual(out["state"],"CONFLICT_REVIEW")
        self.assertFalse(out["automatic_execution"])
        self.assertFalse(out["real_orders_enabled"])
        self.assertIn("não é probabilidade",out["interpretation"].lower())

    def test_safety_veto_blocks_even_if_layers_align(self):
        out=evaluate_decision_stack([
            EvidenceSignal("macro","FUNDAMENTAL","BULLISH",80,"macro"),
            EvidenceSignal("smc","SMC","BULLISH",80,"structure"),
            EvidenceSignal("event","SAFETY","NEUTRAL",100,"event-risk",veto=True),
        ])
        self.assertEqual(out["state"],"BLOCKED_BY_SAFETY")
        self.assertEqual(len(out["vetoes"]),1)


class OperationalPassportTests(unittest.TestCase):
    def test_passport_separates_observed_metrics_from_promotion(self):
        out=build_operational_passport(OperationalPassportInput(
            strategy="FVG",
            state="OBSERVATION",
            trades=120,
            expectancy_r=0.22,
            profit_factor=1.35,
            net_r=26.4,
            max_drawdown_r=6.2,
            assets_covered=4,
            sessions_covered=3,
            regimes_covered=3,
            paper_trades=45,
            paper_expectancy_r=0.18,
            data_quality_pct=92,
            last_validation_date=date(2026,9,20),
        ))
        self.assertTrue(out["eligible_for_human_review"])
        self.assertFalse(out["automatic_promotion"])
        self.assertIsNone(out["profit_probability"])
        self.assertEqual(out["paper"]["gap_vs_backtest_r"],-0.04)

    def test_passport_flags_small_or_narrow_evidence(self):
        out=build_operational_passport(OperationalPassportInput(
            strategy="NEW",
            state="TESTING",
            trades=12,
            expectancy_r=0.8,
            profit_factor=2.5,
            net_r=9.6,
            max_drawdown_r=2.0,
            assets_covered=1,
            sessions_covered=1,
            regimes_covered=1,
            paper_trades=0,
            paper_expectancy_r=None,
            data_quality_pct=60,
        ))
        self.assertFalse(out["eligible_for_human_review"])
        self.assertGreaterEqual(len(out["evidence_flags"]),4)


class WeeklyProfileTests(unittest.TestCase):
    def test_weekly_extremes_are_measured_not_assumed(self):
        rows=[]
        start=pd.Timestamp("2026-08-03",tz="UTC")
        # Three Mon-Fri weeks with deliberately different extreme days.
        patterns=[
            ([10,12,14,13,11],[5,4,3,4,5]),   # Wed high, Wed low
            ([10,15,13,12,11],[5,4,2,3,4]),   # Tue high, Wed low
            ([11,12,13,16,14],[4,3,2,1,2]),   # Thu high, Thu low
        ]
        for week,(highs,lows) in enumerate(patterns):
            for day in range(5):
                dt=start+pd.Timedelta(days=week*7+day)
                rows.append({"datetime":dt,"high":highs[day],"low":lows[day]})
        out=analyze_weekly_extremes(pd.DataFrame(rows))
        self.assertEqual(out["weeks"],3)
        self.assertFalse(out["fixed_day_rule_assumed"])
        self.assertAlmostEqual(out["tuesday_wednesday_high_pct"],66.67,places=2)
        self.assertAlmostEqual(out["tuesday_wednesday_low_pct"],66.67,places=2)
        self.assertIn("não provam comportamento institucional",out["interpretation"].lower())


class BehaviorShiftTests(unittest.TestCase):
    def test_detects_observable_shift_without_claiming_institutional_intent(self):
        baseline=BehaviorStats(
            sample_size=120,
            london_expansion_pct=55,
            new_york_expansion_pct=40,
            sweep_followthrough_pct=62,
            reversal_after_sweep_pct=28,
            level_reaction_pct=58,
            average_range=100,
        )
        recent=BehaviorStats(
            sample_size=35,
            london_expansion_pct=30,
            new_york_expansion_pct=65,
            sweep_followthrough_pct=40,
            reversal_after_sweep_pct=52,
            level_reaction_pct=57,
            average_range=138,
        )
        out=detect_behavior_shift(baseline,recent)
        self.assertEqual(out["state"],"MEANINGFUL_SHIFT_REVIEW")
        self.assertGreaterEqual(out["change_count"],4)
        self.assertFalse(out["institutional_intent_inferred"])
        self.assertFalse(out["automatic_strategy_change"])

    def test_small_recent_window_does_not_trigger_behavior_story(self):
        baseline=BehaviorStats(100,50,45,60,30,55,100)
        recent=BehaviorStats(8,20,75,30,60,30,150)
        out=detect_behavior_shift(baseline,recent)
        self.assertEqual(out["state"],"INSUFFICIENT_SAMPLE")
        self.assertFalse(out["sample_sufficient"])
        self.assertEqual(out["change_count"],0)


class PostTradeDiagnosisTests(unittest.TestCase):
    def setUp(self):
        self.entry=datetime(2026,9,20,12,0,tzinfo=timezone.utc)
        self.snapshot=DecisionSnapshot(
            trade_id="T-1",
            captured_at=self.entry-timedelta(minutes=2),
            entry_time=self.entry,
            side="SELL",
            macro_alignment=-1,
            technical_confirmation=False,
            liquidity_confirmation=True,
            regime_fit=False,
            known_high_impact_event=True,
            data_quality_pct=48,
            plan_followed=False,
        )

    def test_loss_exposes_probable_reasons_without_claiming_causality(self):
        outcome=TradeOutcome(
            exit_time=self.entry+timedelta(hours=1),
            outcome="LOSS",
            net_r=-1.2,
            exit_reason="STOP",
            slippage_r=0.15,
            cost_r=0.05,
        )
        event=DuringTradeEvent(
            event_time=self.entry+timedelta(minutes=20),
            label="CPI",
            impact="HIGH",
        )
        out=diagnose_trade(self.snapshot,outcome,[event])
        codes={x["code"] for x in out["risk_or_failure_factors"]}
        self.assertIn("MACRO_CONFLICT",codes)
        self.assertIn("TECH_UNCONFIRMED",codes)
        self.assertIn("REGIME_MISMATCH",codes)
        self.assertIn("KNOWN_EVENT_RISK",codes)
        self.assertIn("LOW_DATA_QUALITY",codes)
        self.assertIn("PLAN_DEVIATION",codes)
        self.assertIn("HIGH_IMPACT_DURING_TRADE",codes)
        self.assertIn("SLIPPAGE",codes)
        self.assertEqual(out["decision_outcome_relation"],"LOSS_WITH_IDENTIFIED_DECISION_WEAKNESSES")
        self.assertFalse(out["lookahead_used"])
        self.assertFalse(out["causality_claimed"])
        self.assertFalse(out["automatic_strategy_change"])

    def test_good_decision_can_still_lose(self):
        good=DecisionSnapshot(
            trade_id="T-2",
            captured_at=self.entry-timedelta(minutes=1),
            entry_time=self.entry,
            side="BUY",
            macro_alignment=1,
            technical_confirmation=True,
            liquidity_confirmation=True,
            regime_fit=True,
            known_high_impact_event=False,
            data_quality_pct=91,
            plan_followed=True,
        )
        out=diagnose_trade(
            good,
            TradeOutcome(
                exit_time=self.entry+timedelta(minutes=45),
                outcome="LOSS",
                net_r=-1.0,
                exit_reason="STOP",
            ),
        )
        self.assertEqual(out["decision_outcome_relation"],"LOSS_DESPITE_COHERENT_DECISION")
        self.assertIn("não há causa dominante",out["probable_explanations"][0]["detail"])

    def test_bad_decision_can_still_gain(self):
        out=diagnose_trade(
            self.snapshot,
            TradeOutcome(
                exit_time=self.entry+timedelta(minutes=30),
                outcome="GAIN",
                net_r=1.5,
                exit_reason="TARGET",
            ),
        )
        self.assertEqual(out["decision_outcome_relation"],"GAIN_WITH_WEAK_DECISION_QUALITY")

    def test_future_event_is_ignored_for_this_trade(self):
        good=DecisionSnapshot(
            trade_id="T-3",
            captured_at=self.entry-timedelta(minutes=1),
            entry_time=self.entry,
            side="BUY",
            macro_alignment=1,
            technical_confirmation=True,
            liquidity_confirmation=True,
            regime_fit=True,
            known_high_impact_event=False,
            data_quality_pct=90,
            plan_followed=True,
        )
        exit_time=self.entry+timedelta(minutes=30)
        out=diagnose_trade(
            good,
            TradeOutcome(exit_time=exit_time,outcome="GAIN",net_r=1.0,exit_reason="TARGET"),
            [DuringTradeEvent(event_time=exit_time+timedelta(hours=2),label="Future news",impact="HIGH")],
        )
        self.assertEqual(out["during_trade_events"],[])
        self.assertFalse(any(x["code"]=="HIGH_IMPACT_DURING_TRADE" for x in out["risk_or_failure_factors"]))

    def test_snapshot_after_entry_is_rejected_as_lookahead(self):
        bad=DecisionSnapshot(
            trade_id="T-4",
            captured_at=self.entry+timedelta(seconds=1),
            entry_time=self.entry,
            side="BUY",
            macro_alignment=0,
            technical_confirmation=True,
            liquidity_confirmation=True,
            regime_fit=True,
            known_high_impact_event=False,
            data_quality_pct=80,
            plan_followed=True,
        )
        with self.assertRaises(ValueError):
            validate_point_in_time(bad)


if __name__=="__main__":
    unittest.main()
