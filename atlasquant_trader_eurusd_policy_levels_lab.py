"""Fail-closed, offline ECB/Fed policy *level* readers for Trader LAB.

The input bytes are provided by the caller, not authenticated by this module.
ECB DFR change-effective dates and Fed target-range daily effective levels are
NOT monetary-policy decision announcement times or pre-meeting expectations.
Neither a rate difference nor a policy level can authorize an FX direction.
No HTTP, filesystem writes, scheduler, API key, or broker access.
"""
from __future__ import annotations

import csv
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from io import StringIO
import re
from typing import Any

SCHEMA = "ATLASQUANT_TRADER_EURUSD_POLICY_LEVELS_CSV_LAB_V1"
ECB_SERIES = "FM.D.U2.EUR.4F.KR.DFR.LEV"
ECB_SOURCE_URL = ("https://data-api.ecb.europa.eu/service/data/FM/"
                  "D.U2.EUR.4F.KR.DFR.LEV?format=csvdata&startPeriod=2025-01-01")
FED_SOURCE_URL = ("https://fred.stlouisfed.org/graph/fredgraph.csv?"
                  "id=DFEDTARL%2CDFEDTARU")
MAX_BYTES = 512 * 1024
_DECIMAL = re.compile(r"-?[0-9]{1,2}(?:\.[0-9]{1,7})?\Z")


def _blocked(reason: str, currency: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_BLOCKED", "reason": reason,
        "currency": currency, "latest_effective_date": None,
        "rate_percent": None, "lower_bound_percent": None,
        "upper_bound_percent": None,
        "raw_response_sha256": None,
        "collection_clock_utc": None,
        "current_http_response_observed": False,
        "source_origin_independently_authenticated": False,
        "decision_announcement_instant_verified": False,
        "pre_event_consensus_verified": False,
        "point_in_time_vintage_verified": False,
        "market_implied_expectation_verified": False,
        "independent_fx_spot_verified": False,
        "operational_bias": "AGUARDAR", "trade_authorized": False,
        "can_feed_live_radar": False, "publishable": False,
        "worker_enabled": False, "scheduler_enabled": False,
        "new_cost_brl": 0,
    }


def _clock(at: datetime) -> date:
    if not isinstance(at, datetime) or at.tzinfo is None or at.utcoffset() is None:
        raise ValueError("Timezone-aware observation clock required")
    return at.astimezone(timezone.utc).date()


def _rows(raw: Any, required: set[str], max_rows: int) -> list[dict[str, str]] | None:
    if (not isinstance(raw, bytes) or not 1 <= len(raw) <= MAX_BYTES
            or b"\x00" in raw):
        return None
    try:
        data = raw.decode("utf-8-sig")
        reader = csv.DictReader(StringIO(data, newline=""), strict=True)
        fields = reader.fieldnames
        if (not fields or len(fields) != len(set(fields))
                or not required.issubset(fields)):
            return None
        result: list[dict[str, str]] = []
        for row in reader:
            if (len(result) == max_rows or None in row
                    or any(not isinstance(v, str) for v in row.values())):
                return None
            result.append(row)
        return result or None
    except (UnicodeError, csv.Error, ValueError, OverflowError):
        return None


def _date(value: str, today: date) -> date | None:
    if not isinstance(value, str) or not re.fullmatch(r"20[0-9]{2}-[0-9]{2}-[0-9]{2}", value):
        return None
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        return None
    return parsed if parsed <= today else None


def _rate(value: str) -> Decimal | None:
    if not isinstance(value, str) or not _DECIMAL.fullmatch(value):
        return None
    try:
        parsed = Decimal(value)
    except InvalidOperation:
        return None
    return parsed if Decimal("-5") <= parsed <= Decimal("30") else None


def parse_ecb_dfr_effective_csv_lab(
    raw: Any, *, observed_at_utc: datetime,
) -> dict[str, Any]:
    """Read an exact ECB FM DFR series; changes' effective dates only."""
    today = _clock(observed_at_utc)
    out = _blocked("ECB_CSV_REJECTED", "EUR")
    rows = _rows(raw, {"KEY", "FREQ", "REF_AREA", "CURRENCY",
                       "TIME_PERIOD", "OBS_VALUE"}, 250)
    if rows is None:
        return out
    effective: dict[date, str] = {}
    last: date | None = None
    dimensions = {"FREQ": "D", "REF_AREA": "U2", "CURRENCY": "EUR",
                  "PROVIDER_FM": "4F", "INSTRUMENT_FM": "KR",
                  "PROVIDER_FM_ID": "DFR", "DATA_TYPE_FM": "LEV"}
    for row in rows:
        day = _date(row["TIME_PERIOD"], today)
        val = _rate(row["OBS_VALUE"])
        if (row["KEY"] != ECB_SERIES or day is None or val is None
                or (last is not None and day <= last)
                or any(key in row and row[key] != expected
                       for key, expected in dimensions.items())
                or row.get("OBS_STATUS", "") not in ("", "A")):
            return out
        last = day
        effective[day] = str(val)
    latest = max(effective)
    out.update({
        "state": "LAB_ECB_DFR_EFFECTIVE_LEVEL_QUARANTINED", "reason": None,
        "series_id": ECB_SERIES, "source_url": ECB_SOURCE_URL,
        "measure": "DEPOSIT_FACILITY_RATE_PERCENT_PER_ANNUM",
        "effective_date_not_decision_announcement": True,
        "latest_effective_date": latest.isoformat(),
        "rate_percent": effective[latest],
        "effective_changes_count": len(effective),
        "raw_response_sha256": sha256(raw).hexdigest(),
        "collection_clock_utc": observed_at_utc.astimezone(timezone.utc).isoformat(),
    })
    return out


def parse_fed_target_range_csv_lab(
    raw: Any, *, observed_at_utc: datetime,
) -> dict[str, Any]:
    """Read St. Louis Fed graph CSV: daily target range, not FOMC releases."""
    today = _clock(observed_at_utc)
    out = _blocked("FED_CSV_REJECTED", "USD")
    if not isinstance(raw, bytes):
        return out
    # Graph exports have used both DATE and observation_date headers. Their
    # meaning is identical here; a second date column is ambiguous and denied.
    header = raw.split(b"\n", 1)[0].decode("utf-8-sig", errors="replace")
    date_keys = [key for key in ("DATE", "observation_date")
                 if key in header.split(",")]
    if len(date_keys) != 1:
        return out
    date_key = date_keys[0]
    rows = _rows(raw, {date_key, "DFEDTARL", "DFEDTARU"}, 10000)
    if rows is None:
        return out
    last: date | None = None
    latest_pair: tuple[str, str] | None = None
    missing: list[str] = []
    for row in rows:
        day = _date(row[date_key], today)
        if day is None or (last is not None and day <= last):
            return out
        last = day
        lower_text, upper_text = row["DFEDTARL"], row["DFEDTARU"]
        if lower_text == "." or upper_text == ".":
            if lower_text not in (".",) and _rate(lower_text) is None:
                return out
            if upper_text not in (".",) and _rate(upper_text) is None:
                return out
            missing.append(day.isoformat())
            latest_pair = None
            continue
        lower, upper = _rate(lower_text), _rate(upper_text)
        if lower is None or upper is None or lower > upper or upper - lower > 2:
            return out
        latest_pair = str(lower), str(upper)
    if latest_pair is None or last is None:
        return _blocked("FED_LATEST_TARGET_RANGE_MISSING", "USD")
    out.update({
        "state": "LAB_FED_TARGET_RANGE_DAILY_QUARANTINED", "reason": None,
        "series_ids": ["DFEDTARL", "DFEDTARU"],
        "source_url": FED_SOURCE_URL,
        "measure": "FOMC_TARGET_RANGE_EFFECTIVE_DAILY_PERCENT",
        "daily_effective_date_not_fomc_announcement": True,
        "latest_effective_date": last.isoformat(),
        "lower_bound_percent": latest_pair[0],
        "upper_bound_percent": latest_pair[1],
        "missing_daily_rows": missing,
        "raw_response_sha256": sha256(raw).hexdigest(),
        "collection_clock_utc": observed_at_utc.astimezone(timezone.utc).isoformat(),
    })
    return out


def compare_eurusd_policy_levels_lab(eur: Any, usd: Any) -> dict[str, Any]:
    """Expose labels safely; NEVER infer a directional policy spread."""
    expected = ("LAB_ECB_DFR_EFFECTIVE_LEVEL_QUARANTINED",
                "LAB_FED_TARGET_RANGE_DAILY_QUARANTINED")
    correct = (isinstance(eur, dict) and isinstance(usd, dict)
               and eur.get("schema") == SCHEMA and usd.get("schema") == SCHEMA
               and eur.get("currency") == "EUR" and usd.get("currency") == "USD"
               and (eur.get("state"), usd.get("state")) == expected)
    return {
        "schema": SCHEMA,
        "state": ("LAB_POLICY_LEVELS_DIFFERENT_MEASURES_QUARANTINED"
                  if correct else "LAB_BLOCKED"),
        "eur_deposit_facility_percent": eur.get("rate_percent") if correct else None,
        "fed_target_range_lower_percent": usd.get("lower_bound_percent") if correct else None,
        "fed_target_range_upper_percent": usd.get("upper_bound_percent") if correct else None,
        "different_effective_dates": (eur["latest_effective_date"] !=
                                      usd["latest_effective_date"]) if correct else None,
        "different_policy_instruments": True,
        "policy_rate_spread_bps": None,
        "prior_meeting_expectation_bps": None,
        "market_surprise_bps": None,
        "fomc_and_ecb_decision_release_times": None,
        "fx_bias": None, "operational_bias": "AGUARDAR",
        "trade_authorized": False, "can_feed_live_radar": False,
        "publishable": False, "worker_enabled": False,
        "scheduler_enabled": False, "new_cost_brl": 0,
    }


__all__ = ["ECB_SERIES", "ECB_SOURCE_URL", "FED_SOURCE_URL",
           "parse_ecb_dfr_effective_csv_lab", "parse_fed_target_range_csv_lab",
           "compare_eurusd_policy_levels_lab"]
