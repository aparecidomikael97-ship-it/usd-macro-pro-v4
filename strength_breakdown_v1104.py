"""USD Macro Pro V11.0.4 — detalhamento dos pontos de força por moeda/par.

The pair total is exact from Pontuação_Final. Component rows explain where
the macro-strength gap comes from. These are internal model points, not pips
and not a probability of profit.
"""
from __future__ import annotations

from typing import Any, Mapping
import math
import pandas as pd

DEFAULT_WEIGHTS = {
    "juros": 0.20,
    "inflacao": 0.15,
    "pib": 0.15,
    "emprego": 0.20,
    "atividade": 0.20,
    "sentimento": 0.10,
}

FACTOR_META = (
    ("Juros / Treasury", "n_juros", "juros"),
    ("Inflação", "n_inflacao", "inflacao"),
    ("PIB", "n_pib", "pib"),
    ("Emprego", "n_emprego", "emprego"),
    ("Atividade", "n_atividade", "atividade"),
    ("Sentimento", "n_sentimento", "sentimento"),
)


def _num(v: Any, default: float = 0.0) -> float:
    try:
        x = float(v)
        return x if math.isfinite(x) else float(default)
    except Exception:
        return float(default)


def _currency_row(ranking: pd.DataFrame, code: str) -> dict[str, Any]:
    if ranking is None or ranking.empty or "Código" not in ranking.columns:
        return {}
    f = ranking[ranking["Código"].astype(str) == str(code)]
    return f.iloc[0].to_dict() if not f.empty else {}


def _factor_weights(code: str, weights: Mapping[str, float] | None) -> dict[str, float]:
    # USD macro score has its dedicated composition in the app.
    if str(code).upper() == "USD":
        return {
            "juros": 0.35,
            "inflacao": 0.25,
            "pib": 0.00,
            "emprego": 0.25,
            "atividade": 0.15,
            "sentimento": 0.00,
        }
    w = dict(DEFAULT_WEIGHTS)
    w.update({k: _num(v, w.get(k, 0.0)) for k, v in dict(weights or {}).items() if k in w})
    return w


def _contributions(row: Mapping[str, Any], code: str, weights: Mapping[str, float] | None) -> dict[str, float]:
    w = _factor_weights(code, weights)
    out = {}
    for label, col, key in FACTOR_META:
        out[label] = _num(row.get(col, 50.0), 50.0) * _num(w.get(key, 0.0))
    return out


def build_strength_breakdown(
    ranking: pd.DataFrame,
    base: str,
    quote: str,
    weights: Mapping[str, float] | None = None,
) -> dict[str, Any]:
    rb, rq = _currency_row(ranking, base), _currency_row(ranking, quote)
    fb, fq = _num(rb.get("Pontuação_Final", 50), 50), _num(rq.get("Pontuação_Final", 50), 50)
    mb, mq = _num(rb.get("Pontuação_Macro", 50), 50), _num(rq.get("Pontuação_Macro", 50), 50)
    fedb, fedq = _num(rb.get("Influência_Fed", 0), 0), _num(rq.get("Influência_Fed", 0), 0)

    cb, cq = _contributions(rb, base, weights), _contributions(rq, quote, weights)

    # Residual makes the decomposition exact. For USD this can contain its
    # dedicated DXY/surprise/model adjustments not represented by generic factors.
    residual_b = fb - mb - fedb
    residual_q = fq - mq - fedq

    rows = []
    for label, _, _ in FACTOR_META:
        rows.append({
            "Fator": label,
            str(base): round(cb[label], 2),
            str(quote): round(cq[label], 2),
            "Vantagem base": round(cb[label] - cq[label], 2),
        })
    rows.append({
        "Fator": "Federal Reserve",
        str(base): round(fedb, 2),
        str(quote): round(fedq, 2),
        "Vantagem base": round(fedb - fedq, 2),
    })
    rows.append({
        "Fator": "Ajustes dedicados / residual",
        str(base): round(residual_b, 2),
        str(quote): round(residual_q, 2),
        "Vantagem base": round(residual_b - residual_q, 2),
    })

    diff = fb - fq
    ordered = sorted(rows, key=lambda r: abs(float(r["Vantagem base"])), reverse=True)
    top = ordered[:3]
    reasons = []
    for r in top:
        d = float(r["Vantagem base"])
        if abs(d) < 0.05:
            continue
        winner = base if d > 0 else quote
        reasons.append(f"{r['Fator']}: {winner} +{abs(d):.1f} pts")
    dominant = " · ".join(reasons) if reasons else "Diferença distribuída entre vários fatores."

    return {
        "base": base,
        "quote": quote,
        "base_score": round(fb, 2),
        "quote_score": round(fq, 2),
        "difference": round(diff, 2),
        "macro_difference": round(mb - mq, 2),
        "fed_difference": round(fedb - fedq, 2),
        "rows": rows,
        "dominant": dominant,
        "stronger": base if diff > 0 else quote if diff < 0 else "EMPATE",
        "note": "Pontos internos do modelo; não são pips nem probabilidade de lucro.",
    }
