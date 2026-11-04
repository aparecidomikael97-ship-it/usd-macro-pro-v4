"""Free official primary-source NEWS research routing; offline, LAB / HARD NO-GO.

Classifies only *planned exposure* to known upcoming macro events. Official
RSS/JSON discovery is not a paid real-time news terminal, does not guarantee
latency, completeness, delivery or reuse rights, and DOES NOT fetch any URL.
No prices, consensus, actual release or directional forecasts are accepted.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any, Mapping, Sequence

from atlasquant_fx_universe import OFFICIAL_PAIRS, CURRENCIES, split_pair
from atlasquant_trader_macro_event_exposure_lab import CALENDAR as FX_EVENTS

SCHEMA = "ATLASQUANT_TRADER_FREE_PRIMARY_NEWS_ROUTES_LAB_V1"
STATE = "LAB_FREE_OFFICIAL_NEWS_ROUTE_PLAN_NOT_RUNNING"
DENIED = "LAB_PRIMARY_NEWS_ROUTES_REFUSED"
RESEARCH_ON = date(2026, 11, 3)
HORIZONS = ("D1", "W1", "MN1")
HOURS = {"D1": 24, "W1": 168, "MN1": 720}
INDICES = ("SPX500", "NAS100", "US30", "WIN", "WDO")
US_INDEX = frozenset(("SPX500", "NAS100", "US30"))
BR_INDEX = frozenset(("WIN", "WDO"))

# Source routes are inspected documentation leads, not authenticated delivery.
SOURCES = (
    {
        "source_id": "BLS_EMPLOYMENT_RSS",
        "publisher": "US_BLS", "channel": "OFFICIAL_RSS",
        "url": "https://www.bls.gov/feed/empsit.rss",
        "topic": "USD_EMPLOYMENT",
        "live_source_reliability_verified": False,
        "publication_to_ingest_latency_measured": False,
        "automated_polling_enabled": False,
    },
    {
        "source_id": "BLS_CPI_RSS",
        "publisher": "US_BLS", "channel": "OFFICIAL_RSS",
        "url": "https://www.bls.gov/feed/cpi.rss",
        "topic": "USD_CPI",
        "live_source_reliability_verified": False,
        "publication_to_ingest_latency_measured": False,
        "automated_polling_enabled": False,
    },
    {
        "source_id": "FED_MONETARY_RSS",
        "publisher": "US_FEDERAL_RESERVE", "channel": "OFFICIAL_RSS",
        "url": "https://www.federalreserve.gov/feeds/press_monetary.xml",
        "topic": "USD_MONETARY_POLICY",
        "live_source_reliability_verified": False,
        "publication_to_ingest_latency_measured": False,
        "automated_polling_enabled": False,
    },
    {
        "source_id": "BCB_COPOM_OPEN_DATA",
        "publisher": "BRAZIL_CENTRAL_BANK", "channel": "OFFICIAL_PUBLIC_JSON_LEAD",
        "url": "https://dadosabertos.bcb.gov.br/dataset/atas-comunicados-copom",
        "topic": "BRL_MONETARY_POLICY",
        "live_source_reliability_verified": False,
        "publication_to_ingest_latency_measured": False,
        "automated_polling_enabled": False,
    },
    {
        "source_id": "BOE_MPC_OFFICIAL_PAGE",
        "publisher": "BANK_OF_ENGLAND", "channel": "OFFICIAL_DOCUMENT_PAGE",
        "url": "https://www.bankofengland.co.uk/monetary-policy/upcoming-mpc-dates",
        "topic": "GBP_MONETARY_POLICY_SCHEDULE",
        "live_source_reliability_verified": False,
        "publication_to_ingest_latency_measured": False,
        "automated_polling_enabled": False,
    },
)

# The three dates are re-used directly from the existing Trader macro event
# module; BRL is a date-only meeting (not an invented publication instant).
BR_EVENT = {
    "event_id": "BCB_COPOM_20261104", "currency": "BRL",
    "event_kind": "CENTRAL_BANK_DECISION",
    "time_precision": "DATE_ONLY",
    "earliest_at_utc": "2026-11-04T00:00:00Z",
    "latest_at_utc": "2026-11-04T23:59:59Z",
    "source_url": "https://www.bcb.gov.br/acessoinformacao/calendariobc?agenda=Reuni%C3%B5es+do+Copom",
}

SOURCE_BY_EVENT = {
    "BCB_COPOM_20261104": "BCB_COPOM_OPEN_DATA",
    "BOE_MPC_20261105": "BOE_MPC_OFFICIAL_PAGE",
    "BLS_US_EMPLOYMENT_20261106": "BLS_EMPLOYMENT_RSS",
    "BLS_US_CPI_20261110": "BLS_CPI_RSS",
}
EVENTS = (BR_EVENT,) + tuple(FX_EVENTS)


def _deny(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": DENIED, "reason": reason,
        "fx_rows": [], "index_rows": [], "route_rows": [],
        "source_original_payloads_archived": False,
        "actual_releases_verified": False,
        "consensus_verified": False, "source_latency_verified": False,
        "source_license_for_commercial_use_verified": False,
        "news_live": False, "news_realtime_guaranteed": False,
        "directional_bias": None, "probability_calibrated": None,
        "can_feed_live_radar": False, "trade_authorized": False,
        "paid_provider_approved": False, "paid_provider_charged": False,
        "worker_enabled": False, "scheduler_enabled": False,
        "render_configuration_changed": False,
    }


def _utc(iso: str) -> datetime:
    if not isinstance(iso, str) or not iso.endswith("Z"):
        raise ValueError("Calendar timestamp requires a canonical UTC Z suffix")
    d = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    if d.utcoffset() != timedelta(0):
        raise ValueError("Event clock must be UTC")
    return d


def _window_status(ev: Mapping[str, Any], now: datetime, deadline: datetime) -> str:
    first = _utc(ev["earliest_at_utc"])
    last = _utc(ev["latest_at_utc"])
    if now >= last:
        return "WINDOW_PASSED_ACTUAL_NOT_VERIFIED"
    if first <= now < last:
        return "DATE_ONLY_MAY_HAVE_ALREADY_OCCURRED_CHECK_OFFICIAL"
    if first > deadline:
        return "OUTSIDE_HORIZON"
    if last > deadline:
        return "WINDOW_EDGE_UNCERTAIN"
    return "UPCOMING_DOCUMENTARY_SCHEDULE_ONLY"


def build_primary_news_routes_lab(
    *, at: datetime,
    sources: Sequence[Mapping[str, Any]] | None = None,
    events: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Plan public primary-source attention, never fetch or infer FX direction.

    Input customization can ONLY reproduce the pinned source/calendar exactly.
    It cannot inject an actual release, price, consensus, source permission,
    stream activation or fabricated publication timestamp.
    """
    if (not isinstance(at, datetime) or at.tzinfo is None
            or at.utcoffset() is None):
        raise ValueError("Source planning clock must be timezone-aware")
    now = at.astimezone(timezone.utc)
    if now.date() < RESEARCH_ON:
        return _deny("Official route research not documented at historic as-of")
    source_rows = SOURCES if sources is None else sources
    event_rows = EVENTS if events is None else events
    if (not isinstance(source_rows, (tuple, list)) or len(source_rows) != len(SOURCES)
            or not all(isinstance(x, Mapping) and dict(x) == y and set(x) == set(y)
                       for x, y in zip(source_rows, SOURCES))):
        return _deny("Official source lead altered, added or omitted")
    if (not isinstance(event_rows, (tuple, list)) or len(event_rows) != len(EVENTS)
            or not all(isinstance(x, Mapping) and dict(x) == y and set(x) == set(y)
                       for x, y in zip(event_rows, EVENTS))):
        return _deny("Official event date, type or evidence altered")
    if {x["currency"] for x in EVENTS} != {"BRL", "GBP", "USD"}:
        raise RuntimeError("Canonical researched currency exposure changed")
    route_rows = []
    for event in EVENTS:
        sid = SOURCE_BY_EVENT[event["event_id"]]
        source = next(x for x in SOURCES if x["source_id"] == sid)
        statuses = {h: _window_status(event, now, now + timedelta(hours=HOURS[h]))
                    for h in HORIZONS}
        route_rows.append({
            "event_id": event["event_id"],
            "currency": event["currency"],
            "route_source_id": sid,
            "route_url": source["url"],
            "time_precision": event["time_precision"],
            "horizons": statuses,
            "news_ingested": False, "actual_known": False,
            "pre_release_consensus_known": False,
            "latency_evidence_available": False,
            "directional_impact": "AGUARDAR",
            "provider_upgrade_needed_proven": False,
        })
    fx_rows, index_rows = [], []
    for h in HORIZONS:
        for pair in OFFICIAL_PAIRS:
            base, quote = split_pair(pair)
            relevant = [r["event_id"] for r in route_rows
                        if r["currency"] in (base, quote)
                        and r["horizons"][h] not in (
                            "OUTSIDE_HORIZON", "WINDOW_PASSED_ACTUAL_NOT_VERIFIED")]
            fx_rows.append({"pair": pair, "horizon": h,
                            "relevant_event_ids": relevant,
                            "bias": "AGUARDAR", "trade_authorized": False})
        for index in INDICES:
            relevant = []
            for r in route_rows:
                if r["horizons"][h] in ("OUTSIDE_HORIZON", "WINDOW_PASSED_ACTUAL_NOT_VERIFIED"):
                    continue
                if index in BR_INDEX and r["currency"] == "BRL":
                    relevant.append({"event_id": r["event_id"],
                                     "channel": "BR_DOMESTIC_DIRECT_CONTEXT"})
                elif index in BR_INDEX and r["currency"] == "USD":
                    relevant.append({"event_id": r["event_id"],
                                     "channel": "US_GLOBAL_INDIRECT_CONTEXT_UNVERIFIED"})
                elif index in US_INDEX and r["currency"] == "USD":
                    relevant.append({"event_id": r["event_id"],
                                     "channel": "US_DOMESTIC_DIRECT_CONTEXT"})
            index_rows.append({"instrument": index, "horizon": h,
                               "relevant_events": relevant,
                               "bias": "AGUARDAR", "trade_authorized": False})
    if len(fx_rows) != 84 or len(index_rows) != 15:
        raise RuntimeError("News route matrix must cover 28 FX and 5 indices x3")
    return {
        **_deny(""), "state": STATE, "reason": None,
        "as_of_utc": now.isoformat(),
        "route_rows": route_rows, "source_rows": [dict(x) for x in SOURCES],
        "fx_rows": fx_rows, "index_rows": index_rows,
        "source_leads": len(SOURCES), "scheduled_events": len(EVENTS),
        "fx_rows_count": len(fx_rows), "index_rows_count": len(index_rows),
        "coverage_all_g8": False, "coverage_brazil": True,
        "research_note": ("Official public channels are leads only; no authenticated "
                          "feed payload, observed latency or commercial licensing "
                          "assessment. A scheduled release is never an actual release."),
    }


__all__ = ["SCHEMA", "STATE", "DENIED", "SOURCES", "EVENTS", "SOURCE_BY_EVENT",
           "build_primary_news_routes_lab"]
