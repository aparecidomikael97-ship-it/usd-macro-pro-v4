"""AtlasQuant FX28: compare broker-native W1 close to frozen NY17 M15 close.

The two CLOSED historical weeks are explicitly fixed. The native W1
Sunday-00:00 timestamp is a broker-terminal historical label, NOT the
Sun-17-New-York NY17 start. Local historic W1 bars on AM12 were observed
to reflect Friday 23:45 UTC M15 closes, 180/120 minutes after the
respective frozen NY17 Friday closing boundaries.

This is a research-only *timeframe incompatibility test*: even matching
price values must NEVER authorize native W1 candles to be substituted
for NY17-derived labels; historical feed, DST, session calendar, broker
first availability, and execution are not independently attested.

No account, orders, positions, network, files, symbol_select, alerts,
scheduler, deployment or trade authorization. One-shot read-only MT5.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Callable
import argparse
import json

from atlasquant_instrument_registry import FX_28
from atlasquant_mt5_xauusd_closedbar_capture_lab import _terminal_path_ok
from atlasquant_trader_ppi_mt5_m15_capture_lab import (
    _price, _symbol_spec_for_capture, _integer,
)

SCHEMA = "ATLASQUANT_FX28_NY17_VS_NATIVE_W1_CLOSE_ANCHOR_LAB_V1"
WEEKS = {
    "2026-10-25": (
        "2026-10-25T21:00:00+00:00",
        "2026-10-30T21:00:00+00:00",
        "2026-10-30T23:45:00+00:00",
    ),
    "2026-11-01": (
        "2026-11-01T22:00:00+00:00",
        "2026-11-06T22:00:00+00:00",
        "2026-11-06T23:45:00+00:00",
    ),
}


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "state": "LAB_FX28_NATIVE_W1_NY17_ANCHOR_BLOCKED",
        "reason": reason,
        "week_count": 0,
        "pair_week_comparisons": 0,
        "native_w1_close_equals_late_friday_m15": 0,
        "native_w1_close_equals_ny17_m15": 0,
        "native_w1_disagrees_with_ny17_pair_weeks": 0,
        "pairs_with_incomplete_or_bad_native_data": [],
        "weekly_diagnostics": {},
        "native_w1_sunday_utc_midnight_stamps_verified_locally": False,
        "all_comparisons_structurally_available": False,
        "native_weekly_candles_equivalent_to_ny17": False,
        "native_weekly_close_permitted_as_ny17_outcome": False,
        "historical_session_calendar_authenticated": False,
        "historic_original_feed_point_in_time_verified": False,
        "broker_utc_offset_for_historic_period_attested": False,
        "missing_ny17_m15_slots_waived": False,
        "price_values_exported": False,
        "historic_backfill_permitted": False,
        "causal_signal_verified": False,
        "directional_prediction_validated": False,
        "probability_calibrated": False,
        "operational_bias": "AGUARDAR",
        "trade_authorized": False,
        "publishable": False,
        "live_alert_allowed": False,
        "scheduler_enabled": False,
        "worker_enabled": False,
        "account_data_accessed": False,
        "orders_or_positions_accessed": False,
        "market_watch_modified_by_script": False,
        "files_written": 0,
        "new_cost_brl": 0,
        "research_only": True,
    }


def _valid_closed_candle(
    rows: Any, *, expected_utc: datetime, digits: int,
) -> tuple[Any, Any, Any, Any] | None:
    if rows is None or len(rows) != 1:
        return None
    try:
        item = rows[0]
        stamp = _integer(item["time"], strictly_positive=True)
        if stamp != int(expected_utc.timestamp()):
            return None
        o, h, lo, close = tuple(
            _price(item[k], quote_digits=digits)[0]
            for k in ("open", "high", "low", "close")
        )
        if not (lo <= min(o, close) <= max(o, close) <= h):
            return None
        if _integer(item["tick_volume"], strictly_positive=True) <= 0:
            return None
        if _integer(item["spread"], strictly_positive=False) < 0:
            return None
        _integer(item["real_volume"], strictly_positive=False)
        return (o, h, lo, close)
    except (KeyError, IndexError, TypeError, ValueError, OverflowError):
        return None


def inspect_fx28_native_w1_vs_ny17_close_lab(
    api: Any, *, terminal_path: Any, now_utc: Any,
) -> dict[str, Any]:
    out = _blocked("INVALID_TERMINAL_OR_WALL_CLOCK")
    if not _terminal_path_ok(terminal_path):
        return out
    if (not isinstance(now_utc, datetime) or now_utc.tzinfo is None
            or now_utc.utcoffset() is None or now_utc.microsecond):
        return out
    now = now_utc.astimezone(timezone.utc)
    if len(FX_28) != 28 or len(set(FX_28)) != 28:
        out["reason"] = "CANONICAL_FX28_UNIVERSE_CHANGED"
        return out
    # The *latest* late-Friday 23:45 UTC bar closes at Saturday 00 UTC.
    latest_closed = datetime(2026, 11, 7, 0, tzinfo=timezone.utc)
    if now < latest_closed:
        out["reason"] = "W1_NATIVE_OR_M15_WINDOW_NOT_YET_CLOSED"
        return out

    weeks = {}
    for key, (begin, ny_end, last_bar) in WEEKS.items():
        native_stamp = datetime.fromisoformat(key + "T00:00:00+00:00")
        ny17_end = datetime.fromisoformat(ny_end)
        bar_before_ny17 = ny17_end - timedelta(minutes=15)
        later_bar = datetime.fromisoformat(last_bar)
        late_close = later_bar + timedelta(minutes=15)
        delay = int((late_close - ny17_end).total_seconds() // 60)
        if (native_stamp.utcoffset() != timedelta()
                or begin not in (
                    "2026-10-25T21:00:00+00:00",
                    "2026-11-01T22:00:00+00:00")
                or delay not in (120, 180)
                or late_close.hour != 0 or late_close.minute != 0):
            out["reason"] = "FROZEN_W1_NY17_BROKER_TIME_ANCHOR_CONTRACT_CHANGED"
            return out
        weeks[key] = (native_stamp, bar_before_ny17, later_bar, delay)

    try:
        online = api.initialize(path=terminal_path, timeout=10000)
    except (AttributeError, OSError, RuntimeError, TypeError, ValueError):
        out["reason"] = "MT5_INITIALIZATION_EXCEPTION"
        return out
    if not online:
        out["reason"] = "MT5_TERMINAL_DISCONNECTED"
        return out

    try:
        terminal = api.terminal_info()
        if terminal is None or terminal.connected is not True:
            out["reason"] = "MT5_TERMINAL_DISCONNECTED"
            return out

        for week, (native_stamp, ny17_bar, late_bar, delay) in weeks.items():
            matched_late, matched_ny, unlike_ny = 0, 0, 0
            for sym in FX_28:
                info = api.symbol_info(sym)
                if info is None or type(getattr(info, "visible", None)) is not bool:
                    out["reason"] = "SYMBOL_MISSING_OR_VISIBILITY_UNVERIFIABLE"
                    out["pairs_with_incomplete_or_bad_native_data"].append(sym)
                    return out
                spec = _symbol_spec_for_capture(info, sym)
                if spec is None:
                    out["reason"] = "CANONICAL_SYMBOL_PRICE_GRID_INVALID"
                    out["pairs_with_incomplete_or_bad_native_data"].append(sym)
                    return out
                digits = spec["digits_claim"]
                # All three reads are bounded and belong to long CLOSED
                # historical windows, not to forecasts or future prices.
                weekly_rows = api.copy_rates_range(
                    sym, api.TIMEFRAME_W1, native_stamp, native_stamp)
                ny17_rows = api.copy_rates_range(
                    sym, api.TIMEFRAME_M15, ny17_bar, ny17_bar)
                late_rows = api.copy_rates_range(
                    sym, api.TIMEFRAME_M15, late_bar, late_bar)
                after = api.symbol_info(sym)
                if (after is None or type(getattr(after, "visible", None)) is not bool
                        or after.visible != info.visible):
                    out["reason"] = "MARKET_WATCH_VISIBILITY_CHANGED"
                    out["pairs_with_incomplete_or_bad_native_data"].append(sym)
                    return out

                w = _valid_closed_candle(
                    weekly_rows, expected_utc=native_stamp, digits=digits)
                n = _valid_closed_candle(
                    ny17_rows, expected_utc=ny17_bar, digits=digits)
                l = _valid_closed_candle(
                    late_rows, expected_utc=late_bar, digits=digits)
                if w is None or n is None or l is None:
                    out["reason"] = "ONE_OR_MORE_NATIVE_W1_NY17_M15_CANDLES_INVALID"
                    out["pairs_with_incomplete_or_bad_native_data"].append(sym)
                    return out

                same_late = w[3] == l[3]
                same_ny17 = w[3] == n[3]
                matched_late += int(same_late)
                matched_ny += int(same_ny17)
                unlike_ny += int(not same_ny17)

            out["weekly_diagnostics"][week] = {
                "pairs_examined": 28,
                "native_w1_timestamp_utc": native_stamp.isoformat(),
                "ny17_last_m15_open_utc": ny17_bar.isoformat(),
                "late_friday_last_m15_open_utc": late_bar.isoformat(),
                "native_w1_candidate_late_close_offset_after_ny17_minutes": delay,
                "native_close_equals_late_friday_m15_count": matched_late,
                "native_close_equals_ny17_m15_count": matched_ny,
                "native_close_differs_from_ny17_m15_count": unlike_ny,
                "price_difference_direction_not_economic_forecast": True,
                "native_bar_not_ny17_label": True,
            }
            out["week_count"] += 1
            out["pair_week_comparisons"] += 28
            out["native_w1_close_equals_late_friday_m15"] += matched_late
            out["native_w1_close_equals_ny17_m15"] += matched_ny
            out["native_w1_disagrees_with_ny17_pair_weeks"] += unlike_ny

        out["state"] = "LAB_FX28_W1_CLOSE_REFERENCE_MISMATCH_DOCUMENTED_NO_GO"
        out["reason"] = "NATIVE_W1_CLOSE_ANCHOR_NOT_NY17_LABEL_NO_FORECAST_OR_TRADING"
        out["native_w1_sunday_utc_midnight_stamps_verified_locally"] = True
        out["all_comparisons_structurally_available"] = True
        return out
    except (AttributeError, IndexError, KeyError, TypeError, ValueError,
            OSError, RuntimeError, OverflowError):
        out["reason"] = "MT5_READONLY_PRICE_ANCHOR_QUERY_EXCEPTION"
        return out
    finally:
        try:
            api.shutdown()
        except (AttributeError, RuntimeError, OSError, TypeError, ValueError):
            out["state"] = "LAB_FX28_NATIVE_W1_NY17_ANCHOR_BLOCKED"
            out["reason"] = "MT5_SHUTDOWN_ERROR"
        if out["state"] == "LAB_FX28_NATIVE_W1_NY17_ANCHOR_BLOCKED":
            # Never present partial cohort results as a valid comparison.
            out["week_count"] = 0
            out["pair_week_comparisons"] = 0
            out["native_w1_close_equals_late_friday_m15"] = 0
            out["native_w1_close_equals_ny17_m15"] = 0
            out["native_w1_disagrees_with_ny17_pair_weeks"] = 0
            out["weekly_diagnostics"] = {}
            out["all_comparisons_structurally_available"] = False


def main() -> int:
    ap = argparse.ArgumentParser(
        description="LAB: check 28 native W1 close anchors vs NY17 M15, no trades")
    ap.add_argument("--terminal-path", required=True)
    args = ap.parse_args()
    try:
        import MetaTrader5 as mt5
    except ImportError:
        print("LAB_BLOCKED: MetaTrader5 Python package absent")
        return 2
    r = inspect_fx28_native_w1_vs_ny17_close_lab(
        mt5, terminal_path=args.terminal_path,
        now_utc=datetime.now(timezone.utc).replace(microsecond=0))
    print(json.dumps(r, indent=2, sort_keys=True, ensure_ascii=False))
    return 0 if r["all_comparisons_structurally_available"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
