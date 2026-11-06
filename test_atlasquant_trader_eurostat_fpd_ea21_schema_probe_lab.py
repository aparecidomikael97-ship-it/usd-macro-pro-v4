"""All fixtures synthetic; NEVER a Eurostat API/HTTP capture."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import json
import unittest

from atlasquant_trader_eurostat_fpd_ea21_payload_envelope_lab import MAX_BYTES
from atlasquant_trader_eurostat_fpd_ea21_schema_probe_lab import (
    inspect_supplied_eurostat_fpd_ea21_schema_probe_lab as inspect,
)

DOCS = Path(__file__).resolve().parent / "docs" / "continuidade"
META = (DOCS / "TRADER_EUROSTAT_FPD_EA21_20261106_METADATA_CASE_LAB.json").read_bytes()
EURUSD = (DOCS / "TRADER_EURUSD_20261106_FOUR_OFFICIAL_DOCUMENTS_ASOF_CASE_LAB.json").read_bytes()
NOW = datetime(2026, 11, 6, 19, tzinfo=timezone.utc)
URL = ("https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/"
       "prc_hicp_fpd?format=JSON&lang=EN&freq=M&unit=RCH_A&coicop18=CP00"
       "&release=FIN&geo=EA21&time=2026-09")
IDS = ["freq", "unit", "coicop18", "release", "geo", "time"]
CODES = ["M", "RCH_A", "CP00", "FIN", "EA21", "2026-09"]


def fixture(value=777.0, classification="coicop18"):
    ids = [classification if i == "coicop18" else i for i in IDS]
    return {
        "class": "dataset", "version": "2.0", "source": "ESTAT",
        "id": ids, "size": [1] * len(ids),
        "dimension": {k: {"category": {"index": {v: 0}}}
                      for k, v in zip(ids, CODES)},
        "value": {"0": value},
        "status": {"0": "e"},
        "updated": "2026-10-16T21:00:00Z",
    }


def raw(obj):
    return json.dumps(obj).encode("utf-8")


def run(payload=None, *, url=URL, observed=NOW, asof=NOW, meta=META, eurusd=EURUSD):
    return inspect(raw(fixture()) if payload is None else payload,
                   request_url_claim=url, observed_at_utc=observed,
                   as_of_utc=asof, metadata_casebook_raw=meta,
                   eurusd_casebook_raw=eurusd)


class FpdSchemaProbeTests(unittest.TestCase):
    def assert_quarantined_from_trading(self, r):
        self.assertEqual(r["operational_bias"], "AGUARDAR")
        self.assertIsNone(r["fx_bias"])
        self.assertEqual(r["validated_prediction_count"], 0)
        self.assertIsNone(r["validated_accuracy"])
        self.assertEqual((r["http_requests"], r["new_cost_brl"]), (0, 0))
        for k in ("official_http_response_independently_witnessed",
                  "tls_server_identity_independently_attested",
                  "historical_initial_release_bytes_attested",
                  "source_available_at_prior_market_timestamp_verified",
                  "source_response_codes_confirmed_against_live_metadata",
                  "numeric_inflation_value_returned", "real_hicp_value_inspected_or_returned",
                  "dimension_codes_confirmed_from_official_api",
                  "real_release_type_confirmed",
                  "is_comparable_eurusd_inflation_observation",
                  "trade_authorized", "can_feed_live_radar", "publishable",
                  "worker_enabled", "scheduler_enabled"):
            self.assertFalse(r[k], k)
        self.assertNotIn("777", str(r))

    def test_synthetic_2026_coicop18_shape_can_be_seen_not_authenticated(self):
        r = run()
        self.assertEqual(r["state"], "LAB_SUPPLIED_SCHEMA_PROBE_QUARANTINED_NOT_VERIFIED")
        self.assertTrue(r["jsonstat_structure_checked"])
        self.assertEqual(r["supplied_dimension_ids_untrusted"], IDS)
        self.assertEqual(r["supplied_category_codes_untrusted"]["coicop18"], "CP00")
        self.assertEqual(r["supplied_classification_dimension_candidate"], "coicop18")
        self.assert_quarantined_from_trading(r)

    def test_legacy_label_is_only_an_alternative_unverified_shape(self):
        obj = fixture(classification="coicop")
        r = run(payload=raw(obj), url=URL.replace("coicop18=", "coicop="))
        self.assertEqual(r["state"], "LAB_SUPPLIED_SCHEMA_PROBE_QUARANTINED_NOT_VERIFIED")
        self.assertEqual(r["supplied_classification_dimension_candidate"], "coicop")
        self.assert_quarantined_from_trading(r)

    def test_mismatched_request_classification_against_body_is_blocked(self):
        self.assertEqual(run(url=URL.replace("coicop18=", "coicop="))["state"],
                         "LAB_BLOCKED")
        obj = fixture(classification="coicop")
        self.assertEqual(run(payload=raw(obj))["state"], "LAB_BLOCKED")

    def test_url_host_geo_date_dimensions_and_duplicates_are_exact(self):
        for url in (URL.replace("ec.europa.eu", "example.com"),
                    URL.replace("https:", "http:"),
                    URL.replace("EA21", "EA20"),
                    URL.replace("2026-09", "2026-10"),
                    URL + "&lastTimePeriod=1", URL + "&geo=EA20",
                    URL.replace("coicop18=", "coicop=" ) + "&coicop18=CP00",
                    URL.replace("release=FIN", "release=")):
            r = run(url=url)
            self.assertEqual(r["state"], "LAB_BLOCKED", url)
            self.assert_quarantined_from_trading(r)

    def test_no_capture_backdating_or_naive_clock(self):
        earlier = datetime(2026, 10, 16, 23, tzinfo=timezone.utc)
        for kw in ({"observed": earlier},
                   {"observed": NOW + timedelta(minutes=1)},
                   {"observed": datetime(2026, 11, 6, 19)},
                   {"asof": datetime(2026, 11, 6, 19)}):
            self.assertEqual(run(**kw)["state"], "LAB_BLOCKED")

    def test_hash_pinned_context_must_not_be_changed(self):
        for kw in ({"meta": META + b" "}, {"eurusd": EURUSD + b" "},
                   {"meta": b"invalid"}, {"eurusd": b"invalid"}):
            r = run(**kw)
            self.assertEqual(r["state"], "LAB_BLOCKED")
            self.assert_quarantined_from_trading(r)

    def test_reject_bad_json_duplicates_nonfinite_and_oversize(self):
        for data in (b"", b"nil", b"\xff" * 200, b"x" * (MAX_BYTES + 1),
                     raw(fixture()).replace(b'"class":', b'"class": "other", "class":', 1),
                     raw(fixture(float("nan")))):
            self.assertEqual(run(payload=data)["state"], "LAB_BLOCKED")

    def test_fake_class_source_version_updated_are_not_trusted(self):
        for k, v in (("class", "collection"), ("source", "FAKE"),
                     ("version", "1.0"), ("updated", "2026-12-10T00:00:00Z"),
                     ("updated", "2026-10-16T21:00:00")):
            obj = fixture()
            obj[k] = v
            self.assertEqual(run(payload=raw(obj))["state"], "LAB_BLOCKED")

    def test_dimension_cardinality_and_codes_are_bounded(self):
        for mutation in ("size", "id", "index", "bool_index", "value"):
            obj = fixture()
            if mutation == "size": obj["size"][0] = 2
            if mutation == "id": obj["id"].append("another")
            if mutation == "index": obj["dimension"]["geo"]["category"]["index"] = {"EA20": 0}
            if mutation == "bool_index": obj["dimension"]["geo"]["category"]["index"] = {"EA21": False}
            if mutation == "value": obj["value"]["1"] = 22
            self.assertEqual(run(payload=raw(obj))["state"], "LAB_BLOCKED")

    def test_any_synthetic_numbers_remain_inaccessible_and_without_bias(self):
        for value in (-20.0, 0.0, 3.8, 777.0, None, True, "not a rate"):
            r = run(payload=raw(fixture(value)))
            self.assertEqual(r["state"], "LAB_SUPPLIED_SCHEMA_PROBE_QUARANTINED_NOT_VERIFIED")
            self.assertNotIn("inflation_rate", r)
            self.assert_quarantined_from_trading(r)


if __name__ == "__main__":
    unittest.main()
