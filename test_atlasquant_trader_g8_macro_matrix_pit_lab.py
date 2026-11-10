"""Synthetic 8-currency/28-pair matrix tests; no economic fact is asserted."""
from datetime import datetime, timezone
import unittest

from atlasquant_fx_universe import CURRENCIES, OFFICIAL_PAIRS
from atlasquant_trader_g8_macro_matrix_pit_lab import (
    inspect_g8_macro_matrix_pit_lab as inspect,
)

DECISION = datetime(2026, 11, 5, 12, tzinfo=timezone.utc)
EVALUATED = datetime(2026, 11, 8, tzinfo=timezone.utc)


def receipt(currency, indicator, *, published="2026-10-29T12:00:00Z",
            captured="2026-10-29T12:05:00Z", period="2026-09", value="2.0"):
    return {"currency": currency, "indicator": indicator,
            "observation_period": period, "value": value,
            "published_at_utc": published, "captured_at_utc": captured,
            "source_type": ("CENTRAL_BANK" if indicator == "POLICY_RATE"
                            else "OFFICIAL_STATISTICS_OFFICE"),
            "source_sha256": "a" * 64}


def fixtures():
    return {currency: [receipt(currency, "CPI_YOY"),
                       receipt(currency, "POLICY_RATE")]
            for currency in CURRENCIES}


def run(rows=None, *, horizon="D1", decision=DECISION, evaluated=EVALUATED):
    return inspect(fixtures() if rows is None else rows, horizon=horizon,
                   decision_at_utc=decision, evaluated_at_utc=evaluated)


class G8MatrixTests(unittest.TestCase):
    def assert_no_go(self, result):
        self.assertFalse(result["source_independently_authenticated"])
        self.assertFalse(result["historical_point_in_time_verified"])
        self.assertFalse(result["broker_price_source_verified"])
        self.assertFalse(result["backtest_approved"])
        self.assertFalse(result["trade_authorized"])
        self.assertFalse(result["worker_enabled"])
        self.assertFalse(result["scheduler_enabled"])
        self.assertFalse(result["publishable"])
        self.assertEqual(result["operational_bias"], "AGUARDAR")
        self.assertIsNone(result["directional_probability"])
        self.assertIsNone(result["score_0_to_10"])
        self.assertIsNone(result["validated_accuracy"])
        self.assertEqual(result["validated_prediction_count"], 0)
        self.assertEqual((result["http_requests"], result["new_cost_brl"]), (0, 0))

    def test_eight_currency_claims_reused_across_all_28_pairs(self):
        result = run()
        self.assertEqual(result["state"], "LAB_G8_MACRO_MATRIX_CLAIMS_ONLY")
        self.assertEqual((result["currency_count"], result["pair_count"]), (8, 28))
        self.assertEqual(result["claim_only_complete_pairs"], 28)
        self.assertEqual((result["incomplete_pairs"], result["rejected_pairs"]), (0, 0))
        self.assertEqual(set(result["pairs"]), set(OFFICIAL_PAIRS))
        for pair, info in result["pairs"].items():
            self.assertEqual(info["metadata_claim_state"],
                             "LAB_PAIR_MACRO_METADATA_COMPLETE_UNATTESTED", pair)
            self.assertFalse(info["backtest_approved"])
            self.assertEqual(info["operational_bias"], "AGUARDAR")
            self.assertNotIn("value", info)
            self.assertNotIn("source_sha256", info)
        self.assert_no_go(result)

    def test_single_currency_missing_cpi_impacts_seven_pairs(self):
        rows = fixtures()
        rows["NZD"] = [r for r in rows["NZD"] if r["indicator"] != "CPI_YOY"]
        result = run(rows)
        self.assertEqual((result["claim_only_complete_pairs"], result["incomplete_pairs"]),
                         (21, 7))
        self.assertEqual(result["rejected_pairs"], 0)
        for pair, info in result["pairs"].items():
            self.assertEqual("NZD:CPI_YOY:MISSING" in info["missing_or_stale"],
                             "NZD" in pair)
        self.assert_no_go(result)

    def test_no_receipts_is_not_evidence_that_nothing_was_published(self):
        result = run({currency: [] for currency in CURRENCIES})
        self.assertEqual((result["claim_only_complete_pairs"],
                          result["incomplete_pairs"], result["rejected_pairs"]),
                         (0, 28, 0))
        self.assert_no_go(result)

    def test_future_publication_blocks_all_crosses_of_that_currency(self):
        rows = fixtures()
        rows["GBP"][0]["published_at_utc"] = "2026-11-05T12:00:01Z"
        rows["GBP"][0]["captured_at_utc"] = "2026-11-05T12:00:02Z"
        result = run(rows)
        self.assertEqual(result["state"], "LAB_G8_MACRO_MATRIX_HAS_REJECTIONS")
        self.assertEqual((result["claim_only_complete_pairs"], result["rejected_pairs"]),
                         (21, 7))
        for pair, info in result["pairs"].items():
            if "GBP" in pair:
                self.assertEqual(info["rejection_reason"],
                                 "RELEASE_LOOKAHEAD_OR_CHRONOLOGY_INVALID")
        self.assert_no_go(result)

    def test_late_capture_cannot_be_used_at_earlier_decision(self):
        rows = fixtures()
        rows["EUR"][0]["captured_at_utc"] = "2026-11-05T12:00:01Z"
        result = run(rows)
        self.assertEqual(result["rejected_pairs"], 7)
        self.assert_no_go(result)

    def test_same_release_after_daily_cutoff_may_be_claimed_by_later_weekly_cutoff(self):
        rows = fixtures()
        rows["USD"].append(receipt("USD", "CPI_YOY",
                                   published="2026-11-06T10:00:00Z",
                                   captured="2026-11-06T10:05:00Z",
                                   period="2026-10"))
        daily = run(rows, decision=DECISION, horizon="D1")
        weekly = run(rows, horizon="W1",
                     decision=datetime(2026, 11, 7, 12, tzinfo=timezone.utc))
        self.assertEqual(daily["rejected_pairs"], 7)
        self.assertEqual(weekly["rejected_pairs"], 0)
        self.assertEqual(weekly["claim_only_complete_pairs"], 28)
        self.assert_no_go(daily)
        self.assert_no_go(weekly)

    def test_duplicate_vintage_is_never_resolved_silently(self):
        rows = fixtures()
        rows["USD"].append(dict(rows["USD"][0], value="3.0"))
        result = run(rows)
        self.assertEqual(result["state"], "LAB_BLOCKED")
        self.assertEqual(result["reason"], "AMBIGUOUS_DUPLICATE_VINTAGE")
        self.assert_no_go(result)

    def test_wrong_currency_ownership_blocks_whole_matrix(self):
        rows = fixtures()
        rows["EUR"][0]["currency"] = "USD"
        self.assertEqual(run(rows)["reason"], "CURRENCY_RECEIPT_SCHEMA_OR_OWNER_INVALID")

    def test_malformed_indicator_does_not_raise_unhashable_exception(self):
        rows = fixtures()
        rows["EUR"][0]["indicator"] = ["CPI_YOY"]
        self.assertEqual(run(rows)["state"], "LAB_BLOCKED")

    def test_naive_or_future_clocks_and_wrong_horizon_fail_closed(self):
        for kwargs in (
            {"decision": datetime(2026, 11, 5, 12)},
            {"evaluated": datetime(2026, 11, 4, tzinfo=timezone.utc)},
            {"horizon": "MN1"},
        ):
            with self.subTest(kwargs=kwargs):
                self.assertEqual(run(**kwargs)["state"], "LAB_BLOCKED")

    def test_unknown_currency_or_oversized_collection_rejected(self):
        rows = fixtures()
        rows["XYZ"] = []
        self.assertEqual(run(rows)["state"], "LAB_BLOCKED")
        rows = fixtures()
        rows["GBP"] *= 7
        self.assertEqual(run(rows)["reason"], "INVALID_CURRENCY_RECEIPT_COLLECTION")

    def test_invalid_numeric_claim_never_becomes_macro_coverage(self):
        rows = fixtures()
        rows["EUR"][0]["value"] = "NaN"
        result = run(rows)
        self.assertEqual(result["rejected_pairs"], 7)
        self.assertEqual(result["claim_only_complete_pairs"], 21)
        self.assert_no_go(result)

    def test_one_currency_wrong_original_issuer_category_rejects_seven_pairs(self):
        for currency in CURRENCIES:
            for indicator, wrong_type in (("CPI_YOY", "CENTRAL_BANK"),
                                          ("POLICY_RATE", "OFFICIAL_STATISTICS_OFFICE")):
                with self.subTest(currency=currency, indicator=indicator):
                    rows = fixtures()
                    row = next(x for x in rows[currency] if x["indicator"] == indicator)
                    row["source_type"] = wrong_type
                    result = run(rows)
                    self.assertEqual(result["state"], "LAB_G8_MACRO_MATRIX_HAS_REJECTIONS")
                    self.assertEqual((result["rejected_pairs"],
                                      result["claim_only_complete_pairs"]), (7, 21))
                    for pair, info in result["pairs"].items():
                        if currency in pair:
                            self.assertEqual(info["rejection_reason"],
                                             "INDICATOR_ORIGINAL_ISSUER_CATEGORY_MISMATCH")
                    self.assert_no_go(result)


if __name__ == "__main__":
    unittest.main(verbosity=2)
