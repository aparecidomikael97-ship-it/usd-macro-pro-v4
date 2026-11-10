"""Bind a G8 CPI macro source-hash *claim* to local, caller-supplied bytes.

This is deliberately NOT an HTTP client, issuer authentication, first-release
archive or economic value extractor. It cannot authorize a bias or a trade.
"""
from __future__ import annotations

import base64
import binascii
from datetime import datetime, timezone
from hashlib import sha256
import json
import re
from typing import Any

from atlasquant_trader_g8_macro_asof_lab import (
    CPI_FREQUENCY_2026_LAB,
    RECORD_FIELDS_WITH_STAGE_AND_URL,
    _cpi_issuer_claim_host,
    _observation_period,
    _value,
)

SCHEMA = "ATLASQUANT_TRADER_G8_CPI_LOCAL_BYTE_BINDING_LAB_V1"
MAX_BODY_BYTES = 1024 * 1024
_UTC = re.compile(r"20\d\d-\d\d-\d\dT\d\d:\d\d:\d\dZ\Z")
_HEX = re.compile(r"[0-9a-f]{64}\Z")
CAPTURE_FIELDS = frozenset((
    "schema", "currency", "indicator", "observation_period",
    "publication_stage", "source_url", "captured_at_utc",
    "content_type_claim", "http_status_claim", "body_base64",
    "body_sha256", "receipt_sha256", "caller_supplied_unattested",
))


def _time(value: Any) -> datetime | None:
    if not isinstance(value, str) or _UTC.fullmatch(value) is None:
        return None
    try:
        return datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError:
        return None


def _instant(value: Any) -> datetime | None:
    if (not isinstance(value, datetime) or value.tzinfo is None
            or value.utcoffset() is None or value.microsecond != 0):
        return None
    return value.astimezone(timezone.utc)


def _digest_without_receipt(data: dict[str, Any]) -> str:
    return sha256(json.dumps(data, sort_keys=True, ensure_ascii=True,
                             separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_CPI_LOCAL_BINDING_BLOCKED",
        "reason": reason, "currency": None, "observation_period": None,
        "publication_stage_claim": None, "body_sha256_local": None,
        "body_size": 0, "local_byte_hash_matches_macro_claim": False,
        "local_receipt_self_consistent": False,
        "issuer_host_claim_checked": False,
        "issuer_tls_connection_verified": False,
        "original_issuer_bytes_authenticated": False,
        "first_publication_time_independently_attested": False,
        "capture_clock_independently_attested": False,
        "cpi_value_extracted_and_verified_from_body": False,
        "historical_point_in_time_eligible": False,
        "can_feed_macro_bias": False, "validated_accuracy": None,
        "operational_bias": "AGUARDAR", "publishable": False,
        "trade_authorized": False, "worker_enabled": False,
        "scheduler_enabled": False, "network_requests": 0,
        "file_writes": 0, "new_cost_brl": 0,
    }


def build_local_g8_cpi_capture_receipt_lab(
    currency: Any, observation_period: Any, publication_stage: Any,
    source_url: Any, body: Any, *, captured_at_utc: Any,
    content_type_claim: Any = "text/html",
) -> dict[str, Any]:
    """Package supplied bytes without downloading or persisting documents."""
    if (not isinstance(currency, str) or currency not in CPI_FREQUENCY_2026_LAB
            or not isinstance(observation_period, str)
            or publication_stage not in ("FLASH", "FINAL")
            or _cpi_issuer_claim_host(currency, source_url) is None
            or not isinstance(body, bytes) or not 1 <= len(body) <= MAX_BODY_BYTES
            or _time(captured_at_utc) is None
            or content_type_claim not in ("text/html", "application/pdf")):
        return _blocked("CAPTURE_SOURCE_BYTES_OR_METADATA_INVALID")
    record = {
        "schema": SCHEMA, "currency": currency, "indicator": "CPI_YOY",
        "observation_period": observation_period,
        "publication_stage": publication_stage,
        "source_url": source_url, "captured_at_utc": captured_at_utc,
        "content_type_claim": content_type_claim, "http_status_claim": 200,
        "body_base64": base64.b64encode(body).decode("ascii"),
        "body_sha256": sha256(body).hexdigest(),
        "caller_supplied_unattested": True,
    }
    record["receipt_sha256"] = _digest_without_receipt(record)
    return record


def inspect_local_g8_cpi_capture_binding_lab(
    macro_row: Any, capture: Any, *, decision_at_utc: Any,
    evaluated_at_utc: Any,
) -> dict[str, Any]:
    """Require an exact local byte-hash match and safe claimed chronology.

    A self-consistent hash can be forged. Even PASS does not authenticate the
    publisher, independently timestamp retrieval or read a CPI from the body.
    """
    out = _blocked("MACRO_OR_CAPTURE_SCHEMA_INVALID")
    decision, now = _instant(decision_at_utc), _instant(evaluated_at_utc)
    if (not isinstance(macro_row, dict)
            or frozenset(macro_row) != RECORD_FIELDS_WITH_STAGE_AND_URL
            or not isinstance(capture, dict) or frozenset(capture) != CAPTURE_FIELDS
            or decision is None or now is None or decision > now):
        return out
    currency, period, stage = (macro_row["currency"],
                               macro_row["observation_period"],
                               macro_row["publication_stage"])
    if (not isinstance(currency, str) or currency not in CPI_FREQUENCY_2026_LAB
            or macro_row["indicator"] != "CPI_YOY"
            or macro_row["source_type"] != "OFFICIAL_STATISTICS_OFFICE"
            or not isinstance(period, str) or stage not in ("FLASH", "FINAL")
            or _cpi_issuer_claim_host(currency, macro_row["source_url"]) is None
            or _value(macro_row["value"]) is None
            or not isinstance(macro_row["source_sha256"], str)
            or _HEX.fullmatch(macro_row["source_sha256"]) is None):
        return out
    published = _time(macro_row["published_at_utc"])
    captured = _time(macro_row["captured_at_utc"])
    period_info = (_observation_period(period, indicator="CPI_YOY",
                                       published=published, stage=stage)
                   if published is not None else None)
    if (published is None or captured is None or period_info is None
            or period_info[0] != CPI_FREQUENCY_2026_LAB[currency]
            or not published <= captured <= decision):
        out["reason"] = "CPI_PERIOD_OR_DECISION_CHRONOLOGY_INVALID"
        return out
    if (capture["schema"] != SCHEMA or capture["currency"] != currency
            or capture["indicator"] != "CPI_YOY"
            or capture["observation_period"] != period
            or capture["publication_stage"] != stage
            or capture["source_url"] != macro_row["source_url"]
            or capture["captured_at_utc"] != macro_row["captured_at_utc"]
            or capture["content_type_claim"] not in ("text/html", "application/pdf")
            or type(capture["http_status_claim"]) is not int
            or capture["http_status_claim"] != 200
            or capture["caller_supplied_unattested"] is not True):
        out["reason"] = "CAPTURE_METADATA_DOES_NOT_BIND_TO_MACRO_ROW"
        return out
    raw64, body_hash, receipt_hash = (capture["body_base64"],
                                     capture["body_sha256"], capture["receipt_sha256"])
    if (not isinstance(raw64, str) or len(raw64) > (MAX_BODY_BYTES * 4 // 3 + 8)
            or not isinstance(body_hash, str) or _HEX.fullmatch(body_hash) is None
            or not isinstance(receipt_hash, str) or _HEX.fullmatch(receipt_hash) is None):
        out["reason"] = "CAPTURE_BYTE_HASH_ENCODING_INVALID"
        return out
    try:
        body = base64.b64decode(raw64, validate=True)
    except (binascii.Error, ValueError):
        out["reason"] = "CAPTURE_BYTE_HASH_ENCODING_INVALID"
        return out
    if (not 1 <= len(body) <= MAX_BODY_BYTES
            or base64.b64encode(body).decode("ascii") != raw64
            or sha256(body).hexdigest() != body_hash
            or _digest_without_receipt({k: v for k, v in capture.items()
                                       if k != "receipt_sha256"}) != receipt_hash):
        out["reason"] = "CAPTURE_SELF_HASH_INVALID"
        return out
    if body_hash != macro_row["source_sha256"]:
        out["reason"] = "CPI_MACRO_SOURCE_HASH_NOT_BOUND_TO_CAPTURE_BYTES"
        return out
    out.update({
        "state": "LAB_CPI_LOCAL_BYTE_HASH_BOUND_UNATTESTED",
        "reason": "CALLER_BYTES_MATCH_HASH_BUT_NOT_PROVEN_ORIGINAL_ISSUER_RELEASE",
        "currency": currency, "observation_period": period,
        "publication_stage_claim": stage, "body_sha256_local": body_hash,
        "body_size": len(body), "local_byte_hash_matches_macro_claim": True,
        "local_receipt_self_consistent": True, "issuer_host_claim_checked": True,
    })
    return out


__all__ = ["SCHEMA", "MAX_BODY_BYTES", "CAPTURE_FIELDS",
           "build_local_g8_cpi_capture_receipt_lab",
           "inspect_local_g8_cpi_capture_binding_lab"]
