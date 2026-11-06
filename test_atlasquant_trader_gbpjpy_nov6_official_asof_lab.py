"""GBP/JPY official pages and 28-pair documentary coverage: no real bias."""
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import json
import unittest

from atlasquant_fx_universe import OFFICIAL_PAIRS
from atlasquant_trader_gbpjpy_nov6_official_asof_lab import (
    FIXED_CASEBOOK_SHA256,
    inspect_gbpjpy_nov6_official_asof_lab as inspect,
)
from atlasquant_trader_g8_four_currency_doc_coverage_lab import (
    inspect_g8_four_currency_documentary_coverage_lab as inspect_g8,
)

DOCS = Path(__file__).resolve().parent / "docs" / "continuidade"
GBPJPY = (DOCS / "TRADER_GBPJPY_20261106_FOUR_OFFICIAL_DOCUMENTS_ASOF_CASE_LAB.json").read_bytes()
EURUSD = (DOCS / "TRADER_EURUSD_20261106_FOUR_OFFICIAL_DOCUMENTS_ASOF_CASE_LAB.json").read_bytes()
NOW = datetime(2026, 11, 6, 17, tzinfo=timezone.utc)


def at(m, d, h=0, minute=0):
    return datetime(2026, m, d, h, minute, tzinfo=timezone.utc)


def run(when=NOW, raw=GBPJPY):
    return inspect(raw, as_of_utc=when)


def run_g8(when=NOW, *, eurusd=EURUSD, gbpjpy=GBPJPY):
    return inspect_g8(eurusd_casebook_raw=eurusd, gbpjpy_casebook_raw=gbpjpy,
                      as_of_utc=when)


class GbpJpyAndFourCurrencyG8Tests(unittest.TestCase):
    def assert_no_operational_bias(self, r):
        for f in ("can_feed_live_radar", "trade_authorized", "publishable",
                  "worker_enabled", "scheduler_enabled"):
            self.assertIs(r[f], False, f)
        self.assertIsNone(r["fx_bias"])
        self.assertEqual(r["operational_bias"], "AGUARDAR")
        self.assertEqual(r["validated_prediction_count"], 0)
        self.assertIsNone(r["validated_accuracy"])
        self.assertEqual((r["http_requests"], r["new_cost_brl"]), (0, 0))

    def test_nov6_four_official_pages_visible_but_not_pit_witnessed(self):
        r = run()
        self.assertEqual(r["state"], "LAB_FOUR_DOCUMENT_REFERENCES_VISIBLE_BUT_PIT_UNATTESTED")
        self.assertEqual(r["visible_document_count"], 4)
        self.assertTrue(r["two_sided_inflation_and_policy_documentary_coverage"])
        self.assertEqual(r["accepted_casebook_sha256"], FIXED_CASEBOOK_SHA256)
        self.assertEqual(r["accepted_casebook_sha256"], sha256(GBPJPY).hexdigest())
        for flag in ("source_original_bytes_independently_archived",
                     "independent_historical_page_timestamp_witnessed",
                     "pre_event_consensus_available_and_attested",
                     "historical_macroeconomic_vintage_attested",
                     "macro_surprise_quantified", "relative_gbp_jpy_strength_verified",
                     "inflation_statistical_methods_comparable",
                     "policy_rate_instruments_directly_comparable"):
            self.assertIs(r[flag], False, flag)
        self.assert_no_operational_bias(r)

    def test_september_uk_cpi_not_cpih_and_japan_national_not_tokyo(self):
        r = run()
        p = {x["record_id"]: x for x in r["visible_documents_as_retrospective_references"]}
        self.assertEqual(p["GBP_ONS_CPI_SEP2026"]["reference_period"], "2026-09")
        self.assertEqual(p["JPY_STAT_CPI_SEP2026"]["reference_period"], "2026-09")
        self.assertEqual(p["GBP_ONS_CPI_SEP2026"]["reported_values_percent_document_claim"],
                         {"annual_cpi_yoy": "3.5"})
        self.assertEqual(p["JPY_STAT_CPI_SEP2026"]["reported_values_percent_document_claim"],
                         {"annual_national_cpi_yoy": "2.1"})
        self.assertTrue(r["inflation_observation_periods_match"])
        self.assertFalse(r["inflation_statistical_methods_comparable"])

    def test_boe_4_percent_and_boj_around_1_25_are_different_instruments(self):
        p = {x["record_id"]: x for x in run()["visible_documents_as_retrospective_references"]}
        self.assertEqual(p["GBP_BOE_NOV2026_BANK_RATE"]
                         ["reported_values_percent_document_claim"]["bank_rate"], "4.00")
        self.assertEqual(p["JPY_BOJ_OCT2026_MONETARY_DECISION"]
                         ["reported_values_percent_document_claim"]["target_around"], "1.25")

    def test_uk_ons_release_before_0600_utc_does_not_leak(self):
        self.assertEqual(run(when=at(10, 21, 5, 59))["visible_document_count"], 0)
        self.assertEqual(run(when=at(10, 21, 6))["visible_document_count"], 1)

    def test_japan_cpi_date_only_gate_is_next_day_utc(self):
        r = run(when=at(10, 23, 23, 59))
        self.assertIn("JPY_STAT_CPI_SEP2026", r["not_yet_admissible_record_ids"])
        self.assertEqual(r["visible_document_count"], 1)
        self.assertEqual(run(when=at(10, 24))["visible_document_count"], 2)

    def test_boj_policy_exact_statement_release_1202_jst(self):
        r = run(when=at(10, 30, 3, 1))
        self.assertIn("JPY_BOJ_OCT2026_MONETARY_DECISION",
                      r["not_yet_admissible_record_ids"])
        self.assertEqual(r["visible_document_count"], 2)
        self.assertEqual(run(when=at(10, 30, 3, 2))["visible_document_count"], 3)

    def test_boe_date_only_conservative_next_day_gate(self):
        self.assertEqual(run(when=at(11, 5, 23, 59))["visible_document_count"], 3)
        self.assertEqual(run(when=at(11, 6))["visible_document_count"], 4)

    def test_never_invent_october_uk_cpi_or_unreleased_boj_summary(self):
        for r in (run(), run(when=at(11, 20))):
            self.assertFalse(r["future_uk_oct2026_cpi_number_in_casebook"])
            self.assertFalse(r["future_boj_summary_of_opinions_in_casebook"])
            self.assert_no_operational_bias(r)

    def test_source_value_or_time_mutation_is_refused(self):
        for field, fake in (("reference_period", "2026-10"),
                            ("admissibility_gate_utc", "2026-10-01T00:00:00Z"),
                            ("source_url", "https://example.org/fake")):
            c = json.loads(GBPJPY)
            c["records"][0][field] = fake
            self.assertEqual(run(raw=json.dumps(c).encode())["state"], "LAB_BLOCKED")

    def test_reject_bad_clock_broken_bytes_or_duplicate_json_key(self):
        self.assertEqual(run(when=datetime(2026, 11, 6, 17))["state"], "LAB_BLOCKED")
        for raw in (None, b"broken", b"\xff" * 300, b"x" * 6501,
                    GBPJPY.replace(b'"kind":', b'"kind":"FRAUD","kind":', 1)):
            self.assertEqual(run(raw=raw)["state"], "LAB_BLOCKED")

    def test_bridge_covers_all_28_but_only_six_crosses_have_both_document_sets(self):
        r = run_g8()
        self.assertEqual(r["state"], "LAB_G8_28_PAIR_FOUR_CURRENCY_DOCUMENTARY_MAP_NO_BIAS")
        self.assertEqual(r["currency_count"], 8)
        self.assertEqual(r["pair_count"], 28)
        self.assertEqual(r["document_references_visible"], 8)
        self.assertEqual(set(r["currencies_with_both_families_documented_claim_only"]),
                         {"EUR", "USD", "GBP", "JPY"})
        self.assertEqual(r["pair_count_with_two_sided_four_family_documents"], 6)
        self.assertEqual(set(r["pairs_with_both_sides_documented_claim_only"]),
                         {"EUR/USD", "GBP/USD", "USD/JPY", "EUR/GBP", "EUR/JPY", "GBP/JPY"})
        self.assertEqual({x["pair"] for x in r["pairs"]}, set(OFFICIAL_PAIRS))
        self.assert_no_operational_bias(r)

    def test_documentary_six_pair_coverage_is_never_six_real_predictions(self):
        r = run_g8()
        for x in r["pairs"]:
            self.assertEqual(x["D1"], "AGUARDAR")
            self.assertEqual(x["W1"], "AGUARDAR")
            self.assertFalse(x["direct_statistical_or_rate_comparability_verified"])
            self.assertFalse(x["trade_authorized"])
        for f in ("complete_8_currency_16_source_documentary_coverage",
                  "official_document_original_bytes_attested",
                  "source_publication_times_independently_witnessed",
                  "vintage_and_statistical_method_comparability_verified",
                  "independent_currency_strength_ranking_verified",
                  "all_28_pairs_directionally_verified"):
            self.assertFalse(r[f])
        self.assert_no_operational_bias(r)

    def test_before_nov6_boe_and_eurostat_are_withheld_for_partial_pairs(self):
        r = run_g8(when=at(11, 4, 23, 59))
        self.assertEqual(r["document_references_visible"], 6)
        self.assertEqual(r["pairs_with_both_sides_documented_claim_only"], ["USD/JPY"])
        self.assertEqual(r["pair_count_with_two_sided_four_family_documents"], 1)

    def test_nov5_eurostat_appears_but_boe_still_missing(self):
        r = run_g8(when=at(11, 5))
        self.assertEqual(r["document_references_visible"], 7)
        self.assertEqual(set(r["pairs_with_both_sides_documented_claim_only"]),
                         {"EUR/USD", "USD/JPY", "EUR/JPY"})
        self.assert_no_operational_bias(r)

    def test_tampered_either_casebook_blocks_entire_bridge(self):
        for params in ({"eurusd": b"fake"}, {"gbpjpy": b"fake"},
                       {"eurusd": None}, {"gbpjpy": None}):
            r = run_g8(**params)
            self.assertEqual(r["state"], "LAB_BLOCKED")
            self.assert_no_operational_bias(r)

    def test_g8_bridge_naive_clock_rejected(self):
        r = run_g8(when=datetime(2026, 11, 6, 17))
        self.assertEqual(r["state"], "LAB_BLOCKED")
        self.assert_no_operational_bias(r)


if __name__ == "__main__":
    unittest.main()
