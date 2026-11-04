"""Documentary official-news context for the 28-pair D1/W1/MN1 lab panel.

Only reconciled, CALLER-SUPPLIED offline feed simulations are supported.
Headlines, conditional macro hypotheses and curated calendar exposures may
be shown together for source review, never converted into causal FX claims,
live news, relative currency-strength rankings or tradeable market bias.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import re
from typing import Any, Mapping

from atlasquant_fx_universe import CURRENCIES, OFFICIAL_PAIRS, split_pair
from atlasquant_trader_bias_calendar_exposure_link_lab import (
    SCHEMA as BIAS_CALENDAR_SCHEMA,
)
from atlasquant_trader_macro_event_exposure_lab import (
    build_macro_event_exposure_lab,
)
from atlasquant_trader_macro_event_exposure_v2_lab import (
    build_macro_event_exposure_v2_lab,
)
from atlasquant_trader_official_http_collection_contract_lab import (
    RESPONSE_SCHEMA as HTTP_SCHEMA,
)
from atlasquant_trader_official_rss_capture_lab import (
    SCHEMA as RSS_SCHEMA, SOURCES,
)

SCHEMA = "ATLASQUANT_TRADER_NEWS_PAIR_CONTEXT_LAB_V1"
HORIZONS = ("D1", "W1", "MN1")
ARTICLE_LOOKBACK = {"D1": timedelta(days=1), "W1": timedelta(days=7),
                    "MN1": timedelta(days=30)}
HTTP_STATES = {
    "LAB_DOCUMENTARY_RESPONSE_ACCEPTED_ONLY", "LAB_UNATTESTED_NOT_MODIFIED_CLAIM",
    "LAB_SOURCE_RATE_LIMITED", "LAB_SOURCE_UNAVAILABLE",
    "LAB_REDIRECT_BLOCKED", "LAB_HTTP_STATUS_BLOCKED",
}
HEX24 = re.compile(r"^[0-9a-f]{24}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
SOURCE_BY_CURRENCY = {
    code: tuple(source_id for source_id, src in SOURCES.items()
                if src["currency"] == code)
    for code in CURRENCIES
}


def _clock(raw: Any) -> datetime | None:
    if not isinstance(raw, str) or not 20 <= len(raw) <= 40:
        return None
    try:
        point = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except (TypeError, ValueError, OverflowError):
        return None
    if point.tzinfo is None or point.utcoffset() is None:
        return None
    return point.astimezone(timezone.utc)


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_BLOCKED", "reason": reason,
        "rows": [], "pair_count": 0, "bias_horizons": list(HORIZONS),
        "g8_official_news_coverage_complete": False,
        "source_original_bytes_archived": False,
        "source_identity_independently_verified": False,
        "publication_latency_verified": False,
        "cause_of_currency_strength_verified": False,
        "counterevidence_authenticated": False,
        "economic_calendar_realtime_verified": False,
        "currency_bias_operational": False,
        "can_feed_live_radar": False, "trade_authorized": False,
        "worker_enabled": False, "scheduler_enabled": False,
        "publishable": False, "external_http_requests": 0,
        "new_cost_brl": 0,
    }


def _check_bias_calendar(book: Any, now: datetime) -> bool:
    if not isinstance(book, Mapping):
        return False
    if (book.get("schema") != BIAS_CALENDAR_SCHEMA
            or book.get("state") != "LAB_EXPLANATION_ONLY"
            or _clock(book.get("as_of_utc")) != now
            or book.get("pair_count") != len(OFFICIAL_PAIRS)
            or book.get("bias_horizons") != list(HORIZONS)
            or any(book.get(field) is not False for field in (
                "calendar_complete", "real_sources_attested",
                "live_prices_verified", "source_original_bytes_archived",
                "real_direction_inferred", "can_feed_live_radar",
                "trade_authorized", "worker_enabled", "scheduler_enabled",
                "publishable"))):
        return False
    rows = book.get("rows")
    if (not isinstance(rows, list) or len(rows) != len(OFFICIAL_PAIRS)
            or any(not isinstance(row, Mapping) for row in rows)):
        return False
    seen = set()
    try:
        original_calendar = (
            build_macro_event_exposure_v2_lab(at=now)
            if book.get("calendar_version") == "V2_OFFICIAL_PAGE_REVIEW"
            else build_macro_event_exposure_lab(at=now)
        )
    except ValueError:
        return False
    if (book.get("calendar_version") not in ("V1_20261103", "V2_OFFICIAL_PAGE_REVIEW")
            or book.get("curated_event_count") != original_calendar["curated_event_count"]):
        return False
    original_by_pair = {(r["pair"], r["horizon"]): r
                        for r in original_calendar["fx_rows"]}
    for row in rows:
        pair = row.get("pair")
        if not isinstance(pair, str) or pair not in OFFICIAL_PAIRS or pair in seen:
            return False
        seen.add(pair)
        base, quote = split_pair(pair)
        if (row.get("base") != base or row.get("quote") != quote
                or row.get("trade_authorized") is not False
                or not isinstance(row.get("horizons"), Mapping)
                or set(row["horizons"]) != set(HORIZONS)):
            return False
        for horizon in HORIZONS:
            frame = row["horizons"][horizon]
            if (not isinstance(frame, Mapping)
                    or frame.get("operational_bias") != "AGUARDAR"
                    or frame.get("event_exposure_is_not_direction") is not True
                    or frame.get("no_event_from_partial_calendar_is_not_no_risk") is not True
                    or frame.get("windows_are_rolling_not_price_candles") is not True
                    or not isinstance(frame.get("event_exposures"), list)
                    or frame.get("event_exposures") != original_by_pair[(pair, horizon)]["event_exposures"]
                    or frame.get("event_risk_status") != original_by_pair[(pair, horizon)]["risk_status"]
                    or frame.get("comparison") not in (
                        "DADOS_INCOMPLETOS", "HIPOTESES_SINTETICAS_CONCORDAM",
                        "NEUTRALIDADE_OU_DIVERGENCIA", "CONFLITO_ENTRE_HIPOTESES")):
                return False
    return seen == set(OFFICIAL_PAIRS)


def _article_ok(item: Any, snapshot: Mapping, now: datetime) -> bool:
    if not isinstance(item, Mapping):
        return False
    when = _clock(item.get("publisher_claimed_at_utc"))
    cap = _clock(item.get("captured_at_utc"))
    return (
        isinstance(item.get("id"), str) and HEX24.fullmatch(item["id"]) is not None
        and isinstance(item.get("revision_sha256"), str)
        and HEX64.fullmatch(item["revision_sha256"]) is not None
        and item.get("currency") == snapshot.get("currency")
        and item.get("source_id") == snapshot.get("source_id")
        and item.get("topic") == snapshot.get("topic")
        and item.get("market_direction") == "AGUARDAR"
        and item.get("source_attested") is False
        and cap is not None and cap == _clock(snapshot.get("captured_at_utc"))
        and when is not None and when <= cap + timedelta(minutes=5)
        and isinstance(item.get("title"), str)
        and 2 <= len(item["title"]) <= 240
        and isinstance(item.get("publisher_url"), str)
        and item["publisher_url"].startswith("https://")
        and item["publisher_url"].split("/", 3)[2] == SOURCES[snapshot["source_id"]]["hostname"]
    )


def _check_http_batch(book: Any, now: datetime) -> bool:
    if not isinstance(book, Mapping) or book.get("schema") != HTTP_SCHEMA:
        return False
    source = book.get("source_id")
    if not isinstance(source, str) or source not in SOURCES:
        return False
    if (book.get("state") not in HTTP_STATES
            or book.get("source_feed_url") != SOURCES[source]["feed_url"]
            or book.get("response_is_caller_supplied") is not True
            or any(book.get(field) is not False for field in (
                "source_bytes_authenticity_verified", "response_origin_attested",
                "live_data_verified", "news_current_verified", "live_news",
                "can_feed_live_radar", "trade_authorized", "scheduler_enabled",
                "worker_enabled", "notification_sent"))
            or book.get("currency_bias") != "AGUARDAR"
            or book.get("external_http_requests") != 0
            or book.get("new_cost_brl") != 0):
        return False
    stamp = _clock(book.get("received_at_utc"))
    if stamp is None or stamp > now:
        return False
    state = book["state"]
    code = book.get("status_code")
    if type(code) is not int or not (
        (state == "LAB_DOCUMENTARY_RESPONSE_ACCEPTED_ONLY" and code == 200)
        or (state == "LAB_UNATTESTED_NOT_MODIFIED_CLAIM" and code == 304)
        or (state == "LAB_SOURCE_RATE_LIMITED" and code == 429)
        or (state == "LAB_SOURCE_UNAVAILABLE" and 500 <= code <= 599)
        or (state == "LAB_REDIRECT_BLOCKED" and 300 <= code < 400 and code != 304)
        or (state == "LAB_HTTP_STATUS_BLOCKED" and
            not (code == 200 or code == 304 or code == 429 or 300 <= code < 400 or 500 <= code <= 599))
    ):
        return False
    snap = book.get("snapshot")
    if state != "LAB_DOCUMENTARY_RESPONSE_ACCEPTED_ONLY":
        if snap is not None or book.get("diff") is not None:
            return False
        if state == "LAB_UNATTESTED_NOT_MODIFIED_CLAIM":
            cache = book.get("cache")
            return (isinstance(cache, Mapping)
                    and cache.get("source_id") == source
                    and cache.get("feed_url") == SOURCES[source]["feed_url"]
                    and cache.get("response_origin_attested") is False
                    and cache.get("live_data_verified") is False
                    and isinstance(cache.get("payload_sha256"), str)
                    and HEX64.fullmatch(cache["payload_sha256"]) is not None
                    and cache.get("payload_sha256") == book.get("previous_payload_sha256")
                    and _clock(cache.get("received_at_utc")) is not None
                    and _clock(cache["received_at_utc"]) <= stamp)
        return book.get("cache") is None
    if not isinstance(snap, Mapping):
        return False
    if (snap.get("schema") != RSS_SCHEMA
            or snap.get("state") != "LAB_DOCUMENTARY_NEWS_ITEMS_ONLY"
            or snap.get("source_id") != source
            or snap.get("publisher") != SOURCES[source]["publisher"]
            or snap.get("topic") != SOURCES[source]["topic"]
            or snap.get("feed_url") != SOURCES[source]["feed_url"]
            or snap.get("currency") != SOURCES[source]["currency"]
            or _clock(snap.get("captured_at_utc")) != stamp
            or snap.get("source_bytes_authenticity_verified") is not False
            or snap.get("trade_authorized") is not False
            or snap.get("live_news") is not False
            or not isinstance(snap.get("source_payload_sha256"), str)
            or HEX64.fullmatch(snap["source_payload_sha256"]) is None):
        return False
    items = snap.get("items")
    if (not isinstance(items, list) or len(items) > 100
            or snap.get("item_count") != len(items)):
        return False
    if (any(not _article_ok(item, snap, now) for item in items)
            or len({item["id"] for item in items}) != len(items)):
        return False
    cache = book.get("cache")
    if (not isinstance(cache, Mapping)
            or cache.get("source_id") != source
            or cache.get("payload_sha256") != snap["source_payload_sha256"]
            or cache.get("received_at_utc") != snap["captured_at_utc"]
            or cache.get("response_origin_attested") is not False):
        return False
    return True


def build_news_pair_context_lab(
    bias_calendar: Any, http_batches: Any, *, at: datetime,
) -> dict[str, Any]:
    """Join 28x3 calendar/bias hypotheses to official-news documentary leads."""
    if not isinstance(at, datetime) or at.tzinfo is None or at.utcoffset() is None:
        raise ValueError("Timezone-aware evaluation required")
    now = at.astimezone(timezone.utc)
    if not _check_bias_calendar(bias_calendar, now):
        return _blocked("BIAS_CALENDAR_NOT_VALIDATED_LAB_EXPLANATION")
    if (not isinstance(http_batches, (list, tuple))
            or len(http_batches) > len(SOURCES)):
        return _blocked("UNBOUNDED_OR_MISSING_HTTP_BATCHES")
    feed_by_source = {}
    for batch in http_batches:
        if not _check_http_batch(batch, now):
            return _blocked("UNTRUSTED_OR_FORGED_HTTP_BATCH")
        source_id = batch["source_id"]
        if source_id in feed_by_source:
            return _blocked("DUPLICATE_OFFICIAL_NEWS_SOURCE")
        feed_by_source[source_id] = batch

    currency_news = {}
    for currency in CURRENCIES:
        expected = SOURCE_BY_CURRENCY[currency]
        observed = [feed_by_source[source] for source in expected
                    if source in feed_by_source]
        articles = []
        for batch in observed:
            if batch["state"] != "LAB_DOCUMENTARY_RESPONSE_ACCEPTED_ONLY":
                continue
            for item in batch["snapshot"]["items"]:
                articles.append({
                    "source_id": item["source_id"],
                    "topic": item["topic"], "article_id": item["id"],
                    "title_claimed": item["title"],
                    "official_url_claimed": item["publisher_url"],
                    "publisher_claimed_at_utc": item["publisher_claimed_at_utc"],
                    "captured_at_utc": item["captured_at_utc"],
                    "revision_sha256": item["revision_sha256"],
                    "source_origin_verified": False,
                    "directional_inference": "AGUARDAR",
                })
        articles.sort(key=lambda x: (x["publisher_claimed_at_utc"], x["article_id"]),
                      reverse=True)
        currency_news[currency] = {
            "currency": currency,
            "pilot_source_count": len(expected),
            "supplied_source_count": len(observed),
            "missing_pilot_sources": sorted(set(expected) - set(feed_by_source)),
            "source_states": {b["source_id"]: b["state"] for b in observed},
            "articles": articles,
            "news_coverage_complete": False,
            "currency_strength_explained": False,
            "contradictions_checked": False,
        }

    output_rows = []
    by_pair = {r["pair"]: r for r in bias_calendar["rows"]}
    for pair in OFFICIAL_PAIRS:
        base, quote = split_pair(pair)
        combined = by_pair[pair]
        horizon_records = {}
        for horizon in HORIZONS:
            earliest = now - ARTICLE_LOOKBACK[horizon]
            snippets = []
            for currency in (base, quote):
                for article in currency_news[currency]["articles"]:
                    published = _clock(article["publisher_claimed_at_utc"])
                    if published is not None and earliest <= published <= now:
                        snippets.append({"currency": currency, **deepcopy(article)})
            snippets.sort(key=lambda x: (x["publisher_claimed_at_utc"],
                                        x["article_id"]), reverse=True)
            old = combined["horizons"][horizon]
            horizon_records[horizon] = {
                "documentary_news_window": "TRAILING_" + horizon,
                "news_articles_from_supplied_feeds": snippets,
                "news_article_count": len(snippets),
                "macro_vs_relative_comparison_synthetic": old["comparison"],
                "calendar_risk_status_documentary": old["event_risk_status"],
                "event_exposures_documentary": deepcopy(old["event_exposures"]),
                "base_currency_strength_reason": "NAO_COMPROVADO",
                "quote_currency_strength_reason": "NAO_COMPROVADO",
                "counterevidence": "NAO_AUTENTICADA",
                "missing_core_validations": [
                    "MACRO_MICRO_GEOPOLITICA_VERIFICADOS",
                    "CALENDARIO_ATUALIZADO_COM_CUSTODIA",
                    "NOTICIAS_FONTE_E_LATENCIA_AUTENTICADAS",
                    "FORCA_RELATIVA_CAMBIAL_INDEPENDENTE",
                    "CALIBRACAO_OOS_SEM_VAZAMENTO_TEMPORAL",
                ],
                "news_not_proof_of_currency_direction": True,
                "trailing_news_window_not_candle_forecast": True,
                "operational_bias": "AGUARDAR",
            }
        output_rows.append({
            "pair": pair, "base": base, "quote": quote,
            "official_news_pilot_source_status": {
                base: {"expected_leads": currency_news[base]["pilot_source_count"],
                       "supplied_leads": currency_news[base]["supplied_source_count"]},
                quote: {"expected_leads": currency_news[quote]["pilot_source_count"],
                        "supplied_leads": currency_news[quote]["supplied_source_count"]},
            },
            "horizons": horizon_records,
            "trade_authorized": False,
        })
    result = _blocked("NO_ATTESTED_CAUSAL_FX_STRENGTH_OR_FULL_G8_NEWS")
    result.update({
        "state": "LAB_NEWS_CONTEXT_FOR_REVIEW_ONLY",
        "as_of_utc": now.isoformat(),
        "rows": output_rows, "pair_count": len(output_rows),
        "currency_count": len(currency_news),
        "currency_news_coverage": currency_news,
        "supplied_official_news_sources": sorted(feed_by_source),
        "source_leads_are_not_full_coverage": True,
        "news_lookbacks_are_not_D1_W1_MN1_price_periods": True,
        "note": ("Noticia em RSS pode motivar investigacao causal, mas nao "
                 "comprova motivo da forca/fraqueza ou direcao de 28 pares. "
                 "Nenhuma rotina diaria executada; 3 janelas continuam planejadas."),
    })
    return result


__all__ = ["SCHEMA", "HORIZONS", "build_news_pair_context_lab"]
