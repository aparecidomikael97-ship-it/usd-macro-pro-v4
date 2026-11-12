"""Read-only U.S. BLS CPI-U *index level* source-byte capture (LAB).

Provider API doc: https://www.bls.gov/developers/api_signature.htm
The BLS public API v1 supports an unauthenticated GET for one series.
The fixed CUUR0000SA0 is the *not-seasonally-adjusted index level*; it is
NEITHER CPI YoY nor a bilateral currency-strength score. Never substitute
an index level into CPI_YOY receipts for the eight-currency preflight.

A live HTTPS read can establish only that particular bytes were received
from that endpoint at a bounded local observation time. It cannot prove
original first-release time, historical vintages, absence of revisions, the
statistical meaning of each measure, or profitability. Keep its bytes for
separate issuer/period and pre-event custody audits before any research use.

No key/token, files, GitHub writes, broker IO, trading or scheduler.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from email.utils import parsedate_to_datetime
from hashlib import sha256
import json
import re
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

SCHEMA = "ATLASQUANT_TRADER_BLS_CPI_U_V1_BYTES_CAPTURE_LAB_V1"
SERIES = "CUUR0000SA0"
URL = f"https://api.bls.gov/publicAPI/v1/timeseries/data/{SERIES}"
MAX_BODY_BYTES = 512_000
MAX_OBSERVATIONS = 48
PERIOD = re.compile(r"M(?:0[1-9]|1[0-2])\Z")
YEAR = re.compile(r"20[0-3][0-9]\Z")
VALUE = re.compile(r"[0-9]{1,7}(?:\.[0-9]{1,4})?\Z")


class _NoRedirect(HTTPRedirectHandler):
    """Preserve the exact BLS issuer origin; never follow to another host."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _utc(value: Any) -> datetime | None:
    if (not isinstance(value, datetime) or value.tzinfo is None
            or value.utcoffset() is None):
        return None
    try:
        return value.astimezone(timezone.utc)
    except (OverflowError, ValueError):
        return None


def _unique_json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON field")
        result[key] = value
    return result


def _blocked(reason: str, *, attempted_http: int = 0) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_BLS_CPI_U_CAPTURE_BLOCKED",
        "reason": reason, "source_url": URL,
        "series_id": SERIES, "measure": "USD_CPI_U_INDEX_LEVEL_NOT_YOY",
        "last_monthly_period_documentary": None,
        "last_index_level_documentary": None,
        "monthly_observation_count": 0,
        "captured_at_utc": None, "server_date_utc_claim": None,
        "source_sha256": None, "original_source_bytes_in_memory": None,
        "original_source_bytes_retained_in_result": False,
        "http_get_completed": False, "http_requests": attempted_http,
        "no_redirect_enforced": True,
        "publisher_host_static_bls": True,
        "original_release_at_independently_attested": False,
        "original_historical_vintage_independently_attested": False,
        "cpi_yoy_from_same_vintage_computed": False,
        "index_level_safe_to_compare_to_euro_hicp_yoy": False,
        "can_feed_fx28_directional_forecast": False,
        "macro_directional_signal": None,
        "validated_directional_accuracy": None,
        "calibrated_direction_probability": None,
        "operational_bias": "AGUARDAR",
        "live_alert_allowed": False, "publishable": False,
        "trade_authorized": False, "scheduler_enabled": False,
        "worker_enabled": False, "file_writes": 0, "new_cost_brl": 0,
        "research_only": True,
    }


def inspect_bls_cpi_u_v1_bytes_lab(
    *, original_bytes: Any, captured_at_utc: Any,
    server_date_at_utc: Any,
) -> dict[str, Any]:
    """Parse only an original-byte CPI-U *index* receipt, not a YoY forecast.

    Both timestamps and original bytes are supplied by the caller; this is
    a structural local check and never an independent BLS authentication.
    """
    out = _blocked("INVALID_BYTES_OR_CAPTURE_CLOCK")
    captured, server = _utc(captured_at_utc), _utc(server_date_at_utc)
    if (captured is None or server is None
            or abs((captured - server).total_seconds()) > 180
            or not isinstance(original_bytes, bytes)
            or not 0 < len(original_bytes) <= MAX_BODY_BYTES):
        return out
    try:
        parsed = json.loads(
            original_bytes.decode("utf-8", "strict"),
            object_pairs_hook=_unique_json_object,
            parse_constant=lambda _: (_ for _ in ()).throw(ValueError("non-finite JSON")),
        )
    except (UnicodeError, ValueError, TypeError, RecursionError):
        out["reason"] = "MALFORMED_OR_AMBIGUOUS_PROVIDER_JSON"
        return out
    if (not isinstance(parsed, dict)
            or parsed.get("status") != "REQUEST_SUCCEEDED"
            or not isinstance(parsed.get("Results"), list)
            or len(parsed["Results"]) != 1
            or not isinstance(parsed["Results"][0], dict)
            or not isinstance(parsed["Results"][0].get("series"), list)
            or len(parsed["Results"][0]["series"]) != 1):
        out["reason"] = "PROVIDER_STATUS_OR_SINGLE_SERIES_SHAPE_INVALID"
        return out
    series = parsed["Results"][0]["series"][0]
    if (not isinstance(series, dict) or series.get("seriesID") != SERIES
            or not isinstance(series.get("data"), list)
            or not 1 <= len(series["data"]) <= MAX_OBSERVATIONS):
        out["reason"] = "WRONG_SERIES_OR_INVALID_DATA_COUNT"
        return out
    points = {}
    for row in series["data"]:
        if not isinstance(row, dict):
            out["reason"] = "INVALID_MONTHLY_OBSERVATION"
            return out
        yr, mon, value = row.get("year"), row.get("period"), row.get("value")
        if (not isinstance(yr, str) or YEAR.fullmatch(yr) is None
                or not isinstance(mon, str) or PERIOD.fullmatch(mon) is None
                or not isinstance(value, str) or VALUE.fullmatch(value) is None):
            out["reason"] = "INVALID_MONTHLY_OBSERVATION"
            return out
        try:
            level = Decimal(value)
            if not level.is_finite() or not Decimal("0") < level < Decimal("10000000"):
                out["reason"] = "INVALID_MONTHLY_OBSERVATION"
                return out
        except InvalidOperation:
            out["reason"] = "INVALID_MONTHLY_OBSERVATION"
            return out
        key = yr + "-" + mon[1:]
        if key in points:
            out["reason"] = "DUPLICATE_MONTHLY_VINTAGE_IN_RESPONSE"
            return out
        points[key] = value
    latest = max(points)
    # A source captured this month cannot include a genuine observation from
    # a future month. This does not prove official first-availability timing.
    if latest > f"{captured.year:04d}-{captured.month:02d}":
        out["reason"] = "FUTURE_OBSERVATION_MONTH_LOOKAHEAD"
        return out
    out.update({
        "state": "LAB_BLS_CPI_U_INDEX_BYTES_INSPECTED_UNATTESTED",
        "reason": "BLS_INDEX_BYTES_LOCALLY_PARSED_RELEASE_TIME_UNVERIFIED",
        "last_monthly_period_documentary": latest,
        "last_index_level_documentary": points[latest],
        "monthly_observation_count": len(points),
        "captured_at_utc": captured.isoformat(),
        "server_date_utc_claim": server.isoformat(),
        "source_sha256": sha256(original_bytes).hexdigest(),
        "original_source_bytes_in_memory": original_bytes,
        "original_source_bytes_retained_in_result": True,
    })
    return out


def fetch_bls_cpi_u_v1_readonly_lab() -> dict[str, Any]:
    """At most one HTTPS GET, fixed URL, no redirects, no file writes."""
    opener = build_opener(_NoRedirect())
    request = Request(URL, method="GET", headers={
        "Accept": "application/json",
        "Accept-Encoding": "identity",
        "Cache-Control": "no-store",
        "User-Agent": "AtlasQuant-Trader-ReadOnly-CPI-LAB",
    })
    try:
        with opener.open(request, timeout=10) as response:
            if response.getcode() != 200:
                return _blocked("BLS_API_NON_200", attempted_http=1)
            if "json" not in response.headers.get("Content-Type", "").lower():
                return _blocked("BLS_API_NON_JSON_CONTENT_TYPE", attempted_http=1)
            server_header = response.headers.get("Date")
            body = response.read(MAX_BODY_BYTES + 1)
            captured = datetime.now(timezone.utc)
    except (HTTPError, URLError, OSError, TimeoutError, ValueError):
        return _blocked("BLS_API_HTTPS_FETCH_FAILED_NO_FALLBACK", attempted_http=1)
    if len(body) > MAX_BODY_BYTES:
        return _blocked("BLS_API_BODY_TOO_LARGE", attempted_http=1)
    try:
        server = _utc(parsedate_to_datetime(server_header))
    except (ValueError, TypeError, OverflowError):
        server = None
    inspected = inspect_bls_cpi_u_v1_bytes_lab(
        original_bytes=body, captured_at_utc=captured,
        server_date_at_utc=server,
    )
    inspected["http_requests"] = 1
    if inspected["state"] == "LAB_BLS_CPI_U_INDEX_BYTES_INSPECTED_UNATTESTED":
        inspected["http_get_completed"] = True
        inspected["reason"] = "BLS_HTTPS_GET_COMPLETED_NOT_ORIGINAL_RELEASE_ATTESTATION"
    return inspected


__all__ = (
    "SCHEMA", "SERIES", "URL",
    "inspect_bls_cpi_u_v1_bytes_lab", "fetch_bls_cpi_u_v1_readonly_lab",
)
