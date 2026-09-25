"""AION Live Event Intelligence.

Builds a deterministic, read-only event radar from news/calendar evidence already
available inside AtlasQuant. It does not fetch the web, send notifications,
publish content, modify trading scores or place orders.

Important truth contract:
- RSS/news headlines are evidence of reporting, not automatic confirmation that
  the reported real-world event happened exactly as stated.
- market impact channels are hypotheses, never trade signals;
- stale source snapshots cannot produce breaking alerts;
- scheduled macro events may be confirmed as schedule facts when provenance is
  explicit, but their market reaction remains hypothetical.
"""
from __future__ import annotations

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from hashlib import sha256
from typing import Any, Mapping, Sequence
import math
import re
import unicodedata

SCHEMA = "ATLASQUANT_AION_LIVE_EVENT_INTELLIGENCE_V1"

MAX_NEWS_AGE_MINUTES = 180.0
MAX_PAYLOAD_AGE_MINUTES = 120.0
MAX_EVENTS = 80

_CATEGORY_PATTERNS = (
    ("GEOPOLITICAL_DEESCALATION", (
        "ceasefire","truce","peace deal","de-escalat","deescalat",
        "cessar-fogo","trégua","acordo de paz",
    )),
    ("GEOPOLITICAL_ESCALATION", (
        "airstrike","air strike","missile","drone attack","military strike",
        "attack on","attacks on","retaliat","invasion","war escalat",
        "bombard","blockade","troops enter","sanctions escalat",
        "ataque","míssil","missil","retalia","invasão","invasao",
        "bombarde","bloqueio militar",
    )),
    ("BANKING_STRESS", (
        "bank run","bank failure","bank collapse","liquidity crisis",
        "emergency liquidity","deposit flight","falência banc","falencia banc",
        "corrida bancária","corrida bancaria",
    )),
    ("CENTRAL_BANK_HAWKISH", (
        "rate hike","raises rates","raised rates","hawkish","higher for longer",
        "tightening","aumento de juros","subiu juros","juros mais altos",
    )),
    ("CENTRAL_BANK_DOVISH", (
        "rate cut","cuts rates","cut rates","dovish","easing",
        "corte de juros","cortou juros","afrouxamento",
    )),
    ("INFLATION", (
        "inflation","cpi","pce","consumer prices","inflação","inflacao",
    )),
    ("LABOR", (
        "payroll","nonfarm","unemployment","jobless","employment",
        "desemprego","emprego",
    )),
    ("GROWTH", (
        "gdp","recession","growth","pmi","ism","pib","recessão","recessao",
    )),
    ("ENERGY_SUPPLY", (
        "oil supply","opec","pipeline","refinery","strait of hormuz",
        "energy supply","petróleo","petroleo","oleoduto","refinaria",
    )),
    ("TRADE_POLICY", (
        "tariff","trade war","export ban","import ban","tarifa",
        "guerra comercial","proibição de export","proibicao de export",
    )),
)

_IMPACT_TEMPLATES = {
    "GEOPOLITICAL_ESCALATION": (
        ("Petróleo","pressão de alta possível","prêmio de risco/oferta pode aumentar"),
        ("Ouro","demanda defensiva possível","busca por proteção pode crescer"),
        ("USD","fluxo defensivo possível","liquidez e procura por segurança podem favorecer o dólar"),
        ("JPY/CHF","fluxo defensivo possível","moedas historicamente usadas em risk-off"),
        ("Índices globais","pressão negativa possível","aversão a risco pode aumentar"),
    ),
    "GEOPOLITICAL_DEESCALATION": (
        ("Petróleo","prêmio de risco pode cair","menor risco percebido sobre oferta/rotas"),
        ("Ouro","demanda defensiva pode diminuir","redução de hedge"),
        ("Índices globais","alívio positivo possível","apetite a risco pode melhorar"),
    ),
    "BANKING_STRESS": (
        ("Índices financeiros","pressão negativa possível","risco sistêmico/liquidez"),
        ("Treasuries","demanda defensiva possível","busca por segurança"),
        ("USD","reação dependente do epicentro","liquidez defensiva versus risco doméstico"),
        ("Ouro","apoio possível","busca por proteção"),
    ),
    "CENTRAL_BANK_HAWKISH": (
        ("Moeda local","pressão de alta possível","diferencial esperado de juros"),
        ("Yields locais","pressão de alta possível","reprecificação de política monetária"),
        ("Índices locais","pressão negativa possível","taxa de desconto maior"),
    ),
    "CENTRAL_BANK_DOVISH": (
        ("Moeda local","pressão de baixa possível","diferencial esperado de juros"),
        ("Yields locais","pressão de baixa possível","reprecificação mais flexível"),
        ("Índices locais","alívio positivo possível","taxa de desconto menor"),
    ),
    "INFLATION": (
        ("Moeda relacionada","reação depende da surpresa","inflação altera trajetória esperada de juros"),
        ("Yields","reação depende da surpresa","curva reprecifica política monetária"),
        ("Índices","reação pode ser inversa aos yields","condições financeiras"),
    ),
    "LABOR": (
        ("Moeda relacionada","reação depende da surpresa","atividade/juros esperados"),
        ("Yields","reação depende da surpresa","trajetória de política monetária"),
        ("Índices","reação pode ser mista","crescimento versus juros"),
    ),
    "GROWTH": (
        ("Moeda relacionada","reação depende da surpresa","crescimento relativo"),
        ("Índices","reação depende de crescimento e juros","lucros versus política monetária"),
        ("Yields","reação depende do ciclo","crescimento e inflação esperados"),
    ),
    "ENERGY_SUPPLY": (
        ("Petróleo","volatilidade/alta possível","mudança esperada de oferta"),
        ("CAD","sensibilidade positiva possível ao petróleo","termos de troca"),
        ("Índices consumidores de energia","pressão de custo possível","energia mais cara"),
    ),
    "TRADE_POLICY": (
        ("Moedas expostas","volatilidade possível","fluxos comerciais e crescimento"),
        ("Índices globais","pressão negativa possível","incerteza e custos comerciais"),
        ("Commodities","reação depende dos países/setores","mudança de demanda/fluxo"),
    ),
    "SCHEDULED_MACRO": (
        ("FX","volatilidade possível","surpresa versus consenso"),
        ("Yields","reprecificação possível","mudança de expectativa de juros"),
        ("Índices","volatilidade possível","crescimento/inflação/juros"),
    ),
    "OTHER": (
        ("Mercado","impacto não mapeado","evidência insuficiente para mecanismo específico"),
    ),
}


def _clean(value: Any, limit: int = 800) -> str:
    return " ".join(str(value or "").replace("\x00","").split())[:limit]


def _norm(value: Any) -> str:
    raw=unicodedata.normalize("NFKD",str(value or ""))
    return "".join(ch for ch in raw if not unicodedata.combining(ch)).casefold()


def _finite(value: Any) -> float | None:
    try:
        out=float(value)
        return out if math.isfinite(out) else None
    except Exception:
        return None


def _utc(value: Any) -> datetime | None:
    if isinstance(value,datetime):
        dt=value
    else:
        text=_clean(value,160)
        if not text:
            return None
        try:
            dt=datetime.fromisoformat(text.replace("Z","+00:00"))
        except Exception:
            try:
                dt=parsedate_to_datetime(text)
            except Exception:
                return None
    if dt.tzinfo is None:
        dt=dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _age_minutes(value: Any, now: datetime) -> float | None:
    dt=_utc(value)
    if dt is None:
        return None
    return round(max(0.0,(now-dt).total_seconds()/60.0),2)


def _event_id(*parts: Any) -> str:
    raw="|".join(_norm(x) for x in parts)
    return "EVT-"+sha256(raw.encode("utf-8")).hexdigest()[:16].upper()


def _category(title: Any, theme: Any="") -> str:
    text=_norm(f"{title} {theme}")
    for category,patterns in _CATEGORY_PATTERNS:
        if any(_norm(pattern) in text for pattern in patterns):
            return category
    return "OTHER"


def _impact_channels(category: str) -> list[dict[str,str]]:
    return [
        {
            "asset":asset,
            "direction":direction,
            "mechanism":mechanism,
            "truth_state":"HYPOTHESIS",
        }
        for asset,direction,mechanism in _IMPACT_TEMPLATES.get(
            category,_IMPACT_TEMPLATES["OTHER"]
        )
    ]


def _relevance_points(value: Any) -> float:
    text=_norm(value)
    if "alta" in text or "high" in text:
        return 18.0
    if "media" in text or "medium" in text:
        return 10.0
    return 4.0


def _urgency(
    *,
    category: str,
    age_minutes: float | None,
    relevance: Any,
    weighted_impact: Any,
    source_name: Any,
) -> int:
    score=0.0
    if age_minutes is None:
        score+=2
    elif age_minutes<=15:
        score+=35
    elif age_minutes<=60:
        score+=30
    elif age_minutes<=180:
        score+=22
    elif age_minutes<=720:
        score+=8

    score+=_relevance_points(relevance)
    if category in {"GEOPOLITICAL_ESCALATION","BANKING_STRESS"}:
        score+=24
    elif category in {"GEOPOLITICAL_DEESCALATION","CENTRAL_BANK_HAWKISH","CENTRAL_BANK_DOVISH"}:
        score+=18
    elif category in {"INFLATION","LABOR","GROWTH","ENERGY_SUPPLY","TRADE_POLICY"}:
        score+=12

    impact=abs(_finite(weighted_impact) or 0.0)
    score+=min(12.0,impact*12.0)

    src=_norm(source_name)
    if any(x in src for x in ("reuters","associated press","ap news","bloomberg")):
        score+=8
    return int(max(0,min(100,round(score))))


def _alert_level(urgency: int, *, fresh: bool, category: str) -> str:
    if not fresh:
        return "NONE"
    if urgency>=80:
        return "URGENT_REVIEW"
    if urgency>=60:
        return "HIGH_REVIEW"
    if urgency>=40 and category!="OTHER":
        return "WATCH"
    return "NONE"


def news_events(
    payload: Mapping[str,Any] | None,
    *,
    provenance: Any="",
    now: datetime | None=None,
) -> dict[str,Any]:
    current=now or datetime.now(timezone.utc)
    data=dict(payload or {})
    updated_at=data.get("updated_at")
    payload_age=_age_minutes(updated_at,current)
    provenance_text=_clean(provenance,200)
    provenance_confirmed=provenance_text.startswith("GitHub:")
    source_fresh=bool(
        provenance_confirmed
        and payload_age is not None
        and payload_age<=MAX_PAYLOAD_AGE_MINUTES
    )

    currencies=data.get("currencies") if isinstance(data.get("currencies"),Mapping) else {}
    grouped: dict[str,dict[str,Any]]={}
    for currency,raw_ccy in currencies.items():
        if not isinstance(raw_ccy,Mapping):
            continue
        for article in list(raw_ccy.get("articles",[]) or []):
            if not isinstance(article,Mapping):
                continue
            title=_clean(article.get("title"),500)
            if not title:
                continue
            story_id=_clean(article.get("story_id"),100)
            key=story_id or _event_id(title,article.get("published_at"))
            row=grouped.setdefault(key,{
                "story_key":key,
                "title":title,
                "published_at":article.get("published_at"),
                "sources":set(),
                "providers":set(),
                "currencies":set(),
                "relevance":article.get("relevance"),
                "theme":article.get("theme"),
                "weighted_impact":_finite(article.get("weighted_impact")) or 0.0,
                "directional_notes":set(),
                "link":_clean(article.get("link"),1000),
            })
            row["sources"].add(_clean(article.get("source"),180) or "unknown")
            row["providers"].add(_clean(article.get("provider"),180) or "unknown")
            row["currencies"].add(_clean(currency,20))
            direction=_clean(article.get("direction"),100)
            if direction:
                row["directional_notes"].add(direction)
            impact=_finite(article.get("weighted_impact"))
            if impact is not None and abs(impact)>abs(float(row["weighted_impact"])):
                row["weighted_impact"]=impact

    events=[]
    for row in grouped.values():
        category=_category(row["title"],row.get("theme"))
        age=_age_minutes(row.get("published_at"),current)
        fresh=bool(source_fresh and age is not None and age<=MAX_NEWS_AGE_MINUTES)
        sources=sorted(x for x in row["sources"] if x)
        urgency=_urgency(
            category=category,
            age_minutes=age,
            relevance=row.get("relevance"),
            weighted_impact=row.get("weighted_impact"),
            source_name=" ".join(sources),
        )
        alert=_alert_level(urgency,fresh=fresh,category=category)
        events.append({
            "event_id":_event_id(row["story_key"],row["title"]),
            "kind":"NEWS_REPORT",
            "category":category,
            "headline":row["title"],
            "reported_at":_clean(row.get("published_at"),120),
            "age_minutes":age,
            "source_snapshot_fresh":source_fresh,
            "fresh":fresh,
            "truth_state":"INFERENCE" if provenance_confirmed else "UNKNOWN",
            "truth_note":(
                "Manchete/reportagem observada; o evento real descrito não é promovido automaticamente a fato confirmado."
            ),
            "sources":sources,
            "providers":sorted(row["providers"]),
            "source_count":len(sources),
            "currencies":sorted(row["currencies"]),
            "theme":_clean(row.get("theme"),120),
            "upstream_direction_notes":sorted(row["directional_notes"]),
            "urgency_score":urgency,
            "alert_level":alert,
            "impact_channels":_impact_channels(category),
            "impact_truth_state":"HYPOTHESIS",
            "link":row.get("link") or "",
            "is_trade_signal":False,
            "automatic_notification_sent":False,
            "automatic_execution":False,
        })

    events.sort(key=lambda x:(-int(x["urgency_score"]),float(x["age_minutes"] or 10**9)))
    return {
        "source_state":"FRESH" if source_fresh else "STALE_OR_UNCONFIRMED",
        "payload_updated_at":_clean(updated_at,120),
        "payload_age_minutes":payload_age,
        "provenance":provenance_text,
        "provenance_confirmed":provenance_confirmed,
        "events":events[:MAX_EVENTS],
    }


def scheduled_event(
    next_event: Mapping[str,Any] | None,
) -> dict[str,Any] | None:
    event=dict(next_event or {})
    if not bool(event.get("disponivel",False)):
        return None
    source=_clean(event.get("fonte"),180)
    name=_clean(event.get("evento"),240) or "Evento macro"
    impact=_norm(event.get("impacto"))
    days=_finite(event.get("dias"))
    if days is None:
        urgency=45
    elif days<=0:
        urgency=78 if any(x in impact for x in ("maximo","alto","high")) else 60
    elif days<=1:
        urgency=65 if any(x in impact for x in ("maximo","alto","high")) else 48
    elif days<=3:
        urgency=42
    else:
        urgency=25
    truth="CONFIRMED" if source else "UNKNOWN"
    schedule_fresh=bool(source)
    return {
        "event_id":_event_id("calendar",name,event.get("data_txt") or event.get("data")),
        "kind":"SCHEDULED_MACRO",
        "category":"SCHEDULED_MACRO",
        "headline":name,
        "reported_at":_clean(event.get("data_txt") or event.get("data"),120),
        "age_minutes":None,
        "source_snapshot_fresh":schedule_fresh,
        "fresh":schedule_fresh,
        "truth_state":truth,
        "truth_note":"Agenda confirmada somente quando há proveniência explícita; reação de mercado continua hipotética.",
        "sources":[source] if source else [],
        "providers":[],
        "source_count":1 if source else 0,
        "currencies":[],
        "theme":_clean(event.get("tipo"),120),
        "upstream_direction_notes":[],
        "urgency_score":int(urgency),
        "alert_level":_alert_level(int(urgency),fresh=schedule_fresh,category="SCHEDULED_MACRO"),
        "impact_channels":_impact_channels("SCHEDULED_MACRO"),
        "impact_truth_state":"HYPOTHESIS",
        "link":"",
        "is_trade_signal":False,
        "automatic_notification_sent":False,
        "automatic_execution":False,
    }


def live_event_snapshot(
    *,
    news_payload: Mapping[str,Any] | None,
    news_provenance: Any="",
    next_event: Mapping[str,Any] | None=None,
    reliability: Mapping[str,Any] | None=None,
    now: datetime | None=None,
) -> dict[str,Any]:
    news=news_events(news_payload,provenance=news_provenance,now=now)
    events=list(news["events"])
    scheduled=scheduled_event(next_event)
    if scheduled:
        events.append(scheduled)
    events.sort(key=lambda x:(-int(x.get("urgency_score") or 0),x.get("headline") or ""))

    reliability_map=dict(reliability or {})
    degraded=(
        reliability_map.get("degraded_mode")
        if isinstance(reliability_map.get("degraded_mode"),Mapping)
        else {}
    )
    reliability_state=_clean(degraded.get("state") or "UNKNOWN",60).upper()
    alerts=[
        event for event in events
        if event.get("alert_level") in {"WATCH","HIGH_REVIEW","URGENT_REVIEW"}
    ]
    urgent=[x for x in alerts if x.get("alert_level")=="URGENT_REVIEW"]
    fresh_news=[x for x in events if x.get("kind")=="NEWS_REPORT" and x.get("fresh")]

    if reliability_state=="FAIL_CLOSED":
        state="FAIL_CLOSED"
    elif news["source_state"]=="FRESH":
        state="WATCHING"
    elif scheduled:
        state="SCHEDULE_ONLY"
    else:
        state="STALE_OR_UNAVAILABLE"

    return {
        "schema":SCHEMA,
        "state":state,
        "news_source_state":news["source_state"],
        "news_payload_updated_at":news["payload_updated_at"],
        "news_payload_age_minutes":news["payload_age_minutes"],
        "events":events[:MAX_EVENTS],
        "event_count":len(events),
        "fresh_news_events":len(fresh_news),
        "alert_count":len(alerts),
        "urgent_review_count":len(urgent),
        "top_alerts":alerts[:10],
        "delivery_ready":bool(alerts and state=="WATCHING"),
        "continuous_runtime_required":True,
        "continuous_runtime_confirmed":False,
        "automatic_notification_sent":False,
        "notification_requires_integration":True,
        "market_impact_truth_state":"HYPOTHESIS",
        "is_trade_signal":False,
        "automatic_execution":False,
        "real_orders_enabled":False,
    }


__all__=[
    "SCHEMA",
    "MAX_NEWS_AGE_MINUTES",
    "MAX_PAYLOAD_AGE_MINUTES",
    "news_events",
    "scheduled_event",
    "live_event_snapshot",
]
