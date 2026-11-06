"""Official September 2026 headline *page references*, no API/PIT validation."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import json
import unittest

from atlasquant_trader_eurusd_sep2026_official_headline_lab import (
    PINNED_CASEBOOK_SHA256,
    inspect_eurusd_sep2026_official_headline_lab as inspect,
)

CASE_PATH = (Path(__file__).resolve().parent / "docs" / "continuidade" /
             "TRADER_EURUSD_SEP2026_OFFICIAL_HEADLINE_CONTEXT_LAB_20261106.json")
RAW = CASE_PATH.read_bytes()
UTC = timezone.utc
NOW = datetime(2026, 11, 6, 19, tzinfo=UTC)


class OfficialHeadlineSeptemberContextTests(unittest.TestCase):
    def assert_no_trade_or_pit(self, result):
        self.assertEqual(result["operational_bias"], "AGUARDAR")
        self.assertIsNone(result["fx_bias"])
        self.assertEqual(result["validated_forward_prediction_count"], 0)
        self.assertIsNone(result["validated_accuracy"])
        self.assertEqual((result["http_requests"], result["new_cost_brl"]), (0, 0))
        for key in ("same_statistical_methodology_for_both_currency_headlines",
                    "historical_original_release_page_bytes_attested",
                    "independent_release_instant_http_witness",
                    "source_api_response_captured", "published_consensus_surprise_verified",
                    "central_bank_rate_response_verified",
                    "headline_level_differential_authorized_as_fx_factor",
                    "can_feed_live_radar", "trade_authorized", "publishable",
                    "worker_enabled", "scheduler_enabled"):
            self.assertFalse(result[key], key)

    def test_verified_official_page_references_same_september_context_only(self):
        result = inspect(RAW, as_of_utc=NOW)
        self.assertEqual(result["accepted_documentary_casebook_sha256"],
                         PINNED_CASEBOOK_SHA256)
        self.assertEqual(result["state"],
                         "LAB_SAME_SEP2026_PERIOD_DOCUMENTARY_HEADLINE_CONTEXT_ONLY")
        self.assertTrue(result["same_observation_month_available_in_both_releases"])
        self.assertEqual(result["visible_currencies"], ["USD", "EUR"])
        obs = {r["currency"]: r for r in result["visible_press_release_context"]}
        self.assertEqual(obs["USD"]["annual_headline_september_percent"], 3.7)
        self.assertEqual(obs["EUR"]["annual_headline_september_percent"], 3.8)
        self.assert_no_trade_or_pit(result)

    def test_acceleration_is_within_own_series_only(self):
        obs = {r["currency"]: r for r in inspect(RAW, as_of_utc=NOW)[
            "visible_press_release_context"]}
        self.assertEqual((obs["USD"]["annual_headline_august_percent"],
                          obs["USD"]["computed_change_in_annual_rate_from_august_pp"]),
                         (3.4, 0.3))
        self.assertEqual((obs["EUR"]["annual_headline_august_percent"],
                          obs["EUR"]["computed_change_in_annual_rate_from_august_pp"]),
                         (3.2, 0.6))
        self.assertNotIn("pair_inflation_score", inspect(RAW, as_of_utc=NOW))

    def test_before_us_september_release_neither_full_record_visible(self):
        r = inspect(RAW, as_of_utc=datetime(2026, 10, 14, 23, 59, tzinfo=UTC))
        self.assertEqual(r["visible_currencies"], [])
        self.assertFalse(r["same_observation_month_available_in_both_releases"])
        self.assert_no_trade_or_pit(r)

    def test_after_us_but_before_eurostat_full_only_us_visible(self):
        for at in (datetime(2026, 10, 15, tzinfo=UTC),
                   datetime(2026, 10, 16, 23, 59, tzinfo=UTC)):
            r = inspect(RAW, as_of_utc=at)
            self.assertEqual(r["visible_currencies"], ["USD"])
            self.assertEqual(r["state"],
                             "LAB_INCOMPLETE_SEP2026_DOCUMENTARY_CONTEXT_ONLY")
            self.assert_no_trade_or_pit(r)

    def test_eurostat_full_document_only_appears_on_conservative_oct17_gate(self):
        r = inspect(RAW, as_of_utc=datetime(2026, 10, 17, tzinfo=UTC))
        self.assertEqual(r["visible_currencies"], ["USD", "EUR"])
        self.assertTrue(r["same_observation_month_available_in_both_releases"])
        self.assert_no_trade_or_pit(r)

    def test_september_flash_oct2_cannot_be_misrepresented_as_full(self):
        r = inspect(RAW, as_of_utc=datetime(2026, 10, 3, tzinfo=UTC))
        self.assertEqual(r["visible_currencies"], [])
        self.assertEqual(r["state"],
                         "LAB_INCOMPLETE_SEP2026_DOCUMENTARY_CONTEXT_ONLY")
        self.assert_no_trade_or_pit(r)

    def test_timezone_normalization_never_allows_future_evidence(self):
        t = datetime(2026, 10, 16, 16, tzinfo=timezone(timedelta(hours=-4)))
        r = inspect(RAW, as_of_utc=t)
        self.assertEqual(r["visible_currencies"], ["USD"])
        self.assert_no_trade_or_pit(r)

    def test_naive_clock_and_untyped_bytes_fail_closed(self):
        for value in (None, "2026-11-06", datetime(2026, 11, 6, 19)):
            r = inspect(RAW, as_of_utc=value)
            self.assertEqual(r["state"], "LAB_BLOCKED")
            self.assert_no_trade_or_pit(r)
        for value in (None, {}, "raw", b"", b"not JSON"):
            self.assertEqual(inspect(value, as_of_utc=NOW)["state"], "LAB_BLOCKED")

    def test_tampering_any_source_value_date_or_hash_blocks(self):
        for currency, key, value in (("USD", "annual_headline_september_percent", 3.8),
                                     ("EUR", "annual_headline_september_percent", 3.7),
                                     ("EUR", "publication_calendar_date", "2026-10-02"),
                                     ("USD", "conservative_available_at_utc",
                                      "2026-10-14T00:00:00Z")):
            obj = json.loads(RAW)
            for row in obj["observations"]:
                if row["currency"] == currency:
                    row[key] = value
            self.assertEqual(inspect(json.dumps(obj).encode(), as_of_utc=NOW)["state"],
                             "LAB_BLOCKED")
        self.assertEqual(inspect(RAW + b" ", as_of_utc=NOW)["state"], "LAB_BLOCKED")

    def test_documentary_context_never_mistaken_for_api_or_signal(self):
        r = inspect(RAW, as_of_utc=NOW)
        self.assertFalse(r["same_statistical_methodology_for_both_currency_headlines"])
        self.assertFalse(r["historical_original_release_page_bytes_attested"])
        self.assertFalse(r["headline_level_differential_authorized_as_fx_factor"])
        self.assertNotIn("eurusd_buy", r)
        self.assertNotIn("eurusd_sell", r)
        self.assert_no_trade_or_pit(r)


if __name__ == "__main__":
    unittest.main()
