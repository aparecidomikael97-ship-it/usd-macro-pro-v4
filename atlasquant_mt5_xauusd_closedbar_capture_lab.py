"""Opt-in, read-only XAUUSD MT5 capture into a NEW local LAB directory.

No account, position, order, symbol_select, login or broker-setting calls.
Only a human invoking the CLI on the authorized Windows PC can use MT5.
Importing this module does not import MT5 or touch the terminal/filesystem.
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
from pathlib import Path, PureWindowsPath
from typing import Any, Callable

SCHEMA = "ATLASQUANT_MT5_XAUUSD_CLOSED_BAR_CAPTURE_LAB_V1"
SYMBOL = "XAUUSD"
REQUESTS = (("M15", 3000, 900), ("D1", 500, 86400), ("W1", 200, 604800))
FIELDS = ("time_utc_epoch", "open", "high", "low", "close",
          "tick_volume", "spread", "real_volume")


def _stamp(at: datetime) -> str:
    return at.astimezone(timezone.utc).isoformat()


def _base(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_XAUUSD_CAPTURE_BLOCKED",
        "reason": reason, "symbol": SYMBOL,
        "canonical_id": "METAL:XAUUSD", "forex_28_unchanged": True,
        "series_count": 0, "verified_local_bars": 0,
        "records": [], "directory": None, "local_files_written": 0,
        "mt5_account_information_accessed": False,
        "orders_or_positions_accessed": False,
        "symbol_visibility_changed": False,
        "broker_identity_independently_authenticated": False,
        "candle_server_utc_independently_authenticated": False,
        "historical_point_in_time_verified": False,
        "news_and_geopolitics_authenticated": False,
        "gold_bias": None, "calibrated_probability": None,
        "validated_accuracy": None, "operational_bias": "AGUARDAR",
        "can_feed_live_radar": False, "publishable": False,
        "trade_authorized": False, "new_cost_brl": 0,
        "http_requests": 0,
    }


def _terminal_path_ok(value: Any) -> bool:
    if not isinstance(value, str) or not value:
        return False
    path = PureWindowsPath(value)
    return (len(path.drive) == 2 and path.drive[1] == ":"
            and path.is_absolute() and path.name.lower() == "terminal64.exe"
            and ".." not in path.parts)


def _root_ok(root: Any) -> bool:
    if not isinstance(root, Path):
        return False
    return (root.is_absolute() and root.parts[-3:] ==
            ("AtlasQuant", "LAB", "MT5_Snapshots")
            and ".." not in root.parts)


def _rates_to_csv(rates: Any, *, expected: int, step_seconds: int,
                  observed_at_utc: datetime) -> tuple[bytes, dict[str, Any]] | str:
    if rates is None or len(rates) != expected:
        return "CLOSED_BAR_COUNT_INCOMPLETE"
    writer_output = StringIO(newline="")
    writer = csv.writer(writer_output, lineterminator="\n")
    writer.writerow(FIELDS)
    stamps: list[int] = []
    try:
        for bar in rates:
            epoch = bar["time"]
            if isinstance(epoch, bool) or int(epoch) != epoch or epoch <= 0:
                return "INVALID_BAR_EPOCH"
            epoch = int(epoch)
            if stamps and epoch <= stamps[-1]:
                return "BAR_TIME_DUPLICATE_OR_OUT_OF_ORDER"
            if epoch > int(observed_at_utc.timestamp()) + 60:
                return "BAR_OPEN_REPORTED_AFTER_CAPTURE_CLOCK"
            prices = [float(bar[key]) for key in ("open", "high", "low", "close")]
            op, hi, lo, cl = prices
            if (not all(math.isfinite(v) and v > 0 for v in prices)
                    or hi < max(op, cl) or lo > min(op, cl) or hi < lo):
                return "BAR_OHLC_INCONSISTENT"
            volume = [bar[key] for key in ("tick_volume", "spread", "real_volume")]
            if any(isinstance(v, bool) or int(v) != v or v < 0 for v in volume):
                return "BAR_VOLUME_OR_SPREAD_INVALID"
            stamps.append(epoch)
            writer.writerow((epoch, *(repr(v) for v in prices),
                             *(int(v) for v in volume)))
    except (KeyError, IndexError, TypeError, ValueError, OverflowError):
        return "MT5_BAR_FIELDS_INVALID"
    raw = writer_output.getvalue().encode("utf-8")
    gaps = sum(b - a > step_seconds for a, b in zip(stamps, stamps[1:]))
    return raw, {
        "returned": len(stamps), "bar_position_start": 1,
        "earliest_open_utc": datetime.fromtimestamp(stamps[0], timezone.utc).isoformat(),
        "latest_open_utc": datetime.fromtimestamp(stamps[-1], timezone.utc).isoformat(),
        "larger_than_nominal_gaps_needing_calendar_review": gaps,
        "sha256_uncompressed_csv": sha256(raw).hexdigest(),
        "validation_errors": [],
    }


def collect_xauusd_closedbar_snapshot_lab(
    api: Any, *, terminal_path: Any, output_root: Any,
    clock: Callable[[], datetime],
) -> dict[str, Any]:
    """Use only symbol_info + copy_rates_from_pos(start_pos=1); write later.

    All three series must pass before any directory is created. A previously
    existing capture directory is NEVER overwritten. Historical gaps are
    counted for separate calendar review, not imputed or classified as errors.
    """
    out = _base("INVALID_TERMINAL_PATH_OR_LAB_OUTPUT_ROOT")
    if not _terminal_path_ok(terminal_path) or not _root_ok(output_root):
        return out
    now = clock()
    if (not isinstance(now, datetime) or now.tzinfo is None
            or now.utcoffset() is None or now.microsecond != 0):
        out["reason"] = "INVALID_COLLECTOR_WALL_CLOCK"
        return out
    now = now.astimezone(timezone.utc)
    run_dir = output_root / ("XAUUSD_" + now.strftime("%Y%m%dT%H%M%SZ"))
    if run_dir.exists():
        out["reason"] = "CAPTURE_RUN_DIRECTORY_ALREADY_EXISTS_NO_OVERWRITE"
        return out
    try:
        connected = api.initialize(path=terminal_path, timeout=10000)
    except (AttributeError, OSError, TypeError, ValueError, RuntimeError):
        out["reason"] = "MT5_INITIALIZATION_EXCEPTION"
        return out
    if not connected:
        out["reason"] = "MT5_INITIALIZATION_FAILED"
        return out
    pending: list[tuple[str, bytes, dict[str, Any]]] = []
    try:
        terminal = api.terminal_info()
        if terminal is None or terminal.connected is not True:
            out["reason"] = "MT5_TERMINAL_NOT_CONNECTED"
            return out
        info = api.symbol_info(SYMBOL)
        if info is None or info.visible is not True:
            out["reason"] = "XAUUSD_NOT_VISIBLE_NO_AUTO_SELECT"
            return out
        for label, count, step in REQUESTS:
            timeframe = getattr(api, "TIMEFRAME_" + label)
            bars = api.copy_rates_from_pos(SYMBOL, timeframe, 1, count)
            valid = _rates_to_csv(
                bars, expected=count, step_seconds=step, observed_at_utc=now)
            if isinstance(valid, str):
                out["reason"] = label + ":" + valid
                return out
            raw, metadata = valid
            pending.append((label, raw, metadata))
    except (AttributeError, OSError, TypeError, ValueError, RuntimeError):
        out["reason"] = "MT5_READONLY_QUERY_EXCEPTION"
        return out
    finally:
        try:
            api.shutdown()
        except (AttributeError, OSError, TypeError, RuntimeError):
            out["reason"] = "MT5_SHUTDOWN_FAILED_NO_ARCHIVE"
            return out

    # Local files are written only after successful read-only validation of all
    # 3 requested timeframes. No programmatically created trades or alerts.
    try:
        run_dir.mkdir(parents=True, exist_ok=False)
        records: list[dict[str, Any]] = []
        for label, raw, metadata in pending:
            filename = f"XAUUSD_{label}_closedbar.csv.gz"
            buffer = BytesIO()
            with gzip.GzipFile(fileobj=buffer, mode="wb", filename="",
                               compresslevel=6, mtime=0) as zipped:
                zipped.write(raw)
            compressed = buffer.getvalue()
            with (run_dir / filename).open("xb") as handle:
                handle.write(compressed)
            out["local_files_written"] += 1
            if sha256(gzip.decompress((run_dir / filename).read_bytes())).hexdigest() != metadata["sha256_uncompressed_csv"]:
                out["reason"] = "LOCAL_ARCHIVE_READBACK_HASH_MISMATCH"
                return out
            records.append({"symbol": SYMBOL, "timeframe": label,
                            "requested": next(n for t, n, _ in REQUESTS if t == label),
                            "snapshot_file": filename, **metadata})
        manifest = {
            "schema": SCHEMA, "research_only": True,
            "trade_authorized": False, "operational_bias": "AGUARDAR",
            "broker_identity_independently_authenticated": False,
            "historical_point_in_time_verified": False,
            "candle_utc_independently_authenticated": False,
            "captured_at_utc_local_clock_claim": _stamp(now),
            "symbol": SYMBOL, "canonical_id": "METAL:XAUUSD",
            "records": records,
        }
        with (run_dir / "xauusd_manifest.json").open("x", encoding="utf-8") as handle:
            json.dump(manifest, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        out["local_files_written"] += 1
    except (OSError, EOFError, ValueError):
        out["reason"] = "LOCAL_CAPTURE_WRITE_FAILED_LEFT_INCOMPLETE_RUN_UNTOUCHED"
        return out
    out.update({
        "state": "LAB_XAUUSD_LOCAL_3700_CLOSED_BAR_CANDIDATE_UNATTESTED",
        "reason": "LOCAL_CANDLE_INTEGRITY_ONLY_NO_BROKER_OR_POINT_IN_TIME_ATTESTATION",
        "series_count": 3, "verified_local_bars": sum(r["returned"] for r in records),
        "records": records, "directory": str(run_dir),
    })
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="XAUUSD local read-only MT5 LAB export")
    parser.add_argument("--terminal-path", required=True,
                        help="Explicit path to already running terminal64.exe")
    args = parser.parse_args()
    local_data = os.environ.get("LOCALAPPDATA")
    if not local_data:
        print("BLOCKED: Windows LOCALAPPDATA missing")
        return 2
    try:
        import MetaTrader5 as mt5  # deferred: importing this module is safe
    except ImportError:
        print("BLOCKED: MetaTrader5 Python module unavailable")
        return 2
    output_root = (Path(local_data) / "AtlasQuant" / "LAB" / "MT5_Snapshots")
    result = collect_xauusd_closedbar_snapshot_lab(
        mt5, terminal_path=args.terminal_path, output_root=output_root,
        clock=lambda: datetime.now(timezone.utc).replace(microsecond=0))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["series_count"] == 3 else 2


if __name__ == "__main__":
    raise SystemExit(main())
