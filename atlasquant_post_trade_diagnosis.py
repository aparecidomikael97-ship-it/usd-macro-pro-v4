"""AtlasQuant point-in-time post-trade diagnosis.

The module separates decision quality from outcome. It uses evidence captured
at decision time plus explicitly timestamped during-trade events. It never uses
future information to retroactively rewrite the initial thesis.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from math import isfinite
from typing import Iterable

SCHEMA = "ATLASQUANT_POST_TRADE_DIAGNOSIS_V1"


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _finite(name: str, value: float) -> float:
    out = float(value)
    if not isfinite(out):
        raise ValueError(f"{name} deve ser finito")
    return out


@dataclass(frozen=True)
class DecisionSnapshot:
    trade_id: str
    captured_at: datetime
    entry_time: datetime
    side: str
    macro_alignment: int
    technical_confirmation: bool
    liquidity_confirmation: bool
    regime_fit: bool
    known_high_impact_event: bool
    data_quality_pct: float
    plan_followed: bool
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class DuringTradeEvent:
    event_time: datetime
    label: str
    impact: str
    known_before_entry: bool = False


@dataclass(frozen=True)
class TradeOutcome:
    exit_time: datetime
    outcome: str
    net_r: float
    exit_reason: str
    slippage_r: float = 0.0
    cost_r: float = 0.0


def validate_point_in_time(snapshot: DecisionSnapshot) -> None:
    captured = _utc(snapshot.captured_at)
    entry = _utc(snapshot.entry_time)
    if captured > entry:
        raise ValueError(
            "snapshot pré-trade foi capturado depois da entrada; diagnóstico inicial teria look-ahead"
        )
    if int(snapshot.macro_alignment) not in {-1, 0, 1}:
        raise ValueError("macro_alignment deve ser -1, 0 ou 1")
    quality = _finite("data_quality_pct", snapshot.data_quality_pct)
    if not 0 <= quality <= 100:
        raise ValueError("data_quality_pct deve estar entre 0 e 100")


def diagnose_trade(
    snapshot: DecisionSnapshot,
    outcome: TradeOutcome,
    events: Iterable[DuringTradeEvent] = (),
) -> dict[str, object]:
    validate_point_in_time(snapshot)
    entry = _utc(snapshot.entry_time)
    exit_time = _utc(outcome.exit_time)
    if exit_time < entry:
        raise ValueError("exit_time não pode anteceder entry_time")

    outcome_name = str(outcome.outcome or "").strip().upper()
    if outcome_name not in {"GAIN", "LOSS", "BREAKEVEN", "OPEN"}:
        raise ValueError("outcome inválido")

    factors_against: list[dict[str, object]] = []
    factors_supporting: list[dict[str, object]] = []
    unknowns: list[str] = []

    def against(code: str, detail: str, confidence: str) -> None:
        factors_against.append(
            {"code": code, "detail": detail, "confidence": confidence}
        )

    def support(code: str, detail: str, confidence: str) -> None:
        factors_supporting.append(
            {"code": code, "detail": detail, "confidence": confidence}
        )

    if snapshot.macro_alignment < 0:
        against("MACRO_CONFLICT", "o contexto macro capturado estava contra a direção da operação", "HIGH")
    elif snapshot.macro_alignment > 0:
        support("MACRO_ALIGNED", "o contexto macro capturado estava alinhado à direção da operação", "HIGH")
    else:
        unknowns.append("macro sem direção clara no snapshot")

    if snapshot.technical_confirmation:
        support("TECH_CONFIRMED", "houve confirmação técnica registrada antes da entrada", "HIGH")
    else:
        against("TECH_UNCONFIRMED", "a entrada ocorreu sem confirmação técnica registrada", "HIGH")

    if snapshot.liquidity_confirmation:
        support("LIQUIDITY_CONFIRMED", "a leitura de liquidez estava confirmada no snapshot", "MEDIUM")
    else:
        against("LIQUIDITY_UNCONFIRMED", "a leitura de liquidez não estava confirmada", "MEDIUM")

    if snapshot.regime_fit:
        support("REGIME_FIT", "o operacional estava compatível com o regime classificado", "MEDIUM")
    else:
        against("REGIME_MISMATCH", "o operacional estava fora do regime classificado", "HIGH")

    if snapshot.known_high_impact_event:
        against(
            "KNOWN_EVENT_RISK",
            "havia evento de alto impacto conhecido no momento da decisão",
            "HIGH",
        )

    quality = float(snapshot.data_quality_pct)
    if quality < 55:
        against("LOW_DATA_QUALITY", f"qualidade dos dados estava baixa ({quality:.0f}%)", "HIGH")
    elif quality >= 80:
        support("GOOD_DATA_QUALITY", f"qualidade dos dados estava alta ({quality:.0f}%)", "MEDIUM")
    else:
        unknowns.append(f"qualidade dos dados intermediária ({quality:.0f}%)")

    if snapshot.plan_followed:
        support("PLAN_FOLLOWED", "a execução registrada seguiu o plano", "HIGH")
    else:
        against("PLAN_DEVIATION", "houve desvio do plano operacional", "HIGH")

    event_rows: list[dict[str, object]] = []
    for raw in events:
        event_time = _utc(raw.event_time)
        if event_time > exit_time:
            # Future information must not influence this trade diagnosis.
            continue
        if event_time < entry and not raw.known_before_entry:
            # A pre-entry event not known/captured cannot be retroactively treated
            # as something the model should have known.
            classification = "UNCAPTURED_PRE_ENTRY_CONTEXT"
        elif entry <= event_time <= exit_time:
            classification = "DURING_TRADE_EVENT"
        else:
            classification = "KNOWN_PRE_ENTRY_EVENT"
        row = {
            **asdict(raw),
            "event_time": event_time.isoformat(),
            "classification": classification,
        }
        event_rows.append(row)
        if classification == "DURING_TRADE_EVENT" and str(raw.impact).upper() in {"HIGH", "ALTO", "MAXIMUM", "MÁXIMO"}:
            against(
                "HIGH_IMPACT_DURING_TRADE",
                f"evento de alto impacto ocorreu durante a operação: {raw.label}",
                "MEDIUM",
            )
        elif classification == "KNOWN_PRE_ENTRY_EVENT" and str(raw.impact).upper() in {"HIGH", "ALTO", "MAXIMUM", "MÁXIMO"}:
            against(
                "KNOWN_EVENT_TIMING",
                f"evento de alto impacto já era conhecido antes da entrada: {raw.label}",
                "HIGH",
            )

    slippage = _finite("slippage_r", outcome.slippage_r)
    costs = _finite("cost_r", outcome.cost_r)
    net_r = _finite("net_r", outcome.net_r)
    if slippage > 0.10:
        against("SLIPPAGE", f"slippage consumiu {slippage:.2f}R", "HIGH")
    if costs > 0.10:
        against("COSTS", f"custos consumiram {costs:.2f}R", "HIGH")

    high_quality = (
        snapshot.macro_alignment >= 0
        and snapshot.technical_confirmation
        and snapshot.liquidity_confirmation
        and snapshot.regime_fit
        and not snapshot.known_high_impact_event
        and quality >= 70
        and snapshot.plan_followed
    )
    low_quality = (
        snapshot.macro_alignment < 0
        or not snapshot.technical_confirmation
        or not snapshot.regime_fit
        or quality < 55
        or not snapshot.plan_followed
    )

    if outcome_name == "GAIN" and low_quality:
        decision_outcome_relation = "GAIN_WITH_WEAK_DECISION_QUALITY"
    elif outcome_name == "LOSS" and high_quality:
        decision_outcome_relation = "LOSS_DESPITE_COHERENT_DECISION"
    elif outcome_name == "GAIN" and high_quality:
        decision_outcome_relation = "GAIN_WITH_COHERENT_DECISION"
    elif outcome_name == "LOSS" and low_quality:
        decision_outcome_relation = "LOSS_WITH_IDENTIFIED_DECISION_WEAKNESSES"
    else:
        decision_outcome_relation = "MIXED_OR_INCOMPLETE"

    # "Probable" deliberately avoids pretending that OHLC/backtest evidence proves causality.
    if factors_against:
        probable = [dict(x) for x in factors_against[:5]]
    else:
        probable = [{
            "code": "NO_DOMINANT_CAUSE",
            "detail": "não há causa dominante comprovável nos dados fornecidos",
            "confidence": "LOW",
        }]

    return {
        "schema": SCHEMA,
        "trade_id": snapshot.trade_id,
        "outcome": outcome_name,
        "net_r": net_r,
        "decision_outcome_relation": decision_outcome_relation,
        "decision_snapshot": {
            **asdict(snapshot),
            "captured_at": _utc(snapshot.captured_at).isoformat(),
            "entry_time": entry.isoformat(),
        },
        "trade_outcome": {
            **asdict(outcome),
            "exit_time": exit_time.isoformat(),
        },
        "supporting_factors": factors_supporting,
        "risk_or_failure_factors": factors_against,
        "probable_explanations": probable,
        "during_trade_events": event_rows,
        "unknowns": unknowns,
        "lookahead_used": False,
        "causality_claimed": False,
        "automatic_strategy_change": False,
        "interpretation": (
            "O diagnóstico organiza evidências disponíveis e fatores prováveis. "
            "Ele não prova causalidade e não deve usar informação futura para julgar a decisão inicial."
        ),
    }


__all__ = [
    "SCHEMA",
    "DecisionSnapshot",
    "DuringTradeEvent",
    "TradeOutcome",
    "validate_point_in_time",
    "diagnose_trade",
]
