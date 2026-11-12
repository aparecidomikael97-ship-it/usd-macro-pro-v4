"""PPI7 2026-11-13 pre/post 08:30 EST Bid/Ask quality contrast (LAB).

No prediction, PPI actual publication verification, execution cost or trades.
This manual, one-shot, no-files/no-account adapter compares 20 seconds of
Bid/Ask BEFORE and AFTER the frozen 13:30 UTC event boundary. It reuses the
bounded, tick-precision/time validated reader in PR #1896. Nov 10/11
are explicitly historical analog checks; Nov 13 is the planned PPI window.
Neither a time gate nor quote availability proves that BLS published the
release then, nor that these quotes were executable or first-seen then.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import json
from typing import Any, Callable

from atlasquant_mt5_xauusd_closedbar_capture_lab import _terminal_path_ok
from atlasquant_trader_ppi_usd_fx_forward_reaction_lab import EVENT_UTC, USD_FX
from atlasquant_trader_ppi_mt5_m15_capture_lab import _symbol_spec_for_capture
from atlasquant_trader_ppi7_mt5_bidask_tick_preflight_lab import (
    _tick_aggregate,
)

SCHEMA = "ATLASQUANT_TRADER_PPI7_PRE_POST_EVENT_BIDASK_BLACKOUT_LAB_V1"
ANALOG_DAYS = frozenset(("2026-11-10", "2026-11-11"))
EVENT_DAY = "2026-11-13"
ALLOWED_DAYS = ANALOG_DAYS | {EVENT_DAY}
SAMPLE_SECONDS = 20
MIN_POSITIVE_QUOTE_SNAPSHOTS = 3
WIDENED_RATIO = Decimal("2")


def _base(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_PPI7_EVENT_BIDASK_BLOCKED",
        "reason": reason, "reference_day_utc": None,
        "research_window_kind": None,
        "scheduled_ppi_time_utc": EVENT_UTC.isoformat(),
        "before_window_utc": None, "after_window_utc": None,
        "expected_pairs": list(USD_FX), "pair_results": {},
        "pairs_with_complete_local_samples": 0,
        "before_quote_snapshots": 0, "after_quote_snapshots": 0,
        "before_zero_spread_snapshots": 0, "after_zero_spread_snapshots": 0,
        "observed_sample_widened_2x_pair_count": None,
        "pairs_insufficient_for_ratio": [],
        "all_pairs_have_complete_20s_boundaries": False,
        "no_event_time_lookahead": False,
        "official_ppi_actual_authenticated": False,
        "broker_quote_origin_independently_authenticated": False,
        "quotes_original_first_availability_independently_attested": False,
        "execution_spread_commission_slippage_verified": False,
        "post_event_blackout_or_trade_signal_authorized": False,
        "price_direction_bias": "AGUARDAR",
        "directional_probability": None,
        "statistical_accuracy": None,
        "trade_authorized": False, "live_alert_allowed": False,
        "publishable": False, "worker_enabled": False,
        "scheduler_enabled": False, "file_writes": 0,
        "http_requests": 0, "new_cost_brl": 0,
        "account_accessed": False, "positions_orders_accessed": False,
        "market_watch_modified_by_script": False,
        "research_only": True,
    }


def _bounds(day: str) -> tuple[datetime, datetime, datetime, datetime, datetime]:
    """Two adjacent nonoverlapping 20-second windows, ms inclusive."""
    center = datetime.fromisoformat(f"{day}T13:30:00+00:00")
    before_start = center - timedelta(seconds=SAMPLE_SECONDS)
    before_end = center - timedelta(milliseconds=1)
    after_start = center
    after_end = center + timedelta(seconds=SAMPLE_SECONDS, milliseconds=-1)
    ready_at = center + timedelta(seconds=SAMPLE_SECONDS)
    return before_start, before_end, after_start, after_end, ready_at


def _aggregate_state(before: dict[str, Any],
                     after: dict[str, Any]) -> dict[str, Any]:
    """Spread ratio is descriptive *only* if both samples meet strict coverage."""
    a, b = before["median_positive_spread_points"], after["median_positive_spread_points"]
    qualifies = (
        before["near_both_boundaries_observed"]
        and after["near_both_boundaries_observed"]
        and before["positive_spread_snapshots"] >= MIN_POSITIVE_QUOTE_SNAPSHOTS
        and after["positive_spread_snapshots"] >= MIN_POSITIVE_QUOTE_SNAPSHOTS
        and a is not None and b is not None and a > 0
    )
    ratio = (Decimal(str(b)) / Decimal(str(a))) if qualifies else None
    return {
        "before_quote_snapshots": before["quote_snapshots"],
        "after_quote_snapshots": after["quote_snapshots"],
        "before_zero_spread_snapshots": before["zero_spread_snapshots"],
        "after_zero_spread_snapshots": after["zero_spread_snapshots"],
        "before_median_positive_spread_points": a,
        "after_median_positive_spread_points": b,
        "both_windows_near_boundaries": (
            before["near_both_boundaries_observed"]
            and after["near_both_boundaries_observed"]),
        "sample_spread_ratio_post_over_pre": (
            str(ratio.quantize(Decimal(".001"))) if ratio is not None else None),
        "observational_risk_state": (
            "POST_SAMPLE_SPREAD_AT_LEAST_2X_WIDER_NOT_TRADE_SIGNAL"
            if ratio is not None and ratio >= WIDENED_RATIO else
            "NO_2X_WIDENING_IN_LIMITED_SAMPLE_NOT_TRADE_SIGNAL"
            if ratio is not None else
            "INSUFFICIENT_SAMPLE_TO_COMPARE_SPREADS"
        ),
        "execution_cost_verified": False,
        "trade_or_signal_allowed": False,
        "actual_macro_surprise_inferred": False,
        "raw_bidask_quotes_saved": False,
    }


def inspect_ppi7_pre_post_bidask_lab(
    api: Any, *, terminal_path: Any, reference_day: Any,
    clock: Callable[[], datetime],
) -> dict[str, Any]:
    """Bounded read-only, manual event-window inspection, with strict time gate."""
    out = _base("INVALID_TERMINAL_OR_DECLARED_DAY")
    if (not _terminal_path_ok(terminal_path)
            or type(reference_day) is not str
            or reference_day not in ALLOWED_DAYS):
        return out
    try:
        now = clock()
        if (not isinstance(now, datetime) or now.tzinfo is None
                or now.utcoffset() is None or now.microsecond):
            out["reason"] = "INVALID_CAPTURE_CLOCK"
            return out
        now = now.astimezone(timezone.utc)
        before_start, before_end, after_start, after_end, ready = _bounds(reference_day)
        if reference_day == EVENT_DAY and after_start != EVENT_UTC:
            out["reason"] = "FROZEN_PPI_EVENT_CLOCK_MISMATCH"
            return out
        if now < ready:
            out["reason"] = "BOTH_PRE_AND_POST_WINDOWS_MUST_BE_CLOSED"
            return out
    except (TypeError, ValueError, OverflowError):
        out["reason"] = "WINDOW_OR_CLOCK_INVALID"
        return out

    out.update({
        "reference_day_utc": reference_day,
        "research_window_kind": (
            "FROZEN_PPI_EVENT_AFTER_CLOSE_UNATTESTED" if reference_day == EVENT_DAY
            else "PRE_EVENT_HISTORICAL_ANALOG_NOT_A_PPI_RELEASE"),
        "before_window_utc": [before_start.isoformat(), before_end.isoformat()],
        "after_window_utc": [after_start.isoformat(), after_end.isoformat()],
        "no_event_time_lookahead": True,
    })
    try:
        connected = api.initialize(path=terminal_path, timeout=10000)
    except (AttributeError, OSError, ValueError, RuntimeError, TypeError):
        out["reason"] = "MT5_INIT_EXCEPTION"
        return out
    if not connected:
        out["reason"] = "MT5_NOT_CONNECTED"
        return out

    try:
        terminal = api.terminal_info()
        if terminal is None or terminal.connected is not True:
            out["reason"] = "MT5_TERMINAL_DISCONNECTED"
            return out

        for sym in USD_FX:
            info = api.symbol_info(sym)
            if info is None or type(info.visible) is not bool:
                out["reason"] = "CANONICAL_SYMBOL_MISSING"
                out["failed_symbol"] = sym
                return out
            spec = _symbol_spec_for_capture(info, sym)
            if spec is None:
                out["reason"] = "CANONICAL_SYMBOL_METADATA_INVALID"
                out["failed_symbol"] = sym
                return out

            before_ticks = api.copy_ticks_range(
                sym, before_start, before_end, api.COPY_TICKS_INFO)
            after_ticks = api.copy_ticks_range(
                sym, after_start, after_end, api.COPY_TICKS_INFO)

            after_info = api.symbol_info(sym)
            if (after_info is None or type(after_info.visible) is not bool
                    or after_info.visible != info.visible):
                out["reason"] = "MARKET_WATCH_VISIBILITY_CHANGED_OR_UNKNOWN"
                out["failed_symbol"] = sym
                return out
            try:
                before = _tick_aggregate(
                    before_ticks, digits=spec["digits_claim"],
                    start_ms=int(before_start.timestamp() * 1000),
                    end_ms=int(before_end.timestamp() * 1000))
                after = _tick_aggregate(
                    after_ticks, digits=spec["digits_claim"],
                    start_ms=int(after_start.timestamp() * 1000),
                    end_ms=int(after_end.timestamp() * 1000))
            except (ValueError, TypeError, OverflowError) as exc:
                out["reason"] = "WINDOW_TICKS_FAILED_VALIDATION:" + str(exc)[:85]
                out["failed_symbol"] = sym
                return out
            details = _aggregate_state(before, after)
            details["market_watch_visible_before_and_after"] = info.visible
            out["pair_results"][sym] = details
            out["pairs_with_complete_local_samples"] += 1
            out["before_quote_snapshots"] += before["quote_snapshots"]
            out["after_quote_snapshots"] += after["quote_snapshots"]
            out["before_zero_spread_snapshots"] += before["zero_spread_snapshots"]
            out["after_zero_spread_snapshots"] += after["zero_spread_snapshots"]
            if details["sample_spread_ratio_post_over_pre"] is None:
                out["pairs_insufficient_for_ratio"].append(sym)
        out["all_pairs_have_complete_20s_boundaries"] = (
            out["pairs_with_complete_local_samples"] == len(USD_FX)
            and not out["pairs_insufficient_for_ratio"])
        # A missing/undercovered pair must NEVER look like zero widened
        # markets or an apparently complete cross-asset risk conclusion.
        if out["all_pairs_have_complete_20s_boundaries"]:
            out["observed_sample_widened_2x_pair_count"] = sum(
                row["observational_risk_state"].startswith("POST_SAMPLE_SPREAD_")
                for row in out["pair_results"].values())
        out["state"] = "LAB_PPI7_PRE_POST_BIDASK_QUALITY_DESCRIPTIVE_NO_GO"
        out["reason"] = "NOT_BLS_SURPRISE_OR_EXECUTION_COST_OR_SIGNAL"
        return out
    except (AttributeError, OSError, RuntimeError, ValueError, TypeError):
        out["reason"] = "MT5_READONLY_QUOTE_EXCEPTION"
        return out
    finally:
        try:
            api.shutdown()
        except (AttributeError, OSError, RuntimeError, ValueError, TypeError):
            out["state"] = "LAB_PPI7_EVENT_BIDASK_BLOCKED"
            out["reason"] = "MT5_SHUTDOWN_FAILED"
        if out["state"] == "LAB_PPI7_EVENT_BIDASK_BLOCKED":
            # Fail closed as a COHORT: partial first-six-pair stats are
            # diagnostic artifacts, not findings. Preserve failed_symbol and
            # the blocking reason but clear all partial success metrics.
            out["pair_results"] = {}
            out["pairs_with_complete_local_samples"] = 0
            out["before_quote_snapshots"] = 0
            out["after_quote_snapshots"] = 0
            out["before_zero_spread_snapshots"] = 0
            out["after_zero_spread_snapshots"] = 0
            out["observed_sample_widened_2x_pair_count"] = None
            out["pairs_insufficient_for_ratio"] = []
            out["all_pairs_have_complete_20s_boundaries"] = False


def main() -> int:
    parser = argparse.ArgumentParser(description=(
        "PPI7 research-only 20s before/after 13:30 UTC Bid/Ask (no trades)"))
    parser.add_argument("--terminal-path", required=True)
    parser.add_argument("--reference-day", required=True,
                        choices=sorted(ALLOWED_DAYS))
    args = parser.parse_args()
    try:
        import MetaTrader5 as mt5
    except ImportError:
        print("LAB_BLOCKED: MetaTrader5 Python package missing")
        return 2
    out = inspect_ppi7_pre_post_bidask_lab(
        mt5, terminal_path=args.terminal_path,
        reference_day=args.reference_day,
        clock=lambda: datetime.now(timezone.utc).replace(microsecond=0))
    print(json.dumps(out, sort_keys=True, indent=2, ensure_ascii=False))
    return 0 if out["state"] == "LAB_PPI7_PRE_POST_BIDASK_QUALITY_DESCRIPTIVE_NO_GO" else 2


if __name__ == "__main__":
    raise SystemExit(main())
