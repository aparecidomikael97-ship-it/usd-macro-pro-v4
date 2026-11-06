"""Official Cleveland Fed nowcast documentation is NOT an attested daily vintage."""
from datetime import datetime, timezone, timedelta
from pathlib import Path
import json
import unittest

from atlasquant_trader_eurusd_sep2026_clevelandfed_nowcast_pit_gap_lab import (
    PINNED_REFERENCE_SHA256,
    inspect_eurusd_sep2026_clevelandfed_nowcast_pit_gap_lab as inspect,
)

DOCS = Path(__file__).resolve().parent / "docs" / "continuidade"
REF = (DOCS / "TRADER_EURUSD_SEP2026_CLEVELANDFED_MODEL_NOWCAST_PIT_GAP_LAB_20261106.json").read_bytes()
SURVEYS = (DOCS / "TRADER_EURUSD_SEP2026_EXPECTATIONS_MISMATCH_LAB_20261106.json").read_bytes()
POLICY = (DOCS / "TRADER_EURUSD_POLICY_DECISIONS_SEPOCT2026_LAB_20261106.json").read_bytes()
CPI = (DOCS / "TRADER_EURUSD_SEP2026_OFFICIAL_HEADLINE_CONTEXT_LAB_20261106.json").read_bytes()


def at(month, day, hour=0, minute=0):
    return datetime(2026, month, day, hour, minute, tzinfo=timezone.utc)


class ClevelandFedModelNowcastVintageGapTests(unittest.TestCase):
    def run_case(self, when=at(11, 7), ref=REF, surveys=SURVEYS, policy=POLICY,
                 cpi=CPI):
        return inspect(ref, expectations_casebook_raw=surveys,
                       policy_casebook_raw=policy, inflation_casebook_raw=cpi,
                       as_of_utc=when)

    def assert_never_consensus_surprise_or_trade(self, result):
        self.assertEqual(result["operational_bias"], "AGUARDAR")
        self.assertIsNone(result["fx_bias"])
        self.assertIsNone(result["oct13_model_nowcast_percent"])
        self.assertIsNone(result["us_september_cpi_model_error_percentage_points"])
        self.assertEqual(result["historical_point_in_time_forecast_count"], 0)
        self.assertEqual(result["matched_pre_release_market_consensus_by_currency"], {})
        self.assertEqual(result["september_cpi_surprise_by_currency"], {})
        self.assertEqual(result["validated_forward_prediction_count"], 0)
        self.assertIsNone(result["validated_accuracy"])
        self.assertEqual((result["http_requests"], result["new_cost_brl"]), (0, 0))
        for key in ("exact_oct13_sep2026_cpi_nowcast_verified", "can_feed_live_radar",
                    "trade_authorized", "publishable", "worker_enabled",
                    "scheduler_enabled"):
            self.assertFalse(result[key], key)

    def test_source_model_identity_visible_after_research_availability(self):
        r = self.run_case()
        self.assertEqual(r["state"], "LAB_REFERENCE_VISIBLE_NO_ATTESTED_PRE_CPI_VINTAGE")
        self.assertEqual(r["reference_sha256"], PINNED_REFERENCE_SHA256)
        self.assertTrue(r["source_is_model_not_market_consensus"])
        self.assertEqual(r["visible_official_model_metadata"]["target_period"], "2026-09")
        self.assertEqual(r["visible_official_model_metadata"]["historical_value_and_publication_receipt"], "NOT_ATTESTED")
        self.assertIn("NON_SEASONALLY_ADJUSTED", r["visible_official_model_metadata"]["potentially_comparable_measure"])
        self.assert_never_consensus_surprise_or_trade(r)

    def test_current_source_metadata_must_not_leak_into_oct13_2026(self):
        for when in (at(9, 12), at(10, 13), at(10, 14), at(10, 15), at(11, 6, 23, 59)):
            r = self.run_case(when)
            self.assertEqual(r["state"], "LAB_REFERENCE_NOT_YET_AVAILABLE_ASOF")
            self.assertIsNone(r["visible_official_model_metadata"])
            self.assertFalse(r["source_is_model_not_market_consensus"])
            self.assert_never_consensus_surprise_or_trade(r)

    def test_us_cpi_actual_visible_does_not_fabricate_model_error(self):
        r = self.run_case(at(10, 15))
        self.assertEqual(r["latest_documentary_cpi_currencies"], ["USD"])
        self.assert_never_consensus_surprise_or_trade(r)
        r = self.run_case(at(11, 7))
        self.assertEqual(r["latest_documentary_cpi_currencies"], ["USD", "EUR"])
        self.assert_never_consensus_surprise_or_trade(r)

    def test_present_day_observation_or_secondary_reprint_cannot_be_backdated(self):
        for inserted in (3.6, 3.7, 4, "3.60", float("nan")):
            obj = json.loads(REF)
            obj["oct13_headline_yoy_nowcast_percent"] = inserted
            r = self.run_case(ref=json.dumps(obj).encode("utf-8"))
            self.assertEqual(r["state"], "LAB_BLOCKED")
            self.assert_never_consensus_surprise_or_trade(r)

    def test_fake_vintage_receipt_market_consensus_and_direction_are_rejected(self):
        for key, val in (
            ("original_oct13_snapshot_bytes_archived", True),
            ("exact_historical_publication_instant_independently_attested", True),
            ("exact_historical_nowcast_value_from_original_official_oct13_snapshot_verified", True),
            ("market_consensus_for_sep2026_cpi_release_verified", True),
            ("may_compute_sep2026_cpi_model_error", True),
            ("may_compute_sep2026_cpi_event_surprise", True),
            ("fx_direction_authorized", True),
            ("oct13_vintage_sha256", "0" * 64),
        ):
            obj = json.loads(REF)
            obj[key] = val
            r = self.run_case(ref=json.dumps(obj).encode())
            self.assertEqual(r["state"], "LAB_BLOCKED", key)
            self.assert_never_consensus_surprise_or_trade(r)

    def test_wrong_measure_wrong_period_or_source_blocks(self):
        for key, val in (
            ("target_measure", "US_HEADLINE_CPI_MOM_SEASONALLY_ADJUSTED"),
            ("target_reference_period", "2026-10"),
            ("source_url", "https://not-official.example"),
            ("forecast_type", "MARKET_CONSENSUS"),
            ("requested_historical_vintage_calendar_date", "2026-11-06"),
            ("conservative_research_available_at_utc", "2026-10-13T00:00:00Z"),
        ):
            obj = json.loads(REF)
            obj[key] = val
            r = self.run_case(ref=json.dumps(obj).encode())
            self.assertEqual(r["state"], "LAB_BLOCKED", key)
            self.assert_never_consensus_surprise_or_trade(r)

    def test_prior_casebook_tampering_blocks(self):
        for kw in ({"surveys": SURVEYS + b" "}, {"policy": POLICY + b" "},
                   {"cpi": CPI + b" "}):
            r = self.run_case(**kw)
            self.assertEqual(r["state"], "LAB_BLOCKED")
            self.assert_never_consensus_surprise_or_trade(r)

    def test_reject_naive_clock_non_bytes_and_duplicates(self):
        for when in (None, "2026-11-07", datetime(2026, 11, 7)):
            self.assertEqual(self.run_case(when)["state"], "LAB_BLOCKED")
        for bad in (None, {}, "text", b"", REF + b" "):
            self.assertEqual(self.run_case(ref=bad)["state"], "LAB_BLOCKED")
        duplicate = REF.replace(b'"schema":', b'"schema":"wrong","schema":', 1)
        self.assertEqual(self.run_case(ref=duplicate)["state"], "LAB_BLOCKED")

    def test_utc_equivalence_for_future_reference(self):
        self.assertEqual(self.run_case(at(11, 7))["state"],
                         self.run_case(datetime(2026, 11, 6, 20, tzinfo=timezone(timedelta(hours=-4))))["state"])


if __name__ == "__main__":
    unittest.main()
