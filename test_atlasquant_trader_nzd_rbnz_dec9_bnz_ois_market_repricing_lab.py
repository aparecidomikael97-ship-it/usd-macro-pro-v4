"""Adversarial offline tests for three BNZ secondary OIS reports."""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
import unittest

from atlasquant_trader_nzd_rbnz_dec9_bnz_ois_market_repricing_lab import (
    EVENT_UTC, RESEARCH_SAFE_VISIBLE_FROM_UTC, SNAPSHOTS,
    inspect_bnz_reported_ocr_market_repricing_lab as inspect,
)

UTC=timezone.utc
NOW=datetime(2026,11,15,10,0,tzinfo=UTC)


class BnzMarketRepricingTests(unittest.TestCase):
    def safe(self,r):
        self.assertEqual(r["operational_bias"],"AGUARDAR")
        for field in (
            "trade_authorized","live_alert_allowed","publishable",
            "scheduler_enabled","worker_enabled",
            "pdf_document_raw_bytes_archived",
            "underlying_ois_quote_bytes_archived",
            "publisher_first_seen_utc_authenticated",
            "point_in_time_intraday_market_snapshot_authenticated",
            "immediate_pre_dec9_ois_quote_verified",
            "meeting_date_ois_contract_identity_verified",
            "relevant_pre_event_broker_fx_bid_ask_verified",
            "actual_dec9_ocr_verified",
        ):
            self.assertFalse(r[field],field)
        for field in (
            "actual_policy_surprise_basis_points",
            "calibrated_nzd_fx_probability","market_direction",
            "backtest_accuracy",
        ):
            self.assertIsNone(r[field])
        for flag in (
            "not_actual_ois_contract_quotes",
            "not_representative_economist_survey",
            "not_bank_forecast_hike_probability",
            "not_nzd_appreciation_probability",
            "not_exact_snapshot_market_close_times",
        ):
            self.assertTrue(r[flag],flag)
        self.assertEqual(r["unique_issuer_policy_event_roots"],1)
        self.assertEqual((r["http_requests"],r["file_writes"],
                          r["new_cost_brl"]),(0,0,0))

    def verified(self,when=NOW):
        r=inspect(as_of_utc=when)
        self.safe(r)
        self.assertEqual(
            r["state"],
            "LAB_RBNZ_SECONDARY_MARKET_REPRICING_RESEARCH_PRE_DEC9_NO_GO")
        self.assertEqual(r["source_report_count"],3)
        self.assertEqual(r["independent_source_publisher_count"],1)
        self.assertEqual(r["net_change_percentage_points_approx"],-20)
        self.assertEqual(r["difference_in_last_interval_pp_approx"],-15)
        return r

    def test_01_quote_timeline_85_80_65_approximate_not_live(self):
        r=self.verified()
        self.assertEqual(
            [x["reported_dec9_25bp_hike_probability_approx_pct"]
             for x in r["market_probability_snapshots"]],[85,80,65])
        self.assertEqual(
            [x["report_calendar_date_claim"]
             for x in r["market_probability_snapshots"]],
            ["2026-10-29","2026-11-02","2026-11-09"])

    def test_02_three_reports_not_three_independent_market_quotes(self):
        r=self.verified()
        self.assertEqual(r["source_report_count"],3)
        self.assertEqual(r["independent_source_publisher_count"],1)
        self.assertTrue(r["confidence_declined_while_bank_base_case_hike"])
        for x in r["market_probability_snapshots"]:
            self.assertEqual(x["meaning"],
                "APPROX_MEETING_HIKE_ODDS_REPORTED_FROM_OIS_PRICING")
            self.assertIsNone(x["publisher_document_sha256"])
            self.assertIsNone(x["quote_exact_time_in_original_market_feed"])
            self.assertFalse(x["pre_event_market_quote_bid_ask_or_settlement_verified"])
            self.assertTrue(x["not_fx_pair_probability"])

    def test_03_simple_binary_scenarios_never_actual_ois_or_fx(self):
        r=self.verified()
        s=r["conditional_binary_scenarios_only"]
        self.assertEqual(s["hypothetical_expected_change_basis_points"],"16.25")
        self.assertEqual(s["if_hike_25bp_surprise_basis_points_hypothetical"],
                         "8.75")
        self.assertEqual(s["if_hold_0bp_surprise_basis_points_hypothetical"],
                         "-16.25")
        self.assertTrue(s["market_quote_is_not_directly_observed"])
        self.assertTrue(s["scenario_is_not_actual_pre_meeting_ois_or_prediction"])
        self.assertTrue(s["cannot_be_used_for_fx_bias"])
        self.assertIsNone(r["actual_policy_surprise_basis_points"])

    def test_04_research_floor_disallows_fake_oct29_nov02_nov09_early_visibility(self):
        for when in (
            datetime(2026,10,29,10,0,tzinfo=UTC),
            datetime(2026,11,2,10,0,tzinfo=UTC),
            datetime(2026,11,9,10,0,tzinfo=UTC),
            RESEARCH_SAFE_VISIBLE_FROM_UTC-timedelta(seconds=1),
        ):
            with self.subTest(when=when):
                r=inspect(as_of_utc=when)
                self.safe(r)
                self.assertEqual(r["source_report_count"],0)
                self.assertEqual(
                    r["state"],"LAB_RBNZ_MARKET_REPRICING_INPUT_BLOCKED_NO_GO")

    def test_05_first_preflight_sunday_6am_cuiaba(self):
        r=self.verified(NOW)
        self.assertEqual(r["research_visible_floor_utc"],
                         "2026-11-15T00:00:00+00:00")
        self.assertTrue(r["not_exact_snapshot_market_close_times"])

    def test_06_one_second_before_dec9_event_allowed_only_as_scenario(self):
        r=self.verified(EVENT_UTC-timedelta(seconds=1))
        self.assertIsNotNone(r["conditional_binary_scenarios_only"])
        self.assertFalse(r["immediate_pre_dec9_ois_quote_verified"])

    def test_07_event_open_or_after_no_earlier_probability_as_event_surprise(self):
        for when in (EVENT_UTC, EVENT_UTC+timedelta(days=1)):
            with self.subTest(when=when):
                r=inspect(as_of_utc=when)
                self.safe(r)
                self.assertEqual(
                    r["state"],
                    "LAB_RBNZ_RESEARCH_AFTER_DEC9_CANNOT_BACKFILL_SURPRISE_NO_GO")
                self.assertIsNone(r["conditional_binary_scenarios_only"])
                self.assertIsNone(r["actual_policy_surprise_basis_points"])

    def test_08_invalid_clock_and_precision_blocked(self):
        for when in (None,"2026-11-15T10:00:00Z",
                     NOW.replace(tzinfo=None),
                     NOW+timedelta(microseconds=1)):
            with self.subTest(when=when):
                r=inspect(as_of_utc=when)
                self.safe(r)
                self.assertEqual(r["source_report_count"],0)

    def test_09_damaged_vintage_or_duplicate_pdf_blocks(self):
        cases=(
            (replace(SNAPSHOTS[0],report_day=SNAPSHOTS[1].report_day),)+SNAPSHOTS[1:],
            (replace(SNAPSHOTS[0],pdf_url=SNAPSHOTS[1].pdf_url),)+SNAPSHOTS[1:],
            (replace(SNAPSHOTS[0],pdf_url="https://www.bnz.co.nz.evil.test/report"),)+SNAPSHOTS[1:],
            (replace(SNAPSHOTS[0],page_one_indexed=True),)+SNAPSHOTS[1:],
            (replace(SNAPSHOTS[0],hike_probability_approx_pct=101),)+SNAPSHOTS[1:],
            (replace(SNAPSHOTS[0],comment="z"*200),)+SNAPSHOTS[1:],
        )
        for test in cases:
            with self.subTest(first=test[0]):
                r=inspect(as_of_utc=NOW,snapshots=test)
                self.safe(r)
                self.assertEqual(r["source_report_count"],0)

    def test_10_reversal_of_probability_or_update_without_source_blocks(self):
        for values in ((85,80,85),(80,80,65),(85,65,80)):
            altered=tuple(replace(item,hike_probability_approx_pct=values[i])
                          for i,item in enumerate(SNAPSHOTS))
            r=inspect(as_of_utc=NOW,snapshots=altered)
            self.safe(r)
            self.assertEqual(r["reason"],
                             "MARKET_PROBABILITY_SOURCE_VINTAGE_MISMATCH")

    def test_11_more_or_fewer_snapshots_not_claimed_as_more_evidence(self):
        for snaps in ((),SNAPSHOTS[:2],SNAPSHOTS+(SNAPSHOTS[0],),
                      list(SNAPSHOTS)):
            r=inspect(as_of_utc=NOW,snapshots=snaps)
            self.safe(r)
            self.assertEqual(r["source_report_count"],0)

    def test_12_not_confuse_nov09_market_prob_with_oct_decision_95(self):
        r=self.verified()
        self.assertTrue(r["retrospective_october_95pct_hike_was_not_guarantee"])
        self.assertEqual(
            r["market_probability_snapshots"][-1][
                "reported_dec9_25bp_hike_probability_approx_pct"],65)
        self.assertFalse(r["actual_dec9_ocr_verified"])

    def test_13_bnz_report_underlying_bloomberg_not_dba_licensed_feed(self):
        r=self.verified()
        self.assertIn("BLOOMBERG",r["underlying_quote_provider_claim_not_relicensed"])
        self.assertFalse(r["underlying_ois_quote_bytes_archived"])
        self.assertFalse(r["publisher_first_seen_utc_authenticated"])

    def test_14_no_28_independent_pair_macro_predictions_from_one_event(self):
        r=self.verified()
        self.assertEqual(r["unique_issuer_policy_event_roots"],1)
        self.assertFalse(r["trade_authorized"])
        self.assertIsNone(r["calibrated_nzd_fx_probability"])
        self.assertIsNone(r["market_direction"])


if __name__=="__main__":
    unittest.main()
