"""Foundations for the AtlasQuant Investir journey.

This module is deliberately isolated from broker/execution code. It provides
transparent simulations and descriptive quality snapshots; it does not emit
BUY/SELL instructions and never treats a score as a probability of profit.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from math import isfinite
from typing import Dict, List, Optional

SIMULATION_NOTICE = (
    "Simulação educacional: rentabilidade, dividendos e valorização futuros "
    "não são garantidos. Compare cenários, riscos, liquidez, custos e impostos."
)


def _finite(name: str, value: float) -> float:
    value = float(value)
    if not isfinite(value):
        raise ValueError(f"{name} deve ser finito")
    return value


def _monthly_rate(annual_pct: float) -> float:
    annual_pct = _finite("annual_pct", annual_pct)
    if annual_pct <= -100.0:
        raise ValueError("annual_pct deve ser maior que -100")
    return (1.0 + annual_pct / 100.0) ** (1.0 / 12.0) - 1.0


@dataclass(frozen=True)
class CompoundProjectionInput:
    initial_amount: float
    monthly_contribution: float
    annual_return_pct: float
    years: int


@dataclass(frozen=True)
class IncomeProjectionInput:
    initial_amount: float
    monthly_contribution: float
    annual_income_yield_pct: float
    annual_price_growth_pct: float
    years: int
    reinvest_income: bool = True


def project_compound(params: CompoundProjectionInput) -> Dict[str, object]:
    initial = _finite("initial_amount", params.initial_amount)
    monthly = _finite("monthly_contribution", params.monthly_contribution)
    if initial < 0 or monthly < 0:
        raise ValueError("aportes não podem ser negativos")
    if int(params.years) != params.years or params.years <= 0:
        raise ValueError("years deve ser inteiro positivo")

    rate = _monthly_rate(params.annual_return_pct)
    balance = initial
    contributed = initial
    checkpoints: List[Dict[str, float]] = []

    for month in range(1, params.years * 12 + 1):
        balance *= 1.0 + rate
        balance += monthly
        contributed += monthly
        if month % 12 == 0:
            checkpoints.append(
                {
                    "year": month // 12,
                    "contributed": round(contributed, 2),
                    "projected_value": round(balance, 2),
                    "projected_gain": round(balance - contributed, 2),
                }
            )

    return {
        "input": asdict(params),
        "total_contributed": round(contributed, 2),
        "projected_value": round(balance, 2),
        "projected_gain": round(balance - contributed, 2),
        "yearly_checkpoints": checkpoints,
        "notice": SIMULATION_NOTICE,
    }


def project_income_asset(params: IncomeProjectionInput) -> Dict[str, object]:
    initial = _finite("initial_amount", params.initial_amount)
    monthly = _finite("monthly_contribution", params.monthly_contribution)
    if initial < 0 or monthly < 0:
        raise ValueError("aportes não podem ser negativos")
    if int(params.years) != params.years or params.years <= 0:
        raise ValueError("years deve ser inteiro positivo")
    if params.annual_income_yield_pct < 0:
        raise ValueError("annual_income_yield_pct não pode ser negativo")

    growth_rate = _monthly_rate(params.annual_price_growth_pct)
    income_rate = _monthly_rate(params.annual_income_yield_pct)
    balance = initial
    contributed = initial
    cash_income = 0.0
    income_generated = 0.0
    checkpoints: List[Dict[str, float]] = []

    for month in range(1, params.years * 12 + 1):
        balance *= 1.0 + growth_rate
        income = balance * income_rate
        income_generated += income
        if params.reinvest_income:
            balance += income
        else:
            cash_income += income
        balance += monthly
        contributed += monthly
        if month % 12 == 0:
            checkpoints.append(
                {
                    "year": month // 12,
                    "contributed": round(contributed, 2),
                    "portfolio_value": round(balance, 2),
                    "income_generated": round(income_generated, 2),
                    "cash_income_paid": round(cash_income, 2),
                }
            )

    return {
        "input": asdict(params),
        "total_contributed": round(contributed, 2),
        "projected_portfolio_value": round(balance, 2),
        "projected_income_generated": round(income_generated, 2),
        "projected_cash_income_paid": round(cash_income, 2),
        "yearly_checkpoints": checkpoints,
        "notice": SIMULATION_NOTICE,
    }


def required_capital_for_monthly_income(
    target_monthly_income: float, annual_income_yield_pct: float
) -> Dict[str, float | str]:
    target = _finite("target_monthly_income", target_monthly_income)
    annual_yield = _finite("annual_income_yield_pct", annual_income_yield_pct)
    if target < 0:
        raise ValueError("target_monthly_income não pode ser negativo")
    if annual_yield <= 0:
        raise ValueError("annual_income_yield_pct deve ser maior que zero")
    annual_income = target * 12.0
    capital = annual_income / (annual_yield / 100.0)
    return {
        "target_monthly_income": round(target, 2),
        "annual_income_yield_pct": round(annual_yield, 4),
        "illustrative_required_capital": round(capital, 2),
        "notice": SIMULATION_NOTICE,
    }


def _clamp_score(value: float) -> float:
    return round(max(0.0, min(100.0, value)), 1)


def dividend_quality_snapshot(
    *,
    asset_type: str,
    payment_consistency_pct: float,
    payout_ratio_pct: Optional[float],
    net_debt_to_ebitda: Optional[float],
    earnings_or_ffo_growth_pct: Optional[float],
    free_cash_flow_positive: Optional[bool],
    vacancy_pct: Optional[float] = None,
) -> Dict[str, object]:
    """Return a descriptive dividend quality index, never a profit probability."""
    consistency = max(0.0, min(100.0, _finite("payment_consistency_pct", payment_consistency_pct)))
    score = consistency * 0.40
    flags: List[str] = []
    positives: List[str] = []

    if consistency >= 85:
        positives.append("histórico de pagamentos consistente")
    elif consistency < 60:
        flags.append("histórico de pagamentos irregular")

    if payout_ratio_pct is not None:
        payout = _finite("payout_ratio_pct", payout_ratio_pct)
        if 0 <= payout <= 85:
            score += 18
            positives.append("payout dentro de faixa observacional saudável")
        elif payout > 100:
            flags.append("payout acima de 100% exige investigação")
        else:
            score += 8

    if net_debt_to_ebitda is not None:
        debt = _finite("net_debt_to_ebitda", net_debt_to_ebitda)
        if debt <= 2:
            score += 16
            positives.append("alavancagem contida")
        elif debt <= 3.5:
            score += 8
        else:
            flags.append("alavancagem elevada")

    if earnings_or_ffo_growth_pct is not None:
        growth = _finite("earnings_or_ffo_growth_pct", earnings_or_ffo_growth_pct)
        if growth > 5:
            score += 14
            positives.append("lucro/FFO em crescimento")
        elif growth >= 0:
            score += 7
        else:
            flags.append("lucro/FFO em contração")

    if free_cash_flow_positive is True:
        score += 7
        positives.append("fluxo de caixa livre positivo")
    elif free_cash_flow_positive is False:
        flags.append("fluxo de caixa livre negativo")

    if asset_type.strip().lower() in {"fii", "fundo imobiliário", "fundo imobiliario"}:
        if vacancy_pct is None:
            flags.append("vacância não informada")
        else:
            vacancy = _finite("vacancy_pct", vacancy_pct)
            if vacancy <= 8:
                score += 5
                positives.append("vacância baixa")
            elif vacancy > 15:
                flags.append("vacância elevada")
    else:
        score += 5

    return {
        "asset_type": asset_type,
        "dividend_quality_index": _clamp_score(score),
        "positive_factors": positives,
        "risk_flags": flags,
        "interpretation": (
            "Índice de qualidade/consistência baseado nos dados informados; "
            "não representa probabilidade de pagamento, lucro ou valorização."
        ),
    }


def growth_watch_snapshot(
    *,
    revenue_growth_pct: float,
    earnings_growth_pct: float,
    free_cash_flow_margin_pct: Optional[float],
    net_debt_to_ebitda: Optional[float],
    share_dilution_pct: Optional[float] = None,
) -> Dict[str, object]:
    """Create a long-horizon watchlist snapshot without forecasting price."""
    revenue = _finite("revenue_growth_pct", revenue_growth_pct)
    earnings = _finite("earnings_growth_pct", earnings_growth_pct)
    score = 0.0
    reasons: List[str] = []
    risks: List[str] = []

    if revenue >= 15:
        score += 30
        reasons.append("receita cresce em ritmo elevado")
    elif revenue > 5:
        score += 20
        reasons.append("receita cresce")
    elif revenue < 0:
        risks.append("receita em contração")

    if earnings >= 15:
        score += 30
        reasons.append("lucro cresce em ritmo elevado")
    elif earnings > 5:
        score += 20
        reasons.append("lucro cresce")
    elif earnings < 0:
        risks.append("lucro em contração")

    if free_cash_flow_margin_pct is not None:
        fcf = _finite("free_cash_flow_margin_pct", free_cash_flow_margin_pct)
        if fcf >= 10:
            score += 20
            reasons.append("margem de fluxo de caixa livre positiva")
        elif fcf > 0:
            score += 10
        else:
            risks.append("fluxo de caixa livre fraco/negativo")

    if net_debt_to_ebitda is not None:
        debt = _finite("net_debt_to_ebitda", net_debt_to_ebitda)
        if debt <= 1.5:
            score += 15
            reasons.append("alavancagem baixa")
        elif debt <= 3:
            score += 8
        else:
            risks.append("alavancagem elevada")

    if share_dilution_pct is not None:
        dilution = _finite("share_dilution_pct", share_dilution_pct)
        if dilution <= 0:
            score += 5
        elif dilution > 5:
            risks.append("diluição relevante de acionistas")

    return {
        "growth_quality_index": _clamp_score(score),
        "reasons_to_monitor": reasons,
        "risk_flags": risks,
        "interpretation": (
            "Indicador para priorizar estudo e acompanhamento de longo prazo; "
            "não é previsão de preço nem recomendação de compra."
        ),
    }
