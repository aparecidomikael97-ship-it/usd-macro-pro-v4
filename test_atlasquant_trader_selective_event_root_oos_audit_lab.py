"""Synthetic selective OOS census: not evidence of Forex/index accuracy."""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
import unittest

from atlasquant_trader_selective_event_root_oos_audit_lab import (
    FrozenOpportunityManifest, ObservedOpportunity,
    audit_selective_event_roots_lab as audit, LABEL,
)

UTC = timezone.utc
FROZEN = datetime(2026, 1, 1, tzinfo=UTC)
NOW = datetime(2026, 11, 11, 20, tzinfo=UTC)


def case(*, count=7, root_id="PPI_US_20261113", hits=None, abstain=0):
    hits = count - abstain if hits is None else hits
    slots = tuple(f"SLOT_{i:05d}" for i in range(count))
    plan = FrozenOpportunityManifest("CAMPAIGN_OOS_01", "v1.0", FROZEN, slots)
    observations = []
    for i, name in enumerate(slots):
        decision = datetime(2026, 10, 1, tzinfo=UTC) + timedelta(minutes=i)
        issued = i < count - abstain
        observations.append(ObservedOpportunity(
            opportunity_id=name, asset="EUR/USD" if i % 2 == 0 else "USD/JPY",
            horizon="D1", event_root_id=(root_id or f"EVENT_{i:05d}"),
            decided_at_utc=decision,
            issued_direction="ALTA" if issued else "AGUARDAR",
            outcome_observed_at_utc=decision + timedelta(days=1) if issued else None,
            correct_direction=i < hits if issued else None,
            outcome_label=LABEL if issued else None,
        ))
    return plan, observations


class IndependentRootOosCensusTests(unittest.TestCase):
    def run_case(self, plan=None, rows=None, **kwargs):
        if plan is None and rows is None:
            plan, rows = case(**kwargs)
        return audit(frozen_manifest=plan, observations=rows, inspected_at_utc=NOW)

    def safe(self, report):
        self.assertEqual(report["operational_bias"], "AGUARDAR")
        self.assertFalse(report["publishable"])
        self.assertFalse(report["trade_authorized"])
        self.assertFalse(report["live_alert_allowed"])
        self.assertFalse(report["scheduler_enabled"])
        self.assertFalse(report["worker_enabled"])
        self.assertIsNone(report["validated_accuracy"])
        self.assertIsNone(report["calibrated_direction_probability"])
        self.assertIsNone(report["independent_event_trial_count_verified"])
        self.assertFalse(report["market_event_root_independence_verified"])
        self.assertFalse(report["genuine_forward_precommitment_independently_attested"])
        self.assertFalse(report["individual_issued_decisions_first_seen_externally_attested"])
        self.assertFalse(report["execution_costs_and_net_profit_verified"])
        self.assertEqual(report["http_requests"], 0)
        self.assertEqual(report["file_writes"], 0)
        self.assertEqual(report["new_cost_brl"], 0)

    def blocked(self, r, reason):
        self.assertEqual(r["state"], "LAB_EVENT_ROOT_OOS_ABSTAIN")
        self.assertEqual(r["reason"], reason)
        self.assertIsNone(r["signal_hit_rate_observed_unattested"])
        self.safe(r)

    def test_seven_simultaneous_usd_signals_are_one_claimed_event(self):
        r = self.run_case()
        self.assertEqual(r["issued_count"], 7)
        self.assertEqual(r["claimed_event_root_count_issued"], 1)
        self.assertEqual(r["signal_hit_rate_observed_unattested"], 1.0)
        self.assertFalse(r["claimed_root_threshold_reached"])
        self.assertEqual(r["reason"], "CLAIMED_ROOT_SAMPLE_TOO_SMALL_OR_BELOW_RESEARCH_GOAL")
        self.safe(r)

    def test_one_wrong_signal_makes_root_stress_test_fail(self):
        r = self.run_case(hits=6)
        self.assertAlmostEqual(r["signal_hit_rate_observed_unattested"], 6 / 7, places=6)
        self.assertEqual(r["event_root_all_issued_correct_rate_unattested"], 0.0)
        self.assertEqual(r["event_root_hit_count_all_issued_correct"], 0)
        self.safe(r)

    def test_hundred_perfect_caller_named_roots_still_no_go(self):
        r = self.run_case(root_id=None, count=100)
        self.assertEqual(r["claimed_event_root_count_issued"], 100)
        self.assertTrue(r["claimed_root_threshold_reached"])
        self.assertEqual(r["reason"], "ILLUSTRATIVE_ROOT_THRESHOLD_ONLY_INDEPENDENCE_UNVERIFIED")
        self.assertEqual(r["event_root_all_issued_correct_rate_unattested"], 1.0)
        self.assertGreater(r["illustrative_event_root_wilson95_lower_if_iid"], 0.8)
        self.safe(r)

    def test_100_signals_one_root_does_not_meet_100_event_threshold(self):
        r = self.run_case(count=100)
        self.assertEqual(r["claimed_event_root_count_issued"], 1)
        self.assertFalse(r["claimed_root_threshold_reached"])
        self.safe(r)

    def test_seventy_percent_rare_signal_selection_is_audited(self):
        r = self.run_case(count=10, abstain=3)
        self.assertEqual(r["expected_opportunities"], 10)
        self.assertEqual(r["accounted_opportunities"], 10)
        self.assertEqual(r["issued_count"], 7)
        self.assertEqual(r["abstained_count"], 3)
        self.assertEqual(r["issued_selection_rate_documentary"], 0.7)
        self.safe(r)

    def test_all_abstained_has_zero_claimed_accuracy(self):
        r = self.run_case(count=10, abstain=10, hits=0)
        self.assertEqual(r["state"], "LAB_EVENT_ROOT_OOS_ABSTAIN")
        self.assertEqual(r["issued_count"], 0)
        self.assertIsNone(r["signal_hit_rate_observed_unattested"])
        self.safe(r)

    def test_missing_or_extra_slot_blocks_without_partial_result(self):
        plan, rows = case()
        for corrupted in (rows[:-1], rows + [rows[-1]]):
            self.blocked(self.run_case(plan, corrupted), "MISSING_OR_EXTRA_PLANNED_OPPORTUNITIES")

    def test_duplicate_or_cherrypicked_id_rejected(self):
        plan, rows = case()
        rows[4] = replace(rows[4], opportunity_id=rows[0].opportunity_id)
        self.blocked(self.run_case(plan, rows), "INVALID_OUT_OF_ORDER_OR_UNFROZEN_OPPORTUNITY")

    def test_duplicate_manifest_ids_rejected(self):
        plan, rows = case()
        plan = replace(plan, expected_opportunity_ids=plan.expected_opportunity_ids[:-1]
                       + (plan.expected_opportunity_ids[0],))
        self.blocked(self.run_case(plan, rows), "INVALID_OR_DUPLICATE_FROZEN_OPPORTUNITY_PLAN")

    def test_late_precommit_fails(self):
        plan, rows = case()
        plan = replace(plan, frozen_at_utc=rows[0].decided_at_utc)
        self.blocked(self.run_case(plan, rows), "INVALID_OUT_OF_ORDER_OR_UNFROZEN_OPPORTUNITY")

    def test_future_prediction_cannot_be_counted(self):
        plan, rows = case()
        rows[0] = replace(rows[0], decided_at_utc=NOW + timedelta(seconds=1))
        self.blocked(self.run_case(plan, rows), "INVALID_OUT_OF_ORDER_OR_UNFROZEN_OPPORTUNITY")

    def test_future_outcome_cannot_be_counted(self):
        plan, rows = case()
        rows[-1] = replace(rows[-1], outcome_observed_at_utc=NOW + timedelta(seconds=1))
        self.blocked(self.run_case(plan, rows), "ISSUED_SIGNAL_HAS_MISSING_FUTURE_OR_BAD_LABEL")

    def test_missing_or_wrong_outcome_label_blocks(self):
        plan, rows = case()
        for label in (None, "CPI_SURPRISE", "IN_SAMPLE_HIT"):
            rows[0] = replace(rows[0], outcome_label=label)
            self.blocked(self.run_case(plan, rows), "ISSUED_SIGNAL_HAS_MISSING_FUTURE_OR_BAD_LABEL")

    def test_boolean_is_required_not_int_or_string(self):
        plan, rows = case()
        for val in (1, 0, "true", None):
            rows[0] = replace(rows[0], correct_direction=val)
            self.blocked(self.run_case(plan, rows), "ISSUED_SIGNAL_HAS_MISSING_FUTURE_OR_BAD_LABEL")

    def test_abstention_cannot_have_posthoc_success_label(self):
        plan, rows = case(count=7, abstain=1)
        rows[-1] = replace(rows[-1], correct_direction=True)
        self.blocked(self.run_case(plan, rows), "ABSTENTION_CANNOT_COUNT_AS_SCORED_SIGNAL")

    def test_relabelled_loss_to_abstention_is_not_external_proof(self):
        # A caller may dishonestly change a losing issued signal into AGUARDAR.
        # This cannot be detected without a timestamped issuance receipt.
        plan, rows = case(hits=6)
        original = self.run_case(plan, rows)
        self.assertAlmostEqual(original["signal_hit_rate_observed_unattested"], 6 / 7, places=6)
        rows[-1] = replace(
            rows[-1], issued_direction="AGUARDAR", correct_direction=None,
            outcome_observed_at_utc=None, outcome_label=None)
        revised = self.run_case(plan, rows)
        self.assertEqual(revised["signal_hit_rate_observed_unattested"], 1.0)
        self.assertFalse(revised["individual_issued_decisions_first_seen_externally_attested"])
        self.assertIsNone(revised["validated_accuracy"])
        self.safe(revised)

    def test_reversed_time_order_blocks(self):
        plan, rows = case()
        rows[3] = replace(rows[3], decided_at_utc=rows[2].decided_at_utc-timedelta(seconds=1))
        self.blocked(self.run_case(plan, rows), "INVALID_OUT_OF_ORDER_OR_UNFROZEN_OPPORTUNITY")

    def test_invalid_asset_horizon_or_direction_blocks(self):
        plan, rows = case()
        for field, bad in (("asset", "BTC/USDT"), ("horizon", "M5"),
                           ("issued_direction", "COMPRAR"), ("event_root_id", "")):
            with self.subTest(field=field):
                changed = list(rows)
                changed[0] = replace(rows[0], **{field: bad})
                self.blocked(self.run_case(plan, changed), "INVALID_OUT_OF_ORDER_OR_UNFROZEN_OPPORTUNITY")

    def test_index_and_gold_slots_are_valid_but_never_live(self):
        plan, rows = case(count=3)
        rows[0] = replace(rows[0], asset="WIN")
        rows[1] = replace(rows[1], asset="NAS100")
        rows[2] = replace(rows[2], asset="METAL:XAUUSD")
        r = self.run_case(plan, rows)
        self.assertEqual(r["issued_count"], 3)
        self.safe(r)

    def test_bad_clock_and_non_manifest_are_rejected(self):
        plan, rows = case()
        r = audit(frozen_manifest=plan, observations=rows,
                  inspected_at_utc=NOW.replace(tzinfo=None))
        self.blocked(r, "INVALID_MANIFEST_OBSERVATIONS_OR_INSPECTION_CLOCK")
        self.blocked(self.run_case(plan=None, rows=rows),
                     "INVALID_MANIFEST_OBSERVATIONS_OR_INSPECTION_CLOCK")


if __name__ == "__main__":
    unittest.main()
