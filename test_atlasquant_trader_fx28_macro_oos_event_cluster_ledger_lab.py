"""Synthetic-only QA for Motor A event clustering and time-split embargo.

Test inputs are invented. No actual macro forecasts, downloaded originals,
broker candles, outcomes or historical returns are asserted.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime,timedelta,timezone
from hashlib import sha256
import unittest

from atlasquant_fx_universe import OFFICIAL_PAIRS,split_pair
from atlasquant_trader_fx28_macro_oos_event_cluster_ledger_lab import (
    SCHEMA,MacroEventCohortClaim,
    audit_historical_macro_event_cohorts_lab as audit,
)
UTC=timezone.utc
START=datetime(2026,10,1,13,30,tzinfo=UTC)
NOW=datetime(2026,11,15,13,0,tzinfo=UTC)
SPLIT=datetime(2026,10,15,13,30,tzinfo=UTC)


def sha(*items):
    return sha256(("FAKE RESEARCH FILE "+" : ".join(str(x) for x in items)).encode()).hexdigest()


def event(root="US_PPI_OCT2026_MOCK",*,currency="USD",release=START,
          metrics=("US_PPI_FINAL_DEMAND_MOM","US_PPI_CORE_MOM"),
          **overrides):
    base=MacroEventCohortClaim(
        root_id=root,
        issuer_currency=currency,
        scheduled_release_at_utc=release,
        consensus_locally_captured_at_utc=release-timedelta(days=1),
        actual_locally_captured_at_utc=release+timedelta(minutes=3),
        price_locally_captured_at_utc=release+timedelta(hours=5),
        metric_ids=metrics,
        price_pairs=tuple(p for p in OFFICIAL_PAIRS if currency in split_pair(p)),
        horizons=("M15","H1","H4"),
        consensus_original_sha256_claim=sha("CONSENSUS",root),
        actual_original_sha256_claim=sha("ACTUAL",root),
        price_archive_sha256_claim=sha("PRICES",root),
        pre_event_forecast_direction="ABSTAIN",
        pre_event_forecast_issued_at_utc=None,
        competing_release_roots=(),
    )
    return replace(base,**overrides)


class MotorAHistoricalEventCohortTests(unittest.TestCase):
    def run_cohorts(self,events=None,asof=NOW,split=SPLIT):
        r=audit(event_claims=[event()] if events is None else events,
                inspected_at_utc=asof,holdout_begins_at_utc=split)
        self.assertEqual(r["schema"],SCHEMA)
        self.assertEqual(r["operational_bias"],"AGUARDAR")
        self.assertIsNone(r["predicted_currency_direction"])
        self.assertIsNone(r["calibrated_probability"])
        self.assertIsNone(r["out_of_sample_accuracy"])
        self.assertFalse(r["trade_authorized"])
        self.assertFalse(r["publishable"])
        self.assertFalse(r["all_event_times_and_origins_independently_authenticated"])
        self.assertFalse(r["all_pre_event_consensus_vintages_independently_authenticated"])
        self.assertFalse(r["historical_broker_prices_independently_authenticated"])
        self.assertTrue(r["cross_pairs_not_independent_economic_samples"])
        self.assertTrue(r["no_hindsight_scoring"])
        self.assertTrue(r["no_change_to_frozen_672_slot_campaign"])
        self.assertEqual((r["http_requests"],r["mt5_calls"],r["file_writes"]),(0,0,0))
        self.assertEqual(r["new_cost_brl"],0)
        self.assertFalse(r["can_train_calibrated_model"])
        return r

    def blocked(self,events,**kw):
        r=self.run_cohorts(events,**kw)
        self.assertEqual(r["state"],"LAB_MOTOR_A_EVENT_COHORT_LEDGER_BLOCKED_NO_GO")
        self.assertEqual(r["untrusted_candidate_cluster_count"],0)
        return r

    def test_01_two_ppi_metrics_seven_fx_are_one_event_not_fourteen_trials(self):
        r=self.run_cohorts()
        self.assertEqual(r["state"],"LAB_MOTOR_A_MACRO_EVENT_CLUSTER_LEDGER_RECONCILED_NO_GO")
        self.assertEqual(r["untrusted_event_roots_checked"],1)
        self.assertEqual(r["untrusted_metric_rows_checked"],2)
        self.assertEqual(r["untrusted_fx_pair_observations_checked"],7)
        self.assertEqual(r["untrusted_candidate_cluster_count"],1)
        self.assertEqual(r["candidate_train_cluster_count"],1)
        self.assertEqual(r["candidate_holdout_cluster_count"],0)
        self.assertFalse(r["clusters"][0]["forecasts_can_be_scored"])

    def test_02_same_release_minute_usd_and_cad_is_one_macro_cluster(self):
        a=event()
        b=event("CAD_MANUFACTURING_SALES_MOCK",currency="CAD",
                metrics=("CAD_MANUFACTURING_SALES_MOM",))
        r=self.run_cohorts([a,b])
        self.assertEqual(r["untrusted_event_roots_checked"],2)
        self.assertEqual(r["untrusted_metric_rows_checked"],3)
        self.assertEqual(r["untrusted_fx_pair_observations_checked"],14)
        self.assertEqual(r["untrusted_candidate_cluster_count"],1)
        self.assertEqual(r["clusters"][0]["event_roots_count"],2)

    def test_03_two_hours_apart_same_h4_window_clump_as_one(self):
        a=event()
        b=event("US_LABOR_MOCK",release=START+timedelta(hours=2),
                metrics=("US_NONFARM_PAYROLL_CHANGE",))
        r=self.run_cohorts([a,b])
        self.assertEqual(r["untrusted_candidate_cluster_count"],1)

    def test_04_three_transitively_linked_overlapping_events_are_one(self):
        a=event()
        b=event("US_JOBLESS_CLAIMS_MOCK",release=START+timedelta(hours=3))
        c=event("US_ACTIVITY_ISM_MOCK",release=START+timedelta(hours=6))
        r=self.run_cohorts([a,b,c])
        self.assertEqual(r["untrusted_candidate_cluster_count"],1)
        self.assertEqual(r["clusters"][0]["event_roots_count"],3)

    def test_05_two_separate_days_are_two_candidate_clusters(self):
        a=event()
        b=event("US_CPI_NOV2026_MOCK",release=START+timedelta(days=20))
        r=self.run_cohorts([a,b])
        self.assertEqual(r["untrusted_candidate_cluster_count"],2)
        self.assertEqual(r["candidate_train_cluster_count"],1)
        self.assertEqual(r["candidate_holdout_cluster_count"],1)
        self.assertEqual(r["candidate_purged_boundary_cluster_count"],0)

    def test_06_same_consensus_bulletin_is_shared_context_not_two_independent(self):
        a=event()
        b=event("US_CPI_NOV2026_MOCK",release=START+timedelta(days=20),
                consensus_original_sha256_claim=a.consensus_original_sha256_claim)
        r=self.run_cohorts([a,b])
        self.assertEqual(r["untrusted_candidate_cluster_count"],1)
        self.assertEqual(r["candidate_purged_boundary_cluster_count"],1)
        self.assertEqual(r["candidate_train_cluster_count"],0)
        self.assertEqual(r["candidate_holdout_cluster_count"],0)

    def test_07_same_first_print_bytes_under_another_root_is_blocked(self):
        a=event()
        b=event("US_FAKE_SECOND_ROOT",release=START+timedelta(days=20),
                actual_original_sha256_claim=a.actual_original_sha256_claim)
        r=self.blocked([a,b])
        self.assertEqual(r["reason"],"SAME_ACTUAL_BYTES_RELABELED_AS_SECOND_ECONOMIC_EVENT")

    def test_08_bad_or_missing_sha_never_counts_as_original(self):
        self.blocked([event(consensus_original_sha256_claim="0"*63)])
        self.blocked([event(price_archive_sha256_claim="FAKE")])

    def test_09_missing_one_price_pair_blocks(self):
        a=event()
        r=self.blocked([replace(a,price_pairs=a.price_pairs[:-1])])
        self.assertEqual(r["reason"],"INCOMPLETE_NONCANONICAL_SEVEN_CROSS_FX_COHORT")

    def test_10_duplicate_pair_or_reversed_order_blocks(self):
        a=event()
        self.blocked([replace(a,price_pairs=a.price_pairs[:-1]+(a.price_pairs[0],))])
        self.blocked([replace(a,price_pairs=tuple(reversed(a.price_pairs)))])

    def test_11_invalid_metric_id_or_mixed_unit_not_admitted(self):
        self.blocked([event(metrics=("US_PPI_MOM","bad_untrusted_unit"))])
        self.blocked([event(metrics=("nan",))])

    def test_12_duplicate_metric_is_not_second_economic_observation(self):
        self.blocked([event(metrics=("US_PPI_MOM","US_PPI_MOM"))])

    def test_13_duplicate_event_root_cannot_increase_sample(self):
        self.blocked([event(),event()])

    def test_14_late_forecast_cannot_be_backfilled(self):
        a=event(pre_event_forecast_direction="UP",
                pre_event_forecast_issued_at_utc=START+timedelta(seconds=1))
        r=self.blocked([a])
        self.assertEqual(r["reason"],"MISSING_LATE_OR_REWRITTEN_PRE_EVENT_FORECAST")

    def test_15_pre_event_issued_within_twelve_hours_remains_unattested(self):
        a=event(pre_event_forecast_direction="UP",
                pre_event_forecast_issued_at_utc=START-timedelta(hours=2))
        r=self.run_cohorts([a])
        self.assertEqual(r["untrusted_candidate_cluster_count"],1)
        self.assertFalse(r["clusters"][0]["forecasts_can_be_scored"])
        self.assertFalse(r["forecasts_not_retrospectively_fabricated"])

    def test_16_abstain_with_fake_issue_time_rejected(self):
        a=event(pre_event_forecast_direction="ABSTAIN",
                pre_event_forecast_issued_at_utc=START-timedelta(minutes=5))
        self.blocked([a])

    def test_17_price_capture_before_h4_close_is_invalid(self):
        a=event(price_locally_captured_at_utc=START+timedelta(hours=3))
        self.blocked([a])

    def test_18_unknown_competing_root_is_not_marked_no_other_news(self):
        a=event(competing_release_roots=("CAD_MANUFACTURING_SEP_MOCK",))
        r=self.run_cohorts([a])
        self.assertEqual(r["clusters"][0]["other_macro_releases_not_locally_resolved"],
                         ["CAD_MANUFACTURING_SEP_MOCK"])
        self.assertFalse(r["all_release_confounders_discovered"])

    def test_19_explicit_confounded_event_roots_group_across_dates(self):
        a=event(competing_release_roots=("CAD_MANUFACTURING_SEP_MOCK",))
        b=event("CAD_MANUFACTURING_SEP_MOCK",currency="CAD",
                release=START+timedelta(days=20))
        r=self.run_cohorts([a,b])
        self.assertEqual(r["untrusted_candidate_cluster_count"],1)
        self.assertEqual(r["candidate_purged_boundary_cluster_count"],1)
        self.assertEqual(r["clusters"][0]["other_macro_releases_not_locally_resolved"],[])

    def test_20_event_window_straddles_train_holdout_cut_is_purged(self):
        boundary=event("US_CPI_ON_CUTOFF_MOCK",release=SPLIT)
        r=self.run_cohorts([boundary])
        self.assertEqual(r["candidate_purged_boundary_cluster_count"],1)
        self.assertEqual(r["candidate_train_cluster_count"],0)
        self.assertEqual(r["candidate_holdout_cluster_count"],0)

    def test_21_input_order_does_not_change_cohort_partition(self):
        a=event()
        b=event("CAD_MANUFACTURING_SALES_MOCK",currency="CAD")
        c=event("US_CPI_NOV2026_MOCK",release=START+timedelta(days=20))
        self.assertEqual(self.run_cohorts([a,b,c]),
                         self.run_cohorts([c,b,a]))

    def test_22_naive_asof_and_split_are_blocked(self):
        self.blocked([event()],asof=NOW.replace(tzinfo=None))
        self.blocked([event()],split=SPLIT.replace(tzinfo=None))

    def test_23_future_broker_capture_cannot_label_past_window(self):
        self.blocked([event(price_locally_captured_at_utc=NOW+timedelta(minutes=1))])

    def test_24_cuiaba_timezone_matches_utc(self):
        cuiaba=timezone(timedelta(hours=-4))
        a=event(
            scheduled_release_at_utc=START.astimezone(cuiaba),
            consensus_locally_captured_at_utc=(START-timedelta(days=1)).astimezone(cuiaba),
            actual_locally_captured_at_utc=(START+timedelta(minutes=3)).astimezone(cuiaba),
            price_locally_captured_at_utc=(START+timedelta(hours=5)).astimezone(cuiaba),
        )
        self.assertEqual(self.run_cohorts([a],asof=NOW.astimezone(cuiaba),
                           split=SPLIT.astimezone(cuiaba)),
                         self.run_cohorts([event()]))

    def test_25_empty_roster_is_not_zero_failures_or_perfect_score(self):
        r=self.run_cohorts([])
        self.assertEqual(r["state"],"LAB_MOTOR_A_NO_HISTORICAL_EVENT_CLAIMS_NO_GO")
        self.assertEqual(r["untrusted_event_roots_checked"],0)
        self.assertIsNone(r["out_of_sample_accuracy"])

    def test_26_impossible_claim_type_rejected(self):
        self.blocked([{"root_id":"US_PPI_OCT2026_MOCK"}])
        self.blocked([None])

    def test_27_wrong_price_horizons_or_different_collection_clock_rejected(self):
        self.blocked([event(horizons=("M15","H1"))])
        self.blocked([event(price_locally_captured_at_utc=START-timedelta(seconds=1))])

    def test_28_missing_custody_never_converts_to_profitable_strategy(self):
        a=event()
        b=event("US_CPI_NOV2026_MOCK",release=START+timedelta(days=20))
        r=self.run_cohorts([a,b])
        self.assertFalse(r["can_train_calibrated_model"])
        self.assertIsNone(r["out_of_sample_accuracy"])
        self.assertIsNone(r["calibrated_probability"])
        self.assertFalse(any(x["can_count_as_authenticated_trial"] for x in r["clusters"]))

    def test_29_future_only_holdout_split_rejected(self):
        self.blocked([event()],split=NOW+timedelta(days=1))

    def test_30_large_untrusted_file_list_rejected_without_work(self):
        self.blocked([event() for _ in range(513)])

if __name__=="__main__":
    unittest.main(verbosity=2)
