"""Opt-in ONE-SHOT BLS SA CPI-U API capture with raw archive and receipt.

No import-time HTTP, retries, timers, scheduler, workers, trades or alerts.
The BLS API's *current* revised index is not an immutable first-print release.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import ssl
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import HTTPSHandler, Request, build_opener
from zipfile import ZIP_STORED, ZipFile

from atlasquant_trader_bls_cpi_sa_previous_bridge_lab import (
    API_URL, MAX_BYTES, SERIES_ID, parse_current_bls_cpi_sa_index_lab,
)
from atlasquant_trader_g8_single_https_probe_lab import _RejectRedirect

SCHEMA = "ATLASQUANT_TRADER_BLS_CPI_SA_SINGLE_RAW_CAPTURE_LAB_V1"


def _blocked(reason: str, *, attempted: bool = False) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_BLS_SA_CAPTURE_BLOCKED", "reason": reason,
        "url": API_URL, "series_id": SERIES_ID,
        "http_requests": int(attempted), "file_writes": 0,
        "response_sha256": None, "response_bytes": None,
        "collector_started_utc": None, "collector_finished_utc": None,
        "raw_archive_path": None, "raw_archive_sha256": None,
        "raw_archive_bytes": None,
        "latest_index_month": None,
        "latest_mom_sa_percent_derived_documentary": None,
        "tls_system_ca_verification_requested": False,
        "no_redirects_requested": False,
        "current_api_response_seen": False,
        "first_publication_timestamp_independently_verified": False,
        "bls_first_print_actual_authenticated": False,
        "consensus_before_release_authenticated": False,
        "published_headline_mom_verified": False,
        "api_history_is_not_a_frozen_vintage": True,
        "fx_bias": None, "index_bias": None,
        "calibrated_direction_probability": None,
        "operational_bias": "AGUARDAR",
        "trade_authorized": False, "publishable": False,
        "live_alert_allowed": False, "worker_enabled": False,
        "scheduler_enabled": False, "new_cost_brl": 0, "research_only": True,
    }


def capture_current_bls_sa_cpi_once_lab(
    *, manually_authorized: bool = False, timeout_seconds: int = 8,
    archive_dir: str | Path | None = None,
) -> dict[str, Any]:
    """One GET to fixed official API URL, no retries; archive only if opted in.

    'manually_authorized' means the caller intentionally permits this GET; it
    does not authorize a recurring job, account access, or any trade decision.
    """
    if manually_authorized is not True:
        return _blocked("SINGLE_HTTP_REQUEST_NOT_AUTHORIZED")
    if type(timeout_seconds) is not int or not 1 <= timeout_seconds <= 15:
        return _blocked("TIMEOUT_INVALID")
    if archive_dir is not None:
        try:
            path = Path(archive_dir)
            permitted_path = not path.is_symlink() and path.is_dir()
        except (TypeError, ValueError, OSError):
            permitted_path = False
        if not permitted_path:
            return _blocked("ARCHIVE_DIRECTORY_MUST_PREEXIST_AND_NOT_BE_A_SYMLINK")

    request = Request(API_URL, method="GET", headers={
        "Accept": "application/json", "Accept-Encoding": "identity",
        "User-Agent": "AtlasQuant-Trader-LAB-one-shot-BLS-SA-CPI/1.0",
    })
    started = datetime.now(timezone.utc)
    try:
        opener = build_opener(HTTPSHandler(context=ssl.create_default_context()),
                              _RejectRedirect())
        with opener.open(request, timeout=timeout_seconds) as reply:
            if reply.status != 200 or reply.geturl() != API_URL:
                return _blocked("UNEXPECTED_STATUS_OR_REDIRECT", attempted=True)
            content_type = str(reply.headers.get("Content-Type", "")).split(";")[0].strip().lower()
            encoding = str(reply.headers.get("Content-Encoding", "identity")).strip().lower()
            if content_type != "application/json" or encoding != "identity":
                return _blocked("UNEXPECTED_MEDIA_TYPE_OR_ENCODING", attempted=True)
            raw = reply.read(MAX_BYTES + 1)
    except (HTTPError, URLError, OSError, ssl.SSLError, TimeoutError,
            TypeError, ValueError) as exc:
        return _blocked("HTTPS_FAILED_" + type(exc).__name__, attempted=True)
    finished = datetime.now(timezone.utc)

    parsed = parse_current_bls_cpi_sa_index_lab(
        raw, observed_at_utc=finished.replace(microsecond=0),
    )
    if parsed["state"] != "LAB_BLS_SA_INDEX_CURRENT_RESPONSE_UNVERIFIED":
        out = _blocked("BLS_RESPONSE_PARSE_FAILED_" + parsed["reason"], attempted=True)
        out["current_api_response_seen"] = True
        return out

    out = _blocked("MUTABLE_INDEX_API_RESPONSE_NOT_FIRST_PRINT", attempted=True)
    out.update({
        "state": "LAB_BLS_SA_SINGLE_HTTP_RESPONSE_QUARANTINED",
        "response_sha256": sha256(raw).hexdigest(),
        "response_bytes": len(raw),
        "collector_started_utc": started.isoformat(),
        "collector_finished_utc": finished.isoformat(),
        "latest_index_month": parsed["latest_available_index_month"],
        "latest_mom_sa_percent_derived_documentary": parsed[
            "latest_available_mom_sa_percent_derived"],
        "tls_system_ca_verification_requested": True,
        "no_redirects_requested": True,
        "current_api_response_seen": True,
    })
    if archive_dir is None:
        return out

    directory = Path(archive_dir)
    stamp = finished.strftime("%Y%m%dT%H%M%S%fZ")
    filename = "bls_cpi_sa_" + stamp + "_" + sha256(raw).hexdigest()[:12] + ".zip"
    target = directory / filename
    receipt = {
        "schema": SCHEMA,
        "source_url": API_URL,
        "series_id": SERIES_ID,
        "request_method": "GET",
        "collector_started_utc": started.isoformat(),
        "collector_finished_utc": finished.isoformat(),
        "raw_response_sha256": sha256(raw).hexdigest(),
        "raw_response_bytes": len(raw),
        "latest_index_month_documentary": parsed["latest_available_index_month"],
        "latest_derived_mom_sa_documentary": parsed[
            "latest_available_mom_sa_percent_derived"],
        "response_bytes_authenticated_as_original_BLS_release": False,
        "bls_original_release_first_print_authenticated": False,
        "source_is_current_mutable_API": True,
        "do_not_use_as_forecast_or_trade": True,
    }
    try:
        # Zip STORED preserves the exact raw JSON member without modification.
        # mode=x refuses overwrite even in a repeat call with same name.
        with ZipFile(target, mode="x", compression=ZIP_STORED) as archive:
            archive.writestr("response.json", raw)
            archive.writestr("receipt.json", json.dumps(
                receipt, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8"))
        zip_bytes = target.read_bytes()
    except (OSError, RuntimeError, ValueError, TypeError):
        return _blocked("FAILED_TO_ARCHIVE_RAW_RESPONSE", attempted=True)
    out.update({
        "state": "LAB_BLS_SA_RAW_RESPONSE_ARCHIVED_UNATTESTED",
        "raw_archive_path": str(target),
        "raw_archive_sha256": sha256(zip_bytes).hexdigest(),
        "raw_archive_bytes": len(zip_bytes),
        "file_writes": 1,
    })
    return out


__all__ = ["SCHEMA", "capture_current_bls_sa_cpi_once_lab"]
