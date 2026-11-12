"""28-cross Forex NY17 W1 M15 coverage, shared-vs-pair gap audit (LAB).

The W1 retrospective benchmark calendar is FROZEN, including NY DST:
  2026-10-25 17 NY (EDT = 21Z) -> 2026-10-30 17 NY (EDT = 21Z)
  2026-11-01 17 NY (EST = 22Z) -> 2026-11-06 17 NY (EST = 22Z)

Strict naive NY17 5-day M15 grid = 480*28 slots. A missing candle
is an UNOBSERVED expected slot, NOT proof of a broker outage, market
closure, holiday, nor a price that should be forward-filled. Shared
gaps (all 28 symbols) are separated from pair-specific gaps, and no
shared gap is silently waived as an accepted trading-calendar holiday.

No orders, login, account, files, symbol_select, alerts, workers, deploy,
scheduler or statistical directional forecast. Explicit read-only CLI.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
import argparse
import json
from typing import Any, Callable

from atlasquant_instrument_registry import FX_28
from atlasquant_mt5_xauusd_closedbar_capture_lab import _terminal_path_ok
from atlasquant_trader_ppi_mt5_m15_capture_lab import _symbol_spec_for_capture
from atlasquant_trader_fx28_mt5_ny17_d1_gap_guard_lab import (
    _audit_rates, _utc_clock,
)

SCHEMA = "ATLASQUANT_TRADER_FX28_MT5_NY17_W1_SHARED_PAIR_GAP_AUDIT_LAB_V1"
W1_WINDOWS_UTC = {
    "2026-10-25": ("2026-10-25T21:00:00+00:00", "2026-10-30T21:00:00+00:00"),
    "2026-11-01": ("2026-11-01T22:00:00+00:00", "2026-11-06T22:00:00+00:00"),
}
W1_M15_COUNT = 480
MAX_REPORTED_MISSING_UTC = 8


def _empty(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_FX28_W1_READONLY_AUDIT_BLOCKED",
        "reason": reason, "reference_sunday_ny": None,
        "window_start_utc": None, "window_end_utc_exclusive": None,
        "calendar_definition": "FIXED_NY17_GRID_NOT_BROKER_TRADE_SESSIONS",
        "reference_market_schedule_independently_authenticated": False,
        "expected_pairs": 28, "expected_slots_per_pair": W1_M15_COUNT,
        "total_expected_m15_slots": 28 * W1_M15_COUNT,
        "pair_count_attempted": 0, "complete_480_pairs": 0,
        "pairs_with_observed_m15_gaps": [],
        "pair_diagnostics": {},
        "all_pairs_timeseries_structurally_valid": False,
        "all_expected_weekly_m15_slots_present": False,
        "missing_slots_total": None,
        "shared_missing_utc_slot_count": None,
        "shared_missing_utc_first": [],
        "shared_missing_pair_slots_total": None,
        "pair_specific_missing_slots_total": None,
        "pair_specific_missing_by_symbol": {},
        "max_missing_pairs_at_one_timestamp": None,
        "symbols_hidden_when_queried": [],
        "bounded_history_warmup_attempted": [],
        "no_candles_interpolated_or_forward_filled": True,
        "source_feed_independently_verified": False,
        "historic_first_seen_point_in_time_verified": False,
        "future_d1_w1_forecasts_preregistered": False,
        "validated_directional_accuracy": None,
        "calibrated_probability": None,
        "operational_bias": "AGUARDAR",
        "trade_authorized": False, "publishable": False,
        "live_alert_allowed": False, "scheduler_enabled": False,
        "worker_enabled": False, "new_cost_brl": 0,
        "files_written": 0, "account_accessed": False,
        "orders_positions_accessed": False,
        "market_watch_modified": False,
        "research_only": True,
    }


def inspect_fx28_w1_readonly_gap_audit_lab(
    api: Any, *, terminal_path: Any, reference_sunday_ny: Any,
    clock: Callable[[], datetime],
) -> dict[str, Any]:
    out = _empty("INVALID_W1_REFERENCE_OR_TERMINAL")
    if (not _terminal_path_ok(terminal_path)
            or type(reference_sunday_ny) is not str
            or reference_sunday_ny not in W1_WINDOWS_UTC
            or len(FX_28) != 28 or len(set(FX_28)) != 28):
        return out
    now = _utc_clock(clock())
    if now is None:
        out["reason"] = "INVALID_CAPTURE_EVALUATION_CLOCK"
        return out
    lo, hi = W1_WINDOWS_UTC[reference_sunday_ny]
    start = datetime.fromisoformat(lo)
    end = datetime.fromisoformat(hi)
    if end - start != timedelta(days=5):
        out["reason"] = "FROZEN_NY17_WEEK_BOUNDARY_INVALID"
        return out
    if now < end:
        out["reason"] = "W1_LAST_M15_CANDLE_NOT_YET_CLOSED"
        return out
    expected = tuple(int(start.timestamp()) + 900 * n
                     for n in range(W1_M15_COUNT))
    last_open = end - timedelta(minutes=15)
    out["reference_sunday_ny"] = reference_sunday_ny
    out["window_start_utc"] = start.isoformat()
    out["window_end_utc_exclusive"] = end.isoformat()

    try:
        init = api.initialize(path=terminal_path, timeout=10000)
    except (AttributeError, RuntimeError, OSError, ValueError, TypeError):
        out["reason"] = "MT5_INITIALIZE_EXCEPTION"
        return out
    if not init:
        out["reason"] = "MT5_TERMINAL_NOT_CONNECTED"
        return out

    missing_by_pair: dict[str, set[int]] = {}
    can_classify = True
    try:
        terminal = api.terminal_info()
        if terminal is None or terminal.connected is not True:
            out["reason"] = "MT5_TERMINAL_NOT_CONNECTED"
            return out

        for sym in FX_28:
            out["pair_count_attempted"] += 1
            before = api.symbol_info(sym)
            if before is None or type(getattr(before, "visible", None)) is not bool:
                can_classify = False
                out["pair_diagnostics"][sym] = {
                    "reason": "SYMBOL_MISSING_OR_VISIBILITY_UNVERIFIABLE",
                    "returned_bars": None}
                continue
            spec = _symbol_spec_for_capture(before, sym)
            if spec is None:
                can_classify = False
                out["pair_diagnostics"][sym] = {
                    "reason": "CANONICAL_SYMBOL_BASE_QUOTE_OR_TICK_INVALID",
                    "returned_bars": None}
                continue
            if not before.visible:
                out["symbols_hidden_when_queried"].append(sym)
            rates = api.copy_rates_range(sym, api.TIMEFRAME_M15, start, last_open)
            if rates is None or len(rates) != W1_M15_COUNT:
                # Exactly one bounded read-only cache warm-up.
                out["bounded_history_warmup_attempted"].append(sym)
                api.copy_rates_range(
                    sym, api.TIMEFRAME_M15, start - timedelta(days=7), last_open)
                rates = api.copy_rates_range(
                    sym, api.TIMEFRAME_M15, start, last_open)
            after = api.symbol_info(sym)
            if (after is None or type(getattr(after, "visible", None)) is not bool
                    or before.visible != after.visible):
                can_classify = False
                out["pair_diagnostics"][sym] = {
                    "reason": "MARKET_WATCH_VISIBILITY_CHANGED_OR_UNKNOWN",
                    "returned_bars": None}
                continue
            review = _audit_rates(rates, expected, spec["digits_claim"])
            valid = review["reason"] in (
                "COMPLETE_HISTORICAL_SERIES_UNATTESTED",
                "EXACT_M15_CANDLES_MISSING_NO_FILL",
            )
            review["visible_in_market_watch"] = before.visible
            out["pair_diagnostics"][sym] = review
            if not valid:
                can_classify = False
                continue

            times = {int(row["time"]) for row in rates}
            gaps = set(expected) - times
            missing_by_pair[sym] = gaps
            if gaps:
                out["pairs_with_observed_m15_gaps"].append(sym)
            else:
                out["complete_480_pairs"] += 1

        if not can_classify or len(missing_by_pair) != len(FX_28):
            out["reason"] = "UNVERIFIABLE_SYMBOL_OR_CANDLE_DATA_COHORT_NO_AGGREGATION"
            return out

        misses = Counter(t for gaps in missing_by_pair.values() for t in gaps)
        common = sorted(t for t, count in misses.items() if count == len(FX_28))
        shared = set(common)
        by_pair = {
            sym: len(missing_by_pair[sym] - shared) for sym in FX_28
        }
        total = sum(len(gaps) for gaps in missing_by_pair.values())
        isolated = sum(by_pair.values())
        if len(common) * 28 + isolated != total:
            out["reason"] = "SHARED_VS_PAIR_MISSING_COUNT_INCONSISTENT"
            return out
        out.update({
            "state": ("LAB_FX28_W1_NY17_FULL_GRID_HISTORY_ONLY_NO_GO"
                      if total == 0 else
                      "LAB_FX28_W1_NY17_SHARED_AND_PAIR_GAPS_NO_GO"),
            "reason": ("COMPLETE_LOCAL_WEEK_GRID_NO_BROKER_PIT_PROOF"
                       if total == 0 else
                       "MISSING_M15_SLOTS_NO_CALENDAR_EXEMPTION_OR_FILL"),
            "all_pairs_timeseries_structurally_valid": True,
            "all_expected_weekly_m15_slots_present": total == 0,
            "missing_slots_total": total,
            "shared_missing_utc_slot_count": len(common),
            "shared_missing_utc_first": [
                datetime.fromtimestamp(t, timezone.utc).isoformat()
                for t in common[:MAX_REPORTED_MISSING_UTC]],
            "shared_missing_pair_slots_total": len(common) * 28,
            "pair_specific_missing_slots_total": isolated,
            "pair_specific_missing_by_symbol": by_pair,
            "max_missing_pairs_at_one_timestamp": max(misses.values(), default=0),
        })
        return out
    except (AttributeError, IndexError, KeyError, OSError,
            RuntimeError, ValueError, TypeError, OverflowError):
        out["state"] = "LAB_FX28_W1_READONLY_AUDIT_BLOCKED"
        out["reason"] = "MT5_READONLY_W1_QUERY_OR_VALIDATION_EXCEPTION"
        return out
    finally:
        try:
            api.shutdown()
        except (AttributeError, OSError, RuntimeError, ValueError, TypeError):
            out["state"] = "LAB_FX28_W1_READONLY_AUDIT_BLOCKED"
            out["reason"] = "MT5_SHUTDOWN_FAILURE"
        if out["state"] == "LAB_FX28_W1_READONLY_AUDIT_BLOCKED":
            # Suppress any partial batch success on error.
            out["all_expected_weekly_m15_slots_present"] = False
            out["all_pairs_timeseries_structurally_valid"] = False
            out["shared_missing_utc_slot_count"] = None
            out["shared_missing_utc_first"] = []
            out["shared_missing_pair_slots_total"] = None
            out["pair_specific_missing_slots_total"] = None
            out["pair_specific_missing_by_symbol"] = {}
            out["max_missing_pairs_at_one_timestamp"] = None


def main() -> int:
    ap = argparse.ArgumentParser(
        description="AtlasQuant 28 FX closed NY17 W1 M15 gap research LAB")
    ap.add_argument("--terminal-path", required=True)
    ap.add_argument("--reference-sunday-ny", required=True,
                    choices=sorted(W1_WINDOWS_UTC))
    opts = ap.parse_args()
    try:
        import MetaTrader5 as mt5
    except ImportError:
        print("LAB_BLOCKED: MetaTrader5 package absent")
        return 2
    report = inspect_fx28_w1_readonly_gap_audit_lab(
        mt5, terminal_path=opts.terminal_path,
        reference_sunday_ny=opts.reference_sunday_ny,
        clock=lambda: datetime.now(timezone.utc).replace(microsecond=0))
    print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2))
    return 0 if report["all_expected_weekly_m15_slots_present"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
