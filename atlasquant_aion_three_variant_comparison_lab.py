"""A282 LAB: same-CSV, same-cut descriptive comparison of fixed A279-A281 rules.

Caller-supplied OFFLINE historical candles only. No performance ranking,
parameter search, broker feed, execution, P0 authority, or actual out-of-sample
attestation. The three mechanical variants can have different trade counts;
their net-R totals must never be presented as a fair causal superiority proof.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

from atlasquant_aion_causal_fvg_lab import research_causal_fvg_backtest_csv
from atlasquant_aion_causal_structure_lab import research_structure_filtered_backtest_csv
from atlasquant_aion_causal_ob_fvg_lab import research_ob_fvg_backtest_csv

SCHEMA = "ATLASQUANT_AION_THREE_VARIANT_HOLDOUT_COMPARISON_LAB_V1"
SPEC_VERSION = "A282_FIXED_DESCRIPTIVE_COMPARISON_V1"
MIN_HOLDOUT_TRADES = 30
MAX_SERIES = 8
SLICE_FIELDS = frozenset((
    "symbol", "timeframe", "timestamp_basis", "csv_text", "validation_start",
))
MODELS = (
    ("FVG_SMA5", research_causal_fvg_backtest_csv, "candidate_count"),
    ("FVG_BOS", research_structure_filtered_backtest_csv, "filtered_candidate_count"),
    ("FVG_BOS_PLUS_OB_PROXY", research_ob_fvg_backtest_csv, "combined_candidate_count"),
)
SPEC = {
    "version": SPEC_VERSION,
    "model_order": [item[0] for item in MODELS],
    "same_raw_csv_per_model": True,
    "same_holdout_boundary_per_model": True,
    "same_execution_cost_and_windows_per_model": True,
    "no_adaptive_parameter_selection": True,
    "minimum_executed_holdout_trades_per_model": MIN_HOLDOUT_TRADES,
    "no_winner_selection": True,
    "never_pool_unrelated_asset_or_timeframe_r_units": True,
}


def _digest(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, ensure_ascii=True,
                         separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _base() -> dict:
    return {
        "schema": SCHEMA,
        "spec_version": SPEC_VERSION,
        "spec_sha256": _digest(SPEC),
        "valid": False, "status": "INVALID_DESCRIPTIVE_COMPARISON",
        "error": "INVALID_INPUT",
        "models": [], "series": [], "series_count": 0,
        "research_only": True, "historical_only": True,
        "source_is_externally_attested": False,
        "holdout_is_independently_attested": False,
        "historical_plans_captured_in_real_time": False,
        "actual_ict_zones_verified": False,
        "actual_market_return_prediction": False,
        "no_parameter_optimization": True,
        "no_model_ranking": True, "no_winner_selection": True,
        "no_cross_asset_r_aggregation": True,
        "no_new_data_calls": True, "no_orders": True, "no_alerts": True,
        "authorizes_send": False, "p0_homologated": 0,
    }


def _partition_view(partition: Any) -> dict | None:
    if type(partition) is not dict:
        return None
    summary, ledger = partition.get("summary"), partition.get("ledger")
    scenarios = partition.get("friction_scenarios")
    censored = partition.get("censored_trades")
    if (type(summary) is not dict or type(ledger) is not list
            or type(scenarios) is not list
            or type(censored) is not int or censored < 0
            or any(type(row) is not dict for row in ledger)):
        return None
    trades = summary.get("trades")
    signals = summary.get("signals")
    if (type(trades) is not int or trades < 0
            or type(signals) is not int or signals != len(ledger)
            or trades > signals
            or summary.get("no_trade") != signals - trades):
        return None
    if summary.get("sample_status") not in (
            "INSUFFICIENT_SAMPLE", "DESCRIPTIVE_ONLY_NO_PREDICTION"):
        return None
    if summary["sample_status"] != (
            "INSUFFICIENT_SAMPLE" if trades < MIN_HOLDOUT_TRADES
            else "DESCRIPTIVE_ONLY_NO_PREDICTION"):
        return None
    try:
        ledger_sha = _digest(ledger)
        scenario_sha = _digest(scenarios)
    except (TypeError, ValueError, OverflowError):
        return None
    return {
        "candle_count": partition.get("candle_count"),
        "summary": dict(summary),
        "censored_trades": censored,
        "overlap_blocked_plans": sum(
            row.get("status") == "OVERLAP_BLOCKED" for row in ledger
            if type(row) is dict
        ),
        "no_entry_plans": sum(
            row.get("status") in ("NO_ENTRY", "NO_FUTURE_DATA")
            for row in ledger if type(row) is dict
        ),
        "plan_rows": len(ledger),
        "ledger_sha256": ledger_sha,
        "friction_scenarios": list(scenarios),
        "friction_scenarios_sha256": scenario_sha,
        "adequate_descriptive_sample": trades >= MIN_HOLDOUT_TRADES,
    }


def compare_causal_variants_csv(
    csv_text: Any, *, symbol: Any, timeframe: Any,
    timestamp_basis: Any, now: Any, validation_start: Any,
    cost_r: Any, slippage_r: Any,
    max_wait_bars: Any = 8, max_hold_bars: Any = 96,
) -> dict:
    """Return three separately computed research variants; fail entire group.

    All parameters are locked BEFORE inspecting a holdout. Passing a historical
    boundary does not itself prove the split was independent of hindsight.
    """
    result = _base()
    inputs = dict(
        symbol=symbol, timeframe=timeframe, timestamp_basis=timestamp_basis,
        now=now, validation_start=validation_start,
        cost_r=cost_r, slippage_r=slippage_r,
        max_wait_bars=max_wait_bars, max_hold_bars=max_hold_bars,
    )
    reports = []
    for label, runner, count_field in MODELS:
        response = runner(csv_text, **inputs)
        if not response.get("valid"):
            result["error"] = "MODEL_" + label + ":" + str(
                response.get("error") or "INVALID_RESEARCH_RESULT")
            return result
        if (response.get("authorizes_send") is not False
                or response.get("p0_homologated") != 0
                or response.get("no_orders") is not True):
            result["error"] = "UNSAFE_MODEL_CONTRACT:" + label
            return result
        train = _partition_view(response.get("train"))
        holdout = _partition_view(response.get("holdout"))
        count = response.get(count_field)
        if (train is None or holdout is None or type(count) is not int
                or count < 0
                or type(train["candle_count"]) is not int
                or type(holdout["candle_count"]) is not int
                or train["candle_count"] < 3
                or holdout["candle_count"] < 3):
            result["error"] = "INVALID_MODEL_PARTITIONS:" + label
            return result
        reports.append({
            "model": label,
            "fixed_strategy_spec_sha256": response.get(
                "strategy_spec_sha256" if label != "FVG_BOS"
                else "structure_spec_sha256"),
            "historical_candidate_count": count,
            "source_raw_csv_sha256": response.get("raw_csv_sha256"),
            "source_normalized_candles_sha256":
                response.get("normalized_candles_sha256"),
            "validation_start_utc": response.get("validation_start_utc"),
            "assumed_cost_r": response.get("assumed_cost_r"),
            "assumed_slippage_r": response.get("assumed_slippage_r"),
            "no_lookahead_execution": response.get("no_lookahead_execution"),
            "single_position_per_asset": response.get("single_position_per_asset"),
            "train": train, "holdout": holdout,
        })
    first = reports[0]
    common = (
        "source_raw_csv_sha256", "source_normalized_candles_sha256",
        "validation_start_utc", "assumed_cost_r", "assumed_slippage_r",
        "no_lookahead_execution", "single_position_per_asset",
    )
    for model in reports:
        if (any(model[key] != first[key] for key in common)
                or any(model[key] is None for key in common[:5])
                or model["no_lookahead_execution"] is not True
                or model["single_position_per_asset"] is not True
                or type(model["fixed_strategy_spec_sha256"]) is not str
                or len(model["fixed_strategy_spec_sha256"]) != 64
                or model["train"]["candle_count"] != first["train"]["candle_count"]
                or model["holdout"]["candle_count"] != first["holdout"]["candle_count"]):
            result["error"] = "CROSS_MODEL_COMPARABILITY_FAILURE"
            return result
    enough = all(
        model["holdout"]["adequate_descriptive_sample"] for model in reports
    )
    result.update({
        "valid": True, "error": None,
        "status": ("DESCRIPTIVE_ONLY_NOT_INDEPENDENTLY_ATTESTED" if enough
                   else "INSUFFICIENT_HOLDOUT_SAMPLE_FOR_COMPARISON"),
        "symbol": symbol, "timeframe": timeframe,
        "time_basis": timestamp_basis,
        "raw_csv_sha256": first["source_raw_csv_sha256"],
        "normalized_candles_sha256":
            first["source_normalized_candles_sha256"],
        "validation_start_utc": first["validation_start_utc"],
        "assumed_cost_r": first["assumed_cost_r"],
        "assumed_slippage_r": first["assumed_slippage_r"],
        "max_wait_bars": max_wait_bars,
        "max_hold_bars": max_hold_bars,
        "models": reports,
        "all_models_have_at_least_30_holdout_trades": enough,
        "comparison_interpretation": (
            "DESCRIPTIVE_ONLY; UNEQUAL_CANDIDATE_COUNTS_AND_OVERLAPS; "
            "NO_WINNER_OR_VALIDATED_EDGE; UNATTESTED_HISTORICAL_INPUT"
        ),
    })
    return result


def compare_causal_variants_batch(
    slices: Any, *, now: Any, cost_r: Any, slippage_r: Any,
    max_wait_bars: Any = 8, max_hold_bars: Any = 96,
) -> dict:
    """Bounded batch; each symbol/timeframe is reported separately, never pooled."""
    result = _base()
    if type(slices) is not list or not 1 <= len(slices) <= MAX_SERIES:
        result["error"] = "INVALID_SERIES_COUNT"
        return result
    seen, completed = set(), []
    for index, item in enumerate(slices):
        if type(item) is not dict or set(item) != SLICE_FIELDS:
            result["error"] = "INVALID_SERIES_FIELDS_AT_" + str(index)
            return result
        symbol, timeframe = item["symbol"], item["timeframe"]
        if type(symbol) is not str or type(timeframe) is not str:
            result["error"] = "INVALID_SERIES_ID_AT_" + str(index)
            return result
        key = (symbol, timeframe)
        if key in seen:
            result["error"] = "DUPLICATE_SYMBOL_TIMEFRAME"
            return result
        seen.add(key)
        comparison = compare_causal_variants_csv(
            item["csv_text"], symbol=symbol, timeframe=timeframe,
            timestamp_basis=item["timestamp_basis"],
            now=now, validation_start=item["validation_start"],
            cost_r=cost_r, slippage_r=slippage_r,
            max_wait_bars=max_wait_bars, max_hold_bars=max_hold_bars,
        )
        if not comparison["valid"]:
            result["error"] = "SERIES_" + str(index) + ":" + comparison["error"]
            return result
        completed.append(comparison)
    result.update({
        "valid": True, "error": None,
        "status": ("DESCRIPTIVE_BATCH_ONLY_UNATTESTED" if all(
            row["all_models_have_at_least_30_holdout_trades"]
            for row in completed) else "BATCH_HAS_INSUFFICIENT_HOLDOUT_SAMPLES"),
        "series": completed, "series_count": len(completed),
        "models": [],
        "no_pooling_or_winner_selection": True,
    })
    return result


__all__ = [
    "SCHEMA", "SPEC", "SPEC_VERSION", "MIN_HOLDOUT_TRADES", "MAX_SERIES",
    "compare_causal_variants_csv", "compare_causal_variants_batch",
]
