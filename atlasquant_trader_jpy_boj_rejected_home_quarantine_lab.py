"""BoJ rejected homepage forensic quarantine, LAB only; never a policy source.

Pure archive helper. It DOES NOT FETCH anything: a future explicit collector
may give it the original bytes and unmodified transport receipt after exactly
one request. Quarantined original/receipt reside outside official_macro_receipts,
so they cannot inflate current G8 coverage. One SHA-stamped immutable attempt;
any parse/receipt uncertainty => no write. Never retries or overwrites.
No securities data, FX market data, account, MT5, order, alert, scheduler.
"""
from __future__ import annotations
from datetime import datetime,timedelta,timezone
from hashlib import sha256
from pathlib import Path
from typing import Any
import json,re

from atlasquant_trader_jpy_boj_guideline_source_receipt_lab import (
    URL,ALLOWED_FINAL_URLS,MAX_BYTES,RECEIPT_KEYS,
    inspect_boj_home_guideline_receipt_lab,
)

SCHEMA="ATLASQUANT_JPY_BOJ_REJECTED_HOMEPAGE_DIAGNOSTIC_QUARANTINE_LAB_V1"
DENIED="BOJ_POLICY_GUIDELINE_INSTRUMENT_OR_HTML_STRUCTURE_INVALID"
LABEL="JPY_BOJ_HOMEPAGE_REJECTED"
SHA=re.compile(r"[a-f0-9]{64}\Z")
STAMP=re.compile(r"20\d\d-\d\d-\d\dT\d\d:\d\d:\d\dZ\Z")
_ALLOWED_HTML="text/html"
_MAX_RECEIPT_JSON=4096
_MARKERS=(
    "The Bank's Market Operations",
    "Guideline",
    "Bank of Japan Operations",
    "The Bank will encourage the uncollateralized overnight call rate",
    "Interest Rate Applied to the Complementary Deposit Facility",
    "Basic Loan Rate",
)

def _blocked(reason:str)->dict[str,Any]:
    return {
        "schema":SCHEMA,"state":"LAB_JPY_BOJ_REJECTED_QUARANTINE_NO_GO",
        "reason":reason,"quarantined":False,"quarantine_classification":None,
        "policy_data_admitted":False,"current_policy_source_admitted":False,
        "source_html_saved_to_official_macro_receipts":False,
        "source_sha256":None,"source_original_bytes":None,
        "receipt_filename":None,"original_filename":None,
        "source_first_seen_independently_authenticated":False,
        "operational_bias":"AGUARDAR","trade_authorized":False,
        "http_requests":0,"mt5_calls":0,"trade_calls":0,
        "file_writes":0,
    }

def _clock(s:Any)->datetime|None:
    if type(s) is not str or not STAMP.fullmatch(s):
        return None
    try:
        return datetime.strptime(s,"%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return None

def _valid_root(root:Any)->Path|None:
    if type(root) is not str or not root:
        return None
    p=Path(root)
    if not p.is_absolute():
        return None
    try:
        lab=p/"AtlasQuant"/"LAB"
        quarantine=lab/"BoJ_Home_Quarantine_20261115"
        if any(item.is_symlink() for item in (p,p/"AtlasQuant",lab,quarantine)):
            return None
        if not quarantine.resolve(strict=False).is_relative_to(lab.resolve(strict=False)):
            return None
        return quarantine
    except (OSError,ValueError,TypeError,RuntimeError):
        return None

def quarantine_rejected_boj_home_lab(
    *,original_html:Any,receipt:Any,local_appdata:Any,
    decision_at_utc:Any,
)->dict[str,Any]:
    out=_blocked("INVALID_OR_NONOFFICIAL_CAPTURE_UNSAFE")
    if (type(original_html) is not bytes or not 300<=len(original_html)<=MAX_BYTES
            or type(receipt) is not dict or set(receipt)!=RECEIPT_KEYS
            or not isinstance(decision_at_utc,datetime)
            or decision_at_utc.tzinfo is None
            or decision_at_utc.utcoffset() is None
            or decision_at_utc.microsecond):
        return out
    archive=_valid_root(local_appdata)
    if archive is None:
        return _blocked("UNSAFE_QUARANTINE_ROOT")
    if (receipt.get("source_url")!=URL
            or receipt.get("final_url") not in ALLOWED_FINAL_URLS
            or type(receipt.get("http_status")) is not int
            or receipt["http_status"]!=200
            or type(receipt.get("content_type")) is not str
            or receipt["content_type"].split(";")[0].strip().lower()!=_ALLOWED_HTML
            or receipt.get("https_validation_claim") is not True
            or type(receipt.get("redirects_followed")) is not bool
            or receipt["redirects_followed"] != (receipt["final_url"]!=URL)
            or type(receipt.get("body_sha256")) is not str
            or not SHA.fullmatch(receipt["body_sha256"])
            or sha256(original_html).hexdigest()!=receipt["body_sha256"]):
        return out
    start=_clock(receipt.get("started_at_utc"))
    end=_clock(receipt.get("finished_at_utc"))
    if (start is None or end is None or end<start or
            end-start>timedelta(seconds=30) or
            end>decision_at_utc.astimezone(timezone.utc)):
        return _blocked("BOJ_QUARANTINE_CAPTURE_CLOCK_INVALID")
    checked=inspect_boj_home_guideline_receipt_lab(
        original_html=original_html,receipt=receipt,
        decision_at_utc=decision_at_utc)
    if checked.get("state")=="LAB_JPY_BOJ_CURRENT_GUIDELINE_HTML_LOCALLY_CHECKED_NO_GO":
        return _blocked("VALID_BOJ_HOME_NO_NEED_FOR_QUARANTINE")
    if (checked.get("reason")!=DENIED
            or checked.get("html_sha256_matches_local_receipt") is not True
            or checked.get("transport_claim_structurally_consistent") is not True):
        return _blocked("REJECTION_NOT_CONFIRMED_AS_HTML_STRUCTURE_ERROR")
    if any(x is not True for x in (checked.get("trade_authorized") is False,
                                    checked.get("publishable") is False)):
        return _blocked("UNSAFE_VALIDATOR_STATUS")
    # Diagnostic markers describe only literal marker PRESENCE in the
    # response, never HTML content or policy numerical values.
    try:
        decoded=original_html.decode("utf-8-sig")
    except UnicodeError:
        decoded=""
    markers={k:(k in decoded) for k in _MARKERS}
    name=LABEL+"_"+end.strftime("%Y%m%dT%H%M%SZ")+"_"+receipt["body_sha256"][:12]
    original=archive/(name+".html")
    metadata=archive/(name+".diagnostic.json")
    summary={
        "schema":SCHEMA,"state":"LAB_JPY_BOJ_CURRENT_HOME_REFUSED_IN_ISOLATED_QUARANTINE_NO_GO",
        "reason":DENIED,"classification":"OFFICIAL_TRANSPORT_CLAIM_LOCAL_ONLY_HTML_STRUCTURE_REJECTED",
        "capture_finished_utc_os_clock_claim":receipt["finished_at_utc"],
        "original_sha256":receipt["body_sha256"],
        "original_length":len(original_html),
        "original_extension":"html","original_basename":original.name,
        "original_source_url":URL,"final_url":receipt["final_url"],
        "http_status":200,"content_type":receipt["content_type"],
        "original_receipt":receipt,
        "marker_presence_in_raw_original":markers,
        "issuer_first_seen_independently_authenticated":False,
        "current_policy_source_admitted":False,
        "quarantined_html_not_a_current_rate":True,
        "trade_authorized":False,"operational_bias":"AGUARDAR",
    }
    raw=(json.dumps(summary,ensure_ascii=False,sort_keys=True,indent=2)+"\n").encode("utf-8")
    if len(raw)>_MAX_RECEIPT_JSON:
        return _blocked("DIAGNOSTIC_SUMMARY_OVERSIZE")
    try:
        if archive.is_symlink():
            return _blocked("QUARANTINE_DIRECTORY_SYMLINK")
        archive.mkdir(parents=True,exist_ok=True)
        if (original.exists() or metadata.exists()
                or original.is_symlink() or metadata.is_symlink()):
            return _blocked("DUPLICATE_OR_PARTIAL_QUARANTINE_DENIED_NO_OVERWRITE")
        # If the second open fails, the partial original is kept for
        # forensic inspection rather than silently deleted or retried.
        with original.open("xb") as f:f.write(original_html)
        with metadata.open("xb") as f:f.write(raw)
    except (OSError,ValueError,TypeError,RuntimeError):
        blocked=_blocked("QUARANTINE_WRITE_FAILED_POSSIBLE_PARTIAL_NO_RETRY")
        blocked["possible_partial_quarantine"]=True
        blocked["file_writes"]=None  # unknown after an I/O exception
        return blocked
    out.update({
        "state":"LAB_JPY_BOJ_REJECTED_HOME_ORIGINAL_QUARANTINED_NO_GO",
        "reason":DENIED,"quarantined":True,
        "quarantine_classification":"HTML_STRUCTURE_REFUSED_NOT_A_POLICY_SOURCE",
        "source_sha256":receipt["body_sha256"],"source_original_bytes":len(original_html),
        "receipt_filename":metadata.name,"original_filename":original.name,
        "file_writes":2,
    })
    return out

__all__=("SCHEMA","quarantine_rejected_boj_home_lab")
