"""AtlasQuant multi-strategy research comparator.

Runs the five objective research replays independently on the same OHLC sample
and compares observed backtest metrics without merging their signals.

This module is offline, research-only and does not alter the live Gate.
"""
from __future__ import annotations

from collections import OrderedDict
from typing import Any, Mapping
import math

import pandas as pd

from atlasquant_operational_backtest import (
    backtest_many,
    ledger_frame,
    summarize_results,
)
from atlasquant_strategy_replay import generate_bos_choch_ob_signals
from atlasquant_fvg_replay import generate_fvg_signals
from atlasquant_ote_replay import generate_ote_signals
from atlasquant_crt_replay import generate_crt_signals
from atlasquant_amd_replay import generate_amd_signals


STRATEGY_ORDER = (
    "BOS_CHOCH_OB",
    "FVG",
    "OTE",
    "CRT",
    "AMD_PO3",
)

STRATEGY_LABELS = {
    "BOS_CHOCH_OB": "BOS/CHOCH + Order Block",
    "FVG": "FVG",
    "OTE": "OTE 62–79%",
    "CRT": "CRT",
    "AMD_PO3": "AMD / Power of Three",
}


def _sample_tier(trades: int) -> str:
    n=int(trades)
    if n < 20:
        return "AMOSTRA PEQUENA"
    if n < 50:
        return "AMOSTRA INICIAL"
    if n < 100:
        return "AMOSTRA INTERMEDIÁRIA"
    return "AMOSTRA MAIOR"


def generate_strategy_signals(
    candles: pd.DataFrame,
    pair: str,
) -> "OrderedDict[str, list[dict[str, Any]]]":
    """Generate each setup independently using its research defaults."""
    return OrderedDict(
        [
            ("BOS_CHOCH_OB", generate_bos_choch_ob_signals(candles, pair=pair)),
            ("FVG", generate_fvg_signals(candles, pair=pair)),
            ("OTE", generate_ote_signals(candles, pair=pair)),
            ("CRT", generate_crt_signals(candles, pair=pair)),
            ("AMD_PO3", generate_amd_signals(candles, pair=pair)),
        ]
    )


def run_strategy_suite(
    candles: pd.DataFrame,
    *,
    pair: str,
    max_wait_bars: int = 8,
    max_hold_bars: int = 96,
    cost_r: float = 0.0,
    slippage_r: float = 0.0,
) -> "OrderedDict[str, dict[str, Any]]":
    """Generate + backtest all five strategies without mixing their trades."""
    signals_by_strategy=generate_strategy_signals(candles,pair)
    suite: "OrderedDict[str, dict[str, Any]]"=OrderedDict()
    for strategy in STRATEGY_ORDER:
        signals=signals_by_strategy.get(strategy,[])
        results=backtest_many(
            {pair:candles},
            signals,
            single_position_per_pair=True,
            max_wait_bars=int(max_wait_bars),
            max_hold_bars=int(max_hold_bars),
            cost_r=float(cost_r),
            slippage_r=float(slippage_r),
            start_after_signal_bar=True,
        )
        suite[strategy]={
            "strategy":strategy,
            "label":STRATEGY_LABELS[strategy],
            "signals":signals,
            "results":results,
        }
    return suite


def comparison_frame(
    suite: Mapping[str, Mapping[str, Any]],
    *,
    min_trades_for_rank: int = 20,
) -> pd.DataFrame:
    """Return one descriptive row per strategy.

    Observed rank is only assigned when a strategy has at least
    min_trades_for_rank executed trades. It is a sample description, not a
    forecast or permission to use the setup live.
    """
    threshold=max(1,int(min_trades_for_rank))
    rows=[]
    for strategy in STRATEGY_ORDER:
        pack=dict(suite.get(strategy,{}) or {})
        results=list(pack.get("results",[]) or [])
        m=summarize_results(results)
        try: dd=float(m.get("max_drawdown_r",0.0) or 0.0)
        except Exception: dd=float("nan")
        try: net=float(m.get("net_r",0.0) or 0.0)
        except Exception: net=float("nan")
        metrics_finite=all(
            math.isfinite(float(v))
            for v in (m.get("expectancy_r"),m.get("net_r"),m.get("max_drawdown_r"))
            if v is not None
        ) and all(m.get(k) is not None for k in ("expectancy_r","net_r","max_drawdown_r"))
        rows.append({
            "strategy":strategy,
            "operacional":pack.get("label",STRATEGY_LABELS[strategy]),
            "signals":m["signals"],
            "trades":m["trades"],
            "gains":m["gains"],
            "losses":m["losses"],
            "breakeven":m["breakeven"],
            "no_trade":m["no_trade"],
            "win_rate_pct":m["win_rate_pct"],
            "expectancy_r":m["expectancy_r"],
            "net_r":m["net_r"],
            "profit_factor":m["profit_factor"],
            "max_drawdown_r":m["max_drawdown_r"],
            "max_loss_streak":m["max_loss_streak"],
            "ambiguous_same_bar":m["ambiguous_same_bar"],
            "net_r_per_drawdown":None if not (math.isfinite(dd) and math.isfinite(net)) or dd<=0 else round(net/dd,4),
            "sample_tier":_sample_tier(m["trades"]),
            "eligible_observed_rank":bool(m["trades"]>=threshold and metrics_finite),
            "observed_expectancy_rank":None,
        })

    eligible=[r for r in rows if r["eligible_observed_rank"]]
    eligible.sort(
        key=lambda r:(
            -(float(r["expectancy_r"]) if r["expectancy_r"] is not None else float("-inf")),
            -float(r["net_r"]),
            float(r["max_drawdown_r"]),
            str(r["strategy"]),
        )
    )
    for rank,row in enumerate(eligible,start=1):
        for target in rows:
            if target["strategy"]==row["strategy"]:
                target["observed_expectancy_rank"]=rank
                break

    return pd.DataFrame(rows)


def breakdown_frame(
    suite: Mapping[str, Mapping[str, Any]],
    dimension: str,
) -> pd.DataFrame:
    """Describe each strategy separately by pair/session/side/etc."""
    rows=[]
    for strategy in STRATEGY_ORDER:
        pack=dict(suite.get(strategy,{}) or {})
        grouped: dict[str,list[dict[str,Any]]]={}
        for raw in list(pack.get("results",[]) or []):
            row=dict(raw)
            value=str(row.get(dimension,"N/D") or "N/D")
            grouped.setdefault(value,[]).append(row)
        for value,records in grouped.items():
            m=summarize_results(records)
            rows.append({
                "strategy":strategy,
                "operacional":pack.get("label",STRATEGY_LABELS[strategy]),
                dimension:value,
                "trades":m["trades"],
                "gains":m["gains"],
                "losses":m["losses"],
                "win_rate_pct":m["win_rate_pct"],
                "expectancy_r":m["expectancy_r"],
                "net_r":m["net_r"],
                "max_drawdown_r":m["max_drawdown_r"],
            })
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values(
        ["strategy","trades",dimension],
        ascending=[True,False,True],
    ).reset_index(drop=True)


def combined_ledger(suite: Mapping[str, Mapping[str, Any]]) -> pd.DataFrame:
    """Concatenate ledgers while preserving strategy identity on every row."""
    parts=[]
    for strategy in STRATEGY_ORDER:
        pack=dict(suite.get(strategy,{}) or {})
        frame=ledger_frame(list(pack.get("results",[]) or []))
        if frame.empty:
            continue
        frame=frame.copy()
        frame.insert(0,"strategy_family",strategy)
        frame.insert(1,"operacional",pack.get("label",STRATEGY_LABELS[strategy]))
        parts.append(frame)
    if not parts:
        return pd.DataFrame()
    return pd.concat(parts,ignore_index=True,sort=False)
