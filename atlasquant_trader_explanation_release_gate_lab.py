"""Fail-closed explanation readiness for the 28-pair AtlasQuant Trader panel.

All evidence is caller-supplied, synthetic or documentary, not authenticated.
This module never calculates live currency strength, sends HTTP requests,
schedules three daily runs, publishes an operational bias or enables trading.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from atlasquant_fx_universe import CURRENCIES, OFFICIAL_PAIRS
from atlasquant_trader_macro_causal_dossier_lab import (
    HORIZONS, build_macro_causal_dossier_lab,
)
from atlasquant_trader_g8_context_completeness_3x_lab import (
    DIMENSIONS, audit_three_daily_g8_context_lab,
)

SCHEMA = "ATLASQUANT_TRADER_EXPLANATION_RELEASE_GATE_LAB_V1"


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_BLOCKED", "reason": reason,
        "cards": [], "pair_count": 0, "horizon_card_count": 0,
        "operational_bias": "AGUARDAR", "publishable": False,
        "strength_causation_proven": False,
        "real_time_news_verified": False, "real_time_calendar_verified": False,
        "three_daily_updates_verified": False,
        "source_originals_attested": False,
        "contrary_evidence_independently_reviewed": False,
        "relative_strength_independently_verified": False,
        "can_feed_live_radar": False, "trade_authorized": False,
        "scheduler_enabled": False, "worker_enabled": False,
        "external_http_requests": 0, "new_cost_brl": 0,
    }


def build_explanation_release_gate_lab(
    news_pair_context: Any,
    macro_receipts: Any,
    captures: Any,
    *, at: datetime,
) -> dict[str, Any]:
    """Regenerate safe upstream audits; expose *why* pair biases must wait.

    A documentary capture is not a verified collection, and a synthetic
    macro surprise is not proof of causation. Neither can open this gate.
    """
    if not isinstance(at, datetime) or at.tzinfo is None or at.utcoffset() is None:
        raise ValueError("Evaluation clock must be timezone-aware")
    now = at.astimezone(timezone.utc)
    macro = build_macro_causal_dossier_lab(news_pair_context, macro_receipts, at=now)
    if macro.get("state") != "LAB_CAUSAL_EVIDENCE_GAPS_ONLY":
        return _blocked("UNSAFE_MACRO_CAUSAL_EVIDENCE")
    coverage = audit_three_daily_g8_context_lab(captures, at=now)
    if coverage.get("state") != "LAB_COVERAGE_EXPLANATION_ONLY":
        return _blocked("UNSAFE_THREE_DAILY_DOCUMENTARY_COVERAGE")

    pair_coverage = {p["pair"]: p for p in coverage["pair_contexts"]}
    macro_pairs = {p["pair"]: p for p in macro["rows"]}
    if (set(pair_coverage) != set(OFFICIAL_PAIRS)
            or set(macro_pairs) != set(OFFICIAL_PAIRS)
            or set(coverage["currency_contexts"]) != set(CURRENCIES)):
        return _blocked("INCOMPLETE_EIGHT_CURRENCY_PAIR_MATRIX")

    cards = []
    for pair in OFFICIAL_PAIRS:
        old = macro_pairs[pair]
        gaps = pair_coverage[pair]
        base, quote = old["base"], old["quote"]
        frames = {}
        for horizon in HORIZONS:
            documentary = old["horizons"][horizon]
            missing = {c: list(gaps["missing_by_currency"][c]) for c in (base, quote)}
            aged = {c: list(gaps["older_checks_by_currency"][c]) for c in (base, quote)}
            blockers = []
            if coverage["claimed_capture_count"] == 0:
                blockers.append("NENHUMA_COLETA_DOCUMENTAL_FORNECIDA")
            if not coverage["claimed_three_captures_seen"]:
                blockers.append("TRES_COLETAS_DIARIAS_NAO_DEMONSTRADAS")
            # All paths are documentary: even 3 claimed captures lack a
            # trusted run receipt; never promote them to verified updates.
            blockers.append("EXECUCOES_DIARIAS_SEM_COMPROVANTE_INDEPENDENTE")
            for currency in (base, quote):
                if missing[currency]:
                    blockers.append(f"{currency}_DIMENSOES_AUSENTES")
                if aged[currency]:
                    blockers.append(f"{currency}_FONTES_COM_VERIFICACAO_ANTIGA")
            blockers.extend((
                "ORIGEM_DAS_FONTES_NAO_AUTENTICADA",
                "NOTICIAS_E_CALENDARIO_SEM_TEMPO_REAL_VERIFICADO",
                "CONSENSO_E_VALORES_MACRO_SEM_CUSTODIA",
                "REACAO_DE_MERCADO_A_DIVULGACOES_NAO_VERIFICADA",
                "CONTRAPROVAS_INDEPENDENTES_NAO_REVISADAS",
                "FORCA_CAMBIAL_INDEPENDENTE_NAO_CALIBRADA",
                "CAUSA_DE_FORCA_FRAQUEZA_NAO_COMPROVADA",
            ))
            frames[horizon] = {
                "bias": "AGUARDAR",
                "explanation_state": "NAO_PUBLICAVEL_COMO_FATO",
                "why_base_stronger_or_weaker": "NAO_COMPROVADO",
                "why_quote_stronger_or_weaker": "NAO_COMPROVADO",
                "missing_dimensions": missing,
                "older_than_48h_checks": aged,
                "blockers": blockers,
                "macro_synthetic_release_claim_count": len(documentary["macro_surprise_claims"]),
                "macro_synthetic_future_release_claim_count": len(documentary["future_releases_claimed"]),
                "synthetic_surprise_signs_mixed": documentary["mixed_above_below_consensus_claims"],
                "synthetic_surprises_not_currency_direction": True,
                "documentary_news_count": documentary["news_documentary_count"],
                "documentary_calendar_risk": documentary["calendar_risk_status_documentary"],
                "independent_counterevidence": "PENDENTE",
                "source_authenticity_verified": False,
                "macro_causation_verified": False,
                "real_time_calendar_verified": False,
                "real_time_news_verified": False,
                "can_show_as_verified_bias": False,
                "trade_authorized": False,
            }
        cards.append({"pair": pair, "base": base, "quote": quote,
                      "horizons": frames, "trade_authorized": False})

    report = _blocked("FONTES_CONTRAPROVAS_E_CAUSAS_PENDENTES")
    report.update({
        "state": "LAB_EXPLANATION_GATE_CLOSED",
        "as_of_utc": now.isoformat(),
        "date_brt": coverage["date_brt"],
        "cards": cards, "pair_count": len(cards),
        "horizon_card_count": len(cards) * len(HORIZONS),
        "currency_count": len(CURRENCIES),
        "required_context_dimensions": list(DIMENSIONS),
        "daily_documentary_captures_claimed": coverage["claimed_capture_count"],
        "three_documentary_slots_claimed": coverage["claimed_three_captures_seen"],
        "planned_slots": coverage["planned_slots"],
        "source_checks_are_documentary_only": True,
        "macro_releases_are_synthetic_only": True,
        "note": ("Porta fechada: dados fornecidos para pesquisa nao provam "
                 "noticias ao vivo, causa macro nem forca cambial. "
                 "Nenhum vies D1/W1/MN1 pode ser anunciado como real."),
    })
    return report


__all__ = ["SCHEMA", "build_explanation_release_gate_lab"]
