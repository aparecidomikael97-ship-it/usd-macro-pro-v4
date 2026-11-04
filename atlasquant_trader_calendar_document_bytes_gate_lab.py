"""Bind supplied raw calendar-document bytes to three daily OFFLINE reviews.

SHA-256 can establish only consistency between bytes provided to this call
and the caller's claimed document digest. It cannot establish publisher
identity, TLS provenance, an independent timestamp, or archival custody.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from typing import Any, Mapping

from atlasquant_trader_calendar_three_daily_review_lab import (
    build_three_daily_calendar_review_lab,
)
from atlasquant_trader_g8_context_completeness_3x_lab import SLOTS
from atlasquant_trader_official_change_detection_lab import _utc

SCHEMA = "ATLASQUANT_TRADER_CALENDAR_DOCUMENT_BYTES_GATE_LAB_V1"
CAPTURE_FIELDS = frozenset((
    "slot", "captured_at_utc", "snapshots", "document_receipts",
))
RECEIPT_FIELDS = frozenset((
    "source_id", "event_id", "effective_url", "received_at_utc", "body",
))
MAX_DOCUMENTS_PER_SLOT = 64
MAX_DOCUMENT_BYTES = 256 * 1024
MAX_SLOT_BYTES = 2 * 1024 * 1024
MAX_RECEIPT_LAG = timedelta(minutes=10)


def _refused(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_BLOCKED", "reason": reason,
        "calendar_review": None, "checked_document_receipts": [],
        "checked_document_count": 0, "local_chain_head_sha256": None,
        "supplied_bytes_match_declared_digest": False,
        "original_publisher_bytes_authenticated": False,
        "publisher_identity_verified": False,
        "tls_response_custody_attested": False,
        "receipt_timestamps_independently_verified": False,
        "local_chain_independently_witnessed": False,
        "three_daily_updates_verified": False,
        "real_time_calendar_verified": False,
        "notifications_sent": False,
        "operational_bias": "AGUARDAR",
        "publishable": False, "trade_authorized": False,
        "worker_enabled": False, "scheduler_enabled": False,
        "external_http_requests": 0, "new_cost_brl": 0,
    }


def audit_three_daily_calendar_document_bytes_lab(
    captures: Any, *, at: datetime,
) -> dict[str, Any]:
    """Recompute hashes and a local chain for caller-supplied event bodies.

    Reject mismatches and incomplete sets. A complete result is still LAB
    and must never promote source trust, three daily execution or FX bias.
    """
    if not isinstance(at, datetime) or at.tzinfo is None or at.utcoffset() is None:
        raise ValueError("Timezone-aware evaluation clock required")
    if not isinstance(captures, (list, tuple)) or len(captures) > 3:
        return _refused("MAX_THREE_DOCUMENTARY_CAPTURES_PER_DAY")
    standard_captures = []
    for capture in captures:
        if not isinstance(capture, Mapping) or set(capture) != CAPTURE_FIELDS:
            return _refused("INVALID_DOCUMENT_RECEIPT_ENVELOPE")
        standard_captures.append({
            "slot": capture["slot"], "captured_at_utc": capture["captured_at_utc"],
            "snapshots": capture["snapshots"],
        })
    calendar = build_three_daily_calendar_review_lab(standard_captures, at=at)
    if calendar.get("state") != "LAB_THREE_DAILY_CALENDAR_REVIEW_ONLY":
        return _refused("CALENDAR_REVIEW_REJECTED")

    now = at.astimezone(timezone.utc)
    ordered = sorted(captures, key=lambda cap: SLOTS.index(cap["slot"]))
    all_digests = []
    chain = "0" * 64
    for capture in ordered:
        slot = capture["slot"]
        stamp = _utc(capture["captured_at_utc"])
        if stamp is None or stamp > now:
            return _refused("INVALID_CLAIMED_CAPTURE_CLOCK")
        raw_documents = capture["document_receipts"]
        if (not isinstance(raw_documents, list)
                or len(raw_documents) > MAX_DOCUMENTS_PER_SLOT):
            return _refused("INVALID_OR_EXCESS_DOCUMENT_RECEIPTS")
        expected = {}
        for snapshot in capture["snapshots"]:
            for event in snapshot["events"]:
                key = (snapshot["source_id"], event["event_id"])
                if key in expected:
                    return _refused("DUPLICATE_EVENT_SOURCE_PAIR")
                expected[key] = (
                    event["source_url"], event["claimed_document_sha256"],
                    _utc(snapshot["observed_at_utc"]),
                    _utc(event["publisher_updated_at_utc"]),
                )
        if len(expected) != len(raw_documents):
            return _refused("DOCUMENT_RECEIPTS_DO_NOT_COVER_EVENTS")
        seen = set()
        total_bytes = 0
        for document in raw_documents:
            if not isinstance(document, Mapping) or set(document) != RECEIPT_FIELDS:
                return _refused("INVALID_DOCUMENT_RECEIPT_FIELDS")
            source, event_id = document["source_id"], document["event_id"]
            if not isinstance(source, str) or not isinstance(event_id, str):
                return _refused("INVALID_EVENT_SOURCE_IDENTIFIER")
            key = (source, event_id)
            if key in seen or key not in expected:
                return _refused("DUPLICATE_OR_UNEXPECTED_EVENT_DOCUMENT")
            seen.add(key)
            url, declared_digest, snapshot_observed, claimed_published = expected[key]
            received = _utc(document["received_at_utc"])
            body = document["body"]
            if (document["effective_url"] != url
                    or received is None or snapshot_observed is None
                    or claimed_published is None or received < claimed_published
                    or received > snapshot_observed or received > stamp
                    or snapshot_observed - received > MAX_RECEIPT_LAG
                    or not isinstance(body, bytes)
                    or not 1 <= len(body) <= MAX_DOCUMENT_BYTES):
                return _refused("MISSING_BYTES_URL_OR_CLOCK_INCONSISTENT")
            total_bytes += len(body)
            if total_bytes > MAX_SLOT_BYTES:
                return _refused("EXCESS_SOURCE_BYTES_IN_ONE_SLOT")
            digest = sha256(body).hexdigest()
            if digest != declared_digest:
                return _refused("CALLER_DOCUMENT_DIGEST_MISMATCH")
            all_digests.append({
                "slot": slot, "source_id": source, "event_id": event_id,
                "effective_url": url, "claimed_received_at_utc": received.isoformat(),
                "body_sha256": digest, "body_byte_count": len(body),
                "origin_verified": False, "receipt_time_verified": False,
            })
        # Include empty captured slots as well as document records; this
        # locally calculated chain is *not* an independently witnessed log.
        slot_items = sorted((item for item in all_digests if item["slot"] == slot),
                            key=lambda item: (item["source_id"], item["event_id"]))
        chain_material = json.dumps({
            "prior": chain, "slot": slot, "claimed_capture_at_utc": stamp.isoformat(),
            "documents": slot_items,
        }, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        chain = sha256(chain_material.encode("utf-8")).hexdigest()

    report = _refused("CONTENT_HASH_MATCH_IS_NOT_PUBLISHER_AUTHENTICATION")
    report.update({
        "state": "LAB_DOCUMENT_BYTES_CONSISTENT_UNATTESTED",
        "as_of_utc": now.isoformat(),
        "calendar_review": calendar,
        "checked_document_receipts": all_digests,
        "checked_document_count": len(all_digests),
        "local_chain_head_sha256": chain,
        "supplied_bytes_match_declared_digest": True,
        "note": ("SHA-256 coincide apenas com bytes informados pelo chamador. "
                 "Sem autenticacao TLS independente, prova de publicacao "
                 "original, testemunha externa, coleta ativa ou vies real."),
    })
    return report


__all__ = ["SCHEMA", "audit_three_daily_calendar_document_bytes_lab"]
