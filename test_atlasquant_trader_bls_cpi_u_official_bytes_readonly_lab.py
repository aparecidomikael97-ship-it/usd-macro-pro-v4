"""Fully synthetic BLS API v1 bytes and mocked HTTPS. No live macro calls."""
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
import json
import unittest
from unittest.mock import patch

from atlasquant_trader_bls_cpi_u_official_bytes_readonly_lab import (
    SERIES, URL, _NoRedirect, fetch_bls_cpi_u_v1_readonly_lab as fetch,
    inspect_bls_cpi_u_v1_bytes_lab as inspect,
)

UTC = timezone.utc
AT = datetime(2026, 11, 12, 19, 50, tzinfo=UTC)


def payload(*, data=None, status="REQUEST_SUCCEEDED", sid=SERIES):
    rows = ([{"year": "2026", "period": "M09", "value": "325.000"},
             {"year": "2026", "period": "M08", "value": "324.125"}]
            if data is None else data)
    return {"status": status, "responseTime": 15, "message": [],
            "Results": [{"series": [{"seriesID": sid, "data": rows}]}]}


def raw(document=None):
    return json.dumps(
        payload() if document is None else document,
        sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")


def check(body=None, *, at=AT, server=AT):
    return inspect(original_bytes=raw() if body is None else body,
                   captured_at_utc=at, server_date_at_utc=server)


class FakeResponse:
    def __init__(self, data, *, content_type="application/json",
                 server_time=None, status=200):
        self.body = data
        self.status = status
        self.headers = {
            "Content-Type": content_type,
            "Date": format_datetime(
                datetime.now(UTC) if server_time is None else server_time,
                usegmt=True),
        }

    def getcode(self):
        return self.status

    def read(self, n):
        return self.body[:n]

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


class BlsCpiOriginalByteCaptureTests(unittest.TestCase):
    def safe(self, result):
        self.assertEqual(result["operational_bias"], "AGUARDAR")
        self.assertIsNone(result["macro_directional_signal"])
        self.assertIsNone(result["calibrated_direction_probability"])
        self.assertIsNone(result["validated_directional_accuracy"])
        self.assertEqual(result["measure"], "USD_CPI_U_INDEX_LEVEL_NOT_YOY")
        for flag in (
            "original_release_at_independently_attested",
            "original_historical_vintage_independently_attested",
            "cpi_yoy_from_same_vintage_computed",
            "index_level_safe_to_compare_to_euro_hicp_yoy",
            "can_feed_fx28_directional_forecast",
            "publishable", "live_alert_allowed", "trade_authorized",
            "scheduler_enabled", "worker_enabled",
        ):
            self.assertFalse(result[flag], flag)
        self.assertEqual((result["file_writes"], result["new_cost_brl"]), (0, 0))
        self.assertTrue(result["research_only"])

    def test_valid_index_document_retains_original_bytes_and_local_hash(self):
        from hashlib import sha256
        original = raw()
        report = check(original)
        self.assertEqual(report["state"],
                         "LAB_BLS_CPI_U_INDEX_BYTES_INSPECTED_UNATTESTED")
        self.assertEqual(report["source_sha256"], sha256(original).hexdigest())
        self.assertEqual(report["original_source_bytes_in_memory"], original)
        self.assertEqual(report["last_monthly_period_documentary"], "2026-09")
        self.assertEqual(report["last_index_level_documentary"], "325.000")
        self.assertEqual(report["monthly_observation_count"], 2)
        self.assertFalse(report["http_get_completed"])
        self.assertEqual(report["http_requests"], 0)
        self.safe(report)

    def test_response_order_does_not_change_latest_month(self):
        doc = payload()
        doc["Results"][0]["series"][0]["data"].reverse()
        report = check(raw(doc))
        self.assertEqual(report["last_monthly_period_documentary"], "2026-09")
        self.safe(report)

    def test_response_failure_even_with_valid_data_is_blocked(self):
        result = check(raw(payload(status="REQUEST_FAILED")))
        self.assertEqual(result["reason"],
                         "PROVIDER_STATUS_OR_SINGLE_SERIES_SHAPE_INVALID")
        self.safe(result)

    def test_wrong_series_id_cannot_be_labeled_cpi_u(self):
        result = check(raw(payload(sid="CUSR0000SA0")))
        self.assertEqual(result["reason"], "WRONG_SERIES_OR_INVALID_DATA_COUNT")
        self.safe(result)

    def test_future_observation_month_is_not_allowed(self):
        doc = payload(data=[{"year": "2026", "period": "M12", "value": "330.00"}])
        result = check(raw(doc))
        self.assertEqual(result["reason"], "FUTURE_OBSERVATION_MONTH_LOOKAHEAD")
        self.safe(result)

    def test_m13_annual_average_cannot_substitute_for_monthly(self):
        doc = payload(data=[{"year": "2026", "period": "M13", "value": "325.01"}])
        result = check(raw(doc))
        self.assertEqual(result["reason"], "INVALID_MONTHLY_OBSERVATION")
        self.safe(result)

    def test_duplicate_month_blocks_revision_selection(self):
        doc = payload()
        doc["Results"][0]["series"][0]["data"].append(
            {"year": "2026", "period": "M09", "value": "999.999"})
        report = check(raw(doc))
        self.assertEqual(report["reason"],
                         "DUPLICATE_MONTHLY_VINTAGE_IN_RESPONSE")
        self.safe(report)

    def test_nan_negative_or_zero_index_value_fails(self):
        for value in ("NaN", "-2.0", "0.0", "Infinity", "1e6", 325.5):
            with self.subTest(value=value):
                doc = payload(data=[{"year": "2026", "period": "M09",
                                     "value": value}])
                report = check(raw(doc))
                self.assertEqual(report["reason"], "INVALID_MONTHLY_OBSERVATION")
                self.safe(report)

    def test_duplicate_json_key_or_invalid_unicode_not_accepted(self):
        for bad in (
            b'{"status":"REQUEST_SUCCEEDED","status":"REQUEST_FAILED"}',
            b"{not json}",
            b"\xff\xfe",
        ):
            with self.subTest(bad=bad):
                report = check(bad)
                self.assertEqual(report["reason"],
                                 "MALFORMED_OR_AMBIGUOUS_PROVIDER_JSON")
                self.safe(report)

    def test_missing_data_or_multiple_results_are_blocked(self):
        for doc in (
            {"status": "REQUEST_SUCCEEDED", "Results": []},
            {"status": "REQUEST_SUCCEEDED", "Results": [{}, {}]},
            payload(data=[]),
        ):
            with self.subTest(doc=doc):
                report = check(raw(doc))
                self.assertEqual(report["state"], "LAB_BLS_CPI_U_CAPTURE_BLOCKED")
                self.safe(report)

    def test_bad_clock_or_server_skew_is_not_accepted(self):
        for at, server in (
            (datetime(2026, 11, 12, 19, 50), AT),
            (AT, AT - timedelta(minutes=4)),
            (AT, None),
        ):
            with self.subTest(at=at, server=server):
                report = check(at=at, server=server)
                self.assertEqual(report["reason"], "INVALID_BYTES_OR_CAPTURE_CLOCK")
                self.safe(report)

    def test_oversized_body_must_never_be_retained(self):
        report = check(b"x" * 520000)
        self.assertEqual(report["reason"], "INVALID_BYTES_OR_CAPTURE_CLOCK")
        self.assertIsNone(report["original_source_bytes_in_memory"])
        self.safe(report)

    def test_readonly_get_is_single_fixed_bls_endpoint_without_credentials(self):
        response = FakeResponse(raw())
        with patch(
            "atlasquant_trader_bls_cpi_u_official_bytes_readonly_lab.build_opener"
        ) as factory:
            factory.return_value.open.return_value = response
            report = fetch()
            factory.assert_called_once()
            self.assertIsInstance(factory.call_args.args[0], _NoRedirect)
            request = factory.return_value.open.call_args.args[0]
            self.assertEqual(request.get_method(), "GET")
            self.assertEqual(request.full_url, URL)
            self.assertNotIn("authorization", {
                k.lower() for k in request.headers})
        self.assertEqual(report["http_requests"], 1)
        self.assertTrue(report["http_get_completed"])
        self.assertFalse(report["original_release_at_independently_attested"])
        self.safe(report)

    def test_redirect_is_explicitly_disallowed(self):
        from urllib.request import Request
        req = Request(URL, headers={"Accept": "application/json"})
        handler = _NoRedirect()
        self.assertIsNone(handler.redirect_request(
            req, None, 302, "Found", {}, "https://evil.example/mirror"))

    def test_html_or_provider_rate_limit_response_blocks(self):
        for fake in (
            FakeResponse(b"<html>error</html>", content_type="text/html"),
            FakeResponse(raw(), status=429),
        ):
            with patch(
                "atlasquant_trader_bls_cpi_u_official_bytes_readonly_lab.build_opener"
            ) as factory:
                factory.return_value.open.return_value = fake
                report = fetch()
            self.assertEqual(report["state"], "LAB_BLS_CPI_U_CAPTURE_BLOCKED")
            self.assertEqual(report["http_requests"], 1)
            self.assertFalse(report["http_get_completed"])
            self.safe(report)

    def test_api_json_error_never_becomes_price_or_signal(self):
        with patch(
            "atlasquant_trader_bls_cpi_u_official_bytes_readonly_lab.build_opener"
        ) as factory:
            factory.return_value.open.return_value = FakeResponse(
                raw(payload(status="REQUEST_NOT_PROCESSED")))
            report = fetch()
        self.assertEqual(report["reason"],
                         "PROVIDER_STATUS_OR_SINGLE_SERIES_SHAPE_INVALID")
        self.assertFalse(report["http_get_completed"])
        self.safe(report)


if __name__ == "__main__":
    unittest.main()
