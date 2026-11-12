"""Synthetic shared-PPI FX grouping tests; never historical market validation."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import unittest

from atlasquant_fx_universe import OFFICIAL_PAIRS
from atlasquant_trader_fx_evidence_dependency_gate_lab import FactorClaim
from atlasquant_trader_fx_event_concentration_lab import (
    ResearchCandidate, audit_fx_shared_event_concentration_lab as audit,
)

T = datetime(2026, 11, 13, 13, 30, tzinfo=timezone.utc)
AT = T + timedelta(minutes=30)
PPI = "US_PPI_OCT2026"


def candidate(asset="EUR/USD", side="ALTA", horizon="D1", roots=(PPI,)):
    direction = "BASE_RELATIVE" if side == "ALTA" else "QUOTE_RELATIVE"
    factors = tuple(FactorClaim(
        factor_id=f"FACTOR_{i:02d}_{asset.replace('/', '')}",
        root_catalyst_id=root,
        source_family="MACRO",
        relative_side=direction,
        captured_at_utc=T,
        source_sha256_claim="a" * 64,
    ) for i, root in enumerate(roots))
    return ResearchCandidate(asset, horizon, side, AT, factors)


class SharedRootConcentrationTests(unittest.TestCase):
    def check_no_go(self, result):
        self.assertEqual(result["operational_bias"], "AGUARDAR")
        for k in ("event_causality_independently_verified",
                  "cross_pair_correlation_statistically_estimated",
                  "broker_notional_and_executable_liquidity_verified",
                  "portfolio_risk_approved", "publishable", "live_alert_allowed",
                  "trade_authorized", "worker_enabled", "scheduler_enabled"):
            self.assertFalse(result[k], k)
        self.assertIsNone(result["independent_event_trial_count"])
        self.assertIsNone(result["directional_probability"])
        self.assertIsNone(result["validated_accuracy"])
        self.assertEqual((result["http_requests"], result["file_writes"],
                          result["new_cost_brl"]), (0, 0, 0))

    def run_audit(self, items, at=AT):
        result = audit(candidates=items, inspected_at_utc=at)
        self.check_no_go(result)
        return result

    def test_seven_usd_crosses_are_one_claimed_ppi_root(self):
        items = [candidate(pair, "BAIXA" if pair.startswith("USD/") else "ALTA")
                 for pair in OFFICIAL_PAIRS if "USD" in pair]
        self.assertEqual(len(items), 7)
        result = self.run_audit(items)
        self.assertEqual(result["state"], "LAB_SHARED_ROOT_EXPOSURE_REVIEW_REQUIRED")
        self.assertEqual((result["candidate_observations"], result["distinct_assets"],
                          result["claimed_event_roots"]), (7, 7, 1))
        root = result["shared_event_root_groups"][0]
        self.assertEqual(root["root_catalyst_id"], PPI)
        self.assertEqual(root["distinct_assets"], 7)
        self.assertEqual(root["currency_exposure_claims_not_root_causality"]["USD"],
                         ["SHORT"])
        self.assertEqual(result["currency_exposure_conflicts"], [])

    def test_d1_w1_repeated_same_pair_is_not_second_asset_or_trial(self):
        items = [candidate(horizon="D1"), candidate(horizon="W1")]
        result = self.run_audit(items)
        self.assertEqual(result["state"], "LAB_ROOT_INVENTORY_UNATTESTED_NO_GO")
        self.assertEqual((result["candidate_observations"], result["distinct_assets"]),
                         (2, 1))
        self.assertEqual(result["shared_event_root_groups"], [])
        self.assertEqual(result["event_root_inventory"][0]["horizons"], ["D1", "W1"])

    def test_two_pairs_can_have_same_root_without_causal_independence(self):
        result = self.run_audit([candidate(), candidate("GBP/USD")])
        self.assertEqual(result["shared_event_root_groups"][0]["distinct_assets"], 2)
        self.assertIsNone(result["independent_event_trial_count"])

    def test_opposing_usd_exposure_of_same_root_demands_review(self):
        result = self.run_audit([candidate("EUR/USD", "ALTA"),
                                 candidate("USD/JPY", "ALTA")])
        self.assertEqual(result["state"], "LAB_EVENT_EXPOSURE_CONFLICT_ABSTAIN")
        self.assertIn({"root_catalyst_id": PPI, "currency": "USD",
                       "opposing_candidate_exposures": ["LONG", "SHORT"]},
                      result["currency_exposure_conflicts"])

    def test_distinct_root_names_do_not_prove_statistics(self):
        result = self.run_audit([candidate(roots=("US_POLICY_2026",)),
                                 candidate("GBP/USD", roots=("US_PPI_2026",))])
        self.assertEqual(result["claimed_event_roots"], 2)
        self.assertEqual(result["shared_event_root_groups"], [])
        self.assertEqual(result["state"], "LAB_ROOT_INVENTORY_UNATTESTED_NO_GO")

    def test_multiple_claimed_roots_each_reuse_asset_once(self):
        items = [candidate(roots=(PPI, "US_YIELD_REACTION")),
                 candidate("GBP/USD", roots=(PPI, "US_YIELD_REACTION"))]
        result = self.run_audit(items)
        self.assertEqual(result["claimed_event_roots"], 2)
        self.assertEqual(len(result["shared_event_root_groups"]), 2)
        self.assertTrue(all(x["distinct_assets"] == 2 for x in
                            result["shared_event_root_groups"]))

    def test_reversed_pair_alias_is_not_canonical(self):
        result = self.run_audit([candidate("USD/EUR", "BAIXA")])
        self.assertEqual(result["state"], "LAB_EVENT_CONCENTRATION_BLOCKED")

    def test_duplicate_pair_horizon_denied(self):
        result = self.run_audit([candidate(), candidate()])
        self.assertEqual(result["reason"], "DUPLICATED_PAIR_HORIZON_IS_NOT_A_NEW_TRIAL")

    def test_d1_w1_disagreement_denied(self):
        result = self.run_audit([candidate(), candidate(side="BAIXA", horizon="W1")])
        self.assertEqual(result["reason"], "D1_W1_DIRECTION_CONFLICT_ABSTAIN")

    def test_future_factor_capture_denied(self):
        original = candidate()
        invalid = replace(original, factors=(replace(
            original.factors[0], captured_at_utc=AT + timedelta(seconds=1)),))
        result = self.run_audit([invalid])
        self.assertEqual(result["state"], "LAB_EVENT_CONCENTRATION_BLOCKED")

    def test_future_decision_denied(self):
        result = self.run_audit([candidate()], at=AT - timedelta(seconds=1))
        self.assertEqual(result["state"], "LAB_EVENT_CONCENTRATION_BLOCKED")

    def test_naive_datetime_denied(self):
        result = self.run_audit([candidate()], at=AT.replace(tzinfo=None))
        self.assertEqual(result["state"], "LAB_EVENT_CONCENTRATION_BLOCKED")

    def test_fractional_second_denied(self):
        result = self.run_audit([replace(candidate(),
                                         decision_at_utc=AT + timedelta(microseconds=1))])
        self.assertEqual(result["state"], "LAB_EVENT_CONCENTRATION_BLOCKED")

    def test_invalid_root_denied(self):
        result = self.run_audit([candidate(roots=("UNKNOWN",))])
        self.assertEqual(result["state"], "LAB_EVENT_CONCENTRATION_BLOCKED")

    def test_duplicate_factor_id_denied(self):
        original = candidate(roots=(PPI, "US_YIELD_REACTION"))
        factors = (original.factors[0], replace(
            original.factors[1], factor_id=original.factors[0].factor_id))
        result = self.run_audit([replace(original, factors=factors)])
        self.assertEqual(result["state"], "LAB_EVENT_CONCENTRATION_BLOCKED")

    def test_factor_direction_conflict_denied(self):
        original = candidate()
        bad = replace(original, factors=(replace(
            original.factors[0], relative_side="QUOTE_RELATIVE"),))
        result = self.run_audit([bad])
        self.assertEqual(result["state"], "LAB_EVENT_CONCENTRATION_BLOCKED")

    def test_only_neutral_factors_are_not_directional_support(self):
        original = candidate()
        bad = replace(original, factors=(replace(
            original.factors[0], relative_side="NEUTRAL"),))
        result = self.run_audit([bad])
        self.assertEqual(result["state"], "LAB_EVENT_CONCENTRATION_BLOCKED")

    def test_awaiting_is_not_an_active_candidate(self):
        result = self.run_audit([candidate(side="AGUARDAR")])
        self.assertEqual(result["state"], "LAB_EVENT_CONCENTRATION_BLOCKED")

    def test_empty_and_more_than_56_denied(self):
        self.assertEqual(self.run_audit([])["state"], "LAB_EVENT_CONCENTRATION_BLOCKED")
        self.assertEqual(self.run_audit([candidate()] * 57)["state"],
                         "LAB_EVENT_CONCENTRATION_BLOCKED")

    def test_wrong_input_types_denied(self):
        for items in (None, {}, [dict(asset="EUR/USD")]):
            with self.subTest(items=items):
                self.assertEqual(self.run_audit(items)["state"],
                                 "LAB_EVENT_CONCENTRATION_BLOCKED")


if __name__ == "__main__":
    unittest.main(verbosity=2)
