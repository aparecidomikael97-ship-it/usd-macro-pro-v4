"""Synthetic cross-module FX Precision Gate regression; no real source or trading."""
from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
import unittest

from atlasquant_trader_precision_gate_orchestrator_lab import (
    FX28_CANONICAL_SYMBOLS, ResearchPacket,
    inspect_fx_precision_orchestrator_lab as inspect,
)
from atlasquant_trader_selective_bias_gate_lab import (
    BiasObservation, SelectiveAuditClaims,
)
from atlasquant_trader_fx_evidence_dependency_gate_lab import FactorClaim
from test_atlasquant_trader_fx28_bilateral_symmetry_guard_lab import inputs
from test_atlasquant_trader_fx28_d1w1_consensus_guard_lab import w_inputs, WEEK, DECISION
from test_atlasquant_trader_fx_m15_price_cost_veto_lab import fixture as m15_fixture, T
from test_atlasquant_trader_market_regime_veto_lab import candles as regime_candles
from test_atlasquant_trader_selective_bias_gate_lab import holdout

NOW = T + timedelta(seconds=2)
DIRECTION = "BAIXA"   # synthetic EUR < USD in both D1 and W1
QUOTE_RELATIVE = "QUOTE_RELATIVE"


def factor(fid: str, root: str, family: str, cutoff: datetime,
           *, side: str = QUOTE_RELATIVE) -> FactorClaim:
    return FactorClaim(fid, root, family, side, cutoff - timedelta(minutes=15), "a" * 64)


def sources(cutoff: datetime):
    return [
        factor("ECON_CPI", "ROOT_CPI_NOV26", "MACRO", cutoff),
        factor("CENTRAL_BANK", "ROOT_POLICY_NOV26", "POLICY", cutoff),
        factor("MARKET_REPRICING", "ROOT_REPRICING_NOV26", "MARKET", cutoff),
    ]


def fixture() -> ResearchPacket:
    daily_scores, daily_pairs = inputs()
    weekly_scores, weekly_pairs = w_inputs()
    m15_bars, quote = m15_fixture(symbol="EUR/USD", side=DIRECTION)
    candidate = BiasObservation(
        asset="EUR/USD", horizon="D1", evaluated_at=NOW,
        weekly=DIRECTION, daily=DIRECTION, grade_0_to_10=8.5,
        macro_captured_at=DECISION - timedelta(minutes=20),
        snapshot_sha256="a" * 64,
    )
    old = replace(candidate, evaluated_at=NOW-timedelta(minutes=30),
                  macro_captured_at=DECISION-timedelta(hours=1),
                  snapshot_sha256="b" * 64)
    return ResearchPacket(
        candidate=candidate,
        daily_currency_scores=daily_scores, daily_pair_claims=daily_pairs,
        weekly_currency_scores=weekly_scores, weekly_pair_claims=weekly_pairs,
        daily_decision_at_utc=DECISION, weekly_decision_at_utc=WEEK,
        factors_by_horizon={"D1": sources(DECISION), "W1": sources(WEEK)},
        regime_bars_by_horizon={
            "D1": regime_candles("D1", "DOWN"),
            "W1": regime_candles("W1", "DOWN"),
        },
        closed_m15_bars=m15_bars, indicative_quote=quote,
        previous_confirmations=[old],
        holdout_windows=holdout(asset="EUR/USD", horizon="D1", direction=DIRECTION),
        audit_claims=SelectiveAuditClaims(True, True, True, True, True, True),
        calendar_reviewed_at_utc=DECISION + timedelta(hours=1),
        high_impact_events=(),
        d1_coverage_trading_date=date(2026, 11, 10),
        d1_coverage_present_symbols=FX28_CANONICAL_SYMBOLS,
        d1_coverage_observed_at_utc=DECISION-timedelta(minutes=20),
    )


class OrchestrationTests(unittest.TestCase):
    def check(self, packet=None, now=NOW):
        return inspect(packet=fixture() if packet is None else packet,
                       inspected_at_utc=now)

    def no_go(self, r):
        self.assertEqual(r["operational_bias"], "AGUARDAR")
        self.assertFalse(r["trade_authorized"])
        self.assertFalse(r["publishable"])
        self.assertFalse(r["live_alert_allowed"])
        self.assertFalse(r["worker_enabled"])
        self.assertFalse(r["scheduler_enabled"])
        self.assertFalse(r["market_data_and_macro_originals_independently_authenticated"])
        self.assertFalse(r["broker_bid_ask_executable_verified"])
        self.assertFalse(r["calibration_prospectively_verified"])
        self.assertIsNone(r["calibrated_direction_probability"])
        self.assertIsNone(r["validated_accuracy"])
        self.assertEqual(r["new_cost_brl"], 0)

    def test_all_seven_stages_structurally_pass_but_never_signal(self):
        result = self.check()
        self.assertEqual(result["state"], "LAB_PRECISION_RESEARCH_CANDIDATE_UNATTESTED")
        self.assertEqual(result["stages_tested"], 7)
        self.assertEqual(result["stages_structurally_passed"], 7)
        self.assertTrue(result["stage_reports"]["D1_28FX_DATE_COVERAGE"]["structurally_accepted"])
        self.assertFalse(result["d1_28fx_coverage_independently_attested"])
        self.assertEqual(result["research_candidate_direction"], DIRECTION)
        self.assertEqual(result["claimed_unique_event_roots_across_d1w1_not_independent"], 3)
        self.assertEqual(result["blocking_stages"], [])
        self.no_go(result)

    def test_missing_one_d1_pair_blocks_even_if_six_other_stages_pass(self):
        p = fixture()
        rows = tuple(x for x in FX28_CANONICAL_SYMBOLS if x != "GBPNZD")
        result = self.check(replace(p, d1_coverage_present_symbols=rows))
        gate = result["stage_reports"]["D1_28FX_DATE_COVERAGE"]
        self.assertEqual(gate["state"], "LAB_SINGLE_PAIR_D1_MISSING_DATE_QUARANTINE")
        self.assertEqual(gate["missing_symbols"], ["GBPNZD"])
        self.assertIn("D1_28FX_DATE_COVERAGE", result["blocking_stages"])
        self.assertEqual(result["stages_structurally_passed"], 6)
        self.assertIsNone(result["research_candidate_direction"])
        self.no_go(result)

    def test_all_28_missing_cannot_be_reclassified_as_a_holiday(self):
        p = fixture()
        result = self.check(replace(p, d1_coverage_present_symbols=()))
        self.assertIn("D1_28FX_DATE_COVERAGE", result["blocking_stages"])
        self.assertEqual(result["stage_reports"]["D1_28FX_DATE_COVERAGE"]["state"],
                         "LAB_SHARED_28FX_NO_D1_BARS_CALENDAR_UNVERIFIED")
        self.no_go(result)

    def test_partial_date_coverage_blocks_complete_fx28_bias_matrix(self):
        p = fixture()
        for n in (8, 18, 26):
            with self.subTest(observed_count=n):
                result = self.check(replace(p, d1_coverage_present_symbols=FX28_CANONICAL_SYMBOLS[:n]))
                self.assertIn("D1_28FX_DATE_COVERAGE", result["blocking_stages"])
                self.assertEqual(result["stage_reports"]["D1_28FX_DATE_COVERAGE"]["observed_count"], n)
                self.assertIsNone(result["research_candidate_direction"])
                self.no_go(result)

    def test_missing_date_or_coverage_clock_defaults_fail_closed(self):
        p = fixture()
        for edited in (
            replace(p, d1_coverage_trading_date=None),
            replace(p, d1_coverage_observed_at_utc=None),
            replace(p, d1_coverage_present_symbols=None),
        ):
            with self.subTest(edited=edited.d1_coverage_trading_date,
                              clock=edited.d1_coverage_observed_at_utc):
                result = self.check(edited)
                self.assertIn("D1_28FX_DATE_COVERAGE", result["blocking_stages"])
                self.no_go(result)

    def test_future_same_day_or_stale_coverage_date_blocked(self):
        p = fixture()
        for day in (date(2026,11,11), date(2026,11,12), date(2026,11,1)):
            with self.subTest(day=day):
                result = self.check(replace(p, d1_coverage_trading_date=day))
                self.assertEqual(result["stage_reports"]["D1_28FX_DATE_COVERAGE"]["state"],
                                 "LAB_D1_COVERAGE_CUTOFF_BLOCKED")
                self.no_go(result)

    def test_coverage_seen_after_decision_cannot_rewrite_prior_bias(self):
        p = fixture()
        result = self.check(replace(
            p, d1_coverage_observed_at_utc=DECISION+timedelta(seconds=1)))
        self.assertEqual(result["stage_reports"]["D1_28FX_DATE_COVERAGE"]["state"],
                         "LAB_D1_COVERAGE_CUTOFF_BLOCKED")
        self.assertIsNone(result["research_candidate_direction"])
        self.no_go(result)

    def test_claimed_complete_date_still_not_real_provenance_or_edge(self):
        result = self.check()
        report = result["stage_reports"]["D1_28FX_DATE_COVERAGE"]
        self.assertFalse(report["independently_attested"])
        self.assertFalse(result["d1_28fx_coverage_independently_attested"])
        self.assertTrue(result["d1_28fx_coverage_claim_not_source_verified"])
        self.assertIsNone(result["validated_accuracy"])
        self.no_go(result)

    def test_duplicate_or_unknown_symbol_rejected_by_new_date_gate(self):
        p = fixture()
        for syms in (
            FX28_CANONICAL_SYMBOLS[:-1] + (FX28_CANONICAL_SYMBOLS[0],),
            FX28_CANONICAL_SYMBOLS[:-1] + ("XAUUSD",),
        ):
            with self.subTest(syms=syms[-1]):
                result = self.check(replace(p, d1_coverage_present_symbols=syms))
                self.assertIn("D1_28FX_DATE_COVERAGE", result["blocking_stages"])
                self.no_go(result)

    def test_no_bid_ask_requires_abstention(self):
        p = replace(fixture(), indicative_quote=None)
        result = self.check(p)
        self.assertIn("M15_PRICE_COST", result["blocking_stages"])
        self.assertIsNone(result["research_candidate_direction"])
        self.no_go(result)

    def test_spread_expensive_blocks_even_when_all_other_checks_pass(self):
        p = fixture()
        bad = replace(p.indicative_quote, ask="1.10200")
        result = self.check(replace(p, indicative_quote=bad))
        self.assertEqual(result["stage_reports"]["M15_PRICE_COST"]["state"], "LAB_SPREAD_TOO_WIDE_VETO")
        self.no_go(result)

    def test_price_already_extended_rejected(self):
        p = fixture()
        quote = replace(p.indicative_quote, bid="1.09745", ask="1.09753")
        result = self.check(replace(p, indicative_quote=quote))
        self.assertEqual(result["stage_reports"]["M15_PRICE_COST"]["state"], "LAB_PRICE_ALREADY_EXTENDED_VETO")
        self.no_go(result)

    def test_daily_weekly_conflict_blocks(self):
        p = fixture()
        ws, wp = w_inputs(override={"EUR": 200})
        result = self.check(replace(p, weekly_currency_scores=ws, weekly_pair_claims=wp))
        self.assertIn("BILATERAL_D1W1", result["blocking_stages"])
        self.no_go(result)

    def test_candidate_direction_conflicts_with_two_macros(self):
        p = fixture()
        bad = replace(p.candidate, weekly="ALTA", daily="ALTA")
        result = self.check(replace(p, candidate=bad))
        self.assertIn("BILATERAL_D1W1", result["blocking_stages"])
        self.assertIn("EVIDENCE_D1", result["blocking_stages"])
        self.no_go(result)

    def test_three_indicators_same_root_not_three_confirmations(self):
        p = fixture()
        rows = [replace(x, root_catalyst_id="ROOT_CPI_NOV26")
                for x in p.factors_by_horizon["D1"]]
        result = self.check(replace(p, factors_by_horizon={"D1":rows,"W1":p.factors_by_horizon["W1"]}))
        self.assertEqual(result["stage_reports"]["EVIDENCE_D1"]["claimed_root_count"], 1)
        self.assertIn("EVIDENCE_D1", result["blocking_stages"])
        self.no_go(result)

    def test_factor_direction_conflict_even_with_three_roots(self):
        p = fixture()
        rows = p.factors_by_horizon["W1"].copy()
        rows[1] = replace(rows[1], relative_side="BASE_RELATIVE")
        result = self.check(replace(p, factors_by_horizon={"D1":p.factors_by_horizon["D1"],"W1":rows}))
        self.assertIn("EVIDENCE_W1", result["blocking_stages"])
        self.no_go(result)

    def test_regime_range_blocks_even_if_cost_good(self):
        p = fixture()
        rows = {"D1":regime_candles("D1", "RANGE"),"W1":p.regime_bars_by_horizon["W1"]}
        result = self.check(replace(p, regime_bars_by_horizon=rows))
        self.assertIn("MARKET_REGIME", result["blocking_stages"])
        self.no_go(result)

    def test_high_impact_news_blackout(self):
        p = fixture()
        result = self.check(replace(p, high_impact_events=(NOW,)))
        self.assertIn("SELECTIVE_NEWS_OOS", result["blocking_stages"])
        self.no_go(result)

    def test_release_unverified_blocks(self):
        p = fixture()
        result = self.check(replace(p, unverified_event_actual_pending=True))
        self.assertIn("SELECTIVE_NEWS_OOS", result["blocking_stages"])
        self.no_go(result)

    def test_lack_of_out_of_sample_evidence_blocks(self):
        p = fixture()
        result = self.check(replace(p, holdout_windows=[]))
        self.assertIn("SELECTIVE_NEWS_OOS", result["blocking_stages"])
        self.no_go(result)

    def test_false_provenance_claim_blocks(self):
        p = fixture()
        claims = replace(p.audit_claims, market_data_license_reviewed=False)
        result = self.check(replace(p, audit_claims=claims))
        self.assertIn("SELECTIVE_NEWS_OOS", result["blocking_stages"])
        self.no_go(result)

    def test_outdated_calendar_review_blocks_entire_packet(self):
        p = fixture()
        result = self.check(replace(p, calendar_reviewed_at_utc=DECISION-timedelta(days=2)))
        self.assertEqual(result["reason"], "INVALID_HORIZON_DIRECTION_CALENDAR_OR_DECISION_CUTOFF")
        self.no_go(result)

    def test_bad_cutoffs_rejected(self):
        p = fixture()
        result = self.check(replace(p, weekly_decision_at_utc=DECISION+timedelta(seconds=1)))
        self.assertEqual(result["state"], "LAB_PRECISION_ABSTAIN")
        self.no_go(result)

    def test_future_or_naive_candidate_rejected(self):
        p = fixture()
        for v in (NOW+timedelta(seconds=5), NOW.replace(tzinfo=None)):
            with self.subTest(v=v):
                result = self.check(replace(p, candidate=replace(p.candidate, evaluated_at=v)))
                self.assertEqual(result["state"], "LAB_PRECISION_ABSTAIN")
                self.no_go(result)

    def test_missing_one_m15_bar_abstains(self):
        p = fixture()
        result = self.check(replace(p, closed_m15_bars=p.closed_m15_bars[:-1]))
        self.assertIn("M15_PRICE_COST", result["blocking_stages"])
        self.no_go(result)

    def test_no_package_or_bad_input_abstains(self):
        self.no_go(self.check(packet="APPROVED"))
        self.no_go(self.check(now=NOW.replace(tzinfo=None)))


if __name__ == "__main__":
    unittest.main()