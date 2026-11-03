"""Official BCB Focus PDF TEXT cross-check, no original PDF binary or live bias.

The Bank Central BCB page /publicacoes/focus/30102026 says publication on
2026-11-03 and links R20261030.pdf. The values here are copied from text
extracted from that official PDF, pages 1 and 2. Raw bytes, independent
receipt timestamps and source signature were NOT archived or attested.
"""
from __future__ import annotations
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping
from atlasquant_trader_brazil_focus_documentary_lab import MEDIANS
from atlasquant_trader_brazil_focus_secondary_triage_lab import REPORTED_NEW

SCHEMA="ATLASQUANT_BCB_FOCUS_20261030_OFFICIAL_PDF_TEXT_REVIEW_LAB_V1"
STATE="LAB_BCB_OFFICIAL_FOCUS_TEXT_REVIEW_NOT_RAW_ARCHIVE"
DENIED="LAB_BCB_OFFICIAL_FOCUS_REVIEW_REFUSED"
OFFICIAL_PAGE="https://www.bcb.gov.br/publicacoes/focus/30102026"
OFFICIAL_PDF="https://www.bcb.gov.br/content/focus/focus/R20261030.pdf"
CUTOFF=datetime(2026,11,3,15,tzinfo=timezone.utc)
# Indicator/year/old/new/unit/respondents (per year 30-day window).
PINNED_ANNUAL=(
 ("IPCA","2026","5.19","5.22","PCT_CALENDAR_YEAR",144),
 ("IPCA","2027","4.34","4.76","PCT_CALENDAR_YEAR",144),
 ("IPCA","2028","3.75","4.00","PCT_CALENDAR_YEAR",131),
 ("REAL_GDP","2026","1.80","1.76","PCT_CALENDAR_YEAR",117),
 ("REAL_GDP","2027","1.31","1.20","PCT_CALENDAR_YEAR",116),
 ("REAL_GDP","2028","1.81","1.80","PCT_CALENDAR_YEAR",87),
 ("FX_BRL_PER_USD","2026","5.05","5.34","BRL_PER_USD_DECEMBER_REF",120),
 ("FX_BRL_PER_USD","2027","5.15","5.40","BRL_PER_USD_DECEMBER_REF",119),
 ("FX_BRL_PER_USD","2028","5.20","5.40","BRL_PER_USD_DECEMBER_REF",93),
 ("SELIC","2026","13.25","13.50","PCT_AA_YEAR_END",143),
 ("SELIC","2027","11.75","12.50","PCT_AA_YEAR_END",143),
 ("SELIC","2028","10.00","11.00","PCT_AA_YEAR_END",125),
)
# Page 2: month or rolling periods, not next-meeting outcomes.
PINNED_MONTHLY=(
 ("IPCA","2026-10","0.27","PCT_MONTHLY"),
 ("IPCA","2026-11","0.35","PCT_MONTHLY"),
 ("IPCA","2026-12","0.60","PCT_MONTHLY"),
 ("IPCA_SMOOTHED_12M","ROLLING_12M","4.96","PCT_12M_FORECAST"),
 ("FX_BRL_PER_USD","2026-11","5.32","BRL_PER_USD_MONTH_AVERAGE"),
 ("FX_BRL_PER_USD","2026-12","5.34","BRL_PER_USD_MONTH_AVERAGE"),
 ("SELIC","2026-11","13.50","PCT_AA_MONTH_END"),
 ("SELIC","2026-12","13.50","PCT_AA_MONTH_END"),
)
TARGETS={"IPCA":"CALENDAR_YEAR_CHANGE","REAL_GDP":"CALENDAR_YEAR_CHANGE",
 "FX_BRL_PER_USD":"DECEMBER_AVERAGE_FX","SELIC":"YEAR_END_POLICY_TARGET"}

def _refused(reason: str) -> dict[str,Any]:
 return {"schema":SCHEMA,"state":DENIED,"reason":reason,
   "annual_revisions":[],"monthly_forecasts":[],"win_wdo_context":[],
   "official_page_verified_documentary":False,
   "official_pdf_text_reviewed_documentary":False,
   "original_official_pdf_bytes_archived":False,"original_pdf_sha256":None,
   "independent_source_receipt_verified":False,
   "next_copom_meeting_consensus_verified":False,
   "next_copom_market_implied_probability":None,
   "actual_copom_decision_known":False,
   "point_in_time_forecast_input_attested":False,
   "directional_bias":"AGUARDAR","probability_calibrated":None,
   "can_feed_live_radar":False,"can_feed_real_oos":False,
   "trade_authorized":False,"worker_enabled":False,
   "scheduler_enabled":False,"render_configuration_changed":False,
   "paid_provider_approved":False}

def _number(value:Any) -> Decimal | None:
 if not isinstance(value,str) or len(value)>25:return None
 try: d=Decimal(value)
 except (ValueError,InvalidOperation):return None
 return d if d.is_finite() and abs(d)<100000 else None

def review_bcb_focus_official_text_lab(
 payload: Any, *, evaluated_at:datetime
) -> dict[str,Any]:
 """Only documents BCB PDF content transcribed after research; no trade."""
 if not isinstance(evaluated_at,datetime) or evaluated_at.tzinfo is None or evaluated_at.utcoffset() is None:
  raise ValueError("Timezone-aware research time required")
 if evaluated_at.astimezone(timezone.utc)<CUTOFF:
  return _refused("Do not backdate research to before Nov3 conservative cutoff")
 expected_fields={"schema","state","review_date_utc","reference_date",
   "published_on","landing_page_url","pdf_url","document_type",
   "original_pdf_bytes_archived","original_pdf_sha256",
   "annual_medians","monthly_medians"}
 if not isinstance(payload,Mapping) or set(payload)!=expected_fields:
  return _refused("Unknown or missing official-document fields")
 if (payload["schema"]!=SCHEMA or payload["state"]!=STATE or
     payload["review_date_utc"]!="2026-11-03" or
     payload["reference_date"]!="2026-10-30" or
     payload["published_on"]!="2026-11-03" or
     payload["landing_page_url"]!=OFFICIAL_PAGE or
     payload["pdf_url"]!=OFFICIAL_PDF or
     payload["document_type"]!="OFFICIAL_BCB_FOCUS_PDF_TEXT_EXTRACTED_NO_RAW_BYTES" or
     payload["original_pdf_bytes_archived"] is not False or
     payload["original_pdf_sha256"] is not None):
  return _refused("Official identity changed or unearned binary verification claimed")
 annual=payload["annual_medians"]; monthly=payload["monthly_medians"]
 if (not isinstance(annual,list) or not isinstance(monthly,list) or
     len(annual)!=12 or len(monthly)!=8):
  return _refused("Missing or extra documentary medians")
 past={(x["indicator"],x["target_type"],x["target_period"]):x for x in MEDIANS}
 from_news={(i,t,y):Decimal(v) for i,t,y,v,u in REPORTED_NEW}
 revised=[]; reconciled=0
 for raw,fixed in zip(annual,PINNED_ANNUAL):
  if not isinstance(raw,Mapping) or set(raw)!={"indicator","year","previous","now","unit","respondents_30d"}:
   return _refused("Malformed annual median row")
  ind,year,old,new,unit,n=fixed
  if (raw["indicator"],raw["year"],raw["unit"],raw["respondents_30d"])!=(ind,year,unit,n) or type(raw["respondents_30d"]) is not int:
   return _refused("Annual indicator, date, unit or respondent count differs")
  a,b=_number(raw["previous"]),_number(raw["now"])
  if a is None or b is None or a!=Decimal(old) or b!=Decimal(new):
   return _refused("Official annual table transcription altered")
  if year in ("2026","2027"):
   key=(ind,TARGETS[ind],year); previous=past.get(key)
   if previous is None or _number(previous["median_value"])!=a or from_news.get(key)!=b:
    return _refused("BCB PDF not reconciled with prior official and news triage")
   reconciled+=1
  revised.append({"indicator":ind,"target_period":year,"target_type":TARGETS[ind],
    "previous_focus_median":str(a),"new_pdf_median":str(b),
    "signed_revision":str(b-a),"unit":unit,"respondents_30d":n,
    "is_economic_actual":False,"is_next_copom_meeting_consensus":False})
 month_out=[]
 for raw,fixed in zip(monthly,PINNED_MONTHLY):
  if not isinstance(raw,Mapping) or set(raw)!={"indicator","period","now","unit"}:
   return _refused("Malformed monthly Focus row")
  ind,period,value,unit=fixed
  if (raw["indicator"],raw["period"],raw["unit"])!=(ind,period,unit) or _number(raw["now"])!=Decimal(value):
   return _refused("Official monthly reference mismatch")
  month_out.append({"indicator":ind,"target_period":period,"median":value,
    "unit":unit,"source_page":2,"is_meeting_event_actual":False,
    "is_next_copom_consensus":False})
 context=[{"instrument":instrument,"horizon":h,
  "focus_report_date":"2026-10-30",
  "selic_year_end_2026_pct":"13.50",
  "selic_november_month_end_pct":"13.50",
  "nov4_copom_decision_consensus_pct":None,
  "policy_event_probability":None,"directional_bias":"AGUARDAR",
  "trade_authorized":False} for instrument in ("WIN","WDO") for h in ("D1","W1","MN1")]
 return {**_refused(""),"state":STATE,"reason":None,
   "annual_revisions":revised,"monthly_forecasts":month_out,
   "annual_count":len(revised),"monthly_count":len(month_out),
   "reconciled_2026_2027_with_secondary_and_prior":reconciled,
   "official_page_verified_documentary":True,
   "official_pdf_text_reviewed_documentary":True,
   "pdf_source_url":OFFICIAL_PDF,
   "source_publication_date_only":"2026-11-03",
   "win_wdo_context":context,
   "why_no_bias":"BCB text reviewed but original bytes and independent receipt not attested. Month-average FX and month-end Selic/year-end Focus expectations are not the Nov4 Copom decision, market-implied odds or a WIN/WDO directional forecast."}

__all__=["SCHEMA","STATE","DENIED","PINNED_ANNUAL","PINNED_MONTHLY",
 "OFFICIAL_PDF","OFFICIAL_PAGE","CUTOFF","review_bcb_focus_official_text_lab"]
