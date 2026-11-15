"""FX28 extra semantic CSV review: LAB ONLY / offline / NO trading.

Uses the existing frozen write-once verifier first, then validates actual CSV
field names, OHLC constraints, quote-digit grid and volume syntax. Runs only
when explicitly called with --verify. Does NOT change the scheduled collector.
This is structural consistency, NOT source/broker/PIT authentication.
"""
from __future__ import annotations
import argparse,csv,hashlib,json,re,sys
from decimal import Decimal,InvalidOperation
from io import StringIO
from pathlib import Path
from atlasquant_trader_fx28_ny17_m15_writeonce_capture_lab import (
    PAIRS,verify_archive_lab,
)
from atlasquant_trader_ppi_usd_fx_forward_reaction_lab import FIELDS
PRICE=re.compile(r"[0-9]{1,7}(?:\.[0-9]{1,9})?\Z")
NUMBER=re.compile(r"[0-9]{1,12}\Z")
EPOCH=re.compile(r"[1-9][0-9]{9,11}\Z")
def assert_semantics(folder:Path):
    prior=verify_archive_lab(folder)
    manifest_path=folder/"manifest.json"
    manifest_bytes=manifest_path.read_bytes()
    if hashlib.sha256(manifest_bytes).hexdigest()!=prior["manifest_sha256"]:
        raise ValueError("MANIFEST_CHANGED_BETWEEN_READS")
    manifest=json.loads(manifest_bytes)
    if set(manifest["files"])!=set(PAIRS):
        raise ValueError("UNEXPECTED_SYMBOLS")
    verified=0
    total=0
    for sym in PAIRS:
        path=folder/f"{sym}_M15.csv"
        if path.is_symlink() or not path.is_file():
            raise ValueError("MISSING_OR_LINKED_CSV_"+sym)
        raw=path.read_bytes()
        claim=manifest["files"][sym]
        if hashlib.sha256(raw).hexdigest()!=claim["sha256"]:
            raise ValueError("CSV_CHANGED_BETWEEN_READS_"+sym)
        try:
            reader=csv.DictReader(StringIO(raw.decode("utf-8","strict"),newline=""),strict=True)
            if tuple(reader.fieldnames or ())!=FIELDS:
                raise ValueError("INVALID_CSV_HEADER_"+sym)
            digits=claim.get("price_digits_claim")
            if type(digits) is not int or not 2<=digits<=6:
                raise ValueError("INVALID_QUOTE_DIGITS_"+sym)
            tick=Decimal(1).scaleb(-digits)
            n=0
            for row in reader:
                if None in row or tuple(row.keys())!=FIELDS or any(v is None for v in row.values()):
                    raise ValueError("MALFORMED_CSV_ROW_"+sym)
                stamp=row["time_utc_epoch"]
                if not isinstance(stamp,str) or not EPOCH.fullmatch(stamp):
                    raise ValueError("NONCANONICAL_M15_EPOCH_"+sym)
                p={}
                for k in ("open","high","low","close"):
                    s=row[k]
                    if not isinstance(s,str) or not PRICE.fullmatch(s):
                        raise ValueError("INVALID_CSV_PRICE_"+sym)
                    try:
                        v=Decimal(s)
                        if not v.is_finite() or v<=0 or v!=v.quantize(tick):
                            raise ValueError("INVALID_CSV_PRICE_GRID_"+sym)
                        p[k]=v
                    except InvalidOperation:
                        raise ValueError("INVALID_CSV_PRICE_"+sym)
                if p["low"]>min(p["open"],p["close"]) or p["high"]<max(p["open"],p["close"]) or p["low"]>p["high"]:
                    raise ValueError("IMPOSSIBLE_OHLC_RANGE_"+sym)
                for k in ("tick_volume","spread","real_volume"):
                    v=row[k]
                    if not isinstance(v,str) or not NUMBER.fullmatch(v) or (k=="tick_volume" and int(v)<=0):
                        raise ValueError("INVALID_VOLUME_OR_SPREAD_"+sym)
                n+=1
        except (csv.Error,UnicodeError) as exc:
            raise ValueError("UNREADABLE_CSV_"+sym) from exc
        if n!=claim["m15_returned"]:
            raise ValueError("CSV_BAR_COUNT_MISMATCH_"+sym)
        verified+=1
        total+=n
    return {
        "state":"LAB_FX28_SEMANTIC_CSV_REVIEW_OK_CLAIM_ONLY_NO_GO",
        "symbols_structurally_verified":verified,
        "m15_rows_semantically_checked":total,
        "m15_gaps_from_base_verifier":prior["missing_m15_total"],
        "manifest_sha256":prior["manifest_sha256"],
        "broker_first_seen_attested":False,
        "independent_broker_authentication":False,
        "forecast_authenticated":False,
        "trading_authorized":False,"operational_bias":"AGUARDAR",
        "network_calls":0,"mt5_calls":0,"file_writes":0,
    }
def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--verify",type=Path,required=True)
    args=parser.parse_args()
    try:
        result=assert_semantics(args.verify)
        rc=0
    except (ValueError,TypeError,KeyError,OSError,OverflowError) as exc:
        result={"state":"LAB_FX28_SEMANTIC_CSV_REVIEW_BLOCKED_NO_GO",
                "reason":type(exc).__name__+":"+str(exc),
                "trading_authorized":False}
        rc=2
    print(json.dumps(result,sort_keys=True))
    return rc
if __name__=="__main__":
    raise SystemExit(main())
