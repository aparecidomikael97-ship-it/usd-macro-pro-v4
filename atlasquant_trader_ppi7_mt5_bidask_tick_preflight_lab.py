"""PPI7 local pre-event Bid/Ask tick quality sample; read only, LAB only.

Designed after AM12 observed 212 COPY_TICKS_INFO ticks in a 20-second
11-Nov-2026 pre-event analog. Historical terminal ticks are a *local claim*,
not independent broker attestation or proof of executable spread, commission,
fill, slippage, point-in-time access or macro prediction.

Only predeclared 10/11 Nov 2026 historical windows (13:29:50--13:30:10 UTC).
NO order/account/symbol_select, filesystem writes, workers or scheduling.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from statistics import median
from typing import Any, Callable
import argparse
import json

from atlasquant_mt5_xauusd_closedbar_capture_lab import _terminal_path_ok
from atlasquant_trader_ppi_mt5_m15_capture_lab import (
    _price, _symbol_spec_for_capture,
)
from atlasquant_trader_ppi_usd_fx_forward_reaction_lab import USD_FX

SCHEMA = "ATLASQUANT_PPI7_MT5_HISTORIC_BIDASK_TICK_QUALITY_LAB_V1"
ALLOWED_DAYS = frozenset(("2026-11-10", "2026-11-11"))
WINDOW_SECONDS = 20
MAX_TICKS_PER_PAIR = 5_000


def _base(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_HISTORIC_TICK_SAMPLE_BLOCKED",
        "reason": reason, "reference_day_utc": None,
        "window_open_utc": None, "window_end_utc": None,
        "expected_pairs": list(USD_FX), "pairs_checked": 0,
        "pairs_with_ticks": 0, "total_quote_snapshots": 0,
        "total_strictly_positive_spread_snapshots": 0,
        "total_zero_spread_snapshots": 0,
        "pair_results": {},
        "visible_state_unchanged": True,
        "all_pairs_had_ticks": False,
        "all_ticks_had_strictly_positive_spread": False,
        "sample_quote_coverage_near_both_endpoints": False,
        "historical_quotes_authenticated": False,
        "historical_first_available_instant_attested": False,
        "bidask_execution_spread_independently_verified": False,
        "commissions_or_swap_verified": False,
        "slippage_or_fill_verifiable": False,
        "cost_adjusted_forecast_or_reaction_ready": False,
        "price_direction_bias": "AGUARDAR",
        "calibrated_probability": None, "accuracy_validated": None,
        "file_writes": 0, "http_requests": 0,
        "account_info_accessed": False, "orders_positions_accessed": False,
        "market_watch_changed_by_script": False,
        "worker_enabled": False, "scheduler_enabled": False,
        "trade_authorized": False, "publishable": False,
        "new_cost_brl": 0, "research_only": True,
    }


def _milliseconds(value: Any) -> int:
    if isinstance(value, (bool, str, float)):
        raise ValueError("INVALID_TICK_EPOCH_MS")
    try:
        result = int(value)
        if result != value or not 1_500_000_000_000 <= result <= 2_000_000_000_000:
            raise ValueError("INVALID_TICK_EPOCH_MS")
        return result
    except (OverflowError, TypeError, ValueError) as exc:
        raise ValueError("INVALID_TICK_EPOCH_MS") from exc


def _tick_aggregate(
    ticks: Any, *, digits: int, start_ms: int, end_ms: int,
) -> dict[str, Any]:
    if ticks is None or not 1 <= len(ticks) <= MAX_TICKS_PER_PAIR:
        raise ValueError("MISSING_OR_OVERSIZED_HISTORIC_TICKS")
    point = Decimal(1).scaleb(-digits)
    previous = start_ms
    positive: list[int] = []
    zero_count = 0
    first_ms = last_ms = None
    for tick in ticks:
        try:
            epoch_ms = _milliseconds(tick["time_msc"])
            unix_sec = tick["time"]
            if (isinstance(unix_sec, (bool, str, float))
                    or int(unix_sec) != unix_sec
                    or epoch_ms // 1000 != int(unix_sec)
                    or not start_ms <= epoch_ms <= end_ms
                    or epoch_ms < previous):
                raise ValueError("TICK_TIME_ORDER_OR_WINDOW_INVALID")
            bid = _price(tick["bid"], quote_digits=digits)[0]
            ask = _price(tick["ask"], quote_digits=digits)[0]
        except (KeyError, IndexError, TypeError, OverflowError) as exc:
            raise ValueError("TICK_FIELD_MISSING_OR_INVALID") from exc
        if ask < bid:
            raise ValueError("CROSSED_BID_ASK_REJECTED")
        steps = (ask - bid) / point
        if steps != int(steps) or steps > 100_000:
            raise ValueError("INVALID_TICK_SPREAD_GRID")
        spread_points = int(steps)
        if spread_points == 0:
            zero_count += 1
        else:
            positive.append(spread_points)
        previous = epoch_ms
        if first_ms is None:
            first_ms = epoch_ms
        last_ms = epoch_ms

    return {
        "quote_snapshots": len(ticks),
        "positive_spread_snapshots": len(positive),
        "zero_spread_snapshots": zero_count,
        "minimum_positive_spread_points": min(positive) if positive else None,
        "median_positive_spread_points": median(positive) if positive else None,
        "maximum_positive_spread_points": max(positive) if positive else None,
        "first_quote_time_utc": datetime.fromtimestamp(
            first_ms / 1000, tz=timezone.utc).isoformat(timespec="milliseconds"),
        "last_quote_time_utc": datetime.fromtimestamp(
            last_ms / 1000, tz=timezone.utc).isoformat(timespec="milliseconds"),
        "near_both_boundaries_observed": (
            first_ms <= start_ms + 5_000 and last_ms >= end_ms - 5_000),
        "all_quote_spreads_strictly_positive": zero_count == 0,
        "spread_samples_are_not_verified_execution_costs": True,
        "raw_tick_prices_saved": False,
    }


def inspect_ppi7_historical_bidask_ticks_lab(
    api: Any, *, terminal_path: Any, reference_day: Any,
    clock: Callable[[], datetime],
) -> dict[str, Any]:
    out = _base("INVALID_TERMINAL_OR_HISTORIC_DAY")
    if (not _terminal_path_ok(terminal_path) or type(reference_day) is not str
            or reference_day not in ALLOWED_DAYS):
        return out
    try:
        now = clock()
        if (not isinstance(now, datetime) or now.tzinfo is None
                or now.utcoffset() is None or now.microsecond):
            out["reason"] = "INVALID_CURRENT_UTC_CLOCK"
            return out
        now = now.astimezone(timezone.utc)
        start = datetime.fromisoformat(
            reference_day + "T13:29:50+00:00")
        end = start + timedelta(seconds=WINDOW_SECONDS)
        if now < end:
            out["reason"] = "TICK_WINDOW_NOT_YET_CLOSED"
            return out
    except (ValueError, TypeError, OverflowError):
        out["reason"] = "INVALID_HISTORIC_REFERENCE_CLOCK"
        return out

    out["reference_day_utc"] = reference_day
    out["window_open_utc"] = start.isoformat()
    out["window_end_utc"] = end.isoformat()
    start_ms, end_ms = int(start.timestamp() * 1000), int(end.timestamp() * 1000)
    try:
        ok = api.initialize(path=terminal_path, timeout=10000)
    except (AttributeError, OSError, RuntimeError, ValueError, TypeError):
        out["reason"] = "MT5_INITIALIZE_EXCEPTION"
        return out
    if not ok:
        out["reason"] = "MT5_CONNECTION_NOT_AVAILABLE"
        return out
    try:
        terminal = api.terminal_info()
        if terminal is None or terminal.connected is not True:
            out["reason"] = "MT5_TERMINAL_DISCONNECTED"
            return out
        for sym in USD_FX:
            before = api.symbol_info(sym)
            if before is None or type(before.visible) is not bool:
                out["reason"] = "CANONICAL_SYMBOL_MISSING_OR_INVALID"
                out["failed_symbol"] = sym
                return out
            spec = _symbol_spec_for_capture(before, sym)
            if spec is None:
                out["reason"] = "CANONICAL_SYMBOL_SPEC_NOT_VALID"
                out["failed_symbol"] = sym
                return out
            ticks = api.copy_ticks_range(
                sym, start, end, api.COPY_TICKS_INFO)
            after = api.symbol_info(sym)
            if (after is None or type(after.visible) is not bool
                    or after.visible != before.visible):
                out["reason"] = "MARKET_WATCH_VISIBILITY_CHANGED_OR_UNREADABLE"
                out["visible_state_unchanged"] = False
                out["failed_symbol"] = sym
                return out
            try:
                sample = _tick_aggregate(
                    ticks, digits=spec["digits_claim"],
                    start_ms=start_ms, end_ms=end_ms)
            except (ValueError, TypeError, OverflowError) as exc:
                out["reason"] = "LOCAL_TICK_SAMPLE_INVALID:" + str(exc)[:85]
                out["failed_symbol"] = sym
                return out
            sample["visible_in_market_watch"] = before.visible
            out["pair_results"][sym] = sample
            out["pairs_checked"] += 1
            out["pairs_with_ticks"] += 1
            out["total_quote_snapshots"] += sample["quote_snapshots"]
            out["total_strictly_positive_spread_snapshots"] += sample[
                "positive_spread_snapshots"]
            out["total_zero_spread_snapshots"] += sample[
                "zero_spread_snapshots"]

        out["all_pairs_had_ticks"] = out["pairs_with_ticks"] == len(USD_FX)
        out["all_ticks_had_strictly_positive_spread"] = (
            out["total_zero_spread_snapshots"] == 0)
        out["sample_quote_coverage_near_both_endpoints"] = all(
            v["near_both_boundaries_observed"]
            for v in out["pair_results"].values())
        out["state"] = "LAB_REAL_LOCAL_BIDASK_TICK_SAMPLE_UNATTESTED"
        out["reason"] = "READ_ONLY_QUOTE_SAMPLE_NOT_EXECUTION_COST_OR_PIT_PROOF"
        return out
    except (AttributeError, OSError, RuntimeError, ValueError, TypeError):
        out["reason"] = "MT5_READONLY_TICK_QUERY_EXCEPTION"
        return out
    finally:
        try:
            api.shutdown()
        except (AttributeError, OSError, RuntimeError, ValueError, TypeError):
            out["state"] = "LAB_HISTORIC_TICK_SAMPLE_BLOCKED"
            out["reason"] = "MT5_SHUTDOWN_FAILED"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="PPI7 20-second historic bid/ask tick quality, no trades")
    parser.add_argument("--terminal-path", required=True)
    parser.add_argument("--reference-day", required=True,
                        choices=sorted(ALLOWED_DAYS))
    args = parser.parse_args()
    try:
        import MetaTrader5 as mt5  # optional after explicit invocation
    except ImportError:
        print("LAB_BLOCKED: MetaTrader5 Python package missing")
        return 2
    out = inspect_ppi7_historical_bidask_ticks_lab(
        mt5, terminal_path=args.terminal_path,
        reference_day=args.reference_day,
        clock=lambda: datetime.now(timezone.utc).replace(microsecond=0))
    print(json.dumps(out, ensure_ascii=False, sort_keys=True, indent=2))
    return 0 if out["state"] == "LAB_REAL_LOCAL_BIDASK_TICK_SAMPLE_UNATTESTED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
