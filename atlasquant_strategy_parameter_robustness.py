"""AtlasQuant predefined parameter robustness diagnostics.

Runs a SMALL, fixed grid of research variants for each setup. The grid is
declared in code and is not optimized against the uploaded history.

There is intentionally no "best parameter" output, no auto-selection and no
connection to the live Gate. The goal is only to show whether observed results
change sharply under nearby, predefined rule variations.
"""
from __future__ import annotations

from collections import OrderedDict
from typing import Any
import json

import pandas as pd

from atlasquant_operational_backtest import backtest_many, summarize_results
from atlasquant_strategy_comparator import STRATEGY_ORDER, STRATEGY_LABELS
from atlasquant_strategy_replay import generate_bos_choch_ob_signals
from atlasquant_fvg_replay import generate_fvg_signals
from atlasquant_ote_replay import generate_ote_signals
from atlasquant_crt_replay import generate_crt_signals
from atlasquant_amd_replay import generate_amd_signals


PREDEFINED_VARIANTS: "OrderedDict[str,list[dict[str,Any]]]"=OrderedDict([
    ("BOS_CHOCH_OB",[
        {"variant":"RR_1_5","params":{"rr_target":1.5}},
        {"variant":"BASE","params":{"rr_target":2.0}},
        {"variant":"RR_2_5","params":{"rr_target":2.5}},
    ]),
    ("FVG",[
        {"variant":"BASE","params":{"min_gap_atr":0.0}},
        {"variant":"MIN_GAP_0_10_ATR","params":{"min_gap_atr":0.10}},
        {"variant":"MIN_GAP_0_20_ATR","params":{"min_gap_atr":0.20}},
    ]),
    ("OTE",[
        {"variant":"BASE","params":{"entry_mode":"SWEET_705","min_impulse_atr":0.0}},
        {"variant":"ZONE_MIDPOINT","params":{"entry_mode":"ZONE_MIDPOINT","min_impulse_atr":0.0}},
        {"variant":"MIN_IMPULSE_0_50_ATR","params":{"entry_mode":"SWEET_705","min_impulse_atr":0.50}},
    ]),
    ("CRT",[
        {"variant":"BASE","params":{"min_rr":0.0}},
        {"variant":"MIN_RR_0_50","params":{"min_rr":0.50}},
        {"variant":"MIN_RR_1_00","params":{"min_rr":1.00}},
    ]),
    ("AMD_PO3",[
        {"variant":"ACC_6","params":{"accumulation_bars":6}},
        {"variant":"BASE","params":{"accumulation_bars":8}},
        {"variant":"ACC_10","params":{"accumulation_bars":10}},
    ]),
])


def predefined_parameter_grid() -> "OrderedDict[str,list[dict[str,Any]]]":
    """Return a defensive copy of the fixed, non-optimized grid."""
    out=OrderedDict()
    for strategy,variants in PREDEFINED_VARIANTS.items():
        out[strategy]=[
            {"variant":str(x["variant"]),"params":dict(x.get("params",{}))}
            for x in variants
        ]
    return out


def _generate(
    strategy: str,
    candles: pd.DataFrame,
    pair: str,
    params: dict[str,Any],
) -> list[dict[str,Any]]:
    if strategy=="BOS_CHOCH_OB":
        return generate_bos_choch_ob_signals(candles,pair=pair,**params)
    if strategy=="FVG":
        return generate_fvg_signals(candles,pair=pair,**params)
    if strategy=="OTE":
        return generate_ote_signals(candles,pair=pair,**params)
    if strategy=="CRT":
        return generate_crt_signals(candles,pair=pair,**params)
    if strategy=="AMD_PO3":
        return generate_amd_signals(candles,pair=pair,**params)
    raise ValueError(f"unknown strategy: {strategy}")


def parameter_robustness_frame(
    candles: pd.DataFrame,
    *,
    pair: str,
    max_wait_bars: int = 8,
    max_hold_bars: int = 96,
    cost_r: float = 0.0,
    slippage_r: float = 0.0,
) -> pd.DataFrame:
    """Run all fixed variants independently and return descriptive metrics."""
    rows=[]
    grid=predefined_parameter_grid()
    for strategy in STRATEGY_ORDER:
        for spec in grid[strategy]:
            variant=spec["variant"]
            params=dict(spec["params"])
            signals=_generate(strategy,candles,pair,params)
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
            m=summarize_results(results)
            rows.append({
                "strategy":strategy,
                "operacional":STRATEGY_LABELS[strategy],
                "variant":variant,
                "is_base":bool(variant=="BASE"),
                "params_json":json.dumps(params,sort_keys=True,separators=(",",":")),
                "signals":m["signals"],
                "trades":m["trades"],
                "gains":m["gains"],
                "losses":m["losses"],
                "breakeven":m["breakeven"],
                "win_rate_pct":m["win_rate_pct"],
                "expectancy_r":m["expectancy_r"],
                "net_r":m["net_r"],
                "profit_factor":m["profit_factor"],
                "max_drawdown_r":m["max_drawdown_r"],
                "max_loss_streak":m["max_loss_streak"],
            })
    return pd.DataFrame(rows)


def parameter_robustness_summary(
    detail: pd.DataFrame,
    *,
    min_trades_per_variant: int = 20,
) -> pd.DataFrame:
    """Summarize variation ranges without ranking or selecting a winner."""
    minimum=max(1,int(min_trades_per_variant))
    rows=[]
    for strategy in STRATEGY_ORDER:
        if not isinstance(detail,pd.DataFrame) or detail.empty:
            group=pd.DataFrame()
        else:
            group=detail[detail["strategy"]==strategy].copy()

        if group.empty:
            rows.append({
                "strategy":strategy,
                "operacional":STRATEGY_LABELS[strategy],
                "variants_tested":0,
                "all_variants_sufficient":False,
                "positive_variants":0,
                "positive_variant_pct":None,
                "base_expectancy_r":None,
                "worst_expectancy_r":None,
                "best_expectancy_r":None,
                "expectancy_spread_r":None,
                "min_variant_trades":0,
                "max_variant_trades":0,
                "parameter_robustness_status":"INSUFFICIENT",
            })
            continue

        trades=pd.to_numeric(group["trades"],errors="coerce").fillna(0)
        exps=pd.to_numeric(group["expectancy_r"],errors="coerce")
        sufficient=bool((trades>=minimum).all() and exps.notna().all())
        exp_values=[float(x) for x in exps.dropna().tolist()]
        positive=sum(1 for x in exp_values if x>1e-12)
        negative=sum(1 for x in exp_values if x<-1e-12)
        base_rows=group[group["is_base"]==True]
        base_exp=None
        if not base_rows.empty:
            try:
                base_exp=float(base_rows.iloc[0]["expectancy_r"])
            except Exception:
                base_exp=None

        if not sufficient:
            status="INSUFFICIENT"
        elif positive==len(group):
            status="POSITIVE_ALL_PREDEFINED_VARIANTS"
        elif negative==len(group):
            status="NEGATIVE_ALL_PREDEFINED_VARIANTS"
        else:
            status="MIXED_PREDEFINED_VARIANTS"

        worst=min(exp_values) if exp_values else None
        best=max(exp_values) if exp_values else None
        spread=(best-worst) if worst is not None and best is not None else None
        rows.append({
            "strategy":strategy,
            "operacional":group.iloc[0].get("operacional",STRATEGY_LABELS[strategy]),
            "variants_tested":int(len(group)),
            "all_variants_sufficient":sufficient,
            "positive_variants":positive,
            "positive_variant_pct":round(positive/len(group)*100.0,2) if len(group) else None,
            "base_expectancy_r":None if base_exp is None else round(base_exp,4),
            "worst_expectancy_r":None if worst is None else round(worst,4),
            "best_expectancy_r":None if best is None else round(best,4),
            "expectancy_spread_r":None if spread is None else round(spread,4),
            "min_variant_trades":int(trades.min()) if len(trades) else 0,
            "max_variant_trades":int(trades.max()) if len(trades) else 0,
            "parameter_robustness_status":status,
        })
    return pd.DataFrame(rows)


def parameter_robustness_report(
    candles: pd.DataFrame,
    *,
    pair: str,
    max_wait_bars: int = 8,
    max_hold_bars: int = 96,
    cost_r: float = 0.0,
    slippage_r: float = 0.0,
    min_trades_per_variant: int = 20,
) -> dict[str,pd.DataFrame]:
    detail=parameter_robustness_frame(
        candles,
        pair=pair,
        max_wait_bars=max_wait_bars,
        max_hold_bars=max_hold_bars,
        cost_r=cost_r,
        slippage_r=slippage_r,
    )
    summary=parameter_robustness_summary(
        detail,
        min_trades_per_variant=min_trades_per_variant,
    )
    return {"summary":summary,"variants":detail}
