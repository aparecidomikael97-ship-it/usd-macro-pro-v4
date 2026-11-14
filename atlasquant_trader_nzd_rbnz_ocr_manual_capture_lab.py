"""Manual one-shot RBNZ official OCR overview public source capture (LAB).

Requires explicit --capture. No login, key, bypass, retries, broker,
account, market prices, signals, trades, recurring task or deployment.
If explicitly approved in the future, preserve official HTML + SHA receipt under
%LOCALAPPDATA%/AtlasQuant/LAB/official_macro_receipts.

A capture today NEVER authenticates when the source first existed for
an earlier forecast cutoff, nor converts 2pm NZ local into UTC without
the correct New Zealand historical timezone context.
"""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
from hashlib import sha256
import json,os
from pathlib import Path
from typing import Any,Callable
from urllib.request import Request,urlopen

from atlasquant_trader_nzd_rbnz_access_terms_lab import (
    RBNZ_BLOCK_REASON, inspect_rbnz_automated_access_policy_lab,
)
from atlasquant_trader_nzd_rbnz_ocr_receipt_lab import (
    URL,MAX_BYTES,inspect_rbnz_official_ocr_receipt_lab,
)

def _now()->str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def collect_rbnz_ocr_once_lab(
    *,open_url:Callable[...,Any]=urlopen,
    now_utc:Callable[[],str]=_now,
)->tuple[bytes,dict[str,Any]]:
    # An injected opener is for offline synthetic tests only.
    # Production use always supplies the actual urllib.urlopen default.
    # A CLI flag is NOT the issuer's prior written permission.
    if open_url is urlopen:
        raise PermissionError(RBNZ_BLOCK_REASON)
    start=now_utc()
    req=Request(URL,headers={
        "User-Agent":"AtlasQuantTrader-LAB-Research/1.0",
        "Accept":"text/html",
    })
    with open_url(req,timeout=12) as response:
        body=response.read(MAX_BYTES+1)
        if len(body)>MAX_BYTES:
            raise ValueError("RBNZ_OCR_RESPONSE_TOO_LARGE")
        receipt={
            "source_url":URL,
            "final_url":response.geturl(),
            "http_status":response.status,
            "content_type":response.headers.get("Content-Type",""),
            "body_sha256":sha256(body).hexdigest(),
            "started_at_utc":start,
            "finished_at_utc":now_utc(),
            "https_validation_claim":True,
            "redirects_followed":response.geturl()!=URL,
        }
    return body,receipt

def save_rbnz_ocr_public_lab(
    *,body:bytes,receipt:dict[str,Any],local_appdata:str
)->tuple[Path,Path]:
    if not local_appdata or not Path(local_appdata).is_absolute():
        raise ValueError("LAB_LOCALAPPDATA_REQUIRED")
    root=(Path(local_appdata)/"AtlasQuant"/"LAB").resolve()
    raw_folder=root/"official_macro_receipts"
    if raw_folder.is_symlink():
        raise ValueError("LAB_SYMLINK_REFUSED")
    folder=raw_folder.resolve()
    if not folder.is_relative_to(root):
        raise ValueError("LAB_OUTSIDE_ISOLATED_ROOT")
    folder.mkdir(parents=True,exist_ok=True)
    stamp=receipt["finished_at_utc"].replace("-","").replace(":","")
    name=f"NZD_RBNZ_OCR_{stamp}_{receipt['body_sha256'][:12]}"
    source=folder/(name+".html")
    meta=folder/(name+".receipt.json")
    if source.exists() or meta.exists():
        raise FileExistsError("OCR_SOURCE_ALREADY_PRESENT_NO_OVERWRITE")
    with source.open("xb") as out:
        out.write(body)
    with meta.open("xb") as out:
        out.write((json.dumps(receipt,sort_keys=True,indent=2)+"\n").encode("utf-8"))
    return source,meta

def main()->int:
    p=argparse.ArgumentParser()
    p.add_argument("--capture",action="store_true")
    args=p.parse_args()
    if not args.capture:
        print("LAB_NO_HTTP_NO_FILES: explicit --capture required")
        return 2
    # Fail before any HTTP or files even with --capture. Review written
    # allow-list authorization before changing the production collector.
    terms=inspect_rbnz_automated_access_policy_lab()
    if not terms["automated_collection_permission_verified"]:
        print("LAB_RBNZ_PERMISSION_REQUIRED_NO_HTTP_NO_FILES: "+RBNZ_BLOCK_REASON)
        return 2
    try:
        body,receipt=collect_rbnz_ocr_once_lab()
        cutoff=datetime.strptime(
            receipt["finished_at_utc"],"%Y-%m-%dT%H:%M:%SZ"
        ).replace(tzinfo=timezone.utc)
        r=inspect_rbnz_official_ocr_receipt_lab(
            original_html=body,receipt=receipt,decision_at_utc=cutoff)
        if r["state"]!="LAB_NZD_RBNZ_OCR_HTML_LOCALLY_CHECKED_NO_GO":
            print("LAB_RBNZ_CAPTURE_BLOCKED: "+r["reason"])
            return 2
        source,meta=save_rbnz_ocr_public_lab(
            body=body,receipt=receipt,
            local_appdata=os.environ.get("LOCALAPPDATA",""))
        print(json.dumps({
            "state":r["state"],
            "source_local_only":str(source),
            "receipt_local_only":str(meta),
            "source_sha256":receipt["body_sha256"],
            "ocr_pct_claim":r["official_cash_rate_pct_claim"],
            "policy_last_updated_local_claim":r["ocr_updated_nz_local_claim"],
            "historic_first_announcement_authenticated":False,
            "operational_bias":"AGUARDAR","trade_authorized":False,
        },ensure_ascii=False,indent=2))
        return 0
    except (OSError,KeyError,ValueError,TypeError,OverflowError):
        print("LAB_RBNZ_OCR_CAPTURE_FAILED_NO_GO")
        return 2

if __name__=="__main__":
    raise SystemExit(main())
