"""Synthetic contract checks for UNTRUSTED 28-pair quote intake; no trading."""
import unittest
from datetime import datetime, timedelta, timezone
from math import exp

from atlasquant_fx_universe import CURRENCIES, OFFICIAL_PAIRS, split_pair
from atlasquant_trader_fx_quote_intake_lab import (
    SCHEMA, audit_fx_quote_intake_lab,
)

AT = datetime(2026, 11, 2, 15, tzinfo=timezone.utc)
SID = "research-lab-source"
URL = "https://lab.example.invalid/archive"
FACTOR = {"USD": 65.0, "JPY": -70.0, "EUR": 35.0, "GBP": 5.0}


def book(horizon="D1"):
    days_ago = {"D1": 0, "W1": 3, "MN1": 5}[horizon]
    length = {"D1": 1, "W1": 7, "MN1": 30}[horizon]
    end = AT - timedelta(days=days_ago, hours=3)
    start = end - timedelta(days=length)
    captured_start = start + timedelta(minutes=15)
    captured_end = end + timedelta(minutes=15)
    observed = end + timedelta(minutes=25)
    pairs = {}
    for pair in OFFICIAL_PAIRS:
        a, b = split_pair(pair)
        pairs[pair] = {
            "source_id": SID, "start": 100.0,
            "end": 100.0 * exp((FACTOR.get(a, 0.0) -
                                FACTOR.get(b, 0.0)) / 10000),
            "start_at_utc": start.isoformat(),
            "end_at_utc": end.isoformat(),
            "captured_start_at_utc": captured_start.isoformat(),
            "captured_end_at_utc": captured_end.isoformat(),
        }
    return {
        "state": "LAB_UNVERIFIED_QUOTE_BOOK",
        "data_kind": "UNVERIFIED_FX_SPOT_CANDIDATE",
        "source_id": SID, "source_url": URL,
        "price_kind": "SPOT_MID_UNVERIFIED",
        "as_of_utc": observed.isoformat(),
        "period_end": end.date().isoformat(),
        "pairs": pairs,
    }


def books():
    return {h: book(h) for h in ("D1", "W1", "MN1")}


def audit(v=None):
    return audit_fx_quote_intake_lab(books() if v is None else v, at=AT)


class FxQuoteIntakeLabTests(unittest.TestCase):
    def test_three_horizons_28_pairs_each_structurally_complete(self):
        r = audit()
        self.assertEqual(r["schema"], SCHEMA)
        self.assertEqual(r["state"], "LAB_THREE_HORIZONS_STRUCTURALLY_COMPLETE_UNTRUSTED")
        self.assertEqual(r["required_pairs"], 28)
        self.assertEqual(r["required_currencies"], 8)
        for h in ("D1", "W1", "MN1"):
            self.assertEqual(r["horizon_checks"][h]["coverage"], 28)
            self.assertLess(r["horizon_checks"][h]["triangular_residual_bp"], 0.00001)

    def test_quote_reconstruction_does_not_admit_any_real_bias(self):
        r = audit()
        self.assertIsNone(r["actual_currency_strength"])
        self.assertIsNone(r["real_bias_28_pairs"])
        self.assertIsNone(r["daily_ui_contract"])
        for key in ("independent_capture_verified", "provider_license_verified",
                    "market_quotes_verified", "oos_validated", "can_feed_live_radar",
                    "can_feed_real_oos", "trade_authorized", "worker_enabled",
                    "scheduler_enabled"):
            self.assertFalse(r[key], key)

    def test_missing_weekly_quarantines_even_valid_daily_and_monthly(self):
        d = books()
        del d["W1"]
        r = audit(d)
        self.assertEqual(r["state"], "LAB_QUOTE_INTAKE_INCOMPLETE_QUARANTINED")
        self.assertEqual(r["horizon_checks"]["W1"]["state"], "QUARANTINED")
        self.assertEqual(r["horizon_checks"]["D1"]["coverage"], 28)

    def test_missing_monthly_does_not_forge_context(self):
        d = books()
        del d["MN1"]
        self.assertIn("Missing MN1", audit(d)["horizon_checks"]["MN1"]["reason"])

    def test_unexpected_horizon_is_denied_without_partial_admission(self):
        d = books()
        d["M15"] = d["D1"]
        r = audit(d)
        self.assertEqual(r["state"], "LAB_QUOTE_INTAKE_INCOMPLETE_QUARANTINED")
        self.assertEqual(r["horizon_checks"]["D1"]["state"], "QUARANTINED")

    def test_missing_fx_leg_and_noncanonical_inverse_are_rejected(self):
        for key, inverse in (("EUR/USD", False), ("JPY/USD", True)):
            d = books()
            if inverse:
                d["D1"]["pairs"][key] = d["D1"]["pairs"]["USD/JPY"].copy()
            else:
                del d["D1"]["pairs"][key]
            self.assertEqual(audit(d)["horizon_checks"]["D1"]["state"], "QUARANTINED")

    def test_pair_must_not_use_different_provider(self):
        d = books()
        d["D1"]["pairs"]["EUR/USD"]["source_id"] = "different-provider"
        self.assertIn("source identity", audit(d)["horizon_checks"]["D1"]["reason"])

    def test_quote_book_requires_an_explicit_unverified_state(self):
        for k, value in (("state", "REAL_VERIFIED"),
                         ("data_kind", "VALIDATED_DAILY"),
                         ("price_kind", "TRADABLE_BID")):
            d = books()
            d["D1"][k] = value
            self.assertEqual(audit(d)["horizon_checks"]["D1"]["state"], "QUARANTINED")

    def test_unverified_source_url_must_be_https_with_no_credentials(self):
        for url in ("http://lab.example.invalid/data",
                    "https://user:pass@lab.example.invalid/data",
                    "https://lab.example.invalid/data#fragment",
                    "not-a-url", "https://lab.example.invalid:1234/archive"):
            d = books()
            d["D1"]["source_url"] = url
            self.assertEqual(audit(d)["horizon_checks"]["D1"]["state"], "QUARANTINED", url)

    def test_malformed_port_does_not_crash_evidence_audit(self):
        d = books()
        d["D1"]["source_url"] = "https://lab.example.invalid:notaport/archive"
        self.assertEqual(audit(d)["horizon_checks"]["D1"]["state"], "QUARANTINED")

    def test_no_price_string_boolean_nan_inf_zero_or_negative(self):
        for value in ("100", True, float("inf"), float("nan"), 0, -1):
            d = books()
            d["D1"]["pairs"]["EUR/USD"]["end"] = value
            self.assertEqual(audit(d)["horizon_checks"]["D1"]["state"], "QUARANTINED")

    def test_quote_timestamp_without_timezone_fails_closed(self):
        d = books()
        d["D1"]["pairs"]["EUR/USD"]["end_at_utc"] = "2026-11-02T12:00:00"
        self.assertEqual(audit(d)["horizon_checks"]["D1"]["state"], "QUARANTINED")

    def test_source_timestamp_in_future_fails_closed(self):
        d = books()
        d["D1"]["as_of_utc"] = (AT + timedelta(seconds=1)).isoformat()
        self.assertEqual(audit(d)["horizon_checks"]["D1"]["state"], "QUARANTINED")

    def test_quote_capture_before_price_timestamp_refused(self):
        d = books()
        d["D1"]["pairs"]["USD/JPY"]["captured_end_at_utc"] = (
            AT - timedelta(hours=4)).isoformat()
        self.assertEqual(audit(d)["horizon_checks"]["D1"]["state"], "QUARANTINED")

    def test_stale_daily_snapshot_not_recycled_for_todays_bias(self):
        d = books()
        d["D1"]["as_of_utc"] = (AT - timedelta(days=6)).isoformat()
        self.assertEqual(audit(d)["horizon_checks"]["D1"]["state"], "QUARANTINED")

    def test_asynchronous_sample_end_price_time_rejected(self):
        d = books()
        d["D1"]["pairs"]["EUR/USD"]["end_at_utc"] = (
            AT - timedelta(hours=2,minutes=59)).isoformat()
        self.assertIn("not sampled on identical", audit(d)["horizon_checks"]["D1"]["reason"])

    def test_capture_skew_over_sixty_seconds_quarantined(self):
        d = books()
        d["D1"]["pairs"]["GBP/JPY"]["captured_end_at_utc"] = (
            AT - timedelta(hours=2,minutes=43)).isoformat()
        self.assertIn("not synchronized", audit(d)["horizon_checks"]["D1"]["reason"])

    def test_capture_skew_exact_sixty_seconds_is_allowed(self):
        d = books()
        d["D1"]["pairs"]["GBP/JPY"]["captured_end_at_utc"] = (
            AT - timedelta(hours=2,minutes=44)).isoformat()
        self.assertEqual(audit(d)["horizon_checks"]["D1"]["state"],
                         "LAB_STRUCTURAL_CANDIDATE_UNVERIFIED")

    def test_triangular_arbitrage_inconsistent_graph_rejected(self):
        d = books()
        d["D1"]["pairs"]["EUR/USD"]["end"] *= exp(0.02)
        self.assertIn("Triangular", audit(d)["horizon_checks"]["D1"]["reason"])

    def test_extreme_but_consistent_latent_moves_not_forced_into_bias(self):
        d = books()
        for h in ("D1", "W1", "MN1"):
            for pair in OFFICIAL_PAIRS:
                d[h]["pairs"][pair]["end"] = 200.0
        self.assertEqual(audit(d)["state"], "LAB_QUOTE_INTAKE_INCOMPLETE_QUARANTINED")

    def test_wrong_end_period_date_rejected(self):
        d = books()
        d["D1"]["period_end"] = "2026-11-03"
        self.assertEqual(audit(d)["horizon_checks"]["D1"]["state"], "QUARANTINED")

    def test_wrong_window_or_timestamp_order_rejected(self):
        d = books()
        d["D1"]["pairs"]["USD/JPY"]["start_at_utc"] = (
            AT - timedelta(hours=4)).isoformat()
        self.assertEqual(audit(d)["horizon_checks"]["D1"]["state"], "QUARANTINED")
        d = books()
        for pair in OFFICIAL_PAIRS:
            d["D1"]["pairs"][pair]["start_at_utc"] = (
                AT - timedelta(days=5,hours=3)).isoformat()
        self.assertEqual(audit(d)["horizon_checks"]["D1"]["state"], "QUARANTINED")

    def test_extra_hindsight_field_in_quote_or_book_is_rejected(self):
        d = books()
        d["D1"]["pairs"]["EUR/USD"]["future_return"] = 0.15
        self.assertEqual(audit(d)["horizon_checks"]["D1"]["state"], "QUARANTINED")
        d = books()
        d["D1"]["future_bias"] = "BUY"
        self.assertEqual(audit(d)["horizon_checks"]["D1"]["state"], "QUARANTINED")

    def test_naive_audit_time_is_rejected(self):
        with self.assertRaises(ValueError):
            audit_fx_quote_intake_lab(books(), at=datetime(2026, 11, 2, 15))

    def test_no_input_produces_quarantine_not_fake_market_data(self):
        for missing in ({}, None, [], "foo"):
            r = audit_fx_quote_intake_lab(missing, at=AT)
            self.assertEqual(r["state"], "LAB_QUOTE_INTAKE_INCOMPLETE_QUARANTINED")
            self.assertFalse(r["can_feed_live_radar"])
            self.assertIsNone(r["real_bias_28_pairs"])

    def test_untrusted_book_does_not_modify_input(self):
        d = books()
        before = d["D1"]["pairs"]["EUR/USD"].copy()
        audit(d)
        self.assertEqual(d["D1"]["pairs"]["EUR/USD"], before)


if __name__ == "__main__":
    unittest.main()
