"""Fail-closed risk guard foundation for future AtlasQuant execution.

The guard is safe to use in simulation/paper now and is intentionally decoupled
from any broker. Real-order execution remains disabled elsewhere in AtlasQuant.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from math import isfinite
from typing import List


@dataclass(frozen=True)
class RiskLimits:
    bankroll: float
    max_daily_loss: float
    max_loss_per_trade: float
    max_trades_per_day: int
    max_consecutive_losses: int
    max_open_exposure: float


@dataclass(frozen=True)
class RiskState:
    daily_pnl: float = 0.0
    trades_today: int = 0
    consecutive_losses: int = 0
    open_exposure: float = 0.0


@dataclass(frozen=True)
class RiskDecision:
    locked: bool
    reasons: tuple[str, ...]
    remaining_daily_loss_budget: float
    remaining_trade_slots: int


def _finite(name: str, value: float) -> float:
    value = float(value)
    if not isfinite(value):
        raise ValueError(f"{name} deve ser finito")
    return value


def validate_limits(limits: RiskLimits) -> RiskLimits:
    numeric = {
        "bankroll": limits.bankroll,
        "max_daily_loss": limits.max_daily_loss,
        "max_loss_per_trade": limits.max_loss_per_trade,
        "max_open_exposure": limits.max_open_exposure,
    }
    for name, value in numeric.items():
        value = _finite(name, value)
        if value <= 0:
            raise ValueError(f"{name} deve ser maior que zero")
    if limits.max_daily_loss > limits.bankroll:
        raise ValueError("max_daily_loss não pode exceder bankroll")
    if limits.max_loss_per_trade > limits.max_daily_loss:
        raise ValueError("max_loss_per_trade não pode exceder max_daily_loss")
    if limits.max_trades_per_day <= 0 or limits.max_consecutive_losses <= 0:
        raise ValueError("limites de contagem devem ser positivos")
    return limits


def evaluate_risk_guard(
    limits: RiskLimits,
    state: RiskState,
    *,
    requested_trade_risk: float = 0.0,
    requested_exposure: float = 0.0,
) -> RiskDecision:
    validate_limits(limits)
    requested_trade_risk = _finite("requested_trade_risk", requested_trade_risk)
    requested_exposure = _finite("requested_exposure", requested_exposure)
    if requested_trade_risk < 0 or requested_exposure < 0:
        raise ValueError("risco/exposição solicitados não podem ser negativos")

    reasons: List[str] = []
    realized_loss = max(0.0, -float(state.daily_pnl))
    remaining_loss = max(0.0, limits.max_daily_loss - realized_loss)
    remaining_slots = max(0, limits.max_trades_per_day - int(state.trades_today))

    if realized_loss >= limits.max_daily_loss:
        reasons.append("limite de perda diária atingido")
    if state.trades_today >= limits.max_trades_per_day:
        reasons.append("limite de operações do dia atingido")
    if state.consecutive_losses >= limits.max_consecutive_losses:
        reasons.append("limite de perdas consecutivas atingido")
    if state.open_exposure > limits.max_open_exposure:
        reasons.append("exposição aberta acima do limite")
    if requested_trade_risk > limits.max_loss_per_trade:
        reasons.append("risco solicitado por operação acima do limite")
    if requested_trade_risk > remaining_loss:
        reasons.append("risco solicitado excede orçamento de perda restante")
    if state.open_exposure + requested_exposure > limits.max_open_exposure:
        reasons.append("nova exposição excederia o limite")

    return RiskDecision(
        locked=bool(reasons),
        reasons=tuple(reasons),
        remaining_daily_loss_budget=round(remaining_loss, 2),
        remaining_trade_slots=remaining_slots,
    )


def limits_are_tighter_or_equal(current: RiskLimits, proposed: RiskLimits) -> bool:
    validate_limits(current)
    validate_limits(proposed)
    return (
        proposed.bankroll == current.bankroll
        and proposed.max_daily_loss <= current.max_daily_loss
        and proposed.max_loss_per_trade <= current.max_loss_per_trade
        and proposed.max_trades_per_day <= current.max_trades_per_day
        and proposed.max_consecutive_losses <= current.max_consecutive_losses
        and proposed.max_open_exposure <= current.max_open_exposure
    )


def can_apply_limit_change(
    current: RiskLimits,
    proposed: RiskLimits,
    *,
    last_relaxation_at: datetime | None,
    now: datetime,
    relaxation_cooldown_hours: int = 24,
) -> bool:
    """Tightening is immediate; relaxing requires a cooling-off period."""
    if limits_are_tighter_or_equal(current, proposed):
        return True
    if relaxation_cooldown_hours <= 0:
        raise ValueError("relaxation_cooldown_hours deve ser positivo")
    if last_relaxation_at is None:
        return False
    return now >= last_relaxation_at + timedelta(hours=relaxation_cooldown_hours)
