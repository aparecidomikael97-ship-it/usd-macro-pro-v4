"""Economic calendar for AtlasQuant Trader, read-only and fail-closed.

EODHD economic-events API (when existing subscription/token permits) supplies
UTC release timestamps, country, comparison, previous, estimate and actual.
This module never fabricates a consensus or quotes, never sends orders, never
spawns a worker and never writes customer/server state.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
from math import isfinite
import re
from typing import Any, Callable, Mapping, Sequence

from atlasquant_trader_opening_collector import brasilia_clock

SCHEMA = "ATLASQUANT_TRADER_ECONOMIC_CALENDAR_V1"
SOURCE = "EODHD Economic Events"
COUNTRIES = frozenset(("US", "BR", "GB", "DE", "FR", "IT", "ES", "CH",
                       "JP", "CN", "CA", "AU", "NZ"))
CURRENCY = {
    "US": "USD", "BR": "BRL", "GB": "GBP", "DE": "EUR", "FR": "EUR",
    "IT": "EUR", "ES": "EUR", "CH": "CHF", "JP": "JPY",
    "CN": "CNY", "CA": "CAD", "AU": "AUD", "NZ": "NZD",
}
# Order matters: more specific releases ahead of generic title fragments.
RULES = (
    ("unemployment", ("unemployment rate", "jobless claims", "initial claims",
                      "continuing claims", "taxa de desemprego"),
     -1, "Emprego mais fraco pode reduzir apostas em juros elevados."),
    ("inflation", ("consumer price", "cpi", "pce price", "inflation rate",
                   "producer price", "ppi", "hicp", "ipca", "igp m"),
     +1, "Uma inflação surpresa pode alterar juros e inflação implícita."),
    ("employment", ("nonfarm payroll", "payroll", "adp employment",
                    "jolts", "job openings", "non farm", "employment change",
                    "caged", "salarios", "wage growth"),
     +1, "Emprego acima da previsão pode reforçar atividade ou pressão salarial."),
    ("policy", ("interest rate decision", "interest rate", "fed rate",
                "federal funds", "bank rate", "selic", "deposit facility",
                "cash rate", "policy rate"),
     +1, "Decisões inesperadas de juros podem alterar diferenciais de taxas."),
    ("activity", ("gdp", "gross domestic", "pmi", "ism manufacturing",
                  "ism services", "industrial production", "retail sales",
                  "durable goods", "consumer confidence", "trade balance",
                  "building permits", "housing starts", "ibc br", "pib",
                  "vendas no varejo"),
     +1, "Atividade surpreendente pode alterar perspectivas de crescimento e juros."),
)


def _float(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        n = float(value)
    except (ValueError, TypeError, OverflowError):
        return None
    return n if isfinite(n) and abs(n) <= 1e9 else None


def _timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or len(value) > 45 or not value.strip():
        return None
    try:
        point = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        # EODHD documents event timestamps in UTC even without a suffix.
        if point.tzinfo is None:
            point = point.replace(tzinfo=timezone.utc)
        return point.astimezone(timezone.utc)
    except (ValueError, OverflowError):
        return None


def _title_norm(title: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", title.lower())).strip()


def _event_class(title: str) -> tuple[str, int, str]:
    name = _title_norm(title)
    for category, aliases, polarity, description in RULES:
        if any(alias in name for alias in aliases):
            return category, polarity, description
    return "other", 0, "Um indicador isolado não permite inferir direção de moeda."


def event_identity(country: str, title: str, comparison: str, when: datetime) -> str:
    raw = f"{country}|{title.strip().casefold()}|{comparison}|{when.isoformat()}"
    return sha256(raw.encode("utf-8")).hexdigest()[:20]


def _manual_consensus(
    raw: Any, *, event_id: str, release_at: datetime,
    today: datetime
) -> tuple[float | None, str, str]:
    """Only a source-attributed, pre-release manual figure is eligible.

    Caller must enforce ADMIN access to enter overrides. Do not allow manual
    backfilling after release or overwrite authoritative auto consensus.
    """
    if not isinstance(raw, Mapping) or raw.get("event_id") != event_id:
        return None, "", ""
    value = _float(raw.get("value"))
    source = str(raw.get("source") or "").strip()
    author = str(raw.get("author") or "").strip()
    recorded = _timestamp(raw.get("entered_at"))
    if (value is None or not source or len(source) > 180 or
            not author or len(author) > 80 or recorded is None or
            recorded >= release_at or recorded > today + timedelta(minutes=1)):
        return None, "", ""
    return value, source, author


def normalize_events(
    payload: Any, *, at: datetime | None = None,
    manual: Mapping[str, Mapping[str, Any]] | None = None,
    max_items: int = 120
) -> dict[str, Any]:
    """Convert one validated daily EODHD page to a bounded, auditable snapshot."""
    local = brasilia_clock(at)
    today = local.date()
    now = local.astimezone(timezone.utc)
    blank = {"schema": SCHEMA, "state": "NOT_CONNECTED", "date": today.isoformat(),
             "source": "", "fetched_at": "", "events": [], "total": 0,
             "truncated": False, "week_events": [], "week_total": 0,
             "week_truncated": False, "reason": ""}
    if not isinstance(payload, Mapping) or payload.get("ok") is not True:
        return {**blank, "state": "UNAVAILABLE", "reason": str(payload.get("reason") or "SOURCE_UNAVAILABLE")[:70] if isinstance(payload, Mapping) else "SOURCE_UNAVAILABLE"}
    raw = payload.get("data")
    if not isinstance(raw, list):
        return {**blank, "state": "INVALID_PROVIDER"}
    if len(raw) >= 1000:
        return {**blank, "state": "INCOMPLETE_PROVIDER"}
    received_at = _timestamp(payload.get("fetched_at"))
    if received_at is not None:
        age = (now - received_at).total_seconds()
        if age > 2 * 3600 or age < -60:
            return {**blank, "state": "STALE_PROVIDER", "reason": "CACHE_OUTDATED"}
    rows: list[dict[str, Any]] = []
    future_rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in raw:
        if not isinstance(item, Mapping):
            continue
        title = str(item.get("type") or "").strip()
        country = str(item.get("country") or "").strip().upper()
        if not 2 <= len(title) <= 150 or country not in COUNTRIES:
            continue
        utc = _timestamp(item.get("date"))
        if utc is None:
            continue
        event_day = brasilia_clock(utc).date()
        # Today's calendar + the following six days from one bounded query.
        if not today <= event_day < today + timedelta(days=7):
            continue
        comparison = str(item.get("comparison") or "").strip().lower()
        if comparison not in ("", "mom", "yoy", "qoq"):
            continue
        period = str(item.get("period") or "").strip()[:50]
        event_id = event_identity(country, title, comparison, utc)
        if event_id in seen:
            continue
        seen.add(event_id)
        previous = _float(item.get("previous"))
        consensus = _float(item.get("estimate"))
        actual = _float(item.get("actual")) if now >= utc else None
        consensus_source = SOURCE if consensus is not None else ""
        author = ""
        if consensus is None and manual:
            manual_value, source, author = _manual_consensus(
                manual.get(event_id), event_id=event_id, release_at=utc, today=now)
            if manual_value is not None:
                consensus = manual_value
                consensus_source = "MANUAL · " + source
        kind, polarity, note = _event_class(title)
        surprise = round(actual - consensus, 5) if actual is not None and consensus is not None else None
        events = {
            "id": event_id, "country": country, "currency": CURRENCY[country],
            "title": title, "comparison": comparison, "period": period,
            "release_utc": utc.isoformat(), "date_brt": event_day.isoformat(),
            "time_brt": brasilia_clock(utc).strftime("%H:%M"),
            "previous": previous, "consensus": consensus, "actual": actual,
            "consensus_source": consensus_source, "consensus_author": author,
            "category": kind, "polarity": polarity, "note": note,
            "surprise": surprise, "released": now >= utc,
            "source": SOURCE,
        }
        if event_day == today:
            rows.append(events)
        else:
            future_rows.append(events)
    rows.sort(key=lambda item: (item["release_utc"], item["country"], item["title"]))
    future_rows.sort(key=lambda item: (item["release_utc"], item["country"], item["title"]))
    return {"schema": SCHEMA, "state": "READY", "date": today.isoformat(),
            "source": SOURCE, "fetched_at": received_at.isoformat() if received_at else "",
            "events": rows[:max_items], "total": len(rows),
            "truncated": len(rows) > max_items,
            "week_events": future_rows[:max_items], "week_total": len(future_rows),
            "week_truncated": len(future_rows) > max_items}


def explanation(event: Mapping[str, Any]) -> dict[str, str]:
    """Conditional educational scenarios, never investment instructions."""
    name = str(event.get("currency") or "moeda local")
    kind = str(event.get("category") or "")
    polarity = int(event.get("polarity") or 0)
    if kind == "inflation":
        above = (f"Acima do consenso: inflação mais quente pode elevar apostas em juros "
                 f"e favorecer {name} no curto prazo, mas a reação depende das expectativas e do risco.")
        below = (f"Abaixo do consenso: inflação mais fria pode reduzir juros esperados e "
                 f"pressionar {name}; também pode favorecer ações quando o risco permite.")
    elif kind == "unemployment":
        above = (f"Acima do consenso: desemprego/pedidos maiores podem indicar emprego mais "
                 f"fraco e pressionar {name} via expectativas de juros menores.")
        below = (f"Abaixo do consenso: emprego mais resiliente pode sustentar juros esperados "
                 f"e favorecer {name}, mas depende de salários e outras divulgações.")
    elif kind == "employment":
        above = (f"Acima do consenso: emprego mais forte pode favorecer {name} se elevar "
                 "expectativas de juros; crescimento e risco também importam.")
        below = (f"Abaixo do consenso: emprego mais fraco pode pressionar {name} via "
                 "queda de juros esperados; revisão do dado e salários importam.")
    elif kind == "policy":
        above = (f"Taxa acima do esperado: surpresa mais restritiva pode favorecer {name} "
                 "pelo diferencial de juros, salvo risco de recessão/posicionamento.")
        below = (f"Taxa abaixo do esperado: surpresa mais flexível pode pressionar {name} "
                 "se reduzir o retorno relativo da moeda.")
    elif kind == "activity":
        above = (f"Acima do consenso: atividade mais forte pode favorecer {name} por "
                 "crescimento/juros, mas inflação e apetite por risco podem mudar a reação.")
        below = (f"Abaixo do consenso: atividade mais fraca pode pressionar {name} via "
                 "juros esperados menores; confirme a reação dos títulos e do preço.")
    else:
        above = (f"Acima do consenso: impacto direcional em {name} indeterminado sem "
                 "saber que indicador é, sua unidade e o contexto.")
        below = (f"Abaixo do consenso: impacto direcional em {name} indeterminado sem "
                 "a leitura do contexto e da política monetária.")
    actual = event.get("actual")
    consensus = event.get("consensus")
    if actual is None:
        result = "Resultado ainda não divulgado ou não recebido da fonte."
    elif consensus is None:
        result = "Resultado informado, mas sem consenso verificável: surpresa não calculada."
    elif actual > consensus:
        result = "Divulgação ACIMA do consenso. " + above
    elif actual < consensus:
        result = "Divulgação ABAIXO do consenso. " + below
    else:
        result = "Divulgação IGUAL ao consenso: reação dependerá de detalhes e revisões."
    previous = event.get("previous")
    if consensus is None or previous is None:
        expected = "Consenso e/ou número anterior indisponível; não é possível medir a expectativa contra o último dado."
    elif consensus > previous:
        expected = "O mercado prevê um número MAIOR que o anterior: " + f"{previous:g} → {consensus:g}. Uma alta esperada já pode estar precificada."
    elif consensus < previous:
        expected = "O mercado prevê um número MENOR que o anterior: " + f"{previous:g} → {consensus:g}. Uma queda esperada já pode estar precificada."
    else:
        expected = "O mercado prevê um número IGUAL ao anterior: " + f"{consensus:g}."
    # Apply the audited editorial library AFTER the numeric comparison is
    # established. A known event gets a specific scenario; an unrecognized
    # title remains explicitly conditional/unknown. Neither is a trade bias.
    from atlasquant_trader_master_indicator_guide import indicator_guide
    guide = indicator_guide(event.get("title"), event.get("country"),
                            event.get("comparison"))
    if guide["key"] != "unknown":
        above = guide["above"] + f" Moeda de referência do evento: {name}."
        below = guide["below"] + f" Moeda de referência do evento: {name}."
    else:
        above = guide["above"] + f" Moeda local: {name}."
        below = guide["below"] + f" Moeda local: {name}."
    if actual is None:
        result = "Resultado ainda não divulgado ou não recebido da fonte."
    elif consensus is None:
        result = "Resultado informado, mas sem consenso verificável: surpresa não calculada."
    elif actual > consensus:
        result = "Divulgação ACIMA do consenso. " + above
    elif actual < consensus:
        result = "Divulgação ABAIXO do consenso. " + below
    else:
        result = "Divulgação IGUAL ao consenso: reação depende de detalhes, revisões e precificação."
    if name == "USD":
        dollar = (
            "Para os EUA, observar DXY, Treasury 2Y e 10Y e Fed. "
            "USD mais forte pode pressionar EUR/USD e apoiar USD/JPY, "
            "mas risco global, juros japoneses e posicionamento podem inverter a reação."
        )
    elif name == "BRL":
        dollar = (
            "Para Brasil, acompanhar curva DI, Selic, risco fiscal e USD/BRL: "
            "BRL mais forte tende a reduzir USD/BRL, mas isso não é garantia."
        )
    else:
        dollar = (
            f"Para {name}, acompanhar o banco central local e os pares com USD. "
            "Moeda-base valorizada tende a elevar o par; moeda cotada valorizada "
            "tende a reduzi-lo, com outras forças atuando simultaneamente."
        )
    return {"above": above, "below": below, "result": result,
            "expectation": expected, "dollar": dollar,
            "mechanism": guide["mechanism"], "watch": guide["watch"],
            "caution": guide["caution"], "guide_key": guide["key"],
            "certainty": guide["certainty"],
            "risk": "Cenários condicionais, não garantias. Observe revisão, hora, "
                    "composição do indicador, juros, posicionamento e preço."}


def request_eodhd_daily(
    token: str, *, at: datetime | None = None,
    request_get: Callable[..., Any] | None = None
) -> dict[str, Any]:
    """One bounded request per cache miss. Caller must cache and enforce quota.

    No fetch when the configured existing entitlement is absent. Never expose
    the token or raw error body in errors/logs.
    """
    if not isinstance(token, str) or not token.strip():
        return {"ok": False, "reason": "NO_EXISTING_TOKEN", "data": []}
    local = brasilia_clock(at)
    date_from = local.date().isoformat()
    date_to = (local.date() + timedelta(days=7)).isoformat()
    if request_get is None:
        import requests
        request_get = requests.get
    try:
        response = request_get(
            "https://eodhd.com/api/economic-events",
            params={"api_token": token, "from": date_from, "to": date_to,
                    "limit": 1000, "offset": 0, "fmt": "json"},
            timeout=12,
        )
        if int(response.status_code) != 200:
            return {"ok": False, "reason": f"HTTP_{int(response.status_code)}", "data": []}
        payload = response.json()
        if isinstance(payload, Mapping):
            payload = payload.get("data") if not payload.get("error") else None
        if not isinstance(payload, list):
            return {"ok": False, "reason": "INVALID_RESPONSE", "data": []}
        return {"ok": True, "data": payload, "fetched_at": datetime.now(timezone.utc).isoformat()}
    except Exception:
        return {"ok": False, "reason": "PROVIDER_UNAVAILABLE", "data": []}


__all__ = ["SCHEMA", "SOURCE", "COUNTRIES", "RULES", "event_identity",
           "normalize_events", "explanation", "request_eodhd_daily"]
