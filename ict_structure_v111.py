"""AtlasQuant ICT Structure Engine V1.1.1.

Deterministic/observational structure layer for BOS, CHOCH and Order Blocks.
It never decides macro direction, never calls providers and never reports
probability of profit. The supplied side is context from the macro engine.
"""
from __future__ import annotations

from typing import Any

import pandas as pd


def _frame(df: pd.DataFrame | None) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    d = df.copy()
    if "datetime" in d.columns:
        d["datetime"] = pd.to_datetime(d["datetime"], utc=True, errors="coerce")
    for col in ("open", "high", "low", "close"):
        if col in d.columns:
            d[col] = pd.to_numeric(d[col], errors="coerce")
    if not all(col in d.columns for col in ("open", "high", "low", "close")):
        return pd.DataFrame()
    d = d.dropna(subset=["open", "high", "low", "close"]).copy()
    if "datetime" in d.columns:
        d = d.dropna(subset=["datetime"]).sort_values("datetime")
    return d.reset_index(drop=True)


def _atr(d: pd.DataFrame, length: int = 14) -> pd.Series:
    if d.empty:
        return pd.Series(dtype=float)
    prev = d["close"].shift(1)
    tr = pd.concat(
        [
            d["high"] - d["low"],
            (d["high"] - prev).abs(),
            (d["low"] - prev).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return tr.rolling(length, min_periods=max(4, length // 3)).mean()


def _collapse_equal_pivots(points: list[tuple[int, float]]) -> list[tuple[int, float]]:
    """Collapse adjacent duplicate pivots created by flat/equal-price candles."""
    out: list[tuple[int, float]] = []
    for idx, price in points:
        if out:
            last_idx, last_price = out[-1]
            tol = max(abs(price), abs(last_price), 1.0) * 1e-10
            if idx - last_idx <= 2 and abs(price - last_price) <= tol:
                out[-1] = (idx, price)
                continue
        out.append((idx, price))
    return out


def _pivot_points(
    d: pd.DataFrame, left: int = 2, right: int = 2
) -> tuple[list[tuple[int, float]], list[tuple[int, float]]]:
    highs: list[tuple[int, float]] = []
    lows: list[tuple[int, float]] = []
    if len(d) < left + right + 4:
        return highs, lows
    for i in range(left, len(d) - right):
        h = float(d.loc[i, "high"])
        l = float(d.loc[i, "low"])
        if h >= float(d.loc[i - left : i + right, "high"].max()):
            highs.append((i, h))
        if l <= float(d.loc[i - left : i + right, "low"].min()):
            lows.append((i, l))
    return _collapse_equal_pivots(highs), _collapse_equal_pivots(lows)


def _bias_before(
    highs: list[tuple[int, float]],
    lows: list[tuple[int, float]],
    cutoff: int,
) -> str:
    hs = [p for p in highs if p[0] <= cutoff]
    ls = [p for p in lows if p[0] <= cutoff]
    if len(hs) < 2 or len(ls) < 2:
        return "MIXED"
    dh = hs[-1][1] - hs[-2][1]
    dl = ls[-1][1] - ls[-2][1]
    eps = max(abs(hs[-1][1]), abs(ls[-1][1]), 1.0) * 1e-10
    if dh > eps and dl > eps:
        return "BULLISH"
    if dh < -eps and dl < -eps:
        return "BEARISH"
    return "MIXED"


def _structure_events(d: pd.DataFrame) -> list[dict[str, Any]]:
    highs, lows = _pivot_points(d)
    events: list[dict[str, Any]] = []
    if not highs or not lows:
        return events

    # A pivot with right=2 is usable only after two later candles exist.
    for i in range(5, len(d)):
        eligible_h = [x for x in highs if x[0] <= i - 2]
        eligible_l = [x for x in lows if x[0] <= i - 2]
        if not eligible_h or not eligible_l:
            continue

        hi_idx, hi = eligible_h[-1]
        lo_idx, lo = eligible_l[-1]
        prev_close = float(d.loc[i - 1, "close"])
        close = float(d.loc[i, "close"])
        prior_bias = _bias_before(highs, lows, i - 2)

        if close > hi and prev_close <= hi:
            kind = (
                "BOS" if prior_bias == "BULLISH"
                else "CHOCH" if prior_bias == "BEARISH"
                else "MSS"
            )
            events.append(
                {
                    "index": i,
                    "side": "BUY",
                    "kind": kind,
                    "prior_bias": prior_bias,
                    "level": hi,
                    "pivot_index": hi_idx,
                }
            )

        if close < lo and prev_close >= lo:
            kind = (
                "BOS" if prior_bias == "BEARISH"
                else "CHOCH" if prior_bias == "BULLISH"
                else "MSS"
            )
            events.append(
                {
                    "index": i,
                    "side": "SELL",
                    "kind": kind,
                    "prior_bias": prior_bias,
                    "level": lo,
                    "pivot_index": lo_idx,
                }
            )
    return events


def detect_bos_choch(
    df: pd.DataFrame | None,
    side: str,
    *,
    max_age_bars: int = 12,
) -> dict[str, Any]:
    """Detect the most recent confirmed structure break.

    BOS means continuation relative to the prior swing structure.
    CHOCH means a break against a previously directional swing structure.
    MIXED prior structure is intentionally labelled MSS rather than over-claiming
    BOS/CHOCH.
    """
    d = _frame(df).tail(140).reset_index(drop=True)
    side = str(side).upper()
    if len(d) < 12 or side not in ("BUY", "SELL"):
        return {
            "status": "⚪ ESTRUTURA INDISPONÍVEL",
            "score": 0,
            "event": "NONE",
            "text": "BOS/CHOCH aguarda M15 válido e direção macro.",
        }

    events = _structure_events(d)
    if not events:
        return {
            "status": "⚪ SEM BOS/CHOCH RECENTE",
            "score": 35,
            "event": "NONE",
            "text": "Nenhum fechamento rompeu swing confirmado recentemente.",
        }

    event = events[-1]
    bars_ago = len(d) - 1 - int(event["index"])
    event_side = str(event["side"])
    kind = str(event["kind"])
    ts = d.loc[int(event["index"]), "datetime"] if "datetime" in d.columns else None

    if bars_ago > int(max_age_bars):
        status = "⚪ QUEBRA ANTIGA — AGUARDAR NOVA ESTRUTURA"
        score = 35
    elif event_side != side:
        status = f"🔴 {kind} CONTRÁRIO AO MACRO"
        score = 20
    elif kind == "BOS":
        status = "🟢 BOS CONFIRMADO"
        score = 100
    elif kind == "CHOCH":
        status = "🟢 CHOCH CONFIRMADO"
        score = 92
    else:
        status = "🟡 MSS / QUEBRA EM ESTRUTURA MISTA"
        score = 68

    return {
        "status": status,
        "score": score,
        "event": kind,
        "event_side": event_side,
        "prior_bias": event["prior_bias"],
        "level": float(event["level"]),
        "bars_ago": int(bars_ago),
        "break_time": pd.Timestamp(ts).isoformat() if ts is not None and pd.notna(ts) else "",
        "text": (
            f"{kind} {event_side} por fechamento além do swing confirmado "
            f"({float(event['level']):.5f}); estrutura anterior {event['prior_bias']}."
        ),
    }


def detect_order_block(
    df: pd.DataFrame | None,
    side: str,
    *,
    max_structure_age: int = 16,
) -> dict[str, Any]:
    """Detect a conservative rule-based Order Block candidate.

    Requirements:
    1) recent structure break aligned with side;
    2) break candle has directional displacement relative to ATR;
    3) last opposing candle before the break defines the candidate zone.

    The zone is the full high/low range of that opposing candle. A closing break
    through the far edge invalidates it. This is an auditable heuristic, not a
    claim about real institutional orders.
    """
    d = _frame(df).tail(160).reset_index(drop=True)
    side = str(side).upper()
    if len(d) < 14 or side not in ("BUY", "SELL"):
        return {
            "status": "⚪ SEM ORDER BLOCK",
            "score": 0,
            "text": "Order Block aguarda M15 suficiente e direção macro.",
        }

    events = [
        e for e in _structure_events(d)
        if e["side"] == side and len(d) - 1 - int(e["index"]) <= int(max_structure_age)
    ]
    if not events:
        return {
            "status": "⚪ SEM ORDER BLOCK VALIDADO",
            "score": 30,
            "text": "Não há quebra estrutural recente alinhada para validar um Order Block.",
        }

    event = events[-1]
    break_idx = int(event["index"])
    atr = _atr(d)
    atr_value = float(atr.iloc[break_idx]) if break_idx < len(atr) and pd.notna(atr.iloc[break_idx]) else 0.0
    row = d.loc[break_idx]
    body = abs(float(row["close"]) - float(row["open"]))
    candle_range = max(float(row["high"]) - float(row["low"]), 0.0)
    body_atr = body / atr_value if atr_value > 0 else 0.0
    range_atr = candle_range / atr_value if atr_value > 0 else 0.0
    directional = (
        float(row["close"]) > float(row["open"])
        if side == "BUY"
        else float(row["close"]) < float(row["open"])
    )
    displacement_ok = directional and body_atr >= 0.65 and range_atr >= 0.85
    if not displacement_ok:
        return {
            "status": "⚪ SEM ORDER BLOCK VALIDADO",
            "score": 35,
            "structure_event": event["kind"],
            "body_atr": round(body_atr, 2),
            "range_atr": round(range_atr, 2),
            "text": "Há quebra de estrutura, mas falta displacement suficiente para validar a zona de origem.",
        }

    candidate = None
    for j in range(break_idx - 1, max(-1, break_idx - 9), -1):
        o = float(d.loc[j, "open"])
        c = float(d.loc[j, "close"])
        opposite = c < o if side == "BUY" else c > o
        if opposite:
            candidate = j
            break

    if candidate is None:
        return {
            "status": "⚪ SEM ORDER BLOCK VALIDADO",
            "score": 35,
            "structure_event": event["kind"],
            "text": "Quebra + displacement existem, mas não há candle oposto de origem claro.",
        }

    zlow = float(d.loc[candidate, "low"])
    zhigh = float(d.loc[candidate, "high"])
    future = d.iloc[break_idx + 1 :]
    current = d.iloc[-1]
    price = float(current["close"])

    if side == "BUY":
        invalidated = (not future.empty) and bool((future["close"] < zlow).any())
    else:
        invalidated = (not future.empty) and bool((future["close"] > zhigh).any())

    touched = False
    if not future.empty:
        touched = bool(((future["low"] <= zhigh) & (future["high"] >= zlow)).any())
    inside = zlow <= price <= zhigh

    if invalidated:
        status, score = "🔴 ORDER BLOCK INVALIDADO", 10
        text = "A zona candidata foi invalidada por fechamento além da borda oposta."
    elif inside:
        status, score = "🟢 ORDER BLOCK EM MITIGAÇÃO", 92
        text = "Preço está dentro do Order Block ainda válido após quebra + displacement."
    elif touched:
        status, score = "🟡 ORDER BLOCK MITIGADO / ATIVO", 72
        text = "Order Block já recebeu mitigação e segue válido, mas o preço não está dentro da zona."
    else:
        status, score = "🟡 ORDER BLOCK ATIVO", 68
        text = "Order Block validado por quebra + displacement; ainda sem mitigação posterior."

    origin_ts = d.loc[candidate, "datetime"] if "datetime" in d.columns else None
    break_ts = d.loc[break_idx, "datetime"] if "datetime" in d.columns else None
    return {
        "status": status,
        "score": score,
        "side": side,
        "structure_event": event["kind"],
        "zone_low": zlow,
        "zone_high": zhigh,
        "price": price,
        "inside": bool(inside),
        "mitigated": bool(touched),
        "invalidated": bool(invalidated),
        "body_atr": round(body_atr, 2),
        "range_atr": round(range_atr, 2),
        "origin_time": pd.Timestamp(origin_ts).isoformat() if origin_ts is not None and pd.notna(origin_ts) else "",
        "break_time": pd.Timestamp(break_ts).isoformat() if break_ts is not None and pd.notna(break_ts) else "",
        "text": text,
    }


def build_structure_snapshot(
    m15: pd.DataFrame | None,
    side: str,
) -> dict[str, Any]:
    """Return observational structure components without changing execution gates."""
    structure = detect_bos_choch(m15, side)
    order_block = detect_order_block(m15, side)
    return {
        "side": str(side).upper(),
        "structure": structure,
        "order_block": order_block,
        "algorithm_note": (
            "BOS/CHOCH e Order Block são leituras determinísticas/observacionais; "
            "não representam probabilidade de lucro nem ordens institucionais reais."
        ),
        "updated_at": pd.Timestamp.now(tz="UTC").isoformat(),
    }
