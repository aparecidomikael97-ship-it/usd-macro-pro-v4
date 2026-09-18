"""AtlasQuant Operational Backtest Engine V1.

Research-only deterministic simulator for objectively defined trade plans.
It does not create macro direction, entries, stops or targets. Those values
must already be present in the signal/plan being tested.

Safety principles:
- no provider/API calls;
- no look-ahead by default: execution starts after the signal candle;
- same-bar stop+target ambiguity is resolved against the strategy (LOSS);
- invalid/missing levels fail closed;
- outputs observed historical outcomes, never probability of future profit.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Iterable, Mapping
import math

import pandas as pd


REQUIRED_CANDLE_COLUMNS = ("datetime", "open", "high", "low", "close")
REQUIRED_SIGNAL_FIELDS = ("signal_time", "side", "entry", "stop", "target")


def _finite(value: Any) -> float | None:
    try:
        out = float(value)
        return out if math.isfinite(out) else None
    except Exception:
        return None


def normalize_candles(frame: pd.DataFrame | None) -> pd.DataFrame:
    if not isinstance(frame, pd.DataFrame) or frame.empty:
        return pd.DataFrame(columns=REQUIRED_CANDLE_COLUMNS)
    if not all(c in frame.columns for c in REQUIRED_CANDLE_COLUMNS):
        return pd.DataFrame(columns=REQUIRED_CANDLE_COLUMNS)
    d = frame.copy()
    d["datetime"] = pd.to_datetime(d["datetime"], utc=True, errors="coerce")
    for c in ("open", "high", "low", "close"):
        d[c] = pd.to_numeric(d[c], errors="coerce")
    d = d.dropna(subset=list(REQUIRED_CANDLE_COLUMNS)).sort_values("datetime")
    finite = d[["open", "high", "low", "close"]].apply(lambda col: col.map(math.isfinite)).all(axis=1)
    geometry = (d["low"] <= d[["open", "close"]].min(axis=1)) & (d["high"] >= d[["open", "close"]].max(axis=1)) & (d["low"] <= d["high"])
    positive = (d[["open", "high", "low", "close"]] > 0).all(axis=1)
    d = d[finite & geometry & positive]
    d = d.drop_duplicates(subset=["datetime"], keep="last").reset_index(drop=True)
    return d


def _validate_plan(signal: Mapping[str, Any]) -> tuple[bool, str, dict[str, Any]]:
    missing = [k for k in REQUIRED_SIGNAL_FIELDS if signal.get(k) in (None, "")]
    if missing:
        return False, "MISSING_FIELDS:" + ",".join(missing), {}

    try:
        ts = pd.Timestamp(signal.get("signal_time"))
        if ts.tzinfo is None:
            ts = ts.tz_localize("UTC")
        else:
            ts = ts.tz_convert("UTC")
    except Exception:
        return False, "INVALID_SIGNAL_TIME", {}

    side = str(signal.get("side", "")).upper().strip()
    entry = _finite(signal.get("entry"))
    stop = _finite(signal.get("stop"))
    target = _finite(signal.get("target"))
    if side not in ("BUY", "SELL") or None in (entry, stop, target):
        return False, "INVALID_LEVELS", {}

    assert entry is not None and stop is not None and target is not None
    if side == "BUY" and not (stop < entry < target):
        return False, "INVALID_BUY_GEOMETRY", {}
    if side == "SELL" and not (target < entry < stop):
        return False, "INVALID_SELL_GEOMETRY", {}

    risk = abs(entry - stop)
    if risk <= 0:
        return False, "ZERO_RISK", {}

    return True, "", {
        "signal_time": ts,
        "side": side,
        "entry": float(entry),
        "stop": float(stop),
        "target": float(target),
        "risk": float(risk),
    }


def _r_for_price(side: str, entry: float, stop: float, price: float) -> float:
    risk = abs(entry - stop)
    if risk <= 0:
        return 0.0
    raw = (price - entry) / risk
    return float(raw if side == "BUY" else -raw)


def _excursions(
    bars: pd.DataFrame,
    side: str,
    entry: float,
    stop: float,
) -> tuple[float, float]:
    if bars.empty:
        return 0.0, 0.0
    risk = abs(entry - stop)
    if risk <= 0:
        return 0.0, 0.0
    if side == "BUY":
        mfe = (float(bars["high"].max()) - entry) / risk
        mae = (float(bars["low"].min()) - entry) / risk
    else:
        mfe = (entry - float(bars["low"].min())) / risk
        mae = (entry - float(bars["high"].max())) / risk
    return float(mfe), float(mae)


def backtest_signal(
    candles: pd.DataFrame,
    signal: Mapping[str, Any],
    *,
    max_wait_bars: int = 8,
    max_hold_bars: int = 96,
    cost_r: float = 0.0,
    slippage_r: float = 0.0,
    start_after_signal_bar: bool = True,
) -> dict[str, Any]:
    """Backtest one explicit plan against OHLC candles.

    Entry triggers when price touches the explicit entry. Once entered, stop/target
    are checked bar by bar. If stop and target are both touched on one OHLC bar,
    the result is LOSS because intrabar ordering is unknowable.
    """
    d = normalize_candles(candles)
    ok, reason, plan = _validate_plan(signal)
    base = {
        "pair": str(signal.get("pair", signal.get("asset", ""))),
        "setup": str(signal.get("setup", "UNSPECIFIED")),
        "session": str(signal.get("session", "")),
        "source": str(signal.get("source", "ATLASQUANT")),
        "notes": str(signal.get("notes", "")),
    }
    if not ok:
        return {
            **base,
            "status": "INVALID_PLAN",
            "outcome": "NO_TRADE",
            "reason": reason,
            "net_r": None,
        }

    cost=_finite(cost_r)
    slippage=_finite(slippage_r)
    if cost is None or slippage is None or cost < 0 or slippage < 0:
        return {
            **base,
            **plan,
            "status":"INVALID_FRICTION",
            "outcome":"NO_TRADE",
            "reason":"COST_AND_SLIPPAGE_MUST_BE_FINITE_NON_NEGATIVE_R",
            "net_r":None,
        }
    total_friction=float(cost+slippage)

    if d.empty:
        return {
            **base,
            **plan,
            "status": "NO_DATA",
            "outcome": "NO_TRADE",
            "reason": "EMPTY_OR_INVALID_CANDLES",
            "net_r": None,
        }

    signal_time = plan["signal_time"]
    if start_after_signal_bar:
        future = d[d["datetime"] > signal_time].copy()
    else:
        future = d[d["datetime"] >= signal_time].copy()

    if future.empty:
        return {
            **base,
            **plan,
            "status": "NO_FUTURE_DATA",
            "outcome": "NO_TRADE",
            "reason": "NO_CANDLES_AFTER_SIGNAL",
            "net_r": None,
        }

    try:
        wait_bars = int(max_wait_bars)
        hold_bars = int(max_hold_bars)
    except Exception:
        wait_bars = hold_bars = 0
    if wait_bars <= 0 or hold_bars <= 0:
        return {
            **base, **plan, "status": "INVALID_WINDOW", "outcome": "NO_TRADE",
            "reason": "MAX_WAIT_AND_HOLD_MUST_BE_POSITIVE", "net_r": None,
        }

    wait = future.head(wait_bars)
    entry = plan["entry"]
    touched = wait[(wait["low"] <= entry) & (wait["high"] >= entry)]
    if touched.empty:
        return {
            **base,
            **plan,
            "status": "NO_ENTRY",
            "outcome": "NO_TRADE",
            "reason": "ENTRY_NOT_TOUCHED",
            "net_r": None,
            "bars_waited": int(len(wait)),
        }

    entry_idx = int(touched.index[0])
    entry_bar = d.loc[entry_idx]
    active = d.loc[entry_idx:].head(hold_bars).copy()
    side = plan["side"]
    stop = plan["stop"]
    target = plan["target"]

    outcome = "OPEN"
    status = "OPEN"
    exit_price = float(active.iloc[-1]["close"])
    exit_time = active.iloc[-1]["datetime"]
    exit_idx = int(active.index[-1])
    bars_held = 0

    for bars_held, (idx, row) in enumerate(active.iterrows(), start=1):
        low = float(row["low"])
        high = float(row["high"])
        if side == "BUY":
            stop_hit = low <= stop
            target_hit = high >= target
        else:
            stop_hit = high >= stop
            target_hit = low <= target

        if stop_hit and target_hit:
            outcome = "LOSS"
            status = "AMBIGUOUS_SAME_BAR_STOP_FIRST"
            exit_price = stop
            exit_time = row["datetime"]
            exit_idx = int(idx)
            break
        if stop_hit:
            outcome = "LOSS"
            status = "STOP"
            exit_price = stop
            exit_time = row["datetime"]
            exit_idx = int(idx)
            break
        if target_hit:
            outcome = "GAIN"
            status = "TARGET"
            exit_price = target
            exit_time = row["datetime"]
            exit_idx = int(idx)
            break
    else:
        raw_r = _r_for_price(side, entry, stop, exit_price)
        if abs(raw_r) < 1e-12:
            outcome = "BREAKEVEN"
        elif raw_r > 0:
            outcome = "GAIN"
        else:
            outcome = "LOSS"
        status = "TIME_EXIT"

    observed = d.loc[entry_idx:exit_idx].copy()
    mfe_r, mae_r = _excursions(observed, side, entry, stop)
    gross_r = _r_for_price(side, entry, stop, float(exit_price))
    net_r = gross_r - total_friction
    if status == "TARGET":
        gross_r = abs(target - entry) / abs(entry - stop)
        net_r = gross_r - total_friction
    elif status in ("STOP", "AMBIGUOUS_SAME_BAR_STOP_FIRST"):
        gross_r = -1.0
        net_r = -1.0 - total_friction

    final_outcome = "BREAKEVEN" if abs(net_r) < 1e-12 else ("GAIN" if net_r > 0 else "LOSS")
    return {
        **base,
        **plan,
        "status": status,
        "outcome": final_outcome,
        "entry_time": pd.Timestamp(entry_bar["datetime"]).isoformat(),
        "exit_time": pd.Timestamp(exit_time).isoformat(),
        "exit_price": float(exit_price),
        "gross_r": round(float(gross_r), 6),
        "cost_r": round(float(cost), 6),
        "slippage_r": round(float(slippage), 6),
        "total_friction_r": round(float(total_friction), 6),
        "net_r": round(float(net_r), 6),
        "mfe_r": round(float(mfe_r), 6),
        "mae_r": round(float(mae_r), 6),
        "bars_waited": int(list(wait.index).index(entry_idx) + 1),
        "bars_held": int(bars_held),
        "same_bar_ambiguous": bool(status == "AMBIGUOUS_SAME_BAR_STOP_FIRST"),
        "reason": "",
    }


def backtest_many(
    candles_by_pair: Mapping[str, pd.DataFrame],
    signals: Iterable[Mapping[str, Any]],
    *,
    single_position_per_pair: bool = False,
    **kwargs: Any,
) -> list[dict[str, Any]]:
    raw_signals=[dict(x) for x in signals]
    if not single_position_per_pair:
        rows = []
        for signal in raw_signals:
            pair = str(signal.get("pair", signal.get("asset", "")))
            frame = candles_by_pair.get(pair, pd.DataFrame())
            rows.append(backtest_signal(frame, signal, **kwargs))
        return rows

    def _signal_key(signal: Mapping[str, Any]) -> tuple[str, pd.Timestamp]:
        pair=str(signal.get("pair",signal.get("asset","")))
        try:
            ts=pd.Timestamp(signal.get("signal_time"))
            if ts.tzinfo is None:
                ts=ts.tz_localize("UTC")
            else:
                ts=ts.tz_convert("UTC")
        except Exception:
            ts=pd.Timestamp.max.tz_localize("UTC")
        return pair,ts

    rows=[]
    busy_until: dict[str,pd.Timestamp] = {}
    for signal in sorted(raw_signals,key=_signal_key):
        pair = str(signal.get("pair", signal.get("asset", "")))
        _,signal_ts=_signal_key(signal)
        last_exit=busy_until.get(pair)
        if last_exit is not None and signal_ts <= last_exit:
            rows.append({
                "pair":pair,
                "setup":str(signal.get("setup","UNSPECIFIED")),
                "session":str(signal.get("session","")),
                "source":str(signal.get("source","ATLASQUANT")),
                "notes":str(signal.get("notes","")),
                "signal_time":signal_ts,
                "side":str(signal.get("side","")).upper(),
                "status":"OVERLAP_BLOCKED",
                "outcome":"NO_TRADE",
                "reason":"SINGLE_POSITION_PER_PAIR",
                "net_r":None,
            })
            continue

        frame = candles_by_pair.get(pair, pd.DataFrame())
        result=backtest_signal(frame, signal, **kwargs)
        rows.append(result)
        if result.get("net_r") is not None and result.get("exit_time"):
            try:
                exit_ts=pd.Timestamp(result["exit_time"])
                if exit_ts.tzinfo is None:
                    exit_ts=exit_ts.tz_localize("UTC")
                else:
                    exit_ts=exit_ts.tz_convert("UTC")
                busy_until[pair]=exit_ts
            except Exception:
                pass
    return rows


def _max_drawdown(rs: list[float]) -> float:
    equity = peak = 0.0
    max_dd = 0.0
    for value in rs:
        equity += value
        peak = max(peak, equity)
        max_dd = max(max_dd, peak - equity)
    return float(max_dd)


def _max_streak(outcomes: list[str], target: str) -> int:
    best = current = 0
    for out in outcomes:
        if out == target:
            current += 1
            best = max(best, current)
        else:
            current = 0
    return best


def summarize_results(records: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    rows = [dict(x) for x in records]
    executed = [x for x in rows if _finite(x.get("net_r")) is not None]
    rs = [float(x["net_r"]) for x in executed]
    outcomes = [str(x.get("outcome", "")).upper() for x in executed]
    gains = sum(1 for x in outcomes if x == "GAIN")
    losses = sum(1 for x in outcomes if x == "LOSS")
    be = sum(1 for x in outcomes if x == "BREAKEVEN")
    gross_profit = sum(x for x in rs if x > 0)
    gross_loss = abs(sum(x for x in rs if x < 0))
    pf = None if gross_loss == 0 else gross_profit / gross_loss
    return {
        "signals": len(rows),
        "trades": len(executed),
        "gains": gains,
        "losses": losses,
        "breakeven": be,
        "no_trade": len(rows) - len(executed),
        "win_rate_pct": None if not executed else round(gains / len(executed) * 100.0, 2),
        "net_r": round(sum(rs), 4),
        "average_r": None if not rs else round(sum(rs) / len(rs), 4),
        "expectancy_r": None if not rs else round(sum(rs) / len(rs), 4),
        "profit_factor": None if pf is None else round(pf, 4),
        "max_drawdown_r": round(_max_drawdown(rs), 4),
        "max_gain_streak": _max_streak(outcomes, "GAIN"),
        "max_loss_streak": _max_streak(outcomes, "LOSS"),
        "ambiguous_same_bar": sum(1 for x in executed if bool(x.get("same_bar_ambiguous", False))),
    }


def summarize_by(
    records: Iterable[Mapping[str, Any]],
    dimension: str,
) -> pd.DataFrame:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for raw in records:
        row = dict(raw)
        groups[str(row.get(dimension, "N/D") or "N/D")].append(row)
    out = []
    for value, rows in groups.items():
        m = summarize_results(rows)
        out.append({dimension: value, **m})
    if not out:
        return pd.DataFrame()
    return pd.DataFrame(out).sort_values(
        ["trades", dimension],
        ascending=[False, True],
    ).reset_index(drop=True)


def ledger_frame(records: Iterable[Mapping[str, Any]]) -> pd.DataFrame:
    rows = [dict(x) for x in records]
    if not rows:
        return pd.DataFrame()
    preferred = [
        "signal_time", "pair", "setup", "session", "side",
        "entry", "stop", "target", "entry_time", "exit_time", "exit_price",
        "status", "outcome", "gross_r", "cost_r", "slippage_r", "total_friction_r", "net_r",
        "mfe_r", "mae_r", "bars_waited", "bars_held",
        "same_bar_ambiguous", "source", "notes", "reason",
    ]
    extra = sorted({k for row in rows for k in row if k not in preferred and k != "risk"})
    cols = [c for c in preferred if any(c in row for row in rows)] + extra
    return pd.DataFrame(rows).reindex(columns=cols)
