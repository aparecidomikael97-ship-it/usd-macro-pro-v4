"""Offline contract tests: live BLS CPI-U levels are not CPI release vintages."""
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import URLError
from zipfile import ZipFile

from atlasquant_trader_bls_us_cpiu_once_lab import (
    API_URL, SERIES_ID, MAX_BYTES, parse_current_bls_cpiu_lab as parse,
    fetch_current_bls_cpiu_once_lab as fetch,
)

NOW = datetime(2026, 11, 5, 0, 10, tzinfo=timezone.utc)


def row(year, period, value, *, latest=False, flags=None):
    x = {
        "year": str(year), "period": period,
        "value": str(value), "footnotes": [{}] if flags is None else flags,
    }
    if latest:
        x["latest"] = "true"
    return x


def fixture():
    return {
        "status": "REQUEST_SUCCEEDED", "responseTime": 13, "message": [],
        "Results": {"series": [{"seriesID": SERIES_ID, "data": [
            row(2026, "M09", "336.940", latest=True),
            row(2026, "M08", "334.980"),
            row(2025, "M09", "320.000"),
        ]}]},
    }


def raw(x=None):
    return json.dumps(fixture() if x is None else x).encode("utf-8")


class FakeOpener:
    def __init__(self, *, data=None, status=200, url=API_URL,
                 content_type="application/json", fail=None):
        self.data = raw() if data is None else data
        self.status, self.url, self.fail = status, url, fail
        self.headers = {"Content-Type": content_type,
                        "Content-Encoding": "identity"}
        self.open_count = 0

    def open(self, req, timeout):
        self.open_count += 1
        self.req, self.timeout = req, timeout
        if self.fail is not None:
            raise self.fail
        return self

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def geturl(self):
        return self.url

    def read(self, max_len=-1):
        return self.data[:max_len] if max_len > 0 else self.data


class UsBlsCpiuLabTests(unittest.TestCase):
    def test_index_is_not_cpi_inflation_rate_and_yoy_is_derived(self):
        out = parse(raw(), observed_at_utc=NOW)
        self.assertEqual(out["state"], "LAB_CURRENT_US_BLS_CPIU_INDEX_QUARANTINED")
        self.assertEqual(out["series_unit"], "CPI_U_INDEX_1982_84_EQUALS_100")
        self.assertEqual(out["latest_period"], "2026-09")
        self.assertEqual(out["latest_index_value"], "336.940")
        self.assertEqual(out["prior_year_same_month"], "2025-09")
        self.assertEqual(out["derived_yoy_percent_from_same_month_indices"], "5.2938")
        self.assertTrue(out["derived_yoy_not_direct_official_bls_release_claim"])
        self.assertFalse(out["methodologically_comparable_to_EUROSTAT_HICP"])
        self.assertFalse(out["individual_release_instant_verified"])
        self.assertFalse(out["prior_forecast_vintage_verified"])
        self.assertFalse(out["trade_authorized"])
        self.assertEqual(out["operational_bias"], "AGUARDAR")

    def test_bls_m13_annual_average_is_ignored_not_month_thirteen(self):
        x = fixture()
        x["Results"]["series"][0]["data"].insert(
            2, row(2025, "M13", "321.943"))
        x["Results"]["series"][0]["data"].append(
            row(2024, "M13", "313.689"))
        out = parse(raw(x), observed_at_utc=NOW)
        self.assertEqual(out["state"], "LAB_CURRENT_US_BLS_CPIU_INDEX_QUARANTINED")
        self.assertEqual(out["bls_m13_annual_averages_ignored"], 2)
        self.assertTrue(out["annual_average_m13_is_not_monthly_observation"])
        self.assertEqual(out["observations_count"], 3)
        self.assertEqual(out["derived_yoy_percent_from_same_month_indices"], "5.2938")
        self.assertFalse(any(x["month"].endswith("-13") for x in out["observations"]))
        self.assertFalse(out["individual_release_instant_verified"])

    def test_duplicated_m13_and_annual_average_marked_latest_are_refused(self):
        x = fixture()
        x["Results"]["series"][0]["data"].append(
            row(2025, "M13", "321.943"))
        x["Results"]["series"][0]["data"].append(
            row(2025, "M13", "321.943"))
        self.assertEqual(parse(raw(x), observed_at_utc=NOW)["reason"],
                         "BLS_ANNUAL_AVERAGE_INVALID")
        x["Results"]["series"][0]["data"].pop()
        x["Results"]["series"][0]["data"][-1]["latest"] = "true"
        self.assertEqual(parse(raw(x), observed_at_utc=NOW)["reason"],
                         "BLS_ANNUAL_AVERAGE_INVALID")

    def test_bls_dash_is_missing_month_not_zero_or_annual_inflation(self):
        x = fixture()
        x["Results"]["series"][0]["data"].insert(
            2, row(2025, "M10", "-"))
        out = parse(raw(x), observed_at_utc=NOW)
        self.assertEqual(out["state"], "LAB_CURRENT_US_BLS_CPIU_INDEX_QUARANTINED")
        self.assertEqual(out["explicit_missing_months_from_api_sentinel"], ["2025-10"])
        self.assertTrue(out["missing_index_never_replaced_with_zero_or_interpolated"])
        self.assertEqual(out["derived_yoy_percent_from_same_month_indices"], "5.2938")
        self.assertFalse(any(x["month"] == "2025-10" for x in out["observations"]))
        self.assertEqual(out["observations_count"], 3)

    def test_missing_comparison_month_with_dash_does_not_create_yoy(self):
        x = fixture()
        x["Results"]["series"][0]["data"][-1]["value"] = "-"
        out = parse(raw(x), observed_at_utc=NOW)
        self.assertEqual(out["state"], "LAB_CURRENT_US_BLS_CPIU_INDEX_QUARANTINED")
        self.assertEqual(out["explicit_missing_months_from_api_sentinel"], ["2025-09"])
        self.assertIsNone(out["derived_yoy_percent_from_same_month_indices"])
        self.assertFalse(out["prior_year_month_observed"])

    def test_repeated_missing_month_and_fake_latest_sentinel_blocked(self):
        x = fixture()
        x["Results"]["series"][0]["data"].insert(
            2, row(2025, "M10", "-"))
        x["Results"]["series"][0]["data"].insert(
            3, row(2025, "M10", "-"))
        self.assertEqual(parse(raw(x), observed_at_utc=NOW)["reason"],
                         "BLS_FUTURE_OR_DUPLICATED_MONTH")
        x = fixture()
        x["Results"]["series"][0]["data"][0]["value"] = "-"
        self.assertEqual(parse(raw(x), observed_at_utc=NOW)["reason"],
                         "BLS_MISSING_AVERAGE_OR_LATEST_VALUE")

    def test_missing_prior_year_same_month_does_not_fake_yoy(self):
        x = fixture()
        x["Results"]["series"][0]["data"].pop()
        out = parse(raw(x), observed_at_utc=NOW)
        self.assertIsNone(out["derived_yoy_percent_from_same_month_indices"])
        self.assertTrue(out["missing_comparable_month_yields_no_yoy"])
        self.assertFalse(out["prior_year_month_observed"])
        self.assertFalse(out["can_feed_live_radar"])

    def test_missing_month_is_never_replaced_with_previous_month(self):
        x = fixture()
        x["Results"]["series"][0]["data"][-1]["period"] = "M08"
        out = parse(raw(x), observed_at_utc=NOW)
        self.assertIsNone(out["derived_yoy_percent_from_same_month_indices"])
        self.assertEqual(out["prior_year_same_month"], "2025-09")

    def test_api_failure_messages_and_wrong_series_fail_closed(self):
        for kind in ("status", "messages", "no_series", "two_series",
                     "wrong_series", "null_results"):
            with self.subTest(kind=kind):
                x = fixture()
                if kind == "status":
                    x["status"] = "REQUEST_FAILED"
                elif kind == "messages":
                    x["message"] = ["Data missing from requested series"]
                elif kind == "no_series":
                    x["Results"]["series"] = []
                elif kind == "two_series":
                    x["Results"]["series"].append(x["Results"]["series"][0])
                elif kind == "wrong_series":
                    x["Results"]["series"][0]["seriesID"] = "CUSR0000SA0"
                else:
                    x["Results"] = None
                self.assertEqual(parse(raw(x), observed_at_utc=NOW)["state"], "LAB_BLOCKED")

    def test_reject_annual_average_m13_future_year_and_duplicate_month(self):
        for kind in ("annual", "future", "duplicate", "bad_period", "bad_year"):
            with self.subTest(kind=kind):
                x = fixture()
                rows = x["Results"]["series"][0]["data"]
                if kind == "annual":
                    rows[0]["period"] = "M13"
                elif kind == "future":
                    rows[0]["year"] = "2027"
                elif kind == "duplicate":
                    rows[1]["period"] = "M09"
                elif kind == "bad_period":
                    rows[0]["period"] = "M00"
                else:
                    rows[0]["year"] = 2026
                self.assertEqual(parse(raw(x), observed_at_utc=NOW)["state"], "LAB_BLOCKED")

    def test_reject_float_nan_negative_and_unknown_index_formats(self):
        for value in ("NaN", "-2.1", "1e9", "0", "10000", 336.94, None, True):
            with self.subTest(value=value):
                x = fixture()
                x["Results"]["series"][0]["data"][0]["value"] = value
                self.assertEqual(parse(raw(x), observed_at_utc=NOW)["state"], "LAB_BLOCKED")

    def test_preliminary_footnotes_are_retained_not_laundered_to_final(self):
        x = fixture()
        x["Results"]["series"][0]["data"][0]["footnotes"] = [
            {"code": "P", "text": "Preliminary."}
        ]
        out = parse(raw(x), observed_at_utc=NOW)
        self.assertEqual(out["observations"][0]["footnote_codes"], ["P"])
        self.assertTrue(out["observations"][0]["not_proven_final"])
        self.assertFalse(out["trade_authorized"])

    def test_malformed_footnote_latest_and_order_are_blocked(self):
        for kind in ("notes", "latest", "multiple_latest", "ordering"):
            with self.subTest(kind=kind):
                x = fixture()
                rows = x["Results"]["series"][0]["data"]
                if kind == "notes":
                    rows[0]["footnotes"] = "n/a"
                elif kind == "latest":
                    rows[0]["latest"] = True
                elif kind == "multiple_latest":
                    rows[1]["latest"] = "true"
                else:
                    rows[0], rows[1] = rows[1], rows[0]
                self.assertEqual(parse(raw(x), observed_at_utc=NOW)["state"], "LAB_BLOCKED")

    def test_untrusted_caller_bytes_never_infer_real_http_capture(self):
        out = parse(raw(), observed_at_utc=NOW)
        self.assertEqual(out["external_http_requests"], 0)
        self.assertFalse(out["current_http_response_observed"])
        self.assertEqual(out["raw_response_sha256"], sha256(raw()).hexdigest())
        self.assertIsNone(out["raw_snapshot_archive_path"])
        self.assertFalse(out["consensus_before_release_verified"])

    def test_naive_clock_rejected_and_large_or_invalid_json_blocked(self):
        with self.assertRaises(ValueError):
            parse(raw(), observed_at_utc=NOW.replace(tzinfo=None))
        self.assertEqual(parse(b"", observed_at_utc=NOW)["state"], "LAB_BLOCKED")
        self.assertEqual(parse(b"x" * (MAX_BYTES + 1), observed_at_utc=NOW)["state"],
                         "LAB_BLOCKED")
        self.assertEqual(parse(b"broken", observed_at_utc=NOW)["state"], "LAB_BLOCKED")

    def test_disabled_by_default_and_bounded_timeout_use_no_network(self):
        with patch("atlasquant_trader_bls_us_cpiu_once_lab.build_opener",
                   side_effect=AssertionError("network forbidden")):
            self.assertEqual(fetch()["reason"], "MANUAL_HTTP_OPT_IN_REQUIRED")
            for timeout in (-1, 0, 16, True, 4.3, None):
                self.assertEqual(fetch(manually_authorized=True,
                                       timeout_seconds=timeout)["reason"],
                                 "HTTP_TIMEOUT_OUT_OF_BOUNDS")

    def test_one_get_and_archive_preserves_original_raw_bytes(self):
        data = raw()
        fake = FakeOpener(data=data)
        with tempfile.TemporaryDirectory() as folder:
            with patch("atlasquant_trader_bls_us_cpiu_once_lab.build_opener",
                       return_value=fake) as patched:
                out = fetch(manually_authorized=True, archive_dir=folder)
            self.assertEqual(patched.call_count, 1)
            self.assertEqual(fake.open_count, 1)
            self.assertEqual(fake.req.get_method(), "GET")
            self.assertEqual(fake.req.full_url, API_URL)
            self.assertEqual(out["state"], "LAB_CURRENT_US_BLS_CPIU_INDEX_QUARANTINED")
            self.assertEqual(out["external_http_requests"], 1)
            self.assertTrue(out["current_http_response_observed"])
            archive_path = Path(out["raw_snapshot_archive_path"])
            self.assertTrue(archive_path.is_file())
            self.assertTrue(archive_path.is_relative_to(Path(folder)))
            self.assertEqual(out["raw_snapshot_archive_sha256"],
                             sha256(archive_path.read_bytes()).hexdigest())
            with ZipFile(archive_path) as zipfile:
                self.assertEqual(zipfile.read("response.json"), data)
                receipt = json.loads(zipfile.read("observation_receipt.json"))
                self.assertFalse(receipt["prior_forecast_vintage_verified"])
                self.assertEqual(receipt["raw_response_sha256"], sha256(data).hexdigest())
            self.assertFalse(out["trade_authorized"])

    def test_failed_http_and_redirect_do_not_approve_data(self):
        for kind, fake, expected in (
            ("redirect", FakeOpener(url="https://example.com/other"),
             "HTTP_STATUS_OR_URL_INVALID"),
            ("non_json", FakeOpener(content_type="text/html"),
             "HTTP_RESPONSE_NOT_JSON_PLAIN"),
            ("http", FakeOpener(status=503), "HTTP_STATUS_OR_URL_INVALID"),
            ("network", FakeOpener(fail=URLError("no connection")), "HTTPS_FAILED_URLError"),
        ):
            with self.subTest(kind=kind):
                with patch("atlasquant_trader_bls_us_cpiu_once_lab.build_opener",
                           return_value=fake):
                    out = fetch(manually_authorized=True)
                self.assertEqual(out["state"], "LAB_BLOCKED")
                self.assertEqual(out["reason"], expected)
                self.assertEqual(out["external_http_requests"], 1)
                self.assertFalse(out["trade_authorized"])


if __name__ == "__main__":
    unittest.main()
