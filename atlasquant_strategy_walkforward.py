"""AtlasQuant walk-forward diagnostics for strategy backtests.

Uses expanding chronological train windows followed by untouched test windows.
No parameter search, optimization, weighting change or live Gate action occurs.

This is an out-of-sample historical diagnostic, not a forecast.
"""
from __future__ import annotations

from typing import Any, Mapping
import math

import pandas as pd

from atlasquant_operational_backtest import summarize_results
from atlasquant_strategy_comparator import STRATEGY_ORDER, STRATEGY_LABELS
from atlasquant_strategy_stability import _chronological_executed


def _finite(value: Any) -> float | None:
    try:
        out=float(value)
        return out if math.isfinite(out) else None
    except Exception:
        return None


def _partition_sizes(total: int, parts: int) -> list[int]:
    n=max(0,int(total))
    k=max(1,int(parts))
    if n<=0:
        return []
    base=n//k
    rem=n%k
    return [base+(1 if i<rem else 0) for i in range(k)]


def walk_forward_frame(
    suite: Mapping[str, Mapping[str, Any]],
    *,
    initial_train_pct: int = 60,
    test_windows: int = 3,
) -> pd.DataFrame:
    """Build expanding-train / forward-test windows for every strategy.

    Example with 60% train and 3 test windows:
      W1 train = oldest 60%, test = next block
      W2 train = all data through W1, test = next block
      W3 train = all data through W2, test = final block
    """
    pct=int(initial_train_pct)
    windows=max(1,int(test_windows))
    if pct<40 or pct>90:
        raise ValueError("initial_train_pct must be between 40 and 90")

    rows=[]
    for strategy in STRATEGY_ORDER:
        pack=dict(suite.get(strategy,{}) or {})
        executed=_chronological_executed(list(pack.get("results",[]) or []))
        n=len(executed)
        if n<2:
            continue

        initial=max(1,int(math.floor(n*pct/100.0)))
        if initial>=n:
            continue

        remaining=n-initial
        sizes=[x for x in _partition_sizes(remaining,windows) if x>0]
        cursor=initial

        for idx,size in enumerate(sizes,start=1):
            train=executed[:cursor]
            test=executed[cursor:cursor+size]
            cursor+=size
            if not train or not test:
                continue

            tm=summarize_results(train)
            om=summarize_results(test)
            train_exp=_finite(tm.get("expectancy_r"))
            test_exp=_finite(om.get("expectancy_r"))
            degradation=None
            if train_exp is not None and test_exp is not None:
                degradation=round(test_exp-train_exp,4)

            train_times=[x["_stability_time"] for x in train]
            test_times=[x["_stability_time"] for x in test]
            rows.append({
                "strategy":strategy,
                "operacional":pack.get("label",STRATEGY_LABELS[strategy]),
                "window":f"W{idx}",
                "window_index":idx,
                "train_start":min(train_times),
                "train_end":max(train_times),
                "test_start":min(test_times),
                "test_end":max(test_times),
                "train_trades":tm["trades"],
                "test_trades":om["trades"],
                "train_expectancy_r":tm["expectancy_r"],
                "test_expectancy_r":om["expectancy_r"],
                "expectancy_delta_r":degradation,
                "train_net_r":tm["net_r"],
                "test_net_r":om["net_r"],
                "train_win_rate_pct":tm["win_rate_pct"],
                "test_win_rate_pct":om["win_rate_pct"],
                "test_max_drawdown_r":om["max_drawdown_r"],
                "test_max_loss_streak":om["max_loss_streak"],
                "test_positive":None if test_exp is None else bool(test_exp>0),
            })

    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values(
        ["strategy","window_index"],
        ascending=[True,True],
    ).reset_index(drop=True)


def walk_forward_summary(
    windows_df: pd.DataFrame,
    *,
    expected_windows: int = 3,
    min_train_trades: int = 20,
    min_test_trades: int = 5,
) -> pd.DataFrame:
    """Summarize OOS windows descriptively and fail closed on small samples."""
    k=max(1,int(expected_windows))
    min_train=max(1,int(min_train_trades))
    min_test=max(1,int(min_test_trades))
    rows=[]

    for strategy in STRATEGY_ORDER:
        if not isinstance(windows_df,pd.DataFrame) or windows_df.empty:
            group=pd.DataFrame()
        else:
            group=windows_df[windows_df["strategy"]==strategy].sort_values("window_index")

        if group.empty:
            rows.append({
                "strategy":strategy,
                "operacional":STRATEGY_LABELS[strategy],
                "windows_available":0,
                "all_windows_sufficient":False,
                "positive_test_windows":0,
                "negative_test_windows":0,
                "positive_test_pct":None,
                "avg_train_expectancy_r":None,
                "avg_test_expectancy_r":None,
                "avg_expectancy_delta_r":None,
                "worst_test_expectancy_r":None,
                "best_test_expectancy_r":None,
                "total_test_net_r":0.0,
                "walk_forward_status":"INSUFFICIENT",
            })
            continue

        train_n=pd.to_numeric(group["train_trades"],errors="coerce").fillna(0)
        test_n=pd.to_numeric(group["test_trades"],errors="coerce").fillna(0)
        train_exp=pd.to_numeric(group["train_expectancy_r"],errors="coerce")
        test_exp=pd.to_numeric(group["test_expectancy_r"],errors="coerce")
        deltas=pd.to_numeric(group["expectancy_delta_r"],errors="coerce")
        test_net=pd.to_numeric(group["test_net_r"],errors="coerce").fillna(0.0)

        finite_train=train_exp.map(lambda x: bool(pd.notna(x) and math.isfinite(float(x))))
        finite_test=test_exp.map(lambda x: bool(pd.notna(x) and math.isfinite(float(x))))
        finite_delta=deltas.map(lambda x: bool(pd.notna(x) and math.isfinite(float(x))))
        finite_net=test_net.map(lambda x: bool(pd.notna(x) and math.isfinite(float(x))))
        sufficient=bool(
            len(group)>=k
            and (train_n>=min_train).all()
            and (test_n>=min_test).all()
            and finite_train.all()
            and finite_test.all()
            and finite_delta.all()
            and finite_net.all()
        )

        tests=[float(x) for x in test_exp[finite_test].tolist()]
        positive=sum(1 for x in tests if x>1e-12)
        negative=sum(1 for x in tests if x<-1e-12)

        if not sufficient:
            status="INSUFFICIENT"
        elif positive==len(group):
            status="POSITIVE_ALL_OOS_WINDOWS"
        elif negative==len(group):
            status="NEGATIVE_ALL_OOS_WINDOWS"
        else:
            status="MIXED_OOS_WINDOWS"

        rows.append({
            "strategy":strategy,
            "operacional":STRATEGY_LABELS[strategy],
            "windows_available":int(len(group)),
            "all_windows_sufficient":sufficient,
            "positive_test_windows":positive,
            "negative_test_windows":negative,
            "positive_test_pct":round(positive/len(group)*100.0,2) if len(group) else None,
            "avg_train_expectancy_r":round(float(train_exp[finite_train].mean()),4) if finite_train.any() else None,
            "avg_test_expectancy_r":round(float(test_exp[finite_test].mean()),4) if finite_test.any() else None,
            "avg_expectancy_delta_r":round(float(deltas[finite_delta].mean()),4) if finite_delta.any() else None,
            "worst_test_expectancy_r":round(min(tests),4) if tests else None,
            "best_test_expectancy_r":round(max(tests),4) if tests else None,
            "total_test_net_r":round(float(test_net.sum()),4) if finite_net.all() else 0.0,
            "walk_forward_status":status,
        })

    return pd.DataFrame(rows)


def walk_forward_report(
    suite: Mapping[str, Mapping[str, Any]],
    *,
    initial_train_pct: int = 60,
    test_windows: int = 3,
    min_train_trades: int = 20,
    min_test_trades: int = 5,
) -> dict[str, pd.DataFrame]:
    windows=walk_forward_frame(
        suite,
        initial_train_pct=initial_train_pct,
        test_windows=test_windows,
    )
    summary=walk_forward_summary(
        windows,
        expected_windows=test_windows,
        min_train_trades=min_train_trades,
        min_test_trades=min_test_trades,
    )
    return {"summary":summary,"windows":windows}
