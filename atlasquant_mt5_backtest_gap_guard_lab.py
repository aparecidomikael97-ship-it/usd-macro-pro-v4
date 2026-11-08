"""Fail-closed temporal guard for future AtlasQuant MT5 backtest research.

This is an offline LAB component, NOT a backtest runner. Every non-nominal
interval remains a barrier until a separate, evidenced broker-calendar policy
is built and reviewed. No price interpolation and no trading/MT5 API calls.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
from datetime import datetime, timezone
import gzip
from io import StringIO
import json
from pathlib import Path

from atlasquant_mt5_calendar_gap_audit_lab import (
    BAR_SECONDS, DEFAULT_ROOT, ROWS_EXPECTED, audit, classify_gap,
)

SCHEMA = "ATLASQUANT_MT5_BACKTEST_GAP_GUARD_LAB_V1"
CSV_FIELDS = ("time_utc_epoch", "open", "high", "low", "close",
              "tick_volume", "spread", "real_volume")


class GapGuardError(ValueError):
    """An input or unverified interval must not enter a historical label."""


def _iso(epoch: int) -> str:
    return datetime.fromtimestamp(epoch, timezone.utc).isoformat()


def _validate(symbol: str, tf: str, times: list[int]) -> None:
    if (not isinstance(symbol, str) or len(symbol) != 6 or
            not symbol.isascii() or not symbol.isalpha() or not symbol.isupper()):
        raise GapGuardError("INVALID_SYMBOL")
    if tf not in BAR_SECONDS:
        raise GapGuardError("INVALID_TIMEFRAME")
    if not isinstance(times, list) or not times:
        raise GapGuardError("EMPTY_OR_INVALID_TIMESTAMPS")
    if any(type(t) is not int or t <= 0 for t in times):
        raise GapGuardError("INVALID_TIMESTAMP_TYPE_OR_VALUE")
    if any(b <= a for a, b in zip(times, times[1:])):
        raise GapGuardError("TIMESTAMPS_NOT_STRICTLY_INCREASING")
    if tf in ("M15", "D1") and any(t % BAR_SECONDS[tf] for t in times):
        raise GapGuardError("TIMESTAMP_OFF_UTC_GRID")


def _blocked_edge(symbol: str, tf: str, a: int, b: int) -> dict | None:
    kind = classify_gap(tf, a, b)
    if kind == "NOMINAL":
        return None
    return {
        "symbol": symbol, "timeframe": tf,
        "earlier_open_utc": _iso(a), "later_open_utc": _iso(b),
        "classification": kind, "policy": "BLOCK_UNTIL_INDEPENDENT_VERIFICATION",
    }


def partition_series(symbol: str, tf: str, times: list[int]) -> dict:
    """Split at EVERY non-nominal gap, including weekend candidates.

    Segment boundaries are inclusive indices into the original ordered CSV.
    Contiguous is not equivalent to point-in-time or backtest approval.
    """
    _validate(symbol, tf, times)
    segments = []
    barriers = []
    start = 0
    for i in range(1, len(times)):
        barrier = _blocked_edge(symbol, tf, times[i - 1], times[i])
        if barrier is None:
            continue
        barrier["earlier_index"] = i - 1
        barrier["later_index"] = i
        barriers.append(barrier)
        segments.append({"first_index": start, "last_index": i - 1,
                         "bars": i - start})
        start = i
    segments.append({"first_index": start, "last_index": len(times) - 1,
                     "bars": len(times) - start})
    return {"symbol": symbol, "timeframe": tf, "bars": len(times),
            "segments": segments, "blocked_intervals": barriers,
            "calendar_status": "GAPS_BLOCKED" if barriers else "CONTIGUOUS_ONLY"}


def window_decision(symbol: str, tf: str, times: list[int],
                    first_index: int, last_index: int) -> dict:
    """Check an inclusive [first,last] window before labeling/feature use.

    No positive backtest authorization is ever returned: even a nominally
    contiguous window needs separate point-in-time and price provenance gates.
    """
    _validate(symbol, tf, times)
    if (type(first_index) is not int or type(last_index) is not int or
            first_index < 0 or last_index >= len(times) or
            first_index >= last_index):
        raise GapGuardError("INVALID_WINDOW_INDICES")
    barriers = [edge for i in range(first_index + 1, last_index + 1)
                if (edge := _blocked_edge(symbol, tf, times[i - 1], times[i]))]
    return {
        "status": "BLOCKED_UNVERIFIED_GAP" if barriers else "CALENDAR_CONTIGUOUS_UNATTESTED",
        "symbol": symbol, "timeframe": tf,
        "first_index": first_index, "last_index": last_index,
        "calendar_contiguous": not barriers,
        "blocked_intervals": barriers,
        "backtest_approved": False, "operational_bias": "AGUARDAR",
    }


def require_contiguous_window(symbol: str, tf: str, times: list[int],
                              first_index: int, last_index: int) -> dict:
    """Reject a crossing; a successful return authorizes *only* continuity."""
    decision = window_decision(symbol, tf, times, first_index, last_index)
    if not decision["calendar_contiguous"]:
        raise GapGuardError("UNVERIFIED_GAP_CROSSED")
    return decision


def audit_archive(root: Path) -> dict:
    """Read existing local snapshots, verify their audit first, then partition.

    Never changes the archive. Intended for diagnostic reports in the LAB only.
    """
    root = Path(root)
    source = audit(root)
    report = {
        "schema": SCHEMA, "source_audit_status": source["status"],
        "snapshot_root": str(root), "status": "BLOCKED_INVALID_ARCHIVE",
        "errors": list(source["errors"]), "pairs": source["pairs"],
        "files": source["files_verified"], "bars": source["bar_count"],
        "blocked_interval_counts": {}, "segments_total": 0,
        "series_partitions": [], "gbpnzd_2025_09_30_blocked": False,
        "broker_calendar_verified": False, "historical_point_in_time_verified": False,
        "backtest_approved": False, "trade_authorized": False,
        "operational_bias": "AGUARDAR", "new_cost_brl": 0,
    }
    if (source["errors"] or source["pairs"] != 28 or
            source["files_verified"] != 84 or source["bar_count"] != 103600):
        report["errors"].append("FULL_ARCHIVE_INTEGRITY_REQUIRED")
        return report

    kinds = Counter()
    try:
        for manifest_path in sorted(root.glob("batch_??_manifest.json")):
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if manifest.get("schema") != "ATLASQUANT_MT5_CLOSED_BARS_LOCAL_LAB_V1":
                raise GapGuardError("UNEXPECTED_MANIFEST_SCHEMA")
            for record in manifest["records"]:
                symbol, tf = record["symbol"], record["timeframe"]
                if (record.get("validation_errors") or
                        record.get("requested") != ROWS_EXPECTED[tf] or
                        record.get("returned") != ROWS_EXPECTED[tf]):
                    raise GapGuardError("UPSTREAM_SNAPSHOT_NOT_VALIDATED")
                data = gzip.decompress((root / record["snapshot_file"]).read_bytes())
                reader = csv.DictReader(StringIO(data.decode("utf-8")))
                if tuple(reader.fieldnames or ()) != CSV_FIELDS:
                    raise GapGuardError("UNEXPECTED_CSV_FIELDS")
                times = [int(row["time_utc_epoch"]) for row in reader]
                partition = partition_series(symbol, tf, times)
                barriers = partition["blocked_intervals"]
                kinds.update(b["classification"] for b in barriers)
                if symbol == "GBPNZD" and tf == "D1":
                    report["gbpnzd_2025_09_30_blocked"] = any(
                        b["earlier_open_utc"].startswith("2025-09-29T") and
                        b["later_open_utc"].startswith("2025-10-01T") and
                        b["classification"].startswith("REVIEW") for b in barriers)
                report["segments_total"] += len(partition["segments"])
                report["series_partitions"].append(partition)
    except (KeyError, IndexError, TypeError, ValueError, OSError, EOFError) as exc:
        report["errors"].append(f"PARTITION_FAILED_{type(exc).__name__}_{str(exc)[:100]}")
        report["series_partitions"] = []
        report["segments_total"] = 0
        return report

    report["blocked_interval_counts"] = dict(sorted(kinds.items()))
    report["status"] = "BLOCKED_UNVERIFIED_GAPS" if kinds else "CALENDAR_CONTIGUOUS_UNATTESTED"
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    args = parser.parse_args()
    report = audit_archive(args.root)
    print("GAP_GUARD", report["status"])
    print("PAIRS_FILES_BARS", report["pairs"], report["files"], report["bars"])
    print("BLOCKED_COUNTS", report["blocked_interval_counts"])
    print("SEGMENTS", report["segments_total"])
    print("GBPNZD_2025_09_30_BLOCKED", report["gbpnzd_2025_09_30_blocked"])
    print("BACKTEST_APPROVED", report["backtest_approved"])
    print("ERRORS", report["errors"][:5])
    raise SystemExit(2 if report["errors"] else 3 if report["status"] ==
                     "BLOCKED_UNVERIFIED_GAPS" else 0)


if __name__ == "__main__":
    main()
