"""Synthetic contracts for AtlasQuant FX D1 date completeness. No prices used."""
from __future__ import annotations

from datetime import date
import unittest

from atlasquant_fx_d1_shared_calendar_gate_lab import (
    inspect_d1_date_coverage_lab as check,
)

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
                       present_symbols=present, expected_symbols=cohort)
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
                          expected_symbols=SYMBOLS)
                self.assertEqual(row["status"],"LAB_D1_CALENDAR_BLOCKED")
                self.assertFalse(row["trade_authorized"])
        row=check(trading_date=date(2025,9,30),present_symbols=SYMBOLS,
                  expected_symbols=list(SYMBOLS))
        self.assertEqual(row["status"],"LAB_D1_CALENDAR_BLOCKED")

    def test_no_implicit_profit_or_probability(self):
        row=self.call(SYMBOLS)
        self.assertNotIn("win_rate",row)
        self.assertNotIn("net_profit",row)
        self.assertFalse(row["out_of_sample_accuracy_verified"])


if __name__ == "__main__":
    unittest.main()
