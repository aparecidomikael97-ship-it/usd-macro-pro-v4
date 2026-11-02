"""Synthetic + actual legacy-cache tests, never certification of real FX bias."""
import copy
import json
import unittest
from datetime import datetime, timedelta, timezone
from math import exp, log
from pathlib import Path

from atlasquant_fx_universe import CURRENCIES, OFFICIAL_PAIRS, split_pair
from atlasquant_trader_fx_7usd_expost_lab import describe_7usd_legs_expost_lab, PAIRS

AT = datetime(2026, 11, 2, 16, tzinfo=timezone.utc)
START = "2026-10-29T00:00:00+00:00"
END = "2026-10-30T00:00:00+00:00"
LEGACY = Path(__file__).parent / "dados" / "autopilot_daily_cache_v107.json"


def fixture(factors=None):
    latent = {c: 0.0 for c in CURRENCIES}
    latent.update(factors or {"USD": .008, "EUR": .004, "JPY": -.010})
    fx = {}
    for pair in PAIRS:
        base, quote = split_pair(pair)
        p0 = 100.0
        p1 = p0 * exp(latent[base] - latent[quote])
        rows = []
        for when, price in ((START, p0), (END, p1)):
            rows.append({"datetime": when, "open": price,
                         "high": price * 1.01, "low": price * .99,
                         "close": price})
        fx[pair] = {"updated_at": "2026-10-30T01:00:00+00:00",
                    "records": rows}
    return {"updated_at": "2026-10-30T02:00:00+00:00", "pairs": fx}


def describe(data=None, *, start=START, end=END, at=AT):
    return describe_7usd_legs_expost_lab(
        fixture() if data is None else data,
        start_utc=start, end_utc=end, at=at)


class ExpostSevenLegTests(unittest.TestCase):
    def test_g8_factors_center_and_count_seven_vs_21(self):
        out = describe()
        self.assertEqual(out["state"], "LAB_EXPOST_UNVERIFIED_DESCRIPTIVE")
        self.assertEqual(len(out["relative_currency_moves_bp"]), 8)
        self.assertAlmostEqual(sum(out["relative_currency_moves_bp"].values()), 0, places=4)
        self.assertEqual(out["legacy_usd_leg_series"], 7)
        self.assertEqual(out["algebraically_implied_pairs"], 21)
        self.assertEqual(out["independently_verified_market_quotes"], 0)
        self.assertEqual(len(out["pair_views"]), 28)

    def test_usd_jpy_base_quote_returns_positive(self):
        out = describe()
        self.assertAlmostEqual(out["pair_views"]["USD/JPY"]["change_bp"], 180, places=3)
        self.assertEqual(out["pair_views"]["USD/JPY"]["classification"],
                         "OBSERVED_LEG_UNVERIFIED_CACHE")

    def test_eur_usd_base_quote_returns_negative(self):
        out = describe()
        self.assertAlmostEqual(out["pair_views"]["EUR/USD"]["change_bp"], -40, places=3)
        self.assertEqual(out["pair_views"]["EUR/USD"]["classification"],
                         "OBSERVED_LEG_UNVERIFIED_CACHE")

    def test_eur_jpy_cross_is_algebraically_implied_not_observed(self):
        out = describe()
        self.assertAlmostEqual(out["pair_views"]["EUR/JPY"]["change_bp"], 140, places=3)
        self.assertEqual(out["pair_views"]["EUR/JPY"]["classification"],
                         "IMPLIED_ALGEBRAIC_NOT_INDEPENDENT")
        self.assertFalse(out["pair_views"]["EUR/JPY"]["observed_independently"])
        self.assertFalse(out["pair_views"]["EUR/JPY"]["historically_available_at_bar_time_verified"])

    def test_mathematical_parity_with_seven_usd_legs(self):
        out = describe()
        for pair in PAIRS:
            self.assertAlmostEqual(
                out["pair_views"][pair]["change_bp"],
                out["relative_currency_moves_bp"][split_pair(pair)[0]] -
                out["relative_currency_moves_bp"][split_pair(pair)[1]],
                places=3)

    def test_derived_returns_respect_all_28_canonical_pair_orientations(self):
        out = describe()
        self.assertEqual(set(out["pair_views"]), set(OFFICIAL_PAIRS))
        for pair in OFFICIAL_PAIRS:
            a, b = split_pair(pair)
            expected = (out["relative_currency_moves_bp"][a] -
                        out["relative_currency_moves_bp"][b])
            self.assertAlmostEqual(out["pair_views"][pair]["change_bp"], expected, places=3)

    def test_reversed_latent_returns_reverse_relative_ranking(self):
        x = describe(fixture({"USD": -.010, "EUR": -.002, "JPY": .014}))
        self.assertLess(x["relative_currency_moves_bp"]["USD"],
                        x["relative_currency_moves_bp"]["JPY"])
        self.assertLess(x["pair_views"]["USD/JPY"]["change_bp"], 0)

    def test_no_market_forecast_accuracy_or_order_permission(self):
        out = describe()
        for key in ("daily_bias_validated", "weekly_bias_validated",
                    "monthly_bias_validated", "historical_oos_proven",
                    "market_data_verified", "trading_enabled",
                    "worker_enabled", "scheduler_enabled",
                    "bar_labels_are_attested_close_times",
                    "historical_price_availability_verified"):
            self.assertFalse(out[key], key)
        self.assertNotIn("top10", out)
        self.assertNotIn("accuracy_pct", out)

    def test_actual_legacy_cache_is_only_expost_not_certified(self):
        data = json.loads(LEGACY.read_text(encoding="utf-8"))
        first, later = (data["pairs"]["EUR/USD"]["records"][n]["datetime"]
                        for n in (0, 2))
        out = describe(data, start=first, end=later)
        self.assertEqual(out["state"], "LAB_EXPOST_UNVERIFIED_DESCRIPTIVE")
        self.assertEqual(out["bars_per_leg"], 320)
        self.assertEqual(out["weekend_bar_labels_flagged"], 581)
        self.assertIn("UNVERIFIED_WEEKEND_SESSION_MAPPING", out["audit_blockers"])
        self.assertFalse(out["historical_oos_proven"])

    def test_actual_cache_not_current_forecast_or_proven_origin(self):
        data = json.loads(LEGACY.read_text(encoding="utf-8"))
        start = data["pairs"]["EUR/USD"]["records"][0]["datetime"]
        end = data["pairs"]["EUR/USD"]["records"][-1]["datetime"]
        out = describe(data, start=start, end=end)
        self.assertEqual(out["candle_audit_state"], "QUARANTINED_UNVERIFIED_HISTORICAL_CACHE")
        self.assertIn("HISTORY_NOT_FRESH_FOR_DAILY_BIAS", out["audit_blockers"])
        self.assertFalse(out["daily_bias_validated"])

    def test_missing_one_leg_rejects_all_reconstruction(self):
        data = fixture()
        del data["pairs"]["USD/JPY"]
        out = describe(data)
        self.assertEqual(out["state"], "LAB_REJECTED_NO_EXPOST_VIEW")
        self.assertEqual(out["pair_views"], {})

    def test_extra_derived_pair_cannot_pretend_independent_leg(self):
        data = fixture()
        data["pairs"]["EUR/JPY"] = copy.deepcopy(data["pairs"]["USD/JPY"])
        self.assertEqual(describe(data)["state"], "LAB_REJECTED_NO_EXPOST_VIEW")

    def test_asynchronous_bar_dates_fail_instead_of_filling_forward(self):
        data = fixture()
        data["pairs"]["NZD/USD"]["records"][-1]["datetime"] = (
            "2026-10-30T01:00:00+00:00")
        self.assertEqual(describe(data)["state"], "LAB_REJECTED_NO_EXPOST_VIEW")

    def test_invalid_ohlc_high_low_rejects_even_if_close_is_good(self):
        data = fixture()
        data["pairs"]["USD/CHF"]["records"][0]["high"] = 50.0
        self.assertEqual(describe(data)["state"], "LAB_REJECTED_NO_EXPOST_VIEW")

    def test_zero_negative_nan_inf_and_boolean_close_fail(self):
        for bad in (0, -10, float("nan"), float("inf"), True, "100.0"):
            data = fixture()
            data["pairs"]["USD/CAD"]["records"][1]["close"] = bad
            self.assertEqual(describe(data)["state"], "LAB_REJECTED_NO_EXPOST_VIEW")

    def test_duplicate_and_out_of_order_records_fail(self):
        data = fixture()
        data["pairs"]["EUR/USD"]["records"].append(
            dict(data["pairs"]["EUR/USD"]["records"][1]))
        self.assertEqual(describe(data)["state"], "LAB_REJECTED_NO_EXPOST_VIEW")
        data = fixture()
        data["pairs"]["EUR/USD"]["records"] = list(reversed(
            data["pairs"]["EUR/USD"]["records"]))
        self.assertEqual(describe(data)["state"], "LAB_REJECTED_NO_EXPOST_VIEW")

    def test_missing_endpoint_bar_rejects(self):
        self.assertEqual(
            describe(start="2026-10-28T00:00:00+00:00")["state"],
            "LAB_REJECTED_NO_EXPOST_VIEW")

    def test_future_reversed_and_naive_windows_reject(self):
        for start, end in ((END, START), (START, START),
                           (START, "2026-11-04T00:00:00+00:00"),
                           ("2026-10-29T00:00:00", END)):
            self.assertEqual(describe(start=start, end=end)["state"],
                             "LAB_REJECTED_NO_EXPOST_VIEW")

    def test_absent_or_malformed_payload_fails_closed(self):
        for candidate in (None, {}, {"pairs": None}, {"pairs": []}):
            self.assertEqual(describe(candidate)["state"], "LAB_REJECTED_NO_EXPOST_VIEW")

    def test_self_declared_license_cannot_switch_trading_flags(self):
        data = fixture()
        data.update({"source_verified": True, "commercial_license_verified": True,
                     "point_in_time_proven": True, "state": "LIVE"})
        out = describe(data)
        self.assertEqual(out["state"], "LAB_EXPOST_UNVERIFIED_DESCRIPTIVE")
        self.assertFalse(out["market_data_verified"])
        self.assertFalse(out["trading_enabled"])

    def test_requires_aware_evaluation_instant(self):
        with self.assertRaises(ValueError):
            describe(at=datetime(2026, 11, 2, 16))


if __name__ == "__main__":
    unittest.main()
