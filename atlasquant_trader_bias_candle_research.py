"""Research-only FX trend observations from explicitly CLOSED OHLC candles.

This is deliberately NOT a provider adapter or an authenticated market signal.
The result is NEVER a VALIDATED_BIAS_EVIDENCE payload and must NOT be passed
directly to the live Trader as a verified market direction.
"""
from __future__ import annotations

from datetime import datetime, timezone
from math import isfinite
from typing import Any, Mapping

from atlasquant_fx_universe import OFFICIAL_PAIRS
from atlasquant_trader_bias_matrix import MAX_AGE, TIMEFRAMES

SCHEMA = "ATLASQUANT_TREND_FROM_CLOSED_OHLC_RESEARCH_V1"
MIN_BARS = 60


def _utc(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None or dt.utcoffset() is None:
        return None
    return dt.astimezone(timezone.utc)


def _float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if isfinite(number) and number > 0 else None


def _ema(values: list[float], span: int) -> list[float]:
    alpha = 2.0 / (span + 1.0)
    output = [values[0]]
    for value in values[1:]:
        output.append(alpha * value + (1.0 - alpha) * output[-1])
    return output


def _closed_bars(records: Any, *, now: datetime) -> tuple[list[dict[str, Any]], str]:
    if not isinstance(records, (list, tuple)) or len(records) < MIN_BARS:
        return [], "HISTÓRICO_INSUFICIENTE"
    # Parse all available candles, not only the last MIN_BARS. A duplicate,
    # future, malformed or non-monotonic record invalidates this series.
    rows: list[dict[str, Any]] = []
    previous_start = None
    previous_close = None
    for raw in records:
        if not isinstance(raw, Mapping):
            return [], "CANDLE_INVÁLIDO"
        stamp = _utc(raw.get("datetime"))
        closed = _utc(raw.get("closed_at"))
        values = [_float(raw.get(field)) for field in ("open", "high", "low", "close")]
        if stamp is None or closed is None or any(v is None for v in values):
            return [], "CANDLE_INVÁLIDO"
        op, hi, lo, cl = values
        if not lo <= min(op, cl) <= max(op, cl) <= hi:
            return [], "CANDLE_INVÁLIDO"
        if closed <= stamp or closed > now:
            return [], "CANDLE_NÃO_FECHADO"
        if previous_start is not None and (
            stamp <= previous_start or closed <= previous_close or stamp < previous_close
        ):
            return [], "SÉRIE_NÃO_MONOTÔNICA"
        rows.append({"datetime": stamp, "closed_at": closed,
                     "open": op, "high": hi, "low": lo, "close": cl})
        previous_start, previous_close = stamp, closed
    return rows, "VALIDO"


def research_bias_from_bars(records: Any, *, timeframe: str,
                            now: datetime | None = None) -> dict[str, Any]:
    """Filter only; last close must be fresh. No probability or buy/sell advice."""
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None or current.utcoffset() is None:
        raise ValueError("now must be timezone-aware")
    current = current.astimezone(timezone.utc)
    if timeframe not in TIMEFRAMES:
        raise ValueError("unsupported timeframe")
    result = {"state": "NOT_READY", "bias": "AGUARDAR",
              "reason": "SEM_DADOS", "last_closed_at": None}
    candles, state = _closed_bars(records, now=current)
    if state != "VALIDO":
        result["reason"] = state
        return result
    last = candles[-1]["closed_at"]
    if current - last > MAX_AGE[timeframe]:
        result["reason"] = "DADOS_VENCIDOS"
        return result
    closes = [row["close"] for row in candles]
    fast, slow = _ema(closes, 20), _ema(closes, 50)
    recent_range = [
        max(candles[k]["high"] - candles[k]["low"],
            abs(candles[k]["high"] - candles[k - 1]["close"]),
            abs(candles[k]["low"] - candles[k - 1]["close"]))
        for k in range(max(1, len(candles) - 14), len(candles))
    ]
    atr = sum(recent_range) / len(recent_range)
    if not isfinite(atr) or atr <= 0:
        result["reason"] = "VOLATILIDADE_INVALIDA"
        return result
    separation = fast[-1] - slow[-1]
    slope = fast[-1] - fast[-6]
    spread_limit = max(0.15 * atr, 0.00015 * closes[-1])
    slope_limit = max(0.07 * atr, 0.00005 * closes[-1])
    if separation > spread_limit and slope > slope_limit:
        bias = "ALTA"
    elif separation < -spread_limit and slope < -slope_limit:
        bias = "BAIXA"
    else:
        bias = "NEUTRO"
    return {"state": "READY_RESEARCH", "bias": bias,
            "reason": "EMA20_EMA50_INCLINAÇÃO_ATR", "last_closed_at": last.isoformat()}


def build_ohlc_bias_research(payload: Any, *, now: datetime | None = None) -> dict[str, Any]:
    """Build a lab report for 28 pairs. This cannot claim verified origin."""
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None or current.utcoffset() is None:
        raise ValueError("now must include timezone")
    source = payload.get("source") if isinstance(payload, Mapping) else None
    raw_pairs = payload.get("pairs") if isinstance(payload, Mapping) else None
    if not isinstance(raw_pairs, Mapping):
        raw_pairs = {}
    rows = {}
    for pair in OFFICIAL_PAIRS:
        series = raw_pairs.get(pair)
        frames = series if isinstance(series, Mapping) else {}
        rows[pair] = {
            tf: research_bias_from_bars(frames.get(tf), timeframe=tf, now=current)
            for tf in TIMEFRAMES
        }
    coverage = sum(
        all(row[tf]["state"] == "READY_RESEARCH" for tf in TIMEFRAMES)
        for row in rows.values()
    )
    return {
        "schema": SCHEMA, "state": "RESEARCH_ONLY", "source_claim": (
            str(source)[:120] if isinstance(source, str) else ""),
        "rows": rows, "complete_pairs": coverage,
        "total_pairs": len(OFFICIAL_PAIRS),
        "publishable": False, "real_orders_enabled": False,
        "provider_calls": 0, "producer_verified": False,
    }


__all__ = ["SCHEMA", "MIN_BARS", "research_bias_from_bars",
           "build_ohlc_bias_research"]
