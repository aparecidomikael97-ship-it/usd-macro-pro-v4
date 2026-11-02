"""Painel Mestre: reuse legacy V10.6.2 news snapshot without new network calls.

The old Currency News Intelligence can already produce v1061_currency_news in
Streamlit session_state. This read adapter accepts it only with timestamps,
attributed publishers, and safety checks. A published headline is NOT a fact
verification and heuristic news scores are NEVER promoted into trade bias.

No Worker, new API, paid call, persistence, or trade execution.
"""
from __future__ import annotations

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import re
from typing import Any, Mapping
from urllib.parse import urlparse

from atlasquant_trader_opening_collector import brasilia_clock

SCHEMA = "ATLASQUANT_MASTER_NEWS_LEGACY_OBSERVATIONAL_V1"
CURRENCIES = frozenset(("USD", "EUR", "GBP", "JPY", "CHF", "CAD", "AUD", "NZD"))
MAX_SNAPSHOT_AGE = 3 * 3600
MAX_ARTICLE_AGE = 48 * 3600
_GEO_WORDS = re.compile(
    r"\b(sanctions?|tariffs?|trade war|armed conflict|military|invasion|"
    r"geopolitic(?:al|s)?|supply chain|war|opec|conflicts?|"
    r"sancoes|sancao|tarifas?|guerra|conflito|petroleo)\b",
    flags=re.IGNORECASE,
)


def _stamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or not 1 <= len(value) <= 100:
        return None
    try:
        moment = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except (ValueError, OverflowError):
        try:
            moment = parsedate_to_datetime(value.strip())
        except (ValueError, TypeError, IndexError, OverflowError):
            return None
    return moment.astimezone(timezone.utc) if moment.tzinfo else None


def _age(value: Any, now: datetime, limit: int) -> bool:
    point = _stamp(value)
    return point is not None and -60 <= (now - point).total_seconds() <= limit


def _url(raw: Any) -> str:
    value = str(raw or "").strip()
    if not value or len(value) > 1200 or any(ord(c) < 32 for c in value):
        return ""
    try:
        parts = urlparse(value)
        if (parts.scheme.lower() != "https" or not parts.hostname or
                parts.username or parts.password or parts.port not in (None, 443) or
                "." not in parts.hostname):
            return ""
    except (ValueError, AttributeError):
        return ""
    return value


def _text(raw: Any, limit: int) -> str:
    val = str(raw or "").strip()
    val = re.sub(r"[\x00-\x1f\x7f]", " ", val)
    return re.sub(r"\s+", " ", val).strip()[:limit]


def _blank(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "SEM FEED", "reason": reason,
        "source": "Currency News Intelligence V10.6.2 · legado observacional",
        "snapshot_at": "", "articles": [], "total": 0, "covered_currencies": [],
        "geo_count": 0, "signals_enabled": False, "facts_verified": False,
        "new_network_calls": False,
    }


def build_legacy_news_read_model(raw: Any, *, at: datetime | None = None) -> dict[str, Any]:
    now = at or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("Instante de referência requer fuso horário")
    now = now.astimezone(timezone.utc)
    if not isinstance(raw, Mapping):
        return _blank("Nenhum snapshot de notícias existente nesta sessão.")
    fetched = _stamp(raw.get("updated_at"))
    if fetched is None or not _age(raw.get("updated_at"), now, MAX_SNAPSHOT_AGE):
        return _blank("Snapshot de notícias sem fonte temporal fresca.")
    incoming = raw.get("currencies")
    if not isinstance(incoming, Mapping):
        return _blank("Snapshot de moedas sem contrato de leitura.")
    articles: dict[tuple[str, str], dict[str, Any]] = {}
    covered = []
    for currency in CURRENCIES:
        snapshot = incoming.get(currency)
        if not isinstance(snapshot, Mapping):
            continue
        rows = snapshot.get("articles")
        if not isinstance(rows, list):
            continue
        covered.append(currency)
        for item in rows[:18]:
            if not isinstance(item, Mapping):
                continue
            title = _text(item.get("title"), 235)
            source = _text(item.get("source"), 120)
            timestamp = _stamp(item.get("published_at"))
            if not title or len(title) < 8 or not source or source.lower() in (
                "fonte não identificada", "unknown", "unspecified"
            ):
                continue
            if timestamp is None or not _age(item.get("published_at"), now, MAX_ARTICLE_AGE):
                continue
            # Safe identity across the 8 currencies. Do not combine different
            # outlets carrying a similarly worded story into verified fact.
            key = (re.sub(r"\W+", " ", title.casefold()).strip(), source.casefold())
            if key not in articles:
                articles[key] = {
                    "title": title, "publisher": source,
                    "published_at": timestamp.isoformat(),
                    "time_brt": brasilia_clock(timestamp).strftime("%d/%m %H:%M"),
                    "provider": _text(item.get("provider"), 60) or "Fonte editorial existente",
                    "url": _url(item.get("link")),
                    "currencies": [currency],
                    "type": ("GEOPOLÍTICA EM MANCHETE" if _GEO_WORDS.search(title)
                             else "NOTÍCIA EM OBSERVAÇÃO"),
                    "verified_fact": False,
                    "trade_signal": False,
                }
            elif currency not in articles[key]["currencies"]:
                articles[key]["currencies"].append(currency)
    valid = sorted(
        articles.values(), key=lambda row: row["published_at"], reverse=True
    )
    for item in valid:
        item["currencies"].sort()
    if not valid:
        return {**_blank("Snapshot recente, mas sem manchetes atribuídas e recentes."),
                "snapshot_at": fetched.isoformat(), "covered_currencies": sorted(covered)}
    return {
        "schema": SCHEMA,
        "state": "OBSERVACIONAL",
        "reason": "Manchetes existentes, sem verificação independente do conteúdo.",
        "source": "Currency News Intelligence V10.6.2 · legado observacional",
        "snapshot_at": fetched.isoformat(),
        "articles": valid[:12], "total": len(valid),
        "covered_currencies": sorted(covered),
        "geo_count": sum(item["type"] == "GEOPOLÍTICA EM MANCHETE" for item in valid),
        "signals_enabled": False, "facts_verified": False,
        "new_network_calls": False,
    }


__all__ = ["SCHEMA", "build_legacy_news_read_model"]
