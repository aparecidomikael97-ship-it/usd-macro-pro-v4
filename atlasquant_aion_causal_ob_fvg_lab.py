"""A281 LAB: mechanical, prefix-only Order Block proxy and FVG priority.

A selected opposite candle before a confirmed BOS is NOT proof of an
institutional Order Block. Priority is a fixed presentation/research rule,
not proof that FVG is statistically more precise. No live orders or alerts.
"""
from __future__ import annotations

import hashlib
import json
import math
from typing import Any

from atlasquant_aion_historical_csv import import_historical_csv
from atlasquant_aion_causal_structure_lab import generate_causal_structure_csv
from atlasquant_aion_csv_backtest_lab import MAX_PLANS, research_backtest_csv

SCHEMA = "ATLASQUANT_AION_CAUSAL_OB_FVG_PRIORITY_LAB_V1"
OPPOSITE_LOOKBACK_BARS = 5
OB_STOP_BUFFER_RANGE = 0.10
REWARD_R = 2.0
NEAR_ZONE_FRACTION = 0.10
SPEC = {
    "version": "A281_OB_PROXY_ON_CONFIRMED_BOS_V1",
    "opposite_candle_lookback": OPPOSITE_LOOKBACK_BARS,
    "ob_zone": "FULL_HIGH_LOW_OF_LAST_OPPOSITE_BODY_CANDLE",
    "stop_buffer_of_ob_range": OB_STOP_BUFFER_RANGE,
    "target_r": REWARD_R,
    "priority": "FVG_IF_OVERLAPPING_OR_NEAR_AT_SAME_SIGNAL_CLOSE",
    "near_zone_fraction_of_narrower_zone": NEAR_ZONE_FRACTION,
    "no_retroactive_suppression": True,
    "no_external_institutional_validation": True,
}


def _hash(value: dict) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"),
                     ensure_ascii=True, allow_nan=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _base() -> dict:
    return {
        "schema": SCHEMA, "valid": False, "error": "INVALID_INPUT",
        "status": "INVALID_OB_FVG_RESEARCH_INPUT",
        "strategy_spec_sha256": _hash(SPEC),
        "ob_audit": [], "combined_candidate_plans": [],
        "combined_candidate_count": 0,
        "research_only": True, "historical_only": True,
        "ob_is_institutionally_verified": False,
        "fvg_superiority_proven": False,
        "plans_captured_when_generated": False,
        "no_retroactive_signal_repainting": True,
        "no_external_market_attestation": True,
        "no_new_data_calls": True, "no_orders": True, "no_alerts": True,
        "authorizes_send": False, "p0_homologated": 0,
    }


def _near(first: tuple[float, float], second: tuple[float, float]) -> bool:
    a_low, a_high = first
    b_low, b_high = second
    separation = max(a_low - b_high, b_low - a_high, 0.0)
    width = min(a_high - a_low, b_high - b_low)
    return bool(math.isfinite(separation) and math.isfinite(width)
                and width > 0 and separation <= width * NEAR_ZONE_FRACTION)


def generate_causal_ob_fvg_csv(
    csv_text: Any, *, symbol: Any, timeframe: Any,
    timestamp_basis: Any, now: Any,
) -> dict:
    """Propose OB only on a confirmed BOS, then suppress same-bar collision."""
    output = _base()
    history = import_historical_csv(
        csv_text, symbol=symbol, timeframe=timeframe,
        timestamp_basis=timestamp_basis, now=now,
    )
    if not history["valid"]:
        output["error"] = "INVALID_HISTORICAL_CSV:" + history["error"]
        return output
    structure = generate_causal_structure_csv(
        csv_text, symbol=symbol, timeframe=timeframe,
        timestamp_basis=timestamp_basis, now=now,
    )
    if not structure["valid"]:
        output["error"] = "INVALID_STRUCTURE:" + structure["error"]
        return output
    if (history["normalized_candles_sha256"]
            != structure["normalized_candles_sha256"]):
        output["error"] = "INCONSISTENT_HISTORICAL_SOURCE"
        return output

    candles = history["candles"]
    fvg_plans = structure["filtered_candidate_plans"]
    fvg_by_time = {}
    for plan in fvg_plans:
        fvg_by_time.setdefault(plan["signal_time"], []).append(plan)
    retained_ob, audit = [], []
    missing_opposite, suppressed_by_fvg, invalid_derived = 0, 0, 0

    for event in structure["structure_events"]:
        if event["kind"] != "BOS":
            continue
        i = event["bar_index"]
        direction = "BUY" if event["direction"] == "UP" else "SELL"
        # The BOS candle is never eligible as the preceding opposite candle.
        chosen = None
        for j in range(i - 1, max(-1, i - OPPOSITE_LOOKBACK_BARS - 1), -1):
            opposite = candles[j]
            if ((direction == "BUY" and opposite["close"] < opposite["open"])
                    or (direction == "SELL" and opposite["close"] > opposite["open"])):
                chosen = (j, opposite)
                break
        if chosen is None:
            missing_opposite += 1
            audit.append({
                "signal_time": event["detected_at"],
                "status": "NO_OPPOSITE_BODY_IN_PAST_LOOKBACK",
                "accepted": False, "side": direction,
                "prefix_sha256": event["prefix_sha256"],
            })
            continue

        j, opposite = chosen
        low, high = opposite["low"], opposite["high"]
        width = high - low
        entry = low / 2.0 + high / 2.0
        buffer = width * OB_STOP_BUFFER_RANGE
        stop = low - buffer if direction == "BUY" else high + buffer
        risk = entry - stop if direction == "BUY" else stop - entry
        target = (entry + REWARD_R * risk if direction == "BUY"
                  else entry - REWARD_R * risk)
        if (not all(math.isfinite(v) and v > 0 for v in
                    (low, high, width, entry, stop, risk, target))
                or (direction == "BUY" and not stop < entry < target)
                or (direction == "SELL" and not target < entry < stop)):
            invalid_derived += 1
            audit.append({
                "signal_time": event["detected_at"],
                "status": "INVALID_DERIVED_OB_ZONE",
                "accepted": False, "side": direction,
                "prefix_sha256": event["prefix_sha256"],
            })
            continue

        same_bar_fvg = fvg_by_time.get(event["detected_at"], [])
        collision = False
        if i >= 2:
            fvg_zone = (
                (candles[i - 2]["high"], candles[i]["low"])
                if direction == "BUY" else
                (candles[i]["high"], candles[i - 2]["low"])
            )
            collision = any(
                fvg["side"] == direction and _near((low, high), fvg_zone)
                for fvg in same_bar_fvg
            )
        reason = ("FVG_PREFERRED_SAME_CLOSE_NEAR_ZONE" if collision
                  else "OB_PROXY_RETAINED")
        record = {
            "signal_time": event["detected_at"],
            "observed_closed_bars": i + 1,
            "opposite_candle_time": opposite["datetime"],
            "opposite_candle_index": j,
            "bos_confirmed_at": event["detected_at"],
            "side": direction,
            "zone_low": low, "zone_high": high,
            "prefix_sha256": event["prefix_sha256"],
            "status": reason, "accepted": not collision,
            "institutional_ob_verified": False,
        }
        audit.append(record)
        if collision:
            suppressed_by_fvg += 1
            continue
        retained_ob.append({
            "signal_time": event["detected_at"], "setup": "OB",
            "side": direction, "entry": entry,
            "stop": stop, "target": target,
        })

    combined = sorted(
        [*fvg_plans, *retained_ob],
        key=lambda x: (x["signal_time"], x["setup"], x["side"]),
    )
    if len(combined) > MAX_PLANS:
        output["error"] = "COMBINED_CANDIDATE_LIMIT"
        return output
    output.update({
        "valid": True, "error": None,
        "status": "MECHANICAL_OB_FVG_HISTORICAL_CANDIDATES_ONLY",
        "symbol": symbol, "timeframe": timeframe,
        "strategy_spec": dict(SPEC),
        "raw_csv_sha256": history["raw_csv_sha256"],
        "normalized_candles_sha256": history["normalized_candles_sha256"],
        "original_fvg_count": structure["original_fvg_candidate_count"],
        "bos_filtered_fvg_count": len(fvg_plans),
        "bos_events": sum(x["kind"] == "BOS" for x in structure["structure_events"]),
        "missing_opposite_body": missing_opposite,
        "invalid_ob_derived": invalid_derived,
        "ob_suppressed_by_same_close_fvg": suppressed_by_fvg,
        "ob_retained": len(retained_ob),
        "ob_audit": audit,
        "combined_candidate_plans": combined,
        "combined_candidate_count": len(combined),
        "structure_events": structure["structure_events"],
        "no_future_candles_used": True,
    })
    return output


def research_ob_fvg_backtest_csv(
    csv_text: Any, *, symbol: Any, timeframe: Any,
    timestamp_basis: Any, now: Any, validation_start: Any,
    cost_r: Any, slippage_r: Any,
    max_wait_bars: Any = 8, max_hold_bars: Any = 96,
) -> dict:
    """Research-only OB/FVG comparison through existing A277 holdout."""
    prepared = generate_causal_ob_fvg_csv(
        csv_text, symbol=symbol, timeframe=timeframe,
        timestamp_basis=timestamp_basis, now=now,
    )
    if not prepared["valid"]:
        return {
            **_base(), "error": prepared["error"],
            "train": None, "holdout": None,
        }
    result = research_backtest_csv(
        csv_text, symbol=symbol, timeframe=timeframe,
        timestamp_basis=timestamp_basis, now=now,
        validation_start=validation_start,
        manual_plans=prepared["combined_candidate_plans"],
        cost_r=cost_r, slippage_r=slippage_r,
        max_wait_bars=max_wait_bars, max_hold_bars=max_hold_bars,
    )
    result.update({
        "causal_ob_fvg_schema": SCHEMA,
        "strategy_spec_sha256": prepared["strategy_spec_sha256"],
        "combined_candidate_count": prepared["combined_candidate_count"],
        "bos_filtered_fvg_count": prepared["bos_filtered_fvg_count"],
        "ob_retained": prepared["ob_retained"],
        "ob_suppressed_by_same_close_fvg":
            prepared["ob_suppressed_by_same_close_fvg"],
        "ob_audit": prepared["ob_audit"],
        "ob_is_institutionally_verified": False,
        "fvg_superiority_proven": False,
        "plans_captured_when_generated": False,
        "no_orders": True, "no_alerts": True,
        "authorizes_send": False, "p0_homologated": 0,
    })
    return result


__all__ = [
    "SCHEMA", "SPEC", "generate_causal_ob_fvg_csv",
    "research_ob_fvg_backtest_csv",
]
