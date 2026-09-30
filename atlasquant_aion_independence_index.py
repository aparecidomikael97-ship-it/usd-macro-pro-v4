"""AION Independence Index V1.

Private-input, read-only financial transition planning for the ecosystem owner.

The module does not store personal income in repository files, does not recommend
quitting employment, does not move money, and does not treat trading income as
required support for essential expenses.

All personal values are caller-supplied at runtime.
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence
import math

SCHEMA = "ATLASQUANT_AION_INDEPENDENCE_INDEX_V1"
VERSION = "1"


def _num(value: Any, *, minimum: float = 0.0, maximum: float | None = None) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    if not math.isfinite(number) or number < minimum:
        return None
    if maximum is not None and number > maximum:
        return None
    return number


def _money_series(values: Sequence[Any] | None) -> list[float]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        return []
    out: list[float] = []
    for raw in list(values)[:24]:
        value = _num(raw)
        if value is None:
            return []
        out.append(round(value, 2))
    return out


def independence_policy() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": "PRIVATE_INPUTS_REQUIRED",
        "personal_financial_values_persisted_by_module": False,
        "repository_hardcodes_personal_income": False,
        "trade_required_for_essential_expenses": False,
        "automatic_employment_exit_recommendation": False,
        "automatic_financial_action": False,
        "executes_action": False,
    }


def evaluate_independence_index(
    *,
    baseline_net_income_low_brl: Any,
    baseline_net_income_high_brl: Any,
    non_trade_ecosystem_net_income_history_brl: Sequence[Any] | None,
    recurring_revenue_share_pct: Any,
    largest_client_share_pct: Any,
    emergency_reserve_months: Any,
    safety_multiplier: Any,
    required_consistency_months: Any,
    required_reserve_months: Any,
    minimum_recurring_share_pct: Any,
    maximum_client_concentration_pct: Any,
    essential_expenses_depend_on_trade: Any,
) -> dict[str, Any]:
    low = _num(baseline_net_income_low_brl)
    high = _num(baseline_net_income_high_brl)
    history = _money_series(non_trade_ecosystem_net_income_history_brl)
    recurring = _num(recurring_revenue_share_pct, maximum=100)
    concentration = _num(largest_client_share_pct, maximum=100)
    reserve = _num(emergency_reserve_months, maximum=120)
    multiplier = _num(safety_multiplier, minimum=1.0, maximum=3.0)

    consistency = (
        required_consistency_months
        if isinstance(required_consistency_months, int)
        and not isinstance(required_consistency_months, bool)
        and 1 <= required_consistency_months <= 24
        else None
    )
    reserve_required = _num(required_reserve_months, maximum=60)
    recurring_floor = _num(minimum_recurring_share_pct, maximum=100)
    concentration_ceiling = _num(maximum_client_concentration_pct, maximum=100)

    blockers: list[str] = []
    if low is None or high is None or low <= 0 or high < low:
        blockers.append("BASELINE_INCOME_RANGE_INVALID")
    if not history:
        blockers.append("NON_TRADE_INCOME_HISTORY_REQUIRED")
    if recurring is None:
        blockers.append("RECURRING_REVENUE_SHARE_INVALID")
    if concentration is None:
        blockers.append("CLIENT_CONCENTRATION_INVALID")
    if reserve is None:
        blockers.append("RESERVE_MONTHS_INVALID")
    if multiplier is None:
        blockers.append("SAFETY_MULTIPLIER_INVALID")
    if consistency is None:
        blockers.append("CONSISTENCY_REQUIREMENT_INVALID")
    if reserve_required is None:
        blockers.append("RESERVE_REQUIREMENT_INVALID")
    if recurring_floor is None:
        blockers.append("RECURRING_SHARE_FLOOR_INVALID")
    if concentration_ceiling is None:
        blockers.append("CONCENTRATION_CEILING_INVALID")
    if type(essential_expenses_depend_on_trade) is not bool:
        blockers.append("TRADE_DEPENDENCY_FLAG_REQUIRED")

    if blockers:
        return {
            "schema": SCHEMA,
            "version": VERSION,
            "state": "INDEPENDENCE_INDEX_BLOCKED",
            "blockers": blockers,
            "score": None,
            "zone": "UNKNOWN",
            "transition_review_available": False,
            "employment_exit_recommended": False,
            "executes_action": False,
        }

    target_low = round(low * multiplier, 2)
    target_high = round(high * multiplier, 2)

    recent = history[-consistency:] if len(history) >= consistency else history
    average_income = round(sum(recent) / len(recent), 2)
    minimum_income = round(min(recent), 2)
    maximum_income = round(max(recent), 2)
    consistency_months_available = len(history)

    income_target_met = average_income >= target_low
    strong_income_target_met = average_income >= target_high
    consistency_met = consistency_months_available >= consistency
    reserve_met = reserve >= reserve_required
    recurring_met = recurring >= recurring_floor
    concentration_met = concentration <= concentration_ceiling
    trade_independence_met = essential_expenses_depend_on_trade is False

    gates = {
        "income_target_met": income_target_met,
        "strong_income_target_met": strong_income_target_met,
        "consistency_met": consistency_met,
        "reserve_met": reserve_met,
        "recurring_revenue_met": recurring_met,
        "client_concentration_met": concentration_met,
        "essential_expenses_independent_from_trade": trade_independence_met,
    }

    # Score is a planning index, not probability.
    weights = {
        "income_target_met": 25,
        "strong_income_target_met": 10,
        "consistency_met": 20,
        "reserve_met": 15,
        "recurring_revenue_met": 10,
        "client_concentration_met": 10,
        "essential_expenses_independent_from_trade": 10,
    }
    score = sum(weight for key, weight in weights.items() if gates[key])

    critical_review_gates = (
        income_target_met
        and consistency_met
        and reserve_met
        and recurring_met
        and concentration_met
        and trade_independence_met
    )

    if critical_review_gates and score >= 90:
        zone = "TRANSITION_REVIEW_ZONE"
    elif score >= 65:
        zone = "APPROACHING"
    else:
        zone = "BUILDING"

    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": "INDEPENDENCE_INDEX_CALCULATED",
        "score": score,
        "score_is_probability": False,
        "zone": zone,
        "target_income_low_brl": target_low,
        "target_income_high_brl": target_high,
        "average_non_trade_ecosystem_income_brl": average_income,
        "minimum_recent_non_trade_income_brl": minimum_income,
        "maximum_recent_non_trade_income_brl": maximum_income,
        "history_months_available": consistency_months_available,
        "required_consistency_months": consistency,
        "emergency_reserve_months": reserve,
        "required_reserve_months": reserve_required,
        "recurring_revenue_share_pct": recurring,
        "minimum_recurring_share_pct": recurring_floor,
        "largest_client_share_pct": concentration,
        "maximum_client_concentration_pct": concentration_ceiling,
        "gates": gates,
        "transition_review_available": critical_review_gates,
        "employment_exit_recommended": False,
        "requires_personal_human_decision": True,
        "personal_financial_values_persisted_by_module": False,
        "automatic_financial_action": False,
        "executes_action": False,
    }


def transition_review_questions(index: Mapping[str, Any] | None) -> dict[str, Any]:
    row = dict(index or {}) if isinstance(index, Mapping) else {}
    available = (
        row.get("state") == "INDEPENDENCE_INDEX_CALCULATED"
        and row.get("transition_review_available") is True
    )
    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": "HUMAN_TRANSITION_REVIEW_AVAILABLE" if available else "CONTINUE_BUILDING",
        "questions": [
            "A renda não-Trade do ecossistema permaneceu estável além da janela mínima?",
            "A reserva cobre o período definido pelo administrador?",
            "A receita recorrente continua saudável sem concentração excessiva em um cliente?",
            "Despesas essenciais continuam independentes do resultado do Trader?",
            "Impostos, benefícios, saúde, férias e custos pessoais foram considerados fora deste índice?",
            "Existe plano reversível caso a receita caia após a transição?",
        ],
        "employment_exit_recommended": False,
        "decision_owner": "USER",
        "executes_action": False,
    }


__all__ = [
    "SCHEMA",
    "VERSION",
    "independence_policy",
    "evaluate_independence_index",
    "transition_review_questions",
]
