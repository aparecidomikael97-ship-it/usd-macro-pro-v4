"""Synthetic ONS D7G7 /data JSON fixtures: NO actual HTTP capture."""
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
import json
import unittest

from atlasquant_trader_ons_gbp_cpi_current_lab import (
    SCHEMA, SOURCE_DATA, parse_current_ons_gbp_d7g7_lab as parse,
)

NOW = datetime(2026, 11, 5, 2, 10, tzinfo=timezone.utc)


def fixture():
    return {
        "cdid": "D7G7", "dataset": "MM23",
        "description": "CPI ANNUAL RATE 00: ALL ITEMS 2015=100",
        "unit": "%", "preUnit": "", "date": "21 October 2026",
        "nextRelease": "18 November 2026",
        "years": [{"date": "2025", "value": "3.4"}],
        "quarters": [{"date": "2026 Q3", "value": "3.1"}],
        "months": [
            {"date": "2026 JUL", "value": "2.9"},
            {"date": "2026 AUG", "value": "3.1"},
            {"date": "2026 SEP", "value": "3.5"},
        ],
    }


def raw(obj=None):
    return json.dumps(fixture() if obj is None else obj).encode("utf-8")


_UNSET = object()


def run(data=_UNSET, **kwargs):
    return parse(raw() if data is _UNSET else data,
                 observed_at_utc=kwargs.get("observed_at_utc", NOW))


class OnsGbpCpiD7G7Tests(unittest.TestCase):
    def assert_no_signal(self, result):
        for flag in ("individual_release_instant_verified",
                     "archived_historical_vintage_verified",
                     "original_http_response_observed",
                     "original_source_authenticity_verified",
                     "consensus_pre_event_attested",
                     "methodologically_comparable_to_EUR_HICP_US_CPIU",
                     "commercial_redistribution_rights_verified",
                     "trade_authorized", "can_feed_live_radar",
                     "worker_enabled", "scheduler_enabled", "publishable"):
            self.assertIs(result[flag], False, flag)
        self.assertEqual(result["operational_bias"], "AGUARDAR")
        self.assertIsNone(result["fx_bias"])
        self.assertEqual((result["external_http_requests"], result["new_cost_brl"]), (0, 0))

    def test_source_metadata_and_realistic_monthly_fixture(self):
        blob = raw()
        r = run(blob)
        self.assertEqual(r["schema"], SCHEMA)
        self.assertEqual(r["state"], "LAB_CURRENT_GBP_ONS_D7G7_QUARANTINED")
        self.assertEqual(r["source"], "UK_ONS")
        self.assertEqual(r["currency"], "GBP")
        self.assertEqual((r["series_id"], r["source_dataset"]), ("D7G7", "MM23"))
        self.assertEqual(r["source_json_candidate_endpoint"], SOURCE_DATA)
        self.assertEqual((r["latest_period"], r["latest_annual_cpi_rate_percent"]),
                         ("2026-09", "3.5"))
        self.assertEqual(r["release_date_calendar_only"], "2026-10-21")
        self.assertEqual(r["monthly_observation_count"], 3)
        self.assertEqual(r["source_bytes_sha256"], sha256(blob).hexdigest())
        self.assert_no_signal(r)

    def test_annual_and_quarterly_rows_cannot_masquerade_as_monthly(self):
        obj = fixture()
        obj["years"][0]["value"] = "99.9"
        obj["quarters"][0]["value"] = "98.8"
        r = run(raw(obj))
        self.assertEqual(r["latest_annual_cpi_rate_percent"], "3.5")

    def test_missing_prior_month_stays_missing_not_zero(self):
        obj = fixture()
        obj["months"][1]["value"] = ".."
        r = run(raw(obj))
        self.assertIsNone(r["monthly_observations"][1]["annual_cpi_percent_claim"])
        self.assertEqual(r["latest_annual_cpi_rate_percent"], "3.5")

    def test_latest_month_missing_fails_closed(self):
        for missing in ("", ":", "..", None):
            obj = fixture()
            obj["months"][-1]["value"] = missing
            self.assertEqual(run(raw(obj))["state"], "LAB_BLOCKED")

    def test_wrong_series_dataset_title_or_units_rejected(self):
        for key, value in (("cdid", "D7BT"), ("dataset", "MM22"),
                           ("description", "CPI INDEX 00: ALL ITEMS 2015=100"),
                           ("unit", "INDEX"), ("preUnit", "£")):
            obj = fixture()
            obj[key] = value
            self.assertEqual(run(raw(obj))["reason"], "ONS_D7G7_SERIES_METADATA_MISMATCH")

    def test_explicit_source_dataset_can_replace_dataset(self):
        obj = fixture()
        obj["sourceDataset"] = obj.pop("dataset")
        self.assertEqual(run(raw(obj))["state"],
                         "LAB_CURRENT_GBP_ONS_D7G7_QUARANTINED")

    def test_conflicting_dataset_fields_rejected(self):
        obj = fixture()
        obj["sourceDataset"] = "UNKNOWN"
        self.assertEqual(run(raw(obj))["state"], "LAB_BLOCKED")

    def test_duplicate_month_out_of_order_and_invalid_date_rejected(self):
        for kind in ("duplicate", "reverse", "invalid"):
            obj = fixture()
            if kind == "duplicate":
                obj["months"].append(deepcopy(obj["months"][-1]))
            elif kind == "reverse":
                obj["months"].reverse()
            else:
                obj["months"][-1]["date"] = "2026 SEPT"
            self.assertEqual(run(raw(obj))["reason"], "ONS_MONTH_OBSERVATION_INVALID")

    def test_wrong_release_date_or_future_capture_rejected(self):
        for release in ("bad", "2026-10-21", "21 Smarch 2026", "10 November 2026"):
            obj = fixture()
            obj["date"] = release
            self.assertEqual(run(raw(obj))["state"], "LAB_BLOCKED")

    def test_release_before_last_observation_month_rejected(self):
        obj = fixture()
        obj["date"] = "21 August 2026"
        self.assertEqual(run(raw(obj))["reason"],
                         "ONS_LATEST_MONTHLY_RATE_MISSING_OR_RELEASE_PRECEDES_MONTH")

    def test_nan_exponent_comma_bool_or_outside_rate_rejected(self):
        for value in ("NaN", "inf", "3,5", "3e0", True, "-60", "101", [], {}):
            obj = fixture()
            obj["months"][-1]["value"] = value
            self.assertEqual(run(raw(obj))["state"], "LAB_BLOCKED")

    def test_negative_zero_and_ordinary_zero_preserved(self):
        obj = fixture()
        obj["months"][-1]["value"] = "0.0"
        self.assertEqual(run(raw(obj))["latest_annual_cpi_rate_percent"], "0.0")
        obj["months"][-1]["value"] = "-0.1"
        self.assertEqual(run(raw(obj))["latest_annual_cpi_rate_percent"], "-0.1")

    def test_json_duplicate_keys_are_blocked(self):
        data = raw().replace(b'"cdid": "D7G7",', b'"cdid": "D7G7", "cdid": "D7G7",')
        self.assertEqual(run(data)["reason"], "INVALID_JSON_OR_DUPLICATE_KEYS")

    def test_bom_unicode_invalid_or_non_json_denied(self):
        for data in (b"\xff" + raw(), b"not-json" * 20, b"", None, "JSON"):
            self.assertEqual(run(data)["state"], "LAB_BLOCKED")

    def test_absent_timezone_denied(self):
        self.assertEqual(run(observed_at_utc=datetime(2026, 11, 5, 2))["state"],
                         "LAB_BLOCKED")

    def test_date_only_never_becomes_intraday_release_proof(self):
        r = run()
        self.assertTrue(r["release_day_is_not_publication_instant"])
        self.assertTrue(r["current_series_is_not_archived_previous_version"])
        self.assertFalse(r["archived_historical_vintage_verified"])
        self.assert_no_signal(r)


if __name__ == "__main__":
    unittest.main()
