"""Synthetic-only Motor A missing-news confounder quarantine regression tests.

A release may be individually timestamp-valid yet its Forex reaction has
an UNKNOWN competing release. Such cohorts cannot be promoted into a
training or holdout sample. A common unresolved root across far-apart
events forms ONE dependency group before the chronological split.
No real macro calendar, Pepperstone price or forecast is present.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import timedelta, timezone
import unittest

from atlasquant_trader_fx28_macro_oos_event_cluster_ledger_lab import (
    audit_historical_macro_event_cohorts_lab as audit,
)
import test_atlasquant_trader_fx28_macro_oos_event_cluster_ledger_lab as fx

EXT_A="CAD_EXTERNAL_EVENT_UNKNOWN"
EXT_B="US_EXTERNAL_EVENT_UNKNOWN"
UNKNOWN="QUARANTINED_UNRESOLVED_COMPETING_RELEASE_NO_GO"
GOOD="LAB_MOTOR_A_MACRO_EVENT_CLUSTER_LEDGER_RECONCILED_NO_GO"
BAD="LAB_MOTOR_A_EVENT_COHORT_LEDGER_BLOCKED_NO_GO"


def event(root="US_PPI_OCT2026_MOCK", *, offset=0, currency="USD",
          depends=()):
    return fx.event(root,currency=currency,
                    release=fx.START+timedelta(days=offset),
                    competing_release_roots=depends)


def inspect(events):
    return audit(
        event_claims=events,
        inspected_at_utc=fx.NOW,
        holdout_begins_at_utc=fx.SPLIT,
    )


class QuarantineUnknownMacroConfounderTests(unittest.TestCase):
    def safe(self,report):
        self.assertFalse(report["trade_authorized"])
        self.assertFalse(report["publishable"])
        self.assertFalse(report["can_train_calibrated_model"])
        self.assertFalse(report["all_release_confounders_discovered"])
        self.assertFalse(report["historical_broker_prices_independently_authenticated"])
        self.assertIsNone(report["out_of_sample_accuracy"])
        self.assertIsNone(report["calibrated_probability"])
        self.assertIsNone(report["predicted_currency_direction"])
        self.assertEqual(report["operational_bias"],"AGUARDAR")
        self.assertTrue(report["no_hindsight_scoring"])
        self.assertTrue(report["cross_pairs_not_independent_economic_samples"])
        self.assertTrue(report["no_change_to_frozen_672_slot_campaign"])
        self.assertEqual((report["http_requests"],report["mt5_calls"],
                          report["file_writes"],report["new_cost_brl"]),(0,0,0,0))
        for cluster in report["clusters"]:
            self.assertFalse(cluster["can_count_as_authenticated_trial"])
            self.assertFalse(cluster["forecasts_can_be_scored"])

    def reconciled(self,events):
        result=inspect(events)
        self.safe(result)
        self.assertEqual(result["state"],GOOD)
        self.assertEqual(
            result["untrusted_total_cluster_count"],
            result["untrusted_candidate_cluster_count"] +
            result["quarantined_unresolved_confounder_cluster_count"])
        return result

    def test_01_single_train_event_with_missing_news_is_quarantined_not_train(self):
        r=self.reconciled([event(depends=(EXT_A,))])
        self.assertEqual(r["untrusted_event_roots_checked"],1)
        self.assertEqual(r["untrusted_metric_rows_checked"],2)
        self.assertEqual(r["untrusted_fx_pair_observations_checked"],7)
        self.assertEqual(r["untrusted_total_cluster_count"],1)
        self.assertEqual(r["untrusted_candidate_cluster_count"],0)
        self.assertEqual(r["quarantined_unresolved_confounder_cluster_count"],1)
        self.assertEqual(r["candidate_train_cluster_count"],0)
        self.assertEqual(r["candidate_holdout_cluster_count"],0)
        self.assertEqual(r["candidate_purged_boundary_cluster_count"],0)
        self.assertEqual(r["clusters"][0]["partition"],UNKNOWN)
        self.assertEqual(r["clusters"][0]["other_macro_releases_not_locally_resolved"],
                         [EXT_A])

    def test_02_single_holdout_event_with_missing_news_not_holdout(self):
        r=self.reconciled([event("US_CPI_LATER_MOCK",offset=20,depends=(EXT_A,))])
        self.assertEqual(r["candidate_holdout_cluster_count"],0)
        self.assertEqual(r["clusters"][0]["partition"],UNKNOWN)

    def test_03_two_distant_events_sharing_same_unknown_news_join_before_split(self):
        a=event(depends=(EXT_A,))
        b=event("US_CPI_LATER_MOCK",offset=20,depends=(EXT_A,))
        r=self.reconciled([a,b])
        self.assertEqual(r["untrusted_event_roots_checked"],2)
        self.assertEqual(r["untrusted_total_cluster_count"],1)
        self.assertEqual(r["unresolved_competing_release_root_count"],1)
        self.assertEqual(r["quarantined_unresolved_confounder_cluster_count"],1)
        self.assertEqual(r["candidate_train_cluster_count"],0)
        self.assertEqual(r["candidate_holdout_cluster_count"],0)
        self.assertEqual(r["clusters"][0]["event_roots_count"],2)
        self.assertEqual(r["clusters"][0]["partition"],UNKNOWN)
        self.assertEqual(r["clusters"][0]["other_macro_releases_not_locally_resolved"],
                         [EXT_A])

    def test_04_input_order_cannot_remove_shared_unknown_dependency(self):
        a=event(depends=(EXT_A,))
        b=event("US_CPI_LATER_MOCK",offset=20,depends=(EXT_A,))
        self.assertEqual(self.reconciled([a,b]),self.reconciled([b,a]))

    def test_05_two_unknown_roots_shared_transitively_join_three_events(self):
        a=event(depends=(EXT_A,))
        b=event("CAD_SECOND_MOCK",offset=10,currency="CAD",
                depends=(EXT_A,EXT_B))
        c=event("USD_THIRD_MOCK",offset=20,depends=(EXT_B,))
        r=self.reconciled([a,c,b])
        self.assertEqual(r["untrusted_total_cluster_count"],1)
        self.assertEqual(r["unresolved_competing_release_root_count"],2)
        self.assertEqual(r["clusters"][0]["event_roots_count"],3)
        self.assertEqual(r["clusters"][0]["other_macro_releases_not_locally_resolved"],
                         sorted([EXT_A,EXT_B]))
        self.assertEqual(r["clusters"][0]["partition"],UNKNOWN)

    def test_06_distinct_unknown_roots_do_not_falsely_join(self):
        a=event(depends=(EXT_A,))
        b=event("US_CPI_LATER_MOCK",offset=20,depends=(EXT_B,))
        r=self.reconciled([a,b])
        self.assertEqual(r["untrusted_total_cluster_count"],2)
        self.assertEqual(r["quarantined_unresolved_confounder_cluster_count"],2)
        self.assertEqual(r["untrusted_candidate_cluster_count"],0)
        self.assertEqual([x["partition"] for x in r["clusters"]],[UNKNOWN,UNKNOWN])

    def test_07_resolved_competing_root_groups_without_unknown_quarantine(self):
        b_root="CAD_MANUFACTURING_RESOLVED_MOCK"
        a=event(depends=(b_root,))
        b=event(b_root,offset=20,currency="CAD")
        r=self.reconciled([a,b])
        self.assertEqual(r["unresolved_competing_release_root_count"],0)
        self.assertEqual(r["quarantined_unresolved_confounder_cluster_count"],0)
        self.assertEqual(r["untrusted_total_cluster_count"],1)
        self.assertEqual(r["untrusted_candidate_cluster_count"],1)
        self.assertEqual(r["clusters"][0]["partition"],
                         "PURGED_AROUND_HOLDOUT_BOUNDARY")
        self.assertFalse(r["clusters"][0]["forecasts_can_be_scored"])

    def test_08_unconfounded_training_can_remain_candidate_unknown_holdout_quarantined(self):
        a=event()
        b=event("US_CPI_LATER_MOCK",offset=20,depends=(EXT_A,))
        r=self.reconciled([a,b])
        self.assertEqual(r["untrusted_total_cluster_count"],2)
        self.assertEqual(r["untrusted_candidate_cluster_count"],1)
        self.assertEqual(r["candidate_train_cluster_count"],1)
        self.assertEqual(r["candidate_holdout_cluster_count"],0)
        self.assertEqual(r["quarantined_unresolved_confounder_cluster_count"],1)
        self.assertEqual([x["partition"] for x in r["clusters"]],
                         ["CANDIDATE_TRAIN_UNATTESTED",UNKNOWN])

    def test_09_overlap_with_unknown_quarantines_entire_macro_release_cluster(self):
        a=event()
        b=event("CAD_SAME_MINUTE_MOCK",currency="CAD",depends=(EXT_A,))
        r=self.reconciled([a,b])
        self.assertEqual(r["untrusted_total_cluster_count"],1)
        self.assertEqual(r["quarantined_unresolved_confounder_cluster_count"],1)
        self.assertEqual(r["candidate_train_cluster_count"],0)
        self.assertEqual(r["clusters"][0]["event_roots_count"],2)

    def test_10_multiple_macroeconomic_metrics_and_seven_pairs_not_extra_trials(self):
        a=event(depends=(EXT_A,))
        r=self.reconciled([a])
        self.assertEqual(r["untrusted_metric_rows_checked"],2)
        self.assertEqual(r["untrusted_fx_pair_observations_checked"],7)
        self.assertEqual(r["untrusted_candidate_cluster_count"],0)
        self.assertFalse(r["forecasts_not_retrospectively_fabricated"])

    def test_11_unknown_confounder_even_with_fake_up_forecast_not_a_trial(self):
        a=event(depends=(EXT_A,))
        a=replace(a,pre_event_forecast_direction="UP",
                  pre_event_forecast_issued_at_utc=fx.START-timedelta(hours=1))
        r=self.reconciled([a])
        self.assertEqual(r["clusters"][0]["partition"],UNKNOWN)
        self.assertFalse(r["clusters"][0]["forecasts_can_be_scored"])

    def test_12_duplicate_external_confounder_ids_still_fail_closed(self):
        a=event(depends=(EXT_A,EXT_A))
        r=inspect([a])
        self.safe(r)
        self.assertEqual(r["state"],BAD)
        self.assertEqual(r["untrusted_total_cluster_count"],0)

    def test_13_empty_roster_is_not_a_zero_miss_success_rate(self):
        r=inspect([])
        self.safe(r)
        self.assertEqual(r["state"],"LAB_MOTOR_A_NO_HISTORICAL_EVENT_CLAIMS_NO_GO")
        self.assertEqual(r["untrusted_total_cluster_count"],0)
        self.assertIsNone(r["out_of_sample_accuracy"])

    def test_14_a_second_root_in_cuiaba_keeps_same_grouping(self):
        a=event(depends=(EXT_A,))
        b=event("US_CPI_LATER_MOCK",offset=20,depends=(EXT_A,))
        cuiaba=timezone(timedelta(hours=-4))
        b_local=replace(b,
            scheduled_release_at_utc=b.scheduled_release_at_utc.astimezone(cuiaba),
            consensus_locally_captured_at_utc=b.consensus_locally_captured_at_utc.astimezone(cuiaba),
            actual_locally_captured_at_utc=b.actual_locally_captured_at_utc.astimezone(cuiaba),
            price_locally_captured_at_utc=b.price_locally_captured_at_utc.astimezone(cuiaba),
        )
        self.assertEqual(self.reconciled([a,b]),self.reconciled([a,b_local]))

    def test_15_holdout_only_with_clean_events_preserves_candidate_labels(self):
        a=event("US_CPI_LATER_MOCK",offset=20)
        r=self.reconciled([a])
        self.assertEqual(r["unresolved_competing_release_root_count"],0)
        self.assertEqual(r["candidate_holdout_cluster_count"],1)
        self.assertEqual(r["untrusted_candidate_cluster_count"],1)
        self.assertEqual(r["clusters"][0]["partition"],
                         "CANDIDATE_HOLDOUT_UNATTESTED")
        self.assertFalse(r["clusters"][0]["forecasts_can_be_scored"])


if __name__=="__main__":
    unittest.main()
