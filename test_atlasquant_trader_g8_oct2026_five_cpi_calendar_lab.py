"""Immutable 5-source October 2026 CPI schedules; no implied CPI or trade."""
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
import json
import unittest

from atlasquant_fx_universe import OFFICIAL_PAIRS
from atlasquant_trader_g8_oct2026_five_cpi_calendar_lab import (
    PINNED_CASEBOOK_SHA256,
    inspect_g8_oct2026_five_cpi_calendar_lab as inspect,
)

CASE = (Path(__file__).resolve().parent / "docs" / "continuidade" /
        "TRADER_G8_OCT2026_FIVE_OFFICIAL_NEXT_CPI_CALENDAR_LAB_20261106.json").read_bytes()


def at(month, day, hour=0, minute=0):
    return datetime(2026, month, day, hour, minute, tzinfo=timezone.utc)


class G8OctoberCpiOfficialCalendarTests(unittest.TestCase):
    def case(self, when=at(11, 7), raw=CASE):
        return inspect(raw, as_of_utc=when)

    def assert_no_operation_or_actual(self, report):
        self.assertEqual(report["latest_official_cpi_actual_by_currency"], {})
        self.assertEqual(report["release_surprises"], {})
        self.assertIsNone(report["currency_strength_score"])
        self.assertIsNone(report["fx_bias"])
        self.assertEqual(report["operational_bias"], "AGUARDAR")
        self.assertEqual(report["ranked_currencies"], [])
        self.assertIsNone(report["best_pair_of_day"])
        self.assertEqual((report["validated_forward_prediction_count"],
                          report["validated_accuracy"]), (0, None))
        self.assertEqual((report["http_requests"], report["new_cost_brl"]), (0, 0))
        for key in ("can_feed_live_radar", "trade_authorized", "publishable",
                    "worker_enabled", "scheduler_enabled",
                    "original_source_bytes_archived",
                    "source_consultation_instant_independently_attested"):
            self.assertFalse(report[key], key)
        for row in report["pair_rows"]:
            self.assertEqual((row["D1"], row["W1"]), ("AGUARDAR", "AGUARDAR"))
            self.assertIsNone(row["relative_macro_score"])
            self.assertIsNone(row["currency_strength_score"])
            self.assertIsNone(row["market_surprise"])
            self.assertFalse(row["trade_authorized"])
            for event in row["calendar_events"]:
                self.assertIsNone(event["official_actual"])
                self.assertIsNone(event["surprise"])

    def test_pinned_manual_five_source_casebook(self):
        self.assertEqual(sha256(CASE).hexdigest(), PINNED_CASEBOOK_SHA256)
        report = self.case()
        self.assertEqual(report["state"],
                         "LAB_FIVE_CPI_SCHEDULE_DATES_ROUTED_NO_RELEASE_ACTUAL_OR_FX_BIAS")
        self.assertEqual(report["official_sources_checked"], 5)
        self.assertEqual(report["casebook_sha256"], PINNED_CASEBOOK_SHA256)
        events = report["visible_calendar_events"]
        self.assertEqual([(e["currency"], e["scheduled_calendar_date"]) for e in events], [
            ("USD", "2026-11-10"), ("CAD", "2026-11-16"),
            ("EUR", "2026-11-18"), ("GBP", "2026-11-18"),
            ("AUD", "2026-11-25"),
        ])
        self.assertEqual({e["reference_month"] for e in events}, {"2026-10"})
        self.assert_no_operation_or_actual(report)

    def test_28_pairs_25_with_calendar_10_two_15_one_3_zero(self):
        report = self.case()
        self.assertEqual((report["pair_count"], report["pairs_with_calendar_metadata"],
                          report["pairs_with_two_calendar_currencies"],
                          report["pairs_with_one_calendar_currency"],
                          report["pairs_without_calendar_metadata"]),
                         (28, 25, 10, 15, 3))
        self.assertEqual(report["pairs_with_an_upcoming_calendar_event"], 25)
        self.assertEqual({r["pair"] for r in report["pair_rows"]}, set(OFFICIAL_PAIRS))
        self.assert_no_operation_or_actual(report)

    def test_pair_events_match_only_base_and_quote_and_role(self):
        report = self.case()
        for row in report["pair_rows"]:
            currencies = {evt["currency"] for evt in row["calendar_events"]}
            self.assertEqual(currencies, {row["base"], row["quote"]}
                             - {"CHF", "JPY", "NZD"})
            for evt in row["calendar_events"]:
                self.assertEqual(evt["pair_currency_role"],
                                 "BASE" if evt["currency"] == row["base"] else "QUOTE")
        self.assert_no_operation_or_actual(report)

    def test_eurusd_events_are_different_national_indices_and_dates(self):
        row = {r["pair"]: r for r in self.case()["pair_rows"]}["EUR/USD"]
        self.assertEqual([e["currency"] for e in row["calendar_events"]], ["USD", "EUR"])
        self.assertEqual([e["pair_currency_role"] for e in row["calendar_events"]],
                         ["QUOTE", "BASE"])
        self.assertEqual(row["next_calendar_date"], "2026-11-10")
        self.assertEqual([e["currency"] for e in row["next_calendar_events"]], ["USD"])

    def test_eurgbp_same_day_two_events_retained(self):
        row = {r["pair"]: r for r in self.case()["pair_rows"]}["EUR/GBP"]
        self.assertEqual(row["next_calendar_date"], "2026-11-18")
        self.assertEqual([e["currency"] for e in row["next_calendar_events"]],
                         ["EUR", "GBP"])
        self.assertTrue(all(e["official_actual"] is None for e in row["next_calendar_events"]))

    def test_unscheduled_three_currency_pairs_are_cohort_absence_only(self):
        rows = {r["pair"]: r for r in self.case()["pair_rows"]}
        for pair in ("CHF/JPY", "NZD/CHF", "NZD/JPY"):
            self.assertEqual(rows[pair]["calendar_events"], [])
            self.assertIsNone(rows[pair]["next_calendar_date"])
        self.assert_no_operation_or_actual(self.case())

    def test_research_gate_fails_closed_without_leaking_calendar(self):
        for when in (at(11, 6, 23, 59), at(10, 1), at(1, 1)):
            report = self.case(when)
            self.assertEqual(report["state"], "LAB_OFFICIAL_SCHEDULE_NOT_VISIBLE_ASOF")
            self.assertEqual(report["visible_calendar_events"], [])
            self.assertEqual((report["pairs_with_calendar_metadata"],
                              report["pairs_without_calendar_metadata"]), (0, 28))
            self.assertEqual(report["pairs_with_an_upcoming_calendar_event"], 0)
            self.assert_no_operation_or_actual(report)

    def test_timezone_equivalence_and_naive_clock_blocked(self):
        self.assertEqual(self.case(datetime(2026, 11, 6, 20, tzinfo=timezone(
            timedelta(hours=-4)))), self.case(at(11, 7)))
        for when in (None, "2026-11-07", datetime(2026, 11, 7)):
            report = self.case(when)
            self.assertEqual(report["state"], "LAB_BLOCKED")
            self.assertEqual(report["pair_rows"], [])
            self.assert_no_operation_or_actual(report)

    def test_schedule_date_passes_but_no_actual_or_surprise_emerges(self):
        for when, passed in ((at(11, 10), []), (at(11, 11), ["USD"]),
                             (at(11, 17), ["USD", "CAD"]),
                             (at(11, 19), ["USD", "CAD", "EUR", "GBP"]),
                             (at(11, 26), ["USD", "CAD", "EUR", "GBP", "AUD"]),
                             (at(12, 15), ["USD", "CAD", "EUR", "GBP", "AUD"])):
            report = self.case(when)
            actual_passed = [e["currency"] for e in report["visible_calendar_events"]
                             if e["calendar_status"] ==
                             "SCHEDULE_DATE_PASSED_ACTUAL_UNVERIFIED"]
            self.assertEqual(actual_passed, passed)
            self.assertEqual(report["pairs_with_calendar_metadata"], 25)
            self.assert_no_operation_or_actual(report)

    def test_expired_schedule_cannot_be_the_next_event(self):
        rows = {r["pair"]: r for r in self.case(at(11, 11))["pair_rows"]}
        self.assertEqual(rows["EUR/USD"]["next_calendar_date"], "2026-11-18")
        self.assertEqual([e["currency"] for e in rows["EUR/USD"]["next_calendar_events"]],
                         ["EUR"])
        self.assertIsNone(rows["USD/JPY"]["next_calendar_date"])
        after_all = self.case(at(11, 26))
        self.assertEqual(after_all["pairs_with_an_upcoming_calendar_event"], 0)
        self.assert_no_operation_or_actual(after_all)

    def test_mutated_snapshot_bytes_fail_closed(self):
        for raw in (CASE + b" ", CASE[:-1], CASE.replace(b"2026-11-10", b"2026-11-09"),
                    CASE.replace(b'"actual_headline_yoy_percent": null',
                                 b'"actual_headline_yoy_percent": 3.2'),
                    b"{}", None, "casebook"):
            report = self.case(raw=raw)
            self.assertEqual(report["state"], "LAB_BLOCKED")
            self.assertEqual(report["visible_calendar_events"], [])
            self.assertEqual(report["pair_rows"], [])
            self.assert_no_operation_or_actual(report)

    def test_json_validation_enforces_shape_even_if_pin_were_updated(self):
        # Byte pin is the first barrier; these changes also violate the explicit schema.
        case = json.loads(CASE)
        for mutate in (
            lambda d: d.update(sources_checked=True),
            lambda d: d["events"].pop(),
            lambda d: d["events"][0].update(actual_value_published_in_casebook=True),
            lambda d: d["events"][0].update(actual_headline_yoy_percent=3.1),
            lambda d: d.update(may_generate_currency_strength_or_fx_bias=True),
            lambda d: d["events"][2].update(release_stage="FLASH_INSTEAD_OF_FULL"),
        ):
            d = json.loads(json.dumps(case))
            mutate(d)
            raw = json.dumps(d).encode()
            self.assertEqual(self.case(raw=raw)["state"], "LAB_BLOCKED")


if __name__ == "__main__":
    unittest.main()
