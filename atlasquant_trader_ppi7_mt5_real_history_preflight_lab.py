"""PPI7: read-only historic Pepperstone M15 readiness on pre-event days.

Not the post-PPI archive. Preflight uses real, CLOSED historical M15 bars
for two fixed dates prior to 13 Nov 2026, validating against the exact same
strict CSV serializer that the eventual event collector uses. No output
files, account data, orders, symbol selection, alerts or scheduling.
MT5 terminal labels and local history do NOT authenticate the broker/vintage
or constitute a forecast or predictive out-of-sample experiment.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from statistics import median
from typing import Any, Callable
import argparse
import json

from atlasquant_mt5_xauusd_closedbar_capture_lab import _terminal_path_ok
from atlasquant_trader_ppi_usd_fx_forward_reaction_lab import USD_FX
from atlasquant_trader_ppi_mt5_m15_capture_lab import (
    _serialize_exact_window, _symbol_spec_for_capture, ROWS_REQUIRED,
)

SCHEMA = "ATLASQUANT_PPI7_MT5_REAL_PRE_EVENT_HISTORY_PREFLIGHT_LAB_V1"
PAST_DAYS = frozenset(("2026-11-10", "2026-11-11"))
OPEN_HOUR_UTC, OPEN_MINUTE_UTC = 13, 15
INTERVAL_SECONDS = 900


def _base(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "state": "LAB_MT5_PRE_EVENT_HISTORY_PREFLIGHT_BLOCKED",
        "reason": reason,
        "reference_day_utc": None,
        "expected_pairs": list(USD_FX),
        "expected_bars_per_pair": ROWS_REQUIRED,
        "checked_pairs": 0,
        "validated_pairs": 0,
        "validated_bars": 0,
        "pair_results": {},
        "hidden_pairs_with_valid_history": [],
        "history_warmup_attempted": [],
        "only_closed_bars_allowed": True,
        "files_written": 0,
        "http_requests": 0,
        "orders_or_positions_accessed": False,
        "account_information_accessed": False,
        "visibility_changed_by_script": False,
        "broker_identity_independently_authenticated": False,
        "market_data_point_in_time_authenticated": False,
        "future_ppi_event_candles_available": False,
        "event_reaction_measured": False,
        "validated_bias_accuracy": None,
        "operational_bias": "AGUARDAR",
        "trade_authorized": False,
        "live_alert_allowed": False,
        "scheduler_enabled": False,
        "publishable": False,
        "new_cost_brl": 0,
    }


def inspect_pre_event_mt5_m15_history_lab(
    api: Any, *, terminal_path: Any, reference_day: Any,
    clock: Callable[[], datetime],
) -> dict[str, Any]:
    """Check exactly 17 M15 past closed bars for 7 instruments; no storage."""
    result = _base("INVALID_TERMINAL_OR_REFERENCE_DAY")
    if (not _terminal_path_ok(terminal_path)
            or type(reference_day) is not str or reference_day not in PAST_DAYS):
        return result
    try:
        now = clock()
        if (not isinstance(now, datetime) or now.tzinfo is None
                or now.utcoffset() is None or now.microsecond):
            result["reason"] = "INVALID_EVALUATION_CLOCK"
            return result
        now = now.astimezone(timezone.utc)
        start = datetime.fromisoformat(reference_day).replace(
            hour=OPEN_HOUR_UTC, minute=OPEN_MINUTE_UTC, tzinfo=timezone.utc)
        epochs = tuple(int(start.timestamp()) + INTERVAL_SECONDS * i
                       for i in range(ROWS_REQUIRED))
        end_open = datetime.fromtimestamp(epochs[-1], tz=timezone.utc)
        last_close = end_open + timedelta(seconds=INTERVAL_SECONDS)
        if now < last_close:
            result["reason"] = "WINDOW_HAS_UNCLOSED_BAR"
            return result
    except (TypeError, ValueError, OverflowError):
        result["reason"] = "REFERENCE_CLOCK_OR_CALENDAR_INVALID"
        return result
    result["reference_day_utc"] = reference_day

    try:
        connected = api.initialize(path=terminal_path, timeout=10000)
    except (AttributeError, OSError, TypeError, ValueError, RuntimeError):
        result["reason"] = "MT5_INITIALIZE_EXCEPTION"
        return result
    if not connected:
        result["reason"] = "MT5_NOT_CONNECTED"
        return result
    try:
        terminal = api.terminal_info()
        if terminal is None or terminal.connected is not True:
            result["reason"] = "TERMINAL_NOT_CONNECTED"
            return result

        for sym in USD_FX:
            before = api.symbol_info(sym)
            if before is None:
                result["reason"] = "SYMBOL_NOT_FOUND"
                result["failed_symbol"] = sym
                return result
            visible = before.visible
            if type(visible) is not bool:
                result["reason"] = "INVALID_VISIBILITY_METADATA"
                result["failed_symbol"] = sym
                return result
            if _symbol_spec_for_capture(before, sym) is None:
                result["reason"] = "SYMBOL_IDENTITY_OR_TICK_INVALID"
                result["failed_symbol"] = sym
                return result

            bars = api.copy_rates_range(sym, api.TIMEFRAME_M15, start, end_open)
            if bars is None or len(bars) == 0:
                result["history_warmup_attempted"].append(sym)
                api.copy_rates_range(
                    sym, api.TIMEFRAME_M15, start - timedelta(days=2),
                    end_open)
                bars = api.copy_rates_range(sym, api.TIMEFRAME_M15, start, end_open)

            after = api.symbol_info(sym)
            if (after is None or type(after.visible) is not bool
                    or after.visible != visible):
                result["reason"] = "SYMBOL_VISIBILITY_CHANGED_OR_UNVERIFIABLE"
                result["failed_symbol"] = sym
                return result
            try:
                _serialize_exact_window(bars, expected_epochs=epochs)
            except (TypeError, ValueError, OverflowError, IndexError) as exc:
                result["reason"] = ("M15_HISTORY_FAILED_STRICT_SERIALIZER:"
                                    + str(exc)[:90])
                result["failed_symbol"] = sym
                return result
            spreads = [int(row["spread"]) for row in bars]
            result["pair_results"][sym] = {
                "closed_m15_bars": ROWS_REQUIRED,
                "visible_in_market_watch": visible,
                "median_stored_bar_spread_points": median(spreads),
                "max_stored_bar_spread_points": max(spreads),
                "price_bytes_or_ohlc_retained": False,
            }
            if not visible:
                result["hidden_pairs_with_valid_history"].append(sym)
            result["checked_pairs"] += 1
            result["validated_pairs"] += 1
            result["validated_bars"] += ROWS_REQUIRED

        result["state"] = "LAB_MT5_7PAIR_REAL_HISTORICAL_M15_CANDIDATE_UNATTESTED"
        result["reason"] = "HISTORIC_BARS_ONLY_NO_EVENT_RESULT_OR_BROKER_PIT_PROOF"
        return result
    except (AttributeError, OSError, TypeError, ValueError, RuntimeError):
        result["reason"] = "MT5_READONLY_DIAGNOSTIC_EXCEPTION"
        return result
    finally:
        try:
            api.shutdown()
        except (AttributeError, OSError, TypeError, RuntimeError):
            result["state"] = "LAB_MT5_PRE_EVENT_HISTORY_PREFLIGHT_BLOCKED"
            result["reason"] = "MT5_SHUTDOWN_FAILED"
            result["validated_pairs"] = 0
            result["validated_bars"] = 0


def main() -> int:
    ap = argparse.ArgumentParser(
        description="PPI7 prior-day real M15 read-only preflight LAB")
    ap.add_argument("--terminal-path", required=True)
    ap.add_argument("--reference-day", required=True, choices=sorted(PAST_DAYS))
    args = ap.parse_args()
    try:
        import MetaTrader5 as mt5  # optional, only after explicit invocation
    except ImportError:
        print("LAB_BLOCKED: MetaTrader5 package absent")
        return 2
    out = inspect_pre_event_mt5_m15_history_lab(
        mt5, terminal_path=args.terminal_path,
        reference_day=args.reference_day,
        clock=lambda: datetime.now(timezone.utc).replace(microsecond=0))
    print(json.dumps(out, sort_keys=True, indent=2, ensure_ascii=False))
    return 0 if out["validated_bars"] == ROWS_REQUIRED * len(USD_FX) else 2


if __name__ == "__main__":
    raise SystemExit(main())
