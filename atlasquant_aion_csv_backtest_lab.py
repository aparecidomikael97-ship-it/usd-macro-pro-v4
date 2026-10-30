"""A277 LAB: manual-plan historical CSV backtest with a sealed holdout boundary.

Never generates a signal, fetches market data, infers live evidence, executes
orders or promotes P0 authority. All plans are supplied by a human and are
unattested, including their point-in-time provenance.
"""
from __future__ import annotations

from datetime import datetime, timezone
import math
from typing import Any

import pandas as pd

from atlasquant_aion_historical_csv import import_historical_csv
from atlasquant_operational_backtest import backtest_signal, summarize_results

SCHEMA = "ATLASQUANT_AION_CSV_MANUAL_BACKTEST_LAB_V1"
SETUPS = frozenset(("FVG", "OB", "PULLBACK"))
PLAN_FIELDS = frozenset(("signal_time", "setup", "side", "entry", "stop", "target"))
MAX_PLANS = 200
MIN_SEGMENT_BARS = 3
MIN_SAMPLE_TRADES = 30
MAX_WINDOW_BARS = 240


def _base() -> dict:
    return {
        "schema": SCHEMA,
        "status": "INVALID_OR_UNATTESTED_BACKTEST_INPUT",
        "valid": False,
        "error": "INVALID_INPUT",
        "research_only": True,
        "signal_generation": False,
        "manual_plans_unattested": True,
        "holdout_is_independently_attested": False,
        "no_live_gate_effect": True,
        "no_orders": True,
        "no_alerts": True,
        "no_new_data_calls": True,
        "authorizes_send": False,
        "p0_homologated": 0,
        "train": None,
        "holdout": None,
        "raw_csv_sha256": None,
    }


def _time(value: Any) -> datetime | None:
    if type(value) is not str:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            return None
        return parsed.astimezone(timezone.utc)
    except (ValueError, OverflowError):
        return None


def _positive_number(value: Any) -> float | None:
    if type(value) not in (int, float) or value <= 0:
        return None
    try:
        return float(value) if math.isfinite(value) else None
    except (OverflowError, ValueError):
        return None


def _friction(value: Any) -> float | None:
    if type(value) not in (int, float) or value < 0:
        return None
    try:
        return float(value) if math.isfinite(value) and value <= 5 else None
    except (OverflowError, ValueError):
        return None


def _plans(raw: Any, *, all_times: set[str]) -> list[dict] | None:
    if type(raw) is not list or len(raw) > MAX_PLANS:
        return None
    out = []
    seen = set()
    for item in raw:
        if type(item) is not dict or set(item) != PLAN_FIELDS:
            return None
        dt = _time(item["signal_time"])
        setup, side = item["setup"], item["side"]
        if (dt is None or dt.isoformat() not in all_times
                or type(setup) is not str or setup not in SETUPS
                or type(side) is not str or side not in ("BUY", "SELL")):
            return None
        levels = [_positive_number(item[key]) for key in ("entry", "stop", "target")]
        if any(n is None for n in levels):
            return None
        entry, stop, target = levels
        if (side == "BUY" and not stop < entry < target) or (
                side == "SELL" and not target < entry < stop):
            return None
        identifier = (dt.isoformat(), setup, side, entry, stop, target)
        if identifier in seen:
            return None
        seen.add(identifier)
        out.append({
            "signal_time": dt.isoformat(), "setup": setup, "side": side,
            "entry": entry, "stop": stop, "target": target,
        })
    return sorted(out, key=lambda p: (p["signal_time"], p["setup"], p["side"]))


def _report_row(raw: dict, *, timeframe: str, symbol: str) -> dict:
    keys = (
        "status", "outcome", "reason", "setup", "side", "signal_time",
        "entry_time", "exit_time", "gross_r", "cost_r", "slippage_r",
        "total_friction_r", "net_r", "bars_waited", "bars_held",
        "same_bar_ambiguous",
    )
    values = {}
    for key in keys:
        item = raw.get(key)
        if isinstance(item, (pd.Timestamp, datetime)):
            item = item.isoformat()
        values[key] = item
    return {"symbol": symbol, "timeframe": timeframe, **values}


def _sum(rows: list[dict], name: str) -> float:
    return round(sum(float(row[name]) for row in rows
                     if type(row.get(name)) in (float, int)), 6)


def _diagnostic(rows: list[dict]) -> dict:
    summary = summarize_results(rows)
    trades = summary["trades"]
    return {
        **summary,
        "gross_r": _sum(rows, "gross_r"),
        "cost_r": _sum(rows, "cost_r"),
        "slippage_r": _sum(rows, "slippage_r"),
        "sample_status": ("INSUFFICIENT_SAMPLE" if trades < MIN_SAMPLE_TRADES
                          else "DESCRIPTIVE_ONLY_NO_PREDICTION"),
    }


def _friction_scenarios(rows: list[dict], cost: float, slip: float) -> list[dict]:
    executed = [row for row in rows if type(row.get("gross_r")) in (int, float)
                and type(row.get("net_r")) in (int, float)]
    return [
        {
            "scenario": name,
            "assumed_cost_r": round(c, 6),
            "assumed_slippage_r": round(s, 6),
            "executed_trades": len(executed),
            "net_r": round(sum(float(row["gross_r"]) - c - s
                               for row in executed), 6),
            "historical_only": True,
        }
        for name, c, s in (
            ("ZERO_FRICTION", 0.0, 0.0),
            ("CONFIGURED", cost, slip),
            ("STRESS_X2", 2 * cost, 2 * slip),
        )
    ]


def _segment(
    candles: list[dict], plans: list[dict], *, symbol: str, timeframe: str,
    cost: float, slippage: float, max_wait: int, max_hold: int,
) -> dict:
    frame = pd.DataFrame(candles)
    rows = []
    busy_until = None
    censored_active = False
    for plan in plans:
        stamp = _time(plan["signal_time"])
        if censored_active or (busy_until is not None and stamp <= busy_until):
            rows.append(_report_row({
                **plan, "status": "OVERLAP_BLOCKED",
                "reason": ("UNRESOLVED_PRIOR_POSITION" if censored_active
                           else "SINGLE_POSITION_PER_ASSET"),
                "outcome": "NO_TRADE", "net_r": None,
            }, timeframe=timeframe, symbol=symbol))
            continue
        engine_plan = {**plan, "pair": symbol, "timeframe": timeframe,
                       "source": "A277_MANUAL_UNATTESTED"}
        result = backtest_signal(
            frame, engine_plan, max_wait_bars=max_wait,
            max_hold_bars=max_hold, cost_r=cost, slippage_r=slippage,
            start_after_signal_bar=True, require_alignment=False,
        )
        status = result.get("status")
        if status == "TIME_EXIT" and result.get("bars_held", 0) < max_hold:
            # At the holdout/train boundary, the exit is UNKNOWN. Exclude
            # the provisional engine mark-to-market; block later plans.
            result.update({
                "status": "CENSORED_AT_PARTITION_END",
                "outcome": "NO_TRADE", "reason": "HOLD_WINDOW_NOT_OBSERVED",
                "net_r": None, "gross_r": None,
                "cost_r": None, "slippage_r": None,
                "total_friction_r": None, "exit_time": None,
            })
            censored_active = True
        elif status not in (
            "TARGET", "STOP", "AMBIGUOUS_SAME_BAR_STOP_FIRST",
            "TIME_EXIT", "NO_ENTRY", "NO_FUTURE_DATA",
        ):
            # A new/unknown engine result is not silently treated as proof.
            result.update({
                "status": "UNRECOGNIZED_ENGINE_RESULT", "outcome": "NO_TRADE",
                "reason": "ENGINE_CONTRACT_MISMATCH", "net_r": None,
                "gross_r": None, "cost_r": None, "slippage_r": None,
            })
            censored_active = True
        elif result.get("net_r") is not None:
            busy_until = _time(result.get("exit_time"))
        rows.append(_report_row(result, timeframe=timeframe, symbol=symbol))

    months = sorted({row["datetime"][:7] for row in candles})
    monthly = []
    for month in months:
        # Filled exits belong to the exit month. No-trades/censored plans
        # belong to the month of the manual signal.
        group = [row for row in rows
                 if (row["exit_time"] or row["signal_time"])[:7] == month]
        monthly.append({"month_utc": month, **_diagnostic(group)})
    setups = [
        {"setup": setup, **_diagnostic([r for r in rows if r["setup"] == setup])}
        for setup in sorted(SETUPS)
    ]
    return {
        "candle_count": len(candles),
        "first_closed_at": candles[0]["datetime"],
        "last_closed_at": candles[-1]["datetime"],
        "summary": _diagnostic(rows),
        "monthly_utc": monthly,
        "setups": setups,
        "friction_scenarios": _friction_scenarios(rows, cost, slippage),
        "ledger": rows,
        "censored_trades": sum(r["status"] == "CENSORED_AT_PARTITION_END"
                              for r in rows),
    }


def research_backtest_csv(
    csv_text: Any, *, symbol: Any, timeframe: Any,
    timestamp_basis: Any, now: Any, validation_start: Any,
    manual_plans: Any, cost_r: Any, slippage_r: Any,
    max_wait_bars: Any = 8, max_hold_bars: Any = 96,
) -> dict:
    """Historical manual plans only; declared holdout cannot leak train exits.

    This does not assess when a human created the plan; the OOS label is only
    a chronological split, not independent out-of-sample attestation.
    """
    result = _base()
    cost, slip = _friction(cost_r), _friction(slippage_r)
    if cost is None or slip is None:
        result["error"] = "INVALID_COST_OR_SLIPPAGE_R"
        return result
    if (type(max_wait_bars) is not int or type(max_hold_bars) is not int
            or not 1 <= max_wait_bars <= MAX_WINDOW_BARS
            or not 1 <= max_hold_bars <= MAX_WINDOW_BARS):
        result["error"] = "INVALID_WAIT_OR_HOLD_WINDOW"
        return result

    parsed = import_historical_csv(
        csv_text, symbol=symbol, timeframe=timeframe,
        timestamp_basis=timestamp_basis, now=now,
    )
    if not parsed["valid"]:
        result["error"] = "INVALID_HISTORICAL_CSV:" + parsed["error"]
        return result
    candles = parsed["candles"]
    all_times = {row["datetime"] for row in candles}
    boundary = _time(validation_start)
    if boundary is None or boundary.isoformat() not in all_times:
        result["error"] = "INVALID_HOLDOUT_BOUNDARY"
        return result
    train = [c for c in candles if c["datetime"] < boundary.isoformat()]
    holdout = [c for c in candles if c["datetime"] >= boundary.isoformat()]
    if len(train) < MIN_SEGMENT_BARS or len(holdout) < MIN_SEGMENT_BARS:
        result["error"] = "INSUFFICIENT_SPLIT_CANDLES"
        return result
    plans = _plans(manual_plans, all_times=all_times)
    if plans is None:
        result["error"] = "INVALID_MANUAL_PLANS"
        return result

    train_times = {c["datetime"] for c in train}
    train_plans = [p for p in plans if p["signal_time"] in train_times]
    holdout_plans = [p for p in plans if p["signal_time"] not in train_times]
    result.update({
        "status": "HISTORICAL_MANUAL_BACKTEST_UNATTESTED",
        "valid": True, "error": None,
        "symbol": symbol, "timeframe": timeframe,
        "validation_start_utc": boundary.isoformat(),
        "raw_csv_sha256": parsed["raw_csv_sha256"],
        "normalized_candles_sha256": parsed["normalized_candles_sha256"],
        "time_basis": timestamp_basis,
        "assumed_cost_r": cost, "assumed_slippage_r": slip,
        "no_lookahead_execution": True,
        "single_position_per_asset": True,
        "train": _segment(train, train_plans, symbol=symbol, timeframe=timeframe,
                          cost=cost, slippage=slip,
                          max_wait=max_wait_bars, max_hold=max_hold_bars),
        "holdout": _segment(holdout, holdout_plans, symbol=symbol, timeframe=timeframe,
                            cost=cost, slippage=slip,
                            max_wait=max_wait_bars, max_hold=max_hold_bars),
    })
    return result


__all__ = ["SCHEMA", "SETUPS", "MAX_PLANS", "research_backtest_csv"]
