"""AtlasQuant structured geopolitical research engine.

This module converts already-collected geopolitical evidence into a transparent
pair-level context. It does not browse the web, decide political merit, predict
elections, infer motives, change operational gates/scores, or send orders.

Design principles:
- deduplicate one global story across currencies before aggregation;
- separate broad risk-regime effects from explicit currency impacts;
- keep source freshness, independence, severity and duration visible;
- treat unsupported country/commodity implications as context only, not a
  directional FX claim;
- fail closed when evidence is missing or too weak.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Mapping, Sequence
import math
import re
import unicodedata

SCHEMA = "ATLASQUANT_GEOPOLITICAL_ENGINE_V1"

RISK_SENSITIVITY = {
    "USD": 0.35,
    "JPY": 0.85,
    "CHF": 0.80,
    "EUR": -0.20,
    "GBP": -0.20,
    "CAD": -0.55,
    "AUD": -0.75,
    "NZD": -0.75,
}

CATEGORY_TERMS = (
    ("conflict_escalation", (
        "war", "conflict", "attack", "missile", "invasion", "military strike",
        "hostilities", "armed clash", "airstrike", "drone strike",
    )),
    ("sanctions_trade", (
        "sanction", "embargo", "export ban", "export control", "trade war",
        "tariff", "trade restriction",
    )),
    ("shipping_logistics", (
        "shipping disruption", "shipping route", "port closure", "blockade",
        "maritime attack", "vessel attack", "chokepoint",
    )),
    ("energy_supply", (
        "oil supply disruption", "gas supply disruption", "pipeline attack",
        "pipeline disruption", "energy supply disruption", "refinery attack",
    )),
    ("political_uncertainty", (
        "political crisis", "government crisis", "state of emergency",
        "election uncertainty", "political uncertainty",
    )),
    ("diplomacy_deescalation", (
        "ceasefire", "truce", "peace talks", "peace deal", "de escalation",
        "de-escalation", "diplomatic agreement", "diplomatic breakthrough",
        "sanctions relief",
    )),
)

ESCALATION_CATEGORIES = {
    "conflict_escalation", "sanctions_trade", "shipping_logistics",
    "energy_supply", "political_uncertainty",
}
DEESCALATION_CATEGORIES = {"diplomacy_deescalation"}

CHANNEL_BY_CATEGORY = {
    "conflict_escalation": ("risk", "security"),
    "sanctions_trade": ("trade", "policy"),
    "shipping_logistics": ("shipping", "trade"),
    "energy_supply": ("energy", "inflation"),
    "political_uncertainty": ("policy", "risk"),
    "diplomacy_deescalation": ("risk", "diplomacy"),
}

SEVERITY_WORDS = {
    "critical": ("major escalation", "full scale", "full-scale", "invasion", "state of emergency"),
    "high": ("missile", "military strike", "airstrike", "blockade", "embargo", "attack"),
    "medium": ("sanction", "tariff", "export control", "political crisis", "peace talks"),
}

DURATION_FACTORS = {
    "intraday": 0.45,
    "short": 0.60,
    "short_term": 0.60,
    "medium": 0.80,
    "medium_term": 0.80,
    "long": 1.00,
    "long_term": 1.00,
    "structural": 1.00,
    "unknown": 0.65,
}


def _finite(value: Any, default: float = 0.0) -> float:
    try:
        x = float(value)
        return x if math.isfinite(x) else float(default)
    except Exception:
        return float(default)


def _clip(value: Any, lo: float = -100.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, _finite(value)))


def _norm(value: object) -> str:
    raw = unicodedata.normalize("NFKD", str(value or ""))
    raw = "".join(ch for ch in raw if not unicodedata.combining(ch)).casefold()
    raw = re.sub(r"[^a-z0-9% ]+", " ", raw)
    return re.sub(r"\s+", " ", raw).strip()


def _pair(value: object) -> tuple[str, str]:
    raw = str(value or "").upper().replace("-", "/").strip()
    if "/" not in raw:
        return "", ""
    base, quote = raw.split("/", 1)
    return base.strip(), quote.strip()


def _direction(balance: float, deadband: float = 12.0) -> str:
    x = _finite(balance)
    if x >= deadband:
        return "COMPRA"
    if x <= -deadband:
        return "VENDA"
    return "NEUTRO"


def _category(title: object, explicit: object = "") -> str:
    exp = _norm(explicit)
    if exp:
        aliases = {
            "conflict": "conflict_escalation",
            "war": "conflict_escalation",
            "sanctions": "sanctions_trade",
            "trade": "sanctions_trade",
            "shipping": "shipping_logistics",
            "energy": "energy_supply",
            "political": "political_uncertainty",
            "diplomacy": "diplomacy_deescalation",
            "deescalation": "diplomacy_deescalation",
        }
        if exp in aliases:
            return aliases[exp]
        if exp in {x[0] for x in CATEGORY_TERMS}:
            return exp
    t = _norm(title)
    for name, terms in CATEGORY_TERMS:
        if any(_norm(term) in t for term in terms):
            return name
    return ""


def _severity(item: Mapping[str, Any], title: object, category: str) -> tuple[float, str, bool]:
    raw = item.get("severity")
    explicit = raw not in (None, "")
    if explicit:
        if isinstance(raw, (int, float)):
            score = max(0.0, min(100.0, float(raw)))
        else:
            label = _norm(raw)
            score = {
                "low": 25.0, "baixo": 25.0,
                "medium": 50.0, "medio": 50.0,
                "high": 75.0, "alto": 75.0,
                "critical": 95.0, "critico": 95.0,
            }.get(label, 50.0)
    else:
        t = _norm(title)
        score = 38.0
        if category in {"shipping_logistics", "energy_supply", "sanctions_trade"}:
            score = 48.0
        for level, words in SEVERITY_WORDS.items():
            if any(_norm(x) in t for x in words):
                score = {"critical": 78.0, "high": 68.0, "medium": 52.0}[level]
                break
        # Headline-only severity is deliberately capped.
        score = min(score, 78.0)
    label = "CRÍTICO" if score >= 85 else "ALTO" if score >= 65 else "MÉDIO" if score >= 40 else "BAIXO"
    return score, label, explicit


def _duration(item: Mapping[str, Any]) -> tuple[float, str, bool]:
    days = item.get("duration_days")
    if days not in (None, ""):
        try:
            d = max(0.0, float(days))
            factor = 0.45 if d <= 1 else 0.60 if d <= 7 else 0.80 if d <= 30 else 1.00
            label = "INTRADAY" if d <= 1 else "CURTO" if d <= 7 else "MÉDIO" if d <= 30 else "LONGO"
            return factor, label, True
        except Exception:
            pass
    raw = _norm(item.get("duration", item.get("horizon", "")))
    if raw:
        key = raw.replace(" ", "_")
        factor = DURATION_FACTORS.get(key, 0.65)
        label = "CURTO" if factor <= 0.60 else "MÉDIO" if factor < 1.0 else "LONGO"
        return factor, label, True
    return DURATION_FACTORS["unknown"], "NÃO CONFIRMADO", False


def _risk_vote(item: Mapping[str, Any], category: str) -> float:
    explicit = _norm(item.get("risk_regime", item.get("market_regime", "")))
    if explicit:
        if explicit in {"risk off", "riskoff", "defensive", "aversao a risco"}:
            return 1.0
        if explicit in {"risk on", "riskon", "de escalation", "deescalation", "descompressao"}:
            return -1.0
        if explicit in {"neutral", "neutro", "mixed", "misto"}:
            return 0.0
    return {
        "conflict_escalation": 1.00,
        "sanctions_trade": 0.70,
        "shipping_logistics": 0.85,
        "energy_supply": 0.80,
        "political_uncertainty": 0.45,
        "diplomacy_deescalation": -0.80,
    }.get(category, 0.0)


def _story_key(item: Mapping[str, Any]) -> str:
    story_id = str(item.get("story_id") or item.get("event_id") or "").strip()
    if story_id:
        return "id:" + story_id
    title = _norm(item.get("title", item.get("headline", item.get("name", ""))))
    if title:
        return "title:" + title
    return ""


def _source_quality(item: Mapping[str, Any], *, structured: bool) -> float:
    if item.get("fresh") is False or item.get("stale") is True:
        return 0.0
    explicit_q = item.get("quality")
    if explicit_q not in (None, ""):
        base = max(0.0, min(100.0, _finite(explicit_q)))
    else:
        source_factor = max(0.45, min(1.35, _finite(item.get("source_factor", 1.0), 1.0)))
        base = min(92.0, 68.0 * source_factor)
        if structured:
            base = max(base, 75.0)
    recency = max(0.10, min(1.0, _finite(item.get("recency_factor", 1.0), 1.0)))
    independence = max(0.25, min(1.0, _finite(item.get("independence_factor", 1.0), 1.0)))
    return max(0.0, min(100.0, base * recency * independence))


def _explicit_currency_impacts(item: Mapping[str, Any]) -> dict[str, float]:
    raw = item.get("currency_impacts", item.get("fx_impacts", {}))
    if not isinstance(raw, Mapping):
        return {}
    out = {}
    for ccy, value in raw.items():
        code = str(ccy or "").upper().strip()
        if len(code) != 3:
            continue
        if isinstance(value, Mapping):
            value = value.get("impact", value.get("balance", value.get("score", 0)))
        try:
            out[code] = _clip(value)
        except Exception:
            continue
    return out


def _explicit_pair_impact(item: Mapping[str, Any], pair: str) -> float | None:
    raw = item.get("pair_impacts", {})
    if not isinstance(raw, Mapping):
        return None
    wanted = pair.upper().replace("-", "/")
    for key, value in raw.items():
        normalized = str(key or "").upper().replace("-", "/").strip()
        if normalized != wanted:
            continue
        if isinstance(value, Mapping):
            value = value.get("impact", value.get("balance", value.get("score")))
        try:
            return _clip(float(value))
        except Exception:
            return None
    return None


def _list_field(item: Mapping[str, Any], *names: str) -> list[str]:
    for name in names:
        raw = item.get(name)
        if isinstance(raw, Sequence) and not isinstance(raw, (str, bytes)):
            return [str(x).strip() for x in raw if str(x).strip()]
        if isinstance(raw, str) and raw.strip():
            return [raw.strip()]
    return []


def _structured_events(state: Mapping[str, Any]) -> list[dict[str, Any]]:
    raw = state.get("geopolitical_events", state.get("geo_events", []))
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)):
        return []
    return [dict(x) for x in raw if isinstance(x, Mapping)]


def _currency_articles(state: Mapping[str, Any], base: str, quote: str) -> list[dict[str, Any]]:
    currencies = dict(state.get("currencies", {}) or {})
    rows: list[dict[str, Any]] = []
    for ccy in (base, quote):
        cdata = dict(currencies.get(ccy, {}) or {})
        for raw in list(cdata.get("articles", []) or []):
            if not isinstance(raw, Mapping):
                continue
            item = dict(raw)
            item["_currency_context"] = ccy
            rows.append(item)
    return rows


def build_geopolitical_context(pair: object, state: Mapping[str, Any] | None) -> dict[str, Any]:
    base, quote = _pair(pair)
    s = dict(state or {})
    if not base or not quote:
        return {
            "schema": SCHEMA, "available": False, "direction": "INDISPONÍVEL",
            "balance": 0.0, "quality": 0.0, "coverage": 0.0, "events": [],
            "reasons": [], "risks": ["Par inválido ou ausente."],
            "decision_effect": False, "changes_gate": False,
            "changes_score_mestre": False, "real_orders_enabled": False,
        }

    candidates: list[tuple[dict[str, Any], bool]] = []
    candidates.extend((x, True) for x in _structured_events(s))
    candidates.extend((x, False) for x in _currency_articles(s, base, quote))

    stories: dict[str, dict[str, Any]] = {}
    dropped_non_geo = 0
    for item, structured in candidates:
        title = str(item.get("title", item.get("headline", item.get("name", item.get("event", "")))) or "")
        cat = _category(title, item.get("category", item.get("event_type", "")))
        if not cat:
            dropped_non_geo += 1
            continue
        key = _story_key(item)
        if not key:
            continue

        severity, severity_label, severity_explicit = _severity(item, title, cat)
        duration_factor, duration_label, duration_explicit = _duration(item)
        quality = _source_quality(item, structured=structured)
        if quality <= 0:
            continue
        channels = set(str(x) for x in CHANNEL_BY_CATEGORY.get(cat, ()))
        raw_channels = item.get("channels", [])
        if isinstance(raw_channels, Sequence) and not isinstance(raw_channels, (str, bytes)):
            channels.update(str(x).strip() for x in raw_channels if str(x).strip())

        rec = stories.setdefault(key, {
            "story_key": key,
            "title": title,
            "category": cat,
            "channels": set(),
            "sources": set(),
            "quality_values": [],
            "severity_values": [],
            "duration_values": [],
            "severity_labels": [],
            "duration_labels": [],
            "severity_explicit": False,
            "duration_explicit": False,
            "risk_votes": [],
            "currency_impacts": defaultdict(list),
            "pair_impacts": [],
            "regions": set(),
            "countries": set(),
            "commodities": set(),
            "mentions": set(),
            "structured": False,
        })
        rec["structured"] = bool(rec["structured"] or structured)
        rec["channels"].update(channels)
        source = str(item.get("source") or item.get("provider") or "").strip()
        if source:
            rec["sources"].add(source)
        rec["quality_values"].append(quality)
        rec["severity_values"].append(severity)
        rec["duration_values"].append(duration_factor)
        rec["severity_labels"].append(severity_label)
        rec["duration_labels"].append(duration_label)
        rec["severity_explicit"] = bool(rec["severity_explicit"] or severity_explicit)
        rec["duration_explicit"] = bool(rec["duration_explicit"] or duration_explicit)
        rec["risk_votes"].append(_risk_vote(item, cat) * severity / 100.0 * duration_factor)
        rec["regions"].update(_list_field(item, "regions", "affected_regions"))
        rec["countries"].update(_list_field(item, "countries", "affected_countries"))
        rec["commodities"].update(_list_field(item, "commodities", "affected_commodities"))
        pair_impact = _explicit_pair_impact(item, f"{base}/{quote}")
        if pair_impact is not None:
            rec["pair_impacts"].append(pair_impact)

        explicit = _explicit_currency_impacts(item)
        for ccy, impact in explicit.items():
            rec["currency_impacts"][ccy].append(impact)
        context_ccy = str(item.get("_currency_context") or "").upper().strip()
        if context_ccy in {base, quote}:
            rec["mentions"].add(context_ccy)
            if "weighted_impact" in item:
                # Existing news engine impact is already currency-specific.
                rec["currency_impacts"][context_ccy].append(_clip(_finite(item.get("weighted_impact")) * 100.0))

    events: list[dict[str, Any]] = []
    for rec in stories.values():
        quality = max(rec["quality_values"]) if rec["quality_values"] else 0.0
        # Multiple independent named sources strengthen coverage, but not beyond 95.
        if len(rec["sources"]) >= 2:
            quality = min(95.0, quality + min(12.0, (len(rec["sources"]) - 1) * 4.0))
        severity = max(rec["severity_values"]) if rec["severity_values"] else 0.0
        duration_factor = max(rec["duration_values"]) if rec["duration_values"] else 0.65
        risk_vote = sum(rec["risk_votes"]) / max(1, len(rec["risk_votes"]))
        impacts = {}
        for ccy, vals in rec["currency_impacts"].items():
            impacts[ccy] = sum(vals) / max(1, len(vals))
        currency_pair = _clip(impacts.get(base, 0.0) - impacts.get(quote, 0.0))
        explicit_pair = (
            sum(rec["pair_impacts"]) / len(rec["pair_impacts"])
            if rec["pair_impacts"] else None
        )
        direct_pair = _clip(explicit_pair if explicit_pair is not None else currency_pair)
        risk_pair = _clip(
            risk_vote * (RISK_SENSITIVITY.get(base, 0.0) - RISK_SENSITIVITY.get(quote, 0.0)) * 55.0
        )
        # Explicit pair/currency impact has priority; broad regime is contextual and lower-weight.
        pair_balance = _clip(0.72 * direct_pair + 0.28 * risk_pair)
        if not impacts and explicit_pair is None:
            quality *= 0.78
        if not rec["severity_explicit"]:
            quality *= 0.92
        if not rec["duration_explicit"]:
            quality *= 0.94

        events.append({
            "story_key": rec["story_key"],
            "title": rec["title"],
            "category": rec["category"],
            "channels": sorted(rec["channels"]),
            "sources": sorted(rec["sources"]),
            "source_count": len(rec["sources"]),
            "mentions": sorted(rec["mentions"]),
            "severity": round(severity, 1),
            "severity_label": max(rec["severity_labels"], key=lambda x: ("BAIXO","MÉDIO","ALTO","CRÍTICO").index(x)) if rec["severity_labels"] else "N/D",
            "duration_factor": round(duration_factor, 2),
            "duration_label": rec["duration_labels"][0] if rec["duration_labels"] else "NÃO CONFIRMADO",
            "quality": round(max(0.0, min(100.0, quality)), 1),
            "risk_vote": round(risk_vote, 3),
            "currency_impacts": {k: round(v, 1) for k, v in impacts.items()},
            "pair_impact_explicit": explicit_pair is not None,
            "regions": sorted(rec["regions"]),
            "countries": sorted(rec["countries"]),
            "commodities": sorted(rec["commodities"]),
            "direct_pair_balance": round(direct_pair, 1),
            "risk_pair_balance": round(risk_pair, 1),
            "pair_balance": round(pair_balance, 1),
            "structured": bool(rec["structured"]),
        })

    if not events:
        return {
            "schema": SCHEMA, "pair": f"{base}/{quote}", "available": False,
            "direction": "INDISPONÍVEL", "balance": 0.0, "quality": 0.0,
            "coverage": 0.0, "event_count": 0, "independent_stories": 0,
            "risk_regime": "INDISPONÍVEL", "severity": "N/D",
            "geo_conflict": False, "channels": [], "events": [],
            "reasons": [], "risks": [
                "Sem evidência geopolítica independente suficiente; ausência não vira sinal neutro."
            ],
            "dropped_non_geo": dropped_non_geo,
            "probability": False, "decision_effect": False,
            "changes_gate": False, "changes_score_mestre": False,
            "changes_weights": False, "real_orders_enabled": False,
            "automatic_execution": False,
        }

    weighted = 0.0
    denom = 0.0
    for ev in events:
        eff = (0.30 + 0.70 * ev["quality"] / 100.0) * (0.45 + 0.55 * ev["severity"] / 100.0)
        weighted += ev["pair_balance"] * eff
        denom += eff
    balance = _clip(weighted / denom if denom else 0.0)

    qualities = [ev["quality"] for ev in events]
    quality = sum(qualities) / len(qualities)
    independent_stories = len(events)
    source_union = {src.casefold() for ev in events for src in ev["sources"]}
    source_diversity = min(1.0, len(source_union) / 4.0)
    story_coverage = min(1.0, independent_stories / 4.0)
    coverage = 100.0 * (0.65 * story_coverage + 0.35 * source_diversity)

    positives = [ev for ev in events if ev["pair_balance"] >= 18]
    negatives = [ev for ev in events if ev["pair_balance"] <= -18]
    geo_conflict = bool(positives and negatives)
    risks: list[str] = [
        "Geopolítica é contexto de mercado; manchetes podem mudar rapidamente e causalidade não é garantida."
    ]
    if geo_conflict:
        quality *= 0.82
        risks.append("Eventos geopolíticos independentes apontam impactos opostos para o par.")
    if independent_stories == 1:
        quality *= 0.78
        risks.append("A leitura depende de uma única história independente; confirmação adicional é necessária.")
    if any(not ev["structured"] for ev in events):
        risks.append("Parte da classificação vem de manchete; severidade/duração inferidas recebem desconto de qualidade.")
    if any((not ev["currency_impacts"]) and (not ev.get("pair_impact_explicit")) for ev in events):
        risks.append("Evento sem impacto cambial explícito usa apenas efeito amplo de regime, com peso reduzido.")

    avg_risk = sum(ev["risk_vote"] * ev["quality"] for ev in events) / max(1e-9, sum(ev["quality"] for ev in events))
    risk_regime = "RISK-OFF" if avg_risk >= 0.18 else "DESCOMPRESSÃO" if avg_risk <= -0.18 else "MISTO/NEUTRO"
    max_severity = max(ev["severity"] for ev in events)
    severity_label = "CRÍTICO" if max_severity >= 85 else "ALTO" if max_severity >= 65 else "MÉDIO" if max_severity >= 40 else "BAIXO"
    channels = sorted({ch for ev in events for ch in ev["channels"]})

    top = sorted(events, key=lambda x: (abs(x["pair_balance"]), x["quality"], x["severity"]), reverse=True)[:5]
    reasons = []
    for ev in top:
        src = ", ".join(ev["sources"][:2]) if ev["sources"] else "fonte não identificada"
        reasons.append(
            f"{ev['category']}: saldo {ev['pair_balance']:+.0f} · severidade {ev['severity_label']} · "
            f"duração {ev['duration_label']} · {src}."
        )

    available = bool(events and quality >= 22.0)
    return {
        "schema": SCHEMA,
        "pair": f"{base}/{quote}",
        "available": available,
        "direction": _direction(balance) if available else "INDISPONÍVEL",
        "balance": round(balance if available else 0.0, 1),
        "quality": round(max(0.0, min(100.0, quality)) if available else 0.0, 1),
        "coverage": round(max(0.0, min(100.0, coverage)), 1),
        "event_count": len(events),
        "independent_stories": independent_stories,
        "source_count": len(source_union),
        "risk_regime": risk_regime,
        "severity": severity_label,
        "geo_conflict": geo_conflict,
        "channels": channels,
        "regions": sorted({x for ev in events for x in ev.get("regions",[])}),
        "countries": sorted({x for ev in events for x in ev.get("countries",[])}),
        "commodities": sorted({x for ev in events for x in ev.get("commodities",[])}),
        "events": top,
        "reasons": reasons,
        "risks": risks[:8],
        "dropped_non_geo": dropped_non_geo,
        "probability": False,
        "decision_effect": False,
        "changes_gate": False,
        "changes_score_mestre": False,
        "changes_weights": False,
        "real_orders_enabled": False,
        "automatic_execution": False,
    }


__all__ = ["SCHEMA", "RISK_SENSITIVITY", "build_geopolitical_context"]