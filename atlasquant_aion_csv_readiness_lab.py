"""A283 LAB: bounded historical CSV preflight before A282 comparison.

This preflight checks only structural feasibility of user-supplied historical
data. It cannot certify provider authenticity, market sessions, liquidity,
contract expiry, point-in-time capture, profitability, or real OOS integrity.
It is never live readiness and never permits orders or alerts.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from typing import Any

from atlasquant_aion_historical_csv import import_historical_csv
from atlasquant_aion_trader_timeframes import PERIOD_MINUTES
from atlasquant_aion_three_variant_comparison_lab import (
    SLICE_FIELDS, MAX_SERIES, compare_causal_variants_csv,
    compare_causal_variants_batch,
)

SCHEMA = "ATLASQUANT_AION_CSV_DATA_READINESS_LAB_V1"
VERSION = "A283_PRECOMMITTED_STRUCTURAL_CSV_CHECK_V1"
MIN_TRAIN_CANDLES = 100
MIN_HOLDOUT_CANDLES = 100
MIN_DISTINCT_CLOSES = 8
MIN_NONFLAT_CANDLES = 25
SPEC = {
    "version": VERSION,
    "train_minimum_closed_candles": MIN_TRAIN_CANDLES,
    "holdout_minimum_closed_candles": MIN_HOLDOUT_CANDLES,
    "distinct_close_prices_per_partition": MIN_DISTINCT_CLOSES,
    "nonflat_ohlc_bars_per_partition": MIN_NONFLAT_CANDLES,
    "gap_intervals_are_advisory_only": True,
    "market_session_schedule_not_verified": True,
    "no_historical_performance_claim": True,
    "no_external_provenance_claim": True,
}


def _digest(raw: Any) -> str:
    payload = json.dumps(raw, sort_keys=True, ensure_ascii=True,
                         separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _base() -> dict:
    return {
        "schema": SCHEMA, "spec_version": VERSION,
        "spec_sha256": _digest(SPEC),
        "valid": False, "ready_for_offline_research": False,
        "status": "INVALID_HISTORICAL_DATA_PREFLIGHT",
        "error": "INVALID_INPUT",
        "blocking_reasons": [], "advisory_warnings": [],
        "preflights": [], "comparison": None, "series_count": 0,
        "research_only": True, "historical_only": True,
        "no_live_readiness_claim": True,
        "external_provider_attested": False,
        "source_export_time_attested": False,
        "market_sessions_verified": False,
        "data_origin_authenticity_verified": False,
        "future_lookahead_proven_absent_from_strategy_selection": False,
        "strategy_edge_proven": False,
        "no_provider_download": True, "no_new_data_calls": True,
        "no_alerts": True, "no_orders": True,
        "authorizes_send": False, "p0_homologated": 0,
    }


def _utc(value: Any) -> datetime | None:
    if type(value) is not str:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None or dt.utcoffset() is None:
            return None
        return dt.astimezone(timezone.utc)
    except (ValueError, OverflowError):
        return None


def _segment_quality(candles: list[dict], name: str) -> tuple[dict, list[str]]:
    distinct_closes = len({row["close"] for row in candles})
    nonflat = sum(row["high"] > row["low"] for row in candles)
    utc_dates = len({row["datetime"][:10] for row in candles})
    reasons = []
    minimum = (MIN_TRAIN_CANDLES if name == "TRAIN" else MIN_HOLDOUT_CANDLES)
    if len(candles) < minimum:
        reasons.append(name + "_TOO_FEW_CANDLES")
    if distinct_closes < MIN_DISTINCT_CLOSES:
        reasons.append(name + "_LOW_CLOSE_DIVERSITY")
    if nonflat < MIN_NONFLAT_CANDLES:
        reasons.append(name + "_TOO_FEW_NONFLAT_BARS")
    summary = {
        "candle_count": len(candles),
        "distinct_close_values": distinct_closes,
        "nonflat_ohlc_bars": nonflat,
        "flat_ohlc_bars": len(candles) - nonflat,
        "distinct_utc_dates": utc_dates,
        "first_closed_at": candles[0]["datetime"] if candles else None,
        "last_closed_at": candles[-1]["datetime"] if candles else None,
        "minimum_candle_count": minimum,
        "enough_structural_bars": not reasons,
    }
    return summary, reasons


def _spacing(candles: list[dict], *, timeframe: str) -> dict:
    expected_seconds = PERIOD_MINUTES[timeframe] * 60
    irregular = 0
    nonintegral = 0
    elapsed_empty_periods = 0
    max_interval_seconds = 0
    previous = None
    for bar in candles:
        current = datetime.fromisoformat(bar["datetime"])
        if previous is not None:
            difference = int((current - previous).total_seconds())
            if difference > expected_seconds:
                irregular += 1
                elapsed_empty_periods += difference // expected_seconds - 1
            if difference % expected_seconds:
                nonintegral += 1
            max_interval_seconds = max(max_interval_seconds, difference)
        previous = current
    return {
        "expected_timeframe_minutes": PERIOD_MINUTES[timeframe],
        "intervals_longer_than_one_period": irregular,
        "nonintegral_period_intervals": nonintegral,
        "elapsed_empty_periods_lower_bound": elapsed_empty_periods,
        "max_interval_minutes": max_interval_seconds / 60,
        "missing_candles_proven": False,
        "market_closures_and_holidays_excluded": False,
    }


def preflight_historical_csv(
    csv_text: Any, *, symbol: Any, timeframe: Any,
    timestamp_basis: Any, now: Any, validation_start: Any,
) -> dict:
    """Preflight strict OHLC/timeframe integrity and split feasibility only.

    Passing this check is not a quality seal, source attestation, or research
    success. Market closures are not distinguishable from feed gaps here.
    """
    result = _base()
    imported = import_historical_csv(
        csv_text, symbol=symbol, timeframe=timeframe,
        timestamp_basis=timestamp_basis, now=now,
    )
    if not imported["valid"]:
        result["error"] = "INVALID_CSV:" + imported["error"]
        return result
    boundary = _utc(validation_start)
    candles = imported["candles"]
    times = {row["datetime"]: index for index, row in enumerate(candles)}
    if boundary is None or boundary.isoformat() not in times:
        result["error"] = "BOUNDARY_NOT_A_CLOSED_CANDLE"
        return result
    cutoff = times[boundary.isoformat()]
    train, holdout = candles[:cutoff], candles[cutoff:]
    train_stats, train_failures = _segment_quality(train, "TRAIN")
    holdout_stats, holdout_failures = _segment_quality(holdout, "HOLDOUT")
    blockers = [*train_failures, *holdout_failures]
    spacing = _spacing(candles, timeframe=timeframe)
    warnings = []
    if spacing["intervals_longer_than_one_period"]:
        warnings.append("INTERVAL_GAPS_NOT_ATTRIBUTABLE_TO_MARKET_VS_FEED")
    if spacing["nonintegral_period_intervals"]:
        warnings.append("IRREGULAR_TIMESTAMP_GRID_NOT_CERTIFIED")
    if imported["asset_class"] == "UNRESOLVED_FUTURE_ROOT":
        warnings.append("FUTURES_CONTRACT_EXPIRY_NOT_RESOLVED")
    result.update({
        "valid": True, "error": None,
        "status": ("STRUCTURALLY_USABLE_OFFLINE_ONLY_UNATTESTED"
                   if not blockers else "INSUFFICIENT_STRUCTURAL_SAMPLE"),
        "ready_for_offline_research": not blockers,
        "symbol": symbol, "timeframe": timeframe,
        "timestamp_basis": timestamp_basis,
        "asset_class": imported["asset_class"],
        "validation_start_utc": boundary.isoformat(),
        "raw_csv_sha256": imported["raw_csv_sha256"],
        "normalized_candles_sha256": imported["normalized_candles_sha256"],
        "total_candles": len(candles),
        "train": train_stats, "holdout": holdout_stats,
        "spacing": spacing,
        "blocking_reasons": blockers, "advisory_warnings": warnings,
        "historical_source_claim_is_unverified": True,
        "source_authenticity_preflight_cannot_verify": True,
    })
    return result


def compare_if_preflight_ready_csv(
    csv_text: Any, *, symbol: Any, timeframe: Any,
    timestamp_basis: Any, now: Any, validation_start: Any,
    cost_r: Any, slippage_r: Any,
    max_wait_bars: Any = 8, max_hold_bars: Any = 96,
) -> dict:
    """Call A282 only after A283 dataset feasibility; fail closed otherwise."""
    result = _base()
    report = preflight_historical_csv(
        csv_text, symbol=symbol, timeframe=timeframe,
        timestamp_basis=timestamp_basis, now=now,
        validation_start=validation_start,
    )
    if not report["valid"]:
        result["error"] = report["error"]
        return result
    if not report["ready_for_offline_research"]:
        result.update({
            "status": "BLOCKED_INSUFFICIENT_STRUCTURAL_SAMPLE",
            "error": "NOT_READY_FOR_OFFLINE_RESEARCH",
            "blocking_reasons": list(report["blocking_reasons"]),
        })
        return result
    compared = compare_causal_variants_csv(
        csv_text, symbol=symbol, timeframe=timeframe,
        timestamp_basis=timestamp_basis, now=now,
        validation_start=validation_start,
        cost_r=cost_r, slippage_r=slippage_r,
        max_wait_bars=max_wait_bars, max_hold_bars=max_hold_bars,
    )
    if not compared["valid"]:
        result["error"] = "A282:" + str(compared["error"])
        return result
    if (compared["raw_csv_sha256"] != report["raw_csv_sha256"]
            or compared["normalized_candles_sha256"] !=
                report["normalized_candles_sha256"]
            or compared["validation_start_utc"] !=
                report["validation_start_utc"]
            or compared["authorizes_send"] is not False
            or compared["p0_homologated"] != 0
            or compared["no_orders"] is not True):
        result["error"] = "A282_PREFLIGHT_CONTRACT_MISMATCH"
        return result
    result.update({
        "valid": True, "error": None,
        "status": "A283_CHECKED_A282_DESCRIPTIVE_HISTORICAL_ONLY",
        "ready_for_offline_research": True,
        "preflights": [report],
        "series_count": 1,
        "comparison": compared,
        "comparison_sample_status": compared["status"],
    })
    return result


def compare_if_preflight_ready_batch(
    slices: Any, *, now: Any, cost_r: Any, slippage_r: Any,
    max_wait_bars: Any = 8, max_hold_bars: Any = 96,
) -> dict:
    """All series pass structural check before *any* model is evaluated."""
    result = _base()
    if type(slices) is not list or not 1 <= len(slices) <= MAX_SERIES:
        result["error"] = "INVALID_SERIES_COUNT"
        return result
    keys, reports = set(), []
    for index, item in enumerate(slices):
        if type(item) is not dict or set(item) != SLICE_FIELDS:
            result["error"] = "INVALID_SERIES_FIELDS_" + str(index)
            return result
        symbol, timeframe = item["symbol"], item["timeframe"]
        if type(symbol) is not str or type(timeframe) is not str:
            result["error"] = "INVALID_SERIES_ID_" + str(index)
            return result
        key = (symbol, timeframe)
        if key in keys:
            result["error"] = "DUPLICATE_SYMBOL_TIMEFRAME"
            return result
        keys.add(key)
        preflight = preflight_historical_csv(
            item["csv_text"], symbol=symbol, timeframe=timeframe,
            timestamp_basis=item["timestamp_basis"], now=now,
            validation_start=item["validation_start"],
        )
        if not preflight["valid"]:
            result["error"] = "SERIES_" + str(index) + ":" + preflight["error"]
            return result
        if not preflight["ready_for_offline_research"]:
            result.update({
                "status": "BLOCKED_INSUFFICIENT_STRUCTURAL_SAMPLE",
                "error": "SERIES_" + str(index) + ":NOT_READY",
                "blocking_reasons": list(preflight["blocking_reasons"]),
            })
            return result
        reports.append(preflight)
    compared = compare_causal_variants_batch(
        slices, now=now, cost_r=cost_r, slippage_r=slippage_r,
        max_wait_bars=max_wait_bars, max_hold_bars=max_hold_bars,
    )
    if not compared["valid"] or len(compared["series"]) != len(reports):
        result["error"] = "A282_BATCH_FAILURE:" + str(compared.get("error"))
        return result
    for checked, data in zip(reports, compared["series"]):
        if (data["symbol"] != checked["symbol"]
                or data["timeframe"] != checked["timeframe"]
                or data["raw_csv_sha256"] != checked["raw_csv_sha256"]
                or data["normalized_candles_sha256"] !=
                    checked["normalized_candles_sha256"]
                or data["validation_start_utc"] !=
                    checked["validation_start_utc"]
                or data["authorizes_send"] is not False
                or data["p0_homologated"] != 0):
            result["error"] = "A282_BATCH_PREFLIGHT_CONTRACT_MISMATCH"
            return result
    result.update({
        "valid": True, "error": None,
        "status": "A283_CHECKED_BATCH_DESCRIPTIVE_HISTORICAL_ONLY",
        "ready_for_offline_research": True,
        "series_count": len(reports),
        "preflights": reports, "comparison": compared,
        "comparison_sample_status": compared["status"],
        "no_pooled_cross_asset_results": True,
    })
    return result


__all__ = [
    "SCHEMA", "SPEC", "VERSION", "MIN_TRAIN_CANDLES",
    "MIN_HOLDOUT_CANDLES", "preflight_historical_csv",
    "compare_if_preflight_ready_csv", "compare_if_preflight_ready_batch",
]
