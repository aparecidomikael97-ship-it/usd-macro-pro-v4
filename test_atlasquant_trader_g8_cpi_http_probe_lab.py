"""Offline probes with injected HTTP responses; no real network in tests."""
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from urllib.error import HTTPError
import unittest

from atlasquant_trader_g8_macro_asof_lab import CPI_ISSUER_HOSTS
from atlasquant_trader_g8_cpi_http_probe_lab import (
    MAX_BODY_BYTES, probe_g8_cpi_official_page_once_lab as probe,
)

EUROSTAT_URL = "https://ec.europa.eu/eurostat/web/products-euro-indicators/w/2-04112026-ap"
T0 = datetime(2026, 11, 10, 1, 0, 0, tzinfo=timezone.utc)
T1 = T0 + timedelta(seconds=2)


class FakeResponse:
    def __init__(self, body=b"synthetic official-looking bytes", *, url=EUROSTAT_URL,
                 status=200, ct="text/html;charset=UTF-8"):
        self.status = status
        self.body = body
        self.url = url
        self.headers = {"Content-Type": ct, "Date": "Tue, 10 Nov 2026 01:00:02 GMT"}

    def geturl(self):
        return self.url

    def read(self, limit):
        return self.body[:limit]

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class FakeOpener:
    def __init__(self, response):
        self.response = response
        self.called = 0

    def open(self, request, timeout):
        self.called += 1
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


def two_clocks(a=T0, b=T1):
    times = iter((a, b))
    return lambda: next(times)


class CPIHTTPProbeTests(unittest.TestCase):
    def assert_no_go(self, result):
        r = result.report
        self.assertEqual(r["operational_bias"], "AGUARDAR")
        for key in ("original_publisher_bytes_at_first_release_attested",
                    "issuer_identity_independently_attested",
                    "source_history_point_in_time_verified",
                    "collector_clock_independently_attested",
                    "cpi_value_semantically_verified", "trade_authorized",
                    "publishable", "worker_enabled", "scheduler_enabled"):
            self.assertFalse(r[key], key)
        self.assertEqual((r["file_writes"], r["new_cost_brl"]), (0, 0))

    def test_one_successful_response_binds_current_bytes_not_release_vintage(self):
        body = b"SYNTHETIC, NOT OFFICIAL HTML"
        opener = FakeOpener(FakeResponse(body))
        result = probe("EUR", EUROSTAT_URL, opener=opener, clock=two_clocks())
        self.assertEqual(result.report["state"],
                         "LAB_CURRENT_ISSUER_PAGE_HTTP_BYTES_CAPTURED_UNATTESTED")
        self.assertEqual(result.report["body_sha256"], sha256(body).hexdigest())
        self.assertEqual(result.report["body_bytes"], len(body))
        self.assertEqual(result.report["source_url_claim"], EUROSTAT_URL)
        self.assertEqual(result.body, body)
        self.assertFalse(result.report["default_tls_verification_requested"])
        self.assertEqual(opener.called, 1)
        self.assert_no_go(result)

    def test_all_eight_issuer_hosts_can_be_probed_with_injected_bytes(self):
        for currency, hosts in CPI_ISSUER_HOSTS.items():
            url = ("https://ec.europa.eu/eurostat/test" if currency == "EUR"
                   else f"https://{sorted(hosts)[0]}/cpi/test")
            with self.subTest(currency=currency):
                result = probe(currency, url,
                               opener=FakeOpener(FakeResponse(url=url)),
                               clock=two_clocks())
                self.assertIsNotNone(result.body)
                self.assert_no_go(result)

    def test_wrong_host_blocks_before_http_call(self):
        opener = FakeOpener(FakeResponse())
        result = probe("USD", EUROSTAT_URL, opener=opener, clock=two_clocks())
        self.assertEqual(result.report["reason"], "UNAPPROVED_CPI_ISSUER_URL")
        self.assertEqual(opener.called, 0)
        self.assert_no_go(result)

    def test_redirect_even_to_an_official_site_is_rejected(self):
        opener = FakeOpener(FakeResponse(url=EUROSTAT_URL + "?redirected=true"))
        result = probe("EUR", EUROSTAT_URL, opener=opener, clock=two_clocks())
        self.assertEqual(result.report["reason"], "STATUS_OR_REDIRECT_NOT_ACCEPTED")
        self.assertIsNone(result.body)
        self.assert_no_go(result)

    def test_403_is_blocked_without_retry_or_cookie_bypass(self):
        opener = FakeOpener(HTTPError(EUROSTAT_URL, 403, "Forbidden", {}, None))
        result = probe("EUR", EUROSTAT_URL, opener=opener, clock=two_clocks())
        self.assertEqual(result.report["response_status"], 403)
        self.assertEqual(result.report["reason"], "ISSUER_HTTP_STATUS_NOT_200_NO_BYPASS")
        self.assertEqual(opener.called, 1)
        self.assert_no_go(result)

    def test_wrong_mime_type_and_oversize_are_not_successes(self):
        for response in (FakeResponse(ct="application/json"),
                         FakeResponse(body=b"x" * (MAX_BODY_BYTES + 1))):
            result = probe("EUR", EUROSTAT_URL,
                           opener=FakeOpener(response), clock=two_clocks())
            self.assertEqual(result.report["state"], "LAB_HTTPS_PROBE_BLOCKED")
            self.assertIsNone(result.body)
            self.assert_no_go(result)

    def test_reversed_or_naive_collector_clock_is_invalid(self):
        for clock in (two_clocks(T1, T0),
                      two_clocks(datetime(2026, 11, 10), datetime(2026, 11, 10))):
            result = probe("EUR", EUROSTAT_URL, opener=FakeOpener(FakeResponse()), clock=clock)
            self.assertEqual(result.report["state"], "LAB_HTTPS_PROBE_BLOCKED")
            self.assert_no_go(result)

    def test_one_byte_difference_is_not_authenticated_economic_revision(self):
        first = probe("EUR", EUROSTAT_URL,
                      opener=FakeOpener(FakeResponse(body=b"abc")), clock=two_clocks())
        second = probe("EUR", EUROSTAT_URL,
                       opener=FakeOpener(FakeResponse(body=b"abd")), clock=two_clocks())
        self.assertNotEqual(first.report["body_sha256"], second.report["body_sha256"])
        self.assertFalse(first.report["original_publisher_bytes_at_first_release_attested"])
        self.assertFalse(second.report["original_publisher_bytes_at_first_release_attested"])
        self.assert_no_go(first)
        self.assert_no_go(second)


if __name__ == "__main__":
    unittest.main()
