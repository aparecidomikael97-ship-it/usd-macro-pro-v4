"""AtlasQuant Trader — news/position thesis review in isolated LAB.

Joins the existing economic-surprise classifier to the position/event manager.
This is a *conditional documentary audit*, not a market-reaction model.
No broker IO, live radar promotion, probability of profit, or trade commands.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Optional

from atlasquant_news_nowcast import classify_surprise
from atlasquant_position_event_manager import (
    EFFECTS,
    EventContext,
    PositionContext,
    assess_post_event,
    currency_exposure,
)

SCHEMA = "ATLASQUANT_POSITION_NEWS_THESIS_AUDIT_LAB_V1"
G8 = frozenset({"USD", "EUR", "GBP", "JPY", "CHF", "CAD", "AUD", "NZD"})


@dataclass(frozen=True)
class NewsReleaseEvidence:
    """Documentary snapshot; reviewed flags are NOT independent attestations."""

    event_id: str
    indicator: str
    currency: str
    reference_period: str
    unit: str
    previous: Optional[float]
    consensus: Optional[float]
    actual: Optional[float]
    tolerance: float
    scheduled_at: datetime
    consensus_captured_at: Optional[datetime]
    published_at: Optional[datetime]
    captured_at: Optional[datetime]
    source_release_url: str
    source_consensus_url: str
    release_document_reviewed: bool = False
    consensus_vintage_reviewed: bool = False
    revisions_reviewed: bool = False
    economic_context_reviewed: bool = False
    currency_effect_reviewed: bool = False
    currency_effect_hypothesis: str = "UNCERTAIN"


def _utc(value: datetime, field: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field} precisa de timezone explícito")
    return value.astimezone(timezone.utc)


def _number(value: object, field: str) -> Decimal:
    if value is None or isinstance(value, bool):
        raise ValueError(f"{field} ausente ou inválido")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError(f"{field} ausente ou inválido") from exc
    if not result.is_finite():
        raise ValueError(f"{field} não finito")
    return result


def _position_valid(position: PositionContext) -> None:
    base = position.base_currency.upper()
    quote = position.quote_currency.upper()
    if base not in G8 or quote not in G8 or base == quote:
        raise ValueError("moedas do par fora do universo G8")
    if position.pair.upper() != base + quote:
        raise ValueError("par inconsistente com moeda base/cotada")
    if position.side.upper() not in {"LONG", "SHORT"}:
        raise ValueError("lado deve ser LONG ou SHORT")


def audit_news_for_open_position(
    position: PositionContext,
    event: EventContext,
    release: NewsReleaseEvidence,
    *,
    as_of: datetime,
) -> dict[str, object]:
    """Classify documented surprise and *conditional* thesis alignment.

    Positive economic surprise, a stronger currency, price moving in the
    predicted direction, and a justified hold decision are FOUR different
    claims. This function never automatically infers one from another.
    """
    instant = _utc(as_of, "as_of")
    _position_valid(position)
    if not release.event_id.strip() or not release.indicator.strip():
        raise ValueError("evento e indicador são obrigatórios")
    if release.currency.upper() != event.currency.upper():
        raise ValueError("moeda do release não corresponde ao evento")
    if release.currency.upper() not in G8:
        raise ValueError("moeda não suportada")
    if release.currency_effect_hypothesis.upper() not in EFFECTS:
        raise ValueError("efeito macro inválido")
    if not release.reference_period.strip() or not release.unit.strip():
        raise ValueError("período e unidade são obrigatórios")
    _utc(release.scheduled_at, "scheduled_at")
    exposure = currency_exposure(position, event.currency)
    # An unrelated event does not affect the direct currency pair by itself.
    if exposure == 0:
        return {
            "schema": SCHEMA,
            "pair": position.pair.upper(),
            "state": "EVENTO_NAO_DIRETAMENTE_RELACIONADO",
            "relative_exposure": 0,
            "economic_surprise_class": None,
            "conditional_thesis": "NOT_RELEVANT",
            "management_review": "SEM_ACAO_AUTOMATICA",
            "market_reaction_probability": None,
            "probability_of_move_against_position": None,
            "broker_command": None,
            "can_feed_live_radar": False,
            "trade_authorized": False,
        }

    blockers: list[str] = []
    scheduled = _utc(release.scheduled_at, "scheduled_at")
    if release.consensus_captured_at is None:
        blockers.append("CONSENSO_PRE_EVENTO_AUSENTE")
    else:
        consensus_at = _utc(release.consensus_captured_at, "consensus_captured_at")
        if consensus_at >= scheduled:
            blockers.append("CONSENSO_SEM_VINTAGE_PRE_RELEASE")
    if release.published_at is None or release.captured_at is None:
        blockers.append("DIVULGACAO_OU_CAPTURA_AUSENTE")
    else:
        published = _utc(release.published_at, "published_at")
        captured = _utc(release.captured_at, "captured_at")
        if not (scheduled <= published <= captured <= instant):
            blockers.append("ORDEM_TEMPORAL_OU_LOOKAHEAD_INVALIDO")

    if not release.source_release_url.startswith("https://"):
        blockers.append("FONTE_DIVULGACAO_NAO_DOCUMENTADA")
    if not release.source_consensus_url.startswith("https://"):
        blockers.append("FONTE_CONSENSO_NAO_DOCUMENTADA")
    required_reviews = {
        "RELEASE_NAO_REVISADO": release.release_document_reviewed,
        "VINTAGE_CONSENSO_NAO_REVISADA": release.consensus_vintage_reviewed,
        "REVISOES_NAO_REVISADAS": release.revisions_reviewed,
        "CONTEXTO_MACRO_NAO_REVISADO": release.economic_context_reviewed,
        "HIPOTESE_EFEITO_NAO_REVISADA": release.currency_effect_reviewed,
    }
    blockers.extend(code for code, ok in required_reviews.items() if not ok)

    try:
        previous = _number(release.previous, "previous")
        consensus = _number(release.consensus, "consensus")
        actual = _number(release.actual, "actual")
        tolerance = _number(release.tolerance, "tolerance")
        if tolerance < 0:
            raise ValueError("tolerance negativa")
    except ValueError:
        blockers.append("NUMEROS_INCOMPLETOS_OU_INVALIDOS")
        previous = consensus = actual = tolerance = None
    if release.currency_effect_hypothesis.upper() == "UNCERTAIN":
        blockers.append("DIRECAO_ECONOMICA_INDETERMINADA")

    surprise = (
        classify_surprise(actual, consensus, tolerance)
        if all(x is not None for x in (consensus, actual, tolerance)) else None
    )
    # Checking source URLs and user-supplied review flags is NOT a separate
    # trusted witness. Even a fully documented hypothesis is not a trade edge.
    conditional_thesis = "REASSESS"
    management_review = "AGUARDAR_DADOS_E_REVISAO"
    if not blockers:
        conditional = assess_post_event(
            position, event,
            realized_currency_effect=release.currency_effect_hypothesis,
        )
        conditional_thesis = str(conditional["thesis_state"])
        if conditional_thesis == "EVENT_ALIGNED_WITH_POSITION":
            management_review = "REAVALIAR_MANUTENCAO_COM_RISCO"
        elif conditional_thesis == "EVENT_CONFLICTS_WITH_POSITION":
            management_review = "REAVALIAR_SAIDA_STOP_E_TESE"
        else:
            management_review = "REAVALIAR_TESE_SEM_DIRECAO"

    return {
        "schema": SCHEMA,
        "pair": position.pair.upper(),
        "position_side": position.side.upper(),
        "event_id": release.event_id,
        "indicator": release.indicator,
        "reference_period": release.reference_period,
        "currency": release.currency.upper(),
        "as_of_utc": instant.isoformat(),
        "state": ("HIPOTESE_DOCUMENTAL_PARA_REVISAO" if not blockers
                  else "AGUARDAR_EVIDENCIA"),
        "relative_exposure": exposure,
        "previous": str(previous) if previous is not None else None,
        "consensus": str(consensus) if consensus is not None else None,
        "actual": str(actual) if actual is not None else None,
        "economic_surprise_class": surprise,
        "surprise_vs_consensus": str(actual - consensus)
        if actual is not None and consensus is not None else None,
        "macro_effect_hypothesis": release.currency_effect_hypothesis.upper(),
        "conditional_thesis": conditional_thesis,
        "management_review": management_review,
        "blockers": blockers,
        "source_review_flags_are_independent_attestation": False,
        "historic_market_reaction_backtest_verified": False,
        "market_reaction_probability": None,
        "probability_of_move_against_position": None,
        "broker_command": None,
        "automatic_hold_or_exit": False,
        "can_feed_live_radar": False,
        "trade_authorized": False,
        "interpretation": (
            "Surpresa = atual - consenso, NÃO preço futuro. A hipótese de efeito "
            "da moeda depende de interpretação externa do contexto. Revisões, "
            "preço já precificado, volatilidade, spread, stop e reação real "
            "podem contradizer a hipótese; só revisão humana, sem ordens."
        ),
    }


__all__ = ["NewsReleaseEvidence", "audit_news_for_open_position", "SCHEMA"]
