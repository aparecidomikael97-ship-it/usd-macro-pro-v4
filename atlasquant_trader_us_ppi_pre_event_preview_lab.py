"""Read an AM12-captured pre-event TD Economics PPI consensus HTML snapshot.

Offline LAB only. Calendar and issuer schedule are independently separate;
local HTTP/clock assertions are *not* a publisher-signed timestamp or a
licence to redistribute. Never output a market bias or trading order.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from email.utils import parsedate_to_datetime
from hashlib import sha256
from html.parser import HTMLParser
import re
from typing import Any

SCHEMA = "ATLASQUANT_TRADER_US_PPI_OCT2026_PRE_EVENT_SNAPSHOT_LAB_V1"
URL = "https://economics.td.com/domains/economics.td.com/documents/reports/bottom-line/tables/2026-11-06/upcoming.htm"
BLS_SCHEDULE_URL = "https://www.bls.gov/schedule/2026/11_sched_list.htm"
EVENT_RELEASE_UTC = datetime(2026, 11, 13, 13, 30, tzinfo=timezone.utc)
MAX_HTML_BYTES = 256 * 1024
HEX = re.compile(r"[0-9a-f]{64}\Z")
PCT = re.compile(r"(?:0|[1-9][0-9]?)(?:\.[0-9]{1,3})?\Z")
EXPECTED_HEADER = (
    "Release Date", "Time*", "", "Economic Indicator/Event",
    "Data for Period", "Units", "Consensus Forecast", "Last Period",
)
EXPECTED_ROWS = {
    "headline": "PPI Final Demand",
    "core": "PPI Ex Food and Energy",
}


@dataclass(frozen=True)
class LocalCaptureClaim:
    source_url: str
    http_status: int
    content_type: str
    started_at_utc: datetime
    finished_at_utc: datetime
    server_date_http: str
    last_modified_http: str
    content_length_http: int
    body_sha256: str


class _Tables(HTMLParser):
    """Capture actual TD calendar <tr>/<td> cell boundaries, not text fragments."""
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.rows: list[tuple[str, ...]] = []
        self.row: list[str] | None = None
        self.cell: list[str] | None = None
        self.hidden = 0
        self.title_chunks: list[str] = []

    def handle_starttag(self, tag: str, attrs: list) -> None:
        tag = tag.lower()
        if tag in ("script", "style", "noscript", "svg"):
            self.hidden += 1
        if self.hidden:
            return
        if tag == "tr":
            if self.row is not None:
                raise ValueError("NESTED_ROW")
            self.row = []
        elif tag in ("td", "th") and self.row is not None:
            if self.cell is not None:
                raise ValueError("NESTED_CELL")
            self.cell = []

    def handle_data(self, data: str) -> None:
        if self.hidden:
            return
        if self.cell is not None:
            self.cell.append(data)
        else:
            self.title_chunks.append(data)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in ("script", "style", "noscript", "svg") and self.hidden:
            self.hidden -= 1
            return
        if self.hidden:
            return
        if tag in ("td", "th") and self.cell is not None:
            if self.row is None:
                raise ValueError("ORPHAN_CELL")
            self.row.append(" ".join(" ".join(self.cell).split()))
            self.cell = None
        elif tag == "tr" and self.row is not None:
            if self.cell is not None:
                raise ValueError("UNCLOSED_CELL")
            self.rows.append(tuple(self.row))
            self.row = None


def _utc(v: Any) -> datetime | None:
    if not isinstance(v, datetime) or v.tzinfo is None or v.utcoffset() is None:
        return None
    return v.astimezone(timezone.utc)


def _http_date(v: Any) -> datetime | None:
    if not isinstance(v, str) or len(v) > 65:
        return None
    try:
        return _utc(parsedate_to_datetime(v))
    except (TypeError, ValueError, IndexError, OverflowError):
        return None


def _pct(text: str) -> str | None:
    if not isinstance(text, str) or PCT.fullmatch(text) is None:
        return None
    try:
        v = Decimal(text)
    except InvalidOperation:
        return None
    return str(v) if v.is_finite() and 0 <= v < 20 else None


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "state": "LAB_PPI_PRE_EVENT_BLOCKED",
        "reason": reason,
        "source_url": URL,
        "issuer_schedule_url": BLS_SCHEDULE_URL,
        "event_release_utc": EVENT_RELEASE_UTC.isoformat(),
        "source_body_sha256": None,
        "capture_finished_utc_claim": None,
        "publisher_last_modified_http_claim": None,
        "headline_consensus_mom_pct": None,
        "core_consensus_mom_pct": None,
        "headline_previous_mom_pct": None,
        "core_previous_mom_pct": None,
        "local_pre_event_http_capture_claim_checks_pass": False,
        "source_provenance_independently_attested": False,
        "publisher_first_available_instant_attested": False,
        "analyst_poll_membership_and_methodology_verified": False,
        "historical_backtest_point_in_time_attested": False,
        "ready_for_later_retrospective_comparison_lab": False,
        "official_actual_available": None,
        "ppi_surprise": None,
        "usd_bias": None,
        "eurusd_bias": None,
        "operational_bias": "AGUARDAR",
        "calibrated_probability": None,
        "trade_authorized": False,
        "publishable": False,
        "worker_enabled": False,
        "scheduler_enabled": False,
        "http_requests": 0,
        "new_cost_brl": 0,
    }


def inspect_ppi_pre_event_snapshot_lab(
    *, raw_html: Any, receipt: Any, as_of_utc: Any,
) -> dict[str, Any]:
    """Audit one claimed earlier local HTTP snapshot, not a tradable forecast."""
    now = _utc(as_of_utc)
    if now is None or not isinstance(receipt, LocalCaptureClaim):
        return _blocked("INVALID_CLOCK_OR_CAPTURE_CLAIM")
    start, end = _utc(receipt.started_at_utc), _utc(receipt.finished_at_utc)
    server_date, last_modified = (_http_date(receipt.server_date_http),
                                  _http_date(receipt.last_modified_http))
    if (receipt.source_url != URL or type(receipt.http_status) is not int
            or receipt.http_status != 200
            or not isinstance(receipt.content_type, str)
            or receipt.content_type.split(";")[0].strip().lower() != "text/html"
            or type(receipt.content_length_http) is not int
            or start is None or end is None or server_date is None
            or last_modified is None):
        return _blocked("INVALID_HTTP_STATUS_OR_SOURCE_METADATA")
    # We deliberately reject attempts to claim a snapshot from the event
    # release moment onward. This same archive may be inspected later.
    if (start < datetime(2026, 11, 6, tzinfo=timezone.utc)
            or not start <= end < EVENT_RELEASE_UTC
            or end - start > timedelta(minutes=2) or end > now
            or abs((server_date - end).total_seconds()) > 120
            or last_modified > server_date or last_modified >= EVENT_RELEASE_UTC):
        return _blocked("INVALID_OR_POST_EVENT_CAPTURE_TIMELINE")
    if (not isinstance(raw_html, bytes)
            or not 2000 <= len(raw_html) <= MAX_HTML_BYTES
            or len(raw_html) != receipt.content_length_http
            or not isinstance(receipt.body_sha256, str)
            or HEX.fullmatch(receipt.body_sha256) is None
            or sha256(raw_html).hexdigest() != receipt.body_sha256):
        return _blocked("HTML_BODY_LENGTH_OR_DIGEST_INVALID")
    try:
        # The TD Excel-export HTML is legacy Windows-1252, not UTF-8.
        html = raw_html.decode("cp1252", "strict")
        reader = _Tables()
        reader.feed(html)
        reader.close()
        if reader.row is not None or reader.cell is not None:
            return _blocked("UNCLOSED_HTML_TABLE")
    except (UnicodeError, ValueError, TypeError, OverflowError, RecursionError):
        return _blocked("INVALID_HTML_TABLE_OR_CHARSET")
    if reader.rows.count(EXPECTED_HEADER) != 1:
        return _blocked("CONSENSUS_TABLE_HEADER_NOT_EXACT")
    title = "Upcoming Economic Releases and Events: Nov 9 - 13, 2026"
    if not any(title in cell for row in reader.rows for cell in row):
        return _blocked("EXPECTED_WEEK_NOT_PRESENT")
    results: dict[str, tuple[str, str]] = {}
    for key, name in EXPECTED_ROWS.items():
        matching = [r for r in reader.rows if len(r) == 8 and r[3] == name]
        if len(matching) != 1:
            return _blocked("PPI_ROW_MISSING_OR_DUPLICATED")
        row = matching[0]
        if (row[0] != "Nov 13" or row[1] != "8:30" or row[2] != ""
                or row[4] != "Oct" or row[5] != "M/M % Chg."):
            return _blocked("PPI_DATE_PERIOD_OR_METRIC_MISMATCH")
        consensus, previous = _pct(row[6]), _pct(row[7])
        if consensus is None or previous is None:
            return _blocked("PPI_CONSENSUS_AND_PREVIOUS_INVALID")
        results[key] = (consensus, previous)
    out = _blocked("LOCAL_CAPTURE_AND_PRE_EVENT_CONSENSUS_CLAIMS_PARSED_NOT_INDEPENDENTLY_ATTESTED")
    out.update({
        "state": "LAB_PRE_EVENT_PPI_CONSENSUS_ARCHIVED_LOCAL_NO_TRADE",
        "source_body_sha256": receipt.body_sha256,
        "capture_finished_utc_claim": end.isoformat(),
        "publisher_last_modified_http_claim": last_modified.isoformat(),
        "headline_consensus_mom_pct": results["headline"][0],
        "core_consensus_mom_pct": results["core"][0],
        "headline_previous_mom_pct": results["headline"][1],
        "core_previous_mom_pct": results["core"][1],
        "local_pre_event_http_capture_claim_checks_pass": True,
        "ready_for_later_retrospective_comparison_lab": True,
    })
    return out


__all__ = ["SCHEMA", "LocalCaptureClaim", "inspect_ppi_pre_event_snapshot_lab"]