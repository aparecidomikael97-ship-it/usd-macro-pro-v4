"""Read-only FX28 documentary overlay: 5 issuer current archives + CHF/JPY release docs.

DO NOT alter the existing eight-bank parser's contract: it expects current
home pages/issuer-specific receipts, not historical release statements.
The wider 7/8 count below is HISTORICAL DOCUMENTARY COVERAGE ONLY, not seven
accepted current-policy source packets, not 7/8 economic-factor admissions,
not a witnessed forecast, verified first-seen or live tradable bias.

No network, MT5, orders, brokerage accounts, GitHub, publishing or workers.
"""
from __future__ import annotations
from datetime import datetime,timezone
from pathlib import Path
from hashlib import sha256
import importlib.util
import json
import os
import sys
from typing import Any

from atlasquant_fx_universe import CURRENCIES,OFFICIAL_PAIRS,split_pair
from atlasquant_trader_fx28_policy_local_archive_replay_lab import (
    inspect_fx28_official_policy_archive_replay_lab,
    SCHEMA as CURRENT_ARCHIVE_SCHEMA,
)

SCHEMA="ATLASQUANT_FX28_STAGED_HISTORICAL_RELEASE_COVERAGE_OVERLAY_LAB_V1"
_RELEASES = ("CHF","JPY")
# SHA-256 of original issuer release bytes already archived on AM12.
# These pins prevent arbitrary caller metadata from inflating the overlay.
# A matching digest is NOT a signature, immutable first-seen, or a price.
_RELEASE_PINS = {
    "CHF": {
        "sha256":"2ef1d95b54037f1312d1fc7acdd9af8e567e7c888ee1454811a1264aa075880b",
        "bytes":117948,
        "url":"https://www.snb.ch/en/publications/communication/press-releases-restricted/pre_20260924",
        "date":"2026-09-24",
        "instrument":"SNB policy rate",
        "rate_key":"rate_pct", "rate":0.0,
        "decision_kind":"unchanged",
    },
    "JPY": {
        "sha256":"f62859324bd87cc493b9bd2ec09b9030012602cfe66b7298543ad7cffc97a044",
        "bytes":175859,
        "url":"https://www.boj.or.jp/en/mopo/mpmdeci/mpr_2026/k261030a.pdf",
        "date":"2026-10-30",
        "instrument":"uncollateralized overnight call rate",
        "rate_key":"rate_target_pct", "rate":1.25,
        "decision_kind":"target_around",
    },
}
_RELEASE_STEMS = {
    "CHF":("CHF_official_original_curl_20261114.html",
           "CHF_official_original_curl_receipt_20261114.json", 500_000),
    "JPY":("JPY_official_original_curl_20261114.pdf",
           "JPY_official_original_curl_receipt_20261114.json", 1_000_000),
}
CURRENT_STATES={
    "LAB_FX28_POLICY_ARCHIVE_EIGHT_ORIGINALS_LOCAL_ONLY_NO_GO",
    "LAB_FX28_POLICY_ARCHIVE_PARTIAL_OR_REJECTED_NO_GO",
}
MAX_RECEIPT=8192
CUTOFF_UTC_FIELD="local_capture_clock_claim"

def blocked(reason):
    return {
        "schema":SCHEMA,"state":"LAB_FX28_HISTORICAL_OVERLAY_BLOCKED_NO_GO",
        "reason":reason,"currencies_expected":8,"pairs_expected":28,
        "current_issuer_current_page_accepted_count":0,
        "historical_release_document_checked_count":0,
        "currencies_with_any_checked_policy_document_count":0,
        "pairs_with_both_any_checked_policy_documents_count":0,
        "pairs_with_both_current_policy_source_packets_count":0,
        "new_historical_docs_checked":[],
        "new_historical_docs_rejected":{},
        "missing_any_policy_document_currencies":sorted(CURRENCIES),
        "historical_documents_are_not_current_homepage_packets":True,
        "count_of_historical_statements_is_not_count_of_live_policy_expectations":True,
        "historical_macro_first_seen_independently_authenticated":False,
        "authenticated_issuer_origin":False,
        "pre_event_consensus_authenticated":False,
        "broker_m15_independently_authenticated":False,
        "signed_fx_macro_direction_effects_accepted":0,
        "calibrated_probability":None,
        "directional_bias":None,"historical_accuracy":None,
        "operational_bias":"AGUARDAR","trade_authorized":False,
        "publishable":False,"live_alert_allowed":False,
        "worker_enabled":False,"scheduler_enabled":False,
        "network_calls":0,"mt5_calls":0,"file_writes":0,"new_cost_brl":0,
        "research_only":True,
    }

def _dedupe_json_pairs(pairs):
    out={}
    for k,v in pairs:
        if k in out:raise ValueError("JSON_DUPLICATE_KEY")
        out[k]=v
    return out

def _reject_constant(text):
    raise ValueError("JSON_NONFINITE_VALUE")

def _valid_cutoff(t):
    if not isinstance(t,datetime) or t.tzinfo is None or t.microsecond:
        return False
    try:return t.utcoffset() is not None
    except (ValueError,OverflowError,TypeError):return False

def combine_policy_coverage(*, current_policy_report, historical_docs):
    """Only a readout overlay. Preserves old 5/8 Motor-A factor gate, no overrides."""
    out=blocked("BASELINE_OR_HISTORICAL_DOCS_NOT_VERIFIED")
    p=current_policy_report
    if (type(p) is not dict or p.get("schema")!=CURRENT_ARCHIVE_SCHEMA
            or p.get("state") not in CURRENT_STATES
            or p.get("operational_bias")!="AGUARDAR"
            or p.get("trade_authorized") is not False
            or p.get("publishable") is not False
            or p.get("historical_point_in_time_vintage_verified") is not False
            or p.get("source_current_issuer_identity_independently_verified") is not False
            or type(historical_docs) is not dict
            or any(k not in _RELEASES for k in historical_docs)):
        return out
    current=p.get("currencies_locally_checked")
    missing=p.get("currencies_missing")
    rejected=p.get("currencies_rejected")
    if (type(current) is not list or type(missing) is not list
            or type(rejected) is not dict
            or any(type(x) is not str for x in current+missing)
            or len(set(current))!=len(current)
            or (set(current)|set(missing)|set(rejected)) != set(CURRENCIES)
            or (set(current)&set(missing)) or (set(current)&set(rejected))
            or (set(missing)&set(rejected))):
        out["reason"]="BASELINE_CURRENCY_SETS_MALFORMED"
        return out
    current_set=set(current)
    curr_n=p.get("currencies_with_local_original_bytes_validated")
    curr_pair=p.get("pairs_with_both_policy_originals_locally_checked")
    if (type(curr_n) is not int or curr_n!=len(current_set)
            or type(curr_pair) is not int
            or curr_pair !=len(current_set)*(len(current_set)-1)//2):
        out["reason"]="BASELINE_PAIR_COUNT_INCOHERENT"
        return out
    history_good=set()
    history_bad={}
    for currency in _RELEASES:
        if currency not in historical_docs:continue
        s=historical_docs[currency]
        pin=_RELEASE_PINS[currency]
        doc=s.get("document") if type(s) is dict else None
        if (type(s) is not dict or
                s.get("status")!="LOCAL_RELEASE_DOCUMENT_CONTENT_AND_SHA_CHECKED_NO_GO"
                or s.get("currency")!=currency
                or s.get("trading_authorized") is not False
                or s.get("independent_issuer_origin_attested") is not False
                or s.get("release_first_seen_authenticated") is not False
                or s.get("validated_forward_currency_direction") is not False
                or s.get("retrieved_after_original_release") is not True
                or s.get("sha256")!=pin["sha256"]
                or type(s.get("bytes")) is not int or s["bytes"]!=pin["bytes"]
                or s.get("source_url")!=pin["url"]
                or type(doc) is not dict
                or doc.get("date")!=pin["date"]
                or doc.get("instrument")!=pin["instrument"]
                or doc.get("decision_kind")!=pin["decision_kind"]
                or type(doc.get(pin["rate_key"])) not in (int,float)
                or doc[pin["rate_key"]]!=pin["rate"]
                or (currency=="JPY" and (
                    doc.get("decision_vote_for")!=8
                    or doc.get("decision_vote_against")!=1
                    or doc.get("dissenting_proposal_pct")!=1.5))):
            history_bad[currency]="HISTORICAL_RELEASE_PIN_OR_SEMANTICS_REJECTED"
            continue
        history_good.add(currency)
    # If an issuer page is already accepted, do not count it twice.
    covered=current_set|history_good
    pairs=[]
    for pair in OFFICIAL_PAIRS:
        base,quote=split_pair(pair)
        pairs.append({
            "pair":pair,
            "both_have_some_checked_document":base in covered and quote in covered,
            "both_have_current_source_accepted":base in current_set and quote in current_set,
            "document_type_base":
                "current_policy_page" if base in current_set else
                "historical_policy_statement" if base in history_good else "missing",
            "document_type_quote":
                "current_policy_page" if quote in current_set else
                "historical_policy_statement" if quote in history_good else "missing",
            "signed_direction_allowed":False,
        })
    out.update({
        "state":"LAB_FX28_DOCUMENTARY_OVERLAY_RECONCILED_NO_GO",
        "reason":"STAGED_HISTORICAL_RELEASES_NOT_CURRENT_PAGE_GATE_OR_AUTHENTICATED_PIT",
        "current_issuer_current_page_accepted_count":len(current_set),
        "historical_release_document_checked_count":len(history_good),
        "currencies_with_any_checked_policy_document_count":len(covered),
        "pairs_with_both_any_checked_policy_documents_count":
            sum(int(x["both_have_some_checked_document"]) for x in pairs),
        "pairs_with_both_current_policy_source_packets_count":
            sum(int(x["both_have_current_source_accepted"]) for x in pairs),
        "new_historical_docs_checked":sorted(history_good),
        "new_historical_docs_rejected":history_bad,
        "missing_any_policy_document_currencies":sorted(set(CURRENCIES)-covered),
        "base_current_source_currencies":sorted(current_set),
        "pair_document_coverage":pairs,
    })
    return out

def inspect_local_historical_overlay(*,local_appdata,cutoff_utc):
    out=blocked("INVALID_ROOT_OR_CUTOFF")
    if (type(local_appdata) is not str or not local_appdata
            or not Path(local_appdata).is_absolute()
            or not _valid_cutoff(cutoff_utc)):
        return out
    try:
        base=Path(local_appdata)
        atlas=base/"AtlasQuant"
        lab=atlas/"LAB"
        folder=lab/"FX28_IssuerPolicy_Official_20261114"
        if any(p.is_symlink() for p in (base,atlas,lab,folder)):
            out["reason"]="SYMLINK_ARCHIVE_ROOT_REJECTED"
            return out
        root=lab.resolve(strict=False)
        if not folder.resolve(strict=False).is_relative_to(root):
            out["reason"]="ARCHIVE_PATH_ESCAPE_REJECTED"
            return out
        current=inspect_fx28_official_policy_archive_replay_lab(
            local_appdata=local_appdata,decision_at_utc=cutoff_utc)
        if not folder.is_dir():
            return combine_policy_coverage(current_policy_report=current,historical_docs={})
        # Reuse offline, date/sha/content-specific statement parser, not the
        # homepage parser built for different file types.
        source=folder/"validar_documentos_politica_snb_boj_v1.py"
        if source.is_symlink() or not source.is_file():
            out["reason"]="LOCAL_RELEASE_VALIDATOR_NOT_FOUND"
            return out
        spec=importlib.util.spec_from_file_location(
            "atlasquant_history_release_checker",source)
        if spec is None or spec.loader is None:
            out["reason"]="VALIDATOR_LOAD_FAILED"
            return out
        module=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        history={}
        for currency in _RELEASES:
            original_name,receipt_name,max_bytes=_RELEASE_STEMS[currency]
            orig=folder/original_name;rec=folder/receipt_name
            if orig.is_symlink() or rec.is_symlink():continue
            if not orig.is_file() or not rec.is_file():continue
            if not 350<=orig.stat().st_size<=max_bytes:continue
            if not 100<=rec.stat().st_size<=MAX_RECEIPT:continue
            body=orig.read_bytes()
            receipt=json.loads(
                rec.read_bytes().decode("utf-8-sig"),
                object_pairs_hook=_dedupe_json_pairs,
                parse_constant=_reject_constant)
            try:
                checked=module.inspect(currency,body,receipt,cutoff_utc)
            except (KeyError,ValueError,TypeError,OverflowError,
                    RuntimeError,IndexError,UnicodeError):
                continue
            history[currency]=checked
        result=combine_policy_coverage(
            current_policy_report=current,historical_docs=history)
        result["runtime_originals_read_only_from_local_disk"]=True
        return result
    except (OSError,ValueError,TypeError,RuntimeError,ImportError,
            KeyError,AttributeError,RecursionError) as exc:
        out["reason"]="LOCAL_VALIDATOR_OR_FILE_READER_EXCEPTION"
        return out

def main():
    from datetime import datetime,timezone
    now=datetime.now(timezone.utc).replace(microsecond=0)
    r=inspect_local_historical_overlay(
        local_appdata=os.environ.get("LOCALAPPDATA",""),cutoff_utc=now)
    compact={k:v for k,v in r.items() if k!="pair_document_coverage"}
    print(json.dumps(compact,ensure_ascii=False,sort_keys=True,indent=2))
    return 0 if r["state"]=="LAB_FX28_DOCUMENTARY_OVERLAY_RECONCILED_NO_GO" else 2

if __name__=="__main__":
    raise SystemExit(main())
