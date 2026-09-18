"""AtlasQuant Macro Briefing - deterministic, fail-closed narration model.

Transforms already-computed AtlasQuant state into a daily/weekly briefing payload.
It does not fetch market data, create trades, change scores, or bypass Safety Core.
Audio/TTS is a presentation layer and must consume speech_text.
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence


def _f(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _txt(value: Any, fallback: str = "não disponível") -> str:
    value = str(value or "").strip()
    return value if value else fallback


def _fresh(item: Mapping[str, Any]) -> bool:
    if item.get("stale") is True or item.get("data_ready") is False:
        return False
    quality = str(item.get("quality", "")).lower()
    return quality not in {"stale", "missing", "invalid", "blocked"}


def build_macro_briefing(currency_rows: Sequence[Mapping[str, Any]] | None, events: Sequence[Mapping[str, Any]] | None = None, central_banks: Sequence[Mapping[str, Any]] | None = None, *, horizon: str = "today", generated_at: str | None = None) -> dict[str, Any]:
    """Build a presentation-only macro briefing from verified upstream state."""
    horizon = "week" if str(horizon).lower() in {"week", "weekly", "semana"} else "today"
    rows = [dict(x or {}) for x in (currency_rows or []) if _fresh(dict(x or {}))]
    evs = [dict(x or {}) for x in (events or []) if _fresh(dict(x or {}))]
    banks = [dict(x or {}) for x in (central_banks or []) if _fresh(dict(x or {}))]
    scored = sorted(rows, key=lambda x: _f(x.get("score", x.get("strength", 0))), reverse=True)
    strongest = scored[:3]
    weakest = list(reversed(scored[-3:])) if scored else []
    high_events = [e for e in evs if str(e.get("impact", e.get("importance", ""))).lower() in {"high", "alto", "3", "3-star", "3 stars"}]
    if not high_events:
        high_events = evs[:5]
    if not rows:
        state = "DADOS INSUFICIENTES"
        summary = "O AtlasQuant não possui dados macro frescos suficientes para formar um briefing."
    else:
        state = "INFORMATIVO"
        lead = strongest[0]
        tail = weakest[0] if weakest else {}
        summary = (f"Entre as moedas com dados válidos, {_txt(lead.get('currency', lead.get('symbol')))} aparece entre as mais fortes e {_txt(tail.get('currency', tail.get('symbol')))} entre as mais fracas. Isso descreve o estado calculado; não é garantia de movimento futuro.")
    bank_lines = []
    for b in banks[:5]:
        name = _txt(b.get("bank", b.get("name")), "Banco central")
        tone = _txt(b.get("tone", b.get("bias")), "neutro")
        bank_lines.append(f"{name}: tom {tone}")
    event_lines = []
    for e in high_events[:6]:
        label = _txt(e.get("event", e.get("name")), "Evento macro")
        ccy = _txt(e.get("currency"), "")
        when = _txt(e.get("time", e.get("datetime")), "horário não confirmado")
        event_lines.append(f"{label}{' ' + ccy if ccy else ''}}, {when}")
    title = "Briefing macro de hoje" if horizon == "today" else "Briefing macro da semana"
    speech_parts = [title + ".", summary]
    if bank_lines:
        speech_parts.append("Bancos centrais: " + "; ".join(bank_lines) + ".")
    if event_lines:
        speech_parts.append("Eventos relevantes: " + "; ".join(event_lines) + ".")
    speech_parts.append("Antes de qualquer operação, confirme o calendário, a qualidade dos dados e os gates do Safety Core.")
    return {"horizon": horizon, "title": title, "state": state, "generated_at": generated_at, "summary": summary, "strongest": strongest, "weakest": weakest, "central_banks": bank_lines, "events": event_lines, "speech_text": " ".join(speech_parts), "disclaimer": "Briefing informativo baseado no estado do AtlasQuant; não constitui sinal nem garantia de resultado.", "data_sufficient": bool(rows)}
