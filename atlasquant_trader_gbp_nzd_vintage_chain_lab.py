"""Offline capture-version chain for the four pinned GBP/NZD publisher pages.

The bytes, HTTP details and capture clock are provided by the caller. SHA-256
and a hash chain detect *internal* inconsistencies; they do not authenticate a
publisher, seal the chain externally or prove when the bytes were accessible.
No network access, parsing economic values, disk writes, biases or orders.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
import re
from typing import Any

from atlasquant_trader_gbp_nzd_official_pilot_lab import PILOT

SCHEMA = "ATLASQUANT_TRADER_GBP_NZD_VINTAGE_CHAIN_LAB_V1"
MAX_CAPTURES = 32
MAX_RAW_BYTES = 1024 * 1024
MAX_TOTAL_BYTES = 4 * 1024 * 1024
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
UTC_SECOND = re.compile(r"20\d\d-\d\d-\d\dT\d\d:\d\d:\d\dZ\Z")
VINTAGE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,79}\Z")
FIELDS = frozenset((
    "document_id", "vintage_id", "source_url", "claimed_capture_at_utc",
    "claimed_http_status", "claimed_content_type", "raw_bytes", "claimed_sha256",
    "previous_receipt_sha256",
))
MIME_TYPES = frozenset(("text/html", "text/csv", "application/pdf", "application/json"))
GENESIS = "0" * 64


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_BLOCKED", "reason": reason,
        "records_checked": 0, "chain_tip_sha256": None, "candidates": {},
        "claimed_time_source": "CALLER_NOT_TRUSTED_CLOCK",
        "bytes_internal_hash_verified": False,
        "independent_http_response_attested": False,
        "publisher_tls_origin_verified": False,
        "externally_anchored_append_only_history": False,
        "original_historical_capture_attested": False,
        "point_in_time_backtest_approved": False,
        "forecast_probability": None, "operational_bias": "AGUARDAR",
        "trade_authorized": False, "worker_enabled": False,
        "scheduler_enabled": False, "new_cost_brl": 0,
    }


def _clock(raw: Any) -> datetime | None:
    if not isinstance(raw, str) or UTC_SECOND.fullmatch(raw) is None:
        return None
    try:
        return datetime.fromisoformat(raw[:-1] + "+00:00")
    except ValueError:
        return None


def _evaluation_clock(raw: Any) -> datetime | None:
    if (not isinstance(raw, datetime) or raw.tzinfo is None
            or raw.utcoffset() is None or raw.microsecond != 0):
        return None
    return raw.astimezone(timezone.utc)


def inspect_gbp_nzd_vintage_chain_lab(
    snapshots: Any, *, decision_at_utc: datetime, evaluated_at_utc: datetime,
) -> dict[str, Any]:
    """Audit a caller-supplied, sequential, hash-linked list of raw snapshots.

    Return only the *last claimed captured version* by the decision cutoff.
    A source document's publication date never substitutes for the time when
    that version was captured. Even successful inspection remains NO-GO.
    """
    out = _blocked("INVALID_CLOCK_OR_SNAPSHOT_COLLECTION")
    decision, evaluated = (_evaluation_clock(decision_at_utc),
                           _evaluation_clock(evaluated_at_utc))
    if (decision is None or evaluated is None or decision > evaluated
            or not isinstance(snapshots, list) or len(snapshots) > MAX_CAPTURES):
        return out

    latest: dict[str, dict[str, Any]] = {}
    previous_by_document: dict[str, str] = {}
    last_capture: dict[str, datetime] = {}
    seen_vintages: set[tuple[str, str]] = set()
    tip = GENESIS
    total = 0
    for snap in snapshots:
        if not isinstance(snap, dict) or set(snap) != FIELDS:
            out["reason"] = "UNEXPECTED_RECEIPT_FIELDS"
            return out
        document_id = snap["document_id"]
        if not isinstance(document_id, str) or document_id not in PILOT:
            out["reason"] = "UNKNOWN_PINNED_DOCUMENT"
            return out
        pinned = PILOT[document_id]
        if snap["source_url"] != pinned["document_url"]:
            out["reason"] = "SOURCE_URL_NOT_PINNED_TO_RELEASE"
            return out
        vintage = snap["vintage_id"]
        if (not isinstance(vintage, str) or VINTAGE.fullmatch(vintage) is None
                or (document_id, vintage) in seen_vintages):
            out["reason"] = "AMBIGUOUS_OR_UNSAFE_VINTAGE_ID"
            return out
        captured = _clock(snap["claimed_capture_at_utc"])
        publisher_floor = _clock(pinned["availability_floor_utc"])
        if (captured is None or captured < publisher_floor or captured > evaluated
                or (document_id in last_capture and captured <= last_capture[document_id])):
            out["reason"] = "CAPTURE_CLOCK_OUT_OF_ORDER_OR_PREPUBLICATION"
            return out
        if (type(snap["claimed_http_status"]) is not int
                or snap["claimed_http_status"] != 200
                or not isinstance(snap["claimed_content_type"], str)
                or snap["claimed_content_type"] not in MIME_TYPES):
            out["reason"] = "CALLER_HTTP_METADATA_INVALID"
            return out
        raw = snap["raw_bytes"]
        if (not isinstance(raw, bytes) or not 64 <= len(raw) <= MAX_RAW_BYTES):
            out["reason"] = "RAW_BYTES_MISSING_OR_TOO_LARGE"
            return out
        total += len(raw)
        if total > MAX_TOTAL_BYTES:
            out["reason"] = "TOTAL_PAYLOAD_LIMIT_EXCEEDED"
            return out
        content_sha = sha256(raw).hexdigest()
        if (not isinstance(snap["claimed_sha256"], str)
                or HEX64.fullmatch(snap["claimed_sha256"]) is None
                or snap["claimed_sha256"] != content_sha):
            out["reason"] = "PAYLOAD_SHA256_MISMATCH"
            return out
        previous = previous_by_document.get(document_id, GENESIS)
        if snap["previous_receipt_sha256"] != previous:
            out["reason"] = "PER_DOCUMENT_REVISION_CHAIN_MISMATCH"
            return out

        receipt_metadata = {
            "document_id": document_id, "vintage_id": vintage,
            "source_url": snap["source_url"],
            "claimed_capture_at_utc": snap["claimed_capture_at_utc"],
            "claimed_http_status": snap["claimed_http_status"],
            "claimed_content_type": snap["claimed_content_type"],
            "content_sha256": content_sha, "content_bytes": len(raw),
            "previous_receipt_sha256": previous,
            "global_previous_receipt_sha256": tip,
        }
        digest = sha256(json.dumps(receipt_metadata, sort_keys=True, separators=(",", ":"),
                                   ensure_ascii=True).encode("ascii")).hexdigest()
        tip = digest
        previous_by_document[document_id] = digest
        last_capture[document_id] = captured
        seen_vintages.add((document_id, vintage))
        if captured <= decision:
            latest[document_id] = {
                "vintage_id": vintage, "content_sha256": content_sha,
                "receipt_sha256": digest,
                "claimed_capture_at_utc": snap["claimed_capture_at_utc"],
                "capture_independently_attested": False,
                "economic_value_authenticated": False,
                "eligible_for_exante_backtest": False,
            }

    out.update({
        "state": "LAB_INTERNAL_VINTAGE_CHAIN_CONSISTENT_UNATTESTED",
        "reason": "CALLER_CAN_REWRITE_CLOCK_AND_CHAIN; NO_EXTERNAL_TIMESTAMP_ANCHOR",
        "records_checked": len(snapshots), "chain_tip_sha256": tip,
        "candidates": latest, "bytes_internal_hash_verified": True,
    })
    return out


__all__ = ["SCHEMA", "GENESIS", "FIELDS", "inspect_gbp_nzd_vintage_chain_lab"]
