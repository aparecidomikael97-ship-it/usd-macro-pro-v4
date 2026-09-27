"""AtlasQuant Radar board.

Presentation-only assembly for the approved Radar architecture:

- 28 Forex pairs stay monitored;
- a dynamic TOP 10 is highlighted from that universe;
- indices and cryptos stay in separate rankings;
- Dia / Noite / Ambos only reorders attention.

Nothing here sends orders, copies Forex weights into other markets, or turns a
ranking score into a probability of profit.
"""
from __future__ import annotations

import math
from typing import Any, Mapping, Sequence

from atlasquant_fx_universe import CURRENCIES, OFFICIAL_PAIRS, rank_pairs

SCHEMA = "ATLASQUANT_RADAR_BOARD_V1"
FX_MONITORED_COUNT = 28
TOP_FX_LIMIT = 10

INDEX_UNIVERSE = (
    ("DXY", "Índice do dólar"),
    ("US30", "Dow Jones"),
    ("NAS100", "Nasdaq"),
    ("SPX500", "S&P 500"),
    ("IBOV", "Ibovespa"),
    ("WIN", "Mini índice"),
    ("WDO", "Mini dólar"),
)

CRYPTO_UNIVERSE = (
    ("BTC/USD", "Bitcoin"),
    ("ETH/USD", "Ethereum"),
    ("SOL/USD", "Solana"),
)


def _finite(value: Any) -> float | None:
    try:
        number = float(value)
    except Exception:
        return None
    if not math.isfinite(number):
        return None
    return number


def _records(value: Any) -> list[dict[str, Any]]:
    if value is None:
        return []
    if hasattr(value, "iterrows"):
        try:
            return [dict(row) for _, row in value.iterrows()]
        except Exception:
            return []
    if isinstance(value, Mapping):
        return []
    out: list[dict[str, Any]] = []
    try:
        items = list(value)
    except Exception:
        return []
    for item in items:
        if isinstance(item, Mapping):
            out.append(dict(item))
    return out


def _text(row: Mapping[str, Any], *keys: str) -> str:
    for key in keys:
        raw = row.get(key)
        if raw is not None and str(raw).strip():
            return str(raw).strip()
    return ""


def strengths_from_records(ranking: Any) -> dict[str, float] | None:
    """Read G8 scores already computed elsewhere. Incomplete input fails closed."""
    found: dict[str, float] = {}
    for row in _records(ranking):
        code = _text(row, "Código", "codigo", "code", "currency").upper()
        if code not in CURRENCIES or code in found:
            continue
        score = _finite(row.get("Pontuação_Final", row.get("score", row.get("Pontuação Final"))))
        if score is None or not (0.0 <= score <= 100.0):
            return None
        found[code] = score
    if set(found) != set(CURRENCIES):
        return None
    return found


def _base_fx_row(pair: str) -> dict[str, Any]:
    return {
        "pair": pair,
        "asset_class": "FX",
        "coverage": "monitorado",
        "session_bucket": "UNKNOWN",
        "session_label": "Sessão não informada",
        "bias": "NEUTRO",
        "action": "NÃO OPERAR",
        "priority": 0.0,
        "quality": 0.0,
        "data_score": 0.0,
        "data_ready": False,
        "state": "SEM LEITURA",
        "reason": "Par monitorado no universo de 28. Sem leitura válida, a ação permanece NÃO OPERAR.",
        "next_action": "Aguardar leitura válida. Estar monitorado não autoriza entrada.",
        "base_score": 0.0,
        "quote_score": 0.0,
        "strength_diff": 0.0,
        "h4": "—",
        "h1": "—",
        "m15": "—",
        "gate": "—",
        "event": "NORMAL",
        "news": "—",
        "movement": "N/D",
        "blockers": ["Sem pipeline institucional neste par."],
        "signal": {},
        "signal_status_code": "NO_SIGNAL",
        "signal_status_label": "SEM SINAL / AGUARDAR",
        "signal_headline": "AGUARDAR",
        "signal_reference_at": "",
        "signal_reference_display": "horário não comprovado",
        "signal_confirmed_at": "",
        "signal_observed_at": "",
        "signal_valid_until": "",
        "signal_age_minutes": None,
        "signal_remaining_minutes": None,
        "signal_timezone": "UTC",
        "target": "—",
        "w1": "—",
        "d1": "—",
        "pd_zone": "—",
        "sweep_type": "—",
        "sweep_level": "—",
        "ict_read": 0.0,
        "inst_read": 0.0,
        "up": [],
        "down": [],
        "positives": [],
        "hard_blocks": ["Sem leitura institucional."],
        "soft_blocks": [],
        "evidence_source": "Radar / universo Forex 28",
        "real_orders_enabled": False,
        "automatic_execution": False,
        "confidence": "NÃO CONFIRMADA",
        "provenance_state": "SEM DADOS",
        "score_components": {
            "technical": None,
            "macro": None,
            "session": None,
            "quality": None,
        },
        "pipeline": {
            "data": "SEM DADOS",
            "technical": "BLOQUEADO",
            "macro": "BLOQUEADO",
            "session": "NÃO CONFIRMADA",
            "quality": "SEM DADOS",
            "score": "BLOQUEADO",
            "ranking": "MONITORADO",
        },
    }


def _macro_fx_row(view: Any) -> dict[str, Any]:
    side = str(getattr(view, "side", "NEUTRAL")).upper()
    bias = "COMPRA" if side == "BUY" else "VENDA" if side == "SELL" else "NEUTRO"
    intensity = _finite(getattr(view, "directional_score", 0.0)) or 0.0
    row = _base_fx_row(str(getattr(view, "pair")))
    row.update({
        "coverage": "macro",
        "bias": bias,
        "action": "NÃO OPERAR",
        "priority": max(0.0, min(100.0, intensity)),
        "state": "RADAR MACRO",
        "reason": (
            f"Viés macro {bias} por desequilíbrio relativo no universo de 28 pares. "
            "Sem pipeline institucional completo, a ação permanece NÃO OPERAR."
        ),
        "next_action": "Usar só como mapa de atenção. Não tratar intensidade como entrada.",
        "base_score": float(getattr(view, "base_strength", 0.0) or 0.0),
        "quote_score": float(getattr(view, "quote_strength", 0.0) or 0.0),
        "strength_diff": float(getattr(view, "differential", 0.0) or 0.0),
        "signal_headline": "SOMENTE VIÉS MACRO",
        "blockers": ["Pipeline institucional completo ainda não cobre este par."],
        "hard_blocks": ["Radar macro não autoriza execução."],
        "evidence_source": "Radar / força relativa G8",
        "confidence": "BAIXA",
        "provenance_state": "MACRO CONFIRMADO · TÉCNICA AUSENTE",
        "score_components": {
            "technical": None,
            "macro": max(0.0, min(100.0, intensity)),
            "session": None,
            "quality": None,
        },
        "pipeline": {
            "data": "MACRO DISPONÍVEL",
            "technical": "SEM DADOS",
            "macro": "CONFIRMADO",
            "session": "NÃO CONFIRMADA",
            "quality": "PARCIAL",
            "score": "SOMENTE MACRO",
            "ranking": "BLOQUEADO PARA ESTUDO",
        },
    })
    return row


def _normalized_institutional_row(raw: Mapping[str, Any], pair: str) -> dict[str, Any]:
    """Normalize one pre-computed technical record without trusting its action flags."""
    row = _base_fx_row(pair)
    row.update(dict(raw))
    row["pair"] = pair
    row["asset_class"] = "FX"
    row["coverage"] = str(raw.get("coverage") or "institucional")
    row["real_orders_enabled"] = False
    row["automatic_execution"] = False

    technical = _finite(row.get("priority"))
    quality = _finite(row.get("data_score", row.get("quality")))
    ready = bool(row.get("data_ready")) and technical is not None and quality is not None
    session = str(row.get("session_bucket") or "UNKNOWN").upper()
    macro = _finite(row.get("strength_diff"))
    if not ready:
        row["action"] = "NÃO OPERAR"
        row["confidence"] = "NÃO CONFIRMADA"
        row["state"] = "SEM DADOS" if quality is None else "BLOQUEADO"
    else:
        row["confidence"] = "ALTA" if quality >= 80 else "MODERADA" if quality >= 60 else "BAIXA"
    row["provenance_state"] = (
        "CONFIRMADA" if ready else "INCOMPLETA · NÃO CONFIRMADA"
    )
    row["score_components"] = {
        "technical": technical if ready else None,
        "macro": abs(macro) if macro is not None else None,
        "session": 100.0 if session != "UNKNOWN" else None,
        "quality": quality if ready else None,
    }
    row["pipeline"] = {
        "data": "CONFIRMADO" if ready else "SEM DADOS",
        "technical": "CONFIRMADO" if ready else "BLOQUEADO",
        "macro": "CONFIRMADO" if macro is not None else "NÃO CONFIRMADO",
        "session": "CONFIRMADA" if session != "UNKNOWN" else "NÃO CONFIRMADA",
        "quality": "CONFIRMADA" if quality is not None else "SEM DADOS",
        "score": "CALCULADO" if ready else "BLOQUEADO",
        "ranking": "ELEGÍVEL PARA ESTUDO" if ready else "BLOQUEADO PARA ESTUDO",
    }
    return row


def compose_fx_board(
    pack_rows: Sequence[Mapping[str, Any]] | None,
    ranking: Any = None,
) -> dict[str, Any]:
    """Always return the 28 official Forex pairs, enriched when data exists."""
    by_pair: dict[str, dict[str, Any]] = {}
    for raw in list(pack_rows or []):
        if not isinstance(raw, Mapping):
            continue
        pair = str(raw.get("pair") or "").strip().upper()
        if pair not in OFFICIAL_PAIRS or pair in by_pair:
            continue
        by_pair[pair] = _normalized_institutional_row(raw, pair)

    macro_ready = False
    strengths = strengths_from_records(ranking)
    if strengths is not None:
        macro_ready = True
        for view in rank_pairs(strengths):
            if view.pair in by_pair:
                current = by_pair[view.pair]
                if current.get("strength_diff") in (None, "", 0, 0.0) and not current.get("data_ready"):
                    current["strength_diff"] = float(view.differential)
                continue
            by_pair[view.pair] = _macro_fx_row(view)

    rows = [by_pair.get(pair) or _base_fx_row(pair) for pair in OFFICIAL_PAIRS]
    institutional = sum(1 for row in rows if row.get("coverage") == "institucional")
    macro_only = sum(1 for row in rows if row.get("coverage") == "macro")
    missing = sum(1 for row in rows if row.get("coverage") == "monitorado")
    return {
        "schema": SCHEMA,
        "rows": rows,
        "monitored": len(rows),
        "institutional": institutional,
        "macro_only": macro_only,
        "missing": missing,
        "macro_ready": macro_ready,
        "top_limit": TOP_FX_LIMIT,
        "real_orders_enabled": False,
        "automatic_execution": False,
    }


def rank_fx_population(rows: Sequence[Mapping[str, Any]] | None) -> list[dict[str, Any]]:
    """Rank exactly the supplied FX population; invalid values sort last safely."""
    selected = [
        dict(row) for row in list(rows or [])
        if str(dict(row).get("asset_class") or "FX").upper() == "FX"
    ]
    selected.sort(
        key=lambda row: (
            {"MATCH": 0, "UNKNOWN": 1, "OUTSIDE": 2}.get(str(row.get("session_match") or "UNKNOWN"), 1),
            0 if bool(row.get("data_ready")) else 1,
            0 if str(row.get("action") or "").upper() not in {"", "NÃO OPERAR", "NAO OPERAR"} else 1,
            -(_finite(row.get("priority")) or 0.0),
            -(_finite(row.get("data_score")) or 0.0),
            str(row.get("pair") or ""),
        )
    )
    return selected


def highlight_top_fx(rows: Sequence[Mapping[str, Any]] | None, limit: int = TOP_FX_LIMIT) -> list[dict[str, Any]]:
    try:
        size = int(limit)
    except Exception:
        size = TOP_FX_LIMIT
    if isinstance(limit, bool) or size < 0:
        size = 0
    size = min(size, TOP_FX_LIMIT)
    selected = rank_fx_population(rows)
    return selected[:size]


def _observation_map(observations: Any) -> dict[str, Mapping[str, Any]]:
    found: dict[str, Mapping[str, Any]] = {}
    for row in _records(observations):
        symbol = _text(row, "symbol", "pair", "ativo", "Código", "code").upper()
        if symbol and symbol not in found:
            found[symbol] = row
    return found


def _separate_rows(universe: Sequence[tuple[str, str]], observations: Any, *, asset_class: str) -> list[dict[str, Any]]:
    observed = _observation_map(observations)
    rows: list[dict[str, Any]] = []
    for symbol, name in universe:
        extra = dict(observed.get(symbol, {}))
        score = _finite(extra.get("score", extra.get("priority", extra.get("Pontuação_Final"))))
        if score is not None:
            score = max(0.0, min(100.0, score))
        note = _text(extra, "reason", "note", "state")
        rows.append({
            "symbol": symbol,
            "name": name,
            "asset_class": asset_class,
            "score": score,
            "action": "NÃO OPERAR",
            "state": "OBSERVAÇÃO" if score is not None else "SEM LEITURA AO VIVO",
            "reason": note or (
                "Ranking separado e somente observacional. "
                "Este mercado não reutiliza pesos de Forex e não autoriza execução."
            ),
            "real_orders_enabled": False,
            "automatic_execution": False,
        })
    rows.sort(
        key=lambda row: (
            row["score"] is None,
            -(row["score"] or 0.0),
        )
    )
    for index, row in enumerate(rows, start=1):
        row["rank"] = index
    return rows


def index_ranking(observations: Any = None) -> list[dict[str, Any]]:
    return _separate_rows(INDEX_UNIVERSE, observations, asset_class="INDEX")


def crypto_ranking(observations: Any = None) -> list[dict[str, Any]]:
    return _separate_rows(CRYPTO_UNIVERSE, observations, asset_class="CRYPTO")


__all__ = [
    "SCHEMA",
    "FX_MONITORED_COUNT",
    "TOP_FX_LIMIT",
    "INDEX_UNIVERSE",
    "CRYPTO_UNIVERSE",
    "strengths_from_records",
    "compose_fx_board",
    "rank_fx_population",
    "highlight_top_fx",
    "index_ranking",
    "crypto_ranking",
]
