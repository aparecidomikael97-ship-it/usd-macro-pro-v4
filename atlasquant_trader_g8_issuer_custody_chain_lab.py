"""Pure, offline LAB custody envelopes for G8 issuer documents.

This prepares future local AM12 capture without contacting any issuer, writing
files, scheduling collection or accepting historical point-in-time authority.
A SHA-256 hash attests self-consistency only: anyone can rehash a forgery.
"""
from __future__ import annotations

import base64
import binascii
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import re
from typing import Any

from atlasquant_fx_universe import CURRENCIES

SCHEMA = "ATLASQUANT_TRADER_G8_LOCAL_ISSUER_CUSTODY_LAB_V1"
RESEARCH_VISIBLE_AFTER = datetime(2026, 11, 9, tzinfo=timezone.utc)
MAX_BODY_BYTES = 1024 * 1024
MAX_CHAIN = 16
RECORD_KEYS = frozenset((
    "schema", "currency", "decision_date", "document_url",
    "content_type", "collector_started_at_utc", "collector_finished_at_utc",
    "source_http_status_claim", "redirects_followed_claim",
    "sequence", "previous_record_sha256", "body_base64", "body_sha256",
    "record_sha256", "caller_supplied_and_not_independently_attested",
))
DOCS = {
    "USD": ("2026-10-28", "https://www.federalreserve.gov/newsevents/pressreleases/monetary20261028a.htm", "text/html"),
    "EUR": ("2026-10-29", "https://www.ecb.europa.eu/press/pr/date/2026/html/ecb.mp261029~9a493adf17.en.html", "text/html"),
    "GBP": ("2026-11-05", "https://www.bankofengland.co.uk/monetary-policy-summary-and-minutes/2026/november-2026", "text/html"),
    "CAD": ("2026-10-28", "https://www.bankofcanada.ca/2026/10/fad-press-release-2026-10-28/", "text/html"),
    "AUD": ("2026-11-03", "https://www.rba.gov.au/media-releases/2026/mr-26-30.html", "text/html"),
    "JPY": ("2026-10-30", "https://www.boj.or.jp/en/mopo/mpmdeci/mpr_2026/k261030a.pdf", "application/pdf"),
    "CHF": ("2026-09-24", "https://www.snb.ch/en/publications/communication/press-releases-restricted/pre_20260924", "text/html"),
    "NZD": ("2026-10-28", "https://www.rbnz.govt.nz/news-and-events/news/2026/10/ocr-held-at-2-75-percent", "text/html"),
}
_UTC = re.compile(r"20\d\d-\d\d-\d\dT\d\d:\d\d:\d\dZ\Z")
_HEX = re.compile(r"[0-9a-f]{64}\Z")


def _time(value: Any) -> datetime | None:
    if not isinstance(value, str) or _UTC.fullmatch(value) is None:
        return None
    try:
        stamp = datetime.fromisoformat(value[:-1] + "+00:00")
        return stamp if stamp.microsecond == 0 else None
    except (ValueError, OverflowError):
        return None


def _json_bytes(value: dict[str, Any]) -> bytes:
    return json.dumps(value, ensure_ascii=True, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def _refuse(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_RECEIPT_BLOCKED", "reason": reason,
        "receipt_count": 0, "currency": None, "record_sha256": None,
        "byte_count": 0, "chain_integrity_check": False,
        "original_publisher_bytes_at_release_attested": False,
        "issuer_origin_independently_authenticated": False,
        "collector_clock_independently_authenticated": False,
        "historical_point_in_time_eligible": False,
        "eligible_to_feed_macro_bias": False,
        "validated_directional_accuracy": None, "operational_bias": "AGUARDAR",
        "trade_authorized": False, "worker_enabled": False,
        "scheduler_enabled": False, "publishable": False,
        "network_requests": 0, "file_writes": 0, "new_cost_brl": 0,
    }


def build_local_policy_document_receipt_lab(
    currency: Any, body: Any, *, started_at_utc: Any,
    finished_at_utc: Any, sequence: Any = 1,
    previous_record_sha256: Any = None,
) -> dict[str, Any]:
    """Build a self-contained *caller-asserted* receipt; no I/O or persistence."""
    if (not isinstance(currency, str) or currency not in DOCS
            or not isinstance(body, bytes) or not 1 <= len(body) <= MAX_BODY_BYTES
            or type(sequence) is not int or not 1 <= sequence <= MAX_CHAIN
            or (sequence == 1 and previous_record_sha256 is not None)
            or (sequence > 1 and (not isinstance(previous_record_sha256, str)
                                  or _HEX.fullmatch(previous_record_sha256) is None))):
        return _refuse("INVALID_SOURCE_BYTES_OR_CHAIN_SEQUENCE")
    start, finish = _time(started_at_utc), _time(finished_at_utc)
    if (start is None or finish is None or start < RESEARCH_VISIBLE_AFTER
            or not start <= finish <= start + timedelta(seconds=120)):
        return _refuse("CAPTURE_WINDOW_NOT_VALIDATED")
    day, url, mime = DOCS[currency]
    record = {
        "schema": SCHEMA, "currency": currency, "decision_date": day,
        "document_url": url, "content_type": mime,
        "collector_started_at_utc": started_at_utc,
        "collector_finished_at_utc": finished_at_utc,
        "source_http_status_claim": 200, "redirects_followed_claim": False,
        "sequence": sequence, "previous_record_sha256": previous_record_sha256,
        "body_base64": base64.b64encode(body).decode("ascii"),
        "body_sha256": sha256(body).hexdigest(),
        "caller_supplied_and_not_independently_attested": True,
    }
    record["record_sha256"] = sha256(_json_bytes(record)).hexdigest()
    return record


def inspect_local_policy_document_receipt_lab(
    receipt: Any, *, as_of_utc: Any,
) -> dict[str, Any]:
    """Verify internal bytes/metadata, never assert issuer truth or first-seen."""
    out = _refuse("INVALID_RECORD_OR_ASOF")
    if (not isinstance(as_of_utc, datetime) or as_of_utc.tzinfo is None
            or as_of_utc.utcoffset() is None
            or not isinstance(receipt, dict) or receipt.keys() != RECORD_KEYS):
        return out
    now = as_of_utc.astimezone(timezone.utc)
    if now < RESEARCH_VISIBLE_AFTER:
        out["state"] = "LAB_RESEARCH_NOT_VISIBLE_ASOF"
        out["reason"] = "NO_RETROSPECTIVE_AVAILABILITY_BEFORE_2026_11_09"
        return out
    currency = receipt["currency"]
    if not isinstance(currency, str) or currency not in DOCS:
        return out
    decision_day, exact_url, mime = DOCS[currency]
    if (receipt["schema"] != SCHEMA or receipt["decision_date"] != decision_day
            or receipt["document_url"] != exact_url
            or receipt["content_type"] != mime
            or type(receipt["source_http_status_claim"]) is not int
            or receipt["source_http_status_claim"] != 200
            or receipt["redirects_followed_claim"] is not False
            or receipt["caller_supplied_and_not_independently_attested"] is not True):
        return out
    start = _time(receipt["collector_started_at_utc"])
    finish = _time(receipt["collector_finished_at_utc"])
    if (start is None or finish is None or start < RESEARCH_VISIBLE_AFTER
            or not start <= finish <= start + timedelta(seconds=120)):
        return out
    if now < finish:
        out["state"] = "LAB_RECEIPT_NOT_YET_VISIBLE_ASOF"
        out["reason"] = "LOCAL_CAPTURE_FINISHED_AFTER_DECISION_ASOF"
        return out
    seq, previous = receipt["sequence"], receipt["previous_record_sha256"]
    if (type(seq) is not int or not 1 <= seq <= MAX_CHAIN
            or (seq == 1 and previous is not None)
            or (seq > 1 and (not isinstance(previous, str) or _HEX.fullmatch(previous) is None))):
        return out
    encoded, digest, record_digest = (receipt["body_base64"],
                                      receipt["body_sha256"], receipt["record_sha256"])
    if (not isinstance(encoded, str) or len(encoded) > (MAX_BODY_BYTES * 4 // 3 + 8)
            or not isinstance(digest, str) or _HEX.fullmatch(digest) is None
            or not isinstance(record_digest, str) or _HEX.fullmatch(record_digest) is None):
        return out
    try:
        raw = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError):
        return out
    if (not 1 <= len(raw) <= MAX_BODY_BYTES
            or base64.b64encode(raw).decode("ascii") != encoded
            or sha256(raw).hexdigest() != digest):
        return out
    without_record_digest = {k: v for k, v in receipt.items() if k != "record_sha256"}
    if sha256(_json_bytes(without_record_digest)).hexdigest() != record_digest:
        return out
    out.update({
        "state": "LAB_LOCAL_RECEIPT_BYTES_SELF_CONSISTENT_UNATTESTED",
        "reason": "HASH_AND_CHAIN_METADATA_ALONE_CANNOT_PROVE_FIRST_PUBLICATION",
        "receipt_count": 1, "currency": currency,
        "record_sha256": record_digest, "byte_count": len(raw),
        "chain_integrity_check": True,
        "issuer_document_url_claim": exact_url,
        "capture_end_local_claim_utc": receipt["collector_finished_at_utc"],
    })
    return out


def inspect_local_policy_document_chain_lab(
    records: Any, *, as_of_utc: Any,
) -> dict[str, Any]:
    """Check local version order and SHA links; not a signed/immutable log."""
    out = _refuse("INVALID_RECEIPT_CHAIN")
    if not isinstance(records, list) or not 1 <= len(records) <= MAX_CHAIN:
        return out
    prior_digest, prior_end, currency = None, None, None
    total_bytes = 0
    for number, record in enumerate(records, start=1):
        item = inspect_local_policy_document_receipt_lab(record, as_of_utc=as_of_utc)
        if item["state"] != "LAB_LOCAL_RECEIPT_BYTES_SELF_CONSISTENT_UNATTESTED":
            out["reason"] = "RECEIPT_FAILED_" + item["state"]
            return out
        event_end = _time(record["collector_finished_at_utc"])
        event_start = _time(record["collector_started_at_utc"])
        if (record["sequence"] != number
                or record["previous_record_sha256"] != prior_digest
                or (currency is not None and record["currency"] != currency)
                or (prior_end is not None and event_start < prior_end)
                or (prior_end is not None and event_end <= prior_end)):
            out["reason"] = "CHAIN_LINK_ORDER_OR_CURRENCY_MISMATCH"
            return out
        currency = record["currency"]
        prior_digest = record["record_sha256"]
        prior_end = event_end
        total_bytes += item["byte_count"]
    out.update({
        "state": "LAB_LOCAL_APPEND_CHAIN_SELF_CONSISTENT_UNATTESTED",
        "reason": "UNSIGNED_LOCAL_HASH_CHAIN_NOT_INDEPENDENT_CUSTODY",
        "receipt_count": len(records), "currency": currency,
        "record_sha256": prior_digest, "byte_count": total_bytes,
        "chain_integrity_check": True,
    })
    return out


__all__ = ["SCHEMA", "DOCS", "MAX_BODY_BYTES", "build_local_policy_document_receipt_lab",
           "inspect_local_policy_document_receipt_lab",
           "inspect_local_policy_document_chain_lab"]
