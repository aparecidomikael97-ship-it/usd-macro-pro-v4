"""LAB: multi-horizon FX relative-strength bias read model (NO MARKET FORECAST).

Reuses the canonical G8/28-pair algebra from atlasquant_fx_universe.
The supplied 0..100 scores are synthetic until separately sourced, validated,
calibrated and tested OOS. NEVER fetches data, places orders, publishes,
or authorizes a trade; a ranking score is not an accuracy probability.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from math import isfinite
from typing import Any, Mapping

from atlasquant_fx_universe import (
    CURRENCIES, OFFICIAL_PAIRS, evaluate_pair,
)

SCHEMA = "ATLASQUANT_TRADER_BIAS_HORIZONS_LAB_V1"
HORIZONS = ("D1", "W1", "MN1")
MAX_AGE_SECONDS = {"D1": 36 * 3600, "W1": 10 * 86400, "MN1": 45 * 86400}
NEUTRAL_BAND_LAB = 5.0  # experimental, not calibrated


def _stamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or len(value) > 60:
        return None
    try:
        dt = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except (ValueError, OverflowError):
        return None
    return dt.astimezone(timezone.utc) if dt.tzinfo is not None else None


def _snapshot(raw: Any, *, horizon: str, now: datetime) -> dict[str, Any]:
    unavailable = {"state": "INDISPONIVEL", "reason": "Sem evidência sintética completa e datada.",
                   "as_of": None, "scores": None, "ranking": []}
    if not isinstance(raw, Mapping) or raw.get("state") != "LAB_SYNTHETIC":
        return unavailable
    if raw.get("data_kind") != "RELATIVE_STRENGTH_INDEX":
        return {**unavailable, "reason": "Variação de preço não equivale a índice de força relativa."}
    source = raw.get("source")
    method = raw.get("method_id")
    if (not isinstance(source, str) or not 2 <= len(source.strip()) <= 160 or
            not isinstance(method, str) or not 2 <= len(method.strip()) <= 100):
        return {**unavailable, "reason": "Fonte ou método sem identificação."}
    moment = _stamp(raw.get("as_of"))
    if moment is None:
        return {**unavailable, "reason": "Horário precisa de fuso explícito."}
    age = (now - moment).total_seconds()
    if age < -60 or age > MAX_AGE_SECONDS[horizon]:
        return {**unavailable, "reason": "Evidência futura ou fora do prazo conservador."}
    try:
        period_end = date.fromisoformat(raw["period_end"])
    except (KeyError, ValueError, TypeError):
        return {**unavailable, "reason": "Período de observação inválido."}
    if period_end > moment.date() or period_end > now.date():
        return {**unavailable, "reason": "Período econômico posterior à leitura."}
    values = raw.get("strengths")
    if not isinstance(values, Mapping) or set(values) != set(CURRENCIES):
        return {**unavailable, "reason": "Força precisa cobrir exatamente oito moedas."}
    scores = {}
    for key in CURRENCIES:
        value = values[key]
        if isinstance(value, bool) or not isinstance(value, (float, int)):
            return {**unavailable, "reason": "Pontuação não numérica ou booleana."}
        if not isfinite(value) or not 0 <= value <= 100:
            return {**unavailable, "reason": "Pontuação fora de 0 a 100 ou não finita."}
        scores[key] = float(value)
    order = sorted(CURRENCIES, key=lambda code: (-scores[code], code))
    return {"state": "LAB_PRONTO", "reason": "Pontuações sintéticas, sem comprovação real.",
            "as_of": moment.isoformat(), "period_end": period_end.isoformat(),
            "source": source.strip(), "method_id": method.strip(),
            "scores": scores, "ranking": order, "strongest": order[0], "weakest": order[-1]}


def build_bias_horizons_lab(
    snapshots: Mapping[str, Any] | None, *, at: datetime,
) -> dict[str, Any]:
    """Build exactly 28 explainable directional *hypotheses*, never trades.

    Daily is primary; weekly is confirmation; monthly is context, NOT a veto
    or a blended coefficient. Monthly absence doesn't invent a neutral reading.
    """
    if not isinstance(at, datetime) or at.tzinfo is None:
        raise ValueError("Instante de avaliação precisa de fuso horário")
    now = at.astimezone(timezone.utc)
    data = snapshots if isinstance(snapshots, Mapping) else {}
    periods = {h: _snapshot(data.get(h), horizon=h, now=now) for h in HORIZONS}
    daily = periods["D1"]
    # Comparing differently calculated strength indices is unsafe.
    if daily["state"] == "LAB_PRONTO":
        for horizon in ("W1", "MN1"):
            p = periods[horizon]
            if p["state"] == "LAB_PRONTO" and p["method_id"] != daily["method_id"]:
                periods[horizon] = {"state": "INDISPONIVEL",
                                    "reason": "Método de força diferente do diário.",
                                    "as_of": None, "scores": None, "ranking": []}

    rows = []
    for pair in OFFICIAL_PAIRS:
        by_horizon = {}
        for h in HORIZONS:
            p = periods[h]
            if p["state"] != "LAB_PRONTO":
                by_horizon[h] = {"bias": "AGUARDAR", "differential": None,
                                 "ranking_intensity": None}
                continue
            view = evaluate_pair(pair, p["scores"], neutral_band=NEUTRAL_BAND_LAB)
            by_horizon[h] = {
                "bias": {"BUY": "ALTA", "SELL": "BAIXA", "NEUTRAL": "NEUTRO"}[view.side],
                "differential": view.differential,
                "ranking_intensity": view.directional_score,
                "base_score": view.base_strength, "quote_score": view.quote_strength,
            }
        d, w, m = (by_horizon[h]["bias"] for h in HORIZONS)
        if d == "AGUARDAR":
            state, why = "SEM_VIES_DIARIO", "Dados diários ausentes, velhos ou inválidos."
        elif d == "NEUTRO":
            state, why = "NEUTRO", "Diferença diária abaixo da faixa experimental."
        elif w == "AGUARDAR":
            state, why = "SEM_CONFIRMACAO_SEMANAL", "Sem confirmação semanal comparável."
        elif w != d:
            state, why = "CONFLITO_SEMANAL", "Leitura semanal não confirma o viés diário."
        elif m in ("ALTA", "BAIXA") and m != d:
            state, why = "DIARIO_SEMANAL_ALINHADOS_MENSAL_CONTRA", "Mês aponta contexto contrário."
        elif m == d:
            state, why = "TRES_HORIZONTES_ALINHADOS", "Três horizontes concordam no laboratório."
        else:
            state, why = "DIARIO_SEMANAL_ALINHADOS", "Mensal neutro ou indisponível."
        eligible = state in {"TRES_HORIZONTES_ALINHADOS", "DIARIO_SEMANAL_ALINHADOS",
                             "DIARIO_SEMANAL_ALINHADOS_MENSAL_CONTRA"}
        rows.append({"pair": pair, "daily_bias": d, "weekly_bias": w, "monthly_bias": m,
                     "horizons": by_horizon, "state": state, "why": why,
                     "observational_candidate": eligible, "entry_signal": False,
                     "trade_authorized": False})
    candidates = [row for row in rows if row["observational_candidate"]]
    # Stable ranking only among daily+weekly aligned synthetic observations;
    # month agreement is context, not an untested weighted advantage.
    candidates.sort(key=lambda row: (-row["horizons"]["D1"]["ranking_intensity"], row["pair"]))
    return {"schema": SCHEMA, "state": "LAB_SIMULACAO_NAO_HOMOLOGADA",
            "at_utc": now.isoformat(), "periods": periods, "pair_count": len(rows),
            "rows": rows, "top10_observation_only": [r["pair"] for r in candidates[:10]],
            "neutral_band_lab": NEUTRAL_BAND_LAB,
            "relative_strength_is_spot_appreciation": False,
            "ranking_is_accuracy_probability": False, "backtested": False,
            "real_data_verified": False, "trade_authorized": False,
            "worker_enabled": False, "scheduler_enabled": False,
            "why_not": "Pontuações simuladas; método e limiares exigem fonte real, backtest OOS e revisão humana."}


__all__ = ["SCHEMA", "HORIZONS", "build_bias_horizons_lab"]
