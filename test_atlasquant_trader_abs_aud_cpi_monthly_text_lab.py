"""Synthetic source-shaped extracted-text fixtures; no ABS HTTP capture."""
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import unittest

from atlasquant_trader_abs_aud_cpi_monthly_text_lab import (
    SCHEMA, SOURCE_URL, parse_abs_aud_cpi_sep2026_monthly_text_lab as parse,
)

NOW = datetime(2026, 11, 5, 4, tzinfo=timezone.utc)
NARRATIVE = ("The Consumer Price Index (CPI) rose 4.3 per cent in the 12 months "
             "to September 2026, up from 4.0 per cent in the 12 months to August")
TEXT = """CPI rose 4.3% in the year to September 2026
Released
28/10/2026
Source
Consumer Price Index, Australia, September 2026
Release date and time
28/10/2026 11:30am AEDT
The Consumer Price Index (CPI) rose 4.3 per cent in the 12 months to September 2026, up from 4.0 per cent in the 12 months to August, according to the latest data from the Australian Bureau of Statistics.
All groups CPI, Australia, monthly and annual movement (%)
Change from previous month (%) | Annual change (%)
Jul-26 | 1.0 | 3.5
Aug-26 | 0.4 | 4.0
Sep-26 | 0.8 | 4.3
"""


def run(value=TEXT, observed=NOW):
    return parse(value.encode() if isinstance(value, str) else value,
                 observed_at_utc=observed)


class AbsAudCpiMonthlyTextTests(unittest.TestCase):
    def assert_no_go(self, r):
        for flag in ("official_http_response_independently_observed",
                     "original_source_authenticity_verified",
                     "publication_utc_instant_independently_verified",
                     "point_in_time_historical_vintage_verified",
                     "consensus_pre_event_attested",
                     "cross_country_methods_equivalent",
                     "commercial_redistribution_rights_verified",
                     "trade_authorized", "can_feed_live_radar",
                     "worker_enabled", "scheduler_enabled", "publishable"):
            self.assertIs(r[flag], False, flag)
        self.assertIsNone(r["fx_bias"])
        self.assertEqual(r["operational_bias"], "AGUARDAR")
        self.assertEqual((r["external_http_requests"], r["new_cost_brl"]), (0, 0))

    def test_pinned_original_abs_monthly_snapshot(self):
        r = run()
        self.assertEqual(r["schema"], SCHEMA)
        self.assertEqual(r["source_page"], SOURCE_URL)
        self.assertEqual(r["state"], "LAB_AUD_ABS_MONTHLY_CPI_SUPPLIED_TEXT_QUARANTINED")
        self.assertEqual((r["observation_period"], r["observation_frequency"]),
                         ("2026-09", "MONTHLY"))
        self.assertFalse(r["seasonally_adjusted"])
        self.assertEqual(r["headline_cpi_all_groups_monthly_change_percent_claim"], "0.8")
        self.assertEqual(r["headline_cpi_all_groups_annual_change_percent_claim"], "4.3")
        self.assertEqual(r["prior_month_annual_change_percent_claim"], "4.0")
        self.assertEqual(r["published_local_time_claim_AEDT"], "11:30am AEDT")
        self.assertEqual(r["published_release_calendar_date"], "2026-10-28")
        self.assertEqual(r["source_sha256"], sha256(TEXT.encode()).hexdigest())
        self.assert_no_go(r)

    def test_mom_0_8_is_distinct_from_yoy_4_3(self):
        r = run()
        self.assertNotEqual(r["headline_cpi_all_groups_monthly_change_percent_claim"],
                            r["headline_cpi_all_groups_annual_change_percent_claim"])

    def test_revision_of_headline_annual_value_is_rejected(self):
        self.assertEqual(run(TEXT.replace("Sep-26 | 0.8 | 4.3", "Sep-26 | 0.8 | 4.4"))[
            "state"], "LAB_BLOCKED")

    def test_seasonally_adjusted_annual_4_4_is_not_original(self):
        r = run(TEXT.replace("Sep-26 | 0.8 | 4.3", "Sep-26 | 0.6 | 4.4"))
        self.assertEqual(r["reason"], "PINNED_ORIGINAL_ALL_GROUPS_CPI_VALUES_MISMATCH")
        self.assert_no_go(r)

    def test_monthly_row_swap_is_not_accepted(self):
        self.assertEqual(run(TEXT.replace("Sep-26 | 0.8 | 4.3", "Sep-26 | 4.3 | 0.8"))[
            "state"], "LAB_BLOCKED")

    def test_prior_month_yoy_must_be_exact_not_missing_or_zero(self):
        for row in ("Aug-26 | 0.4 | 0.0", "Aug-26 | 0.4 | -",
                    "Aug-26 | 0.4 | 3.9"):
            self.assertEqual(run(TEXT.replace("Aug-26 | 0.4 | 4.0", row))["state"],
                             "LAB_BLOCKED")

    def test_second_september_row_must_not_be_silently_ignored(self):
        self.assertEqual(run(TEXT + "\nSep-26 | 0.8 | 4.3")["state"], "LAB_BLOCKED")

    def test_missing_header_or_reversed_columns_denied(self):
        for header in ("Monthly increase (%) | Annual change (%)",
                       "Annual change (%) | Change from previous month (%)", ""):
            self.assertEqual(run(TEXT.replace(
                "Change from previous month (%) | Annual change (%)", header))["state"],
                "LAB_BLOCKED")

    def test_monthly_label_required_not_quarterly(self):
        self.assertEqual(run(TEXT.replace(
            "All groups CPI, Australia, monthly and annual movement (%)",
            "All groups CPI, Australia, quarterly and annual movement (%)"))["state"],
            "LAB_BLOCKED")

    def test_other_aggregates_cannot_replace_headline(self):
        self.assertEqual(run(TEXT.replace("Sep-26 | 0.8 | 4.3", "Trimmed mean | 0.3 | 3.6"))[
            "state"], "LAB_BLOCKED")

    def test_mismatch_release_title_and_annual_row_denied(self):
        self.assertEqual(run(TEXT.replace("CPI rose 4.3%", "CPI rose 4.4%"))["state"],
                         "LAB_BLOCKED")

    def test_narrative_missing_or_different_annual_denied(self):
        self.assertEqual(run(TEXT.replace(NARRATIVE, "The CPI rose 3.7 percent"))[
            "state"], "LAB_BLOCKED")

    def test_release_date_aedt_and_timezone_required(self):
        for replacement in ("28/10/2026 11:30am AEST", "28/10/2026 11:30am UTC",
                            "27/10/2026 11:30am AEDT", "28/10/2026 10:30am AEDT"):
            self.assertEqual(run(TEXT.replace("28/10/2026 11:30am AEDT", replacement))[
                "state"], "LAB_BLOCKED")

    def test_before_claimed_publication_time_is_blocked(self):
        earlier = datetime(2026, 10, 28, 0, 29, tzinfo=timezone.utc)
        self.assertEqual(run(observed=earlier)["state"], "LAB_BLOCKED")
        at_claimed = datetime(2026, 10, 28, 0, 30, tzinfo=timezone.utc)
        self.assertEqual(run(observed=at_claimed)["state"],
                         "LAB_AUD_ABS_MONTHLY_CPI_SUPPLIED_TEXT_QUARANTINED")

    def test_missing_naive_or_invalid_capture_clock_denied(self):
        for date in (None, datetime(2026, 11, 5), "2026-11-05"):
            self.assertEqual(run(observed=date)["state"], "LAB_BLOCKED")

    def test_bad_numeric_formats_denied(self):
        for value in ("NaN", "Infinity", "1e2", "4,3", "-", "0.0"):
            self.assertEqual(run(TEXT.replace("Sep-26 | 0.8 | 4.3",
                                              f"Sep-26 | 0.8 | {value}"))["state"],
                             "LAB_BLOCKED")

    def test_non_utf8_html_nul_and_oversized_denied(self):
        for bad in (b"\xff" + TEXT.encode(), b"<html>" + TEXT.encode(),
                    TEXT.encode() + b"\x00", b"x" * (128 * 1024 + 1)):
            self.assertEqual(run(bad)["state"], "LAB_BLOCKED")

    def test_missing_or_wrong_type_text_denied(self):
        for bad in (None, [], "short", b""):
            self.assertEqual(run(bad)["state"], "LAB_BLOCKED")

    def test_local_capture_clock_does_not_attest_original_source(self):
        for date in (NOW, NOW + timedelta(minutes=1)):
            self.assert_no_go(run(observed=date))


if __name__ == "__main__":
    unittest.main()
