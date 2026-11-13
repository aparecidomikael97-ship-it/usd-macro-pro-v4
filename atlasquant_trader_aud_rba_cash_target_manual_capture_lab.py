"""One-shot manual RBA current cash-rate-target public HTML capture (LAB).

Requires explicit --capture, uses fixed exact official URL. One HTTPS
request with Python's normal certificate checks; validates original
bytes before retaining source + SHA/clock receipt in isolated
LOCALAPPDATA/AtlasQuant/LAB/official_macro_receipts.

The RBA page may return HTTP 403 to ordinary clients. Respect that:
no retries, user-agent bypass, browser emulation, CAPTCHA, proxies,
fees, broker calls, trading, scheduler or production update.
"""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
from hashlib import sha256
import json,os
from pathlib import Path
from urllib.request import Request,urlopen
from typing import Any,Callable
from atlasquant_trader_aud_rba_cash_target_receipt_lab import (
    URL,MAX_BYTES,inspect_rba_cash_target_current_receipt_lab,
)

def _now()->str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def collect_rba_cash_target_once_lab(
    *,open_url:Callable[...,Any]=urlopen,
    now_utc:Callable[[],str]=_now
)->tuple[bytes,dict[str,Any]]:
    start=now_utc()
    req=Request(URL,headers={"Accept":"text/html",
          "User-Agent":"AtlasQuantTrader-LAB-Research/1.0"})
    with open_url(req,timeout=12) as response:
        body=response.read(MAX_BYTES+1)
        if len(body)>MAX_BYTES:
            raise ValueError("RBA_SOURCE_BODY_TOO_LARGE")
        rec={
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
    return body,rec

def save_rba_target_public_receipt_lab(
    *,body:bytes,receipt:dict[str,Any],local_appdata:str
)->tuple[Path,Path]:
    if not local_appdata or not Path(local_appdata).is_absolute():
        raise ValueError("RBA_LAB_LOCALAPPDATA_MUST_BE_ABSOLUTE")
    root=(Path(local_appdata)/"AtlasQuant"/"LAB").resolve()
    folder_raw=root/"official_macro_receipts"
    if folder_raw.is_symlink():
        raise ValueError("RBA_LAB_SYMLINK_DESTINATION_REFUSED")
    folder=folder_raw.resolve()
    if not folder.is_relative_to(root):
        raise ValueError("RBA_LAB_OUTPUT_OUTSIDE_ROOT")
    folder.mkdir(parents=True,exist_ok=True)
    stamp=receipt["finished_at_utc"].replace("-","").replace(":","")
    stem=f"AUD_RBA_CASH_TARGET_{stamp}_{receipt['body_sha256'][:12]}"
    orig=folder/(stem+".html")
    meta=folder/(stem+".receipt.json")
    if orig.exists() or meta.exists():
        raise FileExistsError("RBA_RECORD_ALREADY_EXISTS_NO_OVERWRITE")
    with orig.open("xb") as output:
        output.write(body)
    with meta.open("xb") as output:
        output.write(
            (json.dumps(receipt,sort_keys=True,indent=2)+"\n").encode("utf-8"))
    return orig,meta

def main()->int:
    parser=argparse.ArgumentParser()
    parser.add_argument("--capture",action="store_true")
    args=parser.parse_args()
    if not args.capture:
        print("LAB_NO_NETWORK_NO_FILES: manual --capture required")
        return 2
    try:
        body,receipt=collect_rba_cash_target_once_lab()
        cutoff=datetime.strptime(
            receipt["finished_at_utc"],"%Y-%m-%dT%H:%M:%SZ"
        ).replace(tzinfo=timezone.utc)
        report=inspect_rba_cash_target_current_receipt_lab(
            original_html=body,receipt=receipt,decision_at_utc=cutoff)
        if report["state"]!="LAB_AUD_RBA_CASH_TARGET_HTML_LOCALLY_CHECKED_NO_GO":
            print("LAB_RBA_CAPTURE_BLOCKED: "+report["reason"])
            return 2
        source,rec=save_rba_target_public_receipt_lab(
            body=body,receipt=receipt,
            local_appdata=os.environ.get("LOCALAPPDATA",""))
        print(json.dumps({
            "state":report["state"],
            "original_local_only":str(source),
            "receipt_local_only":str(rec),
            "sha256":receipt["body_sha256"],
            "cash_rate_target_pct_claim":report["target_cash_rate_pct_claim"],
            "effective_date_claim":report["target_effective_date_claim"],
            "issuer_release_hour_independently_attested":False,
            "historical_first_seen_vintage_verified":False,
            "aonia_conflated":False,
            "operational_bias":"AGUARDAR",
            "trade_authorized":False,
        },ensure_ascii=False,indent=2))
        return 0
    except (OSError,ValueError,KeyError,TypeError,OverflowError):
        print("LAB_RBA_SOURCE_NOT_CAPTURED_NO_GO")
        return 2

if __name__=="__main__":
    raise SystemExit(main())
