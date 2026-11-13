"""BoC Valet V39079 official-policy raw JSON receipt and as-of validator (LAB).

V39079 is the *target for the overnight rate* observed on business days,
not the Bank Rate, CORRA, prime, interest-rate differential or a surprise.

Only a separate manual HTTPS collector may fetch the exact public URL.
This pure gate verifies the original response bytes, format, unique
observations, clock chronology and content digest. Its input timestamps
remain caller/local-machine claims: it cannot prove an issuer's first
publication vintage or that archived bytes existed before any old decision.
No forex direction/probability, broker, trades, orders or alerts.
"""
from __future__ import annotations

from datetime import date, datetime, timezone, timedelta
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import json
import re
from typing import Any

SCHEMA = "ATLASQUANT_CAD_BOC_V39079_OFFICIAL_VAL_RECEIPT_LAB_V1"
URL = "https://www.bankofcanada.ca/valet/observations/V39079/json?recent=5"
SERIES = "V39079"
CONTENT_TYPE = "application/json"
MAX_BYTES = 48_000
RATE = re.compile(r"-?(?:0|[1-9]\d{0,2})(?:\.\d{1,4})?\Z")
DAY = re.compile(r"20\d\d-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12]\d|3[01])\Z")
HASH = re.compile(r"[0-9a-f]{64}\Z")
REQUIRED_RECEIPT_KEYS = frozenset((
    "source_url", "final_url", "http_status", "content_type",
    "body_sha256", "started_at_utc", "finished_at_utc",
    "https_validation_claim", "redirects_followed",
))


def _base(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "state": "LAB_CAD_BOC_RAW_CAPTURE_BLOCKED",
        "reason": reason,
        "currency": "CAD",
        "measure": "BOC_OVERNIGHT_RATE_TARGET",
        "api_series": SERIES,
        "issuer_url": URL,
        "source_bytes_sha256_verified_locally": False,
        "receipt_transport_claim_consistent": False,
        "series_meaning_and_unit_consistent": False,
        "observed_business_day_rows": 0,
        "latest_observation_date_claim": None,
        "latest_target_rate_pct_claim": None,
        "source_captured_at_utc_claim": None,
        "series_values_authenticated_by_issuer_at_release": False,
        "original_source_first_seen_independently_verified": False,
        "historical_point_in_time_vintage_verified": False,
        "issuer_policy_decision_timestamp_verified": False,
        "all_eight_currencies_ready": False,
        "macro_bilateral_completeness": False,
        "relative_strength_or_carry_signal": None,
        "validated_accuracy": None,
        "calibrated_probability": None,
        "operational_bias": "AGUARDAR",
        "trade_authorized": False, "publishable": False,
        "live_alert_allowed": False, "worker_enabled": False,
        "scheduler_enabled": False, "http_requests": 0,
        "files_written": 0, "new_cost_brl": 0,
        "research_only": True,
    }


def _clock(value: Any) -> datetime | None:
    if not isinstance(value, datetime) or value.tzinfo is None:
        return None
    try:
        if value.utcoffset() is None:
            return None
        return value.astimezone(timezone.utc)
    except (ValueError, TypeError, OverflowError):
        return None


def _time(raw: Any) -> datetime | None:
    if type(raw) is not str or len(raw) != 20 or not raw.endswith("Z"):
        return None
    try:
        t = datetime.strptime(raw, "%Y-%m-%dT%H:%M:%SZ")
        return t.replace(tzinfo=timezone.utc) if t.year >= 2020 else None
    except ValueError:
        return None


def _amount(raw: Any) -> Decimal | None:
    if type(raw) is not str or RATE.fullmatch(raw) is None:
        return None
    try:
        value = Decimal(raw)
        return value if value.is_finite() and Decimal("-25") <= value <= Decimal("100") else None
    except InvalidOperation:
        return None


def _no_duplicate_fields(items: list[tuple[str, Any]]) -> dict[str, Any]:
    result = {}
    for key, value in items:
        if key in result:
            raise ValueError("duplicate JSON field")
        result[key] = value
    return result


def inspect_boc_valet_policy_receipt_lab(
    *, original_body: Any, receipt: Any, decision_at_utc: Any,
) -> dict[str, Any]:
    """Inspect supplied original bytes; no independent provenance attestation."""
    out = _base("INVALID_RECEIPT_BODY_OR_DECISION_CLOCK")
    decision = _clock(decision_at_utc)
    if (type(original_body) is not bytes or not 40 <= len(original_body) <= MAX_BYTES
            or type(receipt) is not dict or set(receipt) != REQUIRED_RECEIPT_KEYS
            or decision is None or decision.microsecond):
        return out

    if (receipt["source_url"] != URL or receipt["final_url"] != URL
            or type(receipt["http_status"]) is not int
            or receipt["http_status"] != 200
            or type(receipt["content_type"]) is not str
            or receipt["content_type"].split(";")[0].strip().lower() != CONTENT_TYPE
            or receipt["redirects_followed"] is not False
            or receipt["https_validation_claim"] is not True
            or type(receipt["body_sha256"]) is not str
            or HASH.fullmatch(receipt["body_sha256"]) is None):
        out["reason"] = "NONOFFICIAL_URL_UNSAFE_TRANSPORT_OR_NON_JSON_RESPONSE"
        return out
    observed_start = _time(receipt["started_at_utc"])
    observed_end = _time(receipt["finished_at_utc"])
    if (observed_start is None or observed_end is None
            or not observed_start <= observed_end <= decision
            or observed_end - observed_start > timedelta(seconds=30)):
        out["reason"] = "CAPTURE_AFTER_DECISION_OR_INCONSISTENT_CLOCK"
        return out
    if sha256(original_body).hexdigest() != receipt["body_sha256"]:
        out["reason"] = "ORIGINAL_BODY_SHA256_MISMATCH"
        return out
    out["source_bytes_sha256_verified_locally"] = True
    out["receipt_transport_claim_consistent"] = True

    try:
        obj = json.loads(
            original_body.decode("utf-8-sig"),
            object_pairs_hook=_no_duplicate_fields,
            parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite")),
        )
    except (UnicodeError, ValueError, TypeError, RecursionError):
        out["reason"] = "BOC_RAW_JSON_DECODING_INVALID"
        return out
    if type(obj) is not dict or not {"seriesDetail", "observations"} <= set(obj):
        out["reason"] = "BOC_JSON_SERIES_OR_OBSERVATIONS_MISSING"
        return out

    detail = obj["seriesDetail"]
    obs = obj["observations"]
    if (type(detail) is not dict or set(detail) != {SERIES}
            or type(detail[SERIES]) is not dict
            or type(obs) is not list or not 1 <= len(obs) <= 5):
        out["reason"] = "UNEXPECTED_BOC_SERIES_OR_OBSERVATION_COUNT"
        return out

    meta = detail[SERIES]
    dimension = meta.get("dimension", {})
    unit = meta.get("metadata", {})
    if (meta.get("label") != "Target for the overnight rate (business daily)"
            or meta.get("dateFormat") != "daily"
            or type(dimension) is not dict or dimension.get("key") != "d"
            or type(unit) is not dict or unit.get("unit") != "Percent"
            or unit.get("frequency") != "Business daily"):
        out["reason"] = "BOC_V39079_INSTRUMENT_OR_UNIT_MISMATCH"
        return out

    dates = set()
    numeric = []
    for row in obs:
        if (type(row) is not dict or set(row) != {"d", SERIES}
                or type(row["d"]) is not str or DAY.fullmatch(row["d"]) is None
                or type(row[SERIES]) is not dict or set(row[SERIES]) != {"v"}):
            out["reason"] = "BOC_DAILY_OBSERVATION_SCHEMA_INVALID"
            return out
        try:
            date_seen = date.fromisoformat(row["d"])
        except ValueError:
            out["reason"] = "BOC_OBSERVATION_DATE_INVALID"
            return out
        value = _amount(row[SERIES]["v"])
        if (date_seen in dates or date_seen > observed_end.date()
                or value is None):
            out["reason"] = "BOC_OBSERVATION_DUPLICATE_FUTURE_OR_VALUE_INVALID"
            return out
        dates.add(date_seen)
        numeric.append((date_seen, value))

    latest_date, latest_val = max(numeric, key=lambda item: item[0])
    out.update({
        "state": "LAB_CAD_BOC_ORIGINAL_BYTES_LOCALLY_CHECKED_NO_GO",
        "reason": "OFFICIAL_API_BYTES_MATCH_LOCAL_RECEIPT_NOT_ISSUER_FIRST_RELEASE_ATTESTATION",
        "series_meaning_and_unit_consistent": True,
        "observed_business_day_rows": len(obs),
        "latest_observation_date_claim": latest_date.isoformat(),
        "latest_target_rate_pct_claim": str(latest_val),
        "source_captured_at_utc_claim": observed_end.isoformat(),
    })
    return out


__all__ = ("SCHEMA", "URL", "SERIES", "MAX_BYTES",
           "inspect_boc_valet_policy_receipt_lab")
