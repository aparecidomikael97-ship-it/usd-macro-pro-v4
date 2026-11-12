"""G8 central-bank level semantics — research only, never FX inference."""
from datetime import datetime, timezone, timedelta
from hashlib import sha256
from pathlib import Path
from unittest.mock import patch
import unittest

from atlasquant_fx_universe import CURRENCIES, OFFICIAL_PAIRS
from atlasquant_trader_g8_issuer_custody_chain_lab import DOCS
from atlasquant_trader_g8_policy_instrument_semantics_lab import (
    CASEBOOK_SHA256, inspect_g8_policy_instrument_semantics_lab as inspect,
)

BOOK = (Path(__file__).resolve().parent / "docs" / "continuidade" /
        "TRADER_G8_POLICY_INSTRUMENT_DEFINITION_LAB_20261108.json").read_bytes()
NOW = datetime(2026, 11, 9, tzinfo=timezone.utc)


class PolicyInstrumentTests(unittest.TestCase):
    def run_book(self, raw=BOOK, at=NOW):
        return inspect(raw, as_of_utc=at)

    def assert_no_fx(self, result):
        self.assertEqual(result["operational_bias"], "AGUARDAR")
        self.assertIsNone(result["fx_bias"])
        self.assertIsNone(result["validated_directional_accuracy"])
        self.assertEqual((result["http_requests"], result["file_writes"], result["new_cost_brl"]), (0, 0, 0))
        for field in (
            "original_issuer_response_bytes_archived_at_release",
            "historical_policy_rate_vintages_verified",
            "issuer_release_instant_independently_attested",
            "nominal_instruments_cross_currency_comparable",
            "actual_market_yields_observed", "future_policy_expectation_curve_available",
            "real_interest_rate_differentials_verified", "policy_strength_scores_calculated",
            "trade_authorized", "historical_backtest_approved", "can_feed_live_radar",
            "worker_enabled", "scheduler_enabled", "publishable",
        ):
            self.assertFalse(result[field], field)
        for p in result["pair_rows"]:
            self.assertIsNone(p["raw_nominal_level_spread_pct_points"])
            self.assertFalse(p["economic_stance_comparable"])
            self.assertFalse(p["trade_authorized"])
            self.assertEqual((p["D1"], p["W1"]), ("AGUARDAR", "AGUARDAR"))

    def test_sha_pinned_eight_currencies_28_pairs_without_bias(self):
        self.assertEqual(sha256(BOOK).hexdigest(), CASEBOOK_SHA256)
        r = self.run_book()
        self.assertEqual(r["state"], "LAB_EIGHT_POLICY_INSTRUMENTS_RESEARCHED_HETEROGENEOUS_UNATTESTED")
        self.assertEqual((r["currency_count"], r["pair_count"]), (8, 28))
        self.assertEqual(set(DOCS), set(CURRENCIES))
        self.assertEqual({row["pair"] for row in r["pair_rows"]}, set(OFFICIAL_PAIRS))
        self.assertEqual(r["representation_counts"], {
            "TARGET_RANGE": 1, "APPROXIMATE_GUIDELINE": 1,
            "EXACT_INSTRUMENT_LEVEL": 6,
        })
        self.assert_no_fx(r)

    def test_fed_is_an_interval_not_a_converted_midpoint(self):
        usd = {r["currency"]: r for r in self.run_book()["currency_rows"]}["USD"]
        self.assertEqual(usd["instrument_id"], "FEDERAL_FUNDS_TARGET_RANGE")
        self.assertEqual((usd["issuer_researched_range_low_pct_claim"],
                          usd["issuer_researched_range_high_pct_claim"]), ("3.75", "4.00"))
        self.assertIsNone(usd["issuer_researched_point_pct_claim"])

    def test_japan_stays_approximate_not_an_exact_market_yield(self):
        jpy = {r["currency"]: r for r in self.run_book()["currency_rows"]}["JPY"]
        self.assertTrue(jpy["approximate_wording_must_be_preserved"])
        self.assertEqual(jpy["representation"], "APPROXIMATE_GUIDELINE")
        self.assertEqual(jpy["issuer_researched_point_pct_claim"], "1.25")
        self.assertFalse(jpy["rate_claim_is_a_measured_market_yield"])

    def test_equal_eur_and_cad_2_50_are_different_rate_instruments(self):
        rows = {r["currency"]: r for r in self.run_book()["currency_rows"]}
        self.assertEqual(rows["EUR"]["issuer_researched_point_pct_claim"], "2.50")
        self.assertEqual(rows["CAD"]["issuer_researched_point_pct_claim"], "2.50")
        self.assertNotEqual(rows["EUR"]["instrument_id"], rows["CAD"]["instrument_id"])
        pairs = {r["pair"]: r for r in self.run_book()["pair_rows"]}
        self.assertFalse(pairs["EUR/CAD"]["economic_stance_comparable"])
        self.assertIsNone(pairs["EUR/CAD"]["raw_nominal_level_spread_pct_points"])

    def test_aud_vs_chf_not_auto_buy_even_with_different_nominal_levels(self):
        rows = {r["currency"]: r for r in self.run_book()["currency_rows"]}
        self.assertEqual(rows["AUD"]["issuer_researched_point_pct_claim"], "4.85")
        self.assertEqual(rows["CHF"]["issuer_researched_point_pct_claim"], "0.00")
        pair = next(p for p in self.run_book()["pair_rows"] if p["pair"] == "AUD/CHF")
        self.assertIsNone(pair["raw_nominal_level_spread_pct_points"])
        self.assertEqual(pair["D1"], "AGUARDAR")

    def test_late_research_never_backfilled_into_october_day(self):
        earlier = self.run_book(at=datetime(2026, 11, 8, 23, 59, 59, tzinfo=timezone.utc))
        self.assertEqual(earlier["state"], "LAB_RESEARCH_NOT_VISIBLE_ASOF")
        self.assertEqual((earlier["currency_rows"], earlier["pair_rows"]), ([], []))
        self.assert_no_fx(earlier)

    def test_timezone_equivalence_after_conservative_cutoff(self):
        local = datetime(2026, 11, 8, 20, tzinfo=timezone(timedelta(hours=-4)))
        self.assertEqual(self.run_book(at=local), self.run_book())

    def test_far_future_does_not_certify_history(self):
        future = self.run_book(at=datetime(2028, 1, 1, tzinfo=timezone.utc))
        self.assertEqual(future["currency_count"], 8)
        self.assert_no_fx(future)

    def test_tampered_sha_or_wrong_url_rejected(self):
        for raw in (BOOK + b" ", BOOK.replace(b"3.75", b"3.85"),
                    BOOK.replace(b"www.federalreserve.gov", b"not-an-issuer.example")):
            r = self.run_book(raw)
            self.assertEqual(r["state"], "LAB_BLOCKED")
            self.assert_no_fx(r)

    def test_invalid_asof_and_missing_official_currency_catalog_refused(self):
        for at in (None, datetime(2026, 11, 9)):
            r = self.run_book(at=at)
            self.assertEqual(r["state"], "LAB_BLOCKED")
            self.assert_no_fx(r)
        with patch.dict(DOCS, {}, clear=True):
            self.assertEqual(self.run_book()["state"], "LAB_BLOCKED")


if __name__ == "__main__":
    unittest.main()
