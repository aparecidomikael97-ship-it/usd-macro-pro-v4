"""Synthetic-only two-event census tests; no performance data from fixtures."""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch
import unittest

from atlasquant_trader_us_cpi_ppi_two_event_coverage_lab import (
    inspect_oct2026_us_cpi_ppi_two_event_coverage_lab as inspect,
)
from atlasquant_trader_us_ppi_oct2026_actual_table_guard_lab import (
    RELEASE_UTC as PPI_RELEASE,
)
from atlasquant_trader_us_cpi_source_custody_lab import RELEASE as CPI_RELEASE
from atlasquant_trader_ppi_usd_fx_forward_reaction_lab import LAST_REQUIRED_CLOSE_UTC
from test_atlasquant_trader_us_cpi_ppi_official_body_join_lab import cases
from test_atlasquant_trader_us_cpi_ppi_consensus_body_gate_lab import (
    pair, synthetic_digest_fixture_lock,
)
from test_atlasquant_trader_ppi_one_event_study_join_lab import (
    OneEventStudyJoinTests,
)

UTC=timezone.utc
POST=LAST_REQUIRED_CLOSE_UTC+timedelta(hours=1)


def scenario():
    claims, receipts=cases()
    # Only the source-bound parser may create a claimed PPI consensus.
    stripped=tuple(replace(e,consensus=None,consensus_source_bytes=None)
                   for e in claims)
    return stripped,receipts,pair()


def run(claims,receipts,source,now=POST,packet=None):
    return inspect(research_cutoff_utc=now,event_claims=claims,
                   actual_http_receipts=receipts,
                   ppi_original_pair=source,ppi_study_packet=packet)


class TwoEventCoverageLabTests(unittest.TestCase):
    def safety(self,out):
        self.assertEqual(out["schema"],"ATLASQUANT_US_CPI_PPI_OCT2026_TWO_EVENT_DENOMINATOR_LAB_V1")
        self.assertEqual(out["frozen_macro_event_denominator"],2)
        self.assertEqual([r["kind"] for r in out["event_roots"]],["CPI","PPI"])
        self.assertEqual([r["root_id"] for r in out["event_roots"]],
                         ["US_CPI_OCT2026","US_PPI_OCT2026"])
        self.assertFalse(out["trade_authorized"])
        self.assertFalse(out["publishable"])
        self.assertFalse(out["source_first_seen_independently_authenticated"])
        self.assertFalse(out["broker_prices_independently_authenticated"])
        self.assertFalse(out["ppi_exclusive_news_causality_established"])
        self.assertEqual(out["operational_bias"],"AGUARDAR")
        self.assertEqual(out["pre_event_directional_fx_forecasts_registered_and_independently_witnessed"],0)
        self.assertEqual(out["independent_tradable_prediction_trials"],0)
        self.assertEqual(out["testable_out_of_sample_macro_event_count"],0)
        self.assertIsNone(out["validated_directional_accuracy"])
        self.assertIsNone(out["calibrated_directional_probability"])
        self.assertIsNone(out["market_bias"])
        self.assertFalse(out["original_672_campaign_slots_modified"])
        self.assertTrue(out["seven_correlated_spot_crosses_not_seven_economic_trials"])
        self.assertEqual((out["mt5_calls"],out["http_requests"],out["file_writes"]),(0,0,0))

    def test_01_two_actuals_one_pit_consensus_only(self):
        claims,receipts,sources=scenario()
        with synthetic_digest_fixture_lock(sources):
            r=run(claims,receipts,sources)
        self.safety(r)
        self.assertEqual(r["state"],"LAB_CPI_PPI_TWO_EVENT_DOCUMENTARY_COVERAGE_NO_GO")
        self.assertEqual((r["documentary_actual_events_available"],
                          r["documentary_pre_event_consensus_events_available"],
                          r["documentary_comparable_macro_surprise_events"]), (2,1,1))
        self.assertEqual(r["events_without_comparable_consensus_or_actual"],1)
        self.assertEqual(r["event_roots"][0]["study_stage"],
                         "POST_EVENT_ACTUAL_ONLY_NO_COMPARABLE_CONSENSUS")
        self.assertEqual(r["event_roots"][1]["study_stage"],
                         "RETROSPECTIVE_DOCUMENTARY_SURPRISE_ONLY")
        self.assertIsNone(r["event_roots"][0]["retrospective_surprise_percentage_points"])
        self.assertEqual(r["event_roots"][1]["retrospective_surprise_percentage_points"],"0.1")

    def test_02_real_pinned_source_hashes_required_not_synthetic(self):
        claims,receipts,sources=scenario()
        r=run(claims,receipts,sources)
        self.safety(r)
        self.assertEqual((r["documentary_actual_events_available"],
                          r["documentary_pre_event_consensus_events_available"],
                          r["documentary_comparable_macro_surprise_events"]), (2,0,0))

    def test_03_missing_source_pair_keeps_denominator_two(self):
        claims,receipts,_=scenario()
        r=run(claims,receipts,None)
        self.safety(r)
        self.assertEqual(r["events_without_comparable_consensus_or_actual"],2)
        self.assertEqual(r["documentary_actual_events_available"],2)

    def test_04_missing_cpi_actual_not_deleted_from_denominator(self):
        claims,receipts,sources=scenario()
        claims=(replace(claims[0],actual=None,actual_source_bytes=None),claims[1])
        receipts={**receipts,"CPI":None}
        with synthetic_digest_fixture_lock(sources):
            r=run(claims,receipts,sources)
        self.safety(r)
        self.assertEqual(r["documentary_actual_events_available"],1)
        self.assertEqual(r["documentary_comparable_macro_surprise_events"],1)
        self.assertEqual(r["event_roots"][0]["study_stage"],
                         "NO_ADMISSIBLE_SOURCE_AT_RESEARCH_CUTOFF")

    def test_05_missing_ppi_actual_still_keeps_ppi_consensus_visible(self):
        claims,receipts,sources=scenario()
        claims=(claims[0],replace(claims[1],actual=None,actual_source_bytes=None))
        receipts={**receipts,"PPI":None}
        with synthetic_digest_fixture_lock(sources):
            r=run(claims,receipts,sources)
        self.safety(r)
        self.assertEqual((r["documentary_actual_events_available"],
                          r["documentary_pre_event_consensus_events_available"],
                          r["documentary_comparable_macro_surprise_events"]),(1,1,0))
        self.assertEqual(r["event_roots"][1]["study_stage"],
                         "PRE_EVENT_CONSENSUS_ONLY_NO_FUTURE_ACTUAL")

    def test_06_before_both_events_no_actuals_may_be_seen(self):
        claims,receipts,sources=scenario()
        with synthetic_digest_fixture_lock(sources):
            r=run(claims,receipts,sources,
                  now=CPI_RELEASE-timedelta(hours=1))
        self.safety(r)
        self.assertEqual((r["documentary_actual_events_available"],
                          r["documentary_pre_event_consensus_events_available"],
                          r["documentary_comparable_macro_surprise_events"]),(0,0,0))

    def test_07_after_cpi_actual_before_ppi_publication_only_consensus_ppi(self):
        claims,receipts,sources=scenario()
        with synthetic_digest_fixture_lock(sources):
            r=run(claims,receipts,sources,
                  now=PPI_RELEASE-timedelta(days=1))
        self.safety(r)
        self.assertEqual((r["documentary_actual_events_available"],
                          r["documentary_pre_event_consensus_events_available"],
                          r["documentary_comparable_macro_surprise_events"]),(1,1,0))
        self.assertTrue(r["event_roots"][0]["actual_visible_in_original_claimed_time"])
        self.assertFalse(r["event_roots"][1]["actual_visible_in_original_claimed_time"])

    def test_08_scheduled_ppi_release_is_not_actual_capture(self):
        claims,receipts,sources=scenario()
        with synthetic_digest_fixture_lock(sources):
            r=run(claims,receipts,sources,now=PPI_RELEASE)
        self.safety(r)
        self.assertEqual(r["documentary_actual_events_available"],1)

    def test_09_missing_receipt_fails_closed_and_keeps_two(self):
        claims,receipts,sources=scenario()
        receipts={**receipts,"CPI":None}
        with synthetic_digest_fixture_lock(sources):
            r=run(claims,receipts,sources)
        self.safety(r)
        self.assertEqual(r["state"],"LAB_CPI_PPI_TWO_EVENT_COVERAGE_BLOCKED_NO_GO")
        self.assertEqual(r["documentary_actual_events_available"],0)

    def test_10_wrong_macro_number_fails_before_any_count(self):
        claims,receipts,sources=scenario()
        claims=(replace(claims[0],actual=replace(claims[0].actual,
                                                 numeric_value="99.9")), claims[1])
        with synthetic_digest_fixture_lock(sources):
            r=run(claims,receipts,sources)
        self.safety(r)
        self.assertEqual(r["documentary_actual_events_available"],0)
        self.assertEqual(r["documentary_comparable_macro_surprise_events"],0)

    def test_11_foreign_duplicate_roster_rejected(self):
        claims,receipts,sources=scenario()
        with synthetic_digest_fixture_lock(sources):
            r=run((claims[0],claims[0]),receipts,sources)
        self.safety(r)
        self.assertEqual(r["state"],"LAB_CPI_PPI_TWO_EVENT_COVERAGE_BLOCKED_NO_GO")

    def test_12_naive_clock_rejected(self):
        claims,receipts,sources=scenario()
        r=run(claims,receipts,sources,now=datetime(2026,11,15))
        self.safety(r)
        self.assertEqual(r["state"],"LAB_CPI_PPI_TWO_EVENT_COVERAGE_BLOCKED_NO_GO")

    def test_13_microsecond_decision_clock_rejected_not_rounded_back(self):
        claims,receipts,sources=scenario()
        r=run(claims,receipts,sources,now=POST+timedelta(microseconds=5))
        self.safety(r)
        self.assertEqual(r["documentary_actual_events_available"],0)

    def test_14_cpi_injected_pre_event_consensus_never_counted(self):
        claims,receipts,sources=scenario()
        from test_atlasquant_trader_us_cpi_ppi_pit_visibility_cutoff_lab import macro_cases
        forged=macro_cases()[0]
        claims=(replace(claims[0],consensus=forged.consensus,
                        consensus_source_bytes=forged.consensus_source_bytes),claims[1])
        with synthetic_digest_fixture_lock(sources):
            r=run(claims,receipts,sources)
        self.safety(r)
        self.assertEqual(r["documentary_pre_event_consensus_events_available"],1)
        self.assertIsNone(r["event_roots"][0]["retrospective_surprise_percentage_points"])

    def test_15_no_price_packet_does_not_assume_seven_market_observations(self):
        claims,receipts,sources=scenario()
        with synthetic_digest_fixture_lock(sources):
            r=run(claims,receipts,sources)
        self.safety(r)
        self.assertFalse(r["ppi_fx_price_study_originals_revalidated"])
        self.assertEqual(r["ppi_correlated_fx_pairs_descriptively_observed"],0)
        self.assertEqual(r["ppi_price_study_attachment_reason"],"PPI_PRICE_ORIGINALS_NOT_SUPPLIED")

    def test_16_bogus_price_study_dict_not_accepted_as_one_event(self):
        claims,receipts,sources=scenario()
        with synthetic_digest_fixture_lock(sources):
            r=run(claims,receipts,sources,packet={"state":"SUCCESS","accuracy":"100%"})
        self.safety(r)
        self.assertFalse(r["ppi_fx_price_study_originals_revalidated"])
        self.assertEqual(r["ppi_price_study_attachment_reason"],
                         "PPI_PRICE_STUDY_ORIGINAL_BYTES_NOT_SAME_EVENT")

    def test_17_wrong_ppi_html_in_price_packet_blocks_without_trading(self):
        claims,receipts,sources=scenario()
        t=OneEventStudyJoinTests(methodName="test_integrated_synthetic_study_is_one_event_not_seven_trials")
        t.setUp();self.addCleanup(t.doCleanups)
        bad_packet=replace(t.packet,bls_html=t.packet.bls_html+b" ")
        with synthetic_digest_fixture_lock(sources):
            r=run(claims,receipts,sources,packet=bad_packet)
        self.safety(r)
        self.assertEqual(r["ppi_price_study_attachment_reason"],
                         "PPI_PRICE_STUDY_ORIGINAL_BYTES_NOT_SAME_EVENT")

    def test_18_price_data_not_eligible_before_m15_h4_close(self):
        claims,receipts,sources=scenario()
        t=OneEventStudyJoinTests(methodName="test_integrated_synthetic_study_is_one_event_not_seven_trials")
        t.setUp();self.addCleanup(t.doCleanups)
        with synthetic_digest_fixture_lock(sources):
            r=run(claims,receipts,sources,now=PPI_RELEASE+timedelta(minutes=5),
                  packet=t.packet)
        self.safety(r)
        self.assertFalse(r["ppi_fx_price_study_originals_revalidated"])
        self.assertEqual(r["ppi_price_study_attachment_reason"],
                         "PPI_PRICES_OR_ACTUAL_NOT_VISIBLE_AT_CUTOFF")

    def test_19_end_to_end_price_study_must_revalidate_seven_source_csv(self):
        claims,receipts,sources=scenario()
        t=OneEventStudyJoinTests(methodName="test_integrated_synthetic_study_is_one_event_not_seven_trials")
        t.setUp();self.addCleanup(t.doCleanups)
        with synthetic_digest_fixture_lock(sources):
            with t.isolated_synthetic_pre_event_receipts():
                r=run(claims,receipts,sources,now=POST,packet=t.packet)
        self.safety(r)
        self.assertTrue(r["ppi_fx_price_study_originals_revalidated"])
        self.assertEqual(r["ppi_price_study_attachment_reason"],
                         "SEVEN_CORRELATED_PRICE_SERIES_ONE_EVENT_NO_FORECAST")
        self.assertEqual(r["ppi_correlated_fx_pairs_descriptively_observed"],7)
        self.assertEqual(r["ppi_reaction_economic_event_roots"],1)
        self.assertEqual(r["documentary_comparable_macro_surprise_events"],1)
        self.assertEqual(r["independent_tradable_prediction_trials"],0)

    def test_20_tamper_one_price_csv_blocks_full_attached_study(self):
        claims,receipts,sources=scenario()
        t=OneEventStudyJoinTests(methodName="test_integrated_synthetic_study_is_one_event_not_seven_trials")
        t.setUp();self.addCleanup(t.doCleanups)
        file=t.root/"EURUSD_PPI_20261113_M15.csv"
        file.write_bytes(file.read_bytes()+b"TAMPER")
        with synthetic_digest_fixture_lock(sources):
            with t.isolated_synthetic_pre_event_receipts():
                r=run(claims,receipts,sources,packet=t.packet)
        self.safety(r)
        self.assertFalse(r["ppi_fx_price_study_originals_revalidated"])
        self.assertEqual(r["ppi_price_study_attachment_reason"],
                         "PPI_ONE_EVENT_PRICE_SOURCE_REPLAY_NOT_ACCEPTED")

    def test_21_price_report_cannot_fill_cpi_missing_consensus(self):
        claims,receipts,sources=scenario()
        t=OneEventStudyJoinTests(methodName="test_integrated_synthetic_study_is_one_event_not_seven_trials")
        t.setUp();self.addCleanup(t.doCleanups)
        with synthetic_digest_fixture_lock(sources):
            with t.isolated_synthetic_pre_event_receipts():
                r=run(claims,receipts,sources,packet=t.packet)
        self.safety(r)
        self.assertFalse(r["event_roots"][0]["consensus_visible_in_original_claimed_time"])
        self.assertEqual(r["documentary_comparable_macro_surprise_events"],1)
        self.assertEqual(r["independent_tradable_prediction_trials"],0)

    def test_22_cad_calendar_unknown_still_confounded_event(self):
        claims,receipts,sources=scenario()
        t=OneEventStudyJoinTests(methodName="test_integrated_synthetic_study_is_one_event_not_seven_trials")
        t.setUp();self.addCleanup(t.doCleanups)
        with synthetic_digest_fixture_lock(sources):
            with t.isolated_synthetic_pre_event_receipts():
                r=run(claims,receipts,sources,packet=t.packet)
        self.safety(r)
        self.assertTrue(r["ppi_competing_release_risk_documentary"])
        self.assertFalse(r["ppi_exclusive_news_causality_established"])

    def test_23_ppi_reaction_seven_pairs_are_not_seven_forecast_trials(self):
        claims,receipts,sources=scenario()
        t=OneEventStudyJoinTests(methodName="test_integrated_synthetic_study_is_one_event_not_seven_trials")
        t.setUp();self.addCleanup(t.doCleanups)
        with synthetic_digest_fixture_lock(sources):
            with t.isolated_synthetic_pre_event_receipts():
                r=run(claims,receipts,sources,packet=t.packet)
        self.safety(r)
        self.assertEqual(r["ppi_reaction_economic_event_roots"],1)
        self.assertEqual(r["testable_out_of_sample_macro_event_count"],0)


if __name__ == "__main__":
    unittest.main()
