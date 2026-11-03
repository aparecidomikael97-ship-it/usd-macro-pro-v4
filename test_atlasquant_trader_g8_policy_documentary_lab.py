"""Canonical official G8 policy levels: no hindsight, no FX ranking."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import unittest

from atlasquant_fx_universe import CURRENCIES, OFFICIAL_PAIRS
from atlasquant_trader_g8_policy_documentary_lab import (
    DECISIONS, SCHEMA, build_g8_policy_documentary_lab,
)

AT = datetime(2026, 11, 3, 15, 0, tzinfo=timezone.utc)


def report(at=AT, observations=None):
    return build_g8_policy_documentary_lab(at=at, observations=observations)


def rate(currency, at=AT):
    return report(at=at)["rates"][currency]


def pair(name):
    return next(row for row in report()["pair_rows"] if row["pair"] == name)


class G8PolicyDocumentaryTests(unittest.TestCase):
    def test_full_g8_currency_policy_documents(self):
        r = report()
        self.assertEqual(r["schema"], SCHEMA)
        self.assertEqual(r["state"], "LAB_G8_POLICY_FACTS_NO_DIRECTION")
        self.assertEqual(r["currency_count"], 8)
        self.assertEqual(set(r["rates"]), set(CURRENCIES))
        self.assertEqual(r["visible_document_count"], 8)

    def test_nine_vintages_including_two_australian(self):
        self.assertEqual(len(DECISIONS), 9)
        self.assertEqual(sum(x["currency"] == "AUD" for x in DECISIONS), 2)

    def test_fed_is_range_not_point_or_effective_rate(self):
        row = rate("USD")
        self.assertEqual(row["instrument_id"], "FOMC_TARGET_FED_FUNDS_RANGE")
        self.assertEqual((row["low_pct"], row["high_pct"]), ("3.75", "4.00"))
        self.assertEqual(row["measure_type"], "TARGET_RANGE")

    def test_ecb_is_deposit_facility_not_sovereign_yield(self):
        row = rate("EUR")
        self.assertEqual(row["instrument_id"], "ECB_DEPOSIT_FACILITY_RATE")
        self.assertEqual(row["low_pct"], "2.50")

    def test_boe_bank_rate_375(self):
        self.assertEqual(rate("GBP")["low_pct"], "3.75")

    def test_boj_guide_is_approximate_not_precise_trade(self):
        row = rate("JPY")
        self.assertEqual(row["low_pct"], "1.25")
        self.assertEqual(row["measure_type"], "APPROXIMATE_GUIDELINE")

    def test_snb_zero(self):
        self.assertEqual(rate("CHF")["low_pct"], "0.00")

    def test_boc_250(self):
        self.assertEqual(rate("CAD")["low_pct"], "2.50")
        self.assertEqual(rate("CAD")["instrument_id"], "BOC_OVERNIGHT_RATE_TARGET")

    def test_rba_nov3_new_485_visible_after_announcement(self):
        row = rate("AUD")
        self.assertEqual(row["low_pct"], "4.85")
        self.assertEqual(row["decided_on"], "2026-11-03")
        self.assertEqual(row["effective_on_local"], "2026-11-04")

    def test_rbnz_275(self):
        self.assertEqual(rate("NZD")["low_pct"], "2.75")

    def test_exact_28_canonical_pairs(self):
        r = report()
        self.assertEqual(r["pair_count"], 28)
        self.assertEqual({x["pair"] for x in r["pair_rows"]}, set(OFFICIAL_PAIRS))

    def test_pre_announcement_aud_old_level(self):
        earlier = datetime(2026, 11, 3, 3, 29, tzinfo=timezone.utc)
        self.assertEqual(rate("AUD", earlier)["low_pct"], "4.60")

    def test_at_announced_minute_aud_still_hidden_without_receipt(self):
        minute = datetime(2026, 11, 3, 3, 30, tzinfo=timezone.utc)
        self.assertEqual(rate("AUD", minute)["low_pct"], "4.60")

    def test_aud_new_one_minute_conservative_gate(self):
        moment = datetime(2026, 11, 3, 3, 31, tzinfo=timezone.utc)
        row = rate("AUD", moment)
        self.assertEqual(row["low_pct"], "4.85")
        self.assertEqual(row["availability_state"],
                         "NEW_RATE_ANNOUNCED_EFFECTIVE_NEXT_LOCAL_DATE")

    def test_announcement_before_local_effective_day(self):
        moment = datetime(2026, 11, 3, 12, 59, tzinfo=timezone.utc)
        self.assertEqual(rate("AUD", moment)["availability_state"],
                         "NEW_RATE_ANNOUNCED_EFFECTIVE_NEXT_LOCAL_DATE")

    def test_local_effective_date_reached_not_equal_source_receipt(self):
        moment = datetime(2026, 11, 3, 13, 0, tzinfo=timezone.utc)
        self.assertEqual(rate("AUD", moment)["availability_state"],
                         "NEW_RATE_LOCAL_EFFECTIVE_DATE_REACHED")
        self.assertFalse(rate("AUD", moment)["historical_source_original_bytes_attested"])

    def test_fixed_aedt_offset_does_not_require_tzdata(self):
        sydney = timezone(timedelta(hours=11))
        moment = datetime(2026, 11, 4, 0, 1, tzinfo=sydney)
        self.assertEqual(rate("AUD", moment)["availability_state"],
                         "NEW_RATE_LOCAL_EFFECTIVE_DATE_REACHED")

    def test_nov5_boe_event_requires_refresh(self):
        moment = datetime(2026, 11, 5, 0, tzinfo=timezone.utc)
        self.assertEqual(rate("GBP", moment)["availability_state"],
                         "KNOWN_NEW_DECISION_DATE_REQUIRES_REFRESH")

    def test_before_nov5_boe_old_rate_is_historical_not_projection(self):
        moment = datetime(2026, 11, 4, 23, 59, tzinfo=timezone.utc)
        self.assertEqual(rate("GBP", moment)["availability_state"],
                         "HISTORICAL_POLICY_DOCUMENT_AVAILABLE")

    def test_all_28_pairs_unscored_and_untraded(self):
        for row in report()["pair_rows"]:
            with self.subTest(pair=row["pair"]):
                self.assertIsNone(row["nominal_policy_rate_gap_pp"])
                self.assertIsNone(row["future_policy_expectation_gap_pp"])
                self.assertEqual(row["bias"], "AGUARDAR")
                self.assertIsNone(row["probability_calibrated"])
                self.assertFalse(row["trade_authorized"])

    def test_gbpusd_has_two_policy_references_not_direction(self):
        p = pair("GBP/USD")
        self.assertEqual((p["base_policy"], p["quote_policy"]), ("GBP", "USD"))
        self.assertIsNone(p["nominal_policy_rate_gap_pp"])

    def test_absence_of_verified_cross_bank_comparability(self):
        r = report()
        self.assertFalse(r["cross_bank_policy_rate_comparability_proven"])
        self.assertFalse(r["market_priced_expectations_verified"])

    def test_asof_not_before_research_day(self):
        with self.assertRaises(ValueError):
            report(at=datetime(2026, 11, 2, 23, 59, tzinfo=timezone.utc))

    def test_naive_clock_rejected(self):
        with self.assertRaises(ValueError):
            report(at=datetime(2026, 11, 3, 10))

    def test_non_datetime_rejected(self):
        with self.assertRaises(ValueError):
            report(at="2026-11-03T10:00:00Z")

    def test_clock_offset_normalized(self):
        offset = timezone(timedelta(hours=-4))
        r = report(at=datetime(2026, 11, 3, 11, tzinfo=offset))
        self.assertEqual(r["as_of_utc"], AT.isoformat())

    def test_exact_canonical_copy_accepted(self):
        self.assertEqual(report(observations=deepcopy(list(DECISIONS))), report())

    def test_tampered_aud_new_rate_rejected(self):
        changed = deepcopy(list(DECISIONS))
        changed[7]["low_pct"] = "4.90"
        changed[7]["high_pct"] = "4.90"
        with self.assertRaises(ValueError):
            report(observations=changed)

    def test_forged_early_aud_availability_rejected(self):
        changed = deepcopy(list(DECISIONS))
        changed[7]["conservative_available_from_utc"] = "2026-11-03T00:00:00Z"
        with self.assertRaises(ValueError):
            report(observations=changed)

    def test_wrong_url_host_rejected(self):
        changed = deepcopy(list(DECISIONS))
        changed[4]["source_url"] = "https://www.snb.ch.attack.invalid/pre"
        with self.assertRaises(ValueError):
            report(observations=changed)

    def test_added_strength_claim_rejected(self):
        changed = deepcopy(list(DECISIONS))
        changed[1]["strength_score"] = 100
        with self.assertRaises(ValueError):
            report(observations=changed)

    def test_fake_fed_point_range_rejected(self):
        changed = deepcopy(list(DECISIONS))
        changed[0]["high_pct"] = "3.75"
        with self.assertRaises(ValueError):
            report(observations=changed)

    def test_forged_boj_exact_rate_rejected(self):
        changed = deepcopy(list(DECISIONS))
        changed[3]["measure_type"] = "POINT_TARGET"
        with self.assertRaises(ValueError):
            report(observations=changed)

    def test_missing_or_duplicate_records_rejected(self):
        with self.assertRaises(ValueError):
            report(observations=list(DECISIONS)[:-1])
        changed = deepcopy(list(DECISIONS))
        changed[7] = deepcopy(changed[6])
        with self.assertRaises(ValueError):
            report(observations=changed)

    def test_untrusted_row_types_rejected(self):
        with self.assertRaises(ValueError):
            report(observations="documents")
        with self.assertRaises(ValueError):
            report(observations=[None] * 9)

    def test_publication_markers_never_become_attestation(self):
        for row in report()["rates"].values():
            self.assertFalse(row["historical_source_original_bytes_attested"])
            self.assertFalse(row["currency_strength_inferred"])

    def test_strict_hard_no_go(self):
        r = report()
        for flag in ("source_bytes_archived",
                     "source_receipts_independently_attested",
                     "full_forward_policy_curve_available",
                     "market_priced_expectations_verified",
                     "cross_bank_policy_rate_comparability_proven",
                     "fx_direction_proven", "accuracy_90_proven",
                     "can_feed_live_radar", "trade_authorized",
                     "worker_enabled", "scheduler_enabled"):
            with self.subTest(flag=flag):
                self.assertIs(r[flag], False)


if __name__ == "__main__":
    unittest.main()
