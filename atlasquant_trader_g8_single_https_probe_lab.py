"""One-shot manual HTTPS observation for one G8 DOCUMENTATION lead (LAB).

Never scheduled. No import-time network, background work or cache writes.
A verified TLS connection to a web host is NOT proof that any statistic
inside a live landing page is official, historical, or available ex ante.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import ssl
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import (
    HTTPRedirectHandler, HTTPSHandler, Request, build_opener,
)

from atlasquant_trader_g8_official_source_receipt_lab import SOURCES, _document_url

SCHEMA = "ATLASQUANT_TRADER_G8_MANUAL_HTTPS_OBSERVATION_LAB_V1"
MAX_BODY_BYTES = 256 * 1024
_ALLOWED_MEDIA_TYPES = frozenset({
    "text/html", "application/xhtml+xml", "text/plain", "text/csv",
    "application/json", "application/xml", "text/xml", "application/pdf",
    "application/octet-stream",
})


class _RejectRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # A redirected destination would have a new origin/custody chain.
        return None


def _blocked(reason: str, *, request_attempted: bool = False) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_HTTP_OBSERVATION_BLOCKED",
        "reason": reason, "external_http_requests": int(request_attempted),
        "manual_single_request_only": True,
        "http_endpoint_observed_this_session": False,
        "original_publisher_payload_authenticated": False,
        "publication_time_independently_verified": False,
        "historical_point_in_time_availability_verified": False,
        "economic_indicator_value_extracted": False,
        "can_feed_live_radar": False, "operational_bias": "AGUARDAR",
        "trade_authorized": False, "publishable": False,
        "worker_enabled": False, "scheduler_enabled": False,
        "new_cost_brl": 0,
    }


def probe_g8_documentation_lead_once_lab(
    source_id: Any, *, manually_authorized: bool = False,
    timeout_seconds: int = 8,
) -> dict[str, Any]:
    """Request one EXACT registered landing URL, never follow redirects.

    Only a foreground caller can opt in. Time of observation comes from
    the computer clock; TLS verification is requested from the OS trust
    store. Server response headers and publication dates remain UNTRUSTED.
    Nothing is stored or parsed as a release, market signal or forecast.
    """
    if manually_authorized is not True:
        return _blocked("MANUAL_HTTP_OPT_IN_REQUIRED")
    if not isinstance(source_id, str) or source_id not in SOURCES:
        return _blocked("SOURCE_LEAD_NOT_IN_G8_CATALOG")
    if (isinstance(timeout_seconds, bool)
            or not isinstance(timeout_seconds, int)
            or not 1 <= timeout_seconds <= 15):
        return _blocked("UNBOUNDED_HTTP_TIMEOUT")

    lead = SOURCES[source_id]
    url = lead["documentation_url"]
    if not _document_url(url, url):
        return _blocked("SOURCE_URL_NOT_ALLOWLISTED")
    req = Request(
        url, method="GET",
        headers={
            "User-Agent": "AtlasQuant-Trader-LAB-single-manual-document-check/1.0",
            "Accept": "text/html,application/xhtml+xml,text/plain,application/json,"
                      "application/xml,text/xml,text/csv,application/pdf",
            "Accept-Encoding": "identity",
        },
    )
    try:
        # No external dependencies, urllib default CA verification.
        context = ssl.create_default_context()
        opener = build_opener(HTTPSHandler(context=context), _RejectRedirect())
        with opener.open(req, timeout=timeout_seconds) as response:
            if response.geturl() != url:
                return _blocked("HTTP_FINAL_URL_DIFFERS_FROM_ALLOWLIST", request_attempted=True)
            if response.status != 200:
                return _blocked("HTTP_STATUS_NOT_200", request_attempted=True)
            headers = response.headers
            media_type = str(headers.get("Content-Type", "")).split(";")[0].strip().lower()
            if media_type not in _ALLOWED_MEDIA_TYPES:
                return _blocked("UNSUPPORTED_RESPONSE_MEDIA_TYPE", request_attempted=True)
            if str(headers.get("Content-Encoding", "identity")).strip().lower() != "identity":
                return _blocked("ENCODED_HTTP_BODY_NOT_SUPPORTED", request_attempted=True)
            raw_length = headers.get("Content-Length")
            if raw_length is not None:
                try:
                    declared_length = int(raw_length)
                except (ValueError, TypeError, OverflowError):
                    return _blocked("INVALID_HTTP_CONTENT_LENGTH", request_attempted=True)
                if declared_length <= 0 or declared_length > MAX_BODY_BYTES:
                    return _blocked("HTTP_BODY_TOO_LARGE_OR_EMPTY", request_attempted=True)
            # Bound allocation even if Content-Length is absent or deceptive.
            body = response.read(MAX_BODY_BYTES + 1)
            if not isinstance(body, bytes) or not 1 <= len(body) <= MAX_BODY_BYTES:
                return _blocked("HTTP_BODY_TOO_LARGE_OR_EMPTY", request_attempted=True)
            if raw_length is not None and declared_length != len(body):
                return _blocked("HTTP_CONTENT_LENGTH_MISMATCH", request_attempted=True)
            server_date = str(headers.get("Date", ""))[:120]
    except (HTTPError, URLError, OSError, ssl.SSLError, TimeoutError,
            ValueError, TypeError) as exc:
        return _blocked("HTTPS_REQUEST_FAILED_" + type(exc).__name__, request_attempted=True)

    result = _blocked("DOCUMENTATION_PAGE_NOT_A_RELEASE_OR_HISTORICAL_PROOF")
    result.update({
        "state": "LAB_CURRENT_OFFICIAL_HOST_HTTP_RESPONSE_OBSERVED",
        "source_id": source_id,
        "currency": lead["currency"],
        "family": lead["family"],
        "catalogue_documentation_url": url,
        "http_status": 200, "content_type": media_type,
        "observed_at_local_system_utc": datetime.now(timezone.utc).isoformat(),
        "http_response_content_sha256": sha256(body).hexdigest(),
        "http_response_bytes": len(body),
        "server_date_header_unverified": server_date,
        "tls_standard_ca_validation_requested": True,
        "http_redirects_followed": False,
        "external_http_requests": 1,
        "http_endpoint_observed_this_session": True,
        "not_an_authenticated_economic_release": True,
        "historical_point_in_time_availability_verified": False,
        "notice": (
            "Uma pagina HTTPS consultada AGORA nao prova a divulgacao "
            "de indicadores nem sua disponibilidade no instante de um "
            "vies antigo. Nao alimentar Radar ou ordens."
        ),
    })
    return result


__all__ = ["SCHEMA", "MAX_BODY_BYTES", "probe_g8_documentation_lead_once_lab"]
