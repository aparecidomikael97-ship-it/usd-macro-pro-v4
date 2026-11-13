"""Synthetic future PPI fixtures, never real October-2026 realized observations."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import unittest

from atlasquant_trader_us_ppi_oct2026_actual_table_guard_lab import (
    ClaimedPostReleaseHTTP, OFFICIAL_URL, RELEASE_UTC,
    inspect_ppi_oct2026_first_print_lab as inspect,
    compare_ppi_actual_to_frozen_consensus_lab as compare,
)

UTC = timezone.utc
AFTER = RELEASE_UTC + timedelta(minutes=5)
CAPTURE_START = RELEASE_UTC + timedelta(seconds=30)
TD_SHA = '5f9d9eb128e5a3763ec6a3081bee7ba8c248a665a9d50e0ee132e9cbe037a42a'
TE_SHA = '175c163514590db8e2ddd651f0c9865bd2eed298211f92072549233f670e23c0'


def raw(head='0.5', core='0.2', extra='0.9', *, action='increased', date='Friday, November 13, 2026',
        title='PRODUCER PRICE INDEXES - OCTOBER 2026', swap_core=False,
        dup=False, headline_table=None, include_table=True):
    hval = head if headline_table is None else headline_table
    row = lambda label, code, v: (
        '<tr><td>' + label + '</td><td>FD</td><td>' + code +
        '</td><td>100</td><td>n/a</td><td>0.4</td><td>' + v + '</td></tr>')
    section = (
        '<h2>Table 1. Producer price index percentage changes and weights for Final Demand-Intermediate '
        'Demand groupings, seasonally adjusted [October 2026]</h2>'
        '<table><tr><th>Grouping</th><th>Commodity code</th><th></th><th>Weight</th>'
        '<th>12-month unadjusted</th><th>Earlier</th><th>Sep to Oct SA</th></tr>'
        + row('Final demand', '4', hval)
        + row('Final demand less foods, energy, and trade services', '49116', extra)
        + row('Final demand less foods and energy' if not swap_core else
              'Final demand goods less foods and energy', '49104' if not swap_core else '413', core)
        + (row('Final demand less foods and energy', '49104', core) if dup else '')
        + '</table>') if include_table else ''
    return ('<html><head><title>Producer Price Index News Release - 2026 M10 Results</title>'
            '</head><body><h1>' + title + '</h1>' + date +
            ' <p>The Producer Price Index for final demand ' + action + ' ' + head +
            ' percent in October, seasonally adjusted, the U.S. Bureau of Labor Statistics reported today.</p>'
            '<p>SYNTHETIC TEST CONTENT -- NOT REAL OFFICIAL OCTOBER RESULTS.</p>' + section +
            '<h2>Table 3. Series levels, not monthly rates</h2>'
            '<table>' + row('Final demand less foods and energy', '49104', '9.8') + '</table>'
            '</body></html>').encode('utf-8')


def receipt(body, **kw):
    base = ClaimedPostReleaseHTTP(OFFICIAL_URL, 200, 'text/html', CAPTURE_START,
                                   CAPTURE_START + timedelta(seconds=10), sha256(body).hexdigest())
    return replace(base, **kw)


def td():
    return {'state':'LAB_PRE_EVENT_PPI_CONSENSUS_ARCHIVED_LOCAL_NO_TRADE',
            'source_body_sha256':TD_SHA,
            'headline_consensus_mom_pct':'0.4', 'core_consensus_mom_pct':'0.3'}


def te():
    return {'state':'LAB_TE_PRE_EVENT_CONSENSUS_AND_OWN_FORECAST_DISTINGUISHED',
            'source_sha256':TE_SHA,
            'headline_consensus_mom_pct':'0.4','core_consensus_mom_pct':'0.3',
            'headline_te_own_forecast_mom_pct':'0.3'}


class PpiFirstPrintGuardTests(unittest.TestCase):
    def audit(self, body=None, rec=None, asof=AFTER):
        b = raw() if body is None else body
        return inspect(raw_html=b, receipt=receipt(b) if rec is None else rec, as_of_utc=asof)

    def safe(self, r):
        self.assertEqual(r['operational_bias'], 'AGUARDAR')
        self.assertFalse(r['trade_authorized'])
        self.assertFalse(r['publishable'])
        self.assertFalse(r['worker_enabled'])
        self.assertFalse(r['scheduler_enabled'])
        self.assertFalse(r['official_actual_independently_attested'])
        self.assertFalse(r['point_in_time_backtest_eligible'])
        self.assertFalse(r['source_redistribution_licensed'])
        self.assertIsNone(r['market_bias'])
        self.assertIsNone(r['ex_food_energy_trade_services_pct'])

    def test_01_before_release_no_future_first_print(self):
        r = self.audit(asof=RELEASE_UTC-timedelta(seconds=1))
        self.assertEqual(r['state'], 'LAB_WAIT_BLS_PPI_OCT2026_RELEASE')
        self.assertIsNone(r['headline_final_demand_sa_mom_pct_body_claim'])
        self.safe(r)

    def test_02_after_release_no_html_still_waits(self):
        r = inspect(raw_html=None,receipt=None,as_of_utc=AFTER)
        self.assertEqual(r['state'], 'LAB_WAIT_BLS_PPI_OCT2026_DOCUMENT')
        self.safe(r)

    def test_03_synthetic_table_1_extracts_exact_49104(self):
        r = self.audit()
        self.assertEqual(r['state'], 'LAB_PPI_OCT2026_BLS_TABLE1_BODY_VALUES_UNATTESTED')
        self.assertEqual(r['headline_final_demand_sa_mom_pct_body_claim'],'0.5')
        self.assertEqual(r['core_ex_food_energy_sa_mom_pct_body_claim'],'0.2')
        self.safe(r)

    def test_04_actual_comparison_synthetic_only(self):
        joined=compare(actual=self.audit(),td_snapshot=td(),te_snapshot=te())
        self.assertEqual(joined['state'],'LAB_PPI_RESEARCH_SURPRISE_ONLY_UNATTESTED')
        self.assertEqual(joined['headline_vs_td_pre_event_diff_pp'],'0.1')
        self.assertEqual(joined['core_vs_td_pre_event_diff_pp'],'-0.1')
        self.safe(joined)

    def test_05_forecast_te_must_not_be_confused_with_consensus(self):
        joined=compare(actual=self.audit(),td_snapshot=td(),te_snapshot=te())
        self.assertEqual(joined['headline_vs_td_pre_event_diff_pp'],'0.1')
        self.assertNotEqual(joined['headline_vs_td_pre_event_diff_pp'], '0.2')
        self.safe(joined)

    def test_06_wrong_core_49116_never_accepted_as_49104(self):
        r=self.audit(body=raw(swap_core=True))
        self.assertEqual(r['reason'],'MONTHLY_SA_TABLE1_SERIES_MISSING_OR_HEADLINE_MISMATCH')
        self.safe(r)

    def test_07_duplicate_49104_fails_closed(self):
        r=self.audit(body=raw(dup=True))
        self.assertEqual(r['reason'],'MONTHLY_SA_TABLE1_SERIES_MISSING_OR_HEADLINE_MISMATCH')
        self.safe(r)

    def test_08_body_text_conflicts_with_table_headline(self):
        r=self.audit(body=raw(headline_table='0.6'))
        self.assertEqual(r['reason'],'MONTHLY_SA_TABLE1_SERIES_MISSING_OR_HEADLINE_MISMATCH')
        self.safe(r)

    def test_09_wrong_period_or_event_date(self):
        for change in (raw(title='PRODUCER PRICE INDEXES - SEPTEMBER 2026'),
                       raw(date='Thursday, November 12, 2026')):
            with self.subTest(change=change[:150]):
                r=self.audit(body=change)
                self.assertEqual(r['reason'],'WRONG_PPI_RELEASE_ID_OR_TARGET_PERIOD')
                self.safe(r)

    def test_10_monthly_table_is_mandatory(self):
        r=self.audit(body=raw(include_table=False))
        self.assertEqual(r['reason'],'MONTHLY_SA_TABLE1_MISSING_OR_AMBIGUOUS')
        self.safe(r)

    def test_11_negative_headline_valid_if_table_agrees(self):
        b=raw(head='0.4',action='declined',headline_table='-0.4')
        r=self.audit(body=b)
        self.assertEqual(r['headline_final_demand_sa_mom_pct_body_claim'],'-0.4')
        self.safe(r)

    def test_12_tampering_body_without_hash_detected(self):
        b=raw()
        r=self.audit(body=b+b'X',rec=receipt(b))
        self.assertEqual(r['reason'],'RAW_BODY_SIZE_OR_DIGEST_MISMATCH')
        self.safe(r)

    def test_13_non_200_or_wrong_url_mime_refused(self):
        b=raw()
        for kw in ({'status_code':403},{'status_code':True},
                   {'content_type':'application/json'},
                   {'source_url':'https://other.example/not-bls'}):
            with self.subTest(kw=kw):
                r=self.audit(body=b,rec=receipt(b,**kw))
                self.assertEqual(r['reason'],'SOURCE_STATUS_OR_CHRONOLOGY_NOT_ACCEPTABLE')
                self.safe(r)

    def test_14_post_asof_or_pre_release_capture_rejected(self):
        b=raw()
        for kw in ({'started_utc':RELEASE_UTC-timedelta(seconds=1)},
                   {'finished_utc':AFTER+timedelta(seconds=1)}):
            with self.subTest(kw=kw):
                r=self.audit(body=b,rec=receipt(b,**kw))
                self.assertEqual(r['reason'],'SOURCE_STATUS_OR_CHRONOLOGY_NOT_ACCEPTABLE')
                self.safe(r)

    def test_15_pre_event_lock_hash_wrong_rejected(self):
        snapshot=td()
        snapshot['source_body_sha256']='a'*64
        r=compare(actual=self.audit(),td_snapshot=snapshot,te_snapshot=te())
        self.assertEqual(r['reason'],'PRE_EVENT_LOCK_STATE_OR_HASH_MISMATCH')
        self.safe(r)

    def test_16_two_consensus_sources_disagree_rejected(self):
        snap=te()
        snap['headline_consensus_mom_pct']='0.6'
        r=compare(actual=self.audit(),td_snapshot=td(),te_snapshot=snap)
        self.assertEqual(r['reason'],'PRE_EVENT_CONSENSUS_CONFLICT')
        self.safe(r)

    def test_17_bad_source_actual_not_accepted_to_join(self):
        r=compare(actual=self.audit(body=raw(include_table=False)),td_snapshot=td(),te_snapshot=te())
        self.assertEqual(r['reason'],'NO_ACCEPTED_FIRST_PRINT_CANDIDATE')
        self.safe(r)

    def test_18_non_utc_input_without_timezone_rejected(self):
        r=self.audit(asof=AFTER.replace(tzinfo=None))
        self.assertEqual(r['reason'],'INVALID_AS_OF_CLOCK')
        self.safe(r)

    def test_19_previous_value_is_not_actual(self):
        r=self.audit(body=raw(head='0.5',core='0.2',extra='0.9'))
        self.assertNotEqual(r['headline_final_demand_sa_mom_pct_body_claim'],'1.3')
        self.assertNotEqual(r['core_ex_food_energy_sa_mom_pct_body_claim'],'0.9')
        self.safe(r)

    def test_20_more_than_four_megabytes_blocked(self):
        r=self.audit(body=raw()+b'x'*(4*1024*1024))
        self.assertEqual(r['reason'],'RAW_BODY_SIZE_OR_DIGEST_MISMATCH')
        self.safe(r)


    def test_23_missing_mom_column_header_never_uses_nsa_yoy_value(self):
        b=raw().replace(b"<th>Sep to Oct SA</th>",
                        b"<th>12-month unadjusted</th>")
        report=self.audit(body=b)
        self.assertEqual(report["reason"],
                         "MONTHLY_SA_TABLE1_COLUMN_HEADER_MISSING_OR_AMBIGUOUS")
        self.assertIsNone(report["headline_final_demand_sa_mom_pct_body_claim"])
        self.safe(report)

    def test_24_reordered_columns_use_explicit_monthly_header_not_last_cell(self):
        text=raw().decode("utf-8")
        text=text.replace(
            "<th>Earlier</th><th>Sep to Oct SA</th>",
            "<th>Sep to Oct SA</th><th>12-month unadjusted</th>")
        for v in ("0.5","0.2","0.9","9.8"):
            text=text.replace(
                "<td>0.4</td><td>"+v+"</td>",
                "<td>"+v+"</td><td>9.9</td>")
        report=self.audit(body=text.encode("utf-8"))
        self.assertEqual(report["state"],
                         "LAB_PPI_OCT2026_BLS_TABLE1_BODY_VALUES_UNATTESTED")
        self.assertEqual(report["headline_final_demand_sa_mom_pct_body_claim"],"0.5")
        self.assertEqual(report["core_ex_food_energy_sa_mom_pct_body_claim"],"0.2")
        self.assertNotEqual(report["headline_final_demand_sa_mom_pct_body_claim"],"9.9")
        self.safe(report)

    def test_25_duplicated_october_sa_month_header_blocks_ambiguous_columns(self):
        b=raw().replace(b"<th>Earlier</th>",
                        b"<th>Sep to Oct SA</th>")
        report=self.audit(body=b)
        self.assertEqual(report["reason"],
                         "MONTHLY_SA_TABLE1_COLUMN_HEADER_MISSING_OR_AMBIGUOUS")
        self.safe(report)

    def test_26_wrong_year_october_sa_month_header_rejected(self):
        b=raw().replace(b"<th>Sep to Oct SA</th>",
                        b"<th>Sep to Oct SA 2025</th>")
        report=self.audit(body=b)
        self.assertEqual(report["reason"],
                         "MONTHLY_SA_TABLE1_COLUMN_HEADER_MISSING_OR_AMBIGUOUS")
        self.safe(report)

    def test_27_table_row_with_extra_unlabeled_numeric_cell_rejected(self):
        b=raw().replace(
            b"<td>4</td><td>100</td><td>n/a</td><td>0.4</td><td>0.5</td></tr>",
            b"<td>4</td><td>100</td><td>n/a</td><td>0.4</td><td>9.9</td><td>0.5</td></tr>")
        report=self.audit(body=b)
        self.assertEqual(report["reason"],
                         "MONTHLY_SA_TABLE1_SERIES_MISSING_OR_HEADLINE_MISMATCH")
        self.safe(report)

    def test_28_same_release_still_requires_october_2026_not_any_annual_headline(self):
        b=raw().replace(b"<th>Sep to Oct SA</th>",
                        b"<th>Sep to Oct NSA annual change</th>")
        report=self.audit(body=b)
        self.assertEqual(report["reason"],
                         "MONTHLY_SA_TABLE1_COLUMN_HEADER_MISSING_OR_AMBIGUOUS")
        self.safe(report)

    def test_21_forged_actual_report_has_no_provenance(self):
        candidate=self.audit().copy()
        candidate['source_sha256']=None
        r=compare(actual=candidate,td_snapshot=td(),te_snapshot=te())
        self.assertEqual(r['reason'],'ACTUAL_DOCUMENT_PROVENANCE_CLAIM_INCOMPLETE')
        self.safe(r)

    def test_22_impossible_actual_capture_time(self):
        candidate=self.audit().copy()
        candidate['source_capture_claim_utc']=(RELEASE_UTC-timedelta(seconds=1)).isoformat()
        r=compare(actual=candidate,td_snapshot=td(),te_snapshot=te())
        self.assertEqual(r['reason'],'ACTUAL_DOCUMENT_PROVENANCE_CLAIM_INCOMPLETE')
        self.safe(r)

if __name__ == '__main__':
    unittest.main()