"""Offline guard for a raw ECB EXR CSV response archived in the Trader LAB.

The archive is a single historical response. Hash consistency checks file
integrity after capture, NOT the ECB's identity, publication instant, vintage
or a witnessed point-in-time delivery. No HTTP, API key, scheduler or trading.
"""
from __future__ import annotations

import csv
import hashlib
import re
from datetime import date, datetime, time, timezone
from decimal import Decimal, InvalidOperation
from io import StringIO
from typing import Any, Mapping

from atlasquant_fx_universe import CURRENCIES

SCHEMA = "ATLASQUANT_TRADER_ECB_SDMX_RAW_ARCHIVE_LAB_V1"
STATE = "LAB_ECB_SDMX_BYTES_ARCHIVED_EXPOST_ONLY"
DENIED = "LAB_ECB_SDMX_ARCHIVE_REFUSED"
CODES = frozenset(CURRENCIES) - {"EUR"}
FIELDS = frozenset({
    "schema", "state", "source_url", "query_start", "query_end",
    "captured_at_utc", "http_date_utc", "http_last_modified_utc",
    "http_status", "content_type", "body_bytes", "body_sha256",
    "raw_path", "expected_dates",
})
NEEDED = frozenset({
    "KEY", "FREQ", "CURRENCY", "CURRENCY_DENOM", "EXR_TYPE",
    "EXR_SUFFIX", "TIME_PERIOD", "OBS_VALUE", "OBS_STATUS",
})
RAW_PATH = "docs/continuidade/ecb_exr_g8_20261026_20261102_raw.csv"
BASE = ("https://data-api.ecb.europa.eu/service/data/EXR/"
        "D.AUD+CAD+CHF+GBP+JPY+NZD+USD.EUR.SP00.A")


def expected_url(start: str, end: str) -> str:
    """An exact allowlisted public ECB endpoint; never accepts a caller host."""
    return f"{BASE}?startPeriod={start}&endPeriod={end}&format=csvdata"


def _deny(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": DENIED, "reason": reason,
        "reference_quotes_by_date": {}, "observation_dates": [],
        "original_rows": 0, "original_eur_series": 0,
        "algebraic_crosses_not_independent": 21,
        "independent_spot_quotes_verified": 0,
        "raw_bytes_sha256_matched": False,
        "source_origin_cryptographically_verified": False,
        "publication_time_independently_verified": False,
        "capture_time_independently_attested": False,
        "historical_vintage_attested": False,
        "real_currency_strength": None, "real_predictive_accuracy_proven": False,
        "can_feed_live_radar": False, "can_feed_real_oos": False,
        "trade_authorized": False, "worker_enabled": False,
        "scheduler_enabled": False,
    }


def _iso_date(value: Any) -> date | None:
    if not isinstance(value, str):
        return None
    try:
        result = date.fromisoformat(value)
    except ValueError:
        return None
    return result if result.isoformat() == value else None


def _utc(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.endswith("Z"):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.utcoffset() != timezone.utc.utcoffset(None):
        return None
    return parsed.astimezone(timezone.utc)


def validate_ecb_archived_csv_lab(
    raw: bytes, manifest: Any, *, evaluated_at: datetime,
) -> dict[str, Any]:
    """Validate archived bytes and complete daily EUR references, no live bias.

    All clocks and HTTP facts in the manifest are caller-provided statements.
    Passing this check proves internal archive consistency, not authenticity.
    """
    if not isinstance(evaluated_at, datetime) or evaluated_at.tzinfo is None:
        raise ValueError("Evaluation clock must have a timezone")
    if not isinstance(manifest, Mapping) or set(manifest) != FIELDS:
        return _deny("Manifest fields missing or unexpected")
    if manifest["schema"] != SCHEMA or manifest["state"] != STATE:
        return _deny("Archive identity does not match LAB contract")
    start, end = _iso_date(manifest["query_start"]), _iso_date(manifest["query_end"])
    if start is None or end is None or not start < end or (end-start).days > 370:
        return _deny("Invalid historical date window")
    if manifest["source_url"] != expected_url(start.isoformat(), end.isoformat()):
        return _deny("Source URL is not the exact public ECB series request")
    if manifest["raw_path"] != RAW_PATH:
        return _deny("Unexpected archived source path")
    dates_text = manifest["expected_dates"]
    if not isinstance(dates_text, list) or not 2 <= len(dates_text) <= 371:
        return _deny("Missing expected official observation dates")
    expected_dates = [_iso_date(day) for day in dates_text]
    if (any(day is None for day in expected_dates)
            or expected_dates != sorted(set(expected_dates))
            or expected_dates[0] != start or expected_dates[-1] != end
            or any(day.weekday() >= 5 for day in expected_dates)):
        return _deny("Invalid or unordered observation calendar")
    captured = _utc(manifest["captured_at_utc"])
    server = _utc(manifest["http_date_utc"])
    modified = _utc(manifest["http_last_modified_utc"])
    if captured is None or server is None or modified is None:
        return _deny("HTTP/capture clocks require canonical UTC strings")
    if (captured > evaluated_at.astimezone(timezone.utc) or
            modified > server or server > captured or
            captured < datetime.combine(end, time(18), tzinfo=timezone.utc)):
        return _deny("Unusable capture or HTTP chronology")
    if (type(manifest["http_status"]) is not int or manifest["http_status"] != 200
            or manifest["content_type"] != "text/csv"):
        return _deny("Unverified HTTP status or media type")
    if not isinstance(raw, bytes) or not 1 <= len(raw) <= 200_000 or b"\x00" in raw:
        return _deny("Raw CSV is missing, oversized, or contains NUL")
    digest = hashlib.sha256(raw).hexdigest()
    if (type(manifest["body_bytes"]) is not int
            or manifest["body_bytes"] != len(raw)
            or not isinstance(manifest["body_sha256"], str)
            or not re.fullmatch(r"[0-9a-f]{64}", manifest["body_sha256"])
            or manifest["body_sha256"] != digest):
        return _deny("Raw byte length or SHA-256 mismatch")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return _deny("CSV is not strict UTF-8")
    try:
        reader = csv.DictReader(StringIO(text, newline=""), strict=True)
        header = reader.fieldnames
        if (not header or len(header) != len(set(header))
                or not NEEDED.issubset(header)):
            return _deny("Unexpected CSV header or repeated column")
        by_day: dict[date, dict[str, str]] = {}
        count = 0
        for row in reader:
            count += 1
            if count > 3000 or None in row or any(v is None for v in row.values()):
                return _deny("Malformed, incomplete or oversized CSV row")
            currency = row["CURRENCY"]
            day = _iso_date(row["TIME_PERIOD"])
            if (currency not in CODES or day not in expected_dates
                    or row["FREQ"] != "D" or row["CURRENCY_DENOM"] != "EUR"
                    or row["EXR_TYPE"] != "SP00" or row["EXR_SUFFIX"] != "A"
                    or row["KEY"] != f"EXR.D.{currency}.EUR.SP00.A"
                    or row["OBS_STATUS"] != "A"):
                return _deny("Unexpected series, date, or observation status")
            value = row["OBS_VALUE"]
            if not isinstance(value, str) or not re.fullmatch(r"[0-9]{1,6}(?:\.[0-9]{1,10})?", value):
                return _deny("Invalid decimal quotation")
            try:
                rate = Decimal(value)
            except InvalidOperation:
                return _deny("Non-decimal ECB reference")
            if not Decimal("0.0001") <= rate <= Decimal("100000"):
                return _deny("Out-of-range ECB reference")
            daily = by_day.setdefault(day, {})
            if currency in daily:
                return _deny("Repeated currency observation")
            daily[currency] = value
    except (csv.Error, ValueError):
        return _deny("Cannot parse strict ECB CSV")
    if set(by_day) != set(expected_dates):
        return _deny("Missing or unexpected observation dates")
    if any(set(quotes) != CODES for quotes in by_day.values()):
        return _deny("Seven complete G8 EUR quotes required on every date")
    return {
        **_deny(""), "state": STATE, "reason": None,
        "reference_quotes_by_date": {
            day.isoformat(): dict(sorted(by_day[day].items()))
            for day in sorted(by_day)
        },
        "observation_dates": [day.isoformat() for day in sorted(by_day)],
        "original_rows": count, "original_eur_series": len(CODES),
        "raw_bytes_sha256_matched": True, "body_sha256": digest,
        "source_attribution": "ECB public EXR data; AtlasQuant archive and calculations.",
        "why_not": ("ECB daily informational references, not independently"
                    " attested historical delivery or broker spot prices."
                    " The 21 additional G8 crosses are algebraic, not"
                    " independent market observations."),
    }


__all__ = ["SCHEMA", "STATE", "RAW_PATH", "expected_url",
           "validate_ecb_archived_csv_lab"]
