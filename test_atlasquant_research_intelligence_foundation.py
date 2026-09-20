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
from atlasquant_passport_evidence import EvidenceCriteria, fuse_operational_evidence
from atlasquant_research_evidence_capture import hydrate_research_evidence
from atlasquant_research_evidence_store import (
    evidence_record,
    latest_evidence_by_strategy,
    merge_evidence_records,
    parse_evidence_records,
    persist_research_evidence,
    serialize_evidence_records,
)
from atlasquant_backtest_intelligence import (
    backtest_intelligence_bundle,
    build_passport_from_backtest,
    diagnose_backtest_record,
    diagnosis_cause_summary,
)
from atlasquant_backtest_context import (
    context_template_csv,
    enrich_signals_point_in_time,
    normalize_context_snapshots,
)
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

    def test_passport_accepts_unknown_data_quality_as_evidence_gap(self):
        out=build_operational_passport(OperationalPassportInput(
            strategy="FVG",
            state="TESTING",
            trades=80,
            expectancy_r=0.15,
            profit_factor=1.2,
            net_r=12.0,
            max_drawdown_r=5.0,
            assets_covered=2,
            sessions_covered=2,
            regimes_covered=2,
            paper_trades=0,
            paper_expectancy_r=None,
            data_quality_pct=None,
        ))
        self.assertIsNone(out["data_quality_pct"])
        self.assertIn("qualidade dos dados não registrada",out["evidence_flags"])
        self.assertFalse(out["eligible_for_human_review"])

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


class BacktestContextTests(unittest.TestCase):
    def test_join_uses_latest_snapshot_before_signal_only(self):
        context=pd.DataFrame([
            {
                "captured_at":"2026-09-20T11:00:00Z","pair":"EUR/USD",
                "macro_alignment":-1,"regime":"RANGE","data_quality_pct":80,
            },
            {
                "captured_at":"2026-09-20T11:55:00Z","pair":"EUR/USD",
                "macro_alignment":1,"regime":"TREND","data_quality_pct":95,
            },
            {
                "captured_at":"2026-09-20T12:05:00Z","pair":"EUR/USD",
                "macro_alignment":-1,"regime":"FUTURE","data_quality_pct":99,
            },
        ])
        signal={
            "signal_time":"2026-09-20T12:00:00Z",
            "pair":"EUR/USD","side":"BUY","entry":1.1,"stop":1.09,"target":1.12,
        }
        out=enrich_signals_point_in_time([signal],context)
        self.assertEqual(out["matched"],1)
        self.assertFalse(out["future_context_used"])
        enriched=out["signals"][0]
        self.assertEqual(enriched["macro_alignment"],1)
        self.assertEqual(enriched["regime"],"TREND")
        self.assertNotEqual(enriched["regime"],"FUTURE")
        self.assertTrue(str(enriched["decision_captured_at"]).startswith("2026-09-20T11:55:00"))

    def test_explicit_signal_metadata_is_never_overwritten(self):
        context=pd.DataFrame([{
            "captured_at":"2026-09-20T11:55:00Z","pair":"EUR/USD",
            "macro_alignment":-1,"regime":"RANGE",
        }])
        signal={
            "signal_time":"2026-09-20T12:00:00Z","pair":"EUR/USD",
            "macro_alignment":1,"regime":"TREND",
        }
        out=enrich_signals_point_in_time([signal],context)
        self.assertEqual(out["signals"][0]["macro_alignment"],1)
        self.assertEqual(out["signals"][0]["regime"],"TREND")
        self.assertEqual(out["overwritten_explicit_fields"],0)

    def test_context_template_and_normalization_require_provenance_time_and_pair(self):
        self.assertIn("captured_at,pair",context_template_csv())
        normalized=normalize_context_snapshots(pd.DataFrame({
            "snapshot_time":["2026-09-20T11:00:00Z"],
            "par":["EUR/USD"],
            "macro":[1],
        }))
        self.assertEqual(len(normalized),1)
        self.assertEqual(normalized.iloc[0]["pair"],"EUR/USD")
        self.assertEqual(normalized.iloc[0]["macro_alignment"],1)


class BacktestIntelligenceTests(unittest.TestCase):
    def test_incomplete_context_explains_mechanics_without_inventing_macro(self):
        row={
            "signal_time":"2026-09-20T11:55:00+00:00",
            "entry_time":"2026-09-20T12:00:00+00:00",
            "exit_time":"2026-09-20T12:30:00+00:00",
            "pair":"EUR/USD",
            "setup":"FVG",
            "side":"BUY",
            "status":"STOP",
            "outcome":"LOSS",
            "net_r":-1.0,
            "cost_r":0.0,
            "slippage_r":0.0,
        }
        out=diagnose_backtest_record(row)
        self.assertFalse(out["context_diagnosis_available"])
        self.assertEqual(out["decision_outcome_relation"],"CONTEXT_INCOMPLETE")
        self.assertGreater(len(out["missing_context"]),0)
        self.assertIn("stop",out["probable_explanations"][0]["detail"].lower())
        self.assertFalse(out["causality_claimed"])
        self.assertFalse(out["lookahead_used"])

    def test_full_point_in_time_context_diagnoses_gain_quality_separately(self):
        row={
            "trade_id":"FULL-1",
            "signal_time":"2026-09-20T11:55:00+00:00",
            "decision_captured_at":"2026-09-20T11:55:00+00:00",
            "entry_time":"2026-09-20T12:00:00+00:00",
            "exit_time":"2026-09-20T12:45:00+00:00",
            "pair":"EUR/USD",
            "setup":"FVG",
            "side":"SELL",
            "status":"TARGET",
            "outcome":"GAIN",
            "net_r":1.8,
            "cost_r":0.1,
            "slippage_r":0.1,
            "macro_alignment":-1,
            "technical_confirmation":False,
            "liquidity_confirmation":True,
            "regime_fit":False,
            "known_high_impact_event":True,
            "data_quality_pct":52,
            "plan_followed":False,
            "event_time":"2026-09-20T12:20:00+00:00",
            "event_label":"CPI",
            "event_impact":"HIGH",
            "event_known_before_entry":False,
        }
        out=diagnose_backtest_record(row)
        self.assertTrue(out["context_diagnosis_available"])
        self.assertEqual(out["context_coverage_pct"],100.0)
        self.assertEqual(out["decision_outcome_relation"],"GAIN_WITH_WEAK_DECISION_QUALITY")
        codes={x["code"] for x in out["risk_or_failure_factors"]}
        self.assertIn("MACRO_CONFLICT",codes)
        self.assertIn("TECH_UNCONFIRMED",codes)
        self.assertIn("REGIME_MISMATCH",codes)
        self.assertIn("KNOWN_EVENT_RISK",codes)
        self.assertIn("HIGH_IMPACT_DURING_TRADE",codes)
        self.assertFalse(out["causality_claimed"])

    def test_passport_from_backtest_marks_missing_quality_and_paper(self):
        rows=[
            {"pair":"EUR/USD","setup":"FVG","session":"London","outcome":"GAIN","net_r":2.0},
            {"pair":"EUR/USD","setup":"FVG","session":"London","outcome":"LOSS","net_r":-1.0},
        ]
        out=build_passport_from_backtest(rows,strategy="FVG")
        self.assertEqual(out["state"],"TESTING")
        self.assertFalse(out["automatic_promotion"])
        self.assertIn("qualidade dos dados não registrada",out["evidence_flags"])
        self.assertIn("paper trading ainda insuficiente",out["evidence_flags"])

    def test_cause_summary_counts_loss_factors_without_calling_them_causal(self):
        diagnoses=[
            {
                "outcome":"LOSS",
                "probable_explanations":[
                    {"code":"STOP_HIT","detail":"stop","confidence":"HIGH"},
                    {"code":"MACRO_CONFLICT","detail":"macro contra","confidence":"HIGH"},
                ],
            },
            {
                "outcome":"LOSS",
                "probable_explanations":[
                    {"code":"STOP_HIT","detail":"stop","confidence":"HIGH"},
                    {"code":"MACRO_CONFLICT","detail":"macro contra","confidence":"HIGH"},
                ],
            },
            {
                "outcome":"GAIN",
                "probable_explanations":[
                    {"code":"TARGET_HIT","detail":"alvo","confidence":"HIGH"},
                ],
            },
        ]
        rows=diagnosis_cause_summary(diagnoses)
        macro=[x for x in rows if x["outcome"]=="LOSS" and x["code"]=="MACRO_CONFLICT"][0]
        self.assertEqual(macro["trades"],2)
        self.assertEqual(macro["share_of_outcome_pct"],100.0)
        self.assertFalse(macro["causality_claimed"])

    def test_bundle_keeps_diagnosis_and_passport_together(self):
        rows=[
            {
                "signal_time":"2026-09-20T11:55:00+00:00",
                "entry_time":"2026-09-20T12:00:00+00:00",
                "exit_time":"2026-09-20T12:30:00+00:00",
                "pair":"EUR/USD","setup":"FVG","session":"London",
                "side":"BUY","status":"TARGET","outcome":"GAIN","net_r":2.0,
            }
        ]
        out=backtest_intelligence_bundle(rows,strategy="FVG")
        self.assertEqual(out["executed_trades"],1)
        self.assertEqual(out["rich_context_trades"],0)
        self.assertEqual(out["passport"]["strategy"],"FVG")
        self.assertFalse(out["automatic_execution"])
        self.assertFalse(out["automatic_promotion"])


class PassportEvidenceFusionTests(unittest.TestCase):
    def _passport(self):
        return {
            "strategy":"FVG",
            "state":"TESTING",
            "observed_metrics":{
                "trades":120,
                "expectancy_r":0.22,
                "profit_factor":1.4,
                "net_r":26.4,
                "max_drawdown_r":5.0,
            },
            "coverage":{"assets":3,"sessions":3,"regimes":3},
            "data_quality_pct":94,
        }

    def test_full_evidence_can_only_become_human_review_candidate(self):
        paper={
            "forward_samples":45,
            "forward_expectancy_r":0.18,
            "forward_profit_factor":1.3,
            "forward_max_drawdown_r":4.0,
            "forward_win_rate_pct":55,
        }
        shadow={"samples":120,"eligible_for_manual_review":True}
        out=fuse_operational_evidence(
            self._passport(),
            paper_summary=paper,
            temporal_status="POSITIVE_ACROSS_FOLDS",
            walk_forward_status="POSITIVE_ALL_OOS_WINDOWS",
            friction_status="POSITIVE_ALL_TESTED_FRICTION",
            parameter_status="POSITIVE_ALL_PREDEFINED_VARIANTS",
            positive_fold_pct=75,
            oos_positive_pct=67,
            friction_positive_pct=75,
            parameter_positive_pct=70,
            shadow_summary=shadow,
            criteria=EvidenceCriteria(require_shadow=True),
        )
        self.assertEqual(out["state"],"HUMAN_REVIEW_CANDIDATE")
        self.assertTrue(out["eligible_for_human_review"])
        self.assertFalse(out["automatic_promotion"])
        self.assertFalse(out["automatic_strategy_change"])
        self.assertFalse(out["real_orders_enabled"])
        self.assertIn("não mede probabilidade",out["interpretation"].lower())

    def test_good_backtest_without_paper_stays_pending(self):
        out=fuse_operational_evidence(
            self._passport(),
            temporal_status="POSITIVE_ACROSS_FOLDS",
            walk_forward_status="POSITIVE_ALL_OOS_WINDOWS",
            friction_status="POSITIVE_ALL_TESTED_FRICTION",
            parameter_status="POSITIVE_ALL_PREDEFINED_VARIANTS",
            positive_fold_pct=75,
            oos_positive_pct=67,
            friction_positive_pct=75,
            parameter_positive_pct=70,
        )
        self.assertEqual(out["state"],"PAPER_EVIDENCE_PENDING")
        self.assertFalse(out["eligible_for_human_review"])
        self.assertIn("paper_sample",out["failures"])
        self.assertIn("paper_backtest_alignment",out["failures"])

    def test_negative_or_weak_robustness_does_not_count_as_sufficient(self):
        paper={"forward_samples":40,"forward_expectancy_r":0.18}
        out=fuse_operational_evidence(
            self._passport(),
            paper_summary=paper,
            temporal_status="MIXED_ACROSS_FOLDS",
            walk_forward_status="MIXED_OOS_WINDOWS",
            friction_status="BREAKS_UNDER_TESTED_FRICTION",
            parameter_status="MIXED_PREDEFINED_VARIANTS",
            positive_fold_pct=33,
            oos_positive_pct=33,
            friction_positive_pct=50,
            parameter_positive_pct=33,
        )
        self.assertFalse(out["checks"]["temporal_diagnostic"])
        self.assertFalse(out["checks"]["walk_forward_diagnostic"])
        self.assertFalse(out["checks"]["friction_diagnostic"])
        self.assertFalse(out["checks"]["parameter_diagnostic"])
        self.assertFalse(out["eligible_for_human_review"])

    def test_negative_backtest_or_paper_expectancy_cannot_be_review_ready(self):
        bad_passport=self._passport()
        bad_passport["observed_metrics"]=dict(bad_passport["observed_metrics"])
        bad_passport["observed_metrics"]["expectancy_r"]=-0.05
        paper={"forward_samples":45,"forward_expectancy_r":-0.04}
        out=fuse_operational_evidence(
            bad_passport,
            paper_summary=paper,
            temporal_status="POSITIVE_ACROSS_FOLDS",
            walk_forward_status="POSITIVE_ALL_OOS_WINDOWS",
            friction_status="POSITIVE_ALL_TESTED_FRICTION",
            parameter_status="POSITIVE_ALL_PREDEFINED_VARIANTS",
            positive_fold_pct=75,
            oos_positive_pct=67,
            friction_positive_pct=75,
            parameter_positive_pct=70,
        )
        self.assertFalse(out["checks"]["backtest_expectancy"])
        self.assertFalse(out["checks"]["paper_expectancy"])
        self.assertFalse(out["eligible_for_human_review"])

    def test_paper_gap_is_descriptive_and_can_block_review(self):
        paper={"forward_samples":50,"forward_expectancy_r":-0.20}
        out=fuse_operational_evidence(
            self._passport(),
            paper_summary=paper,
            temporal_status="POSITIVE_ACROSS_FOLDS",
            walk_forward_status="POSITIVE_ALL_OOS_WINDOWS",
            friction_status="POSITIVE_ALL_TESTED_FRICTION",
            parameter_status="POSITIVE_ALL_PREDEFINED_VARIANTS",
            positive_fold_pct=75,
            oos_positive_pct=67,
            friction_positive_pct=75,
            parameter_positive_pct=70,
        )
        self.assertEqual(out["state"],"EVIDENCE_GAPS")
        self.assertFalse(out["checks"]["paper_backtest_alignment"])
        self.assertAlmostEqual(
            out["backtest_paper_comparison"]["expectancy_gap_r"],
            -0.42,
        )


class ResearchEvidenceStoreTests(unittest.TestCase):
    def test_store_roundtrip_and_deduplication(self):
        a=evidence_record(
            strategy="FVG",
            captured_at="2026-09-20T12:00:00+00:00",
            source="BACKTEST",
            pair="EUR/USD",
            passport={"state":"TESTING"},
            evidence={"state":"PAPER_EVIDENCE_PENDING"},
        )
        raw=serialize_evidence_records([a])
        parsed=parse_evidence_records(raw)
        self.assertEqual(parsed[0]["record_id"],a["record_id"])
        merged,added=merge_evidence_records(parsed,[a])
        self.assertEqual(added,0)
        self.assertEqual(len(merged),1)

    def test_latest_evidence_by_strategy_uses_latest_timestamp(self):
        old=evidence_record(
            strategy="FVG",captured_at="2026-09-20T10:00:00+00:00",
            source="BACKTEST",passport={},evidence={},
        )
        new=evidence_record(
            strategy="FVG",captured_at="2026-09-20T11:00:00+00:00",
            source="BACKTEST",passport={"state":"NEW"},evidence={},
        )
        latest=latest_evidence_by_strategy([new,old])
        self.assertEqual(latest["FVG"]["passport"]["state"],"NEW")

    def test_session_and_remote_evidence_hydrate_without_duplicates(self):
        a=evidence_record(
            strategy="FVG",captured_at="2026-09-20T12:00:00Z",
            source="BACKTEST",passport={},evidence={},
        )
        b=evidence_record(
            strategy="OTE",captured_at="2026-09-20T12:01:00Z",
            source="BACKTEST",passport={},evidence={},
        )
        rows=hydrate_research_evidence([a],[a,b])
        self.assertEqual(len(rows),2)
        self.assertEqual({x["strategy"] for x in rows},{"FVG","OTE"})

    def test_store_refuses_runtime_write_to_main_without_network(self):
        record=evidence_record(
            strategy="FVG",captured_at="2026-09-20T12:00:00+00:00",
            source="BACKTEST",passport={},evidence={},
        )
        out=persist_research_evidence(
            [record],
            repo="owner/repo",
            branch="main",
            token="secret",
        )
        self.assertFalse(out["ok"])
        self.assertEqual(out["reason"],"UNSAFE_BRANCH")


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
