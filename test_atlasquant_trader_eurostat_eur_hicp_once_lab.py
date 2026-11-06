"""No-network fixtures for the EUR HICP 2026 ECOICOP v2 laboratory reader."""
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import URLError
from zipfile import ZipFile

from atlasquant_trader_eurostat_eur_hicp_once_lab import (
    API_URL, MAX_BYTES, parse_current_eur_hicp_jsonstat_lab as parse,
    fetch_current_eur_hicp_once_lab as fetch,
)


NOW = datetime(2026, 11, 4, 23, 55, tzinfo=timezone.utc)


def fixture():
    return {
        "version": "2.0", "class": "dataset", "source": "ESTAT",
        "updated": "2026-11-04T11:00:00+0100",
        "id": ["freq", "unit", "coicop18", "geo", "time"],
        "size": [1, 1, 1, 1, 3],
        "dimension": {
            "freq": {"category": {"index": {"M": 0}}},
            "unit": {"category": {"index": {"RCH_A": 0}}},
            "coicop18": {"category": {"index": {"TOTAL": 0}}},
            "geo": {"category": {"index": {"EA": 0}}},
            "time": {"category": {"index": {
                "2026-08": 0, "2026-09": 1, "2026-10": 2}}},
        },
        "value": {"0": 3.2, "1": 3.8, "2": 4.0},
        "status": {"2": "e"},
    }


def raw(obj=None):
    return json.dumps(fixture() if obj is None else obj).encode("utf-8")


class FakeOpener:
    def __init__(self, data=None, url=API_URL, status=200, headers=None,
                 fail=None):
        self.data = raw() if data is None else data
        self.url, self.status, self.fail = url, status, fail
        self.headers = headers if headers is not None else {
            "Content-Type": "application/json", "Content-Encoding": "identity",
            "Content-Length": str(len(self.data)),
        }
        self.calls = 0

    def open(self, request, timeout):
        self.calls += 1
        self.timeout = timeout
        self.request = request
        if self.fail:
            raise self.fail
        return self

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def geturl(self):
        return self.url

    def read(self, limit=-1):
        return self.data[:limit] if limit >= 0 else self.data


class EurostatHicpLabTests(unittest.TestCase):
    def test_real_shape_fixture_keeps_e_flag_and_never_authorizes_trade(self):
        out = parse(raw(), observed_at_utc=NOW)
        self.assertEqual(out["state"], "LAB_EUR_HICP_CURRENT_JSONSTAT_QUARANTINED")
        self.assertEqual([(x["period"], x["annual_inflation_percent"])
                          for x in out["historical_months_observed_not_historical_vintages"]],
                         [("2026-08", 3.2), ("2026-09", 3.8), ("2026-10", 4.0)])
        self.assertEqual(out["estimate_count"], 1)
        self.assertEqual(out["historical_months_observed_not_historical_vintages"][-1]
                         ["status_interpretation"], "ESTIMATED_NOT_FINAL")
        self.assertFalse(out["trade_authorized"])
        self.assertFalse(out["can_feed_live_radar"])
        self.assertFalse(out["release_at_instant_proven"])
        self.assertFalse(out["pre_event_vintage_proven"])
        self.assertTrue(out["dataset_update_not_individual_release_instant"])
        self.assertEqual(out["operational_bias"], "AGUARDAR")

    def test_legacy_dataset_shape_and_wrong_units_blocked(self):
        for kind in ("old_coicop", "wrong_unit", "wrong_geo", "source",
                     "dimension_extra", "extra_series", "old_version"):
            with self.subTest(kind=kind):
                x = fixture()
                if kind == "old_coicop":
                    x["id"][2] = "coicop"
                elif kind == "wrong_unit":
                    x["dimension"]["unit"]["category"]["index"] = {"RCH_M": 0}
                elif kind == "wrong_geo":
                    x["dimension"]["geo"]["category"]["index"] = {"US": 0}
                elif kind == "source":
                    x["source"] = "SOMEBODY"
                elif kind == "dimension_extra":
                    x["dimension"]["unknown"] = {}
                elif kind == "extra_series":
                    x["size"] = [1, 1, 1, 2, 3]
                else:
                    x["version"] = "1.0"
                out = parse(raw(x), observed_at_utc=NOW)
                self.assertEqual(out["state"], "LAB_BLOCKED")
                self.assertFalse(out["trade_authorized"])

    def test_missing_nan_infinity_and_fabricated_value_blocked(self):
        for value in (None, True, "3.8", float("nan"), float("inf"), -999.0):
            with self.subTest(value=str(value)):
                x = fixture()
                x["value"]["1"] = value
                self.assertEqual(parse(raw(x), observed_at_utc=NOW)["state"],
                                 "LAB_BLOCKED")
        x = fixture()
        del x["value"]["2"]
        self.assertEqual(parse(raw(x), observed_at_utc=NOW)["reason"],
                         "JSONSTAT_MISSING_OR_EXTRA_VALUES")

    def test_estimate_cannot_be_laundered_into_final_or_unknown_status(self):
        x = fixture()
        x["status"] = {"2": "p"}
        self.assertEqual(parse(raw(x), observed_at_utc=NOW)["reason"],
                         "JSONSTAT_UNKNOWN_OBSERVATION_STATUS")
        x["status"] = {}
        out = parse(raw(x), observed_at_utc=NOW)
        self.assertEqual(out["estimate_count"], 0)
        self.assertEqual(out["historical_months_observed_not_historical_vintages"][-1]
                         ["status_interpretation"],
                         "UNFLAGGED_NOT_PROOF_OF_FINALITY")

    def test_future_month_update_and_bad_time_index_are_refused(self):
        cases = []
        x = fixture()
        x["dimension"]["time"]["category"]["index"]["2026-10"] = 0
        cases.append(x)
        x = fixture()
        x["dimension"]["time"]["category"]["index"]["2027-01"] = 2
        del x["dimension"]["time"]["category"]["index"]["2026-10"]
        cases.append(x)
        x = fixture()
        x["updated"] = "2026-11-05T11:00:00+01:00"
        cases.append(x)
        x = fixture()
        x["updated"] = "2026-11-04T11:00:00"
        cases.append(x)
        for x in cases:
            with self.subTest(case=x):
                self.assertEqual(parse(raw(x), observed_at_utc=NOW)["state"],
                                 "LAB_BLOCKED")

    def test_malformed_mixed_type_time_index_fails_closed(self):
        x = fixture()
        x["dimension"]["time"]["category"]["index"]["2026-10"] = "2"
        self.assertEqual(parse(raw(x), observed_at_utc=NOW)["reason"],
                         "JSONSTAT_TIME_INDEX_INVALID")
        x["dimension"]["time"]["category"]["index"]["2026-10"] = None
        self.assertEqual(parse(raw(x), observed_at_utc=NOW)["reason"],
                         "JSONSTAT_TIME_INDEX_INVALID")

    def test_caller_supplied_bytes_never_become_a_verified_retrieval(self):
        out = parse(raw(), observed_at_utc=NOW)
        self.assertEqual(out["external_http_requests"], 0)
        self.assertFalse(out["current_http_response_observed"])
        self.assertEqual(out["raw_response_sha256"], sha256(raw()).hexdigest())
        self.assertIsNone(out["raw_snapshot_archive_path"])
        self.assertFalse(out["source_payload_custody_authenticated"])

    def test_opt_in_and_timeout_required_without_network(self):
        with patch("atlasquant_trader_eurostat_eur_hicp_once_lab.build_opener",
                   side_effect=AssertionError("network called without permission")):
            self.assertEqual(fetch()["reason"], "MANUAL_HTTP_OPT_IN_REQUIRED")
            for timeout in (0, -1, True, 20, 3.6):
                self.assertEqual(fetch(manually_authorized=True,
                                       timeout_seconds=timeout)["reason"],
                                 "HTTP_TIMEOUT_OUT_OF_BOUNDS")

    def test_one_read_current_dataset_and_archive_exact_response(self):
        data = raw()
        opener = FakeOpener(data)
        with tempfile.TemporaryDirectory() as folder:
            with patch("atlasquant_trader_eurostat_eur_hicp_once_lab.build_opener",
                       return_value=opener) as mock:
                result = fetch(manually_authorized=True, archive_dir=folder)
            self.assertEqual(mock.call_count, 1)
            self.assertEqual(opener.calls, 1)
            self.assertEqual(opener.request.full_url, API_URL)
            self.assertEqual(opener.request.get_method(), "GET")
            self.assertEqual(opener.timeout, 8)
            self.assertEqual(result["state"], "LAB_EUR_HICP_CURRENT_JSONSTAT_QUARANTINED")
            self.assertEqual(result["external_http_requests"], 1)
            self.assertTrue(result["current_http_response_observed"])
            saved = Path(result["raw_snapshot_archive_path"])
            self.assertTrue(saved.is_file())
            self.assertTrue(saved.is_relative_to(Path(folder)))
            self.assertEqual(len(list(Path(folder).glob("*.zip"))), 1)
            self.assertEqual(result["raw_snapshot_archive_sha256"],
                             sha256(saved.read_bytes()).hexdigest())
            with ZipFile(saved) as snapshot:
                self.assertEqual(snapshot.read("response.json"), data)
                receipt = json.loads(snapshot.read("observation_receipt.json"))
                self.assertEqual(receipt["raw_response_sha256"],
                                 sha256(data).hexdigest())
                self.assertFalse(receipt["pre_event_vintage_proven"])
            self.assertFalse(result["trade_authorized"])

    def test_bad_final_url_status_type_and_oversize_are_refused(self):
        for kind, changes in (
            ("url", {"url": "https://ec.europa.eu/unreviewed"}),
            ("status", {"status": 503}),
            ("content", {"headers": {"Content-Type": "text/html"}}),
            ("huge", {"data": b"a" * (MAX_BYTES + 2)}),
            ("json", {"data": b"{broken"}),
        ):
            with self.subTest(kind=kind):
                opener = FakeOpener(**changes)
                with patch("atlasquant_trader_eurostat_eur_hicp_once_lab.build_opener",
                           return_value=opener):
                    out = fetch(manually_authorized=True)
                self.assertEqual(out["state"], "LAB_BLOCKED")
                self.assertEqual(out["external_http_requests"], 1)

    def test_transport_failure_reports_one_attempt_and_no_trusted_origin(self):
        opener = FakeOpener(fail=URLError("no connectivity"))
        with patch("atlasquant_trader_eurostat_eur_hicp_once_lab.build_opener",
                   return_value=opener):
            out = fetch(manually_authorized=True)
        self.assertEqual(out["state"], "LAB_BLOCKED")
        self.assertEqual(out["external_http_requests"], 1)
        self.assertFalse(out["release_at_instant_proven"])


if __name__ == "__main__":
    unittest.main()
