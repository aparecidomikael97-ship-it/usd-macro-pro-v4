"""Pure M15 hypothetical execution replay; no signals, broker, or orders.

Consumes *pre-annotated* research setups and complete OHLC bars. It cannot
establish whether the setup was genuinely discovered without hindsight.
No market feed, authentication, performance claim, or trading authority.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from math import isfinite
from typing import Any, Mapping

from atlasquant_fx_universe import OFFICIAL_PAIRS

SCHEMA = "ATLASQUANT_M15_EXECUTION_REPLAY_LAB_V1"
OUTPUT_SCHEMA = "ATLASQUANT_M15_EXECUTION_REPLAY_RESULT_LAB_V1"
M15 = timedelta(minutes=15)
ALLOWED_SETUPS = frozenset({"FVG", "ORDER_BLOCK", "PULLBACK"})


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema": OUTPUT_SCHEMA, "state": "BLOCKED", "reason": reason,
        "outcome": "NONE", "net_r": None, "entry_fill": None,
        "exit_fill": None, "costs_are_assumptions": True,
        "source_authenticated": False, "signal_causal_verified": False,
        "spread_slippage_verified": False, "profitability_verified": False,
        "publishable": False, "trade_authorized": False,
    }


def _num(value: Any, *, positive: bool = True) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        v = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    if not isfinite(v) or (v <= 0 if positive else v < 0):
        return None
    return v


def _timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        t = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if t.tzinfo is None or t.utcoffset() is None:
        return None
    t = t.astimezone(timezone.utc)
    if t.minute % 15 or t.second or t.microsecond:
        return None
    return t


def _bar(raw: Any) -> tuple[datetime, float, float, float, float] | None:
    if not isinstance(raw, Mapping):
        return None
    stamp = _timestamp(raw.get("time"))
    values = [_num(raw.get(key)) for key in ("open", "high", "low", "close")]
    if stamp is None or any(x is None for x in values):
        return None
    opening, high, low, close = values
    assert opening is not None and high is not None and low is not None and close is not None
    if high < max(opening, close, low) or low > min(opening, close, high):
        return None
    return stamp, opening, high, low, close


def replay_m15_setup(payload: Any, *, now: datetime | None = None) -> dict[str, Any]:
    """Replay next-bar-open hypothetical fill through a fixed M15 horizon.

    Requires signal_index to point at an already *completed* annotation bar.
    A target and stop touched within one candle resolve to STOP_FIRST by policy.
    This conservative policy is an assumption, not proof of intrabar order.
    """
    if not isinstance(payload, Mapping) or payload.get("schema") != SCHEMA:
        return _blocked("INVALID_CONTRACT")
    if payload.get("state") != "OFFLINE_RESEARCH" or payload.get("timeframe") != "M15":
        return _blocked("INVALID_CONTRACT")
    if payload.get("pair") not in OFFICIAL_PAIRS:
        return _blocked("INVALID_PAIR")
    side = payload.get("side")
    if side not in ("BUY", "SELL") or payload.get("setup_kind") not in ALLOWED_SETUPS:
        return _blocked("INVALID_SETUP_OR_SIDE")
    if any(key in payload for key in ("token", "api_key", "access_token", "authorization")):
        return _blocked("SENSITIVE_FIELD_NOT_ALLOWED")
    current = now if now is not None else datetime.now(timezone.utc)
    if current.tzinfo is None or current.utcoffset() is None:
        raise ValueError("now must be timezone-aware")
    current = current.astimezone(timezone.utc)
    raw_bars = payload.get("bars")
    if not isinstance(raw_bars, list) or not 4 <= len(raw_bars) <= 500:
        return _blocked("INVALID_BAR_COUNT")
    raw_index = payload.get("signal_bar_index")
    if type(raw_index) is not int or not 2 <= raw_index < len(raw_bars) - 1:
        return _blocked("SIGNAL_NOT_BEFORE_ENTRY")
    signal_index = raw_index
    parsed: list[tuple[datetime, float, float, float, float]] = []
    for raw in raw_bars:
        bar = _bar(raw)
        if bar is None:
            return _blocked("INVALID_OHLC_OR_BAR_TIME")
        if bar[0] + M15 > current:
            return _blocked("FUTURE_OR_OPEN_BAR")
        if parsed and bar[0] - parsed[-1][0] != M15:
            return _blocked("M15_GAP_OR_ORDER")
        parsed.append(bar)
    signal_confirmed = _timestamp(payload.get("signal_confirmed_at"))
    if signal_confirmed != parsed[signal_index][0] + M15:
        return _blocked("SIGNAL_CONFIRMATION_TIME_INVALID")
    point = _num(payload.get("point_size"))
    spread_points = _num(payload.get("spread_points_assumed"), positive=False)
    slippage_points = _num(payload.get("slippage_points_assumed"), positive=False)
    stop = _num(payload.get("stop_mid"))
    target = _num(payload.get("target_mid"))
    if None in (point, spread_points, slippage_points, stop, target):
        return _blocked("MISSING_OR_INVALID_COSTS_OR_LEVELS")
    assert point is not None and spread_points is not None and slippage_points is not None
    assert stop is not None and target is not None
    half_spread = point * spread_points / 2
    slippage = point * slippage_points
    if not isfinite(half_spread + slippage):
        return _blocked("NUMERIC_RANGE_INVALID")
    cost = half_spread + slippage
    entry = parsed[signal_index + 1]
    entry_open = entry[1]
    if side == "BUY":
        fill = entry_open + cost
        stop_fill, target_fill = stop - cost, target - cost
        risk = fill - stop_fill
        valid_geometry = (
            stop < entry_open < target and stop_fill > 0 and target_fill > fill
        )
    else:
        fill = entry_open - cost
        stop_fill, target_fill = stop + cost, target + cost
        risk = stop_fill - fill
        valid_geometry = (
            target < entry_open < stop and fill > 0 and
            target_fill > 0 and target_fill < fill
        )
    if (not valid_geometry or not isfinite(fill + risk + stop_fill + target_fill)
            or risk <= 0):
        return _blocked("INVALID_RISK_GEOMETRY")
    outcome = "UNRESOLVED_NO_EXIT"
    exit_fill: float | None = None
    exit_time: str | None = None
    for bar in parsed[signal_index + 1:]:
        hit_stop = bar[3] <= stop if side == "BUY" else bar[2] >= stop
        hit_target = bar[2] >= target if side == "BUY" else bar[3] <= target
        if hit_stop or hit_target:
            outcome = "AMBIGUOUS_STOP_FIRST" if hit_stop and hit_target else ("STOP" if hit_stop else "TARGET")
            exit_fill = stop_fill if hit_stop else target_fill
            exit_time = bar[0].isoformat()
            break
    net_r: float | None = None
    if exit_fill is not None:
        pnl = exit_fill - fill if side == "BUY" else fill - exit_fill
        net_r = pnl / risk
        if not isfinite(net_r):
            return _blocked("NUMERIC_RANGE_INVALID")
    out = _blocked("SCENARIO_REPLAY_ONLY_NOT_PROFITABILITY")
    out.update({
        "state": "RESEARCH_ONLY",
        "pair": payload["pair"], "side": side, "setup_kind": payload["setup_kind"],
        "signal_bar_start": parsed[signal_index][0].isoformat(),
        "entry_bar_start": entry[0].isoformat(),
        "entry_fill": round(fill, 8),
        "stop_fill_assumed": round(stop_fill, 8),
        "target_fill_assumed": round(target_fill, 8),
        "risk_per_unit_assumed": round(risk, 8),
        "exit_fill": round(exit_fill, 8) if exit_fill is not None else None,
        "exit_bar_start": exit_time,
        "outcome": outcome,
        "net_r": round(net_r, 6) if net_r is not None else None,
        "notice": "Hypothetical OHLC replay, not verified signal, trading, or performance.",
    })
    return out


__all__ = ["SCHEMA", "OUTPUT_SCHEMA", "replay_m15_setup"]
