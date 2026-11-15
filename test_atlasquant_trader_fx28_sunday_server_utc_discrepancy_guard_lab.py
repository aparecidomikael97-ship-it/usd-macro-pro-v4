"""No live MT5 or web. Three historical caller claims only, DST adversarial."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import unittest

from test_atlasquant_trader_fx28_sunday_open_research_protocol_lab import (
    historical_fixture,
)
from atlasquant_trader_fx28_sunday_server_utc_discrepancy_guard_lab import (
    inspect_fx28_sunday_server_utc_discrepancy_lab as audit,
    PEPPERSTONE_HOURS_URL, METAQUOTES_API_URL,
)

UTC = timezone.utc
ASOF = datetime(2026,11,15,23,40,tzinfo=UTC)


class SundayFx28ServerUtcP0Tests(unittest.TestCase):
    def check(self, history=None, at=ASOF):
        return audit(
            historical_sunday_summaries=(
                historical_fixture() if history is None else history),
            inspected_at_utc=at)

    def safe(self, out):
        self.assertFalse(out["actual_time_axis_shift_independently_proven"])
        self.assertFalse(out["true_broker_open_time_independently_proven"])
        self.assertFalse(out["mt5_epoch_values_independently_attested"])
        self.assertFalse(out["proven_api_time_conversion_error"])
        for key in (
            "missing_20261115_bar_backfilled",
            "original_672_campaign_slots_modified",
            "clock_rewrite_allowed","historical_accuracy_validated",
            "trade_authorized","publishable","scheduler_enabled"):
            self.assertFalse(out[key],key)
        self.assertEqual((out["http_requests"],out["mt5_calls"],
                          out["file_writes"],out["new_cost_brl"]),(0,0,0,0))
        self.assertIsNone(out["validated_directional_accuracy"])
        self.assertEqual(out["operational_bias"],"AGUARDAR")
        self.assertEqual(out["source_urls"],[
            PEPPERSTONE_HOURS_URL,METAQUOTES_API_URL])

    def test_01_all_3_historical_minimum_lags_match_server_offsets(self):
        r=self.check()
        self.safe(r)
        self.assertEqual(
            r["state"],"LAB_FX28_SUNDAY_SERVER_OFFSET_ALIGNED_TIME_AXIS_P0_NO_GO")
        self.assertEqual(r["historical_sundays_valid"],3)
        self.assertEqual(r["historical_pair_series"],84)
        self.assertEqual(r["observed_historical_nominal_m15_bars"],0)
        self.assertEqual(r["weeks_with_min_lag_equal_published_server_offset"],3)
        self.assertTrue(r["all_minimum_lags_match_server_offset"])
        self.assertEqual([i["published_server_offset_hours"]
                         for i in r["clock_discrepancy_cases"]],[3,2,2])
        self.assertEqual([i["first_historical_bar_lag_min_claim_only"]
                         for i in r["clock_discrepancy_cases"]],[180,120,120])
        self.assertEqual([i["published_first_fx_minute_at_nominal_plus_seconds"]
                         for i in r["clock_discrepancy_cases"]],[60]*3)
        self.assertTrue(all(i["pseudoutc_hypothesis_is_unverified"]
                            for i in r["clock_discrepancy_cases"]))

    def test_02_oct25_summer_dst_ny17_21z(self):
        r=self.check()["clock_discrepancy_cases"][0]
        self.assertEqual(r["nominal_new_york_17_utc"],"2026-10-25T21:00:00+00:00")
        self.assertEqual(r["derived_pseudoutc_server_midnight_hypothesis_at_utc"],
                         "2026-10-26T00:00:00+00:00")

    def test_03_nov01_us_dst_end_changes_server_offset_3_to_2(self):
        r=self.check()["clock_discrepancy_cases"][1]
        self.assertEqual(r["nominal_new_york_17_utc"],"2026-11-01T22:00:00+00:00")
        self.assertEqual(r["published_server_offset_hours"],2)
        self.assertEqual(r["derived_pseudoutc_server_midnight_hypothesis_at_utc"],
                         "2026-11-02T00:00:00+00:00")

    def test_04_nov08_still_winter_gmt2(self):
        r=self.check()["clock_discrepancy_cases"][2]
        self.assertEqual(r["published_server_offset_hours"],2)

    def test_05_one_historical_lag_minimum_135_flags_mixed_not_silent_fix(self):
        x=historical_fixture()
        d=x[1]["first_actual_m15_lag_minute_distribution"]
        d["135"]+=d.pop("120")
        x[1]["min_observed_lag_min"]=135
        r=self.check(x)
        self.safe(r)
        self.assertEqual(r["state"],
                         "LAB_FX28_SUNDAY_SERVER_OFFSET_MIXED_HISTORY_P0_NO_GO")
        self.assertEqual(r["weeks_with_min_lag_equal_published_server_offset"],2)
        self.assertFalse(r["all_minimum_lags_match_server_offset"])

    def test_06_spoofed_oct25_ny17_22z_rejected_not_rewritten(self):
        x=historical_fixture()
        x[0]["frozen_start_utc_in_sample"]="2026-10-25T22:00:00+00:00"
        r=self.check(x)
        self.safe(r)
        self.assertEqual(r["reason"],
                         "THREE_WEEK_HISTORICAL_DATA_UNVERIFIED_OR_INCOMPLETE")

    def test_07_forecast_period_original_20261115_no_future_recompute(self):
        self.assertTrue(self.check()["original_672_campaign_slots_modified"] is False)

    def test_08_mt5_none_must_not_be_m15_absent(self):
        x=historical_fixture()
        x[0]["mt5_api_none_count"]=1
        r=self.check(x)
        self.safe(r)
        self.assertEqual(r["reason"],
                         "THREE_WEEK_HISTORICAL_DATA_UNVERIFIED_OR_INCOMPLETE")

    def test_09_historical_series_not_28_is_blocked(self):
        x=historical_fixture()
        x[1]["valid_nonempty_series_count"]=27
        r=self.check(x)
        self.safe(r)
        self.assertEqual(r["historical_sundays_valid"],0)

    def test_10_wrong_histogram_count_blocked(self):
        x=historical_fixture()
        x[2]["first_actual_m15_lag_minute_distribution"]["120"]+=1
        self.assertEqual(self.check(x)["state"],
            "LAB_FX28_SUNDAY_SERVER_UTC_DISCREPANCY_BLOCKED_NO_GO")

    def test_11_missing_two_or_duplicate_week_not_valid(self):
        x=historical_fixture()
        self.assertEqual(self.check(x[:2])["historical_sundays_valid"],0)
        x[1]=deepcopy(x[0])
        self.assertEqual(self.check(x)["historical_sundays_valid"],0)

    def test_12_naive_time_is_blocked(self):
        r=self.check(at=datetime(2026,11,15,23,40))
        self.safe(r)
        self.assertEqual(r["state"],
                         "LAB_FX28_SUNDAY_SERVER_UTC_DISCREPANCY_BLOCKED_NO_GO")

    def test_13_inspection_before_frozen_week_blocked(self):
        r=self.check(at=datetime(2026,11,15,21,tzinfo=UTC))
        self.safe(r)
        self.assertEqual(r["historical_sundays_valid"],0)

    def test_14_microseconds_not_accepted_as_trusted_clock(self):
        r=self.check(at=ASOF+timedelta(microseconds=1))
        self.safe(r)
        self.assertEqual(r["state"],
                         "LAB_FX28_SUNDAY_SERVER_UTC_DISCREPANCY_BLOCKED_NO_GO")

    def test_15_no_forecast_price_source_accuracy_even_if_3_of_3_match(self):
        r=self.check()
        self.safe(r)
        self.assertTrue(
            r["official_pages_are_documentary_not_broker_account_attestation"])
        self.assertTrue(r["mt5_copy_rates_range_documentation_says_utc"])
        self.assertFalse(r["true_broker_open_time_independently_proven"])


if __name__=="__main__":
    unittest.main(verbosity=2)
