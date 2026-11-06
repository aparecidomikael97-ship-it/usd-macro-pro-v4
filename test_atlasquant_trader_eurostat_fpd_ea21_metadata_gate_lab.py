"""No EA20-in-2026 or future final CPI leaked into an as-of study."""
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import json
import unittest

from atlasquant_trader_eurostat_fpd_ea21_metadata_gate_lab import (
    FIXED_CASEBOOK_SHA256, inspect_eurostat_fpd_ea21_metadata_gate_lab as inspect,
)

DOCS = Path(__file__).resolve().parent / "docs" / "continuidade"
METADATA = (DOCS / "TRADER_EUROSTAT_FPD_EA21_20261106_METADATA_CASE_LAB.json").read_bytes()
EURUSD = (DOCS / "TRADER_EURUSD_20261106_FOUR_OFFICIAL_DOCUMENTS_ASOF_CASE_LAB.json").read_bytes()
NOW = datetime(2026, 11, 6, 19, tzinfo=timezone.utc)


def at(m, d, h=0, minute=0):
    return datetime(2026, m, d, h, minute, tzinfo=timezone.utc)


def run(when=NOW, raw=METADATA, eurusd=EURUSD):
    return inspect(raw, eurusd_casebook_raw=eurusd, as_of_utc=when)


class EurostatFpdEa21MetadataTests(unittest.TestCase):
    def assert_no_signal(self, r):
        self.assertEqual(r["operational_bias"], "AGUARDAR")
        self.assertIsNone(r["fx_bias"])
        self.assertEqual(r["validated_prediction_count"], 0)
        self.assertIsNone(r["validated_accuracy"])
        self.assertEqual((r["http_requests"], r["new_cost_brl"]), (0, 0))
        for f in ("dataset_api_payload_captured", "schema_dimension_codes_verified",
                  "original_historical_release_time_witnessed",
                  "flash_and_final_same_observation_assumed",
                  "valid_oct2026_full_inferred_from_scheduled_date",
                  "historical_first_released_data_immutable_verified",
                  "can_supply_pit_macroeconomic_vintage", "can_feed_live_radar",
                  "trade_authorized", "publishable", "worker_enabled",
                  "scheduler_enabled", "oct2026_full_release_data_in_this_lab",
                  "original_feb2026_first_release_bytes_witnessed"):
            self.assertIs(r[f], False, f)

    def test_ea21_and_ea20_are_distinct_and_only_metadata_pinned(self):
        r = run()
        self.assertEqual(r["state"], "LAB_EUROSTAT_EA21_FPD_METADATA_ONLY_NOT_API_PAYLOAD")
        self.assertEqual(r["accepted_casebook_sha256"], FIXED_CASEBOOK_SHA256)
        self.assertEqual(r["accepted_casebook_sha256"], sha256(METADATA).hexdigest())
        self.assertEqual(r["2026_euro_area_geo_candidate"], "EA21")
        self.assertEqual(r["2025_euro_area_geo_historical"], "EA20")
        self.assert_no_signal(r)

    def test_api_dimensions_documented_labels_not_verified_codes(self):
        r = run()
        self.assertEqual(r["api_dimension_labels_documented_only"],
                         ["freq", "unit", "coicop", "release", "geo", "TIME_PERIOD"])
        self.assertFalse(r["schema_dimension_codes_verified"])

    def test_september_full_fpd_metadata_day_after_oct16_gate(self):
        self.assertFalse(run(when=at(10, 16, 23, 59))[
            "sep2026_full_dataset_metadata_reference_visible_asof"])
        self.assertIsNone(run(when=at(10, 16, 23, 59))[
            "documentary_latest_full_reference_period_asof"])
        r = run(when=at(10, 17))
        self.assertTrue(r["sep2026_full_dataset_metadata_reference_visible_asof"])
        self.assertEqual(r["documentary_latest_full_reference_period_asof"], "2026-09")
        self.assert_no_signal(r)

    def test_nov4_oct_flash_not_visible_before_eurostat_conservative_gate(self):
        self.assertFalse(run(when=at(11, 4, 23, 59))[
            "oct2026_flash_reference_visible_in_separate_case"])
        self.assertTrue(run(when=at(11, 5))[
            "oct2026_flash_reference_visible_in_separate_case"])

    def test_flash_october_may_be_visible_while_fpd_full_is_not(self):
        r = run()
        self.assertTrue(r["oct2026_flash_reference_visible_in_separate_case"])
        self.assertEqual(r["documentary_latest_full_reference_period_asof"], "2026-09")
        self.assertFalse(r["oct2026_full_release_data_in_this_lab"])
        self.assert_no_signal(r)

    def test_nov18_schedule_never_invents_future_full_data(self):
        for when in (at(11, 6), at(11, 18), at(11, 19), at(12, 31)):
            r = run(when=when)
            self.assertFalse(r["oct2026_full_release_data_in_this_lab"])
            self.assertFalse(r["valid_oct2026_full_inferred_from_scheduled_date"])
            self.assert_no_signal(r)

    def test_january_first_published_2026_erratum_remains_unattested(self):
        x = json.loads(METADATA)
        e = x["historical_erratum"]
        self.assertEqual(e["initial_full_release_date"], "2026-02-25")
        self.assertEqual(e["incorrect_fpd_update_date"], "2026-03-03")
        self.assertEqual(e["original_fpd_restored_date"], "2026-04-24")
        self.assertIs(e["historical_first_published_dataset_never_changed_claim"], False)
        r = run()
        self.assertTrue(r["jan2026_first_released_dataset_had_2026_erratum"])
        self.assertFalse(r["historical_first_released_data_immutable_verified"])

    def test_reject_substitution_of_ea20_or_fake_release_clock(self):
        for target, key, value in (
            ("euro_area_geographical_rules", "from_2026_01", "EA20"),
            ("euro_area_geographical_rules", "ea20_is_2026_target_geo", True),
            ("historical_erratum", "original_fpd_restored_date", "2026-02-25"),
        ):
            x = json.loads(METADATA)
            x[target][key] = value
            self.assertEqual(run(raw=json.dumps(x).encode())["state"], "LAB_BLOCKED")

    def test_reject_fake_full_cpi_or_api_verification(self):
        for key, value in (("october_2026_full_release_value_captured", True),
                           ("full_dataset_response_received", True),
                           ("api_release_dimension_codes_verified", True),
                           ("dataset_documentary_last_full_period_seen_on_2026_11_06", "2026-10")):
            x = json.loads(METADATA)
            x[key] = value
            self.assertEqual(run(raw=json.dumps(x).encode())["state"], "LAB_BLOCKED")

    def test_eurusd_casebook_tampering_blocks_fpd_bridge(self):
        for raw in (None, b"not eurostat", EURUSD + b" "):
            r = run(eurusd=raw)
            self.assertEqual(r["state"], "LAB_BLOCKED")
            self.assert_no_signal(r)

    def test_bad_metadata_bytes_and_naive_clock_are_refused(self):
        self.assertEqual(run(when=datetime(2026, 11, 6))[
            "state"], "LAB_BLOCKED")
        for raw in (None, b"", "text", b"\xff" * 900, b"x" * 10001,
                    METADATA.replace(b'"kind":', b'"kind":"OTHER","kind":', 1)):
            r = run(raw=raw)
            self.assertEqual(r["state"], "LAB_BLOCKED")
            self.assert_no_signal(r)


if __name__ == "__main__":
    unittest.main()
