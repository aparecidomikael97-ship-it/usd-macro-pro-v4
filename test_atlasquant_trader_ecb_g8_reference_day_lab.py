"""One-day ECB G8 reference arithmetic; source-informed, NOT original XML."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import unittest

from atlasquant_fx_universe import CURRENCIES, OFFICIAL_PAIRS
from atlasquant_trader_ecb_g8_reference_day_lab import (
    SCHEMA, EUR_QUOTES, build_ecb_g8_reference_day_lab as build,
)

NOW = datetime(2026, 11, 5, 5, tzinfo=timezone.utc)


def pair(report, symbol):
    return next(x for x in report["pairs"] if x["pair"] == symbol)


class EcbOneDayG8Tests(unittest.TestCase):
    def assert_no_go(self, r):
        for field in ("original_xml_bytes_obtained", "source_original_http_authenticated",
                      "release_instant_verified", "point_in_time_vintage_verified",
                      "broker_m15_execution_quotes_verified", "historical_accuracy_verified",
                      "trade_authorized", "can_feed_live_radar", "publishable",
                      "worker_enabled", "scheduler_enabled"):
            self.assertIs(r[field], False, field)
        self.assertIsNone(r["source_raw_sha256"])
        self.assertIsNone(r["fx_bias"])
        self.assertEqual(r["operational_bias"], "AGUARDAR")
        self.assertEqual((r["external_http_requests"], r["new_cost_brl"]), (0, 0))

    def test_official_public_page_seven_eur_quotes_and_one_base(self):
        self.assertEqual(EUR_QUOTES, {
            "EUR": "1", "USD": "1.1267", "GBP": "0.83460", "JPY": "178.30",
            "CHF": "0.9188", "AUD": "1.6061", "CAD": "1.5701", "NZD": "1.9988"})
        self.assertEqual(set(EUR_QUOTES), set(CURRENCIES))

    def test_28_canonical_crosses_are_derived_with_no_bias(self):
        r = build(as_of_utc=NOW)
        self.assertEqual(r["schema"], SCHEMA)
        self.assertEqual(r["state"], "LAB_ECB_G8_ONE_DAY_REFERENCE_CROSS_ARITHMETIC_ONLY")
        self.assertEqual((r["currency_count"], r["pair_count"]), (8,28))
        self.assertEqual({x["pair"] for x in r["pairs"]}, set(OFFICIAL_PAIRS))
        self.assertEqual(r["entry_mode"], "MANUALLY_TRANSCRIBED_PUBLIC_REFERENCE_VALUES")
        self.assert_no_go(r)

    def test_direct_eur_usd_reference(self):
        self.assertEqual(pair(build(as_of_utc=NOW),"EUR/USD")["derived_reference_rate"],
                         "1.12670000")

    def test_gbp_usd_is_implied_not_a_broker_quote(self):
        x = pair(build(as_of_utc=NOW), "GBP/USD")
        self.assertEqual(x["derived_reference_rate"], "1.34998802")
        self.assertFalse(x["observed_broker_quote"])

    def test_usd_jpy_is_implied(self):
        self.assertEqual(pair(build(as_of_utc=NOW),"USD/JPY")["derived_reference_rate"],
                         "158.24975592")

    def test_aud_nzd_is_implied(self):
        self.assertEqual(pair(build(as_of_utc=NOW),"AUD/NZD")["derived_reference_rate"],
                         "1.24450532")

    def test_all_28_use_correct_orientation_not_inverted(self):
        r = build(as_of_utc=NOW)
        for row in r["pairs"]:
            base, quote = row["pair"].split("/")
            expected = Decimal(EUR_QUOTES[quote]) / Decimal(EUR_QUOTES[base])
            self.assertLessEqual(abs(expected - Decimal(row["derived_reference_rate"])),
                                 Decimal("0.000000005"))
            self.assertEqual(row["unit"], f"{quote}_PER_1_{base}")
            self.assertIsNone(row["currency_strength_rank"])
            self.assertEqual((row["D1"],row["W1"]), ("AGUARDAR","AGUARDAR"))
            self.assertFalse(row["trade_authorized"])

    def test_missing_or_naive_clock_rejected(self):
        for v in (None, "2026-11-05", datetime(2026,11,5), {}, 1):
            self.assertEqual(build(as_of_utc=v)["state"],"LAB_BLOCKED")

    def test_research_clock_not_before_next_calendar_day(self):
        for v in (datetime(2026,11,4,23,59,tzinfo=timezone.utc),
                  datetime(2026,11,4,12,tzinfo=timezone.utc)):
            r = build(as_of_utc=v)
            self.assertEqual(r["state"],"LAB_BLOCKED")
            self.assert_no_go(r)

    def test_utc_offset_normalized(self):
        r = build(as_of_utc=datetime(2026,11,5,1,
                                    tzinfo=timezone(timedelta(hours=-4))))
        self.assertEqual(r["research_as_of_utc"], NOW.isoformat())
        self.assert_no_go(r)

    def test_next_day_boundary_not_ex_ante_proof(self):
        r = build(as_of_utc=datetime(2026,11,5,tzinfo=timezone.utc))
        self.assertEqual(r["state"],"LAB_ECB_G8_ONE_DAY_REFERENCE_CROSS_ARITHMETIC_ONLY")
        self.assert_no_go(r)

    def test_cross_reference_is_not_m15_or_trading(self):
        r = build(as_of_utc=NOW)
        self.assertFalse(r["broker_m15_execution_quotes_verified"])
        self.assertFalse(r["historical_accuracy_verified"])
        self.assert_no_go(r)

if __name__ == "__main__":
    unittest.main()
