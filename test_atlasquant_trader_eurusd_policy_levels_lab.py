"""Offline synthetic tests only: no current-rate or pre-event proof."""
from __future__ import annotations

from datetime import datetime, timezone
import unittest

from atlasquant_trader_eurusd_policy_levels_lab import (
    compare_eurusd_policy_levels_lab,
    parse_ecb_dfr_effective_csv_lab as ecb,
    parse_fed_target_range_csv_lab as fed,
)

NOW = datetime(2026, 11, 5, 0, 30, tzinfo=timezone.utc)
ECB_HEADER = "KEY,FREQ,REF_AREA,CURRENCY,TIME_PERIOD,OBS_VALUE,OBS_STATUS\n"
ECB_ROWS = (
    "FM.D.U2.EUR.4F.KR.DFR.LEV,D,U2,EUR,2025-06-11,2.0000000,A\n"
    "FM.D.U2.EUR.4F.KR.DFR.LEV,D,U2,EUR,2026-09-16,2.5000000,A\n"
)
FED_HEADER = "observation_date,DFEDTARL,DFEDTARU\n"
FED_ROWS = (
    "2026-11-01,3.75,4.00\n"
    "2026-11-02,3.75,4.00\n"
    "2026-11-03,3.75,4.00\n"
)


def ecb_raw(rows: str = ECB_ROWS, header: str = ECB_HEADER) -> bytes:
    return (header + rows).encode()


def fed_raw(rows: str = FED_ROWS, header: str = FED_HEADER) -> bytes:
    return (header + rows).encode()


class PolicyLevelTests(unittest.TestCase):
    def test_ecb_valid_level_is_not_announcement_or_signal(self):
        r = ecb(ecb_raw(), observed_at_utc=NOW)
        self.assertEqual(r["state"], "LAB_ECB_DFR_EFFECTIVE_LEVEL_QUARANTINED")
        self.assertEqual(r["latest_effective_date"], "2026-09-16")
        self.assertEqual(r["rate_percent"], "2.5000000")
        self.assertEqual(r["effective_changes_count"], 2)
        self.assertTrue(r["effective_date_not_decision_announcement"])
        self.assertFalse(r["source_origin_independently_authenticated"])
        self.assertFalse(r["decision_announcement_instant_verified"])
        self.assertFalse(r["pre_event_consensus_verified"])
        self.assertFalse(r["trade_authorized"])

    def test_fed_valid_range_is_not_surprise_or_signal(self):
        r = fed(fed_raw(), observed_at_utc=NOW)
        self.assertEqual(r["state"], "LAB_FED_TARGET_RANGE_DAILY_QUARANTINED")
        self.assertEqual(r["lower_bound_percent"], "3.75")
        self.assertEqual(r["upper_bound_percent"], "4.00")
        self.assertTrue(r["daily_effective_date_not_fomc_announcement"])
        self.assertIsNone(r["rate_percent"])
        self.assertFalse(r["point_in_time_vintage_verified"])
        self.assertFalse(r["market_implied_expectation_verified"])

    def test_no_direction_even_with_both_valid(self):
        result = compare_eurusd_policy_levels_lab(
            ecb(ecb_raw(), observed_at_utc=NOW),
            fed(fed_raw(), observed_at_utc=NOW))
        self.assertEqual(result["state"],
                         "LAB_POLICY_LEVELS_DIFFERENT_MEASURES_QUARANTINED")
        self.assertTrue(result["different_effective_dates"])
        for field in ("policy_rate_spread_bps", "prior_meeting_expectation_bps",
                      "market_surprise_bps", "fx_bias"):
            self.assertIsNone(result[field])
        self.assertEqual(result["operational_bias"], "AGUARDAR")
        self.assertFalse(result["can_feed_live_radar"])

    def test_blocked_comparison_has_no_levels(self):
        result = compare_eurusd_policy_levels_lab(
            ecb(b"junk", observed_at_utc=NOW), fed(fed_raw(), observed_at_utc=NOW))
        self.assertEqual(result["state"], "LAB_BLOCKED")
        self.assertIsNone(result["eur_deposit_facility_percent"])
        self.assertIsNone(result["fed_target_range_upper_percent"])

    def test_ecb_wrong_identity_dimension_and_status_rejected(self):
        for old, new in (
            ("FM.D.U2.EUR.4F.KR.DFR.LEV", "FM.D.U2.EUR.4F.KR.MRR_FR.LEV"),
            (",U2,", ",US,"), (",EUR,", ",USD,"),
            (",D,U2", ",M,U2"), (",A\n", ",P\n"),
        ):
            with self.subTest(new=new):
                self.assertEqual(ecb(ecb_raw().replace(old.encode(), new.encode()),
                                     observed_at_utc=NOW)["state"], "LAB_BLOCKED")

    def test_ecb_rejects_future_unsorted_duplicate_and_bad_calendar(self):
        for rows in (
            ECB_ROWS.replace("2026-09-16", "2027-09-16"),
            ECB_ROWS + ECB_ROWS.splitlines(keepends=True)[-1],
            "".join(reversed(ECB_ROWS.splitlines(keepends=True))),
            ECB_ROWS.replace("2026-09-16", "2026-02-30"),
        ):
            with self.subTest(rows=rows[-45:]):
                self.assertEqual(ecb(ecb_raw(rows), observed_at_utc=NOW)["state"],
                                 "LAB_BLOCKED")

    def test_fed_missing_historical_date_is_not_zero_or_interpolated(self):
        rows = FED_ROWS.replace("2026-11-02,3.75,4.00", "2026-11-02,.,.")
        r = fed(fed_raw(rows), observed_at_utc=NOW)
        self.assertEqual(r["missing_daily_rows"], ["2026-11-02"])
        self.assertEqual(r["latest_effective_date"], "2026-11-03")

    def test_fed_missing_latest_is_rejected_no_prior_rollover(self):
        rows = FED_ROWS.replace("2026-11-03,3.75,4.00", "2026-11-03,.,.")
        r = fed(fed_raw(rows), observed_at_utc=NOW)
        self.assertEqual(r["state"], "LAB_BLOCKED")
        self.assertIsNone(r["upper_bound_percent"])

    def test_fed_bad_range_wrong_units_or_false_future_rejected(self):
        for rows in (
            FED_ROWS.replace("3.75,4.00", "4.25,4.00"),
            FED_ROWS.replace("3.75,4.00", "3.75,6.25"),
            FED_ROWS.replace("3.75,4.00", "3.75,NaN"),
            FED_ROWS.replace("2026-11-03", "2026-11-06"),
            FED_ROWS.replace("2026-11-03", "2026-11-01"),
            FED_ROWS.replace("3.75,4.00", "3.75%,4.00%"),
        ):
            with self.subTest(rows=rows[-50:]):
                self.assertEqual(fed(fed_raw(rows), observed_at_utc=NOW)["state"],
                                 "LAB_BLOCKED")

    def test_fed_accepts_date_header_alias_only(self):
        raw = fed_raw(header="DATE,DFEDTARU,DFEDTARL\n",
                      rows="2026-11-03,4.00,3.75\n")
        self.assertEqual(fed(raw, observed_at_utc=NOW)["upper_bound_percent"],
                         "4.00")
        raw = fed_raw(header="DATE,observation_date,DFEDTARL,DFEDTARU\n",
                      rows="2026-11-03,2026-11-03,3.75,4.00\n")
        self.assertEqual(fed(raw, observed_at_utc=NOW)["state"], "LAB_BLOCKED")

    def test_malformed_csv_duplicate_header_and_non_utf8_blocked(self):
        cases = (
            b"\xff\xfe", b"", b"a" * (512 * 1024 + 1),
            ecb_raw(header=ECB_HEADER.replace("KEY,FREQ", "KEY,KEY,FREQ")),
            ecb_raw() + b"\x00",
            ecb_raw() + b"EXTRA\n",
            ecb_raw().replace(b"2.5000000", b"1e3"),
        )
        for raw in cases:
            with self.subTest(raw_size=len(raw)):
                self.assertEqual(ecb(raw, observed_at_utc=NOW)["state"],
                                 "LAB_BLOCKED")

    def test_time_clock_must_be_aware(self):
        for parser, raw in ((ecb, ecb_raw()), (fed, fed_raw())):
            with self.assertRaises(ValueError):
                parser(raw, observed_at_utc=NOW.replace(tzinfo=None))

    def test_no_live_http_or_collection_proof_from_caller_bytes(self):
        for parser, raw in ((ecb, ecb_raw()), (fed, fed_raw())):
            r = parser(raw, observed_at_utc=NOW)
            self.assertFalse(r["current_http_response_observed"])
            self.assertFalse(r["independent_fx_spot_verified"])
            self.assertFalse(r["worker_enabled"])
            self.assertFalse(r["scheduler_enabled"])
            self.assertEqual(r["new_cost_brl"], 0)


if __name__ == "__main__":
    unittest.main()
