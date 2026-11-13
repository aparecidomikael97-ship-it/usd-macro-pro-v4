"""One-shot exact ECB SDMX CSV local-evidence capture: LAB only.

Run explicitly with --capture. Retains original public CSV and a JSON
receipt under LOCALAPPDATA/AtlasQuant/LAB/official_macro_receipts only.
Never touches broker, account, orders, forecasts or GitHub. Does not
attest publication vintage or change a NO-GO decision.
"""
from __future__ import annotations

import argparse
from datetime import datetime,timezone
from hashlib import sha256
import json,os
from pathlib import Path
from urllib.request import Request,urlopen
from typing import Any,Callable

from atlasquant_trader_eur_ecb_dfr_sdmx_receipt_lab import (
    URL,MAX_BYTES,inspect_ecb_dfr_change_date_csv_receipt_lab,
)


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def collect_ecb_dfr_once_lab(
    *,open_url:Callable[...,Any]=urlopen,
    now_utc:Callable[[],str]=_now,
) -> tuple[bytes,dict[str,Any]]:
    start=now_utc()
    request=Request(URL,headers={
        "Accept":"text/csv",
        "User-Agent":"AtlasQuantTrader-LAB/1.0",
    })
    with open_url(request,timeout=12) as response:
        raw=response.read(MAX_BYTES+1)
        if len(raw)>MAX_BYTES:
            raise ValueError("ECB_RESPONSE_OVERSIZE")
        rec={
            "source_url":URL,
            "final_url":response.geturl(),
            "http_status":response.status,
            "content_type":response.headers.get("Content-Type",""),
            "body_sha256":sha256(raw).hexdigest(),
            "started_at_utc":start,
            "finished_at_utc":now_utc(),
            "https_validation_claim":True,
            "redirects_followed":response.geturl()!=URL,
        }
    return raw,rec


def save_ecb_dfr_lab(
    *,body:bytes,receipt:dict[str,Any],local_appdata:str,
) -> tuple[Path,Path]:
    if not local_appdata or not Path(local_appdata).is_absolute():
        raise ValueError("LOCALAPPDATA_NOT_ABSOLUTE")
    base=(Path(local_appdata)/"AtlasQuant"/"LAB").resolve()
    outdir=(base/"official_macro_receipts").resolve()
    if not outdir.is_relative_to(base) or outdir.is_symlink():
        raise ValueError("NOT_AN_ISOLATED_LAB_OUTPUT_DIR")
    outdir.mkdir(parents=True,exist_ok=True)
    stamp=receipt["finished_at_utc"].replace("-","").replace(":","")
    prefix=f"EUR_ECB_FM_B_DFR_{stamp}_{receipt['body_sha256'][:12]}"
    csv_path=outdir/(prefix+".csv")
    rec_path=outdir/(prefix+".receipt.json")
    if csv_path.exists() or rec_path.exists():
        raise FileExistsError("SOURCE_RECEIPT_ALREADY_EXISTS_NO_OVERWRITE")
    with csv_path.open("xb") as file:
        file.write(body)
    with rec_path.open("xb") as file:
        file.write((json.dumps(receipt,sort_keys=True,indent=2)+"\n").encode("utf-8"))
    return csv_path,rec_path


def main() -> int:
    parser=argparse.ArgumentParser()
    parser.add_argument("--capture",action="store_true")
    args=parser.parse_args()
    if not args.capture:
        print("LAB_NO_HTTP_OR_FILE: --capture required")
        return 2
    try:
        body,receipt=collect_ecb_dfr_once_lab()
        cutoff=datetime.strptime(
            receipt["finished_at_utc"],"%Y-%m-%dT%H:%M:%SZ").replace(
                tzinfo=timezone.utc)
        check=inspect_ecb_dfr_change_date_csv_receipt_lab(
            original_csv=body,receipt=receipt,decision_at_utc=cutoff)
        if check["state"] != "LAB_EUR_ECB_SDMX_ORIGINAL_BYTES_LOCALLY_CHECKED_NO_GO":
            print("ECB_LAB_BLOCKED: "+check["reason"])
            return 2
        p,r=save_ecb_dfr_lab(
            body=body,receipt=receipt,
            local_appdata=os.environ.get("LOCALAPPDATA",""))
        print(json.dumps({
            "state":check["state"],
            "local_original_csv":str(p),
            "local_receipt_json":str(r),
            "sha256":receipt["body_sha256"],
            "last_change_date":check["last_effective_change_date_claim"],
            "deposit_rate_pct":check["latest_deposit_rate_pct_claim"],
            "true_first_release_time_authenticated":False,
            "validated_directional_accuracy":None,
            "operational_bias":"AGUARDAR","trade_authorized":False,
        },indent=2,ensure_ascii=False))
        return 0
    except (OSError,ValueError,KeyError,TypeError):
        print("LAB_ECB_CAPTURE_FAILED_NO_TRADE")
        return 2


if __name__=="__main__":
    raise SystemExit(main())
