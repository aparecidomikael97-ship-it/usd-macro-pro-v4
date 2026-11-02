"""Contract tests for two real quoted ECB documents; no live quote authorization."""
import copy
import json
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path

from atlasquant_fx_universe import CURRENCIES, OFFICIAL_PAIRS
from atlasquant_trader_ecb_documentary_reference_lab import (
    SCHEMA, compare_ecb_g8_documentary_reference_lab,
)

CASE_PATH = (Path(__file__).resolve().parent / "docs" / "continuidade" /
             "TRADER_ECB_TWO_DATES_DOCUMENTARY_CASE_LAB_20261102.json")
RESEARCH_TIME = datetime(2026, 11, 2, 20, tzinfo=timezone.utc)


def fixture():
    return json.loads(CASE_PATH.read_text(encoding="utf-8"))


def inspect(documents=None, evaluated=RESEARCH_TIME):
    pair = fixture()["documents"] if documents is None else documents
    return compare_ecb_g8_documentary_reference_lab(
        pair[0], pair[1], evaluated_at=evaluated,
    )


class EcbDocumentaryReferenceLabTests(unittest.TestCase):
    def test_two_genuine_published_documentary_snapshots_are_labeled_only_as_research(self):
        data = fixture()
        self.assertEqual(data["state"], "OFFICIAL_PUBLIC_REFERENCES_MANUALLY_READ_NOT_CUSTODIED")
        self.assertEqual(len(data["sources"]), 2)
        self.assertEqual(data["documents"][0]["eur_quotes"]["USD"], "1.1172")
        self.assertEqual(data["documents"][1]["eur_quotes"]["JPY"], "177.10")
        self.assertFalse(data["sources"][0]["raw_download_saved"])
        self.assertFalse(data["sources"][1]["raw_download_saved"])

    def test_seven_eur_rate_sources_yield_28_reference_comparisons_only(self):
        result = inspect()
        self.assertEqual(result["schema"], SCHEMA)
        self.assertEqual(result["state"], "LAB_ECB_DOCUMENTARY_REFERENCE_MATH_ONLY")
        self.assertEqual(result["official_eur_reference_legs"], 7)
        self.assertEqual(result["algebraically_derived_non_eur_crosses"], 21)
        self.assertEqual(set(result["pair_cross_reference_changes"]), set(OFFICIAL_PAIRS))
        self.assertEqual(set(result["currency_reference_ranking"]), set(CURRENCIES))
        self.assertEqual(result["independent_spot_quotes_verified"], 0)

    def test_reference_direction_is_arithmetic_not_trading_recommendation(self):
        r = inspect()
        self.assertGreater(r["pair_cross_reference_changes"]["USD/JPY"]["reference_change_pct"], 0)
        self.assertGreater(r["pair_cross_reference_changes"]["EUR/USD"]["reference_change_pct"], 0)
        self.assertLess(r["currency_reference_log_change_bp"]["JPY"],
                        r["currency_reference_log_change_bp"]["CHF"])
        self.assertEqual(r["currency_reference_ranking"][0], "CHF")
        self.assertEqual(r["currency_reference_ranking"][-1], "JPY")

    def test_reference_quotations_preserve_official_decimal_text(self):
        out = inspect()["original_eur_quotes"]
        self.assertEqual(out["2026-10-30"]["GBP"], "0.83380")
        self.assertEqual(out["2026-11-02"]["GBP"], "0.83580")
        self.assertEqual(out["2026-11-02"]["CHF"], "0.9193")

    def test_non_eur_cross_is_algebraic_and_not_an_independent_quote(self):
        r = inspect()["pair_cross_reference_changes"]
        pair = r["USD/JPY"]
        self.assertEqual(pair["origin"], "ALGEBRAIC_CROSS_FROM_SEVEN_EUR_QUOTES")
        self.assertFalse(pair["independent_spot_quote"])
        self.assertAlmostEqual(float(pair["current_implied_reference"]),
                               177.10 / 1.1216, places=7)
        self.assertEqual(r["EUR/USD"]["origin"], "EUR_ECB_REFERENCE_OR_INVERSE")

    def test_both_dates_must_be_available_after_evening_research_gate(self):
        early = datetime(2026, 11, 2, 17, 59, tzinfo=timezone.utc)
        result = inspect(evaluated=early)
        self.assertEqual(result["state"], "LAB_ECB_DOCUMENT_REVIEW_REFUSED")
        self.assertIn("evening", result["reason"])
        self.assertEqual(inspect(evaluated=datetime(2026, 11, 2, 18,
                          tzinfo=timezone.utc))["state"],
                         "LAB_ECB_DOCUMENTARY_REFERENCE_MATH_ONLY")

    def test_utc_evening_gate_requires_no_installed_time_zone_database(self):
        out = inspect(evaluated=datetime(2026, 11, 2, 18, tzinfo=timezone.utc))
        self.assertEqual(out["reference_publication_evening_gate_utc"],
                         "2026-11-02T18:00:00+00:00")
        self.assertFalse(out["publication_time_independently_verified"])

    def test_same_day_morning_forecast_cannot_use_afternoon_ecb_reference(self):
        morning = datetime(2026, 11, 2, 11, tzinfo=timezone.utc)
        r = inspect(evaluated=morning)
        self.assertEqual(r["state"], "LAB_ECB_DOCUMENT_REVIEW_REFUSED")
        self.assertEqual(r["pair_cross_reference_changes"], {})

    def test_source_document_identity_must_be_expected_ecb_official_page(self):
        for key, val in (("source_name", "fake-api"),
                         ("source_page", "https://example.com/latest"),
                         ("state", "REAL_VERIFIED_SPOT")):
            docs = copy.deepcopy(fixture()["documents"])
            docs[0][key] = val
            self.assertEqual(inspect(docs)["state"], "LAB_ECB_DOCUMENT_REVIEW_REFUSED")

    def test_missing_or_extra_currency_rejects_all_reference_comparisons(self):
        docs = copy.deepcopy(fixture()["documents"])
        del docs[1]["eur_quotes"]["JPY"]
        self.assertEqual(inspect(docs)["state"], "LAB_ECB_DOCUMENT_REVIEW_REFUSED")
        docs = copy.deepcopy(fixture()["documents"])
        docs[0]["eur_quotes"]["BRL"] = "6.0692"
        self.assertEqual(inspect(docs)["state"], "LAB_ECB_DOCUMENT_REVIEW_REFUSED")

    def test_bogus_numeric_strings_nan_zero_or_negative_rejected(self):
        for invalid in (None, 1.5, "NaN", "Infinity", "0", "-1", "abc", "1000000", "1e-999999", "0.000001"):
            docs = copy.deepcopy(fixture()["documents"])
            docs[1]["eur_quotes"]["CAD"] = invalid
            self.assertEqual(inspect(docs)["state"],
                             "LAB_ECB_DOCUMENT_REVIEW_REFUSED", repr(invalid))

    def test_future_date_and_same_date_both_rejected(self):
        for new in ("2026-11-03", "2026-10-30"):
            docs = copy.deepcopy(fixture()["documents"])
            docs[1]["date"] = new
            self.assertEqual(inspect(docs)["state"], "LAB_ECB_DOCUMENT_REVIEW_REFUSED")

    def test_weekend_reference_date_rejected(self):
        docs = copy.deepcopy(fixture()["documents"])
        docs[1]["date"] = "2026-10-31"
        self.assertEqual(inspect(docs)["state"], "LAB_ECB_DOCUMENT_REVIEW_REFUSED")

    def test_reversed_dates_rejected(self):
        docs = copy.deepcopy(fixture()["documents"])
        docs.reverse()
        self.assertEqual(inspect(docs)["state"], "LAB_ECB_DOCUMENT_REVIEW_REFUSED")

    def test_distant_dates_not_presented_as_adjacent_comparison(self):
        docs = copy.deepcopy(fixture()["documents"])
        docs[0]["date"] = "2026-10-20"
        self.assertEqual(inspect(docs)["state"], "LAB_ECB_DOCUMENT_REVIEW_REFUSED")

    def test_more_than_allowed_change_is_not_converted_into_strength(self):
        docs = copy.deepcopy(fixture()["documents"])
        docs[1]["eur_quotes"]["USD"] = "2.00"
        self.assertEqual(inspect(docs)["state"], "LAB_ECB_DOCUMENT_REVIEW_REFUSED")

    def test_unexpected_fields_do_not_allow_hindsight_metrics(self):
        docs = copy.deepcopy(fixture()["documents"])
        docs[1]["next_week_direction"] = "BUY"
        self.assertEqual(inspect(docs)["state"], "LAB_ECB_DOCUMENT_REVIEW_REFUSED")

    def test_naive_evaluation_clock_cannot_prove_exante_availability(self):
        with self.assertRaises(ValueError):
            inspect(evaluated=datetime(2026, 11, 2, 20))

    def test_no_live_forecast_oos_worker_trade_permission_in_success_or_denial(self):
        for out in (inspect(), inspect(evaluated=datetime(
                2026, 11, 2, 11, tzinfo=timezone.utc))):
            self.assertIsNone(out["real_currency_strength"])
            self.assertFalse(out["actual_historical_capture_attested"])
            self.assertFalse(out["original_bytes_custodied"])
            self.assertFalse(out["publication_time_independently_verified"])
            for flag in ("real_predictive_accuracy_proven", "can_feed_live_radar",
                         "can_feed_real_oos", "trade_authorized",
                         "worker_enabled", "scheduler_enabled"):
                self.assertFalse(out[flag], flag)

    def test_manifest_does_not_claim_commercial_or_point_in_time_license_proof(self):
        d = fixture()
        self.assertFalse(d["rights_review"]["commercial_product_legal_review_completed"])
        self.assertTrue(d["limitations"]["crosses_21_derived_not_21_observed"])
        for key in ("can_feed_live_radar", "can_feed_real_oos",
                    "trade_authorized", "worker_enabled", "scheduler_enabled",
                    "paid_api_invoked"):
            self.assertFalse(d[key], key)


if __name__ == "__main__":
    unittest.main()
