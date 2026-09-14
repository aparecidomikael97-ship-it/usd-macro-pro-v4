"""Pure market-map rules for USD Macro Pro V10.2 Professional.

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


def structure_regime(high_state: str, low_state: str) -> dict[str, str]:
    """Classify swing geometry without forcing a trend when highs/lows conflict."""
    hs, ls = str(high_state), str(low_state)
    if hs == "HH" and ls == "HL":
        return {"bias": "ALTISTA", "regime": "TENDÊNCIA ALTISTA", "quality": "CONFIRMADA"}
    if hs == "LH" and ls == "LL":
        return {"bias": "BAIXISTA", "regime": "TENDÊNCIA BAIXISTA", "quality": "CONFIRMADA"}
    if hs == "HH" and ls == "LL":
        return {"bias": "NEUTRO", "regime": "EXPANSÃO DOS DOIS LADOS", "quality": "MISTA"}
    if hs == "LH" and ls == "HL":
        return {"bias": "NEUTRO", "regime": "COMPRESSÃO", "quality": "MISTA"}
    if "EQ" in hs or "EQ" in ls:
        return {"bias": "NEUTRO", "regime": "EQUILÍBRIO / LIQUIDEZ", "quality": "MISTA"}
    return {"bias": "NEUTRO", "regime": "ESTRUTURA INCOMPLETA", "quality": "INCOMPLETA"}


def market_structure(frame: pd.DataFrame, wing: int = 2) -> dict[str, Any]:
    d = normalize_ohlc(frame)
    if d.empty:
        return {"bias": "NEUTRO", "high_state": "—", "low_state": "—", "regime": "SEM DADOS", "quality": "INCOMPLETA", "highs": [], "lows": []}
    highs, lows = swing_points(d, wing=wing)
    atr = _atr(d) or max(float(d.iloc[-1]["close"]) * 0.001, 1e-9)
    tol = atr * 0.08
    high_state = "—"
    low_state = "—"
    if len(highs) >= 2:
        high_state = _compare_levels(highs[-1][1], highs[-2][1], tol, "HH", "LH", "EQH")
    if len(lows) >= 2:
        low_state = _compare_levels(lows[-1][1], lows[-2][1], tol, "HL", "LL", "EQL")
    reg = structure_regime(high_state, low_state)
    return {
        "bias": reg["bias"],
        "high_state": high_state,
        "low_state": low_state,
        "regime": reg["regime"],
        "quality": reg["quality"],
        "highs": highs,
        "lows": lows,
        "atr": atr,
    }


def trend_context(frame: pd.DataFrame) -> dict[str, Any]:
    """Top-down context from EMA regime plus explicit swing-structure confirmation."""
    d = normalize_ohlc(frame)
    if len(d) < 15:
        return {
            "bias": "NEUTRO", "score": 50.0, "ema20": None, "ema50": None,
            "structure": market_structure(d), "reason": "Histórico insuficiente.",
            "ema_bias": "NEUTRO", "confirmation": "INCOMPLETA",
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

    ema_points = 0.0
    ema_points += 1.0 if last > ema20 else -1.0 if last < ema20 else 0.0
    ema_points += 1.0 if ema20 > ema50 else -1.0 if ema20 < ema50 else 0.0
    ema_points += 1.0 if slope > 0 else -1.0 if slope < 0 else 0.0
    ema_bias = "ALTISTA" if ema_points >= 2 else "BAIXISTA" if ema_points <= -2 else "NEUTRO"

    struct_points = 2.0 if struct["bias"] == "ALTISTA" else -2.0 if struct["bias"] == "BAIXISTA" else 0.0
    score = float(np.clip(50.0 + (ema_points + struct_points) * 10.0, 0.0, 100.0))
    bias = "ALTISTA" if score >= 65 else "BAIXISTA" if score <= 35 else "NEUTRO"

    if struct["bias"] == bias and bias != "NEUTRO":
        confirmation = "CONFIRMADA"
    elif struct["bias"] == "NEUTRO" and bias != "NEUTRO":
        confirmation = "PARCIAL · MÉDIAS SEM ESTRUTURA LIMPA"
    elif struct["bias"] != "NEUTRO" and bias != "NEUTRO":
        confirmation = "CONFLITO"
    else:
        confirmation = "NEUTRA"

    reasons = [
        "preço acima da EMA20" if last > ema20 else "preço abaixo da EMA20",
        "EMA20 acima da EMA50" if ema20 > ema50 else "EMA20 abaixo da EMA50",
        "EMA20 inclinando para cima" if slope > 0 else "EMA20 inclinando para baixo" if slope < 0 else "EMA20 lateral",
        f"estrutura {struct['high_state']}/{struct['low_state']} · {struct['regime']}",
    ]
    return {
        "bias": bias,
        "score": score,
        "ema20": ema20,
        "ema50": ema50,
        "last": last,
        "ema_bias": ema_bias,
        "confirmation": confirmation,
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


def liquidity_kind(name: str) -> str:
    """Return the semantic pool type. High-side pools are BSL; low-side pools are SSL."""
    n = str(name).strip().upper()
    bsl_exact = {"PDH", "PWH", "PMH", "EQH", "ASIA HIGH"}
    ssl_exact = {"PDL", "PWL", "PML", "EQL", "ASIA LOW"}
    if n in bsl_exact or n.endswith(" HIGH") or "SWING HIGH" in n:
        return "BSL"
    if n in ssl_exact or n.endswith(" LOW") or "SWING LOW" in n:
        return "SSL"
    return "REFERÊNCIA"


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
        kind = liquidity_kind(str(name))
        distance = abs(level - p) / pip
        if kind == "BSL":
            status = "🟢 DISPONÍVEL ACIMA" if level > p else "⚪ JÁ NEGOCIADA / ATRÁS DO PREÇO"
        elif kind == "SSL":
            status = "🟢 DISPONÍVEL ABAIXO" if level < p else "⚪ JÁ NEGOCIADA / ATRÁS DO PREÇO"
        else:
            status = "🔵 REFERÊNCIA" 
        rows.append({
            "Nível": str(name), "Preço": level, "Tipo": kind,
            "Status": status, "Distância (pips)": distance,
        })
    priority = {"BSL": 0, "SSL": 1, "REFERÊNCIA": 2}
    return sorted(rows, key=lambda r: (priority.get(r["Tipo"], 9), r["Distância (pips)"]))


def nearest_liquidity(current_price: float, levels: Mapping[str, Any]) -> tuple[tuple[str, float] | None, tuple[str, float] | None]:
    """Nearest *available* semantic BSL above and SSL below.

    A PDH never becomes SSL simply because price traded above it.  Once behind
    price, it is considered consumed/negotiated and is not a forward target.
    """
    p = float(current_price)
    bsl: list[tuple[str, float]] = []
    ssl: list[tuple[str, float]] = []
    for name, raw in levels.items():
        try:
            value = float(raw)
        except (TypeError, ValueError):
            continue
        kind = liquidity_kind(str(name))
        if kind == "BSL" and value > p:
            bsl.append((str(name), value))
        elif kind == "SSL" and value < p:
            ssl.append((str(name), value))
    return (
        min(bsl, key=lambda x: x[1] - p) if bsl else None,
        min(ssl, key=lambda x: p - x[1]) if ssl else None,
    )


def premium_discount(current_price: float, low: float | None, high: float | None) -> dict[str, Any]:
    try:
        p, lo, hi = float(current_price), float(low), float(high)
    except (TypeError, ValueError):
        return {"zone": "INDEFINIDO", "position": None, "equilibrium": None, "inside_range": None, "expansion_pct": None}
    if not (math.isfinite(p) and math.isfinite(lo) and math.isfinite(hi)) or hi <= lo:
        return {"zone": "INDEFINIDO", "position": None, "equilibrium": None, "inside_range": None, "expansion_pct": None}
    position = (p - lo) / (hi - lo) * 100.0
    if position > 100:
        zone = "ACIMA DO RANGE"
        expansion = position - 100.0
        inside = False
    elif position < 0:
        zone = "ABAIXO DO RANGE"
        expansion = abs(position)
        inside = False
    else:
        zone = "DESCONTO" if position < 45 else "PRÊMIO" if position > 55 else "EQUILÍBRIO"
        expansion = 0.0
        inside = True
    return {
        "zone": zone, "position": float(position), "equilibrium": (hi + lo) / 2.0,
        "inside_range": inside, "expansion_pct": float(expansion),
    }


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


def adr_context(daily_frame: pd.DataFrame, intraday_frame: pd.DataFrame, now: Any = None, length: int = 14) -> dict[str, Any]:
    """Average Daily Range context using completed daily bars + current NY-day intraday range.

    This is a volatility/exhaustion filter, not a directional indicator.  It helps
    avoid chasing a move after the market has already consumed most of its recent
    average daily range.
    """
    if now is None:
        now_ny = datetime.now(NY_TZ)
    else:
        ts = pd.Timestamp(now)
        if ts.tzinfo is None:
            ts = ts.tz_localize(NY_TZ)
        else:
            ts = ts.tz_convert(NY_TZ)
        now_ny = ts.to_pydatetime()

    d = completed_daily(daily_frame, now_ny.date())
    i = normalize_ohlc(intraday_frame)
    if d.empty or i.empty:
        return {"available": False, "adr": None, "today_range": None, "used_pct": None, "state": "SEM DADOS"}

    daily_ranges = (d["high"] - d["low"]).tail(max(3, int(length)))
    if daily_ranges.empty:
        return {"available": False, "adr": None, "today_range": None, "used_pct": None, "state": "SEM DADOS"}
    adr = float(daily_ranges.mean())
    if not math.isfinite(adr) or adr <= 0:
        return {"available": False, "adr": None, "today_range": None, "used_pct": None, "state": "SEM DADOS"}

    local = i.copy()
    local["datetime_ny"] = local["datetime"].dt.tz_convert(NY_TZ)
    part = local[local["datetime_ny"].dt.date == now_ny.date()]
    if part.empty:
        return {"available": False, "adr": adr, "today_range": None, "used_pct": None, "state": "SEM RANGE HOJE"}

    today_range = float(part["high"].max() - part["low"].min())
    used = 100.0 * today_range / adr if adr > 0 else None
    if used is None or not math.isfinite(used):
        state = "SEM DADOS"
    elif used < 60:
        state = "🟢 ESPAÇO DISPONÍVEL"
    elif used < 90:
        state = "🟡 RANGE MODERADO"
    elif used < 120:
        state = "🟠 DIA ESTICADO"
    else:
        state = "🔴 RANGE EXTREMO"
    return {
        "available": True, "adr": adr, "today_range": today_range,
        "used_pct": float(used), "state": state, "length": int(length),
    }


def intraday_open_context(intraday_frame: pd.DataFrame, now: Any = None) -> dict[str, Any]:
    """Return current price versus NY midnight open and current week opening bar."""
    d = normalize_ohlc(intraday_frame)
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
    current = float(local.iloc[-1]["close"])

    day_part = local[local["datetime_ny"].dt.date == now_ny.date()]
    day_open = float(day_part.iloc[0]["open"]) if not day_part.empty else None

    monday = now_ny.date() - timedelta(days=now_ny.weekday())
    week_start = _combine_local(monday, time(0, 0))
    week_part = local[local["datetime_ny"] >= week_start]
    week_open = float(week_part.iloc[0]["open"]) if not week_part.empty else None

    return {
        "available": True, "current": current, "day_open": day_open, "week_open": week_open,
        "above_day_open": None if day_open is None else current >= day_open,
        "above_week_open": None if week_open is None else current >= week_open,
    }


def recent_sweeps(frame: pd.DataFrame, levels: Mapping[str, Any], bars: int = 12) -> list[dict[str, Any]]:
    """Detect semantic liquidity sweeps only on levels that are actual BSL/SSL pools."""
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
            kind = liquidity_kind(str(name))
            if kind == "BSL" and h > lv and c < lv:
                out.append({
                    "level": str(name), "type": "SWEEP BSL", "datetime": row["datetime"],
                    "price": lv, "high": h, "low": l, "close": c,
                    "excess_abs": float(h - lv), "rejection": "fechou de volta abaixo do nível",
                })
            elif kind == "SSL" and l < lv and c > lv:
                out.append({
                    "level": str(name), "type": "SWEEP SSL", "datetime": row["datetime"],
                    "price": lv, "high": h, "low": l, "close": c,
                    "excess_abs": float(lv - l), "rejection": "fechou de volta acima do nível",
                })
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
    """Observational checklist; deliberately not a win probability."""
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
            sweep_ok = latest_sweep == "SWEEP SSL"
        elif side == "BAIXISTA":
            sweep_ok = latest_sweep == "SWEEP BSL"
    checks.append(("Sweep coerente", sweep_ok))
    checks.append(("Killzone ativa", bool(killzone_active)))

    available = [ok for _, ok in checks if ok is not None]
    passed = sum(bool(ok) for ok in available)
    total = len(available)
    ratio = passed / total if total else 0.0
    label = "ALTO" if total >= 3 and ratio >= 0.75 else "MÉDIO" if total >= 2 and ratio >= 0.5 else "BAIXO"
    return {"label": label, "passed": passed, "total": total, "checks": checks, "ratio": ratio}


def _direction_sign(side: str) -> int:
    return 1 if side == "ALTISTA" else -1 if side == "BAIXISTA" else 0


def event_risk(event: Mapping[str, Any] | None) -> dict[str, Any]:
    """Conservative event gate when only date/impact are known, not exact release time."""
    if not isinstance(event, Mapping) or not event:
        return {"level": "NORMAL", "score": 1.0, "text": "Sem evento principal identificado na janela atual."}
    days = event.get("dias")
    impact = str(event.get("impacto", "")).upper()
    name = str(event.get("evento", "Evento macro"))
    high = impact in {"MÁXIMO", "MAXIMO", "ALTO", "HIGH", "MAXIMUM"}
    try:
        d = int(days) if days is not None else None
    except Exception:
        d = None
    if high and d == 0:
        return {"level": "ALTO", "score": 0.20, "text": f"{name} é hoje; conferir o horário antes de nova entrada."}
    if high and d == 1:
        return {"level": "ELEVADO", "score": 0.55, "text": f"{name} é amanhã; reduzir agressividade e evitar carregar risco sem plano."}
    if high and d is not None and d <= 3:
        return {"level": "ATENÇÃO", "score": 0.75, "text": f"{name} em {d} dias; narrativa pode mudar rapidamente."}
    return {"level": "NORMAL", "score": 1.0, "text": f"{name}: sem bloqueio temporal forte pela regra atual."}


def macro_regime_summary(pair: str, macro_direction: str, macro_score: float, quality: float,
                         macro_context: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Explain weekly/recent macro consistency using data already produced by the base engine.

    This is a consistency/readiness layer, not a second directional model and not
    a statistical probability.
    """
    ctx = dict(macro_context or {})
    side = macro_side(macro_direction)
    side_sign = _direction_sign(side)
    base, quote = (str(pair).split("/") + [""])[:2]
    usd_pair_sign = 1 if base == "USD" else -1 if quote == "USD" else 0

    components: list[dict[str, Any]] = []
    def add(name: str, raw_sign: int | None, detail: str, weight: float):
        if raw_sign is None or side_sign == 0:
            state = None
        else:
            pair_sign = raw_sign * usd_pair_sign if usd_pair_sign else raw_sign
            state = pair_sign == side_sign if pair_sign != 0 else None
        components.append({"name": name, "ok": state, "detail": detail, "weight": float(weight)})

    usd_score = ctx.get("usd_score")
    if usd_score is not None and usd_pair_sign:
        us = float(usd_score)
        sign = 1 if us >= 58 else -1 if us <= 42 else 0
        add("Regime macro USD", sign, f"USD {us:.0f}/100", 25)

    fed_tone = str(ctx.get("fed_tone", ""))
    if fed_tone and usd_pair_sign:
        ft = fed_tone.lower()
        sign = 1 if ("restr" in ft or "hawk" in ft) else -1 if ("flex" in ft or "dov" in ft or "expans" in ft) else 0
        add("Federal Reserve", sign, fed_tone, 20)

    trend = ctx.get("trend") if isinstance(ctx.get("trend"), Mapping) else {}
    trend_score = trend.get("score") if isinstance(trend, Mapping) else None
    if trend_score is not None and usd_pair_sign:
        ts = float(trend_score)
        sign = 1 if ts >= 57 else -1 if ts <= 43 else 0
        add("Tendência macro recente", sign, f"{ts:.0f}/100", 20)

    surprise = float(ctx.get("surprise_adjustment", 0.0) or 0.0)
    if usd_pair_sign:
        sign = 1 if surprise > 1 else -1 if surprise < -1 else 0
        add("Surpresas econômicas", sign, f"ajuste {surprise:+.1f}", 15)

    fomc_score = ctx.get("fomc_score")
    if fomc_score is not None and usd_pair_sign:
        fs = float(fomc_score)
        sign = 1 if fs >= 55 else -1 if fs <= 45 else 0
        weight = max(5.0, min(20.0, float(ctx.get("fomc_weight", 0.0) or 0.0)))
        add("FOMC", sign, f"{fs:.0f}/100", weight)

    available = [x for x in components if x["ok"] is not None]
    weight_total = sum(x["weight"] for x in available)
    weight_ok = sum(x["weight"] for x in available if x["ok"] is True)
    consistency = (100.0 * weight_ok / weight_total) if weight_total else 50.0
    if side == "NEUTRO":
        weekly_label = "SEM LADO"
    elif consistency >= 75 and float(quality) >= 70:
        weekly_label = "FORTE"
    elif consistency >= 55:
        weekly_label = "MODERADO"
    else:
        weekly_label = "FRÁGIL / CONFLITANTE"

    risk = event_risk(ctx.get("event"))
    # Recent impulse emphasizes fast-changing proxies already computed by the base engine.
    recent_vals = [x for x in components if x["name"] in {"Tendência macro recente", "Surpresas econômicas", "FOMC"} and x["ok"] is not None]
    if not recent_vals:
        recent_label = "NEUTRO / SEM DADO"
    else:
        recent_ratio = sum(x["weight"] for x in recent_vals if x["ok"] is True) / max(1e-9, sum(x["weight"] for x in recent_vals))
        recent_label = "CONFIRMA" if recent_ratio >= 0.67 else "MISTO" if recent_ratio >= 0.34 else "CONTRA"

    return {
        "side": side,
        "weekly_label": weekly_label,
        "consistency": float(consistency),
        "recent_label": recent_label,
        "event_risk": risk,
        "components": components,
        "macro_score": float(macro_score),
        "quality": float(quality),
    }


def setup_readiness(macro_direction: str, macro_score: float, quality: float,
                    weekly_ctx: Mapping[str, Any], daily_ctx: Mapping[str, Any],
                    pd_zone: str, latest_sweep: str, killzone_active: bool,
                    event_risk_level: str = "NORMAL") -> dict[str, Any]:
    """Strict selectivity gate. Score = readiness, never a win probability."""
    side = macro_side(macro_direction)
    checks: list[dict[str, Any]] = []
    def add(name: str, ok: bool | None, weight: float, detail: str):
        checks.append({"name": name, "ok": ok, "weight": float(weight), "detail": detail})

    add("Macro forte", None if side == "NEUTRO" else float(macro_score) >= 70, 15, f"Score {float(macro_score):.0f}/100")
    add("Qualidade dos dados", float(quality) >= 75, 15, f"{float(quality):.0f}%")
    add("W1 alinhado", None if side == "NEUTRO" else weekly_ctx.get("bias") == side, 15, str(weekly_ctx.get("confirmation", "—")))
    add("D1 alinhado", None if side == "NEUTRO" else daily_ctx.get("bias") == side, 15, str(daily_ctx.get("confirmation", "—")))

    struct_ok = None if side == "NEUTRO" else (
        weekly_ctx.get("structure", {}).get("bias") == side and daily_ctx.get("structure", {}).get("bias") == side
    )
    add("Estrutura W1+D1 limpa", struct_ok, 10, f"W1 {weekly_ctx.get('structure',{}).get('regime','—')} · D1 {daily_ctx.get('structure',{}).get('regime','—')}")

    loc_ok = None
    if side == "ALTISTA": loc_ok = pd_zone in {"DESCONTO", "EQUILÍBRIO"}
    elif side == "BAIXISTA": loc_ok = pd_zone in {"PRÊMIO", "EQUILÍBRIO"}
    add("Localização eficiente", loc_ok, 10, pd_zone)

    sweep_ok = None if side == "NEUTRO" else False
    if side == "ALTISTA" and latest_sweep: sweep_ok = latest_sweep == "SWEEP SSL"
    elif side == "BAIXISTA" and latest_sweep: sweep_ok = latest_sweep == "SWEEP BSL"
    add("Sweep coerente", sweep_ok, 8, latest_sweep or "Sem sweep recente")
    add("Killzone ativa", bool(killzone_active), 7, "Ativa" if killzone_active else "Fora da janela")

    risk = str(event_risk_level).upper()
    event_ok = risk not in {"ALTO", "ELEVADO"}
    add("Risco de evento", event_ok, 5, risk)

    available = [x for x in checks if x["ok"] is not None]
    denom = sum(x["weight"] for x in available)
    points = sum(x["weight"] for x in available if x["ok"] is True)
    score = 100.0 * points / denom if denom else 0.0

    hard_conflict = (
        side == "NEUTRO"
        or weekly_ctx.get("bias") != side
        or daily_ctx.get("bias") != side
        or risk == "ALTO"
    )
    if hard_conflict:
        score = min(score, 69.0)
    elif risk == "ELEVADO":
        score = min(score, 77.0)
    if float(macro_score) < 70 or float(quality) < 75:
        score = min(score, 77.0)
    if struct_ok is not True:
        score = min(score, 87.0)
    if loc_ok is not True:
        score = min(score, 77.0)
    if sweep_ok is not True or not bool(killzone_active):
        score = min(score, 87.0)

    if score >= 88 and not hard_conflict:
        grade, action = "A+", "🟢 CONTEXTO DE ALTA SELETIVIDADE"
    elif score >= 78 and not hard_conflict:
        grade, action = "A", "🟢 CONTEXTO FORTE · EXIGIR H4/H1/M15"
    elif score >= 65:
        grade, action = "B", "🟡 AGUARDAR MELHOR TIMING / CONFIRMAÇÃO"
    else:
        grade, action = "WAIT", "🔴 NÃO FORÇAR ENTRADA"
    return {"score": float(score), "grade": grade, "action": action, "checks": checks, "hard_conflict": hard_conflict}


