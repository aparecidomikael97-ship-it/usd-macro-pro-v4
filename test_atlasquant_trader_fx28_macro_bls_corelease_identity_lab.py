"""Synthetic-only BLS Real Earnings official-root roster identity safety.

This does NOT prove independent publisher first-seen, the December 2026
release outcome, any historical prices, pre-event consensus or Forex edge.
The public BLS December 2026 calendar schedules CPI and Real Earnings
for November 2026 together at 2026-12-10T13:30:00Z.
No live data/MT5/network is accessed; all observations are fake.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import timedelta, timezone
from hashlib import sha256
import unittest

import test_atlasquant_trader_fx28_macro_frozen_forecast_cutoff_lab as f
from atlasquant_trader_us_dec2026_frozen_evaluation_protocol_lab import (
    FROZEN_PLAN, PINNED_PLAN_SHA256, canonical_frozen_plan_bytes_lab,
)

OTHER="US_REAL_EARNINGS_NOV2026"
REASON="BLS_CORELEASE_IDENTITY_CLOCK_CURRENCY_OR_METRIC_MISMATCH"
KNOWN="QUARANTINED_KNOWN_SAME_TIME_BLS_CORELEASE_NO_EXCLUSIVE_CAUSALITY"


def real(*, offset=timedelta(0), currency="USD",
         metrics=("US_REAL_EARNINGS_MOM",), root=OTHER):
    return f.fx.event(root, currency=currency,
                      release=f.RELEASE[f.CPI]+offset,metrics=metrics)


class CoreleaseIdentityPITTests(unittest.TestCase):
    def safety(self,result):
        self.assertIs(result["trade_authorized"],False)
        self.assertIs(result["publishable"],False)
        self.assertIs(result["can_train_calibrated_model"],False)
        self.assertIs(result["all_event_times_and_origins_independently_authenticated"],False)
        self.assertIs(result["official_bls_calendar_first_seen_independently_attested"],False)
        self.assertIs(result["forecasts_not_retrospectively_fabricated"],False)
        self.assertIs(result["out_of_sample_accuracy"],None)
        self.assertIs(result["calibrated_probability"],None)
        self.assertIs(result["predicted_currency_direction"],None)
        self.assertEqual(result["operational_bias"],"AGUARDAR")
        self.assertIs(result["no_change_to_frozen_672_slot_campaign"],True)
        self.assertEqual((result["http_requests"],result["mt5_calls"],
                          result["file_writes"],result["new_cost_brl"]),(0,0,0,0))
        for cluster in result["clusters"]:
            self.assertIs(cluster["can_count_as_authenticated_trial"],False)
            self.assertIs(cluster["forecasts_can_be_scored"],False)
            self.assertIs(cluster["exclusive_cpi_causality_claim_allowed"],False)

    def reject(self, event):
        result=f.check([f.fixed(f.CPI),event])
        self.safety(result)
        self.assertEqual(result["state"],f.BLOCK)
        self.assertEqual(result["reason"],REASON)
        self.assertEqual(result["untrusted_event_roots_checked"],0)
        self.assertEqual(result["untrusted_candidate_cluster_count"],0)
        self.assertEqual(result["quarantined_unresolved_confounder_cluster_count"],0)
        self.assertEqual(result["quarantined_known_same_time_corelease_cluster_count"],0)
        self.assertFalse(result["frozen_dec2026_abstain_rule_verified_claim_only"])
        return result

    def accept(self, rows):
        result=f.check(rows)
        self.safety(result)
        self.assertEqual(result["state"],f.OK,result["reason"])
        self.assertEqual(result["out_of_sample_accuracy"],None)
        return result

    def test_01_exact_bls_time_and_usd_real_earnings_join_known_quarantine(self):
        r=self.accept([f.fixed(f.CPI),real()])
        self.assertEqual(r["untrusted_total_cluster_count"],1)
        self.assertEqual(r["clusters"][0]["partition"],KNOWN)
        self.assertEqual(r["clusters"][0]["root_ids"],[f.CPI,OTHER])
        self.assertEqual(r["untrusted_candidate_cluster_count"],0)
        self.assertEqual(r["quarantined_known_same_time_corelease_cluster_count"],1)
        self.assertEqual(r["untrusted_directional_forecast_claims_checked"],0)
        self.assertEqual(r["untrusted_abstention_event_roots_checked"],2)

    def test_02_same_name_claimed_one_second_late_refused(self):
        self.reject(real(offset=timedelta(seconds=1)))

    def test_03_same_name_claimed_one_second_early_refused(self):
        self.reject(real(offset=timedelta(seconds=-1)))

    def test_04_same_name_claimed_one_day_later_refused(self):
        self.reject(real(offset=timedelta(days=1)))

    def test_05_same_name_claimed_one_day_earlier_refused(self):
        self.reject(real(offset=timedelta(days=-1)))

    def test_06_same_name_claimed_one_hour_later_refused(self):
        self.reject(real(offset=timedelta(hours=1)))

    def test_07_same_name_claimed_cad_issuer_refused(self):
        self.reject(real(currency="CAD"))

    def test_08_same_name_claimed_eur_issuer_refused(self):
        self.reject(real(currency="EUR"))

    def test_09_same_name_given_cpi_metric_not_real_earnings_refused(self):
        self.reject(real(metrics=("US_CPI_ALL_ITEMS_MOM",)))

    def test_10_same_name_given_ppi_metric_not_real_earnings_refused(self):
        self.reject(real(metrics=("US_PPI_FINAL_DEMAND_MOM",)))

    def test_11_mixed_real_earnings_and_unrelated_metric_refused(self):
        self.reject(real(metrics=("US_REAL_EARNINGS_MOM","US_PPI_FINAL_DEMAND_MOM")))

    def test_12_multiple_real_earnings_metrics_are_only_unattested_claims(self):
        r=self.accept([f.fixed(f.CPI),
            real(metrics=("US_REAL_EARNINGS_MOM","US_REAL_EARNINGS_YOY"))])
        self.assertEqual(r["quarantined_known_same_time_corelease_cluster_count"],1)
        self.assertIsNone(r["calibrated_probability"])

    def test_13_cuiaba_utc_minus_four_is_same_instant_not_misdated(self):
        tz=timezone(timedelta(hours=-4))
        e=real()
        transformed=replace(e,
            scheduled_release_at_utc=e.scheduled_release_at_utc.astimezone(tz),
            consensus_locally_captured_at_utc=e.consensus_locally_captured_at_utc.astimezone(tz),
            actual_locally_captured_at_utc=e.actual_locally_captured_at_utc.astimezone(tz),
            price_locally_captured_at_utc=e.price_locally_captured_at_utc.astimezone(tz))
        self.assertEqual(self.accept([f.fixed(f.CPI),e]),
                         self.accept([f.fixed(f.CPI),transformed]))

    def test_14_adding_frozen_ppi_cannot_hide_fake_real_earnings_roster(self):
        r=f.check([f.fixed(f.CPI),f.fixed(f.PPI),real(offset=timedelta(days=1))])
        self.safety(r)
        self.assertEqual(r["state"],f.BLOCK)
        self.assertEqual(r["reason"],REASON)
        self.assertEqual(r["untrusted_candidate_cluster_count"],0)

    def test_15_missing_real_earnings_remains_cpi_quarantine(self):
        r=self.accept([f.fixed(f.CPI)])
        self.assertEqual(r["quarantined_unresolved_confounder_cluster_count"],1)
        self.assertEqual(r["clusters"][0]["other_macro_releases_not_locally_resolved"],[OTHER])

    def test_16_arbitrary_alias_is_not_automatically_an_official_bls_claim(self):
        fake=real(root="US_REAL_EARNINGS_NOV2026_MOCK",offset=timedelta(days=1))
        r=self.accept([fake])
        self.assertEqual(r["untrusted_candidate_cluster_count"],1)
        self.assertEqual(r["quarantined_known_same_time_corelease_cluster_count"],0)
        self.assertFalse(r["all_release_confounders_discovered"])

    def test_17_frozen_cpi_ppi_plan_sha_and_two_abstentions_unchanged(self):
        self.assertEqual(sha256(canonical_frozen_plan_bytes_lab(FROZEN_PLAN)).hexdigest(),
                         PINNED_PLAN_SHA256)
        self.assertEqual(FROZEN_PLAN["registered_forecasts"],0)
        self.assertEqual(FROZEN_PLAN["independent_economic_event_roots"],2)
        self.assertEqual([row["forecast_direction"] for row in FROZEN_PLAN["event_roots"]],
                         ["ABSTAIN","ABSTAIN"])
        r=self.accept([f.fixed(f.CPI),f.fixed(f.PPI),real()])
        self.assertEqual(r["untrusted_event_roots_checked"],3)
        self.assertEqual(r["frozen_dec2026_event_roots_seen"],[f.CPI,f.PPI])
        self.assertEqual(r["untrusted_directional_forecast_claims_checked"],0)
        self.assertEqual(r["quarantined_known_same_time_corelease_cluster_count"],1)
        self.assertEqual(r["candidate_holdout_cluster_count"],1)


if __name__=="__main__":
    unittest.main()
