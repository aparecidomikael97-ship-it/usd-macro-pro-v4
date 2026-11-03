"""Precommitted CPI model observation with strict post-event separation."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
from copy import deepcopy
import json
import unittest

from atlasquant_trader_cpi_prospective_freeze_lab import (
    SCHEMA, inspect_cpi_prospective_freeze_lab,
)

CASE = Path(__file__).resolve().parent / "docs" / "continuidade" / "TRADER_CPI_PROSPECTIVE_FREEZE_20261103.json"
AFTER = datetime(2026, 11, 3, 9, 30, tzinfo=timezone.utc)
POST = datetime(2026, 11, 11, 14, 0, tzinfo=timezone.utc)


def snapshot():
    return json.loads(CASE.read_text(encoding="utf-8"))


def assess(item=None, when=AFTER, actual=None):
    return inspect_cpi_prospective_freeze_lab(
        snapshot() if item is None else item, evaluated_at=when, later_actual=actual)


def fake_actual():
    return {
        "state": "LAB_CALLER_SUPPLIED_ACTUAL_UNATTESTED",
        "source_url": "https://www.bls.gov/news.release/archives/cpi_11102026.htm",
        "published_at_utc": "2026-11-10T13:30:00Z",
        "captured_at_utc": "2026-11-10T14:00:00Z",
        "cpi_mom_sa_pct": 0.30, "core_cpi_mom_sa_pct": 0.25,
    }


class CPIForecastProspectiveFreezeLabTests(unittest.TestCase):
    def test_prospective_snapshot_before_event(self):
        item = snapshot()
        self.assertEqual(item["schema"], SCHEMA)
        self.assertEqual(item["source_reported_update_day"], "2026-11-02")
        self.assertEqual(item["release_scheduled_utc"], "2026-11-10T13:30:00Z")
        self.assertLess(datetime.fromisoformat(item["observed_at_utc"].replace("Z", "+00:00")),
                        datetime(2026, 11, 10, 13, 30, tzinfo=timezone.utc))

    def test_official_model_numbers_not_market_consensus(self):
        item = snapshot()
        self.assertEqual(item["measured_model_forecast"], {
            "CPI_MOM_SA_PCT": 0.24, "CORE_CPI_MOM_SA_PCT": 0.21,
            "CPI_YOY_NSA_PCT": 3.74, "CORE_CPI_YOY_NSA_PCT": 2.48,
        })
        self.assertIn("NOT_MARKET_CONSENSUS", item["forecast_type"])
        self.assertIsNone(item["market_consensus"])

    def test_pre_event_result_and_sha_digest_reproducible(self):
        a, b = assess(), assess()
        self.assertEqual(a["state"], "LAB_PROSPECTIVE_DOCUMENTARY_NOWCAST_PRE_EVENT")
        self.assertEqual(a["snapshot_sha256"], b["snapshot_sha256"])
        self.assertEqual(len(a["snapshot_sha256"]), 64)
        self.assertEqual(a["directional_bias"], "AGUARDAR")
        self.assertIsNone(a["later_actual"])

    def test_snapshot_content_hash_changes_if_forecast_changes(self):
        item = snapshot()
        item["measured_model_forecast"]["CPI_MOM_SA_PCT"] = 0.28
        self.assertNotEqual(assess(item)["snapshot_sha256"], assess()["snapshot_sha256"])

    def test_earlier_asof_is_rejected(self):
        self.assertEqual(assess(when=datetime(2026, 11, 2, 12, tzinfo=timezone.utc))["state"],
                         "LAB_FORWARD_CPI_FREEZE_REFUSED")

    def test_past_due_result_not_model_as_actual(self):
        out = assess(when=POST)
        self.assertEqual(out["state"], "LAB_CPI_EVENT_PASSED_OUTCOME_NOT_INGESTED")
        self.assertIsNone(out["later_actual"])
        self.assertIsNone(out["absolute_error_pp"])

    def test_future_actual_injected_rejected(self):
        self.assertEqual(assess(actual=fake_actual())["state"], "LAB_FORWARD_CPI_FREEZE_REFUSED")

    def test_post_event_synthetic_actual_error_is_not_real_oos(self):
        out = assess(when=POST, actual=fake_actual())
        self.assertEqual(out["state"], "LAB_SYNTHETIC_FORWARD_ERROR_COMPARISON_ONLY")
        self.assertEqual(out["absolute_error_pp"], {
            "CPI_MOM_SA_PP": 0.06, "CORE_CPI_MOM_SA_PP": 0.04,
        })
        self.assertFalse(out["real_oos_verified"])
        self.assertEqual(out["directional_bias"], "AGUARDAR")

    def test_all_promotions_denied(self):
        for out in (assess(), assess(when=POST), assess(when=POST, actual=fake_actual())):
            self.assertIsNone(out["probability_calibrated"])
            self.assertFalse(out["accuracy_90_proven"])
            for key in ("official_source_html_verified", "market_consensus_verified",
                        "real_oos_verified", "predictive_edge_proven",
                        "can_feed_live_radar", "trade_authorized",
                        "worker_enabled", "scheduler_enabled"):
                self.assertFalse(out[key], key)

    def test_self_claimed_independent_timestamp_not_accepted(self):
        item = snapshot()
        item["independent_timestamp_attested"] = True
        self.assertEqual(assess(item)["state"], "LAB_FORWARD_CPI_FREEZE_REFUSED")

    def test_all_fake_provenance_flags_rejected(self):
        keys = ("model_updated_intraday_time_attested",
                "source_html_bytes_archived",
                "source_http_response_headers_archived",
                "provider_historical_vintage_attested",
                "rights_to_redistribute_source_html_verified",
                "real_oos_performance_verified", "trade_authorized")
        for key in keys:
            with self.subTest(key=key):
                item = snapshot()
                item[key] = True
                self.assertEqual(assess(item)["state"], "LAB_FORWARD_CPI_FREEZE_REFUSED")

    def test_actual_and_consensus_cannot_be_in_frozen_snapshot(self):
        for key in ("official_release_actual", "market_consensus"):
            with self.subTest(key=key):
                item = snapshot()
                item[key] = 0.25
                self.assertEqual(assess(item)["state"], "LAB_FORWARD_CPI_FREEZE_REFUSED")

    def test_swapped_reference_period_rejected(self):
        item = snapshot()
        item["release_reference_month"] = "2026-09"
        self.assertEqual(assess(item)["state"], "LAB_FORWARD_CPI_FREEZE_REFUSED")

    def test_schedule_time_shift_rejected(self):
        item = snapshot()
        item["release_scheduled_utc"] = "2026-11-10T12:30:00Z"
        self.assertEqual(assess(item)["state"], "LAB_FORWARD_CPI_FREEZE_REFUSED")

    def test_date_after_observation_rejected(self):
        item = snapshot()
        item["source_reported_update_day"] = "2026-11-04"
        self.assertEqual(assess(item)["state"], "LAB_FORWARD_CPI_FREEZE_REFUSED")

    def test_bad_measure_names_rejected(self):
        item = snapshot()
        item["measured_model_forecast"]["CPI_ANNUAL_SA"] = 3.74
        self.assertEqual(assess(item)["state"], "LAB_FORWARD_CPI_FREEZE_REFUSED")

    def test_nan_or_boolean_value_rejected(self):
        for bad in (float("nan"), float("inf"), True, "0.24"):
            with self.subTest(value=str(bad)):
                item = snapshot()
                item["measured_model_forecast"]["CPI_MOM_SA_PCT"] = bad
                self.assertEqual(assess(item)["state"], "LAB_FORWARD_CPI_FREEZE_REFUSED")

    def test_wrong_nowcast_source_rejected(self):
        item = snapshot()
        item["source_url"] = "https://www.clevelandfed.org.evil.example/indicators-and-data/inflation-nowcasting"
        self.assertEqual(assess(item)["state"], "LAB_FORWARD_CPI_FREEZE_REFUSED")

    def test_unexpected_result_field_rejected(self):
        item = snapshot()
        item["market_direction"] = "EURUSD_SELL"
        self.assertEqual(assess(item)["state"], "LAB_FORWARD_CPI_FREEZE_REFUSED")

    def test_fake_actual_source_host_rejected(self):
        actual = fake_actual()
        actual["source_url"] = "https://www.bls.gov.evil.example/news.release/archives/cpi_11102026.htm"
        self.assertEqual(assess(when=POST, actual=actual)["state"], "LAB_FORWARD_CPI_FREEZE_REFUSED")

    def test_fake_actual_before_release_rejected(self):
        actual = fake_actual()
        actual["published_at_utc"] = "2026-11-10T13:29:00Z"
        self.assertEqual(assess(when=POST, actual=actual)["state"], "LAB_FORWARD_CPI_FREEZE_REFUSED")

    def test_future_captured_actual_rejected(self):
        actual = fake_actual()
        actual["captured_at_utc"] = "2026-11-12T15:00:00Z"
        self.assertEqual(assess(when=POST, actual=actual)["state"], "LAB_FORWARD_CPI_FREEZE_REFUSED")

    def test_extra_result_fields_rejected(self):
        actual = fake_actual()
        actual["policy_rate_change"] = -0.25
        self.assertEqual(assess(when=POST, actual=actual)["state"], "LAB_FORWARD_CPI_FREEZE_REFUSED")

    def test_actual_is_explicitly_synthetic(self):
        actual = fake_actual()
        actual["state"] = "REAL_CPI_CERTIFIED"
        self.assertEqual(assess(when=POST, actual=actual)["state"], "LAB_FORWARD_CPI_FREEZE_REFUSED")

    def test_naive_evaluation_time_rejected(self):
        with self.assertRaises(ValueError):
            assess(when=datetime(2026, 11, 3, 9, 30))


if __name__ == "__main__":
    unittest.main()
