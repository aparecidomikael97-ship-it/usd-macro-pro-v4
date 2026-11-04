"""LAB-only BLS RSS2.0 item identity and pubDate consistency gate.

This is an OFFLINE syntactic cross-check over caller-supplied bytes and timing
claims. It does not establish actual news publication, source authenticity,
receipts, real feed latency, commercial rights, actual CPI/NFP, or trading bias.
"""
from __future__ import annotations

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Mapping
import xml.etree.ElementTree as ET

from atlasquant_trader_official_news_latency_lab import (
    STATE as LATENCY_STATE,
    assess_official_news_delays_lab,
)

SCHEMA = "ATLASQUANT_TRADER_OFFICIAL_RSS_ITEM_GATE_LAB_V1"
STATE = "LAB_RSS_ITEM_METADATA_INTERNALLY_CONSISTENT_UNATTESTED"
DENIED = "LAB_RSS_ITEM_GATE_REFUSED"
MAX_ITEM_COUNT = 100
MAX_TAG_COUNT = 1200


def _refuse(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": DENIED, "reason": reason,
        "event_id": None, "item_url": None,
        "rss_item_matches_declared_event": False,
        "rss_pubdate_matches_declared_clock": False,
        "raw_sha256_internally_matched": False,
        "source_origin_independently_attested": False,
        "source_release_time_independently_attested": False,
        "delivery_latency_independently_attested": False,
        "feed_actual_economic_value_extracted": False,
        "market_consensus_verified": False,
        "probability_calibrated": None,
        "directional_bias": "AGUARDAR",
        "realtime_news_enabled": False,
        "can_feed_live_radar": False,
        "can_feed_real_oos": False,
        "trade_authorized": False,
        "worker_enabled": False,
        "scheduler_enabled": False,
        "render_configuration_changed": False,
        "paid_provider_approved": False,
    }


def _one_plain_text(parent: ET.Element, name: str, *, maxlen: int) -> str | None:
    child = parent.findall(name)
    if len(child) != 1 or len(child[0]) != 0:
        return None
    value = child[0].text
    if not isinstance(value, str):
        return None
    value = value.strip()
    if not value or len(value) > maxlen or any(ord(c) < 32 for c in value):
        return None
    return value


def _rfc822_utc(value: str) -> datetime | None:
    try:
        instant = parsedate_to_datetime(value)
    except (TypeError, ValueError, OverflowError, IndexError):
        return None
    if instant.tzinfo is None or instant.utcoffset() is None:
        return None
    return instant.astimezone(timezone.utc)


def validate_official_bls_rss_item_lab(
    record: Mapping[str, Any] | None, *, evaluated_at: datetime,
) -> dict[str, Any]:
    """Require matching RSS item/link/pubDate before considering a feed sample.

    Does NOT trust the asserted source or claimed clocks. No SSRF/network is
    performed, and RSS content is never interpreted as CPI/NFP actuals.
    """
    earlier = assess_official_news_delays_lab([record], evaluated_at=evaluated_at)
    if earlier["state"] != LATENCY_STATE:
        return _refuse("Underlying news delivery receipt contract refused: " + str(earlier["reason"]))
    payload = record["raw_payload_bytes"]
    if any(marker in payload.upper() for marker in (b"<!DOCTYPE", b"<!ENTITY")):
        return _refuse("DTD and entity declarations are not allowed in RSS fixtures")
    try:
        root = ET.fromstring(payload)
    except (ET.ParseError, ValueError, TypeError, OverflowError):
        return _refuse("Invalid XML bytes")
    if root.tag != "rss" or root.attrib != {"version": "2.0"}:
        return _refuse("RSS 2.0 root/version required in this limited pilot")
    if sum(1 for _ in root.iter()) > MAX_TAG_COUNT:
        return _refuse("Oversized XML node count")
    channels = root.findall("channel")
    if len(channels) != 1:
        return _refuse("Exactly one RSS channel required")
    channel = channels[0]
    items = channel.findall("item")
    if not 1 <= len(items) <= MAX_ITEM_COUNT:
        return _refuse("RSS item count outside bounded pilot")
    match = []
    seen_links: set[str] = set()
    for item in items:
        link = _one_plain_text(item, "link", maxlen=240)
        if link is None or link in seen_links:
            return _refuse("Missing or duplicate RSS item links")
        seen_links.add(link)
        if link == record["item_url"]:
            match.append(item)
    if len(match) != 1:
        return _refuse("No unique RSS item points to the declared official release URL")
    item = match[0]
    title = _one_plain_text(item, "title", maxlen=240)
    published = _one_plain_text(item, "pubDate", maxlen=100)
    if title is None or published is None:
        return _refuse("RSS item has no plain title and pubDate")
    parsed = _rfc822_utc(published)
    if parsed is None:
        return _refuse("RSS pubDate must carry an explicit numeric offset or recognized UTC zone")
    claimed = datetime.fromisoformat(record["feed_published_at_utc"].replace("Z", "+00:00"))
    if parsed != claimed:
        return _refuse("RSS item pubDate and declared feed-published clock disagree")
    return {
        **_refuse(""),
        "state": STATE, "reason": None,
        "event_id": record["event_id"],
        "item_url": record["item_url"],
        "rss_item_title_unverified": title,
        "rss_item_count": len(items),
        "rss_item_pubdate_claimed_utc": parsed.isoformat(),
        "rss_item_matches_declared_event": True,
        "rss_pubdate_matches_declared_clock": True,
        "raw_sha256_internally_matched": True,
        "capture_mode": record["capture_mode"],
        "note": ("RSS metadata and SHA-256 agree internally with caller-supplied "
                 "claims. Source identity, original publication and all "
                 "receipt clocks remain UNATTESTED; no market actuals or forecasts."),
    }


__all__ = ["SCHEMA", "STATE", "DENIED", "validate_official_bls_rss_item_lab"]
