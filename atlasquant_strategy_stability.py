"""AtlasQuant temporal stability diagnostics for strategy backtests.

Splits each strategy's executed trades into deterministic chronological folds
and reports whether observed expectancy keeps the same sign across the sample.

Research-only: no weights, live gates, probabilities or execution permissions
are changed by this module.
"""
from __future__ import annotations

from typing import Any, Mapping
import math

import pandas as pd

from atlasquant_operational_backtest import summarize_results
from atlasquant_strategy_comparator import STRATEGY_ORDER, STRATEGY_LABELS


_TIME_FIELDS=("signal_time","entry_time","exit_time")


def _finite(value: Any) -> float | None:
    try:
        out=float(value)
        return out if math.isfinite(out) else None
    except Exception:
        return None


def _timestamp(row: Mapping[str, Any]) -> pd.Timestamp | None:
    for field in _TIME_FIELDS:
        raw=row.get(field)
        if raw in (None,""):
            continue
        ts=pd.to_datetime(raw,utc=True,errors="coerce")
        if not pd.isna(ts):
            return pd.Timestamp(ts)
    return None


def _chronological_executed(records: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows=[]
    for order,raw in enumerate(records):
        row=dict(raw)
        if _finite(row.get("net_r")) is None:
            continue
        ts=_timestamp(row)
        if ts is None:
            continue
        row["_stability_time"]=ts
        row["_original_order"]=order
        rows.append(row)
    rows.sort(key=lambda x:(x["_stability_time"],x["_original_order"]))
    return rows


def temporal_fold_frame(
    suite: Mapping[str, Mapping[str, Any]],
    *,
    folds: int = 3,
) -> pd.DataFrame:
    """Build near-equal chronological trade-count folds per strategy."""
    k=max(2,int(folds))
    rows=[]
    for strategy in STRATEGY_ORDER:
        pack=dict(suite.get(strategy,{}) or {})
        executed=_chronological_executed(list(pack.get("results",[]) or []))
        n=len(executed)
        if n < k:
            continue

        base=n//k
        rem=n%k
        start=0
        for idx in range(k):
            size=base+(1 if idx<rem else 0)
            group=executed[start:start+size]
            start+=size
            if not group:
                continue
            metrics=summarize_results(group)
            times=[x["_stability_time"] for x in group]
            rows.append({
                "strategy":strategy,
                "operacional":pack.get("label",STRATEGY_LABELS[strategy]),
                "fold":f"F{idx+1}",
                "fold_index":idx+1,
                "start_time":min(times),
                "end_time":max(times),
                "trades":metrics["trades"],
                "gains":metrics["gains"],
                "losses":metrics["losses"],
                "breakeven":metrics["breakeven"],
                "win_rate_pct":metrics["win_rate_pct"],
                "expectancy_r":metrics["expectancy_r"],
                "net_r":metrics["net_r"],
                "max_drawdown_r":metrics["max_drawdown_r"],
                "max_loss_streak":metrics["max_loss_streak"],
            })
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values(
        ["strategy","fold_index"],
        ascending=[True,True],
    ).reset_index(drop=True)


def temporal_stability_summary(
    folds_df: pd.DataFrame,
    *,
    folds: int = 3,
    min_trades_per_fold: int = 5,
) -> pd.DataFrame:
    """Summarize cross-fold consistency without forecasting future performance."""
    k=max(2,int(folds))
    minimum=max(1,int(min_trades_per_fold))
    rows=[]
    for strategy in STRATEGY_ORDER:
        if not isinstance(folds_df,pd.DataFrame) or folds_df.empty:
            group=pd.DataFrame()
        else:
            group=folds_df[folds_df["strategy"]==strategy].sort_values("fold_index")

        if group.empty or len(group)<k:
            rows.append({
                "strategy":strategy,
                "operacional":STRATEGY_LABELS[strategy],
                "folds_available":int(len(group)),
                "all_folds_sufficient":False,
                "positive_folds":0,
                "negative_folds":0,
                "flat_folds":0,
                "positive_fold_pct":None,
                "worst_expectancy_r":None,
                "best_expectancy_r":None,
                "expectancy_spread_r":None,
                "expectancy_std_r":None,
                "total_net_r":0.0,
                "stability_status":"INSUFFICIENT",
            })
            continue

        trades=pd.to_numeric(group["trades"],errors="coerce").fillna(0)
        exps=pd.to_numeric(group["expectancy_r"],errors="coerce")
        nets=pd.to_numeric(group["net_r"],errors="coerce").fillna(0.0)
        sufficient=bool((trades>=minimum).all() and exps.notna().all())

        exp_values=[float(x) for x in exps.dropna().tolist()]
        positive=sum(1 for x in exp_values if x>1e-12)
        negative=sum(1 for x in exp_values if x<-1e-12)
        flat=len(exp_values)-positive-negative

        if not sufficient:
            status="INSUFFICIENT"
        elif positive==k:
            status="POSITIVE_ACROSS_FOLDS"
        elif negative==k:
            status="NEGATIVE_ACROSS_FOLDS"
        else:
            status="MIXED_ACROSS_FOLDS"

        worst=min(exp_values) if exp_values else None
        best=max(exp_values) if exp_values else None
        spread=(best-worst) if worst is not None and best is not None else None
        std=float(pd.Series(exp_values,dtype=float).std(ddof=0)) if exp_values else None

        rows.append({
            "strategy":strategy,
            "operacional":STRATEGY_LABELS[strategy],
            "folds_available":int(len(group)),
            "all_folds_sufficient":sufficient,
            "positive_folds":positive,
            "negative_folds":negative,
            "flat_folds":flat,
            "positive_fold_pct":round(positive/k*100.0,2),
            "worst_expectancy_r":None if worst is None else round(worst,4),
            "best_expectancy_r":None if best is None else round(best,4),
            "expectancy_spread_r":None if spread is None else round(spread,4),
            "expectancy_std_r":None if std is None else round(std,4),
            "total_net_r":round(float(nets.sum()),4),
            "stability_status":status,
        })
    return pd.DataFrame(rows)


def temporal_stability_report(
    suite: Mapping[str, Mapping[str, Any]],
    *,
    folds: int = 3,
    min_trades_per_fold: int = 5,
) -> dict[str, pd.DataFrame]:
    fold_df=temporal_fold_frame(suite,folds=folds)
    summary=temporal_stability_summary(
        fold_df,
        folds=folds,
        min_trades_per_fold=min_trades_per_fold,
    )
    return {"summary":summary,"folds":fold_df}
