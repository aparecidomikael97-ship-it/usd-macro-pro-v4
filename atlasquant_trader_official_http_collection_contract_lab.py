"""Pure offline HTTP intake contract for official AtlasQuant Trader RSS leads.

No transport, HTTP request, scheduler, persistence, cost, deployment, live
data authentication or trading exists here. Response metadata and body are
CALLER-SUPPLIED and cannot attest to the official source's authenticity.
"""
from __future__ import annotations

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from hashlib import sha256
import re
from typing import Any, Mapping

from atlasquant_trader_official_rss_capture_lab import (
    MAX_FEED_BYTES, SCHEMA as RSS_SCHEMA, SOURCES,
    diff_official_rss_captures_lab, normalize_official_rss_lab,
)

PLAN_SCHEMA = "ATLASQUANT_TRADER_OFFICIAL_HTTP_PLAN_LAB_V1"
RESPONSE_SCHEMA = "ATLASQUANT_TRADER_OFFICIAL_HTTP_RESPONSE_LAB_V1"
CACHE_SCHEMA = "ATLASQUANT_TRADER_OFFICIAL_HTTP_CACHE_LAB_V1"
HEX64 = re.compile(r"^[0-9a-f]{64}$")
ETAG_RE = re.compile(r'^(?:W/)?"[\x20\x21\x23-\x7e]{1,180}"$')
ALLOWED_TYPES = {
    "application/rss+xml", "application/atom+xml", "application/rdf+xml",
    "application/xml", "text/xml",
}
MAX_TIMEOUT_SECONDS = 8


def _clock(value: Any) -> datetime:
    if (not isinstance(value, datetime) or value.tzinfo is None
            or value.utcoffset() is None):
        raise ValueError("Timezone-aware datetime required")
    return value.astimezone(timezone.utc)


def _parse_iso(value: Any) -> datetime | None:
    if not isinstance(value, str) or len(value) > 40:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return _clock(parsed)
    except ValueError:
        return None


def _last_modified(value: Any, *, not_after: datetime) -> bool:
    if not isinstance(value, str) or not 16 <= len(value) <= 60:
        return False
    if any(ord(ch) < 32 or ord(ch) > 126 for ch in value):
        return False
    try:
        parsed = parsedate_to_datetime(value)
        return _clock(parsed) <= not_after
    except (ValueError, TypeError, IndexError, OverflowError):
        return False


def _etag(value: Any) -> bool:
    return isinstance(value, str) and ETAG_RE.fullmatch(value) is not None


def _cache_ok(cache: Any, source_id: str, at: datetime) -> bool:
    if not isinstance(cache, Mapping) or source_id not in SOURCES:
        return False
    received = _parse_iso(cache.get("received_at_utc"))
    etag = cache.get("etag")
    last = cache.get("last_modified")
    return (
        cache.get("schema") == CACHE_SCHEMA
        and cache.get("source_id") == source_id
        and cache.get("feed_url") == SOURCES[source_id]["feed_url"]
        and isinstance(cache.get("payload_sha256"), str)
        and HEX64.fullmatch(cache["payload_sha256"]) is not None
        and received is not None and received <= at
        and (etag is None or _etag(etag))
        and (last is None or _last_modified(last, not_after=received))
        and cache.get("response_origin_attested") is False
        and cache.get("live_data_verified") is False
    )


def _base(reason: str) -> dict[str, Any]:
    return {
        "schema": RESPONSE_SCHEMA, "state": "LAB_RESPONSE_REJECTED",
        "reason": reason, "snapshot": None, "diff": None, "cache": None,
        "source_bytes_authenticity_verified": False,
        "response_origin_attested": False,
        "live_data_verified": False, "news_current_verified": False,
        "currency_bias": "AGUARDAR", "full_g8_news_coverage": False,
        "live_news": False, "can_feed_live_radar": False,
        "trade_authorized": False, "scheduler_enabled": False,
        "worker_enabled": False, "retry_scheduled": False,
        "notification_sent": False, "external_http_requests": 0,
        "new_cost_brl": 0,
    }


def plan_official_feed_request_lab(
    source_id: str, *, planned_at: datetime, previous_cache: Any = None,
) -> dict[str, Any]:
    """Describe a safe, non-executable conditional GET for a pinned source."""
    at = _clock(planned_at)
    if not isinstance(source_id, str) or source_id not in SOURCES:
        return {**_base("UNREVIEWED_FEED_SOURCE"), "schema": PLAN_SCHEMA}
    if at.date() < datetime(2026, 11, 4, tzinfo=timezone.utc).date():
        return {**_base("SOURCE_LEAD_NOT_RESEARCHED_AS_OF_DATE"),
                "schema": PLAN_SCHEMA}
    if previous_cache is not None and not _cache_ok(previous_cache, source_id, at):
        return {**_base("INVALID_OR_MISMATCHED_CACHE"), "schema": PLAN_SCHEMA}
    headers = {"Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml"}
    if previous_cache is not None:
        if previous_cache["etag"] is not None:
            headers["If-None-Match"] = previous_cache["etag"]
        if previous_cache["last_modified"] is not None:
            headers["If-Modified-Since"] = previous_cache["last_modified"]
    return {
        "schema": PLAN_SCHEMA, "state": "LAB_NON_EXECUTABLE_REQUEST_PLAN",
        "source_id": source_id, "url": SOURCES[source_id]["feed_url"],
        "method": "GET", "headers": headers,
        "planned_at_utc": at.isoformat(),
        "previous_payload_sha256": (
            previous_cache["payload_sha256"] if previous_cache else None),
        "previous_cache_received_at_utc": (
            previous_cache["received_at_utc"] if previous_cache else None),
        "timeout_seconds": MAX_TIMEOUT_SECONDS, "max_response_bytes": MAX_FEED_BYTES,
        "allow_redirects": False, "follow_redirects": False,
        "connect_to_network": False, "request_executed": False,
        "scheduler_enabled": False, "worker_enabled": False,
        "external_http_requests": 0, "new_cost_brl": 0,
        "trade_authorized": False, "live_news": False,
    }


def _valid_plan(plan: Any, at: datetime) -> bool:
    if not isinstance(plan, Mapping) or plan.get("schema") != PLAN_SCHEMA:
        return False
    source_id = plan.get("source_id")
    issued = _parse_iso(plan.get("planned_at_utc"))
    if not isinstance(source_id, str) or source_id not in SOURCES:
        return False
    if issued is None or issued > at:
        return False
    h = plan.get("headers")
    if not isinstance(h, Mapping):
        return False
    accept = "application/rss+xml, application/atom+xml, application/xml, text/xml"
    if h.get("Accept") != accept or set(h) - {"Accept", "If-None-Match", "If-Modified-Since"}:
        return False
    if "If-None-Match" in h and not _etag(h["If-None-Match"]):
        return False
    if "If-Modified-Since" in h and not _last_modified(h["If-Modified-Since"], not_after=issued):
        return False
    previous_hash = plan.get("previous_payload_sha256")
    previous_at = plan.get("previous_cache_received_at_utc")
    if previous_hash is not None and (
            not isinstance(previous_hash, str) or HEX64.fullmatch(previous_hash) is None
            or _parse_iso(previous_at) is None
            or _parse_iso(previous_at) > issued):
        return False
    if previous_hash is None and (previous_at is not None or len(h) != 1):
        return False
    return (
        plan.get("state") == "LAB_NON_EXECUTABLE_REQUEST_PLAN"
        and plan.get("url") == SOURCES[source_id]["feed_url"]
        and plan.get("method") == "GET"
        and type(plan.get("timeout_seconds")) is int
        and plan["timeout_seconds"] == MAX_TIMEOUT_SECONDS
        and plan.get("max_response_bytes") == MAX_FEED_BYTES
        and plan.get("allow_redirects") is False
        and plan.get("follow_redirects") is False
        and plan.get("connect_to_network") is False
        and plan.get("request_executed") is False
        and plan.get("scheduler_enabled") is False
        and plan.get("worker_enabled") is False
        and plan.get("external_http_requests") == 0
    )


def _headers(raw: Any) -> dict[str, str] | None:
    if not isinstance(raw, Mapping) or len(raw) > 50:
        return None
    out = {}
    for k, v in raw.items():
        if not isinstance(k, str) or not isinstance(v, str) or not 1 <= len(k) <= 70:
            return None
        name = k.lower()
        if name in out or not re.fullmatch(r"[a-z0-9-]+", name):
            return None
        if len(v) > 1024 or any(ord(ch) < 32 or ord(ch) == 127 for ch in v):
            return None
        out[name] = v.strip()
    return out


def _previous_report_ok(report: Any, plan: Mapping, received: datetime) -> bool:
    if not isinstance(report, Mapping):
        return False
    reported_at = _parse_iso(report.get("captured_at_utc"))
    source_id = plan["source_id"]
    source = SOURCES[source_id]
    return (
        report.get("schema") == RSS_SCHEMA
        and report.get("state") == "LAB_DOCUMENTARY_NEWS_ITEMS_ONLY"
        and report.get("source_id") == source_id
        and report.get("feed_url") == source["feed_url"]
        and report.get("currency") == source["currency"]
        and report.get("publisher") == source["publisher"]
        and report.get("topic") == source["topic"]
        and report.get("source_payload_sha256") == plan.get("previous_payload_sha256")
        and reported_at is not None and reported_at <= received
        and report.get("source_bytes_authenticity_verified") is False
        and report.get("trade_authorized") is False
        and report.get("live_news") is False
        and report.get("realtime_latency_verified") is False
    )


def reconcile_official_feed_response_lab(
    plan: Any, response: Any, *, received_at: datetime,
    previous_cache: Any = None, previous_report: Any = None,
) -> dict[str, Any]:
    """Reconcile caller-supplied synthetic HTTP response without making a request."""
    at = _clock(received_at)
    if not _valid_plan(plan, at):
        return _base("UNSAFE_OR_FORGED_REQUEST_PLAN")
    source_id = plan["source_id"]
    has_prior = plan["previous_payload_sha256"] is not None
    if has_prior != (previous_cache is not None):
        return _base("CACHE_NOT_SUPPLIED_AS_PLANNED")
    if has_prior and (
            not _cache_ok(previous_cache, source_id, at)
            or plan["previous_payload_sha256"] != previous_cache["payload_sha256"]
            or plan["previous_cache_received_at_utc"] != previous_cache["received_at_utc"]
            or plan["headers"].get("If-None-Match") != previous_cache["etag"]
            or plan["headers"].get("If-Modified-Since") != previous_cache["last_modified"]):
        return _base("PREVIOUS_CACHE_DOES_NOT_MATCH_PLAN")
    if previous_report is not None and (
            not has_prior or not _previous_report_ok(previous_report, plan, at)):
        return _base("UNTRUSTED_PREVIOUS_NEWS_REPORT")
    if not isinstance(response, Mapping):
        return _base("MISSING_CALLER_RESPONSE")
    code = response.get("status_code")
    body = response.get("body")
    hdr = _headers(response.get("headers"))
    if (type(code) is not int or hdr is None or not isinstance(body, bytes)
            or len(body) > MAX_FEED_BYTES
            or response.get("effective_url") != SOURCES[source_id]["feed_url"]):
        return _base("INVALID_SYNTHETIC_HTTP_RESPONSE")
    if "etag" in hdr and not _etag(hdr["etag"]):
        return _base("UNSAFE_ETAG")
    if "last-modified" in hdr and not _last_modified(hdr["last-modified"], not_after=at):
        return _base("UNSAFE_LAST_MODIFIED")
    result = _base("CALLER_RESPONSE_NOT_ORIGIN_AUTHENTICATED")
    result.update({
        "source_id": source_id, "status_code": code,
        "received_at_utc": at.isoformat(),
        "source_feed_url": SOURCES[source_id]["feed_url"],
        "response_is_caller_supplied": True,
    })
    if 300 <= code < 400 and code != 304:
        result.update(state="LAB_REDIRECT_BLOCKED", reason="MANUAL_SOURCE_REVIEW_REQUIRED")
        return result
    if code == 304:
        if body or not has_prior or not plan["headers"].get("If-None-Match") and not plan["headers"].get("If-Modified-Since"):
            return _base("UNEXPECTED_OR_UNCONDITIONAL_304")
        result.update({
            "state": "LAB_UNATTESTED_NOT_MODIFIED_CLAIM",
            "reason": "304_IS_NOT_PROOF_OF_FRESH_NEWS",
            "previous_payload_sha256": previous_cache["payload_sha256"],
            "previous_cache_received_at_utc": previous_cache["received_at_utc"],
            "cache": dict(previous_cache),
            "no_new_items_inferred": True,
        })
        return result
    if code == 429:
        result.update(state="LAB_SOURCE_RATE_LIMITED", reason="NO_AUTOMATIC_RETRY")
        return result
    if 500 <= code <= 599:
        result.update(state="LAB_SOURCE_UNAVAILABLE", reason="NO_STALE_TO_LIVE_PROMOTION")
        return result
    if code != 200:
        result.update(state="LAB_HTTP_STATUS_BLOCKED", reason="HTTP_STATUS_NOT_APPROVED")
        return result
    ctype = hdr.get("content-type", "").split(";", 1)[0].strip().lower()
    if ctype not in ALLOWED_TYPES or not body:
        return _base("NON_XML_OR_EMPTY_SUCCESS_RESPONSE")
    snap = normalize_official_rss_lab(source_id, body, captured_at=at)
    if snap.get("state") != "LAB_DOCUMENTARY_NEWS_ITEMS_ONLY":
        return _base("RSS_PARSER_REJECTED_" + snap.get("reason", "UNKNOWN"))
    diff = None
    if previous_report is not None:
        diff = diff_official_rss_captures_lab(previous_report, snap)
        if diff.get("state") != "LAB_NEWS_CHANGE_REVIEW_ONLY":
            return _base("INVALID_RSS_REVISION_COMPARISON")
    cache = {
        "schema": CACHE_SCHEMA, "source_id": source_id,
        "feed_url": SOURCES[source_id]["feed_url"],
        "payload_sha256": sha256(body).hexdigest(),
        "received_at_utc": at.isoformat(),
        "etag": hdr.get("etag"), "last_modified": hdr.get("last-modified"),
        "response_origin_attested": False, "live_data_verified": False,
    }
    result.update({
        "state": "LAB_DOCUMENTARY_RESPONSE_ACCEPTED_ONLY",
        "snapshot": snap, "diff": diff, "cache": cache,
        "body_bytes_not_archived": True, "no_trade_signal_created": True,
    })
    return result
