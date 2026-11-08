"""Read-only audit of timestamp gaps in local MT5 G8/28 snapshots.

Weekends are classified as candidates, not certified broker sessions.
Uses only files written by the earlier collector. No MT5 API or trading calls.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
from datetime import datetime, timezone
import gzip
from hashlib import sha256
from io import StringIO
import json
import os
from pathlib import Path

SCHEMA = "ATLASQUANT_MT5_CALENDAR_GAP_AUDIT_LAB_V1"
BAR_SECONDS = {"M15": 900, "D1": 86400, "W1": 604800}
ROWS_EXPECTED = {"M15": 3000, "D1": 500, "W1": 200}
DEFAULT_ROOT = (Path(os.environ.get("LOCALAPPDATA", ".")) /
                "AtlasQuant" / "LAB" / "MT5_Snapshots" / "20261107_AM12")


def classify_gap(tf: str, earlier: int, later: int) -> str:
    """Timestamp-only classification; never asserts broker-market open."""
    if tf not in BAR_SECONDS or later <= earlier:
        return "REVIEW_INVALID_TIME_OR_TF"
    step = BAR_SECONDS[tf]
    if later == earlier + step:
        return "NOMINAL"
    if later < earlier + step or (later - earlier) % step != 0:
        return "REVIEW_NON_GRID_DELTA"
    first = datetime.fromtimestamp(earlier, timezone.utc)
    last = datetime.fromtimestamp(later, timezone.utc)
    if tf == "M15":
        if first.weekday() == 4 and last.weekday() in (6, 0):
            return "WEEKEND_CANDIDATE"
    elif tf == "D1":
        if first.weekday() == 4 and last.weekday() == 0 and (later - earlier) == 3 * step:
            return "WEEKEND_CANDIDATE"
        if first.weekday() == 4 and last.weekday() == 6 and (later - earlier) == 2 * step:
            return "WEEKEND_CANDIDATE"
    return "REVIEW_UNEXPLAINED"


def audit(root: Path) -> dict:
    root = Path(root)
    issues = []
    gap_kinds = Counter()
    per_tf = defaultdict(Counter)
    review_missing_dates = Counter()
    review_date_pairs = defaultdict(list)
    review_by_symbol = Counter()
    examples = []
    pair_frames = set()
    pair_names = set()
    earliest = {}
    latest = {}
    manifests = sorted(root.glob("batch_??_manifest.json"))
    if len(manifests) != 7:
        issues.append(f"MANIFEST_COUNT_{len(manifests)}")
    bars_total = 0
    files_count = 0
    for manifest_path in manifests:
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            records = manifest["records"]
        except (ValueError, OSError, KeyError) as exc:
            issues.append(f"MANIFEST_INVALID_{manifest_path.name}_{type(exc).__name__}")
            continue
        for record in records:
            try:
                symbol = record["symbol"]
                tf = record["timeframe"]
                if (not isinstance(symbol, str) or len(symbol) != 6 or
                        not symbol.isalpha() or tf not in BAR_SECONDS):
                    raise ValueError("UNSUPPORTED_SYMBOL_OR_TF")
                key = (symbol, tf)
                if key in pair_frames:
                    raise ValueError("DUPLICATE_SERIES")
                pair_frames.add(key)
                pair_names.add(symbol)
                target = root / f"{symbol}_{tf}_closedbar.csv.gz"
                if record["snapshot_file"] != target.name:
                    raise ValueError("SNAPSHOT_FILENAME_MISMATCH")
                raw = gzip.decompress(target.read_bytes())
                if sha256(raw).hexdigest() != record["sha256_uncompressed_csv"]:
                    raise ValueError("HASH_MISMATCH")
                data = list(csv.DictReader(StringIO(raw.decode("utf-8"))))
                if (len(data) != ROWS_EXPECTED[tf] or
                        record["returned"] != len(data) or
                        record["bar_position_start"] != 1):
                    raise ValueError("BAR_COUNT_OR_OPEN_BAR")
                times = [int(row["time_utc_epoch"]) for row in data]
                if not times or len(set(times)) != len(times):
                    raise ValueError("DUPLICATE_TIMESTAMP")
                if tf == "M15" and any(t % BAR_SECONDS[tf] for t in times):
                    raise ValueError("M15_OFF_GRID")
                if tf == "D1" and any(t % BAR_SECONDS[tf] for t in times):
                    raise ValueError("D1_OFF_GRID")
                pair_tf_counts = Counter()
                for x,y in zip(times,times[1:]):
                    cls = classify_gap(tf,x,y)
                    if cls == "NOMINAL":
                        continue
                    gap_kinds[cls] += 1
                    per_tf[tf][cls] += 1
                    pair_tf_counts[cls] += 1
                    if cls.startswith("REVIEW"):
                        review_by_symbol[symbol] += 1
                        if tf == "D1":
                            for missing in range(x + BAR_SECONDS[tf], y, BAR_SECONDS[tf]):
                                missing_date = datetime.fromtimestamp(missing,timezone.utc).date().isoformat()
                                review_missing_dates[missing_date] += 1
                                review_date_pairs[missing_date].append(symbol)
                    if cls.startswith("REVIEW") and len(examples) < 20:
                        examples.append({
                            "symbol": symbol, "timeframe": tf,
                            "start_utc": datetime.fromtimestamp(x,timezone.utc).isoformat(),
                            "end_utc": datetime.fromtimestamp(y,timezone.utc).isoformat(),
                            "delta_seconds": y-x, "classification": cls
                        })
                oldest = datetime.fromtimestamp(times[0],timezone.utc).isoformat()
                newest = datetime.fromtimestamp(times[-1],timezone.utc).isoformat()
                if (record["earliest_open_utc"] != oldest or
                        record["latest_open_utc"] != newest):
                    raise ValueError("MANIFEST_TIMESTAMP_MISMATCH")
                earliest[tf] = min(oldest, earliest.get(tf, oldest))
                latest[tf] = max(newest, latest.get(tf, newest))
                bars_total += len(times)
                files_count += 1
            except (KeyError, IndexError, ValueError, OSError, EOFError, TypeError) as exc:
                issues.append(f"FILE_INVALID_{record.get('symbol','?')}_{record.get('timeframe','?')}_{type(exc).__name__}_{str(exc)[:60]}")
    if len(pair_names) != 28 or len(pair_frames) != 84 or bars_total != 103600:
        issues.append("EXPECTED_28_PAIRS_84_SERIES_103600_BARS")
    review = sum(value for key,value in gap_kinds.items() if key.startswith("REVIEW"))
    outcome = "LOCAL_CALENDAR_CANDIDATE_PASS" if not issues and review == 0 else "LOCAL_CALENDAR_REVIEW_REQUIRED"
    result = {
        "schema": SCHEMA,
        "snapshot_root": str(root),
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": outcome, "pairs": len(pair_names),
        "files_verified": files_count, "bar_count": bars_total,
        "gap_class_counts": dict(gap_kinds),
        "gap_counts_by_tf": {name: dict(per_tf.get(name, {})) for name in BAR_SECONDS},
        "review_gap_count": review, "review_examples": examples,
        "missing_weekday_dates_to_review": dict(sorted(review_missing_dates.items())),
        "missing_weekday_date_pairs": {k: sorted(v) for k,v in sorted(review_date_pairs.items())},
        "review_gap_count_by_pair": dict(sorted(review_by_symbol.items())),
        "earliest_by_tf": earliest, "latest_by_tf": latest,
        "errors": issues,
        "classification_is_provisional": True,
        "broker_trading_schedule_verified": False,
        "historical_point_in_time_verified": False,
        "out_of_sample_probability_verified": False,
        "trade_authorized": False, "operational_bias": "AGUARDAR",
        "new_cost_brl": 0,
    }
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    args = parser.parse_args()
    result = audit(args.root)
    target = args.root / "calendar_gap_audit_summary.json"
    target.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("RESULT",result["status"], "PAIRS",result["pairs"], "FILES",result["files_verified"], "BARS",result["bar_count"])
    print("GAPS",result["gap_counts_by_tf"])
    print("REVIEW_GAP_COUNT",result["review_gap_count"])
    print("REVIEW_MISSING_DATES",result["missing_weekday_dates_to_review"])
    print("ISOLATED_DATES",{k:v for k,v in result["missing_weekday_date_pairs"].items() if len(v)<3})
    print("REVIEW_PAIRS",result["review_gap_count_by_pair"])
    print("EXAMPLES",result["review_examples"][:8])
    print("ERRORS",result["errors"][:15])
    print("REPORT",target)
    raise SystemExit(0 if not result["errors"] else 2)


if __name__ == "__main__":
    main()
