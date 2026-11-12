"""Single read-only HTTPS probe of a caller-identified G8 CPI issuer page.

No retries, persistence, credentials, redirects, schedules, app integration or
trades. A successful request now does not establish historical availability.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
import socket
import sys
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

from atlasquant_trader_g8_macro_asof_lab import _cpi_issuer_claim_host

SCHEMA = "ATLASQUANT_TRADER_G8_CPI_ONCE_HTTPS_PROBE_LAB_V1"
MAX_BODY_BYTES = 1024 * 1024
USER_AGENT = "AtlasQuant-Research-LAB/0.1 (read-only; no trading)"


class _NeverRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


@dataclass(frozen=True)
class HTTPProbeLabResult:
    report: dict[str, Any]
    body: bytes | None = None


def _blocked(reason: str, *, status: int | None = None) -> HTTPProbeLabResult:
    return HTTPProbeLabResult({
        "schema": SCHEMA, "state": "LAB_HTTPS_PROBE_BLOCKED", "reason": reason,
        "response_status": status, "source_url_claim": None,
        "final_url_observed": None, "response_date_header": None,
        "last_modified_header": None, "content_type": None,
        "body_bytes": 0, "body_sha256": None,
        "local_started_utc_claim": None, "local_finished_utc_claim": None,
        "default_tls_verification_requested": False,
        "original_publisher_bytes_at_first_release_attested": False,
        "issuer_identity_independently_attested": False,
        "source_history_point_in_time_verified": False,
        "collector_clock_independently_attested": False,
        "cpi_value_semantically_verified": False,
        "operational_bias": "AGUARDAR", "trade_authorized": False,
        "publishable": False, "scheduler_enabled": False,
        "worker_enabled": False, "file_writes": 0, "new_cost_brl": 0,
    })


def probe_g8_cpi_official_page_once_lab(
    currency: Any, source_url: Any, *, opener: Any = None,
    clock: Callable[[], datetime] | None = None,
) -> HTTPProbeLabResult:
    """Fetch at most 1 MiB in memory. `body` is returned but never written.

    `opener` and `clock` injection exists for offline deterministic tests.
    The real default opener uses normal Python TLS validation and refuses any
    HTTP redirect, including a redirect to another alleged official host.
    """
    if (not isinstance(currency, str)
            or _cpi_issuer_claim_host(currency, source_url) is None):
        return _blocked("UNAPPROVED_CPI_ISSUER_URL")
    if clock is None:
        clock = lambda: datetime.now(timezone.utc)
    using_default_opener = opener is None
    if opener is None:
        opener = build_opener(_NeverRedirect())
    start = clock()
    if not isinstance(start, datetime) or start.tzinfo is None or start.utcoffset() is None:
        return _blocked("INVALID_COLLECTOR_CLOCK")
    start = start.astimezone(timezone.utc)
    try:
        request = Request(source_url, headers={"User-Agent": USER_AGENT}, method="GET")
        with opener.open(request, timeout=15) as response:
            status = response.status
            final_url = response.geturl()
            ct_raw = response.headers.get("Content-Type", "")
            content_type = ct_raw.split(";", 1)[0].strip().lower()
            date_header = response.headers.get("Date")
            modified_header = response.headers.get("Last-Modified")
            if (type(status) is not int or status != 200 or final_url != source_url):
                return _blocked("STATUS_OR_REDIRECT_NOT_ACCEPTED", status=status)
            if content_type not in ("text/html", "application/pdf"):
                return _blocked("UNSUPPORTED_CPI_DOCUMENT_CONTENT_TYPE", status=status)
            body = response.read(MAX_BODY_BYTES + 1)
    except HTTPError as exc:
        return _blocked("ISSUER_HTTP_STATUS_NOT_200_NO_BYPASS", status=exc.code)
    except (URLError, TimeoutError, socket.timeout, OSError, ValueError):
        return _blocked("ISSUER_REQUEST_FAILED_NO_RETRY")
    finish = clock()
    if (not isinstance(finish, datetime) or finish.tzinfo is None
            or finish.utcoffset() is None):
        return _blocked("INVALID_COLLECTOR_CLOCK")
    finish = finish.astimezone(timezone.utc)
    if (finish < start or (finish - start).total_seconds() > 60
            or not isinstance(body, bytes) or not 1 <= len(body) <= MAX_BODY_BYTES):
        return _blocked("CAPTURE_WINDOW_OR_SIZE_INVALID")
    report = _blocked("UNSET").report
    report.update({
        "state": "LAB_CURRENT_ISSUER_PAGE_HTTP_BYTES_CAPTURED_UNATTESTED",
        "reason": "CURRENT_BYTES_ONLY_NOT_ORIGINAL_RELEASE_VINTAGE",
        "response_status": 200, "source_url_claim": source_url,
        "final_url_observed": final_url, "response_date_header": date_header,
        "last_modified_header": modified_header,
        "content_type": content_type, "body_bytes": len(body),
        "body_sha256": sha256(body).hexdigest(),
        "local_started_utc_claim": start.isoformat(),
        "local_finished_utc_claim": finish.isoformat(),
        "default_tls_verification_requested": using_default_opener,
    })
    return HTTPProbeLabResult(report, body)


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("Usage: python atlasquant_trader_g8_cpi_http_probe_lab.py USD https://official/press-release")
        return 2
    result = probe_g8_cpi_official_page_once_lab(argv[1], argv[2])
    print(json.dumps(result.report, ensure_ascii=False, sort_keys=True))
    return 0 if result.body is not None else 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))


__all__ = ["SCHEMA", "HTTPProbeLabResult", "probe_g8_cpi_official_page_once_lab"]
