"""A280 LAB: causal, delayed swing confirmation and mechanical BOS/CHOCH.

This is NOT externally attested market structure, a reversal forecast, a
trade recommendation or a validated ICT classifier. Pivot j becomes known
only after 2 further closed candles. All state updates are prefix-only.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

from atlasquant_aion_historical_csv import import_historical_csv
from atlasquant_aion_causal_fvg_lab import generate_causal_fvg_csv
from atlasquant_aion_csv_backtest_lab import research_backtest_csv

SCHEMA = "ATLASQUANT_AION_CAUSAL_STRUCTURE_FILTER_LAB_V1"
PIVOT_LEFT = 2
PIVOT_RIGHT = 2
MAX_BOS_AGE_BARS = 8
GENESIS = "0" * 64
STRUCTURE_SPEC = {
    "version": "A280_DELAYED_PIVOT_BREAK_V1",
    "pivot_left_closed_bars": PIVOT_LEFT,
    "pivot_right_closed_bars": PIVOT_RIGHT,
    "break_condition": "CLOSE_CROSSES_CONFIRMED_UNBROKEN_SWING",
    "first_break": "INITIAL_BREAK",
    "same_direction": "BOS",
    "opposite_direction": "CHOCH",
    "fvg_filter": "LATEST_BOS_SAME_SIDE_WITHIN_8_BARS",
    "no_live_authority": True,
}


def _hash(value: dict) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"),
                     ensure_ascii=True, allow_nan=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _base() -> dict:
    return {
        "schema": SCHEMA,
        "valid": False, "error": "INVALID_INPUT",
        "status": "INVALID_CAUSAL_STRUCTURE_INPUT",
        "structure_spec_sha256": _hash(STRUCTURE_SPEC),
        "structure_events": [], "reversal_context_records": [],
        "filter_decisions": [], "filtered_candidate_plans": [],
        "filtered_candidate_count": 0,
        "research_only": True, "historical_only": True,
        "external_structure_attested": False,
        "actual_ict_structure_verified": False,
        "actual_fvg_validity_verified": False,
        "reversal_is_a_forecast": False,
        "no_future_pivot_confirmation": True,
        "plans_captured_when_generated": False,
        "no_new_data_calls": True, "no_orders": True, "no_alerts": True,
        "authorizes_send": False, "p0_homologated": 0,
    }


def _scan(candles: list[dict]) -> tuple[list[dict], list[dict], list[str]]:
    events = []
    last_high, last_low, last_direction = None, None, None
    latest_event = None
    latest_event_by_bar = []
    prefix_hashes = []
    prefix = GENESIS
    for i, bar in enumerate(candles):
        prefix = _hash({"previous_sha256": prefix, "candle": bar})
        prefix_hashes.append(prefix)
        # The pivot at i-2 is recognized only NOW, at the close of i.
        # No event at i may use a pivot first confirmed on i.
        if i >= PIVOT_LEFT + PIVOT_RIGHT:
            j = i - PIVOT_RIGHT
            window = candles[j - PIVOT_LEFT:j + PIVOT_RIGHT + 1]
            central = candles[j]
            if all(central["high"] > row["high"]
                   for k, row in enumerate(window) if k != PIVOT_LEFT):
                last_high = {
                    "price": central["high"], "pivot_index": j,
                    "pivot_time": central["datetime"],
                    "confirmed_index": i, "confirmed_at": bar["datetime"],
                    "broken": False,
                }
            if all(central["low"] < row["low"]
                   for k, row in enumerate(window) if k != PIVOT_LEFT):
                last_low = {
                    "price": central["low"], "pivot_index": j,
                    "pivot_time": central["datetime"],
                    "confirmed_index": i, "confirmed_at": bar["datetime"],
                    "broken": False,
                }

        prior_close = candles[i - 1]["close"] if i > 0 else None
        up = bool(
            prior_close is not None and last_high is not None
            and not last_high["broken"] and last_high["confirmed_index"] < i
            and prior_close <= last_high["price"] < bar["close"]
        )
        down = bool(
            prior_close is not None and last_low is not None
            and not last_low["broken"] and last_low["confirmed_index"] < i
            and bar["close"] < last_low["price"] <= prior_close
        )
        if up and down:
            # If two inconsistent swing levels cross simultaneously, do not
            # fabricate a structural direction from ambiguous evidence.
            latest_event_by_bar.append(None)
            latest_event = None
            last_direction = None
            continue
        if up or down:
            direction = "UP" if up else "DOWN"
            pivot = last_high if up else last_low
            pivot["broken"] = True
            kind = ("INITIAL_BREAK" if last_direction is None else
                    "BOS" if direction == last_direction else "CHOCH")
            event = {
                "kind": kind, "direction": direction,
                "detected_at": bar["datetime"], "bar_index": i,
                "observed_closed_bars": i + 1,
                "pivot_time": pivot["pivot_time"],
                "pivot_confirmed_at": pivot["confirmed_at"],
                "pivot_confirmed_index": pivot["confirmed_index"],
                "pivot_level": pivot["price"],
                "prefix_sha256": prefix,
                "no_future_confirmation": True,
            }
            events.append(event)
            latest_event = event
            last_direction = direction
        latest_event_by_bar.append(latest_event)
    return events, latest_event_by_bar, prefix_hashes


def generate_causal_structure_csv(
    csv_text: Any, *, symbol: Any, timeframe: Any,
    timestamp_basis: Any, now: Any,
) -> dict:
    """Add delayed pivots to causal A279 candidates; only BOS-aligned pass."""
    output = _base()
    history = import_historical_csv(
        csv_text, symbol=symbol, timeframe=timeframe,
        timestamp_basis=timestamp_basis, now=now,
    )
    if not history["valid"]:
        output["error"] = "INVALID_HISTORICAL_CSV:" + history["error"]
        return output
    fvg = generate_causal_fvg_csv(
        csv_text, symbol=symbol, timeframe=timeframe,
        timestamp_basis=timestamp_basis, now=now,
    )
    if not fvg["valid"]:
        output["error"] = "INVALID_CAUSAL_FVG:" + fvg["error"]
        return output
    candles = history["candles"]
    events, last_by_bar, prefixes = _scan(candles)
    if len(fvg["candidate_plans"]) != len(fvg["candidate_audit"]):
        output["error"] = "INCONSISTENT_FVG_AUDIT"
        return output
    by_time = {bar["datetime"]: i for i, bar in enumerate(candles)}
    plans, decisions = [], []

    for candidate, audit in zip(fvg["candidate_plans"], fvg["candidate_audit"]):
        i = by_time[candidate["signal_time"]]
        if prefixes[i] != audit["prefix_sha256"]:
            output["error"] = "INCONSISTENT_HISTORY_PREFIX"
            return output
        event = last_by_bar[i]
        direction = "UP" if candidate["side"] == "BUY" else "DOWN"
        if event is None:
            reason = "NO_CONFIRMED_BREAK"
        elif event["kind"] != "BOS":
            reason = "LATEST_STRUCTURE_NOT_BOS"
        elif event["direction"] != direction:
            reason = "BOS_DIRECTION_CONFLICT"
        elif i - event["bar_index"] > MAX_BOS_AGE_BARS:
            reason = "STALE_BOS"
        else:
            reason = "BOS_ALIGNED_FIXED_FILTER"
            plans.append(candidate)
        decisions.append({
            "signal_time": candidate["signal_time"],
            "side": candidate["side"],
            "accepted": reason == "BOS_ALIGNED_FIXED_FILTER",
            "reason": reason,
            "fvg_prefix_sha256": audit["prefix_sha256"],
            "last_structure_kind": event["kind"] if event else None,
            "last_structure_time": event["detected_at"] if event else None,
            "last_structure_direction": event["direction"] if event else None,
        })

    output.update({
        "valid": True, "error": None,
        "status": "MECHANICAL_STRUCTURE_FILTERED_HISTORICAL_ONLY",
        "symbol": symbol, "timeframe": timeframe,
        "structure_spec": dict(STRUCTURE_SPEC),
        "raw_csv_sha256": history["raw_csv_sha256"],
        "normalized_candles_sha256": history["normalized_candles_sha256"],
        "structure_events": events,
        "reversal_context_records": [x for x in events if x["kind"] == "CHOCH"],
        "filter_decisions": decisions,
        "original_fvg_candidate_count": fvg["candidate_count"],
        "filtered_candidate_plans": plans,
        "filtered_candidate_count": len(plans),
        "rejected_candidate_count": len(decisions) - len(plans),
        "last_prefix_sha256": prefixes[-1],
    })
    return output


def research_structure_filtered_backtest_csv(
    csv_text: Any, *, symbol: Any, timeframe: Any,
    timestamp_basis: Any, now: Any, validation_start: Any,
    cost_r: Any, slippage_r: Any,
    max_wait_bars: Any = 8, max_hold_bars: Any = 96,
) -> dict:
    """Run A277 offline only on causally filtered research candidates."""
    structure = generate_causal_structure_csv(
        csv_text, symbol=symbol, timeframe=timeframe,
        timestamp_basis=timestamp_basis, now=now,
    )
    if not structure["valid"]:
        return {
            **_base(), "error": structure["error"],
            "train": None, "holdout": None,
        }
    backtest = research_backtest_csv(
        csv_text, symbol=symbol, timeframe=timeframe,
        timestamp_basis=timestamp_basis, now=now,
        validation_start=validation_start,
        manual_plans=structure["filtered_candidate_plans"],
        cost_r=cost_r, slippage_r=slippage_r,
        max_wait_bars=max_wait_bars, max_hold_bars=max_hold_bars,
    )
    backtest.update({
        "causal_structure_schema": SCHEMA,
        "structure_spec_sha256": structure["structure_spec_sha256"],
        "structure_events": structure["structure_events"],
        "reversal_context_records": structure["reversal_context_records"],
        "filter_decisions": structure["filter_decisions"],
        "original_fvg_candidate_count": structure["original_fvg_candidate_count"],
        "filtered_candidate_count": structure["filtered_candidate_count"],
        "external_structure_attested": False,
        "actual_ict_structure_verified": False,
        "plans_captured_when_generated": False,
        "no_orders": True, "no_alerts": True,
        "authorizes_send": False, "p0_homologated": 0,
    })
    return backtest


__all__ = [
    "SCHEMA", "STRUCTURE_SPEC", "generate_causal_structure_csv",
    "research_structure_filtered_backtest_csv",
]
