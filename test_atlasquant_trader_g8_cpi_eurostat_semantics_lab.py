"""Pure synthetic HTML and temporary archive tests; no HTTP/MT5/trading."""
from hashlib import sha256
import json
from pathlib import Path
import tempfile
import unittest

from atlasquant_trader_g8_cpi_eurostat_semantics_lab import (
    interpret_eurostat_flash_html_lab as parse,
    interpret_eurostat_flash_archive_lab as verify_parse,
)
from atlasquant_trader_g8_cpi_local_archive_lab import archive_one_g8_cpi_current_page_lab
from atlasquant_trader_g8_cpi_http_probe_lab import HTTPProbeLabResult

URL = "https://ec.europa.eu/eurostat/web/products-euro-indicators/w/2-04112026-ap"


def html_doc(*, headline="4.0", og="4.0", table="4.0e", period="October 2026",
             label=None, stamp="2026-11-04T10:00:00Z", duplicate=False):
    label = label or "Flash estimate - " + period
    h = f'<h1 class="ecl-page-header__title">Euro area annual inflation up to {headline}%</h1>'
    if duplicate:
        h += h
    return (f'''<!doctype html><html><head>
      <meta property="article:published_time" content="{stamp}">
      <meta property="og:description" content="Overview Euro area annual inflation is expected to be {og}% in {period}, up from 3.8% in September according to a flash estimate from Eurostat. Then more text.">
      </head><body><span class="ecl-label ecl-label--highlight">{label}</span>{h}
      <table><tr><th>Euro area annual inflation and its components (%)</th></tr>
      <tr><th>Weights</th><th>Annual rate</th><th>Monthly rate</th></tr>
      <tr><th>2026</th><th>Oct 25</th><th>May 26</th><th>Jun 26</th><th>Jul 26</th><th>Aug 26</th><th>Sept 26</th><th>Oct 26</th><th>Oct 26</th></tr>
      <tr><th class="vertical-header"><p><strong>All-items HICP</strong></p></th>
      <td>1000.0</td><td>2.1</td><td>3.2</td><td>2.8</td><td>2.9</td><td>3.2</td><td>3.8</td><td>{table}</td><td>0.4e</td></tr>
      </table></body></html>''').encode("utf-8")


def archive_fixture(dirpath: str, body: bytes):
    report = {
        "state": "LAB_CURRENT_ISSUER_PAGE_HTTP_BYTES_CAPTURED_UNATTESTED",
        "source_url_claim": URL, "final_url_observed": URL,
        "response_status": 200, "body_bytes": len(body),
        "body_sha256": sha256(body).hexdigest(), "content_type": "text/html",
        "local_started_utc_claim": "2026-11-10T01:12:51+00:00",
        "local_finished_utc_claim": "2026-11-10T01:12:54+00:00",
    }
    return archive_one_g8_cpi_current_page_lab(
        "EUR", URL, "2026-10", "FLASH", directory=dirpath,
        probe=lambda _currency, _source: HTTPProbeLabResult(report, body))


class EurostatSemanticsLabTests(unittest.TestCase):
    def assert_readonly_no_bias(self, r):
        self.assertEqual(r["operational_bias"], "AGUARDAR")
        self.assertEqual(r["file_writes"], 0)
        self.assertEqual(r["new_cost_brl"], 0)
        for key in ("value_independently_verified", "issuer_first_release_authenticated",
                    "clock_independently_authenticated", "historical_point_in_time_eligible",
                    "can_feed_macro_bias", "trade_authorized", "publishable",
                    "scheduler_enabled", "worker_enabled"):
            self.assertIs(r[key], False, key)

    def test_same_document_three_way_extraction_is_documentary_only(self):
        r = parse(html_doc(), period="2026-10")
        self.assertEqual(r["state"], "LAB_EUR_CPI_FLASH_DOCUMENTARY_EXTRACTED_UNATTESTED")
        self.assertEqual(r["documentary_cpi_yoy_percent"], "4.0")
        self.assertEqual(r["documentary_previous_yoy_percent"], "3.8")
        self.assertEqual(r["source_publication_timestamp_claim"], "2026-11-04T10:00:00Z")
        self.assertTrue(r["same_document_value_consistent"])
        self.assertFalse(r["local_archive_integrity_verified"])
        self.assert_readonly_no_bias(r)

    def test_visual_markups_do_not_change_extracted_cells(self):
        body = html_doc().replace(b"<td>4.0e</td>", b"<td><p><strong>4.0e</strong></p></td>")
        self.assertTrue(parse(body, period="2026-10")["same_document_value_consistent"])

    def test_mismatched_rates_fail_closed(self):
        for kw in ({"headline": "4.1"}, {"og": "4.1"}, {"table": "4.1e"},
                   {"table": "4.0"}, {"table": "bad"}):
            with self.subTest(kw=kw):
                r = parse(html_doc(**kw), period="2026-10")
                self.assertEqual(r["state"], "LAB_EUR_CPI_SEMANTIC_BLOCKED")
                self.assert_readonly_no_bias(r)

    def test_different_reference_period_and_stage_fail_closed(self):
        for kw in ({"period": "September 2026"}, {"label": "Final results - October 2026"}):
            with self.subTest(kw=kw):
                self.assertFalse(parse(html_doc(**kw), period="2026-10")["same_document_value_consistent"])
        self.assertFalse(parse(html_doc(), period="2026-11")["same_document_value_consistent"])

    def test_duplicate_heads_fail_closed(self):
        self.assertFalse(parse(html_doc(duplicate=True), period="2026-10")["same_document_value_consistent"])

    def test_missing_table_and_wrong_header_fail_closed(self):
        body = html_doc()
        for replacement in (b"No HICP", b"Monthly prices"):
            with self.subTest(replacement=replacement):
                edited = body.replace(b"All-items HICP", replacement)
                self.assertFalse(parse(edited, period="2026-10")["same_document_value_consistent"])
        self.assertFalse(parse(body.replace(b"Sept 26", b"Sept 25"), period="2026-10")["same_document_value_consistent"])

    def test_missing_or_bad_publication_metadata_fail_closed(self):
        for stamp in ("unknown", "2026-12-99T10:00:00Z", "2026-11-04 10:00:00"):
            with self.subTest(stamp=stamp):
                self.assertFalse(parse(html_doc(stamp=stamp), period="2026-10")["same_document_value_consistent"])

    def test_non_utf8_and_invalid_inputs_fail_closed(self):
        for body, period in ((b"\xff", "2026-10"), (b"", "2026-10"),
                             (html_doc(), "2026-Q3"), (html_doc(), None),
                             (b"x" * 1048577, "2026-10")):
            with self.subTest(period=period):
                self.assertFalse(parse(body, period=period)["same_document_value_consistent"])

    def test_archived_synthetic_bytes_are_parsed_without_any_new_writes(self):
        with tempfile.TemporaryDirectory() as d:
            archived = archive_fixture(d, html_doc())
            files_before = sorted(Path(d).iterdir())
            r = verify_parse(archived["manifest_path"])
            self.assertTrue(r["local_archive_integrity_verified"])
            self.assertTrue(r["same_document_value_consistent"])
            self.assertEqual(sorted(Path(d).iterdir()), files_before)
            self.assert_readonly_no_bias(r)

    def test_tampering_archive_body_fails_integrity_before_parsing(self):
        with tempfile.TemporaryDirectory() as d:
            a = archive_fixture(d, html_doc())
            Path(a["body_path"]).write_bytes(html_doc(headline="5.0"))
            r = verify_parse(a["manifest_path"])
            self.assertFalse(r["local_archive_integrity_verified"])
            self.assertFalse(r["same_document_value_consistent"])
            self.assert_readonly_no_bias(r)

    def test_wrong_currency_and_url_in_manifest_block(self):
        for key, value in (("currency", "USD"), ("source_url", "https://other.example/x"),
                           ("publication_stage_claim", "FINAL"), ("reference_period_claim", "2026-11")):
            with self.subTest(key=key), tempfile.TemporaryDirectory() as d:
                a = archive_fixture(d, html_doc())
                manifest_path = Path(a["manifest_path"])
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                manifest[key] = value
                manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
                self.assertFalse(verify_parse(manifest_path)["same_document_value_consistent"])


if __name__ == "__main__":
    unittest.main()
