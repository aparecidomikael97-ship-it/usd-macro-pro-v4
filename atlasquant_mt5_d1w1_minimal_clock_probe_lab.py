"""AtlasQuant LAB: minimal MT5 D1/W1 clock probe; read only, no orders.

Only EURUSD/GBPNZD, D1/W1, and *closed-bar positions* 1..N. No account_info,
positions, trades, symbol_select, login, platform changes, or historical bulk
export. Never infer broker identity, an authenticated market session, live bias,
or directional accuracy from the terminal's timestamp conventions.

Importing this module does not import MetaTrader5 or connect to a terminal.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from numbers import Integral
from pathlib import Path
from typing import Any, Callable
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

SCHEMA = "ATLASQUANT_MT5_MINIMAL_D1W1_CLOCK_PROBE_LAB_V1"
SYMBOLS = ("EURUSD", "GBPNZD")
HORIZONS = ("D1", "W1")
SECONDS = {"D1": 86400, "W1": 604800}
MAX_BARS = 20
DEFAULT_BARS = 12


def _utc(value: Any) -> datetime | None:
    if not isinstance(value, datetime) or value.utcoffset() is None:
        return None
    return value.astimezone(timezone.utc)


def _stamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _blocked(reason: str, now: datetime | None = None) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "state": "LAB_MT5_CLOCK_PROBE_BLOCKED", "reason": reason,
        "probe_started_at_utc": _stamp(now) if now else None,
        "symbols": list(SYMBOLS), "timeframes": list(HORIZONS),
        "bar_position_start": 1, "terminal_connected_observed": False,
        "terminal_build": None, "requested_series": 4, "checked_series": 0,
        "checked_bar_labels": 0, "reference_discrepancy_count": 0,
        "series": [], "report_sha256_local_only": None,
        "server_identity_authenticated": False,
        "pepperstone_server_association_verified": False,
        "broker_session_calendar_verified": False,
        "timestamp_represents_actual_session_open_verified": False,
        "price_vintage_at_decision_authenticated": False,
        "real_directional_accuracy_validated": False,
        "validated_directional_accuracy": None,
        "calibrated_direction_probability": None,
        "operational_bias": "AGUARDAR", "publishable": False,
        "live_alert_allowed": False, "trade_authorized": False,
        "worker_enabled": False, "scheduler_enabled": False,
        "new_cost_brl": 0, "research_only": True,
    }


def inspect_mt5_d1w1_clock_lab(
    api: Any, *, now_utc: Any, count: int = DEFAULT_BARS,
) -> dict[str, Any]:
    """Inspect an *already initialized* MT5 API; never initialize or shutdown.

    Nothing is written to disk. The API calls are exactly terminal_info,
    symbol_info and copy_rates_from_pos; caller owns connection lifecycle.
    """
    now = _utc(now_utc)
    result = _blocked("INVALID_OBSERVATION_CLOCK_OR_SAMPLE_SIZE", now)
    if now is None or type(count) is not int or not (2 <= count <= MAX_BARS):
        return result
    try:
        zone = ZoneInfo("America/New_York")
    except ZoneInfoNotFoundError:
        result["reason"] = "NY_TIMEZONE_DATA_UNAVAILABLE"
        return result
    try:
        terminal = api.terminal_info()
        if terminal is None or getattr(terminal, "connected", None) is not True:
            result["reason"] = "TERMINAL_NOT_CONNECTED"
            return result
        result["terminal_connected_observed"] = True
        build = getattr(terminal, "build", None)
        if isinstance(build, Integral) and not isinstance(build, bool):
            result["terminal_build"] = int(build)
        frames = {"D1": api.TIMEFRAME_D1, "W1": api.TIMEFRAME_W1}
        rows: list[dict[str, Any]] = []
        discrepancies = 0
        for symbol in SYMBOLS:
            details = api.symbol_info(symbol)
            if details is None or getattr(details, "visible", None) is not True:
                result["reason"] = "SYMBOL_NOT_VISIBLE_NO_AUTO_SELECT"
                return result
            for horizon in HORIZONS:
                rates = api.copy_rates_from_pos(symbol, frames[horizon], 1, count)
                if rates is None or len(rates) != count:
                    result["reason"] = "MISSING_CLOSED_BARS_OR_PARTIAL_SERIES"
                    return result
                times: list[int] = []
                for bar in rates:
                    value = bar["time"]
                    if not isinstance(value, Integral) or isinstance(value, bool):
                        result["reason"] = "INVALID_MT5_TIME_VALUE"
                        return result
                    epoch = int(value)
                    if epoch <= 0 or (times and epoch <= times[-1]):
                        result["reason"] = "NON_MONOTONIC_OR_INVALID_MT5_TIMES"
                        return result
                    times.append(epoch)
                samples: list[dict[str, Any]] = []
                for epoch in times:
                    opened = datetime.fromtimestamp(epoch, tz=timezone.utc)
                    # A conservative safety fence. MT5 position 1 is generally
                    # closed, but never trust it without independent timing.
                    if opened + timedelta(seconds=SECONDS[horizon]) > now:
                        result["reason"] = "BAR_NOT_NOMINALLY_CLOSED_AT_OBSERVATION"
                        return result
                    ny = opened.astimezone(zone)
                    is_session_day = (ny.weekday() == 6 if horizon == "W1"
                                      else ny.weekday() in (6, 0, 1, 2, 3))
                    matches = bool(is_session_day and (ny.hour, ny.minute, ny.second) == (17, 0, 0))
                    discrepancies += int(not matches)
                    samples.append({
                        "open_epoch": epoch,
                        "open_utc": _stamp(opened),
                        "open_new_york": ny.isoformat(),
                        "reference_ny_17h_match": matches,
                    })
                rows.append({
                    "symbol": symbol, "timeframe": horizon,
                    "requested_closed_positions": count,
                    "earliest_open_utc": samples[0]["open_utc"],
                    "latest_open_utc": samples[-1]["open_utc"],
                    "bar_labels": samples,
                })
        result.update({
            "state": ("LAB_CLOCK_REFERENCE_DISCREPANCY_NEEDS_SERVER_REVIEW"
                      if discrepancies else "LAB_NY_CLOSE_PATTERN_MATCH_UNATTESTED"),
            "reason": ("MT5_BAR_LABELS_DISAGREE_WITH_NY17_REFERENCE"
                       if discrepancies else "NY17_MATCH_STILL_NOT_BROKER_PROOF"),
            "checked_series": len(rows),
            "checked_bar_labels": len(rows) * count,
            "reference_discrepancy_count": discrepancies,
            "series": rows,
        })
        # A local integrity fingerprint, not an external timestamp proof.
        payload = json.dumps(result, sort_keys=True, ensure_ascii=True,
                             separators=(",", ":"), allow_nan=False).encode("ascii")
        result["report_sha256_local_only"] = sha256(payload).hexdigest()
        return result
    except (AttributeError, KeyError, TypeError, ValueError, OverflowError, OSError, IndexError):
        result["reason"] = "MT5_DATA_OR_CLOCK_QUERY_FAILED"
        return result


def run_connected_probe(
    api: Any, *, terminal_path: str,
    now_utc: datetime | Callable[[], datetime], count: int = DEFAULT_BARS,
) -> dict[str, Any]:
    """Initialize MT5 only once, and always release the Python API connection.

    `shutdown` disconnects this API session, not the user's MT5 terminal.
    """
    if not isinstance(terminal_path, str) or not terminal_path:
        return _blocked("INVALID_TERMINAL_PATH")
    try:
        ok = api.initialize(path=terminal_path, timeout=10000)
    except (AttributeError, TypeError, OSError):
        return _blocked("MT5_INITIALIZATION_FAILED")
    if not ok:
        return _blocked("MT5_INITIALIZATION_FAILED")
    try:
        observed = now_utc() if callable(now_utc) else now_utc
        return inspect_mt5_d1w1_clock_lab(api, now_utc=observed, count=count)
    finally:
        api.shutdown()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--terminal-path", default=r"C:\Program Files\MetaTrader 5\terminal64.exe")
    parser.add_argument("--count", type=int, default=DEFAULT_BARS)
    parser.add_argument("--report", type=Path, default=None,
                        help="Optional local JSON report path; default prints only")
    args = parser.parse_args()
    # Import only when called on the authorized local Windows terminal.
    try:
        import MetaTrader5 as mt5
    except ImportError:
        result = _blocked("META_TRADER5_PYTHON_PACKAGE_NOT_INSTALLED")
    else:
        result = run_connected_probe(mt5, terminal_path=args.terminal_path,
                                     now_utc=lambda: datetime.now(timezone.utc),
                                     count=args.count)
    raw = json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    if args.report is not None:
        target = args.report
        if target.exists() or target.is_symlink() or not target.parent.is_dir():
            raise SystemExit("REPORT_PATH_UNSAFE_OR_EXISTS_NO_OVERWRITE")
        target.write_text(raw, encoding="utf-8", newline="\n")
        print("LOCAL_REPORT_WRITTEN", str(target))
    else:
        print(raw)
    return 0 if result["state"].startswith("LAB_NY_CLOSE_PATTERN_MATCH") else 3


if __name__ == "__main__":
    raise SystemExit(main())
