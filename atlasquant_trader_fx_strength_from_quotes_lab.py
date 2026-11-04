"""LAB-only G8 currency strength from synchronized 28-pair spot snapshots.

Pure deterministic arithmetic: complete graph log-returns -> centered currency
factors -> display-only relative strength. No live inputs, provider, credentials,
trades, paper execution, scheduler, runtime state, or calibrated accuracy.
"""
from __future__ import annotations

from datetime import datetime, timezone
from math import isfinite, log
from typing import Any, Mapping

from atlasquant_fx_universe import CURRENCIES, OFFICIAL_PAIRS, split_pair
from atlasquant_trader_bias_horizons_lab import HORIZONS, build_bias_horizons_lab

SCHEMA = "ATLASQUANT_FX_STRENGTH_FROM_QUOTES_LAB_V1"
METHOD = "G8_COMPLETE_GRAPH_CENTERED_LOG_RETURNS_LAB_V1"
# Display normalization by horizon, not backtested and not a probability.
# If a currency exceeds the uncalibrated range, refuse rather than saturate.
SCALE_BP_LAB = {"D1": 200.0, "W1": 700.0, "MN1": 1500.0}
WINDOW_DAYS = {"D1": (0.7, 4.0), "W1": (4.0, 10.0), "MN1": (18.0, 42.0)}
MAX_DISAGREEMENT_BP_LAB = 15.0
AGE_SECONDS = {"D1": 36 * 3600, "W1": 10 * 86400, "MN1": 45 * 86400}


def _time(raw: Any) -> datetime | None:
    if not isinstance(raw, str) or not 10 <= len(raw) <= 60:
        return None
    try:
        value = datetime.fromisoformat(raw.strip().replace("Z", "+00:00"))
    except (ValueError, OverflowError):
        return None
    return value.astimezone(timezone.utc) if value.tzinfo is not None else None


def _price(raw: Any) -> float | None:
    if isinstance(raw, bool) or not isinstance(raw, (float, int)):
        return None
    value = float(raw)
    return value if isfinite(value) and 0 < value <= 1e8 else None


def _fail(reason: str) -> dict[str, Any]:
    return {"state": "AGUARDAR", "reason": reason,
            "strength_snapshot": None, "raw_log_return_bp": {},
            "currency_log_return_bp": {}, "max_residual_bp": None}


def _compute_period(raw: Any, *, horizon: str, now: datetime) -> dict[str, Any]:
    if not isinstance(raw, Mapping) or raw.get("state") != "LAB_SYNTHETIC_SPOT":
        return _fail("Sem preços sintéticos explicitamente autorizados em LAB.")
    if raw.get("data_kind") != "SYNTHETIC_FX_SPOT_CLOSES":
        return _fail("Contrato de preço ou período incompatível.")
    source = raw.get("source")
    if not isinstance(source, str) or not 2 <= len(source.strip()) <= 160:
        return _fail("Fonte dos preços sem identificação.")
    observed = _time(raw.get("as_of"))
    if observed is None:
        return _fail("Horário de disponibilidade sem fuso explícito.")
    age = (now - observed).total_seconds()
    if age < 0 or age > AGE_SECONDS[horizon]:
        return _fail("Leitura futura ou antiga demais para o horizonte.")
    quotes = raw.get("pairs")
    if not isinstance(quotes, Mapping) or set(quotes) != set(OFFICIAL_PAIRS):
        return _fail("Cobertura incompleta ou extra: exigidos exatamente os 28 pares canônicos.")
    start_ref = None
    end_ref = None
    returns = {}
    for pair in OFFICIAL_PAIRS:
        quote = quotes[pair]
        if not isinstance(quote, Mapping) or quote.get("source") != source:
            return _fail("Fonte inconsistente entre pares.")
        start_at = _time(quote.get("start_at"))
        end_at = _time(quote.get("end_at"))
        start_price = _price(quote.get("start"))
        end_price = _price(quote.get("end"))
        if (start_at is None or end_at is None or
                start_price is None or end_price is None):
            return _fail("Cotação, horário ou formato de preço inválido.")
        if not start_at < end_at <= observed <= now:
            return _fail("Cotação futura ou ordem temporal impossível.")
        if start_ref is None:
            start_ref, end_ref = start_at, end_at
        elif (start_at, end_at) != (start_ref, end_ref):
            return _fail("Pares não sincronizados no início e no fechamento.")
        r = log(end_price) - log(start_price)
        if abs(r) > 0.5:
            return _fail("Retorno extremo fora do contrato LAB.")
        returns[pair] = r
    days = (end_ref - start_ref).total_seconds() / 86400
    lo, hi = WINDOW_DAYS[horizon]
    if days < lo or days > hi:
        return _fail("Janela temporal incompatível com o horizonte.")
    if raw.get("period_end") != end_ref.date().isoformat():
        return _fail("Período declarado não corresponde ao fechamento UTC.")
    # Complete directed graph K8. In the least-squares solution centered at
    # zero, x_i = (sum_j signed log(P_ij,end / P_ij,start)) / 8.
    factors = {currency: 0.0 for currency in CURRENCIES}
    for pair, delta in returns.items():
        base, quote = split_pair(pair)
        factors[base] += delta
        factors[quote] -= delta
    n = len(CURRENCIES)
    factors = {key: value / n for key, value in factors.items()}
    residual = max(abs(delta - (factors[split_pair(pair)[0]] -
                                 factors[split_pair(pair)[1]]))
                   for pair, delta in returns.items()) * 10000
    if residual > MAX_DISAGREEMENT_BP_LAB:
        return _fail("Retornos triangulares incompatíveis; possível defasagem, fonte ou dado incorreto.")
    unit = SCALE_BP_LAB[horizon]
    factors_bp = {key: factors[key] * 10000 for key in CURRENCIES}
    if any(abs(value) > unit for value in factors_bp.values()):
        return _fail("Escala LAB insuficiente; não truncar forças nem forçar direção.")
    display = {key: round(50 + value * 50 / unit, 6)
               for key, value in factors_bp.items()}
    snap = {"state": "LAB_SYNTHETIC", "data_kind": "RELATIVE_STRENGTH_INDEX",
            "source": source, "method_id": METHOD,
            "as_of": observed.isoformat(), "period_end": end_ref.date().isoformat(),
            "strengths": display}
    return {"state": "LAB_COMPUTED", "reason": "Fatores relativos sintéticos consistentes.",
            "strength_snapshot": snap,
            "currency_log_return_bp": {k: round(v, 5) for k, v in factors_bp.items()},
            "raw_log_return_bp": {k: round(v * 10000, 5) for k, v in returns.items()},
            "max_residual_bp": round(residual, 7),
            "start_utc": start_ref.isoformat(), "end_utc": end_ref.isoformat(),
            "score_scale_bp_lab": unit,
            "scaling_calibrated": False, "source_verified": False}


def build_fx_strength_from_quotes_lab(
    books: Mapping[str, Any] | None, *, at: datetime,
) -> dict[str, Any]:
    """Make three synthetic snapshots and pass them to the existing bias matrix."""
    if not isinstance(at, datetime) or at.tzinfo is None:
        raise ValueError("O instante da avaliação precisa ter fuso horário.")
    now = at.astimezone(timezone.utc)
    source = books if isinstance(books, Mapping) else {}
    diagnostics = {h: _compute_period(source.get(h), horizon=h, now=now)
                   for h in HORIZONS}
    strengths = {h: info["strength_snapshot"] for h, info in diagnostics.items()
                 if info["state"] == "LAB_COMPUTED"}
    matrix = build_bias_horizons_lab(strengths, at=now)
    return {"schema": SCHEMA, "state": "LAB_SIMULACAO_NAO_HOMOLOGADA",
            "diagnostics": diagnostics, "bias_matrix": matrix,
            "real_quotes_verified": False, "backtested": False,
            "accuracy_probability": None, "macro_confirmed": False,
            "trade_authorized": False, "scheduler_enabled": False,
            "worker_enabled": False,
            "why_not": "Método, fontes e limiares sintéticos: exigem dados reais "
                       "auditáveis, validação ponto-no-tempo, OOS e revisão humana."}


__all__ = ["SCHEMA", "METHOD", "build_fx_strength_from_quotes_lab"]
