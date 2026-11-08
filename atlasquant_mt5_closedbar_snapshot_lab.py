"""AtlasQuant Trader: offline-only MT5 candle export (LAB). No orders or positions.

Requires existing open MT5 terminal, installed MetaTrader5 in this script folder,
numpy from the Python 3.11 environment. Writes no account/server credentials.
Every export excludes bar index 0 (potentially open/incomplete).
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import gzip
from hashlib import sha256
from io import BytesIO, StringIO
import json
import math
import os
from pathlib import Path
import sys

import MetaTrader5 as mt5
import numpy as np

SYMBOLS = (
    "EURUSD GBPUSD AUDUSD NZDUSD USDJPY USDCHF USDCAD "
    "EURGBP EURJPY EURCHF EURCAD EURAUD EURNZD "
    "GBPJPY GBPCHF GBPCAD GBPAUD GBPNZD "
    "AUDJPY AUDCHF AUDCAD AUDNZD "
    "NZDJPY NZDCHF NZDCAD CADJPY CADCHF CHFJPY"
).split()
REQUESTS = (("M15", mt5.TIMEFRAME_M15, 3000),
            ("D1", mt5.TIMEFRAME_D1, 500),
            ("W1", mt5.TIMEFRAME_W1, 200))
COLUMNS = ("time_utc_epoch", "open", "high", "low", "close",
           "tick_volume", "spread", "real_volume")
SCHEMA = "ATLASQUANT_MT5_CLOSED_BARS_LOCAL_LAB_V1"


def utc(when: float) -> str:
    return datetime.fromtimestamp(int(when), tz=timezone.utc).isoformat()


def serialize_bars(rates) -> bytes:
    output = StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(COLUMNS)
    for bar in rates:
        writer.writerow((int(bar["time"]), repr(float(bar["open"])),
                         repr(float(bar["high"])), repr(float(bar["low"])),
                         repr(float(bar["close"])), int(bar["tick_volume"]),
                         int(bar["spread"]), int(bar["real_volume"])))
    return output.getvalue().encode("utf-8")


def validate(rates) -> list[str]:
    if rates is None or len(rates) == 0:
        return ["NO_BARS"]
    errors: list[str] = []
    times = rates["time"]
    if not np.all(np.diff(times) > 0):
        errors.append("NON_INCREASING_TIME")
    for name in ("open", "high", "low", "close"):
        if not np.all(np.isfinite(rates[name])):
            errors.append(name.upper() + "_NONFINITE")
        if not np.all(rates[name] > 0):
            errors.append(name.upper() + "_NONPOSITIVE")
    if not np.all(rates["high"] >= np.maximum(rates["open"], rates["close"])):
        errors.append("HIGH_BELOW_BODY")
    if not np.all(rates["low"] <= np.minimum(rates["open"], rates["close"])):
        errors.append("LOW_ABOVE_BODY")
    if not np.all(rates["high"] >= rates["low"]):
        errors.append("HIGH_BELOW_LOW")
    for name in ("tick_volume", "spread", "real_volume"):
        if not np.all(rates[name] >= 0):
            errors.append(name.upper() + "_NEGATIVE")
    return errors


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", type=int, required=True)
    parser.add_argument("--count", type=int, default=4)
    args = parser.parse_args()
    if not (0 <= args.start < 28 and 1 <= args.count <= 6):
        raise SystemExit("SAFE_BATCH_RANGE_REQUIRED")
    output_dir = (Path(os.environ["LOCALAPPDATA"]) / "AtlasQuant" / "LAB" /
                  "MT5_Snapshots" / "20261107_AM12")
    output_dir.mkdir(parents=True, exist_ok=True)
    if not mt5.initialize(path=r"C:\Program Files\MetaTrader 5\terminal64.exe",
                          timeout=10000):
        raise SystemExit("MT5_UNAVAILABLE_FOR_READONLY_PROBE")
    try:
        terminal = mt5.terminal_info()
        if terminal is None or not terminal.connected:
            raise SystemExit("MT5_DISCONNECTED")
        selected = SYMBOLS[args.start:args.start + args.count]
        records = []
        for symbol in selected:
            info = mt5.symbol_info(symbol)
            if info is None or not info.visible:
                records.append({"symbol": symbol, "error": "NOT_VISIBLE"})
                print("SYMBOL", symbol, "NOT_VISIBLE", flush=True)
                continue
            for label, timeframe, requested in REQUESTS:
                rates = mt5.copy_rates_from_pos(symbol, timeframe, 1, requested)
                errors = validate(rates)
                count = 0 if rates is None else len(rates)
                if count != requested:
                    errors.append("INCOMPLETE_REQUEST")
                record = {
                    "symbol": symbol, "timeframe": label, "requested": requested,
                    "returned": count, "bar_position_start": 1,
                    "observed_at_utc": utc(datetime.now(timezone.utc).timestamp()),
                    "earliest_open_utc": utc(rates[0]["time"]) if count else None,
                    "latest_open_utc": utc(rates[-1]["time"]) if count else None,
                    "validation_errors": errors, "sha256_uncompressed_csv": None,
                    "snapshot_file": None,
                }
                if count > 0 and not errors:
                    raw = serialize_bars(rates)
                    raw_sha = sha256(raw).hexdigest()
                    target = output_dir / f"{symbol}_{label}_closedbar.csv.gz"
                    buffer = BytesIO()
                    with gzip.GzipFile(fileobj=buffer, mode="wb", filename="",
                                       compresslevel=6, mtime=0) as gz:
                        gz.write(raw)
                    tmp = target.with_suffix(".gz.tmp")
                    tmp.write_bytes(buffer.getvalue())
                    os.replace(tmp, target)
                    record["sha256_uncompressed_csv"] = raw_sha
                    record["snapshot_file"] = target.name
                records.append(record)
                print("CHECK", symbol, label, "BARS", count,
                      "OK" if not errors else ",".join(errors), flush=True)
        result = {
            "schema": SCHEMA, "research_only": True, "trade_authorized": False,
            "prediction_available": False, "operational_bias": "AGUARDAR",
            "broker_identity_independently_verified": False,
            "historical_point_in_time_verified": False,
            "price_vendor": "MT5_TERMINAL_UNATTESTED",
            "terminal_build": int(terminal.build),
            "batch_start": args.start, "batch_count": len(selected),
            "snapshot_dir": str(output_dir),
            "record_count": len(records), "records": records,
        }
        target = output_dir / f"batch_{args.start:02d}_manifest.json"
        tmp = target.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n",
                       encoding="utf-8")
        os.replace(tmp, target)
        print("SUMMARY", "RECORDS", len(records), "FULL_VALID",
              sum(r.get("sha256_uncompressed_csv") is not None for r in records),
              "FAILURES", sum(r.get("sha256_uncompressed_csv") is None for r in records),
              "MANIFEST", target, flush=True)
    finally:
        mt5.shutdown()


if __name__ == "__main__":
    main()
