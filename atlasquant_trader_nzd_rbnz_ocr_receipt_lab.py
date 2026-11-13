"""RBNZ Official Cash Rate (OCR) policy vs commentary source receipt (LAB).

Official current overview: https://www.rbnz.govt.nz/monetary-policy/
about-monetary-policy/the-official-cash-rate (joined below).
OCR is the current **decided policy rate**, not headline CPI,
forecast of a future OCR, home mortgage rate, deposit market rate,
or currency/equity price. A comment saying "may need to increase"
does NOT mean that a rate increase has happened.

The page reports an update at 2:00pm local New Zealand time, not
necessarily an independently attested original announcement timestamp
or a UTC instant. Without issuer first-seen provenance never publish
historical point-in-time rates, backtested forecasts, directional
strength scores, position changes, or confidence estimates.

Pure/offline validation of caller-supplied original HTML/receipt, no
network, IO, MT5, orders, account, push, recurring worker or costs.
"""
from __future__ import annotations

from datetime import date, datetime, timezone, timedelta
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from html.parser import HTMLParser
import re
from typing import Any

SCHEMA="ATLASQUANT_NZD_RBNZ_OFFICIAL_CASH_RATE_HTML_RECEIPT_LAB_V1"
URL="https://www.rbnz.govt.nz/monetary-policy/about-monetary-policy/the-official-cash-rate"
MAX_BYTES=400_000
HEX64=re.compile(r"[0-9a-f]{64}\Z")
PCT=re.compile(r"(?:0|[1-9]\d{0,1})(?:\.\d{1,3})?\Z")
MONTH=r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
DATE_TEXT=rf"(?:0?[1-9]|[12]\d|3[01]) {MONTH} 20\d\d"
OCR_CARD=re.compile(
    rf"\bOfficial Cash Rate\s+(?P<rate>(?:0|[1-9]\d{{0,1}})(?:\.\d{{1,3}})?)\s*%\s+"
    rf"Updated:\s*(?P<updated>2:00pm,\s*{DATE_TEXT})\s+"
    rf"Next update:\s*(?P<next>2:00pm,\s*{DATE_TEXT})",
    flags=re.I,
)
RECEIPT_FIELDS=frozenset((
    "source_url","final_url","http_status","content_type",
    "body_sha256","started_at_utc","finished_at_utc",
    "https_validation_claim","redirects_followed",
))

class _PageText(HTMLParser):
    def __init__(self)->None:
        super().__init__(convert_charrefs=True)
        self.parts:list[str]=[]
        self.ignore=0
    def handle_starttag(self,tag,attrs):
        if tag in ("script","style","svg","noscript"):
            self.ignore+=1
    def handle_endtag(self,tag):
        if tag in ("script","style","svg","noscript") and self.ignore:
            self.ignore-=1
    def handle_data(self,content):
        if not self.ignore:
            self.parts.append(content)

def _base(reason:str)->dict[str,Any]:
    return {
        "schema":SCHEMA,"state":"LAB_NZD_RBNZ_OCR_RECEIPT_BLOCKED",
        "reason":reason,"currency":"NZD",
        "issuer":"Reserve Bank of New Zealand",
        "measure":"RBNZ_OFFICIAL_CASH_RATE",
        "official_source_url":URL,
        "original_html_sha256_matches_local_receipt":False,
        "http_transport_claim_structurally_coherent":False,
        "official_ocr_policy_card_locally_consistent":False,
        "official_cash_rate_pct_claim":None,
        "ocr_updated_nz_local_claim":None,
        "next_ocr_update_nz_local_claim":None,
        "original_source_received_utc_claim":None,
        "october_hold_decision_independently_attested":False,
        "september_change_publication_time_attested":False,
        "forecast_or_commentary_used_as_actual_ocr":False,
        "issuer_1400_local_assumed_utc_without_timezone":False,
        "issuer_first_release_available_at_cutoff_verified":False,
        "historical_first_seen_vintage_authenticated":False,
        "inflation_rate_used_as_ocr":False,
        "exchange_rate_used_as_ocr":False,
        "g8_policy_sources_ready":False,
        "fx28_bilateral_macro_complete":False,
        "calibrated_directional_probability":None,
        "historical_accuracy_validated":False,
        "operational_bias":"AGUARDAR",
        "trade_authorized":False,"publishable":False,
        "worker_enabled":False,"scheduler_enabled":False,
        "live_alert_allowed":False,
        "network_calls":0,"files_written":0,"new_cost_brl":0,
        "research_only":True,
    }

def _utc(raw:Any)->datetime|None:
    if type(raw) is not str or not re.fullmatch(
        r"20\d\d-\d\d-\d\dT\d\d:\d\d:\d\dZ",raw):
        return None
    try:
        return datetime.strptime(raw,"%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc)
    except ValueError:
        return None

def _cutoff(raw:Any)->datetime|None:
    if not isinstance(raw,datetime) or raw.tzinfo is None or raw.microsecond:
        return None
    try:
        return raw.astimezone(timezone.utc) if raw.utcoffset() is not None else None
    except (ValueError,TypeError,OverflowError):
        return None

def _day(raw:Any)->date|None:
    if type(raw) is not str or not re.fullmatch(DATE_TEXT,raw,re.I):
        return None
    try:
        return datetime.strptime(raw,"%d %b %Y").date()
    except ValueError:
        return None

def _rate(raw:Any)->Decimal|None:
    if type(raw) is not str or PCT.fullmatch(raw) is None:
        return None
    try:
        v=Decimal(raw)
        return v if v.is_finite() and Decimal("0")<=v<=Decimal("30") else None
    except InvalidOperation:
        return None

def inspect_rbnz_official_ocr_receipt_lab(
    *,original_html:Any,receipt:Any,decision_at_utc:Any
)->dict[str,Any]:
    out=_base("MISSING_OR_INVALID_ORIGINAL_BYTES_RECEIPT_OR_CUTOFF")
    cutoff=_cutoff(decision_at_utc)
    if (type(original_html) is not bytes
        or not 120<=len(original_html)<=MAX_BYTES
        or type(receipt) is not dict or set(receipt)!=RECEIPT_FIELDS
        or cutoff is None):
        return out
    if (receipt["source_url"]!=URL or receipt["final_url"]!=URL
        or type(receipt["http_status"]) is not int or receipt["http_status"]!=200
        or type(receipt["content_type"]) is not str
        or receipt["content_type"].split(";")[0].strip().lower()!="text/html"
        or receipt["https_validation_claim"] is not True
        or receipt["redirects_followed"] is not False
        or type(receipt["body_sha256"]) is not str
        or HEX64.fullmatch(receipt["body_sha256"]) is None):
        out["reason"]="RBNZ_OFFICIAL_URL_MEDIA_HTTP_OR_TLS_CLAIM_INVALID"
        return out
    before=_utc(receipt["started_at_utc"])
    after=_utc(receipt["finished_at_utc"])
    if (before is None or after is None
        or not before<=after<=cutoff
        or after-before>timedelta(seconds=30)):
        out["reason"]="RBNZ_LOCAL_CAPTURE_AFTER_DECISION_OR_BAD_CLOCK"
        return out
    if sha256(original_html).hexdigest()!=receipt["body_sha256"]:
        out["reason"]="RBNZ_ORIGINAL_HTML_SHA256_MISMATCH"
        return out
    out["original_html_sha256_matches_local_receipt"]=True
    out["http_transport_claim_structurally_coherent"]=True
    try:
        parser=_PageText()
        parser.feed(original_html.decode("utf-8-sig","strict"))
        parser.close()
        text=" ".join(" ".join(parser.parts).split())
        if ("The official cash rate (OCR)" not in text
            or "We set the OCR to keep inflation low and stable." not in text):
            raise ValueError("not the issuer OCR page")
        matches=list(OCR_CARD.finditer(text))
        if len(matches)!=1:
            raise ValueError("no unique OCR source card")
        card=matches[0]
        amount=_rate(card.group("rate"))
        update=card.group("updated")
        next_text=card.group("next")
        published_day=_day(update.split(",",1)[1].strip())
        scheduled_day=_day(next_text.split(",",1)[1].strip())
        if (amount is None or published_day is None or scheduled_day is None
            or published_day>=after.date()
            or scheduled_day<=after.date()):
            raise ValueError("OCR page stale or future")
    except (UnicodeError,TypeError,ValueError,InvalidOperation,OverflowError):
        out["reason"]="RBNZ_OCR_POLICY_CARD_OR_CHRONOLOGY_INVALID"
        return out
    out.update({
        "state":"LAB_NZD_RBNZ_OCR_HTML_LOCALLY_CHECKED_NO_GO",
        "reason":"CURRENT_SOURCE_HTML_NOT_INDEPENDENT_HISTORICAL_MPC_VINTAGE",
        "official_ocr_policy_card_locally_consistent":True,
        "official_cash_rate_pct_claim":str(amount),
        "ocr_updated_nz_local_claim":update,
        "next_ocr_update_nz_local_claim":next_text,
        "original_source_received_utc_claim":after.isoformat(),
    })
    return out

__all__=("SCHEMA","URL","MAX_BYTES",
         "inspect_rbnz_official_ocr_receipt_lab")
