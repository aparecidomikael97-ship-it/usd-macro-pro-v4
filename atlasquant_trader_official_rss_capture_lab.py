"""OFFLINE parsing and revision detection for selected official RSS/Atom leads.

This never performs HTTP, downloads a feed, verifies its publisher, archives
source bytes, obtains a commercial licence, enables a scheduler or predicts FX.
The bytes and capture clock are supplied by a caller and remain UNATTESTED.
Intended to prepare auditable 3x-daily official-news intake in a later phase.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from hashlib import sha256
import re
from typing import Any, Mapping
from urllib.parse import urlsplit
import xml.etree.ElementTree as ET

from atlasquant_fx_universe import OFFICIAL_PAIRS
from atlasquant_trader_g8_official_feed_registry_lab import DIRECTORY_LINKED_LEADS

SCHEMA = "ATLASQUANT_TRADER_OFFICIAL_RSS_CAPTURE_LAB_V1"
DIFF_SCHEMA = "ATLASQUANT_TRADER_OFFICIAL_RSS_REVISION_DIFF_LAB_V1"
MAX_FEED_BYTES = 256 * 1024
MAX_ITEMS = 100
REVIEW_DATE = date(2026, 11, 4)
HEX24 = re.compile(r"^[0-9a-f]{24}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")

# These are OFFICIAL-PAGE-documented feed leads, not validated live streams.
SOURCES = {
    "US_BLS_EMPLOYMENT": {
        "currency": "USD", "publisher": "US_BLS", "topic": "EMPLOYMENT",
        "feed_url": "https://www.bls.gov/feed/empsit.rss",
        "hostname": "www.bls.gov",
    },
    "US_BLS_CPI": {
        "currency": "USD", "publisher": "US_BLS", "topic": "INFLATION",
        "feed_url": "https://www.bls.gov/feed/cpi.rss",
        "hostname": "www.bls.gov",
    },
    "US_FED_MONETARY": {
        "currency": "USD", "publisher": "US_FEDERAL_RESERVE",
        "topic": "MONETARY_POLICY",
        "feed_url": "https://www.federalreserve.gov/feeds/press_monetary.xml",
        "hostname": "www.federalreserve.gov",
    },
    "EU_ECB_PRESS": {
        "currency": "EUR", "publisher": "EU_ECB", "topic": "CENTRAL_BANK_NEWS",
        "feed_url": "https://www.ecb.europa.eu/rss/press.html",
        "hostname": "www.ecb.europa.eu",
    },
    "EU_ECB_STATPRESS": {
        "currency": "EUR", "publisher": "EU_ECB", "topic": "STATISTICS_NEWS",
        "feed_url": "https://www.ecb.europa.eu/rss/statpress.html",
        "hostname": "www.ecb.europa.eu",
    },
}

# Research-only additions backed by first-party RSS directories. Admission to
# this OFFLINE parser does not validate network access, licences or freshness.
# NZD's unconfirmed RSS lead is intentionally NOT allowed here.
SOURCES.update({
    source_id: {key: details[key] for key in (
        "currency", "publisher", "topic", "feed_url", "hostname")}
    for source_id, details in DIRECTORY_LINKED_LEADS.items()
})


def _base(reason: str, *, diff: bool = False) -> dict[str, Any]:
    return {
        "schema": DIFF_SCHEMA if diff else SCHEMA,
        "state": "LAB_REJECTED", "reason": reason,
        "items": [] if not diff else None,
        "changes": [] if diff else None,
        "missing_from_current_partial_feed": [] if diff else None,
        "source_bytes_authenticity_verified": False,
        "source_original_bytes_archived": False,
        "commercial_reuse_license_verified": False,
        "full_g8_news_coverage": False,
        "live_news": False, "realtime_latency_verified": False,
        "currency_bias": "AGUARDAR", "probability_calibrated": None,
        "can_feed_live_radar": False, "trade_authorized": False,
        "scheduler_enabled": False, "worker_enabled": False,
        "external_http_requests": 0, "new_cost_brl": 0,
    }


def _tag(el: ET.Element) -> str:
    return el.tag.rsplit("}", 1)[-1].lower()


def _child(el: ET.Element, name: str) -> ET.Element | None:
    return next((x for x in el if _tag(x) == name), None)


def _value(el: ET.Element | None) -> str:
    return " ".join("".join(el.itertext()).split()) if el is not None else ""


def _published(raw: str) -> datetime | None:
    if not isinstance(raw, str) or not 10 <= len(raw) <= 100:
        return None
    try:
        point = parsedate_to_datetime(raw)
    except (ValueError, TypeError, IndexError):
        try:
            point = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except (ValueError, OverflowError):
            return None
    return (point.astimezone(timezone.utc) if point.tzinfo is not None
            and point.utcoffset() is not None else None)


def _official_url(raw: Any, host: str) -> bool:
    if not isinstance(raw, str) or not 20 <= len(raw) <= 1800:
        return False
    try:
        u = urlsplit(raw)
        return (u.scheme == "https" and u.hostname == host
                and u.username is None and u.password is None
                and u.port in (None, 443) and not u.fragment
                and u.path not in ("", "/")
                and not any(ch.isspace() for ch in raw))
    except ValueError:
        return False


def _extract_item(item: ET.Element, atom: bool) -> tuple[str, str, str, str, str]:
    title = _value(_child(item, "title"))
    guid = _value(_child(item, "id" if atom else "guid"))
    published = (_value(_child(item, "published"))
                 or _value(_child(item, "updated"))) if atom else (
                     _value(_child(item, "pubdate"))
                     or _value(_child(item, "date")))
    description = _value(_child(item, "summary" if atom else "description"))
    link = ""
    if atom:
        for el in item:
            if _tag(el) == "link" and el.attrib.get("rel", "alternate") == "alternate":
                link = el.attrib.get("href", "")
                break
    else:
        link = _value(_child(item, "link"))
    return title, guid, link, published, description


def normalize_official_rss_lab(
    source_id: str, raw_xml: Any, *, captured_at: datetime,
) -> dict[str, Any]:
    """Parse bounded caller-provided RSS/RDF/Atom without network access."""
    if (not isinstance(captured_at, datetime) or captured_at.tzinfo is None
            or captured_at.utcoffset() is None):
        raise ValueError("Capture timestamp must contain timezone")
    now = captured_at.astimezone(timezone.utc)
    if not isinstance(source_id, str) or source_id not in SOURCES:
        return _base("UNREVIEWED_FEED_SOURCE")
    if now.date() < REVIEW_DATE:
        return _base("SOURCE_LEAD_NOT_RESEARCHED_AS_OF_DATE")
    if (not isinstance(raw_xml, bytes) or not 1 <= len(raw_xml) <= MAX_FEED_BYTES
            or b"<!doctype" in raw_xml.lower()
            or b"<!entity" in raw_xml.lower()):
        return _base("UNSAFE_OR_OVERSIZED_XML")
    try:
        root = ET.fromstring(raw_xml)
    except (ET.ParseError, RecursionError):
        return _base("INVALID_XML")
    root_tag = _tag(root)
    if root_tag == "rss":
        channel = _child(root, "channel")
        elements = [x for x in channel if _tag(x) == "item"] if channel is not None else []
        if channel is None:
            return _base("RSS_CHANNEL_REQUIRED")
        atom = False
    elif root_tag == "rdf":
        elements = [x for x in root if _tag(x) == "item"]
        atom = False
    elif root_tag == "feed":
        elements = [x for x in root if _tag(x) == "entry"]
        atom = True
    else:
        return _base("ONLY_RSS_RDF_OR_ATOM_ALLOWED")
    if len(elements) > MAX_ITEMS:
        return _base("TOO_MANY_FEED_ITEMS")
    src = SOURCES[source_id]
    indexed = set()
    items = []
    for entry in elements:
        title, guid, link, pub, descr = _extract_item(entry, atom)
        stamp = _published(pub)
        if (not 2 <= len(title) <= 240 or not 2 <= len(guid or link) <= 1024
                or stamp is None or stamp > now + timedelta(minutes=5)
                or not _official_url(link, src["hostname"])):
            return _base("UNSAFE_OR_UNDATED_NEWS_ITEM")
        sid = sha256(f"{source_id}|{guid or link}".encode("utf-8")).hexdigest()[:24]
        if sid in indexed:
            return _base("DUPLICATE_NEWS_ID")
        indexed.add(sid)
        revision = sha256(
            (title + "\n" + link + "\n" + stamp.isoformat() + "\n" + descr)
            .encode("utf-8")
        ).hexdigest()
        items.append({
            "id": sid, "source_id": source_id,
            "currency": src["currency"], "topic": src["topic"],
            "title": title, "publisher_url": link,
            "publisher_claimed_at_utc": stamp.isoformat(),
            "captured_at_utc": now.isoformat(),
            "claimed_pub_to_capture_seconds": int((now - stamp).total_seconds()),
            "revision_sha256": revision,
            "source_attested": False, "market_direction": "AGUARDAR",
        })
    items.sort(key=lambda i: (i["publisher_claimed_at_utc"], i["id"]),
               reverse=True)
    result = _base("CALLER_BYTES_NOT_AUTHENTICATED")
    result.update({
        "state": "LAB_DOCUMENTARY_NEWS_ITEMS_ONLY",
        "source_id": source_id, "publisher": src["publisher"],
        "currency": src["currency"], "topic": src["topic"],
        "feed_url": src["feed_url"],
        "captured_at_utc": now.isoformat(),
        "source_payload_sha256": sha256(raw_xml).hexdigest(),
        "items": items, "item_count": len(items),
        "feed_empty_does_not_prove_no_news": True,
        "note": "RSS documental parcial; fonte/latencia originais nao auditadas.",
    })
    return result


def diff_official_rss_captures_lab(previous: Any, current: Any) -> dict[str, Any]:
    """Find new/revised article *claims*; disappearance is not retraction."""
    if not isinstance(previous, Mapping) or not isinstance(current, Mapping):
        return _base("REQUIRED_CAPTURES_MISSING", diff=True)
    if (previous.get("schema") != SCHEMA or current.get("schema") != SCHEMA
            or previous.get("state") != "LAB_DOCUMENTARY_NEWS_ITEMS_ONLY"
            or current.get("state") != "LAB_DOCUMENTARY_NEWS_ITEMS_ONLY"
            or previous.get("source_id") != current.get("source_id")
            or previous.get("currency") != current.get("currency")
            or not isinstance(previous.get("source_id"), str)
            or previous.get("source_id") not in SOURCES
            or any(book.get(key) is not False
                   for book in (previous, current) for key in (
                       "source_bytes_authenticity_verified", "live_news",
                       "realtime_latency_verified", "trade_authorized"))):
        return _base("UNVERIFIED_OR_MISMATCHED_FEEDS", diff=True)
    a = _published(previous.get("captured_at_utc"))
    b = _published(current.get("captured_at_utc"))
    if a is None or b is None or b <= a:
        return _base("CAPTURE_TIMESTAMPS_NOT_INCREASING", diff=True)
    for book in (previous, current):
        items = book.get("items")
        source = SOURCES[book["source_id"]]
        if (not isinstance(items, list) or len(items) > MAX_ITEMS
                or any(not isinstance(x, Mapping) for x in items)
                or book.get("item_count") != len(items)
                or book.get("currency") != source["currency"]
                or book.get("topic") != source["topic"]
                or book.get("publisher") != source["publisher"]
                or book.get("feed_url") != source["feed_url"]
                or not isinstance(book.get("source_payload_sha256"), str)
                or HEX64.fullmatch(book["source_payload_sha256"]) is None):
            return _base("INVALID_ITEM_LIST", diff=True)
        ids = []
        for x in items:
            identity, rev = x.get("id"), x.get("revision_sha256")
            issued = _published(x.get("publisher_claimed_at_utc"))
            if (not isinstance(identity, str) or HEX24.fullmatch(identity) is None
                    or not isinstance(rev, str) or HEX64.fullmatch(rev) is None
                    or x.get("source_id") != book.get("source_id")
                    or x.get("currency") != book.get("currency")
                    or x.get("market_direction") != "AGUARDAR"
                    or x.get("source_attested") is not False
                    or x.get("captured_at_utc") != book.get("captured_at_utc")
                    or not isinstance(x.get("title"), str)
                    or not 2 <= len(x["title"]) <= 240
                    or not _official_url(x.get("publisher_url"), source["hostname"])
                    or issued is None or issued > _published(book["captured_at_utc"]) + timedelta(minutes=5)):
                return _base("FORGED_OR_INCOMPLETE_ITEM", diff=True)
            ids.append(identity)
        if len(set(ids)) != len(ids):
            return _base("DUPLICATE_ITEM_ID", diff=True)
    before = {x["id"]: x for x in previous["items"]}
    after = {x["id"]: x for x in current["items"]}
    affected = [p for p in OFFICIAL_PAIRS
                if current["currency"] in p.split("/")]
    changes = []
    for identity, item in sorted(after.items()):
        old = before.get(identity)
        if old is None or old["revision_sha256"] != item["revision_sha256"]:
            changes.append({
                "item_id": identity,
                "change": "NEW_ARTICLE" if old is None else "DOCUMENT_REVISED",
                "source_url": item.get("publisher_url"),
                "currency": current["currency"],
                "possible_pair_context": affected,
                "directional_impact": "AGUARDAR",
                "human_source_verification_needed": True,
            })
    result = _base("DIFF_NOT_INDEPENDENTLY_AUTHENTICATED", diff=True)
    result.update({
        "state": "LAB_NEWS_CHANGE_REVIEW_ONLY",
        "source_id": current["source_id"],
        "currency": current["currency"],
        "observed_at_utc": b.isoformat(),
        "changes": changes, "change_count": len(changes),
        "missing_from_current_partial_feed": sorted(set(before) - set(after)),
        "affected_pairs": affected if changes else [],
        "notification_sent": False,
        "news_item_disappearance_is_not_retraction": True,
        "note": "Comparacao parcial sem autenticar bytes ou notificar usuario.",
    })
    return result


__all__ = ["SCHEMA", "DIFF_SCHEMA", "SOURCES", "normalize_official_rss_lab",
           "diff_official_rss_captures_lab"]
