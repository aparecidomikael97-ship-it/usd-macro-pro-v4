"""BLS missing October 2025 YoY baseline and Reuters monthly poll: no false surprise."""
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
import unittest

from atlasquant_fx_universe import OFFICIAL_PAIRS
from atlasquant_trader_us_oct2026_cpi_metric_availability_consensus_lab import (
    PINNED_RECEIPT_SHA256,
    inspect_us_oct2026_cpi_metric_availability_consensus_lab as inspect,
)

DOCS = Path(__file__).resolve().parent / "docs" / "continuidade"
FILES = {
    "five": "TRADER_G8_OCT2026_FIVE_OFFICIAL_NEXT_CPI_CALENDAR_LAB_20261106.json",
    "three": "TRADER_G8_JPY_CHF_NZD_NEXT_CPI_SCHEDULES_LAB_20261106.json",
    "eurusd": "TRADER_EURUSD_20261106_FOUR_OFFICIAL_DOCUMENTS_ASOF_CASE_LAB.json",
    "gbpjpy": "TRADER_GBPJPY_20261106_FOUR_OFFICIAL_DOCUMENTS_ASOF_CASE_LAB.json",
    "other": "TRADER_G8_CHF_AUD_CAD_NZD_20261106_OFFICIAL_ASOF_CASE_LAB.json",
    "oct": "TRADER_US_OCT2026_CLEVELANDFED_FORWARD_NOWCAST_RECEIPT_20261106.json",
    "nov": "TRADER_US_NOV2026_CLEVELANDFED_EARLY_NOWCAST_RECEIPT_20261106.json",
    "surveys": "TRADER_EURUSD_SEP2026_EXPECTATIONS_MISMATCH_LAB_20261106.json",
    "policy": "TRADER_EURUSD_POLICY_DECISIONS_SEPOCT2026_LAB_20261106.json",
    "cpi": "TRADER_EURUSD_SEP2026_OFFICIAL_HEADLINE_CONTEXT_LAB_20261106.json",
    "metric": "TRADER_US_OCT2026_CPI_MOM_YOY_METRIC_AVAILABILITY_CONSENSUS_LAB_20261106.json",
}
DATA = {key: (DOCS / name).read_bytes() for key, name in FILES.items()}


def at(y, m, d, h=0, minute=0):
    return datetime(y, m, d, h, minute, tzinfo=timezone.utc)


class USOctoberCpiMetricAvailabilityTests(unittest.TestCase):
    def case(self, when=at(2026, 11, 7), **override):
        data = {**DATA, **override}
        return inspect(
            five_calendar_casebook_raw=data["five"],
            three_calendar_casebook_raw=data["three"],
            eurusd_macro_casebook_raw=data["eurusd"],
            gbpjpy_macro_casebook_raw=data["gbpjpy"],
            remaining_four_macro_casebook_raw=data["other"],
            october_us_model_receipt_raw=data["oct"],
            november_us_model_receipt_raw=data["nov"],
            survey_expectations_casebook_raw=data["surveys"],
            september_policy_casebook_raw=data["policy"],
            september_cpi_casebook_raw=data["cpi"],
            oct2026_metric_receipt_raw=data["metric"],
            as_of_utc=when,
        )

    def assert_guard(self, report):
        for field in ("oct2026_headline_yoy_model_usable_for_actual_surprise",
                      "source_original_bytes_independently_attested",
                      "pre_event_poll_collection_time_witnessed", "can_feed_live_radar",
                      "trade_authorized", "publishable", "worker_enabled",
                      "scheduler_enabled"):
            self.assertFalse(report[field], field)
        for field in ("oct2026_headline_mom_verified_point_in_time_consensus",
                      "oct2026_headline_mom_official_actual",
                      "oct2026_headline_yoy_official_actual",
                      "oct2026_headline_mom_surprise",
                      "oct2026_headline_yoy_surprise", "validated_accuracy",
                      "best_pair_of_day", "fx_bias"):
            self.assertIsNone(report[field], field)
        self.assertEqual(report["operational_bias"], "AGUARDAR")
        self.assertEqual(report["ranked_currencies"], [])
        self.assertEqual((report["http_requests"], report["new_cost_brl"]), (0, 0))
        self.assertEqual(report["validated_forward_prediction_count"], 0)
        for row in report["pair_rows"]:
            self.assertEqual((row["D1"], row["W1"]), ("AGUARDAR", "AGUARDAR"))
            self.assertFalse(row["trade_authorized"])
            self.assertFalse(row["oct2026_us_cpi_mom_consensus_verified"])
            self.assertFalse(row["oct2026_us_cpi_yoy_nowcast_matches_publishable_bls_metric"])
            for name in ("oct2026_us_cpi_mom_actual", "oct2026_us_cpi_mom_surprise",
                         "oct2026_us_cpi_yoy_surprise", "relative_macro_score", "fx_bias"):
                self.assertIsNone(row[name])

    def test_receipt_pinned_to_exact_bytes(self):
        self.assertEqual(sha256(DATA["metric"]).hexdigest(), PINNED_RECEIPT_SHA256)

    def test_all_28_pairs_and_exactly_seven_usd_exposures(self):
        report = self.case()
        self.assertEqual(report["state"],
                         "LAB_US_OCT2026_YOY_NOT_PUBLISHABLE_MOM_POLL_UNATTESTED_NO_FX_BIAS")
        self.assertEqual((report["pair_count"], report["usd_pair_count"],
                          report["non_usd_pair_count"]), (28, 7, 21))
        self.assertEqual({r["pair"] for r in report["pair_rows"]}, set(OFFICIAL_PAIRS))
        self.assert_guard(report)

    def test_october_yoy_cannot_use_missing_2025_index(self):
        report = self.case()
        self.assertIs(report["oct2026_headline_yoy_bls_publishable"], False)
        usd = [r for r in report["pair_rows"] if r["us_currency_role"]]
        self.assertEqual(len(usd), 7)
        for r in usd:
            self.assertEqual(r["oct2026_us_cpi_yoy_metric_status"],
                             "BLS_HEADLINE_YOY_UNAVAILABLE_MISSING_OCT2025_INDEX")
            self.assertIn("NO_OCT2025_US_ALL_ITEMS_CPI_INDEX_FOR_OCT2026_YOY",
                          r["missing_prerequisites"])
        self.assert_guard(report)

    def test_mom_0_3_consensus_candidate_is_not_verified(self):
        report = self.case()
        self.assertEqual(report["oct2026_headline_mom_reported_poll_percent_document_only"],
                         "0.3")
        rows = {r["pair"]: r for r in report["pair_rows"]}
        self.assertEqual(rows["GBP/USD"]["us_currency_role"], "QUOTE")
        self.assertEqual(rows["USD/JPY"]["us_currency_role"], "BASE")
        self.assertEqual(rows["USD/JPY"]["oct2026_us_cpi_mom_reported_consensus_percent_document_only"],
                         "0.3")
        self.assertIsNone(report["oct2026_headline_mom_verified_point_in_time_consensus"])
        self.assert_guard(report)

    def test_21_pairs_without_usd_do_not_inherit_us_cpi_claim(self):
        report = self.case()
        others = [r for r in report["pair_rows"] if not r["us_currency_role"]]
        self.assertEqual(len(others), 21)
        for row in others:
            self.assertIsNone(row["oct2026_us_cpi_yoy_metric_status"])
            self.assertIsNone(row["oct2026_us_cpi_mom_reported_consensus_percent_document_only"])
            self.assertNotIn("NO_OCT2025_US_ALL_ITEMS_CPI_INDEX_FOR_OCT2026_YOY",
                             row["missing_prerequisites"])
        self.assert_guard(report)

    def test_after_release_time_passes_no_actual_or_surprise(self):
        report = self.case(at(2026, 11, 10, 13, 30))
        self.assertEqual(report["release_state"],
                         "SCHEDULE_PASSED_ACTUAL_STILL_UNAUTHENTICATED")
        self.assert_guard(report)

    def test_before_release_time_is_not_a_reported_actual(self):
        report = self.case(at(2026, 11, 10, 13, 29))
        self.assertEqual(report["release_state"], "BEFORE_SCHEDULED_RELEASE_NO_ACTUAL")
        self.assert_guard(report)

    def test_never_backdate_nov6_research_into_earlier_times(self):
        for when in (at(2026, 11, 6, 23, 59), at(2026, 9, 30)):
            report = self.case(when)
            self.assertEqual(report["state"], "LAB_US_METRIC_RESEARCH_NOT_VISIBLE_ASOF")
            self.assertEqual(report["pair_rows"], [])
            self.assert_guard(report)

    def test_tz_equivalence_and_naive_rejected(self):
        tz_m4 = timezone(timedelta(hours=-4))
        self.assertEqual(self.case(datetime(2026, 11, 6, 20, tzinfo=tz_m4)),
                         self.case(at(2026, 11, 7)))
        for when in (None, "2026-11-07", datetime(2026, 11, 7)):
            report = self.case(when)
            self.assertEqual(report["state"], "LAB_BLOCKED")
            self.assertEqual(report["pair_rows"], [])
            self.assert_guard(report)

    def test_receipt_tampering_and_missing_are_blocked(self):
        replacements = (None, "not bytes", DATA["metric"] + b" ",
                        DATA["metric"].replace(b'"0.3"', b'"0.4"'),
                        DATA["metric"].replace(b'"missing_2026_october_headline_yoy": true',
                                               b'"missing_2026_october_headline_yoy": false'))
        for altered in replacements:
            report = self.case(metric=altered)
            self.assertEqual(report["state"], "LAB_BLOCKED")
            self.assert_guard(report)

    def test_every_parent_evidence_is_required(self):
        for key in FILES:
            if key == "metric":
                continue
            report = self.case(**{key: DATA[key] + b" "})
            self.assertEqual(report["state"], "LAB_BLOCKED", key)
            self.assertEqual(report["pair_rows"], [], key)
            self.assert_guard(report)


if __name__ == "__main__":
    unittest.main()
