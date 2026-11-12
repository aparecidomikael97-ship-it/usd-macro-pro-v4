"""Read-only AM12 M15 archive loader for the 28-cross NY17 LAB batch audit.

This module can read local files ONLY when explicitly invoked with a snapshot
root. It neither connects to MT5 nor writes reports/files or uses network.
Every manifest and series must be present and safe; bad inventory or bytes
fail closed. Seven manifest files describe 84 series (M15/D1/W1), but ONLY
the 28 M15 CSV.gz bytes are read/locally SHA-checked by the downstream gate.
All other manifest records are inventory metadata, NOT audited D1/W1 bytes.

Example (in an authorized terminal, from the repository):
  python -B atlasquant_trader_mt5_28fx_archive_reader_lab.py \\
    --root "<snapshot directory>" --horizon D1 \\
    --start-utc 2026-11-08T22:00:00+00:00 \\
    --end-utc 2026-11-09T22:00:00+00:00 \\
    --as-of-utc 2026-11-12T12:00:00+00:00

This is never evidence of predictive accuracy, broker provenance, or a trade.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from atlasquant_instrument_registry import FX_28
from atlasquant_fx_universe import OFFICIAL_PAIRS
from atlasquant_trader_mt5_closedbar_outcome_lab import MT5_SCHEMA
from atlasquant_trader_mt5_forward_label_gate_lab import EXPECTED, MAX_GZIP_BYTES
from atlasquant_trader_mt5_28fx_m15_batch_audit_lab import (
    inspect_28fx_m15_archive_batch_lab,
)

SCHEMA = "ATLASQUANT_TRADER_MT5_AM12_READONLY_28FX_RUNNER_LAB_V1"
MAX_MANIFEST_BYTES = 200_000
TIMEFRAMES = frozenset(("M15", "D1", "W1"))


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "state": "LAB_AM12_READONLY_28FX_RUNNER_BLOCKED",
        "reason": reason,
        "manifest_files_seen": 0,
        "inventory_series_seen": 0,
        "m15_archive_files_read": 0,
        "batch_result": None,
        "all_28_m15_archive_bytes_self_consistent": False,
        "all_84_series_original_bytes_verified": False,
        "broker_provenance_authenticated": False,
        "broker_calendar_verified": False,
        "price_vintage_at_bias_decision_verified": False,
        "precommitted_forecast_proven": False,
        "validated_directional_accuracy": None,
        "calibrated_probability": None,
        "operational_bias": "AGUARDAR",
        "trade_authorized": False, "publishable": False,
        "live_alert_allowed": False, "worker_enabled": False,
        "scheduler_enabled": False, "output_files_written": 0,
        "mt5_connections": 0, "http_requests": 0,
        "new_cost_brl": 0, "research_only": True,
    }


def _parse_utc(value: Any) -> datetime | None:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        return None
    return value.astimezone(timezone.utc)


def _iso_utc(text: Any) -> datetime | None:
    if not isinstance(text, str) or not 1 <= len(text) <= 60:
        return None
    try:
        return _parse_utc(datetime.fromisoformat(text.replace("Z", "+00:00")))
    except ValueError:
        return None


def _json_no_duplicate_keys(raw: bytes) -> Any:
    def unique(pairs):
        out = {}
        for name, value in pairs:
            if name in out:
                raise ValueError("DUPLICATE_JSON_KEY")
            out[name] = value
        return out
    return json.loads(
        raw.decode("utf-8", "strict"),
        object_pairs_hook=unique,
        parse_constant=lambda _: (_ for _ in ()).throw(ValueError("NONFINITE_JSON")),
    )


def inspect_local_am12_28fx_lab(
    *, root: Any, horizon: Any,
    start_at_utc: Any, end_at_utc: Any, evaluated_at_utc: Any,
) -> dict[str, Any]:
    """Read source files once, return only safe documentary metadata.

    No partial dataset is accepted as 28FX coverage. Source-manifest SHA
    matching is SELF-CONSISTENCY, not externally authenticated provenance.
    """
    out = _blocked("INVALID_ROOT_OR_EVALUATION_CLOCK")
    start, end, evaluated = (
        _parse_utc(start_at_utc), _parse_utc(end_at_utc),
        _parse_utc(evaluated_at_utc),
    )
    if (not isinstance(root, (str, Path)) or not isinstance(horizon, str)
            or horizon not in ("D1", "W1")
            or any(x is None for x in (start, end, evaluated))
            or not start < end <= evaluated):
        return out
    directory = Path(root)
    if not directory.is_dir() or directory.is_symlink():
        out["reason"] = "ROOT_MISSING_NOT_DIRECTORY_OR_SYMLINK"
        return out
    manifests = sorted(directory.glob("batch_??_manifest.json"))
    out["manifest_files_seen"] = len(manifests)
    if len(manifests) != 7:
        out["reason"] = "SEVEN_BATCH_MANIFESTS_REQUIRED"
        return out

    records: dict[tuple[str, str], dict[str, Any]] = {}
    try:
        for manifest_path in manifests:
            if (not manifest_path.is_file() or manifest_path.is_symlink()
                    or manifest_path.stat().st_size > MAX_MANIFEST_BYTES):
                raise ValueError("UNSAFE_OR_OVERSIZED_MANIFEST")
            document = _json_no_duplicate_keys(manifest_path.read_bytes())
            if (not isinstance(document, dict)
                    or document.get("schema") != MT5_SCHEMA
                    or document.get("trade_authorized") is not False
                    or document.get("research_only") is not True
                    or document.get("prediction_available") is not False
                    or document.get("broker_identity_independently_verified") is not False
                    or document.get("historical_point_in_time_verified") is not False
                    or not isinstance(document.get("records"), list)):
                raise ValueError("MANIFEST_SCHEMA_OR_PROVENANCE_INVALID")
            for record in document["records"]:
                if not isinstance(record, dict):
                    raise ValueError("MALFORMED_SERIES_RECORD")
                symbol, frame = record.get("symbol"), record.get("timeframe")
                if symbol not in FX_28 or frame not in TIMEFRAMES:
                    raise ValueError("UNSUPPORTED_SERIES_IN_MANIFEST")
                key = symbol, frame
                if key in records:
                    raise ValueError("DUPLICATE_SERIES_ACROSS_MANIFESTS")
                if (record.get("snapshot_file") != f"{symbol}_{frame}_closedbar.csv.gz"
                        or type(record.get("requested")) is not int
                        or record["requested"] != EXPECTED[frame]
                        or type(record.get("returned")) is not int
                        or record["returned"] != EXPECTED[frame]
                        or type(record.get("bar_position_start")) is not int
                        or record["bar_position_start"] != 1
                        or record.get("validation_errors") != []):
                    raise ValueError("SERIES_RECORD_INCOMPLETE_OR_INVALID")
                records[key] = record
        out["inventory_series_seen"] = len(records)
        if (len(records) != 84
                or set(records) != {(sym, frame) for sym in FX_28 for frame in TIMEFRAMES}):
            raise ValueError("INCOMPLETE_84_SERIES_INVENTORY")

        snapshots = {}
        for pair in OFFICIAL_PAIRS:
            symbol = pair.replace("/", "")
            record = records[symbol, "M15"]
            filename = f"{symbol}_M15_closedbar.csv.gz"
            candidate = directory / filename
            if (not candidate.is_file() or candidate.is_symlink()
                    or not 0 < candidate.stat().st_size <= MAX_GZIP_BYTES):
                raise ValueError("M15_ARCHIVE_MISSING_SYMLINK_OR_OVERSIZED")
            captured = _iso_utc(record.get("observed_at_utc"))
            if captured is None or captured > evaluated:
                raise ValueError("M15_MANIFEST_CAPTURE_CLOCK_INVALID_OR_FUTURE")
            snapshots[pair] = {
                "manifest_record": record,
                "compressed_csv_gz": candidate.read_bytes(),
                "archive_captured_at_utc": captured,
            }
            out["m15_archive_files_read"] += 1

        result = inspect_28fx_m15_archive_batch_lab(
            snapshots_by_pair=snapshots,
            horizon=horizon, start_at_utc=start, end_at_utc=end,
            evaluated_at_utc=evaluated,
        )
    except (OSError, UnicodeError, ValueError, TypeError, OverflowError,
            json.JSONDecodeError) as exc:
        out["reason"] = (str(exc) if isinstance(exc, ValueError)
                         else "MANIFEST_OR_ARCHIVE_READ_FAILED")
        return out

    out["batch_result"] = result
    out["all_28_m15_archive_bytes_self_consistent"] = (
        result["all_28_local_archive_window_checks_passed"]
    )
    out["state"] = ("LAB_AM12_LOCAL_M15_WINDOW_CHECKS_ONLY_NO_GO"
                    if out["all_28_m15_archive_bytes_self_consistent"]
                    else "LAB_AM12_LOCAL_M15_INCOMPLETE_OR_GAPS_NO_GO")
    out["reason"] = ("M15_MANIFEST_SELF_CONSISTENCY_NOT_BROKER_AUTHENTICATION"
                     if out["all_28_m15_archive_bytes_self_consistent"]
                     else "M15_ARCHIVE_OR_NY17_WINDOW_REQUIRES_REVIEW")
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True,
                        help="Local AM12 snapshot directory (READ-ONLY)")
    parser.add_argument("--horizon", choices=("D1", "W1"), required=True)
    parser.add_argument("--start-utc", required=True)
    parser.add_argument("--end-utc", required=True)
    parser.add_argument("--as-of-utc", required=True)
    args = parser.parse_args(argv)
    result = inspect_local_am12_28fx_lab(
        root=args.root, horizon=args.horizon,
        start_at_utc=_iso_utc(args.start_utc),
        end_at_utc=_iso_utc(args.end_utc),
        evaluated_at_utc=_iso_utc(args.as_of_utc),
    )
    # Print a reproducible summary to stdout; NEVER create report files.
    print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
    return 0 if result["state"] == "LAB_AM12_LOCAL_M15_WINDOW_CHECKS_ONLY_NO_GO" else 2


if __name__ == "__main__":
    raise SystemExit(main())
