"""Bind claimed BLS API bytes to an as-of cutoff, without PIT attestation.

A self-consistent hash and caller-provided capture time only establish
local observation metadata. They cannot prove a publisher's original
release, independent timestamp, historical revision or tradable edge.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
import re
from typing import Any

from atlasquant_trader_us_bls_cpi_yoy_snapshot_lab import (
    MAX_RESPONSE_BYTES, SOURCE_URL_CLAIM,
    interpret_bls_cpi_u_snapshot_lab,
)

SCHEMA = "ATLASQUANT_TRADER_US_BLS_API_SNAPSHOT_ASOF_LAB_V1"
RECEIPT_SCHEMA = "ATLASQUANT_TRADER_US_BLS_CURRENT_API_RECEIPT_LAB_V1"
_UTC = re.compile(r"20\d\d-\d\d-\d\dT\d\d:\d\d:\d\dZ\Z")
_HEX = re.compile(r"[0-9a-f]{64}\Z")
_RECEIPT_FIELDS = frozenset((
    "schema", "source_url_claim", "method_claim", "http_status_claim",
    "content_type_claim", "redirects_followed_claim",
    "body_bytes", "body_sha256", "local_started_utc_claim",
    "local_finished_utc_claim", "caller_supplied_unattested",
    "original_issuer_release_authenticated",
    "collector_clock_independently_authenticated",
))


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_BLS_ASOF_BLOCKED", "reason": reason,
        "reference_period": None, "decision_at_utc": None,
        "capture_finished_utc_claim": None, "body_sha256": None,
        "derived_yoy_percent": None, "local_body_hash_self_consistent": False,
        "source_origin_independently_authenticated": False,
        "publisher_first_release_authenticated": False,
        "collector_clock_independently_authenticated": False,
        "historical_point_in_time_eligible": False,
        "eligible_to_feed_macro_bias": False,
        "revisions_independently_audited": False,
        "derived_value_is_official_published_yoy": False,
        "operational_bias": "AGUARDAR", "trade_authorized": False,
        "publishable": False, "scheduler_enabled": False,
        "worker_enabled": False, "http_requests": 0,
        "file_writes": 0, "new_cost_brl": 0,
    }


def _time(s: Any) -> datetime | None:
    if not isinstance(s, str) or _UTC.fullmatch(s) is None:
        return None
    try:
        return datetime.fromisoformat(s[:-1] + "+00:00")
    except ValueError:
        return None


def _cutoff(value: Any) -> datetime | None:
    if (not isinstance(value, datetime) or value.tzinfo is None
            or value.utcoffset() is None or value.microsecond != 0):
        return None
    return value.astimezone(timezone.utc)


def inspect_bls_cpi_claimed_snapshot_asof_lab(
    raw_response: Any, receipt: Any, *, reference_period: str,
    decision_at_utc: datetime, evaluated_at_utc: datetime,
) -> dict[str, Any]:
    """Refuse any response whose *claimed capture* ends after decision time.

    Caller can forge the receipt and the clock; successful result is an
    arithmetic demonstration, NEVER real historical-PIT certification.
    """
    out = _blocked("INVALID_RECEIPT_BYTES_OR_CLOCK")
    decision, evaluation = _cutoff(decision_at_utc), _cutoff(evaluated_at_utc)
    if (decision is None or evaluation is None or decision > evaluation
            or not isinstance(raw_response, bytes)
            or not 1 <= len(raw_response) <= MAX_RESPONSE_BYTES
            or not isinstance(receipt, dict) or receipt.keys() != _RECEIPT_FIELDS):
        return out
    if (receipt["schema"] != RECEIPT_SCHEMA
            or receipt["source_url_claim"] != SOURCE_URL_CLAIM
            or receipt["method_claim"] != "GET"
            or type(receipt["http_status_claim"]) is not int
            or receipt["http_status_claim"] != 200
            or receipt["content_type_claim"] != "application/json"
            or receipt["redirects_followed_claim"] is not False
            or type(receipt["body_bytes"]) is not int
            or receipt["body_bytes"] != len(raw_response)
            or not isinstance(receipt["body_sha256"], str)
            or _HEX.fullmatch(receipt["body_sha256"]) is None
            or receipt["body_sha256"] != sha256(raw_response).hexdigest()
            or receipt["caller_supplied_unattested"] is not True
            or receipt["original_issuer_release_authenticated"] is not False
            or receipt["collector_clock_independently_authenticated"] is not False):
        return out
    started = _time(receipt["local_started_utc_claim"])
    finished = _time(receipt["local_finished_utc_claim"])
    if (started is None or finished is None or started > finished
            or finished - started > timedelta(seconds=120)):
        return out
    if finished > decision:
        out.update({
            "state": "LAB_BLS_CAPTURE_NOT_VISIBLE_AT_DECISION",
            "reason": "CLAIMED_CAPTURE_FINISHED_AFTER_DECISION_NO_LOOKAHEAD",
            "decision_at_utc": decision.isoformat(),
        })
        return out
    parsed = interpret_bls_cpi_u_snapshot_lab(
        raw_response, reference_period=reference_period)
    if parsed["state"] != "LAB_BLS_CPI_U_DERIVED_YOY_FROM_MUTABLE_API_BYTES_UNATTESTED":
        out["reason"] = "BLS_INDEX_RESPONSE_INVALID_OR_TARGET_MONTH_UNAVAILABLE"
        return out
    out.update({
        "state": "LAB_BLS_CAPTURE_SELF_CONSISTENT_AND_NONFUTURE_UNATTESTED",
        "reason": "CLAIMED_CAPTURE_BEFORE_CUTOFF_NOT_AUTHENTICATED_PUBLISHER_VINTAGE",
        "reference_period": reference_period,
        "decision_at_utc": decision.isoformat(),
        "capture_finished_utc_claim": receipt["local_finished_utc_claim"],
        "body_sha256": receipt["body_sha256"],
        "local_body_hash_self_consistent": True,
        "derived_yoy_percent": parsed["derived_yoy_percent"],
    })
    return out


__all__ = ["SCHEMA", "RECEIPT_SCHEMA", "inspect_bls_cpi_claimed_snapshot_asof_lab"]
