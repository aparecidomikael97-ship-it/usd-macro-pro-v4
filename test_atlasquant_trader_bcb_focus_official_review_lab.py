"""Official BCB Focus PDF transcriptions vs historic/secondary reports."""
from __future__ import annotations
import json
import copy
import unittest
from datetime import datetime,timezone
from decimal import Decimal
from pathlib import Path
from atlasquant_trader_bcb_focus_official_review_lab import (
 SCHEMA,STATE,DENIED,PINNED_ANNUAL,PINNED_MONTHLY,
 OFFICIAL_PDF,OFFICIAL_PAGE,CUTOFF,review_bcb_focus_official_text_lab as review)
SOURCE=(Path(__file__).resolve().parent/"docs"/"continuidade"/
        "TRADER_BCB_FOCUS_20261030_OFFICIAL_REVIEW_LAB.json")
AT=datetime(2026,11,3,16,tzinfo=timezone.utc)

def doc():return json.loads(SOURCE.read_text(encoding="utf-8"))
_SENTINEL=object()
def result(payload=_SENTINEL,*,at=AT):
 return review(doc() if payload is _SENTINEL else payload,evaluated_at=at)
def yearly(r,i,y):
 return next(v for v in r["annual_revisions"]
             if v["indicator"]==i and v["target_period"]==y)
def monthly(r,i,p):
 return next(v for v in r["monthly_forecasts"]
             if v["indicator"]==i and v["target_period"]==p)

class BCBFocusOfficialReviewLabTests(unittest.TestCase):
 def test_bcb_publication_is_primary_text_not_an_archived_binary(self):
  d=doc();r=result()
  self.assertEqual((r["state"],r["schema"]),(STATE,SCHEMA))
  self.assertEqual(d["landing_page_url"],OFFICIAL_PAGE)
  self.assertEqual(d["pdf_url"],OFFICIAL_PDF)
  self.assertEqual(d["published_on"],"2026-11-03")
  self.assertTrue(r["official_page_verified_documentary"])
  self.assertTrue(r["official_pdf_text_reviewed_documentary"])
  self.assertFalse(r["original_official_pdf_bytes_archived"])
  self.assertIsNone(r["original_pdf_sha256"])
  self.assertFalse(r["independent_source_receipt_verified"])
 def test_all_12_annual_and_eight_monthly_official_medians(self):
  r=result()
  self.assertEqual((r["annual_count"],r["monthly_count"]),(12,8))
  self.assertEqual(len(PINNED_ANNUAL),12)
  self.assertEqual(len(PINNED_MONTHLY),8)
  self.assertEqual(r["reconciled_2026_2027_with_secondary_and_prior"],8)
 def test_2026_ipca_and_2027_ipca_revision(self):
  r=result()
  self.assertEqual(yearly(r,"IPCA","2026")["new_pdf_median"],"5.22")
  self.assertEqual(yearly(r,"IPCA","2026")["signed_revision"],"0.03")
  self.assertEqual(yearly(r,"IPCA","2027")["signed_revision"],"0.42")
 def test_selic_year_end_distinct_from_copom_decision(self):
  r=result()
  self.assertEqual(yearly(r,"SELIC","2026")["new_pdf_median"],"13.50")
  self.assertEqual(yearly(r,"SELIC","2027")["new_pdf_median"],"12.50")
  self.assertEqual(monthly(r,"SELIC","2026-11")["median"],"13.50")
  self.assertEqual(monthly(r,"SELIC","2026-12")["median"],"13.50")
  self.assertTrue(all(not x["is_next_copom_consensus"]
                      for x in r["monthly_forecasts"]))
  self.assertFalse(r["next_copom_meeting_consensus_verified"])
 def test_year_end_fx_is_not_spot_or_month_end_november(self):
  r=result()
  self.assertEqual(yearly(r,"FX_BRL_PER_USD","2026")["new_pdf_median"],"5.34")
  self.assertEqual(monthly(r,"FX_BRL_PER_USD","2026-11")["median"],"5.32")
  self.assertEqual(monthly(r,"FX_BRL_PER_USD","2026-12")["median"],"5.34")
  self.assertEqual(monthly(r,"FX_BRL_PER_USD","2026-11")["unit"],
                   "BRL_PER_USD_MONTH_END")
 def test_pib_2026_and_2027_both_revised_down(self):
  r=result()
  self.assertEqual(yearly(r,"REAL_GDP","2026")["signed_revision"],"-0.04")
  self.assertEqual(yearly(r,"REAL_GDP","2027")["signed_revision"],"-0.11")
 def test_2028_annual_medians_extend_beyond_secondary_report(self):
  r=result()
  self.assertEqual(yearly(r,"IPCA","2028")["new_pdf_median"],"4.00")
  self.assertEqual(yearly(r,"SELIC","2028")["new_pdf_median"],"11.00")
  self.assertEqual(yearly(r,"REAL_GDP","2028")["new_pdf_median"],"1.80")
  self.assertEqual(yearly(r,"FX_BRL_PER_USD","2028")["new_pdf_median"],"5.40")
 def test_respondents_are_counts_not_probabilities(self):
  r=result()
  self.assertEqual(yearly(r,"IPCA","2026")["respondents_30d"],144)
  self.assertEqual(yearly(r,"SELIC","2026")["respondents_30d"],143)
  self.assertEqual(yearly(r,"FX_BRL_PER_USD","2026")["respondents_30d"],120)
  self.assertFalse(r["actual_copom_decision_known"])
  self.assertIsNone(r["next_copom_market_implied_probability"])
 def test_8_previous_observations_reconciled_with_existing_frozen_modules(self):
  self.assertEqual(result()["reconciled_2026_2027_with_secondary_and_prior"],8)
 def test_six_win_wdo_horizon_rows_are_context_only(self):
  r=result()
  self.assertEqual({(v["instrument"],v["horizon"]) for v in r["win_wdo_context"]},
       {(a,b) for a in ("WIN","WDO") for b in ("D1","W1","MN1")})
  self.assertTrue(all(v["directional_bias"]=="AGUARDAR"
                      and v["trade_authorized"] is False
                      and v["nov4_copom_decision_consensus_pct"] is None
                      for v in r["win_wdo_context"]))
 def test_document_original_bytes_claim_must_stay_false(self):
  d=doc();d["original_pdf_bytes_archived"]=True
  self.assertEqual(result(d)["state"],DENIED)
  d=doc();d["original_pdf_sha256"]="a"*64
  self.assertEqual(result(d)["state"],DENIED)
 def test_official_urls_and_dates_cannot_be_changed(self):
  for field,value in (("landing_page_url","https://elsewhere.example"),
    ("pdf_url","https://elsewhere.example"),("published_on","2026-11-02"),
    ("reference_date","2026-10-23"),("review_date_utc","2026-11-02")):
   with self.subTest(field=field):
    d=doc();d[field]=value
    self.assertEqual(result(d)["state"],DENIED)
 def test_missing_extra_and_malformed_document_rejected(self):
  for d in (None,[],{},"x",{"schema":SCHEMA}):
   with self.subTest(payload=type(d).__name__):
    self.assertEqual(result(d)["state"],DENIED)
  d=doc();d["trade_authorized"]=True
  self.assertEqual(result(d)["state"],DENIED)
 def test_annual_reordering_missing_and_duplication_denied(self):
  for changed in ("reverse","remove","repeat"):
   d=doc()
   if changed=="reverse": d["annual_medians"].reverse()
   elif changed=="remove": d["annual_medians"].pop()
   else:d["annual_medians"][1]=copy.deepcopy(d["annual_medians"][0])
   self.assertEqual(result(d)["state"],DENIED)
 def test_annual_modified_value_indicator_and_type_rejected(self):
  for field,value in (("now","5.23"),("previous","5.20"),
     ("unit","PCT_MONTHLY"),("indicator","OTHER"),("year","2025"),
     ("respondents_30d",145),("respondents_30d",True),
     ("now",True),("now","NaN"),("now","=2+2")):
   with self.subTest(field=field,value=value):
    d=doc();d["annual_medians"][0][field]=value
    self.assertEqual(result(d)["state"],DENIED)
 def test_monthly_missing_and_imposter_median_rejected(self):
  d=doc();d["monthly_medians"].pop()
  self.assertEqual(result(d)["state"],DENIED)
  for field,value in (("now","13.25"),("unit","PCT_SPOT"),
      ("period","2026-11-04"),("indicator","COPOM"),
      ("now",None),("now","Infinity")):
   with self.subTest(field=field,value=value):
    d=doc();d["monthly_medians"][6][field]=value
    self.assertEqual(result(d)["state"],DENIED)
 def test_no_prospective_false_asof_at_midnight(self):
  early=datetime(2026,11,3,0,tzinfo=timezone.utc)
  self.assertEqual(result(at=early)["state"],DENIED)
  self.assertEqual(result(at=datetime(2026,11,2,23,tzinfo=timezone.utc))["state"],DENIED)
 def test_timezone_naive_rejected(self):
  with self.assertRaises(ValueError):result(at=datetime(2026,11,3,16))
 def test_different_input_objects_cannot_escape_pit_and_trade_gate(self):
  for input_doc in (doc(),None):
   r=result(input_doc)
   for flag in ("original_official_pdf_bytes_archived",
      "independent_source_receipt_verified","point_in_time_forecast_input_attested",
      "can_feed_live_radar","can_feed_real_oos","trade_authorized",
      "worker_enabled","scheduler_enabled","paid_provider_approved",
      "render_configuration_changed"):
    self.assertFalse(r[flag],flag)
   self.assertEqual(r["directional_bias"],"AGUARDAR")
   self.assertIsNone(r["probability_calibrated"])

if __name__=="__main__":unittest.main()
