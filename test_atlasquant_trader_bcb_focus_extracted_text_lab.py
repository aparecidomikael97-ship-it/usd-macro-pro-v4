"""Source-text checks for BCB Focus Oct30: official PDF text, NOT raw binary."""
from __future__ import annotations
import copy
import json
import unittest
from datetime import datetime, timezone
from pathlib import Path
from atlasquant_trader_bcb_focus_extracted_text_lab import (
 SCHEMA,STATE,DENIED,EXTRACTED_TEXT_GIT_BLOB_SHA1,
 crosscheck_bcb_focus_extracted_text_lab as crosscheck,
)

ROOT=Path(__file__).resolve().parent
TEXT=ROOT/"docs/continuidade/R20261030_BCB_PDF_TEXT_EXTRACTED_LAB_20261103.txt"
BOOK=ROOT/"docs/continuidade/TRADER_BCB_FOCUS_20261030_OFFICIAL_REVIEW_LAB.json"
NOW=datetime(2026,11,3,17,tzinfo=timezone.utc)

def document():return json.loads(BOOK.read_text(encoding="utf-8"))
def text_bytes():return TEXT.read_bytes()
_UNSET=object()
def evaluate(raw=_UNSET,doc=_UNSET,*,at=NOW):
 return crosscheck(text_bytes() if raw is _UNSET else raw,
                   document() if doc is _UNSET else doc,evaluated_at=at)

class BCBFocusTextCrosscheckTests(unittest.TestCase):
 def test_four_annual_indicators_and_three_monthly_indicators(self):
  t=TEXT.read_text(encoding="utf-8")
  annual,monthly=t.split("Focus - Relatório de Mercado Pág. 1/2",1)
  for beginning in ("IPCA (variação %)","PIB Total (variação % sobre ano anterior)",
                    "Câmbio (R$/US$)","Selic (% a.a)"):
   self.assertEqual(sum(x.startswith(beginning+" ") for x in annual.splitlines()),1)
   self.assertEqual(sum(x.startswith(beginning+" ") for x in monthly.splitlines()),
                    0 if beginning.startswith("PIB Total") else 1)
 def test_real_extracted_text_matches_all_pinned_selected_values(self):
  r=evaluate()
  self.assertEqual((r["schema"],r["state"]),(SCHEMA,STATE))
  self.assertEqual((r["annual_matches"],r["monthly_matches"]),(12,8))
  self.assertEqual(len(r["match_details"]),20)
  self.assertTrue(r["extracted_text_blob_integrity_matched"])
  self.assertEqual(r["extracted_text_git_blob_sha1"],EXTRACTED_TEXT_GIT_BLOB_SHA1)
 def test_specific_selic_year_and_november_month_reconciled(self):
  rows=evaluate()["match_details"]
  self.assertEqual(next(x for x in rows if x["indicator"]=="SELIC" and x["period"]=="2026")["median"],"13.50")
  self.assertEqual(next(x for x in rows if x["indicator"]=="SELIC" and x["period"]=="2026-11")["median"],"13.50")
 def test_ipca_three_years_and_months(self):
  r=evaluate()
  d={(x["indicator"],x["period"]):x["median"] for x in r["match_details"]}
  self.assertEqual(d[("IPCA","2026")],"5.22")
  self.assertEqual(d[("IPCA","2027")],"4.76")
  self.assertEqual(d[("IPCA","2028")],"4.00")
  self.assertEqual(d[("IPCA","2026-11")],"0.35")
  self.assertEqual(d[("IPCA_SMOOTHED_12M","ROLLING_12M")],"4.96")
 def test_dollar_monthly_vs_yearly_labels_stay_distinct(self):
  r=evaluate()
  rows={(x["indicator"],x["period"]):x for x in r["match_details"]}
  self.assertEqual(rows[("FX_BRL_PER_USD","2026")]["median"],"5.34")
  self.assertEqual(rows[("FX_BRL_PER_USD","2026-11")]["median"],"5.32")
 def test_pdf_binary_is_not_archived_or_cryptographically_verified(self):
  r=evaluate()
  for flag in ("original_pdf_bytes_archived",
               "original_pdf_cryptographic_signature_verified",
               "independent_bcb_http_receipt_attested",
               "extraction_is_official_original_binary",
               "point_in_time_historical_capture_proven"):
   self.assertFalse(r[flag],flag)
  self.assertIsNone(r["original_pdf_sha256"])
 def test_text_blob_id_is_not_original_pdf_hash(self):
  r=evaluate()
  self.assertEqual(len(r["extracted_text_git_blob_sha1"]),40)
  self.assertIsNone(r["original_pdf_sha256"])
  self.assertNotEqual(r["source_evidence_kind"],"ORIGINAL_PDF")
 def test_cannot_feed_wdo_win_trade_or_live_service(self):
  r=evaluate()
  self.assertEqual(r["fx_win_wdo_direction"],"AGUARDAR")
  self.assertIsNone(r["probability_calibrated"])
  for flag in ("pre_event_market_expectation_proven",
               "next_copom_consensus_verified","actual_copom_known",
               "real_oos_accuracy_proven","can_feed_live_radar",
               "trade_authorized","worker_enabled","scheduler_enabled",
               "paid_provider_approved","render_configuration_changed"):
   self.assertFalse(r[flag],flag)
 def test_changed_text_bytes_refused_even_with_plausible_rate(self):
  raw=text_bytes()
  for before,after in ((b"5,19 5,22",b"5,19 5,23"),
                       (b"13,25 13,50",b"13,25 13,75"),
                       (b"30 de outubro de 2026",b"29 de outubro de 2026")):
   with self.subTest(candidate=before):
    changed=raw.replace(before,after,1)
    self.assertNotEqual(changed,raw)
    self.assertEqual(evaluate(changed)["state"],DENIED)
 def test_missing_xml_synthetic_and_invalid_raw_content_refused(self):
  for raw in (None,{},b"",b"fake",b"x"*25001,"text",b"\xff"*5000):
   with self.subTest(rawtype=str(type(raw))):
    self.assertEqual(evaluate(raw)["state"],DENIED)
 def test_modified_annual_reported_value_refused(self):
  d=document()
  d["annual_medians"][0]["now"]="5.23"
  self.assertEqual(evaluate(doc=d)["state"],DENIED)
 def test_modified_annual_respondent_count_refused(self):
  d=document()
  d["annual_medians"][0]["respondents_30d"]=10
  self.assertEqual(evaluate(doc=d)["state"],DENIED)
 def test_modified_monthly_2026_11_selic_rejected(self):
  d=document()
  x=next(x for x in d["monthly_medians"] if x["indicator"]=="SELIC" and x["period"]=="2026-11")
  x["now"]="13.75"
  self.assertEqual(evaluate(doc=d)["state"],DENIED)
 def test_false_claim_original_pdf_binary_sha_rejected(self):
  d=document();d["original_pdf_bytes_archived"]=True
  self.assertEqual(evaluate(doc=d)["state"],DENIED)
  d=document();d["original_pdf_sha256"]="a"*64
  self.assertEqual(evaluate(doc=d)["state"],DENIED)
 def test_backdating_extracted_pdf_research_denied(self):
  self.assertEqual(evaluate(at=datetime(2026,11,3,0,tzinfo=timezone.utc))["state"],DENIED)
  self.assertEqual(evaluate(at=datetime(2026,11,2,23,tzinfo=timezone.utc))["state"],DENIED)
 def test_explicit_utc_offset_normalized(self):
  self.assertEqual(evaluate(at=datetime.fromisoformat("2026-11-03T12:01:00-04:00"))["state"],STATE)
 def test_naive_datetime_rejected(self):
  with self.assertRaises(ValueError):
   evaluate(at=datetime(2026,11,3,16))
 def test_reordered_monthly_observations_cannot_change_crosschecked_content(self):
  d=document();d["monthly_medians"].reverse()
  # Cross-check is based on indicator+period identity, not row order:
  # provenance still only via exact extracted text, not by index.
  self.assertEqual(evaluate(doc=d)["state"],STATE)

if __name__=="__main__":unittest.main()
