"""Synthetic CPI/PPI PIT vintage tests: NEVER real macro prints or FX signals."""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import unittest

from atlasquant_trader_fx28_macro_event_surprise_reaction_contract_lab import (
    MetricIdentity, PreEventConsensus, OfficialActual,
)
from atlasquant_trader_us_cpi_source_custody_lab import RELEASE as CPI
from atlasquant_trader_us_ppi_oct2026_actual_table_guard_lab import RELEASE_UTC as PPI
from atlasquant_trader_us_cpi_ppi_pit_visibility_cutoff_lab import (
    EventVintageClaim, inspect_us_cpi_ppi_pit_cutoff_lab as inspect,
)

UTC=timezone.utc
CPI_RAW=b"SYNTHETIC CPI FINAL SOURCE CONTENT NOT REAL BLS"
PPI_RAW=b"SYNTHETIC PPI FINAL SOURCE CONTENT NOT REAL BLS"
CPI_POLL=b"SYNTHETIC CPI ANALYST CONSENSUS NOT REAL"
PPI_POLL=b"SYNTHETIC PPI ANALYST CONSENSUS NOT REAL"
POLL_URL="https://www.reuters.com/world/us/synthetic-research-mock"
BLS_CPI="https://www.bls.gov/news.release/archives/cpi_11102026.htm"
BLS_PPI="https://www.bls.gov/news.release/archives/ppi_11132026.htm"


def macro_cases():
    rows=[]
    for kind, release, poll_raw, actual_raw, source, name, cv, av in (
        ("CPI",CPI,CPI_POLL,CPI_RAW,BLS_CPI,"US_CPI_U_HEADLINE","0.2","0.3"),
        ("PPI",PPI,PPI_POLL,PPI_RAW,BLS_PPI,"US_PPI_FINAL_DEMAND","0.2","0.4"),
    ):
        metric=MetricIdentity(
            currency="USD",series_id=name,reference_period="2026-10",
            transformation="MOM",seasonal_adjustment="SA",unit="PERCENT")
        consensus=PreEventConsensus(
            metric=metric,numeric_value=cv,source_url=POLL_URL,
            original_sha256_claim=sha256(poll_raw).hexdigest(),
            published_at_utc=release-timedelta(days=3),
            locally_captured_at_utc=release-timedelta(days=2))
        first=OfficialActual(
            metric=metric,numeric_value=av,official_source_url=source,
            original_sha256_claim=sha256(actual_raw).hexdigest(),
            scheduled_release_at_utc=release,
            published_at_utc=release,
            locally_captured_at_utc=release+timedelta(minutes=3),
            first_print_vintage_claim="FIRST_PRINT_CLAIM_ONLY")
        rows.append(EventVintageClaim(
            kind=kind,consensus=consensus,consensus_source_bytes=poll_raw,
            actual=first,actual_source_bytes=actual_raw))
    return tuple(rows)


class CpiPpiPitCutoffTests(unittest.TestCase):
    def examine(self, *, cutoff=None, horizon="D1", rows=None):
        return inspect(
            decision_cutoff_utc=(
                PPI+timedelta(minutes=4) if cutoff is None else cutoff),
            research_horizon=horizon,
            event_claims=macro_cases() if rows is None else rows)

    def guard(self,r):
        self.assertEqual(r["economic_event_roster"],["CPI","PPI"])
        self.assertEqual((r["us_release_direct_leg_pairs"],
                          r["non_usd_direct_leg_pairs"]),(7,21))
        self.assertTrue(r["ppi_event_not_seven_independent_fx_trials"])
        self.assertTrue(r["cpi_ppi_mom_sa_are_distinct_metrics"])
        self.assertTrue(r["release_time_is_not_source_first_seen"])
        self.assertTrue(r["local_sha256_is_not_independent_issuer_attestation"])
        self.assertTrue(r["horizon_M1_not_a_slot_in_original_672_fx28_campaign"])
        for key in (
            "pre_event_feature_contaminated_by_future_actual",
            "consensus_captured_after_release_used_as_pre_event",
            "original_672_campaign_slots_modified",
            "source_first_seen_independently_authenticated",
            "pre_event_consensus_independently_authenticated",
            "live_signal_authorized","trade_authorized","publishable",
            "scheduler_enabled"):
            self.assertFalse(r[key],key)
        self.assertIsNone(r["validated_fx_accuracy"])
        self.assertIsNone(r["calibrated_directional_probability"])
        self.assertIsNone(r["directional_bias"])
        self.assertEqual((r["http_requests"],r["file_writes"],r["mt5_calls"]),(0,0,0))
        self.assertEqual(r["operational_bias"],"AGUARDAR")

    def test_01_both_post_release_synthetic_surprises_are_only_documentary(self):
        r=self.examine()
        self.guard(r)
        self.assertEqual(r["state"],
            "LAB_US_CPI_PPI_CUTOFF_LOCALLY_RECONCILED_UNATTESTED_NO_GO")
        self.assertEqual(r["economic_events_reconciled"],2)
        self.assertEqual(r["research_events_with_pre_release_consensus_visible"],2)
        self.assertEqual(r["research_events_with_first_print_visible_at_cutoff_claim_only"],2)
        self.assertEqual(r["documentary_surprises_comparable_after_release_only"],2)
        self.assertEqual([x["actual_minus_consensus_percentage_points_documentary"]
                          for x in r["feature_rows"]],["0.1","0.2"])
        self.assertEqual([x["metric_id"] for x in r["feature_rows"]],
                         ["US_CPI_U_HEADLINE","US_PPI_FINAL_DEMAND"])

    def test_02_day_before_cpi_release_consensus_only_zero_future_actuals(self):
        r=self.examine(cutoff=CPI-timedelta(hours=2))
        self.guard(r)
        self.assertEqual(r["research_events_with_pre_release_consensus_visible"],1)
        self.assertEqual(r["research_events_with_first_print_visible_at_cutoff_claim_only"],0)
        self.assertTrue(all(x["actual_first_print_percent_local_claim_visible"] is None
                            for x in r["feature_rows"]))
        self.assertTrue(all(x["actual_minus_consensus_percentage_points_documentary"] is None
                            for x in r["feature_rows"]))
        self.assertEqual(r["feature_rows"][0]["cutoff_stage"],
                         "PRE_RELEASE_CONSENSUS_LOCAL_CLAIM_VISIBLE_NO_GO")
        self.assertEqual(r["feature_rows"][1]["cutoff_stage"],
                         "PRE_RELEASE_CONSENSUS_NOT_YET_VISIBLE")

    def test_03_just_before_first_cpi_release_no_lookahead(self):
        r=self.examine(cutoff=CPI-timedelta(seconds=1))
        self.guard(r)
        self.assertEqual(r["research_events_with_first_print_visible_at_cutoff_claim_only"],0)

    def test_04_at_exact_cpi_release_actual_not_captured_yet(self):
        r=self.examine(cutoff=CPI)
        self.guard(r)
        self.assertEqual(r["research_events_with_first_print_visible_at_cutoff_claim_only"],0)
        self.assertEqual(r["feature_rows"][0]["cutoff_stage"],
                         "RELEASE_PASSED_BUT_ACTUAL_NOT_VISIBLE_AT_CUTOFF")

    def test_05_after_cpi_capture_ppi_still_future(self):
        r=self.examine(cutoff=CPI+timedelta(minutes=5))
        self.guard(r)
        self.assertEqual(r["research_events_with_first_print_visible_at_cutoff_claim_only"],1)
        self.assertEqual(r["documentary_surprises_comparable_after_release_only"],1)
        self.assertIsNone(r["feature_rows"][1]["actual_first_print_percent_local_claim_visible"])

    def test_06_before_ppi_release_cpi_available_ppi_hidden(self):
        r=self.examine(cutoff=PPI-timedelta(seconds=1))
        self.guard(r)
        self.assertEqual(r["feature_rows"][1]["cutoff_stage"],
                         "PRE_RELEASE_CONSENSUS_LOCAL_CLAIM_VISIBLE_NO_GO")
        self.assertIsNone(r["feature_rows"][1]["actual_minus_consensus_percentage_points_documentary"])

    def test_07_exact_ppi_release_is_not_actual_first_seen(self):
        r=self.examine(cutoff=PPI)
        self.guard(r)
        self.assertEqual(r["research_events_with_first_print_visible_at_cutoff_claim_only"],1)
        self.assertEqual(r["feature_rows"][1]["cutoff_stage"],
                         "RELEASE_PASSED_BUT_ACTUAL_NOT_VISIBLE_AT_CUTOFF")

    def test_08_before_ppi_local_capture_even_if_release_passed(self):
        r=self.examine(cutoff=PPI+timedelta(minutes=2))
        self.guard(r)
        self.assertIsNone(r["feature_rows"][1]["actual_first_print_percent_local_claim_visible"])

    def test_09_exact_ppi_capture_time_candidate_visible_documentary(self):
        r=self.examine(cutoff=PPI+timedelta(minutes=3))
        self.guard(r)
        self.assertEqual(r["documentary_surprises_comparable_after_release_only"],2)

    def test_10_m1_stage_is_research_not_new_672_horizon(self):
        r=self.examine(horizon="M1")
        self.guard(r)
        self.assertEqual(r["requested_research_horizon"],"M1")
        self.assertEqual(r["economic_events_reconciled"],2)
        self.assertIsNone(r["validated_fx_accuracy"])

    def test_11_w1_stage_research_only(self):
        r=self.examine(horizon="W1")
        self.guard(r)
        self.assertEqual(r["requested_research_horizon"],"W1")

    def test_12_invalid_horizon_rejected(self):
        r=self.examine(horizon="M15")
        self.guard(r)
        self.assertEqual(r["state"],"LAB_US_CPI_PPI_PIT_VISIBILITY_BLOCKED_NO_GO")

    def test_13_cpi_yoy_cannot_masquerade_as_mom(self):
        rows=list(macro_cases())
        wrong=replace(rows[0].consensus.metric,transformation="YOY")
        rows[0]=replace(rows[0],consensus=replace(rows[0].consensus,metric=wrong))
        r=self.examine(rows=rows)
        self.guard(r)
        self.assertEqual(r["reason"],"INVALID_PRE_RELEASE_CONSENSUS_VINTAGE_OR_METRIC")

    def test_14_ppi_core_cannot_be_headline(self):
        rows=list(macro_cases())
        wrong=replace(rows[1].actual.metric,series_id="US_PPI_EX_FOOD_ENERGY")
        rows[1]=replace(rows[1],actual=replace(rows[1].actual,metric=wrong))
        self.assertEqual(self.examine(rows=rows)["reason"],
                         "INVALID_FIRST_PRINT_OR_WRONG_METRIC_OR_RELEASE_CLOCK")

    def test_15_ppi_nsa_cannot_be_sa(self):
        rows=list(macro_cases())
        wrong=replace(rows[1].consensus.metric,seasonal_adjustment="NSA")
        rows[1]=replace(rows[1],consensus=replace(rows[1].consensus,metric=wrong))
        self.assertEqual(self.examine(rows=rows)["reason"],
                         "INVALID_PRE_RELEASE_CONSENSUS_VINTAGE_OR_METRIC")

    def test_16_wrong_reference_month_rejected(self):
        rows=list(macro_cases())
        wrong=replace(rows[0].actual.metric,reference_period="2026-09")
        rows[0]=replace(rows[0],actual=replace(rows[0].actual,metric=wrong))
        self.assertEqual(self.examine(rows=rows)["reason"],
                         "INVALID_FIRST_PRINT_OR_WRONG_METRIC_OR_RELEASE_CLOCK")

    def test_17_post_release_consensus_not_pre_event_witness(self):
        rows=list(macro_cases())
        late=replace(rows[1].consensus,
                     locally_captured_at_utc=PPI+timedelta(seconds=1))
        rows[1]=replace(rows[1],consensus=late)
        r=self.examine(rows=rows)
        self.guard(r)
        self.assertEqual(r["reason"],"INVALID_PRE_RELEASE_CONSENSUS_VINTAGE_OR_METRIC")

    def test_18_consensus_published_after_release_rejected(self):
        rows=list(macro_cases())
        late=replace(rows[0].consensus,published_at_utc=CPI+timedelta(minutes=1),
                     locally_captured_at_utc=CPI+timedelta(minutes=2))
        rows[0]=replace(rows[0],consensus=late)
        self.assertEqual(self.examine(rows=rows)["reason"],
                         "INVALID_PRE_RELEASE_CONSENSUS_VINTAGE_OR_METRIC")

    def test_19_cpi_actual_published_before_scheduled_release_rejected(self):
        rows=list(macro_cases())
        fake=replace(rows[0].actual,published_at_utc=CPI-timedelta(seconds=1))
        rows[0]=replace(rows[0],actual=fake)
        self.assertEqual(self.examine(rows=rows)["reason"],
                         "INVALID_FIRST_PRINT_OR_WRONG_METRIC_OR_RELEASE_CLOCK")

    def test_20_release_clock_cannot_be_retimen(self):
        rows=list(macro_cases())
        fake=replace(rows[1].actual,
                     scheduled_release_at_utc=PPI-timedelta(hours=1))
        rows[1]=replace(rows[1],actual=fake)
        self.assertEqual(self.examine(rows=rows)["reason"],
                         "INVALID_FIRST_PRINT_OR_WRONG_METRIC_OR_RELEASE_CLOCK")

    def test_21_actual_bls_url_cannot_be_reuters_or_other_publisher(self):
        rows=list(macro_cases())
        fake=replace(rows[0].actual,official_source_url=POLL_URL)
        rows[0]=replace(rows[0],actual=fake)
        self.assertEqual(self.examine(rows=rows)["reason"],
                         "INVALID_FIRST_PRINT_OR_WRONG_METRIC_OR_RELEASE_CLOCK")

    def test_22_hash_does_not_match_actual_original_bytes(self):
        rows=list(macro_cases())
        rows[1]=replace(rows[1],actual_source_bytes=b"DIFFERENT BLS HTML")
        self.assertEqual(self.examine(rows=rows)["reason"],
                         "INVALID_FIRST_PRINT_OR_WRONG_METRIC_OR_RELEASE_CLOCK")

    def test_23_hash_does_not_match_consensus_original_bytes(self):
        rows=list(macro_cases())
        rows[1]=replace(rows[1],consensus_source_bytes=b"DIFFERENT POLL")
        self.assertEqual(self.examine(rows=rows)["reason"],
                         "INVALID_PRE_RELEASE_CONSENSUS_VINTAGE_OR_METRIC")

    def test_24_missing_actual_remains_absent_even_after_release(self):
        rows=list(macro_cases())
        rows[1]=replace(rows[1],actual=None,actual_source_bytes=None)
        r=self.examine(rows=rows)
        self.guard(r)
        self.assertEqual(r["research_events_with_first_print_visible_at_cutoff_claim_only"],1)
        self.assertEqual(r["feature_rows"][1]["cutoff_stage"],
                         "RELEASE_PASSED_BUT_ACTUAL_NOT_VISIBLE_AT_CUTOFF")

    def test_25_missing_consensus_never_posthoc_fill_from_actual(self):
        rows=list(macro_cases())
        rows[1]=replace(rows[1],consensus=None,consensus_source_bytes=None)
        r=self.examine(rows=rows)
        self.guard(r)
        self.assertEqual(r["feature_rows"][1]["cutoff_stage"],
                         "POST_RELEASE_ACTUAL_ONLY_WITHOUT_PRE_EVENT_CONSENSUS")
        self.assertIsNone(r["feature_rows"][1]["actual_minus_consensus_percentage_points_documentary"])

    def test_26_if_no_consensus_pre_event_nothing_guessed(self):
        rows=list(macro_cases())
        rows[1]=replace(rows[1],consensus=None,consensus_source_bytes=None)
        r=self.examine(rows=rows,cutoff=PPI-timedelta(minutes=1))
        self.guard(r)
        self.assertEqual(r["feature_rows"][1]["cutoff_stage"],
                         "PRE_RELEASE_CONSENSUS_NOT_YET_VISIBLE")
        self.assertIsNone(r["feature_rows"][1]["consensus_percent_local_claim_visible"])

    def test_27_mismatched_present_value_and_bytes_rejected(self):
        rows=list(macro_cases())
        rows[0]=replace(rows[0],actual_source_bytes=None)
        self.assertEqual(self.examine(rows=rows)["reason"],
                         "ACTUAL_VALUE_OR_RAW_BYTES_MISSING")

    def test_28_one_duplicate_event_does_not_replace_ppi(self):
        rows=list(macro_cases())
        rows[1]=replace(rows[1],kind="CPI")
        self.assertEqual(self.examine(rows=rows)["reason"],
                         "DUPLICATE_UNKNOWN_OR_UNTYPED_MACRO_EVENT")

    def test_29_naive_or_microsecond_asof_rejected(self):
        for asof in (datetime(2026,11,13,13,34),
                     PPI+timedelta(microseconds=1)):
            with self.subTest(asof=asof):
                self.assertEqual(self.examine(cutoff=asof)["state"],
                    "LAB_US_CPI_PPI_PIT_VISIBILITY_BLOCKED_NO_GO")

    def test_30_int_float_actual_or_consensus_not_accepted(self):
        rows=list(macro_cases())
        rows[0]=replace(rows[0],actual=replace(rows[0].actual,numeric_value=0.3))
        self.assertEqual(self.examine(rows=rows)["reason"],
                         "INVALID_FIRST_PRINT_OR_WRONG_METRIC_OR_RELEASE_CLOCK")
        rows=list(macro_cases())
        rows[1]=replace(rows[1],consensus=replace(rows[1].consensus,
                                                  numeric_value="nan"))
        self.assertEqual(self.examine(rows=rows)["reason"],
                         "INVALID_PRE_RELEASE_CONSENSUS_VINTAGE_OR_METRIC")

    def test_31_actual_vintage_must_be_first_print_claim(self):
        rows=list(macro_cases())
        rows[0]=replace(rows[0],actual=replace(rows[0].actual,
                                              first_print_vintage_claim="REVISED"))
        self.assertEqual(self.examine(rows=rows)["reason"],
                         "INVALID_FIRST_PRINT_OR_WRONG_METRIC_OR_RELEASE_CLOCK")

    def test_32_consensus_captured_after_decision_within_pre_release_hidden(self):
        rows=list(macro_cases())
        cutoff=PPI-timedelta(days=1,minutes=1)
        # PPI claimed locally captured at PPI-2days so visible: replace to PPI-6h
        later=PPI-timedelta(hours=6)
        rows[1]=replace(rows[1],consensus=replace(rows[1].consensus,
                                                  locally_captured_at_utc=later))
        r=self.examine(rows=rows,cutoff=cutoff)
        self.guard(r)
        self.assertIsNone(r["feature_rows"][1]["consensus_percent_local_claim_visible"])
        self.assertEqual(r["feature_rows"][1]["cutoff_stage"],
                         "PRE_RELEASE_CONSENSUS_NOT_YET_VISIBLE")

    def test_33_cutoff_before_both_consensus_captures_shows_nothing(self):
        r=self.examine(cutoff=CPI-timedelta(days=4))
        self.guard(r)
        self.assertEqual(r["research_events_with_pre_release_consensus_visible"],0)
        self.assertEqual(r["research_events_with_first_print_visible_at_cutoff_claim_only"],0)
        self.assertTrue(all(x["consensus_percent_local_claim_visible"] is None
                            for x in r["feature_rows"]))


if __name__=="__main__":
    unittest.main(verbosity=2)
