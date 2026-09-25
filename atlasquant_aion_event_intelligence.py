"""AION real-time event intelligence and governed alerting.

This layer consumes evidence already produced by AtlasQuant (news runtime,
calendar, Source Mesh / Reliability state) and turns it into:
- deduplicated event records;
- explicit fact vs report vs inference labels;
- market-impact hypotheses by asset/channel;
- internal alert candidates;
- compact event/alert journals for Checkpoint persistence.

It performs no provider I/O, sends no external notification, changes no market
score, places no orders and never turns a hypothesis into a fact.
"""
from __future__ import annotations

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from hashlib import sha256
from typing import Any, Mapping, Sequence
import json
import math
import re
import unicodedata

SCHEMA="ATLASQUANT_AION_EVENT_INTELLIGENCE_V1"
MAX_EVENTS=1200
MAX_ALERTS=1200

CATEGORIES=(
    "GEOPOLITICAL_ESCALATION",
    "GEOPOLITICAL_DEESCALATION",
    "CENTRAL_BANK_HAWKISH",
    "CENTRAL_BANK_DOVISH",
    "INFLATION",
    "LABOR",
    "GROWTH",
    "ENERGY_SUPPLY",
    "TRADE_FISCAL_POLICY",
    "SYSTEMIC_RISK",
    "GENERAL_MARKET",
)
ALERT_STATES=("NONE","WATCH","REVIEW_INTERNAL","URGENT_INTERNAL","HOLD")

_OFFICIAL_HINTS=(
    ".gov","federalreserve.gov","ecb.europa.eu","bankofengland.co.uk",
    "boj.or.jp","bankofcanada.ca","rba.gov.au","snb.ch","imf.org",
    "worldbank.org","bis.org",
)

_RULES=(
    ("GEOPOLITICAL_DEESCALATION",(
        "ceasefire","cessar-fogo","truce","peace talks","peace deal",
        "de-escalat","deescalat","withdraws troops","retirada de tropas",
    )),
    ("GEOPOLITICAL_ESCALATION",(
        "attack","attacks","strike","strikes","missile","missiles","bombing",
        "airstrike","air strike","invasion","invades","war ","warfare",
        "sanction","sanctions","retaliat","drone attack","military action",
        "ataque","ataques","míssil","missil","bombardeio","invasão","invasao",
        "guerra","sanções","sancoes","retalia",
    )),
    ("SYSTEMIC_RISK",(
        "bank run","bank failure","bank collapse","default","credit event",
        "liquidity crisis","systemic risk","emergency bailout","rescue package",
        "quebra de banco","crise de liquidez","calote","risco sistêmico",
    )),
    ("CENTRAL_BANK_HAWKISH",(
        "hawkish","rate hike","hikes rates","higher for longer","tightening",
        "raises rates","raise rates","juros mais altos","alta de juros",
        "aperto monetário","aperto monetario",
    )),
    ("CENTRAL_BANK_DOVISH",(
        "dovish","rate cut","cuts rates","easing","lower rates","stimulus",
        "corte de juros","redução de juros","reducao de juros",
        "afrouxamento monetário","afrouxamento monetario",
    )),
    ("ENERGY_SUPPLY",(
        "oil supply","crude supply","opec","pipeline","refinery","strait of hormuz",
        "hormuz","oil output","production cut","production cuts","energy supply",
        "petróleo","petroleo","oleoduto","refinaria","produção de petróleo",
        "producao de petroleo",
    )),
    ("INFLATION",(
        "cpi","pce","inflation","consumer prices","core prices",
        "inflação","inflacao","preços ao consumidor","precos ao consumidor",
    )),
    ("LABOR",(
        "payroll","nonfarm","jobs report","unemployment","jobless","wages",
        "emprego","desemprego","salários","salarios",
    )),
    ("GROWTH",(
        "gdp","retail sales","industrial production","pmi","ism",
        "growth","recession","recessão","recessao","pib","vendas no varejo",
    )),
    ("TRADE_FISCAL_POLICY",(
        "tariff","tariffs","trade war","fiscal package","government shutdown",
        "debt ceiling","tax cuts","tax hike","tarifa","tarifas","guerra comercial",
        "pacote fiscal","teto da dívida","teto da divida",
    )),
)

_DIRECTION_RULES=(
    ("ESCALATION",("attack","strike","missile","invasion","retaliat","sanction","ataque","míssil","missil","guerra","retalia")),
    ("DEESCALATION",("ceasefire","truce","peace deal","de-escalat","cessar-fogo")),
    ("HAWKISH",("hawkish","rate hike","raises rates","higher for longer","tightening","alta de juros","aperto monet")),
    ("DOVISH",("dovish","rate cut","cuts rates","easing","corte de juros","afrouxamento")),
    ("HOTTER",("above expectations","above forecast","hotter","accelerates","higher than expected","acima do esperado","acelerou")),
    ("COOLER",("below expectations","below forecast","cooler","slows","lower than expected","abaixo do esperado","desacelerou")),
)

_CATEGORY_SEVERITY={
    "GEOPOLITICAL_ESCALATION":94,
    "SYSTEMIC_RISK":94,
    "GEOPOLITICAL_DEESCALATION":78,
    "CENTRAL_BANK_HAWKISH":84,
    "CENTRAL_BANK_DOVISH":84,
    "ENERGY_SUPPLY":80,
    "INFLATION":78,
    "LABOR":78,
    "GROWTH":68,
    "TRADE_FISCAL_POLICY":76,
    "GENERAL_MARKET":45,
}


def _clean(value:Any,limit:int=800)->str:
    return " ".join(str(value or "").replace("\x00","").split())[:limit]


def _norm(value:Any)->str:
    raw=unicodedata.normalize("NFKD",str(value or ""))
    raw="".join(ch for ch in raw if not unicodedata.combining(ch))
    return raw.casefold()


def _finite(value:Any)->float|None:
    try:
        out=float(value)
        return out if math.isfinite(out) else None
    except Exception:
        return None


def _utc(value:Any)->datetime|None:
    if isinstance(value,datetime):
        dt=value
    else:
        text=_clean(value,160)
        if not text:
            return None
        try:
            dt=parsedate_to_datetime(text)
        except Exception:
            try:
                dt=datetime.fromisoformat(text.replace("Z","+00:00"))
            except Exception:
                return None
    if dt.tzinfo is None:
        dt=dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _age_minutes(value:Any,*,now:datetime|None=None)->float|None:
    dt=_utc(value)
    if dt is None:
        return None
    current=now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current=current.replace(tzinfo=timezone.utc)
    return round(max(0.0,(current.astimezone(timezone.utc)-dt).total_seconds()/60.0),2)


def _fingerprint(*parts:Any,prefix:str="EVT")->str:
    raw="|".join(_clean(x,1000) for x in parts)
    return prefix+"-"+sha256(raw.encode("utf-8")).hexdigest()[:18].upper()


def _is_official_source(source:Any,link:Any="")->bool:
    hay=_norm(str(source or "")+" "+str(link or ""))
    return any(token in hay for token in _OFFICIAL_HINTS)


def classify_event_text(headline:Any,theme:Any="")->dict[str,Any]:
    text=_norm(str(headline or "")+" "+str(theme or ""))
    category="GENERAL_MARKET"
    matched=[]
    for candidate,keywords in _RULES:
        found=[kw for kw in keywords if kw in text]
        if found:
            category=candidate
            matched=found[:5]
            break
    direction="UNKNOWN"
    direction_hits=[]
    for candidate,keywords in _DIRECTION_RULES:
        found=[kw for kw in keywords if kw in text]
        if found:
            direction=candidate
            direction_hits=found[:5]
            break
    return {
        "category":category,
        "directional_cue":direction,
        "classification_truth":"INFERENCE",
        "matched_keywords":matched,
        "direction_keywords":direction_hits,
        "automatic_fact_claim":False,
    }


def _currency_asset(currency:str)->str:
    c=_clean(currency,8).upper()
    return {
        "USD":"USD / DXY",
        "EUR":"EUR",
        "GBP":"GBP",
        "JPY":"JPY",
        "CHF":"CHF",
        "CAD":"CAD",
        "AUD":"AUD",
        "NZD":"NZD",
        "BRL":"BRL / WDO",
    }.get(c,c or "Moeda afetada")


def impact_hypotheses(
    category:Any,
    *,
    directional_cue:Any="UNKNOWN",
    currencies:Sequence[Any]|None=None,
)->dict[str,Any]:
    cat=_clean(category,80).upper()
    cue=_clean(directional_cue,80).upper()
    curr=[_clean(x,8).upper() for x in list(currencies or []) if _clean(x,8)]
    rows=[]
    invalidators=[]

    def add(asset,effect,mechanism):
        rows.append({
            "asset":asset,
            "possible_effect":effect,
            "mechanism":mechanism,
            "truth_state":"HYPOTHESIS",
        })

    if cat=="GEOPOLITICAL_ESCALATION":
        add("Brent / petróleo","pressão de alta possível","prêmio de risco e risco de oferta/rotas")
        add("Ouro","demanda defensiva possível","busca por proteção")
        add("JPY / CHF","fluxo defensivo possível","aversão a risco")
        add("USD / DXY","fluxo defensivo possível, mas reação pode ser mista","liquidez global e diferencial de risco")
        add("S&P 500 / Nasdaq / Dow","pressão negativa possível","risk-off e aumento do prêmio de risco")
        add("WIN / Ibovespa","pressão de risk-off possível","aversão global a risco e commodities/câmbio")
        add("WDO / USD-BRL","pressão de alta possível","busca por dólar em ambiente de risk-off")
        invalidators=[
            "evento é rapidamente contido ou desmentido",
            "não há impacto em energia, rotas, sanções ou fluxo de risco",
            "mercado já havia precificado a escalada",
        ]
    elif cat=="GEOPOLITICAL_DEESCALATION":
        add("Brent / petróleo","prêmio de risco pode cair","menor risco de oferta/rotas")
        add("Ouro","demanda defensiva pode diminuir","redução de hedge")
        add("Índices globais","alívio positivo possível","retorno do apetite a risco")
        add("WDO / USD-BRL","alívio de alta possível","menor busca por dólar defensivo")
        invalidators=["acordo não é confirmado","surge nova escalada","risco de oferta permanece"]
    elif cat=="SYSTEMIC_RISK":
        add("USD / DXY","reação defensiva possível","busca por liquidez em dólares")
        add("Ouro","demanda defensiva possível","proteção contra estresse financeiro")
        add("Índices globais","pressão negativa possível","aversão a risco e risco de crédito")
        add("Treasuries","queda de yields possível em flight-to-quality","procura por ativos defensivos")
        invalidators=["evento é isolado","liquidez oficial contém o risco","contágio não se confirma"]
    elif cat in {"CENTRAL_BANK_HAWKISH","CENTRAL_BANK_DOVISH"}:
        hawkish=cat=="CENTRAL_BANK_HAWKISH" or cue=="HAWKISH"
        for c in (curr or [""]):
            if c:
                add(_currency_asset(c),"fortalecimento possível" if hawkish else "enfraquecimento possível",
                    "diferencial de juros mais restritivo" if hawkish else "diferencial de juros mais flexível")
        add("Títulos / yields","alta possível" if hawkish else "queda possível",
            "reprecificação da curva de juros")
        add("Índices acionários","pressão negativa possível" if hawkish else "alívio positivo possível",
            "taxa de desconto e condições financeiras")
        invalidators=["coletiva contradiz a manchete","decisão já estava precificada","guidance/dot plot aponta direção diferente"]
    elif cat in {"INFLATION","LABOR","GROWTH"}:
        hot=cue in {"HOTTER","HAWKISH"}
        cool=cue in {"COOLER","DOVISH"}
        for c in (curr or [""]):
            if c:
                effect="fortalecimento possível" if hot else "enfraquecimento possível" if cool else "reação direcional não definida"
                add(_currency_asset(c),effect,"reprecificação de crescimento/inflação/juros")
        add("Yields","alta possível" if hot else "queda possível" if cool else "reação depende da surpresa",
            "reprecificação de juros")
        add("Índices","reação pode ser mista","crescimento e taxa de desconto podem atuar em sentidos opostos")
        invalidators=["revisões ou componentes internos contradizem o headline","surpresa já estava precificada","reação do banco central difere do esperado"]
    elif cat=="ENERGY_SUPPLY":
        add("Brent / petróleo","pressão de alta ou queda conforme oferta","choque de oferta/produção")
        add("CAD","sensibilidade positiva ao petróleo possível","termos de troca/energia")
        add("JPY / EUR","sensibilidade negativa a energia cara possível","dependência de importação de energia")
        add("Inflação global","pressão inflacionária possível","repasse de energia")
        invalidators=["impacto físico na oferta não se confirma","estoques/produção compensam","notícia é apenas especulativa"]
    elif cat=="TRADE_FISCAL_POLICY":
        add("USD / moedas afetadas","reação depende do diferencial de crescimento e inflação","tarifas/fiscal alteram atividade, preços e fluxos")
        add("Índices","volatilidade possível","mudança em margens, crescimento e política")
        add("WDO / BRL","volatilidade possível","risk sentiment e comércio exterior")
        invalidators=["medida não é implementada","escopo final é menor","mercado já precificou"]
    else:
        add("Mercado relacionado","impacto não definido","falta classificação causal robusta")
        invalidators=["evidência insuficiente","headline não representa evento material"]

    return {
        "schema":SCHEMA,
        "category":cat or "GENERAL_MARKET",
        "directional_cue":cue or "UNKNOWN",
        "channels":rows,
        "invalidators":invalidators,
        "is_prediction":False,
        "is_trade_signal":False,
        "profit_probability":None,
        "automatic_execution":False,
    }


def _event_truth(*,official:bool,report_observed:bool,independent_sources:int)->str:
    if official:
        return "CONFIRMED"
    if report_observed and independent_sources>=2:
        return "INFERENCE"
    return "UNKNOWN"


def _alert_for_event(
    event:Mapping[str,Any],
    *,
    reliability:Mapping[str,Any]|None=None,
)->dict[str,Any]:
    e=dict(event or {})
    rel=dict(reliability or {})
    degraded=rel.get("degraded_mode") if isinstance(rel.get("degraded_mode"),Mapping) else {}
    degraded_state=_clean(degraded.get("state"),80).upper()
    age=_finite(e.get("age_minutes"))
    fresh=age is not None and age<=60
    recent=age is not None and age<=180
    severity=int(_finite(e.get("severity_score")) or 0)
    truth=_clean(e.get("event_truth"),40).upper()
    official=bool(e.get("official_source",False))
    independent=int(_finite(e.get("independent_sources")) or 1)

    if degraded_state=="FAIL_CLOSED":
        state="HOLD"
        reason="Reliability Guardian está em FAIL_CLOSED."
    elif not recent:
        state="NONE"
        reason="Evento não é recente o suficiente para alerta."
    elif severity>=88 and fresh and (official or independent>=2):
        state="URGENT_INTERNAL"
        reason="Evento crítico/fresco com evidência forte o suficiente para revisão imediata."
    elif severity>=75 and recent:
        state="REVIEW_INTERNAL"
        reason="Evento relevante requer confirmação/revisão interna antes de qualquer conclusão forte."
    elif severity>=55 and recent:
        state="WATCH"
        reason="Evento merece acompanhamento, mas não atende gate de urgência."
    else:
        state="NONE"
        reason="Impacto/evidência abaixo do gate de alerta."

    alert_id=_fingerprint(e.get("event_id"),state,prefix="ALT")
    return {
        "schema":SCHEMA,
        "alert_id":alert_id,
        "event_id":_clean(e.get("event_id"),80),
        "state":state,
        "reason":reason,
        "severity_score":severity,
        "event_truth":truth or "UNKNOWN",
        "fresh":fresh,
        "recent":recent,
        "requires_human_review":state in {"REVIEW_INTERNAL","URGENT_INTERNAL","HOLD"},
        "external_notification_candidate":state in {"REVIEW_INTERNAL","URGENT_INTERNAL"},
        "external_notification_allowed":False,
        "requires_channel_integration":True,
        "market_action_authorized":False,
        "real_orders_enabled":False,
        "automatic_execution":False,
    }


def _compact_event(event:Mapping[str,Any])->dict[str,Any]:
    e=dict(event or {})
    return {
        "schema":SCHEMA,
        "event_id":_clean(e.get("event_id"),80),
        "headline":_clean(e.get("headline"),600),
        "published_at":_clean(e.get("published_at"),100),
        "observed_at":_clean(e.get("observed_at"),100),
        "age_minutes":_finite(e.get("age_minutes")),
        "source":_clean(e.get("source"),180),
        "provider":_clean(e.get("provider"),180),
        "link":_clean(e.get("link"),1200),
        "currencies":[_clean(x,8).upper() for x in list(e.get("currencies") or [])[:12]],
        "category":_clean(e.get("category"),80).upper() or "GENERAL_MARKET",
        "directional_cue":_clean(e.get("directional_cue"),80).upper() or "UNKNOWN",
        "classification_truth":"INFERENCE",
        "event_truth":_clean(e.get("event_truth"),40).upper() or "UNKNOWN",
        "report_truth":_clean(e.get("report_truth"),40).upper() or "UNKNOWN",
        "official_source":bool(e.get("official_source",False)),
        "independent_sources":max(1,int(_finite(e.get("independent_sources")) or 1)),
        "severity_score":max(0,min(100,int(_finite(e.get("severity_score")) or 0))),
        "relevance":_clean(e.get("relevance"),80),
        "theme":_clean(e.get("theme"),180),
        "first_seen_at":_clean(e.get("first_seen_at") or e.get("observed_at"),100),
        "last_seen_at":_clean(e.get("last_seen_at") or e.get("observed_at"),100),
        "market_action_authorized":False,
        "real_orders_enabled":False,
    }


def extract_currency_news_events(
    payload:Mapping[str,Any]|None,
    *,
    provenance:Any="",
    now:datetime|None=None,
    max_age_hours:float=24.0,
    limit:int=240,
)->list[dict[str,Any]]:
    p=dict(payload or {})
    currencies=p.get("currencies") if isinstance(p.get("currencies"),Mapping) else {}
    current=now or datetime.now(timezone.utc)
    provenance_confirmed=_clean(provenance,200).startswith("GitHub:")
    grouped:dict[str,dict[str,Any]]={}

    for currency,info_raw in currencies.items():
        info=dict(info_raw or {}) if isinstance(info_raw,Mapping) else {}
        for article_raw in list(info.get("articles",[]) or [])[:80]:
            if not isinstance(article_raw,Mapping):
                continue
            article=dict(article_raw)
            headline=_clean(article.get("title"),700)
            if not headline:
                continue
            published=_utc(article.get("published_at"))
            age=None if published is None else _age_minutes(published,now=current)
            if age is not None and age>float(max_age_hours)*60.0:
                continue
            source=_clean(article.get("source"),180)
            link=_clean(article.get("link"),1200)
            story_id=_clean(article.get("story_id"),100)
            key=story_id or _fingerprint(_norm(headline),source,prefix="STORY")
            item=grouped.get(key)
            if item is None:
                official=_is_official_source(source,link)
                classification=classify_event_text(headline,article.get("theme"))
                rel=_finite(article.get("relevance_points")) or 0.0
                weighted=abs(_finite(article.get("weighted_impact")) or 0.0)
                base=_CATEGORY_SEVERITY.get(classification["category"],45)
                severity=int(max(0,min(100,base+min(8,rel/2)+min(8,weighted*8))))
                event_id=_fingerprint(key,headline,prefix="EVT")
                item={
                    "event_id":event_id,
                    "headline":headline,
                    "published_at":published.isoformat() if published else "",
                    "observed_at":current.astimezone(timezone.utc).isoformat(),
                    "age_minutes":age,
                    "source":source,
                    "provider":_clean(article.get("provider"),120),
                    "link":link,
                    "currencies":[],
                    "sources":set(),
                    "official_source":official,
                    "independent_sources":1,
                    "report_truth":"CONFIRMED" if provenance_confirmed and bool(source) else "UNKNOWN",
                    "event_truth":"UNKNOWN",
                    "category":classification["category"],
                    "directional_cue":classification["directional_cue"],
                    "classification_truth":"INFERENCE",
                    "matched_keywords":classification["matched_keywords"],
                    "direction_keywords":classification["direction_keywords"],
                    "severity_score":severity,
                    "relevance":_clean(article.get("relevance"),80),
                    "theme":_clean(article.get("theme"),180),
                    "story_id":story_id,
                }
                grouped[key]=item
            c=_clean(currency,8).upper()
            if c and c not in item["currencies"]:
                item["currencies"].append(c)
            if source:
                item["sources"].add(source)

    events=[]
    for item in grouped.values():
        item["independent_sources"]=max(1,len(item["sources"]))
        item["event_truth"]=_event_truth(
            official=bool(item["official_source"]),
            report_observed=item["report_truth"]=="CONFIRMED",
            independent_sources=item["independent_sources"],
        )
        item["impact"]=impact_hypotheses(
            item["category"],
            directional_cue=item["directional_cue"],
            currencies=item["currencies"],
        )
        item.pop("sources",None)
        events.append(_compact_event(item)|{"impact":item["impact"]})

    events.sort(key=lambda x:(
        -int(x.get("severity_score") or 0),
        float(x.get("age_minutes") if x.get("age_minutes") is not None else 1e12),
    ))
    return events[:max(1,min(int(limit or 1),1000))]


def structured_calendar_event(
    event:Mapping[str,Any]|None,
    *,
    now:datetime|None=None,
)->dict[str,Any]|None:
    e=dict(event or {})
    if not bool(e.get("disponivel",False)):
        return None
    name=_clean(e.get("evento") or e.get("name"),300)
    source=_clean(e.get("fonte") or e.get("source"),180)
    if not name:
        return None
    current=now or datetime.now(timezone.utc)
    classification=classify_event_text(name,e.get("tipo"))
    impact_label=_clean(e.get("impacto"),80).upper()
    severity=_CATEGORY_SEVERITY.get(classification["category"],60)
    if impact_label in {"MÁXIMO","MAXIMO","HIGH","ALTO"}:
        severity=max(severity,82)
    event_id=_fingerprint(name,e.get("data_txt") or e.get("data"),source,prefix="CAL")
    currency=_clean(e.get("moeda") or e.get("currency"),8).upper()
    item={
        "event_id":event_id,
        "headline":name,
        "published_at":"",
        "observed_at":current.astimezone(timezone.utc).isoformat(),
        "age_minutes":0.0,
        "source":source,
        "provider":"economic_calendar",
        "link":"",
        "currencies":[currency] if currency else [],
        "official_source":_is_official_source(source),
        "independent_sources":1,
        "report_truth":"CONFIRMED" if source else "UNKNOWN",
        "event_truth":"CONFIRMED" if source else "UNKNOWN",
        "category":classification["category"],
        "directional_cue":classification["directional_cue"],
        "classification_truth":"INFERENCE",
        "severity_score":severity,
        "relevance":"Calendário",
        "theme":_clean(e.get("tipo"),180),
    }
    item["impact"]=impact_hypotheses(
        item["category"],
        directional_cue=item["directional_cue"],
        currencies=item["currencies"],
    )
    return _compact_event(item)|{"impact":item["impact"]}


def govern_event_alerts(
    events:Sequence[Mapping[str,Any]]|None,
    *,
    reliability:Mapping[str,Any]|None=None,
)->dict[str,Any]:
    event_rows=[dict(x) for x in list(events or []) if isinstance(x,Mapping)]
    alerts=[_alert_for_event(event,reliability=reliability) for event in event_rows]
    active=[x for x in alerts if x["state"]!="NONE"]
    rank={"URGENT_INTERNAL":0,"REVIEW_INTERNAL":1,"HOLD":2,"WATCH":3,"NONE":4}
    active.sort(key=lambda x:(rank.get(x["state"],9),-int(x["severity_score"])))
    return {
        "alerts":alerts,
        "active_alerts":len(active),
        "urgent_alerts":sum(1 for x in active if x["state"]=="URGENT_INTERNAL"),
        "review_alerts":sum(1 for x in active if x["state"]=="REVIEW_INTERNAL"),
        "watch_alerts":sum(1 for x in active if x["state"]=="WATCH"),
        "hold_alerts":sum(1 for x in active if x["state"]=="HOLD"),
        "top_alert":active[0] if active else None,
        "external_notification_allowed":False,
        "market_action_authorized":False,
        "real_orders_enabled":False,
    }


def build_event_intelligence(
    *,
    news_payload:Mapping[str,Any]|None=None,
    news_provenance:Any="",
    next_event:Mapping[str,Any]|None=None,
    reliability:Mapping[str,Any]|None=None,
    now:datetime|None=None,
    max_age_hours:float=24.0,
)->dict[str,Any]:
    current=now or datetime.now(timezone.utc)
    events=extract_currency_news_events(
        news_payload,
        provenance=news_provenance,
        now=current,
        max_age_hours=max_age_hours,
    )
    calendar=structured_calendar_event(next_event,now=current)
    if calendar is not None:
        events=[calendar]+[x for x in events if x.get("event_id")!=calendar.get("event_id")]

    governed=govern_event_alerts(events,reliability=reliability)
    alerts=list(governed["alerts"])
    category_counts:dict[str,int]={}
    truth_counts:dict[str,int]={}
    for event in events:
        category_counts[event["category"]]=category_counts.get(event["category"],0)+1
        truth_counts[event["event_truth"]]=truth_counts.get(event["event_truth"],0)+1

    return {
        "schema":SCHEMA,
        "generated_at":current.astimezone(timezone.utc).isoformat(),
        "events":events,
        "alerts":alerts,
        "event_count":len(events),
        "active_alerts":governed["active_alerts"],
        "urgent_alerts":governed["urgent_alerts"],
        "review_alerts":governed["review_alerts"],
        "watch_alerts":governed["watch_alerts"],
        "hold_alerts":governed["hold_alerts"],
        "category_counts":category_counts,
        "truth_counts":truth_counts,
        "top_alert":governed["top_alert"],
        "external_notification_channel_connected":False,
        "external_notification_allowed":False,
        "background_ready":True,
        "market_action_authorized":False,
        "real_orders_enabled":False,
        "automatic_execution":False,
    }


def normalize_event_journal(rows:Sequence[Mapping[str,Any]]|None)->list[dict[str,Any]]:
    out=[]
    seen=set()
    for raw in list(rows or [])[-MAX_EVENTS*2:]:
        if not isinstance(raw,Mapping):
            continue
        item=_compact_event(raw)
        eid=item["event_id"]
        if not eid or eid in seen:
            continue
        seen.add(eid)
        out.append(item)
    return out[-MAX_EVENTS:]


def normalize_alert_journal(rows:Sequence[Mapping[str,Any]]|None)->list[dict[str,Any]]:
    out=[]
    seen=set()
    for raw in list(rows or [])[-MAX_ALERTS*2:]:
        if not isinstance(raw,Mapping):
            continue
        state=_clean(raw.get("state"),40).upper()
        if state not in ALERT_STATES:
            state="NONE"
        event_id=_clean(raw.get("event_id"),80)
        alert_id=_clean(raw.get("alert_id"),80) or _fingerprint(event_id,state,prefix="ALT")
        if alert_id in seen:
            continue
        seen.add(alert_id)
        out.append({
            "schema":SCHEMA,
            "alert_id":alert_id,
            "event_id":event_id,
            "state":state,
            "reason":_clean(raw.get("reason"),600),
            "severity_score":max(0,min(100,int(_finite(raw.get("severity_score")) or 0))),
            "event_truth":_clean(raw.get("event_truth"),40).upper() or "UNKNOWN",
            "first_seen_at":_clean(raw.get("first_seen_at") or raw.get("created_at"),100),
            "last_seen_at":_clean(raw.get("last_seen_at") or raw.get("updated_at"),100),
            "requires_human_review":bool(raw.get("requires_human_review",False)),
            "external_notification_allowed":False,
            "market_action_authorized":False,
            "real_orders_enabled":False,
        })
    return out[-MAX_ALERTS:]


def merge_event_journal(
    existing:Sequence[Mapping[str,Any]]|None,
    incoming:Sequence[Mapping[str,Any]]|None,
    *,
    observed_at:Any="",
)->list[dict[str,Any]]:
    rows={x["event_id"]:x for x in normalize_event_journal(existing)}
    stamp=_clean(observed_at,100) or datetime.now(timezone.utc).isoformat()
    for raw in list(incoming or []):
        if not isinstance(raw,Mapping):
            continue
        item=_compact_event(raw)
        if not item["event_id"]:
            continue
        prior=rows.get(item["event_id"])
        if prior:
            item["first_seen_at"]=prior.get("first_seen_at") or stamp
        else:
            item["first_seen_at"]=item.get("first_seen_at") or stamp
        item["last_seen_at"]=stamp
        rows[item["event_id"]]=item
    return list(rows.values())[-MAX_EVENTS:]


def merge_alert_journal(
    existing:Sequence[Mapping[str,Any]]|None,
    incoming:Sequence[Mapping[str,Any]]|None,
    *,
    observed_at:Any="",
)->list[dict[str,Any]]:
    rows={x["alert_id"]:x for x in normalize_alert_journal(existing)}
    stamp=_clean(observed_at,100) or datetime.now(timezone.utc).isoformat()
    for raw in list(incoming or []):
        if not isinstance(raw,Mapping):
            continue
        state=_clean(raw.get("state"),40).upper()
        if state=="NONE":
            continue
        event_id=_clean(raw.get("event_id"),80)
        alert_id=_clean(raw.get("alert_id"),80) or _fingerprint(event_id,state,prefix="ALT")
        prior=rows.get(alert_id,{})
        rows[alert_id]={
            "schema":SCHEMA,
            "alert_id":alert_id,
            "event_id":event_id,
            "state":state if state in ALERT_STATES else "WATCH",
            "reason":_clean(raw.get("reason"),600),
            "severity_score":max(0,min(100,int(_finite(raw.get("severity_score")) or 0))),
            "event_truth":_clean(raw.get("event_truth"),40).upper() or "UNKNOWN",
            "first_seen_at":prior.get("first_seen_at") or stamp,
            "last_seen_at":stamp,
            "requires_human_review":bool(raw.get("requires_human_review",False)),
            "external_notification_allowed":False,
            "market_action_authorized":False,
            "real_orders_enabled":False,
        }
    return list(rows.values())[-MAX_ALERTS:]


def event_intelligence_digest(
    events:Sequence[Mapping[str,Any]]|None,
    alerts:Sequence[Mapping[str,Any]]|None,
)->str:
    payload={
        "events":normalize_event_journal(events),
        "alerts":normalize_alert_journal(alerts),
    }
    raw=json.dumps(payload,ensure_ascii=False,sort_keys=True,default=str)
    return sha256(raw.encode("utf-8")).hexdigest()[:24]


def event_intelligence_summary(
    events:Sequence[Mapping[str,Any]]|None,
    alerts:Sequence[Mapping[str,Any]]|None,
)->dict[str,Any]:
    e=normalize_event_journal(events)
    a=normalize_alert_journal(alerts)
    counts={state:0 for state in ALERT_STATES}
    for row in a:
        counts[row["state"]]=counts.get(row["state"],0)+1
    return {
        "schema":SCHEMA,
        "events":len(e),
        "alerts":len(a),
        "urgent":counts.get("URGENT_INTERNAL",0),
        "review":counts.get("REVIEW_INTERNAL",0),
        "watch":counts.get("WATCH",0),
        "hold":counts.get("HOLD",0),
        "external_notification_allowed":False,
        "market_action_authorized":False,
        "real_orders_enabled":False,
    }


__all__=[
    "SCHEMA","CATEGORIES","ALERT_STATES",
    "classify_event_text","impact_hypotheses",
    "extract_currency_news_events","structured_calendar_event",
    "build_event_intelligence","govern_event_alerts","normalize_event_journal",
    "normalize_alert_journal","merge_event_journal","merge_alert_journal",
    "event_intelligence_digest","event_intelligence_summary",
]
