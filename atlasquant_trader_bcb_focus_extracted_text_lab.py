"""Audit extracted TEXT from the published official BCB Focus PDF, LAB only.

The file here contains third-party extracted text (NOT the official PDF bytes).
A Git blob hash checks this exact extraction's local integrity only. Values
are reconciled with the already versioned transcription for 12 annual
forecasts and 8 monthly references. Original binary, source signature,
HTTP receipt and historic availability remain unverified; no trading allowed.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from hashlib import sha1
import re
from typing import Any, Mapping

from atlasquant_trader_bcb_focus_official_review_lab import (
    PINNED_ANNUAL, PINNED_MONTHLY, SCHEMA as REVIEW_SCHEMA,
    STATE as REVIEW_STATE, OFFICIAL_PDF,
)

SCHEMA="ATLASQUANT_BCB_FOCUS_PDF_TEXT_EXTRACT_CROSSCHECK_LAB_V1"
STATE="LAB_OFFICIAL_FOCUS_TEXT_MATCHED_NO_ORIGINAL_PDF"
DENIED="LAB_FOCUS_TEXT_CROSSCHECK_REFUSED"
EXTRACTED_TEXT_GIT_BLOB_SHA1="7123568a4140fb751c757f8fc423538d0905b18c"
RESEARCH_CUTOFF=datetime(2026,11,3,15,tzinfo=timezone.utc)
ROW_PATTERN=re.compile(
    r"(\d+,\d{2})\s+(\d+,\d{2})\s+(\d+,\d{2})\s+"
    r"(?:[▲▼]\s*)?\(\d+\)\s+(\d+)"
)
LABELS={
 "IPCA":"IPCA (variação %)",
 "REAL_GDP":"PIB Total (variação % sobre ano anterior)",
 "FX_BRL_PER_USD":"Câmbio (R$/US$)",
 "SELIC":"Selic (% a.a)",
}

def _deny(reason:str)->dict[str,Any]:
 return {
  "schema":SCHEMA, "state":DENIED, "reason":reason,
  "annual_matches":0,"monthly_matches":0,"match_details":[],
  "extracted_text_blob_integrity_matched":False,
  "original_pdf_bytes_archived":False,"original_pdf_sha256":None,
  "original_pdf_cryptographic_signature_verified":False,
  "independent_bcb_http_receipt_attested":False,
  "extraction_is_official_original_binary":False,
  "point_in_time_historical_capture_proven":False,
  "pre_event_market_expectation_proven":False,
  "next_copom_consensus_verified":False,"actual_copom_known":False,
  "fx_win_wdo_direction":"AGUARDAR","probability_calibrated":None,
  "real_oos_accuracy_proven":False,"can_feed_live_radar":False,
  "trade_authorized":False,"worker_enabled":False,
  "scheduler_enabled":False,"render_configuration_changed":False,
  "paid_provider_approved":False,
 }

def _git_blob_sha1(raw:bytes)->str:
 return sha1(b"blob "+str(len(raw)).encode("ascii")+b"\x00"+raw).hexdigest()

def _row(section:str,label:str)->list[tuple[str,str,int]]|None:
 matches=[line for line in section.splitlines() if line.startswith(label+" ")]
 if len(matches)!=1:return None
 groups=ROW_PATTERN.findall(matches[0])
 if not groups:return None
 return [(old.replace(",","."), now.replace(",","."),int(n))
         for _four_weeks,old,now,n in groups]

def crosscheck_bcb_focus_extracted_text_lab(
 raw:Any, transcription:Any, *, evaluated_at:datetime,
)->dict[str,Any]:
 """Verify static PDF-to-text extraction agrees with a pinned transcription.

 No external fetch or content signature check. The SHA-1 is a Git blob
 identifier of the *text extraction*, not of the BCB original PDF.
 """
 if not isinstance(evaluated_at,datetime) or evaluated_at.tzinfo is None or evaluated_at.utcoffset() is None:
  raise ValueError("Evaluation instant must include explicit timezone")
 if evaluated_at.astimezone(timezone.utc)<RESEARCH_CUTOFF:
  return _deny("Do not backdate the text audit before research day cutoff")
 if not isinstance(raw,bytes) or len(raw)>25000 or len(raw)<3000:
  return _deny("Missing, truncated or oversized extracted text bytes")
 if _git_blob_sha1(raw)!=EXTRACTED_TEXT_GIT_BLOB_SHA1:
  return _deny("Extracted text content differs from the archived Git blob")
 try:
  content=raw.decode("utf-8")
 except UnicodeError:
  return _deny("Extraction is not UTF8")
 if content.count("Focus - Relatório de Mercado Pág. 1/2")!=1 or content.count("Focus - Relatório de Mercado Pág. 2/2")!=1:
  return _deny("Expected precisely two documented PDF text pages")
 first,rest=content.split("Focus - Relatório de Mercado Pág. 1/2",1)
 second=rest.split("Focus - Relatório de Mercado Pág. 2/2",1)[0]
 if "Expectativas de Mercado 30 de outubro de 2026" not in first or "Expectativas de Mercado 30 de outubro de 2026" not in second:
  return _deny("Missing reviewed official document title and date")
 if not isinstance(transcription,Mapping) or set(transcription)!={
  "schema","state","review_date_utc","reference_date","published_on",
  "landing_page_url","pdf_url","document_type","original_pdf_bytes_archived",
  "original_pdf_sha256","annual_medians","monthly_medians",
 }:
  return _deny("Reviewed PDF document structure changed")
 if (transcription["schema"]!=REVIEW_SCHEMA or transcription["state"]!=REVIEW_STATE
     or transcription["pdf_url"]!=OFFICIAL_PDF
     or transcription["reference_date"]!="2026-10-30"
     or transcription["published_on"]!="2026-11-03"
     or transcription["original_pdf_bytes_archived"] is not False
     or transcription["original_pdf_sha256"] is not None):
  return _deny("PDF original source and original-binary absence not preserved")
 annual=transcription["annual_medians"]
 monthly=transcription["monthly_medians"]
 if not isinstance(annual,list) or not isinstance(monthly,list) or len(annual)!=12 or len(monthly)!=8:
  return _deny("Required full official transcription missing")
 totals={"annual":0,"monthly":0}
 details=[]
 for indicator,label in LABELS.items():
  arr=_row(first,label)
  if arr is None or len(arr)!=4:
   return _deny("Missing or ambiguous annual PDF extracted row for "+indicator)
  for year_index,year in enumerate(("2026","2027","2028")):
   expected=next((x for x in PINNED_ANNUAL if x[0]==indicator and x[1]==year),None)
   actual=next((x for x in annual if isinstance(x,Mapping)
                and x.get("indicator")==indicator and x.get("year")==year),None)
   if expected is None or actual is None:return _deny("Missing annual target")
   old,new,n=arr[year_index]
   if (old,new,n)!=(expected[2],expected[3],expected[5]):
    return _deny("Annual PDF text differs from pinned expected table")
   if (actual.get("previous"),actual.get("now"),actual.get("respondents_30d"))!=(expected[2],expected[3],expected[5]):
    return _deny("Annual documentary transcription disagrees with extracted text")
   totals["annual"]+=1
   details.append({"indicator":indicator,"period":year,"kind":"ANNUAL",
                   "median":new,"respondents_30d":n})
  if indicator not in ("IPCA","FX_BRL_PER_USD","SELIC"):continue
  arr_month=_row(second,label)
  nmonth={"IPCA":4,"FX_BRL_PER_USD":2,"SELIC":2}[indicator]
  if arr_month is None or len(arr_month)!=nmonth:
   return _deny("Monthly PDF extracted row count mismatch for "+indicator)
  wanted=({"IPCA":[("IPCA","2026-10"),("IPCA","2026-11"),("IPCA","2026-12"),
                       ("IPCA_SMOOTHED_12M","ROLLING_12M")],
           "FX_BRL_PER_USD":[("FX_BRL_PER_USD","2026-11"),("FX_BRL_PER_USD","2026-12")],
           "SELIC":[("SELIC","2026-11"),("SELIC","2026-12")]})[indicator]
  for (kind,period),(_old,new,_n) in zip(wanted,arr_month):
   expected=next((x for x in PINNED_MONTHLY if x[0]==kind and x[1]==period),None)
   actual=next((x for x in monthly if isinstance(x,Mapping)
                and x.get("indicator")==kind and x.get("period")==period),None)
   if expected is None or actual is None or new!=expected[2] or actual.get("now")!=expected[2]:
    return _deny("Monthly official PDF text and transcription disagree")
   totals["monthly"]+=1
   details.append({"indicator":kind,"period":period,"kind":"MONTHLY","median":new})
 if totals!={"annual":12,"monthly":8}:
  return _deny("Missing expected total official source checks")
 return {**_deny(""),"state":STATE,"reason":None,
   "annual_matches":12,"monthly_matches":8,"match_details":details,
   "source_bcb_pdf_url":OFFICIAL_PDF,
   "extracted_text_git_blob_sha1":EXTRACTED_TEXT_GIT_BLOB_SHA1,
   "extracted_text_blob_integrity_matched":True,
   "source_evidence_kind":"THIRD_PARTY_TEXT_EXTRACTED_FROM_OFFICIAL_PDF_URL",
   "note":"Matched extracted text against 20 pinned Focus observations. Neither a raw PDF download nor a signed BCB-origin response; no live macro prediction."}

__all__=["SCHEMA","STATE","DENIED","EXTRACTED_TEXT_GIT_BLOB_SHA1",
         "crosscheck_bcb_focus_extracted_text_lab"]
