"""Offline inspection of a *SUPPLIED* small Eurostat FPD JSON-stat envelope.

No HTTP. The supplied URL, headers and JSON bytes can be fabricated by the
caller; structural validation is NOT provenance, release-time witnessing,
first-publication proof, inflation comparability or currency direction.
Numerical observations are intentionally NOT returned to the caller.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
from math import isfinite
from typing import Any
from urllib.parse import parse_qsl, urlsplit

from atlasquant_trader_eurostat_fpd_ea21_metadata_gate_lab import (
    inspect_eurostat_fpd_ea21_metadata_gate_lab,
)

SCHEMA = "ATLASQUANT_TRADER_EUROSTAT_FPD_EA21_SUPPLIED_PAYLOAD_ENVELOPE_LAB_V1"
MAX_BYTES = 64 * 1024
EXPECTED_DIMENSIONS = ("freq", "unit", "coicop", "release", "geo", "time")
EXPECTED_QUERY_KEYS = frozenset((
    "format", "lang", "freq", "unit", "coicop", "release", "geo", "time",
))
EXPECTED_HOST = "ec.europa.eu"
EXPECTED_PATH = "/eurostat/api/dissemination/statistics/1.0/data/prc_hicp_fpd"


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_BLOCKED", "reason": reason,
        "submitted_payload_sha256": None, "submitted_payload_byte_count": 0,
        "submitted_jsonstat_dataset_id": None,
        "declared_dimension_ids": [], "declared_unit_code_unverified": None,
        "declared_release_code_unverified": None,
        "submitted_dataset_updated_at_utc": None,
        "submitted_capture_clock_utc": None,
        "jsonstat_structure_checked": False,
        "official_http_response_independently_witnessed": False,
        "tls_server_identity_independently_attested": False,
        "historical_initial_release_bytes_attested": False,
        "source_available_at_prior_market_timestamp_verified": False,
        "source_response_codes_confirmed_against_live_metadata": False,
        "numeric_inflation_value_returned": False,
        "euro_area_in_2026": "EA21",
        "oct2026_full_cpi_inferred": False,
        "jan2026_fpd_immutable_verified": False,
        "validated_prediction_count": 0, "validated_accuracy": None,
        "fx_bias": None, "operational_bias": "AGUARDAR",
        "can_feed_live_radar": False, "trade_authorized": False,
        "publishable": False, "worker_enabled": False,
        "scheduler_enabled": False, "http_requests": 0, "new_cost_brl": 0,
    }


def _unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in pairs:
        if k in out:
            raise ValueError("duplicate JSON key")
        out[k] = v
    return out


def _utc(value: Any) -> datetime | None:
    if (not isinstance(value, datetime) or value.tzinfo is None
            or value.utcoffset() is None):
        return None
    return value.astimezone(timezone.utc)


def _url_fields(value: Any) -> dict[str, str] | None:
    if not isinstance(value, str) or len(value) > 1200:
        return None
    try:
        p = urlsplit(value)
        if (p.scheme != "https" or p.hostname != EXPECTED_HOST
                or p.username is not None or p.password is not None
                or p.port is not None or p.path != EXPECTED_PATH
                or p.fragment or not p.query):
            return None
        pairs = parse_qsl(p.query, keep_blank_values=True, strict_parsing=True)
        if (len(pairs) != len(EXPECTED_QUERY_KEYS)
                or {k for k, _ in pairs} != EXPECTED_QUERY_KEYS):
            return None
        q = dict(pairs)
        if (q["format"] != "JSON" or q["lang"] != "EN"
                or q["freq"] != "M" or q["geo"] != "EA21"
                or q["time"] != "2026-09"
                or not all(q[k] and len(q[k]) <= 32
                           for k in ("unit", "coicop", "release"))):
            return None
        return q
    except (TypeError, ValueError):
        return None


def inspect_supplied_eurostat_fpd_ea21_payload_envelope_lab(
    raw: Any, *, request_url_claim: Any,
    observed_at_utc: Any, as_of_utc: Any,
    metadata_casebook_raw: Any, eurusd_casebook_raw: Any,
) -> dict[str, Any]:
    """Validate one synthetic or manually supplied 2026-09 JSON-stat cell."""
    out = _blocked("INVALID_SUPPLIED_JSONSTAT_OR_ASOF_OR_SOURCE_CONTEXT")
    observed, now = _utc(observed_at_utc), _utc(as_of_utc)
    q = _url_fields(request_url_claim)
    if (observed is None or now is None or observed > now
            or not isinstance(raw, bytes) or not 100 <= len(raw) <= MAX_BYTES
            or q is None):
        return out
    metadata = inspect_eurostat_fpd_ea21_metadata_gate_lab(
        metadata_casebook_raw,
        eurusd_casebook_raw=eurusd_casebook_raw,
        as_of_utc=now,
    )
    if (metadata["state"] != "LAB_EUROSTAT_EA21_FPD_METADATA_ONLY_NOT_API_PAYLOAD"
            or not metadata["sep2026_full_dataset_metadata_reference_visible_asof"]):
        return out
    try:
        obj = json.loads(
            raw.decode("utf-8", "strict"), object_pairs_hook=_unique,
            parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite")),
        )
        dims = obj["dimension"]
        ids = obj["id"]
        size = obj["size"]
        if (obj["class"] != "dataset" or obj["version"] != "2.0"
                or obj["source"] != "ESTAT"
                or not isinstance(ids, list) or len(ids) != len(EXPECTED_DIMENSIONS)
                or set(ids) != set(EXPECTED_DIMENSIONS)
                or not isinstance(size, list) or len(size) != len(ids)
                or any(type(n) is not int or n != 1 for n in size)
                or not isinstance(dims, dict) or set(dims) != set(ids)):
            return out
        for code in ids:
            index = dims[code]["category"]["index"]
            if (not isinstance(index, dict) or set(index) != {q[code]}
                    or type(index[q[code]]) is not int or index[q[code]] != 0):
                return out
        values = obj["value"]
        if (not isinstance(values, dict) or set(values) != {"0"}
                or type(values["0"]) not in (float, int)
                or not isfinite(values["0"])):
            return out
        flags = obj.get("status", {})
        if not isinstance(flags, dict) or set(flags).difference({"0"}):
            return out
        update = datetime.fromisoformat(obj["updated"].replace("Z", "+00:00"))
        if (update.tzinfo is None or update.utcoffset() is None
                or update.astimezone(timezone.utc) > observed):
            return out
    except (UnicodeDecodeError, ValueError, TypeError, KeyError, AttributeError,
            OverflowError, RecursionError):
        return out
    out.update({
        "state": "LAB_SUPPLIED_JSONSTAT_ENVELOPE_QUARANTINED_NOT_SOURCE_ATTESTED",
        "reason": "CALLER_SUPPLIED_BYTES_AND_URL_NOT_AN_AUTHENTICATED_ORIGINAL_HTTP_RECEIPT",
        "submitted_payload_sha256": sha256(raw).hexdigest(),
        "submitted_payload_byte_count": len(raw),
        "submitted_jsonstat_dataset_id": "prc_hicp_fpd",
        "declared_dimension_ids": ids,
        "declared_unit_code_unverified": q["unit"],
        "declared_release_code_unverified": q["release"],
        "submitted_dataset_updated_at_utc": update.astimezone(timezone.utc).isoformat(),
        "submitted_capture_clock_utc": observed.isoformat(),
        "jsonstat_structure_checked": True,
    })
    return out


__all__ = ["SCHEMA", "MAX_BYTES", "EXPECTED_PATH",
           "inspect_supplied_eurostat_fpd_ea21_payload_envelope_lab"]
