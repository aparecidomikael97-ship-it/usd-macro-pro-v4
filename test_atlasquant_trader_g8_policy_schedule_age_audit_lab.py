"""Eight issuer calendar windows, all strictly research-only and date-level."""
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch
import unittest

from atlasquant_fx_universe import OFFICIAL_PAIRS
from atlasquant_trader_g8_macro_asof_lab import FRESH_DAYS, OBSERVATION_AGE_LIMIT_DAYS
from atlasquant_trader_g8_policy_schedule_age_audit_lab import (
    CASEBOOK_SHA256, inspect_g8_policy_schedule_age_audit_lab as inspect,
)

CASEBOOK = (Path(__file__).resolve().parent / "docs" / "continuidade" /
            "TRADER_G8_EIGHT_POLICY_DECISION_CALENDAR_LAB_20261108.json").read_bytes()
AS_OF = datetime(2026, 11, 9, tzinfo=timezone.utc)


class PolicyScheduleAgeTests(unittest.TestCase):
    def run_case(self, raw=CASEBOOK, *, as_of=AS_OF):
        return inspect(raw, as_of_utc=as_of)

    def assert_no_trade(self, r):
        self.assertEqual(r["operational_bias"], "AGUARDAR")
        self.assertIsNone(r["fx_bias"])
        self.assertIsNone(r["validated_directional_accuracy"])
        self.assertEqual((r["http_requests"], r["new_cost_brl"]), (0, 0))
        for k in ("rate_values_from_issuers_verified", "historical_rate_vintages_verified",
                  "original_publisher_bytes_archived",
                  "exact_research_consultation_instant_attested",
                  "exact_original_announcement_instant_attested",
                  "future_scheduled_decisions_occurred", "unplanned_decisions_are_excluded",
                  "real_broker_prices_verified", "policy_rates_cross_currency_comparable",
                  "trade_authorized", "can_feed_live_radar", "worker_enabled",
                  "scheduler_enabled", "publishable"):
            self.assertFalse(r[k], k)
        for pair in r["pair_rows"]:
            self.assertEqual((pair["D1"], pair["W1"]), ("AGUARDAR", "AGUARDAR"))
            self.assertFalse(pair["trade_authorized"])

    def test_all_eight_issuer_schedules_pass_structural_ceiling_without_signals(self):
        import hashlib
        self.assertEqual(hashlib.sha256(CASEBOOK).hexdigest(), CASEBOOK_SHA256)
        r = self.run_case()
        self.assertEqual(r["state"], "LAB_EIGHT_POLICY_CALENDAR_WINDOWS_FIT_CURRENT_AGE_CEILINGS_UNATTESTED")
        self.assertEqual((r["currency_count"], r["pair_count"]), (8, 28))
        self.assertEqual(r["currencies_with_schedule_age_gap"], [])
        self.assertEqual(r["max_decision_gap_days"], 76)
        self.assertEqual(r["minimum_published_age_margin_days"], 44)
        self.assertEqual({p["pair"] for p in r["pair_rows"]}, set(OFFICIAL_PAIRS))
        self.assertTrue(all(p["both_schedule_windows_fit_ceilings"] for p in r["pair_rows"]))
        self.assert_no_trade(r)

    def test_swiss_longest_decision_window_is_seventy_six_days(self):
        by = {row["currency"]: row for row in self.run_case()["currency_rows"]}
        chf = by["CHF"]
        self.assertEqual((chf["prior_decision_calendar_date_claim"],
                          chf["next_scheduled_decision_calendar_date_claim"]),
                         ("2026-09-24", "2026-12-10"))
        self.assertEqual((chf["prior_to_next_announcement_eve_days"],
                          chf["publication_age_ceiling_days"],
                          chf["published_age_margin_days"]), (76, 120, 44))

    def test_new_zealand_fsr_is_not_confused_with_next_ocr_decision(self):
        by = {row["currency"]: row for row in self.run_case()["currency_rows"]}
        nzd = by["NZD"]
        self.assertEqual((nzd["prior_decision_calendar_date_claim"],
                          nzd["next_scheduled_decision_calendar_date_claim"]),
                         ("2026-10-28", "2026-12-09"))
        self.assertEqual(nzd["excluded_non_decision_events_from_rate_calendar"],
                         ["FINANCIAL_STABILITY_REPORT"])

    def test_month_end_is_coarse_metadata_not_exact_decision_date(self):
        by = {row["currency"]: row for row in self.run_case()["currency_rows"]}
        gbp = by["GBP"]
        self.assertEqual(gbp["prior_decision_calendar_date_claim"], "2026-11-05")
        self.assertEqual(gbp["legacy_monthly_period_end_date"], "2026-11-30")
        self.assertNotEqual(gbp["legacy_monthly_period_age_at_next_eve_days"],
                            gbp["prior_to_next_announcement_eve_days"])
        self.assertFalse(self.run_case()["exact_original_announcement_instant_attested"])

    def test_reduced_publication_age_ceiling_flags_swiss_and_stays_blocked(self):
        with patch.dict(FRESH_DAYS, {"POLICY_RATE": 70}):
            r = self.run_case()
        self.assertEqual(r["state"], "LAB_POLICY_CALENDAR_AGE_CEILING_REVIEW_REQUIRED")
        self.assertEqual(r["currencies_with_schedule_age_gap"], ["CHF"])
        self.assertTrue(any(not p["both_schedule_windows_fit_ceilings"] for p in r["pair_rows"]))
        self.assert_no_trade(r)

    def test_reduced_monthly_competence_cap_also_flags_swiss(self):
        with patch.dict(OBSERVATION_AGE_LIMIT_DAYS, {("POLICY_RATE", "MONTHLY"): 45}):
            r = self.run_case()
        self.assertEqual(r["state"], "LAB_POLICY_CALENDAR_AGE_CEILING_REVIEW_REQUIRED")
        self.assertIn("CHF", r["currencies_with_schedule_age_gap"])
        self.assert_no_trade(r)

    def test_corrupt_casebook_and_invalid_clocks_refused(self):
        for raw, when in ((CASEBOOK + b" ", AS_OF), (CASEBOOK.replace(b"2026-12-09", b"2026-11-09"), AS_OF),
                          (b"{}", AS_OF), (CASEBOOK, datetime(2026, 11, 9)),
                          (CASEBOOK, None)):
            r = self.run_case(raw, as_of=when)
            self.assertEqual(r["state"], "LAB_BLOCKED")
            self.assertEqual((r["currency_rows"], r["pair_rows"]), ([], []))
            self.assert_no_trade(r)

    def test_cautious_visibility_date_and_timezone_equivalence(self):
        r = self.run_case(as_of=datetime(2026, 11, 8, 23, 59, tzinfo=timezone.utc))
        self.assertEqual(r["state"], "LAB_RESEARCH_NOT_VISIBLE_ASOF")
        self.assertEqual(r["currency_rows"], [])
        self.assert_no_trade(r)
        shifted = datetime(2026, 11, 8, 20, tzinfo=timezone(timedelta(hours=-4)))
        self.assertEqual(self.run_case(as_of=shifted), self.run_case())

    def test_far_future_clock_does_not_validate_future_policy_decisions(self):
        r = self.run_case(as_of=datetime(2027, 2, 1, tzinfo=timezone.utc))
        self.assertEqual(r["currency_count"], 8)
        self.assertTrue(all(row["future_schedule_is_not_an_announced_decision"]
                            for row in r["currency_rows"]))
        self.assert_no_trade(r)


if __name__ == "__main__":
    unittest.main()
