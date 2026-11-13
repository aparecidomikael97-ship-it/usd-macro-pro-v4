"""One-shot public SNB current policy page original-byte capture (LAB).

No action without explicit --capture; fixed official SNB URL, one bounded
TLS HTTPS request, source body + hash/clock receipt stored under local
%LOCALAPPDATA%/AtlasQuant/LAB/official_macro_receipts only.
Do not extract or republish SARON/BFIX third-party market data. Page
snapshot cannot authenticate historical vintage or exact issuer release.
No MT5, account, trades, orders, worker, deploy, or new costs.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
from typing import Any, Callable
from urllib.request import Request, urlopen

from atlasquant_trader_chf_snb_current_policy_receipt_lab import (
    URL, MAX_BYTES, inspect_snb_current_policy_receipt_lab,
)

def _now()->str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def collect_snb_current_policy_once_lab(
    *, open_url:Callable[...,Any]=urlopen,
    now_utc:Callable[[],str]=_now,
)->tuple[bytes,dict[str,Any]]:
    start=now_utc()
    request=Request(URL,headers={
        "User-Agent":"AtlasQuantTrader-LAB-Research/1.0",
        "Accept":"text/html",
    })
    with open_url(request,timeout=12) as response:
        body=response.read(MAX_BYTES+1)
        if len(body)>MAX_BYTES:
            raise ValueError("SNB_HTML_OVERSIZE_NO_CAPTURE")
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

def save_snb_policy_public_bytes_lab(
    *, body:bytes,receipt:dict[str,Any],local_appdata:str,
)->tuple[Path,Path]:
    if not local_appdata or not Path(local_appdata).is_absolute():
        raise ValueError("LOCALAPPDATA_ROOT_MUST_BE_ABSOLUTE")
    root=(Path(local_appdata)/"AtlasQuant"/"LAB").resolve()
    source_folder=root/"official_macro_receipts"
    if source_folder.is_symlink():
        raise ValueError("SOURCE_FOLDER_IS_SYMLINK")
    folder=source_folder.resolve()
    if not folder.is_relative_to(root):
        raise ValueError("SOURCE_FOLDER_ESCAPES_ISOLATED_LAB")
    folder.mkdir(parents=True,exist_ok=True)
    stamp=receipt["finished_at_utc"].replace("-","").replace(":","")
    stem=f"CHF_SNB_CURRENT_POLICY_{stamp}_{receipt['body_sha256'][:12]}"
    orig=folder/(stem+".html")
    meta=folder/(stem+".receipt.json")
    if orig.exists() or meta.exists():
        raise FileExistsError("CAPTURE_ALREADY_EXISTS")
    with orig.open("xb") as file:
        file.write(body)
    with meta.open("xb") as file:
        file.write(
            (json.dumps(receipt,sort_keys=True,indent=2)+"\n").encode("utf-8"))
    return orig,meta

def main()->int:
    parser=argparse.ArgumentParser()
    parser.add_argument("--capture",action="store_true")
    args=parser.parse_args()
    if not args.capture:
        print("LAB_NO_NETWORK_NO_WRITES: explicit --capture required")
        return 2
    try:
        body,receipt=collect_snb_current_policy_once_lab()
        cutoff=datetime.strptime(
            receipt["finished_at_utc"],"%Y-%m-%dT%H:%M:%SZ"
        ).replace(tzinfo=timezone.utc)
        report=inspect_snb_current_policy_receipt_lab(
            original_html=body,receipt=receipt,decision_at_utc=cutoff)
        if report["state"]!="LAB_CHF_SNB_CURRENT_POLICY_HTML_LOCALLY_CHECKED_NO_GO":
            print("LAB_SNB_CAPTURE_BLOCKED: "+report["reason"])
            return 2
        original,meta=save_snb_policy_public_bytes_lab(
            body=body,receipt=receipt,
            local_appdata=os.environ.get("LOCALAPPDATA",""))
        print(json.dumps({
            "state":report["state"],
            "source_local":str(original),
            "receipt_local":str(meta),
            "source_sha256":receipt["body_sha256"],
            "policy_rate_pct_claim":report["current_snb_policy_rate_pct_claim"],
            "valid_from_date_claim":report["policy_valid_from_date_claim"],
            "saron_extracted":False,
            "historical_policy_release_first_seen_verified":False,
            "operational_bias":"AGUARDAR",
            "trade_authorized":False,
        },ensure_ascii=False,indent=2))
        return 0
    except (OSError,TypeError,ValueError,KeyError,OverflowError):
        print("LAB_SNB_SOURCE_CAPTURE_FAILED_NO_TRADE")
        return 2

if __name__=="__main__":
    raise SystemExit(main())
