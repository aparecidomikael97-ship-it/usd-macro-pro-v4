"""Synthetic-only pre-event forecast cutoff and frozen December ABSTAIN tests.

All prices, SHA claims and forecasts in this test file are INVENTED.
The real December CPI/PPI research protocol has ZERO directional forecasts
and is pre-registered to ABSTAIN at both events. The historical ledger
must never manufacture a real forecast from caller-provided timestamps.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
import unittest

from atlasquant_trader_fx28_macro_oos_event_cluster_ledger_lab import (
    audit_historical_macro_event_cohorts_lab as audit,
)
from atlasquant_trader_us_dec2026_frozen_evaluation_protocol_lab import (
    FROZEN_PLAN,PINNED_PLAN_SHA256,canonical_frozen_plan_bytes_lab,
)
from hashlib import sha256
import test_atlasquant_trader_fx28_macro_oos_event_cluster_ledger_lab as fx

UTC=timezone.utc
CPI="US_CPI_NOV2026"
PPI="US_PPI_NOV2026"
UPROOT="US_PPI_OCT2026_MOCK"
RELEASE={
    CPI:datetime(2026,12,10,13,30,tzinfo=UTC),
    PPI:datetime(2026,12,15,13,30,tzinfo=UTC),
}
NOW=datetime(2026,12,20,15,0,tzinfo=UTC)
SPLIT=datetime(2026,12,13,13,30,tzinfo=UTC)
BLOCK="LAB_MOTOR_A_EVENT_COHORT_LEDGER_BLOCKED_NO_GO"
OK="LAB_MOTOR_A_MACRO_EVENT_CLUSTER_LEDGER_RECONCILED_NO_GO"


def fixed(root=CPI,**overrides):
    metrics=(("US_CPI_ALL_ITEMS_MOM","US_CPI_CORE_MOM")
             if root==CPI else
             ("US_PPI_FINAL_DEMAND_MOM","US_PPI_CORE_MOM"))
    base=fx.event(root,release=RELEASE[root],metrics=metrics)
    return replace(base,**overrides)


def generic(direction="UP",minutes=60,*,release=fx.START,
            root=UPROOT,**overrides):
    return fx.event(
        root,release=release,
        pre_event_forecast_direction=direction,
        pre_event_forecast_issued_at_utc=release-timedelta(minutes=minutes),
        **overrides,
    )


def check(records):
    return audit(event_claims=records,inspected_at_utc=NOW,
                 holdout_begins_at_utc=SPLIT)


class FrozenDecemberNoRetrospectivePredictionTests(unittest.TestCase):
    def safe(self,result):
        self.assertFalse(result["trade_authorized"])
        self.assertFalse(result["publishable"])
        self.assertFalse(result["can_train_calibrated_model"])
        self.assertFalse(result["all_event_times_and_origins_independently_authenticated"])
        self.assertFalse(result["forecasts_not_retrospectively_fabricated"])
        self.assertIsNone(result["predicted_currency_direction"])
        self.assertIsNone(result["calibrated_probability"])
        self.assertIsNone(result["out_of_sample_accuracy"])
        self.assertTrue(result["cross_pairs_not_independent_economic_samples"])
        self.assertEqual(result["directional_forecast_freeze_before_release_minutes"],60)
        self.assertTrue(result["no_change_to_frozen_672_slot_campaign"])
        self.assertEqual((result["http_requests"],result["mt5_calls"],
                          result["file_writes"],result["new_cost_brl"]),(0,0,0,0))
        self.assertTrue(all(not e["can_count_as_authenticated_trial"]
                            and not e["forecasts_can_be_scored"]
                            for e in result["clusters"]))

    def success(self,records):
        r=check(records)
        self.safe(r)
        self.assertEqual(r["state"],OK,r["reason"])
        self.assertTrue(r["frozen_dec2026_abstain_rule_verified_claim_only"])
        self.assertEqual(
            r["untrusted_event_roots_checked"],
            r["untrusted_abstention_event_roots_checked"] +
            r["untrusted_directional_forecast_claims_checked"])
        self.assertEqual(r["untrusted_candidate_cluster_count"] +
                         r["quarantined_unresolved_confounder_cluster_count"],
                         r["untrusted_total_cluster_count"])
        return r

    def reject(self,records,reason):
        r=check(records)
        self.safe(r)
        self.assertEqual(r["state"],BLOCK)
        self.assertEqual(r["reason"],reason)
        self.assertEqual(r["untrusted_event_roots_checked"],0)
        self.assertEqual(r["untrusted_candidate_cluster_count"],0)
        self.assertFalse(r["frozen_dec2026_abstain_rule_verified_claim_only"])
        return r

    def test_01_locked_plan_sha_and_both_events_explicitly_abstain(self):
        blob=canonical_frozen_plan_bytes_lab(FROZEN_PLAN)
        self.assertEqual(sha256(blob).hexdigest(),PINNED_PLAN_SHA256)
        self.assertEqual(FROZEN_PLAN["registered_forecasts"],0)
        self.assertEqual([x["forecast_direction"] for x in
                          FROZEN_PLAN["event_roots"]],["ABSTAIN","ABSTAIN"])

    def test_02_cpi_correct_clock_and_abstention_retained_denominator(self):
        r=self.success([fixed(CPI)])
        self.assertEqual(r["untrusted_abstention_event_roots_checked"],1)
        self.assertEqual(r["untrusted_directional_forecast_claims_checked"],0)
        self.assertEqual(r["frozen_dec2026_event_roots_seen"],[CPI])
        self.assertEqual(r["untrusted_candidate_cluster_count"],1)

    def test_03_ppi_correct_clock_and_abstention_retained_denominator(self):
        r=self.success([fixed(PPI)])
        self.assertEqual(r["frozen_dec2026_event_roots_seen"],[PPI])

    def test_04_two_december_events_are_two_abstentions_no_accuracy(self):
        r=self.success([fixed(CPI),fixed(PPI)])
        self.assertEqual(r["untrusted_event_roots_checked"],2)
        self.assertEqual(r["untrusted_abstention_event_roots_checked"],2)
        self.assertEqual(r["untrusted_directional_forecast_claims_checked"],0)
        self.assertEqual(r["frozen_dec2026_event_roots_seen"],[CPI,PPI])
        self.assertEqual(r["untrusted_candidate_cluster_count"],2)
        self.assertEqual(r["candidate_train_cluster_count"],1)
        self.assertEqual(r["candidate_holdout_cluster_count"],1)
        self.assertFalse(any(c["forecasts_can_be_scored"] for c in r["clusters"]))

    def test_05_cpi_up_forecast_even_pre_release_is_frozen_override(self):
        self.reject([fixed(CPI,
            pre_event_forecast_direction="UP",
            pre_event_forecast_issued_at_utc=RELEASE[CPI]-timedelta(hours=2))],
            "FROZEN_DEC2026_EVENT_ABSTAIN_OR_CLOCK_OVERRIDE")

    def test_06_ppi_down_forecast_even_pre_release_is_frozen_override(self):
        self.reject([fixed(PPI,
            pre_event_forecast_direction="DOWN",
            pre_event_forecast_issued_at_utc=RELEASE[PPI]-timedelta(hours=8))],
            "FROZEN_DEC2026_EVENT_ABSTAIN_OR_CLOCK_OVERRIDE")

    def test_07_cpi_up_one_minute_before_is_never_a_forecast(self):
        self.reject([fixed(CPI,
            pre_event_forecast_direction="UP",
            pre_event_forecast_issued_at_utc=RELEASE[CPI]-timedelta(minutes=1))],
            "FROZEN_DEC2026_EVENT_ABSTAIN_OR_CLOCK_OVERRIDE")

    def test_08_ppi_wrong_release_date_cannot_shift_frozen_plan(self):
        # The generic actual-before-release PIT gate legitimately rejects
        # this invalid clock BEFORE the frozen policy check is reached.
        self.reject([fixed(PPI,
            scheduled_release_at_utc=RELEASE[PPI]+timedelta(days=1))],
            "EVENT_ID_TIME_METRIC_OR_CONFOUNDER_CONTRADICTION")

    def test_09_cpi_wrong_release_minute_refused(self):
        self.reject([fixed(CPI,
            scheduled_release_at_utc=RELEASE[CPI]+timedelta(seconds=1))],
            "FROZEN_DEC2026_EVENT_ABSTAIN_OR_CLOCK_OVERRIDE")

    def test_10_ppi_wrong_issuer_fails_no_renaming_to_cad_news(self):
        # Seven USD crosses cannot masquerade as the CAD issuer cohort;
        # the canonical pair-set gate rejects it first, also fail-closed.
        self.reject([fixed(PPI,issuer_currency="CAD")],
            "INCOMPLETE_NONCANONICAL_SEVEN_CROSS_FX_COHORT")

    def test_11_cpi_abstain_with_fake_issue_time_not_permitted(self):
        self.reject([fixed(CPI,
            pre_event_forecast_issued_at_utc=RELEASE[CPI]-timedelta(hours=3))],
            "FROZEN_DEC2026_EVENT_ABSTAIN_OR_CLOCK_OVERRIDE")

    def test_12_generic_forecast_at_exactly_one_hour_is_only_unattested_claim(self):
        r=self.success([generic(minutes=60)])
        self.assertEqual(r["untrusted_directional_forecast_claims_checked"],1)
        self.assertEqual(r["untrusted_abstention_event_roots_checked"],0)
        self.assertEqual(r["frozen_dec2026_event_roots_seen"],[])
        self.assertFalse(r["forecasts_not_retrospectively_fabricated"])

    def test_13_generic_forecast_one_second_late_fails(self):
        self.reject([generic(minutes=60-1/60)],
            "MISSING_LATE_OR_REWRITTEN_PRE_EVENT_FORECAST")

    def test_14_generic_forecast_one_microsecond_late_fails(self):
        e=generic(minutes=60)
        e=replace(e,pre_event_forecast_issued_at_utc=
                  e.pre_event_forecast_issued_at_utc+timedelta(microseconds=1))
        self.reject([e],"MISSING_LATE_OR_REWRITTEN_PRE_EVENT_FORECAST")

    def test_15_generic_forecast_59_minutes_before_fails(self):
        self.reject([generic(minutes=59)],
            "MISSING_LATE_OR_REWRITTEN_PRE_EVENT_FORECAST")

    def test_16_generic_forecast_two_hours_before_is_claim_not_win_rate(self):
        r=self.success([generic(minutes=120,direction="DOWN")])
        self.assertEqual(r["untrusted_directional_forecast_claims_checked"],1)

    def test_17_generic_forecast_at_12hour_lookback_boundary_accepted_claim(self):
        r=self.success([generic(minutes=12*60)])
        self.assertEqual(r["untrusted_directional_forecast_claims_checked"],1)

    def test_18_generic_forecast_one_microsecond_older_than_12h_blocks(self):
        e=generic(minutes=12*60)
        e=replace(e,pre_event_forecast_issued_at_utc=
                  e.pre_event_forecast_issued_at_utc-timedelta(microseconds=1))
        self.reject([e],"MISSING_LATE_OR_REWRITTEN_PRE_EVENT_FORECAST")

    def test_19_generic_forecast_before_source_captured_blocks(self):
        r=self.reject([generic(minutes=60,
            consensus_locally_captured_at_utc=fx.START-timedelta(minutes=15))],
            "MISSING_LATE_OR_REWRITTEN_PRE_EVENT_FORECAST")
        self.assertEqual(r["untrusted_event_roots_checked"],0)

    def test_20_two_frozen_events_and_generic_up_preserve_abstention_count(self):
        r=self.success([fixed(CPI),fixed(PPI),generic(
            release=datetime(2026,10,1,13,30,tzinfo=UTC))])
        self.assertEqual(r["untrusted_abstention_event_roots_checked"],2)
        self.assertEqual(r["untrusted_directional_forecast_claims_checked"],1)
        self.assertEqual(r["untrusted_event_roots_checked"],3)
        self.assertIsNone(r["out_of_sample_accuracy"])

    def test_21_frozen_cpi_cuiaba_release_represents_same_instant(self):
        tz=timezone(timedelta(hours=-4))
        e=fixed(CPI)
        alt=replace(e,
            scheduled_release_at_utc=e.scheduled_release_at_utc.astimezone(tz),
            consensus_locally_captured_at_utc=e.consensus_locally_captured_at_utc.astimezone(tz),
            actual_locally_captured_at_utc=e.actual_locally_captured_at_utc.astimezone(tz),
            price_locally_captured_at_utc=e.price_locally_captured_at_utc.astimezone(tz))
        self.assertEqual(self.success([e]),self.success([alt]))

    def test_22_december_forecast_override_fails_all_even_if_other_event_clean(self):
        a=fixed(CPI)
        b=fixed(PPI,
            pre_event_forecast_direction="UP",
            pre_event_forecast_issued_at_utc=RELEASE[PPI]-timedelta(hours=2))
        self.reject([a,b],"FROZEN_DEC2026_EVENT_ABSTAIN_OR_CLOCK_OVERRIDE")

    def test_23_missing_external_news_still_quarantines_abstention(self):
        e=fixed(CPI,competing_release_roots=("USD_EXTERNAL_CONFOUNDER_MOCK",))
        r=self.success([e])
        self.assertEqual(r["quarantined_unresolved_confounder_cluster_count"],1)
        self.assertEqual(r["candidate_train_cluster_count"],0)
        self.assertEqual(r["candidate_holdout_cluster_count"],0)
        self.assertEqual(r["untrusted_abstention_event_roots_checked"],1)

    def test_24_empty_roster_still_no_perfect_accuracy(self):
        r=check([])
        self.safe(r)
        self.assertEqual(r["state"],"LAB_MOTOR_A_NO_HISTORICAL_EVENT_CLAIMS_NO_GO")
        self.assertEqual(r["untrusted_event_roots_checked"],0)
        self.assertIsNone(r["out_of_sample_accuracy"])

if __name__=="__main__":
    unittest.main()
