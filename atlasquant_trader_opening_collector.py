"""Coletor puro e fail-closed para a Estratégia de Abertura WIN.

Não agenda tarefas, não acessa rede e não ativa o AION. Recebe uma função
provedora injetada APÓS confirmação do instrumento, direitos e custo do feed.
Dados não verificados nunca geram viés ou ordem.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from math import isfinite
from typing import Any, Callable, Mapping
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

MODEL = "ATLASQUANT_WIN_OPENING_RESEARCH_V1"
# Identidades FIXAS; não confundir spot de minério/petróleo com futuros.
INSTRUMENTS = {
    "vix": ("VIX_INDEX", "VIX · Índice Cboe de Volatilidade", "previous_close"),
    "iron": ("SGX_IODEX_IRON_ORE_FUTURES", "SGX IODEX Iron Ore Futures", "previous_settlement"),
    "oil": ("WTI_LIGHT_SWEET_CRUDE_FUTURES", "WTI · Futuros de petróleo leve bruto", "previous_settlement"),
}
START_MINUTE = 8 * 60 + 40
END_MINUTE = 8 * 60 + 55


def brasilia_timezone():
    try:
        return ZoneInfo("America/Sao_Paulo")
    except ZoneInfoNotFoundError:
        # Fallback para Windows LAB sem pacote tzdata; não usar para séries históricas com DST.
        return timezone(timedelta(hours=-3))


def brasilia_clock(at: datetime | None = None) -> datetime:
    now = at if at is not None else datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("O instante deve ter fuso horário")
    return now.astimezone(brasilia_timezone())


def in_collection_window(at: datetime | None = None) -> bool:
    local = brasilia_clock(at)
    minutes = local.hour * 60 + local.minute
    return local.weekday() < 5 and START_MINUTE <= minutes <= END_MINUTE


def _positive_number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        n = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return n if isfinite(n) and n > 0 else None


def _read_quote(raw: Any, *, kind: str, local: datetime) -> dict[str, Any] | None:
    if not isinstance(raw, Mapping) or raw.get("state") != "VERIFIED_QUOTE":
        return None
    expected_symbol, name, baseline = INSTRUMENTS[kind]
    if raw.get("instrument_id") != expected_symbol or raw.get("reference_type") != baseline:
        return None
    source = str(raw.get("source") or "").strip()
    if not source or len(source) > 100:
        return None
    last = _positive_number(raw.get("price"))
    previous = _positive_number(raw.get("previous_reference"))
    if last is None or previous is None:
        return None
    try:
        stamp = datetime.fromisoformat(str(raw.get("as_of") or "").replace("Z", "+00:00"))
        if stamp.tzinfo is None:
            return None
        quote_local = stamp.astimezone(brasilia_timezone())
        # O feed deve representar o mercado hoje, não o fechamento de ontem.
        if quote_local.date() != local.date():
            return None
        age = (local - quote_local).total_seconds()
        if not -60 <= age <= 10 * 60:
            return None
        ref_date = date.fromisoformat(str(raw.get("reference_date") or ""))
        if not (timedelta(days=1) <= local.date() - ref_date <= timedelta(days=7)):
            return None
    except (ValueError, TypeError, OverflowError):
        return None
    change = 100.0 * (last / previous - 1)
    if not isfinite(change) or abs(change) > 100:
        return None
    return {"instrument_id": expected_symbol, "name": name,
            "source": source, "as_of": stamp.astimezone(timezone.utc).isoformat(),
            "price": last, "previous_reference": previous,
            "reference_type": baseline, "reference_date": ref_date.isoformat(),
            "pct": round(change, 4)}


def build_opening_snapshot(
    fetch_quote: Callable[[str], Mapping[str, Any] | None] | None,
    *, at: datetime | None = None
) -> dict[str, Any] | None:
    """Consulta os três instrumentos na janela 08:40–08:55 BRT.

    Cada instrumento deve vir de um feed licenciado/validado com símbolo correto,
    preço, referência anterior, horário e fonte. Não grava nada; o agendador e a
    persistência diária são integrados separadamente após aprovação.
    """
    local = brasilia_clock(at)
    if not in_collection_window(local) or fetch_quote is None:
        return None
    results = {}
    for key, (instrument_id, _, _) in INSTRUMENTS.items():
        try:
            raw = fetch_quote(instrument_id)
        except Exception:
            # Falha de fonte: nenhum viés parcial.
            return None
        parsed = _read_quote(raw, kind=key, local=local)
        if parsed is None:
            return None
        results[key] = parsed
    as_of = max(datetime.fromisoformat(item["as_of"]) for item in results.values())
    return {
        "state": "VALIDATED_OPENING",
        "model": MODEL,
        "source": " | ".join(f"{name.upper()}: {results[name]['source']}"
                             for name in ("vix", "iron", "oil")),
        "as_of": as_of.isoformat(),
        "session_date": local.date().isoformat(),
        "vix_pct": results["vix"]["pct"],
        "iron_pct": results["iron"]["pct"],
        "oil_pct": results["oil"]["pct"],
        "quotes": results,
    }


__all__ = ["MODEL", "INSTRUMENTS", "in_collection_window",
           "brasilia_clock", "build_opening_snapshot"]
