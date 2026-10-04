"""Fail-closed executive market snapshot for the AtlasQuant Master Panel.

This module only summarizes evidence already available in the application. It
does not collect data, infer missing fundamentals, or authorize execution.
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence

from atlasquant_radar_board import (
    compose_fx_board,
    crypto_ranking,
    highlight_top_fx,
    index_ranking,
)

SCHEMA = "ATLASQUANT_MASTER_MARKET_V1"


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _source_rows(source_status: Mapping[str, Any] | None) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for name, raw in sorted(_mapping(source_status).items(), key=lambda item: str(item[0])):
        item = _mapping(raw)
        raw_text = str(raw or "")
        state = str(
            item.get("status")
            or item.get("state")
            or item.get("estado")
            or raw_text
            or ("CONFIRMADA" if raw is True else "INDISPONÍVEL")
        ).upper()
        if any(token in state for token in ("✅", "OK", "ATUAL", "CONFIRM", "ONLINE", "VÁLID")):
            normalized = "CONFIRMADA"
        elif any(token in state for token in ("⚠", "FALLBACK", "DEGRAD", "CACHE", "STALE", "SEGURANÇA")):
            normalized = "FALLBACK"
        else:
            normalized = "INDISPONÍVEL"
        rows.append({
            "Fonte": str(name),
            "Estado": normalized,
            "Referência": str(
                item.get("timestamp")
                or item.get("updated_at")
                or item.get("data")
                or "HORÁRIO NÃO COMPROVADO"
            ),
        })
    return rows


def _event_snapshot(macro_context: Mapping[str, Any] | None) -> dict[str, Any]:
    event = _mapping(_mapping(macro_context).get("event"))
    available = bool(event.get("disponivel") or event.get("available"))
    title = str(event.get("nome") or event.get("name") or event.get("evento") or "")
    reference = str(
        event.get("data_hora")
        or event.get("timestamp")
        or event.get("data")
        or event.get("date")
        or ""
    )
    if not available or not title:
        return {
            "state": "SEM EVENTO CONFIRMADO",
            "title": "Nenhum evento econômico confirmado neste estado",
            "reference": "HORÁRIO NÃO COMPROVADO",
            "pre_news": "BLOQUEADO",
            "reason": "Sem evento e horário provenientes, o pré-notícia não é inferido.",
        }
    return {
        "state": "CONFIRMADO",
        "title": title,
        "reference": reference or "HORÁRIO NÃO COMPROVADO",
        "pre_news": "REVISAR" if reference else "BLOQUEADO",
        "reason": (
            "Evento proveniente disponível; revisar impacto e horário antes do estudo."
            if reference
            else "Evento sem horário comprovado; pré-notícia permanece bloqueado."
        ),
    }


def _domain(
    name: str,
    *,
    available: bool,
    detail: str,
    source: str,
    fallback: bool = False,
) -> dict[str, str]:
    return {
        "Domínio": name,
        "Estado": "FALLBACK" if fallback else "CONFIRMADO" if available else "SEM DADOS",
        "Leitura": detail if available or fallback else "Não confirmada; nenhuma leitura foi fabricada.",
        "Fonte": source if available or fallback else "FONTE AUSENTE",
    }


def build_executive_market_snapshot(
    *,
    ranking: Any = None,
    master_rows: Sequence[Mapping[str, Any]] | None = None,
    macro_context: Mapping[str, Any] | None = None,
    source_status: Mapping[str, Any] | None = None,
    fx_resident: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the executive view from known data, preserving absent evidence."""
    fx = compose_fx_board([], ranking)
    fx_rows = list(fx["rows"])
    from atlasquant_interface_final import eligible_fx_population
    top_fx = eligible_fx_population(dict(fx_resident or {}))['ranked'][:10]
    macro_attention = highlight_top_fx([row for row in fx_rows if row.get('coverage')=='macro'])
    indexes = index_ranking()
    cryptos = crypto_ranking()
    rows = [dict(row) for row in list(master_rows or []) if isinstance(row, Mapping)]

    aligned = [
        row for row in rows
        if str(row.get("Estado") or "").startswith(("🟢", "🟡 QUASE"))
    ]
    divergent = [
        row for row in rows
        if "CONFLITO" in str(row.get("Estado") or "")
        or "CONTRA" in str(row.get("Estado") or "")
    ]
    released = [
        row for row in rows
        if str(row.get("Autorização") or "").startswith("✅")
        and str(row.get("Status temporal") or "") == "ATUAL"
    ]
    blocked = [row for row in rows if row not in released]

    macro = _mapping(macro_context)
    event = _event_snapshot(macro)
    macro_available = any(
        macro.get(key) not in (None, "", {}, [])
        for key in ("trend", "surprise_adjustment", "fomc_score")
    )
    domains = [
        _domain(
            "Macro",
            available=macro_available,
            detail="Contexto macro disponível no motor; consultar componentes antes de interpretar.",
            source="Motor macro AtlasQuant",
        ),
        _domain(
            "Fundamentalista",
            available=macro_available,
            detail="Leitura parcial dos indicadores presentes; ausências continuam não confirmadas.",
            source="Motor macro AtlasQuant",
        ),
        _domain(
            "Micro / fluxo",
            available=False,
            detail="",
            source="",
        ),
        _domain(
            "Geopolítica",
            available=False,
            detail="",
            source="",
        ),
        _domain(
            "Sentimento",
            available=False,
            detail="",
            source="",
        ),
    ]
    dxy = next((row for row in indexes if row["symbol"] == "DXY"), None)
    source_rows = _source_rows(source_status)
    fallbacks = [row for row in source_rows if row["Estado"] == "FALLBACK"]
    unavailable = [row for row in source_rows if row["Estado"] == "INDISPONÍVEL"]

    return {
        "schema": SCHEMA,
        "forex": {
            "monitored": fx["monitored"],
            "population":fx_rows,
            "top_limit": fx["top_limit"],
            "top": top_fx,
            "macro_attention":macro_attention,
            "macro_ready": fx["macro_ready"],
            "institutional": fx["institutional"],
            "macro_only": fx["macro_only"],
            "missing": fx["missing"],
        },
        "indices": indexes,
        "cryptos": cryptos,
        "dxy": dxy,
        "domains": domains,
        "event": event,
        "alignment": {
            "aligned": len(aligned),
            "divergent": len(divergent),
            "aligned_pairs": [str(row.get("Par") or "") for row in aligned],
            "divergent_pairs": [str(row.get("Par") or "") for row in divergent],
        },
        "opportunities": {
            "released_for_study": released,
            "blocked": blocked,
        },
        "sources": source_rows,
        "fallback_count": len(fallbacks),
        "unavailable_source_count": len(unavailable),
        "real_orders_enabled": False,
        "automatic_execution": False,
        "disclaimer": (
            "Visão informativa para estudo. Liberação para estudo não habilita ordem real, "
            "execução automática ou recomendação personalizada."
        ),
    }


__all__ = ["SCHEMA", "build_executive_market_snapshot"]
