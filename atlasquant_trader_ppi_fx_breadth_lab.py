"""PPI seven-pair USD-normalized post-news breadth, descriptive LAB only.

Takes the output of the *separate* full-CSV M15 reader. This helper does not
authenticate its input, re-read market files, estimate a USD factor, predict
direction, identify causality or fit a cross-sectional probability. Seven FX
moves from the SAME PPI release are ONE economic event, not seven trials.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
import re
from typing import Any

from atlasquant_trader_ppi_usd_fx_forward_reaction_lab import USD_FX, WINDOWS

SCHEMA = "ATLASQUANT_TRADER_PPI_7FX_USD_NORMALIZED_BREADTH_LAB_V1"
PRICE_STATE = "LAB_PPI_FX_7PAIR_FORWARD_REACTION_DOCUMENTARY_NO_GO"
DOCUMENTARY = "LAB_PPI_7FX_CROSS_PAIR_BREADTH_DOCUMENTARY_NO_GO"
BLOCKED = "LAB_PPI_7FX_CROSS_PAIR_BREADTH_BLOCKED"
METRICS = tuple(label for label, _ in WINDOWS)
# Exact two-decimal bps text emitted by the upstream price parser.
BPS = re.compile(r"-?(?:0|[1-9][0-9]{0,6})\.[0-9]{2}\Z")


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": BLOCKED, "reason": reason,
        "event_root_id": "US_PPI_OCT2026",
        "economic_event_count_documentary": 1,
        "fx_pair_count_documentary": 0,
        "cross_pair_breadth_by_horizon": None,
        "cross_horizon_m15_to_h4_sign_reversals": None,
        "rounded_zero_bps_can_mask_tiny_price_moves": True,
        "seven_correlated_pairs_not_seven_independent_trials": True,
        "cross_pair_price_moves_do_not_estimate_usd_causality": True,
        "source_price_bytes_revalidated_by_this_helper": False,
        "broker_candles_independently_authenticated": False,
        "bid_ask_execution_costs_verified": False,
        "pre_event_directional_forecast_registered": False,
        "validated_prediction_count": 0,
        "independent_prediction_trials_verified": 0,
        "validated_directional_accuracy": None,
        "calibrated_direction_probability": None,
        "market_bias": None,
        "operational_bias": "AGUARDAR", "publishable": False,
        "live_alert_allowed": False, "trade_authorized": False,
        "worker_enabled": False, "scheduler_enabled": False,
        "http_requests": 0, "file_writes": 0, "new_cost_brl": 0,
        "research_only": True,
    }


def _sign(v: Decimal) -> int:
    return (v > 0) - (v < 0)


def summarize_ppi_7fx_breadth_lab(*, price_reaction_report: Any) -> dict[str, Any]:
    """Count + / - / rounded-flat USD-relative spot moves for 3 horizons.

    Do not interpret consensus, interest rates, trade costs, or future signals.
    The upstream PPI study must first re-read all raw source/price bytes.
    """
    report = price_reaction_report
    if (not isinstance(report, dict)
            or report.get("state") != PRICE_STATE
            or report.get("independent_economic_event_sample_count") != 1
            or report.get("source_broker_independently_authenticated") is not False
            or report.get("prediction_precommitted_and_validated") is not False):
        return _blocked("REQUIRED_FULL_SEVEN_PAIR_PRICE_REACTION_REPORT_MISSING")
    rows = report.get("price_reactions_usd_normalized_bps")
    if not isinstance(rows, dict) or set(rows) != set(USD_FX):
        return _blocked("SEVEN_CANONICAL_USD_PAIRS_REQUIRED")
    normalized: dict[str, dict[str, Decimal]] = {}
    for sym in USD_FX:
        fields = rows.get(sym)
        if not isinstance(fields, dict) or set(fields) != set(METRICS):
            return _blocked("ALL_THREE_HORIZONS_PER_PAIR_REQUIRED")
        normalized[sym] = {}
        for horizon in METRICS:
            raw = fields[horizon]
            if not isinstance(raw, str) or BPS.fullmatch(raw) is None:
                return _blocked("INVALID_OR_NON_CANONICAL_TWO_DECIMAL_BPS")
            try:
                value = Decimal(raw)
            except InvalidOperation:
                return _blocked("INVALID_BPS_DECIMAL")
            if not value.is_finite():
                return _blocked("NON_FINITE_BPS")
            normalized[sym][horizon] = value
    horizons = {}
    for horizon in METRICS:
        values = [normalized[sym][horizon] for sym in USD_FX]
        sorted_values = sorted(values)
        up = [sym for sym in USD_FX if _sign(normalized[sym][horizon]) > 0]
        down = [sym for sym in USD_FX if _sign(normalized[sym][horizon]) < 0]
        rounded_zero = [sym for sym in USD_FX if _sign(normalized[sym][horizon]) == 0]
        if len(up) == 7:
            pattern = "SEVEN_POSITIVE_USD_NORMALIZED_PRICE_MOVES"
        elif len(down) == 7:
            pattern = "SEVEN_NEGATIVE_USD_NORMALIZED_PRICE_MOVES"
        elif len(rounded_zero) == 7:
            pattern = "SEVEN_ROUNDED_ZERO_PRICE_MOVES"
        elif up and down:
            pattern = "MIXED_POSITIVE_NEGATIVE_SPOT_REACTIONS"
        else:
            pattern = "PARTIAL_SIGN_WITH_ROUNDED_ZERO_REACTIONS"
        horizons[horizon] = {
            "positive_usd_normalized_move_count": len(up),
            "negative_usd_normalized_move_count": len(down),
            "rounded_zero_usd_normalized_move_count": len(rounded_zero),
            "positive_pair_symbols": up,
            "negative_pair_symbols": down,
            "rounded_zero_pair_symbols": rounded_zero,
            "sign_pattern_documentary_not_predictive": pattern,
            "median_of_seven_normalized_bps_documentary": str(sorted_values[3]),
            "min_normalized_bps_documentary": str(sorted_values[0]),
            "max_normalized_bps_documentary": str(sorted_values[-1]),
            "max_minus_min_bps_descriptive": str(sorted_values[-1] - sorted_values[0]),
            "independent_event_trials": 0,
        }
    reversals = [
        sym for sym in USD_FX
        if _sign(normalized[sym]["M15"]) * _sign(normalized[sym]["H4"]) < 0
    ]
    out = _blocked("CROSS_PAIR_COHERENCE_IS_NOT_A_PREDICTED_USD_FACTOR")
    out.update({
        "state": DOCUMENTARY,
        "reason": "SEVEN_MARKET_REACTIONS_ONE_EVENT_NO_DIRECTIONAL_FORECAST",
        "fx_pair_count_documentary": 7,
        "cross_pair_breadth_by_horizon": horizons,
        "cross_horizon_m15_to_h4_sign_reversals": reversals,
    })
    return out


__all__ = ["SCHEMA", "DOCUMENTARY", "summarize_ppi_7fx_breadth_lab"]
