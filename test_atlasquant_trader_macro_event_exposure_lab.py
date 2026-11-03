"""Documentary macro event exposure, not a predictive signal."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import unittest

from atlasquant_fx_universe import OFFICIAL_PAIRS
from atlasquant_trader_macro_event_exposure_lab import (
    CALENDAR, HORIZONS, INDICES, SCHEMA, build_macro_event_exposure_lab,
)

AT = datetime(2026, 11, 3, 12, 0, tzinfo=timezone.utc)


def watch(at=AT, schedule=None):
    return build_macro_event_exposure_lab(at=at, schedule=schedule)


def fx(report, pair, horizon):
    return next(row for row in report["fx_rows"]
                if row["pair"] == pair and row["horizon"] == horizon)


def index(report, instrument, horizon):
    return next(row for row in report["index_rows"]
                if row["instrument"] == instrument and row["horizon"] == horizon)


def ids(row):
    return [e["event_id"] for e in row["event_exposures"]]


class MacroEventExposureLabTests(unittest.TestCase):
    def test_schema_and_research_only(self):
        r = watch()
        self.assertEqual(r["schema"], SCHEMA)
        self.assertEqual(r["state"], "LAB_CALENDAR_RISK_EXPOSURE_ONLY")

    def test_canonical_28_and_three_horizons(self):
        r = watch()
        self.assertEqual(r["fx_row_count"], 84)
        self.assertEqual(len(r["fx_rows"]), 28 * 3)
        self.assertEqual(
            {(row["pair"], row["horizon"]) for row in r["fx_rows"]},
            {(p, h) for p in OFFICIAL_PAIRS for h in HORIZONS},
        )

    def test_five_indices_and_three_horizons(self):
        r = watch()
        self.assertEqual(r["index_row_count"], 15)
        self.assertEqual(
            {(row["instrument"], row["horizon"]) for row in r["index_rows"]},
            {(i, h) for i in INDICES for h in HORIZONS},
        )

    def test_rolling_window_sizes_explicit(self):
        self.assertEqual(watch()["rolling_windows"],
                         {"D1": 86400, "W1": 604800, "MN1": 2592000})

    def test_daily_no_event_at_nov3_noon(self):
        r = watch()
        self.assertTrue(all(not row["event_exposures"]
                            for row in r["fx_rows"] if row["horizon"] == "D1"))
        self.assertTrue(all(not row["event_exposures"]
                            for row in r["index_rows"] if row["horizon"] == "D1"))

    def test_weekly_gbp_and_us_employment_not_cpi(self):
        r = watch()
        self.assertEqual(ids(fx(r, "GBP/USD", "W1")),
                         ["BOE_MPC_20261105", "BLS_US_EMPLOYMENT_20261106"])
        self.assertNotIn("BLS_US_CPI_20261110", ids(fx(r, "GBP/USD", "W1")))

    def test_monthly_gbpusd_three_distinct_events(self):
        self.assertEqual(len(ids(fx(watch(), "GBP/USD", "MN1"))), 3)

    def test_gbp_only_has_boe(self):
        r = watch()
        self.assertEqual(ids(fx(r, "EUR/GBP", "W1")), ["BOE_MPC_20261105"])

    def test_usd_only_has_employment(self):
        r = watch()
        self.assertEqual(ids(fx(r, "EUR/USD", "W1")),
                         ["BLS_US_EMPLOYMENT_20261106"])

    def test_euro_aussie_not_claimed_directly_exposed(self):
        self.assertEqual(ids(fx(watch(), "EUR/AUD", "MN1")), [])

    def test_unaffected_pair_not_claimed_macro_safe(self):
        self.assertEqual(fx(watch(), "EUR/AUD", "W1")["risk_status"],
                         "NO_EVENT_FROM_THIS_PARTIAL_CALENDAR")

    def test_13_unique_direct_fx_pairs_in_weekly_watch(self):
        rows = [row for row in watch()["fx_rows"]
                if row["horizon"] == "W1" and row["event_exposures"]]
        self.assertEqual(len(rows), 13)

    def test_us_indices_have_us_macro_risk_not_boe(self):
        r = watch()
        for instrument in ("SPX500", "NAS100", "US30"):
            with self.subTest(instrument=instrument):
                row = index(r, instrument, "W1")
                self.assertEqual(ids(row), ["BLS_US_EMPLOYMENT_20261106"])
                self.assertEqual(row["event_exposures"][0]["exposure_channel"],
                                 "US_DOMESTIC_MACRO_CONTEXT")

    def test_brazil_indices_indirect_channel_not_proven(self):
        r = watch()
        for instrument in ("WIN", "WDO"):
            with self.subTest(instrument=instrument):
                row = index(r, instrument, "W1")
                self.assertEqual(row["event_exposures"][0]["exposure_channel"],
                                 "INDIRECT_US_CONTEXT_UNVERIFIED")

    def test_research_has_exact_three_cited_schedule_references(self):
        r = watch()
        self.assertEqual(r["curated_event_count"], 3)
        self.assertEqual(
            [event["source_url"] for event in r["events"]],
            [event["source_url"] for event in CALENDAR],
        )

    def test_boe_date_only_must_not_invent_time(self):
        r = watch()
        boe = r["events"][0]
        self.assertEqual(boe["time_precision"], "DATE_ONLY")
        self.assertEqual(boe["earliest_at_utc"], "2026-11-05T00:00:00Z")
        self.assertEqual(boe["latest_at_utc"], "2026-11-05T23:59:59Z")

    def test_nov4_daily_boe_boundary_uncertain(self):
        r = watch(at=datetime(2026, 11, 4, 15, tzinfo=timezone.utc))
        row = fx(r, "GBP/USD", "D1")
        self.assertEqual(row["event_exposures"][0]["timing_state"],
                         "WINDOW_EDGE_TIME_UNCERTAIN")

    def test_nov5_boe_may_have_already_occurred(self):
        r = watch(at=datetime(2026, 11, 5, 15, tzinfo=timezone.utc))
        row = fx(r, "GBP/USD", "D1")
        self.assertEqual(row["event_exposures"][0]["timing_state"],
                         "DATE_ONLY_MAY_ALREADY_HAVE_OCCURRED")

    def test_next_day_boe_no_longer_upcoming(self):
        r = watch(at=datetime(2026, 11, 6, 0, tzinfo=timezone.utc))
        row = fx(r, "GBP/USD", "D1")
        self.assertNotIn("BOE_MPC_20261105", ids(row))

    def test_employment_at_release_exactly_not_upcoming(self):
        r = watch(at=datetime(2026, 11, 6, 13, 30, tzinfo=timezone.utc))
        self.assertNotIn("BLS_US_EMPLOYMENT_20261106",
                         ids(fx(r, "EUR/USD", "D1")))

    def test_cpi_enters_weekly_window_at_precise_boundary(self):
        r = watch(at=datetime(2026, 11, 3, 13, 30, tzinfo=timezone.utc))
        self.assertIn("BLS_US_CPI_20261110", ids(fx(r, "EUR/USD", "W1")))

    def test_hour_boundary_not_date_rounding(self):
        r = watch(at=datetime(2026, 11, 3, 13, 29, tzinfo=timezone.utc))
        self.assertNotIn("BLS_US_CPI_20261110", ids(fx(r, "EUR/USD", "W1")))

    def test_naive_time_rejected(self):
        with self.assertRaises(ValueError):
            watch(at=datetime(2026, 11, 3, 12))

    def test_before_research_date_rejected(self):
        with self.assertRaises(ValueError):
            watch(at=datetime(2026, 11, 2, 23, tzinfo=timezone.utc))

    def test_non_datetime_time_rejected(self):
        with self.assertRaises(ValueError):
            watch(at="2026-11-03T12:00:00Z")

    def test_aware_non_utc_equivalent(self):
        offset = timezone(timedelta(hours=-4))
        r = watch(at=datetime(2026, 11, 3, 8, tzinfo=offset))
        self.assertEqual(r["as_of_utc"], AT.isoformat())

    def test_caller_can_provide_exact_canonical_copy(self):
        self.assertEqual(watch(schedule=deepcopy(list(CALENDAR))), watch())

    def test_missing_event_rejected(self):
        with self.assertRaises(ValueError):
            watch(schedule=list(CALENDAR)[:2])

    def test_duplicate_event_rejected(self):
        bad = deepcopy(list(CALENDAR))
        bad[1] = deepcopy(bad[0])
        with self.assertRaises(ValueError):
            watch(schedule=bad)

    def test_shifted_release_time_rejected(self):
        bad = deepcopy(list(CALENDAR))
        bad[1]["earliest_at_utc"] = "2026-11-06T12:30:00Z"
        bad[1]["latest_at_utc"] = "2026-11-06T12:30:00Z"
        with self.assertRaises(ValueError):
            watch(schedule=bad)

    def test_fake_official_host_rejected(self):
        bad = deepcopy(list(CALENDAR))
        bad[2]["source_url"] = "https://www.bls.gov.evil.test/schedule/news_release/cpi.htm"
        with self.assertRaises(ValueError):
            watch(schedule=bad)

    def test_added_direction_field_rejected(self):
        bad = deepcopy(list(CALENDAR))
        bad[0]["gbpusd_direction"] = "BAIXA"
        with self.assertRaises(ValueError):
            watch(schedule=bad)

    def test_consensus_or_actual_injection_rejected(self):
        for key in ("consensus", "actual", "probability_90_pct"):
            with self.subTest(key=key):
                bad = deepcopy(list(CALENDAR))
                bad[1][key] = "0.9"
                with self.assertRaises(ValueError):
                    watch(schedule=bad)

    def test_no_real_verification_claims(self):
        r = watch()
        for key in ("calendar_complete", "calendar_realtime_refreshed",
                    "source_original_bytes_archived",
                    "independent_source_receipt_verified", "consensus_verified",
                    "actual_releases_verified", "market_price_reaction_verified",
                    "real_oos_accuracy_proven", "accuracy_90_proven",
                    "market_direction_inferred", "can_feed_live_radar",
                    "trade_authorized", "worker_enabled", "scheduler_enabled"):
            with self.subTest(key=key):
                self.assertIs(r[key], False)

    def test_every_row_abstains_from_direction_and_trading(self):
        r = watch()
        for row in r["fx_rows"] + r["index_rows"]:
            with self.subTest(row=row):
                self.assertEqual(row["bias"], "AGUARDAR")
                self.assertIsNone(row["direction_probability"])
                self.assertFalse(row["trade_authorized"])

    def test_individual_events_are_unique_and_not_independent_forecasts(self):
        r = watch()
        self.assertEqual(len({e["event_id"] for e in r["events"]}), 3)
        self.assertFalse(r["market_direction_inferred"])

    def test_canonical_full_calendar_requires_review_and_version_change(self):
        with self.assertRaises(ValueError):
            watch(schedule=[])
        with self.assertRaises(ValueError):
            watch(schedule="https://example.com/calendar")


if __name__ == "__main__":
    unittest.main()
