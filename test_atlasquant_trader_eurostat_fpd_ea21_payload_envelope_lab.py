"""Synthetic JSON-stat fixture proves only structural quarantine, NOT API."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import json
import unittest

from atlasquant_trader_eurostat_fpd_ea21_payload_envelope_lab import (
    MAX_BYTES, inspect_supplied_eurostat_fpd_ea21_payload_envelope_lab as inspect,
)

DOCS = Path(__file__).resolve().parent / "docs" / "continuidade"
META = (DOCS / "TRADER_EUROSTAT_FPD_EA21_20261106_METADATA_CASE_LAB.json").read_bytes()
EURUSD = (DOCS / "TRADER_EURUSD_20261106_FOUR_OFFICIAL_DOCUMENTS_ASOF_CASE_LAB.json").read_bytes()
NOW = datetime(2026, 11, 6, 19, tzinfo=timezone.utc)
URL = ("https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/"
       "prc_hicp_fpd?format=JSON&lang=EN&freq=M&unit=RCH_A&coicop=CP00"
       "&release=FIN&geo=EA21&time=2026-09")
IDS = ["freq", "unit", "coicop", "release", "geo", "time"]
CODES = ["M", "RCH_A", "CP00", "FIN", "EA21", "2026-09"]


def fixture(value=777.0):
    """Deliberately fake observation; its number MUST NEVER escape parser."""
    return {
        "class": "dataset", "version": "2.0", "source": "ESTAT",
        "id": list(IDS), "size": [1] * len(IDS),
        "dimension": {k: {"category": {"index": {v: 0}}}
                      for k, v in zip(IDS, CODES)},
        "value": {"0": value},
        "updated": "2026-10-16T21:00:00Z",
    }


def raw(obj=None):
    return json.dumps(fixture() if obj is None else obj).encode("utf-8")


def run(payload=None, *, url=URL, observed=NOW, asof=NOW, meta=META, eurusd=EURUSD):
    return inspect(raw() if payload is None else payload,
                   request_url_claim=url, observed_at_utc=observed,
                   as_of_utc=asof, metadata_casebook_raw=meta,
                   eurusd_casebook_raw=eurusd)


class FpdEa21SuppliedEnvelopeTests(unittest.TestCase):
    def assert_no_pit_or_trade(self, r):
        self.assertEqual(r["operational_bias"], "AGUARDAR")
        self.assertIsNone(r["fx_bias"])
        self.assertEqual(r["validated_prediction_count"], 0)
        self.assertIsNone(r["validated_accuracy"])
        self.assertEqual((r["http_requests"], r["new_cost_brl"]), (0, 0))
        for f in ("official_http_response_independently_witnessed",
                  "tls_server_identity_independently_attested",
                  "historical_initial_release_bytes_attested",
                  "source_available_at_prior_market_timestamp_verified",
                  "source_response_codes_confirmed_against_live_metadata",
                  "numeric_inflation_value_returned", "oct2026_full_cpi_inferred",
                  "jan2026_fpd_immutable_verified", "trade_authorized",
                  "can_feed_live_radar", "publishable", "worker_enabled",
                  "scheduler_enabled"):
            self.assertFalse(r[f], f)

    def test_synthetic_envelope_passes_but_never_authenticates_or_returns_value(self):
        r = run()
        self.assertEqual(r["state"],
                         "LAB_SUPPLIED_JSONSTAT_ENVELOPE_QUARANTINED_NOT_SOURCE_ATTESTED")
        self.assertTrue(r["jsonstat_structure_checked"])
        self.assertEqual(r["submitted_jsonstat_dataset_id"], "prc_hicp_fpd")
        self.assertEqual(r["declared_dimension_ids"], IDS)
        self.assertEqual(r["declared_unit_code_unverified"], "RCH_A")
        self.assertEqual(r["declared_release_code_unverified"], "FIN")
        self.assertEqual(r["euro_area_in_2026"], "EA21")
        self.assertNotIn("777", str(r))
        self.assert_no_pit_or_trade(r)

    def test_url_and_geo_require_exact_official_endpoint_and_ea21(self):
        for fake in (URL.replace("EA21", "EA20"),
                     URL.replace("ec.europa.eu", "example.com"),
                     URL.replace("https://", "http://"),
                     URL.replace("prc_hicp_fpd", "prc_hicp_minr"),
                     URL + "&geo=EA20", URL + "&lastTimePeriod=2",
                     URL.replace("2026-09", "2026-10")):
            r = run(url=fake)
            self.assertEqual(r["state"], "LAB_BLOCKED")
            self.assert_no_pit_or_trade(r)

    def test_unknown_values_require_actual_schema_check_not_implicit_approval(self):
        obj = fixture()
        obj["dimension"]["geo"]["category"]["index"] = {"EA20": 0}
        self.assertEqual(run(payload=raw(obj))["state"], "LAB_BLOCKED")
        obj = fixture()
        obj["dimension"]["release"]["category"]["index"] = {"FLS": 0}
        self.assertEqual(run(payload=raw(obj))["state"], "LAB_BLOCKED")
        obj = fixture()
        obj["dimension"]["geo"]["category"]["index"] = {"EA21": False}
        self.assertEqual(run(payload=raw(obj))["state"], "LAB_BLOCKED")

    def test_single_series_bounded_no_other_period_or_column(self):
        obj = fixture()
        obj["size"][-1] = 2
        self.assertEqual(run(payload=raw(obj))["state"], "LAB_BLOCKED")
        obj = fixture()
        obj["value"]["1"] = 300.0
        self.assertEqual(run(payload=raw(obj))["state"], "LAB_BLOCKED")
        obj = fixture()
        obj["id"].append("extra")
        self.assertEqual(run(payload=raw(obj))["state"], "LAB_BLOCKED")

    def test_reject_nonfinite_bad_type_or_duplicate_json(self):
        for fake in (None, b"", "hello", b"\xff" * 150, b"x" * (MAX_BYTES + 1),
                     raw().replace(b'"class":', b'"class":"extra","class":', 1)):
            if fake is None:
                fake = b"nil"
            r = run(payload=fake)
            self.assertEqual(r["state"], "LAB_BLOCKED")
            self.assert_no_pit_or_trade(r)
        for v in (True, None, "4.0", float("nan"), float("inf")):
            obj = fixture(v)
            self.assertEqual(run(payload=raw(obj))["state"], "LAB_BLOCKED")

    def test_updated_declared_later_than_capture_not_allowed(self):
        obj = fixture()
        obj["updated"] = "2026-12-01T00:00:00Z"
        self.assertEqual(run(payload=raw(obj))["state"], "LAB_BLOCKED")

    def test_capture_clock_must_precede_asof_and_be_timezone_aware(self):
        for kwargs in ({"observed": NOW + timedelta(hours=1)},
                       {"observed": datetime(2026, 11, 6, 19)},
                       {"asof": datetime(2026, 11, 6, 19)}):
            r = run(**kwargs)
            self.assertEqual(r["state"], "LAB_BLOCKED")

    def test_sep_full_metadata_not_usable_before_documentary_floor(self):
        earlier = datetime(2026, 10, 16, 23, 59, tzinfo=timezone.utc)
        r = run(observed=earlier, asof=earlier)
        self.assertEqual(r["state"], "LAB_BLOCKED")
        self.assert_no_pit_or_trade(r)

    def test_mutated_metadata_or_eurusd_reference_rejected(self):
        for kwargs in ({"meta": META + b" "}, {"eurusd": EURUSD + b" "},
                       {"meta": b"invalid"}, {"eurusd": b"invalid"}):
            r = run(**kwargs)
            self.assertEqual(r["state"], "LAB_BLOCKED")
            self.assert_no_pit_or_trade(r)

    def test_changing_synthetic_numeric_value_cannot_produce_buy_sell_bias(self):
        for value in (-20.0, 0.0, 3.8, 777.0):
            r = run(payload=raw(fixture(value)))
            self.assertEqual(r["state"],
                             "LAB_SUPPLIED_JSONSTAT_ENVELOPE_QUARANTINED_NOT_SOURCE_ATTESTED")
            self.assertNotIn("annual_inflation_percent", r)
            self.assert_no_pit_or_trade(r)


if __name__ == "__main__":
    unittest.main()
