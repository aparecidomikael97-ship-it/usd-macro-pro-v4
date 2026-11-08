"""Independent, offline integrity audit of AtlasQuant MT5 local snapshots (LAB).

Does not connect to MT5, brokers, accounts or any remote source. Hashes prove
local consistency only, not historical availability or market accuracy.
"""
from __future__ import annotations
import csv
from datetime import datetime, timezone
import gzip
from hashlib import sha256
from io import StringIO
import json
from pathlib import Path
import os
import math

ROOT = (Path(os.environ["LOCALAPPDATA"]) / "AtlasQuant" / "LAB" /
        "MT5_Snapshots" / "20261107_AM12")
SCHEMA = "ATLASQUANT_MT5_CLOSED_BARS_LOCAL_LAB_V1"
AUDIT_SCHEMA = "ATLASQUANT_MT5_SNAPSHOT_AUDIT_LAB_V1"
FIELDS = ["time_utc_epoch", "open", "high", "low", "close",
          "tick_volume", "spread", "real_volume"]
EXPECTED = {"M15": 3000, "D1": 500, "W1": 200}
SECONDS = {"M15": 900, "D1": 86400, "W1": 604800}

def main():
    # Optional isolated test root allows tamper testing without touching originals.
    global ROOT
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, default=ROOT)
    ROOT = parser.parse_args().root
    errors: list[str] = []
    snapshots: list[dict] = []
    file_bytes = 0
    pairs: set[str] = set()
    frames: dict[str, dict] = {}
    manifests = sorted(ROOT.glob("batch_??_manifest.json"))
    if len(manifests) != 7:
        errors.append(f"MANIFESTS_EXPECTED_7_GOT_{len(manifests)}")
    for name in manifests:
        manifest_raw = name.read_bytes()
        item = json.loads(manifest_raw)
        if item.get("schema") != SCHEMA or item.get("trade_authorized") is not False:
            errors.append(f"INVALID_MANIFEST:{name.name}")
        data = item.get("records", [])
        if len(data) != 12:
            errors.append(f"INCOMPLETE_BATCH:{name.name}")
        for record in data:
            symbol, frame = record["symbol"], record["timeframe"]
            key = f"{symbol}:{frame}"
            pairs.add(symbol)
            if key in frames:
                errors.append(f"DUPLICATE_SERIES:{key}")
                continue
            frames[key] = record
            if record["bar_position_start"] != 1 or record["returned"] != EXPECTED[frame]:
                errors.append(f"BAR_COUNT_OR_INDEX:{key}")
                continue
            if record["validation_errors"]:
                errors.append(f"UPSTREAM_VALIDATION_FAILED:{key}")
            target = ROOT / f"{symbol}_{frame}_closedbar.csv.gz"
            if target.name != record.get("snapshot_file") or not target.is_file():
                errors.append(f"MISSING_SNAPSHOT:{key}")
                continue
            compressed = target.read_bytes()
            file_bytes += len(compressed)
            try:
                raw = gzip.decompress(compressed)
                actual_hash = sha256(raw).hexdigest()
                if actual_hash != record["sha256_uncompressed_csv"]:
                    errors.append(f"HASH_MISMATCH:{key}")
                reader = csv.DictReader(StringIO(raw.decode("utf-8")))
                if reader.fieldnames != FIELDS:
                    errors.append(f"CSV_SCHEMA:{key}")
                rows = list(reader)
                if len(rows) != EXPECTED[frame]:
                    errors.append(f"CSV_ROW_COUNT:{key}")
                times = [int(x["time_utc_epoch"]) for x in rows]
                if not times or any(b <= a for a,b in zip(times,times[1:])):
                    errors.append(f"TIME_NOT_MONOTONIC:{key}")
                if times:
                    oldest = datetime.fromtimestamp(times[0],timezone.utc).isoformat()
                    newest = datetime.fromtimestamp(times[-1],timezone.utc).isoformat()
                    if (oldest != record["earliest_open_utc"] or
                            newest != record["latest_open_utc"]):
                        errors.append(f"TIME_MANIFEST_MISMATCH:{key}")
                for row in rows:
                    o,h,l,c = (float(row[f]) for f in ("open","high","low","close"))
                    if (not all(math.isfinite(v) and v>0 for v in (o,h,l,c))
                            or h < max(o,c) or l > min(o,c) or h < l
                            or any(int(row[f]) < 0 for f in
                                   ("tick_volume","spread","real_volume"))):
                        errors.append(f"OHLC_VALUE_INVALID:{key}")
                        break
                gaps = sum(b-a>SECONDS[frame] for a,b in zip(times,times[1:]))
                snapshots.append({"symbol":symbol,"timeframe":frame,
                                  "bars":len(rows), "earliest":oldest,
                                  "latest":newest,"sha256_csv":actual_hash,
                                  "compressed_bytes":len(compressed),
                                  "larger_than_nominal_intervals":gaps})
            except Exception as exc:
                errors.append(f"CSV_VERIFY_FAILED:{key}:{type(exc).__name__}")
    if len(pairs)!=28 or len(frames)!=84:
        errors.append(f"COVERAGE_PAIRS_{len(pairs)}_SERIES_{len(frames)}")
    output={
        "schema":AUDIT_SCHEMA, "checked_at_utc":datetime.now(timezone.utc).isoformat(),
        "source":"AM12_MT5_TERMINAL_UNATTESTED",
        "directory":str(ROOT),"symbol_count":len(pairs),
        "series_count":len(frames),"verified_series":len(snapshots),
        "verified_bars":sum(x["bars"] for x in snapshots),
        "verified_compressed_bytes":file_bytes,
        "oldest_by_tf":{tf:min((x["earliest"] for x in snapshots if x["timeframe"]==tf),default=None) for tf in EXPECTED},
        "latest_by_tf":{tf:max((x["latest"] for x in snapshots if x["timeframe"]==tf),default=None) for tf in EXPECTED},
        "larger_than_nominal_intervals_by_tf":{tf:sum(x["larger_than_nominal_intervals"] for x in snapshots if x["timeframe"]==tf) for tf in EXPECTED},
        "manifest_count":len(manifests),
        "audit_errors":errors, "status":"LOCAL_INTEGRITY_PASS" if not errors else "LOCAL_INTEGRITY_FAIL",
        "historical_point_in_time_verified":False, "issuer_or_broker_authenticated":False,
        "economic_vintages_verified":False,"out_of_sample_accuracy_verified":False,
        "operational_bias":"AGUARDAR","score_0_to_10":None,
        "can_feed_live_radar":False, "trade_authorized":False,
    }
    target=ROOT/"audit_summary.json"
    tmp=ROOT/"audit_summary.json.tmp"
    tmp.write_text(json.dumps(output,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    os.replace(tmp,target)
    print("AUDIT_STATUS",output["status"])
    print("PAIRS",len(pairs),"SERIES",len(frames),
          "VERIFIED_SERIES",len(snapshots),"VERIFIED_BARS",output["verified_bars"])
    print("COMPRESSED_MIB",round(file_bytes/1024**2,3))
    print("OLDEST_BY_TF",output["oldest_by_tf"])
    print("LATEST_BY_TF",output["latest_by_tf"])
    print("LARGER_THAN_NOMINAL_GAPS",output["larger_than_nominal_intervals_by_tf"],
          "(weekends/market closures included; not all missing bars)")
    print("ERRORS",errors[:20])
    print("SUMMARY_PATH",target)
    raise SystemExit(0 if not errors else 2)

if __name__=="__main__":
    main()
