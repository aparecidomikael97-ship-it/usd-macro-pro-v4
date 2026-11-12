"""Offline XAU/USD macro-document + Treasury context join (LAB only).

Accepts a caller-provided *claimed* predecision collection for FOMC, CPI and
nonfarm payrolls. Reruns the Treasury nominal/TIPS parser with original bytes.
Neither page strings nor hashes prove first-publication time, document origin,
market data vintages, DXY licensing, broker prices or a gold directional edge.
No network, IO, MT5, signal emission or trading authority.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import re
from typing import Any
from urllib.parse import urlsplit

from atlasquant_trader_xauusd_us_treasury_yields_lab import (
    TreasuryCsvReceipt, inspect_xauusd_treasury_yields_lab,
)

SCHEMA = "ATLASQUANT_XAUUSD_US_MACRO_PIT_SOURCE_JOIN_LAB_V1"
EVENT_KINDS = ("FOMC_POLICY", "BLS_CPI", "BLS_NFP")
_KIND = {
    "FOMC_POLICY": ("www.federalreserve.gov", re.compile(r"/newsevents/pressreleases/monetary(\d{8})[a-z]\.htm\Z"),
                    (b"federal reserve", b"federal open market committee"), 150),
    "BLS_CPI": ("www.bls.gov", re.compile(r"/news\.release/archives/cpi_(\d{8})\.htm\Z"),
                (b"consumer price index",), 65),
    "BLS_NFP": ("www.bls.gov", re.compile(r"/news\.release/archives/empsit_(\d{8})\.htm\Z"),
                (b"employment situation",), 65),
}
_PERIOD = re.compile(r"20\d\d-(0[1-9]|1[0-2])\Z")
_SHA = re.compile(r"[a-f0-9]{64}\Z")
MIN_DOCUMENT_BYTES = 50
MAX_DOCUMENT_BYTES = 384_000
BLACKOUT = timedelta(minutes=40)


@dataclass(frozen=True)
class MacroDocument:
    event_kind: str
    source_url: str
    reference_period: str
    released_at_utc_claim: datetime
    captured_at_utc_claim: datetime
    html_body: bytes
    sha256_claim: str


@dataclass(frozen=True)
class ScheduledMacroEvent:
    event_kind: str
    scheduled_at_utc_claim: datetime


def _utc(x: Any) -> datetime | None:
    if (not isinstance(x, datetime) or x.utcoffset() is None
            or x.microsecond != 0):
        return None
    return x.astimezone(timezone.utc)


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_XAUUSD_US_MACRO_JOIN_BLOCKED",
        "reason": reason, "asset": "METAL:XAUUSD",
        "macro_documents_expected": len(EVENT_KINDS), "macro_documents_accepted": 0,
        "macro_documentary_rows": [], "treasury_context_status": None,
        "treasury_real_10y_context_pct": None,
        "predecision_fomc_cpi_nfp_join_documentary_complete": False,
        "usd_dxy_vendor_context_verified": False,
        "treasury_csv_originals_authenticated": False,
        "original_bls_and_fed_pages_authenticated": False,
        "independent_first_publication_instants_verified": False,
        "macro_calendar_completeness_verified": False,
        "all_gold_predecision_factors_ready": False,
        "gold_price_and_spread_from_broker_verified": False,
        "out_of_sample_gold_accuracy_validated": False,
        "validated_directional_accuracy": None,
        "calibrated_direction_probability": None,
        "research_candidate_direction": None,
        "operational_bias": "AGUARDAR", "trade_authorized": False,
        "publishable": False, "live_alert_allowed": False,
        "worker_enabled": False, "scheduler_enabled": False,
        "http_requests": 0, "file_writes": 0, "new_cost_brl": 0,
        "research_only": True,
    }


def _url_event_day(doc: MacroDocument) -> datetime | None:
    spec = _KIND.get(doc.event_kind)
    if spec is None or type(doc.source_url) is not str or len(doc.source_url) > 300:
        return None
    host, path_rule, _, _ = spec
    try:
        link = urlsplit(doc.source_url)
        if (link.scheme != "https" or link.hostname != host or link.username is not None
                or link.password is not None or link.port is not None
                or link.query or link.fragment):
            return None
    except ValueError:
        return None
    match = path_rule.fullmatch(link.path)
    if match is None:
        return None
    try:
        date_text = match.group(1)
        if doc.event_kind == "FOMC_POLICY":
            return datetime.strptime(date_text, "%Y%m%d").replace(tzinfo=timezone.utc)
        return datetime.strptime(date_text, "%m%d%Y").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _check_doc(doc: Any, freeze: datetime) -> tuple[str, dict[str, Any] | None]:
    if not isinstance(doc, MacroDocument) or doc.event_kind not in EVENT_KINDS:
        return "INVALID_OFFICIAL_MACRO_DOCUMENT_TYPE_OR_KIND", None
    url_day = _url_event_day(doc)
    if url_day is None:
        return "NOT_AN_ALLOWED_OFFICIAL_ARCHIVE_RELEASE_URL", None
    released, captured = _utc(doc.released_at_utc_claim), _utc(doc.captured_at_utc_claim)
    if (released is None or captured is None or not released <= captured <= freeze
            or released.date() != url_day.date()):
        return "SOURCE_RELEASE_CAPTURE_OR_URL_DATE_NOT_PREDECISION", None
    if (type(doc.reference_period) is not str or _PERIOD.fullmatch(doc.reference_period) is None
            or doc.reference_period > released.strftime("%Y-%m")):
        return "INVALID_OR_FUTURE_REFERENCE_PERIOD", None
    if ((freeze - released) > timedelta(days=_KIND[doc.event_kind][3])):
        return "MACRO_SOURCE_AGE_EXCEEDS_RESEARCH_LIMIT", None
    if (type(doc.html_body) is not bytes or not MIN_DOCUMENT_BYTES <= len(doc.html_body) <= MAX_DOCUMENT_BYTES
            or type(doc.sha256_claim) is not str or _SHA.fullmatch(doc.sha256_claim) is None
            or sha256(doc.html_body).hexdigest() != doc.sha256_claim):
        return "ORIGINAL_BODY_BYTES_OR_HASH_NOT_SELF_CONSISTENT", None
    # Structural sanity only; not a document parsing, issuer witness or value extraction.
    low = doc.html_body.lower()
    if any(term not in low for term in _KIND[doc.event_kind][2]):
        return "DOCUMENT_CONTENT_DOES_NOT_MATCH_CLAIMED_RELEASE_KIND", None
    return "OK", {
        "event_kind": doc.event_kind,
        "source_url_claim": doc.source_url,
        "reference_period_claim": doc.reference_period,
        "released_at_utc_claim": released.isoformat(),
        "captured_at_utc_claim": captured.isoformat(),
        "source_body_sha256_local_only": doc.sha256_claim,
        "origin_and_release_clock_unattested": True,
    }


def inspect_xauusd_us_macro_join_lab(
    documents: Any, *, nominal_treasury: Any, real_treasury: Any,
    forecast_frozen_at_utc: Any, as_of_utc: Any,
    known_future_events: Any = (),
) -> dict[str, Any]:
    """Require a complete predecision US macro set, and recheck Treasury bytes.

    'known_future_events' is supplied by caller, not an independently complete
    economic calendar. If a claimed FOMC/CPI/NFP event is near the decision,
    abstain even when earlier monthly documents are structurally acceptable.
    """
    out = _blocked("INVALID_AS_OF_OR_FORECAST_FREEZE")
    now, freeze = _utc(as_of_utc), _utc(forecast_frozen_at_utc)
    if now is None or freeze is None or freeze > now:
        return out
    if not isinstance(known_future_events, (tuple, list)) or len(known_future_events) > 24:
        out["reason"] = "INVALID_HIGH_IMPACT_CALENDAR_CLAIM"
        return out
    event_keys = set()
    for event in known_future_events:
        if not isinstance(event, ScheduledMacroEvent) or event.event_kind not in EVENT_KINDS:
            out["reason"] = "INVALID_HIGH_IMPACT_CALENDAR_CLAIM"
            return out
        when = _utc(event.scheduled_at_utc_claim)
        if when is None or (event.event_kind, when) in event_keys:
            out["reason"] = "INVALID_OR_DUPLICATE_EVENT_TIME_CLAIM"
            return out
        event_keys.add((event.event_kind, when))
        if abs(when - freeze) <= BLACKOUT:
            out["reason"] = "HIGH_IMPACT_FOMC_CPI_OR_NFP_RELEASE_BLACKOUT"
            return out
    if not isinstance(documents, (tuple, list)) or len(documents) != len(EVENT_KINDS):
        out["reason"] = "MISSING_OR_EXTRA_US_OFFICIAL_MACRO_DOCUMENTS"
        return out
    docs_by_kind = {}
    for doc in documents:
        if not isinstance(doc, MacroDocument) or doc.event_kind not in EVENT_KINDS:
            out["reason"] = "INVALID_OFFICIAL_MACRO_DOCUMENT_TYPE_OR_KIND"
            return out
        if doc.event_kind in docs_by_kind:
            out["reason"] = "DUPLICATE_OFFICIAL_MACRO_DOCUMENT_KIND"
            return out
        status, item = _check_doc(doc, freeze)
        if status != "OK":
            out["reason"] = doc.event_kind + ":" + status
            return out
        docs_by_kind[doc.event_kind] = item
    if set(docs_by_kind) != set(EVENT_KINDS):
        out["reason"] = "MISSING_REQUIRED_FOMC_CPI_OR_NFP_DOCUMENT"
        return out
    out["macro_documents_accepted"] = 3
    out["macro_documentary_rows"] = [docs_by_kind[k] for k in EVENT_KINDS]
    treasury = inspect_xauusd_treasury_yields_lab(
        nominal_treasury, real_treasury,
        decision_freeze_utc=freeze, as_of_utc=now,
    )
    out["treasury_context_status"] = treasury["state"]
    if treasury["state"] != "LAB_XAUUSD_TREASURY_CONTEXT_DOCUMENTARY_UNATTESTED":
        out["reason"] = "TREASURY_NOMINAL_REAL_10Y_CONTEXT_NOT_READY:" + treasury["reason"]
        return out
    out.update({
        "state": "LAB_XAUUSD_US_MACRO_CONTEXT_DOCUMENTARY_NO_GO",
        "reason": "RAW_BODIES_AND_CLOCKS_SELF_CONSISTENT_BUT_PUBLISHER_DXY_AND_BROKER_UNATTESTED",
        "predecision_fomc_cpi_nfp_join_documentary_complete": True,
        "treasury_real_10y_context_pct": treasury["real_tips_latest_10y_pct"],
    })
    return out


__all__ = ["SCHEMA", "EVENT_KINDS", "MacroDocument", "ScheduledMacroEvent",
           "inspect_xauusd_us_macro_join_lab"]
