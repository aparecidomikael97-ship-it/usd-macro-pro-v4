"""Official Focus 2026-10-23 PDF documentary medians, no live inference."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import unittest

from atlasquant_trader_brazil_focus_documentary_lab import (
    SCHEMA, MEDIANS, build_brazil_focus_documentary_lab,
)

AT = datetime(2026, 11, 3, 12, tzinfo=timezone.utc)


def build(at=AT, observations=None):
    return build_brazil_focus_documentary_lab(at=at, observations=observations)


def metric(indicator, target_type, period):
    return next(x for x in build()["focus_rows"]
                if x["indicator"] == indicator and
                x["target_type"] == target_type and
                x["target_period"] == period)


def index(instrument, horizon="W1", at=AT):
    return next(x for x in build(at)["win_wdo_horizons"]
                if x["instrument"] == instrument and x["horizon"] == horizon)


class BrazilFocusDocumentaryTests(unittest.TestCase):
    def test_schema_and_no_trade_documentary_state(self):
        x = build()
        self.assertEqual(x["schema"], SCHEMA)
        self.assertEqual(x["state"], "LAB_FOCUS_PRIOR_PDF_NOT_A_FX_FORECAST")

    def test_nine_distinct_focus_reference_medians(self):
        self.assertEqual(len(MEDIANS), 9)
        self.assertEqual(build()["focus_row_count"], 9)
        keys = {(x["indicator"], x["target_type"], x["target_period"])
                for x in MEDIANS}
        self.assertEqual(len(keys), 9)

    def test_official_focus_source_reference_date(self):
        x = build()
        self.assertEqual(x["focus_reference_date"], "2026-10-23")
        self.assertEqual(x["focus_published_on"], "2026-10-26")
        self.assertTrue(x["focus_pdf_url"].endswith("/R20261023.pdf"))

    def test_ipca_year_2026_519_from_official_pdf(self):
        self.assertEqual(metric("IPCA", "CALENDAR_YEAR_CHANGE",
                                "2026")["median_value"], "5.19")

    def test_ipca_year_2027_434_not_same_year(self):
        self.assertEqual(metric("IPCA", "CALENDAR_YEAR_CHANGE",
                                "2027")["median_value"], "4.34")

    def test_selic_endyear_2026_1325(self):
        self.assertEqual(metric("SELIC", "YEAR_END_POLICY_TARGET",
                                "2026")["median_value"], "13.25")

    def test_selic_november_end_month_1350(self):
        self.assertEqual(metric("SELIC", "MONTH_END_POLICY_TARGET",
                                "2026-11")["median_value"], "13.50")

    def test_month_end_is_not_year_end(self):
        a = metric("SELIC", "YEAR_END_POLICY_TARGET", "2026")
        b = metric("SELIC", "MONTH_END_POLICY_TARGET", "2026-11")
        self.assertNotEqual(a["median_value"], b["median_value"])
        self.assertNotEqual(a["target_type"], b["target_type"])

    def test_selic_endyear_2027_1175(self):
        self.assertEqual(metric("SELIC", "YEAR_END_POLICY_TARGET",
                                "2027")["median_value"], "11.75")

    def test_fx_brl_usd_is_december_reference_not_spot(self):
        a = metric("FX_BRL_PER_USD", "DECEMBER_AVERAGE_FX", "2026")
        self.assertEqual(a["median_value"], "5.05")
        self.assertEqual(a["value_unit"], "BRL_PER_USD")
        self.assertNotIn("spot", a["note"].lower().split()[:2])

    def test_fx_2027_expectation_is_different_year(self):
        self.assertEqual(metric("FX_BRL_PER_USD", "DECEMBER_AVERAGE_FX",
                                "2027")["median_value"], "5.15")

    def test_gdp_calendar_year_not_q2_actual(self):
        a = metric("REAL_GDP", "CALENDAR_YEAR_CHANGE", "2026")
        b = metric("REAL_GDP", "CALENDAR_YEAR_CHANGE", "2027")
        self.assertEqual((a["median_value"], b["median_value"]),
                         ("1.80", "1.31"))

    def test_all_report_values_marked_same_origin(self):
        self.assertTrue(all(x["source_reference"] == "2026-10-23" for x in MEDIANS))
        self.assertTrue(all(x["source_published_on"] == "2026-10-26"
                            for x in MEDIANS))
        self.assertEqual(len({x["source_url"] for x in MEDIANS}), 1)

    def test_new_scheduled_focus_review_always_required_on_nov3(self):
        x = build()
        self.assertEqual(x["focus_freshness"],
                         "NEW_SCHEDULED_FOCUS_RELEASE_REQUIRES_OFFICIAL_PDF_REVIEW")
        self.assertEqual(x["new_focus_release_day"], "2026-11-03")
        self.assertFalse(x["new_focus_release_numeric_values_verified"])

    def test_old_focus_not_labeled_latest(self):
        x = build()
        self.assertFalse(x["last_verified_document_is_most_recent"])
        self.assertIsNone(x["focus_pdf_content_sha256"])
        self.assertFalse(x["source_original_pdf_bytes_archived"])
        self.assertFalse(x["source_original_pdf_signature_verified"])

    def test_new_focus_release_remains_unverified_after_date(self):
        future = build(datetime(2026, 11, 5, 12, tzinfo=timezone.utc))
        self.assertFalse(future["new_focus_release_numeric_values_verified"])
        self.assertEqual(future["focus_reference_date"], "2026-10-23")

    def test_six_win_wdo_horizons_remain(self):
        x = build()
        self.assertEqual(x["index_horizon_count"], 6)
        self.assertEqual({(r["instrument"], r["horizon"])
                          for r in x["win_wdo_horizons"]},
                         {(s, h) for s in ("WIN", "WDO")
                          for h in ("D1", "W1", "MN1")})

    def test_domestic_actuals_and_survey_differ(self):
        r = index("WIN")
        self.assertEqual(r["brazil_actuals"]["SELIC_TARGET_20260916"]
                         ["value_pct"], "13.75")
        self.assertEqual(metric("SELIC", "YEAR_END_POLICY_TARGET",
                                "2026")["median_value"], "13.25")

    def test_copom_upcoming_and_nfp_us_separate(self):
        r = index("WDO")
        self.assertTrue(any(x["event_id"] == "COPOM_DECISION_20261104"
                            for x in r["brazil_upcoming_events"]))
        self.assertTrue(any(x["event_id"] == "BLS_US_EMPLOYMENT_20261106"
                            for x in r["usd_upcoming_events"]))

    def test_not_convert_month_end_to_copom_consensus(self):
        for r in build()["win_wdo_horizons"]:
            self.assertIsNone(r["next_copom_meeting_decision_consensus_pct"])
            self.assertIsNone(r["next_copom_cut_probability"])
            self.assertFalse(r["newer_focus_report_verified"])

    def test_no_direction_or_probability_for_indices(self):
        for r in build()["win_wdo_horizons"]:
            self.assertEqual(r["directional_bias"], "AGUARDAR")
            self.assertIsNone(r["probability_calibrated"])
            self.assertFalse(r["trade_authorized"])

    def test_no_operational_state_promoted(self):
        x = build()
        for key in (
            "market_priced_brazil_expectations_verified",
            "pre_meeting_consensus_verified",
            "directional_accuracy_oos_proven", "accuracy_90_proven",
            "can_feed_live_radar", "trade_authorized", "worker_enabled",
            "scheduler_enabled",
        ):
            self.assertFalse(x[key], key)

    def test_reject_wrong_doc_number(self):
        rows = deepcopy(list(MEDIANS))
        rows[2]["median_value"] = "13.50"
        with self.assertRaises(ValueError):
            build(observations=rows)

    def test_reject_wrong_report_origin(self):
        rows = deepcopy(list(MEDIANS))
        rows[0]["source_url"] = "https://www.bcb.gov.br.attacker.invalid"
        with self.assertRaises(ValueError):
            build(observations=rows)

    def test_reject_injected_live_signal_field(self):
        rows = deepcopy(list(MEDIANS))
        rows[1]["buy_wdo"] = True
        with self.assertRaises(ValueError):
            build(observations=rows)

    def test_reject_mistagging_monthly_as_yearly(self):
        rows = deepcopy(list(MEDIANS))
        rows[8]["target_type"] = "YEAR_END_POLICY_TARGET"
        with self.assertRaises(ValueError):
            build(observations=rows)

    def test_reject_missing_median(self):
        rows = deepcopy(list(MEDIANS))[:-1]
        with self.assertRaises(ValueError):
            build(observations=rows)

    def test_reject_extra_median(self):
        rows = deepcopy(list(MEDIANS)) + [deepcopy(MEDIANS[0])]
        with self.assertRaises(ValueError):
            build(observations=rows)

    def test_research_before_nov3_blocked(self):
        with self.assertRaises(ValueError):
            build(at=datetime(2026, 11, 2, 23, 59, tzinfo=timezone.utc))

    def test_naive_clock_rejected(self):
        with self.assertRaises(ValueError):
            build(at=datetime(2026, 11, 3, 12))

    def test_timezone_normalized(self):
        at = datetime(2026, 11, 3, 8, tzinfo=timezone(timedelta(hours=-4)))
        self.assertEqual(build(at)["as_of_utc"], AT.isoformat())

    def test_no_requests_or_worker_interface(self):
        import atlasquant_trader_brazil_focus_documentary_lab as module
        self.assertFalse(hasattr(module, "requests"))
        self.assertFalse(hasattr(module, "run_worker"))
