"""Offline synthetic timezone cases for Twelve Data D1 market label safety."""
import json
import unittest
from datetime import datetime, timezone
from pathlib import Path

from atlasquant_trader_twelve_d1_time_lab import (
    audit_synthetic_twelve_d1_time_labels_lab,
    assess_synthetic_d1_availability_lab,
)

NOW = datetime(2026, 11, 2, 16, tzinfo=timezone.utc)
LEGACY = Path(__file__).parent / "dados" / "autopilot_daily_cache_v107.json"


def fixture(*, value="2026-01-10 00:00:00", zone="Australia/Sydney"):
    return {
        "state": "LAB_SYNTHETIC_TWELVE_D1", "interval": "1day",
        "asset_class": "forex", "requested_timezone": "UTC",
        "meta": {"exchange_timezone": zone, "symbol": "EUR/USD"},
        "values": [{"datetime": value}],
    }


def inspect(data, *, now=NOW):
    return audit_synthetic_twelve_d1_time_labels_lab(data, at=now)


class TwelveDailyTimeLabTests(unittest.TestCase):
    def test_sydney_summer_midnight_is_previous_day_13_utc(self):
        out = inspect(fixture())
        self.assertEqual(out["state"], "LAB_LOCAL_LABEL_CONVERSION_ONLY")
        self.assertEqual(
            out["utc_bar_open_labels"][0]["calculated_utc_bar_open_label"],
            "2026-01-09T13:00:00+00:00")
        self.assertFalse(out["requested_utc_controls_daily_timezone"])

    def test_sydney_winter_midnight_is_previous_day_14_utc(self):
        out = inspect(fixture(value="2026-07-10 00:00:00"))
        self.assertEqual(
            out["utc_bar_open_labels"][0]["calculated_utc_bar_open_label"],
            "2026-07-09T14:00:00+00:00")

    def test_request_timezone_utc_does_not_override_exchange_timezone(self):
        data = fixture()
        data["requested_timezone"] = "America/New_York"
        one = inspect(data)
        data["requested_timezone"] = "UTC"
        two = inspect(data)
        self.assertEqual(one["utc_bar_open_labels"], two["utc_bar_open_labels"])
        self.assertTrue(one["requested_timezone_ignored_for_daily"])

    def test_explicit_metadata_required_even_when_request_says_utc(self):
        data = fixture()
        del data["meta"]["exchange_timezone"]
        out = inspect(data)
        self.assertEqual(out["state"], "LAB_REJECTED_UNVERIFIED_D1_TIME_LABEL")
        self.assertFalse(out["can_feed_bias"])

    def test_bad_iana_zone_rejected(self):
        out = inspect(fixture(zone="Atlantis/Unknown"))
        self.assertEqual(out["state"], "LAB_REJECTED_UNVERIFIED_D1_TIME_LABEL")

    def test_ambiguous_new_york_fall_fold_is_rejected(self):
        # 2026-11-01 01:30 local is repeated when DST ends.
        out = inspect(fixture(value="2026-11-01 01:30:00",
                              zone="America/New_York"))
        self.assertEqual(out["state"], "LAB_REJECTED_UNVERIFIED_D1_TIME_LABEL")

    def test_nonexistent_new_york_spring_clock_is_rejected(self):
        # 2026-03-08 02:30 local never happened (DST spring-forward).
        out = inspect(fixture(value="2026-03-08 02:30:00",
                              zone="America/New_York"))
        self.assertEqual(out["state"], "LAB_REJECTED_UNVERIFIED_D1_TIME_LABEL")

    def test_a_naive_label_is_only_accepted_with_declared_exchange_zone(self):
        out = inspect(fixture(value="2026-01-10 00:00:00"))
        self.assertEqual(out["state"], "LAB_LOCAL_LABEL_CONVERSION_ONLY")
        self.assertFalse(out["bar_close_time_verified"])
        self.assertFalse(out["utc_bar_open_labels"][0]["price_available_at_this_label_verified"])

    def test_timezone_aware_input_label_not_silently_mixed(self):
        data = fixture(value="2026-01-10T00:00:00+00:00")
        self.assertEqual(inspect(data)["state"],
                         "LAB_REJECTED_UNVERIFIED_D1_TIME_LABEL")

    def test_daily_local_labels_must_be_strictly_ordered(self):
        data = fixture()
        data["values"].append({"datetime": "2026-01-09 00:00:00"})
        self.assertEqual(inspect(data)["state"],
                         "LAB_REJECTED_UNVERIFIED_D1_TIME_LABEL")
        data = fixture()
        data["values"].append({"datetime": "2026-01-10 00:00:00"})
        self.assertEqual(inspect(data)["state"],
                         "LAB_REJECTED_UNVERIFIED_D1_TIME_LABEL")

    def test_two_dates_across_dst_convert_with_distinct_offsets(self):
        data = fixture()
        data["values"] = [{"datetime": "2026-01-10 00:00:00"},
                          {"datetime": "2026-07-10 00:00:00"}]
        out = inspect(data)
        self.assertEqual(out["count"], 2)
        self.assertEqual(
            [v["calculated_utc_bar_open_label"] for v in out["utc_bar_open_labels"]],
            ["2026-01-09T13:00:00+00:00", "2026-07-09T14:00:00+00:00"])

    def test_future_label_must_be_rejected(self):
        out = inspect(fixture(value="2026-12-10 00:00:00"))
        self.assertEqual(out["state"], "LAB_REJECTED_UNVERIFIED_D1_TIME_LABEL")

    def test_wrong_asset_interval_and_state_do_not_pass(self):
        for field, value in (("state", "REAL_PROVIDER_OK"),
                             ("interval", "15min"), ("asset_class", "crypto")):
            data = fixture()
            data[field] = value
            self.assertEqual(inspect(data)["state"],
                             "LAB_REJECTED_UNVERIFIED_D1_TIME_LABEL")

    def test_existing_legacy_cache_cannot_restore_missing_source_meta(self):
        raw = json.loads(LEGACY.read_text(encoding="utf-8"))
        out = inspect(raw)
        self.assertEqual(out["state"], "LAB_REJECTED_UNVERIFIED_D1_TIME_LABEL")
        self.assertFalse(out["provider_response_independently_verified"])

    def test_cannot_self_attest_close_licensing_or_market_quality(self):
        data = fixture()
        data.update({"provider_verified": True, "market_verified": True,
                     "commercial_license_verified": True, "bar_closed": True})
        out = inspect(data)
        for key in ("bar_close_time_verified", "market_session_mapping_verified",
                    "provider_response_independently_verified", "can_feed_bias",
                    "can_feed_oos", "trade_authorized", "worker_enabled",
                    "scheduler_enabled"):
            self.assertFalse(out[key], key)

    def test_invalid_or_missing_payload_is_refused(self):
        for raw in (None, {}, {"state": "LAB_SYNTHETIC_TWELVE_D1"}, []):
            self.assertEqual(inspect(raw)["state"],
                             "LAB_REJECTED_UNVERIFIED_D1_TIME_LABEL")

    def test_d1_first_label_alone_never_supplies_a_closed_candle(self):
        data = fixture()
        out = assess_synthetic_d1_availability_lab(
            data, captured_at_utc="2026-01-10T13:10:00+00:00",
            forecast_issued_at_utc="2026-01-10T13:30:00+00:00", at=NOW)
        self.assertEqual(out["candidates"], [])
        self.assertEqual(len(out["pending_or_unproven_labels"]), 1)
        self.assertFalse(out["can_feed_real_oos"])

    def test_after_following_open_allows_only_noncertified_clock_hypothesis(self):
        data = fixture()
        data["values"].append({"datetime": "2026-01-11 00:00:00"})
        out = assess_synthetic_d1_availability_lab(
            data, captured_at_utc="2026-01-10T13:01:00+00:00",
            forecast_issued_at_utc="2026-01-10T13:02:00+00:00", at=NOW)
        self.assertEqual(out["state"], "LAB_CLOCK_HYPOTHESIS_NOT_ATTESTED")
        self.assertEqual(len(out["candidates"]), 1)
        self.assertEqual(len(out["pending_or_unproven_labels"]), 1)
        self.assertEqual(out["candidates"][0]["next_bar_open_utc"],
                         "2026-01-10T13:00:00+00:00")
        self.assertEqual(out["candidates"][0]["earliest_unverified_capture_at_utc"],
                         "2026-01-10T13:01:00+00:00")
        self.assertFalse(out["capture_integrity_verified"])
        self.assertFalse(out["can_feed_real_bias"])

    def test_capture_before_next_bar_open_cannot_assume_prior_close(self):
        data = fixture()
        data["values"].append({"datetime": "2026-01-11 00:00:00"})
        out = assess_synthetic_d1_availability_lab(
            data, captured_at_utc="2026-01-10T12:59:00+00:00",
            forecast_issued_at_utc="2026-01-10T13:10:00+00:00", at=NOW)
        self.assertEqual(out["candidates"], [])
        self.assertEqual(len(out["pending_or_unproven_labels"]), 2)

    def test_fraudulently_postdated_capture_cannot_backdate_to_open(self):
        data = fixture()
        data["values"].append({"datetime": "2026-01-11 00:00:00"})
        out = assess_synthetic_d1_availability_lab(
            data, captured_at_utc="2026-01-12T13:01:00+00:00",
            forecast_issued_at_utc="2026-01-12T13:02:00+00:00", at=NOW)
        self.assertEqual(out["candidates"][0]["earliest_unverified_capture_at_utc"],
                         "2026-01-12T13:01:00+00:00")
        self.assertFalse(out["capture_integrity_verified"])
        self.assertFalse(out["can_feed_real_oos"])

    def test_capture_later_than_forecast_is_rejected(self):
        out = assess_synthetic_d1_availability_lab(
            fixture(), captured_at_utc="2026-01-10T13:00:00+00:00",
            forecast_issued_at_utc="2026-01-10T12:00:00+00:00", at=NOW)
        self.assertEqual(out["state"], "LAB_D1_AVAILABILITY_NOT_PROVEN")

    def test_naive_capture_and_future_forecast_are_rejected(self):
        for cap, forecast in (
            ("2026-01-10T13:00:00", "2026-01-10T14:00:00+00:00"),
            ("2026-01-10T13:00:00+00:00", "2026-12-10T14:00:00+00:00"),
        ):
            out = assess_synthetic_d1_availability_lab(
                fixture(), captured_at_utc=cap,
                forecast_issued_at_utc=forecast, at=NOW)
            self.assertEqual(out["state"], "LAB_D1_AVAILABILITY_NOT_PROVEN")

    def test_missing_timezone_metadata_fails_before_availability(self):
        data = fixture()
        del data["meta"]["exchange_timezone"]
        out = assess_synthetic_d1_availability_lab(
            data, captured_at_utc="2026-01-10T13:00:00+00:00",
            forecast_issued_at_utc="2026-01-10T14:00:00+00:00", at=NOW)
        self.assertEqual(out["state"], "LAB_D1_AVAILABILITY_NOT_PROVEN")

    def test_legacy_cache_cannot_self_attest_historical_lookahead(self):
        data = json.loads(LEGACY.read_text(encoding="utf-8"))
        out = assess_synthetic_d1_availability_lab(
            data, captured_at_utc="2026-09-17T06:28:10+00:00",
            forecast_issued_at_utc="2026-09-17T07:00:00+00:00", at=NOW)
        self.assertEqual(out["state"], "LAB_D1_AVAILABILITY_NOT_PROVEN")
        self.assertFalse(out["can_feed_real_bias"])

    def test_naive_evaluation_instant_is_invalid(self):
        with self.assertRaises(ValueError):
            inspect(fixture(), now=datetime(2026, 11, 2, 16))


if __name__ == "__main__":
    unittest.main()
