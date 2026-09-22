"""AtlasQuant central 7-pair matrix core.

Pure assembly helpers used by the Streamlit app. This module does not call
providers, does not write runtime data, and does not enable trading.
"""
from __future__ import annotations

import math
from typing import Any, Callable, Mapping

import numpy as np
import pandas as pd

PAIR_MATRIX_PAIRS=(
    "EUR/USD","GBP/USD","AUD/USD","NZD/USD","USD/JPY","USD/CHF","USD/CAD",
)
REQUIRED_RANKING_CODES=frozenset({"USD","EUR","GBP","AUD","NZD","JPY","CHF","CAD"})


def _finite(value: Any, default: float | None = None) -> float | None:
    try:
        x=float(value)
    except Exception:
        return default
    return x if math.isfinite(x) else default


def resolve_pair_usd_context(
    *,
    usd_base: Any,
    surprise_adjusted_usd: Any,
    surprise_adjustment: Any,
    fomc_score: Any,
    fomc_active: Any,
    fomc_post_release_active: Any,
    next_event: Mapping[str,Any] | None,
)->dict[str,Any]:
    """Resolve the single USD score used by all pair-matrix consumers."""
    base=_finite(usd_base,50.0)
    before=_finite(surprise_adjusted_usd,base)
    adjustment=_finite(surprise_adjustment,0.0)
    score=_finite(fomc_score,50.0)
    event=dict(next_event or {})
    weight=0.0

    name=str(event.get("evento","")).casefold()
    available=bool(event.get("disponivel",False))
    days=_finite(event.get("dias"),None)
    is_fomc=("fomc" in name) or ("federal open market" in name)

    if (
        bool(fomc_active)
        and not bool(fomc_post_release_active)
        and available
        and is_fomc
        and days is not None
    ):
        if days <= 2:
            weight=0.25
        elif days <= 7:
            weight=0.20
        elif days <= 14:
            weight=0.12
        else:
            weight=0.06

    after=(1.0-weight)*before+weight*score
    return {
        "usd_base":float(np.clip(base,0.0,100.0)),
        "usd_before_fomc":float(np.clip(before,0.0,100.0)),
        "usd_for_pairs":float(np.clip(after,0.0,100.0)),
        "surprise_adjustment":float(adjustment),
        "fomc_score":float(np.clip(score,0.0,100.0)),
        "fomc_active":bool(fomc_active),
        "fomc_post_release_active":bool(fomc_post_release_active),
        "fomc_weight":float(weight),
        "fomc_integrated":bool(weight>0.0),
        "event":event,
    }


def _empty_result(reason: str, *, missing_codes: list[str] | None = None)->dict[str,Any]:
    return {
        "ready":False,
        "reason":str(reason),
        "missing_codes":list(missing_codes or []),
        "matrix":pd.DataFrame(),
        "pairs_expected":len(PAIR_MATRIX_PAIRS),
        "pairs_built":0,
        "trading_side_effects":False,
    }


def build_pair_matrix(
    *,
    ranking: pd.DataFrame,
    usd_context: Mapping[str,Any],
    fed_tone: Any,
    confluence_fn: Callable[...,Mapping[str,Any]],
)->dict[str,Any]:
    """Build all seven pairs once. Any invalid input fails closed."""
    if not isinstance(ranking,pd.DataFrame) or ranking.empty:
        return _empty_result("ranking indisponível")
    required_cols={"Código","Pontuação_Final"}
    if not required_cols.issubset(ranking.columns):
        return _empty_result("ranking sem colunas obrigatórias")

    work=ranking[["Código","Pontuação_Final"]].copy()
    work["Código"]=work["Código"].astype(str).str.upper().str.strip()
    work["Pontuação_Final"]=pd.to_numeric(work["Pontuação_Final"],errors="coerce")
    work=work[work["Pontuação_Final"].map(lambda x: bool(pd.notna(x) and math.isfinite(float(x))))]
    scores=dict(zip(work["Código"],work["Pontuação_Final"].astype(float)))

    missing=sorted(REQUIRED_RANKING_CODES-set(scores))
    # USD itself is resolved separately, but its presence in the ranking remains
    # an integrity check that the G8 ranking completed successfully.
    if missing:
        return _empty_result("ranking G8 incompleto",missing_codes=missing)

    usd=_finite(usd_context.get("usd_for_pairs"),None)
    adjustment=_finite(usd_context.get("surprise_adjustment"),None)
    if usd is None or adjustment is None:
        return _empty_result("contexto USD inválido")

    rows=[]
    try:
        for pair in PAIR_MATRIX_PAIRS:
            base,quote=pair.split("/")
            sb=usd if base=="USD" else _finite(scores.get(base),None)
            sq=usd if quote=="USD" else _finite(scores.get(quote),None)
            if sb is None or sq is None:
                return _empty_result("score de moeda ausente")
            diff=float(sb-sq)

            raw_direction="⚪ NEUTRO" if abs(diff)<6 else (
                f"🟢 COMPRA {pair}" if diff>0 else f"🔴 VENDA {pair}"
            )
            conf=dict(confluence_fn(
                base,quote,diff,float(usd),float(adjustment),str(fed_tone or "Neutro"),ranking
            ) or {})
            score=_finite(conf.get("score_confluencia"),None)
            quality=_finite(conf.get("qualidade_confluencia"),None)
            level=str(conf.get("nivel","")).upper().strip()
            if score is None or quality is None or not (0.0 <= score <= 100.0) or not (0.0 <= quality <= 100.0):
                return _empty_result(f"confluência inválida em {pair}")

            if abs(diff)<6 or score<58 or quality<50:
                decision="⚪ AGUARDAR"
                display_level="BAIXA"
            elif level=="ALTA":
                decision=raw_direction
                display_level="ALTA"
            elif level=="MODERADA":
                decision=raw_direction
                display_level="MODERADA"
            else:
                decision="⚪ AGUARDAR CONFIRMAÇÃO"
                display_level="BAIXA"

            rank=float(np.clip(score*0.60+quality*0.40,0.0,100.0))
            rows.append({
                "Par":pair,
                "Direção":decision,
                "Dif. macro":round(diff,1),
                "Score final":round(score,0),
                "Qualidade":round(quality,0),
                "Confluência":display_level,
                "Índice ranking":round(rank,1),
            })
    except Exception as exc:
        return _empty_result(f"falha na confluência: {type(exc).__name__}")

    matrix=pd.DataFrame(rows).sort_values(
        ["Índice ranking","Qualidade","Score final"],ascending=False
    ).reset_index(drop=True)
    matrix.insert(0,"Ranking",range(1,len(matrix)+1))
    ready=bool(len(matrix)==len(PAIR_MATRIX_PAIRS) and matrix["Par"].nunique()==len(PAIR_MATRIX_PAIRS))
    if not ready:
        return _empty_result("matriz incompleta")
    return {
        "ready":True,
        "reason":"OK",
        "missing_codes":[],
        "matrix":matrix,
        "pairs_expected":len(PAIR_MATRIX_PAIRS),
        "pairs_built":len(matrix),
        "trading_side_effects":False,
    }


__all__=[
    "PAIR_MATRIX_PAIRS","REQUIRED_RANKING_CODES",
    "resolve_pair_usd_context","build_pair_matrix",
]
