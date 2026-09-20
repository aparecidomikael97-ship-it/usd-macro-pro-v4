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
    min_backtest_trades:int=50
    min_paper_trades:int=20
    min_regimes:int=2
    min_sessions:int=2
    min_assets:int=1
    max_abs_expectancy_gap_r:float=0.25
    min_data_quality_pct:float=70.0
    require_temporal:bool=True
    require_walk_forward:bool=True
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

    checks={
        "backtest_sample":bt_trades>=int(c.min_backtest_trades),
        "asset_coverage":_count(coverage.get("assets"))>=int(c.min_assets),
        "session_coverage":_count(coverage.get("sessions"))>=int(c.min_sessions),
        "regime_coverage":_count(coverage.get("regimes"))>=int(c.min_regimes),
        "data_quality":bool(data_quality is not None and data_quality>=float(c.min_data_quality_pct)),
        "paper_sample":forward_samples>=int(c.min_paper_trades),
        "paper_backtest_alignment":bool(
            expectancy_gap is not None
            and abs(expectancy_gap)<=float(c.max_abs_expectancy_gap_r)
        ),
        "temporal_diagnostic":(
            _available_status(temporal_status) if c.require_temporal else True
        ),
        "walk_forward_diagnostic":(
            _available_status(walk_forward_status) if c.require_walk_forward else True
        ),
        "shadow_review":(
            bool(shadow.get("eligible_for_manual_review",False))
            if c.require_shadow else True
        ),
    }

    evidence_steps=[
        {
            "step":"BACKTEST",
            "available":bt_trades>0,
            "sufficient":checks["backtest_sample"],
            "detail":f"{bt_trades} trade(s) históricos",
        },
        {
            "step":"TEMPORAL",
            "available":_available_status(temporal_status),
            "sufficient":checks["temporal_diagnostic"],
            "detail":str(temporal_status or "não executado"),
        },
        {
            "step":"WALK_FORWARD",
            "available":_available_status(walk_forward_status),
            "sufficient":checks["walk_forward_diagnostic"],
            "detail":str(walk_forward_status or "não executado"),
        },
        {
            "step":"PAPER_FORWARD",
            "available":forward_samples>0,
            "sufficient":bool(checks["paper_sample"] and checks["paper_backtest_alignment"]),
            "detail":(
                f"{forward_samples} amostra(s) · gap "
                + ("—" if expectancy_gap is None else f"{expectancy_gap:+.2f}R")
            ),
        },
        {
            "step":"SHADOW",
            "available":_count(shadow.get("samples"))>0,
            "sufficient":bool(shadow.get("eligible_for_manual_review",False)),
            "detail":f"{_count(shadow.get('samples'))} amostra(s)",
        },
        {
            "step":"HUMAN_REVIEW",
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

    available_count=sum(1 for step in evidence_steps[:-1] if step["available"])
    required_evidence_steps=5
    evidence_coverage_pct=round(100.0*available_count/required_evidence_steps,1)

    return {
        "schema":SCHEMA,
        "strategy":str(p.get("strategy") or ""),
        "state":state,
        "checks":checks,
        "failures":failures,
        "evidence_steps":evidence_steps,
        "evidence_coverage_pct":evidence_coverage_pct,
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
