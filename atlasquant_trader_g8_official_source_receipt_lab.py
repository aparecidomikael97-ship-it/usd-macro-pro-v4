"""Curated G8 official-document leads and unauthenticated offline receipt gate.

HTTPS domains and caller-claimed timestamps are only STRUCTURAL checks. No
fetch, TLS verification, archive custody, licensing, or market inference is
performed by this LAB module. Even an accepted receipt remains quarantined.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import re
from typing import Any, Mapping
from urllib.parse import urlsplit

from atlasquant_fx_universe import CURRENCIES

SCHEMA = "ATLASQUANT_TRADER_G8_OFFICIAL_RECEIPT_GATE_LAB_V1"
FAMILIES = ("INFLATION", "POLICY")
IDENTITY = re.compile(r"^[A-Za-z0-9:_-]{3,90}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
MAX_TEXT_BYTES = 32768
RECEIPT_FIELDS = frozenset((
    "state", "source_id", "event_id", "kind", "event_at_utc",
    "published_at_utc", "captured_at_utc", "document_url",
    "excerpt_utf8", "claimed_sha256",
))

# Official sites researched on 2026-11-02. Landing pages are NOT
# immutable historical observations or automatically licensed data feeds.
_CANDIDATES = (
    ("USD", "INFLATION", "US_BLS_CPI", "Bureau of Labor Statistics",
     "https://www.bls.gov/schedule/2026/"),
    ("USD", "POLICY", "US_FED_FOMC", "Federal Reserve",
     "https://www.federalreserve.gov/newsevents/pressreleases/2026-press-fomc.htm"),
    ("EUR", "INFLATION", "EU_EUROSTAT_HICP", "Eurostat",
     "https://ec.europa.eu/eurostat/web/hicp/information-data"),
    ("EUR", "POLICY", "EU_ECB_POLICY", "European Central Bank",
     "https://www.ecb.europa.eu/press/govcdec/mopo/html/index.en.html"),
    ("GBP", "INFLATION", "UK_ONS_CPI", "Office for National Statistics",
     "https://www.ons.gov.uk/economy/inflationandpriceindices/bulletins/consumerpriceinflation/latest"),
    ("GBP", "POLICY", "UK_BOE_BANK_RATE", "Bank of England",
     "https://www.bankofengland.co.uk/monetary-policy/the-interest-rate-bank-rate"),
    ("JPY", "INFLATION", "JP_STAT_CPI", "Statistics Bureau of Japan",
     "https://www.stat.go.jp/data/cpi/1.htm"),
    ("JPY", "POLICY", "JP_BOJ_MPM", "Bank of Japan",
     "https://www.boj.or.jp/en/mopo/mpmsche_minu/"),
    ("CHF", "INFLATION", "CH_BFS_CPI", "Swiss Federal Statistical Office",
     "https://www.bfs.admin.ch/en/press-releases"),
    ("CHF", "POLICY", "CH_SNB_MPA", "Swiss National Bank",
     "https://www.snb.ch/en/the-snb/mandates-goals/monetary-policy/decisions"),
    ("AUD", "INFLATION", "AU_ABS_CPI", "Australian Bureau of Statistics",
     "https://www.abs.gov.au/statistics/economy/price-indexes-and-inflation/consumer-price-index-australia/latest-release"),
    ("AUD", "POLICY", "AU_RBA_DECISIONS", "Reserve Bank of Australia",
     "https://www.rba.gov.au/monetary-policy/int-rate-decisions/"),
    ("CAD", "INFLATION", "CA_STATCAN_CPI", "Statistics Canada",
     "https://www.statcan.gc.ca/en/subjects-start/prices_and_price_indexes/consumer_price_indexes"),
    ("CAD", "POLICY", "CA_BOC_RATE", "Bank of Canada",
     "https://www.bankofcanada.ca/core-functions/monetary-policy/key-interest-rate/"),
    ("NZD", "INFLATION", "NZ_STATS_CPI", "Stats NZ",
     "https://www.stats.govt.nz/indicators/consumers-price-index-cpi/"),
    ("NZD", "POLICY", "NZ_RBNZ_OCR", "Reserve Bank of New Zealand",
     "https://www.rbnz.govt.nz/monetary-policy/monetary-policy-decisions"),
)
SOURCES = {
    source_id: {
        "currency": currency, "family": family, "publisher": publisher,
        "documentation_url": url, "hostname": urlsplit(url).hostname,
    }
    for currency, family, source_id, publisher, url in _CANDIDATES
}


def official_g8_source_catalog_lab() -> dict[str, Any]:
    """Return G8 source DOCUMENTATION leads, never usable live source status."""
    return {
        "schema": SCHEMA, "state": "LAB_DOCUMENTATION_LEADS_ONLY",
        "currency_count": len(CURRENCIES), "family_count": len(FAMILIES),
        "lead_count": len(SOURCES),
        "sources": {key: dict(value) for key, value in sorted(SOURCES.items())},
        "historical_payloads_downloaded": False,
        "original_receipt_attested": False,
        "intraday_availability_attested": False,
        "commercial_redistribution_rights_verified": False,
        "real_forex_bias_verified": False,
        "trade_authorized": False, "worker_enabled": False,
        "scheduler_enabled": False,
    }


def _utc(raw: Any) -> datetime | None:
    if not isinstance(raw, str) or not 20 <= len(raw) <= 40:
        return None
    if not (raw.endswith("Z") or raw.endswith("+00:00")):
        return None
    try:
        x = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except (ValueError, OverflowError):
        return None
    if x.utcoffset() != timedelta(0):
        return None
    return x.astimezone(timezone.utc)


def _document_url(raw: Any, expected_url: str) -> bool:
    """Allow only a catalogued DOCUMENTATION lead, not any same-host URL.

    This is a strict offline allowlist; it cannot prove that a publisher
    actually served the document, nor does it validate redirects or TLS.
    New official release URLs need review before adding separate leads.
    """
    if not isinstance(raw, str) or not 10 <= len(raw) <= 1024:
        return False
    if raw != expected_url:
        return False
    try:
        parsed = urlsplit(raw)
        expected = urlsplit(expected_url)
        return (
            parsed.scheme == "https" and parsed.hostname == expected.hostname
            and parsed.username is None and parsed.password is None
            and parsed.port in (None, 443) and not parsed.fragment
            and not parsed.query and parsed.path not in ("", "/")
            and not any(c.isspace() for c in raw)
        )
    except ValueError:
        return False


def _refused(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_OFFICIAL_RECEIPT_REFUSED",
        "reason": reason, "receipt": None,
        "official_document_authenticity_verified": False,
        "historical_capture_attested": False,
        "macro_direction_inferred": False, "can_feed_exante_bias": False,
        "real_oos_authorized": False, "trade_authorized": False,
        "worker_enabled": False, "scheduler_enabled": False,
    }


def inspect_claimed_macro_receipt_lab(
    receipt: Any, *, forecast_issued_at: datetime, evaluated_at: datetime,
) -> dict[str, Any]:
    """Inspect a caller-supplied text snapshot; NEVER attest it as official.

    A checksum proves only internal text consistency, and a claimed timestamp
    cannot prove that the text was actually obtainable at forecast issuance.
    """
    if (not isinstance(forecast_issued_at, datetime)
            or forecast_issued_at.tzinfo is None
            or not isinstance(evaluated_at, datetime)
            or evaluated_at.tzinfo is None):
        raise ValueError("Explicit timezone-aware evaluation and issuance required")
    issued = forecast_issued_at.astimezone(timezone.utc)
    evaluated = evaluated_at.astimezone(timezone.utc)
    if issued > evaluated:
        return _refused("Forecast issue later than evaluation")
    if not isinstance(receipt, Mapping) or set(receipt) != RECEIPT_FIELDS:
        return _refused("Unsupported or retrospective input fields")
    if receipt["state"] != "LAB_CALLER_SUPPLIED_TEXT":
        return _refused("Only explicitly untrusted manual snapshots permitted")
    source_id = receipt["source_id"]
    if not isinstance(source_id, str) or source_id not in SOURCES:
        return _refused("Unknown official source lead")
    source = SOURCES[source_id]
    event_id = receipt["event_id"]
    if not isinstance(event_id, str) or not IDENTITY.fullmatch(event_id):
        return _refused("Missing bounded unique event identifier")
    if not _document_url(receipt["document_url"], source["documentation_url"]):
        return _refused("Document URL not the catalogued official documentation lead")
    kind = receipt["kind"]
    if kind not in ("SCHEDULED", "RELEASED_CONTEXT"):
        return _refused("Unknown event type")
    event = _utc(receipt["event_at_utc"])
    published = _utc(receipt["published_at_utc"])
    captured = _utc(receipt["captured_at_utc"])
    if event is None or published is None or captured is None:
        return _refused("Timestamp must be exact UTC")
    if not published <= captured <= issued:
        return _refused("Claims were not available by issuance cutoff")
    if kind == "SCHEDULED" and event <= issued:
        return _refused("Scheduled event is no longer future")
    if kind == "RELEASED_CONTEXT" and not event <= published:
        return _refused("Published context cannot predate event")
    excerpt = receipt["excerpt_utf8"]
    if not isinstance(excerpt, str) or not excerpt.strip():
        return _refused("Nonempty UTF-8 text snapshot required")
    raw = excerpt.encode("utf-8")
    if not 1 <= len(raw) <= MAX_TEXT_BYTES:
        return _refused("Text snapshot exceeds bounded size")
    digest = sha256(raw).hexdigest()
    claimed_hash = receipt["claimed_sha256"]
    if not isinstance(claimed_hash, str) or not HEX64.fullmatch(claimed_hash) or claimed_hash != digest:
        return _refused("Declared content hash does not match snapshot text")
    metadata = {
        "source_id": source_id, "currency": source["currency"],
        "family": source["family"], "event_id": event_id, "kind": kind,
        "event_at_utc": event.isoformat(), "published_at_utc": published.isoformat(),
        "captured_at_utc": captured.isoformat(), "forecast_issued_at_utc": issued.isoformat(),
        "document_url": receipt["document_url"], "content_sha256": digest,
        "content_bytes": len(raw),
        "url_matches_curated_documentation_lead_only": True,
        "page_content_or_release_authenticated": False,
    }
    record_digest = sha256(
        json.dumps(metadata, sort_keys=True, ensure_ascii=True, separators=(",", ":")).encode()
    ).hexdigest()
    return {
        **_refused(""),
        "state": "LAB_OFFICIAL_RECEIPT_QUARANTINED_UNATTESTED",
        "reason": "Source hostname, timestamp and bytes are only caller claims",
        "receipt": {**metadata, "record_sha256": record_digest},
        "structural_asof_consistent": True,
    }


__all__ = ["SCHEMA", "FAMILIES", "SOURCES", "MAX_TEXT_BYTES",
           "official_g8_source_catalog_lab", "inspect_claimed_macro_receipt_lab"]
