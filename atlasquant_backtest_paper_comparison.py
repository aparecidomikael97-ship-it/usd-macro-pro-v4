"""Read-only Backtest × Forward/Paper comparison for AtlasQuant.

This module only summarizes already-collected evidence. It never routes orders,
changes setup state, promotes strategies, or changes gates/weights.
"""
from __future__ import annotations

import math
from typing import Any, Mapping


def _finite(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _nonnegative(value: Any) -> float | None:
    number = _finite(value)
    return number if number is not None and number >= 0 else None


def _percentage(value: Any) -> float | None:
    number = _finite(value)
    return number if number is not None and 0 <= number <= 100 else None


def _count(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    number = _finite(value)
    if number is None or number < 0 or not number.is_integer():
        return None
    return int(number)


def _invalid_supplied(source: Mapping[str, Any], key: str, normalized: Any) -> bool:
    """Flag a supplied metric that could not be normalized without guessing."""
    return key in source and source.get(key) is not None and normalized is None


def compare_backtest_paper(evidence: Mapping[str, Any] | None) -> dict[str, Any]:
    """Return descriptive BT × Paper diagnostics without making decisions.

    Missing/invalid evidence fails closed to ``comparable=False``.  The output is
    deliberately descriptive: no threshold here can approve a setup.
    """
    source = dict(evidence) if isinstance(evidence, Mapping) else {}
    backtest_samples = _count(source.get("backtest_samples", source.get("trades")))
    paper_samples = _count(source.get("forward_samples"))
    backtest_expectancy = _finite(source.get("expectancy_r"))
    paper_expectancy = _finite(source.get("forward_expectancy_r"))
    backtest_pf = _nonnegative(source.get("profit_factor"))
    paper_pf = _nonnegative(source.get("forward_profit_factor"))
    backtest_dd = _nonnegative(source.get("max_drawdown_r"))
    paper_dd = _nonnegative(source.get("forward_max_drawdown_r"))
    paper_win_rate = _percentage(source.get("forward_win_rate_pct"))

    data_quality_issues: list[str] = []
    optional_metrics = (
        ("profit_factor", backtest_pf),
        ("forward_profit_factor", paper_pf),
        ("max_drawdown_r", backtest_dd),
        ("forward_max_drawdown_r", paper_dd),
        ("forward_win_rate_pct", paper_win_rate),
    )
    for key, normalized in optional_metrics:
        if _invalid_supplied(source, key, normalized):
            data_quality_issues.append(f"INVALID_{key.upper()}")

    required_metrics_present = all(
        value is not None for value in (backtest_expectancy, paper_expectancy)
    )
    samples_present = (
        backtest_samples is not None
        and paper_samples is not None
        and backtest_samples > 0
        and paper_samples > 0
    )
    comparable = required_metrics_present and samples_present
    expectancy_gap = None
    expectancy_retention_pct = None
    if comparable:
        expectancy_gap = round(paper_expectancy - backtest_expectancy, 4)
        if backtest_expectancy != 0:
            expectancy_retention_pct = round(paper_expectancy / backtest_expectancy * 100.0, 2)

    return {
        "backtest_samples": backtest_samples,
        "paper_samples": paper_samples,
        "backtest_expectancy_r": backtest_expectancy,
        "paper_expectancy_r": paper_expectancy,
        "expectancy_gap_r": expectancy_gap,
        "expectancy_retention_pct": expectancy_retention_pct,
        "backtest_profit_factor": backtest_pf,
        "paper_profit_factor": paper_pf,
        "backtest_max_drawdown_r": backtest_dd,
        "paper_max_drawdown_r": paper_dd,
        "paper_win_rate_pct": paper_win_rate,
        "data_quality_ok": not data_quality_issues,
        "data_quality_issues": data_quality_issues,
        "comparable": comparable,
        "descriptive_only": True,
        "manual_review_required": True,
        "automatic_strategy_change": False,
        "automatic_weight_change": False,
        "real_orders_enabled": False,
    }


def comparison_rows(evidence_by_setup: Mapping[str, Mapping[str, Any]] | None) -> list[dict[str, Any]]:
    """Build stable rows for a setup-performance panel."""
    if not isinstance(evidence_by_setup, Mapping):
        return []
    rows: list[dict[str, Any]] = []
    for setup_id, evidence in sorted(evidence_by_setup.items(), key=lambda item: str(item[0])):
        row = {"setup_id": str(setup_id)}
        row.update(compare_backtest_paper(evidence))
        rows.append(row)
    return rows


__all__ = ["compare_backtest_paper", "comparison_rows"]