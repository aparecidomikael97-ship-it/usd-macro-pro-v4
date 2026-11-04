"""LAB documentary prior readings for GBP/USD events: no prediction."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import unittest

from atlasquant_fx_universe import OFFICIAL_PAIRS, CURRENCIES
from atlasquant_trader_pre_event_fundamentals_lab import (
    PRIOR_PUBLICATIONS, SCHEMA, build_pre_event_fundamentals_lab,
)

BASE = datetime(2026, 11, 3, 16, tzinfo=timezone.utc)


def build(at=BASE, observations=None):
    return build_pre_event_fundamentals_lab(at=at, observations=observations)


def event(report, eid):
    return next(x for x in report["events"] if x["event_id"] == eid)


def pair(report, name):
    return next(x for x in report["pair_comparisons"] if x["pair"] == name)


class PriorFundamentalsTests(unittest.TestCase):
    def test_documentary_state_and_six_measurements(self):
        report = build()
        self.assertEqual(report["schema"], SCHEMA)
        self.assertEqual(report["state"], "LAB_OFFICIAL_PRIOR_FACTS_UNATTESTED")
        self.assertEqual(report["historical_measure_count"], 6)

    def test_28_pair_matrix_complete(self):
        report = build()
        self.assertEqual(report["pair_count"], 28)
        self.assertEqual({x["pair"] for x in report["pair_comparisons"]},
                         set(OFFICIAL_PAIRS))

    def test_all_eight_currencies_keys_and_only_two_evidenced(self):
        report = build()
        self.assertEqual(set(report["currency_evidence"]), set(CURRENCIES))
        nonempty = {c for c, rows in report["currency_evidence"].items() if rows}
        self.assertEqual(nonempty, {"GBP", "USD"})

    def test_usd_has_five_prior_measures(self):
        self.assertEqual(len(build()["currency_evidence"]["USD"]), 5)

    def test_gbp_has_one_prior_measure(self):
        self.assertEqual(len(build()["currency_evidence"]["GBP"]), 1)

    def test_old_boe_policy_rate_september_375(self):
        row = build()["currency_evidence"]["GBP"][0]
        self.assertEqual((row["indicator_id"], row["value"], row["unit"]),
                         ("POLICY_RATE", "3.75", "PERCENT"))
        self.assertEqual(row["source_published_on"], "2026-09-17")
        self.assertEqual(row["reference_period"], "2026-09")

    def test_previous_nfp_and_unemployment_are_distinct(self):
        rows = event(build(), "BLS_US_EMPLOYMENT_20261106")["prior_observations"]
        self.assertEqual({(r["measure"], r["value"]) for r in rows},
                         {("PAYROLL_MONTHLY_CHANGE", "29"),
                          ("U3_UNEMPLOYMENT_RATE", "4.2")})

    def test_nfp_thousands_not_percent(self):
        rows = event(build(), "BLS_US_EMPLOYMENT_20261106")["prior_observations"]
        self.assertEqual(next(x["unit"] for x in rows if x["indicator_id"] == "NFP"),
                         "THOUSANDS")

    def test_september_cpi_monthly_yearly_core_separate(self):
        rows = event(build(), "BLS_US_CPI_20261110")["prior_observations"]
        self.assertEqual({(r["measure"], r["value"]) for r in rows},
                         {("HEADLINE_CPI_SA_MOM", "0.6"),
                          ("HEADLINE_CPI_NSA_YOY", "3.7"),
                          ("CORE_CPI_SA_MOM", "0.3")})

    def test_three_upcoming_events_have_prior_context_before_nov5(self):
        report = build()
        self.assertEqual(len(report["events"]), 3)
        self.assertTrue(all(x["event_state"] == "PRIOR_CONTEXT_FOR_FUTURE_EVENT"
                            for x in report["events"]))

    def test_boe_day_forces_refresh_without_actual_invention(self):
        report = build(at=datetime(2026, 11, 5, 15, tzinfo=timezone.utc))
        row = event(report, "BOE_MPC_20261105")
        self.assertEqual(row["event_state"],
                         "DATE_ONLY_OR_RELEASE_TIME_IN_PROGRESS_REFRESH_REQUIRED")
        self.assertFalse(row["current_event_actual_available"])

    def test_boe_later_day_requires_new_release(self):
        report = build(at=datetime(2026, 11, 6, 0, tzinfo=timezone.utc))
        row = event(report, "BOE_MPC_20261105")
        self.assertEqual(row["event_state"], "EVENT_TIME_PASSED_NEW_RELEASE_REQUIRED")

    def test_nfp_exact_minute_requires_refresh(self):
        report = build(at=datetime(2026, 11, 6, 13, 30, tzinfo=timezone.utc))
        row = event(report, "BLS_US_EMPLOYMENT_20261106")
        self.assertEqual(row["event_state"],
                         "DATE_ONLY_OR_RELEASE_TIME_IN_PROGRESS_REFRESH_REQUIRED")
        self.assertFalse(row["surprise_available"])

    def test_nfp_after_scheduled_minute_requires_new_actual(self):
        report = build(at=datetime(2026, 11, 6, 13, 31, tzinfo=timezone.utc))
        row = event(report, "BLS_US_EMPLOYMENT_20261106")
        self.assertEqual(row["event_state"], "EVENT_TIME_PASSED_NEW_RELEASE_REQUIRED")

    def test_cpi_after_nov10_requires_new_actual(self):
        report = build(at=datetime(2026, 11, 10, 13, 31, tzinfo=timezone.utc))
        row = event(report, "BLS_US_CPI_20261110")
        self.assertEqual(row["event_state"], "EVENT_TIME_PASSED_NEW_RELEASE_REQUIRED")

    def test_after_event_does_not_falsely_relabel_prior_as_new(self):
        report = build(at=datetime(2026, 11, 12, 12, tzinfo=timezone.utc))
        for row in report["events"]:
            with self.subTest(event=row["event_id"]):
                self.assertFalse(row["current_event_actual_available"])
                self.assertFalse(row["current_event_consensus_available"])
                self.assertFalse(row["surprise_available"])
                self.assertEqual(row["fx_direction"], "AGUARDAR")

    def test_gbpusd_not_comparable_despite_both_currencies_evidenced(self):
        row = pair(build(), "GBP/USD")
        self.assertEqual((row["base_prior_series_count"], row["quote_prior_series_count"]),
                         (1, 5))
        self.assertEqual(row["comparison_state"],
                         "HETEROGENEOUS_SERIES_NO_COMPARABLE_DIFFERENTIAL")
        self.assertEqual(row["bias"], "AGUARDAR")

    def test_euraud_has_no_prior_series_in_this_pilot(self):
        row = pair(build(), "EUR/AUD")
        self.assertEqual((row["base_prior_series_count"], row["quote_prior_series_count"]),
                         (0, 0))

    def test_no_probability_for_any_pair(self):
        for row in build()["pair_comparisons"]:
            self.assertIsNone(row["direction_probability"])
            self.assertFalse(row["trade_authorized"])

    def test_official_archive_urls_exact_not_bare_claim(self):
        rows = build()["currency_evidence"]
        self.assertEqual(rows["GBP"][0]["source_url"],
                         "https://www.bankofengland.co.uk/monetary-policy-summary-and-minutes/2026/september-2026")
        self.assertEqual({r["source_url"] for r in rows["USD"]},
                         {"https://www.bls.gov/news.release/archives/empsit_10022026.htm",
                          "https://www.bls.gov/news.release/archives/cpi_10142026.htm"})

    def test_research_date_cannot_be_backdated(self):
        with self.assertRaises(ValueError):
            build(at=datetime(2026, 11, 2, 23, 59, tzinfo=timezone.utc))

    def test_naive_datetime_rejected(self):
        with self.assertRaises(ValueError):
            build(at=datetime(2026, 11, 3, 16))

    def test_wrong_type_datetime_rejected(self):
        with self.assertRaises(ValueError):
            build(at="2026-11-03T16:00:00Z")

    def test_offset_time_normalized_to_utc(self):
        offset = timezone(timedelta(hours=-4))
        report = build(at=datetime(2026, 11, 3, 12, tzinfo=offset))
        self.assertEqual(report["as_of_utc"], BASE.isoformat())

    def test_exact_canonical_copied_records_accepted(self):
        self.assertEqual(build(observations=deepcopy(list(PRIOR_PUBLICATIONS))), build())

    def test_extra_fake_probability_field_rejected(self):
        altered = deepcopy(list(PRIOR_PUBLICATIONS))
        altered[0]["confidence_pct"] = 90
        with self.assertRaises(ValueError):
            build(observations=altered)

    def test_edited_cpi_value_rejected(self):
        altered = deepcopy(list(PRIOR_PUBLICATIONS))
        altered[3]["value"] = "0.9"
        with self.assertRaises(ValueError):
            build(observations=altered)

    def test_wrong_monthly_yearly_measure_rejected(self):
        altered = deepcopy(list(PRIOR_PUBLICATIONS))
        altered[4]["measure"] = "HEADLINE_CPI_SA_MOM"
        with self.assertRaises(ValueError):
            build(observations=altered)

    def test_fake_source_url_rejected(self):
        altered = deepcopy(list(PRIOR_PUBLICATIONS))
        altered[2]["source_url"] = "https://www.bls.gov.attack.test/news.release/archives/empsit_10022026.htm"
        with self.assertRaises(ValueError):
            build(observations=altered)

    def test_manipulated_publication_date_rejected(self):
        altered = deepcopy(list(PRIOR_PUBLICATIONS))
        altered[0]["source_published_on"] = "2026-11-05"
        with self.assertRaises(ValueError):
            build(observations=altered)

    def test_missing_or_duplicate_rows_rejected(self):
        with self.assertRaises(ValueError):
            build(observations=list(PRIOR_PUBLICATIONS)[:-1])
        altered = deepcopy(list(PRIOR_PUBLICATIONS))
        altered[1] = altered[0]
        with self.assertRaises(ValueError):
            build(observations=altered)

    def test_untrusted_input_wrong_shapes_rejected(self):
        with self.assertRaises(ValueError):
            build(observations="source")
        with self.assertRaises(ValueError):
            build(observations=[None] * 6)

    def test_six_measurements_never_imply_real_fx_predictive_power(self):
        report = build()
        for name in ("original_source_bytes_archived",
                     "source_capture_independently_attested",
                     "source_live_refreshed", "full_g8_macro_coverage",
                     "upcoming_consensus_verified", "upcoming_actual_verified",
                     "economic_surprise_calculated",
                     "relative_currency_strength_inferred",
                     "real_oos_accuracy_proven", "accuracy_90_proven",
                     "can_feed_live_radar", "trade_authorized",
                     "worker_enabled", "scheduler_enabled"):
            with self.subTest(flag=name):
                self.assertIs(report[name], False)

    def test_no_fvg_ob_bos_or_technical_direction_required(self):
        report = build()
        self.assertEqual(report["state"], "LAB_OFFICIAL_PRIOR_FACTS_UNATTESTED")
        self.assertFalse(report["relative_currency_strength_inferred"])


if __name__ == "__main__":
    unittest.main()
