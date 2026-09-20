"""Position-by-event foundation for AtlasQuant.

Consumes directional context already produced by upstream macro engines. This
module does not predict the release and does not tell the user to hold, exit or
add to a position. It exposes alignment, event risk and review requirements.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from math import isfinite
from typing import Dict, Optional

EFFECTS = {"SUPPORTIVE", "ADVERSE", "NEUTRAL", "UNCERTAIN"}
SIDES = {"LONG", "SHORT"}
HIGH_IMPACT = {"HIGH", "ALTO", "MAXIMUM", "MAXIMO", "MÁXIMO"}


@dataclass(frozen=True)
class PositionContext:
    pair: str
    base_currency: str
    quote_currency: str
    side: str
    horizon: str
    unrealized_r: float = 0.0


@dataclass(frozen=True)
class EventContext:
    name: str
    currency: str
    impact: str
    minutes_to_event: Optional[float] = None
    expected_currency_effect: str = "UNCERTAIN"
    priced_in_state: str = "UNKNOWN"


def _normal(value: str) -> str:
    return str(value or "").strip().upper()


def _finite_optional(value: Optional[float]) -> Optional[float]:
    if value is None:
        return None
    value = float(value)
    if not isfinite(value):
        raise ValueError("minutes_to_event deve ser finito")
    return value


def currency_exposure(position: PositionContext, currency: str) -> int:
    """Return +1 if the position benefits from currency strength, -1 if hurt."""
    side = _normal(position.side)
    if side not in SIDES:
        raise ValueError("side deve ser LONG ou SHORT")
    base = _normal(position.base_currency)
    quote = _normal(position.quote_currency)
    target = _normal(currency)
    if target not in {base, quote}:
        return 0

    long_sign = 1 if target == base else -1
    return long_sign if side == "LONG" else -long_sign


def _effect_sign(effect: str) -> int:
    effect = _normal(effect)
    if effect not in EFFECTS:
        raise ValueError("currency effect inválido")
    return {"SUPPORTIVE": 1, "ADVERSE": -1, "NEUTRAL": 0, "UNCERTAIN": 0}[effect]


def _timing_state(minutes: Optional[float]) -> str:
    if minutes is None:
        return "UNKNOWN_TIME"
    if minutes < 0:
        return "PASSED"
    if minutes <= 15:
        return "IMMINENT"
    if minutes <= 240:
        return "NEAR"
    if minutes <= 1440:
        return "TODAY"
    return "SCHEDULED"


def assess_pre_event(position: PositionContext, event: EventContext) -> Dict[str, object]:
    minutes = _finite_optional(event.minutes_to_event)
    exposure = currency_exposure(position, event.currency)
    impacted = exposure != 0
    impact = _normal(event.impact)
    effect = _normal(event.expected_currency_effect)
    effect_sign = _effect_sign(effect)
    alignment_value = exposure * effect_sign if impacted else 0

    if not impacted:
        scenario = "NOT_RELEVANT"
    elif effect == "UNCERTAIN":
        scenario = "UNCERTAIN"
    elif alignment_value > 0:
        scenario = "ALIGNED_SCENARIO"
    elif alignment_value < 0:
        scenario = "CONFLICTING_SCENARIO"
    else:
        scenario = "NEUTRAL_SCENARIO"

    timing = _timing_state(minutes)
    high_impact = impact in HIGH_IMPACT
    elevated_window = timing in {"IMMINENT", "NEAR"}
    review_required = bool(impacted and (effect == "UNCERTAIN" or (high_impact and elevated_window)))

    risks = []
    if impacted and high_impact and elevated_window:
        risks.append("evento de alto impacto próximo pode aumentar volatilidade")
    if impacted and effect == "UNCERTAIN":
        risks.append("efeito direcional esperado está incerto")
    if impacted and _normal(event.priced_in_state) in {"HIGH", "ALTO", "PARTIAL", "PARCIAL"}:
        risks.append("parte da expectativa pode já estar precificada")
    if position.unrealized_r > 0 and review_required:
        risks.append("posição está em lucro, mas lucro aberto não elimina risco de evento")

    return {
        "position": asdict(position),
        "event": asdict(event),
        "impacted": impacted,
        "currency_exposure": exposure,
        "scenario_alignment": scenario,
        "timing_state": timing,
        "high_impact": high_impact,
        "review_required": review_required,
        "risk_flags": risks,
        "action": "HUMAN_REVIEW_ONLY" if review_required else "NO_AUTOMATIC_ACTION",
        "interpretation": (
            "O resultado descreve alinhamento de cenário e risco de evento. "
            "Não é previsão do movimento nem instrução para manter, sair ou aumentar posição."
        ),
    }


def assess_post_event(
    position: PositionContext,
    event: EventContext,
    *,
    realized_currency_effect: str,
) -> Dict[str, object]:
    """Reassess thesis after an upstream macro engine classifies the release."""
    exposure = currency_exposure(position, event.currency)
    impacted = exposure != 0
    effect = _normal(realized_currency_effect)
    sign = _effect_sign(effect)

    if not impacted:
        thesis_state = "NOT_RELEVANT"
    elif effect == "UNCERTAIN":
        thesis_state = "REASSESS"
    elif exposure * sign > 0:
        thesis_state = "EVENT_ALIGNED_WITH_POSITION"
    elif exposure * sign < 0:
        thesis_state = "EVENT_CONFLICTS_WITH_POSITION"
    else:
        thesis_state = "EVENT_NEUTRAL"

    return {
        "position": asdict(position),
        "event": asdict(event),
        "realized_currency_effect": effect,
        "thesis_state": thesis_state,
        "review_required": bool(impacted),
        "action": "HUMAN_REVIEW_ONLY" if impacted else "NO_AUTOMATIC_ACTION",
        "interpretation": (
            "A classificação pós-evento vem do motor macro upstream. "
            "Este módulo não transforma surpresa econômica em ordem automática."
        ),
    }
