"""Pre-registered October CPI model forecast is immutable, never market consensus."""
from datetime import datetime, timezone, timedelta
from pathlib import Path
import json
import unittest

from atlasquant_trader_us_oct2026_clevelandfed_forward_nowcast_lab import (
    PINNED_RECEIPT_SHA256,
    inspect_us_oct2026_clevelandfed_forward_nowcast_lab as inspect,
)

PATH = (Path(__file__).resolve().parent / "docs" / "continuidade"
        / "TRADER_US_OCT2026_CLEVELANDFED_FORWARD_NOWCAST_RECEIPT_20261106.json")
RECEIPT = PATH.read_bytes()


def at(month, day, hour=0, minute=0):
    return datetime(2026, month, day, hour, minute, tzinfo=timezone.utc)


class USOct2026ClevelandFedForwardNowcastTests(unittest.TestCase):
    def case(self, when=at(11, 8), receipt=RECEIPT):
        return inspect(receipt, as_of_utc=when)

    def assert_no_market_surprise_or_trade(self, r):
        self.assertEqual(r["operational_bias"], "AGUARDAR")
        self.assertIsNone(r["fx_bias"])
        self.assertIsNone(r["analyst_consensus_percent"])
        self.assertIsNone(r["release_surprise_percentage_points"])
        self.assertIsNone(r["model_error_percentage_points"])
        self.assertIsNone(r["first_bls_actual_headline_yoy_percent"])
        self.assertEqual(r["validated_forward_prediction_count"], 0)
        self.assertIsNone(r["validated_accuracy"])
        self.assertFalse(r["original_html_snapshot_archived"])
        self.assertFalse(r["exact_retrieval_instant_independently_attested"])
        self.assertEqual((r["http_requests"], r["new_cost_brl"]), (0, 0))
        for k in ("can_feed_live_radar", "trade_authorized", "publishable",
                  "worker_enabled", "scheduler_enabled"):
            self.assertFalse(r[k], k)

    def test_official_primary_page_number_precommitted_before_release(self):
        r = self.case()
        self.assertEqual(r["state"], "LAB_PRE_RELEASE_MODEL_FORECAST_CONTEXT_ONLY")
        self.assertEqual(r["pinned_receipt_sha256"], PINNED_RECEIPT_SHA256)
        self.assertEqual(r["research_calendar_date"], "2026-11-06")
        self.assertEqual(r["source_updated_calendar_date_not_capture_instant"], "2026-11-06")
        self.assertEqual(r["model_nowcast_percent_documentary_only"], 3.74)
        self.assertTrue(r["model_nowcast_visible_before_release"])
        self.assertEqual(r["first_bls_release_scheduled_utc"], "2026-11-10T13:30:00Z")
        self.assertEqual(r["forecast_class"], "STATISTICAL_MODEL_NOWCAST_NOT_ANALYST_CONSENSUS")
        self.assert_no_market_surprise_or_trade(r)

    def test_asof_before_conservative_research_day_does_not_leak_forecast(self):
        for when in (at(10, 13), at(11, 6), at(11, 6, 23, 59)):
            r = self.case(when)
            self.assertEqual(r["state"], "LAB_NOT_YET_AVAILABLE_ASOF")
            self.assertIsNone(r["model_nowcast_percent_documentary_only"])
            self.assertIsNone(r["source_updated_calendar_date_not_capture_instant"])
            self.assertFalse(r["model_nowcast_visible_before_release"])
            self.assert_no_market_surprise_or_trade(r)

    def test_release_boundary_no_actual_number_or_fake_model_error(self):
        before = self.case(at(11, 10, 13, 29))
        self.assertTrue(before["model_nowcast_visible_before_release"])
        self.assertEqual(before["state"], "LAB_PRE_RELEASE_MODEL_FORECAST_CONTEXT_ONLY")
        after = self.case(at(11, 10, 13, 30))
        self.assertEqual(after["state"], "LAB_AWAIT_OFFICIAL_FIRST_RELEASE_NO_EX_POST_COMPARISON")
        self.assertFalse(after["model_nowcast_visible_before_release"])
        self.assertEqual(after["model_nowcast_percent_documentary_only"], 3.74)
        self.assert_no_market_surprise_or_trade(after)

    def test_future_asof_still_cannot_retroactively_fill_bls_actual(self):
        for when in (at(11, 11), at(12, 1)):
            r = self.case(when)
            self.assertEqual(r["state"], "LAB_AWAIT_OFFICIAL_FIRST_RELEASE_NO_EX_POST_COMPARISON")
            self.assertIsNone(r["first_bls_actual_headline_yoy_percent"])
            self.assert_no_market_surprise_or_trade(r)

    def test_tamper_model_value_even_plausible_matches_fail_closed(self):
        for val in (3.6, 3.7, 3.75, "3.74", 4, None):
            payload = json.loads(RECEIPT)
            payload["source_transcribed_forecast_percent"] = val
            r = self.case(receipt=json.dumps(payload).encode("utf-8"))
            self.assertEqual(r["state"], "LAB_BLOCKED")
            self.assert_no_market_surprise_or_trade(r)

    def test_tamper_consensus_actual_result_and_trade_proof_fail_closed(self):
        changes = (("first_release_actual_observed", True),
                   ("first_release_actual_headline_cpi_yoy_percent", 3.7),
                   ("may_compute_ex_post_model_error", True),
                   ("may_compute_market_surprise", True),
                   ("may_infer_fx_direction", True),
                   ("exact_retrieval_instant_independently_attested", True),
                   ("source_original_html_bytes_archived", True),
                   ("source_original_html_sha256", "0" * 64))
        for k, val in changes:
            payload = json.loads(RECEIPT)
            payload[k] = val
            r = self.case(receipt=json.dumps(payload).encode())
            self.assertEqual(r["state"], "LAB_BLOCKED", k)
            self.assert_no_market_surprise_or_trade(r)

    def test_tamper_period_measure_time_and_source_fail_closed(self):
        for key, val in (
            ("target_reference_month", "2026-09"),
            ("target_indicator", "US_CORE_CPI_MONTH_OVER_MONTH"),
            ("source_url", "https://example.com/forecast"),
            ("source_page_updated_calendar_date", "2026-11-10"),
            ("conservative_visible_after_utc", "2026-11-06T00:00:00Z"),
            ("first_release_scheduled_utc", "2026-11-09T13:30:00Z"),
        ):
            payload = json.loads(RECEIPT)
            payload[key] = val
            self.assertEqual(self.case(receipt=json.dumps(payload).encode())["state"],
                             "LAB_BLOCKED", key)

    def test_tamper_bytes_duplicates_and_nonfinite_fail_closed(self):
        for bad in (None, "str", {}, b"", RECEIPT + b" "):
            self.assertEqual(self.case(receipt=bad)["state"], "LAB_BLOCKED")
        duplicate = RECEIPT.replace(b'"schema":', b'"schema":"x","schema":', 1)
        self.assertEqual(self.case(receipt=duplicate)["state"], "LAB_BLOCKED")
        nan = RECEIPT.replace(b"3.74", b"NaN", 1)
        self.assertEqual(self.case(receipt=nan)["state"], "LAB_BLOCKED")

    def test_naive_asof_rejected_and_timezone_normalized(self):
        for when in (None, "2026-11-08", datetime(2026, 11, 8)):
            self.assertEqual(self.case(when)["state"], "LAB_BLOCKED")
        local = datetime(2026, 11, 7, 20, tzinfo=timezone(timedelta(hours=-4)))
        self.assertEqual(self.case(local), self.case(at(11, 8)))


if __name__ == "__main__":
    unittest.main()
