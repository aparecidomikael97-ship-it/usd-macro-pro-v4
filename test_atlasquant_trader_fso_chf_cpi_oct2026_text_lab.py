"""Synthetic Swiss FSO source-shaped text fixtures; not original HTTP evidence."""
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import unittest

from atlasquant_trader_fso_chf_cpi_oct2026_text_lab import (
    SCHEMA, SOURCE_URL, parse_fso_chf_cpi_oct2026_text_lab as parse,
)

STAMP = datetime(2026, 11, 5, 2, tzinfo=timezone.utc)
TEXT = """Press release Published on 3 November 2026

Consumer prices increased by 0.2% in October

Neuchâtel, 03.11.2026 — The Consumer Price Index (CPI) increased by 0.2% in October 2026 compared with the previous month, reaching 101.7 points (December 2025 = 100). Inflation was +1.5% compared with the same month of the previous year. These are the results of the Federal Statistical Office (FSO).
"""


def run(text=TEXT, stamp=STAMP):
    return parse(text.encode("utf-8") if isinstance(text, str) else text,
                 observed_at_utc=stamp)


class SwissCpiTests(unittest.TestCase):
    def assert_no_go(self, out):
        for key in ("source_is_original_official_http_response",
                    "original_source_authenticity_independently_verified",
                    "individual_release_instant_verified",
                    "archived_historical_vintage_verified",
                    "consensus_pre_event_attested",
                    "cross_country_methods_equivalent",
                    "commercial_redistribution_rights_verified",
                    "release_clock_attested",
                    "trade_authorized", "can_feed_live_radar",
                    "worker_enabled", "scheduler_enabled", "publishable"):
            self.assertIs(out[key], False, key)
        self.assertEqual(out["operational_bias"], "AGUARDAR")
        self.assertIsNone(out["fx_bias"])
        self.assertEqual((out["external_http_requests"], out["new_cost_brl"]), (0, 0))

    def test_frozen_swiss_national_cpi_numbers_have_distinct_units(self):
        r = run()
        self.assertEqual(r["schema"], SCHEMA)
        self.assertEqual(r["state"], "LAB_CHF_FSO_NATIONAL_CPI_SUPPLIED_TEXT_QUARANTINED")
        self.assertEqual((r["currency"], r["source_page"]), ("CHF", SOURCE_URL))
        self.assertEqual((r["reference_period"], r["observation_frequency"]), ("2026-10", "MONTHLY"))
        self.assertEqual(r["index_base"], "DECEMBER_2025_100")
        self.assertEqual(r["index_points_claim"], "101.7")
        self.assertEqual(r["published_mom_percent_claim"], "0.2")
        self.assertEqual(r["published_yoy_percent_claim"], "1.5")
        self.assertIsNone(r["seasonally_adjusted"])
        self.assertEqual(r["release_calendar_date_claim"], "2026-11-03")
        self.assertEqual(r["source_sha256"], sha256(TEXT.encode()).hexdigest())
        self.assertEqual(r["source_byte_count"], len(TEXT.encode()))
        self.assert_no_go(r)

    def test_change_annual_rate_blocked(self):
        self.assertEqual(run(TEXT.replace("+1.5%", "+1.6%"))["state"], "LAB_BLOCKED")

    def test_change_monthly_rate_blocked(self):
        self.assertEqual(run(TEXT.replace("increased by 0.2% in October 2026",
                                           "increased by 0.3% in October 2026"))["state"], "LAB_BLOCKED")

    def test_change_index_points_blocked(self):
        self.assertEqual(run(TEXT.replace("101.7 points", "101.8 points"))["state"], "LAB_BLOCKED")

    def test_change_base_blocked(self):
        self.assertEqual(run(TEXT.replace("December 2025 = 100",
                                           "December 2020 = 100"))["state"], "LAB_BLOCKED")

    def test_change_reference_period_blocked(self):
        self.assertEqual(run(TEXT.replace("October 2026", "September 2026"))["state"], "LAB_BLOCKED")

    def test_no_retroactively_fake_release_date(self):
        self.assertEqual(run(TEXT.replace("3 November 2026", "2 November 2026"))["state"], "LAB_BLOCKED")

    def test_no_wrong_neuchatel_date(self):
        self.assertEqual(run(TEXT.replace("03.11.2026", "01.11.2026"))["state"], "LAB_BLOCKED")

    def test_duplicate_text_refused(self):
        self.assertEqual(run(TEXT + TEXT)["state"], "LAB_BLOCKED")

    def test_harmonised_swap_rejected(self):
        self.assertEqual(run(TEXT + "\nHarmonised Index of Consumer Prices")["state"], "LAB_BLOCKED")

    def test_adjusted_swap_rejected(self):
        self.assertEqual(run(TEXT + "\nSeasonally adjusted")["state"], "LAB_BLOCKED")

    def test_corrupt_html_rejected(self):
        self.assertEqual(run(TEXT + "<script>bad</script>")["state"], "LAB_BLOCKED")

    def test_utf8_invalid_rejected(self):
        self.assertEqual(run(b"\xff" + TEXT.encode())["state"], "LAB_BLOCKED")

    def test_future_capture_not_a_release_proof(self):
        self.assert_no_go(run(stamp=STAMP + timedelta(days=2)))

    def test_before_conservative_day_cutoff_rejected(self):
        self.assertEqual(run(stamp=datetime(2026,11,3,23,59,tzinfo=timezone.utc))["state"],
                         "LAB_BLOCKED")

    def test_naive_capture_rejected(self):
        self.assertEqual(run(stamp=STAMP.replace(tzinfo=None))["state"], "LAB_BLOCKED")

    def test_missing_invalid_types_rejected(self):
        for value in (None, {}, [], b"", "short", 12):
            self.assertEqual(run(value)["state"], "LAB_BLOCKED")

    def test_capture_offset_converted_to_utc(self):
        from datetime import timedelta as td
        offset = timezone(td(hours=-4))
        r = run(stamp=datetime(2026,11,4,22,tzinfo=offset))
        self.assertEqual(r["observed_at_local_system_utc"], STAMP.isoformat())
        self.assert_no_go(r)


if __name__ == "__main__":
    unittest.main()
