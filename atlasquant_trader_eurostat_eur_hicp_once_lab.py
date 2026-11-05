"""Manual Eurostat EUR HICP annual inflation observation (strict LAB).

Dataset prc_hicp_minr uses ECOICOP v2 after the old manr dataset ended in
2025. This reads the LATEST mutable Eurostat dataset, not a pre-event vintage.
Nothing feeds live bias, orders, cron or AION. HTTP is OFF by default.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from math import isfinite
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import HTTPSHandler, Request, build_opener
import json
import re
import ssl
from zipfile import ZipFile, ZIP_STORED

from atlasquant_trader_g8_single_https_probe_lab import _RejectRedirect

SCHEMA = "ATLASQUANT_TRADER_EUROSTAT_EUR_HICP_ECOICOP2_LAB_V1"
API_URL = ("https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/"
           "prc_hicp_minr?format=JSON&lang=EN&geo=EA&unit=RCH_A"
           "&coicop18=TOTAL&lastTimePeriod=3")
MAX_BYTES = 128 * 1024
_EXPECTED_IDS = ["freq", "unit", "coicop18", "geo", "time"]
_FIXED = {"freq": "M", "unit": "RCH_A", "coicop18": "TOTAL", "geo": "EA"}
_PERIOD = re.compile(r"^20[0-9]{2}-(0[1-9]|1[0-2])$")


def _blocked(reason: str, *, attempted: bool = False) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_BLOCKED", "reason": reason,
        "currency": "EUR", "indicator": "EURO_AREA_HICP_YOY",
        "source": "EUROSTAT", "source_dataset": "prc_hicp_minr",
        "external_http_requests": int(attempted),
        "current_http_response_observed": False,
        "pre_event_vintage_proven": False,
        "release_at_instant_proven": False,
        "economic_causation_verified": False,
        "source_payload_custody_authenticated": False,
        "independent_forex_spot_verified": False,
        "trade_authorized": False, "can_feed_live_radar": False,
        "publishable": False, "worker_enabled": False,
        "scheduler_enabled": False, "new_cost_brl": 0,
        "operational_bias": "AGUARDAR",
    }


def parse_current_eur_hicp_jsonstat_lab(
    raw: Any, *, observed_at_utc: datetime,
) -> dict[str, Any]:
    """Interpret caller-supplied JSON bytes, ALWAYS without ex-ante authority."""
    if (not isinstance(observed_at_utc, datetime)
            or observed_at_utc.tzinfo is None
            or observed_at_utc.utcoffset() is None):
        raise ValueError("Timezone-aware capture clock required")
    now = observed_at_utc.astimezone(timezone.utc)
    if (not isinstance(raw, bytes) or
            not 1 <= len(raw) <= MAX_BYTES):
        return _blocked("INVALID_JSONSTAT_BYTE_LENGTH")
    try:
        obj = json.loads(raw)
    except (UnicodeDecodeError, ValueError, TypeError, OverflowError):
        return _blocked("JSONSTAT_NOT_VALID_JSON")
    if not isinstance(obj, dict):
        return _blocked("JSONSTAT_NOT_OBJECT")
    if (obj.get("class") != "dataset" or obj.get("version") != "2.0"
            or obj.get("source") != "ESTAT"
            or obj.get("id") != _EXPECTED_IDS
            or not isinstance(obj.get("size"), list)):
        return _blocked("JSONSTAT_WRONG_DATASET_OR_STRUCTURE")
    size = obj["size"]
    if (len(size) != 5 or size[:4] != [1, 1, 1, 1]
            or isinstance(size[4], bool) or not isinstance(size[4], int)
            or not 1 <= size[4] <= 3):
        return _blocked("JSONSTAT_NOT_ONE_SERIES_WITH_BOUNDED_MONTHS")
    count = size[4]
    dims = obj.get("dimension")
    if not isinstance(dims, dict) or set(dims) != set(_EXPECTED_IDS):
        return _blocked("JSONSTAT_DIMENSIONS_NOT_EXACT")
    for dimension, code in _FIXED.items():
        item = dims.get(dimension)
        if (not isinstance(item, dict)
                or not isinstance(item.get("category"), dict)
                or item["category"].get("index") != {code: 0}):
            return _blocked("JSONSTAT_DIMENSIONS_NOT_EXACT")
    time_dim = dims["time"]
    if (not isinstance(time_dim, dict)
            or not isinstance(time_dim.get("category"), dict)):
        return _blocked("JSONSTAT_TIME_DIMENSION_INVALID")
    indexes = time_dim["category"].get("index")
    if not isinstance(indexes, dict) or len(indexes) != count:
        return _blocked("JSONSTAT_TIME_INDEX_INVALID")
    if (any(not isinstance(period, str) or not _PERIOD.fullmatch(period)
            for period in indexes)
            or any(type(x) is not int for x in indexes.values())
            or sorted(indexes.values()) != list(range(count))):
        return _blocked("JSONSTAT_TIME_INDEX_INVALID")
    periods = sorted(indexes, key=lambda period: indexes[period])
    if (periods != sorted(periods)
            or any(period > now.strftime("%Y-%m") for period in periods)):
        return _blocked("JSONSTAT_FUTURE_OR_UNSORTED_MONTH")
    values = obj.get("value")
    if (not isinstance(values, dict)
            or set(values) != {str(i) for i in range(count)}):
        return _blocked("JSONSTAT_MISSING_OR_EXTRA_VALUES")
    status = obj.get("status", {})
    if (not isinstance(status, dict)
            or not set(status).issubset(values.keys())
            or any(x != "e" for x in status.values())):
        return _blocked("JSONSTAT_UNKNOWN_OBSERVATION_STATUS")
    updated_raw = obj.get("updated")
    if not isinstance(updated_raw, str):
        return _blocked("DATASET_UPDATE_TIME_MISSING")
    try:
        updated = datetime.fromisoformat(updated_raw.replace("Z", "+00:00"))
    except (ValueError, OverflowError, TypeError):
        return _blocked("DATASET_UPDATE_TIME_INVALID")
    if (updated.tzinfo is None or updated.utcoffset() is None
            or updated.astimezone(timezone.utc) > now):
        return _blocked("DATASET_UPDATE_TIME_INVALID_OR_FUTURE")

    rows = []
    for i, period in enumerate(periods):
        val = values[str(i)]
        if (isinstance(val, bool) or not isinstance(val, (float, int))
                or not isfinite(val) or not -50.0 <= val <= 100.0):
            return _blocked("JSONSTAT_VALUE_NOT_FINITE_OR_IMPLAUSIBLE")
        rows.append({
            "period": period, "annual_inflation_percent": float(val),
            "status_flag": status.get(str(i), ""),
            "status_interpretation": (
                "ESTIMATED_NOT_FINAL" if status.get(str(i)) == "e"
                else "UNFLAGGED_NOT_PROOF_OF_FINALITY"),
            "individual_release_instant_proven": False,
            "was_available_before_historical_forecast_proven": False,
        })
    result = _blocked("LATEST_DATASET_ONLY_NO_HISTORICAL_VINTAGES")
    result.update({
        "state": "LAB_EUR_HICP_CURRENT_JSONSTAT_QUARANTINED",
        "raw_response_sha256": sha256(raw).hexdigest(),
        "raw_response_bytes": len(raw),
        "observed_at_local_system_utc": now.isoformat(),
        "dataset_updated_at_declared_utc": updated.astimezone(timezone.utc).isoformat(),
        "dataset_update_not_individual_release_instant": True,
        "collection_not_proof_of_historical_availability": True,
        "series_dimensions_verified": True,
        "historical_months_observed_not_historical_vintages": rows,
        "estimate_count": sum(x["status_flag"] == "e" for x in rows),
        "raw_snapshot_archive_path": None,
    })
    return result


def fetch_current_eur_hicp_once_lab(
    *, manually_authorized: bool = False, timeout_seconds: int = 8,
    archive_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Opt-in one request; archive raw bytes ONLY if explicit directory passed."""
    if manually_authorized is not True:
        return _blocked("MANUAL_HTTP_OPT_IN_REQUIRED")
    if (isinstance(timeout_seconds, bool)
            or not isinstance(timeout_seconds, int)
            or not 1 <= timeout_seconds <= 15):
        return _blocked("HTTP_TIMEOUT_OUT_OF_BOUNDS")
    request = Request(API_URL, method="GET", headers={
        "Accept": "application/json", "Accept-Encoding": "identity",
        "User-Agent": "AtlasQuant-Trader-LAB-manual-HICP/1.0",
    })
    try:
        opener = build_opener(
            HTTPSHandler(context=ssl.create_default_context()), _RejectRedirect())
        with opener.open(request, timeout=timeout_seconds) as response:
            if response.status != 200 or response.geturl() != API_URL:
                return _blocked("HTTP_STATUS_OR_FINAL_URL_INVALID", attempted=True)
            media = response.headers.get("Content-Type", "").split(";")[0].strip().lower()
            if media != "application/json" or response.headers.get(
                    "Content-Encoding", "identity").lower() != "identity":
                return _blocked("HTTP_NOT_PLAIN_JSON", attempted=True)
            raw = response.read(MAX_BYTES + 1)
    except (HTTPError, URLError, OSError, ssl.SSLError, TimeoutError,
            TypeError, ValueError) as exc:
        return _blocked("HTTPS_FAILED_" + type(exc).__name__, attempted=True)
    captured = datetime.now(timezone.utc)
    parsed = parse_current_eur_hicp_jsonstat_lab(raw, observed_at_utc=captured)
    parsed["external_http_requests"] = 1
    parsed["current_http_response_observed"] = True
    parsed["exact_url_requested"] = API_URL
    parsed["tls_default_ca_validation_requested"] = True
    parsed["http_redirects_followed"] = False
    if parsed["state"] != "LAB_EUR_HICP_CURRENT_JSONSTAT_QUARANTINED":
        return parsed
    if archive_dir is not None:
        try:
            directory = Path(archive_dir)
            if not directory.is_dir():
                return _blocked("SNAPSHOT_DIRECTORY_MISSING", attempted=True)
            stamp = captured.strftime("%Y%m%dT%H%M%S%fZ")
            name = "eurostat_eur_hicp_" + stamp + "_" + sha256(raw).hexdigest()[:12] + ".zip"
            dest = directory / name
            metadata = {k: v for k, v in parsed.items() if k != "raw_snapshot_archive_path"}
            with ZipFile(dest, "x", compression=ZIP_STORED) as archive:
                archive.writestr("response.json", raw)
                archive.writestr("observation_receipt.json",
                                 json.dumps(metadata, sort_keys=True,
                                            ensure_ascii=False, indent=2))
            parsed["raw_snapshot_archive_path"] = str(dest)
            parsed["raw_snapshot_archive_sha256"] = sha256(dest.read_bytes()).hexdigest()
        except (OSError, ValueError, TypeError, RuntimeError):
            return _blocked("SNAPSHOT_ARCHIVE_FAILED", attempted=True)
    return parsed


__all__ = [
    "SCHEMA", "API_URL", "parse_current_eur_hicp_jsonstat_lab",
    "fetch_current_eur_hicp_once_lab",
]
