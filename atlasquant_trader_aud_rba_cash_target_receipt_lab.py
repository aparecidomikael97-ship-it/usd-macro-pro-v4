"""RBA AUD cash rate *target* current HTML source gate, pure LAB.

Official https://www.rba.gov.au/cash-rate-target-overview.html.
Target is NOT realized interbank overnight cash rate/AONIA. The effective
date is NOT the 2:30 pm Sydney MPC publication time. Current homepage
cannot attest historic original first-available publication, CPI, pre-
event forex predictions or trading profitability.

Receipts/bytes are caller-supplied local claims: matching SHA never
authenticates issuer, TLS transaction, vintage or original release.
No network, files, account, broker, positions, signals or scheduled work.
"""
from __future__ import annotations

from datetime import date, datetime, timezone, timedelta
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from html.parser import HTMLParser
import re
from typing import Any

SCHEMA="ATLASQUANT_AUD_RBA_CASH_RATE_TARGET_HTML_RECEIPT_LAB_V1"
URL="https://www.rba.gov.au/cash-rate-target-overview.html"
HISTORY_URL="https://www.rba.gov.au/statistics/cash-rate/"
MAX_BYTES=250_000
SHA64=re.compile(r"[0-9a-f]{64}\Z")
PERCENT=re.compile(r"(?:0|[1-9]\d{0,1})(?:\.\d{1,3})?\Z")
MONTH=r"(?:January|February|March|April|May|June|July|August|September|October|November|December)"
DATE=re.compile(rf"([1-9]|[12]\d|3[01]) ({MONTH}) (20\d\d)\Z")
CLAIM=re.compile(
    rf"\bCash rate target\s+"
    rf"(?P<rate>(?:0|[1-9]\d{{0,1}})(?:\.\d{{1,3}})?)\s*%\s+"
    rf"Effective date\s+(?P<effective>(?:[1-9]|[12]\d|3[01]) {MONTH} 20\d\d)\s+"
    rf"Next update\s+(?P<next>2[.]30 pm,\s*(?:[1-9]|[12]\d|3[01]) {MONTH} 20\d\d)",
    flags=re.I,
)
RECEIPT_KEYS=frozenset((
    "source_url","final_url","http_status","content_type",
    "body_sha256","started_at_utc","finished_at_utc",
    "https_validation_claim","redirects_followed",
))

class _Visible(HTMLParser):
    def __init__(self)->None:
        super().__init__(convert_charrefs=True)
        self.parts:list[str]=[]
        self.skip=0
    def handle_starttag(self,tag,attrs):
        if tag in ("script","style","noscript","svg"):
            self.skip+=1
    def handle_endtag(self,tag):
        if tag in ("script","style","noscript","svg") and self.skip:
            self.skip-=1
    def handle_data(self,text):
        if not self.skip:
            self.parts.append(text)

def _base(reason:str)->dict[str,Any]:
    return {
        "schema":SCHEMA,"state":"LAB_AUD_RBA_CASH_TARGET_RECEIPT_BLOCKED",
        "reason":reason,"currency":"AUD","issuer":"Reserve Bank of Australia",
        "instrument":"RBA_CASH_RATE_TARGET","source_url":URL,
        "history_source_reference_url":HISTORY_URL,
        "raw_html_sha256_matches_local_receipt":False,
        "https_transport_claim_structurally_consistent":False,
        "target_page_semantics_consistent":False,
        "target_cash_rate_pct_claim":None,
        "target_effective_date_claim":None,
        "issuer_next_update_sydney_local_claim":None,
        "source_observed_at_utc_claim":None,
        "overnight_aonia_realized_rate_mistaken_for_target":False,
        "effective_date_treated_as_publication_instant":False,
        "sydney_1430_assumed_utc_without_timezone":False,
        "release_first_seen_independently_attested":False,
        "historical_policy_vintage_authenticated":False,
        "rba_screenshot_or_html_original_captured":False,
        "last_mpc_statement_timestamp_authenticated":False,
        "issuer_monetary_policy_model_calibrated":False,
        "bilateral_fx28_macro_complete":False,
        "g8_policy_sources_ready":False,
        "fx_bias":None,"calibrated_probability":None,
        "validated_accuracy":None,
        "operational_bias":"AGUARDAR",
        "trade_authorized":False,"publishable":False,
        "worker_enabled":False,"scheduler_enabled":False,
        "live_alert_allowed":False,
        "network_calls":0,"files_written":0,"new_cost_brl":0,
        "research_only":True,
    }

def _clock(raw:Any)->datetime|None:
    if type(raw) is not str or not re.fullmatch(r"20\d\d-\d\d-\d\dT\d\d:\d\d:\d\dZ",raw):
        return None
    try:
        return datetime.strptime(raw,"%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return None

def _cutoff(raw:Any)->datetime|None:
    if not isinstance(raw,datetime) or raw.tzinfo is None or raw.microsecond:
        return None
    try:
        return raw.astimezone(timezone.utc) if raw.utcoffset() is not None else None
    except (TypeError,ValueError,OverflowError):
        return None

def _date(raw:Any)->date|None:
    if type(raw) is not str or DATE.fullmatch(raw) is None:
        return None
    try:
        return datetime.strptime(raw,"%d %B %Y").date()
    except ValueError:
        return None

def inspect_rba_cash_target_current_receipt_lab(
    *,original_html:Any,receipt:Any,decision_at_utc:Any
)->dict[str,Any]:
    out=_base("INVALID_OR_MISSING_SOURCE_BYTES_RECEIPT_OR_CUTOFF")
    cutoff=_cutoff(decision_at_utc)
    if (type(original_html) is not bytes
        or not 150<=len(original_html)<=MAX_BYTES
        or type(receipt) is not dict or set(receipt)!=RECEIPT_KEYS
        or cutoff is None):
        return out
    if (receipt["source_url"]!=URL or receipt["final_url"]!=URL
        or type(receipt["http_status"]) is not int or receipt["http_status"]!=200
        or type(receipt["content_type"]) is not str
        or receipt["content_type"].split(";")[0].strip().lower()!="text/html"
        or receipt["https_validation_claim"] is not True
        or receipt["redirects_followed"] is not False
        or type(receipt["body_sha256"]) is not str
        or SHA64.fullmatch(receipt["body_sha256"]) is None):
        out["reason"]="RBA_OFFICIAL_SOURCE_URL_MEDIA_OR_TLS_CLAIM_INVALID"
        return out
    before=_clock(receipt["started_at_utc"])
    after=_clock(receipt["finished_at_utc"])
    if (before is None or after is None
        or not before<=after<=cutoff
        or after-before>timedelta(seconds=30)):
        out["reason"]="RBA_CAPTURE_CLOCK_AFTER_CUTOFF_OR_INCOHERENT"
        return out
    if sha256(original_html).hexdigest()!=receipt["body_sha256"]:
        out["reason"]="RBA_ORIGINAL_HTML_SHA256_MISMATCH"
        return out
    out["raw_html_sha256_matches_local_receipt"]=True
    out["https_transport_claim_structurally_consistent"]=True
    try:
        parser=_Visible()
        parser.feed(original_html.decode("utf-8-sig","strict"))
        parser.close()
        visible=" ".join(" ".join(parser.parts).split())
        if ("Cash rate target – the key monetary policy decision" not in visible
            or "What is the cash rate?" not in visible):
            raise ValueError("incorrect RBA overview")
        # Both date & rate are in the same target card; quoted average
        # overnight AONIA elsewhere in the page is never used as the target.
        matched=CLAIM.findall(visible)
        if len(matched)!=1:
            raise ValueError("target card not unique")
        mat=CLAIM.search(visible)
        if mat is None:
            raise ValueError("target card not found")
        raw_rate=mat.group("rate")
        amount=Decimal(raw_rate)
        effective=_date(mat.group("effective"))
        next_text=mat.group("next")
        next_date=_date(next_text.split(",",1)[1].strip())
        if (PERCENT.fullmatch(raw_rate) is None or not amount.is_finite()
            or not Decimal("0")<=amount<=Decimal("30")
            or effective is None or next_date is None
            or effective>=after.date()
            or next_date<=after.date()):
            raise ValueError("rate or time not causally valid")
    except (UnicodeError,ValueError,TypeError,InvalidOperation,OverflowError):
        out["reason"]="RBA_CASH_TARGET_CARD_RATE_EFFECTIVE_OR_NEXT_UPDATE_INVALID"
        return out
    out.update({
        "state":"LAB_AUD_RBA_CASH_TARGET_HTML_LOCALLY_CHECKED_NO_GO",
        "reason":"CURRENT_WEBPAGE_LOCAL_CLAIM_NOT_ORIGINAL_MPC_RELEASE_PIT_VINTAGE",
        "target_page_semantics_consistent":True,
        "target_cash_rate_pct_claim":str(amount),
        "target_effective_date_claim":effective.isoformat(),
        "issuer_next_update_sydney_local_claim":next_text,
        "source_observed_at_utc_claim":after.isoformat(),
    })
    return out

__all__=("SCHEMA","URL","HISTORY_URL","MAX_BYTES",
         "inspect_rba_cash_target_current_receipt_lab")
