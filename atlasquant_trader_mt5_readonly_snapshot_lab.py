"""Capture 28 G8 FX price histories from an already-open MT5, LAB only.

This adapter reads CLOSED bars through the official MetaTrader5 Python API.
It never logs in, selects symbols, changes charts, sends orders, schedules a
worker or connects the data to the live Radar. All quotes are broker-reported,
not independently authenticated or a proven point-in-time backtest dataset.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path
from typing import Any

from atlasquant_instrument_registry import FX_28


SCHEMA = "ATLASQUANT_TRADER_MT5_G8_CLOSED_BARS_READONLY_LAB_V1"
TIMEFRAME_COUNTS = {"M15": 64, "D1": 30, "W1": 12}
TIMEFRAME_SECONDS = {"M15": 900, "D1": 86400, "W1": 604800}
PRICE_FIELDS = ("open", "high", "low", "close")
OTHER_FIELDS = ("tick_volume", "spread", "real_volume")


def _base(captured: datetime) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "state": "LAB_BLOCKED",
        "reason": "NOT_COLLECTED",
        "captured_at_utc": captured.isoformat(),
        "source": "MT5_CONNECTED_TERMINAL_BROKER_REPORTED_UNVERIFIED",
        "timestamp_basis": "MT5_UNIX_SECONDS_UTC_REPORTED_NOT_INDEPENDENTLY_ATTESTED",
        "expected_pairs": len(FX_28),
        "validated_pairs": 0,
        "validated_bars": 0,
        "timeframe_counts": dict(TIMEFRAME_COUNTS),
        "pairs": {},
        "broker_identity_independently_verified": False,
        "quotes_independently_verified": False,
        "historical_vintage_point_in_time_verified": False,
        "fx_ny_1700_d1w1_aligned": False,
        "historical_predictive_accuracy": None,
        "fx_bias": None,
        "operational_bias": "AGUARDAR",
        "can_feed_live_radar": False,
        "trade_authorized": False,
        "worker_enabled": False,
        "scheduler_enabled": False,
        "publishable": False,
        "new_cost_brl": 0,
    }


def _validate_bars(raw: Any, *, timeframe: str, captured_epoch: int) -> dict[str, Any]:
    """Return normalized bars, rejecting unfinished or inconsistent candles.

    M15 weekend/session gaps are counted, never silently filled. Daily/weekly
    bars are broker-session boundaries, not asserted to be New York 17:00.
    """
    expected = TIMEFRAME_COUNTS[timeframe]
    if raw is None or len(raw) != expected:
        raise ValueError("MISSING_OR_INCOMPLETE_HISTORY")

    previous: int | None = None
    interval_gaps = 0
    bars: list[dict[str, Any]] = []
    for item in raw:
        ts = int(item["time"])
        if ts < 946684800 or ts > 4102444800 or previous is not None and ts <= previous:
            raise ValueError("INVALID_BAR_TIMESTAMP_SEQUENCE")
        if timeframe == "M15" and ts % TIMEFRAME_SECONDS["M15"]:
            raise ValueError("MISALIGNED_M15_OPEN_TIMESTAMP")
        if ts + TIMEFRAME_SECONDS[timeframe] > captured_epoch:
            raise ValueError("CURRENT_OR_FUTURE_BAR_REJECTED")
        if previous is not None and timeframe == "M15":
            diff = ts - previous
            if diff != 900:
                interval_gaps += 1

        prices = {field: float(item[field]) for field in PRICE_FIELDS}
        if any(not math.isfinite(v) or not 0.0001 <= v <= 1000 for v in prices.values()):
            raise ValueError("INVALID_PRICE")
        if not (prices["low"] <= min(prices["open"], prices["close"])
                <= max(prices["open"], prices["close"]) <= prices["high"]):
            raise ValueError("INCONSISTENT_OHLC")
        quantities = {field: int(item[field]) for field in OTHER_FIELDS}
        if any(quantities[field] < 0 for field in OTHER_FIELDS):
            raise ValueError("NEGATIVE_VOLUME_OR_SPREAD")

        bars.append({"time": ts, **prices, **quantities})
        previous = ts

    return {
        "closed_bars": expected,
        "first_bar_open_utc": datetime.fromtimestamp(bars[0]["time"], timezone.utc).isoformat(),
        "last_bar_open_utc": datetime.fromtimestamp(bars[-1]["time"], timezone.utc).isoformat(),
        "non_contiguous_m15_intervals": interval_gaps if timeframe == "M15" else None,
        "bars": bars,
    }


def collect_mt5_fx_snapshot_lab(mt5: Any, *, captured_at_utc: datetime) -> dict[str, Any]:
    """Inject MT5 API for deterministic tests; no authorization to trade.

    Only calls initialize, symbols_get, copy_rates_from_pos and shutdown.
    Position 1 specifically excludes the MT5 still-forming candle.
    """
    if captured_at_utc.tzinfo is None or captured_at_utc.utcoffset() is None:
        raise ValueError("captured_at_utc must be timezone-aware")
    now = captured_at_utc.astimezone(timezone.utc)
    report = _base(now)
    connected = False
    try:
        if not mt5.initialize():
            report["reason"] = "MT5_TERMINAL_NOT_CONNECTED"
            return report
        connected = True
        available = {s.name for s in mt5.symbols_get() or []}
        missing = [pair for pair in FX_28 if pair not in available]
        if missing:
            report["reason"] = "CANONICAL_28_SYMBOLS_NOT_AVAILABLE"
            report["missing_symbols"] = missing
            return report
        collected: dict[str, Any] = {}
        bar_total = 0
        now_epoch = int(now.timestamp())
        for pair in FX_28:
            candles = {}
            for tf, count in TIMEFRAME_COUNTS.items():
                rates = mt5.copy_rates_from_pos(pair, getattr(mt5, "TIMEFRAME_" + tf), 1, count)
                candles[tf] = _validate_bars(rates, timeframe=tf, captured_epoch=now_epoch)
                bar_total += count
            collected[pair] = candles

        report.update({
            "state": "LAB_BROKER_HISTORY_STRUCTURALLY_VALID_UNVERIFIED",
            "reason": "BROKER_QUOTE_SOURCE_AND_POINT_IN_TIME_NOT_INDEPENDENTLY_VERIFIED",
            "validated_pairs": len(collected),
            "validated_bars": bar_total,
            "pairs": collected,
        })
        return report
    except (AttributeError, KeyError, TypeError, ValueError, OverflowError, RuntimeError) as exc:
        # Return no partial, potentially misleading history or terminal secrets.
        report["reason"] = str(exc) if isinstance(exc, ValueError) else "MT5_READ_FAILED"
        return report
    finally:
        if connected:
            mt5.shutdown()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="MT5 read-only closed-candle LAB snapshot")
    parser.add_argument("--out", type=Path, help="Create a NEW local private JSON file (no overwrite)")
    args = parser.parse_args(argv)
    try:
        import MetaTrader5 as mt5  # Only installed in the separate Windows LAB venv.
    except ImportError:
        print("MT5_PYTHON_PACKAGE_UNAVAILABLE")
        return 2
    report = collect_mt5_fx_snapshot_lab(mt5, captured_at_utc=datetime.now(timezone.utc))
    if args.out and report["state"] != "LAB_BLOCKED":
        try:
            with args.out.open("x", encoding="utf-8") as destination:
                json.dump(report, destination, ensure_ascii=False, sort_keys=True, allow_nan=False)
                destination.write("\n")
        except OSError:
            print("SNAPSHOT_FILE_NOT_CREATED")
            return 2
    print(json.dumps({k: report[k] for k in ("schema", "state", "reason", "captured_at_utc", "validated_pairs", "validated_bars", "operational_bias", "trade_authorized")}, ensure_ascii=False, sort_keys=True))
    return 0 if report["state"] != "LAB_BLOCKED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
