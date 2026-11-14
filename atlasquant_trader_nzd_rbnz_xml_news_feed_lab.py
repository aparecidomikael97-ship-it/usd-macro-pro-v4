"""RBNZ official XML news feed — bounded issuer announcement discovery LAB.

The bank explicitly documents an XML feed covering OCR media releases.
Its Terms of Use dated 12 Nov 2026 permit <=120 automated requests/hour,
with RBNZ-Automated-Agent/<organisation>/<application> User-Agent and
non-disruptive operation. This is the bank's EXPRESSLY documented XML
publication interface, not an alternate HTML URL chosen to evade the
previous HTTP 403 on its OCR overview page.

This reader (a) can inspect supplied XML bytes WITHOUT network, and
(b) can make exactly one GET only with an explicit CLI flag. It never
follows redirects, retries, writes original XML, saves artifacts, accesses
the broker, or publishes directions. Feed metadata/claimed pubDate
IS NOT a separately verified real first-seen timestamp. Even a news item
about OCR is not evidence of the realized OCR, a prediction, or impact.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from hashlib import sha256
import json
import re
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, HTTPHandler, HTTPSHandler, HTTPRedirectHandler
from xml.etree import ElementTree as ET

from atlasquant_trader_nzd_rbnz_access_terms_lab import (
    OCR_MEDIA_RELEASE_XML_FEED_URL as URL,
    REQUIRED_USER_AGENT_PATTERN,
    TERMS_LAST_UPDATED,
)

SCHEMA = "ATLASQUANT_NZD_RBNZ_XML_NEWS_FEED_DISCOVERY_LAB_V1"
USER_AGENT = "RBNZ-Automated-Agent/AtlasQuant/FX28ResearchLAB"
MAX_BYTES = 1_000_000
MAX_ITEMS = 200
MAX_TITLE = 400
MAX_LINK = 2048
ATOM = "{http://www.w3.org/2005/Atom}"
RFC3339 = re.compile(r"20\d\d-\d\d-\d\dT\d\d:\d\d:\d\d(?:Z|[+-]\d\d:\d\d)\Z")
UTC_RECEIPT = re.compile(r"20\d\d-\d\d-\d\dT\d\d:\d\d:\d\dZ\Z")
TOPIC = re.compile(
    r"\b(?:official cash rate|ocr|monetary policy(?: statement| review| decision)?)\b",
    re.I,
)
ALLOWED_TYPES = frozenset((
    "application/xml", "text/xml", "application/rss+xml",
    "application/atom+xml",
))
RECEIPT_KEYS = frozenset((
    "source_url", "final_url", "status", "content_type",
    "body_sha256", "started_at_utc", "finished_at_utc",
    "https_validation_claim", "redirects_followed",
))


def _utc(value: Any) -> datetime | None:
    if type(value) is not datetime or value.tzinfo is None:
        return None
    try:
        if value.utcoffset() is None or value.microsecond:
            return None
        return value.astimezone(timezone.utc)
    except (OverflowError, ValueError, TypeError):
        return None


def _stamp(value: Any) -> datetime | None:
    if type(value) is not str or UTC_RECEIPT.fullmatch(value) is None:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc)
    except ValueError:
        return None


def _published(value: str, kind: str) -> datetime | None:
    if type(value) is not str or len(value) > 120:
        return None
    try:
        if kind == "RSS":
            parsed = parsedate_to_datetime(value)
        elif kind == "ATOM" and RFC3339.fullmatch(value):
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        else:
            return None
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            return None
        return parsed.astimezone(timezone.utc).replace(microsecond=0)
    except (TypeError, ValueError, OverflowError):
        return None


def _link_valid(value: Any) -> bool:
    if type(value) is not str or not 1 <= len(value) <= MAX_LINK:
        return False
    try:
        u = urlsplit(value)
        return (u.scheme == "https"
                and u.hostname in ("www.rbnz.govt.nz", "rbnz.govt.nz")
                and u.port is None and u.username is None
                and u.password is None and u.fragment == ""
                and u.path.startswith("/") and not any(
                    ord(c) < 32 or ord(c) == 127 for c in value))
    except (ValueError, TypeError):
        return False


def _one_text(parent: ET.Element, name: str) -> str | None:
    hits = parent.findall(name)
    if len(hits) != 1:
        return None
    content = "".join(hits[0].itertext()).strip()
    return content or None


def _base(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "state": "LAB_RBNZ_XML_FEED_BLOCKED_NO_GO",
        "reason": reason,
        "official_feed_url": URL,
        "terms_last_updated_claim": TERMS_LAST_UPDATED,
        "request_user_agent_pattern": REQUIRED_USER_AGENT_PATTERN,
        "feed_body_sha256_local": None,
        "receipt_finished_utc_local_claim": None,
        "parsed_format": None,
        "items_in_feed": 0,
        "ocr_related_title_matches": 0,
        "ocr_related_articles": [],
        "feed_metadata_is_not_first_seen_timestamp": True,
        "topic_match_is_not_ocr_decision_proof": True,
        "actual_ocr_percent_verified": None,
        "pre_event_market_consensus_verified": False,
        "signed_nzd_fx_effect_verified": False,
        "historical_first_seen_authenticated": False,
        "original_xml_retained": False,
        "am12_ocr_original_archived": False,
        "operational_bias": "AGUARDAR",
        "trade_authorized": False,
        "live_alert_allowed": False,
        "publishable": False,
        "scheduler_enabled": False,
        "worker_enabled": False,
        "http_requests": 0,
        "file_writes": 0,
        "new_cost_brl": 0,
        "research_only": True,
    }


def inspect_rbnz_news_xml_bytes_lab(
    *, original_xml: Any, receipt: Any, inspected_at_utc: Any,
) -> dict[str, Any]:
    """Inspect only captured bytes+receipt; do not infer outcome or vintage."""
    out = _base("INVALID_BYTES_RECEIPT_OR_CLOCK")
    now = _utc(inspected_at_utc)
    if (now is None or type(original_xml) is not bytes
            or not 20 <= len(original_xml) <= MAX_BYTES
            or type(receipt) is not dict
            or set(receipt) != RECEIPT_KEYS):
        return out
    start, end = (_stamp(receipt.get(key)) for key in (
        "started_at_utc", "finished_at_utc"))
    if (start is None or end is None
            or end < start or end-start > timedelta(seconds=30)
            or end > now or now-end > timedelta(seconds=30)
            or receipt.get("source_url") != URL
            or receipt.get("final_url") != URL
            or type(receipt.get("status")) is not int
            or receipt.get("status") != 200
            or type(receipt.get("content_type")) is not str
            or receipt["content_type"].split(";")[0].strip().lower()
               not in ALLOWED_TYPES
            or receipt.get("https_validation_claim") is not True
            or receipt.get("redirects_followed") is not False
            or type(receipt.get("body_sha256")) is not str
            or receipt["body_sha256"] != sha256(original_xml).hexdigest()):
        out["reason"] = "UNTRUSTED_URL_UTC_TLS_CONTENT_TYPE_OR_SHA"
        return out
    if (re.search(rb"<!\s*(?:DOCTYPE|ENTITY)\b",
                  original_xml, flags=re.I) is not None):
        out["reason"] = "XML_DTD_OR_ENTITY_DECLARATION_PROHIBITED"
        return out
    try:
        root = ET.fromstring(original_xml)
    except (ET.ParseError, ValueError, TypeError, RecursionError):
        out["reason"] = "MALFORMED_XML"
        return out

    if root.tag == "rss" and root.attrib.get("version") == "2.0":
        kind = "RSS"
        channels = root.findall("channel")
        if len(channels) != 1:
            out["reason"] = "INVALID_RSS_CHANNEL"
            return out
        channel = channels[0]
        channel_title = _one_text(channel, "title")
        entries = channel.findall("item")
    elif root.tag == ATOM+"feed":
        kind = "ATOM"
        channel_title = _one_text(root, ATOM+"title")
        entries = root.findall(ATOM+"entry")
    else:
        out["reason"] = "UNSUPPORTED_XML_FEED_VARIANT"
        return out

    if (channel_title is None or not any(x in channel_title.lower() for x in (
            "reserve bank", "rbnz", "te pūtea"))
            or len(entries) > MAX_ITEMS):
        out["reason"] = "ISSUER_CHANNEL_NOT_IDENTIFIED_OR_TOO_MANY_ENTRIES"
        return out

    seen: set[str] = set()
    relevant = []
    for entry in entries:
        if kind == "RSS":
            title = _one_text(entry, "title")
            url = _one_text(entry, "link")
            published_raw = _one_text(entry, "pubDate")
            guid = _one_text(entry, "guid")
        else:
            title = _one_text(entry, ATOM+"title")
            links = [
                elem.attrib.get("href") for elem in entry.findall(ATOM+"link")
                if elem.attrib.get("rel", "alternate") == "alternate"
            ]
            url = links[0] if len(links) == 1 else None
            published_raw = (_one_text(entry, ATOM+"published")
                             or _one_text(entry, ATOM+"updated"))
            guid = _one_text(entry, ATOM+"id")

        published = _published(published_raw or "", kind)
        if (title is None or len(title) > MAX_TITLE
                or not _link_valid(url)
                or published is None
                or not datetime(1999, 1, 1, tzinfo=timezone.utc) <= published <= end
                or guid is not None and len(guid) > MAX_LINK):
            out["reason"] = "UNVERIFIED_FEED_ITEM_TITLE_LINK_OR_PUBLICATION_DATE"
            return out
        key = guid or url
        if key in seen:
            out["reason"] = "DUPLICATE_NEWS_ITEM_ID"
            return out
        seen.add(key)
        if TOPIC.search(title):
            # Topic classification only. No rates, article bodies or headlines
            # are extracted or redistributed by this source.
            relevant.append({
                "official_article_url": url,
                "headline_sha256_local": sha256(title.encode("utf-8")).hexdigest(),
                "published_utc_issuer_feed_claim": published.isoformat(),
                "observed_at_utc_local_receipt_claim": end.isoformat(),
                "first_seen_by_issuer_or_prior_reader_attested": False,
                "classification": "OCR_RELATED_HEADLINE_NOT_AUTHENTICATED_DECISION",
                "actual_ocr_pct": None,
                "pre_event_consensus": None,
                "directional_fx_effect": None,
            })

    out.update({
        "state": "LAB_RBNZ_XML_FEED_STRUCTURE_CHECKED_NO_GO",
        "reason": "TITLE_AND_PUBLICATION_DATE_NOT_POLICY_ACTUAL_OR_FIRST_SEEN",
        "feed_body_sha256_local": receipt["body_sha256"],
        "receipt_finished_utc_local_claim": end.isoformat(),
        "parsed_format": kind,
        "items_in_feed": len(entries),
        "ocr_related_title_matches": len(relevant),
        "ocr_related_articles": relevant,
    })
    return out


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def collect_rbnz_news_xml_once_lab(
    *, explicit_request: Any,
    request_open: Callable[..., Any] | None = None,
    now_stamp: Callable[[], str] | None = None,
) -> dict[str, Any]:
    """Single compliant issuer XML GET; NO retries, redirect or storage."""
    out = _base("EXPLICIT_REQUEST_FLAG_REQUIRED")
    if explicit_request is not True:
        return out
    if request_open is None:
        request_open = build_opener(_NoRedirect, HTTPSHandler).open
    if now_stamp is None:
        now_stamp = lambda: datetime.now(timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ")
    if not callable(request_open) or not callable(now_stamp):
        out["reason"] = "INVALID_TEST_OPEN_OR_CLOCK"
        return out
    start = now_stamp()
    req = Request(URL, headers={
        "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml",
        "User-Agent": USER_AGENT,
    }, method="GET")
    out["http_requests"] = 1
    try:
        with request_open(req, timeout=12) as response:
            raw = response.read(MAX_BYTES+1)
            receipt = {
                "source_url": URL, "final_url": response.geturl(),
                "status": response.status,
                "content_type": response.headers.get("Content-Type", ""),
                "body_sha256": sha256(raw).hexdigest(),
                "started_at_utc": start,
                "finished_at_utc": now_stamp(),
                "https_validation_claim": True,
                "redirects_followed": response.geturl() != URL,
            }
        inspected = _stamp(receipt["finished_at_utc"])
        if inspected is None:
            out["reason"] = "COLLECTOR_FINISH_CLOCK_INVALID"
            return out
        result = inspect_rbnz_news_xml_bytes_lab(
            original_xml=raw, receipt=receipt, inspected_at_utc=inspected)
        result["http_requests"] = 1
        return result
    except HTTPError as exc:
        out["reason"] = ("EXPLICIT_FEED_HTTP_"+str(exc.code)+"_NO_RETRY"
                         if type(exc.code) is int and 300 <= exc.code <= 599
                         else "OFFICIAL_XML_HTTP_STATUS_UNUSABLE")
    except (URLError, OSError, TypeError, ValueError, KeyError,
            OverflowError, RuntimeError, RecursionError):
        out["reason"] = "OFFICIAL_XML_FEED_HTTPS_OR_RESPONSE_FAILED_NO_RETRY"
    return out


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--inspect-official-once", action="store_true")
    args = p.parse_args(argv)
    report = collect_rbnz_news_xml_once_lab(
        explicit_request=args.inspect_official_once)
    print(json.dumps(report, sort_keys=True, indent=2, ensure_ascii=False))
    return 0 if report["state"] == "LAB_RBNZ_XML_FEED_STRUCTURE_CHECKED_NO_GO" else 2


if __name__ == "__main__":
    raise SystemExit(main())
