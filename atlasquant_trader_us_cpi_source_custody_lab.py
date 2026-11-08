"""Offline custody *preflight* for October 2026 US CPI news research.

The caller supplies bytes and timestamps. Neither HTTPS provenance, original
publication, independent clock, analyst-poll semantics nor CPI values are
verified here. Passing this check NEVER authorizes a nowcast or a trade.
"""
from __future__ import annotations

import base64
import binascii
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import re
from typing import Any
from urllib.parse import urlsplit


SCHEMA = "ATLASQUANT_TRADER_US_CPI_NEWS_SOURCE_CUSTODY_LAB_V1"
RESEARCH_VISIBLE_AFTER = datetime(2026, 11, 9, tzinfo=timezone.utc)
RELEASE = datetime(2026, 11, 10, 13, 30, tzinfo=timezone.utc)
MAX_BODY_BYTES = 1024 * 1024
MAX_CAPTURE_SECONDS = 120
METRIC = "CPI_U_HEADLINE_MOM_SEASONALLY_ADJUSTED_PERCENT_CHANGE"
PREVIOUS_ID = "US_CPI_2026_09_BLS_PREVIOUS"
CONSENSUS_ID = "US_CPI_2026_10_EXACT_EVENT_ANALYST_POLL"
SOURCE_IDS = frozenset((PREVIOUS_ID, CONSENSUS_ID))
OFFICIAL_PREVIOUS_URL = "https://www.bls.gov/news.release/archives/cpi_10142026.htm"
OFFICIAL_PREVIOUS_PUBLICATION_CLAIM = "2026-10-14T12:30:00Z"
_CLOCK = re.compile(r"20\d\d-\d\d-\d\dT\d\d:\d\d:\d\dZ\Z")
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_RECORD_FIELDS = frozenset((
    "schema", "source_id", "source_url_claim", "metric", "reference_month",
    "source_kind_claim", "source_published_at_claim_utc", "source_content_type_claim",
    "http_status_claim", "collector_started_at_claim_utc", "collector_finished_at_claim_utc",
    "captured_body_base64", "captured_body_sha256", "receipt_sha256",
    "caller_supplied_unattested", "scheduled_event_at_utc",
))


def _instant(value: Any) -> datetime | None:
    if not isinstance(value, str) or _CLOCK.fullmatch(value) is None:
        return None
    try:
        return datetime.fromisoformat(value[:-1] + "+00:00")
    except (ValueError, OverflowError):
        return None


def _json_bytes(record: dict[str, Any]) -> bytes:
    return json.dumps(record, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("utf-8")


def _external_https_url(value: Any) -> bool:
    if not isinstance(value, str) or len(value) > 2048 or any(ord(c) < 33 for c in value):
        return False
    try:
        parsed = urlsplit(value)
        host = parsed.hostname
        return (parsed.scheme == "https" and parsed.port is None
                and parsed.username is None and parsed.password is None
                and isinstance(host, str) and "." in host
                and not host.endswith((".local", ".localhost", ".internal", ".invalid"))
                and bool(parsed.path) and not parsed.fragment)
    except ValueError:
        return False


def _identity_valid(source_id: Any, source_url: Any, published_at: Any) -> bool:
    if not isinstance(source_id, str) or source_id not in SOURCE_IDS or not _external_https_url(source_url):
        return False
    published = _instant(published_at)
    if published is None:
        return False
    if source_id == PREVIOUS_ID:
        return (source_url == OFFICIAL_PREVIOUS_URL
                and published_at == OFFICIAL_PREVIOUS_PUBLICATION_CLAIM)
    # A claimed analyst survey still needs separate independent examination.
    return (published >= datetime(2026, 10, 1, tzinfo=timezone.utc) and published < RELEASE
            and urlsplit(source_url).hostname != "www.bls.gov")


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_SOURCE_CUSTODY_BLOCKED", "reason": reason,
        "source_id": None, "body_bytes_self_consistent": False,
        "capture_claim_before_forecast": False,
        "publisher_origin_independently_verified": False,
        "capture_clock_independently_witnessed": False,
        "source_publication_time_independently_witnessed": False,
        "event_poll_value_and_metric_parsed_from_original": False,
        "historical_pit_eligible": False,
        "ready_for_news_nowcast": False, "ready_for_fx_bias": False,
        "probabilities": None, "operational_bias": "AGUARDAR",
        "trade_authorized": False, "worker_enabled": False,
        "scheduler_enabled": False, "network_requests": 0,
        "file_writes": 0, "new_cost_brl": 0,
    }


def build_us_cpi_source_receipt_lab(
    source_id: Any, body: Any, *, source_url: Any,
    published_at_claim_utc: Any, started_at_claim_utc: Any,
    finished_at_claim_utc: Any,
) -> dict[str, Any]:
    """Build an *unattested* in-memory receipt from caller-provided raw bytes."""
    if (not _identity_valid(source_id, source_url, published_at_claim_utc)
            or not isinstance(body, bytes) or not 1 <= len(body) <= MAX_BODY_BYTES):
        return _blocked("INVALID_SOURCE_ID_URL_OR_BODY")
    published = _instant(published_at_claim_utc)
    start = _instant(started_at_claim_utc)
    finish = _instant(finished_at_claim_utc)
    if (start is None or finish is None or published is None
            or start < RESEARCH_VISIBLE_AFTER
            or not published <= start <= finish <= start + timedelta(seconds=MAX_CAPTURE_SECONDS)):
        return _blocked("INVALID_CAPTURE_OR_PUBLISHER_CLAIM_CLOCK")
    record = {
        "schema": SCHEMA, "source_id": source_id,
        "source_url_claim": source_url, "metric": METRIC,
        "reference_month": "2026-09" if source_id == PREVIOUS_ID else "2026-10",
        "source_kind_claim": "OFFICIAL_PRIOR_RELEASE" if source_id == PREVIOUS_ID
                             else "EXACT_EVENT_ANALYST_POLL",
        "source_published_at_claim_utc": published_at_claim_utc,
        "source_content_type_claim": "text/html", "http_status_claim": 200,
        "collector_started_at_claim_utc": started_at_claim_utc,
        "collector_finished_at_claim_utc": finished_at_claim_utc,
        "captured_body_base64": base64.b64encode(body).decode("ascii"),
        "captured_body_sha256": sha256(body).hexdigest(),
        "caller_supplied_unattested": True,
        "scheduled_event_at_utc": "2026-11-10T13:30:00Z",
    }
    record["receipt_sha256"] = sha256(_json_bytes(record)).hexdigest()
    return record


def inspect_us_cpi_source_receipt_lab(
    receipt: Any, *, as_of_utc: Any, forecast_cutoff_utc: Any,
) -> dict[str, Any]:
    """Check local consistency and *claimed* chronology, never source authority."""
    result = _blocked("INVALID_RECEIPT_OR_CLOCK")
    if (not isinstance(receipt, dict) or receipt.keys() != _RECORD_FIELDS
            or not isinstance(as_of_utc, datetime) or as_of_utc.tzinfo is None
            or as_of_utc.utcoffset() is None or not isinstance(forecast_cutoff_utc, datetime)
            or forecast_cutoff_utc.tzinfo is None or forecast_cutoff_utc.utcoffset() is None):
        return result
    observed = as_of_utc.astimezone(timezone.utc)
    cutoff = forecast_cutoff_utc.astimezone(timezone.utc)
    if observed < RESEARCH_VISIBLE_AFTER:
        return _blocked("RESEARCH_NOT_VISIBLE_BEFORE_NOV9")
    if not RESEARCH_VISIBLE_AFTER <= cutoff <= observed or cutoff >= RELEASE:
        return _blocked("FORECAST_CUTOFF_NOT_AN_OBSERVED_PRERELEASE_INSTANT")
    source_id = receipt["source_id"]
    if (receipt["schema"] != SCHEMA
            or not _identity_valid(source_id, receipt["source_url_claim"],
                                   receipt["source_published_at_claim_utc"])
            or receipt["metric"] != METRIC
            or receipt["reference_month"] != ("2026-09" if source_id == PREVIOUS_ID else "2026-10")
            or receipt["source_kind_claim"] != (
                "OFFICIAL_PRIOR_RELEASE" if source_id == PREVIOUS_ID else "EXACT_EVENT_ANALYST_POLL")
            or receipt["source_content_type_claim"] != "text/html"
            or type(receipt["http_status_claim"]) is not int or receipt["http_status_claim"] != 200
            or receipt["caller_supplied_unattested"] is not True
            or receipt["scheduled_event_at_utc"] != "2026-11-10T13:30:00Z"):
        return result
    published = _instant(receipt["source_published_at_claim_utc"])
    start = _instant(receipt["collector_started_at_claim_utc"])
    finish = _instant(receipt["collector_finished_at_claim_utc"])
    if (published is None or start is None or finish is None
            or start < RESEARCH_VISIBLE_AFTER
            or not published <= start <= finish <= start + timedelta(seconds=MAX_CAPTURE_SECONDS)):
        return result
    if finish > observed:
        return _blocked("CAPTURE_FINISHED_AFTER_INSPECTION_ASOF")
    if finish > cutoff:
        return _blocked("CAPTURE_FINISHED_AFTER_FORECAST_CUTOFF")
    encoded = receipt["captured_body_base64"]
    digest = receipt["captured_body_sha256"]
    record_digest = receipt["receipt_sha256"]
    if (not isinstance(encoded, str) or len(encoded) > MAX_BODY_BYTES * 4 // 3 + 8
            or not isinstance(digest, str) or _SHA256.fullmatch(digest) is None
            or not isinstance(record_digest, str) or _SHA256.fullmatch(record_digest) is None):
        return result
    try:
        raw = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error):
        return result
    if (not 1 <= len(raw) <= MAX_BODY_BYTES
            or base64.b64encode(raw).decode("ascii") != encoded
            or sha256(raw).hexdigest() != digest):
        return result
    unsigned = {name: value for name, value in receipt.items() if name != "receipt_sha256"}
    if sha256(_json_bytes(unsigned)).hexdigest() != record_digest:
        return result
    result.update({
        "state": "LAB_BYTES_CONSISTENT_CLAIMED_PRERELEASE_CAPTURE_UNATTESTED",
        "reason": "LOCAL_HASHES_DO_NOT_PROVE_PUBLISHER_OR_PIT_AUTHORITY",
        "source_id": source_id, "body_bytes_self_consistent": True,
        "capture_claim_before_forecast": True, "captured_body_sha256": digest,
        "receipt_sha256": record_digest,
    })
    return result


def inspect_us_cpi_pre_event_bundle_lab(
    previous_receipt: Any, consensus_receipt: Any, *,
    as_of_utc: Any, forecast_cutoff_utc: Any,
) -> dict[str, Any]:
    """Both documents are mandatory; a paired candidate is still NOT a nowcast."""
    result = _blocked("MISSING_OR_UNATTESTED_CPI_PRE_EVENT_SOURCES")
    for expected, candidate in ((PREVIOUS_ID, previous_receipt), (CONSENSUS_ID, consensus_receipt)):
        checked = inspect_us_cpi_source_receipt_lab(
            candidate, as_of_utc=as_of_utc, forecast_cutoff_utc=forecast_cutoff_utc)
        if checked["state"] != "LAB_BYTES_CONSISTENT_CLAIMED_PRERELEASE_CAPTURE_UNATTESTED":
            result["reason"] = f"{expected}:{checked['reason']}"
            return result
        if checked["source_id"] != expected:
            result["reason"] = "MISLABELED_OR_REUSED_NEWS_SOURCE"
            return result
    result.update({
        "state": "LAB_TWO_SOURCE_DOCUMENTARY_CANDIDATE_UNATTESTED",
        "reason": "NEEDS_EXTERNAL_ORIGIN_TIME_AND_EVENT_POLL_CONTENT_AUDIT",
        "source_id": "US_CPI_2026_10_PRE_EVENT_BUNDLE",
        "body_bytes_self_consistent": True,
        "capture_claim_before_forecast": True,
    })
    return result


__all__ = [
    "SCHEMA", "RELEASE", "PREVIOUS_ID", "CONSENSUS_ID", "OFFICIAL_PREVIOUS_URL",
    "OFFICIAL_PREVIOUS_PUBLICATION_CLAIM", "MAX_BODY_BYTES",
    "build_us_cpi_source_receipt_lab", "inspect_us_cpi_source_receipt_lab",
    "inspect_us_cpi_pre_event_bundle_lab",
]
