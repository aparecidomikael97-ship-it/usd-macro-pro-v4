"""USD Macro Pro V11.0.6 — detalhamento dos pontos de força por moeda/par.

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


def _raw_contributions(row: Mapping[str, Any], code: str, weights: Mapping[str, float] | None) -> dict[str, float]:
    w = _factor_weights(code, weights)
    out = {}
    for label, col, key in FACTOR_META:
        out[label] = _num(row.get(col, 50.0), 50.0) * _num(w.get(key, 0.0))
    return out


def _scaled_contributions(
    row: Mapping[str, Any],
    code: str,
    weights: Mapping[str, float] | None,
    macro_score: float,
) -> dict[str, float]:
    """Scales factor contributions so they sum exactly to Pontuação_Macro."""
    raw = _raw_contributions(row, code, weights)
    total = sum(raw.values())
    if abs(total) < 1e-12:
        # No usable factors: keep all zero and let residual explain the macro score.
        return {k: 0.0 for k in raw}
    scale = float(macro_score) / float(total)
    return {k: float(v) * scale for k, v in raw.items()}



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

    cb = _scaled_contributions(rb, base, weights, mb)
    cq = _scaled_contributions(rq, quote, weights, mq)

    # Residual makes the decomposition exact. For USD this can contain its
    # dedicated DXY/surprise/model adjustments not represented by generic factors.
    residual_b = fb - sum(cb.values()) - fedb
    residual_q = fq - sum(cq.values()) - fedq

    rows = []
    def _row(label: str, vb: float, vq: float) -> dict[str, Any]:
        d = float(vb) - float(vq)
        winner = base if d > 0.005 else quote if d < -0.005 else "EMPATE"
        return {
            "Fator": label,
            str(base): round(vb, 2),
            str(quote): round(vq, 2),
            "Diferença base−cotada": round(d, 2),
            "Favorece": winner,
        }

    for label, _, _ in FACTOR_META:
        rows.append(_row(label, cb[label], cq[label]))
    rows.append(_row("Federal Reserve", fedb, fedq))
    rows.append(_row("Ajustes dedicados / residual", residual_b, residual_q))

    diff = fb - fq
    ordered = sorted(rows, key=lambda r: abs(float(r["Diferença base−cotada"])), reverse=True)
    top = ordered[:3]
    reasons = []
    for r in top:
        d = float(r["Diferença base−cotada"])
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
        "pair_pressure": (
            f"viés relativo favorece alta de {base}/{quote}" if diff > 0
            else f"viés relativo favorece queda de {base}/{quote}" if diff < 0
            else "força relativa equilibrada"
        ),
        "explained_base": round(sum(cb.values()) + fedb + residual_b, 2),
        "explained_quote": round(sum(cq.values()) + fedq + residual_q, 2),
        "base_macro": round(mb, 2),
        "quote_macro": round(mq, 2),
        "base_fed": round(fedb, 2),
        "quote_fed": round(fedq, 2),
        "base_adjustments": round(residual_b, 2),
        "quote_adjustments": round(residual_q, 2),
        "adjustment_difference": round(residual_b - residual_q, 2),
        "note": "Pontos internos do modelo; não são pips nem probabilidade de lucro.",
    }


def attribution_sides(breakdown: Mapping[str, Any]) -> dict[str, Any]:
    """Agrupa fatores a favor de cada moeda e reconcilia o resultado líquido."""
    base=str(breakdown.get("base","BASE")); quote=str(breakdown.get("quote","COTADA"))
    base_items=[]; quote_items=[]
    for r in breakdown.get("rows",[]) or []:
        d=_num(r.get("Diferença base−cotada",0),0)
        item={"Fator":str(r.get("Fator","")),"pts":round(abs(d),2)}
        if d>0.005: base_items.append(item)
        elif d<-0.005: quote_items.append(item)
    base_items.sort(key=lambda x:x["pts"],reverse=True); quote_items.sort(key=lambda x:x["pts"],reverse=True)
    return {
        "base":base,"quote":quote,
        "base_items":base_items,"quote_items":quote_items,
        "base_advantages":round(sum(x["pts"] for x in base_items),2),
        "quote_advantages":round(sum(x["pts"] for x in quote_items),2),
        "net":round(_num(breakdown.get("difference",0),0),2),
    }
