"""AtlasQuant FX28: explicit one-shot write-once MT5 M15 archive, LAB ONLY.

This module does nothing on import. Its command-line entrypoint must be run
manually with a previously open MT5 terminal. Only initialize, terminal_info,
symbol_info, copy_rates_range, and shutdown are used. No account, orders,
symbol_select, credentials, or recurring worker. These are local historical
claims, NOT independent broker/source or point-in-time evidence.

Preserve absent candles as actual GAPS, never fill/retime/omit their pair.
The frozen campaign timestamps are never changed.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from io import StringIO
import json
import os
from pathlib import Path
from typing import Any, Callable

from atlasquant_mt5_xauusd_closedbar_capture_lab import _terminal_path_ok
from atlasquant_trader_ppi_mt5_m15_capture_lab import (
    _integer, _price, _symbol_spec_for_capture,
)
from atlasquant_trader_ppi_usd_fx_forward_reaction_lab import FIELDS

SCHEMA = "ATLASQUANT_FX28_NY17_M15_WRITEONCE_HISTORY_LAB_V1"
PAIRS = (
    "EURUSD", "GBPUSD", "AUDUSD", "NZDUSD", "USDJPY", "USDCHF", "USDCAD",
    "EURGBP", "EURJPY", "EURCHF", "EURCAD", "EURAUD", "EURNZD",
    "GBPJPY", "GBPCHF", "GBPCAD", "GBPAUD", "GBPNZD",
    "AUDJPY", "AUDCHF", "AUDCAD", "AUDNZD",
    "NZDJPY", "NZDCHF", "NZDCAD", "CADJPY", "CADCHF", "CHFJPY",
)
# Rehearsals are historical. The prospective entries must never be accessed
# before their CLOSED window; the first 15-min snapshot is not a D1/W1 label.
WINDOWS = {
    "REHEARSAL_SUN_20261108_D1": ("2026-11-08T22:00:00+00:00",
                                   "2026-11-09T22:00:00+00:00"),
    "REHEARSAL_TUE_20261110_D1": ("2026-11-10T22:00:00+00:00",
                                   "2026-11-11T22:00:00+00:00"),
    "CAMPAIGN_FIRST_M15_20261115": ("2026-11-15T22:00:00+00:00",
                                     "2026-11-15T22:15:00+00:00"),
    "CAMPAIGN_FIRST_D1_20261115": ("2026-11-15T22:00:00+00:00",
                                    "2026-11-16T22:00:00+00:00"),
    "CAMPAIGN_FIRST_W1_20261115": ("2026-11-15T22:00:00+00:00",
                                    "2026-11-20T22:00:00+00:00"),
}
assert len(PAIRS) == len(set(PAIRS)) == 28
assert all((datetime.fromisoformat(end) - datetime.fromisoformat(start))
           in (timedelta(minutes=15), timedelta(days=1), timedelta(days=5))
           for start, end in WINDOWS.values())


def _base(reason: str, *, window: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_FX28_M15_CAPTURE_BLOCKED",
        "reason": reason, "window": window, "archive_dir": None,
        "expected_symbols": 28, "captured_symbols": 0,
        "expected_m15_per_symbol": None, "captured_m15_total": 0,
        "missing_m15_total": None, "fully_covered_symbols": None,
        "manifest_sha256": None, "sha256_by_symbol": None,
        "source_kind": "MT5_HISTORY_RETRIEVED_AT_CAPTURE_TIME_UNATTESTED",
        "pre_event_forecasts_authenticated": False,
        "historical_source_first_seen_attested": False,
        "broker_price_identity_independently_authenticated": False,
        "archive_hash_only_checks_local_integrity": True,
        "no_imputation_no_clock_shift": True,
        "trade_authorized": False, "operational_bias": "AGUARDAR",
        "publishable": False, "worker_enabled": False, "scheduled": False,
    }


def _utc(value: Any) -> datetime | None:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        return None
    return value.astimezone(timezone.utc)


def _serialize_rows(rates: Any, *, expected: tuple[int, ...],
                    digits: int) -> tuple[bytes, list[int], int]:
    """Accept only strictly ordered, on-grid real bars; never synthesize gaps."""
    if rates is None:
        rates = ()
    if len(rates) > len(expected):
        raise ValueError("TOO_MANY_M15_CANDLES")
    expected_set = set(expected)
    raw = StringIO(newline="")
    writer = csv.writer(raw, lineterminator="\n")
    writer.writerow(FIELDS)
    seen: list[int] = []
    for bar in rates:
        epoch = _integer(bar["time"], strictly_positive=True)
        if epoch not in expected_set or (seen and epoch <= seen[-1]):
            raise ValueError("M15_DUPLICATE_OUTSIDE_GRID_OR_UNSORTED")
        prices = [_price(bar[k], quote_digits=digits) for k in
                  ("open", "high", "low", "close")]
        op, hi, lo, cl = (p[0] for p in prices)
        if not lo <= min(op, cl) <= max(op, cl) <= hi:
            raise ValueError("OHLC_INCONSISTENT")
        amounts = [_integer(bar[k], strictly_positive=(k == "tick_volume"))
                   for k in ("tick_volume", "spread", "real_volume")]
        writer.writerow((epoch, *(p[1] for p in prices), *amounts))
        seen.append(epoch)
    missing = sorted(expected_set.difference(seen))
    return raw.getvalue().encode("utf-8"), missing, len(seen)


def collect_window_lab(api: Any, *, window: str, terminal_path: str,
                       output_root: Path,
                       clock: Callable[[], datetime]) -> dict[str, Any]:
    out = _base("INVALID_WINDOW_OR_TERMINAL", window=window)
    if (window not in WINDOWS or not _terminal_path_ok(terminal_path)
            or not isinstance(output_root, Path) or not output_root.is_absolute()):
        return out
    try:
        now = _utc(clock())
    except (TypeError, ValueError, OverflowError, RuntimeError):
        now = None
    if now is None:
        out["reason"] = "INVALID_CAPTURE_CLOCK"
        return out
    start_s, end_s = WINDOWS[window]
    start, end = datetime.fromisoformat(start_s), datetime.fromisoformat(end_s)
    if now < end:
        out["reason"] = "FROZEN_WINDOW_NOT_YET_CLOSED_NO_MT5_IO"
        return out
    expected = tuple(range(int(start.timestamp()), int(end.timestamp()), 900))
    out["expected_m15_per_symbol"] = len(expected)
    path = output_root / (window + "_" + now.strftime("%Y%m%dT%H%M%S%fZ"))
    if path.exists() or path.is_symlink():
        out["reason"] = "WRITE_ONCE_DIRECTORY_ALREADY_EXISTS"
        return out
    connected = False
    pending: dict[str, bytes] = {}
    records: dict[str, dict[str, Any]] = {}
    problem: str | None = None
    try:
        connected = api.initialize(path=terminal_path, timeout=12000) is True
        if not connected:
            problem = "MT5_NOT_CONNECTED"
        else:
            terminal = api.terminal_info()
            if terminal is None or getattr(terminal, "connected", None) is not True:
                problem = "TERMINAL_NOT_CONNECTED"
            else:
                for symbol in PAIRS:
                    info = api.symbol_info(symbol)
                    if info is None or type(getattr(info, "visible", None)) is not bool:
                        problem = "SYMBOL_METADATA_MISSING_" + symbol
                        break
                    visible = info.visible
                    spec = _symbol_spec_for_capture(info, symbol)
                    if spec is None:
                        problem = "SYMBOL_CURRENCY_OR_TICK_INVALID_" + symbol
                        break
                    rates = api.copy_rates_range(
                        symbol, api.TIMEFRAME_M15, start, end - timedelta(minutes=15))
                    info_after = api.symbol_info(symbol)
                    if (info_after is None or
                            type(getattr(info_after, "visible", None)) is not bool or
                            info_after.visible != visible):
                        problem = "SYMBOL_VISIBILITY_CHANGED_OR_UNKNOWN_" + symbol
                        break
                    raw, missing, count = _serialize_rows(
                        rates, expected=expected, digits=spec["digits_claim"])
                    pending[symbol] = raw
                    records[symbol] = {
                        "sha256": sha256(raw).hexdigest(),
                        "m15_returned": count, "m15_missing": len(missing),
                        "missing_open_epochs_utc": missing,
                        "first_expected_open_present": expected[0] not in missing,
                        "last_expected_open_present": expected[-1] not in missing,
                        "market_watch_visible_claim": visible,
                        "price_digits_claim": spec["digits_claim"],
                        "mt5_no_bars_returned": rates is None,
                    }
    except (AttributeError, TypeError, ValueError, KeyError, OSError,
            OverflowError, RuntimeError) as exc:
        problem = "READONLY_MT5_OR_CANDLE_CHECK_FAILED_" + type(exc).__name__
    finally:
        if connected:
            try:
                api.shutdown()
            except (AttributeError, OSError, TypeError, RuntimeError):
                problem = "MT5_SHUTDOWN_FAILED"
    if problem is not None or len(pending) != len(PAIRS):
        out["reason"] = problem or "INCOMPLETE_COHORT"
        return out

    manifest = {
        "schema": SCHEMA, "window": window, "window_start_utc": start_s,
        "window_end_exclusive_utc": end_s,
        "retrieved_at_utc_local_clock_claim": now.isoformat(),
        "expected_symbols_ordered": list(PAIRS),
        "expected_m15_per_symbol": len(expected),
        "source_kind": out["source_kind"],
        "source_first_seen_independently_attested": False,
        "broker_identity_independently_authenticated": False,
        "prediction_witness_precommitted": False,
        "no_missing_candle_interpolation": True,
        "files": records,
        "research_only": True, "trade_authorized": False,
    }
    try:
        output_root.mkdir(parents=True, exist_ok=True)
        path.mkdir(exist_ok=False)
        for symbol, raw in pending.items():
            file = path / (symbol + "_M15.csv")
            with file.open("xb") as handle:
                handle.write(raw)
            if sha256(file.read_bytes()).hexdigest() != records[symbol]["sha256"]:
                out["reason"] = "READBACK_SHA256_MISMATCH_INCOMPLETE_RUN"
                return out
        manifest_bytes = (json.dumps(manifest, sort_keys=True, indent=2) + "\n").encode("utf-8")
        with (path / "manifest.json").open("xb") as handle:
            handle.write(manifest_bytes)
    except OSError:
        out["reason"] = "ARCHIVE_WRITE_FAILED_INCOMPLETE_RUN"
        return out
    missing_total = sum(r["m15_missing"] for r in records.values())
    complete = sum(r["m15_missing"] == 0 for r in records.values())
    out.update({
        "state": ("LAB_FX28_M15_ARCHIVE_COMPLETE_CLAIM_ONLY_NO_GO"
                  if complete == 28 else "LAB_FX28_M15_ARCHIVE_WITH_GAPS_NO_GO"),
        "reason": "LOCAL_M15_BYTES_SEALED_HASH_ONLY_NO_BROKER_PIT_ATTESTATION",
        "archive_dir": str(path),
        "captured_symbols": 28, "captured_m15_total":
            sum(r["m15_returned"] for r in records.values()),
        "missing_m15_total": missing_total,
        "fully_covered_symbols": complete,
        "manifest_sha256": sha256(manifest_bytes).hexdigest(),
        "sha256_by_symbol": {s: records[s]["sha256"] for s in PAIRS},
    })
    return out


def verify_archive_lab(path: Path) -> dict[str, Any]:
    """Offline independent read-back: every CSV digest, manifest and grid."""
    if not path.is_dir() or path.is_symlink():
        raise ValueError("INVALID_ARCHIVE_DIRECTORY")
    manifest_path = path / "manifest.json"
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise ValueError("MISSING_MANIFEST")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    window = manifest.get("window")
    if (manifest.get("schema") != SCHEMA or window not in WINDOWS
            or manifest.get("expected_symbols_ordered") != list(PAIRS)
            or set(manifest.get("files", {})) != set(PAIRS)):
        raise ValueError("INVALID_COHORT_OR_SCHEMA")
    start_s, end_s = WINDOWS[window]
    if (manifest.get("window_start_utc") != start_s
            or manifest.get("window_end_exclusive_utc") != end_s
            or manifest.get("prediction_witness_precommitted") is not False
            or manifest.get("broker_identity_independently_authenticated") is not False
            or manifest.get("source_first_seen_independently_attested") is not False):
        raise ValueError("WINDOW_OR_EVIDENCE_STATUS_MISMATCH")
    expected = set(range(
        int(datetime.fromisoformat(start_s).timestamp()),
        int(datetime.fromisoformat(end_s).timestamp()), 900))
    summaries = {}
    for symbol in PAIRS:
        file = path / (symbol + "_M15.csv")
        if file.is_symlink() or not file.is_file():
            raise ValueError("MISSING_CSV_" + symbol)
        raw = file.read_bytes()
        row = manifest["files"][symbol]
        if sha256(raw).hexdigest() != row.get("sha256"):
            raise ValueError("CSV_SHA256_MISMATCH_" + symbol)
        lines = list(csv.DictReader(StringIO(raw.decode("utf-8")), dialect="excel"))
        times = [int(line["time_utc_epoch"]) for line in lines]
        if times != sorted(set(times)) or not set(times) <= expected:
            raise ValueError("CSV_EPOCH_INVALID_" + symbol)
        missing = sorted(expected.difference(times))
        if (len(times) != row["m15_returned"] or
                len(missing) != row["m15_missing"] or
                missing != row["missing_open_epochs_utc"]):
            raise ValueError("MANIFEST_CSV_GAP_DISAGREEMENT_" + symbol)
        summaries[symbol] = len(missing)
    return {
        "state": "LAB_FX28_M15_HASHES_AND_GAPS_VERIFIED_CLAIM_ONLY_NO_GO",
        "window": window, "symbol_hashes_verified": 28,
        "missing_m15_total": sum(summaries.values()),
        "fully_covered_symbols": sum(v == 0 for v in summaries.values()),
        "manifest_sha256": sha256(manifest_path.read_bytes()).hexdigest(),
        "source_first_seen_attested": False,
        "forecast_witness_authenticated": False,
        "trade_authorized": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--window", choices=tuple(WINDOWS))
    parser.add_argument("--verify", type=Path)
    parser.add_argument("--terminal-path")
    args = parser.parse_args()
    if bool(args.window) == bool(args.verify):
        parser.error("select exactly one: --window OR --verify")
    if args.verify is not None:
        try:
            result = verify_archive_lab(args.verify)
        except (ValueError, OSError, KeyError, TypeError, json.JSONDecodeError) as exc:
            print(json.dumps({"state": "LAB_ARCHIVE_VERIFICATION_BLOCKED",
                              "reason": type(exc).__name__ + ":" + str(exc)}))
            return 2
    else:
        try:
            import MetaTrader5 as mt5
        except ImportError:
            print(json.dumps({"state": "MT5_PYTHON_PACKAGE_NOT_INSTALLED"}))
            return 2
        root = os.environ.get("LOCALAPPDATA")
        if not root:
            return 2
        result = collect_window_lab(
            mt5, window=args.window, terminal_path=args.terminal_path or "",
            output_root=Path(root) / "AtlasQuant" / "LAB" / "FX28_NY17_M15",
            clock=lambda: datetime.now(timezone.utc))
    print(json.dumps(result, sort_keys=True), flush=True)
    return 0 if result["state"] in (
        "LAB_FX28_M15_ARCHIVE_COMPLETE_CLAIM_ONLY_NO_GO",
        "LAB_FX28_M15_ARCHIVE_WITH_GAPS_NO_GO",
        "LAB_FX28_M15_HASHES_AND_GAPS_VERIFIED_CLAIM_ONLY_NO_GO") else 2


if __name__ == "__main__":
    raise SystemExit(main())
