"""Synthetic-only prospective CPI/PPI TD/TE semantic research tests."""
from __future__ import annotations
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import unittest

from atlasquant_trader_us_dec2026_consensus_semantic_candidate_lab import (
    inspect_dec2026_consensus_semantic_candidate_lab as inspect,
)
from atlasquant_trader_us_dec2026_pre_event_consensus_custody_lab import EVENTS
import test_atlasquant_trader_us_dec2026_pre_event_consensus_custody_lab as source_fixture

UTC=timezone.utc
CPI="US_CPI_NOV2026"
PPI="US_PPI_NOV2026"
ROOT={
 CPI:dict(short="Dec 10", date="2026-12-10",
          title="Upcoming Economic Releases and Events: Dec 7 - 11, 2026",
          td_head="CPI All Items",td_core="CPI Ex Food and Energy",
          te_head="Inflation Rate MoM NOV",te_core="Core Inflation Rate MoM NOV",
          url_head="/united-states/inflation-rate-mom",
          url_core="/united-states/core-inflation-rate-mom"),
 PPI:dict(short="Dec 15",date="2026-12-15",
          title="Upcoming Economic Releases and Events: Dec 14 - 18, 2026",
          td_head="PPI Final Demand",td_core="PPI Ex Food and Energy",
          te_head="PPI MoM NOV",te_core="Core PPI MoM NOV",
          url_head="/united-states/producer-price-inflation-mom",
          url_core="/united-states/core-producer-prices-mom"),
}
RELEASE={root:dt for root,_,_,dt in EVENTS}
POST=datetime(2026,12,17,tzinfo=UTC)

def td_html(root=CPI, *, head="0.4",core="0.3",prev="0.2",prev_core="0.1",
            day=None,period="Nov",unit="M/M % Chg.",title=None,
            header="Consensus Forecast",duplicate=False,head_name=None,hh="8:30"):
    s=ROOT[root]
    def row(name,value,prior):
        return (f"<tr><td>{s['short'] if day is None else day}</td><td>{hh}</td>"
                f"<td></td><td>{name}</td><td>{period}</td><td>{unit}</td>"
                f"<td>{value}</td><td>{prior}</td></tr>")
    top=("<tr><td>Release Date</td><td>Time*</td><td></td>"
         "<td>Economic Indicator/Event</td><td>Data for Period</td><td>Units</td>"
         f"<td>{header}</td><td>Last Period</td></tr>")
    h=row(head_name or s["td_head"],head,prev)
    c=row(s["td_core"],core,prev_core)
    raw=("<html><body><table><tr><td>"+
         (s["title"] if title is None else title)+
         "</td></tr>"+top+h+c+(h if duplicate else "")+
         "</table>"+("PROVISIONAL SYNTHETIC NOT A REAL TD ECONOMICS SNAPSHOT "*50)+
         "</body></html>")
    return raw.encode("cp1252")

def te_html(root=CPI, *, head="0.4%",core="0.3%",prev="0.2%",
            prev_core="0.1%",own="0.5%",actual="",date=None,
            head_name=None,head_url=None,duplicate=False,
            headings=("Actual","Previous","Consensus","Forecast")):
    s=ROOT[root]
    def row(route,label,prior,consensus,forecast):
        return (
            f'<tr data-url="{route}" data-event="mock" data-country="united states">'
            f'<td class=" {s["date"] if date is None else date}">01:30 PM</td>'
            f'<td><table><tr><td>US</td></tr></table></td>'
            f'<td>{label}</td><td>{actual}</td>'
            f'<td>{prior}</td><td>{consensus}</td><td>{forecast}</td>'
            "<td></td><td></td><td></td></tr>")
    h=row(head_url or s["url_head"],head_name or s["te_head"],prev,head,own)
    c=row(s["url_core"],s["te_core"],prev_core,core,"0.6%")
    hdr="".join("<th>"+v+"</th>" for v in headings)
    return ("<html><body><table><thead><tr>"+hdr+"</tr></thead>"+h+c+
            (h if duplicate else "")+"</table>"+
            "PROVISIONAL SYNTHETIC NOT REAL TRADING ECONOMICS SNAPSHOT "*50+
            "</body></html>").encode()

def original(root,provider,html=None):
    body=html if html is not None else (
        td_html(root) if provider=="TD_ECONOMICS" else te_html(root))
    x=source_fixture.sample(root=root,provider=provider)
    return replace(x,html_original_bytes=body,
                   original_sha256_claim=sha256(body).hexdigest())

def pair(root=CPI,*,td=None,te=None):
    return (original(root,"TD_ECONOMICS",td),
            original(root,"TRADING_ECONOMICS",te))

def replay(items=(),at=POST):
    return inspect(source_snapshots=items,inspected_at_utc=at)

class DecemberSemanticCandidateTests(unittest.TestCase):
    def safety(self,r):
        self.assertEqual(r["schema"],"ATLASQUANT_US_DEC2026_CONSENSUS_SEMANTIC_CANDIDATE_LAB_V1")
        self.assertEqual(r["frozen_economic_event_denominator"],2)
        self.assertEqual([x["event_root"] for x in r["events"]],[CPI,PPI])
        self.assertEqual(r["operational_bias"],"AGUARDAR")
        self.assertFalse(r["trade_authorized"])
        self.assertFalse(r["publishable"])
        self.assertFalse(r["fx28_original_672_slots_modified"])
        self.assertEqual(r["economic_consensus_pre_event_independently_authenticated"],0)
        self.assertEqual(r["registered_directional_fx_predictions"],0)
        self.assertEqual(r["independent_fx_oos_trials"],0)
        self.assertIsNone(r["win_rate"])
        self.assertIsNone(r["fx_bias"])
        self.assertIsNone(r["calibrated_probability"])
        self.assertEqual((r["http_requests"],r["file_writes"],r["mt5_calls"]),(0,0,0))
        for row in r["events"]:
            self.assertFalse(row["source_semantic_schema_approved_on_real_december_html"])
            self.assertFalse(row["publisher_first_seen_independently_authenticated"])
            self.assertFalse(row["provider_poll_methodology_independently_authenticated"])
            self.assertFalse(row["consensus_eligible_for_fx_prediction"])
            self.assertFalse(row["independent_validated_fx_forecast"])
    def good(self,items=(),at=POST):
        r=replay(items,at)
        self.safety(r)
        self.assertEqual(r["state"],"LAB_DEC2026_TWO_SOURCE_PROVISIONAL_SEMANTICS_ONLY_HARD_NO_GO")
        return r
    def blocked(self,items=(),at=POST):
        r=replay(items,at)
        self.safety(r)
        self.assertEqual(r["state"],"LAB_DEC2026_CONSENSUS_SEMANTICS_BLOCKED_HARD_NO_GO")
        self.assertEqual(r["local_two_source_candidate_event_count"],0)
        for row in r["events"]:
            self.assertIsNone(row["provisional_consensus_headline_mom_sa_pct"])
        return r

    def test_01_two_roots_no_documents_no_pre_event_forecast(self):
        self.assertEqual(self.good()["local_two_source_candidate_event_count"],0)
    def test_02_cpi_two_sources_same_mom_research_only(self):
        r=self.good(pair(CPI))
        self.assertEqual(r["local_two_source_candidate_event_count"],1)
        self.assertEqual(r["events"][0]["provisional_consensus_headline_mom_sa_pct"],"0.4")
        self.assertEqual(r["events"][0]["provisional_consensus_core_mom_sa_pct"],"0.3")
        self.assertEqual(r["events"][0]["td_previous_headline_mom_pct"],"0.2")
        self.assertEqual(r["events"][0]["te_provider_forecast_headline_mom_pct"],"0.5")
    def test_03_ppi_two_sources_reference_november(self):
        r=self.good(pair(PPI))
        self.assertEqual(r["events"][1]["provisional_consensus_headline_mom_sa_pct"],"0.4")
        self.assertEqual(r["events"][1]["provisional_consensus_core_mom_sa_pct"],"0.3")
    def test_04_four_source_snapshots_are_only_two_events(self):
        r=self.good(pair(CPI)+pair(PPI))
        self.assertEqual(r["local_two_source_candidate_event_count"],2)
        self.assertEqual(r["independent_fx_oos_trials"],0)
    def test_05_td_alone_not_enough(self):
        self.assertEqual(self.good((original(CPI,"TD_ECONOMICS"),))
                         ["local_two_source_candidate_event_count"],0)
    def test_06_te_alone_not_enough(self):
        self.assertEqual(self.good((original(CPI,"TRADING_ECONOMICS"),))
                         ["local_two_source_candidate_event_count"],0)
    def test_07_future_capture_invisible(self):
        a,b=pair()
        r=self.good((a,b),at=a.finished_at_utc-timedelta(microseconds=1))
        self.assertEqual(r["local_two_source_candidate_event_count"],0)
    def test_08_candidate_visible_exactly_at_last_capture(self):
        a,b=pair()
        r=self.good((a,b),at=max(a.finished_at_utc,b.finished_at_utc))
        self.assertEqual(r["local_two_source_candidate_event_count"],1)
    def test_09_own_forecast_not_confused_with_consensus(self):
        r=self.good(pair(te=te_html(own="0.9%")))
        self.assertEqual(r["events"][0]["provisional_consensus_headline_mom_sa_pct"],"0.4")
        self.assertEqual(r["events"][0]["te_provider_forecast_headline_mom_pct"],"0.9")
    def test_10_swapped_te_headers_block(self):
        self.blocked(pair(te=te_html(headings=("Actual","Previous","Forecast","Consensus"))))
    def test_11_pre_event_te_actual_nonempty_block(self):
        self.blocked(pair(te=te_html(actual="0.7%")))
    def test_12_td_last_period_column_disguised_as_consensus(self):
        self.blocked(pair(td=td_html(header="Last Period")))
    def test_13_td_yoy_vs_mom_mismatch(self):
        self.blocked(pair(td=td_html(unit="Y/Y % Chg.")))
    def test_14_td_reference_october_not_november(self):
        self.blocked(pair(td=td_html(period="Oct")))
    def test_15_td_wrong_release_day(self):
        self.blocked(pair(td=td_html(day="Dec 11")))
    def test_16_td_wrong_release_time(self):
        self.blocked(pair(td=td_html(hh="9:00")))
    def test_17_td_wrong_week_title(self):
        self.blocked(pair(td=td_html(title="Upcoming Economic Releases Dec 11 - 16")))
    def test_18_td_cpi_wrong_inflation_metric_name(self):
        self.blocked(pair(td=td_html(head_name="CPI YoY Annual Inflation")))
    def test_19_td_duplicate_headline_table(self):
        self.blocked(pair(td=td_html(duplicate=True)))
    def test_20_te_duplicate_event_row(self):
        self.blocked(pair(te=te_html(duplicate=True)))
    def test_21_te_wrong_day(self):
        self.blocked(pair(te=te_html(date="2026-12-11")))
    def test_22_te_wrong_metric_route(self):
        self.blocked(pair(te=te_html(head_url="/united-states/inflation-rate")))
    def test_23_te_wrong_period_label(self):
        self.blocked(pair(te=te_html(head_name="Inflation Rate MoM OCT")))
    def test_24_two_publisher_headline_consensus_disagreement(self):
        self.blocked(pair(CPI,te=te_html(head="0.5%"))+pair(PPI))
    def test_25_core_consensus_disagreement(self):
        self.blocked(pair(PPI,td=td_html(PPI,core="0.2")))
    def test_26_previous_month_value_disagreement(self):
        self.blocked(pair(te=te_html(prev="0.1%")))
    def test_27_td_nan_is_invalid(self):
        self.blocked(pair(td=td_html(head="NaN")))
    def test_28_te_nan_is_invalid(self):
        self.blocked(pair(te=te_html(head="NaN%")))
    def test_29_te_missing_percent_is_invalid(self):
        self.blocked(pair(te=te_html(head="0.4")))
    def test_30_td_illegal_percent_sign_is_invalid(self):
        self.blocked(pair(td=td_html(head="0.4%")))
    def test_31_signed_monthly_deflation_is_possible_not_a_signal(self):
        r=self.good(pair(td=td_html(head="-0.2"),te=te_html(head="-0.2%")))
        self.assertEqual(r["events"][0]["provisional_consensus_headline_mom_sa_pct"],"-0.2")
        self.assertFalse(r["events"][0]["consensus_eligible_for_fx_prediction"])
    def test_32_bad_source_hash_rejected_before_semantics(self):
        a,b=pair()
        self.blocked((replace(a,original_sha256_claim="f"*64),b))
    def test_33_future_corrupt_body_hidden_until_cutoff(self):
        a,b=pair()
        a=replace(a,original_sha256_claim="f"*64)
        self.good((a,b),at=a.finished_at_utc-timedelta(seconds=1))
        self.blocked((a,b),at=a.finished_at_utc)
    def test_34_post_release_snapshot_blocked_even_if_number_matches(self):
        a,b=pair()
        a=replace(a,started_at_utc=RELEASE[CPI]+timedelta(seconds=1),
                  finished_at_utc=RELEASE[CPI]+timedelta(seconds=3))
        self.blocked((a,b),at=RELEASE[CPI]+timedelta(hours=2))
    def test_35_wrong_provider_url_is_not_same_vintage(self):
        a,b=pair()
        self.blocked((replace(a,source_url="https://example.invalid/",final_url="https://example.invalid/"),b))
    def test_36_duplicate_snapshots_fail_closed(self):
        a,b=pair()
        self.blocked((a,b,a))
    def test_37_naive_cutoff_invalid(self):
        self.blocked(pair(),at=datetime(2026,12,17))
    def test_38_manual_dict_is_not_original_html(self):
        self.blocked(({"event_root":CPI,"consensus":"0.4"},))
    def test_39_missing_ppi_keeps_denominator_two(self):
        r=self.good(pair(CPI))
        self.assertIsNone(r["events"][1]["provisional_consensus_headline_mom_sa_pct"])
    def test_40_te_corrupted_utf8_fails_and_cannot_fake_number(self):
        a,b=pair()
        raw=b.html_original_bytes+b"\xff"
        b=replace(b,html_original_bytes=raw,original_sha256_claim=sha256(raw).hexdigest())
        self.blocked((a,b))
    def test_41_two_events_one_raw_reused_fails_source_gate(self):
        items=list(pair(CPI)+pair(PPI))
        reused=items[1].html_original_bytes
        items[3]=replace(items[3],html_original_bytes=reused,
                         original_sha256_claim=sha256(reused).hexdigest())
        self.blocked(tuple(items))
    def test_42_invented_outcome_after_news_still_no_prediction(self):
        r=self.good(pair(CPI)+pair(PPI),at=RELEASE[PPI]+timedelta(days=7))
        self.assertEqual(r["registered_directional_fx_predictions"],0)
        self.assertIsNone(r["win_rate"])
    def test_43_duplicate_te_header_no_implicit_column_mapping(self):
        a,b=pair()
        raw=b.html_original_bytes.replace(b"</thead>",
            b"<tr><th>Actual</th><th>Previous</th><th>Consensus</th>"
            b"<th>Forecast</th></tr></thead>")
        b=replace(b,html_original_bytes=raw,original_sha256_claim=sha256(raw).hexdigest())
        self.blocked((a,b))
    def test_44_out_of_range_consensus_not_monthly_percentage(self):
        self.blocked(pair(td=td_html(head="99.9"),te=te_html(head="99.9%")))
    def test_45_candidate_is_not_independently_attested_survey(self):
        r=self.good(pair())
        self.assertFalse(r["events"][0]["source_semantic_schema_approved_on_real_december_html"])
        self.assertFalse(r["events"][0]["provider_poll_methodology_independently_authenticated"])

if __name__=="__main__":
    unittest.main()
