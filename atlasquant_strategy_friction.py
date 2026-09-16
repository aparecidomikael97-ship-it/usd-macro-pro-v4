"""AtlasQuant cost/slippage sensitivity diagnostics.

Reprices the SAME historical executions under multiple friction assumptions.
No signal is regenerated and no entry/exit path is changed between scenarios.

Slippage is modeled conservatively as an additional adverse drag in R per
executed trade. It is not a tick-by-tick fill simulator.

Research-only: does not alter the live Gate, weights or strategy parameters.
"""
from __future__ import annotations

from typing import Any, Iterable, Mapping
import math

import pandas as pd

from atlasquant_operational_backtest import summarize_results
from atlasquant_strategy_comparator import STRATEGY_ORDER, STRATEGY_LABELS


def _finite(value: Any) -> float | None:
    try:
        out=float(value)
        return out if math.isfinite(out) else None
    except Exception:
        return None


def build_friction_scenarios(
    *,
    base_cost_r: float = 0.0,
    slippage_levels_r: Iterable[float] = (0.0,0.02,0.05,0.10),
    include_zero_baseline: bool = True,
) -> list[dict[str, Any]]:
    cost=_finite(base_cost_r)
    if cost is None or cost<0:
        raise ValueError("base_cost_r must be finite and >= 0")

    slips=[]
    for raw in slippage_levels_r:
        value=_finite(raw)
        if value is None or value<0:
            raise ValueError("slippage levels must be finite and >= 0")
        slips.append(float(value))

    pairs=[]
    if include_zero_baseline:
        pairs.append((0.0,0.0,"ZERO_FRICTION"))
    for slip in slips:
        pairs.append((float(cost),float(slip),None))

    seen=set()
    out=[]
    for cost_r,slip_r,label in pairs:
        key=(round(cost_r,10),round(slip_r,10))
        if key in seen:
            continue
        seen.add(key)
        total=cost_r+slip_r
        scenario=label or f"C{cost_r:.3f}_S{slip_r:.3f}"
        out.append({
            "scenario":scenario,
            "cost_r":round(cost_r,6),
            "slippage_r":round(slip_r,6),
            "total_friction_r":round(total,6),
        })
    out.sort(key=lambda x:(x["total_friction_r"],x["cost_r"],x["slippage_r"],x["scenario"]))
    return out


def _reprice_results(
    records: Iterable[Mapping[str, Any]],
    *,
    cost_r: float,
    slippage_r: float,
) -> list[dict[str, Any]]:
    total=float(cost_r)+float(slippage_r)
    rows=[]
    for raw in records:
        row=dict(raw)
        gross=_finite(row.get("gross_r"))
        if gross is None:
            net=_finite(row.get("net_r"))
            if net is not None:
                old_cost=_finite(row.get("cost_r")) or 0.0
                old_slip=_finite(row.get("slippage_r")) or 0.0
                gross=float(net+old_cost+old_slip)

        row["cost_r"]=round(float(cost_r),6)
        row["slippage_r"]=round(float(slippage_r),6)
        row["total_friction_r"]=round(total,6)

        if gross is None:
            row["net_r"]=None
            rows.append(row)
            continue

        net_r=float(gross)-total
        row["gross_r"]=round(float(gross),6)
        row["net_r"]=round(net_r,6)
        row["outcome"]="BREAKEVEN" if abs(net_r)<1e-12 else ("GAIN" if net_r>0 else "LOSS")
        rows.append(row)
    return rows


def friction_sensitivity_frame(
    suite: Mapping[str, Mapping[str, Any]],
    scenarios: Iterable[Mapping[str, Any]],
) -> pd.DataFrame:
    """Return one strategy/scenario row while preserving identical executions."""
    normalized=[]
    for raw in scenarios:
        scenario=dict(raw)
        cost=_finite(scenario.get("cost_r"))
        slip=_finite(scenario.get("slippage_r"))
        if cost is None or slip is None or cost<0 or slip<0:
            raise ValueError("scenario cost/slippage must be finite and >= 0")
        normalized.append({
            "scenario":str(scenario.get("scenario") or f"C{cost:.3f}_S{slip:.3f}"),
            "cost_r":float(cost),
            "slippage_r":float(slip),
            "total_friction_r":float(cost+slip),
        })

    if not normalized:
        return pd.DataFrame()

    rows=[]
    for strategy in STRATEGY_ORDER:
        pack=dict(suite.get(strategy,{}) or {})
        original=list(pack.get("results",[]) or [])
        for scenario in normalized:
            repriced=_reprice_results(
                original,
                cost_r=scenario["cost_r"],
                slippage_r=scenario["slippage_r"],
            )
            m=summarize_results(repriced)
            rows.append({
                "strategy":strategy,
                "operacional":pack.get("label",STRATEGY_LABELS[strategy]),
                **scenario,
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
                "positive_expectancy":None if m["expectancy_r"] is None else bool(m["expectancy_r"]>0),
            })
    return pd.DataFrame(rows).sort_values(
        ["strategy","total_friction_r","cost_r","slippage_r"],
        ascending=[True,True,True,True],
    ).reset_index(drop=True)


def friction_sensitivity_summary(
    sensitivity_df: pd.DataFrame,
    *,
    min_trades: int = 20,
) -> pd.DataFrame:
    threshold=max(1,int(min_trades))
    rows=[]

    for strategy in STRATEGY_ORDER:
        if not isinstance(sensitivity_df,pd.DataFrame) or sensitivity_df.empty:
            group=pd.DataFrame()
        else:
            group=sensitivity_df[sensitivity_df["strategy"]==strategy].sort_values(
                ["total_friction_r","cost_r","slippage_r"]
            )

        if group.empty:
            rows.append({
                "strategy":strategy,
                "operacional":STRATEGY_LABELS[strategy],
                "trades":0,
                "scenarios_tested":0,
                "positive_scenarios":0,
                "positive_scenario_pct":None,
                "baseline_expectancy_r":None,
                "worst_expectancy_r":None,
                "expectancy_drop_to_worst_r":None,
                "first_nonpositive_total_friction_r":None,
                "first_nonpositive_cost_r":None,
                "first_nonpositive_slippage_r":None,
                "sensitivity_status":"INSUFFICIENT",
            })
            continue

        trades=int(pd.to_numeric(group["trades"],errors="coerce").fillna(0).max())
        exps=pd.to_numeric(group["expectancy_r"],errors="coerce")
        baseline=group.iloc[0]
        baseline_exp=_finite(baseline.get("expectancy_r"))
        finite_exps=[float(x) for x in exps.dropna().tolist()]
        positive=sum(1 for x in finite_exps if x>1e-12)

        first_nonpositive=None
        for _,r in group.iterrows():
            exp=_finite(r.get("expectancy_r"))
            if exp is not None and exp<=1e-12:
                first_nonpositive=r
                break

        worst=min(finite_exps) if finite_exps else None
        drop=None
        if baseline_exp is not None and worst is not None:
            drop=baseline_exp-worst

        if trades<threshold or baseline_exp is None:
            status="INSUFFICIENT"
        elif baseline_exp<=1e-12:
            status="NONPOSITIVE_BASELINE"
        elif positive==len(finite_exps) and len(finite_exps)==len(group):
            status="POSITIVE_ALL_TESTED_FRICTION"
        else:
            status="BREAKS_UNDER_TESTED_FRICTION"

        rows.append({
            "strategy":strategy,
            "operacional":group.iloc[0].get("operacional",STRATEGY_LABELS[strategy]),
            "trades":trades,
            "scenarios_tested":int(len(group)),
            "positive_scenarios":positive,
            "positive_scenario_pct":round(positive/len(group)*100.0,2) if len(group) else None,
            "baseline_expectancy_r":None if baseline_exp is None else round(baseline_exp,4),
            "worst_expectancy_r":None if worst is None else round(worst,4),
            "expectancy_drop_to_worst_r":None if drop is None else round(drop,4),
            "first_nonpositive_total_friction_r":None if first_nonpositive is None else round(float(first_nonpositive["total_friction_r"]),4),
            "first_nonpositive_cost_r":None if first_nonpositive is None else round(float(first_nonpositive["cost_r"]),4),
            "first_nonpositive_slippage_r":None if first_nonpositive is None else round(float(first_nonpositive["slippage_r"]),4),
            "sensitivity_status":status,
        })
    return pd.DataFrame(rows)


def friction_breakdown_frame(
    suite: Mapping[str, Mapping[str, Any]],
    scenarios: Iterable[Mapping[str, Any]],
    *,
    dimensions: Iterable[str] = ("session","pair"),
) -> pd.DataFrame:
    """Describe friction sensitivity by segment without mixing strategies."""
    scenario_rows=[dict(x) for x in scenarios]
    dims=[str(x).strip() for x in dimensions if str(x).strip()]
    rows=[]
    for strategy in STRATEGY_ORDER:
        pack=dict(suite.get(strategy,{}) or {})
        original=list(pack.get("results",[]) or [])
        for scenario in scenario_rows:
            cost=_finite(scenario.get("cost_r"))
            slip=_finite(scenario.get("slippage_r"))
            if cost is None or slip is None or cost<0 or slip<0:
                raise ValueError("scenario cost/slippage must be finite and >= 0")
            repriced=_reprice_results(original,cost_r=cost,slippage_r=slip)
            for dimension in dims:
                grouped={}
                for raw in repriced:
                    row=dict(raw)
                    value=str(row.get(dimension,"N/D") or "N/D")
                    grouped.setdefault(value,[]).append(row)
                for segment,records in grouped.items():
                    m=summarize_results(records)
                    rows.append({
                        "strategy":strategy,
                        "operacional":pack.get("label",STRATEGY_LABELS[strategy]),
                        "dimension":dimension,
                        "segment":segment,
                        "scenario":str(scenario.get("scenario") or f"C{cost:.3f}_S{slip:.3f}"),
                        "cost_r":float(cost),
                        "slippage_r":float(slip),
                        "total_friction_r":float(cost+slip),
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
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values(
        ["dimension","strategy","segment","total_friction_r"],
        ascending=[True,True,True,True],
    ).reset_index(drop=True)


def friction_sensitivity_report(
    suite: Mapping[str, Mapping[str, Any]],
    *,
    base_cost_r: float = 0.0,
    slippage_levels_r: Iterable[float] = (0.0,0.02,0.05,0.10),
    min_trades: int = 20,
) -> dict[str, pd.DataFrame]:
    scenarios=build_friction_scenarios(
        base_cost_r=base_cost_r,
        slippage_levels_r=slippage_levels_r,
        include_zero_baseline=True,
    )
    detail=friction_sensitivity_frame(suite,scenarios)
    summary=friction_sensitivity_summary(detail,min_trades=min_trades)
    breakdown=friction_breakdown_frame(
        suite,
        scenarios,
        dimensions=("session","pair"),
    )
    return {"summary":summary,"scenarios":detail,"breakdown":breakdown}
