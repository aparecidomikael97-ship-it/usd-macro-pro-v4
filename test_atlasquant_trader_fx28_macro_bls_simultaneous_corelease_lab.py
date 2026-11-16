"""BLS December-2026 CPI / Real Earnings simultaneous news research gate.

FACT FROM PUBLIC BLS SCHEDULE (checked 2026-11-16, page Last Modified
2026-11-09): on Thursday December 10, 2026 at 08:30 U.S. Eastern, the
Consumer Price Index for November AND Real Earnings for November are
listed for the same release time. PPI November is Dec 15 at 08:30 ET.
Official source: https://www.bls.gov/schedule/2026/12_sched_list.htm

These are SYNTHETIC archive/cohort tests. The government schedule is not
an independently timestamp-attested versioned original in this repository.
Real Earnings is related to CPI, not established as an independent shock.
Simultaneous publications preclude *exclusive CPI causal attribution*,
not all descriptive price research. NEVER create another registered USD
prediction or change frozen two-event ABSTAIN protocol.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import timedelta, timezone
from hashlib import sha256
import unittest

import test_atlasquant_trader_fx28_macro_frozen_forecast_cutoff_lab as f
from atlasquant_trader_us_dec2026_frozen_evaluation_protocol_lab import (
    FROZEN_PLAN,PINNED_PLAN_SHA256,canonical_frozen_plan_bytes_lab,
)

CPI=f.CPI
PPI=f.PPI
OTHER="US_REAL_EARNINGS_NOV2026"
MISSING="QUARANTINED_UNRESOLVED_COMPETING_RELEASE_NO_GO"
KNOWN="QUARANTINED_KNOWN_SAME_TIME_BLS_CORELEASE_NO_EXCLUSIVE_CAUSALITY"


def check(rows):
    r=f.check(rows)
    assert r["state"]==f.OK, r["reason"]
    assert r["untrusted_candidate_cluster_count"] + r[
        "quarantined_unresolved_confounder_cluster_count"] + r[
        "quarantined_known_same_time_corelease_cluster_count"] == r[
        "untrusted_total_cluster_count"]
    assert r["trade_authorized"] is False
    assert r["publishable"] is False
    assert r["can_train_calibrated_model"] is False
    assert r["out_of_sample_accuracy"] is None
    assert r["predicted_currency_direction"] is None
    assert r["calibrated_probability"] is None
    assert r["official_bls_calendar_first_seen_independently_attested"] is False
    assert r["no_change_to_frozen_672_slot_campaign"] is True
    assert r["new_cost_brl"]==0
    assert (r["http_requests"],r["mt5_calls"],r["file_writes"])==(0,0,0)
    assert all(not row["forecasts_can_be_scored"] and
               not row["exclusive_cpi_causality_claim_allowed"]
               for row in r["clusters"])
    return r


class OfficialBLSSameTimeCoreleaseTests(unittest.TestCase):
    def test_01_bls_calendar_reference_is_explicit_not_first_seen_claim(self):
        r=check([f.fixed(CPI)])
        self.assertEqual(r["official_bls_same_time_calendar_url"],
            "https://www.bls.gov/schedule/2026/12_sched_list.htm")
        self.assertFalse(r["official_bls_calendar_first_seen_independently_attested"])

    def test_02_cpi_missing_real_earnings_is_quarantined_not_candidate_train(self):
        r=check([f.fixed(CPI)])
        self.assertEqual(r["untrusted_event_roots_checked"],1)
        self.assertEqual(r["untrusted_total_cluster_count"],1)
        self.assertEqual(r["candidate_train_cluster_count"],0)
        self.assertEqual(r["untrusted_candidate_cluster_count"],0)
        self.assertEqual(r["quarantined_unresolved_confounder_cluster_count"],1)
        self.assertEqual(r["unresolved_competing_release_root_count"],1)
        self.assertEqual(r["clusters"][0]["partition"],MISSING)
        self.assertEqual(r["clusters"][0]["other_macro_releases_not_locally_resolved"],[OTHER])
        self.assertEqual(r["clusters"][0]["official_bls_same_time_coreleases"],[OTHER])

    def test_03_ppi_does_not_inherit_cpi_scheduled_simultaneity(self):
        r=check([f.fixed(PPI)])
        self.assertEqual(r["unresolved_competing_release_root_count"],0)
        self.assertEqual(r["quarantined_unresolved_confounder_cluster_count"],0)
        self.assertEqual(r["candidate_holdout_cluster_count"],1)
        self.assertEqual(r["clusters"][0]["official_bls_same_time_coreleases"],[])

    def test_04_both_december_frozen_abstentions_still_two_economic_roots(self):
        r=check([f.fixed(CPI),f.fixed(PPI)])
        self.assertEqual(r["untrusted_event_roots_checked"],2)
        self.assertEqual(r["untrusted_abstention_event_roots_checked"],2)
        self.assertEqual(r["untrusted_directional_forecast_claims_checked"],0)
        self.assertEqual(r["untrusted_total_cluster_count"],2)
        self.assertEqual(r["untrusted_candidate_cluster_count"],1)
        self.assertEqual(r["candidate_train_cluster_count"],0)
        self.assertEqual(r["candidate_holdout_cluster_count"],1)
        self.assertEqual(r["quarantined_unresolved_confounder_cluster_count"],1)
        self.assertEqual(r["frozen_dec2026_event_roots_seen"],[CPI,PPI])

    def test_05_explicit_known_external_root_is_not_double_counted(self):
        cpi=f.fixed(CPI,competing_release_roots=(OTHER,))
        r=check([cpi])
        self.assertEqual(r["unresolved_competing_release_root_count"],1)
        self.assertEqual(r["clusters"][0]["other_macro_releases_not_locally_resolved"],[OTHER])
        self.assertEqual(r["clusters"][0]["official_bls_same_time_coreleases"],[OTHER])

    def test_06_locally_inserting_fake_real_earnings_cannot_clear_quarantine(self):
        cpi=f.fixed(CPI)
        fake=f.fx.event(
            OTHER,release=f.RELEASE[CPI],
            metrics=("US_REAL_EARNINGS_MOM",),
        )
        r=check([cpi,fake])
        self.assertEqual(r["untrusted_total_cluster_count"],1)
        self.assertEqual(r["untrusted_event_roots_checked"],2)
        self.assertEqual(r["unresolved_competing_release_root_count"],0)
        self.assertEqual(r["quarantined_known_same_time_corelease_cluster_count"],1)
        self.assertEqual(r["untrusted_candidate_cluster_count"],0)
        self.assertEqual(r["clusters"][0]["partition"],KNOWN)
        self.assertEqual(r["clusters"][0]["event_roots_count"],2)
        self.assertEqual(r["clusters"][0]["official_bls_same_time_coreleases"],[OTHER])

    def test_07_manual_corelease_cluster_is_independent_of_input_order(self):
        cpi=f.fixed(CPI)
        fake=f.fx.event(OTHER,release=f.RELEASE[CPI],
                         metrics=("US_REAL_EARNINGS_MOM",))
        self.assertEqual(check([cpi,fake]),check([fake,cpi]))

    def test_08_cuiaba_timezone_same_instant_keeps_calendar_guard(self):
        tz=timezone(timedelta(hours=-4))
        cpi=f.fixed(CPI)
        alt=replace(cpi,
            scheduled_release_at_utc=cpi.scheduled_release_at_utc.astimezone(tz),
            consensus_locally_captured_at_utc=cpi.consensus_locally_captured_at_utc.astimezone(tz),
            actual_locally_captured_at_utc=cpi.actual_locally_captured_at_utc.astimezone(tz),
            price_locally_captured_at_utc=cpi.price_locally_captured_at_utc.astimezone(tz))
        self.assertEqual(check([cpi]),check([alt]))

    def test_09_frozen_cpi_root_not_overrideable_into_up_forecast(self):
        row=replace(f.fixed(CPI),
            pre_event_forecast_direction="UP",
            pre_event_forecast_issued_at_utc=f.RELEASE[CPI]-timedelta(hours=2))
        r=f.check([row])
        self.assertEqual(r["state"],f.BLOCK)
        self.assertEqual(r["reason"],"FROZEN_DEC2026_EVENT_ABSTAIN_OR_CLOCK_OVERRIDE")

    def test_10_cpi_root_alias_mock_is_not_automatically_verified_official(self):
        mock=f.fx.event(
            "US_CPI_NOV2026_MOCK",release=f.RELEASE[CPI],
            metrics=("US_CPI_ALL_ITEMS_MOM",),
        )
        r=check([mock])
        self.assertEqual(r["untrusted_candidate_cluster_count"],1)
        self.assertEqual(r["quarantined_unresolved_confounder_cluster_count"],0)
        self.assertEqual(r["clusters"][0]["official_bls_same_time_coreleases"],[])
        self.assertFalse(r["can_train_calibrated_model"])

    def test_11_another_external_unknown_release_is_also_preserved(self):
        cpi=f.fixed(CPI,competing_release_roots=("US_SECOND_UNKNOWN_MOCK",))
        r=check([cpi])
        self.assertEqual(r["unresolved_competing_release_root_count"],2)
        self.assertEqual(r["clusters"][0]["other_macro_releases_not_locally_resolved"],
                         [OTHER,"US_SECOND_UNKNOWN_MOCK"])

    def test_12_bls_schedule_does_not_change_frozen_plan_hash(self):
        blob=canonical_frozen_plan_bytes_lab(FROZEN_PLAN)
        self.assertEqual(sha256(blob).hexdigest(),PINNED_PLAN_SHA256)
        self.assertEqual(FROZEN_PLAN["independent_economic_event_roots"],2)
        self.assertEqual(FROZEN_PLAN["registered_forecasts"],0)
        self.assertEqual([e["forecast_direction"] for e in
                          FROZEN_PLAN["event_roots"]],["ABSTAIN","ABSTAIN"])

    def test_13_missing_corelease_never_counts_seven_fx_as_seven_oucomes(self):
        r=check([f.fixed(CPI)])
        self.assertEqual(r["untrusted_fx_pair_observations_checked"],7)
        self.assertEqual(r["untrusted_event_roots_checked"],1)
        self.assertEqual(r["quarantined_unresolved_confounder_cluster_count"],1)
        self.assertTrue(r["cross_pairs_not_independent_economic_samples"])

    def test_14_ppi_and_cpi_reverse_order_still_same_quarantine(self):
        a,b=f.fixed(CPI),f.fixed(PPI)
        self.assertEqual(check([a,b]),check([b,a]))

    def test_15_with_real_earnings_declared_and_ppi_elsewhere_counts_one_holdout(self):
        cpi=f.fixed(CPI)
        real=f.fx.event(OTHER,release=f.RELEASE[CPI],
                        metrics=("US_REAL_EARNINGS_MOM",))
        ppi=f.fixed(PPI)
        r=check([cpi,real,ppi])
        self.assertEqual(r["untrusted_total_cluster_count"],2)
        self.assertEqual(r["quarantined_known_same_time_corelease_cluster_count"],1)
        self.assertEqual(r["candidate_holdout_cluster_count"],1)
        self.assertEqual(r["candidate_train_cluster_count"],0)
        self.assertEqual(r["untrusted_candidate_cluster_count"],1)

    def test_16_same_time_corelease_does_not_imply_broker_spread_or_accuracy(self):
        r=check([f.fixed(CPI)])
        self.assertFalse(r["historical_broker_prices_independently_authenticated"])
        self.assertFalse(r["all_event_times_and_origins_independently_authenticated"])
        self.assertFalse(r["forecasts_not_retrospectively_fabricated"])
        self.assertFalse(r["all_release_confounders_discovered"])
        self.assertIsNone(r["out_of_sample_accuracy"])
        self.assertIsNone(r["calibrated_probability"])


if __name__=="__main__":
    unittest.main()
