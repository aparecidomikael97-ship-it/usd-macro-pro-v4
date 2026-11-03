"""Offline timestamp and byte-integrity audit for proposed free BLS news feeds.

No network, scheduling, Render integration or actual RSS polling. Clock fields
are CALLER CLAIMS; even valid bytes+SHA256 cannot verify original source,
independent receipt time, feed publication time, or provider latency.
Designed to refuse a paid-provider recommendation based on synthetic evidence.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
from typing import Any, Mapping, Sequence
import re
from urllib.parse import urlsplit

from atlasquant_trader_primary_news_routes_lab import EVENTS, SOURCES, SOURCE_BY_EVENT

SCHEMA = "ATLASQUANT_TRADER_OFFICIAL_NEWS_LATENCY_AUDIT_LAB_V1"
STATE = "LAB_DECLARED_NEWS_DELAYS_NOT_INDEPENDENTLY_VERIFIED"
DENIED = "LAB_NEWS_LATENCY_AUDIT_REFUSED"
MAX_RECORDS = 30
MIN_INDEPENDENT_REAL_EVENTS_FOR_PROVIDER_DECISION = 10
RESEARCH_START = date(2026, 11, 3)
ALLOW_EVENTS = frozenset((
    "BLS_US_EMPLOYMENT_20261106",
    "BLS_US_CPI_20261110",
))
FIELDS = frozenset((
    "event_id", "source_id", "source_url", "item_url",
    "scheduled_release_at_utc", "feed_published_at_utc",
    "first_seen_at_utc", "captured_at_utc", "displayed_at_utc",
    "capture_mode", "http_status", "content_type",
    "raw_payload_bytes", "raw_payload_sha256",
))
CAPTURE_MODES = frozenset(("SYNTHETIC_CONTRACT_TEST", "MANUAL_UNATTESTED"))
_CANON_EVENTS = {x["event_id"]: x for x in EVENTS if x["event_id"] in ALLOW_EVENTS}
_CANON_SOURCES = {x["source_id"]: x for x in SOURCES}
_DIGEST = re.compile(r"^[0-9a-f]{64}$")


def _clock(raw: Any) -> datetime | None:
    if not isinstance(raw, str) or len(raw) > 40 or not raw.endswith("Z"):
        return None
    try:
        parsed = datetime.fromisoformat(raw[:-1] + "+00:00")
    except (OverflowError, ValueError):
        return None
    if parsed.utcoffset() != timedelta(0):
        return None
    return parsed.astimezone(timezone.utc)


def _bls_item_url(value: Any) -> bool:
    if not isinstance(value, str) or len(value) > 240:
        return False
    try:
        parsed = urlsplit(value)
    except ValueError:
        return False
    return (parsed.scheme == "https" and parsed.netloc == "www.bls.gov"
            and parsed.path.startswith("/news.release/")
            and parsed.path.endswith(".htm")
            and not parsed.username and not parsed.password
            and not parsed.query and not parsed.fragment)


def _deny(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": DENIED, "reason": reason,
        "records": [], "record_count": 0,
        "synthetic_contract_count": 0, "manual_unattested_count": 0,
        "independent_delivery_receipts": 0,
        "source_publication_time_attested": False,
        "capture_time_independently_attested": False,
        "feed_authenticity_cryptographically_verified": False,
        "news_delay_verified": False, "news_realtime_guaranteed": False,
        "provider_comparison_evidence_sufficient": False,
        "paid_provider_recommended": False, "paid_provider_approved": False,
        "raw_source_payloads_archived": False,
        "directional_bias": None, "prediction_accuracy_proven": False,
        "can_feed_live_radar": False, "trade_authorized": False,
        "worker_enabled": False, "scheduler_enabled": False,
        "render_configuration_changed": False,
    }


def assess_official_news_delays_lab(
    records: Sequence[Mapping[str, Any]] | None, *, evaluated_at: datetime,
) -> dict[str, Any]:
    """Describe caller-claimed delays after exact event/byte/clock checks.

    A schedule is not a release receipt. RSS pubDate is publisher-supplied
    metadata, not necessarily the actual publication/embargo instant.
    Detection/capture/display times can all be forged by the caller; reporting
    numbers requires these limitations to remain explicitly attached.
    """
    if (not isinstance(evaluated_at, datetime) or evaluated_at.tzinfo is None
            or evaluated_at.utcoffset() is None):
        raise ValueError("Evaluation instant needs a real timezone")
    now = evaluated_at.astimezone(timezone.utc)
    if now.date() < RESEARCH_START:
        return _deny("Cannot backdate source audit before research")
    if (not isinstance(records, (tuple, list))
            or not 1 <= len(records) <= MAX_RECORDS):
        return _deny("Need a bounded nonempty offline capture collection")
    keys: set[str] = set()
    output = []
    for x in records:
        if not isinstance(x, Mapping) or set(x) != FIELDS:
            return _deny("Unrecognized news capture fields or added permissions")
        eid, sid = x["event_id"], x["source_id"]
        if not isinstance(eid, str) or eid not in _CANON_EVENTS or eid in keys:
            return _deny("Repeated, date-only or unrecognized macro event")
        keys.add(eid)
        if (sid != SOURCE_BY_EVENT[eid] or sid not in _CANON_SOURCES
                or x["source_url"] != _CANON_SOURCES[sid]["url"]):
            return _deny("Feed and event identity are not an approved official lead")
        if not _bls_item_url(x["item_url"]):
            return _deny("BLS story URL is malformed or not on the allowlist")
        expected = _clock(_CANON_EVENTS[eid]["earliest_at_utc"])
        scheduled = _clock(x["scheduled_release_at_utc"])
        published = _clock(x["feed_published_at_utc"])
        first_seen = _clock(x["first_seen_at_utc"])
        captured = _clock(x["captured_at_utc"])
        displayed = _clock(x["displayed_at_utc"])
        if (expected is None or scheduled != expected or
                published is None or first_seen is None or
                captured is None or displayed is None):
            return _deny("Missing, invented or noncanonical UTC event clocks")
        # Schedule is a lower bound for this restricted BLS pilot. A
        # publication timestamp before it needs independent manual review.
        if not scheduled <= published <= first_seen <= captured <= displayed <= now:
            return _deny("Clock sequence impossible or event information leaked early")
        if (displayed - scheduled > timedelta(days=7)
                or displayed - first_seen > timedelta(days=2)):
            return _deny("Stale capture or display latency outside pilot bound")
        if x["capture_mode"] not in CAPTURE_MODES:
            return _deny("Mode must explicitly identify synthetic or unattested manual")
        if type(x["http_status"]) is not int or x["http_status"] != 200:
            return _deny("HTTP response status is not the allowed research sample")
        if x["content_type"] not in ("application/rss+xml", "application/xml", "text/xml"):
            return _deny("Unexpected declared RSS content type")
        body = x["raw_payload_bytes"]
        digest = x["raw_payload_sha256"]
        if (not isinstance(body, bytes) or not 1 <= len(body) <= 200_000
                or b"\x00" in body or not isinstance(digest, str)
                or not _DIGEST.fullmatch(digest)
                or sha256(body).hexdigest() != digest):
            return _deny("Missing, inconsistent or tampered source payload bytes")
        try:
            body.decode("utf-8")
        except UnicodeDecodeError:
            return _deny("Payload is not strict UTF-8")
        # Do NOT interpret content: having one valid checksum does not prove
        # the body came from that feed, its RSS pubDate or that it reports NFP.
        def seconds(later: datetime, earlier: datetime) -> int:
            return int((later - earlier).total_seconds())
        output.append({
            "event_id": eid, "source_id": sid,
            "capture_mode": x["capture_mode"],
            "story_url_claimed": x["item_url"],
            "scheduled_release_at_utc": scheduled.isoformat(),
            "feed_published_claimed_at_utc": published.isoformat(),
            "first_seen_claimed_at_utc": first_seen.isoformat(),
            "captured_claimed_at_utc": captured.isoformat(),
            "displayed_claimed_at_utc": displayed.isoformat(),
            "declared_schedule_to_feed_pubdate_seconds": seconds(published, scheduled),
            "declared_feed_pubdate_to_first_seen_seconds": seconds(first_seen, published),
            "declared_first_seen_to_capture_seconds": seconds(captured, first_seen),
            "declared_capture_to_display_seconds": seconds(displayed, captured),
            "declared_schedule_to_display_seconds": seconds(displayed, scheduled),
            "raw_payload_sha256_internally_matched": True,
            "source_provenance_independently_verified": False,
            "publication_time_independently_verified": False,
            "receipt_clock_independently_verified": False,
            "publication_to_detection_real_latency_proven": False,
            "can_be_used_as_live_news": False,
        })
    output.sort(key=lambda r: r["event_id"])
    return {
        **_deny(""), "state": STATE, "reason": None,
        "record_count": len(output), "records": output,
        "synthetic_contract_count": sum(
            r["capture_mode"] == "SYNTHETIC_CONTRACT_TEST" for r in output),
        "manual_unattested_count": sum(
            r["capture_mode"] == "MANUAL_UNATTESTED" for r in output),
        "independent_delivery_receipts": 0,
        "provider_decision_minimum_events": MIN_INDEPENDENT_REAL_EVENTS_FOR_PROVIDER_DECISION,
        "note": (
            "Declared dates and locally matched SHA-256, NOT a measured "
            "real-world delivery SLA. Must collect authenticated receipts "
            "across independent events before any provider comparison."
        ),
    }


__all__ = [
    "SCHEMA", "STATE", "DENIED", "FIELDS", "CAPTURE_MODES",
    "MIN_INDEPENDENT_REAL_EVENTS_FOR_PROVIDER_DECISION",
    "assess_official_news_delays_lab",
]
