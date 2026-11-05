"""Synthetic extracted StatCan Table 1 text, not a genuine HTTP response."""
from datetime import datetime, timezone
from hashlib import sha256
import unittest

from atlasquant_trader_statcan_cad_cpi_table_text_lab import (
    SCHEMA, SOURCE_URL, parse_statcan_cad_all_items_table_text_lab as parse,
)

OBSERVED = datetime(2026, 11, 5, 1, tzinfo=timezone.utc)
TITLE = "Consumer Price Index, major components and special aggregates, Canada – Not seasonally adjusted"
ROW = "All-items | 164.9 | 169.8 | 170.0 | 0.1 | 3.1"
TEXT = f"""# Table 1
{TITLE}
{TITLE}
September
2025 | August
2026 | September
2026 | August to September 2026 | September 2025 to September 2026
(2002=100) | (2002=100) | (2002=100) | % change | % change
{ROW}
Food | 197.5 | 202.4 | 201.8 | -0.3 | 2.2
All-items excluding food | 159.1 | 163.9 | 164.2 | 0.2 | 3.2
All-items excluding food and energy | 155.4 | 158.8 | 158.6 | -0.1 | 2.1
Date modified:
2026-10-19
"""


def run(src=TEXT, observed=OBSERVED):
    return parse(src.encode() if isinstance(src, str) else src,
                 observed_at_utc=observed)


class StatCanAllItemsTableTextTests(unittest.TestCase):
    def assert_no_signal(self, x):
        for flag in ("source_is_original_official_http_response",
                     "original_source_authenticity_independently_verified",
                     "individual_release_instant_verified",
                     "archived_historical_vintage_verified",
                     "consensus_pre_event_attested",
                     "cross_country_methods_equivalent",
                     "commercial_redistribution_rights_verified", "trade_authorized",
                     "can_feed_live_radar", "worker_enabled", "scheduler_enabled",
                     "publishable"):
            self.assertIs(x[flag], False, flag)
        self.assertIsNone(x["fx_bias"])
        self.assertEqual(x["operational_bias"], "AGUARDAR")
        self.assertEqual((x["external_http_requests"], x["new_cost_brl"]), (0, 0))

    def test_2026_september_canada_headline_from_table_shaped_fixture(self):
        x = run()
        self.assertEqual(x["schema"], SCHEMA)
        self.assertEqual(x["state"], "LAB_CANADA_CPI_SUPPLIED_TABLE_TEXT_QUARANTINED")
        self.assertEqual((x["currency"], x["source_page"]), ("CAD", SOURCE_URL))
        self.assertEqual(x["reference_period"], "2026-09")
        self.assertEqual(x["index_base"], "2002=100")
        self.assertEqual(x["base_year"], 2002)
        self.assertEqual(x["page_modified_calendar_only"], "2026-10-19")
        self.assertEqual(x["index_sep_2025_claim"], "164.9")
        self.assertEqual(x["index_aug_2026_claim"], "169.8")
        self.assertEqual(x["index_sep_2026_claim"], "170.0")
        self.assertEqual(x["published_mom_percent_claim"], "0.1")
        self.assertEqual(x["published_yoy_percent_claim"], "3.1")
        self.assertIs(x["seasonally_adjusted"], False)
        self.assertEqual(x["source_sha256"], sha256(TEXT.encode()).hexdigest())
        self.assert_no_signal(x)

    def test_food_or_ex_fresh_food_rows_do_not_replace_headline(self):
        x = run(TEXT.replace("2.2", "9.9").replace("3.2", "4.4"))
        self.assertEqual(x["published_yoy_percent_claim"], "3.1")
        self.assert_no_signal(x)

    def test_headline_annual_is_last_column_not_mom_or_index(self):
        x = run(TEXT.replace(ROW, "All-items | 164.9 | 169.8 | 170.0 | 0.4 | 3.9"))
        self.assertEqual((x["published_mom_percent_claim"],
                          x["published_yoy_percent_claim"],
                          x["index_sep_2026_claim"]), ("0.4", "3.9", "170.0"))

    def test_missing_headline_only_exclusions_rejected(self):
        self.assertEqual(run(TEXT.replace(ROW, ""))["state"], "LAB_BLOCKED")

    def test_duplicate_headline_row_rejected(self):
        self.assertEqual(run(TEXT + "\n" + ROW)["state"], "LAB_BLOCKED")

    def test_wrong_geography_rejected(self):
        self.assertEqual(run(TEXT.replace("Canada –", "Ontario –"))["state"],
                         "LAB_BLOCKED")

    def test_seasonally_adjusted_wrong_family_rejected(self):
        self.assertEqual(run(TEXT.replace("Not seasonally adjusted", "Seasonally adjusted"))[
            "state"], "LAB_BLOCKED")

    def test_2025_base_cannot_replace_2002_base(self):
        self.assertEqual(run(TEXT.replace("(2002=100)", "(2025=100)"))["state"],
                         "LAB_BLOCKED")

    def test_wrong_column_month_year_rejected(self):
        for old, new in (("September 2025", "August 2025"),
                         ("August to September 2026", "July to September 2026"),
                         ("September 2025 to September 2026",
                          "September 2024 to September 2026")):
            self.assertEqual(run(TEXT.replace(old, new, 1))["state"], "LAB_BLOCKED")

    def test_too_many_or_missing_index_unit_columns_rejected(self):
        for replacement in ("(2002=100) | (2002=100)",
                            "(2002=100) | (2002=100) | (2002=100) | (2002=100)"):
            src = TEXT.replace("(2002=100) | (2002=100) | (2002=100)", replacement)
            self.assertEqual(run(src)["state"], "LAB_BLOCKED")

    def test_bad_last_column_unit_rejected(self):
        self.assertEqual(run(TEXT.replace("% change | % change", "% change | index"))[
            "state"], "LAB_BLOCKED")

    def test_negative_headline_annual_preserves_sign(self):
        x = run(TEXT.replace(ROW, "All-items | 164.9 | 169.8 | 170.0 | 0.1 | -0.7"))
        self.assertEqual(x["published_yoy_percent_claim"], "-0.7")
        self.assert_no_signal(x)

    def test_zero_headline_annual_is_real_zero_not_missing(self):
        x = run(TEXT.replace(ROW, "All-items | 164.9 | 169.8 | 170.0 | 0.1 | 0.0"))
        self.assertEqual(x["published_yoy_percent_claim"], "0.0")

    def test_nan_inf_exponent_comma_percent_disallowed(self):
        for val in ("NaN", "Inf", "1e3", "3,1", "-0.0%"):
            x = run(TEXT.replace(ROW, f"All-items | 164.9 | 169.8 | 170.0 | 0.1 | {val}"))
            self.assertEqual(x["state"], "LAB_BLOCKED")

    def test_outside_index_and_rate_bounds_rejected(self):
        for value in ("0.0", "450.0", "-10.0"):
            x = run(TEXT.replace(ROW, f"All-items | 164.9 | 169.8 | {value} | 0.1 | 3.1"))
            self.assertEqual(x["state"], "LAB_BLOCKED")
        self.assertEqual(run(TEXT.replace(ROW, "All-items | 164.9 | 169.8 | 170.0 | 0.1 | 101.0"))[
            "state"], "LAB_BLOCKED")

    def test_missing_modified_date_rejected(self):
        self.assertEqual(run(TEXT.replace("2026-10-19", "2026-10-18"))["state"],
                         "LAB_BLOCKED")

    def test_duplicate_modified_date_rejected(self):
        self.assertEqual(run(TEXT + "Date modified: 2026-10-19")["state"],
                         "LAB_BLOCKED")

    def test_prior_to_page_modified_day_rejected(self):
        earlier = datetime(2026, 10, 18, 10, tzinfo=timezone.utc)
        self.assertEqual(run(observed=earlier)["state"], "LAB_BLOCKED")

    def test_plain_text_not_html_or_invalid_utf8(self):
        for bad in (TEXT.encode() + b"<html>", b"\xff" + TEXT.encode(),
                    TEXT.encode() + b"\x00"):
            self.assertEqual(run(bad)["state"], "LAB_BLOCKED")

    def test_oversize_small_or_non_bytes_rejected(self):
        for bad in (b"", b"x" * (128 * 1024 + 1), None, {}):
            self.assertEqual(run(bad)["state"], "LAB_BLOCKED")

    def test_clock_must_be_timezone_aware(self):
        self.assertEqual(run(observed=datetime(2026, 11, 5))["state"], "LAB_BLOCKED")
        self.assertEqual(run(observed=None)["state"], "LAB_BLOCKED")

    def test_single_title_heading_supported_but_duplicate_three_rejected(self):
        once = TEXT.replace(TITLE + "\n", "", 1)
        self.assertEqual(run(once)["state"],
                         "LAB_CANADA_CPI_SUPPLIED_TABLE_TEXT_QUARANTINED")
        self.assertEqual(run(TEXT + TITLE)["state"], "LAB_BLOCKED")

    def test_all_text_claims_quarantined_without_market_signal(self):
        for change in (TEXT, TEXT.replace("3.1", "3.2", 1),
                       TEXT.replace(ROW, "All-items | 164.9 | 169.8 | 170.0 | 0.1 | 0.0")):
            self.assert_no_signal(run(change))


if __name__ == "__main__":
    unittest.main()
