"""Synthetic tests of Trading Economics calendar column boundaries and PPI scope."""
import unittest
from dataclasses import replace
from datetime import datetime,timezone,timedelta
from hashlib import sha256
from atlasquant_trader_us_ppi_te_second_consensus_lab import (
    SOURCE,EVENT,Capture,inspect_te_ppi_snapshot_lab as inspect
)
UTC=timezone.utc
START=datetime(2026,11,11,1,15,51,tzinfo=UTC)
END=START+timedelta(seconds=3)
NOW=END+timedelta(hours=1)
RENDER=END-timedelta(seconds=40)
DATE="Wed, 11 Nov 2026 01:16:00 GMT"

def fixture(h="0.4%",c="0.3%",own="0.3%",actual="",
            date="2026-11-13",head="Actual Previous Consensus Forecast"):
    cells=head.split()
    th="".join("<th>"+s+"</th>" for s in cells)
    def row(url,name,previous,consensus,forecast):
        return (f'<tr data-url="{url}" data-event="test" data-country="united states">'
                f'<td class=" {date}">01:30 PM</td>'
                f'<td><table><tr><td>US</td></tr></table></td>'
                f'<td>{name} <span>OCT</span></td>'
                f'<td><span id="actual">{actual}</span></td>'
                f'<td><span id="previous">{previous}</span></td>'
                f'<td><span id="consensus">{consensus}</span></td>'
                f'<td><span id="forecast">{forecast}</span></td>'
                f'<td></td><td></td><td></td></tr>')
    text=("<html><body><table><thead><tr>"+th+"</tr></thead>"+
          row("/united-states/producer-price-inflation-mom","PPI MoM","1.3%",h,own)+
          row("/united-states/core-producer-prices-mom","Core PPI MoM","0.7%",c,"0.3%")+
          "</table></body></html>")
    return ("<html><body>"+"x"*1200+text+"</body></html>").encode()

def cap(raw):
    return Capture(SOURCE,200,"text/html",START,END,DATE,RENDER,
                   sha256(raw).hexdigest(),len(raw))

class TestPPISecondPublisher(unittest.TestCase):
    def run_case(self, raw=None, rec=None, now=NOW):
        body=fixture() if raw is None else raw
        return inspect(raw_html=body,capture=cap(body) if rec is None else rec,as_of_utc=now)
    def never_live(self,v):
        self.assertEqual(v["operational_bias"],"AGUARDAR")
        self.assertFalse(v["trade_authorized"])
        self.assertFalse(v["publishable"])
        self.assertIsNone(v["market_direction"])
        self.assertIsNone(v["ppi_actual"])
        self.assertIsNone(v["ppi_surprise"])
        self.assertFalse(v["original_publisher_timestamp_independently_attested"])
        self.assertFalse(v["poll_methodology_independently_verified"])
    def test_columns_distinct_and_correct(self):
        v=self.run_case()
        self.assertEqual(v["state"],"LAB_TE_PRE_EVENT_CONSENSUS_AND_OWN_FORECAST_DISTINGUISHED")
        self.assertEqual(v["headline_consensus_mom_pct"],"0.4")
        self.assertEqual(v["headline_te_own_forecast_mom_pct"],"0.3")
        self.assertEqual(v["core_consensus_mom_pct"],"0.3")
        self.assertEqual(v["headline_previous_mom_pct"],"1.3")
        self.assertTrue(v["both_consensus_and_forecast_separate"])
        self.never_live(v)
    def test_missing_actual_required(self):
        v=self.run_case(raw=fixture(actual="0.9%"))
        self.assertEqual(v["state"],"LAB_TE_PPI_SOURCE_BLOCKED")
        self.never_live(v)
    def test_wrong_table_header_refused(self):
        v=self.run_case(raw=fixture(head="Actual Previous Forecast Consensus"))
        self.assertEqual(v["reason"],"EVENT_ROWS_OR_COLUMN_HEADER_MISSING")
        self.never_live(v)
    def test_after_event_snapshot_cannot_leak(self):
        raw=fixture()
        r=replace(cap(raw),finished_utc=EVENT, started_utc=EVENT-timedelta(seconds=1))
        v=self.run_case(raw=raw,rec=r,now=EVENT+timedelta(hours=1))
        self.assertEqual(v["reason"],"FUTURE_OR_POST_EVENT_SNAPSHOT")
        self.never_live(v)
    def test_wrong_day_no_promotion(self):
        v=self.run_case(raw=fixture(date="2026-11-12"))
        self.assertEqual(v["reason"],"UNEXPECTED_PPI_DATE_PERIOD_ACTUAL_OR_METRIC")
        self.never_live(v)
    def test_digest_changed_fails(self):
        raw=fixture()
        changed=raw+b"tampered"
        v=self.run_case(raw=changed,rec=cap(raw))
        self.assertEqual(v["reason"],"HTML_SIZE_OR_HASH_MISMATCH")
        self.never_live(v)
    def test_source_http_403_rejected(self):
        raw=fixture()
        for rec in (replace(cap(raw),source_url="https://other.example/calendar"),
                    replace(cap(raw),http_status=403),
                    replace(cap(raw),content_type="application/json"),
                    replace(cap(raw),http_status=True)):
            with self.subTest(rec=rec):
                v=self.run_case(raw=raw,rec=rec)
                self.assertEqual(v["reason"],"SOURCE_OR_HTTP_CLAIM_INVALID")
                self.never_live(v)
    def test_bad_or_nonfinite_pct(self):
        for consensus in ("NaN","20.1%","0.4","-0.4%"):
            with self.subTest(consensus=consensus):
                v=self.run_case(raw=fixture(h=consensus))
                self.assertEqual(v["reason"],"PPI_CONSENSUS_PREVIOUS_OR_FORECAST_INVALID")
                self.never_live(v)
    def test_duplicate_row_refused(self):
        raw=fixture()
        x=b'<tr data-url="/united-states/producer-price-inflation-mom"><td>duplicated</td></tr>'
        v=self.run_case(raw=raw.replace(b"</table></body></html>",x+b"</table></body></html>"))
        self.assertEqual(v["reason"],"EVENT_ROWS_OR_COLUMN_HEADER_MISSING")
        self.never_live(v)
    def test_changed_core_definition_rejected(self):
        raw=fixture()
        v=self.run_case(raw=raw.replace(b"Core PPI MoM",b"PPI Ex Food Energy Trade MoM"))
        self.assertEqual(v["reason"],"UNEXPECTED_PPI_DATE_PERIOD_ACTUAL_OR_METRIC")
        self.never_live(v)
    def test_not_evidence_if_future_as_of(self):
        raw=fixture()
        v=self.run_case(raw=raw,now=START-timedelta(seconds=1))
        self.assertEqual(v["reason"],"FUTURE_OR_POST_EVENT_SNAPSHOT")
        self.never_live(v)
    def test_bad_server_clock(self):
        raw=fixture()
        v=self.run_case(raw=raw,rec=replace(cap(raw),response_date_http="Thu, 12 Nov 2026 01:16:00 GMT"))
        self.assertEqual(v["reason"],"FUTURE_OR_POST_EVENT_SNAPSHOT")
        self.never_live(v)

if __name__=="__main__":
    unittest.main()
