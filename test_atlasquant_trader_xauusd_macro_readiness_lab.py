"""Synthetic XAU/USD macro readiness checks; no MT5 or FRED queries."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import unittest

from atlasquant_instrument_registry import (
    FX_28, GOLD_REFERENCE, get_gold_reference, normalize_fx_symbol,
)
from atlasquant_trader_xauusd_macro_readiness_lab import (
    GoldDriverClaim, inspect_xauusd_macro_driver_readiness_lab as inspect,
)

UTC = timezone.utc
DECISION = datetime(2026, 11, 10, 12, 0, tzinfo=UTC)
EVAL = datetime(2026, 11, 10, 13, 0, tzinfo=UTC)


def receipt(driver, label, value, published, captured):
    defs = {
        "US_REAL_YIELD_10Y": ("FRED_DFII10", "PERCENT_ANNUAL", "D1"),
        "US_BROAD_DOLLAR": ("FRED_DTWEXBGS", "INDEX_JAN2006_100", "D1"),
        "XAUUSD_BROKER_PRICE": ("PEPPERSTONE_MT5_XAUUSD", "USD_PER_TROY_OUNCE", "M15"),
    }
    src, unit, freq = defs[driver]
    return GoldDriverClaim(driver=driver, source_id=src, unit=unit,
                           sampling=freq, observation_label=label,
                           value_claim=value,
                           published_at=datetime.fromisoformat(published.replace("Z", "+00:00")),
                           captured_at=datetime.fromisoformat(captured.replace("Z", "+00:00")),
                           original_sha256_claim="c" * 64)


def fixture():
    return [
        receipt("US_REAL_YIELD_10Y", "2026-11-05", "2.60",
                "2026-11-05T17:00:00Z", "2026-11-05T17:01:00Z"),
        receipt("US_REAL_YIELD_10Y", "2026-11-06", "2.63",
                "2026-11-06T17:00:00Z", "2026-11-06T17:01:00Z"),
        receipt("US_BROAD_DOLLAR", "2026-10-29", "121.73",
                "2026-11-02T18:00:00Z", "2026-11-02T18:01:00Z"),
        receipt("US_BROAD_DOLLAR", "2026-10-30", "121.66",
                "2026-11-02T18:00:00Z", "2026-11-02T18:01:00Z"),
        receipt("XAUUSD_BROKER_PRICE", "2026-11-10T11:15:00Z", "4000.00",
                "2026-11-10T11:30:00Z", "2026-11-10T11:31:00Z"),
        receipt("XAUUSD_BROKER_PRICE", "2026-11-10T11:30:00Z", "4001.00",
                "2026-11-10T11:45:00Z", "2026-11-10T11:46:00Z"),
    ]


def run(rows=None, *, instrument="XAU/USD", horizon="D1", decision=DECISION,
        evaluated=EVAL):
    return inspect(fixture() if rows is None else rows, instrument=instrument,
                   horizon=horizon, decision_at_utc=decision,
                   evaluated_at_utc=evaluated)


class XauUsdReadinessLabTests(unittest.TestCase):
    def no_go(self, result):
        for field in ("news_and_geopolitics_authenticated",
                      "macro_calendar_authenticated", "fred_series_responses_authenticated",
                      "pepperstone_xauusd_bars_authenticated", "broker_contract_spec_verified",
                      "source_clocks_independently_authenticated",
                      "historical_point_in_time_verified",
                      "driver_relationships_directionally_validated",
                      "trade_authorized", "publishable", "worker_enabled",
                      "scheduler_enabled"):
            self.assertIs(result[field], False, field)
        self.assertIs(result["separate_from_fx_28"], True)
        self.assertIsNone(result["xauusd_bias"])
        self.assertIsNone(result["score_0_to_10"])
        self.assertIsNone(result["calibrated_probability"])
        self.assertIsNone(result["validated_accuracy"])
        self.assertEqual(result["operational_bias"], "AGUARDAR")
        self.assertEqual((result["http_requests"], result["file_writes"],
                          result["new_cost_brl"]), (0, 0, 0))

    def blocked(self, value, reason):
        self.assertEqual(value["state"], "LAB_XAUUSD_DRIVER_READINESS_BLOCKED")
        self.assertEqual(value["reason"], reason)
        self.no_go(value)

    def test_gold_reference_distinct_from_all_28_fx_pairs(self):
        self.assertEqual(len(FX_28), 28)
        self.assertNotIn("XAUUSD", FX_28)
        self.assertEqual(GOLD_REFERENCE.canonical_id, "METAL:XAUUSD")
        self.assertEqual(get_gold_reference(" XAU/USD "), GOLD_REFERENCE)
        self.assertEqual(get_gold_reference("METAL:XAUUSD"), GOLD_REFERENCE)
        with self.assertRaises(ValueError):
            normalize_fx_symbol("XAU/USD")
        with self.assertRaises(ValueError):
            get_gold_reference("EUR/USD")

    def test_all_three_synthetic_claims_present_still_no_bias(self):
        r = run()
        self.assertEqual(r["state"], "LAB_XAUUSD_THREE_DRIVER_CLAIMS_PRESENT_UNATTESTED")
        self.assertEqual(r["claimed_complete_drivers"], 3)
        self.assertTrue(r["all_three_driver_claims_present"])
        self.assertEqual(r["missing_drivers"], [])
        self.assertEqual(set(r["driver_states"]), {
            "US_REAL_YIELD_10Y", "US_BROAD_DOLLAR", "XAUUSD_BROKER_PRICE"})
        for item in r["driver_states"].values():
            self.assertFalse(item["directional_contribution_allowed"])
            self.assertFalse(item["issuer_or_broker_authenticated"])
        self.no_go(r)

    def test_no_source_is_three_missing_and_zero_signal(self):
        r = run([])
        self.assertEqual(r["state"], "LAB_XAUUSD_DRIVER_CLAIMS_INCOMPLETE")
        self.assertEqual(r["claimed_complete_drivers"], 0)
        self.assertEqual(len(r["missing_drivers"]), 3)
        self.no_go(r)

    def test_only_real_yield_does_not_stand_in_for_gold_price(self):
        r = run(fixture()[:2])
        self.assertEqual(r["claimed_complete_drivers"], 1)
        self.assertIn("XAUUSD_BROKER_PRICE", r["missing_drivers"])
        self.no_go(r)

    def test_one_observation_is_not_a_trend(self):
        r = run(fixture()[:-1])
        self.assertEqual(r["claimed_complete_drivers"], 2)
        self.assertIn("XAUUSD_BROKER_PRICE", r["missing_drivers"])
        self.no_go(r)

    def test_wrong_fred_series_or_dxy_substitution_rejected(self):
        rows = fixture()
        rows[2] = replace(rows[2], source_id="ICE_DXY")
        self.blocked(run(rows), "UNSUPPORTED_SOURCE_UNIT_OR_HASH_CLAIM")

    def test_wrong_broker_price_unit_rejected(self):
        rows = fixture()
        rows[-1] = replace(rows[-1], unit="USD_PER_BARREL")
        self.blocked(run(rows), "UNSUPPORTED_SOURCE_UNIT_OR_HASH_CLAIM")

    def test_future_publication_or_capture_is_not_available_at_decision(self):
        rows = fixture()
        rows[-1] = replace(rows[-1], captured_at=DECISION + timedelta(seconds=1))
        self.blocked(run(rows), "FUTURE_OR_INVALID_OBSERVATION_RELEASE_CAPTURE_TIME")
        rows = fixture()
        rows[-1] = replace(rows[-1], published_at=DECISION + timedelta(minutes=1))
        self.blocked(run(rows), "FUTURE_OR_INVALID_OBSERVATION_RELEASE_CAPTURE_TIME")

    def test_gold_m15_cannot_be_published_before_candle_close(self):
        rows = fixture()
        rows[-1] = replace(rows[-1], published_at=datetime(2026, 11, 10, 11, 35, tzinfo=UTC))
        self.blocked(run(rows), "FUTURE_OR_INVALID_OBSERVATION_RELEASE_CAPTURE_TIME")

    def test_stale_gold_price_must_not_enable_research_readiness(self):
        rows = fixture()
        late_decision = DECISION + timedelta(hours=4)
        self.blocked(run(rows, decision=late_decision, evaluated=late_decision),
                     "CLAIMED_DRIVER_OBSERVATION_STALE_XAUUSD_BROKER_PRICE")

    def test_stale_broad_dollar_claim_rejected(self):
        rows = fixture()
        rows[2] = replace(rows[2], observation_label="2026-10-01")
        rows[3] = replace(rows[3], observation_label="2026-10-02")
        self.blocked(run(rows), "CLAIMED_DRIVER_OBSERVATION_STALE_US_BROAD_DOLLAR")

    def test_duplicate_observation_blocks_the_whole_gate(self):
        rows = fixture()
        rows[1] = rows[0]
        self.blocked(run(rows), "DUPLICATE_DRIVER_OBSERVATION")

    def test_nonfinite_or_wrong_price_claim_rejected(self):
        for bad in ("NaN", "-1", "4,000", "0"):
            rows = fixture()
            rows[-1] = replace(rows[-1], value_claim=bad)
            with self.subTest(value=bad):
                self.blocked(run(rows), "INVALID_DRIVER_VALUE_CLAIM")

    def test_negative_real_yield_is_a_valid_claim_but_no_direction(self):
        rows = fixture()
        rows[1] = replace(rows[1], value_claim="-0.25")
        r = run(rows)
        self.assertEqual(r["state"], "LAB_XAUUSD_THREE_DRIVER_CLAIMS_PRESENT_UNATTESTED")
        self.no_go(r)

    def test_invalid_source_clock_and_sha_rejected(self):
        rows = fixture()
        rows[0] = replace(rows[0], original_sha256_claim="bad")
        self.blocked(run(rows), "UNSUPPORTED_SOURCE_UNIT_OR_HASH_CLAIM")
        rows = fixture()
        rows[0] = replace(rows[0], published_at=rows[0].published_at.replace(tzinfo=None))
        self.blocked(run(rows), "FUTURE_OR_INVALID_OBSERVATION_RELEASE_CAPTURE_TIME")

    def test_invalid_instrument_horizon_and_eval_time_rejected(self):
        for kwargs in ({"instrument": "EUR/USD"}, {"horizon": "M15"},
                       {"decision": EVAL, "evaluated": DECISION}):
            with self.subTest(kwargs=kwargs):
                self.blocked(run(**kwargs), "INVALID_INSTRUMENT_HORIZON_OR_CLOCK")

    def test_input_list_not_modified(self):
        rows = fixture()
        before = list(rows)
        _ = run(rows)
        self.assertEqual(rows, before)


if __name__ == "__main__":
    unittest.main()
