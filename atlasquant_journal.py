"""AtlasQuant Flight Recorder + Backtest/Forward-Test journal helpers."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable, Mapping, Any
import csv
import io
import math
import uuid


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def make_decision_record(*, asset: str, side: str, directional_score: float,
                         data_quality: float, engine_version: str,
                         reasons: Iterable[str] = (), contradictions: Iterable[str] = (),
                         model_versions: Mapping[str, str] | None = None,
                         snapshot: Mapping[str, Any] | None = None,
                         timestamp: str | None = None) -> dict[str, Any]:
    return {
        "decision_id": uuid.uuid4().hex,
        "timestamp": timestamp or _now_iso(),
        "asset": str(asset), "side": str(side).upper(),
        "directional_score": float(directional_score), "data_quality": float(data_quality),
        "engine_version": str(engine_version),
        "model_versions": dict(model_versions or {}),
        "reasons": list(reasons), "contradictions": list(contradictions),
        "snapshot": dict(snapshot or {}),
    }


def attach_trade_result(decision: Mapping[str, Any], *, outcome: str, r_multiple: float,
                        entry_price: float | None = None, exit_price: float | None = None,
                        mae_r: float | None = None, mfe_r: float | None = None,
                        spread_cost_r: float = 0.0, slippage_cost_r: float = 0.0,
                        closed_at: str | None = None) -> dict[str, Any]:
    row = dict(decision)
    row.update({
        "outcome": str(outcome).upper(), "r_multiple": float(r_multiple),
        "entry_price": entry_price, "exit_price": exit_price,
        "mae_r": mae_r, "mfe_r": mfe_r,
        "spread_cost_r": float(spread_cost_r), "slippage_cost_r": float(slippage_cost_r),
        "net_r": float(r_multiple) - float(spread_cost_r) - float(slippage_cost_r),
        "closed_at": closed_at or _now_iso(),
    })
    return row


def make_blocked_record(*, asset: str, reasons: Iterable[str], engine_version: str,
                        snapshot: Mapping[str, Any] | None = None,
                        timestamp: str | None = None) -> dict[str, Any]:
    return {
        "decision_id": uuid.uuid4().hex, "timestamp": timestamp or _now_iso(),
        "asset": str(asset), "side": "NO_TRADE", "outcome": "BLOCKED",
        "engine_version": str(engine_version), "block_reasons": list(reasons),
        "snapshot": dict(snapshot or {}),
    }


def _max_drawdown(series: list[float]) -> float:
    equity = peak = 0.0
    max_dd = 0.0
    for r in series:
        equity += r
        peak = max(peak, equity)
        max_dd = max(max_dd, peak - equity)
    return max_dd


def summarize_trades(records: Iterable[Mapping[str, Any]]) -> dict[str, float | int | None]:
    trades = []
    for row in records:
        try:
            r = float(row.get("net_r", row.get("r_multiple")))
        except Exception:
            continue
        if math.isfinite(r):
            trades.append((str(row.get("outcome", "")).upper(), r, row))
    rs = [r for _, r, _ in trades]
    wins = sum(1 for _, r, _ in trades if r > 0)
    losses = sum(1 for _, r, _ in trades if r < 0)
    breakeven = sum(1 for _, r, _ in trades if r == 0)
    gross_profit = sum(r for r in rs if r > 0)
    gross_loss = abs(sum(r for r in rs if r < 0))
    pf = None if gross_loss == 0 else gross_profit / gross_loss
    return {
        "trades": len(trades), "wins": wins, "losses": losses, "breakeven": breakeven,
        "win_rate_pct": None if not trades else round(wins / len(trades) * 100.0, 2),
        "net_r": round(sum(rs), 4),
        "average_r": None if not rs else round(sum(rs) / len(rs), 4),
        "expectancy_r": None if not rs else round(sum(rs) / len(rs), 4),
        "profit_factor": None if pf is None else round(pf, 4),
        "max_drawdown_r": round(_max_drawdown(rs), 4),
    }


def to_csv(records: Iterable[Mapping[str, Any]]) -> str:
    rows = [dict(r) for r in records]
    if not rows:
        return ""
    fields = sorted({k for row in rows for k in row})
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({k: row.get(k) if not isinstance(row.get(k), (dict, list, tuple)) else repr(row.get(k)) for k in fields})
    return buf.getvalue()
