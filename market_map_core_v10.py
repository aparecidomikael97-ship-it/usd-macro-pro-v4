"""Pure market-map rules for USD Macro Pro V10.

This module intentionally contains no Streamlit or network calls.  It turns
OHLC data into higher-timeframe context, liquidity references, ICT-style time
windows and an observational alignment summary.  The outputs are context, not
profit probabilities and do not alter the legacy Score Mestre.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Any, Iterable, Mapping
from zoneinfo import ZoneInfo
import math

import numpy as np
import pandas as pd

NY_TZ = ZoneInfo("America/New_York")

KILLZONES_NY = (
    ("Asian Range", time(20, 0), time(0, 0)),
    ("London Killzone", time(2, 0), time(5, 0)),
    ("New York AM", time(7, 0), time(10, 0)),
    ("London Close", time(10, 0), time(12, 0)),
    ("New York PM", time(13, 30), time(16, 0)),
)

QUARTER_PHASES = {
    1: "Q1 · Acumulação / construção de contexto",
    2: "Q2 · Manipulação / busca de liquidez",
    3: "Q3 · Expansão / distribuição",
    4: "Q4 · Continuação / reversão / reequilíbrio",
}


def _as_utc(ts: Any) -> pd.Timestamp:
    out = pd.Timestamp(ts)
    if out.tzinfo is None:
        return out.tz_localize("UTC")
    return out.tz_convert("UTC")


def normalize_ohlc(values: Any) -> pd.DataFrame:
    """Return a clean UTC OHLC frame from Twelve Data-like values.

    Invalid/missing/non-positive bars and impossible OHLC geometry are removed.
    Duplicate timestamps are resolved by keeping the last observation.
    """
    if isinstance(values, pd.DataFrame):
        df = values.copy()
    else:
        try:
            df = pd.DataFrame(values or [])
        except Exception:
            return pd.DataFrame(columns=["datetime", "open", "high", "low", "close"])

    required = ["datetime", "open", "high", "low", "close"]
    if any(c not in df.columns for c in required):
        return pd.DataFrame(columns=required)

    d = df[required].copy()
    d["datetime"] = pd.to_datetime(d["datetime"], utc=True, errors="coerce")
    for c in ("open", "high", "low", "close"):
        d[c] = pd.to_numeric(d[c], errors="coerce")
    d = d.dropna(subset=required)
    if d.empty:
        return d.reset_index(drop=True)

    finite = np.isfinite(d[["open", "high", "low", "close"]]).all(axis=1)
    positive = (d[["open", "high", "low", "close"]] > 0).all(axis=1)
    geometry = (
        d["high"].ge(d[["open", "close", "low"]].max(axis=1))
        & d["low"].le(d[["open", "close", "high"]].min(axis=1))
    )
    d = d[finite & positive & geometry]
    return (
        d.sort_values("datetime")
        .drop_duplicates(subset=["datetime"], keep="last")
        .reset_index(drop=True)
    )


def aggregate_ohlc(frame: pd.DataFrame, rule: str) -> pd.DataFrame:
    """Aggregate OHLC bars using a pandas resample rule (e.g. W-FRI, ME)."""
    d = normalize_ohlc(frame)
    if d.empty:
        return d
    idx = d.set_index("datetime")
    agg = idx.resample(rule, label="right", closed="right").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last"}
    )
    return agg.dropna().reset_index()


def completed_daily(frame: pd.DataFrame, today: date | str | None = None) -> pd.DataFrame:
    """Exclude the provider's current calendar-day bar from daily context."""
    d = normalize_ohlc(frame)
    if d.empty:
        return d
    if today is None:
        today = datetime.now(NY_TZ).date()
    today = pd.Timestamp(today).date()
    return d[d["datetime"].dt.date < today].reset_index(drop=True)


def _atr(frame: pd.DataFrame, length: int = 14) -> float | None:
    d = normalize_ohlc(frame)
    if len(d) < 2:
        return None
    prev = d["close"].shift(1)
    tr = pd.concat(
        [(d["high"] - d["low"]), (d["high"] - prev).abs(), (d["low"] - prev).abs()],
        axis=1,
    ).max(axis=1)
    value = tr.rolling(length, min_periods=max(2, min(length, len(d)) // 2)).mean().iloc[-1]
    return float(value) if pd.notna(value) and math.isfinite(float(value)) else None


def swing_points(frame: pd.DataFrame, wing: int = 2) -> tuple[list[tuple[pd.Timestamp, float]], list[tuple[pd.Timestamp, float]]]:
    """Return pivot highs and lows using a symmetric fractal wing."""
    d = normalize_ohlc(frame)
    highs: list[tuple[pd.Timestamp, float]] = []
    lows: list[tuple[pd.Timestamp, float]] = []
    if len(d) < wing * 2 + 1:
        return highs, lows
    for i in range(wing, len(d) - wing):
        h = float(d.iloc[i]["high"])
        l = float(d.iloc[i]["low"])
        h_window = d.iloc[i - wing : i + wing + 1]["high"]
        l_window = d.iloc[i - wing : i + wing + 1]["low"]
        if h >= float(h_window.max()) and (h_window == h).sum() == 1:
            highs.append((d.iloc[i]["datetime"], h))
        if l <= float(l_window.min()) and (l_window == l).sum() == 1:
            lows.append((d.iloc[i]["datetime"], l))
    return highs, lows


def _compare_levels(a: float, b: float, tolerance: float, higher_code: str, lower_code: str, equal_code: str) -> str:
    if abs(a - b) <= tolerance:
        return equal_code
    return higher_code if a > b else lower_code


def market_structure(frame: pd.DataFrame, wing: int = 2) -> dict[str, Any]:
    d = normalize_ohlc(frame)
    if d.empty:
        return {"bias": "NEUTRO", "high_state": "—", "low_state": "—", "highs": [], "lows": []}
    highs, lows = swing_points(d, wing=wing)
    atr = _atr(d) or max(float(d.iloc[-1]["close"]) * 0.001, 1e-9)
    tol = atr * 0.08
    high_state = "—"
    low_state = "—"
    if len(highs) >= 2:
        high_state = _compare_levels(highs[-1][1], highs[-2][1], tol, "HH", "LH", "EQH")
    if len(lows) >= 2:
        low_state = _compare_levels(lows[-1][1], lows[-2][1], tol, "HL", "LL", "EQL")

    if high_state in ("HH", "EQH") and low_state == "HL":
        bias = "ALTISTA"
    elif high_state == "HH" and low_state in ("HL", "EQL"):
        bias = "ALTISTA"
    elif high_state in ("LH", "EQH") and low_state == "LL":
        bias = "BAIXISTA"
    elif high_state == "LH" and low_state in ("LL", "EQL"):
        bias = "BAIXISTA"
    else:
        bias = "NEUTRO"

    return {
        "bias": bias,
        "high_state": high_state,
        "low_state": low_state,
        "highs": highs,
        "lows": lows,
        "atr": atr,
    }


def trend_context(frame: pd.DataFrame) -> dict[str, Any]:
    """Directional context from structure + EMA regime, not a trade signal."""
    d = normalize_ohlc(frame)
    if len(d) < 15:
        return {
            "bias": "NEUTRO", "score": 50.0, "ema20": None, "ema50": None,
            "structure": market_structure(d), "reason": "Histórico insuficiente.",
        }

    close = d["close"].astype(float)
    ema20_s = close.ewm(span=20, adjust=False).mean()
    ema50_s = close.ewm(span=50, adjust=False).mean()
    ema20 = float(ema20_s.iloc[-1])
    ema50 = float(ema50_s.iloc[-1])
    last = float(close.iloc[-1])
    slope_n = min(5, len(d) - 1)
    slope = float(ema20_s.iloc[-1] - ema20_s.iloc[-1 - slope_n]) if slope_n > 0 else 0.0
    struct = market_structure(d)

    points = 0.0
    points += 1.0 if last > ema20 else -1.0 if last < ema20 else 0.0
    points += 1.0 if ema20 > ema50 else -1.0 if ema20 < ema50 else 0.0
    points += 1.0 if slope > 0 else -1.0 if slope < 0 else 0.0
    points += 2.0 if struct["bias"] == "ALTISTA" else -2.0 if struct["bias"] == "BAIXISTA" else 0.0
    score = float(np.clip(50.0 + points * 10.0, 0.0, 100.0))
    bias = "ALTISTA" if score >= 65 else "BAIXISTA" if score <= 35 else "NEUTRO"

    reasons = []
    reasons.append("preço acima da EMA20" if last > ema20 else "preço abaixo da EMA20")
    reasons.append("EMA20 acima da EMA50" if ema20 > ema50 else "EMA20 abaixo da EMA50")
    reasons.append(f"estrutura {struct['high_state']}/{struct['low_state']}")
    return {
        "bias": bias,
        "score": score,
        "ema20": ema20,
        "ema50": ema50,
        "last": last,
        "structure": struct,
        "reason": " · ".join(reasons),
    }


def _current_period_end(today: date, freq: str) -> date:
    return pd.Timestamp(today).to_period(freq).end_time.date()


def prior_period_levels(daily_frame: pd.DataFrame, today: date | str | None = None) -> dict[str, float]:
    """Return PDH/PDL, PWH/PWL and PMH/PML from completed periods."""
    if today is None:
        today = datetime.now(NY_TZ).date()
    today = pd.Timestamp(today).date()
    d = completed_daily(daily_frame, today)
    levels: dict[str, float] = {}
    if d.empty:
        return levels

    last_day = d.iloc[-1]
    levels["PDH"] = float(last_day["high"])
    levels["PDL"] = float(last_day["low"])

    weekly = aggregate_ohlc(d, "W-FRI")
    if not weekly.empty:
        current_end = _current_period_end(today, "W-FRI")
        closed = weekly[weekly["datetime"].dt.date < current_end]
        if not closed.empty:
            row = closed.iloc[-1]
            levels["PWH"] = float(row["high"])
            levels["PWL"] = float(row["low"])

    monthly = aggregate_ohlc(d, "ME")
    if not monthly.empty:
        current_end = _current_period_end(today, "M")
        closed = monthly[monthly["datetime"].dt.date < current_end]
        if not closed.empty:
            row = closed.iloc[-1]
            levels["PMH"] = float(row["high"])
            levels["PML"] = float(row["low"])
    return levels


def equal_liquidity_levels(frame: pd.DataFrame, lookback: int = 80, wing: int = 2) -> dict[str, float]:
    """Find the most recent approximate equal high/low clusters."""
    d = normalize_ohlc(frame).tail(max(lookback, wing * 2 + 2))
    if d.empty:
        return {}
    highs, lows = swing_points(d, wing=wing)
    atr = _atr(d) or float(d.iloc[-1]["close"]) * 0.001
    tol = max(atr * 0.15, float(d.iloc[-1]["close"]) * 0.00025)
    out: dict[str, float] = {}

    for points, name in ((highs, "EQH"), (lows, "EQL")):
        found = None
        for i in range(len(points) - 1, 0, -1):
            for j in range(i - 1, -1, -1):
                if abs(points[i][1] - points[j][1]) <= tol:
                    found = (points[i][1] + points[j][1]) / 2.0
                    break
            if found is not None:
                break
        if found is not None:
            out[name] = float(found)
    return out


def pip_size(pair: str) -> float:
    return 0.01 if "JPY" in str(pair).upper() else 0.0001


def liquidity_rows(current_price: float, levels: Mapping[str, Any], pair: str) -> list[dict[str, Any]]:
    p = float(current_price)
    pip = pip_size(pair)
    rows = []
    for name, raw in levels.items():
        try:
            level = float(raw)
        except (TypeError, ValueError):
            continue
        if not math.isfinite(level) or level <= 0:
            continue
        side = "BSL · acima" if level > p else "SSL · abaixo" if level < p else "No preço"
        distance = abs(level - p) / pip
        rows.append({"Nível": str(name), "Preço": level, "Lado": side, "Distância (pips)": distance})
    return sorted(rows, key=lambda r: r["Distância (pips)"])


def nearest_liquidity(current_price: float, levels: Mapping[str, Any]) -> tuple[tuple[str, float] | None, tuple[str, float] | None]:
    p = float(current_price)
    above: list[tuple[str, float]] = []
    below: list[tuple[str, float]] = []
    for name, raw in levels.items():
        try:
            value = float(raw)
        except (TypeError, ValueError):
            continue
        if value > p:
            above.append((str(name), value))
        elif value < p:
            below.append((str(name), value))
    return (min(above, key=lambda x: x[1] - p) if above else None,
            min(below, key=lambda x: p - x[1]) if below else None)


def premium_discount(current_price: float, low: float | None, high: float | None) -> dict[str, Any]:
    try:
        p, lo, hi = float(current_price), float(low), float(high)
    except (TypeError, ValueError):
        return {"zone": "INDEFINIDO", "position": None, "equilibrium": None}
    if not (math.isfinite(p) and math.isfinite(lo) and math.isfinite(hi)) or hi <= lo:
        return {"zone": "INDEFINIDO", "position": None, "equilibrium": None}
    position = (p - lo) / (hi - lo) * 100.0
    zone = "DESCONTO" if position < 45 else "PRÊMIO" if position > 55 else "EQUILÍBRIO"
    return {"zone": zone, "position": float(position), "equilibrium": (hi + lo) / 2.0}


def _combine_local(day: date, t: time) -> datetime:
    return datetime.combine(day, t, tzinfo=NY_TZ)


def _window_for_day(day: date, start: time, end: time) -> tuple[datetime, datetime]:
    s = _combine_local(day, start)
    e_day = day + timedelta(days=1) if end <= start else day
    e = _combine_local(e_day, end)
    return s, e


def killzone_state(now: Any = None) -> dict[str, Any]:
    """Return active and next ICT-style time window anchored to New York time."""
    if now is None:
        now_ny = datetime.now(NY_TZ)
    else:
        ts = pd.Timestamp(now)
        if ts.tzinfo is None:
            ts = ts.tz_localize(NY_TZ)
        else:
            ts = ts.tz_convert(NY_TZ)
        now_ny = ts.to_pydatetime()

    windows: list[dict[str, Any]] = []
    for delta in (-1, 0, 1):
        day = now_ny.date() + timedelta(days=delta)
        for name, start, end in KILLZONES_NY:
            s, e = _window_for_day(day, start, end)
            windows.append({"name": name, "start": s, "end": e})
    active = [w for w in windows if w["start"] <= now_ny < w["end"]]
    future = [w for w in windows if w["start"] > now_ny]
    nxt = min(future, key=lambda w: w["start"]) if future else None
    return {
        "now_ny": now_ny,
        "active": active[0] if active else None,
        "next": nxt,
        "windows": sorted(windows, key=lambda w: w["start"]),
    }


def quarterly_clock(now: Any = None, anchor_hour: int = 0) -> dict[str, Any]:
    """Split the NY day into four 6h macro quarters and four 90m micro quarters.

    ``anchor_hour`` is intentionally configurable because Quarterly Theory has
    multiple public conventions.  The app treats this as a time scaffold, not a
    claim that price must follow the named phase.
    """
    if anchor_hour not in (0, 18):
        raise ValueError("anchor_hour must be 0 or 18")
    if now is None:
        now_ny = datetime.now(NY_TZ)
    else:
        ts = pd.Timestamp(now)
        if ts.tzinfo is None:
            ts = ts.tz_localize(NY_TZ)
        else:
            ts = ts.tz_convert(NY_TZ)
        now_ny = ts.to_pydatetime()

    anchor = _combine_local(now_ny.date(), time(anchor_hour, 0))
    if now_ny < anchor:
        anchor -= timedelta(days=1)
    elapsed_min = int((now_ny - anchor).total_seconds() // 60)
    quarter = min(4, elapsed_min // 360 + 1)
    q_start = anchor + timedelta(hours=(quarter - 1) * 6)
    q_end = q_start + timedelta(hours=6)
    within = int((now_ny - q_start).total_seconds() // 60)
    micro = min(4, within // 90 + 1)
    micro_start = q_start + timedelta(minutes=(micro - 1) * 90)
    micro_end = micro_start + timedelta(minutes=90)
    return {
        "quarter": quarter,
        "phase": QUARTER_PHASES[quarter],
        "quarter_start": q_start,
        "quarter_end": q_end,
        "micro": micro,
        "micro_start": micro_start,
        "micro_end": micro_end,
        "anchor_hour": anchor_hour,
        "now_ny": now_ny,
    }


def session_range(frame: pd.DataFrame, now: Any = None, start: time = time(20, 0), end: time = time(0, 0)) -> dict[str, Any]:
    """Return the latest active or completed NY-time session range from intraday bars."""
    d = normalize_ohlc(frame)
    if d.empty:
        return {"available": False}
    if now is None:
        now_ny = datetime.now(NY_TZ)
    else:
        ts = pd.Timestamp(now)
        if ts.tzinfo is None:
            ts = ts.tz_localize(NY_TZ)
        else:
            ts = ts.tz_convert(NY_TZ)
        now_ny = ts.to_pydatetime()

    local = d.copy()
    local["datetime_ny"] = local["datetime"].dt.tz_convert(NY_TZ)
    candidates = []
    for delta in range(0, 7):
        day = now_ny.date() - timedelta(days=delta)
        s, e = _window_for_day(day, start, end)
        if s > now_ny:
            continue
        active = s <= now_ny < e
        end_eff = min(now_ny, e)
        mask = (local["datetime_ny"] >= s) & (local["datetime_ny"] < end_eff)
        part = local.loc[mask]
        if not part.empty:
            candidates.append((s, e, active, part))
            if active:
                break
            if e <= now_ny:
                break
    if not candidates:
        return {"available": False}
    s, e, active, part = candidates[0]
    return {
        "available": True,
        "active": bool(active),
        "start": s,
        "end": e,
        "high": float(part["high"].max()),
        "low": float(part["low"].min()),
        "open": float(part.iloc[0]["open"]),
        "close": float(part.iloc[-1]["close"]),
        "bars": int(len(part)),
    }


def ny_midnight_open(frame: pd.DataFrame, now: Any = None) -> float | None:
    d = normalize_ohlc(frame)
    if d.empty:
        return None
    if now is None:
        now_ny = datetime.now(NY_TZ)
    else:
        ts = pd.Timestamp(now)
        if ts.tzinfo is None:
            ts = ts.tz_localize(NY_TZ)
        else:
            ts = ts.tz_convert(NY_TZ)
        now_ny = ts.to_pydatetime()
    local = d.copy()
    local["datetime_ny"] = local["datetime"].dt.tz_convert(NY_TZ)
    start = _combine_local(now_ny.date(), time(0, 0))
    end = start + timedelta(days=1)
    part = local[(local["datetime_ny"] >= start) & (local["datetime_ny"] < end)]
    if part.empty:
        return None
    return float(part.iloc[0]["open"])


def recent_sweeps(frame: pd.DataFrame, levels: Mapping[str, Any], bars: int = 12) -> list[dict[str, Any]]:
    """Detect simple liquidity sweeps: breach a level and close back across it."""
    d = normalize_ohlc(frame).tail(max(1, int(bars)))
    out: list[dict[str, Any]] = []
    if d.empty:
        return out
    for _, row in d.iterrows():
        h, l, c = float(row["high"]), float(row["low"]), float(row["close"])
        for name, raw in levels.items():
            try:
                lv = float(raw)
            except (TypeError, ValueError):
                continue
            if h > lv and c < lv:
                out.append({"level": str(name), "type": "SWEEP BSL", "datetime": row["datetime"], "price": lv})
            elif l < lv and c > lv:
                out.append({"level": str(name), "type": "SWEEP SSL", "datetime": row["datetime"], "price": lv})
    # de-duplicate, keeping the most recent hit per level/type
    dedup: dict[tuple[str, str], dict[str, Any]] = {}
    for item in out:
        dedup[(item["level"], item["type"])] = item
    return sorted(dedup.values(), key=lambda x: x["datetime"], reverse=True)


def macro_side(direction: str) -> str:
    u = str(direction).upper()
    if "COMPRA" in u or "BUY" in u:
        return "ALTISTA"
    if "VENDA" in u or "SELL" in u:
        return "BAIXISTA"
    return "NEUTRO"


def alignment_summary(
    macro_direction: str,
    weekly_bias: str,
    daily_bias: str,
    pd_zone: str = "INDEFINIDO",
    latest_sweep: str = "",
    killzone_active: bool = False,
) -> dict[str, Any]:
    """Observational 0..5 checklist; deliberately not a probability."""
    side = macro_side(macro_direction)
    checks: list[tuple[str, bool | None]] = []
    checks.append(("Macro x W1", None if side == "NEUTRO" else weekly_bias == side))
    checks.append(("Macro x D1", None if side == "NEUTRO" else daily_bias == side))
    loc_ok = None
    if side == "ALTISTA" and pd_zone != "INDEFINIDO":
        loc_ok = pd_zone in ("DESCONTO", "EQUILÍBRIO")
    elif side == "BAIXISTA" and pd_zone != "INDEFINIDO":
        loc_ok = pd_zone in ("PRÊMIO", "EQUILÍBRIO")
    checks.append(("Localização P/D", loc_ok))

    sweep_ok = None
    if latest_sweep:
        if side == "ALTISTA":
            sweep_ok = "SSL" in latest_sweep
        elif side == "BAIXISTA":
            sweep_ok = "BSL" in latest_sweep
    checks.append(("Sweep coerente", sweep_ok))
    checks.append(("Killzone ativa", bool(killzone_active)))

    available = [ok for _, ok in checks if ok is not None]
    passed = sum(bool(ok) for ok in available)
    total = len(available)
    ratio = passed / total if total else 0.0
    label = "ALTO" if total >= 3 and ratio >= 0.75 else "MÉDIO" if total >= 2 and ratio >= 0.5 else "BAIXO"
    return {"label": label, "passed": passed, "total": total, "checks": checks, "ratio": ratio}
