"""Guard the CPI-period audit from producing premature G8 macro bias."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import unittest

from atlasquant_fx_universe import OFFICIAL_PAIRS
from atlasquant_trader_g8_pair_comparability_gate_lab import (
    EVIDENCE_GATES_NOT_MET, _classify_inflation_periods,
    inspect_g8_pair_comparability_gate_lab as inspect,
)

BASE = Path(__file__).resolve().parent / "docs" / "continuidade"
EURUSD = (BASE / "TRADER_EURUSD_20261106_FOUR_OFFICIAL_DOCUMENTS_ASOF_CASE_LAB.json").read_bytes()
GBPJPY = (BASE / "TRADER_GBPJPY_20261106_FOUR_OFFICIAL_DOCUMENTS_ASOF_CASE_LAB.json").read_bytes()
OTHER = (BASE / "TRADER_G8_CHF_AUD_CAD_NZD_20261106_OFFICIAL_ASOF_CASE_LAB.json").read_bytes()
NOW = datetime(2026, 11, 6, 17, tzinfo=timezone.utc)


def at(month, day, hour=0, minute=0):
    return datetime(2026, month, day, hour, minute, tzinfo=timezone.utc)


def run(when=NOW, *, eurusd=EURUSD, gbpjpy=GBPJPY, other=OTHER):
    return inspect(eurusd_casebook_raw=eurusd, gbpjpy_casebook_raw=gbpjpy,
                   remaining_four_casebook_raw=other, as_of_utc=when)


class G8PairComparabilityGateTests(unittest.TestCase):
    def assert_stays_quarantined(self, result):
        self.assertEqual(result["operational_bias"], "AGUARDAR")
        self.assertIsNone(result["fx_bias"])
        self.assertIsNone(result["best_pair_of_day"])
        self.assertEqual(result["ranked_currencies"], [])
        self.assertEqual(result["validated_prediction_count"], 0)
        self.assertIsNone(result["validated_accuracy"])
        self.assertEqual((result["http_requests"], result["new_cost_brl"]), (0, 0))
        for flag in ("trade_authorized", "can_feed_live_radar", "publishable",
                     "worker_enabled", "scheduler_enabled",
                     "original_source_bytes_attested",
                     "source_publication_time_independently_attested",
                     "cpi_series_cross_country_comparable",
                     "policy_stance_cross_country_comparable",
                     "consensus_available_pre_event", "historical_price_outcomes_validated"):
            self.assertIs(result[flag], False, flag)
        self.assertEqual(tuple(result["evidence_gates_not_met"]), EVIDENCE_GATES_NOT_MET)

    def test_nov6_all_28_but_zero_tradable_comparisons(self):
        r = run()
        self.assertEqual(r["state"], "LAB_28_PAIR_COMPARABILITY_AUDIT_NO_FX_BIAS")
        self.assertEqual((r["currencies_in_universe"], r["pairs_in_universe"],
                          r["official_page_references_visible"]), (8, 28, 16))
        self.assertEqual(len(r["pair_rows"]), 28)
        self.assertEqual({p["pair"] for p in r["pair_rows"]}, set(OFFICIAL_PAIRS))
        self.assertTrue(all(p["both_sides_cpi_and_policy_page_references_visible"]
                            for p in r["pair_rows"]))
        self.assert_stays_quarantined(r)

    def test_exact_period_bins_eleven_seven_ten(self):
        r = run()
        self.assertEqual(r["monthly_same_period_pair_count_document_only"], 11)
        self.assertEqual(r["mixed_quarterly_monthly_pair_count_document_only"], 7)
        self.assertEqual(r["monthly_different_period_pair_count_document_only"], 10)
        self.assertEqual(r["pairs_missing_cpi_or_policy_asof"], 0)
        self.assertEqual(r["quarterly_same_period_pair_count_document_only"], 0)
        self.assertEqual(r["quarterly_different_period_pair_count_document_only"], 0)
        self.assertEqual(r["unknown_period_format_pair_count_document_only"], 0)
        self.assertEqual(sum((r[k] for k in (
            "monthly_same_period_pair_count_document_only",
            "mixed_quarterly_monthly_pair_count_document_only",
            "monthly_different_period_pair_count_document_only",
            "pairs_missing_cpi_or_policy_asof"))), 28)

    def test_same_month_does_not_claim_harmonized_method(self):
        p = {x["pair"]: x for x in run()["pair_rows"]}
        self.assertEqual(p["GBP/USD"]["inflation_period_audit"],
                         "MONTHLY_SAME_PERIOD_DOCUMENT_ONLY")
        self.assertEqual(p["EUR/CHF"]["inflation_period_audit"],
                         "MONTHLY_SAME_PERIOD_DOCUMENT_ONLY")
        for pair in ("GBP/USD", "EUR/CHF"):
            self.assertFalse(p[pair]["same_period_means_comparable_inflation"])
            self.assertFalse(p[pair]["policy_instrument_comparability_verified"])
            self.assertFalse(p[pair]["macro_score_available"])

    def test_month_mismatch_eur_usd_kept_explicit(self):
        p = {x["pair"]: x for x in run()["pair_rows"]}
        x = p["EUR/USD"]
        self.assertEqual(x["inflation_base_period"], "2026-10")
        self.assertEqual(x["inflation_quote_period"], "2026-09")
        self.assertEqual(x["inflation_period_audit"], "MONTHLY_DIFFERENT_PERIOD")
        self.assertFalse(x["macro_score_available"])

    def test_nzd_quarter_is_not_mislabeled_september_month(self):
        p = {x["pair"]: x for x in run()["pair_rows"]}
        self.assertEqual(p["AUD/NZD"]["inflation_period_audit"], "MONTHLY_VS_QUARTERLY")
        self.assertEqual(p["AUD/NZD"]["inflation_base_period"], "2026-09")
        self.assertEqual(p["AUD/NZD"]["inflation_quote_period"], "2026-Q3")
        self.assertEqual(p["NZD/CHF"]["inflation_period_audit"], "MONTHLY_VS_QUARTERLY")
        self.assertEqual(p["NZD/CHF"]["inflation_base_period"], "2026-Q3")

    def test_two_equal_quarters_are_not_called_mixed_frequency(self):
        status = _classify_inflation_periods("2026-Q3", "2026-Q3", complete=True)
        self.assertEqual(status, "QUARTERLY_SAME_PERIOD_DOCUMENT_ONLY")

    def test_two_different_quarters_are_not_called_mixed_frequency(self):
        status = _classify_inflation_periods("2026-Q2", "2026-Q3", complete=True)
        self.assertEqual(status, "QUARTERLY_DIFFERENT_PERIOD")

    def test_actual_month_quarter_is_still_mixed_frequency(self):
        for a, b in (("2026-09", "2026-Q3"), ("2026-Q3", "2026-09")):
            self.assertEqual(_classify_inflation_periods(a, b, complete=True),
                             "MONTHLY_VS_QUARTERLY")

    def test_invalid_or_ambiguous_reference_period_is_unknown(self):
        for a, b in (("2026-13", "2026-09"), ("2026-Q5", "2026-Q3"),
                     ("2026", "2026-09"), (None, "2026-Q3")):
            with self.subTest(base=a, quote=b):
                self.assertEqual(_classify_inflation_periods(a, b, complete=True),
                                 "UNKNOWN_PERIOD_FORMAT")

    def test_incomplete_documents_override_period_matching(self):
        self.assertEqual(_classify_inflation_periods(
            "2026-Q3", "2026-Q3", complete=False), "DOCUMENTS_NOT_YET_ADMISSIBLE_ASOF")

    def test_all_rows_await_daily_weekly_with_no_fake_accuracy(self):
        for x in run()["pair_rows"]:
            self.assertEqual((x["D1"], x["W1"]), ("AGUARDAR", "AGUARDAR"))
            self.assertFalse(x["official_page_values_historically_authenticated"])
            self.assertFalse(x["trade_authorized"])
            self.assertFalse(x["macro_score_available"])

    def test_before_nov6_gbp_policy_date_no_premature_completion(self):
        r = run(when=at(11, 5))
        self.assertEqual(r["official_page_references_visible"], 15)
        self.assertEqual(r["pairs_missing_cpi_or_policy_asof"], 7)
        self.assertEqual(r["monthly_same_period_pair_count_document_only"], 7)
        self.assertEqual(r["monthly_different_period_pair_count_document_only"], 8)
        self.assertEqual(r["mixed_quarterly_monthly_pair_count_document_only"], 6)
        x = {p["pair"]: p for p in r["pair_rows"]}
        self.assertEqual(x["GBP/JPY"]["inflation_period_audit"],
                         "DOCUMENTS_NOT_YET_ADMISSIBLE_ASOF")
        self.assertEqual(x["EUR/USD"]["inflation_period_audit"],
                         "MONTHLY_DIFFERENT_PERIOD")
        self.assert_stays_quarantined(r)

    def test_at_early_date_no_fabricated_document_coverage(self):
        r = run(when=at(9, 1))
        self.assertEqual(r["official_page_references_visible"], 0)
        self.assertEqual(r["pairs_missing_cpi_or_policy_asof"], 28)
        self.assertEqual(r["monthly_same_period_pair_count_document_only"], 0)
        self.assertEqual(r["mixed_quarterly_monthly_pair_count_document_only"], 0)
        self.assert_stays_quarantined(r)

    def test_offsets_normalized_to_utc_and_are_deterministic(self):
        r = run(when=NOW.astimezone(timezone(timedelta(hours=-4))))
        self.assertEqual(r["as_of_utc"], NOW.isoformat())
        self.assertEqual(r["monthly_same_period_pair_count_document_only"], 11)

    def test_input_casebook_mutation_or_missing_blocks_all(self):
        for kw in ({"eurusd": EURUSD + b" "}, {"gbpjpy": None},
                   {"other": OTHER.replace(b'"4.85"', b'"4.86"')}):
            r = run(**kw)
            self.assertEqual(r["state"], "LAB_BLOCKED")
            self.assertEqual(r["pair_rows"], [])
            self.assert_stays_quarantined(r)

    def test_unsafe_time_refused_without_partial_output(self):
        for bad in (None, "2026-11-06", datetime(2026, 11, 6)):
            r = run(when=bad)
            self.assertEqual(r["state"], "LAB_BLOCKED")
            self.assertEqual(r["pair_rows"], [])
            self.assert_stays_quarantined(r)


if __name__ == "__main__":
    unittest.main()
