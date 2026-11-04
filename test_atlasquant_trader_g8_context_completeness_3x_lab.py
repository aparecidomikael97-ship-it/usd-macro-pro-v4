"""Eight-currency causal coverage must expose gaps, never claim live bias."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import unittest

from atlasquant_fx_universe import CURRENCIES, OFFICIAL_PAIRS
from atlasquant_trader_g8_context_completeness_3x_lab import (
    DIMENSIONS, SCHEMA, audit_three_daily_g8_context_lab,
)

AT = datetime(2026, 11, 4, 21, tzinfo=timezone.utc)
SLOTS = (
    ("PRE_MARKET", "2026-11-04T09:40:00Z"),
    ("MIDDAY", "2026-11-04T13:50:00Z"),
    ("CLOSE", "2026-11-04T20:20:00Z"),
)
URLS = {
    "USD": "https://www.bls.gov/schedule/news_release/cpi.htm",
    "EUR": "https://www.ecb.europa.eu/home/html/rss.en.html",
    "GBP": "https://www.bankofengland.co.uk/monetary-policy/upcoming-mpc-dates",
    "JPY": "https://www.boj.or.jp/en/mopo/mpmsche_minu/",
    "CHF": "https://www.snb.ch/en/the-snb/mandates-goals/monetary-policy/decisions",
    "AUD": "https://www.abs.gov.au/statistics/labour/employment-and-unemployment/labour-force-australia",
    "CAD": "https://www150.statcan.gc.ca/n1/en/type/daily",
    "NZD": "https://www.rbnz.govt.nz/monetary-policy",
}


def capture(which=0, *, all_documented=False):
    slot, stamp = SLOTS[which]
    dims = {}
    for c in CURRENCIES:
        dims[c] = {}
        for key in DIMENSIONS:
            dims[c][key] = (
                {"status": "DOCUMENTARY_ONLY", "source_url": URLS[c],
                 "source_checked_at_utc": stamp}
                if all_documented else
                {"status": "MISSING", "source_url": None,
                 "source_checked_at_utc": None}
            )
    return {
        "slot": slot, "captured_at_utc": stamp,
        "currency_dimensions": dims,
        "original_source_receipts_attested": False,
        "real_data_verified": False, "live_price_verified": False,
        "trade_authorized": False,
    }


def audit(captures, *, at=AT):
    return audit_three_daily_g8_context_lab(captures, at=at)


class CausalCompletenessThreeDailyLabTests(unittest.TestCase):
    def test_empty_day_reports_8_currencies_28_pairs_and_9_gaps(self):
        r = audit([])
        self.assertEqual((r["schema"], r["state"]),
                         (SCHEMA, "LAB_COVERAGE_EXPLANATION_ONLY"))
        self.assertEqual(r["currency_count"], 8)
        self.assertEqual(r["pair_count"], 28)
        self.assertEqual({row["pair"] for row in r["pair_contexts"]},
                         set(OFFICIAL_PAIRS))
        self.assertEqual(set(r["required_dimensions"]), set(DIMENSIONS))
        self.assertEqual(r["claimed_capture_count"], 0)
        for c in CURRENCIES:
            self.assertEqual(r["currency_contexts"][c]["missing_dimensions"],
                             list(DIMENSIONS))
            self.assertEqual(r["currency_contexts"][c]["currency_strength"],
                             "AGUARDAR")
        self.assertFalse(r["three_daily_updates_verified"])
        self.assertFalse(r["real_bias_verified"])
        self.assertFalse(r["trade_authorized"])

    def test_claimed_three_documentary_captures_are_never_proof_of_run(self):
        captures = [capture(i, all_documented=True) for i in range(3)]
        original = deepcopy(captures)
        r = audit(captures)
        self.assertEqual(captures, original)
        self.assertTrue(r["claimed_three_captures_seen"])
        self.assertEqual(r["claimed_capture_slots"],
                         ["PRE_MARKET", "MIDDAY", "CLOSE"])
        self.assertFalse(r["three_daily_updates_verified"])
        self.assertFalse(r["sources_attested"])
        self.assertEqual(r["currency_contexts"]["USD"]["missing_dimensions"], [])
        for row in r["pair_contexts"]:
            self.assertEqual([row[h] for h in ("D1", "W1", "MN1")],
                             ["AGUARDAR"] * 3)
            self.assertFalse(row["reason_for_strength_difference_confirmed"])
        self.assertIsNone(r["probability_calibrated"])
        self.assertEqual(r["new_external_requests"], 0)

    def test_latest_available_capture_exposes_evidence_gap_by_pair(self):
        c = capture(1)
        c["currency_dimensions"]["USD"]["INFLATION"] = {
            "status": "DOCUMENTARY_ONLY", "source_url": URLS["USD"],
            "source_checked_at_utc": "2026-11-04T13:45:00Z",
        }
        r = audit([c])
        self.assertNotIn("INFLATION",
                         r["currency_contexts"]["USD"]["missing_dimensions"])
        usd_jpy = next(x for x in r["pair_contexts"] if x["pair"] == "USD/JPY")
        self.assertNotIn("INFLATION", usd_jpy["missing_by_currency"]["USD"])
        self.assertIn("INFLATION", usd_jpy["missing_by_currency"]["JPY"])
        self.assertEqual(usd_jpy["D1"], "AGUARDAR")

    def test_source_checked_older_than_48h_is_flagged_not_fabricated(self):
        c = capture(1)
        c["currency_dimensions"]["GBP"]["POLICY_RATE_EXPECTATIONS"] = {
            "status": "DOCUMENTARY_ONLY", "source_url": URLS["GBP"],
            "source_checked_at_utc": "2026-11-02T10:00:00Z",
        }
        r = audit([c])
        self.assertEqual(r["currency_contexts"]["GBP"]
                         ["older_than_48h_source_checks"], ["POLICY_RATE_EXPECTATIONS"])
        self.assertEqual(r["currency_contexts"]["GBP"]["currency_strength"],
                         "AGUARDAR")

    def test_duplicate_or_inverted_slot_timestamps_refused(self):
        a = capture(0)
        self.assertEqual(audit([a, deepcopy(a)])["reason"],
                         "DUPLICATE_DAILY_SLOT")
        b = capture(2)
        b["captured_at_utc"] = "2026-11-04T08:00:00Z"
        self.assertEqual(audit([a, b])["reason"],
                         "CAPTURES_NOT_CHRONOLOGICAL")

    def test_extra_or_missing_dimensions_and_currencies_refused(self):
        for action in ("missing_currency", "extra_dimension", "missing_dimension"):
            with self.subTest(action=action):
                c = capture()
                if action == "missing_currency":
                    c["currency_dimensions"].pop("USD")
                elif action == "extra_dimension":
                    c["currency_dimensions"]["USD"]["FX_MAGIC_SCORE"] = {}
                else:
                    c["currency_dimensions"]["USD"].pop("OFFICIAL_NEWS")
                self.assertEqual(audit([c])["state"], "LAB_BLOCKED")

    def test_forged_live_data_and_unknown_evidence_status_refused(self):
        for field in ("original_source_receipts_attested", "real_data_verified",
                      "live_price_verified", "trade_authorized"):
            with self.subTest(field=field):
                c = capture()
                c[field] = True
                self.assertEqual(audit([c])["state"], "LAB_BLOCKED")
        c = capture()
        c["currency_dimensions"]["USD"]["INFLATION"]["status"] = "LIVE_CONFIRMED"
        self.assertEqual(audit([c])["state"], "LAB_BLOCKED")

    def test_invalid_issuer_url_or_future_check_refused(self):
        for field, value in (("source_url", "https://www.bls.gov.evil.test/cpi"),
                             ("source_checked_at_utc", "2026-11-04T23:59:00Z")):
            with self.subTest(field=field):
                c = capture(1)
                c["currency_dimensions"]["USD"]["INFLATION"] = {
                    "status": "DOCUMENTARY_ONLY", "source_url": URLS["USD"],
                    "source_checked_at_utc": "2026-11-04T13:45:00Z",
                }
                c["currency_dimensions"]["USD"]["INFLATION"][field] = value
                self.assertEqual(audit([c])["state"], "LAB_BLOCKED")

    def test_future_snapshot_other_day_naive_clock_and_over_3_refused(self):
        self.assertEqual(audit([capture(0)] * 4)["state"], "LAB_BLOCKED")
        c = capture(0)
        c["captured_at_utc"] = (AT + timedelta(hours=1)).isoformat()
        self.assertEqual(audit([c])["state"], "LAB_BLOCKED")
        c = capture(0)
        c["captured_at_utc"] = "2026-11-03T09:40:00Z"
        self.assertEqual(audit([c])["state"], "LAB_BLOCKED")
        with self.assertRaises(ValueError):
            audit([], at=AT.replace(tzinfo=None))

    def test_slot_monitor_keeps_local_planned_windows(self):
        r = audit([capture(i) for i in range(3)])
        self.assertEqual([x["slot_state"] for x in r["planned_slots"]],
                         ["DOCUMENTARY_CAPTURE_CLAIMED"] * 3)
        self.assertEqual(r["planned_slots"][0]["scheduled_at_brt"],
                         "2026-11-04T06:35:00-03:00")


if __name__ == "__main__":
    unittest.main()
