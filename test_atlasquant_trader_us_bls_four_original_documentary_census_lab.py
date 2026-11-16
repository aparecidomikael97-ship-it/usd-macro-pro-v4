"""Four-release coverage regression: synthetic documents only, no market sample."""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone, timedelta
from hashlib import sha256
import unittest

from atlasquant_trader_us_bls_four_original_documentary_census_lab import (
    OriginalBlsReleaseClaim, inspect_four_bls_original_documentary_events_lab as inspect,
)
from atlasquant_trader_us_bls_sep2026_original_pair_once_lab import SPECS
from test_atlasquant_trader_us_bls_sep2026_original_pair_once_lab import body
from test_atlasquant_trader_us_oct2026_cpi_release_text_guard_lab import raw as oct_cpi
from test_atlasquant_trader_us_ppi_oct2026_actual_table_guard_lab import raw as oct_ppi
from atlasquant_trader_us_oct2026_cpi_release_text_guard_lab import URL as OCT_CPI_URL
from atlasquant_trader_us_ppi_oct2026_actual_table_guard_lab import OFFICIAL_URL as OCT_PPI_URL

UTC=timezone.utc
D={
    ("2026-09","CPI"):datetime(2026,11,16,2,20,25,tzinfo=UTC),
    ("2026-09","PPI"):datetime(2026,11,16,2,20,27,tzinfo=UTC),
    ("2026-10","CPI"):datetime(2026,11,16,1,15,45,tzinfo=UTC),
    ("2026-10","PPI"):datetime(2026,11,14,16,0,53,tzinfo=UTC),
}
AFTER=datetime(2026,11,16,3,0,tzinfo=UTC)


def sources():
    raws={
        ("2026-09","CPI"):body("CPI"),
        ("2026-09","PPI"):body("PPI"),
        ("2026-10","CPI"):oct_cpi(),
        ("2026-10","PPI"):oct_ppi(head="0.3",core="0.3",extra="0.5"),
    }
    urls={
        ("2026-09","CPI"):SPECS["CPI"]["url"],
        ("2026-09","PPI"):SPECS["PPI"]["url"],
        ("2026-10","CPI"):OCT_CPI_URL,
        ("2026-10","PPI"):OCT_PPI_URL,
    }
    return tuple(OriginalBlsReleaseClaim(
        reference_period=k[0],indicator=k[1],source_url=urls[k],
        html_original_bytes=blob,http_status=200,
        content_type="text/html; charset=utf-8",
        capture_started_at_utc=D[k]-timedelta(seconds=1),
        capture_finished_at_utc=D[k],
        original_sha256_claim=sha256(blob).hexdigest(),
    ) for k,blob in raws.items())


def check(docs=None, cutoff=AFTER):
    return inspect(source_claims=sources() if docs is None else docs,
                   research_cutoff_utc=cutoff)


class FourBlsActualsDocumentaryCensusTests(unittest.TestCase):
    def safe(self,v):
        self.assertEqual(v["schema"],"ATLASQUANT_BLS_CPI_PPI_SEP_OCT2026_FOUR_EVENT_CENSUS_LAB_V1")
        self.assertEqual(v["frozen_documentary_release_denominator"],4)
        self.assertEqual(v["economic_event_roots_in_universe"],4)
        self.assertEqual([e["root_id"] for e in v["events"]],
            ["US_CPI_SEP2026","US_PPI_SEP2026","US_CPI_OCT2026","US_PPI_OCT2026"])
        self.assertEqual(v["historical_consensus_events_independently_authenticated"],0)
        self.assertEqual(v["independent_precommitted_forex_predictions_verified"],0)
        self.assertEqual(v["sample_size_for_validated_oos_scoring"],0)
        self.assertIsNone(v["out_of_sample_directional_accuracy"])
        self.assertIsNone(v["calibrated_probability"])
        self.assertIsNone(v["forex_bias"])
        self.assertFalse(v["source_first_seen_independently_authenticated"])
        self.assertFalse(v["broker_bid_ask_independently_authenticated"])
        self.assertFalse(v["trade_authorized"])
        self.assertFalse(v["publishable"])
        self.assertFalse(v["fx28_672_campaign_slots_modified"])
        self.assertEqual(v["operational_bias"],"AGUARDAR")
        self.assertEqual((v["http_requests"],v["mt5_calls"],v["file_writes"]),(0,0,0))

    def test_01_four_original_like_sources_documentary_not_predictions(self):
        r=check()
        self.safe(r)
        self.assertEqual(r["state"],"LAB_BLS_FOUR_EVENT_DOCUMENTARY_CENSUS_NO_GO")
        self.assertEqual(r["documentary_originals_reconciled_at_cutoff"],4)
        self.assertEqual(r["documentary_originals_not_yet_visible_or_missing"],0)
        self.assertEqual([e["actual_headline_sa_mom_pct_documentary"] for e in r["events"]],
                         ["0.6","1.3","0.4","0.3"])

    def test_02_empty_roster_preserves_fixed_four_denominator(self):
        r=check(())
        self.safe(r)
        self.assertEqual(r["state"],"LAB_BLS_FOUR_EVENT_DOCUMENTARY_CENSUS_NO_GO")
        self.assertEqual(r["documentary_originals_reconciled_at_cutoff"],0)
        self.assertEqual(r["documentary_originals_not_yet_visible_or_missing"],4)

    def test_03_one_missing_sep_2026_report_not_dropped_from_denominator(self):
        r=check(sources()[1:])
        self.safe(r)
        self.assertEqual(r["documentary_originals_reconciled_at_cutoff"],3)
        self.assertEqual(r["events"][0]["doc_status"],"MISSING_OR_NOT_YET_CAPTURED")

    def test_04_no_files_at_historical_2026_oct13_as_of(self):
        r=check(cutoff=datetime(2026,10,13,tzinfo=UTC))
        self.safe(r)
        self.assertEqual(r["documentary_originals_reconciled_at_cutoff"],0)
        self.assertEqual([e["actual_headline_sa_mom_pct_documentary"] for e in r["events"]],
                         [None,None,None,None])

    def test_05_nov15_only_october_ppi_copy_was_locally_captured(self):
        r=check(cutoff=datetime(2026,11,15,20,tzinfo=UTC))
        self.safe(r)
        self.assertEqual(r["documentary_originals_reconciled_at_cutoff"],1)
        self.assertEqual(r["events"][3]["actual_headline_sa_mom_pct_documentary"],"0.3")
        self.assertIsNone(r["events"][2]["actual_headline_sa_mom_pct_documentary"])

    def test_06_sep_ppi_receipt_future_at_022026_not_visible(self):
        r=check(cutoff=datetime(2026,11,16,2,20,26,tzinfo=UTC))
        self.safe(r)
        self.assertEqual(r["documentary_originals_reconciled_at_cutoff"],3)
        self.assertIsNone(r["events"][1]["actual_headline_sa_mom_pct_documentary"])

    def test_07_at_exact_sep_ppi_receipt_end_now_four_visible(self):
        r=check(cutoff=D[("2026-09","PPI")])
        self.safe(r)
        self.assertEqual(r["documentary_originals_reconciled_at_cutoff"],4)

    def test_08_bad_sep_cpi_sha_blocked_after_capture(self):
        arr=list(sources())
        arr[0]=replace(arr[0],original_sha256_claim="f"*64)
        r=check(tuple(arr))
        self.safe(r)
        self.assertEqual(r["state"],"LAB_BLS_FOUR_EVENT_CENSUS_BLOCKED_NO_GO")

    def test_09_bad_sep_cpi_sha_still_hidden_before_its_capture(self):
        arr=list(sources())
        arr[0]=replace(arr[0],original_sha256_claim="f"*64)
        r=check(tuple(arr),cutoff=datetime(2026,11,15,20,tzinfo=UTC))
        self.safe(r)
        self.assertEqual(r["state"],"LAB_BLS_FOUR_EVENT_DOCUMENTARY_CENSUS_NO_GO")
        self.assertEqual(r["documentary_originals_reconciled_at_cutoff"],1)

    def test_10_wrong_ppi_2026_october_headline_rejected(self):
        arr=list(sources())
        bad=oct_ppi(head="0.9",core="0.3")
        arr[3]=replace(arr[3],html_original_bytes=bad,
                       original_sha256_claim=sha256(bad).hexdigest())
        r=check(tuple(arr))
        self.safe(r)
        self.assertEqual(r["state"],"LAB_BLS_FOUR_EVENT_CENSUS_BLOCKED_NO_GO")

    def test_11_cpi_oct_wrong_monthly_number_rejected(self):
        arr=list(sources())
        bad=oct_cpi(head="0.9")
        arr[2]=replace(arr[2],html_original_bytes=bad,
                       original_sha256_claim=sha256(bad).hexdigest())
        r=check(tuple(arr))
        self.safe(r)
        self.assertEqual(r["state"],"LAB_BLS_FOUR_EVENT_CENSUS_BLOCKED_NO_GO")

    def test_12_same_source_html_relabelled_second_event_rejected(self):
        arr=list(sources())
        arr[1]=replace(arr[1],html_original_bytes=arr[0].html_original_bytes,
                       original_sha256_claim=arr[0].original_sha256_claim)
        r=check(tuple(arr))
        self.safe(r)
        self.assertEqual(r["state"],"LAB_BLS_FOUR_EVENT_CENSUS_BLOCKED_NO_GO")

    def test_13_duplicate_event_not_an_extra_release(self):
        a=sources()
        r=check((a[0],a[0]))
        self.safe(r)
        self.assertEqual(r["state"],"LAB_BLS_FOUR_EVENT_CENSUS_BLOCKED_NO_GO")

    def test_14_nonexistent_future_period_fifth_event_blocked(self):
        a=sources()
        added=replace(a[0],reference_period="2026-11")
        r=check((added,))
        self.safe(r)
        self.assertEqual(r["state"],"LAB_BLS_FOUR_EVENT_CENSUS_BLOCKED_NO_GO")

    def test_15_fifth_item_cannot_raise_denominator_to_five(self):
        a=sources()
        r=check(a+(a[0],))
        self.safe(r)
        self.assertEqual(r["frozen_documentary_release_denominator"],4)
        self.assertEqual(r["documentary_originals_reconciled_at_cutoff"],0)

    def test_16_document_before_embargo_capture_clock_refused(self):
        a=list(sources())
        a[0]=replace(a[0],capture_started_at_utc=datetime(2026,10,14,12,29,tzinfo=UTC))
        r=check(tuple(a))
        self.safe(r)
        self.assertEqual(r["state"],"LAB_BLS_FOUR_EVENT_CENSUS_BLOCKED_NO_GO")

    def test_17_bad_nan_or_microsecond_only_cutoff_cannot_fake_future(self):
        r=check(cutoff=datetime(2026,11,16,2,20,26,999999,tzinfo=UTC))
        self.safe(r)
        self.assertEqual(r["documentary_originals_reconciled_at_cutoff"],3)

    def test_18_naive_cutoff_blocked_no_sources_visible(self):
        r=check(cutoff=datetime(2026,11,16,3,0))
        self.safe(r)
        self.assertEqual(r["documentary_originals_reconciled_at_cutoff"],0)

    def test_19_wrong_url_even_same_bytes_rejected(self):
        a=list(sources())
        a[1]=replace(a[1],source_url="https://example.com/ppi")
        r=check(tuple(a))
        self.safe(r)
        self.assertEqual(r["state"],"LAB_BLS_FOUR_EVENT_CENSUS_BLOCKED_NO_GO")

    def test_20_http_bool_true_not_status200(self):
        a=list(sources())
        a[1]=replace(a[1],http_status=True)
        r=check(tuple(a))
        self.safe(r)
        self.assertEqual(r["state"],"LAB_BLS_FOUR_EVENT_CENSUS_BLOCKED_NO_GO")

    def test_21_wrong_mime_type_rejected(self):
        a=list(sources())
        a[2]=replace(a[2],content_type="application/json")
        r=check(tuple(a))
        self.safe(r)
        self.assertEqual(r["state"],"LAB_BLS_FOUR_EVENT_CENSUS_BLOCKED_NO_GO")

    def test_22_swapped_capture_clock_rejected(self):
        a=list(sources())
        a[2]=replace(a[2],capture_started_at_utc=a[2].capture_finished_at_utc+timedelta(seconds=2))
        r=check(tuple(a))
        self.safe(r)
        self.assertEqual(r["state"],"LAB_BLS_FOUR_EVENT_CENSUS_BLOCKED_NO_GO")

    def test_23_no_fx_predictions_even_with_four_originals(self):
        r=check()
        self.safe(r)
        self.assertTrue(r["cross_metric_double_counting_prevented"])
        self.assertTrue(r["missing_economic_events_cannot_be_dropped"])
        self.assertEqual(r["independent_precommitted_forex_predictions_verified"],0)


if __name__ == "__main__":
    unittest.main()
