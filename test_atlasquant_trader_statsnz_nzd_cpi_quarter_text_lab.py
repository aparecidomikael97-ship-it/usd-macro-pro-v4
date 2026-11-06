"""Only synthetic source-shaped Stats NZ quarterly extracted text fixtures."""
from datetime import datetime, timezone
from hashlib import sha256
import unittest

from atlasquant_trader_statsnz_nzd_cpi_quarter_text_lab import (
    SCHEMA, SOURCE_URL, parse_statsnz_nzd_cpi_sep2026_quarter_text_lab as parse,
)

OBSERVED = datetime(2026, 11, 5, 4, tzinfo=timezone.utc)
ROW = "CPI all groups | 0.7 | 3.7"
TEXT = """Consumers price index: September 2026 quarter
22 October 2026, 10:45am
The consumers price index (CPI) measures prices purchased by NZ households.
Key facts
Description | Quarterly percentage change | Annual percentage change
CPI all groups | 0.7 | 3.7
Tradeables | 0.2 | 4.3
Non-tradeables | 1.0 | 3.3
CPI excluding food group, household energy subgroup, and vehicle fuels | 1.1 | 2.9
Consumers price index, percentage change, September 2022–September 2026
Quarter | CPI all groups (quarterly) | CPI all groups (annual)
"""


def run(value=TEXT, observed=OBSERVED):
    return parse(value.encode() if isinstance(value, str) else value,
                 observed_at_utc=observed)


class StatsNzQuarterlyTextTests(unittest.TestCase):
    def assert_no_go(self, result):
        for flag in ("official_http_response_independently_observed",
                     "original_source_authenticity_verified",
                     "publication_utc_instant_independently_verified",
                     "historical_vintage_verified", "monthly_values_synthesized",
                     "consensus_pre_event_attested", "cross_country_methods_equivalent",
                     "commercial_redistribution_rights_verified", "trade_authorized",
                     "can_feed_live_radar", "worker_enabled", "scheduler_enabled",
                     "publishable"):
            self.assertIs(result[flag], False, flag)
        self.assertIsNone(result["fx_bias"])
        self.assertEqual(result["operational_bias"], "AGUARDAR")
        self.assertEqual((result["external_http_requests"], result["new_cost_brl"]), (0, 0))

    def test_official_page_shaped_quarterly_fixture(self):
        result = run()
        self.assertEqual(result["schema"], SCHEMA)
        self.assertEqual(result["state"], "LAB_NZD_QUARTERLY_CPI_TEXT_QUARANTINED")
        self.assertEqual(result["source_page"], SOURCE_URL)
        self.assertEqual(result["observation_frequency"], "QUARTERLY")
        self.assertEqual(result["observation_period"], "2026-Q3")
        self.assertEqual(result["period_end_month_not_monthly_observation"], "2026-09")
        self.assertEqual(result["headline_cpi_all_groups_quarter_change_percent_claim"], "0.7")
        self.assertEqual(result["headline_cpi_all_groups_annual_change_percent_claim"], "3.7")
        self.assertEqual(result["release_date_calendar_only"], "2026-10-22")
        self.assertEqual(result["publisher_display_time_without_verified_utc_instant"], "10:45am")
        self.assertEqual(result["source_sha256"], sha256(TEXT.encode()).hexdigest())
        self.assert_no_go(result)

    def test_quarterly_change_is_not_annual_change(self):
        text = TEXT.replace(ROW, "CPI all groups | 1.9 | 4.7")
        r = run(text)
        self.assertEqual((r["headline_cpi_all_groups_quarter_change_percent_claim"],
                          r["headline_cpi_all_groups_annual_change_percent_claim"]),
                         ("1.9", "4.7"))

    def test_other_cpi_aggregates_cannot_replace_all_groups(self):
        t = TEXT.replace("Tradeables | 0.2 | 4.3", "Tradeables | 0.2 | 80.0")
        self.assertEqual(run(t)["headline_cpi_all_groups_annual_change_percent_claim"], "3.7")

    def test_only_tradeables_without_headline_rejected(self):
        self.assertEqual(run(TEXT.replace(ROW, ""))["state"], "LAB_BLOCKED")

    def test_duplicate_headline_rejected(self):
        self.assertEqual(run(TEXT + "\n" + ROW)["state"], "LAB_BLOCKED")

    def test_missing_title_or_wrong_quarter_rejected(self):
        for t in (TEXT.replace("September 2026 quarter", "June 2026 quarter", 1),
                  TEXT.replace("Consumers price index:", "Tradeables price index:", 1)):
            self.assertEqual(run(t)["state"], "LAB_BLOCKED")

    def test_title_repeated_refused(self):
        self.assertEqual(run(TEXT + "\nConsumers price index: September 2026 quarter")[
            "state"], "LAB_BLOCKED")

    def test_date_not_claimed_as_verified_utc_release(self):
        r = run()
        self.assertIs(r["publication_utc_instant_independently_verified"], False)
        self.assert_no_go(r)

    def test_wrong_release_day_or_missing_time_rejected(self):
        for x in ("21 October 2026, 10:45am", "22 October 2026, 9:45am",
                  "22 October 2026"):
            self.assertEqual(run(TEXT.replace("22 October 2026, 10:45am", x))["state"],
                             "LAB_BLOCKED")

    def test_future_claimed_publication_after_capture_day_rejected(self):
        earlier = datetime(2026, 10, 21, 11, tzinfo=timezone.utc)
        self.assertEqual(run(observed=earlier)["state"], "LAB_BLOCKED")

    def test_wrong_units_or_column_order_rejected(self):
        for header in ("Description | Monthly percentage change | Annual percentage change",
                       "Description | Annual percentage change | Quarterly percentage change",
                       "Description | Quarterly index | Annual percentage change"):
            t = TEXT.replace("Description | Quarterly percentage change | Annual percentage change",
                             header)
            self.assertEqual(run(t)["state"], "LAB_BLOCKED")

    def test_negative_and_zero_rates_preserved(self):
        for values in (("-0.4", "0.0"), ("0.0", "-0.7")):
            t = TEXT.replace(ROW, f"CPI all groups | {values[0]} | {values[1]}")
            r = run(t)
            self.assertEqual(r["headline_cpi_all_groups_quarter_change_percent_claim"],
                             values[0])
            self.assertEqual(r["headline_cpi_all_groups_annual_change_percent_claim"],
                             values[1])
            self.assert_no_go(r)

    def test_nan_infinity_exponent_or_comma_rejected(self):
        for x in ("NaN", "Inf", "1e2", "3,7"):
            self.assertEqual(run(TEXT.replace(ROW, f"CPI all groups | 0.7 | {x}"))[
                "state"], "LAB_BLOCKED")

    def test_rates_out_of_bounds_rejected(self):
        for x in ("101.0", "-51.0", "999.0"):
            self.assertEqual(run(TEXT.replace(ROW, f"CPI all groups | 0.7 | {x}"))[
                "state"], "LAB_BLOCKED")

    def test_html_raw_nul_or_invalid_utf8_rejected(self):
        for bad in (TEXT.encode() + b"<html>", b"\xff" + TEXT.encode(),
                    TEXT.encode() + b"\x00"):
            self.assertEqual(run(bad)["state"], "LAB_BLOCKED")

    def test_short_oversized_or_non_bytes_rejected(self):
        for bad in (b"", b"x" * (64 * 1024 + 1), None, []):
            self.assertEqual(run(bad)["state"], "LAB_BLOCKED")

    def test_naive_or_absent_capture_clock_rejected(self):
        self.assertEqual(run(observed=datetime(2026, 11, 5))["state"], "LAB_BLOCKED")
        self.assertEqual(run(observed=None)["state"], "LAB_BLOCKED")

    def test_monthly_values_never_synthesized_for_any_valid_input(self):
        for value in (TEXT, TEXT.replace(ROW, "CPI all groups | 1.1 | 3.9")):
            self.assertIs(run(value)["monthly_values_synthesized"], False)
            self.assert_no_go(run(value))


if __name__ == "__main__":
    unittest.main()
