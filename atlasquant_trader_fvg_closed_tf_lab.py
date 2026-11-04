"""Synthetic FVG research with timeframe isolation and no lookahead.

Three *closed* candles can form an observational FVG candidate. It is
not an order block, market signal, calibrated edge, or price forecast.
No app/TradingView integration, external prices, HTTP, Worker or trades.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping

from atlasquant_fx_universe import OFFICIAL_PAIRS

SCHEMA = "ATLASQUANT_TRADER_FVG_CLOSED_TF_LAB_V1"
TIMEFRAMES = {"M15": 15, "H1": 60, "H4": 240}
BOOK_FIELDS = frozenset({"state", "source", "symbol", "price_kind",
                         "as_of_utc", "timeframes"})
BAR_FIELDS = frozenset({"open_at_utc", "open", "high", "low", "close"})
PRICE_PATTERN = re.compile(r"[0-9]{1,6}(?:\.[0-9]{1,10})?")
MIN_GAP_BP_LAB = Decimal("2.0")


def _deny(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_FVG_INPUT_QUARANTINED", "reason": reason,
        "timeframe_checks": {}, "total_candidates": 0,
        "verified_market_zones": 0, "predictive_accuracy_proven": False,
        "live_bias": None, "live_radar": None, "trade_signal": None,
        "can_feed_live_radar": False, "can_feed_real_oos": False,
        "trade_authorized": False, "worker_enabled": False,
        "scheduler_enabled": False,
    }


def _clock(raw: Any) -> datetime | None:
    if not isinstance(raw, str) or not 20 <= len(raw) <= 40:
        return None
    if not (raw.endswith("Z") or raw.endswith("+00:00")):
        return None
    try:
        value = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if value.utcoffset() != timedelta(0):
        return None
    return value.astimezone(timezone.utc)


def _decimal(raw: Any) -> Decimal | None:
    if not isinstance(raw, str) or not PRICE_PATTERN.fullmatch(raw):
        return None
    try:
        value = Decimal(raw)
    except InvalidOperation:
        return None
    return value if Decimal("0.0001") <= value <= Decimal("100000") else None


def _tf_check(raw: Any, tf: str, as_of: datetime) -> dict[str, Any]:
    if not isinstance(raw, list) or not 1 <= len(raw) <= 2048:
        return {"state": "QUARANTINED", "reason": "Unbounded or empty timeframe", "candidates": []}
    minutes = TIMEFRAMES[tf]
    delta = timedelta(minutes=minutes)
    parsed = []
    for item in raw:
        if not isinstance(item, Mapping) or set(item) != BAR_FIELDS:
            return {"state": "QUARANTINED", "reason": "Unexpected candle fields", "candidates": []}
        t = _clock(item["open_at_utc"])
        v = [_decimal(item[k]) for k in ("open", "high", "low", "close")]
        if t is None or any(x is None for x in v):
            return {"state": "QUARANTINED", "reason": "Candle lacks UTC or numeric OHLC", "candidates": []}
        op, hi, lo, close = v
        if not lo <= min(op, close) <= max(op, close) <= hi:
            return {"state": "QUARANTINED", "reason": "Contradictory OHLC", "candidates": []}
        if t.hour * 60 % minutes != 0 or t.minute != 0 and minutes >= 60 or (
            minutes == 15 and t.minute % 15 != 0) or t.second or t.microsecond:
            return {"state": "QUARANTINED", "reason": "Not aligned to declared UTC timeframe", "candidates": []}
        parsed.append((t, op, hi, lo, close))
    start = parsed[0][0]
    if any(row[0] != start + i * delta for i, row in enumerate(parsed)):
        return {"state": "QUARANTINED", "reason": "Gap or duplicate within timeframe", "candidates": []}
    if parsed[-1][0] + delta > as_of:
        return {"state": "QUARANTINED", "reason": "Last candle not fully closed", "candidates": []}
    if len(parsed) < 3:
        return {"state": "INSUFFICIENT_HISTORY", "reason": "At least three closed candles required",
                "candidates": [], "closed_bars": len(parsed)}
    candidates = []
    for i in range(2, len(parsed)):
        former, latest = parsed[i-2], parsed[i]
        bull = latest[3] > former[2]
        bear = latest[2] < former[3]
        if not (bull or bear):
            continue
        low, high = ((former[2], latest[3]) if bull else (latest[2], former[3]))
        width_bp = (high - low) / low * Decimal("10000")
        if width_bp < MIN_GAP_BP_LAB:
            continue
        filled, touched = False, False
        for future in parsed[i+1:]:
            # These are observations AFTER detection, never inputs to formation.
            if bull:
                if future[3] <= low:
                    filled = True
                    break
                if future[3] < high:
                    touched = True
            else:
                if future[2] >= high:
                    filled = True
                    break
                if future[2] > low:
                    touched = True
        status = "FULLY_FILLED" if filled else "TOUCHED" if touched else "UNTESTED"
        candidates.append({
            "timeframe": tf, "direction": "BULLISH" if bull else "BEARISH",
            "lower": str(low), "upper": str(high),
            "width_bp": str(width_bp.quantize(Decimal("0.001"))),
            "formed_after_utc": (latest[0] + delta).isoformat(),
            "reviewed_at_utc": as_of.isoformat(), "subsequent_state": status,
            "trade_signal": False,
        })
    return {"state": "LAB_CLOSED_CANDLES_ONLY", "closed_bars": len(parsed),
            "reason": "Structural FVG candidates; no validated tradable zones",
            "candidates": candidates}


def study_fvg_closed_timeframes_lab(book: Any, *, evaluated_at: datetime) -> dict[str, Any]:
    """Study M15/H1/H4 individually. Inadequate H4 history never becomes a zone."""
    if not isinstance(evaluated_at, datetime) or evaluated_at.tzinfo is None:
        raise ValueError("Evaluation time must include timezone")
    if not isinstance(book, Mapping) or set(book) != BOOK_FIELDS:
        return _deny("Missing or extra book fields")
    if (book["state"] != "LAB_SYNTHETIC_OHLC_ONLY"
            or book["source"] != "SYNTHETIC_FIXTURE_ONLY"
            or book["price_kind"] != "SYNTHETIC_BID_OHLC"
            or book["symbol"] not in OFFICIAL_PAIRS):
        return _deny("Untrusted or non-synthetic book cannot be admitted")
    at = evaluated_at.astimezone(timezone.utc)
    as_of = _clock(book["as_of_utc"])
    if as_of is None or as_of > at:
        return _deny("Unverified or future evaluation cutoff")
    inputs = book["timeframes"]
    if not isinstance(inputs, Mapping) or set(inputs) != set(TIMEFRAMES):
        return _deny("Timeframe keys must be exactly M15/H1/H4")
    result = {tf: _tf_check(inputs[tf], tf, as_of) for tf in TIMEFRAMES}
    total = sum(len(item["candidates"]) for item in result.values())
    return {
        **_deny(""), "state": "LAB_FVG_STRUCTURAL_STUDY_ONLY",
        "reason": "Synthetic-only independent timeframe study",
        "symbol": book["symbol"], "timeframe_checks": result,
        "total_candidates": total, "min_gap_bp_uncalibrated": str(MIN_GAP_BP_LAB),
        "why_not": "FVG geometry from closed synthetic candles is neither price truth "
                   "nor predictive success; no OOS or live authorization.",
    }


__all__ = ["SCHEMA", "TIMEFRAMES", "study_fvg_closed_timeframes_lab"]
