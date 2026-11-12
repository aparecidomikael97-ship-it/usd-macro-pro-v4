"""FX28 Pepperstone MT5 NY17 D1 M15 history readiness, LAB only.

Read-only retrospective coverage check for two EXPLICIT past sessions.
A result is NOT a forecast, broker provenance, an independently attested
price history, a forward label, probability or permission to trade.
Historical M15 bars may be absent near NY17 even if neighboring bars exist.
Never synthesize/forward-fill a candle or treat any lack of ticks as flat.

Manual CLI only. No file writes, symbol_select, account_info, order_send,
positions, login, worker, scheduler or automatic alerts.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Callable
import argparse
import json

from atlasquant_instrument_registry import FX_28
from atlasquant_mt5_xauusd_closedbar_capture_lab import _terminal_path_ok
from atlasquant_trader_ppi_mt5_m15_capture_lab import (
    _symbol_spec_for_capture, _integer, _price,
)

SCHEMA = "ATLASQUANT_TRADER_FX28_AM12_NY17_D1_M15_GAP_GUARD_LAB_V1"
ALLOWED_SESSIONS = frozenset(("2026-11-10", "2026-11-11"))
BARS_PER_SESSION = 96
M15_SECONDS = 900
MAX_GAP_TIMESTAMPS = 6


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_FX28_NY17_D1_PREFLIGHT_BLOCKED",
        "reason": reason, "session_start_utc": None,
        "session_end_utc_exclusive": None,
        "expected_pairs": len(FX_28), "expected_candles_per_pair": BARS_PER_SESSION,
        "expected_total_candles": len(FX_28) * BARS_PER_SESSION,
        "pairs_checked": 0, "pairs_with_complete_history": 0,
        "valid_candles_seen": 0, "missing_candles_total": 0,
        "pairs_with_gaps_or_invalid_data": [], "pair_diagnostics": {},
        "symbols_hidden_but_history_queried": [],
        "bounded_history_warmup_attempted": [],
        "all_28_d1_m15_histories_structurally_complete": False,
        "broker_feed_independently_authenticated": False,
        "original_history_point_in_time_attested": False,
        "future_bias_forecast_preregistered": False,
        "future_outcome_label_authorized": False,
        "observed_past_prices_are_not_predictive_accuracy": True,
        "calibrated_direction_probability": None,
        "directional_accuracy_validated": None,
        "directional_bias": None, "operational_bias": "AGUARDAR",
        "live_alert_allowed": False, "trade_authorized": False,
        "publishable": False, "worker_enabled": False,
        "scheduler_enabled": False, "files_written": 0,
        "account_info_accessed": False, "orders_or_positions_accessed": False,
        "market_watch_modified_by_script": False,
        "new_cost_brl": 0, "research_only": True,
    }


def _utc_clock(value: Any) -> datetime | None:
    if (not isinstance(value, datetime) or value.tzinfo is None
            or value.utcoffset() is None or value.microsecond):
        return None
    try:
        return value.astimezone(timezone.utc)
    except (ValueError, OverflowError):
        return None


def _expected_epochs(start: datetime) -> tuple[int, ...]:
    return tuple(int(start.timestamp()) + M15_SECONDS * i
                 for i in range(BARS_PER_SESSION))


def _audit_rates(rates: Any, epochs: tuple[int, ...], digits: int) -> dict[str, Any]:
    """Strict 96/480-bar timestamp inventory for D1/W1; never interpolate."""
    if (type(epochs) is not tuple or len(epochs) not in (96, 480)
            or any(type(t) is not int or t <= 0 for t in epochs)
            or any(epochs[i + 1] - epochs[i] != 900
                   for i in range(len(epochs) - 1))):
        raise ValueError("INVALID_FROZEN_D1_W1_M15_EPOCH_GRID")
    if rates is None:
        return {
            "reason": "HISTORY_NULL", "returned_bars": None,
            "missing_count": len(epochs),
            "first_missing_utc": [
                datetime.fromtimestamp(t, timezone.utc).isoformat()
                for t in epochs[:MAX_GAP_TIMESTAMPS]],
            "valid_candles": 0,
        }
    if len(rates) > len(epochs):
        return {
            "reason": "EXCESS_ROWS_OR_UNEXPECTED_TIMEFRAME",
            "returned_bars": len(rates), "missing_count": None,
            "first_missing_utc": [], "valid_candles": 0,
        }
    try:
        times = [int(_integer(x["time"], strictly_positive=True)) for x in rates]
    except (KeyError, ValueError, TypeError, OverflowError, IndexError):
        return {
            "reason": "INVALID_CANDLE_TIME_FIELD",
            "returned_bars": len(rates), "missing_count": None,
            "first_missing_utc": [], "valid_candles": 0,
        }
    expected_set = set(epochs)
    if (len(set(times)) != len(times)
            or any(t not in expected_set for t in times)
            or times != sorted(times)):
        return {
            "reason": "DUPLICATE_OUT_OF_WINDOW_OR_UNSORTED_CANDLE",
            "returned_bars": len(rates), "missing_count": None,
            "first_missing_utc": [], "valid_candles": 0,
        }
    have = set(times)
    gaps = [t for t in epochs if t not in have]
    if gaps:
        return {
            "reason": "EXACT_M15_CANDLES_MISSING_NO_FILL",
            "returned_bars": len(rates), "missing_count": len(gaps),
            "first_missing_utc": [
                datetime.fromtimestamp(t, timezone.utc).isoformat()
                for t in gaps[:MAX_GAP_TIMESTAMPS]],
            "valid_candles": 0,
        }
    if times != list(epochs):
        return {
            "reason": "M15_CANDLE_TIMESTAMPS_MISMATCH",
            "returned_bars": len(rates), "missing_count": None,
            "first_missing_utc": [], "valid_candles": 0,
        }
    try:
        for x in rates:
            o, h, lo, c = [
                _price(x[k], quote_digits=digits)[0]
                for k in ("open", "high", "low", "close")]
            if not lo <= min(o, c) <= max(o, c) <= h:
                raise ValueError("INCONSISTENT_CANDLE_OHLC")
            _integer(x["tick_volume"], strictly_positive=True)
            _integer(x["spread"], strictly_positive=False)
            _integer(x["real_volume"], strictly_positive=False)
    except (ValueError, KeyError, TypeError, OverflowError, IndexError):
        return {
            "reason": "M15_PRICE_OR_VOLUME_INVALID",
            "returned_bars": len(rates), "missing_count": 0,
            "first_missing_utc": [], "valid_candles": 0,
        }
    return {
        "reason": "COMPLETE_HISTORICAL_SERIES_UNATTESTED",
        "returned_bars": len(rates),
        "missing_count": 0, "first_missing_utc": [],
        "valid_candles": len(epochs),
    }


def inspect_fx28_ny17_d1_m15_readiness_lab(
    api: Any, *, terminal_path: Any, session_start_day: Any,
    clock: Callable[[], datetime],
) -> dict[str, Any]:
    result = _blocked("INVALID_INPUT_OR_DECLARED_SESSION")
    if (not _terminal_path_ok(terminal_path)
            or type(session_start_day) is not str
            or session_start_day not in ALLOWED_SESSIONS
            or len(FX_28) != 28 or len(set(FX_28)) != 28):
        return result
    now = _utc_clock(clock())
    if now is None:
        result["reason"] = "INVALID_CURRENT_WALL_CLOCK"
        return result
    start = datetime.fromisoformat(session_start_day + "T22:00:00+00:00")
    end = start + timedelta(days=1)
    if now < end:
        result["reason"] = "NY17_D1_SESSION_HAS_UNCLOSED_M15_BAR"
        return result

    result["session_start_utc"] = start.isoformat()
    result["session_end_utc_exclusive"] = end.isoformat()
    last_open = end - timedelta(minutes=15)
    epochs = _expected_epochs(start)

    try:
        connected = api.initialize(path=terminal_path, timeout=10000)
    except (AttributeError, ValueError, TypeError, OSError, RuntimeError):
        result["reason"] = "MT5_INITIALIZE_FAILED"
        return result
    if not connected:
        result["reason"] = "MT5_TERMINAL_NOT_CONNECTED"
        return result
    try:
        terminal = api.terminal_info()
        if terminal is None or terminal.connected is not True:
            result["reason"] = "MT5_TERMINAL_NOT_CONNECTED"
            return result
        for sym in FX_28:
            info = api.symbol_info(sym)
            result["pairs_checked"] += 1
            if info is None or type(getattr(info, "visible", None)) is not bool:
                row = {"reason": "SYMBOL_NOT_FOUND_OR_VISIBILITY_INVALID",
                       "returned_bars": None, "missing_count": None,
                       "first_missing_utc": [], "valid_candles": 0}
                result["pair_diagnostics"][sym] = row
                result["pairs_with_gaps_or_invalid_data"].append(sym)
                continue
            visible = info.visible
            spec = _symbol_spec_for_capture(info, sym)
            if spec is None:
                row = {"reason": "SYMBOL_BASE_QUOTE_POINT_OR_DIGITS_INVALID",
                       "returned_bars": None, "missing_count": None,
                       "first_missing_utc": [], "valid_candles": 0}
                result["pair_diagnostics"][sym] = row
                result["pairs_with_gaps_or_invalid_data"].append(sym)
                continue
            if not visible:
                result["symbols_hidden_but_history_queried"].append(sym)

            bars = api.copy_rates_range(sym, api.TIMEFRAME_M15, start, last_open)
            if bars is None or len(bars) != BARS_PER_SESSION:
                # Query a bounded two-day prefix once to warm the MT5 cache.
                # Even partial 94/96 *must* remain blocked if it persists.
                result["bounded_history_warmup_attempted"].append(sym)
                api.copy_rates_range(
                    sym, api.TIMEFRAME_M15, start - timedelta(days=2), last_open)
                bars = api.copy_rates_range(
                    sym, api.TIMEFRAME_M15, start, last_open)
            after = api.symbol_info(sym)
            if (after is None
                    or type(getattr(after, "visible", None)) is not bool
                    or after.visible != visible):
                row = {"reason": "SYMBOL_VISIBILITY_CHANGED_OR_UNVERIFIABLE",
                       "returned_bars": None, "missing_count": None,
                       "first_missing_utc": [], "valid_candles": 0}
                result["pair_diagnostics"][sym] = row
                result["pairs_with_gaps_or_invalid_data"].append(sym)
                continue
            row = _audit_rates(bars, epochs, spec["digits_claim"])
            row["market_watch_visible"] = visible
            result["pair_diagnostics"][sym] = row
            if row["valid_candles"] == BARS_PER_SESSION:
                result["pairs_with_complete_history"] += 1
                result["valid_candles_seen"] += BARS_PER_SESSION
            else:
                result["pairs_with_gaps_or_invalid_data"].append(sym)
                if row["missing_count"] is not None:
                    result["missing_candles_total"] += row["missing_count"]

        complete = (
            result["pairs_checked"] == 28
            and result["pairs_with_complete_history"] == 28
            and result["valid_candles_seen"] == 28 * BARS_PER_SESSION)
        result["all_28_d1_m15_histories_structurally_complete"] = complete
        result["state"] = (
            "LAB_FX28_NY17_D1_HISTORICAL_COVERAGE_ONLY_NO_GO"
            if complete else "LAB_FX28_NY17_D1_HISTORICAL_GAPS_NO_GO")
        result["reason"] = (
            "LOCAL_M15_HISTORY_COMPLETE_NOT_BROKER_PIT_OR_BIAS_PROOF"
            if complete else "PAIR_GAPS_OR_INVALID_HISTORY_CANNOT_FILL")
        return result
    except (AttributeError, KeyError, ValueError, TypeError, OSError, RuntimeError):
        result["state"] = "LAB_FX28_NY17_D1_PREFLIGHT_BLOCKED"
        result["reason"] = "MT5_READONLY_QUERY_ERROR"
        result["all_28_d1_m15_histories_structurally_complete"] = False
        return result
    finally:
        try:
            api.shutdown()
        except (AttributeError, OSError, RuntimeError, TypeError):
            result["state"] = "LAB_FX28_NY17_D1_PREFLIGHT_BLOCKED"
            result["reason"] = "MT5_SHUTDOWN_ERROR"
            result["all_28_d1_m15_histories_structurally_complete"] = False


def main() -> int:
    ap = argparse.ArgumentParser(
        description="AtlasQuant FX28 NY17 closed D1 M15 history preflight LAB")
    ap.add_argument("--terminal-path", required=True)
    ap.add_argument("--session-start-day", required=True,
                    choices=sorted(ALLOWED_SESSIONS))
    opts = ap.parse_args()
    try:
        import MetaTrader5 as mt5
    except ImportError:
        print("LAB_BLOCKED: MetaTrader5 package missing")
        return 2
    out = inspect_fx28_ny17_d1_m15_readiness_lab(
        mt5, terminal_path=opts.terminal_path,
        session_start_day=opts.session_start_day,
        clock=lambda: datetime.now(timezone.utc).replace(microsecond=0))
    print(json.dumps(out, sort_keys=True, indent=2, ensure_ascii=False))
    return 0 if out["all_28_d1_m15_histories_structurally_complete"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
