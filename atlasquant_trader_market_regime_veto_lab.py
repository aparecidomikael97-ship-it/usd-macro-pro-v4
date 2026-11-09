"""AtlasQuant LAB: close-only FX market-regime contradiction veto, NEVER a signal.

This module checks caller-supplied OHLC and timestamps; neither broker provenance,
exchange calendars, historical P-I-T availability nor directional accuracy is
independently proven. A regime is descriptive, not an FX causality claim.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from statistics import median
from typing import Any
import re

from atlasquant_fx_universe import OFFICIAL_PAIRS
from atlasquant_trader_selective_bias_gate_lab import BiasObservation

SCHEMA = "ATLASQUANT_TRADER_MARKET_REGIME_VETO_LAB_V1"
HORIZONS = ("W1", "D1")
BAR_SECONDS = {"D1": 86400, "W1": 604800}
MIN_BARS = 32
MAX_BARS = 180
ER_LOOKBACK = 20
TREND_MIN_ER = Decimal("0.55")
RANGE_MAX_ER = Decimal("0.30")
SHOCK_TR_MULTIPLIER = Decimal("2.50")
MAX_AGE = {"D1": timedelta(days=7), "W1": timedelta(days=28)}
_HASH = re.compile(r"[0-9a-f]{64}\Z")


@dataclass(frozen=True)
class ClosedMarketBar:
    opened_at: datetime
    closed_at: datetime
    recorded_at: datetime
    open: str
    high: str
    low: str
    close: str
    source_sha256_claim: str


def _utc(value: Any) -> datetime | None:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        return None
    return value.astimezone(timezone.utc)


def _price(value: Any) -> Decimal | None:
    if not isinstance(value, str) or not 1 <= len(value) <= 32:
        return None
    try:
        number = Decimal(value)
    except (InvalidOperation, ValueError):
        return None
    return number if number.is_finite() and 0 < number <= Decimal("100000000") else None


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_MARKET_REGIME_RESEARCH_VETO",
        "reason": reason, "research_veto": True,
        "W1": None, "D1": None, "blockers": [reason],
        "regime_thresholds_calibrated": False,
        "historical_broker_prices_independently_authenticated": False,
        "price_archive_pit_independently_authenticated": False,
        "broker_trading_calendar_independently_verified": False,
        "risk_off_from_cross_asset_flows_verified": False,
        "incremental_accuracy_improvement_validated": False,
        "validated_directional_accuracy": None,
        "calibrated_direction_probability": None,
        "fx_bias": None, "index_bias": None,
        "operational_bias": "AGUARDAR", "publishable": False,
        "live_alert_allowed": False, "trade_authorized": False,
        "worker_enabled": False, "scheduler_enabled": False,
        "http_requests": 0, "new_cost_brl": 0, "research_only": True,
    }


def _evaluate_horizon(bars: Any, *, horizon: str, cutoff: datetime,
                      side: str) -> dict[str, Any]:
    report: dict[str, Any] = {"horizon": horizon, "regime": None,
        "direction_documentary": None, "efficiency_ratio": None,
        "latest_true_range_vs_prior_median": None,
        "research_veto": True, "reason": "INVALID_OHLC_OR_ASOF_CLAIMS",
        "price_source_independently_authenticated": False,
        "risk_off_verified": False}
    if not isinstance(bars, (tuple, list)) or not MIN_BARS <= len(bars) <= MAX_BARS:
        report["reason"] = "MISSING_OR_INSUFFICIENT_CLOSED_BARS"
        return report
    closes: list[Decimal] = []
    true_ranges: list[Decimal] = []
    previous_start: datetime | None = None
    previous_close: Decimal | None = None
    for bar in bars:
        if not isinstance(bar, ClosedMarketBar):
            return report
        opened, closed, recorded = (_utc(bar.opened_at), _utc(bar.closed_at),
                                     _utc(bar.recorded_at))
        if (opened is None or closed is None or recorded is None
                or closed - opened != timedelta(seconds=BAR_SECONDS[horizon])
                or not opened < closed <= recorded <= cutoff
                or not isinstance(bar.source_sha256_claim, str)
                or _HASH.fullmatch(bar.source_sha256_claim) is None):
            report["reason"] = "INVALID_OR_LOOKAHEAD_BAR_TIMESTAMPS"
            return report
        if previous_start is not None:
            gap = opened - previous_start
            if gap < timedelta(seconds=BAR_SECONDS[horizon]) or (
                horizon == "D1" and gap > timedelta(days=4)) or (
                horizon == "W1" and gap != timedelta(days=7)):
                report["reason"] = "UNREVIEWED_BAR_GAP_OR_ORDER"
                return report
        o, h, l, c = map(_price, (bar.open, bar.high, bar.low, bar.close))
        if (any(v is None for v in (o, h, l, c))
                or not l <= min(o, c) <= max(o, c) <= h):
            return report
        tr = max(h - l, abs(h - previous_close), abs(l - previous_close)) if previous_close else h - l
        closes.append(c)
        true_ranges.append(tr)
        previous_start, previous_close = opened, c
    if cutoff - _utc(bars[-1].closed_at) > MAX_AGE[horizon]:
        report["reason"] = "LAST_CLOSED_BAR_TOO_OLD"
        return report
    moves = [abs(b - a) for a, b in zip(closes[-ER_LOOKBACK-1:-1], closes[-ER_LOOKBACK:])]
    path = sum(moves)
    if path <= 0:
        report["reason"] = "NO_PRICE_MOVEMENT_FOR_EFFICIENCY"
        return report
    er = abs(closes[-1] - closes[-ER_LOOKBACK-1]) / path
    reference_tr = median(true_ranges[-ER_LOOKBACK-1:-1])
    if reference_tr <= 0:
        report["reason"] = "NO_PRIOR_VOLATILITY_REFERENCE"
        return report
    shock = true_ranges[-1] / reference_tr
    report["efficiency_ratio"] = str(er.quantize(Decimal("0.0001")))
    # Huge price-scale changes can overflow Decimal.quantize's working
    # precision. They are data-quality reviews, never confident regimes.
    if shock >= Decimal("1000000"):
        report.update({"regime": "VOLATILITY_SHOCK",
                       "latest_true_range_vs_prior_median": format(shock, ".2E"),
                       "reason": "EXTREME_PRICE_SCALE_OR_VOLATILITY_REQUIRES_REVIEW"})
        return report
    report["latest_true_range_vs_prior_median"] = str(shock.quantize(Decimal("0.01")))
    net = closes[-1] - closes[-ER_LOOKBACK-1]
    direction = "ALTA" if net > 0 else "BAIXA" if net < 0 else None
    if shock >= SHOCK_TR_MULTIPLIER:
        regime, reason = "VOLATILITY_SHOCK", "VOLATILITY_SHOCK_REQUIRES_REVIEW"
    elif er >= TREND_MIN_ER and direction is not None:
        regime = "TREND"
        reason = "TREND_AGREES_DOCUMENTARY_ONLY" if direction == side else "TREND_CONTRADICTS_CANDIDATE"
    elif er <= RANGE_MAX_ER:
        regime, reason = "RANGE", "RANGE_DOES_NOT_SUPPORT_DIRECTIONAL_RESEARCH"
    else:
        regime, reason = "TRANSITION", "TRANSITION_REGIME_INDETERMINATE"
    report.update({"regime": regime, "direction_documentary": direction,
                   "reason": reason, "research_veto": reason != "TREND_AGREES_DOCUMENTARY_ONLY"})
    return report


def inspect_market_regime_veto_lab(*, candidate: Any, bars_by_horizon: Any,
                                   decision_at_by_horizon: Any,
                                   as_of_utc: Any) -> dict[str, Any]:
    """Strict 2-horizon research veto; positive alignment is NOT authorization."""
    out = _blocked("INVALID_CANDIDATE_OR_DECISION_CLOCK")
    current = _utc(as_of_utc)
    if not isinstance(candidate, BiasObservation) or current is None:
        return out
    candidate_at = _utc(candidate.evaluated_at)
    if (candidate.asset not in OFFICIAL_PAIRS or candidate.horizon not in HORIZONS
            or candidate.weekly not in ("ALTA", "BAIXA")
            or candidate.daily not in ("ALTA", "BAIXA")
            or candidate.weekly != candidate.daily or candidate_at is None
            or candidate_at > current):
        return out
    if not isinstance(decision_at_by_horizon, dict) or set(decision_at_by_horizon) != set(HORIZONS):
        return out
    decisions = {h: _utc(decision_at_by_horizon[h]) for h in HORIZONS}
    if (any(d is None or d > candidate_at for d in decisions.values())
            or decisions["W1"] > decisions["D1"]):
        return out
    if not isinstance(bars_by_horizon, dict) or set(bars_by_horizon) != set(HORIZONS):
        return _blocked("MARKET_REGIME_BARS_MISSING_OR_WRONG_HORIZONS")
    details = {h: _evaluate_horizon(bars_by_horizon[h], horizon=h,
                                   cutoff=decisions[h], side=candidate.daily)
               for h in HORIZONS}
    vetoes = [f"{h}_{details[h]['reason']}" for h in HORIZONS if details[h]["research_veto"]]
    out.update({"W1": details["W1"], "D1": details["D1"],
                "blockers": vetoes, "research_veto": bool(vetoes),
                "state": "LAB_MARKET_REGIME_RESEARCH_VETO" if vetoes else "LAB_REGIME_ALIGNMENT_DOCUMENTARY_NOT_LIVE",
                "reason": "REGIME_VETO" if vetoes else "REGIME_MATCHES_BUT_SOURCES_AND_EDGE_UNVERIFIED"})
    return out


__all__ = ["SCHEMA", "ClosedMarketBar", "inspect_market_regime_veto_lab"]
