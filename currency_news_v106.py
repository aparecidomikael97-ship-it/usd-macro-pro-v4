"""USD Macro Pro V10.6 — Global Currency News Intelligence.

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
Esta versão é OBSERVACIONAL. Ela NÃO altera Score Mestre, Gate, pesos, Market Map
ou histórico oficial. Serve como confluência adicional para posterior validação.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from typing import Any, Mapping
import math
import re
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


def analyze_articles(currency: str, items: list[dict[str, Any]]) -> dict[str, Any]:
    analyzed = []
    for item in _dedupe(items):
        rel_points, rel_level = _relevance(currency, item.get("title", ""))
        if rel_level == "Baixa":
            continue

        raw_impact, direction, explanation = _headline_impact(currency, item.get("title", ""))
        recency = _recency_factor(item.get("published_at"))
        source_factor = _source_factor(item.get("source", ""))
        rel_factor = min(1.0, rel_points / 8.0)

        weighted_impact = float(np.clip(raw_impact * recency * source_factor * rel_factor, -1.2, 1.2))
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
            "age_hours": age,
        })

    analyzed.sort(
        key=lambda x: (x["relevance_points"] * x["recency_factor"] * x["source_factor"], abs(x["weighted_impact"])),
        reverse=True,
    )
    analyzed = analyzed[:15]

    directional = [x for x in analyzed if abs(x["weighted_impact"]) >= 0.04]
    if directional:
        weights = np.array([
            max(0.2, x["relevance_points"] / 4.0) * x["recency_factor"] * x["source_factor"]
            for x in directional
        ], dtype=float)
        impacts = np.array([x["weighted_impact"] for x in directional], dtype=float)
        avg_impact = float(np.average(impacts, weights=weights))
        net = float(np.clip(avg_impact * 10.0, -10.0, 10.0))
        agreement = float(np.clip(abs(np.sum(impacts * weights)) / max(np.sum(abs(impacts) * weights), 1e-9), 0, 1))
    else:
        net = 0.0
        agreement = 0.0

    sources = {str(x.get("source", "")).strip().lower() for x in analyzed if str(x.get("source", "")).strip()}
    fresh_avg = float(np.mean([x["recency_factor"] for x in analyzed])) if analyzed else 0.0
    coverage_factor = min(1.0, len(analyzed) / 10.0)
    diversity_factor = min(1.0, len(sources) / 5.0)

    coverage_quality = float(np.clip(
        100 * (0.45 * coverage_factor + 0.25 * diversity_factor + 0.30 * fresh_avg),
        0, 100
    ))
    directional_confidence = float(np.clip(
        100 * (0.30 * coverage_factor + 0.20 * diversity_factor + 0.20 * fresh_avg + 0.30 * agreement),
        0, 100
    ))

    news_score = float(np.clip(50.0 + net * 5.0, 0, 100))
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
        "source_count": len(sources),
        "top_theme": top_theme,
        "articles": analyzed,
    }


def _load_one_currency(currency: str, newsapi_key: str = "") -> dict[str, Any]:
    profile = CURRENCY_PROFILES[currency]
    items: list[dict[str, Any]] = []
    for query in profile["queries"]:
        items.extend(_rss_items(query))

    # NewsAPI is a fallback, not the primary source.
    if len(items) < 4 and newsapi_key:
        items.extend(_newsapi_items(profile, newsapi_key))

    return analyze_articles(currency, items)


@st.cache_data(ttl=1800, show_spinner=False)
def load_currency_news_intelligence(newsapi_key: str = "") -> dict[str, Any]:
    results = {}
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {
            pool.submit(_load_one_currency, currency, newsapi_key): currency
            for currency in CURRENCY_PROFILES
        }
        for future in as_completed(futures):
            currency = futures[future]
            try:
                results[currency] = future.result()
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
                    "source_count": 0,
                    "top_theme": "Erro de coleta",
                    "articles": [],
                    "error": f"{type(exc).__name__}: {exc}",
                }

    return {
        "updated_at": pd.Timestamp.now(tz="UTC").isoformat(),
        "currencies": results,
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
        diff = float(np.clip(base_net - quote_net, -20.0, 20.0))

        if diff >= 2.0:
            news_direction = f"COMPRA {pair}"
            news_label = "🟢 COMPRA"
        elif diff <= -2.0:
            news_direction = f"VENDA {pair}"
            news_label = "🔴 VENDA"
        else:
            news_direction = "NEUTRO"
            news_label = "⚪ NEUTRO"

        motor = matrix_map.get(pair, "—")
        motor_upper = motor.upper()
        if "COMPRA" in motor_upper:
            motor_side = "BUY"
        elif "VENDA" in motor_upper:
            motor_side = "SELL"
        else:
            motor_side = "WAIT"

        news_side = "BUY" if diff >= 2 else "SELL" if diff <= -2 else "NEUTRAL"
        if motor_side == "WAIT":
            alignment = "⚪ OBSERVAÇÃO"
        elif news_side == "NEUTRAL":
            alignment = "⚪ NEUTRO"
        elif motor_side == news_side:
            alignment = "🟢 CONFIRMA"
        else:
            alignment = "🔴 CONFLITA"

        quality = min(
            float(b.get("coverage_quality", 0.0) or 0.0),
            float(q.get("coverage_quality", 0.0) or 0.0),
        )

        rows.append({
            "Par": pair,
            "Motor base": motor,
            "Notícias": news_label,
            "Diferencial notícias": round(diff, 2),
            "Alinhamento": alignment,
            "Qualidade notícias": round(quality, 0),
            f"{base} notícias": round(float(b.get("news_score", 50.0) or 50.0), 1),
            f"{quote} notícias": round(float(q.get("news_score", 50.0) or 50.0), 1),
        })

    df = pd.DataFrame(rows)
    if not df.empty:
        df["_rank"] = df["Diferencial notícias"].abs() * (df["Qualidade notícias"] / 100.0)
        df = df.sort_values("_rank", ascending=False, kind="stable").drop(columns=["_rank"])
    return df


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
    st.subheader("🌍 Currency News Intelligence — V10.6")
    st.caption(
        "Leitura de notícias e bancos centrais das 8 principais moedas. "
        "Camada observacional: ainda NÃO altera o Score Mestre."
    )

    c_refresh, c_info = st.columns([1, 3])
    with c_refresh:
        if st.button("🔄 Atualizar notícias", key="v106_refresh_news", use_container_width=True):
            load_currency_news_intelligence.clear()
            st.rerun()
    with c_info:
        st.info(
            "O motor reduz duplicidade, pesa fonte + relevância + frescor e separa "
            "banco central, inflação, emprego, crescimento, intervenção e commodities."
        )

    with st.spinner("Analisando notícias globais das 8 moedas..."):
        intelligence = load_currency_news_intelligence(newsapi_key)

    currencies = dict(intelligence.get("currencies", {}) or {})
    st.session_state["v106_currency_news"] = intelligence

    pair_df = pair_news_table(intelligence, matrix)
    st.session_state["v106_pair_news"] = pair_df.to_dict("records") if not pair_df.empty else []

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
            "Convicção": round(float(data.get("directional_confidence", 0.0) or 0.0)),
            "Cobertura": round(float(data.get("coverage_quality", 0.0) or 0.0)),
            "Artigos": int(data.get("article_count", 0) or 0),
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
        m1.metric("Moeda mais forte nas notícias", str(strongest["Moeda"]), f'{float(strongest["Score notícias"]):.1f}/100')
        m2.metric("Moeda mais fraca nas notícias", str(weakest["Moeda"]), f'{float(weakest["Score notícias"]):.1f}/100')
        m3.metric("Artigos relevantes", int(summary["Artigos"].sum()))
        m4.metric("Moedas analisadas", f"{len(summary)}/8")

    updated = intelligence.get("updated_at", "")
    if updated:
        try:
            st.caption(f"Última análise global: {pd.Timestamp(updated).strftime('%d/%m/%Y %H:%M UTC')}")
        except Exception:
            pass

    st.markdown("### 🧭 Força de notícias por moeda")
    st.dataframe(summary, hide_index=True, use_container_width=True)

    st.markdown("### 💱 Confluência das notícias com os 7 pares")
    st.caption(
        "Diferencial = impacto da moeda base − impacto da moeda cotada. "
        "A tabela compara esse lado com a direção atual do motor base."
    )
    st.dataframe(pair_df, hide_index=True, use_container_width=True)

    aligned = pair_df[pair_df["Alinhamento"] == "🟢 CONFIRMA"] if not pair_df.empty else pd.DataFrame()
    conflicts = pair_df[pair_df["Alinhamento"] == "🔴 CONFLITA"] if not pair_df.empty else pd.DataFrame()

    p1, p2 = st.columns(2)
    p1.metric("Pares confirmados por notícias", len(aligned))
    p2.metric("Pares em conflito com notícias", len(conflicts))

    st.markdown("### 🔎 Raio-X de uma moeda")
    selected = st.selectbox(
        "Moeda",
        list(CURRENCY_PROFILES.keys()),
        format_func=lambda x: f"{x} · {CURRENCY_PROFILES[x]['name']}",
        key="v106_selected_currency",
    )
    data = currencies.get(selected, {})
    r1, r2, r3, r4 = st.columns(4)
    r1.metric("Score notícias", f"{float(data.get('news_score', 50.0)):.1f}/100")
    r2.metric("Impacto líquido", f"{float(data.get('net_impact', 0.0)):+.2f}")
    r3.metric("Convicção", f"{float(data.get('directional_confidence', 0.0)):.0f}%")
    r4.metric("Cobertura", f"{float(data.get('coverage_quality', 0.0)):.0f}%")

    st.markdown(
        f"**Banco central:** {data.get('bank', '—')} · "
        f"**Viés:** {data.get('bias', '⚪ NEUTRO')} · "
        f"**Tema dominante:** {data.get('top_theme', '—')}"
    )
    st.link_button(
        f"🏦 Abrir site oficial — {data.get('bank', 'Banco central')}",
        data.get("official_url", CURRENCY_PROFILES[selected]["official_url"]),
    )

    articles = data.get("articles", []) or []
    if articles:
        rows = []
        for a in articles[:12]:
            age = a.get("age_hours")
            if age is None:
                age_txt = "—"
            elif age < 24:
                age_txt = f"{age:.0f}h"
            else:
                age_txt = f"{age/24:.1f}d"
            rows.append({
                "Impacto": a.get("direction", "⚪ Neutro"),
                "Tema": a.get("theme", "—"),
                "Relevância": a.get("relevance", "—"),
                "Fonte": a.get("source", "—"),
                "Idade": age_txt,
                "Manchete": a.get("title", ""),
                "Leitura": a.get("explanation", ""),
            })
        st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
    else:
        st.warning("Nenhuma manchete relevante foi encontrada para esta moeda agora.")

    with st.expander("🛡️ Como evitamos notícias enganosas / duplicadas"):
        st.markdown(
            "- Manchetes quase iguais são agrupadas por similaridade de palavras.\n"
            "- Fonte oficial e grandes veículos recebem peso maior.\n"
            "- Notícias antigas perdem peso rapidamente.\n"
            "- Manchetes sem tema macro claro ficam neutras ou são descartadas.\n"
            "- Commodity/risk-off só afeta moedas em que há relação econômica plausível.\n"
            "- A camada de notícias não altera o Score Mestre na V10.6."
        )

    with st.expander("🧪 Como vamos validar antes de colocar no Score Mestre"):
        st.markdown(
            "Primeiro observamos se **notícias confirmando o motor** melhoram o resultado das configurações "
            "A/A+ e se conflitos antecipam operações ruins. Depois de uma amostra suficiente, podemos testar "
            "um peso pequeno (por exemplo 5–10%) sem contar duas vezes o mesmo tema macro."
        )

    st.download_button(
        "⬇️ Baixar snapshot das notícias (CSV)",
        summary.to_csv(index=False).encode("utf-8"),
        "currency_news_v106.csv",
        "text/csv",
        use_container_width=True,
    )
