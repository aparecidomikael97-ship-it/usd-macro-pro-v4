"""AtlasQuant V11.6 — custos conservadores para Paper Trading.

Camada puramente analítica. Não envia ordens, não conecta corretora e não
altera sinais, Gate, pesos ou seleção de estratégia. Mantém realized_r como
resultado bruto legado e acrescenta custo/slippage/net R de forma auditável.
"""
from __future__ import annotations

import math
from typing import Any

import pandas as pd

FRICTION_VERSION = "V11.6_PAPER_FRICTION"
DEFAULT_SPREAD_R = 0.04
DEFAULT_SLIPPAGE_R = 0.02
DEFAULT_TOTAL_R = DEFAULT_SPREAD_R + DEFAULT_SLIPPAGE_R

FRICTION_COLUMNS = [
    "gross_r", "spread_cost_r", "slippage_cost_r", "total_friction_r",
    "net_r", "friction_version",
]


def _finite(value: Any) -> float | None:
    try:
        out = float(value)
        return out if math.isfinite(out) else None
    except Exception:
        return None


def apply_paper_friction(trades: pd.DataFrame | None) -> pd.DataFrame:
    """Enriquece o diário sem reclassificar WIN/LOSS e sem sobrescrever realized_r."""
    if trades is None:
        d = pd.DataFrame()
    else:
        d = trades.copy()
    for col in FRICTION_COLUMNS:
        if col not in d.columns:
            d[col] = None
    if d.empty:
        return d

    for idx, row in d.iterrows():
        if str(row.get("status", "")).upper() != "CLOSED":
            continue
        gross = _finite(row.get("realized_r"))
        if gross is None:
            continue
        d.at[idx, "gross_r"] = round(gross, 4)
        d.at[idx, "spread_cost_r"] = DEFAULT_SPREAD_R
        d.at[idx, "slippage_cost_r"] = DEFAULT_SLIPPAGE_R
        d.at[idx, "total_friction_r"] = DEFAULT_TOTAL_R
        d.at[idx, "net_r"] = round(gross - DEFAULT_TOTAL_R, 4)
        d.at[idx, "friction_version"] = FRICTION_VERSION
    return d


def summarize_net(trades: pd.DataFrame | None) -> dict[str, Any]:
    d = apply_paper_friction(trades)
    if d.empty:
        net = pd.Series(dtype=float)
        gross = pd.Series(dtype=float)
    else:
        closed = d[d.get("status", pd.Series(index=d.index, dtype=str)).astype(str).str.upper().eq("CLOSED")]
        gross = pd.to_numeric(closed.get("gross_r"), errors="coerce").dropna()
        net = pd.to_numeric(closed.get("net_r"), errors="coerce").dropna()
    gp = float(net[net > 0].sum()) if not net.empty else 0.0
    gl = float(-net[net < 0].sum()) if not net.empty else 0.0
    return {
        "version": FRICTION_VERSION,
        "closed_costed": int(len(net)),
        "gross_r": round(float(gross.sum()), 4) if not gross.empty else 0.0,
        "friction_r": round(float((gross - net).sum()), 4) if len(gross) and len(net) else 0.0,
        "net_r": round(float(net.sum()), 4) if not net.empty else 0.0,
        "avg_net_r": round(float(net.mean()), 4) if not net.empty else 0.0,
        "profit_factor_net_r": None if gl <= 0 else round(gp / gl, 4),
        "assumptions": {
            "spread_cost_r_per_closed_trade": DEFAULT_SPREAD_R,
            "slippage_cost_r_per_closed_trade": DEFAULT_SLIPPAGE_R,
            "total_friction_r_per_closed_trade": DEFAULT_TOTAL_R,
            "model": "fixed conservative research friction; not broker-specific",
        },
        "safety": {
            "real_orders": False,
            "broker_connection": False,
            "changes_signal": False,
            "changes_gate": False,
            "auto_strategy_selection": False,
        },
    }
