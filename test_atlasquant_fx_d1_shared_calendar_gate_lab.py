"""Synthetic contracts for AtlasQuant FX D1 date completeness. No prices used."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import unittest

from atlasquant_instrument_registry import FX_28

from atlasquant_fx_d1_shared_calendar_gate_lab import (
    inspect_d1_date_coverage_lab as check,
)

FIXED_AS_OF_UTC = datetime(2026, 11, 16, 18, 0, tzinfo=timezone.utc)

SYMBOLS = (
    "EURUSD","GBPUSD","AUDUSD","NZDUSD","USDJPY","USDCHF","USDCAD",
    "EURGBP","EURJPY","EURCHF","EURCAD","EURAUD","EURNZD",
    "GBPJPY","GBPCHF","GBPCAD","GBPAUD","GBPNZD",
    "AUDJPY","AUDCHF","AUDCAD","AUDNZD",
    "NZDJPY","NZDCHF","NZDCAD","CADJPY","CADCHF","CHFJPY",
)

class D1CalendarGateTests(unittest.TestCase):
    def call(self, present, date_string="2025-09-30", cohort=SYMBOLS):
        result = check(trading_date=date.fromisoformat(date_string),
                       present_symbols=present, expected_symbols=cohort,
                       as_of_utc=FIXED_AS_OF_UTC)
        self.assertEqual(result["operational_bias"], "AGUARDAR")
        self.assertFalse(result["trade_authorized"])
        self.assertFalse(result["publishable"])
        self.assertFalse(result["imputation_allowed"])
        self.assertFalse(result["unrestricted_backtest_authorized"])
        self.assertFalse(result["trading_calendar_independently_verified"])
        self.assertFalse(result["historical_broker_source_independently_verified"])
        self.assertIsNone(result["direction_probability"])
        return result

    def test_all_present_is_only_documentary_completeness(self):
        row=self.call(SYMBOLS)
        self.assertEqual(row["observed_count"], 28)
        self.assertTrue(row["rank_28fx_coverage_complete"])
        self.assertEqual(row["status"],"LAB_ALL_28_D1_BARS_PRESENT_DOCUMENTARY_UNATTESTED")

    def test_gbpnzd_isolated_gap_quarantined(self):
        row=self.call(tuple(s for s in SYMBOLS if s!="GBPNZD"))
        self.assertEqual(row["missing_symbols"], ["GBPNZD"])
        self.assertEqual(row["missing_count"],1)
        self.assertEqual(row["status"],"LAB_SINGLE_PAIR_D1_MISSING_DATE_QUARANTINE")
        self.assertFalse(row["rank_28fx_coverage_complete"])

    def test_whole_cohort_without_candles_not_labeled_as_holiday(self):
        row=self.call((),date_string="2025-12-25")
        self.assertEqual(row["status"],"LAB_SHARED_28FX_NO_D1_BARS_CALENDAR_UNVERIFIED")
        self.assertEqual(row["missing_count"],28)
        self.assertNotIn("holiday_verified",row)

    def test_partial_coverage_8_and_18(self):
        for n in (8,18):
            with self.subTest(n=n):
                row=self.call(SYMBOLS[:n])
                self.assertEqual(row["status"],"LAB_PARTIAL_D1_COHORT_CALENDAR_UNVERIFIED")
                self.assertEqual(row["observed_count"],n)
                self.assertFalse(row["rank_28fx_coverage_complete"])

    def test_duplicate_pair_is_blocked_even_if_list_length_28(self):
        row=self.call(SYMBOLS[:-1]+(SYMBOLS[0],))
        self.assertEqual(row["reason"],"UNKNOWN_OR_DUPLICATE_D1_SYMBOL")

    def test_unknown_instrument_is_blocked(self):
        row=self.call(SYMBOLS[:-1]+("XAUUSD",))
        self.assertEqual(row["reason"],"UNKNOWN_OR_DUPLICATE_D1_SYMBOL")

    def test_missing_expected_pair_in_registry_rejected(self):
        row=self.call(SYMBOLS,cohort=SYMBOLS[:-1])
        self.assertEqual(row["reason"],"INVALID_CALENDAR_OR_COHORT")

    def test_non_date_and_non_tuple_universe_rejected(self):
        for wrong_date in (None,"2025-09-30"):
            with self.subTest(wrong_date=wrong_date):
                row=check(trading_date=wrong_date,present_symbols=SYMBOLS,
                          expected_symbols=SYMBOLS,as_of_utc=FIXED_AS_OF_UTC)
                self.assertEqual(row["status"],"LAB_D1_CALENDAR_BLOCKED")
                self.assertFalse(row["trade_authorized"])
        row=check(trading_date=date(2025,9,30),present_symbols=SYMBOLS,
                  expected_symbols=list(SYMBOLS),as_of_utc=FIXED_AS_OF_UTC)
        self.assertEqual(row["status"],"LAB_D1_CALENDAR_BLOCKED")

    def test_no_implicit_profit_or_probability(self):
        row=self.call(SYMBOLS)
        self.assertNotIn("win_rate",row)
        self.assertNotIn("net_profit",row)
        self.assertFalse(row["out_of_sample_accuracy_verified"])

    # Extra synthetic adversarial cases; original nine test methods retained.
    def test_registry_constant_is_exact_official_source_not_caller_claim(self):
        self.assertEqual(SYMBOLS, FX_28)
        row=self.call(FX_28,cohort=FX_28)
        self.assertTrue(row["rank_28fx_coverage_complete"])
        self.assertEqual(row["observed_count"],28)

    def test_forged_universe_of_28_valid_length_strings_is_blocked(self):
        forged=tuple("ZZ"+str(i).zfill(4) for i in range(28))
        row=self.call(forged,cohort=forged)
        self.assertEqual(row["reason"],"INVALID_CALENDAR_OR_COHORT")
        self.assertFalse(row["rank_28fx_coverage_complete"])

    def test_exact_registry_order_is_mandatory_even_with_same_set(self):
        reversed_registry=tuple(reversed(FX_28))
        row=self.call(FX_28,cohort=reversed_registry)
        self.assertEqual(row["status"],"LAB_D1_CALENDAR_BLOCKED")
        self.assertEqual(row["reason"],"INVALID_CALENDAR_OR_COHORT")

    def test_expected_registry_lowercase_or_whitespace_not_normalized(self):
        for bad in (("eurusd",)+FX_28[1:],
                    (" EURUSD",)+FX_28[1:],
                    ("EURUSD ",)+FX_28[1:],
                    ("",)+FX_28[1:]):
            with self.subTest(first=bad[0]):
                out=self.call(FX_28,cohort=bad)
                self.assertEqual(out["reason"],"INVALID_CALENDAR_OR_COHORT")

    def test_present_lowercase_space_empty_is_rejected_unmodified(self):
        for bad in ("eurusd","EURUSD "," EURUSD",""):
            with self.subTest(bad=bad):
                row=self.call((bad,)+FX_28[1:])
                self.assertEqual(row["reason"],"UNKNOWN_OR_DUPLICATE_D1_SYMBOL")
                self.assertFalse(row["rank_28fx_coverage_complete"])

    def test_wrong_present_type_generator_and_nontext_rejected(self):
        for bad in ("EURUSD", iter(FX_28), [FX_28[0], None], 5):
            with self.subTest(value=type(bad)):
                row=check(trading_date=date(2025,9,30),
                          present_symbols=bad,expected_symbols=FX_28,
                          as_of_utc=FIXED_AS_OF_UTC)
                self.assertEqual(row["status"],"LAB_D1_CALENDAR_BLOCKED")

    def test_unhashable_cohort_malformed_type_never_crashes(self):
        wrong=(["EURUSD"],)+FX_28[1:]
        row=check(trading_date=date(2025,9,30),
                  present_symbols=FX_28,expected_symbols=wrong,
                  as_of_utc=FIXED_AS_OF_UTC)
        self.assertEqual(row["reason"],"INVALID_CALENDAR_OR_COHORT")

    def test_missing_as_of_utc_fails_closed_not_typeerror(self):
        row=check(trading_date=date(2025,9,30),
                  present_symbols=FX_28,expected_symbols=FX_28)
        self.assertEqual(row["reason"],"MISSING_OR_INVALID_AS_OF_UTC")
        self.assertFalse(row["rank_28fx_coverage_complete"])
        self.assertFalse(row["trade_authorized"])

    def test_naive_non_utc_and_non_datetime_clock_are_blocked(self):
        for clock in (datetime(2026,11,16,18,0), None,
                      datetime(2026,11,16,19,0,tzinfo=timezone(timedelta(hours=1))),
                      "2026-11-16T18:00:00Z",date(2026,11,16),True):
            with self.subTest(clock=str(clock)):
                row=check(trading_date=date(2025,9,30),
                          present_symbols=FX_28,expected_symbols=FX_28,
                          as_of_utc=clock)
                self.assertEqual(row["reason"],"MISSING_OR_INVALID_AS_OF_UTC")

    def test_far_future_2999_cannot_be_marked_complete_at_either_offset(self):
        for offset in (None,2,3):
            with self.subTest(offset=offset):
                row=check(trading_date=date(2999,1,1),
                          present_symbols=FX_28,expected_symbols=FX_28,
                          as_of_utc=FIXED_AS_OF_UTC,
                          server_utc_offset_hours=offset)
                self.assertEqual(row["status"],"LAB_D1_CALENDAR_BLOCKED")
                self.assertFalse(row["rank_28fx_coverage_complete"])

    def test_one_day_future_without_verified_server_offset_blocks(self):
        row=check(trading_date=date(2026,11,16),
                  present_symbols=FX_28,expected_symbols=FX_28,
                  as_of_utc=datetime(2026,11,15,22,1,tzinfo=timezone.utc))
        self.assertEqual(row["reason"],
                         "FUTURE_D1_DATE_REQUIRES_SERVER_OFFSET_TO_CHECK_CALENDAR")

    def test_monday_server_gmt2_from_sunday_utc_is_suspect_not_complete(self):
        sunday=datetime(2026,11,15,22,1,tzinfo=timezone.utc)
        row=check(trading_date=date(2026,11,16),present_symbols=FX_28,
                  expected_symbols=FX_28,as_of_utc=sunday,
                  server_utc_offset_hours=2)
        self.assertEqual(row["status"],
                         "LAB_D1_UTC_SUNDAY_SERVER_MONDAY_SUSPECT_UNAUTHENTICATED")
        self.assertFalse(row["rank_28fx_coverage_complete"])
        self.assertTrue(row["server_day_ahead_of_utc_calendar"])
        self.assertEqual(row["observed_count"],28)
        self.assertFalse(row["trade_authorized"])

    def test_monday_server_gmt3_from_sunday_utc_is_suspect_not_complete(self):
        sunday=datetime(2026,7,12,21,1,tzinfo=timezone.utc)
        row=check(trading_date=date(2026,7,13),present_symbols=FX_28,
                  expected_symbols=FX_28,as_of_utc=sunday,
                  server_utc_offset_hours=3)
        self.assertEqual(row["status"],
                         "LAB_D1_UTC_SUNDAY_SERVER_MONDAY_SUSPECT_UNAUTHENTICATED")
        self.assertFalse(row["rank_28fx_coverage_complete"])
        self.assertTrue(row["server_day_ahead_of_utc_calendar"])

    def test_wrong_offset_cannot_allow_monday_calendar_ahead(self):
        sunday=datetime(2026,7,12,21,1,tzinfo=timezone.utc)
        row=check(trading_date=date(2026,7,13),present_symbols=FX_28,
                  expected_symbols=FX_28,as_of_utc=sunday,
                  server_utc_offset_hours=2)
        self.assertEqual(row["reason"],"D1_DATE_AFTER_CLAIMED_SERVER_CALENDAR_NOW")
        self.assertEqual(row["status"],"LAB_D1_CALENDAR_BLOCKED")

    def test_server_offset_must_be_explicitly_two_or_three_integer(self):
        for offset in (0,1,4,2.0,True,"2",timedelta(hours=2)):
            with self.subTest(offset=offset):
                row=check(trading_date=date(2025,9,30),
                          present_symbols=FX_28,expected_symbols=FX_28,
                          as_of_utc=FIXED_AS_OF_UTC,
                          server_utc_offset_hours=offset)
                self.assertEqual(row["reason"],"INVALID_OR_UNSUPPORTED_SERVER_UTC_OFFSET")

    def test_saturday_28_synthetic_claims_are_suspect_not_blocked(self):
        row=check(trading_date=date(2026,11,14),
                  present_symbols=FX_28,expected_symbols=FX_28,
                  as_of_utc=FIXED_AS_OF_UTC,
                  server_utc_offset_hours=2)
        self.assertEqual(row["status"],"LAB_D1_WEEKEND_CALENDAR_SUSPECT_UNAUTHENTICATED")
        self.assertNotEqual(row["status"],"LAB_D1_CALENDAR_BLOCKED")
        self.assertTrue(row["weekend_server_calendar_suspect"])
        self.assertFalse(row["rank_28fx_coverage_complete"])
        self.assertFalse(row["weekend_d1_bars_independently_verified"])

    def test_sunday_utc_week_open_ambiguous_not_complete_or_rejected(self):
        for offset in (2,3):
            with self.subTest(offset=offset):
                row=check(trading_date=date(2026,11,15),
                          present_symbols=FX_28,expected_symbols=FX_28,
                          as_of_utc=datetime(2026,11,15,23,0,tzinfo=timezone.utc),
                          server_utc_offset_hours=offset)
                self.assertEqual(row["status"],
                                 "LAB_D1_WEEKEND_CALENDAR_SUSPECT_UNAUTHENTICATED")
                self.assertFalse(row["rank_28fx_coverage_complete"])
                self.assertFalse(row["historical_broker_source_independently_verified"])

    def test_weekend_partial_or_zero_does_not_hide_documentary_gaps(self):
        for n in (0,13,27,28):
            with self.subTest(n=n):
                row=check(trading_date=date(2026,11,14),
                          present_symbols=FX_28[:n],expected_symbols=FX_28,
                          as_of_utc=FIXED_AS_OF_UTC)
                self.assertEqual(row["status"],
                                 "LAB_D1_WEEKEND_CALENDAR_SUSPECT_UNAUTHENTICATED")
                self.assertEqual(row["observed_count"],n)
                self.assertEqual(row["missing_count"],28-n)
                self.assertFalse(row["rank_28fx_coverage_complete"])

    def test_naive_future_boolean_cannot_unlock_calendar(self):
        row=check(trading_date=date(2025,9,30),
                  present_symbols=FX_28,expected_symbols=FX_28,
                  as_of_utc=FIXED_AS_OF_UTC,server_utc_offset_hours=True)
        self.assertEqual(row["status"],"LAB_D1_CALENDAR_BLOCKED")

    def test_no_real_data_or_trades_even_with_28_weekday_claims(self):
        row=self.call(FX_28)
        self.assertTrue(row["rank_28fx_coverage_complete"])
        self.assertFalse(row["trading_calendar_independently_verified"])
        self.assertFalse(row["historical_broker_source_independently_verified"])
        self.assertFalse(row["single_pair_backtest_authorized"])
        self.assertIsNone(row["direction_probability"])
        self.assertFalse(row["trade_authorized"])

    # Three independently audited defects only: open current D1, precise
    # UTC/server labels, and descriptive blocked reason for future day.
    def test_current_utc_day_0010_1500_2359_never_complete(self):
        for hh,mm in ((0,10),(15,0),(23,59)):
            with self.subTest(clock=(hh,mm)):
                now=datetime(2026,11,16,hh,mm,tzinfo=timezone.utc)
                row=check(trading_date=now.date(),present_symbols=FX_28,
                          expected_symbols=FX_28,as_of_utc=now)
                self.assertEqual(row["status"],
                                 "LAB_D1_CURRENT_DAY_CANDLE_NOT_CLOSED")
                self.assertEqual(row["observed_count"],28)
                self.assertFalse(row["rank_28fx_coverage_complete"])
                self.assertEqual(row["operational_bias"],"AGUARDAR")
                self.assertFalse(row["trade_authorized"])

    def test_yesterday_weekday_with_28_stays_documentary_complete(self):
        now=datetime(2026,11,17,15,0,tzinfo=timezone.utc)
        row=check(trading_date=date(2026,11,16),
                  present_symbols=FX_28,expected_symbols=FX_28,
                  as_of_utc=now)
        self.assertEqual(row["status"],
                         "LAB_ALL_28_D1_BARS_PRESENT_DOCUMENTARY_UNATTESTED")
        self.assertTrue(row["rank_28fx_coverage_complete"])
        self.assertFalse(row["historical_broker_source_independently_verified"])
        self.assertFalse(row["trade_authorized"])

    def test_previous_friday_28_still_documentary_complete(self):
        now=datetime(2026,11,16,18,0,tzinfo=timezone.utc)
        row=check(trading_date=date(2026,11,13),
                  present_symbols=FX_28,expected_symbols=FX_28,
                  as_of_utc=now)
        self.assertEqual(row["status"],
                         "LAB_ALL_28_D1_BARS_PRESENT_DOCUMENTARY_UNATTESTED")
        self.assertTrue(row["rank_28fx_coverage_complete"])
        self.assertFalse(row["trading_calendar_independently_verified"])

    def test_current_server_day_gmt2_and_gmt3_cannot_be_complete(self):
        now=datetime(2026,11,16,15,0,tzinfo=timezone.utc)
        for offset in (2,3):
            with self.subTest(offset=offset):
                row=check(trading_date=date(2026,11,16),
                          present_symbols=FX_28,expected_symbols=FX_28,
                          as_of_utc=now,server_utc_offset_hours=offset)
                self.assertEqual(row["status"],
                                 "LAB_D1_CURRENT_DAY_CANDLE_NOT_CLOSED")
                self.assertFalse(row["rank_28fx_coverage_complete"])

    def test_today_weekends_stay_weekend_suspect_over_current_day(self):
        for now in (datetime(2026,11,14,15,tzinfo=timezone.utc),
                    datetime(2026,11,15,15,tzinfo=timezone.utc)):
            for offset in (None,2,3):
                with self.subTest(now=now,offset=offset):
                    row=check(trading_date=now.date(),present_symbols=FX_28,
                              expected_symbols=FX_28,as_of_utc=now,
                              server_utc_offset_hours=offset)
                    self.assertEqual(
                        row["status"],
                        "LAB_D1_WEEKEND_CALENDAR_SUSPECT_UNAUTHENTICATED")
                    self.assertFalse(row["rank_28fx_coverage_complete"])
                    self.assertTrue(row["weekend_server_calendar_suspect"])

    def test_sunday_utc_monday_server_has_specific_label_priority(self):
        sunday=datetime(2026,11,15,22,1,tzinfo=timezone.utc)
        row=check(trading_date=date(2026,11,16),
                  present_symbols=FX_28,expected_symbols=FX_28,
                  as_of_utc=sunday,server_utc_offset_hours=2)
        self.assertEqual(
            row["status"],
            "LAB_D1_UTC_SUNDAY_SERVER_MONDAY_SUSPECT_UNAUTHENTICATED")
        self.assertTrue(row["server_day_ahead_of_utc_calendar"])
        self.assertFalse(row["rank_28fx_coverage_complete"])
        self.assertFalse(row["trade_authorized"])

    def test_tuesday_server_from_monday_utc_gets_generic_label(self):
        monday=datetime(2026,11,16,23,30,tzinfo=timezone.utc)
        row=check(trading_date=date(2026,11,17),present_symbols=FX_28,
                  expected_symbols=FX_28,as_of_utc=monday,
                  server_utc_offset_hours=3)
        self.assertEqual(
            row["status"],
            "LAB_D1_SERVER_DAY_AHEAD_OF_UTC_SUSPECT_UNAUTHENTICATED")
        self.assertEqual(
            row["reason"],"SERVER_DAY_AHEAD_OF_UTC_NOT_CLOSED_D1")
        self.assertTrue(row["server_day_ahead_of_utc_calendar"])
        self.assertFalse(row["rank_28fx_coverage_complete"])

    def test_future_year_2999_no_offset_block_reason_mentions_future(self):
        row=check(trading_date=date(2999,1,1),present_symbols=FX_28,
                  expected_symbols=FX_28,
                  as_of_utc=datetime(2026,11,16,18,tzinfo=timezone.utc))
        self.assertEqual(row["status"],"LAB_D1_CALENDAR_BLOCKED")
        self.assertEqual(
            row["reason"],
            "FUTURE_D1_DATE_REQUIRES_SERVER_OFFSET_TO_CHECK_CALENDAR")
        self.assertFalse(row["rank_28fx_coverage_complete"])
        self.assertFalse(row["trade_authorized"])

    def test_current_partial_cohort_still_not_called_complete(self):
        now=datetime(2026,11,16,15,tzinfo=timezone.utc)
        for count in (0,13,27,28):
            with self.subTest(count=count):
                row=check(trading_date=now.date(),
                          present_symbols=FX_28[:count],
                          expected_symbols=FX_28,as_of_utc=now)
                self.assertEqual(row["status"],
                                 "LAB_D1_CURRENT_DAY_CANDLE_NOT_CLOSED")
                self.assertEqual(row["missing_count"],28-count)
                self.assertFalse(row["rank_28fx_coverage_complete"])


if __name__ == "__main__":
    unittest.main()
