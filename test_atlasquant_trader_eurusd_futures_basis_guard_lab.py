"""All futures fixtures are synthetic and are not market-source attestations."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import unittest

from atlasquant_trader_eurusd_futures_basis_guard_lab import (
    PRODUCTS, RateFuturesQuoteClaim,
    RESEARCH_VISIBLE_FROM_UTC,
    inspect_eurusd_futures_basis_guard_lab as inspect,
)

UTC = timezone.utc
OLD = datetime(2026, 11, 11, 16, tzinfo=UTC)
NEW = datetime(2026, 11, 13, 16, tzinfo=UTC)
AS_OF = datetime(2026, 11, 14, 18, tzinfo=UTC)


def sample(currency, *, first="95", second="94.8", volume=20, month="2027-02"):
    return [
        RateFuturesQuoteClaim(currency, PRODUCTS[currency]["code"], month,
                              OLD, OLD + timedelta(minutes=10), first, volume, "a" * 64),
        RateFuturesQuoteClaim(currency, PRODUCTS[currency]["code"], month,
                              NEW, NEW + timedelta(minutes=10), second, volume, "b" * 64),
    ]


def dataset():
    return {"USD": sample("USD"), "EUR": sample("EUR", first="97.5", second="97.4")}


class EurusdFuturesBasisGuardTests(unittest.TestCase):
    def run_case(self, quotes=None, at=AS_OF):
        return inspect(claims_by_currency=dataset() if quotes is None else quotes, as_of_utc=at)

    def assert_no_go(self, report):
        self.assertEqual(report["operational_bias"], "AGUARDAR")
        for f in ("publisher_bytes_independently_archived", "licensed_data_redistribution_verified",
                  "original_publication_timestamps_independently_attested",
                  "cross_currency_rate_basis_normalized", "market_data_authenticated",
                  "usable_as_policy_expectations_vintage", "trade_authorized", "publishable",
                  "worker_enabled", "scheduler_enabled"):
            self.assertFalse(report[f], f)
        for f in ("eurusd_normalized_differential_change_bps", "eurusd_directional_bias",
                  "calibrated_direction_probability", "fx_bias"):
            self.assertIsNone(report[f], f)
        self.assertTrue(report["underlying_basis_different"])
        self.assertEqual((report["http_requests"], report["file_writes"], report["new_cost_brl"]),
                         (0, 0, 0))

    def test_both_individual_futures_moves_are_not_cross_currency_policy_signal(self):
        r = self.run_case()
        self.assertEqual(r["state"], "LAB_FUTURES_BASIS_UNNORMALIZED_NO_GO")
        self.assertEqual(set(r["quote_rows"]), {"USD", "EUR"})
        self.assertEqual(r["quote_rows"]["USD"]["index_implied_rate_change_bps_claim"], "20.0")
        self.assertEqual(r["quote_rows"]["EUR"]["index_implied_rate_change_bps_claim"], "10.0")
        self.assertNotEqual(r["quote_rows"]["USD"]["contract_underlying"],
                            r["quote_rows"]["EUR"]["contract_underlying"])
        self.assert_no_go(r)

    def test_same_currency_wrong_product_code_refused(self):
        d = dataset()
        d["EUR"] = [replace(x, product_code="ZQ") for x in d["EUR"]]
        r = self.run_case(d)
        self.assertEqual(r["quote_rows"]["EUR"]["status"], "FUTURES_QUOTE_EVIDENCE_UNAVAILABLE")
        self.assert_no_go(r)

    def test_no_volume_must_not_be_called_trade_supported_price(self):
        for volume in (0, -1, True, 1.2):
            with self.subTest(volume=volume):
                d = dataset()
                d["EUR"] = sample("EUR", volume=volume)
                r = self.run_case(d)
                self.assertEqual(r["quote_rows"]["EUR"]["status"], "FUTURES_QUOTE_EVIDENCE_UNAVAILABLE")
                self.assert_no_go(r)

    def test_contract_rolling_between_vintages_cannot_be_delta(self):
        d = dataset()
        d["USD"][1] = replace(d["USD"][1], delivery_month="2027-03")
        r = self.run_case(d)
        self.assertEqual(r["quote_rows"]["USD"]["status"], "FUTURES_QUOTE_EVIDENCE_UNAVAILABLE")
        self.assert_no_go(r)

    def test_clearly_expired_delivery_month_cannot_masquerade_as_future(self):
        d = dataset()
        d["USD"] = sample("USD", month="2026-10")
        r = self.run_case(d)
        self.assertEqual(r["quote_rows"]["USD"]["status"], "FUTURES_QUOTE_EVIDENCE_UNAVAILABLE")
        self.assert_no_go(r)

    def test_future_publication_claim_does_not_enter_asof(self):
        d = dataset()
        d["EUR"][1] = replace(d["EUR"][1], published_at_utc=AS_OF + timedelta(minutes=1),
                              captured_at_utc=AS_OF + timedelta(minutes=2))
        r = self.run_case(d)
        self.assertEqual(r["quote_rows"]["EUR"]["status"], "FUTURES_QUOTE_EVIDENCE_UNAVAILABLE")
        self.assert_no_go(r)

    def test_stale_capture_or_same_hash_not_independent_snapshot(self):
        for mutation in ({"captured_at_utc": NEW + timedelta(hours=25)},
                         {"source_sha256_claim": "a" * 64},
                         {"futures_price_index": "NaN"}):
            d = dataset()
            d["USD"][1] = replace(d["USD"][1], **mutation)
            r = self.run_case(d)
            self.assertEqual(r["quote_rows"]["USD"]["status"], "FUTURES_QUOTE_EVIDENCE_UNAVAILABLE")
            self.assert_no_go(r)

    def test_research_discovery_is_not_backfilled_into_prior_asof(self):
        r = self.run_case(at=RESEARCH_VISIBLE_FROM_UTC - timedelta(seconds=1))
        self.assertEqual(r["state"], "LAB_RESEARCH_NOT_VISIBLE_AS_OF")
        self.assertEqual(r["quote_rows"], {})
        self.assert_no_go(r)

    def test_missing_currency_or_naive_clock_fails_closed(self):
        for quotes, at in (({"USD": sample("USD")}, AS_OF),
                           (dataset(), AS_OF.replace(tzinfo=None)),
                           (dataset(), None)):
            r = self.run_case(quotes, at)
            self.assertEqual(r["state"], "LAB_INVALID_INPUT")
            self.assert_no_go(r)

    def test_far_future_asof_does_not_make_old_quotes_current(self):
        r = self.run_case(at=datetime(2026, 12, 1, tzinfo=UTC))
        self.assertEqual(r["quote_rows"]["EUR"]["status"], "FUTURES_QUOTE_EVIDENCE_UNAVAILABLE")
        self.assert_no_go(r)


if __name__ == "__main__":
    unittest.main()
