"""AUD/NZD CPI series identity pilot. Metadata research only; never a FX signal.

No source URL, caller-declared vintage or SHA proves independent provenance.
This companion does NOT bypass the earlier G8 V1 macro-as-of gate.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any
import json
import re

SCHEMA = "ATLASQUANT_CPI_SERIES_AUDNZD_LAB_V2"
# Local catalog keys, NOT official issuer series identifiers.
CATALOG = {
    "AUD_MONTHLY_CPI_YOY": ("AUD", "MONTHLY", "2025-10"),
    "AUD_QUARTERLY_CPI_YOY": ("AUD", "QUARTERLY", "2020-01"),
    "NZD_QUARTERLY_CPI_YOY": ("NZD", "QUARTERLY", "2020-01"),
    "NZD_MONTHLY_CPI_YOY": ("NZD", "MONTHLY", "2027-01"),
}
FIELDS = {"currency", "atlasquant_series_key", "frequency", "observation_period",
          "value", "published_at_utc", "captured_at_utc", "source_sha256", "source_url"}
MONTH = re.compile(r"20\d\d-(?:0[1-9]|1[0-2])\Z")
UTC = re.compile(r"20\d\d-\d\d-\d\dT\d\d:\d\d:\d\dZ\Z")
NUMBER = re.compile(r"-?(?:0|[1-9]\d{0,2})(?:\.\d{1,4})?\Z")
SHA = re.compile(r"[0-9a-f]{64}\Z")
QUARTERS = {"03", "06", "09", "12"}


def _time(s: Any) -> datetime:
    if not isinstance(s, str) or not UTC.fullmatch(s):
        raise ValueError("TIMESTAMP_FORMAT")
    try:
        return datetime.fromisoformat(s[:-1] + "+00:00")
    except ValueError as exc:
        raise ValueError("TIMESTAMP_FORMAT") from exc


def _reject(reason: str) -> dict[str, Any]:
    return {"schema": SCHEMA, "state": "LAB_BLOCKED", "reason": reason,
            "comparability": None, "coverage": {}, "operational_bias": "AGUARDAR",
            "score_0_to_10": None, "validated_accuracy": None,
            "source_independently_verified": False, "vintage_independently_verified": False,
            "can_feed_live_radar": False, "trade_authorized": False,
            "automatic_alert_enabled": False, "new_cost_brl": 0}


def audit_cpi_series_lab(payload: Any, *, as_of_utc: datetime) -> dict[str, Any]:
    """Validate a two-series AUD/NZD CPI claim, never attest/score/act on it."""
    try:
        if (not isinstance(as_of_utc, datetime) or as_of_utc.tzinfo is None
                or as_of_utc.utcoffset() is None):
            raise ValueError("DECISION_CLOCK_INVALID")
        now = as_of_utc.astimezone(timezone.utc)
        if not isinstance(payload, dict) or set(payload) != {"schema", "pair", "decision_at_utc", "records"}:
            raise ValueError("ENVELOPE_INVALID")
        if payload["schema"] != SCHEMA or payload["pair"] != "AUD/NZD":
            raise ValueError("UNSUPPORTED_SCHEMA_OR_PAIR")
        decision = _time(payload["decision_at_utc"])
        if decision > now:
            raise ValueError("DECISION_CLOCK_IN_FUTURE")
        rows = payload["records"]
        if not isinstance(rows, list) or len(rows) != 2:
            raise ValueError("TWO_SOURCES_REQUIRED")
        reviewed: dict[str, dict[str, Any]] = {}
        for row in rows:
            if not isinstance(row, dict) or set(row) != FIELDS:
                raise ValueError("RECORD_FIELDS_INVALID")
            name = row["atlasquant_series_key"]
            if not isinstance(name, str) or name not in CATALOG:
                raise ValueError("UNKNOWN_SERIES_KEY")
            currency, cadence, first_period = CATALOG[name]
            if row["currency"] != currency or row["frequency"] != cadence:
                raise ValueError("SERIES_ID_FREQUENCY_CURRENCY_MISMATCH")
            period = row["observation_period"]
            if not isinstance(period, str) or not MONTH.fullmatch(period) or period < first_period:
                raise ValueError("REFERENCE_PERIOD_INVALID_FOR_SERIES")
            if cadence == "QUARTERLY" and period[-2:] not in QUARTERS:
                raise ValueError("QUARTER_END_REQUIRED")
            numeric = row["value"]
            if not isinstance(numeric, str) or not NUMBER.fullmatch(numeric):
                raise ValueError("VALUE_FORMAT_INVALID")
            try:
                number = Decimal(numeric)
            except InvalidOperation as exc:
                raise ValueError("VALUE_FORMAT_INVALID") from exc
            if not number.is_finite() or not Decimal("-50") <= number <= Decimal("100"):
                raise ValueError("VALUE_RANGE_INVALID")
            if not isinstance(row["source_sha256"], str) or not SHA.fullmatch(row["source_sha256"]):
                raise ValueError("SOURCE_HASH_FORMAT_INVALID")
            url = row["source_url"]
            if (not isinstance(url, str) or not url.startswith(
                    "https://www.abs.gov.au/" if currency == "AUD"
                    else "https://www.stats.govt.nz/")):
                raise ValueError("SOURCE_URL_FORMAT_INVALID")
            published = _time(row["published_at_utc"])
            captured = _time(row["captured_at_utc"])
            if not published <= captured <= decision or period > published.strftime("%Y-%m"):
                raise ValueError("LOOKAHEAD_OR_CHRONOLOGY")
            lag = (decision.year - int(period[:4])) * 12 + decision.month - int(period[-2:])
            max_lag = 2 if cadence == "MONTHLY" else 4
            max_age = 60 if cadence == "MONTHLY" else 120
            if lag > max_lag or (decision - published).total_seconds() > max_age * 86400:
                raise ValueError("CPI_PERIOD_OR_RELEASE_STALE")
            if currency in reviewed:
                raise ValueError("DUPLICATE_CURRENCY")
            reviewed[currency] = {"atlasquant_series_key": name, "frequency": cadence,
                                  "observation_period": period,
                                  "reference_months_behind_decision": lag,
                                  "published_at_utc_claim": row["published_at_utc"],
                                  "source_sha256_claim": row["source_sha256"]}
        if set(reviewed) != {"AUD", "NZD"}:
            raise ValueError("BOTH_CURRENCIES_REQUIRED")
    except (ValueError, TypeError, KeyError, OverflowError) as exc:
        return _reject(str(exc) if str(exc) else "MALFORMED_INPUT")

    comparable = reviewed["AUD"]["frequency"] == reviewed["NZD"]["frequency"]
    result = _reject("SOURCE_AND_HISTORICAL_VINTAGE_UNATTESTED")
    result.update({
        "state": "LAB_CPI_SAME_FREQUENCY_UNATTESTED" if comparable else "LAB_CPI_FREQUENCY_MISMATCH",
        "reason": "SOURCE_AND_HISTORICAL_VINTAGE_UNATTESTED" if comparable else "MONTHLY_VS_QUARTERLY_NOT_LIKE_FOR_LIKE",
        "comparability": "SAME_FREQUENCY_UNATTESTED" if comparable else "DIFFERENT_FREQUENCIES",
        "coverage": reviewed,
    })
    return result


__all__ = ["SCHEMA", "CATALOG", "audit_cpi_series_lab"]
