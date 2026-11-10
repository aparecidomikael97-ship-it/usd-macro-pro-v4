"""Offline, read-only audit of one isolated MT5 XAUUSD collector directory.

This verifies that the stored CSV, gzip and manifest agree. It cannot prove
Pepperstone identity, actual historic market prices, or point-in-time custody.
There are no MT5, network, order or filesystem write calls.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import gzip
from hashlib import sha256
from io import StringIO
import json
import math
from pathlib import Path
import re
from typing import Any

from atlasquant_mt5_xauusd_closedbar_capture_lab import FIELDS, REQUESTS, SCHEMA

AUDIT_SCHEMA = "ATLASQUANT_MT5_XAUUSD_ARCHIVE_AUDIT_LAB_V1"
MAX_MANIFEST_BYTES = 512_000
MAX_GZIP_BYTES = 2_000_000
MAX_CSV_BYTES = 3_000_000


def _base(root: Any) -> dict[str, Any]:
    return {
        "schema": AUDIT_SCHEMA,
        "capture_directory": str(root),
        "status": "LOCAL_XAUUSD_ARCHIVE_FAIL",
        "errors": [], "verified_series": 0, "verified_bars": 0,
        "timeframes": {}, "archive_read_only": True,
        "archive_is_independently_authenticated": False,
        "broker_identity_independently_authenticated": False,
        "candle_server_utc_independently_authenticated": False,
        "historical_point_in_time_verified": False,
        "news_and_geopolitics_authenticated": False,
        "calibrated_probability": None, "gold_bias": None,
        "validated_accuracy": None, "operational_bias": "AGUARDAR",
        "can_feed_live_radar": False, "publishable": False,
        "trade_authorized": False, "new_cost_brl": 0,
    }


def _check_series(root: Path, record: Any, label: str, count: int,
                  period: int, captured_epoch: int) -> dict[str, Any]:
    """Raise ValueError with a stable reason; never modify archive files."""
    if not isinstance(record, dict):
        raise ValueError("RECORD_NOT_OBJECT")
    filename = f"XAUUSD_{label}_closedbar.csv.gz"
    if (record.get("symbol") != "XAUUSD" or record.get("timeframe") != label
            or record.get("snapshot_file") != filename
            or type(record.get("requested")) is not int
            or record["requested"] != count
            or type(record.get("returned")) is not int
            or record["returned"] != count
            or type(record.get("bar_position_start")) is not int
            or record["bar_position_start"] != 1
            or record.get("validation_errors") != []):
        raise ValueError("RECORD_SCHEMA_OR_CLOSED_BAR_COUNT")
    checksum = record.get("sha256_uncompressed_csv")
    if not isinstance(checksum, str) or not re.fullmatch(r"[a-f0-9]{64}", checksum):
        raise ValueError("RECORD_HASH_MALFORMED")
    target = root / filename
    if target.is_symlink() or not target.is_file():
        raise ValueError("ARCHIVE_FILE_MISSING_OR_SYMLINK")
    if target.stat().st_size > MAX_GZIP_BYTES:
        raise ValueError("COMPRESSED_FILE_OVERSIZED")
    try:
        with gzip.open(target, "rb") as zipped:
            raw = zipped.read(MAX_CSV_BYTES + 1)
    except (OSError, EOFError, ValueError) as exc:
        raise ValueError("GZIP_UNREADABLE") from exc
    if len(raw) > MAX_CSV_BYTES:
        raise ValueError("DECOMPRESSED_CSV_OVERSIZED")
    if sha256(raw).hexdigest() != checksum:
        raise ValueError("ARCHIVE_SHA256_MISMATCH")
    try:
        reader = csv.DictReader(StringIO(raw.decode("utf-8"), newline=""))
        if reader.fieldnames != list(FIELDS):
            raise ValueError("CSV_HEADER_INVALID")
        times: list[int] = []
        for row in reader:
            if (len(row) != len(FIELDS)
                    or any(not isinstance(row.get(k), str) for k in FIELDS)):
                raise ValueError("CSV_ROW_SCHEMA_INVALID")
            epoch_str = row["time_utc_epoch"]
            if not epoch_str.isascii() or not epoch_str.isdecimal():
                raise ValueError("CSV_EPOCH_INVALID")
            epoch = int(epoch_str)
            if (epoch <= 0 or (times and epoch <= times[-1])
                    or epoch > captured_epoch + 60):
                raise ValueError("CSV_EPOCH_ORDER_OR_FUTURE")
            prices = [float(row[key]) for key in ("open", "high", "low", "close")]
            op, hi, lo, cl = prices
            if (not all(math.isfinite(v) and v > 0 for v in prices)
                    or hi < max(op, cl) or lo > min(op, cl) or hi < lo):
                raise ValueError("CSV_OHLC_INVALID")
            for key in ("tick_volume", "spread", "real_volume"):
                value = row[key]
                if not value.isascii() or not value.isdecimal():
                    raise ValueError("CSV_VOLUME_OR_SPREAD_INVALID")
            times.append(epoch)
            if len(times) > count:
                raise ValueError("CSV_ROW_COUNT_EXCESS")
    except (OverflowError, TypeError, UnicodeError) as exc:
        raise ValueError("CSV_PARSE_EXCEPTION") from exc
    if len(times) != count:
        raise ValueError("CSV_ROW_COUNT_INCOMPLETE")
    try:
        first = datetime.fromtimestamp(times[0], timezone.utc).isoformat()
        last = datetime.fromtimestamp(times[-1], timezone.utc).isoformat()
    except (OverflowError, ValueError, OSError) as exc:
        raise ValueError("CSV_TIMESTAMP_OUT_OF_RANGE") from exc
    gaps = sum(y - x > period for x, y in zip(times, times[1:]))
    if (record.get("earliest_open_utc") != first
            or record.get("latest_open_utc") != last
            or type(record.get("larger_than_nominal_gaps_needing_calendar_review")) is not int
            or record["larger_than_nominal_gaps_needing_calendar_review"] != gaps):
        raise ValueError("MANIFEST_TIME_OR_GAP_METADATA_MISMATCH")
    return {"bars": count, "first_open_utc": first, "last_open_utc": last,
            "larger_than_nominal_intervals": gaps,
            "sha256_uncompressed_csv": checksum}


def audit_xauusd_closedbar_archive_lab(capture_directory: Any) -> dict[str, Any]:
    """Fail closed on missing, altered or incomplete archives; never write."""
    result = _base(capture_directory)
    problems = result["errors"]
    if not isinstance(capture_directory, Path):
        problems.append("CAPTURE_DIRECTORY_NOT_PATH")
        return result
    root = capture_directory
    if (not root.is_absolute() or root.is_symlink() or not root.is_dir()
            or root.parent.parts[-3:] != ("AtlasQuant", "LAB", "MT5_Snapshots")
            or not re.fullmatch(r"XAUUSD_\d{8}T\d{6}Z", root.name)):
        problems.append("CAPTURE_DIRECTORY_NOT_ISOLATED_XAUUSD_LAB")
        return result
    try:
        existing = {p.name for p in root.iterdir()}
    except OSError:
        problems.append("CAPTURE_DIRECTORY_UNREADABLE")
        return result
    required = {"xauusd_manifest.json"} | {
        f"XAUUSD_{label}_closedbar.csv.gz" for label, _, _ in REQUESTS}
    if existing != required:
        problems.append("ARCHIVE_FILE_SET_INCOMPLETE_OR_UNEXPECTED")
        return result
    manifest_path = root / "xauusd_manifest.json"
    if manifest_path.is_symlink():
        problems.append("MANIFEST_SYMLINK_FORBIDDEN")
        return result
    try:
        if manifest_path.stat().st_size > MAX_MANIFEST_BYTES:
            raise ValueError("MANIFEST_OVERSIZED")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError) as exc:
        problems.append("MANIFEST_UNREADABLE_OR_INVALID:" + str(exc)[:40])
        return result
    if not isinstance(manifest, dict):
        problems.append("MANIFEST_NOT_OBJECT")
        return result
    if (manifest.get("schema") != SCHEMA
            or manifest.get("symbol") != "XAUUSD"
            or manifest.get("canonical_id") != "METAL:XAUUSD"
            or manifest.get("trade_authorized") is not False
            or manifest.get("research_only") is not True
            or manifest.get("operational_bias") != "AGUARDAR"
            or manifest.get("broker_identity_independently_authenticated") is not False
            or manifest.get("historical_point_in_time_verified") is not False
            or manifest.get("candle_utc_independently_authenticated") is not False):
        problems.append("MANIFEST_SAFETY_OR_INSTRUMENT_SCHEMA_INVALID")
        return result
    captured = manifest.get("captured_at_utc_local_clock_claim")
    try:
        claim = datetime.fromisoformat(captured)
        if claim.tzinfo is None or claim.utcoffset().total_seconds() != 0:
            raise ValueError("CAPTURE_CLOCK_NOT_UTC")
        if root.name != "XAUUSD_" + claim.strftime("%Y%m%dT%H%M%SZ"):
            raise ValueError("CAPTURE_CLOCK_DIRECTORY_MISMATCH")
        captured_epoch = int(claim.timestamp())
    except (TypeError, ValueError, OverflowError, AttributeError) as exc:
        problems.append("MANIFEST_CAPTURE_CLOCK_INVALID:" + str(exc)[:40])
        return result
    records = manifest.get("records")
    if (not isinstance(records, list) or len(records) != len(REQUESTS)
            or any(not isinstance(rec, dict) for rec in records)):
        problems.append("MANIFEST_SERIES_COUNT_INVALID")
        return result
    labels = [rec.get("timeframe") for rec in records]
    expected_labels = {label for label, _, _ in REQUESTS}
    if (not all(isinstance(label, str) for label in labels)
            or len(set(labels)) != len(REQUESTS)
            or set(labels) != expected_labels):
        problems.append("MANIFEST_DUPLICATE_OR_UNEXPECTED_TIMEFRAME")
        return result
    by_label = {rec["timeframe"]: rec for rec in records}
    for label, count, period in REQUESTS:
        try:
            verified = _check_series(root, by_label[label], label, count,
                                     period, captured_epoch)
        except (OSError, ValueError, TypeError, IndexError, KeyError) as exc:
            problems.append(f"{label}:{exc}")
            continue
        result["verified_series"] += 1
        result["verified_bars"] += verified["bars"]
        result["timeframes"][label] = verified
    if not problems and result["verified_bars"] == 3700:
        result["status"] = "LOCAL_XAUUSD_ARCHIVE_INTEGRITY_PASS_UNATTESTED"
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Offline, read-only XAUUSD MT5 archive audit")
    parser.add_argument("--capture-directory", type=Path, required=True)
    args = parser.parse_args()
    result = audit_xauusd_closedbar_archive_lab(args.capture_directory)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["status"].startswith("LOCAL_XAUUSD_ARCHIVE_INTEGRITY_PASS") else 2


if __name__ == "__main__":
    raise SystemExit(main())
