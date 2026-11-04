"""V2 calendar: official-page review, vintage safety, timezone, no direction."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import unittest
from zoneinfo import ZoneInfo

from atlasquant_fx_universe import OFFICIAL_PAIRS
from atlasquant_trader_macro_event_exposure_v2_lab import (
    CALENDAR, REVIEW_DATE, SCHEMA, build_macro_event_exposure_v2_lab,
)

AT = datetime(2026, 11, 4, 12, tzinfo=timezone.utc)


def watch(at=AT, schedule=None):
    return build_macro_event_exposure_v2_lab(at=at, schedule=schedule)


def fx(result, pair, horizon):
    return next(x for x in result["fx_rows"]
                if x["pair"] == pair and x["horizon"] == horizon)


def event_ids(result, pair, horizon):
    return [x["event_id"] for x in fx(result, pair, horizon)["event_exposures"]]


class OfficialReviewV2LabTests(unittest.TestCase):
    def test_review_vintage_and_10_events_do_not_promote_calendar(self):
        r = watch()
        self.assertEqual(r["schema"], SCHEMA)
        self.assertEqual(r["calendar_review_date_utc"], REVIEW_DATE.isoformat())
        self.assertEqual(r["calendar_version"], "V2_OFFICIAL_PAGE_REVIEW")
        self.assertEqual(r["curated_event_count"], 10)
        self.assertEqual(r["fx_row_count"], 84)
        self.assertEqual(r["index_row_count"], 15)
        self.assertEqual({(x["pair"], x["horizon"]) for x in r["fx_rows"]},
                         {(p, h) for p in OFFICIAL_PAIRS
                          for h in ("D1", "W1", "MN1")})
        self.assertEqual(r["rolling_windows"],
                         {"D1": 86400, "W1": 604800, "MN1": 2592000})
        for key in ("calendar_complete", "calendar_realtime_refreshed",
                    "source_original_bytes_archived",
                    "independent_source_receipt_verified", "consensus_verified",
                    "actual_releases_verified", "market_price_reaction_verified",
                    "real_oos_accuracy_proven", "accuracy_90_proven",
                    "market_direction_inferred", "can_feed_live_radar",
                    "trade_authorized", "worker_enabled", "scheduler_enabled"):
            self.assertIs(r[key], False, key)
        for x in r["fx_rows"] + r["index_rows"]:
            self.assertEqual(x["bias"], "AGUARDAR")
            self.assertIsNone(x["direction_probability"])
            self.assertFalse(x["trade_authorized"])

    def test_fx_currencies_have_documentary_exposure_not_direction(self):
        r = watch()
        self.assertEqual(event_ids(r, "GBP/JPY", "D1"),
                         ["BOE_MPC_20261105"])
        self.assertEqual(event_ids(r, "USD/CAD", "W1"),
                         ["BLS_US_PRODUCTIVITY_20261105", "STATCAN_CA_LFS_20261106",
                          "BLS_US_EMPLOYMENT_20261106", "BLS_US_CPI_20261110"])
        self.assertIn("ABS_AU_LABOR_20261119", event_ids(r, "EUR/AUD", "MN1"))
        self.assertIn("RBNZ_NZ_FSR_20261117", event_ids(r, "EUR/NZD", "MN1"))
        self.assertIn("ONS_UK_GDP_20261112", event_ids(r, "EUR/GBP", "MN1"))
        self.assertIn("ONS_UK_LABOR_20261117", event_ids(r, "EUR/GBP", "MN1"))
        self.assertEqual(event_ids(r, "EUR/JPY", "MN1"), [])
        self.assertEqual(fx(r, "EUR/JPY", "MN1")["risk_status"],
                         "NO_EVENT_FROM_THIS_PARTIAL_CALENDAR")

    def test_boe_time_is_precise_in_v2_without_rewriting_v1(self):
        r = watch()
        boe = r["events"][0]
        self.assertEqual((boe["time_precision"], boe["earliest_at_utc"]),
                         ("SCHEDULED_MINUTE", "2026-11-05T12:00:00Z"))
        future = watch(datetime(2026, 11, 5, 12, tzinfo=timezone.utc))
        self.assertNotIn("BOE_MPC_20261105", event_ids(future, "GBP/JPY", "D1"))
        from atlasquant_trader_macro_event_exposure_lab import CALENDAR as OLD
        self.assertEqual((OLD[0]["time_precision"], OLD[0]["earliest_at_utc"]),
                         ("DATE_ONLY", "2026-11-05T00:00:00Z"))

    def test_rbnz_corrected_fsr_is_not_11_nov_policy(self):
        r = watch()
        nz = next(x for x in r["events"] if x["currency"] == "NZD")
        self.assertEqual(nz["event_kind"],
                         "FINANCIAL_STABILITY_REPORT_NOT_POLICY_DECISION")
        self.assertEqual(nz["event_id"], "RBNZ_NZ_FSR_20261117")
        self.assertEqual(nz["earliest_at_utc"],
                         datetime(2026, 11, 17, 9,
                                  tzinfo=ZoneInfo("Pacific/Auckland"))
                         .astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
        self.assertNotIn("RBNZ_NZ_FSR_20261117",
                         event_ids(r, "EUR/NZD", "W1"))

    def test_australia_dst_release_utc_conversion(self):
        au = next(x for x in CALENDAR if x["currency"] == "AUD")
        expected = datetime(2026, 11, 19, 11, 30,
                            tzinfo=ZoneInfo("Australia/Sydney"))
        self.assertEqual(au["earliest_at_utc"],
                         expected.astimezone(timezone.utc)
                         .strftime("%Y-%m-%dT%H:%M:%SZ"))

    def test_canadian_labor_does_not_invent_time(self):
        ca = next(x for x in CALENDAR if x["currency"] == "CAD")
        self.assertEqual(ca["time_precision"], "DATE_ONLY")
        r = watch(datetime(2026, 11, 6, 12, tzinfo=timezone.utc))
        e = next(x for x in fx(r, "USD/CAD", "D1")["event_exposures"]
                 if x["currency"] == "CAD")
        self.assertEqual(e["timing_state"],
                         "DATE_ONLY_MAY_ALREADY_HAVE_OCCURRED")

    def test_us_index_coverage_stays_distinct_from_win_wdo(self):
        r = watch()
        for x in r["index_rows"]:
            if x["event_exposures"]:
                channel = ("US_DOMESTIC_MACRO_CONTEXT"
                           if x["instrument"] in ("SPX500", "NAS100", "US30")
                           else "INDIRECT_US_CONTEXT_UNVERIFIED")
                self.assertTrue(all(e["currency"] == "USD" and
                                    e["exposure_channel"] == channel
                                    for e in x["event_exposures"]))

    def test_vintage_gate_disallows_retroactive_nov3_review(self):
        with self.assertRaises(ValueError):
            watch(datetime(2026, 11, 3, 23, 59, tzinfo=timezone.utc))
        with self.assertRaises(ValueError):
            watch(AT.replace(tzinfo=None))
        with self.assertRaises(ValueError):
            watch("2026-11-04T12:00:00Z")

    def test_exact_canonical_copy_and_timezone_normalization(self):
        self.assertEqual(watch(schedule=deepcopy(list(CALENDAR))), watch())
        as_manaus = datetime(2026, 11, 4, 8,
                             tzinfo=timezone(timedelta(hours=-4)))
        self.assertEqual(watch(as_manaus), watch())

    def test_missing_extra_duplicate_event_are_rejected(self):
        for kind in ("missing", "extra", "duplicate"):
            with self.subTest(kind=kind):
                c = deepcopy(list(CALENDAR))
                if kind == "missing":
                    c.pop()
                elif kind == "extra":
                    c.append(deepcopy(c[0]))
                else:
                    c[1] = deepcopy(c[0])
                with self.assertRaises(ValueError):
                    watch(schedule=c)

    def test_fake_schedule_authority_and_direction_are_rejected(self):
        for field, value in (("earliest_at_utc", "2026-11-11T20:00:00Z"),
                             ("source_url", "https://www.rbnz.govt.nz.evil.test"),
                             ("event_kind", "POLICY_RATE_DECISION"),
                             ("consensus", 0.75), ("pair_direction", "ALTA")):
            with self.subTest(field=field):
                c = deepcopy(list(CALENDAR))
                c[7][field] = value
                with self.assertRaises(ValueError):
                    watch(schedule=c)


if __name__ == "__main__":
    unittest.main()
