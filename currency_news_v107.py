"""USD Macro Pro V10.7 — Full Autopilot News Layer.

Analisa notícias macroeconômicas e de bancos centrais para:
USD, EUR, GBP, JPY, CHF, CAD, AUD e NZD.

Objetivos:
- separar notícia relevante de ruído;
- classificar tema (banco central, inflação, emprego, crescimento, intervenção,
  commodities e risco);
- aplicar peso de relevância, fonte e frescor;
- evitar duplicidade de manchetes;
- gerar viés de notícias por moeda;
- comparar as duas moedas de cada par;
- medir se a camada de notícias CONFIRMA ou CONFLITA com o motor macro atual.

IMPORTANTE:
Esta versão continua OBSERVACIONAL. Ela NÃO altera Score Mestre, Gate, pesos, Market Map
ou histórico oficial. A V10.7 corrige integridade temporal, aceita estado do Autopilot
e mantém os botões manuais apenas como plano B.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from typing import Any, Mapping
import base64
import io
import json
import math
import os
import re
import time
import urllib.parse
import xml.etree.ElementTree as ET

import numpy as np
import pandas as pd
import requests
import streamlit as st


CURRENCY_PROFILES = {
    "USD": {
        "name": "Dólar Americano",
        "bank": "Federal Reserve",
        "official_url": "https://www.federalreserve.gov/",
        "aliases": (
            "usd", "dollar", "u.s. dollar", "us dollar", "united states",
            "federal reserve", "fomc", "fed", "treasury"
        ),
        "bank_aliases": ("federal reserve", "fomc", "fed chair", "fed governor"),
        "queries": (
            '("Federal Reserve" OR FOMC OR "US inflation" OR "US jobs" OR Treasury) dollar when:7d',
            '("US CPI" OR payroll OR unemployment OR "US GDP" OR "Fed rate") dollar when:7d',
        ),
        "commodity": None,
    },
    "EUR": {
        "name": "Euro",
        "bank": "Banco Central Europeu",
        "official_url": "https://www.ecb.europa.eu/",
        "aliases": (
            "eur", "euro", "eurozone", "euro area", "european central bank",
            "ecb", "eurostat"
        ),
        "bank_aliases": ("european central bank", "ecb", "lagarde"),
        "queries": (
            '("European Central Bank" OR ECB OR Eurozone inflation OR Eurostat) euro when:7d',
            '(Eurozone PMI OR "euro area growth" OR "ECB rates" OR "euro area jobs") euro when:7d',
        ),
        "commodity": None,
    },
    "GBP": {
        "name": "Libra Esterlina",
        "bank": "Bank of England",
        "official_url": "https://www.bankofengland.co.uk/",
        "aliases": (
            "gbp", "pound", "pound sterling", "sterling", "united kingdom",
            "uk economy", "bank of england", "boe", "ons"
        ),
        "bank_aliases": ("bank of england", "boe", "bailey"),
        "queries": (
            '("Bank of England" OR BoE OR "UK inflation" OR ONS) sterling when:7d',
            '("UK jobs" OR "UK GDP" OR "UK wages" OR "BoE rates") pound when:7d',
        ),
        "commodity": None,
    },
    "JPY": {
        "name": "Iene Japonês",
        "bank": "Bank of Japan",
        "official_url": "https://www.boj.or.jp/en/",
        "aliases": (
            "jpy", "yen", "japanese yen", "japan", "bank of japan", "boj",
            "ministry of finance japan"
        ),
        "bank_aliases": ("bank of japan", "boj", "ueda"),
        "queries": (
            '("Bank of Japan" OR BoJ OR "Japan inflation" OR "Japan wages") yen when:7d',
            '("yen intervention" OR "Japan GDP" OR "BoJ rates" OR "Japan economy") yen when:7d',
        ),
        "commodity": "safe_haven",
    },
    "CHF": {
        "name": "Franco Suíço",
        "bank": "Swiss National Bank",
        "official_url": "https://www.snb.ch/en/",
        "aliases": (
            "chf", "swiss franc", "franc", "switzerland", "swiss national bank",
            "snb", "swiss inflation"
        ),
        "bank_aliases": ("swiss national bank", "snb", "schlegel"),
        "queries": (
            '("Swiss National Bank" OR SNB OR "Swiss inflation") franc when:7d',
            '("Switzerland GDP" OR "SNB rates" OR "Swiss economy" OR "franc intervention") when:7d',
        ),
        "commodity": "safe_haven",
    },
    "CAD": {
        "name": "Dólar Canadense",
        "bank": "Bank of Canada",
        "official_url": "https://www.bankofcanada.ca/",
        "aliases": (
            "cad", "canadian dollar", "canada", "bank of canada", "boc",
            "statistics canada", "loonie"
        ),
        "bank_aliases": ("bank of canada", "boc", "macklem"),
        "queries": (
            '("Bank of Canada" OR BoC OR "Canada inflation" OR "Canada jobs") "Canadian dollar" when:7d',
            '("Canada GDP" OR "BoC rates" OR oil OR crude) "Canadian dollar" when:7d',
        ),
        "commodity": "oil",
    },
    "AUD": {
        "name": "Dólar Australiano",
        "bank": "Reserve Bank of Australia",
        "official_url": "https://www.rba.gov.au/",
        "aliases": (
            "aud", "australian dollar", "australia", "reserve bank of australia",
            "rba", "australian bureau of statistics", "aussie"
        ),
        "bank_aliases": ("reserve bank of australia", "rba", "bullock"),
        "queries": (
            '("Reserve Bank of Australia" OR RBA OR "Australia inflation" OR "Australia jobs") "Australian dollar" when:7d',
            '("Australia GDP" OR China OR "iron ore" OR "RBA rates") "Australian dollar" when:7d',
        ),
        "commodity": "china_iron",
    },
    "NZD": {
        "name": "Dólar Neozelandês",
        "bank": "Reserve Bank of New Zealand",
        "official_url": "https://www.rbnz.govt.nz/",
        "aliases": (
            "nzd", "new zealand dollar", "new zealand", "reserve bank of new zealand",
            "rbnz", "stats nz", "kiwi"
        ),
        "bank_aliases": ("reserve bank of new zealand", "rbnz"),
        "queries": (
            '("Reserve Bank of New Zealand" OR RBNZ OR "New Zealand inflation" OR "New Zealand jobs") "New Zealand dollar" when:7d',
            '("New Zealand GDP" OR dairy OR China OR "RBNZ rates") kiwi when:7d',
        ),
        "commodity": "dairy_china",
    },
}

PAIR_ORDER = ("EUR/USD", "GBP/USD", "AUD/USD", "NZD/USD", "USD/JPY", "USD/CHF", "USD/CAD")

HIGH_TOPICS = (
    "interest rate", "interest rates", "rate hike", "rate cut", "rates",
    "monetary policy", "inflation", "cpi", "pce", "employment", "jobs",
    "unemployment", "payroll", "wages", "gdp", "growth", "pmi",
    "retail sales", "trade balance", "intervention", "currency intervention"
)
MEDIUM_TOPICS = (
    "economy", "economic", "consumer", "business", "manufacturing", "services",
    "housing", "exports", "imports", "yield", "yields", "bond", "bonds"
)
IRRELEVANT = (
    "football", "soccer", "rugby", "baseball", "basketball", "celebrity",
    "movie", "music", "travel money", "holiday money", "best exchange rate",
    "crypto casino", "online casino", "lottery"
)

HAWKISH = (
    "hawkish", "rate hike", "rate hikes", "hike rates", "raise rates",
    "higher for longer", "tightening", "restrictive", "rates stay high",
    "not ready to cut", "delay rate cuts", "fewer rate cuts",
    "less likely to cut", "inflation remains elevated", "sticky inflation"
)
DOVISH = (
    "dovish", "rate cut", "rate cuts", "cut rates", "lower rates", "easing",
    "more rate cuts", "ready to cut", "inflation cooling", "disinflation",
    "growth slowing", "weaker labor", "recession risk"
)

MACRO_POS = (
    "stronger than expected", "beats expectations", "beat expectations",
    "above expectations", "growth accelerates", "economy accelerates",
    "gdp expands", "employment rises", "jobs growth", "jobs beat",
    "unemployment falls", "wages rise", "retail sales rise", "pmi rises",
    "robust economy", "resilient economy"
)
MACRO_NEG = (
    "weaker than expected", "misses expectations", "missed expectations",
    "below expectations", "growth slows", "economy slows", "gdp contracts",
    "employment falls", "jobs miss", "unemployment rises", "wages fall",
    "retail sales fall", "pmi falls", "recession", "downturn"
)

INFLATION_HOT = (
    "inflation rises", "inflation accelerates", "inflation hotter",
    "hot inflation", "price pressures rise", "inflation above expectations"
)
INFLATION_COOL = (
    "inflation falls", "inflation slows", "inflation cools",
    "inflation below expectations", "price pressures ease", "disinflation"
)

RISK_OFF = (
    "risk-off", "risk aversion", "market turmoil", "geopolitical tensions",
    "war fears", "flight to safety", "safe haven demand"
)
RISK_ON = (
    "risk-on", "risk appetite", "global stocks rally", "risk sentiment improves"
)

OFFICIAL_TERMS = (
    "federal reserve", "european central bank", "bank of england", "bank of japan",
    "swiss national bank", "bank of canada", "reserve bank of australia",
    "reserve bank of new zealand", "eurostat", "office for national statistics",
    "statistics canada", "australian bureau of statistics", "stats nz",
    "bureau of labor statistics", "bureau of economic analysis"
)
PREMIUM_MEDIA = (
    "reuters", "bloomberg", "financial times", "wall street journal",
    "associated press", "cnbc", "nikkei", "marketwatch"
)
LOWER_TRUST = (
    "blog", "substack", "youtube", "medium", "seeking alpha"
)

STOPWORDS = {
    "the", "a", "an", "and", "or", "to", "of", "in", "on", "for", "with",
    "as", "at", "by", "from", "is", "are", "was", "were", "be", "after",
    "before", "over", "under", "amid", "says", "say", "could", "may", "will"
}


def _norm_text(text: str) -> str:
    t = str(text or "").lower()
    t = re.sub(r"\s+-\s+[^-]{2,80}$", "", t)
    t = re.sub(r"[^a-z0-9% ]+", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def _tokens(text: str) -> set[str]:
    return {x for x in _norm_text(text).split() if len(x) > 2 and x not in STOPWORDS}


def _jaccard(a: str, b: str) -> float:
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / max(1, len(ta | tb))


def _source_factor(source: str) -> float:
    s = _norm_text(source)
    if any(x in s for x in OFFICIAL_TERMS):
        return 1.35
    if any(x in s for x in PREMIUM_MEDIA):
        return 1.15
    if any(x in s for x in LOWER_TRUST):
        return 0.70
    return 1.00


def _parse_date(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    try:
        if isinstance(value, datetime):
            dt = value
        else:
            txt = str(value)
            try:
                dt = parsedate_to_datetime(txt)
            except Exception:
                dt = pd.Timestamp(txt).to_pydatetime()
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def _age_hours(value: Any) -> float | None:
    dt = _parse_date(value)
    if dt is None:
        return None
    return max(0.0, (datetime.now(timezone.utc) - dt).total_seconds() / 3600.0)


def _recency_factor(value: Any) -> float:
    age = _age_hours(value)
    if age is None:
        return 0.55
    if age <= 12:
        return 1.00
    if age <= 24:
        return 0.92
    if age <= 48:
        return 0.78
    if age <= 96:
        return 0.58
    if age <= 168:
        return 0.38
    return 0.20


def _contains_any(text: str, terms) -> int:
    t = _norm_text(text)
    return sum(1 for x in terms if x in t)


def _rss_items(query: str, timeout: int = 10) -> list[dict[str, Any]]:
    q = urllib.parse.quote(query)
    url = f"https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en"
    try:
        r = requests.get(url, timeout=timeout, headers={"User-Agent": "USD-Macro-Pro/10.6"})
        r.raise_for_status()
        root = ET.fromstring(r.content)
        out = []
        for item in root.iter("item"):
            title = (item.findtext("title", "") or "").strip()
            pub = (item.findtext("pubDate", "") or "").strip()
            link = (item.findtext("link", "") or "").strip()
            src_node = item.find("source")
            source = (src_node.text or "").strip() if src_node is not None and src_node.text else ""
            if not source and " - " in title:
                source = title.rsplit(" - ", 1)[-1].strip()
            if title:
                out.append({
                    "title": title,
                    "published_at": pub,
                    "source": source or "Fonte não identificada",
                    "link": link,
                    "provider": "Google News RSS",
                })
        return out
    except Exception:
        return []


def _newsapi_items(profile: Mapping[str, Any], api_key: str) -> list[dict[str, Any]]:
    if not api_key:
        return []
    try:
        query = f'"{profile["bank"]}" OR "{profile["name"]}"'
        since = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d")
        r = requests.get(
            "https://newsapi.org/v2/everything",
            params={
                "q": query,
                "language": "en",
                "from": since,
                "sortBy": "publishedAt",
                "pageSize": 30,
                "apiKey": api_key,
            },
            timeout=12,
            headers={"User-Agent": "USD-Macro-Pro/10.6"},
        )
        if not r.ok:
            return []
        out = []
        for article in r.json().get("articles", []):
            title = str(article.get("title", "") or "").strip()
            if not title:
                continue
            out.append({
                "title": title,
                "published_at": article.get("publishedAt", ""),
                "source": str((article.get("source") or {}).get("name", "") or "NewsAPI"),
                "link": str(article.get("url", "") or ""),
                "provider": "NewsAPI",
            })
        return out
    except Exception:
        return []


def _dedupe(items: list[dict[str, Any]], max_items: int = 35) -> list[dict[str, Any]]:
    # Prefer fresher / better source copies of essentially the same story.
    enriched = []
    for x in items:
        item = dict(x)
        item["_source_factor"] = _source_factor(item.get("source", ""))
        age = _age_hours(item.get("published_at"))
        item["_age"] = 9999.0 if age is None else age
        enriched.append(item)
    enriched.sort(key=lambda x: (x["_age"], -x["_source_factor"]))

    kept: list[dict[str, Any]] = []
    for item in enriched:
        title = item.get("title", "")
        if any(_jaccard(title, old.get("title", "")) >= 0.80 for old in kept):
            continue
        kept.append(item)
        if len(kept) >= max_items:
            break
    for item in kept:
        item.pop("_source_factor", None)
        item.pop("_age", None)
    return kept


def _relevance(currency: str, title: str) -> tuple[float, str]:
    profile = CURRENCY_PROFILES[currency]
    t = _norm_text(title)
    if any(x in t for x in IRRELEVANT):
        return 0.0, "Baixa"

    entity = sum(1 for x in profile["aliases"] if x in t)
    bank = sum(1 for x in profile["bank_aliases"] if x in t)
    high = sum(1 for x in HIGH_TOPICS if x in t)
    medium = sum(1 for x in MEDIUM_TOPICS if x in t)

    points = min(12.0, entity * 1.5 + bank * 2.0 + high * 1.4 + medium * 0.35)
    if points >= 5.0:
        return points, "Alta"
    if points >= 2.6:
        return points, "Média"
    return points, "Baixa"


def _theme(title: str, currency: str) -> str:
    t = _norm_text(title)
    profile = CURRENCY_PROFILES[currency]
    if "intervention" in t or "intervene" in t:
        return "Intervenção cambial"
    if any(x in t for x in profile["bank_aliases"]) or "rate " in t or "rates " in t or "monetary policy" in t:
        return "Banco central / juros"
    if "inflation" in t or "cpi" in t or "pce" in t or "prices" in t:
        return "Inflação"
    if "jobs" in t or "employment" in t or "unemployment" in t or "wages" in t or "payroll" in t:
        return "Emprego"
    if "gdp" in t or "growth" in t or "pmi" in t or "retail sales" in t:
        return "Crescimento"
    if any(x in t for x in ("oil", "crude", "iron ore", "dairy", "china")):
        return "Commodities / China"
    if any(x in t for x in RISK_OFF + RISK_ON):
        return "Risco global"
    return "Macro geral"


def _specific_adjustment(currency: str, title: str) -> tuple[float, str]:
    t = _norm_text(title)
    mode = CURRENCY_PROFILES[currency].get("commodity")

    if currency == "JPY" and ("intervention" in t or "intervene" in t):
        if any(x in t for x in ("support yen", "buy yen", "strengthen yen", "defend yen")):
            return 0.85, "Intervenção descrita como suporte ao iene."
        if any(x in t for x in ("weaken yen", "sell yen")):
            return -0.75, "Intervenção descrita como pressão sobre o iene."

    if currency == "CHF" and ("intervention" in t or "intervene" in t):
        if any(x in t for x in ("weaken franc", "sell franc", "curb franc strength")):
            return -0.80, "Ação para enfraquecer o franco."
        if any(x in t for x in ("support franc", "buy franc", "strengthen franc")):
            return 0.70, "Ação descrita como suporte ao franco."

    if mode == "oil":
        if "oil" in t or "crude" in t:
            if any(x in t for x in ("oil rises", "oil climbs", "crude rises", "oil rally", "oil gains")):
                return 0.25, "Petróleo mais forte tende a ajudar o CAD."
            if any(x in t for x in ("oil falls", "oil drops", "crude falls", "oil selloff", "oil slides")):
                return -0.25, "Petróleo mais fraco tende a pesar no CAD."

    if mode == "china_iron":
        if any(x in t for x in ("china stimulus", "china growth accelerates", "iron ore rises", "iron ore rally")):
            return 0.22, "China/commodities mais fortes tendem a apoiar o AUD."
        if any(x in t for x in ("china slowdown", "china growth slows", "iron ore falls", "iron ore drops")):
            return -0.22, "China/commodities mais fracas tendem a pesar no AUD."

    if mode == "dairy_china":
        if any(x in t for x in ("dairy prices rise", "dairy auction rises", "china stimulus", "china demand rises")):
            return 0.22, "Demanda/commodities mais fortes tendem a apoiar o NZD."
        if any(x in t for x in ("dairy prices fall", "dairy auction falls", "china slowdown", "china demand falls")):
            return -0.22, "Demanda/commodities mais fracas tendem a pesar no NZD."

    if mode == "safe_haven":
        if any(x in t for x in RISK_OFF):
            return 0.16, "Aversão a risco pode favorecer moeda de refúgio."
        if any(x in t for x in RISK_ON):
            return -0.10, "Apetite por risco pode reduzir demanda defensiva."

    return 0.0, ""


def _headline_impact(currency: str, title: str) -> tuple[float, str, str]:
    t = _norm_text(title)
    hawk = _contains_any(t, HAWKISH)
    dove = _contains_any(t, DOVISH)
    pos = _contains_any(t, MACRO_POS)
    neg = _contains_any(t, MACRO_NEG)
    hot = _contains_any(t, INFLATION_HOT)
    cool = _contains_any(t, INFLATION_COOL)

    raw = 0.0
    reasons = []

    if hawk or dove:
        delta = 0.42 * (hawk - dove)
        raw += delta
        if delta > 0:
            reasons.append("tom mais hawkish / juros altos por mais tempo")
        elif delta < 0:
            reasons.append("tom mais dovish / maior chance de cortes")

    if pos or neg:
        delta = 0.18 * (pos - neg)
        raw += delta
        if delta > 0:
            reasons.append("atividade/emprego mais fortes")
        elif delta < 0:
            reasons.append("atividade/emprego mais fracos")

    # Hot/cool inflation only receives meaningful direction when rates/central bank are in context.
    rate_context = (
        any(x in t for x in CURRENCY_PROFILES[currency]["bank_aliases"])
        or "rate" in t or "monetary policy" in t
    )
    if hot or cool:
        mult = 0.20 if rate_context else 0.08
        delta = mult * (hot - cool)
        raw += delta
        if delta > 0:
            reasons.append("inflação mais quente pode elevar expectativa de juros")
        elif delta < 0:
            reasons.append("inflação mais fria pode reduzir expectativa de juros")

    special, special_reason = _specific_adjustment(currency, title)
    raw += special
    if special_reason:
        reasons.append(special_reason)

    raw = float(np.clip(raw, -1.0, 1.0))
    if raw > 0.12:
        direction = "🟢 Fortalece"
    elif raw < -0.12:
        direction = "🔴 Enfraquece"
    else:
        direction = "⚪ Neutro"

    explanation = "; ".join(reasons[:2]) if reasons else "Sem direção macro clara na manchete."
    return raw, direction, explanation



def _collect_one_currency(currency: str, newsapi_key: str = "") -> list[dict[str, Any]]:
    """Collects and locally deduplicates raw stories for one currency."""
    profile = CURRENCY_PROFILES[currency]
    items: list[dict[str, Any]] = []
    for query in profile["queries"]:
        items.extend(_rss_items(query))

    # NewsAPI stays fallback-only to avoid multiplying the same story.
    if len(items) < 4 and newsapi_key:
        items.extend(_newsapi_items(profile, newsapi_key))

    return _dedupe(items, max_items=28)


def _assign_global_story_clusters(
    raw_by_currency: Mapping[str, list[dict[str, Any]]],
    threshold: float = 0.76,
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    """Clusters similar headlines ACROSS currencies.

    One global story can legitimately matter to more than one currency. Instead of deleting
    it from the second currency, the V10.6.1 applies an independence penalty:
    1 / sqrt(number of currencies sharing the same story).
    """
    flat: list[dict[str, Any]] = []
    for currency, items in raw_by_currency.items():
        for item in items:
            row = dict(item)
            row["_currency"] = currency
            row["_age_sort"] = _age_hours(row.get("published_at"))
            if row["_age_sort"] is None:
                row["_age_sort"] = 9999.0
            row["_source_sort"] = _source_factor(row.get("source", ""))
            flat.append(row)

    flat.sort(key=lambda x: (x["_age_sort"], -x["_source_sort"]))

    clusters: list[dict[str, Any]] = []
    for row in flat:
        title = row.get("title", "")
        best_idx, best_sim = None, 0.0
        for idx, cluster in enumerate(clusters):
            sim = _jaccard(title, cluster["representative"])
            if sim > best_sim:
                best_idx, best_sim = idx, sim
        if best_idx is not None and best_sim >= threshold:
            clusters[best_idx]["items"].append(row)
            clusters[best_idx]["currencies"].add(row["_currency"])
        else:
            clusters.append({
                "representative": title,
                "items": [row],
                "currencies": {row["_currency"]},
            })

    clustered: dict[str, list[dict[str, Any]]] = {c: [] for c in CURRENCY_PROFILES}
    shared_clusters = 0
    for idx, cluster in enumerate(clusters, start=1):
        story_id = f"S{idx:04d}"
        currencies = sorted(cluster["currencies"])
        shared_count = max(1, len(currencies))
        if shared_count > 1:
            shared_clusters += 1
        independence = 1.0 / math.sqrt(shared_count)

        for raw in cluster["items"]:
            row = {k: v for k, v in raw.items() if not str(k).startswith("_")}
            row["story_id"] = story_id
            row["shared_currency_count"] = shared_count
            row["shared_currencies"] = ", ".join(currencies)
            row["independence_factor"] = float(independence)
            clustered[raw["_currency"]].append(row)

    meta = {
        "global_unique_stories": len(clusters),
        "global_shared_stories": shared_clusters,
        "raw_currency_mentions": len(flat),
        "shared_story_ratio": (shared_clusters / len(clusters)) if clusters else 0.0,
    }
    return clustered, meta


def analyze_articles(currency: str, items: list[dict[str, Any]]) -> dict[str, Any]:
    analyzed = []
    raw_relevant_count = 0

    for item in _dedupe(items, max_items=28):
        rel_points, rel_level = _relevance(currency, item.get("title", ""))
        if rel_level == "Baixa":
            continue
        raw_relevant_count += 1

        raw_impact, direction, explanation = _headline_impact(currency, item.get("title", ""))
        recency = _recency_factor(item.get("published_at"))
        source_factor = _source_factor(item.get("source", ""))
        rel_factor = min(1.0, rel_points / 8.0)
        independence_factor = float(np.clip(item.get("independence_factor", 1.0) or 1.0, 0.30, 1.0))

        weighted_impact = float(np.clip(
            raw_impact * recency * source_factor * rel_factor * independence_factor,
            -1.0, 1.0
        ))
        age = _age_hours(item.get("published_at"))
        analyzed.append({
            **item,
            "relevance_points": float(rel_points),
            "relevance": rel_level,
            "theme": _theme(item.get("title", ""), currency),
            "raw_impact": float(raw_impact),
            "weighted_impact": weighted_impact,
            "direction": direction,
            "explanation": explanation,
            "recency_factor": float(recency),
            "source_factor": float(source_factor),
            "independence_factor": independence_factor,
            "age_hours": age,
        })

    analyzed.sort(
        key=lambda x: (
            x["relevance_points"]
            * x["recency_factor"]
            * x["source_factor"]
            * x["independence_factor"],
            abs(x["weighted_impact"])
        ),
        reverse=True,
    )
    analyzed = analyzed[:12]

    directional = [x for x in analyzed if abs(x["weighted_impact"]) >= 0.035]
    if directional:
        weights = np.array([
            max(0.2, x["relevance_points"] / 4.0)
            * x["recency_factor"]
            * x["source_factor"]
            * x["independence_factor"]
            for x in directional
        ], dtype=float)
        impacts = np.array([x["weighted_impact"] for x in directional], dtype=float)
        avg_impact = float(np.average(impacts, weights=weights))
        # Slightly more conservative than V10.6.
        net = float(np.clip(avg_impact * 9.0, -9.0, 9.0))
        agreement = float(np.clip(
            abs(np.sum(impacts * weights)) / max(np.sum(abs(impacts) * weights), 1e-9),
            0, 1
        ))
    else:
        net = 0.0
        agreement = 0.0

    sources = {
        str(x.get("source", "")).strip().lower()
        for x in analyzed if str(x.get("source", "")).strip()
    }
    fresh_avg = float(np.mean([x["recency_factor"] for x in analyzed])) if analyzed else 0.0
    effective_independent = float(sum(x.get("independence_factor", 1.0) for x in analyzed))
    shared_count = sum(1 for x in analyzed if int(x.get("shared_currency_count", 1) or 1) > 1)
    shared_ratio = (shared_count / len(analyzed)) if analyzed else 0.0

    coverage_factor = min(1.0, effective_independent / 8.0)
    diversity_factor = min(1.0, len(sources) / 5.0)
    source_quality = (
        float(np.mean([min(1.0, x["source_factor"] / 1.35) for x in analyzed]))
        if analyzed else 0.0
    )

    # Coverage answers: "do we have enough independent/fresh/diverse evidence?"
    coverage_quality = float(np.clip(
        100 * (
            0.40 * coverage_factor
            + 0.25 * diversity_factor
            + 0.25 * fresh_avg
            + 0.10 * source_quality
        ),
        0, 92
    ))

    # Directional conviction answers: "does the evidence agree on a direction?"
    # It is explicitly NOT a calibrated probability.
    signal_strength = min(1.0, abs(net) / 6.0)
    independence_quality = min(1.0, effective_independent / 6.0)
    directional_confidence = float(np.clip(
        100 * (
            0.40 * agreement
            + 0.30 * signal_strength
            + 0.15 * independence_quality
            + 0.15 * fresh_avg
        ),
        0, 90
    ))
    if abs(net) < 1.0:
        directional_confidence = min(directional_confidence, 55.0)

    news_score = float(np.clip(50.0 + net * 4.0, 10, 90))
    if net >= 2.0:
        bias = "🟢 FORTALECE"
    elif net <= -2.0:
        bias = "🔴 ENFRAQUECE"
    else:
        bias = "⚪ NEUTRO"

    theme_counts = {}
    for x in analyzed:
        theme_counts[x["theme"]] = theme_counts.get(x["theme"], 0) + 1
    top_theme = max(theme_counts, key=theme_counts.get) if theme_counts else "Sem tema dominante"

    return {
        "currency": currency,
        "name": CURRENCY_PROFILES[currency]["name"],
        "bank": CURRENCY_PROFILES[currency]["bank"],
        "official_url": CURRENCY_PROFILES[currency]["official_url"],
        "net_impact": net,
        "news_score": news_score,
        "bias": bias,
        "coverage_quality": coverage_quality,
        "directional_confidence": directional_confidence,
        "article_count": len(analyzed),
        "raw_relevant_count": raw_relevant_count,
        "effective_independent_stories": effective_independent,
        "shared_story_ratio": shared_ratio,
        "source_count": len(sources),
        "top_theme": top_theme,
        "articles": analyzed,
    }


@st.cache_data(ttl=1800, show_spinner=False)
def load_currency_news_intelligence(newsapi_key: str = "") -> dict[str, Any]:
    raw_by_currency: dict[str, list[dict[str, Any]]] = {}

    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {
            pool.submit(_collect_one_currency, currency, newsapi_key): currency
            for currency in CURRENCY_PROFILES
        }
        for future in as_completed(futures):
            currency = futures[future]
            try:
                raw_by_currency[currency] = future.result()
            except Exception:
                raw_by_currency[currency] = []

    clustered, cluster_meta = _assign_global_story_clusters(raw_by_currency)

    results = {}
    for currency in CURRENCY_PROFILES:
        try:
            results[currency] = analyze_articles(currency, clustered.get(currency, []))
        except Exception as exc:
            results[currency] = {
                "currency": currency,
                "name": CURRENCY_PROFILES[currency]["name"],
                "bank": CURRENCY_PROFILES[currency]["bank"],
                "official_url": CURRENCY_PROFILES[currency]["official_url"],
                "net_impact": 0.0,
                "news_score": 50.0,
                "bias": "⚪ NEUTRO",
                "coverage_quality": 0.0,
                "directional_confidence": 0.0,
                "article_count": 0,
                "raw_relevant_count": 0,
                "effective_independent_stories": 0.0,
                "shared_story_ratio": 0.0,
                "source_count": 0,
                "top_theme": "Erro de análise",
                "articles": [],
                "error": f"{type(exc).__name__}: {exc}",
            }

    return {
        "updated_at": pd.Timestamp.now(tz="UTC").isoformat(),
        "currencies": results,
        **cluster_meta,
    }


def pair_news_table(
    intelligence: Mapping[str, Any],
    matrix: pd.DataFrame | None = None,
) -> pd.DataFrame:
    currencies = dict(intelligence.get("currencies", {}) or {})
    matrix_map = {}
    if matrix is not None and not matrix.empty and "Par" in matrix.columns:
        for _, row in matrix.iterrows():
            matrix_map[str(row.get("Par", ""))] = str(row.get("Direção", row.get("Direcao", "")))

    rows = []
    for pair in PAIR_ORDER:
        base, quote = pair.split("/")
        b = currencies.get(base, {})
        q = currencies.get(quote, {})
        base_net = float(b.get("net_impact", 0.0) or 0.0)
        quote_net = float(q.get("net_impact", 0.0) or 0.0)
        diff = float(np.clip(base_net - quote_net, -18.0, 18.0))

        if diff >= 2.0:
            news_label = "🟢 COMPRA"
            news_side = "BUY"
        elif diff <= -2.0:
            news_label = "🔴 VENDA"
            news_side = "SELL"
        else:
            news_label = "⚪ NEUTRO"
            news_side = "NEUTRAL"

        motor = matrix_map.get(pair, "—")
        motor_upper = motor.upper()
        if "COMPRA" in motor_upper:
            motor_side = "BUY"
        elif "VENDA" in motor_upper:
            motor_side = "SELL"
        else:
            motor_side = "WAIT"

        if motor_side == "WAIT":
            alignment = "⚪ OBSERVAÇÃO"
        elif news_side == "NEUTRAL":
            alignment = "⚪ NEUTRO"
        elif motor_side == news_side:
            alignment = "🟢 CONFIRMA"
        else:
            alignment = "🔴 CONFLITA"

        coverage = min(
            float(b.get("coverage_quality", 0.0) or 0.0),
            float(q.get("coverage_quality", 0.0) or 0.0),
        )
        avg_directional = (
            float(b.get("directional_confidence", 0.0) or 0.0)
            + float(q.get("directional_confidence", 0.0) or 0.0)
        ) / 2.0
        pair_conviction = float(np.clip(
            avg_directional * min(1.0, abs(diff) / 4.0),
            0, 90
        ))
        independent = (
            float(b.get("effective_independent_stories", 0.0) or 0.0)
            + float(q.get("effective_independent_stories", 0.0) or 0.0)
        )

        rows.append({
            "Par": pair,
            "Motor base": motor,
            "Notícias": news_label,
            "Diferencial notícias": round(diff, 2),
            "Alinhamento": alignment,
            "Cobertura notícias": round(coverage, 0),
            "Convicção heurística": round(pair_conviction, 0),
            "Histórias independentes": round(independent, 1),
            f"{base} notícias": round(float(b.get("news_score", 50.0) or 50.0), 1),
            f"{quote} notícias": round(float(q.get("news_score", 50.0) or 50.0), 1),
        })

    df = pd.DataFrame(rows)
    if not df.empty:
        df["_rank"] = (
            df["Diferencial notícias"].abs()
            * (df["Cobertura notícias"] / 100.0)
            * (0.5 + 0.5 * df["Convicção heurística"] / 100.0)
        )
        df = df.sort_values("_rank", ascending=False, kind="stable").drop(columns=["_rank"])
    return df


# ============================================================
# V10.6.1 — PERSISTENT CALIBRATION / VALIDATION
# ============================================================
_NEWS_VALIDATION_PATH = "dados/currency_news_validation_v1061.csv"
_SCANNER_PATH = "dados/scanner_tecnico_v934.json"

def _gh_cfg_v1061() -> tuple[str, str, str]:
    try:
        token = st.secrets.get("GITHUB_TOKEN_HISTORICO", os.getenv("GITHUB_TOKEN_HISTORICO", ""))
        repo = st.secrets.get(
            "GITHUB_REPO_HISTORICO",
            os.getenv("GITHUB_REPO_HISTORICO", "aparecidomikael97-ship-it/usd-macro-pro-v4")
        )
        branch = st.secrets.get("GITHUB_BRANCH_HISTORICO", os.getenv("GITHUB_BRANCH_HISTORICO", "main"))
    except Exception:
        token, repo, branch = "", "aparecidomikael97-ship-it/usd-macro-pro-v4", "main"
    return str(token).strip(), str(repo).strip(), str(branch).strip()


def _gh_headers_v1061(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _gh_read_csv_v1061(path: str) -> tuple[pd.DataFrame, str]:
    token, repo, branch = _gh_cfg_v1061()
    if not token or not repo:
        return pd.DataFrame(), "GitHub persistente não configurado."
    try:
        url = f"https://api.github.com/repos/{repo}/contents/{path}"
        r = requests.get(url, headers=_gh_headers_v1061(token), params={"ref": branch}, timeout=20)
        if r.status_code == 404:
            return pd.DataFrame(), ""
        r.raise_for_status()
        raw = base64.b64decode(r.json()["content"])
        return pd.read_csv(io.BytesIO(raw)), ""
    except Exception as exc:
        return pd.DataFrame(), f"{type(exc).__name__}: {exc}"


def _gh_write_csv_v1061(path: str, df: pd.DataFrame, message: str) -> tuple[bool, str]:
    token, repo, branch = _gh_cfg_v1061()
    if not token or not repo:
        return False, "GitHub persistente não configurado."
    try:
        url = f"https://api.github.com/repos/{repo}/contents/{path}"
        headers = _gh_headers_v1061(token)
        current = requests.get(url, headers=headers, params={"ref": branch}, timeout=20)
        sha = current.json().get("sha", "") if current.status_code == 200 else ""
        if current.status_code not in (200, 404):
            current.raise_for_status()
        payload = {
            "message": message,
            "content": base64.b64encode(df.to_csv(index=False).encode("utf-8")).decode("ascii"),
            "branch": branch,
        }
        if sha:
            payload["sha"] = sha
        r = requests.put(url, headers=headers, json=payload, timeout=25)
        r.raise_for_status()
        return True, ""
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"


def _gh_read_json_v1061(path: str) -> tuple[dict[str, Any], str]:
    token, repo, branch = _gh_cfg_v1061()
    if not token or not repo:
        return {}, "GitHub persistente não configurado."
    try:
        url = f"https://api.github.com/repos/{repo}/contents/{path}"
        r = requests.get(url, headers=_gh_headers_v1061(token), params={"ref": branch}, timeout=20)
        if r.status_code == 404:
            return {}, "Arquivo não encontrado."
        r.raise_for_status()
        raw = base64.b64decode(r.json()["content"]).decode("utf-8")
        return json.loads(raw), ""
    except Exception as exc:
        return {}, f"{type(exc).__name__}: {exc}"


def _parse_state_time_v1061(value: Any) -> pd.Timestamp | None:
    if value in (None, ""):
        return None
    try:
        if isinstance(value, (float, int)) or str(value).replace(".", "", 1).isdigit():
            ts = pd.Timestamp(float(value), unit="s", tz="UTC")
        else:
            ts = pd.to_datetime(value, utc=True)
        return ts
    except Exception:
        return None


def _scanner_price_map_v1061(max_age_minutes: float = 60.0) -> dict[str, dict[str, Any]]:
    state, _ = _gh_read_json_v1061(_SCANNER_PATH)
    results = dict(state.get("resultados", {}) or {})
    now = pd.Timestamp.now(tz="UTC")
    out = {}
    for pair, raw in results.items():
        if not isinstance(raw, dict):
            continue
        tec = raw.get("tecnico", {}) if isinstance(raw.get("tecnico", {}), dict) else {}
        price = float(tec.get("preco_m15", 0.0) or 0.0)
        stamp = _parse_state_time_v1061(
            raw.get("m15_fetched_at", raw.get("processado_em"))
        )
        candle = _parse_state_time_v1061(tec.get("ultima_atualizacao"))
        age_min = None
        if stamp is not None:
            age_min = max(0.0, (now - stamp).total_seconds() / 60.0)
        fresh = bool(price > 0 and age_min is not None and age_min <= max_age_minutes)
        out[str(pair)] = {
            "price": price if price > 0 else None,
            "processado_em": stamp,
            "candle": candle,
            "age_minutes": age_min,
            "fresh": fresh,
        }
    return out


def _validation_columns_v1061() -> list[str]:
    return [
        "day_utc", "registered_at", "pair", "motor_base", "news_side",
        "news_diff", "alignment", "coverage", "conviction",
        "base_news_score", "quote_news_score",
        "base_independent_stories", "quote_independent_stories",
        "base_shared_ratio", "quote_shared_ratio",
        "signal_frozen_at", "entry_origin", "backfilled_at", "m15_candle_time",
        "auto_managed", "timing_migrated_v107",
        "entry_price", "entry_time", "price_source", "validation_status",
        "price_1h", "return_1h_pct", "hit_1h",
        "price_4h", "return_4h_pct", "hit_4h",
        "price_24h", "return_24h_pct", "hit_24h",
    ]


def _bool_or_none_news_v1081(value):
    try:
        if pd.isna(value):
            return None
    except Exception:
        pass
    text = str(value).strip().lower()
    if text in ("true", "1", "sim", "yes"):
        return True
    if text in ("false", "0", "nao", "não", "no"):
        return False
    return None


def _normalize_validation_dtypes_v1081(df: pd.DataFrame) -> pd.DataFrame:
    """Evita bool em coluna float64 ao ler snapshots antigos do GitHub CSV."""
    cols = _validation_columns_v1061()
    if df is None:
        return pd.DataFrame(columns=cols)
    df = df.copy()
    for c in cols:
        if c not in df.columns:
            df[c] = None
    for c in ("auto_managed", "timing_migrated_v107", "hit_1h", "hit_4h", "hit_24h"):
        df[c] = df[c].map(_bool_or_none_news_v1081).astype("object")
    for c in (
        "news_diff", "coverage", "conviction", "base_news_score", "quote_news_score",
        "base_independent_stories", "quote_independent_stories", "base_shared_ratio",
        "quote_shared_ratio", "entry_price", "price_1h", "return_1h_pct",
        "price_4h", "return_4h_pct", "price_24h", "return_24h_pct",
    ):
        df[c] = pd.to_numeric(df[c], errors="coerce").astype("float64")
    return df


def _side_from_diff_v1062(diff: float) -> str:
    diff = float(diff or 0.0)
    if diff >= 2.0:
        return "BUY"
    if diff <= -2.0:
        return "SELL"
    return "NEUTRAL"


def _pair_lookup_v1062(pair_df: pd.DataFrame) -> dict[str, dict[str, Any]]:
    out = {}
    if pair_df is None or pair_df.empty:
        return out
    for _, row in pair_df.iterrows():
        pair = str(row.get("Par", "") or "")
        if pair:
            out[pair] = row.to_dict()
    return out


def _apply_news_fields_v1062(
    df: pd.DataFrame,
    idx: Any,
    pair: str,
    current: Mapping[str, Any],
    intelligence: Mapping[str, Any],
    now_iso: str,
    freeze_signal: bool,
) -> str:
    """Atualiza os campos da notícia para o estado atual do par.

    Enquanto não existe preço de entrada, o snapshot é provisório.
    Ao capturar preço fresco, notícia + preço são congelados no mesmo momento.
    """
    base, quote = pair.split("/")
    currencies = dict(intelligence.get("currencies", {}) or {})
    b = currencies.get(base, {})
    q = currencies.get(quote, {})

    diff = float(current.get("Diferencial notícias", 0.0) or 0.0)
    side = _side_from_diff_v1062(diff)

    df.at[idx, "motor_base"] = str(current.get("Motor base", ""))
    df.at[idx, "news_side"] = side
    df.at[idx, "news_diff"] = diff
    df.at[idx, "alignment"] = str(current.get("Alinhamento", ""))
    df.at[idx, "coverage"] = float(current.get("Cobertura notícias", 0.0) or 0.0)
    df.at[idx, "conviction"] = float(current.get("Convicção heurística", 0.0) or 0.0)
    df.at[idx, "base_news_score"] = float(b.get("news_score", 50.0) or 50.0)
    df.at[idx, "quote_news_score"] = float(q.get("news_score", 50.0) or 50.0)
    df.at[idx, "base_independent_stories"] = float(b.get("effective_independent_stories", 0.0) or 0.0)
    df.at[idx, "quote_independent_stories"] = float(q.get("effective_independent_stories", 0.0) or 0.0)
    df.at[idx, "base_shared_ratio"] = float(b.get("shared_story_ratio", 0.0) or 0.0)
    df.at[idx, "quote_shared_ratio"] = float(q.get("shared_story_ratio", 0.0) or 0.0)

    if freeze_signal:
        df.at[idx, "signal_frozen_at"] = now_iso
    return side


def _backfill_today_rows_v1062(
    df: pd.DataFrame,
    intelligence: Mapping[str, Any],
    pair_df: pd.DataFrame,
    price_map: Mapping[str, Mapping[str, Any]],
    day: str,
    now_iso: str,
) -> tuple[pd.DataFrame, int, int, list[str]]:
    """Preenche preço em linhas já existentes SEM criar duplicidade.

    Regras:
    - nunca sobrescreve entry_price já gravado;
    - só captura preço quando scanner <=60 min e o lado das notícias é BUY/SELL;
    - antes do preço existir, atualiza o sinal para o estado ATUAL;
    - sinal e preço são congelados juntos no momento do backfill.
    """
    if df is None or df.empty:
        return df, 0, 0, []

    lookup = _pair_lookup_v1062(pair_df)
    backfilled = 0
    refreshed_without_price = 0
    pairs_backfilled: list[str] = []

    for idx, row in df.iterrows():
        if str(row.get("day_utc", "")) != str(day):
            continue

        pair = str(row.get("pair", "") or "")
        if not pair or pair not in lookup:
            continue

        # Não altera uma entrada já congelada.
        existing_price = pd.to_numeric(pd.Series([row.get("entry_price")]), errors="coerce").iloc[0]
        if pd.notna(existing_price) and float(existing_price) > 0:
            continue

        current = lookup[pair]
        current_side = _apply_news_fields_v1062(
            df, idx, pair, current, intelligence, now_iso, freeze_signal=False
        )

        if current_side == "NEUTRAL":
            df.at[idx, "validation_status"] = "OBSERVACAO_NEUTRA"
            df.at[idx, "price_source"] = "Sem entrada: notícias neutras"
            refreshed_without_price += 1
            continue

        px = dict(price_map.get(pair, {}) or {})
        entry_price = px.get("price") if px.get("fresh") else None
        entry_time = px.get("candle") or px.get("processado_em")

        if entry_price is None or entry_time is None:
            df.at[idx, "validation_status"] = "SEM_PRECO_FRESCO"
            df.at[idx, "price_source"] = "Aguardando scanner M15 <=60min"
            refreshed_without_price += 1
            continue

        # Congela sinal atual + preço no MESMO momento.
        _apply_news_fields_v1062(
            df, idx, pair, current, intelligence, now_iso, freeze_signal=True
        )
        df.at[idx, "entry_price"] = float(entry_price)
        # V10.7 TIMING INTEGRITY:
        # entry_time is the moment the signal + price are actually frozen.
        # The candle timestamp is preserved separately.
        df.at[idx, "entry_time"] = now_iso
        df.at[idx, "m15_candle_time"] = entry_time.isoformat()
        df.at[idx, "entry_origin"] = "BACKFILL_M15_FRESCO"
        df.at[idx, "backfilled_at"] = now_iso
        df.at[idx, "auto_managed"] = False
        df.at[idx, "timing_migrated_v107"] = False
        df.at[idx, "price_source"] = "Backfill scanner M15 <=60min"
        df.at[idx, "validation_status"] = "PENDENTE"
        backfilled += 1
        pairs_backfilled.append(pair)

    return df, backfilled, refreshed_without_price, pairs_backfilled


def backfill_today_news_prices_v1062(
    intelligence: Mapping[str, Any],
    pair_df: pd.DataFrame,
) -> tuple[bool, str, pd.DataFrame]:
    df, err = _gh_read_csv_v1061(_NEWS_VALIDATION_PATH)
    if err and df.empty:
        return False, err, df
    if df.empty:
        return True, "Nenhum snapshot existe ainda para recuperar.", df

    df = _normalize_validation_dtypes_v1081(df)
    cols = _validation_columns_v1061()
    for c in cols:
        if c not in df.columns:
            df[c] = None

    day = pd.Timestamp.now(tz="UTC").strftime("%Y-%m-%d")
    now_iso = pd.Timestamp.now(tz="UTC").isoformat()
    price_map = _scanner_price_map_v1061(max_age_minutes=60)

    df, backfilled, refreshed, pairs = _backfill_today_rows_v1062(
        df, intelligence, pair_df, price_map, day, now_iso
    )

    if backfilled or refreshed:
        ok, save_err = _gh_write_csv_v1061(
            _NEWS_VALIDATION_PATH,
            df[cols],
            "V10.6.2: recuperar preço fresco em snapshots de notícias"
        )
        if not ok:
            return False, save_err, df

    fresh_pairs = sum(1 for p in PAIR_ORDER if (price_map.get(p, {}) or {}).get("fresh"))
    if backfilled:
        msg = (
            f"{backfilled} snapshot(s) recuperado(s) com preço M15 fresco: "
            + ", ".join(pairs)
            + f". Scanner fresco em {fresh_pairs}/7 pares."
        )
    else:
        msg = (
            f"Nenhum snapshot direcional pôde receber preço agora. "
            f"Scanner fresco em {fresh_pairs}/7 pares. "
            "Atualize o scanner técnico e tente novamente."
        )
    return True, msg, df


def register_daily_news_snapshot_v1061(
    intelligence: Mapping[str, Any],
    pair_df: pd.DataFrame,
) -> tuple[bool, str, pd.DataFrame]:
    """Registra 1 linha por par/dia e recupera linhas existentes sem preço.

    V10.6.2 preserva a regra:
        1 par + 1 dia = no máximo 1 snapshot.

    Se a linha já existe, entry_price está vazio e o scanner ficou fresco depois,
    a MESMA linha é atualizada; uma segunda linha não é criada.
    """
    df, err = _gh_read_csv_v1061(_NEWS_VALIDATION_PATH)
    if err and df.empty:
        return False, err, df

    cols = _validation_columns_v1061()
    if df.empty:
        df = pd.DataFrame(columns=cols)
    for c in cols:
        if c not in df.columns:
            df[c] = None

    price_map = _scanner_price_map_v1061(max_age_minutes=60)
    currencies = dict(intelligence.get("currencies", {}) or {})
    day = pd.Timestamp.now(tz="UTC").strftime("%Y-%m-%d")
    now_iso = pd.Timestamp.now(tz="UTC").isoformat()

    # Primeiro recupera linhas de hoje que já existiam sem preço.
    df, backfilled, refreshed, backfilled_pairs = _backfill_today_rows_v1062(
        df, intelligence, pair_df, price_map, day, now_iso
    )

    existing = set()
    if not df.empty:
        existing = set(df["day_utc"].astype(str) + "|" + df["pair"].astype(str))

    added = 0
    new_directional_with_price = 0
    new_rows = []

    for _, row in pair_df.iterrows():
        pair = str(row.get("Par", "") or "")
        key = f"{day}|{pair}"
        if not pair or key in existing:
            continue

        base, quote = pair.split("/")
        diff = float(row.get("Diferencial notícias", 0.0) or 0.0)
        side = _side_from_diff_v1062(diff)

        px = dict(price_map.get(pair, {}) or {})
        entry_price = px.get("price") if px.get("fresh") else None
        entry_time = px.get("candle") or px.get("processado_em")
        entry_time_iso = entry_time.isoformat() if entry_time is not None else None

        if side in ("BUY", "SELL") and entry_price is not None and entry_time_iso:
            status = "PENDENTE"
            new_directional_with_price += 1
            signal_frozen_at = now_iso
            entry_origin = "REGISTRO_INICIAL"
            price_source = "Scanner M15 <=60min"
            m15_candle_time = entry_time_iso
            entry_time_iso = now_iso
        elif side == "NEUTRAL":
            status = "OBSERVACAO_NEUTRA"
            signal_frozen_at = now_iso
            entry_origin = "SEM_ENTRADA_NEUTRA"
            price_source = "Sem entrada: notícias neutras"
            entry_price = None
            entry_time_iso = None
            m15_candle_time = None
        else:
            status = "SEM_PRECO_FRESCO"
            signal_frozen_at = None
            entry_origin = "AGUARDANDO_BACKFILL"
            price_source = "Aguardando scanner M15 <=60min"
            entry_price = None
            entry_time_iso = None
            m15_candle_time = None

        b = currencies.get(base, {})
        q = currencies.get(quote, {})
        new_rows.append({
            "day_utc": day,
            "registered_at": now_iso,
            "pair": pair,
            "motor_base": str(row.get("Motor base", "")),
            "news_side": side,
            "news_diff": diff,
            "alignment": str(row.get("Alinhamento", "")),
            "coverage": float(row.get("Cobertura notícias", 0.0) or 0.0),
            "conviction": float(row.get("Convicção heurística", 0.0) or 0.0),
            "base_news_score": float(b.get("news_score", 50.0) or 50.0),
            "quote_news_score": float(q.get("news_score", 50.0) or 50.0),
            "base_independent_stories": float(b.get("effective_independent_stories", 0.0) or 0.0),
            "quote_independent_stories": float(q.get("effective_independent_stories", 0.0) or 0.0),
            "base_shared_ratio": float(b.get("shared_story_ratio", 0.0) or 0.0),
            "quote_shared_ratio": float(q.get("shared_story_ratio", 0.0) or 0.0),
            "signal_frozen_at": signal_frozen_at,
            "entry_origin": entry_origin,
            "backfilled_at": None,
            "m15_candle_time": m15_candle_time,
            "auto_managed": False,
            "timing_migrated_v107": False,
            "entry_price": entry_price,
            "entry_time": entry_time_iso,
            "price_source": price_source,
            "validation_status": status,
            "price_1h": None, "return_1h_pct": None, "hit_1h": None,
            "price_4h": None, "return_4h_pct": None, "hit_4h": None,
            "price_24h": None, "return_24h_pct": None, "hit_24h": None,
        })
        added += 1

    if new_rows:
        df = pd.concat([df, pd.DataFrame(new_rows)], ignore_index=True)

    if new_rows or backfilled or refreshed:
        ok, save_err = _gh_write_csv_v1061(
            _NEWS_VALIDATION_PATH,
            df[cols],
            "V10.6.2: registrar/recuperar snapshot diário de notícias"
        )
        if not ok:
            return False, save_err, df

    today = df[df["day_utc"].astype(str) == day].copy()
    entry_num = pd.to_numeric(today["entry_price"], errors="coerce") if not today.empty else pd.Series(dtype=float)
    ready_today = int(
        (
            today["news_side"].astype(str).isin(["BUY", "SELL"])
            & entry_num.notna()
            & (entry_num > 0)
        ).sum()
    ) if not today.empty else 0

    return True, (
        f"{added} novo(s); {backfilled} recuperado(s) com preço fresco; "
        f"{ready_today} snapshot(s) direcional(is) de hoje pronto(s) para validação."
    ), df



def _td_candles_v1061(pair: str, outputsize: int = 500) -> tuple[pd.DataFrame, str]:
    try:
        api_key = st.secrets.get("CHAVE_TWELVE_DATA", os.getenv("CHAVE_TWELVE_DATA", ""))
    except Exception:
        api_key = os.getenv("CHAVE_TWELVE_DATA", "")
    if not api_key:
        return pd.DataFrame(), "CHAVE_TWELVE_DATA ausente."
    try:
        r = requests.get(
            "https://api.twelvedata.com/time_series",
            params={
                "symbol": pair,
                "interval": "15min",
                "outputsize": int(outputsize),
                "apikey": api_key,
                "timezone": "UTC",
                "format": "JSON",
            },
            timeout=20,
        )
        if r.status_code != 200:
            return pd.DataFrame(), f"HTTP {r.status_code}"
        js = r.json()
        vals = js.get("values") or []
        if not vals:
            return pd.DataFrame(), str(js.get("message", "Sem candles M15."))
        df = pd.DataFrame(vals)
        df["datetime"] = pd.to_datetime(df["datetime"], utc=True, errors="coerce")
        df["close"] = pd.to_numeric(df["close"], errors="coerce")
        df = df.dropna(subset=["datetime", "close"]).sort_values("datetime").reset_index(drop=True)
        return df, ""
    except Exception as exc:
        return pd.DataFrame(), f"{type(exc).__name__}: {exc}"


def _directional_return_v1061(side: str, entry: float, exit_price: float) -> float | None:
    try:
        entry = float(entry)
        exit_price = float(exit_price)
        if entry == 0:
            return None
        raw = (exit_price / entry - 1.0) * 100.0
        return -raw if str(side).upper() == "SELL" else raw
    except Exception:
        return None


def validate_next_news_snapshots_v1061(max_rows: int = 2) -> tuple[bool, str, pd.DataFrame]:
    df, err = _gh_read_csv_v1061(_NEWS_VALIDATION_PATH)
    if err:
        return False, err, df
    if df.empty:
        return True, "Ainda não há snapshots registrados.", df

    # Important for pandas 2.x: bool/empty values share object dtype.
    for c in ("hit_1h", "hit_4h", "hit_24h"):
        if c in df.columns:
            df[c] = df[c].astype("object")

    now = pd.Timestamp.now(tz="UTC")
    candidates = []
    for i, row in df.iterrows():
        side = str(row.get("news_side", ""))
        if side not in ("BUY", "SELL"):
            continue
        if pd.isna(row.get("entry_price")) or not str(row.get("entry_time", "")):
            continue
        if str(row.get("validation_status", "")) == "COMPLETO":
            continue
        try:
            entry_time = pd.to_datetime(row["entry_time"], utc=True)
        except Exception:
            continue
        if (now - entry_time).total_seconds() < 3600:
            continue
        candidates.append(i)

    if not candidates:
        return True, "Nenhum snapshot maduro aguardando validação agora.", df

    processed = 0
    errors = []
    for i in candidates[:max_rows]:
        row = df.loc[i]
        pair = str(row["pair"])
        side = str(row["news_side"])
        entry = float(row["entry_price"])
        entry_time = pd.to_datetime(row["entry_time"], utc=True)

        candles, candle_err = _td_candles_v1061(pair, 500)
        if candles.empty:
            errors.append(f"{pair}: {candle_err}")
            continue

        for hours in (1, 4, 24):
            col_price = f"price_{hours}h"
            col_ret = f"return_{hours}h_pct"
            col_hit = f"hit_{hours}h"

            if pd.notna(row.get(col_price)):
                continue
            target = entry_time + pd.Timedelta(hours=hours)
            if now < target:
                continue

            hits = candles[candles["datetime"] >= target]
            if hits.empty:
                continue
            exit_price = float(hits.iloc[0]["close"])
            ret = _directional_return_v1061(side, entry, exit_price)
            df.at[i, col_price] = exit_price
            df.at[i, col_ret] = ret
            df.at[i, col_hit] = bool(ret > 0) if ret is not None else None

        if pd.notna(df.at[i, "price_24h"]):
            df.at[i, "validation_status"] = "COMPLETO"
        elif pd.notna(df.at[i, "price_1h"]) or pd.notna(df.at[i, "price_4h"]):
            df.at[i, "validation_status"] = "PARCIAL"
        else:
            df.at[i, "validation_status"] = "PENDENTE"
        processed += 1

    if processed:
        ok, save_err = _gh_write_csv_v1061(
            _NEWS_VALIDATION_PATH, df[_validation_columns_v1061()],
            "V10.6.1: validar snapshots de notícias"
        )
        if not ok:
            return False, save_err, df

    msg = f"{processed} snapshot(s) processados."
    if errors:
        msg += " Falhas: " + " | ".join(errors[:2])
    return True, msg, df


def _hit_rate_v1061(df: pd.DataFrame, col: str) -> tuple[str, int]:
    if df.empty or col not in df.columns:
        return "—", 0
    s = df[col].dropna()
    if s.empty:
        return "—", 0
    vals = s.map(lambda x: str(x).strip().lower() in ("true", "1", "sim"))
    return f"{100 * vals.mean():.1f}%", len(vals)


def render_news_validation_panel_v1061(
    intelligence: Mapping[str, Any],
    pair_df: pd.DataFrame,
):
    st.markdown("### 🧪 Calibração & Validação — V10.7")
    st.caption(
        "🤖 O Autopilot V10.7 registra, recupera preço e valida 1H/4H/24H em segundo plano. "
        "Os botões abaixo ficam somente como plano B/manual."
    )

    price_map_diag = _scanner_price_map_v1061(max_age_minutes=60)
    diag_rows = []
    for pair in PAIR_ORDER:
        px = dict(price_map_diag.get(pair, {}) or {})
        age = px.get("age_minutes")
        diag_rows.append({
            "Par": pair,
            "Preço M15": px.get("price"),
            "Idade scanner (min)": round(float(age), 1) if age is not None else None,
            "Fresco <=60m": "✅ SIM" if px.get("fresh") else "❌ NÃO",
        })

    fresh_count = sum(1 for x in diag_rows if x["Fresco <=60m"] == "✅ SIM")
    st.info(
        f"📡 Scanner com preço fresco em {fresh_count}/7 pares. "
        "Se estiver 0/7, atualize o scanner técnico no Painel Mestre e volte aqui."
    )
    with st.expander("📡 Ver frescor do scanner M15", expanded=False):
        st.dataframe(pd.DataFrame(diag_rows), hide_index=True, use_container_width=True)

    a, b, c = st.columns(3)
    with a:
        if st.button(
            "🧰 Manual: registrar/atualizar",
            key="v1062_register_snapshot",
            use_container_width=True
        ):
            ok, msg, _ = register_daily_news_snapshot_v1061(intelligence, pair_df)
            (st.success if ok else st.error)(msg)
    with b:
        if st.button(
            "🧰 Manual: recuperar preço",
            key="v1062_backfill_price",
            use_container_width=True
        ):
            ok, msg, _ = backfill_today_news_prices_v1062(intelligence, pair_df)
            (st.success if ok else st.warning)(msg)
    with c:
        if st.button(
            "🧰 Manual: validar próximos 2",
            key="v1062_validate_news",
            use_container_width=True
        ):
            ok, msg, _ = validate_next_news_snapshots_v1061(max_rows=2)
            (st.success if ok else st.warning)(msg)

    hist, err = _gh_read_csv_v1061(_NEWS_VALIDATION_PATH)
    if err and hist.empty:
        st.info(err)
        return
    if hist.empty:
        st.info("Nenhum snapshot de notícias registrado ainda.")
        return

    h1, n1 = _hit_rate_v1061(hist, "hit_1h")
    h4, n4 = _hit_rate_v1061(hist, "hit_4h")
    h24, n24 = _hit_rate_v1061(hist, "hit_24h")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Snapshots", len(hist))
    m2.metric("Acerto 1H", h1, f"N={n1}")
    m3.metric("Acerto 4H", h4, f"N={n4}")
    m4.metric("Acerto 24H", h24, f"N={n24}")

    if max(n1, n4, n24) < 30:
        st.warning(
            "Amostra pequena. Não use estes percentuais para ajustar pesos ainda. "
            "Meta mínima inicial: dezenas de snapshots independentes."
        )

    # Compare aligned vs conflicts only when a result exists.
    stats_rows = []
    for alignment in ("🟢 CONFIRMA", "🔴 CONFLITA", "⚪ NEUTRO", "⚪ OBSERVAÇÃO"):
        sub = hist[hist["alignment"].astype(str) == alignment]
        if sub.empty:
            continue
        r1, c1 = _hit_rate_v1061(sub, "hit_1h")
        r4, c4 = _hit_rate_v1061(sub, "hit_4h")
        r24, c24 = _hit_rate_v1061(sub, "hit_24h")
        stats_rows.append({
            "Alinhamento": alignment,
            "Snapshots": len(sub),
            "1H": r1, "N 1H": c1,
            "4H": r4, "N 4H": c4,
            "24H": r24, "N 24H": c24,
        })
    if stats_rows:
        st.markdown("#### Notícias confirmando x conflitando com o motor")
        st.dataframe(pd.DataFrame(stats_rows), hide_index=True, use_container_width=True)

    show_cols = [
        "day_utc", "pair", "news_side", "news_diff", "alignment",
        "coverage", "conviction", "signal_frozen_at", "entry_origin",
        "entry_price", "entry_time", "validation_status",
        "return_1h_pct", "hit_1h", "return_4h_pct", "hit_4h",
        "return_24h_pct", "hit_24h",
    ]
    show_cols = [c for c in show_cols if c in hist.columns]
    st.dataframe(hist[show_cols].tail(30).iloc[::-1], hide_index=True, use_container_width=True)


def _macro_score_map(ranking: pd.DataFrame | None) -> dict[str, float]:
    out = {}
    if ranking is None or ranking.empty:
        return out
    code_col = "Código" if "Código" in ranking.columns else None
    score_col = "Pontuação_Final" if "Pontuação_Final" in ranking.columns else None
    if not code_col or not score_col:
        return out
    for _, row in ranking.iterrows():
        out[str(row[code_col])] = float(row[score_col])
    return out


def render_currency_news_panel(
    matrix: pd.DataFrame | None = None,
    ranking: pd.DataFrame | None = None,
    newsapi_key: str = "",
):
    st.subheader("🌍 Currency News Intelligence — V10.7")
    st.caption(
        "Calibração global de notícias para as 8 moedas. "
        "Camada observacional: NÃO altera o Score Mestre."
    )

    c_refresh, c_info = st.columns([1, 3])
    with c_refresh:
        if st.button("🔄 Atualizar notícias", key="v1061_refresh_news", use_container_width=True):
            load_currency_news_intelligence.clear()
            st.rerun()
    with c_info:
        st.info(
            "V10.6.2: deduplicação global + recuperação de preço fresco; ENTRE moedas + peso de independência + "
            "cobertura separada da convicção direcional + validação 1H/4H/24H."
        )

    with st.spinner("Analisando e calibrando notícias globais..."):
        intelligence = load_currency_news_intelligence(newsapi_key)

    currencies = dict(intelligence.get("currencies", {}) or {})
    st.session_state["v1061_currency_news"] = intelligence

    pair_df = pair_news_table(intelligence, matrix)
    st.session_state["v1061_pair_news"] = pair_df.to_dict("records") if not pair_df.empty else []

    macro_scores = _macro_score_map(ranking)
    summary_rows = []
    for currency in CURRENCY_PROFILES:
        data = currencies.get(currency, {})
        news_score = float(data.get("news_score", 50.0) or 50.0)
        macro_score = macro_scores.get(currency)
        if macro_score is None:
            confluence = "—"
        elif macro_score >= 55 and news_score >= 55:
            confluence = "🟢 CONFIRMA FORÇA"
        elif macro_score <= 45 and news_score <= 45:
            confluence = "🟢 CONFIRMA FRAQUEZA"
        elif (macro_score >= 55 and news_score <= 45) or (macro_score <= 45 and news_score >= 55):
            confluence = "🔴 CONFLITA"
        else:
            confluence = "⚪ MISTO"

        summary_rows.append({
            "Moeda": currency,
            "Banco central": data.get("bank", "—"),
            "Viés notícias": data.get("bias", "⚪ NEUTRO"),
            "Score notícias": round(news_score, 1),
            "Impacto": round(float(data.get("net_impact", 0.0) or 0.0), 2),
            "Convicção heurística": round(float(data.get("directional_confidence", 0.0) or 0.0)),
            "Cobertura": round(float(data.get("coverage_quality", 0.0) or 0.0)),
            "Histórias independentes": round(float(data.get("effective_independent_stories", 0.0) or 0.0), 1),
            "Compartilhadas %": round(100 * float(data.get("shared_story_ratio", 0.0) or 0.0)),
            "Artigos exibidos": int(data.get("article_count", 0) or 0),
            "Tema dominante": data.get("top_theme", "—"),
            "Macro atual": round(macro_score, 1) if macro_score is not None else None,
            "Confluência": confluence,
        })

    summary = pd.DataFrame(summary_rows)
    valid = summary[summary["Cobertura"] >= 20].copy() if not summary.empty else pd.DataFrame()

    if not valid.empty:
        strongest = valid.sort_values("Score notícias", ascending=False).iloc[0]
        weakest = valid.sort_values("Score notícias", ascending=True).iloc[0]
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Mais forte nas notícias", str(strongest["Moeda"]), f'{float(strongest["Score notícias"]):.1f}/100')
        m2.metric("Mais fraca nas notícias", str(weakest["Moeda"]), f'{float(weakest["Score notícias"]):.1f}/100')
        m3.metric("Histórias globais únicas", int(intelligence.get("global_unique_stories", 0) or 0))
        m4.metric("Histórias compartilhadas", int(intelligence.get("global_shared_stories", 0) or 0))

    updated = intelligence.get("updated_at", "")
    if updated:
        try:
            st.caption(f"Última análise: {pd.Timestamp(updated).strftime('%d/%m/%Y %H:%M UTC')}")
        except Exception:
            pass

    st.warning(
        "⚠️ Convicção heurística NÃO é probabilidade de a moeda subir. "
        "Ela mede acordo/direção das evidências depois da calibração."
    )

    st.markdown("### 🧭 Força calibrada de notícias por moeda")
    st.dataframe(summary, hide_index=True, use_container_width=True)

    st.markdown("### 💱 Confluência das notícias com os 7 pares")
    st.caption(
        "A mesma história publicada/citada em várias moedas perde peso de independência. "
        "Assim reduzimos dupla contagem."
    )
    st.dataframe(pair_df, hide_index=True, use_container_width=True)

    aligned = pair_df[pair_df["Alinhamento"] == "🟢 CONFIRMA"] if not pair_df.empty else pd.DataFrame()
    conflicts = pair_df[pair_df["Alinhamento"] == "🔴 CONFLITA"] if not pair_df.empty else pd.DataFrame()
    p1, p2, p3 = st.columns(3)
    p1.metric("Confirmados", len(aligned))
    p2.metric("Conflitos", len(conflicts))
    p3.metric("Compartilhamento global", f"{100*float(intelligence.get('shared_story_ratio',0) or 0):.0f}%")

    st.markdown("### 🔎 Raio-X de uma moeda")
    selected = st.selectbox(
        "Moeda",
        list(CURRENCY_PROFILES.keys()),
        format_func=lambda x: f"{x} · {CURRENCY_PROFILES[x]['name']}",
        key="v1061_selected_currency",
    )
    data = currencies.get(selected, {})
    r1, r2, r3, r4, r5 = st.columns(5)
    r1.metric("Score notícias", f"{float(data.get('news_score', 50.0)):.1f}/100")
    r2.metric("Impacto líquido", f"{float(data.get('net_impact', 0.0)):+.2f}")
    r3.metric("Convicção heurística", f"{float(data.get('directional_confidence', 0.0)):.0f}%")
    r4.metric("Cobertura", f"{float(data.get('coverage_quality', 0.0)):.0f}%")
    r5.metric("Histórias indep.", f"{float(data.get('effective_independent_stories', 0.0)):.1f}")

    st.markdown(
        f"**Banco central:** {data.get('bank', '—')} · "
        f"**Viés:** {data.get('bias', '⚪ NEUTRO')} · "
        f"**Tema dominante:** {data.get('top_theme', '—')} · "
        f"**Compartilhadas:** {100*float(data.get('shared_story_ratio',0) or 0):.0f}%"
    )
    st.link_button(
        f"🏦 Site oficial — {data.get('bank', 'Banco central')}",
        data.get("official_url", CURRENCY_PROFILES[selected]["official_url"]),
    )

    articles = data.get("articles", []) or []
    if articles:
        rows = []
        for a in articles[:12]:
            age = a.get("age_hours")
            age_txt = "—" if age is None else (f"{age:.0f}h" if age < 24 else f"{age/24:.1f}d")
            rows.append({
                "Impacto": a.get("direction", "⚪ Neutro"),
                "Tema": a.get("theme", "—"),
                "Relevância": a.get("relevance", "—"),
                "Fonte": a.get("source", "—"),
                "Idade": age_txt,
                "Independência": round(float(a.get("independence_factor", 1.0) or 1.0), 2),
                "Compartilhada com": a.get("shared_currencies", selected),
                "Manchete": a.get("title", ""),
                "Leitura": a.get("explanation", ""),
            })
        st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
    else:
        st.warning("Nenhuma manchete relevante encontrada agora.")

    with st.expander("🛡️ Calibração + Timing Integrity V10.7"):
        st.markdown(
            "- Deduplicação local **e global entre moedas**.\n"
            "- Uma história compartilhada mantém contexto, mas recebe peso menor de independência.\n"
            "- Cobertura mede quantidade/diversidade/frescor; convicção mede acordo direcional.\n"
            "- Convicção foi limitada e não pode ser interpretada como chance de gain.\n"
            "- Score de notícias ficou mais conservador.\n"
            "- A integração com Score Mestre continua bloqueada até validação."
        )

    render_news_validation_panel_v1061(intelligence, pair_df)

    st.download_button(
        "⬇️ Baixar snapshot calibrado (CSV)",
        summary.to_csv(index=False).encode("utf-8"),
        "currency_news_v1061.csv",
        "text/csv",
        use_container_width=True,
    )

