"""AtlasQuant Operational Passport evidence fusion.

Combines already-computed research evidence from Backtest, stability,
walk-forward, Paper/Forward and Shadow. The output measures evidence coverage,
not profitability, and can at most become eligible for human review.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Any, Mapping

from atlasquant_backtest_paper_comparison import compare_backtest_paper

SCHEMA="ATLASQUANT_PASSPORT_EVIDENCE_V1"


@dataclass(frozen=True)
class EvidenceCriteria:
    min_backtest_trades:int=100
    min_paper_trades:int=30
    min_regimes:int=2
    min_sessions:int=2
    min_assets:int=1
    max_abs_expectancy_gap_r:float=0.20
    min_expectancy_r:float=0.0
    min_profit_factor:float=1.0
    max_drawdown_r:float=12.0
    min_data_quality_pct:float=70.0
    min_positive_fold_pct:float=66.0
    min_oos_positive_pct:float=60.0
    min_friction_positive_pct:float=60.0
    min_parameter_positive_pct:float=60.0
    require_temporal:bool=True
    require_walk_forward:bool=True
    require_friction:bool=True
    require_parameter:bool=True
    require_shadow:bool=False


def _finite(value:Any)->float|None:
    try:
        out=float(value)
        return out if isfinite(out) else None
    except Exception:
        return None


def _count(value:Any)->int:
    if isinstance(value,bool):
        return 0
    try:
        out=int(value)
        return max(0,out)
    except Exception:
        return 0


def _available_status(value:Any)->bool:
    raw=str(value or "").strip().upper()
    return bool(raw and raw not in {"N/A","NA","NONE","UNKNOWN","INSUFFICIENT","SEM AMOSTRA"})


def fuse_operational_evidence(
    passport:Mapping[str,Any]|None,
    *,
    paper_summary:Mapping[str,Any]|None=None,
    temporal_status:Any=None,
    walk_forward_status:Any=None,
    friction_status:Any=None,
    parameter_status:Any=None,
    positive_fold_pct:Any=None,
    oos_positive_pct:Any=None,
    friction_positive_pct:Any=None,
    parameter_positive_pct:Any=None,
    shadow_summary:Mapping[str,Any]|None=None,
    criteria:EvidenceCriteria|None=None,
)->dict[str,Any]:
    c=criteria or EvidenceCriteria()
    p=dict(passport or {})
    observed=dict(p.get("observed_metrics",{}) or {})
    coverage=dict(p.get("coverage",{}) or {})
    paper=dict(paper_summary or {})
    shadow=dict(shadow_summary or {})

    bt_trades=_count(observed.get("trades"))
    bt_expectancy=_finite(observed.get("expectancy_r"))
    bt_pf=_finite(observed.get("profit_factor"))
    bt_dd=_finite(observed.get("max_drawdown_r"))
    data_quality=_finite(p.get("data_quality_pct"))

    forward_samples=_count(paper.get("forward_samples",paper.get("paper_samples")))
    forward_expectancy=_finite(
        paper.get("forward_expectancy_r",paper.get("paper_expectancy_r"))
    )

    comparison=compare_backtest_paper({
        "backtest_samples":bt_trades,
        "forward_samples":forward_samples,
        "expectancy_r":bt_expectancy,
        "forward_expectancy_r":forward_expectancy,
        "profit_factor":bt_pf,
        "forward_profit_factor":paper.get("forward_profit_factor"),
        "max_drawdown_r":bt_dd,
        "forward_max_drawdown_r":paper.get("forward_max_drawdown_r"),
        "forward_win_rate_pct":paper.get("forward_win_rate_pct"),
    })
    expectancy_gap=_finite(comparison.get("expectancy_gap_r"))

    fold_pct=_finite(positive_fold_pct)
    oos_pct=_finite(oos_positive_pct)
    friction_pct=_finite(friction_positive_pct)
    parameter_pct=_finite(parameter_positive_pct)

    checks={
        "backtest_sample":bt_trades>=int(c.min_backtest_trades),
        "asset_coverage":_count(coverage.get("assets"))>=int(c.min_assets),
        "session_coverage":_count(coverage.get("sessions"))>=int(c.min_sessions),
        "regime_coverage":_count(coverage.get("regimes"))>=int(c.min_regimes),
        "data_quality":bool(data_quality is not None and data_quality>=float(c.min_data_quality_pct)),
        "backtest_expectancy":bool(bt_expectancy is not None and bt_expectancy>float(c.min_expectancy_r)),
        "profit_factor":bool(bt_pf is not None and bt_pf>=float(c.min_profit_factor)),
        "drawdown":bool(bt_dd is not None and abs(bt_dd)<=float(c.max_drawdown_r)),
        "paper_sample":forward_samples>=int(c.min_paper_trades),
        "paper_expectancy":bool(
            forward_expectancy is not None
            and forward_expectancy>float(c.min_expectancy_r)
        ),
        "paper_backtest_alignment":bool(
            expectancy_gap is not None
            and abs(expectancy_gap)<=float(c.max_abs_expectancy_gap_r)
        ),
        "temporal_diagnostic":(
            bool(
                _available_status(temporal_status)
                and fold_pct is not None
                and fold_pct>=float(c.min_positive_fold_pct)
            )
            if c.require_temporal else True
        ),
        "walk_forward_diagnostic":(
            bool(
                _available_status(walk_forward_status)
                and oos_pct is not None
                and oos_pct>=float(c.min_oos_positive_pct)
            )
            if c.require_walk_forward else True
        ),
        "friction_diagnostic":(
            bool(
                _available_status(friction_status)
                and friction_pct is not None
                and friction_pct>=float(c.min_friction_positive_pct)
            )
            if c.require_friction else True
        ),
        "parameter_diagnostic":(
            bool(
                _available_status(parameter_status)
                and parameter_pct is not None
                and parameter_pct>=float(c.min_parameter_positive_pct)
            )
            if c.require_parameter else True
        ),
        "shadow_review":(
            bool(shadow.get("eligible_for_manual_review",False))
            if c.require_shadow else True
        ),
    }

    backtest_sufficient=all(
        checks[name]
        for name in (
            "backtest_sample","asset_coverage","session_coverage","regime_coverage",
            "data_quality","backtest_expectancy","profit_factor","drawdown",
        )
    )
    paper_sufficient=all(
        checks[name]
        for name in ("paper_sample","paper_expectancy","paper_backtest_alignment")
    )

    evidence_steps=[
        {
            "step":"BACKTEST",
            "required":True,
            "available":bt_trades>0,
            "sufficient":backtest_sufficient,
            "detail":f"{bt_trades} trade(s) históricos",
        },
        {
            "step":"TEMPORAL",
            "required":bool(c.require_temporal),
            "available":_available_status(temporal_status) and fold_pct is not None,
            "sufficient":checks["temporal_diagnostic"],
            "detail":str(temporal_status or "não executado")+" · "+("—" if fold_pct is None else f"{fold_pct:.1f}% folds positivos"),
        },
        {
            "step":"WALK_FORWARD",
            "required":bool(c.require_walk_forward),
            "available":_available_status(walk_forward_status) and oos_pct is not None,
            "sufficient":checks["walk_forward_diagnostic"],
            "detail":str(walk_forward_status or "não executado")+" · "+("—" if oos_pct is None else f"{oos_pct:.1f}% OOS positivo"),
        },
        {
            "step":"FRICTION",
            "required":bool(c.require_friction),
            "available":_available_status(friction_status) and friction_pct is not None,
            "sufficient":checks["friction_diagnostic"],
            "detail":str(friction_status or "não executado")+" · "+("—" if friction_pct is None else f"{friction_pct:.1f}% cenários positivos"),
        },
        {
            "step":"PARAMETERS",
            "required":bool(c.require_parameter),
            "available":_available_status(parameter_status) and parameter_pct is not None,
            "sufficient":checks["parameter_diagnostic"],
            "detail":str(parameter_status or "não executado")+" · "+("—" if parameter_pct is None else f"{parameter_pct:.1f}% variantes positivas"),
        },
        {
            "step":"PAPER_FORWARD",
            "required":True,
            "available":forward_samples>0,
            "sufficient":paper_sufficient,
            "detail":(
                f"{forward_samples} amostra(s) · gap "
                + ("—" if expectancy_gap is None else f"{expectancy_gap:+.2f}R")
            ),
        },
        {
            "step":"SHADOW",
            "required":bool(c.require_shadow),
            "available":_count(shadow.get("samples"))>0,
            "sufficient":checks["shadow_review"],
            "detail":(
                f"{_count(shadow.get('samples'))} amostra(s)"
                + (" · opcional" if not c.require_shadow else "")
            ),
        },
        {
            "step":"HUMAN_REVIEW",
            "required":True,
            "available":False,
            "sufficient":False,
            "detail":"sempre manual; nunca promovido automaticamente",
        },
    ]

    failures=[name for name,ok in checks.items() if not ok]
    human_review_ready=not failures
    if bt_trades<=0:
        state="NO_BACKTEST_EVIDENCE"
    elif not checks["backtest_sample"]:
        state="BACKTEST_BUILDING"
    elif not checks["paper_sample"]:
        state="PAPER_EVIDENCE_PENDING"
    elif failures:
        state="EVIDENCE_GAPS"
    else:
        state="HUMAN_REVIEW_CANDIDATE"

    machine_steps=[step for step in evidence_steps[:-1] if step.get("required")]
    required_evidence_steps=max(1,len(machine_steps))
    available_count=sum(1 for step in machine_steps if step.get("available"))
    sufficient_count=sum(1 for step in machine_steps if step.get("sufficient"))
    evidence_coverage_pct=round(100.0*available_count/required_evidence_steps,1)
    evidence_sufficient_pct=round(100.0*sufficient_count/required_evidence_steps,1)

    return {
        "schema":SCHEMA,
        "strategy":str(p.get("strategy") or ""),
        "state":state,
        "checks":checks,
        "failures":failures,
        "evidence_steps":evidence_steps,
        "evidence_coverage_pct":evidence_coverage_pct,
        "evidence_sufficient_pct":evidence_sufficient_pct,
        "required_machine_steps":required_evidence_steps,
        "backtest_paper_comparison":comparison,
        "eligible_for_human_review":human_review_ready,
        "automatic_promotion":False,
        "automatic_strategy_change":False,
        "real_orders_enabled":False,
        "interpretation":(
            "Cobertura de evidências mede quais etapas de validação foram observadas. "
            "Ela não mede probabilidade de lucro e não aprova o operacional automaticamente."
        ),
    }


__all__=[
    "SCHEMA",
    "EvidenceCriteria",
    "fuse_operational_evidence",
]
