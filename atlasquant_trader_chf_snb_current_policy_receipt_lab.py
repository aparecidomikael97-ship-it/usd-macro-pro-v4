"""SNB current policy rate vs sight deposits vs SARON source guard (LAB).

Only validate *caller-provided* raw public issuer HTML and a local HTTP/SHA
receipt from the SNB current-rate page. The SNB policy rate is not the
SARON market benchmark, the liquidity facility special rate, or the
interest on sight deposits ABOVE its threshold.

Current-page "valid from" DATE does not prove first issuer publication
TIME or historic point-in-time availability. Third-party SARON/BFIX
information has distinct data-rights notices: never extract, return,
or republish market benchmark prices/FX from this gate.

Pure, no HTTP, files, MT5, account, positions, orders, alerts,
directional probabilities, signal generation, scheduler or deploy.
"""
from __future__ import annotations

from datetime import date, datetime, timezone, timedelta
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from html.parser import HTMLParser
import re
from typing import Any

SCHEMA="ATLASQUANT_CHF_SNB_CURRENT_POLICY_RATE_HTML_RECEIPT_LAB_V1"
URL="https://www.snb.ch/en/srv/current_interest_exchange_rates"
POLICY_RELEASE_URL="https://www.snb.ch/en/publications/communication/press-releases-restricted/pre_20260924"
MAX_BYTES=350_000
SHA64=re.compile(r"[0-9a-f]{64}\Z")
PCT=r"(-?(?:0|[1-9]\d{0,1})(?:\.\d{1,3})?)"
DATE=r"([0-3]\d\.[01]\d\.20\d\d)"
POLICY_RE=re.compile(r"\bSNB policy rate\s+"+PCT+r"%\s+valid from\s+"+DATE+r"\b",re.I)
UP_TO_RE=re.compile(r"\bInterest rate on sight deposits up to threshold\s+"+PCT+r"%\s+valid from\s+"+DATE+r"\b",re.I)
ABOVE_RE=re.compile(r"\bInterest rate on sight deposits above threshold\s+"+PCT+r"%\s+valid from\s+"+DATE+r"\b",re.I)
DISCOUNT_RE=re.compile(r"\bDiscount:\s*(\d{1,3})\s+basis points\b",re.I)
RECEIPT_FIELDS=frozenset((
    "source_url","final_url","http_status","content_type",
    "body_sha256","started_at_utc","finished_at_utc",
    "https_validation_claim","redirects_followed",
))

class _VisibleText(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str]=[]
        self.skip_depth=0

    def handle_starttag(self,tag,attrs):
        if tag in ("script","style","noscript","svg"):
            self.skip_depth+=1

    def handle_endtag(self,tag):
        if tag in ("script","style","noscript","svg") and self.skip_depth:
            self.skip_depth-=1

    def handle_data(self,data):
        if not self.skip_depth:
            self.parts.append(data)


def _base(reason:str)->dict[str,Any]:
    return {
        "schema":SCHEMA,
        "state":"LAB_CHF_SNB_POLICY_RECEIPT_BLOCKED",
        "reason":reason,
        "currency":"CHF",
        "issuer":"Swiss National Bank",
        "measure":"SNB_POLICY_RATE",
        "source_url":URL,
        "september_2026_release_reference_url":POLICY_RELEASE_URL,
        "original_html_sha256_locally_matching":False,
        "http_transport_claim_locally_consistent":False,
        "snb_policy_rate_semantic_claim_consistent":False,
        "current_snb_policy_rate_pct_claim":None,
        "sight_deposit_up_to_threshold_pct_claim":None,
        "sight_deposit_above_threshold_pct_claim":None,
        "discount_basis_points_claim":None,
        "policy_valid_from_date_claim":None,
        "local_capture_finished_at_utc_claim":None,
        "saron_benchmark_extracted_or_republished":False,
        "bfix_exchange_rate_extracted_or_republished":False,
        "market_saron_conflated_with_policy_rate":False,
        "special_liquidity_facility_rate_conflated":False,
        "sight_deposit_above_threshold_conflated":False,
        "historical_issuer_first_release_verified":False,
        "issuer_policy_announcement_utc_verified":False,
        "current_page_is_historical_pit_vintage":False,
        "september_release_original_bytes_captured":False,
        "all_eight_g8_macro_sources_complete":False,
        "bilateral_fx28_macroeconomics_authenticated":False,
        "calibrated_directional_probability":None,
        "validated_fx_accuracy":None,
        "operational_bias":"AGUARDAR",
        "trade_authorized":False,
        "publishable":False,
        "worker_enabled":False,
        "scheduler_enabled":False,
        "live_alert_allowed":False,
        "network_calls":0,
        "files_written":0,
        "new_cost_brl":0,
        "research_only":True,
    }

def _clock(raw:Any)->datetime|None:
    if type(raw) is not str or not re.fullmatch(
        r"20\d\d-\d\d-\d\dT\d\d:\d\d:\d\dZ",raw
    ):
        return None
    try:
        return datetime.strptime(raw,"%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return None

def _decision(raw:Any)->datetime|None:
    if not isinstance(raw,datetime) or raw.tzinfo is None or raw.microsecond:
        return None
    try:
        return raw.astimezone(timezone.utc) if raw.utcoffset() is not None else None
    except (ValueError,TypeError,OverflowError):
        return None

def _amount(raw:Any)->Decimal|None:
    if type(raw) is not str:
        return None
    try:
        num=Decimal(raw)
        if not num.is_finite() or not Decimal("-25")<=num<=Decimal("50"):
            return None
        return num
    except InvalidOperation:
        return None

def _day(raw:Any)->date|None:
    if type(raw) is not str:
        return None
    try:
        return datetime.strptime(raw,"%d.%m.%Y").date()
    except ValueError:
        return None

def inspect_snb_current_policy_receipt_lab(
    *, original_html:Any, receipt:Any, decision_at_utc:Any,
)->dict[str,Any]:
    result=_base("INVALID_HTML_RECEIPT_OR_DECISION_CLOCK")
    decision=_decision(decision_at_utc)
    if (type(original_html) is not bytes
            or not 200<=len(original_html)<=MAX_BYTES
            or type(receipt) is not dict or set(receipt)!=RECEIPT_FIELDS
            or decision is None):
        return result
    if (receipt["source_url"]!=URL or receipt["final_url"]!=URL
            or type(receipt["http_status"]) is not int
            or receipt["http_status"]!=200
            or type(receipt["content_type"]) is not str
            or receipt["content_type"].split(";")[0].strip().lower()!="text/html"
            or receipt["https_validation_claim"] is not True
            or receipt["redirects_followed"] is not False
            or type(receipt["body_sha256"]) is not str
            or SHA64.fullmatch(receipt["body_sha256"]) is None):
        result["reason"]="SNB_URL_OR_HTTPS_TRANSPORT_CLAIM_NOT_EXACT"
        return result
    before=_clock(receipt["started_at_utc"])
    after=_clock(receipt["finished_at_utc"])
    if (before is None or after is None or not before<=after<=decision
            or after-before>timedelta(seconds=30)):
        result["reason"]="SNB_CAPTURE_AFTER_DECISION_OR_BAD_LOCAL_CLOCK"
        return result
    if sha256(original_html).hexdigest()!=receipt["body_sha256"]:
        result["reason"]="SNB_ORIGINAL_HTML_HASH_MISMATCH"
        return result
    result["original_html_sha256_locally_matching"]=True
    result["http_transport_claim_locally_consistent"]=True

    try:
        parser=_VisibleText()
        parser.feed(original_html.decode("utf-8-sig","strict"))
        parser.close()
        text=" ".join(" ".join(parser.parts).split())
        # Bind to actual page title, not a numeric mention in unrelated pages.
        if "Current interest rates and exchange rates" not in text:
            raise ValueError("wrong page title")
        policy=POLICY_RE.findall(text)
        upto=UP_TO_RE.findall(text)
        above=ABOVE_RE.findall(text)
        discounts=DISCOUNT_RE.findall(text)
        if any(len(records)!=1 for records in (policy,upto,above,discounts)):
            raise ValueError("missing or ambiguous SNB measures")
        policy_rate,policy_date=policy[0]
        upto_rate,upto_date=upto[0]
        above_rate,above_date=above[0]
        d_policy,d_upto,d_above=map(_day,(policy_date,upto_date,above_date))
        p,u,a=map(_amount,(policy_rate,upto_rate,above_rate))
        discount=int(discounts[0])
        if (any(x is None for x in (d_policy,d_upto,d_above,p,u,a))
                or not d_policy==d_upto==d_above
                or d_policy>=after.date()
                or not 0<=discount<=100
                or p!=u
                or p-a!=Decimal(discount)/Decimal(100)):
            raise ValueError("SNB policy/deposit dates/rates/discount mismatch")
    except (UnicodeError,ValueError,TypeError,OverflowError,AssertionError):
        result["reason"]="SNB_POLICY_VS_DEPOSIT_OR_HTML_SEMANTICS_INVALID"
        return result
    result.update({
        "state":"LAB_CHF_SNB_CURRENT_POLICY_HTML_LOCALLY_CHECKED_NO_GO",
        "reason":"CURRENT_SNB_PAGE_LOCAL_CAPTURE_NOT_HISTORICAL_ISSUER_FIRST_RELEASE",
        "snb_policy_rate_semantic_claim_consistent":True,
        "current_snb_policy_rate_pct_claim":str(p),
        "sight_deposit_up_to_threshold_pct_claim":str(u),
        "sight_deposit_above_threshold_pct_claim":str(a),
        "discount_basis_points_claim":discount,
        "policy_valid_from_date_claim":d_policy.isoformat(),
        "local_capture_finished_at_utc_claim":after.isoformat(),
    })
    return result

__all__=("SCHEMA","URL","POLICY_RELEASE_URL","MAX_BYTES",
         "inspect_snb_current_policy_receipt_lab")
