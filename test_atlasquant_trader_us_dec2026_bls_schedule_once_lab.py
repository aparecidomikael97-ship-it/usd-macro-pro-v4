"""Synthetic-only guard tests for the one-off official BLS schedule capture."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import unittest

import atlasquant_trader_us_dec2026_bls_schedule_once_lab as m

UTC = timezone.utc
MARK = datetime(2026, 11, 16, 16, 30, 12, tzinfo=UTC)


def html(*, cpi_date="Thursday, December 10, 2026",
         ppi_date="Tuesday, December 15, 2026",
         cpi_time="08:30 AM", ppi_time="08:30 AM",
         real_earnings=True, extra=""):
    rows = [
        ("Thursday, December 10, 2026", "08:30 AM",
         "Consumer Price Index for November 2026"),
        (cpi_date, cpi_time, "Real Earnings for November 2026"),
        (ppi_date, ppi_time, "Producer Price Index for November 2026"),
    ]
    if not real_earnings:
        rows.pop(1)
    def render(r):
        return "<tr>" + "".join("<td>" + s + "</td>" for s in r) + "</tr>"
    return ("<!DOCTYPE html><html><body><table>"
            + "".join(map(render, rows)) + extra
            + "</table></body></html>").encode("utf-8")


class FakeResponse:
    def __init__(self, *, raw=None, status=200, url=m.URL,
                 mime="text/html; charset=UTF-8", date=None,
                 encoding="identity"):
        self.status = status
        self.url = url
        self.body = html() if raw is None else raw
        self.headers = {
            "Content-Type": mime,
            "Content-Encoding": encoding,
            "Date": date or format_datetime(MARK, usegmt=True),
        }
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def geturl(self):
        return self.url
    def read(self, count):
        return self.body[:count]


class OpenOnce:
    def __init__(self, response=None):
        self.response = response or FakeResponse()
        self.calls = 0
    def __call__(self, request, *, timeout):
        self.calls += 1
        assert self.calls == 1, "NO_RETRY"
        assert request.full_url == m.URL and request.get_method() == "GET"
        assert timeout == 15
        return self.response


def clock(now=MARK):
    seq = iter([now, now + timedelta(seconds=1)])
    return lambda: next(seq)


class DecemberBlsScheduleTests(unittest.TestCase):
    def check_nogo(self, result):
        self.assertFalse(result["trade_authorized"])
        self.assertFalse(result["publishable"])
        self.assertIsNone(result["accuracy"])
        self.assertIsNone(result["usd_bias"])
        self.assertFalse(result["pre_event_consensus_authenticated"])
        self.assertFalse(result["publisher_first_seen_independently_attested"])
        self.assertFalse(result["changes_to_fx28_672_slots"])
        self.assertEqual(result["operational_bias"], "AGUARDAR")
        self.assertEqual(result["registered_fx_forecasts"], 0)
        self.assertEqual(result["mt5_calls"], 0)

    def test_01_calendar_three_exact_semantic_rows(self):
        out = m.inspect_dec2026_schedule_original_lab(raw_html=html())
        self.check_nogo(out)
        self.assertEqual(out["schedule_release_rows_reconciled"], 3)
        self.assertEqual(
            [e["scheduled_release_utc_calendar_claim"] for e in out["scheduled_rows"]],
            ["2026-12-10T13:30:00+00:00", "2026-12-10T13:30:00+00:00",
             "2026-12-15T13:30:00+00:00"])
        self.assertEqual(out["schedule_original_sha256"], sha256(html()).hexdigest())
        self.assertTrue(out["co_release_CPI_real_earnings_same_instant"])

    def test_02_missing_real_earnings_blocks(self):
        self.assertEqual(m.inspect_dec2026_schedule_original_lab(
            raw_html=html(real_earnings=False))["schedule_release_rows_reconciled"], 0)

    def test_03_shifted_real_earnings_day_blocks(self):
        self.assertEqual(m.inspect_dec2026_schedule_original_lab(
            raw_html=html(cpi_date="Friday, December 11, 2026")
        )["schedule_release_rows_reconciled"], 0)

    def test_04_shifted_ppi_day_blocks(self):
        self.assertEqual(m.inspect_dec2026_schedule_original_lab(
            raw_html=html(ppi_date="Wednesday, December 16, 2026")
        )["schedule_release_rows_reconciled"], 0)

    def test_05_wrong_cpi_or_ppi_clock_blocks(self):
        for value in ("08:31 AM", "09:30 AM"):
            self.assertEqual(m.inspect_dec2026_schedule_original_lab(
                raw_html=html(cpi_time=value))["schedule_release_rows_reconciled"], 0)
            self.assertEqual(m.inspect_dec2026_schedule_original_lab(
                raw_html=html(ppi_time=value))["schedule_release_rows_reconciled"], 0)

    def test_06_duplicate_target_row_rejected(self):
        extra = "<tr><td>Tuesday, December 15, 2026</td>" \
                "<td>08:30 AM</td><td>Producer Price Index for November 2026</td></tr>"
        self.assertEqual(m.inspect_dec2026_schedule_original_lab(
            raw_html=html(extra=extra))["schedule_release_rows_reconciled"], 0)

    def test_07_invalid_utf8_blocked(self):
        self.assertEqual(m.inspect_dec2026_schedule_original_lab(
            raw_html=html() + b"\xff")["schedule_release_rows_reconciled"], 0)

    def test_08_bad_or_oversized_bytes_blocked(self):
        for raw in (None, "not bytes", b"tiny", b"a" * (m.MAX_BYTES + 1)):
            self.assertEqual(m.inspect_dec2026_schedule_original_lab(
                raw_html=raw)["schedule_release_rows_reconciled"], 0)

    def test_09_no_explicit_optin_does_nothing(self):
        opener = OpenOnce()
        with TemporaryDirectory() as root:
            out = m.capture_dec2026_schedule_original_once_lab(
                allow_one_official_get=False, output_root=root,
                request_open=opener, clock=clock())
            self.check_nogo(out)
            self.assertEqual(opener.calls, 0)
            self.assertEqual(out["file_writes"], 0)
            self.assertEqual(list(Path(root).iterdir()), [])

    def test_10_mock_http_writes_verified_original_and_receipt(self):
        opener = OpenOnce()
        with TemporaryDirectory() as root:
            out = m.capture_dec2026_schedule_original_once_lab(
                allow_one_official_get=True, output_root=root,
                request_open=opener, clock=clock())
            self.check_nogo(out)
            self.assertTrue(out["original_html_locally_archived"], out)
            self.assertEqual(opener.calls, 1)
            self.assertEqual(out["file_writes"], 2)
            folder = Path(root) / out["archive_basename"]
            original = (folder / "original.html").read_bytes()
            receipt = json.loads((folder / "receipt.json").read_bytes())
            self.assertEqual(original, html())
            self.assertEqual(receipt["original_html_sha256"], sha256(original).hexdigest())
            self.assertEqual(receipt["schedule_release_rows_reconciled"], 3)
            self.assertFalse(receipt["consensus_and_forex_prediction_verified"])

    def test_11_http_403_never_writes(self):
        opener = OpenOnce(FakeResponse(status=403))
        with TemporaryDirectory() as root:
            out = m.capture_dec2026_schedule_original_once_lab(
                allow_one_official_get=True, output_root=root,
                request_open=opener, clock=clock())
            self.check_nogo(out)
            self.assertFalse(out["original_html_locally_archived"])
            self.assertEqual(list(Path(root).iterdir()), [])

    def test_12_redirect_or_mime_mismatch_never_writes(self):
        for response in (FakeResponse(url="https://bls.gov/other"),
                         FakeResponse(mime="application/json"),
                         FakeResponse(encoding="gzip")):
            with TemporaryDirectory() as root:
                out = m.capture_dec2026_schedule_original_once_lab(
                    allow_one_official_get=True, output_root=root,
                    request_open=OpenOnce(response), clock=clock())
                self.check_nogo(out)
                self.assertFalse(out["original_html_locally_archived"])
                self.assertEqual(list(Path(root).iterdir()), [])

    def test_13_http_date_outside_receipt_range_blocks(self):
        old = format_datetime(MARK - timedelta(days=2), usegmt=True)
        with TemporaryDirectory() as root:
            out = m.capture_dec2026_schedule_original_once_lab(
                allow_one_official_get=True, output_root=root,
                request_open=OpenOnce(FakeResponse(date=old)), clock=clock())
            self.assertEqual(out["reason"], "BLS_HTTP_DATE_OUTSIDE_CAPTURE_CLOCK_WINDOW")
            self.assertFalse(out["original_html_locally_archived"])

    def test_14_freeze_blocks_before_network(self):
        opener = OpenOnce()
        after = datetime(2026, 12, 10, 12, 30, 1, tzinfo=UTC)
        with TemporaryDirectory() as root:
            out = m.capture_dec2026_schedule_original_once_lab(
                allow_one_official_get=True, output_root=root,
                request_open=opener, clock=lambda: after)
            self.check_nogo(out)
            self.assertEqual(opener.calls, 0)
            self.assertEqual(out["file_writes"], 0)

    def test_15_invalid_output_directory_never_calls_network(self):
        opener = OpenOnce()
        with TemporaryDirectory() as root:
            out = m.capture_dec2026_schedule_original_once_lab(
                allow_one_official_get=True,
                output_root=str(Path(root) / "missing"),
                request_open=opener, clock=clock())
            self.assertEqual(opener.calls, 0)
            self.check_nogo(out)

    def test_16_wrong_live_release_row_blocks_physical_archive(self):
        opener = OpenOnce(FakeResponse(raw=html(ppi_date="Wednesday, December 16, 2026")))
        with TemporaryDirectory() as root:
            out = m.capture_dec2026_schedule_original_once_lab(
                allow_one_official_get=True, output_root=root,
                request_open=opener, clock=clock())
            self.assertEqual(out["reason"], "LIVE_BLS_SCHEDULE_ROWS_DO_NOT_MATCH_FROZEN_PLAN")
            self.assertEqual(list(Path(root).iterdir()), [])

    def test_17_no_m15_price_or_consensus_from_source(self):
        out = m.inspect_dec2026_schedule_original_lab(raw_html=html())
        self.check_nogo(out)
        self.assertNotIn("forex_win_rate", out)
        self.assertNotIn("broker_prices", out)
        self.assertNotIn("numerical_consensus", out)


    def test_18_real_bls_nested_layout_table_accepts_only_inner_rows(self):
        # The live BLS calendar is an actual table nested within an outer
        # layout table. This valid structure caused the first LAB run to
        # fail safely; the inner release rows must remain physical rows.
        raw = html().replace(b"<table>", b"<table><tr><td><table>", 1).replace(
            b"</table>", b"</table></td></tr></table>", 1)
        out = m.inspect_dec2026_schedule_original_lab(raw_html=raw)
        self.check_nogo(out)
        self.assertEqual(out["schedule_release_rows_reconciled"], 3)
        self.assertEqual(len(out["scheduled_rows"]), 3)

    def test_19_unmatched_table_row_blocks_instead_of_silent_recovery(self):
        bad = html().replace(b"</table>", b"</tr></table>")
        self.assertEqual(m.inspect_dec2026_schedule_original_lab(
            raw_html=bad)["schedule_release_rows_reconciled"], 0)



if __name__ == "__main__":
    unittest.main()
