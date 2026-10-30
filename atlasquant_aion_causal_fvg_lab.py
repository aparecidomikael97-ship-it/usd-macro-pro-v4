"""A279 LAB: causal, fixed-rule historical FVG candidate research.

A mechanical 3-candle gap is a *candidate*, NOT a proven/valid ICT FVG,
trade signal, reversal forecast, or live instruction. Every prefix checksum
and plan uses only candles closed at or before its signal candle.
No provider, external timestamp attestation, broker, Worker, or order.
"""
from __future__ import annotations

import hashlib
import json
import math
from typing import Any

from atlasquant_aion_historical_csv import import_historical_csv
from atlasquant_aion_csv_backtest_lab import MAX_PLANS, research_backtest_csv

SCHEMA = "ATLASQUANT_AION_CAUSAL_FVG_RESEARCH_LAB_V1"
STRATEGY_VERSION = "A279_FIXED_FVG_SMA5_V1"
SMA_BARS = 5
MIN_GAP_RANGE_RATIO = 0.15
TARGET_R = 2.0
GENESIS = "0" * 64
SPEC = {
    "version": STRATEGY_VERSION,
    "sma_bars": SMA_BARS,
    "gap_min_mean_range_ratio": MIN_GAP_RANGE_RATIO,
    "target_r": TARGET_R,
    "entry": "MIDPOINT_OF_3_CANDLE_GAP",
    "stop": "EXTREME_OF_LAST_3_CANDLES",
    "execution": "FIRST_ELIGIBLE_BAR_AFTER_CLOSED_SIGNAL",
    "no_adaptive_tuning": True,
}


def _hash(data: dict) -> str:
    return hashlib.sha256(json.dumps(
        data, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")).hexdigest()


def _base() -> dict:
    return {
        "schema": SCHEMA,
        "valid": False,
        "status": "INVALID_CAUSAL_RESEARCH_INPUT",
        "error": "INVALID_INPUT",
        "strategy_version": STRATEGY_VERSION,
        "strategy_spec_sha256": _hash(SPEC),
        "candidate_plans": [],
        "candidate_audit": [],
        "candidate_count": 0,
        "research_only": True,
        "historical_only": True,
        "source_is_externally_attested": False,
        "plan_capture_is_externally_attested": False,
        "algorithmic_causality_only": True,
        "no_future_candles_used_in_candidates": True,
        "not_tradeable_signals": True,
        "not_verified_ict_zones": True,
        "no_new_data_calls": True,
        "no_alerts": True,
        "no_orders": True,
        "authorizes_send": False,
        "p0_homologated": 0,
    }


def generate_causal_fvg_csv(
    csv_text: Any, *, symbol: Any, timeframe: Any,
    timestamp_basis: Any, now: Any,
) -> dict:
    """Deterministic prefix-only FVG candidates with SMA5 trend filter.

    A candidate's signal_time is the closing timestamp of candle i.
    Entry can occur only AFTER i under the existing A277 engine.
    """
    output = _base()
    imported = import_historical_csv(
        csv_text, symbol=symbol, timeframe=timeframe,
        timestamp_basis=timestamp_basis, now=now,
    )
    if not imported["valid"]:
        output["error"] = "INVALID_HISTORICAL_CSV:" + imported["error"]
        return output
    candles = imported["candles"]
    previous_hash = GENESIS
    plans, audit = [], []
    gap_candidates, trend_rejected, untradeable = 0, 0, 0

    for i, bar in enumerate(candles):
        previous_hash = _hash({
            "previous_sha256": previous_hash, "candle": bar,
        })
        if i < SMA_BARS:
            continue
        prior = candles[i - 2]
        previous_closes = [x["close"] for x in candles[i - SMA_BARS:i]]
        current_closes = [x["close"] for x in candles[i - SMA_BARS + 1:i + 1]]
        preceding_sma = sum(previous_closes) / SMA_BARS
        current_sma = sum(current_closes) / SMA_BARS
        mean_range = sum(
            x["high"] - x["low"]
            for x in candles[i - SMA_BARS + 1:i + 1]
        ) / SMA_BARS
        if not all(math.isfinite(v) for v in (
                preceding_sma, current_sma, mean_range)):
            output["error"] = "UNSAFE_INDICATOR_ARITHMETIC"
            return output
        bullish_gap = bar["low"] - prior["high"]
        bearish_gap = prior["low"] - bar["high"]
        if not math.isfinite(bullish_gap) or not math.isfinite(bearish_gap):
            output["error"] = "UNSAFE_GAP_ARITHMETIC"
            return output

        if bullish_gap > 0:
            direction, gap = "BUY", bullish_gap
            trend_ok = bar["close"] > current_sma > preceding_sma
            lower, upper = prior["high"], bar["low"]
        elif bearish_gap > 0:
            direction, gap = "SELL", bearish_gap
            trend_ok = bar["close"] < current_sma < preceding_sma
            lower, upper = bar["high"], prior["low"]
        else:
            continue
        gap_candidates += 1
        if (not trend_ok or mean_range <= 0
                or gap < MIN_GAP_RANGE_RATIO * mean_range):
            trend_rejected += 1
            continue

        entry = (lower / 2.0) + (upper / 2.0)
        window = candles[i - 2:i + 1]
        stop = (min(x["low"] for x in window) if direction == "BUY"
                else max(x["high"] for x in window))
        risk = (entry - stop if direction == "BUY" else stop - entry)
        target = (entry + TARGET_R * risk if direction == "BUY"
                  else entry - TARGET_R * risk)
        if (not all(math.isfinite(n) and n > 0 for n in
                    (entry, stop, risk, target))
                or (direction == "BUY" and not stop < entry < target)
                or (direction == "SELL" and not target < entry < stop)):
            untradeable += 1
            continue
        if len(plans) >= MAX_PLANS:
            output["error"] = "TOO_MANY_HISTORICAL_CANDIDATES"
            return output
        plan = {
            "signal_time": bar["datetime"], "setup": "FVG",
            "side": direction, "entry": entry,
            "stop": stop, "target": target,
        }
        plans.append(plan)
        audit.append({
            "signal_time": bar["datetime"],
            "observed_closed_bars": i + 1,
            "prefix_sha256": previous_hash,
            "side": direction,
            "gap_size": round(gap, 12),
            "prior_sma5": round(preceding_sma, 12),
            "current_sma5": round(current_sma, 12),
        })
    output.update({
        "valid": True, "status": "MECHANICAL_FVG_HISTORICAL_CANDIDATES_ONLY",
        "error": None, "symbol": symbol, "timeframe": timeframe,
        "strategy_spec": dict(SPEC),
        "raw_csv_sha256": imported["raw_csv_sha256"],
        "normalized_candles_sha256": imported["normalized_candles_sha256"],
        "last_prefix_sha256": previous_hash,
        "observed_candles": len(candles),
        "gap_patterns_observed": gap_candidates,
        "gap_candidates_filtered": trend_rejected,
        "untradeable_candidates": untradeable,
        "candidate_plans": plans, "candidate_audit": audit,
        "candidate_count": len(plans),
        "historical_plans_not_captured_as_they_happened": True,
    })
    return output


def research_causal_fvg_backtest_csv(
    csv_text: Any, *, symbol: Any, timeframe: Any,
    timestamp_basis: Any, now: Any, validation_start: Any,
    cost_r: Any, slippage_r: Any,
    max_wait_bars: Any = 8, max_hold_bars: Any = 96,
) -> dict:
    """Backtest fixed historic candidates, never stamp a fake A278 receipt."""
    candidates = generate_causal_fvg_csv(
        csv_text, symbol=symbol, timeframe=timeframe,
        timestamp_basis=timestamp_basis, now=now,
    )
    if not candidates["valid"]:
        return {
            **_base(), "error": candidates["error"],
            "train": None, "holdout": None,
        }
    result = research_backtest_csv(
        csv_text, symbol=symbol, timeframe=timeframe,
        timestamp_basis=timestamp_basis, now=now,
        validation_start=validation_start,
        manual_plans=candidates["candidate_plans"],
        cost_r=cost_r, slippage_r=slippage_r,
        max_wait_bars=max_wait_bars, max_hold_bars=max_hold_bars,
    )
    result.update({
        "causal_fvg_schema": SCHEMA,
        "strategy_version": STRATEGY_VERSION,
        "strategy_spec_sha256": candidates["strategy_spec_sha256"],
        "candidate_count": candidates["candidate_count"],
        "candidate_audit": candidates["candidate_audit"],
        "candidate_no_future_candles_used": True,
        "historical_plans_not_captured_as_they_happened": True,
        "not_verified_ict_zones": True,
        "no_orders": True, "no_alerts": True,
        "authorizes_send": False, "p0_homologated": 0,
    })
    return result


__all__ = [
    "SCHEMA", "SPEC", "STRATEGY_VERSION", "generate_causal_fvg_csv",
    "research_causal_fvg_backtest_csv",
]
