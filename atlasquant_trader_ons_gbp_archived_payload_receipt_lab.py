"""Opaque-byte receipt guard for a separately captured ONS D7G7 archive.

No CSV interpretation or HTTP access. A caller-provided hash, URL and clock
cannot prove TLS origin, release time, or point-in-time market availability.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import re
from typing import Any

from atlasquant_trader_ons_gbp_archived_link_catalog_lab import (
    plan_ons_gbp_archived_source_leads_lab,
)

SCHEMA = "ATLASQUANT_TRADER_ONS_GBP_ARCHIVE_PAYLOAD_RECEIPT_LAB_V1"
MAX_ARCHIVE_BYTES = 2 * 1024 * 1024
_HEX64 = re.compile(r"[0-9a-f]{64}\Z")
_MIME_RE = re.compile(
    r"(?:application/octet-stream|text/csv|application/csv)"
    r"(?:;\s*charset=(?:utf-8|us-ascii))?\Z"
)


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "state": "LAB_BLOCKED",
        "reason": reason,
        "currency": "GBP",
        "series_id": "D7G7",
        "version_id": None,
        "source_raw_sha256": None,
        "source_bytes": None,
        "declared_observed_at_utc": None,
        "expected_source_url_allowlisted": False,
        "declared_response_status_checked": False,
        "declared_content_length_matched": False,
        "provided_sha256_matched": False,
        "reported_supersession_calendar_state": None,
        "payload_csv_structure_verified": False,
        "http_response_independently_observed": False,
        "external_sha256_independently_attested": False,
        "publisher_tls_origin_verified": False,
        "original_historical_snapshot_independently_verified": False,
        "release_instant_independently_verified": False,
        "point_in_time_historically_available_verified": False,
        "commercial_redistribution_rights_verified": False,
        "usable_for_backtest": False,
        "fx_bias": None,
        "operational_bias": "AGUARDAR",
        "trade_authorized": False,
        "can_feed_live_radar": False,
        "worker_enabled": False,
        "scheduler_enabled": False,
        "publishable": False,
        "external_http_requests": 0,
        "new_cost_brl": 0,
    }


def _utc(value: Any) -> datetime | None:
    if (not isinstance(value, datetime) or value.tzinfo is None
            or value.utcoffset() is None):
        return None
    return value.astimezone(timezone.utc)


def inspect_ons_gbp_archive_payload_receipt_lab(
    raw_payload: Any, *, version_id: Any, claimed_source_url: Any,
    claimed_http_status: Any, claimed_content_type: Any,
    claimed_content_length: Any, independently_recorded_sha256: Any,
    claimed_observed_at_utc: Any, historical_as_of_utc: Any,
    evaluated_at_utc: Any,
) -> dict[str, Any]:
    """Check a supplied byte receipt against a pinned archive link.

    The SHA is a matching *claim* supplied by the caller; this function does
    not know whether it was independently recorded before any modification.
    """
    out = _blocked("INVALID_BYTES_OR_CLOCKS")
    captured = _utc(claimed_observed_at_utc)
    cutoff = _utc(historical_as_of_utc)
    evaluated = _utc(evaluated_at_utc)
    if (not isinstance(raw_payload, bytes)
            or not 16 <= len(raw_payload) <= MAX_ARCHIVE_BYTES
            or captured is None or cutoff is None or evaluated is None
            or captured > evaluated or cutoff > evaluated):
        return out

    plan = plan_ons_gbp_archived_source_leads_lab(
        historical_as_of_utc=cutoff, evaluated_at_utc=evaluated,
        version_id=version_id,
    )
    if (plan["state"] != "LAB_ONS_PREVIOUS_LINK_LEADS_QUARANTINED"
            or plan["catalog_entries_count"] != 1):
        out["reason"] = "UNKNOWN_VERSION_ID"
        return out
    lead = plan["catalog_entries"][0]
    if (not isinstance(claimed_source_url, str)
            or claimed_source_url != lead["official_archive_download_url_candidate"]):
        out["reason"] = "SOURCE_URL_NOT_PINNED_OLD_ONS_VERSION"
        return out
    if type(claimed_http_status) is not int or claimed_http_status != 200:
        out["reason"] = "DECLARED_HTTP_STATUS_NOT_SUCCESS"
        return out
    if (not isinstance(claimed_content_type, str)
            or _MIME_RE.fullmatch(claimed_content_type.strip().lower()) is None):
        out["reason"] = "UNRECOGNIZED_CLAIMED_CONTENT_TYPE"
        return out
    if (type(claimed_content_length) is not int
            or claimed_content_length != len(raw_payload)):
        out["reason"] = "DECLARED_BYTE_COUNT_MISMATCH"
        return out
    digest = sha256(raw_payload).hexdigest()
    if (not isinstance(independently_recorded_sha256, str)
            or _HEX64.fullmatch(independently_recorded_sha256) is None
            or independently_recorded_sha256 != digest):
        out["reason"] = "PROVIDED_SHA256_MISMATCH_OR_INVALID"
        return out

    out.update({
        "state": "LAB_ONS_ARCHIVE_BYTES_INTERNALLY_MATCHED_QUARANTINED",
        "reason": "MATCHING_CALLER_RECEIPT_NOT_ORIGIN_OR_HISTORICAL_AVAILABILITY_PROOF",
        "version_id": version_id,
        "source_raw_sha256": digest,
        "source_bytes": len(raw_payload),
        "declared_observed_at_utc": captured.isoformat(),
        "expected_source_url_allowlisted": True,
        "declared_response_status_checked": True,
        "declared_content_length_matched": True,
        "provided_sha256_matched": True,
        "reported_supersession_calendar_state": lead[
            "status_relative_to_historical_cutoff"],
    })
    return out


__all__ = ["SCHEMA", "MAX_ARCHIVE_BYTES", "inspect_ons_gbp_archive_payload_receipt_lab"]
