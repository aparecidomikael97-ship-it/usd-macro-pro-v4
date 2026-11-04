"""Explain *observed* ECB reference changes without inventing their causes.

LAB only. No market-price feed, economic news retrieval, scheduling or trade bias.
Overlapping D1/W1/MN1 observations are not independent confirmations.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from atlasquant_fx_universe import CURRENCIES, OFFICIAL_PAIRS
from atlasquant_trader_ecb_three_horizon_matrix_lab import (
    HORIZONS, build_ecb_three_horizon_reference_matrix_lab,
)

SCHEMA = "ATLASQUANT_TRADER_ECB_HORIZON_CONTEXT_LAB_V1"
EVIDENCE_REQUIRED_PER_CURRENCY = (
    "POLITICA_MONETARIA_E_EXPECTATIVAS", "INFLACAO", "EMPREGO",
    "ATIVIDADE_E_MICROECONOMIA", "GEOPOLITICA", "NOTICIAS_VERIFICADAS",
    "CALENDARIO_ECONOMICO_E_REVISOES", "CONTRAPROVAS",
)
OUTCOME_MAP = {
    "BASE_OUTPERFORMED_IN_REFERENCE": "BASE_SUPEROU_NA_REFERENCIA",
    "QUOTE_OUTPERFORMED_IN_REFERENCE": "COTADA_SUPEROU_NA_REFERENCIA",
    "UNCHANGED_IN_REFERENCE": "SEM_DIFERENCA_NA_REFERENCIA",
}


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_BLOCKED", "reason": reason,
        "pair_count": 0, "pair_explanations": [],
        "currency_summaries": {}, "operational_bias": "AGUARDAR",
        "cause_of_strength_verified": False,
        "macro_micro_geo_news_calendar_attested": False,
        "source_original_bytes_authenticated": False,
        "independent_market_prices_verified": False,
        "overlapping_windows_are_independent_evidence": False,
        "can_feed_live_radar": False, "trade_authorized": False,
        "publishable": False, "scheduler_enabled": False,
        "worker_enabled": False, "external_http_requests": 0,
        "new_cost_brl": 0,
    }


def _relative_extremes(ranking: list[dict[str, Any]]) -> dict[str, Any]:
    """Respect ties: a sorted rank does not mean a uniquely strong currency."""
    if not ranking:
        return {"state": "SEM_HISTORICO", "mais_fortes": [], "mais_fracas": []}
    ordered = {r["currency"]: r["relative_log_change_percentage_points"]
               for r in ranking}
    high, low = max(ordered.values()), min(ordered.values())
    # ECB inputs undergo logarithmic arithmetic; near-ties after the
    # reference matrix's six-decimal rounding must be declared ties.
    tolerance = 0.000001
    strong = sorted(c for c, s in ordered.items() if high - s <= tolerance)
    weak = sorted(c for c, s in ordered.items() if s - low <= tolerance)
    return {
        "state": "EMPATE_DE_REFERENCIA" if len(strong) > 1 or len(weak) > 1
                 else "EXTREMOS_HISTORICOS_UNICOS",
        "mais_fortes": strong,
        "mais_fracas": weak,
        "referencia_log_pp_max": high,
        "referencia_log_pp_min": low,
        "nao_comprova_fundamento": True,
    }


def build_ecb_horizon_context_lab(xml_data: Any, *, at: datetime) -> dict[str, Any]:
    """Turn 28×3 ECB historical comparisons into honest context/readiness rows."""
    matrix = build_ecb_three_horizon_reference_matrix_lab(xml_data, at=at)
    if matrix.get("state") != "LAB_EXPOST_REFERENCE_MATRIX_ONLY":
        return _blocked("HISTORICO_BCE_RECUSADO_" + matrix.get("reason", "UNKNOWN"))
    if (matrix.get("pair_count") != 28 or matrix.get("currency_count") != 8
            or matrix.get("operational_bias") != "AGUARDAR"
            or matrix.get("trade_authorized") is not False):
        return _blocked("MATRIZ_BCE_INSEGURA")

    currency_summaries: dict[str, Any] = {}
    extremes = {}
    for frame in HORIZONS:
        ranking = matrix["currency_ranking_by_horizon"].get(frame, [])
        if ranking and {r["currency"] for r in ranking} != set(CURRENCIES):
            return _blocked("RANKING_INCOMPLETO")
        extremes[frame] = _relative_extremes(ranking)
    for currency in CURRENCIES:
        currency_summaries[currency] = {
            "currency": currency,
            "ranking_referencia": {
                frame: next((item["rank"] for item in
                             matrix["currency_ranking_by_horizon"][frame]
                             if item["currency"] == currency), None)
                for frame in HORIZONS
            },
            "evidencias_fundamentais_pendentes": list(EVIDENCE_REQUIRED_PER_CURRENCY),
            "porque_forte_ou_fraca": "NAO_DEMONSTRADO_PELO_BCE",
            "fundamentals_verified": False,
        }

    explanations = []
    seen = set()
    for row in matrix["pair_rows"]:
        pair = row["pair"]
        if pair not in OFFICIAL_PAIRS or pair in seen:
            return _blocked("PAR_DUPLICADO_OU_DESCONHECIDO")
        seen.add(pair)
        observations = {}
        sides = []
        for frame in HORIZONS:
            f = row["horizons"][frame]
            if f["research_state"] == "INSUFFICIENT_REFERENCE_HISTORY":
                side = "HISTORICO_INSUFICIENTE"
            else:
                side = OUTCOME_MAP.get(f["historical_reference_relation"])
                if side is None:
                    return _blocked("ROTULO_HISTORICO_DESCONHECIDO")
            sides.append(side)
            observations[frame] = {
                "relacao_passada": side,
                "variacao_referencia_pct": f["observed_reference_change_pct"],
                "de": f.get("start_reference_date"),
                "ate": f.get("end_reference_date"),
                "vies_operacional": "AGUARDAR",
            }
        if "HISTORICO_INSUFICIENTE" in sides:
            status = "HISTORICO_INCOMPLETO"
        elif len(set(sides)) == 1 and sides[0] != "SEM_DIFERENCA_NA_REFERENCIA":
            status = "MESMA_RELACAO_HISTORICA_3_JANELAS_SOBREPOSTAS"
        elif ("BASE_SUPEROU_NA_REFERENCIA" in sides
              and "COTADA_SUPEROU_NA_REFERENCIA" in sides):
            status = "DIVERGENCIA_HISTORICA_ENTRE_HORIZONTES"
        else:
            status = "REFERENCIA_HISTORICA_MISTA_OU_ESTAVEL"
        explanations.append({
            "pair": pair, "base": row["base"], "quote": row["quote"],
            "historico": observations,
            "comparacao_d1_w1_mn1": status,
            "janelas_sobrepostas_nao_sao_tres_confirmacoes": True,
            "porque_base_forte": "SEM_EVIDENCIA_CAUSAL_VERIFICADA",
            "porque_cotada_fraca": "SEM_EVIDENCIA_CAUSAL_VERIFICADA",
            "fundamentos_a_investigar_por_moeda": {
                row["base"]: list(EVIDENCE_REQUIRED_PER_CURRENCY),
                row["quote"]: list(EVIDENCE_REQUIRED_PER_CURRENCY),
            },
            "precisa_preco_de_mercado_independente": True,
            "vies_operacional": {frame: "AGUARDAR" for frame in HORIZONS},
            "trade_authorized": False,
        })
    if seen != set(OFFICIAL_PAIRS):
        return _blocked("FALTAM_PARES_FOREX")
    out = _blocked("BCE_APENAS_RELATO_HISTORICO_SEM_CAUSAS_VERIFICADAS")
    out.update({
        "state": "LAB_CONTEXT_EXPOST_ONLY",
        "reference_date": matrix["reference_date"],
        "reference_age_days": matrix["reference_age_days"],
        "reference_outdated_over_four_days": matrix["reference_age_over_four_days"],
        "comparison_horizons": list(HORIZONS),
        "period_MN1": "JANELA_MOVEL_30_DIAS_CORRIDOS",
        "pair_count": len(explanations), "pair_explanations": explanations,
        "currency_summaries": currency_summaries,
        "strongest_weakest_reference_only": extremes,
        "not_independent_quotes_count": 21,
        "reference_rate_is_not_executable_price": True,
        "why_not": ("O BCE descreve apenas mudanças anteriores de referência. "
                    "Para justificar força/fraqueza ou viés futuro, faltam fatos "
                    "macro e micro, notícias, calendário e geopolítica com "
                    "origem validada, contraprovas e preços independentes."),
    })
    return out


__all__ = ["SCHEMA", "build_ecb_horizon_context_lab", "EVIDENCE_REQUIRED_PER_CURRENCY"]
