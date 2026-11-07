"""AtlasQuant Trader selective FX bias policy: research LAB only.

Score labels are presentation categories, not probabilities. Every assertion
about sources, OOS validation and risk comes from the caller: even a perfect
claim remains a LAB candidate. No trading, live Radar or notification actions.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from atlasquant_fx_universe import OFFICIAL_PAIRS

SCHEMA = "ATLASQUANT_SELECTIVE_FX_BIAS_GATE_LAB_V1"
VALID_HORIZONS = {"D1", "W1"}
VALID_DIRECTIONS = {"ALTA", "BAIXA", "NEUTRO", "AGUARDAR"}
VALID_REGIMES = {"TENDENCIA", "LATERAL", "TRANSICAO", "CHOQUE", "VOLATILIDADE_ALTA", "INDETERMINADO"}
CATEGORIES = {6: "MODERADO", 7: "FORTE", 8: "ALTO", 9: "EXTRA", 10: "EXTRA"}
COVERAGE_STATES = {"DOCUMENTADO_IMPACTO", "DOCUMENTADO_NEUTRO", "INDETERMINADO"}
COOLDOWNS = {"D1": timedelta(days=1), "W1": timedelta(days=7)}


@dataclass(frozen=True)
class BiasReview:
    pair: str
    horizon: str
    direction: str
    score_0_to_10: Optional[int]
    scored_at_utc: datetime
    macro_bilateral_evidence_verified: bool
    source_vintages_verified: bool
    market_regime: str
    market_regime_verified: bool
    microeconomics_status: str
    geopolitics_status: str
    model_oos_calibration_verified: bool
    model_beats_baseline_oos: bool
    forward_paper_validation_verified: bool
    independence_risk_reviewed: bool
    price_reaction_labels_verified: bool
    has_future_leakage: bool = False
    last_displayed_at_utc: Optional[datetime] = None
    frozen_model_version: str = ""


def _utc(value: datetime, label: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{label}: fuso horário obrigatório")
    return value.astimezone(timezone.utc)


def _score(score: Optional[int]) -> Optional[int]:
    if score is None:
        return None
    if type(score) is not int or score < 0 or score > 10:
        raise ValueError("score_0_to_10 deve ser inteiro 0..10 ou ausente")
    return score


def audit_selective_bias_lab(candidate: BiasReview, *, as_of_utc: datetime) -> dict[str, object]:
    """Review an externally produced, *untrusted* score; never issue a signal.

    Never turn a supplied 'validated' flag into independent certification.
    The gate reports whether a hypothetical display policy would pass, pending
    independent evidence, approval and production integration.
    """
    now = _utc(as_of_utc, "as_of_utc")
    scored = _utc(candidate.scored_at_utc, "scored_at_utc")
    if candidate.pair not in OFFICIAL_PAIRS:
        raise ValueError("par fora dos 28 cruzamentos G8")
    if candidate.horizon not in VALID_HORIZONS:
        raise ValueError("horizonte fora de D1/W1")
    if candidate.direction not in VALID_DIRECTIONS:
        raise ValueError("direção desconhecida")
    if candidate.market_regime not in VALID_REGIMES:
        raise ValueError("regime desconhecido")
    if candidate.microeconomics_status not in COVERAGE_STATES:
        raise ValueError("microeconomia sem estado verificável")
    if candidate.geopolitics_status not in COVERAGE_STATES:
        raise ValueError("geopolítica sem estado verificável")
    score = _score(candidate.score_0_to_10)
    if candidate.frozen_model_version and len(candidate.frozen_model_version.strip()) > 64:
        raise ValueError("identidade do modelo inválida")

    blockers: list[str] = []
    if scored > now:
        blockers.append("PREVISAO_FUTURA")
    if candidate.has_future_leakage:
        blockers.append("VAZAMENTO_TEMPORAL")
    if score is None:
        blockers.append("NOTA_AUSENTE")
    elif score < 6:
        blockers.append("ABAIXO_DO_LIMIAR_SELETIVO")
    if candidate.direction not in {"ALTA", "BAIXA"}:
        blockers.append("SEM_DIRECAO_CANDIDATA")
    if not candidate.macro_bilateral_evidence_verified:
        blockers.append("MACRO_DAS_DUAS_MOEDAS_SEM_PROVA")
    if not candidate.source_vintages_verified:
        blockers.append("FONTES_E_VINTAGES_NAO_ATESTADOS")
    if not candidate.market_regime_verified or candidate.market_regime == "INDETERMINADO":
        blockers.append("REGIME_NAO_VALIDADO")
    if candidate.microeconomics_status == "INDETERMINADO":
        blockers.append("MICROECONOMIA_SEM_CONTEXTO")
    if candidate.geopolitics_status == "INDETERMINADO":
        blockers.append("GEOPOLITICA_SEM_CONTEXTO")
    if not candidate.model_oos_calibration_verified:
        blockers.append("PROBABILIDADES_NAO_CALIBRADAS_OOS")
    if not candidate.model_beats_baseline_oos:
        blockers.append("SEM_VANTAGEM_OOS_SOBRE_BASELINE")
    if not candidate.forward_paper_validation_verified:
        blockers.append("VALIDACAO_PROSPECTIVA_PENDENTE")
    if not candidate.independence_risk_reviewed:
        blockers.append("RISCO_INDEPENDENTE_PENDENTE")
    if not candidate.price_reaction_labels_verified:
        blockers.append("REAÇÃO_PREÇO_NAO_VERIFICADA")
    if not candidate.frozen_model_version.strip():
        blockers.append("VERSAO_MODELO_NAO_CONGELADA")

    if candidate.last_displayed_at_utc is not None:
        previous = _utc(candidate.last_displayed_at_utc, "last_displayed_at_utc")
        if previous > now:
            blockers.append("ULTIMA_EXIBICAO_FUTURA")
        elif now - previous < COOLDOWNS[candidate.horizon]:
            blockers.append("JANELA_REPETICAO_DO_MESMO_VIES")

    hypothetical_review_ready = not blockers
    return {
        "schema": SCHEMA,
        "pair": candidate.pair,
        "horizon": candidate.horizon,
        "direction_for_research": candidate.direction,
        "score_0_to_10": score,
        "score_label": CATEGORIES.get(score) if score is not None else None,
        "is_probability": False,
        "directional_accuracy_pct": None,
        "probability_of_profit_pct": None,
        "macro_includes_two_currencies": candidate.macro_bilateral_evidence_verified,
        "microeconomics_context": candidate.microeconomics_status,
        "geopolitics_context": candidate.geopolitics_status,
        "market_regime": candidate.market_regime,
        "model_version_claim": candidate.frozen_model_version,
        "hypothetical_policy_ready_for_human_review": hypothetical_review_ready,
        "state": "CANDIDATO_LAB_REVISÃO_HUMANA" if hypothetical_review_ready else "AGUARDAR",
        "blockers": blockers,
        "flags_are_independent_attestation": False,
        "real_historical_accuracy_verified": False,
        "can_feed_live_radar": False,
        "automatic_alert_enabled": False,
        "automatic_hold_or_exit": False,
        "trade_authorized": False,
        "broker_command": None,
        "new_cost_brl": 0,
    }


__all__ = ["SCHEMA", "BiasReview", "audit_selective_bias_lab"]
