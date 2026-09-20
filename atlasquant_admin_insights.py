"""Administrator insight foundation for AtlasQuant private validation.

Summarizes already-computed strategy observations. It deliberately separates
sample leadership from production readiness and never auto-promotes a setup to
Beginner mode.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from math import isfinite
from typing import Dict, Iterable, List


@dataclass(frozen=True)
class StrategyObservation:
    strategy: str
    trades: int
    expectancy_r: float
    net_r: float
    profit_factor: float
    max_drawdown_r: float
    regimes_covered: int
    paper_backtest_gap_r: float
    data_quality_pct: float


@dataclass(frozen=True)
class BeginnerReadinessCriteria:
    min_trades: int
    min_profit_factor: float
    min_expectancy_r: float
    max_drawdown_r: float
    min_regimes_covered: int
    max_abs_paper_backtest_gap_r: float
    min_data_quality_pct: float


def _finite(name: str, value: float) -> float:
    value = float(value)
    if not isfinite(value):
        raise ValueError(f"{name} deve ser finito")
    return value


def evaluate_beginner_readiness(
    observation: StrategyObservation,
    criteria: BeginnerReadinessCriteria,
) -> Dict[str, object]:
    if criteria.min_trades <= 0 or criteria.min_regimes_covered <= 0:
        raise ValueError("critérios mínimos devem ser positivos")
    checks = {
        "sample_size": observation.trades >= criteria.min_trades,
        "profit_factor": _finite("profit_factor", observation.profit_factor) >= criteria.min_profit_factor,
        "expectancy": _finite("expectancy_r", observation.expectancy_r) >= criteria.min_expectancy_r,
        "drawdown": abs(_finite("max_drawdown_r", observation.max_drawdown_r)) <= criteria.max_drawdown_r,
        "regime_coverage": observation.regimes_covered >= criteria.min_regimes_covered,
        "paper_backtest_alignment": abs(_finite("paper_backtest_gap_r", observation.paper_backtest_gap_r))
        <= criteria.max_abs_paper_backtest_gap_r,
        "data_quality": _finite("data_quality_pct", observation.data_quality_pct)
        >= criteria.min_data_quality_pct,
    }
    failures = [name for name, ok in checks.items() if not ok]
    return {
        "strategy": observation.strategy,
        "checks": checks,
        "failures": failures,
        "eligible_for_human_review": not failures,
        "automatic_promotion": False,
        "interpretation": (
            "Elegibilidade significa somente que o setup pode seguir para revisão humana. "
            "Não significa lucro garantido, aprovação comercial ou promoção automática."
        ),
    }


def build_weekly_admin_brief(
    observations: Iterable[StrategyObservation],
    criteria: BeginnerReadinessCriteria,
) -> Dict[str, object]:
    rows = list(observations)
    evaluations = [evaluate_beginner_readiness(row, criteria) for row in rows]

    sample_order = sorted(
        rows,
        key=lambda x: (
            -_finite("expectancy_r", x.expectancy_r),
            -_finite("profit_factor", x.profit_factor),
            abs(_finite("max_drawdown_r", x.max_drawdown_r)),
            str(x.strategy),
        ),
    )
    drawdown_attention = sorted(
        rows,
        key=lambda x: (-abs(_finite("max_drawdown_r", x.max_drawdown_r)), str(x.strategy)),
    )
    insufficient = [
        row.strategy
        for row in rows
        if row.trades < criteria.min_trades or row.regimes_covered < criteria.min_regimes_covered
    ]
    eligible = [e["strategy"] for e in evaluations if e["eligible_for_human_review"]]

    observed_leader = sample_order[0].strategy if sample_order else None
    largest_drawdown = drawdown_attention[0].strategy if drawdown_attention else None

    return {
        "observation_count": len(rows),
        "observed_sample_order": [row.strategy for row in sample_order],
        "observed_expectancy_leader": observed_leader,
        "largest_drawdown_attention": largest_drawdown,
        "insufficient_validation": insufficient,
        "eligible_for_human_review": eligible,
        "evaluations": evaluations,
        "automatic_beginner_promotion": False,
        "summary_note": (
            "Ordem observada descreve esta amostra. O modo Iniciante exige robustez, "
            "cobertura de regimes, alinhamento paper/backtest, qualidade dos dados e revisão humana."
        ),
    }


def serialize_observations(observations: Iterable[StrategyObservation]) -> List[Dict[str, object]]:
    return [asdict(row) for row in observations]
