"""Synthetic fixtures only: no official prices, issuer archives, or live signals."""
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
import unittest

from atlasquant_trader_eurusd_sr3_esr_quarter_lab import (
    QuarterFuturesQuoteClaim, PRODUCTS, RESEARCH_VISIBLE_FROM_UTC,
    imm_quarter_window, inspect_eurusd_sr3_esr_imm_quarter_lab as inspect,
)
UTC = timezone.utc
ASOF = datetime(2026, 11, 14, 17, tzinfo=UTC)
D1 = datetime(2026, 11, 11, 15, tzinfo=UTC)
D2 = datetime(2026, 11, 13, 15, tzinfo=UTC)


def synthetic(c: str, *, period="2026-09", price1="96.00", price2="95.98"):
    p = PRODUCTS[c]["code"]
    return [QuarterFuturesQuoteClaim(c, p, period, date(2026, 11, 11), D1,
                                     D1 + timedelta(minutes=10), D1 + timedelta(minutes=20),
                                     price1, 20, "a"*64),
            QuarterFuturesQuoteClaim(c, p, period, date(2026, 11, 13), D2,
                                     D2 + timedelta(minutes=10), D2 + timedelta(minutes=20),
                                     price2, 20, "b"*64)]


def dataset():
    return {"USD": synthetic("USD"), "EUR": synthetic("EUR", price1="97.00", price2="97.03")}


class SR3ESRQuarterTests(unittest.TestCase):
    def get(self, q=None, t=ASOF):
        return inspect(quotes_by_currency=dataset() if q is None else q, as_of_utc=t)

    def assert_no_trade(self, r):
        self.assertEqual(r["operational_bias"], "AGUARDAR")
        self.assertIsNone(r["eurusd_spot_direction"])
        self.assertIsNone(r["calibrated_direction_probability"])
        self.assertIsNone(r["claimed_sofr_minus_estr_change_bps"])
        for k in ("cme_product_slate_proves_contract_liquidity", "same_benchmark_or_policy_rate",
                  "benchmark_basis_adjusted", "independent_issuer_bytes_archived",
                  "quote_timestamps_independently_attested", "licensed_reuse_verified",
                  "contract_specific_liquidity_attested", "forward_fx_basis_verified",
                  "forward_exchange_rate_verified", "point_in_time_backtest_ready",
                  "trade_authorized", "publishable", "scheduler_enabled"):
            self.assertFalse(r[k], k)
        self.assertEqual((r["http_requests"], r["file_writes"], r["new_cost_brl"]), (0, 0, 0))

    def test_imm_quarter_windows_exact_including_year_wrap(self):
        self.assertEqual(imm_quarter_window("2026-09"), (date(2026,9,16), date(2026,12,16)))
        self.assertEqual(imm_quarter_window("2026-12"), (date(2026,12,16), date(2027,3,17)))
        self.assertEqual(imm_quarter_window("2027-03"), (date(2027,3,17), date(2027,6,16)))

    def test_invalid_reference_periods(self):
        for v in (None, "2026-11", "2026-9", "hello", "2026-00", "200-09", "2100-09", 0):
            with self.subTest(v=v):
                self.assertIsNone(imm_quarter_window(v))

    def test_synthetic_quarter_aligns_without_spot_signal(self):
        r = self.get()
        self.assertEqual(r["state"], "LAB_SR3_ESR_MATCHED_QUARTER_NOT_AUTHENTICATED")
        self.assertTrue(r["both_claimed_quotes_same_quarter"])
        self.assertEqual(r["evidence_by_currency"]["USD"]["imm_reference_end_exclusive"], "2026-12-16")
        self.assertEqual(r["evidence_by_currency"]["USD"]["claimed_underlying_rate_change_bps"], "2.00")
        self.assertEqual(r["evidence_by_currency"]["EUR"]["claimed_underlying_rate_change_bps"], "-3.00")
        self.assert_no_trade(r)

    def test_named_september_contract_is_active_in_november(self):
        r = self.get()
        self.assertEqual(r["evidence_by_currency"]["USD"]["status"], "SELF_CLAIMED_VINTAGES_ONLY_NOT_AUTHENTICATED")
        self.assert_no_trade(r)

    def test_expired_september_contract_rejected_after_december_imm(self):
        r = self.get(t=datetime(2026,12,17,tzinfo=UTC))
        self.assertEqual(r["evidence_by_currency"]["USD"]["status"], "CLAIMS_INVALID_OR_UNAVAILABLE")
        self.assert_no_trade(r)

    def test_volume_totals_do_not_certify_specific_vintage(self):
        r = self.get()
        self.assertEqual(r["cme_product_slate_volumes"]["ESR"]["volume"], 185)
        self.assertEqual(r["cme_product_slate_volumes"]["SR3"]["volume"], 4735231)
        self.assertFalse(r["cme_product_slate_proves_contract_liquidity"])
        self.assert_no_trade(r)

    def test_zero_trade_volume_invalid_even_when_product_total_positive(self):
        q = dataset()
        q["EUR"][1] = replace(q["EUR"][1], contract_session_volume=0)
        r = self.get(q)
        self.assertEqual(r["evidence_by_currency"]["EUR"]["status"], "CLAIMS_INVALID_OR_UNAVAILABLE")
        self.assertFalse(r["both_claimed_quotes_same_quarter"])
        self.assert_no_trade(r)

    def test_settlement_is_not_proof_of_executed_trade(self):
        q = dataset()
        q["EUR"] = [replace(x, quote_kind="SETTLEMENT", contract_session_volume=None) for x in q["EUR"]]
        r = self.get(q)
        self.assertEqual(r["evidence_by_currency"]["EUR"]["quote_kind"], "SETTLEMENT")
        self.assertFalse(r["evidence_by_currency"]["EUR"]["volume_from_named_contract_authenticated"])
        self.assert_no_trade(r)

    def test_mismatched_reference_quarters_never_compare(self):
        q = dataset()
        q["EUR"] = synthetic("EUR", period="2026-12")
        r = self.get(q)
        self.assertFalse(r["both_claimed_quotes_same_quarter"])
        self.assert_no_trade(r)

    def test_mismatched_new_trade_dates_never_compare(self):
        q = dataset()
        q["EUR"][1] = replace(q["EUR"][1],
                               trade_date=date(2026,11,12),
                               observed_at_utc=D2-timedelta(days=1),
                               published_at_utc=D2-timedelta(days=1)+timedelta(minutes=10),
                               captured_at_utc=D2-timedelta(days=1)+timedelta(minutes=20))
        self.assertEqual(self.get(q)["evidence_by_currency"]["EUR"]["status"],
                         "SELF_CLAIMED_VINTAGES_ONLY_NOT_AUTHENTICATED")
        r = self.get(q)
        self.assertFalse(r["both_claimed_quotes_same_quarter"])
        self.assert_no_trade(r)

    def test_future_capture_not_usable_at_cutoff(self):
        q = dataset()
        q["EUR"][1] = replace(q["EUR"][1], captured_at_utc=ASOF+timedelta(seconds=1))
        r = self.get(q)
        self.assertEqual(r["evidence_by_currency"]["EUR"]["status"], "CLAIMS_INVALID_OR_UNAVAILABLE")
        self.assert_no_trade(r)

    def test_claimed_source_hashes_not_attestation(self):
        q = dataset()
        q["USD"][1] = replace(q["USD"][1], source_sha256_claim=q["USD"][0].source_sha256_claim)
        r = self.get(q)
        self.assertEqual(r["evidence_by_currency"]["USD"]["status"], "CLAIMS_INVALID_OR_UNAVAILABLE")
        self.assert_no_trade(r)

    def test_cross_currency_instrument_code_rejected(self):
        q = dataset()
        q["EUR"][0] = replace(q["EUR"][0], product_code="SR3")
        r = self.get(q)
        self.assertEqual(r["evidence_by_currency"]["EUR"]["status"], "CLAIMS_INVALID_OR_UNAVAILABLE")
        self.assert_no_trade(r)

    def test_before_documentation_research_is_blocked(self):
        r = self.get(t=RESEARCH_VISIBLE_FROM_UTC-timedelta(seconds=1))
        self.assertEqual(r["state"], "LAB_RESEARCH_NOT_VISIBLE_AS_OF")
        self.assertEqual(r["evidence_by_currency"], {})
        self.assert_no_trade(r)

    def test_naive_utc_cutoff_blocked(self):
        r = self.get(t=ASOF.replace(tzinfo=None))
        self.assertEqual(r["state"], "LAB_INVALID_INPUT")
        self.assert_no_trade(r)

    def test_invalid_nonfinite_prices_blocked(self):
        for invalid in ("NaN", "Infinity", "oops", "1000000"):
            with self.subTest(p=invalid):
                q=dataset()
                q["USD"][1] = replace(q["USD"][1], futures_price_index=invalid)
                r=self.get(q)
                self.assertEqual(r["evidence_by_currency"]["USD"]["status"], "CLAIMS_INVALID_OR_UNAVAILABLE")
                self.assert_no_trade(r)

    def test_changing_reference_month_between_vintages_blocked(self):
        q = dataset()
        q["USD"][1] = replace(q["USD"][1], reference_start_month="2026-12")
        r = self.get(q)
        self.assertEqual(r["evidence_by_currency"]["USD"]["status"], "CLAIMS_INVALID_OR_UNAVAILABLE")
        self.assert_no_trade(r)

    def test_weekend_or_far_future_claim_does_not_create_signal(self):
        q = dataset()
        r = self.get(q, t=datetime(2030,1,1,tzinfo=UTC))
        self.assert_no_trade(r)


if __name__ == "__main__":
    unittest.main()