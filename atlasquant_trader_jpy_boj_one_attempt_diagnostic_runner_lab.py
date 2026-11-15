"""DRAFT manual JPY homepage one-attempt wrapper with forensic fallback.

NOT scheduled, not installed in preflight, no public CLI for implicit capture.
Run only with explicit --capture and human inspection AFTER Sunday's frozen
campaign. One immutable claim is created BEFORE the (at most one) HTTP fetch.
The original BOJ checker decides if this is policy-source material. Rejected
structural responses can be kept in a separate forensic quarantine. Never
promote quarantine to official_macro_receipts or apply a retroactive vintage.
"""
from __future__ import annotations
from datetime import datetime,timezone
from pathlib import Path
from typing import Callable,Any
import argparse,json,os
from atlasquant_trader_jpy_boj_guideline_manual_capture_lab import (
    collect_boj_home_once_lab,save_boj_home_in_lab,
)
from atlasquant_trader_jpy_boj_guideline_source_receipt_lab import (
    inspect_boj_home_guideline_receipt_lab,
)
from atlasquant_trader_jpy_boj_rejected_home_quarantine_lab import (
    quarantine_rejected_boj_home_lab,DENIED,
)

SCHEMA="ATLASQUANT_JPY_BOJ_ONE_ATTEMPT_DIAGNOSTIC_RUNNER_LAB_V1"
CLAIM_NAME="JPY_BOJ_HOME_20261115_ONE_ATTEMPT.claim.json"
TARGET_DIR="BoJ_Home_Quarantine_20261115"
VALID_STATE="LAB_JPY_BOJ_CURRENT_GUIDELINE_HTML_LOCALLY_CHECKED_NO_GO"

def _report(reason:str)->dict[str,Any]:
    return {
        "schema":SCHEMA,
        "state":"LAB_JPY_BOJ_MANUAL_ATTEMPT_BLOCKED_NO_GO",
        "reason":reason,
        "one_attempt_claim_created":False,
        "http_fetch_function_calls":0,
        "original_accepted_policy_source_archived":False,
        "rejected_original_in_forensic_quarantine":False,
        "attempt_already_reserved":False,
        "retry_or_alternate_url_allowed":False,
        "quarantine_is_policy_source":False,
        "boJ_source_current_and_first_seen_independently_attested":False,
        "valid_forex_bias":None,"calibrated_probability":None,
        "trade_authorized":False,"operational_bias":"AGUARDAR",
        "scheduler_modified":False,
        "production_deployment":False,
    }

def one_attempt_boj_policy_or_quarantine_lab(
    *, fetch_once:Callable[[],tuple[bytes,dict[str,Any]]],
    local_appdata:str,
    now:Callable[[],datetime],
)->dict[str,Any]:
    out=_report("INVALID_ROOT_FETCHER_OR_CLOCK")
    if not callable(fetch_once) or not callable(now) or type(local_appdata) is not str:
        return out
    root=Path(local_appdata)
    if not root.is_absolute():
        return out
    lab=root/"AtlasQuant"/"LAB"
    folder=lab/TARGET_DIR
    try:
        if any(item.is_symlink() for item in (root,root/"AtlasQuant",lab,folder)):
            out["reason"]="UNSAFE_QUARANTINE_ROOT_SYMLINK"
            return out
        if not folder.resolve(strict=False).is_relative_to(lab.resolve(strict=False)):
            out["reason"]="OUTSIDE_ALLOWED_LAB"
            return out
        candidate=now()
        if not isinstance(candidate,datetime) or candidate.tzinfo is None or candidate.utcoffset() is None:
            out["reason"]="BAD_CURRENT_CLOCK"
            return out
        # THIS MANUAL RUNNER MUST NOT BE USED BEFORE the 22:00-22:15Z
        # Sunday first-bar campaign. This does not authorize deployment
        # afterwards either, but prevents a premature public fetch.
        if candidate.astimezone(timezone.utc)<datetime(2026,11,15,22,20,tzinfo=timezone.utc):
            out["reason"]="FROZEN_FX28_SUNDAY_FIRST_M15_STILL_PENDING_NO_BOJ_DIAGNOSTIC"
            return out
        folder.mkdir(parents=True,exist_ok=True)
        claim=folder/CLAIM_NAME
        try:
            with claim.open("xb") as f:
                f.write((json.dumps({
                    "schema":SCHEMA,"one_attempt":True,
                    "original_boj_url":"https://www.boj.or.jp/en/",
                    "claimed_utc_os_clock_unattested":candidate.astimezone(timezone.utc).isoformat(),
                    "first_seen_independently_verified":False,
                    "trade_authorized":False,
                },sort_keys=True)+"\n").encode("utf-8"))
        except FileExistsError:
            out["reason"]="EXISTING_BOJ_ONE_ATTEMPT_CLAIM_NO_SECOND_FETCH"
            out["attempt_already_reserved"]=True
            return out
        out["one_attempt_claim_created"]=True
        # A crash after creating the claim must never trigger a retry.
        out["http_fetch_function_calls"]=1
        original,receipt=fetch_once()
        cutoff=now()
        if not isinstance(cutoff,datetime) or cutoff.tzinfo is None or cutoff.utcoffset() is None:
            out["reason"]="BAD_POST_FETCH_CLOCK_CLAIM_REMAINS"
            return out
        cutoff=cutoff.astimezone(timezone.utc).replace(microsecond=0)
        checked=inspect_boj_home_guideline_receipt_lab(
            original_html=original,receipt=receipt,decision_at_utc=cutoff)
        if checked.get("state")==VALID_STATE:
            if (checked.get("trade_authorized") is not False
                    or checked.get("publishable") is not False
                    or checked.get("operational_bias")!="AGUARDAR"):
                out["reason"]="FORGED_VALID_BOJ_STATUS_NO_POLICY_ARCHIVE"
                return out
            # Still LOCAL_DOCUMENT_ONLY / NO TRADING.
            original_path,meta_path=save_boj_home_in_lab(
                body=original,receipt=receipt,local_appdata=local_appdata)
            out["state"]="LAB_JPY_BOJ_CURRENT_HOMEPAGE_LOCALLY_CHECKED_NO_GO"
            out["reason"]="ORIGINAL_ACCEPTED_AS_LOCAL_DOCUMENT_NOT_ISSUER_VINTAGE"
            out["original_accepted_policy_source_archived"]=True
            return out
        if checked.get("reason")!=DENIED:
            out["reason"]="BOJ_REJECTED_FOR_NONSTRUCTURAL_REASON_CLAIM_PERSISTS"
            return out
        forensic=quarantine_rejected_boj_home_lab(
            original_html=original,receipt=receipt,local_appdata=local_appdata,
            decision_at_utc=cutoff)
        if not forensic["quarantined"]:
            out["reason"]="STRUCTURAL_REJECTION_BUT_QUARANTINE_FAILED_"+forensic["reason"]
            return out
        out["state"]="LAB_JPY_BOJ_REJECTED_HOMEPAGE_STORED_SEPARATELY_NO_GO"
        out["reason"]=DENIED
        out["rejected_original_in_forensic_quarantine"]=True
        return out
    except (OSError,RuntimeError,ValueError,TypeError,KeyError,OverflowError) as exc:
        # The permanent claim may exist; do not delete it or retry.
        out["reason"]="BOJ_ATTEMPT_EXCEPTION_"+type(exc).__name__+"_NO_RETRY"
        return out

def main(argv:list[str]|None=None)->int:
    cli=argparse.ArgumentParser(description="Manual BoJ one-attempt forensic pipeline; NO-GO")
    cli.add_argument("--capture",action="store_true")
    args=cli.parse_args(argv)
    if not args.capture:
        print(json.dumps(_report("EXPLICIT_CAPTURE_FLAG_REQUIRED")))
        return 2
    r=one_attempt_boj_policy_or_quarantine_lab(
        fetch_once=collect_boj_home_once_lab,
        local_appdata=os.environ.get("LOCALAPPDATA",""),
        now=lambda:datetime.now(timezone.utc))
    print(json.dumps(r,ensure_ascii=False,sort_keys=True))
    return 0 if (r["original_accepted_policy_source_archived"]
                 or r["rejected_original_in_forensic_quarantine"]) else 2

if __name__=="__main__":
    raise SystemExit(main())

__all__=("SCHEMA","one_attempt_boj_policy_or_quarantine_lab","main")
