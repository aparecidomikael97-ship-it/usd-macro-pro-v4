"""Synthetic-only test suite: no real bank HTML included in repository."""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import unittest

from atlasquant_trader_us_ppi_pre_event_preview_lab import (
    LocalCaptureClaim, URL, EVENT_RELEASE_UTC,
    inspect_ppi_pre_event_snapshot_lab as inspect,
)
UTC = timezone.utc
START = datetime(2026, 11, 11, 0, 58, 10, tzinfo=UTC)
END = datetime(2026, 11, 11, 0, 58, 12, tzinfo=UTC)
AS_OF = datetime(2026, 11, 11, 1, 0, tzinfo=UTC)


def html(*, head="0.4", core="0.3", when="Nov 13", unit="M/M % Chg.",
         header="Consensus Forecast", previous="1.3", duplicate=False):
    row1 = (f"<tr><td>{when}</td><td>8:30</td><td></td><td>PPI Final Demand</td>"
            f"<td>Oct</td><td>{unit}</td><td>{head}</td><td>{previous}</td></tr>")
    row2 = (f"<tr><td>Nov 13</td><td>8:30</td><td></td><td>PPI Ex Food and Energy</td>"
            f"<td>Oct</td><td>{unit}</td><td>{core}</td><td>0.7</td></tr>")
    title = "<tr><td colspan='8'>Upcoming Economic Releases and Events: Nov 9 - 13, 2026</td></tr>"
    headings = (f"<tr><td>Release Date</td><td>Time*</td><td></td>"
                f"<td>Economic Indicator/Event</td><td>Data for Period</td>"
                f"<td>Units</td><td>{header}</td><td>Last Period</td></tr>")
    raw = ("<html><body><table>" + title + headings + row1 + row2
           + (row1 if duplicate else "") + "</table>" + "x"*2100 + "</body></html>")
    return raw.encode("cp1252")


def rec(body):
    return LocalCaptureClaim(URL, 200, "text/html", START, END,
        "Wed, 11 Nov 2026 00:58:18 GMT",
        "Fri, 06 Nov 2026 18:00:39 GMT",len(body),sha256(body).hexdigest())


class TDPreEventPPIResearchLabTests(unittest.TestCase):
    def get(self, body=None, claim=None, at=AS_OF):
        body = html() if body is None else body
        return inspect(raw_html=body, receipt=rec(body) if claim is None else claim, as_of_utc=at)

    def no_trade(self, v):
        self.assertEqual(v["operational_bias"], "AGUARDAR")
        for field in ("source_provenance_independently_attested",
              "publisher_first_available_instant_attested",
              "analyst_poll_membership_and_methodology_verified",
              "historical_backtest_point_in_time_attested", "trade_authorized",
              "publishable", "worker_enabled", "scheduler_enabled"):
            self.assertIs(v[field], False, field)
        for field in ("official_actual_available", "ppi_surprise", "usd_bias",
                      "eurusd_bias", "calibrated_probability"):
            self.assertIsNone(v[field], field)
        self.assertEqual((v["http_requests"],v["new_cost_brl"]),(0,0))

    def test_matching_october_2026_ppi_headline_and_core_consensus(self):
        v=self.get()
        self.assertEqual(v["state"],"LAB_PRE_EVENT_PPI_CONSENSUS_ARCHIVED_LOCAL_NO_TRADE")
        self.assertEqual((v["headline_consensus_mom_pct"],v["core_consensus_mom_pct"]),("0.4","0.3"))
        self.assertEqual((v["headline_previous_mom_pct"],v["core_previous_mom_pct"]),("1.3","0.7"))
        self.assertTrue(v["ready_for_later_retrospective_comparison_lab"])
        self.assertTrue(v["local_pre_event_http_capture_claim_checks_pass"])
        self.no_trade(v)

    def test_falsified_body_sha_cannot_pass(self):
        b=html();x=self.get(body=b+b"!",claim=rec(b));self.assertEqual(x["reason"],"HTML_BODY_LENGTH_OR_DIGEST_INVALID");self.no_trade(x)

    def test_wrong_source_and_http_status(self):
        b=html()
        for field,value in (("source_url","https://not-bank.example"),("http_status",403),("http_status",True),
                            ("content_type","application/json")):
            with self.subTest(field=field):
                x=self.get(body=b,claim=replace(rec(b),**{field:value}))
                self.assertEqual(x["reason"],"INVALID_HTTP_STATUS_OR_SOURCE_METADATA")
                self.no_trade(x)

    def test_not_after_release(self):
        b=html();x=self.get(body=b,claim=replace(rec(b),finished_at_utc=EVENT_RELEASE_UTC),at=EVENT_RELEASE_UTC)
        self.assertEqual(x["reason"],"INVALID_OR_POST_EVENT_CAPTURE_TIMELINE");self.no_trade(x)

    def test_refuse_future_capture_cutoff(self):
        x=self.get(at=START);self.assertEqual(x["reason"],"INVALID_OR_POST_EVENT_CAPTURE_TIMELINE");self.no_trade(x)

    def test_server_date_drift_beyond_two_minutes(self):
        b=html();x=self.get(body=b,claim=replace(rec(b),server_date_http="Wed, 11 Nov 2026 01:08:18 GMT"))
        self.assertEqual(x["reason"],"INVALID_OR_POST_EVENT_CAPTURE_TIMELINE");self.no_trade(x)

    def test_bad_modified_time_not_accepted(self):
        b=html();x=self.get(body=b,claim=replace(rec(b),last_modified_http="Fri, 13 Nov 2026 13:31:00 GMT"))
        self.assertEqual(x["reason"],"INVALID_OR_POST_EVENT_CAPTURE_TIMELINE");self.no_trade(x)

    def test_metric_mismatch_and_calendar_day(self):
        for b in (html(unit="Y/Y % Chg."),html(when="Nov 12")):
            x=self.get(b);self.assertEqual(x["reason"],"PPI_DATE_PERIOD_OR_METRIC_MISMATCH");self.no_trade(x)

    def test_consensus_and_last_period_not_switched(self):
        b=html(header="Last Period");x=self.get(b)
        self.assertEqual(x["reason"],"CONSENSUS_TABLE_HEADER_NOT_EXACT");self.no_trade(x)

    def test_duplicate_actual_row_blocks(self):
        x=self.get(html(duplicate=True));self.assertEqual(x["reason"],"PPI_ROW_MISSING_OR_DUPLICATED");self.no_trade(x)

    def test_out_of_range_or_nonfinite_number(self):
        for v in ("NaN","Infinity","1200","-0.3","", "0,3"):
            with self.subTest(v=v):
                x=self.get(html(core=v));self.assertEqual(x["reason"],"PPI_CONSENSUS_AND_PREVIOUS_INVALID");self.no_trade(x)

    def test_short_body_and_wrong_hash_format(self):
        b=b"<html>no ppi</html>";x=self.get(b)
        self.assertEqual(x["reason"],"HTML_BODY_LENGTH_OR_DIGEST_INVALID");self.no_trade(x)
        b=html();x=self.get(body=b,claim=replace(rec(b),body_sha256="wrong"))
        self.assertEqual(x["reason"],"HTML_BODY_LENGTH_OR_DIGEST_INVALID");self.no_trade(x)

    def test_html_unknown_or_no_week(self):
        b=html().replace(b"Nov 9 - 13, 2026",b"Nov 9 - 12, 2026")
        x=self.get(b);self.assertEqual(x["reason"],"EXPECTED_WEEK_NOT_PRESENT");self.no_trade(x)

    def test_capture_inspection_can_occur_after_release_but_snapshot_must_be_prior(self):
        x=self.get(at=EVENT_RELEASE_UTC+timedelta(days=1))
        self.assertTrue(x["ready_for_later_retrospective_comparison_lab"])
        self.assertIsNone(x["official_actual_available"]);self.no_trade(x)

    def test_unsupported_timestamp_and_missing_input(self):
        for t in (None,"2026-11-11",AS_OF.replace(tzinfo=None)):
            x=self.get(at=t);self.assertEqual(x["reason"],"INVALID_CLOCK_OR_CAPTURE_CLAIM");self.no_trade(x)


if __name__ == "__main__":
    unittest.main()