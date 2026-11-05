"""Exploratory offline ONS D7G7 monthly UK CPI annual-rate JSON parser.

The ONS publishes this series and superseded historical versions. The
website /data JSON representation must be confirmed against original captured
bytes before this parser is treated as integrated with a live source.
No HTTP or directional GBP inference; date-only is NOT a release timestamp.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import json
import re
from typing import Any

SCHEMA = "ATLASQUANT_TRADER_ONS_GBP_D7G7_CPI_CURRENT_LAB_V1"
SERIES_ID = "D7G7"
SOURCE_DATASET = "MM23"
EXPECTED_TITLE = "CPI ANNUAL RATE 00: ALL ITEMS 2015=100"
SOURCE_PAGE = "https://www.ons.gov.uk/economy/inflationandpriceindices/timeseries/d7g7/mm23"
SOURCE_PREVIOUS = SOURCE_PAGE + "/previous"
SOURCE_DATA = SOURCE_PAGE + "/data"
MONTH_NAMES = {name: i for i, name in enumerate((
    "JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"
), start=1)}
MAX_BYTES = 512 * 1024
MAX_ROWS = 1200
MONTH_RE = re.compile(r"(20\d\d|19\d\d) (JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)")
RATE_RE = re.compile(r"-?(?:0|[1-9]\d{0,2})(?:\.\d{1,3})?")


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_BLOCKED", "reason": reason,
        "currency": "GBP", "source": "UK_ONS", "series_id": SERIES_ID,
        "source_dataset": SOURCE_DATASET,
        "source_page": SOURCE_PAGE, "source_previous_versions": SOURCE_PREVIOUS,
        "source_json_candidate_endpoint": SOURCE_DATA,
        "source_bytes_sha256": None, "source_byte_count": None,
        "observed_at_local_system_utc": None,
        "latest_period": None, "latest_annual_cpi_rate_percent": None,
        "monthly_observations": [], "monthly_observation_count": 0,
        "release_date_calendar_only": None,
        "individual_release_instant_verified": False,
        "archived_historical_vintage_verified": False,
        "original_http_response_observed": False,
        "original_source_authenticity_verified": False,
        "consensus_pre_event_attested": False,
        "methodologically_comparable_to_EUR_HICP_US_CPIU": False,
        "commercial_redistribution_rights_verified": False,
        "fx_bias": None, "operational_bias": "AGUARDAR",
        "trade_authorized": False, "can_feed_live_radar": False,
        "worker_enabled": False, "scheduler_enabled": False,
        "publishable": False, "external_http_requests": 0, "new_cost_brl": 0,
    }


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    item: dict[str, Any] = {}
    for key, value in pairs:
        if key in item:
            raise ValueError("duplicate JSON key")
        item[key] = value
    return item


def _rate(raw: Any) -> str | None:
    if raw is None or raw in ("", "..", ":"):
        return None
    if isinstance(raw, bool) or not isinstance(raw, (str, int, float, Decimal)):
        raise ValueError("bad rate type")
    s = str(raw)
    if RATE_RE.fullmatch(s) is None:
        raise ValueError("bad rate syntax")
    try:
        value = Decimal(s)
    except InvalidOperation as exc:
        raise ValueError("bad decimal") from exc
    if not Decimal("-50") <= value <= Decimal("100"):
        raise ValueError("out of range")
    return s


def parse_current_ons_gbp_d7g7_lab(
    raw: Any, *, observed_at_utc: datetime,
) -> dict[str, Any]:
    """Only parse provided bytes; do not assert their ONS origin or vintage."""
    out = _blocked("INVALID_INPUT_OR_CAPTURE_CLOCK")
    if (not isinstance(raw, bytes) or not 100 <= len(raw) <= MAX_BYTES
            or not isinstance(observed_at_utc, datetime)
            or observed_at_utc.tzinfo is None or observed_at_utc.utcoffset() is None):
        return out
    now = observed_at_utc.astimezone(timezone.utc)
    try:
        obj = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_object,
                         parse_constant=lambda _s: (_ for _ in ()).throw(ValueError("NaN")))
    except (UnicodeDecodeError, ValueError, TypeError, RecursionError):
        out["reason"] = "INVALID_JSON_OR_DUPLICATE_KEYS"
        return out
    if not isinstance(obj, dict):
        out["reason"] = "INVALID_ONS_JSON_ROOT"
        return out
    dataset_ids = [obj.get(k) for k in ("dataset", "sourceDataset") if k in obj]
    if (obj.get("cdid") != SERIES_ID or not dataset_ids
            or any(x != SOURCE_DATASET for x in dataset_ids)
            or obj.get("description") != EXPECTED_TITLE
            or obj.get("unit") != "%"
            or obj.get("preUnit") not in (None, "")
            or not isinstance(obj.get("months"), list)):
        out["reason"] = "ONS_D7G7_SERIES_METADATA_MISMATCH"
        return out
    release_str = obj.get("date")
    if not isinstance(release_str, str):
        out["reason"] = "ONS_RELEASE_CALENDAR_DATE_MISSING"
        return out
    try:
        release_day = datetime.strptime(release_str, "%d %B %Y").date()
    except ValueError:
        out["reason"] = "ONS_RELEASE_CALENDAR_DATE_INVALID"
        return out
    if release_day > now.date():
        out["reason"] = "ONS_REPORTED_RELEASE_DATE_AFTER_LOCAL_CAPTURE"
        return out

    months = obj["months"]
    if not 1 <= len(months) <= MAX_ROWS:
        out["reason"] = "ONS_MONTH_COUNT_UNSUPPORTED"
        return out
    rows = []
    last_yearmonth = None
    try:
        for item in months:
            if not isinstance(item, dict) or not isinstance(item.get("date"), str):
                raise ValueError("bad month")
            match = MONTH_RE.fullmatch(item["date"])
            if match is None:
                raise ValueError("bad date")
            yearmonth = (int(match.group(1)), MONTH_NAMES[match.group(2)])
            if last_yearmonth is not None and yearmonth <= last_yearmonth:
                raise ValueError("unsorted or duplicate month")
            last_yearmonth = yearmonth
            value = _rate(item.get("value"))
            rows.append({"period": f"{yearmonth[0]:04d}-{yearmonth[1]:02d}",
                         "annual_cpi_percent_claim": value})
    except (ValueError, TypeError, OverflowError):
        out["reason"] = "ONS_MONTH_OBSERVATION_INVALID"
        return out
    if (not rows or rows[-1]["annual_cpi_percent_claim"] is None
            or release_day < datetime.strptime(rows[-1]["period"], "%Y-%m").date()):
        out["reason"] = "ONS_LATEST_MONTHLY_RATE_MISSING_OR_RELEASE_PRECEDES_MONTH"
        return out

    out.update({
        "state": "LAB_CURRENT_GBP_ONS_D7G7_QUARANTINED",
        "reason": "ONS_RAW_BYTES_NOT_HISTORICAL_VINTAGE_OR_INDEPENDENT_ORIGIN",
        "source_bytes_sha256": sha256(raw).hexdigest(),
        "source_byte_count": len(raw),
        "observed_at_local_system_utc": now.isoformat(),
        "latest_period": rows[-1]["period"],
        "latest_annual_cpi_rate_percent": rows[-1]["annual_cpi_percent_claim"],
        "monthly_observations": rows[-min(15, len(rows)):],
        "monthly_observation_count": len(rows),
        "release_date_calendar_only": release_day.isoformat(),
        "release_day_is_not_publication_instant": True,
        "current_series_is_not_archived_previous_version": True,
    })
    return out


__all__ = ["SCHEMA", "SERIES_ID", "SOURCE_DATA", "parse_current_ons_gbp_d7g7_lab"]
