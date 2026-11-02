"""Audits the actual repository cache, without treating it as verified FX."""
import copy
import json
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from atlasquant_trader_fx_legacy_cache_audit_lab import (
    USD_LEGS, audit_legacy_fx_daily_cache_lab,
)

NOW = datetime(2026, 11, 2, 16, tzinfo=timezone.utc)
FILE = Path(__file__).parent / "dados" / "autopilot_daily_cache_v107.json"


def legacy():
    return json.loads(FILE.read_text(encoding="utf-8"))


def sample():
    instant = "2026-10-30T00:00:00+00:00"
    update = "2026-10-30T01:00:00+00:00"
    record = {"datetime": instant, "open": 1.0, "high": 1.02,
              "low": 0.98, "close": 1.01}
    return {"updated_at": update,
            "pairs": {key: {"updated_at": update, "cache_day": "2026-10-30",
                            "records": [dict(record)]} for key in USD_LEGS}}


class LegacyCacheAuditTests(unittest.TestCase):
    def audit(self, data):
        return audit_legacy_fx_daily_cache_lab(data, at=NOW)

    def test_existing_repo_cache_is_flagged_not_claimed_certified(self):
        self.assertTrue(FILE.is_file(), "Expected existing legacy cache to exist")
        out = self.audit(legacy())
        self.assertEqual(out["state"], "QUARANTINED_UNVERIFIED_HISTORICAL_CACHE")
        self.assertEqual(out["covered_pairs"], 7)
        self.assertEqual(out["present_usd_legs"], 7)
        self.assertEqual(out["total_candles"], 2240)
        self.assertEqual(out["weekend_dated_bars"], 581)
        self.assertEqual(len(out["missing_28_pairs"]), 21)
        self.assertEqual(out["latest_candle_utc"], "2026-09-17T00:00:00+00:00")
        self.assertTrue(out["aligned_candle_dates"])
        self.assertFalse(out["daily_bias_ready"])
        self.assertFalse(out["historical_oos_ready"])

    def test_actual_cache_reports_weekend_bar_findings_for_every_leg(self):
        out = self.audit(legacy())
        self.assertIn("UNVERIFIED_WEEKEND_SESSION_MAPPING", out["blockers"])
        self.assertIn("HISTORY_NOT_FRESH_FOR_DAILY_BIAS", out["blockers"])
        for pair in USD_LEGS:
            self.assertEqual(out["pairs"][pair]["weekend_dated_bars"], 83)
            self.assertTrue(out["pairs"][pair]["structurally_valid"])

    def test_cache_has_no_claimed_market_or_license_validation(self):
        out = self.audit(sample())
        self.assertFalse(out["provider_identity_attested"])
        self.assertFalse(out["license_attested"])
        self.assertFalse(out["point_in_time_capture_attested"])
        self.assertFalse(out["historical_oos_ready"])
        self.assertFalse(out["real_accuracy_publishable"])
        self.assertFalse(out["derive_missing_crosses_as_real"])
        self.assertFalse(out["trade_authorized"])
        self.assertFalse(out["worker_enabled"])
        self.assertFalse(out["scheduler_enabled"])

    def test_no_weekend_fixture_still_does_not_self_certify_provenance(self):
        out = self.audit(sample())
        self.assertEqual(out["weekend_dated_bars"], 0)
        self.assertNotIn("UNVERIFIED_WEEKEND_SESSION_MAPPING", out["blockers"])
        self.assertIn("PROVIDER_ORIGIN_NOT_INDEPENDENTLY_VERIFIED", out["blockers"])
        self.assertFalse(out["daily_bias_ready"])

    def test_cannot_forge_market_proof_by_self_claimed_fields(self):
        inp = sample()
        inp["provider_verified"] = True
        inp["license_verified"] = True
        inp["capture_attested"] = True
        out = self.audit(inp)
        self.assertFalse(out["provider_identity_attested"])
        self.assertFalse(out["historical_oos_ready"])

    def test_missing_leg_blocks_7_leg_coverage(self):
        inp = sample()
        del inp["pairs"]["USD/JPY"]
        out = self.audit(inp)
        self.assertEqual(out["present_usd_legs"], 6)
        self.assertIn("MISSING_G8_USD_LEGS", out["blockers"])

    def test_extra_inverse_pair_not_treated_as_28_real_crosses(self):
        inp = sample()
        inp["pairs"]["JPY/USD"] = copy.deepcopy(inp["pairs"]["USD/JPY"])
        out = self.audit(inp)
        self.assertIn("UNEXPECTED_SYMBOLS", out["blockers"])
        self.assertEqual(out["covered_pairs"], 7)

    def test_nonfinite_boolean_zero_and_negative_prices_rejected(self):
        for value in (False, float("nan"), float("inf"), 0, -1, "1.0"):
            inp = sample()
            inp["pairs"]["USD/JPY"]["records"][0]["close"] = value
            out = self.audit(inp)
            self.assertIn("BAD_TIMESTAMP_OR_PRICE", out["pairs"]["USD/JPY"]["audit_findings"])

    def test_invalid_ohlc_high_low_is_caught(self):
        inp = sample()
        inp["pairs"]["USD/CHF"]["records"][0]["high"] = 0.5
        out = self.audit(inp)
        self.assertIn("BAD_OHLC_RANGE", out["pairs"]["USD/CHF"]["audit_findings"])

    def test_naive_and_future_candle_timestamps_rejected(self):
        inp = sample()
        inp["pairs"]["USD/CAD"]["records"][0]["datetime"] = "2026-10-30T00:00:00"
        out = self.audit(inp)
        self.assertIn("BAD_TIMESTAMP_OR_PRICE", out["pairs"]["USD/CAD"]["audit_findings"])
        inp = sample()
        inp["pairs"]["USD/CAD"]["records"][0]["datetime"] = (NOW + timedelta(days=1)).isoformat()
        out = self.audit(inp)
        self.assertIn("FUTURE_CANDLE", out["pairs"]["USD/CAD"]["audit_findings"])

    def test_duplicate_or_out_of_order_candles_are_blocked(self):
        inp = sample()
        inp["pairs"]["EUR/USD"]["records"].append(dict(inp["pairs"]["EUR/USD"]["records"][0]))
        out = self.audit(inp)
        self.assertIn("DUPLICATE_OR_UNORDERED_CANDLE", out["pairs"]["EUR/USD"]["audit_findings"])

    def test_misaligned_candle_dates_across_usd_legs_detected(self):
        inp = sample()
        new = inp["pairs"]["NZD/USD"]["records"][0]
        new["datetime"] = "2026-10-29T00:00:00+00:00"
        out = self.audit(inp)
        self.assertFalse(out["aligned_candle_dates"])
        self.assertIn("CROSS_PAIR_CALENDAR_MISMATCH", out["blockers"])

    def test_cache_clock_before_candle_flags_pair_and_global(self):
        inp = sample()
        inp["pairs"]["USD/JPY"]["updated_at"] = "2026-10-20T00:00:00+00:00"
        inp["updated_at"] = "2026-10-20T00:00:00+00:00"
        out = self.audit(inp)
        self.assertIn("INVALID_CACHE_UPDATE_CLOCK", out["pairs"]["USD/JPY"]["audit_findings"])
        self.assertIn("INVALID_GLOBAL_CACHE_CLOCK", out["blockers"])

    def test_malformed_payload_fails_closed_and_no_crash(self):
        for inp in (None, {}, {"pairs": None}, {"pairs": {"EUR/USD": None}}):
            out = self.audit(inp)
            self.assertEqual(out["state"], "QUARANTINED_UNVERIFIED_HISTORICAL_CACHE")
            self.assertFalse(out["historical_oos_ready"])

    def test_audit_requires_timezone_aware_instant(self):
        with self.assertRaises(ValueError):
            audit_legacy_fx_daily_cache_lab(sample(), at=datetime(2026, 11, 2))


if __name__ == "__main__":
    unittest.main()
